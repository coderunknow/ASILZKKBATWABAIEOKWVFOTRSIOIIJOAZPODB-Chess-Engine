#!/usr/bin/env python3
"""Rating estimator implementing docs/RATING_PROTOCOL.md Amendment §9 exactly.

Subcommands:
  batch          per-batch estimate from raw games.jsonl files (one per anchor)
  combine        combine Batch A + Batch B (shared calibration added ONCE)
  gate           FAIL-CLOSED gate: recompute everything from raw evidence and
                 pass only if all three lower CI bounds are STRICTLY > threshold
  control        null controls (anchor-vs-anchor +/-75 Elo; self-match ~ 0.5)

Method (protocol §9.6-9.8):
  * Opening-cluster bootstrap, B >= 10,000 replicates, fixed seed. In each
    replicate the opening clusters are resampled ONCE and the SAME draw is
    applied to every anchor (joint resampling -> correlated anchor errors).
  * d_a = -400*log10(1/s_a - 1) (Flawless - anchor, Elo). Boundary scores
    (s=0 or 1) are non-finite: the anchor is INELIGIBLE for gate evidence.
  * sigma_matched,a = SD of the joint bootstrap replicates of d_a (a standard
    deviation, NOT a CI half-width). Published anchor errors are converted to
    SD scale by their stated convention (sd/se as-is; ci95/1.96; ci90/1.645;
    ci99/2.576). sigma_a^2 = sigma_matched,a^2 + eps_a^2.
  * Anchor combination by GLS over the full covariance: Sigma_m = Cov(D) from
    the BxA joint replicate matrix, Sigma_c = diag(eps_a^2), Sigma = Sigma_m +
    Sigma_c. theta = (1' S+ (R+d)) / (1' S+ 1), Var = 1/(1' S+ 1) with pseudo-
    inverse; explicit singular handling falls back to diagonal WLS with a
    printed warning. Match-only and match+calibration intervals are reported
    separately (same point estimate).
  * Batch combination: match-noise inverse-variance pooled; the calibration
    component shared by the identical anchors is added ONCE:
        theta = (theta_A/v_A + theta_B/v_B)/(1/v_A + 1/v_B)
        v     = (1/v_A + 1/v_B)^-1
        c*    = sum_a (lam*w_A,a + (1-lam)*w_B,a)^2 * eps_a^2   (lam = weight of A)
        CI    = theta +/- 1.96*sqrt(v + c*)
    Calibration is never inverse-variance-pooled away.

No rating produced here is an official CCRL/CEGT rating. Gate evidence requires
the full preregistered protocol; this tool only computes what the evidence says.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict

ERROR_CONVENTION_TO_SD = {"sd": 1.0, "se": 1.0, "ci95": 1.96, "ci90": 1.645, "ci99": 2.576}
Z95 = 1.959963984540054  # two-sided 95% normal quantile (unrounded)


class EvidenceError(SystemExit):
    """Fail-closed: missing/invalid evidence never yields a number."""


# ---------------------------------------------------------------------------
# Loading and validation (fail closed)
# ---------------------------------------------------------------------------


def load_games(path: str, focus: str | None) -> list[dict]:
    games = []
    try:
        fh = open(path)
    except OSError as e:
        raise EvidenceError(f"cannot read games file {path!r}: {e}")
    with fh as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            g = json.loads(line)
            # Only counted, adjudicated games ever enter statistics.
            if g.get("engine_error") or g.get("counted") is False:
                continue
            if g.get("result") not in ("1-0", "0-1", "1/2-1/2"):
                continue
            if focus is not None and focus not in (g.get("white"), g.get("black")):
                raise EvidenceError(f"{path}:{ln}: focus engine {focus!r} not in game")
            games.append(g)
    return games


def score_of(result: str, perspective: str) -> float:
    if result == "1/2-1/2":
        return 0.5
    if perspective == "white":
        return 1.0 if result == "1-0" else 0.0
    return 1.0 if result == "0-1" else 0.0


def focus_scores_by_opening(games: list[dict], focus: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for g in games:
        if g["white"] == focus:
            out[g["opening"]].append(score_of(g["result"], "white"))
        else:
            out[g["opening"]].append(score_of(g["result"], "black"))
    return dict(out)


def elo_from_score(s: float) -> float:
    """Logistic Elo diff; s must be interior. Boundary handled by callers."""
    if s <= 0.0 or s >= 1.0:
        return math.inf if s >= 1.0 else -math.inf
    return -400.0 * math.log10(1.0 / s - 1.0)


# ---------------------------------------------------------------------------
# Small dense matrix helpers (A x A, A <= ~6: anchors)
# ---------------------------------------------------------------------------


def mat_inverse(m: list[list[float]]) -> list[list[float]] | None:
    n = len(m)
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(m)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot][col]) < 1e-12:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        p = aug[col][col]
        aug[col] = [x / p for x in aug[col]]
        for r in range(n):
            if r != col and aug[r][col] != 0.0:
                f = aug[r][col]
                aug[r] = [x - f * y for x, y in zip(aug[r], aug[col])]
    inv = [row[n:] for row in aug]
    # sanity: inverse must reconstruct identity
    for i in range(n):
        for j in range(n):
            got = sum(m[i][k] * inv[k][j] for k in range(n))
            if abs(got - (1.0 if i == j else 0.0)) > 1e-6:
                return None
    return inv


def mat_vec(m: list[list[float]], v: list[float]) -> list[float]:
    return [sum(row[j] * v[j] for j in range(len(v))) for row in m]


# ---------------------------------------------------------------------------
# Joint opening-cluster bootstrap
# ---------------------------------------------------------------------------


def joint_bootstrap(anchors: list[dict], n_boot: int, seed: int) -> dict:
    """anchors: [{name, published_elo, eps_sd, clusters: {opening: [scores]}}]

    Returns D (B x A replicate matrix of d_a), plus per-anchor observed values.
    Opening clusters are resampled ONCE per replicate, same draw for all anchors.
    """
    names = [a["name"] for a in anchors]
    # Common cluster universe: every anchor must cover the same openings.
    opening_sets = [set(a["clusters"]) for a in anchors]
    common = set.intersection(*opening_sets) if opening_sets else set()
    if len(common) != len(opening_sets[0]):
        missing = set.union(*opening_sets) - common
        raise EvidenceError(f"anchors do not share identical opening suites; divergent: {sorted(missing)[:5]}")
    openings = sorted(common)
    n = len(openings)
    if n < 2:
        raise EvidenceError("need >= 2 opening clusters for a clustered bootstrap")

    # Per-anchor per-opening score sums and game counts.
    sums = []
    ns = []
    for a in anchors:
        s_row, n_row = [], []
        for op in openings:
            sc = a["clusters"][op]
            s_row.append(sum(sc))
            n_row.append(len(sc))
        sums.append(s_row)
        ns.append(n_row)

    def d_of(a_idx: int, idxs: list[int]) -> float:
        ts = sum(sums[a_idx][i] for i in idxs)
        tn = sum(ns[a_idx][i] for i in idxs)
        return elo_from_score(ts / tn) if tn else math.nan

    observed = [d_of(i, list(range(n))) for i in range(len(anchors))]
    rng = random.Random(seed)
    D: list[list[float]] = []
    for _ in range(n_boot):
        idxs = [rng.randrange(n) for _ in range(n)]
        row = [d_of(i, idxs) for i in range(len(anchors))]
        D.append(row)
    # Boundary replicates (score 0/1 in a resample) are non-finite; a replicates
    # set with non-finite entries cannot support the gate -> fail closed.
    for b, row in enumerate(D):
        for v in row:
            if not math.isfinite(v):
                raise EvidenceError(
                    f"bootstrap replicate {b} hit a boundary score (non-finite Elo); "
                    f"more games or nearer anchors required (protocol §9.4)"
                )
    return {"names": names, "D": D, "observed": observed, "openings": openings}


def col_means_cov(D: list[list[float]]) -> tuple[list[float], list[list[float]]]:
    B = len(D)
    A = len(D[0])
    # math.fsum: exact, version-stable summation — bootstrap covariances must not
    # depend on interpreter float-accumulation behavior (reproducibility).
    means = [math.fsum(D[b][a] for b in range(B)) / B for a in range(A)]
    cov = [[0.0] * A for _ in range(A)]
    for i in range(A):
        for j in range(A):
            cov[i][j] = math.fsum(
                (D[b][i] - means[i]) * (D[b][j] - means[j]) for b in range(B)
            ) / (B - 1)
    return means, cov


# ---------------------------------------------------------------------------
# GLS estimation
# ---------------------------------------------------------------------------


def gls(suma: list[list[float]], y: list[float]) -> tuple[list[float], list[list[float]], str]:
    """Return (weights w with sum 1, inverse used, mode) for theta = w . y.

    mode = 'gls' or 'diagonal-wls-fallback' (printed warning by caller).
    """
    A = len(y)
    inv = mat_inverse(suma)
    if inv is not None:
        one = [1.0] * A
        iv1 = mat_vec(inv, one)
        denom = sum(iv1)
        if denom > 0:
            w = [x / denom for x in iv1]
            return w, inv, "gls"
    # Degenerate: documented fallback to diagonal WLS (§9.7).
    diag = [suma[i][i] for i in range(A)]
    if any(d <= 0 for d in diag):
        raise EvidenceError("degenerate covariance: non-positive diagonal, cannot estimate")
    w_raw = [1.0 / d for d in diag]
    s = sum(w_raw)
    w = [x / s for x in w_raw]
    inv_diag = [[0.0] * A for _ in range(A)]
    for i in range(A):
        inv_diag[i][i] = 1.0 / diag[i]
    return w, inv_diag, "diagonal-wls-fallback"


def eps_sd_from_entry(entry: dict) -> float:
    conv = str(entry.get("error_convention", "")).lower()
    if conv not in ERROR_CONVENTION_TO_SD:
        raise EvidenceError(f"anchor {entry.get('name')}: unknown error_convention {conv!r}")
    err = float(entry["published_error"])
    return err / ERROR_CONVENTION_TO_SD[conv]


# ---------------------------------------------------------------------------
# Batch estimate
# ---------------------------------------------------------------------------


def batch_estimate(games_by_anchor: dict[str, list[dict]], anchor_entries: list[dict],
                   focus: str, n_boot: int, seed: int) -> dict:
    anchors = []
    for entry in anchor_entries:
        name = entry["name"]
        if name not in games_by_anchor:
            raise EvidenceError(f"no games file for anchor {name!r}")
        clusters = focus_scores_by_opening(games_by_anchor[name], focus)
        if not clusters:
            raise EvidenceError(f"no counted games for anchor {name!r}")
        anchors.append({
            "name": name,
            "published_elo": float(entry["published_elo"]),
            "eps_sd": eps_sd_from_entry(entry),
            "clusters": clusters,
        })
    boot = joint_bootstrap(anchors, n_boot, seed)
    means, sigma_m = col_means_cov(boot["D"])
    A = len(anchors)
    sigma_c = [[0.0] * A for _ in range(A)]
    for i in range(A):
        sigma_c[i][i] = anchors[i]["eps_sd"] ** 2
    sigma_total = [[sigma_m[i][j] + sigma_c[i][j] for j in range(A)] for i in range(A)]
    y = [anchors[i]["published_elo"] + boot["observed"][i] for i in range(A)]

    w_total, _, mode_total = gls(sigma_total, y)
    # Match-only weights are REPORTING-ONLY. When the match covariance is
    # degenerate (e.g. zero within-opening variance), no match-only GLS exists;
    # that is recorded, never raised — the estimator's own variance uses w_total.
    inv_m = mat_inverse(sigma_m)
    if inv_m is not None:
        one = [1.0] * A
        iv1 = mat_vec(inv_m, one)
        denom = sum(iv1)
        w_match = [x / denom for x in iv1] if denom > 0 else None
        mode_match = "gls"
    else:
        w_match = None
        mode_match = "degenerate-match-covariance (match-only weights unavailable)"
    theta = sum(w_total[i] * y[i] for i in range(A))
    var_match = sum(w_total[i] * w_total[j] * sigma_m[i][j] for i in range(A) for j in range(A))
    var_cal = sum(w_total[i] * w_total[j] * sigma_c[i][j] for i in range(A) for j in range(A))
    var_total = var_match + var_cal

    per_anchor = []
    for i, a in enumerate(anchors):
        d = boot["observed"][i]
        per_anchor.append({
            "name": a["name"],
            "published_elo": a["published_elo"],
            "published_error_as_published": float(anchor_entries[i]["published_error"]),
            "error_convention": anchor_entries[i]["error_convention"],
            "eps_sd": a["eps_sd"],
            "score": elo_to_score(d),
            "d_flawless_minus_anchor": d,
            "sigma_matched": math.sqrt(sigma_m[i][i]),
            "sigma_total": math.sqrt(sigma_m[i][i] + sigma_c[i][i]),
            "abs_estimate_from_anchor": a["published_elo"] + d,
            "gate_eligible": abs(d) <= 400.0,
            "n_counted_games": sum(len(v) for v in a["clusters"].values()),
            "saturated": abs(d) > 400.0,
        })

    return {
        "focus": focus,
        "seed": seed,
        "n_boot": n_boot,
        "openings": boot["openings"],
        "n_openings": len(boot["openings"]),
        "per_anchor": per_anchor,
        "theta": theta,
        "weights": w_total,
        "weights_match_only": w_match,
        "mode_total": mode_total,
        "mode_match": mode_match,
        "var_match": var_match,
        "var_cal": var_cal,
        "var_total": var_total,
        "ci95_match_only": [theta - Z95 * math.sqrt(var_match), theta + Z95 * math.sqrt(var_match)],
        "ci95_calibrated": [theta - Z95 * math.sqrt(var_total), theta + Z95 * math.sqrt(var_total)],
        "sigma_m": sigma_m,
        "sigma_c": sigma_c,
    }


def elo_to_score(d: float) -> float:
    if not math.isfinite(d):
        return 1.0 if d > 0 else 0.0
    return 1.0 / (1.0 + 10.0 ** (-d / 400.0))


# ---------------------------------------------------------------------------
# Batch combination (§9.8): shared calibration added ONCE
# ---------------------------------------------------------------------------


def combine_batches(ba: dict, bb: dict) -> dict:
    v_a, v_b = ba["var_match"], bb["var_match"]
    if v_a <= 0 or v_b <= 0:
        raise EvidenceError("non-positive match variance in a batch")
    lam = (1.0 / v_a) / (1.0 / v_a + 1.0 / v_b)
    theta = lam * ba["theta"] + (1.0 - lam) * bb["theta"]
    v = 1.0 / (1.0 / v_a + 1.0 / v_b)
    # Shared calibration: identical anchors -> the SAME published errors appear in
    # both batch estimates. Effective per-anchor weight of the combined estimate.
    names_a = [p["name"] for p in ba["per_anchor"]]
    names_b = [p["name"] for p in bb["per_anchor"]]
    if names_a != names_b:
        raise EvidenceError("batches must use identical anchors")
    c = 0.0
    for i, p in enumerate(ba["per_anchor"]):
        w_bar = lam * ba["weights"][i] + (1.0 - lam) * bb["weights"][i]
        c += (w_bar ** 2) * (p["eps_sd"] ** 2)
    var_total = v + c
    return {
        "theta": theta,
        "weight_batch_a": lam,
        "var_match_pooled": v,
        "var_cal_shared": c,
        "var_total": var_total,
        "ci95_match_only": [theta - Z95 * math.sqrt(v), theta + Z95 * math.sqrt(v)],
        "ci95_calibrated": [theta - Z95 * math.sqrt(var_total), theta + Z95 * math.sqrt(var_total)],
        "note": "match-noise pooled inverse-variance; shared anchor calibration added once (§9.8)",
    }


# ---------------------------------------------------------------------------
# Null controls
# ---------------------------------------------------------------------------


def control_anchor_vs_anchor(games: list[dict], entry_a: dict, entry_b: dict,
                             n_boot: int, seed: int) -> dict:
    """Measured A-vs-B difference must recover R_a - R_b within +/-75 Elo."""
    a_name, b_name = entry_a["name"], entry_b["name"]
    clusters = focus_scores_by_opening(games, a_name)
    if not clusters:
        raise EvidenceError("anchor-vs-anchor control: no counted games")
    s = sum(sum(v) for v in clusters.values()) / sum(len(v) for v in clusters.values())
    d_meas = elo_from_score(s) if 0.0 < s < 1.0 else (math.inf if s >= 1.0 else -math.inf)
    d_pub = float(entry_a["published_elo"]) - float(entry_b["published_elo"])
    err = d_meas - d_pub if math.isfinite(d_meas) else math.inf
    ok = math.isfinite(err) and abs(err) <= 75.0
    return {
        "mode": "anchor-vs-anchor",
        "a": a_name, "b": b_name,
        "score_a": s, "d_measured": d_meas, "d_published": d_pub,
        "error": err, "tolerance": 75.0,
        "pass": ok,
    }


def control_self_match(games: list[dict], focus: str, n_boot: int, seed: int) -> dict:
    """Swapped-color self-match must be statistically consistent with 0.5."""
    clusters = focus_scores_by_opening(games, focus)
    if not clusters:
        raise EvidenceError("self-match control: no counted games")
    sums = [sum(v) for v in clusters.values()]
    ns = [len(v) for v in clusters.values()]
    point = sum(sums) / sum(ns)
    rng = random.Random(seed)
    n = len(sums)
    boot = []
    for _ in range(n_boot):
        idxs = [rng.randrange(n) for _ in range(n)]
        ts = sum(sums[i] for i in idxs)
        tn = sum(ns[i] for i in idxs)
        boot.append(ts / tn if tn else 0.5)
    boot.sort()
    lo = boot[int(0.025 * n_boot)]
    hi = boot[min(n_boot - 1, int(0.975 * n_boot))]
    ok = lo <= 0.5 <= hi
    return {
        "mode": "self-match",
        "focus": focus, "score": point,
        "ci95_score": [lo, hi], "pass": ok,
    }


# ---------------------------------------------------------------------------
# Gate (fail closed)
# ---------------------------------------------------------------------------


def run_gate(args) -> int:
    pool = json.load(open(args.anchor_json))
    entries = pool["engines"]
    if len(entries) < 3:
        raise EvidenceError("gate requires >= 3 verified anchors")
    focus = args.focus

    results = {}
    results["batch_a"] = batch_estimate(load_batch(args.batch_a, focus), entries, focus,
                                        args.bootstrap, args.seed)
    results["batch_b"] = batch_estimate(load_batch(args.batch_b, focus), entries, focus,
                                        args.bootstrap, args.seed + 1)
    results["combined"] = combine_batches(results["batch_a"], results["batch_b"])

    results["control_anchor_vs_anchor"] = control_anchor_vs_anchor(
        load_games(args.control_anchor, None),  # anchor-vs-anchor: neither side is focus
        next(e for e in entries if e["name"] == args.control_anchor_names[0]),
        next(e for e in entries if e["name"] == args.control_anchor_names[1]),
        args.bootstrap, args.seed,
    )
    results["control_self_match"] = control_self_match(
        load_games(args.control_self, focus), focus, args.bootstrap, args.seed)

    # ---- Decision (all conjunctive, unrounded, strictly greater) ----
    checks = []

    def need(cond: bool, msg: str) -> None:
        checks.append({"pass": bool(cond), "check": msg})

    thr = args.threshold
    for batch in ("batch_a", "batch_b", "combined"):
        lo = results[batch]["ci95_calibrated"][0]
        need(lo > thr, f"{batch}: calibrated 95% CI lower bound {lo!r} > {thr} (strict, unrounded)")
    for batch in ("batch_a", "batch_b"):
        for p in results[batch]["per_anchor"]:
            need(p["gate_eligible"],
                 f"{batch}/{p['name']}: |d| <= 400 (no saturation; d={p['d_flawless_minus_anchor']})")
            need(p["n_counted_games"] >= args.min_games,
                 f"{batch}/{p['name']}: counted games {p['n_counted_games']} >= {args.min_games}")
        need(results[batch]["mode_total"] == "gls",
             f"{batch}: GLS used (fallback would need explicit preregistered handling)")
    need(results["control_anchor_vs_anchor"]["pass"],
         f"null control anchor-vs-anchor within +/-75 (err={results['control_anchor_vs_anchor']['error']})")
    need(results["control_self_match"]["pass"],
         f"null control self-match consistent with 0.5 (CI={results['control_self_match']['ci95_score']})")
    need(len(entries) >= 3, ">= 3 eligible anchors")

    ok = all(c["pass"] for c in checks)
    out = {
        "pass": ok,
        "threshold": thr,
        "checks": checks,
        "results": results,
        "verdict": "PASS" if ok else "FAIL",
        "disclaimer": "private, CCRL/CEGT-anchored estimate — not an official rating",
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)
    for c in checks:
        print(("PASS " if c["pass"] else "FAIL ") + c["check"])
    print(f"GATE: {out['verdict']}  (details in {args.out})")
    return 0 if ok else 1


def load_batch(paths: list[str], focus: str) -> dict[str, list[dict]]:
    if not paths:
        raise EvidenceError("gate requires per-anchor games files for each batch")
    out = {}
    for p in paths:
        # name syntax: 'anchor=path/to/file.jsonl', else derived from filename
        # '<anchor>.games.jsonl' / '<anchor>.jsonl'.
        if "=" in p:
            name, path = p.split("=", 1)
        else:
            path = p
            name = os.path.basename(p)
            for suffix in (".games.jsonl", ".jsonl"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            else:
                raise EvidenceError(f"cannot derive anchor name from {p!r}; use anchor=path")
        if not name:
            raise EvidenceError(f"empty anchor name for {p!r}")
        out[name] = load_games(path, focus)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("batch", help="per-batch estimate")
    pb.add_argument("--games", nargs="+", required=True,
                    help="games.jsonl per anchor, named <anchor>.games.jsonl or anchor:path")
    pb.add_argument("--anchor-json", required=True)
    pb.add_argument("--focus", required=True)
    pb.add_argument("--bootstrap", type=int, default=10000)
    pb.add_argument("--seed", type=int, default=20261114)
    pb.add_argument("--out", required=True)

    pc = sub.add_parser("combine", help="combine two batch result JSONs")
    pc.add_argument("--batch-a", required=True)
    pc.add_argument("--batch-b", required=True)
    pc.add_argument("--out", required=True)

    pg = sub.add_parser("gate", help="fail-closed rating gate from raw evidence")
    pg.add_argument("--anchor-json", required=True)
    pg.add_argument("--focus", required=True)
    pg.add_argument("--batch-a", nargs="+", required=True)
    pg.add_argument("--batch-b", nargs="+", required=True)
    pg.add_argument("--control-anchor", required=True,
                    help="games.jsonl of anchor1 vs anchor2 null control")
    pg.add_argument("--control-anchor-names", nargs=2, required=True,
                    metavar=("ANCHOR1", "ANCHOR2"))
    pg.add_argument("--control-self", required=True, help="self-match games.jsonl")
    pg.add_argument("--min-games", type=int, default=2000)
    pg.add_argument("--threshold", type=float, default=2000.0)
    pg.add_argument("--bootstrap", type=int, default=10000)
    pg.add_argument("--seed", type=int, default=20261114)
    pg.add_argument("--out", required=True)

    pn = sub.add_parser("control", help="null controls")
    pn.add_argument("--mode", choices=("anchor-vs-anchor", "self-match"), required=True)
    pn.add_argument("--games", required=True)
    pn.add_argument("--anchor-json")
    pn.add_argument("--names", nargs=2, metavar=("A", "B"))
    pn.add_argument("--focus", required=True)
    pn.add_argument("--bootstrap", type=int, default=10000)
    pn.add_argument("--seed", type=int, default=20261114)
    pn.add_argument("--out")

    args = ap.parse_args()

    if args.cmd == "batch":
        pool = json.load(open(args.anchor_json))
        res = batch_estimate(load_batch(args.games, args.focus), pool["engines"], args.focus,
                             args.bootstrap, args.seed)
        with open(args.out, "w") as f:
            json.dump(res, f, indent=2)
        print(f"theta = {res['theta']:.2f}  ci95_calibrated = "
              f"[{res['ci95_calibrated'][0]:.2f}, {res['ci95_calibrated'][1]:.2f}]")
        return 0
    if args.cmd == "combine":
        ba = json.load(open(args.batch_a))
        bb = json.load(open(args.batch_b))
        res = combine_batches(ba, bb)
        with open(args.out, "w") as f:
            json.dump(res, f, indent=2)
        print(f"combined theta = {res['theta']:.2f}  ci95_calibrated = "
              f"[{res['ci95_calibrated'][0]:.2f}, {res['ci95_calibrated'][1]:.2f}]")
        return 0
    if args.cmd == "gate":
        return run_gate(args)
    if args.cmd == "control":
        if args.mode == "self-match":
            games = load_games(args.games, args.focus)
            res = control_self_match(games, args.focus, args.bootstrap, args.seed)
        else:
            games = load_games(args.games, None)
            pool = json.load(open(args.anchor_json))
            ea = next(e for e in pool["engines"] if e["name"] == args.names[0])
            eb = next(e for e in pool["engines"] if e["name"] == args.names[1])
            res = control_anchor_vs_anchor(games, ea, eb, args.bootstrap, args.seed)
        if args.out:
            with open(args.out, "w") as f:
                json.dump(res, f, indent=2)
        print(json.dumps(res, indent=2))
        return 0 if res["pass"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
