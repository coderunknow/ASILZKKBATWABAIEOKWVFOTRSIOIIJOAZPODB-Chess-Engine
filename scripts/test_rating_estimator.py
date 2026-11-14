#!/usr/bin/env python3
"""Regression tests for scripts/rating_estimator.py (RATING_PROTOCOL Amendment §9).

Run: python3 scripts/test_rating_estimator.py   (stdlib only; no pytest required)

Synthetic-scenario coverage: balanced-match recovery, perfect/zero boundaries,
known anchor differences, correlated opening difficulty, anchor-uncertainty
conversion, GLS + covariance + singular fallback, shared calibration across
batches, combined CI math, missing/invalid evidence rejection, fixed-seed
reproducibility, null-control verdicts, and a full fail-closed gate run.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rating_estimator as re  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PASS = 0
FAIL = 0


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {msg}")


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


# ---------------------------------------------------------------------------
# Synthetic evidence generators
# ---------------------------------------------------------------------------

FOCUS = "Flawless"


def make_games(anchor: str, opening_scores, white_is_focus=True):
    """opening_scores: list of (opening_name, wins, losses, draws) from FOCUS view.

    Colors alternate per game so both sides are covered deterministically.
    """
    games = []
    gi = 0
    for oname, w, l, d in opening_scores:
        seq = ["1-0"] * w + ["0-1"] * l + ["1/2-1/2"] * d
        for k, res in enumerate(seq):
            gi += 1
            if k % 2 == 0:
                white, black = FOCUS, anchor
                result = res
            else:
                white, black = anchor, FOCUS
                # res is from focus view; flip decisive results
                result = {"1-0": "0-1", "0-1": "1-0", "1/2-1/2": "1/2-1/2"}[res]
            games.append({
                "opening": oname, "white": white, "black": black,
                "result": result, "counted": True, "engine_error": False,
                "game_index": gi,
            })
    return games


def write_jsonl(path, games):
    with open(path, "w") as f:
        for g in games:
            f.write(json.dumps(g) + "\n")


def pool_entry(name, elo, err, conv="ci95"):
    return {
        "name": name, "version": "1.0", "sha256": "b" * 64,
        "published_elo": elo, "published_error": err, "error_convention": conv,
        "license": "GPL-3.0", "license_verified": True,
        "binary_source_url": "https://example.org/x", "binary_downloaded": True,
        "binary_sha256_verified": True,
    }


def uniform_openings(n_open, w, l, d, prefix="op"):
    return [(f"{prefix}{i:03d}", w, l, d) for i in range(n_open)]


def varied_openings(n_open, prefix="v"):
    """Heterogeneous clusters (required: uniform clusters make Sigma_m degenerate).

    Per opening: wins 24..26, losses 4..6, draws fill to 34. Points per opening
    25..29/34 -> s in [0.735, 0.853] -> |d| < 400 (no saturation), and every
    cluster is interior so no bootstrap replicate hits a boundary.
    """
    out = []
    for i in range(n_open):
        w = 24 + (i % 3)
        l = 4 + ((i // 3) % 3)
        d = 34 - w - l
        out.append((f"{prefix}{i:03d}", w, l, d))
    return out


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_eps_conversion():
    check(close(re.eps_sd_from_entry({"error_convention": "ci95", "published_error": 19.6}), 10.0),
          "ci95 -> /1.96")
    check(close(re.eps_sd_from_entry({"error_convention": "ci90", "published_error": 16.45}), 10.0),
          "ci90 -> /1.645")
    check(close(re.eps_sd_from_entry({"error_convention": "ci99", "published_error": 25.76}), 10.0),
          "ci99 -> /2.576")
    check(close(re.eps_sd_from_entry({"error_convention": "sd", "published_error": 10.0}), 10.0),
          "sd as-is")
    check(close(re.eps_sd_from_entry({"error_convention": "se", "published_error": 10.0}), 10.0),
          "se as-is")
    try:
        re.eps_sd_from_entry({"error_convention": "plusminus", "published_error": 10})
        check(False, "ambiguous convention rejected")
    except SystemExit:
        check(True, "ambiguous convention rejected")


def test_gls_math():
    # Identity covariance -> simple average.
    w, _, mode = re.gls([[1.0, 0.0], [0.0, 1.0]], [2000.0, 2100.0])
    check(mode == "gls" and close(sum(w), 1.0) and close(w[0], 0.5), "GLS identity -> average")
    theta = sum(w[i] * y for i, y in enumerate([2000.0, 2100.0]))
    check(close(theta, 2050.0), "GLS theta 2050")
    # Singular covariance -> documented diagonal fallback.
    w2, _, mode2 = re.gls([[1.0, 1.0], [1.0, 1.0]], [2000.0, 2100.0])
    check(mode2 == "diagonal-wls-fallback" and close(sum(w2), 1.0), "singular -> diagonal WLS fallback")
    # Weighted: diag variances 1 and 3 -> weights 3/4, 1/4.
    w3, _, _ = re.gls([[1.0, 0.0], [0.0, 3.0]], [2000.0, 2100.0])
    check(close(w3[0], 0.75) and close(w3[1], 0.25), "GLS inverse-variance weights")


def test_joint_bootstrap_correlation():
    # Both anchors do better in the same openings -> d_a co-move -> positive cov.
    easy = [(f"e{i}", 20, 2, 2) for i in range(30)]
    hard = [(f"h{i}", 8, 14, 2) for i in range(30)]
    scores = easy + hard
    a1 = {"name": "A1", "published_elo": 2000, "eps_sd": 10.0,
          "clusters": {t[0]: make_cluster_list(t) for t in scores}}
    a2 = {"name": "A2", "published_elo": 2100, "eps_sd": 10.0,
          "clusters": {t[0]: make_cluster_list(t) for t in scores}}
    boot = re.joint_bootstrap([a1, a2], 2000, 42)
    _, cov = re.col_means_cov(boot["D"])
    check(cov[0][1] > 0, f"shared opening difficulty -> positive off-diagonal cov ({cov[0][1]:.3f})")
    check(cov[0][0] > 0 and cov[1][1] > 0, "positive variances")
    # Reproducibility under fixed seed.
    boot2 = re.joint_bootstrap([a1, a2], 2000, 42)
    check(boot["D"] == boot2["D"], "fixed seed -> identical replicates")
    boot3 = re.joint_bootstrap([a1, a2], 2000, 43)
    check(boot["D"] != boot3["D"], "different seed -> different replicates")


def make_cluster_list(triple):
    _, w, l, d = (triple[0], triple[1], triple[2], triple[3]) if len(triple) == 4 else (None,) + triple
    return [1.0] * w + [0.0] * l + [0.5] * d


def test_boundaries_rejected():
    # Perfect score everywhere -> bootstrap hits boundary -> fail closed.
    a = {"name": "A", "published_elo": 1900, "eps_sd": 10.0,
         "clusters": {f"op{i}": [1.0] * 20 for i in range(5)}}
    try:
        re.joint_bootstrap([a], 100, 7)
        check(False, "perfect score rejected")
    except SystemExit:
        check(True, "perfect score -> EvidenceError (fail closed)")
    a2 = {"name": "A", "published_elo": 1900, "eps_sd": 10.0,
          "clusters": {f"op{i}": [0.0] * 20 for i in range(5)}}
    try:
        re.joint_bootstrap([a2], 100, 7)
        check(False, "zero score rejected")
    except SystemExit:
        check(True, "zero score -> EvidenceError (fail closed)")


def test_batch_estimate_recovery():
    # Flawless scores 28/34 = 0.8235 vs anchor at 2000 -> d = +262.5.
    scores = uniform_openings(60, 27, 5, 2)
    games = make_games("A1", scores)
    entries = [pool_entry("A1", 2000, 30)]
    res = re.batch_estimate({"A1": games}, entries, FOCUS, 2000, 20261114)
    s = 28.0 / 34.0
    d_expected = -400.0 * math.log10(1.0 / s - 1.0)
    check(close(res["per_anchor"][0]["d_flawless_minus_anchor"], d_expected, 1e-6),
          f"per-anchor d recovery ({res['per_anchor'][0]['d_flawless_minus_anchor']:.2f} vs {d_expected:.2f})")
    check(close(res["theta"], 2000 + d_expected, 1e-6), "single-anchor theta = R + d")
    check(res["ci95_calibrated"][0] < res["theta"] < res["ci95_calibrated"][1], "CI brackets theta")
    lo_m, hi_m = res["ci95_match_only"]
    lo_c, hi_c = res["ci95_calibrated"]
    check((hi_c - lo_c) > (hi_m - lo_m), "calibration widens the CI")
    check(res["per_anchor"][0]["gate_eligible"], "d within saturation limit")
    check(res["per_anchor"][0]["n_counted_games"] == 60 * 34, "game count")


def test_saturation_flagged():
    # d = +500 saturates: recorded, ineligible for gate.
    scores = uniform_openings(60, 33, 1, 0)
    games = make_games("A1", scores)
    res = re.batch_estimate({"A1": games}, [pool_entry("A1", 2000, 30)], FOCUS, 500, 1)
    p = res["per_anchor"][0]
    check(p["d_flawless_minus_anchor"] > 400 and not p["gate_eligible"] and p["saturated"],
          "saturation recorded and excluded from gate eligibility")


def test_shared_calibration():
    # Two near-identical batches: shared calibration must be added ONCE.
    scores = varied_openings(60)
    games = make_games("A1", scores)
    entries = [pool_entry("A1", 2000, 30), pool_entry("A2", 2100, 30), pool_entry("A3", 1900, 30)]
    g2 = {"A1": games, "A2": make_games("A2", scores), "A3": make_games("A3", scores)}
    ba = re.batch_estimate(g2, entries, FOCUS, 1000, 11)
    bb = re.batch_estimate(g2, entries, FOCUS, 1000, 12)
    comb = re.combine_batches(ba, bb)
    check(comb["var_match_pooled"] < ba["var_match"], "match noise pools down")
    check(comb["var_cal_shared"] > 0.5 * ba["var_cal"],
          "shared calibration NOT halved by pooling")
    check(close(comb["var_cal_shared"], ba["var_cal"], 0.1 * max(ba["var_cal"], 1.0)),
          "identical batches: shared calibration added once (within bootstrap jitter)")
    check(comb["var_total"] > comb["var_match_pooled"], "calibration still in the total variance")
    lam = comb["weight_batch_a"]
    check(close(lam, 0.5, 0.05), "near-identical batches -> ~equal weights")
    check(close(comb["theta"], lam * ba["theta"] + (1 - lam) * bb["theta"]),
          "combined theta weighted mean")
    lo_m, hi_m = comb["ci95_match_only"]
    lo_c, hi_c = comb["ci95_calibrated"]
    check((hi_c - lo_c) > (hi_m - lo_m), "combined calibrated CI wider than match-only")


def test_missing_invalid_evidence():
    try:
        re.load_games("/nonexistent/games.jsonl", FOCUS)
        check(False, "missing file rejected")
    except SystemExit:
        check(True, "missing file rejected (fail closed)")
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "g.jsonl")
        write_jsonl(p, [{"opening": "x", "white": "Someone", "black": "Else",
                         "result": "1-0", "counted": True}])
        try:
            re.load_games(p, FOCUS)
            check(False, "games without focus rejected")
        except SystemExit:
            check(True, "games without focus engine rejected")
        write_jsonl(p, [{"opening": "x", "white": FOCUS, "black": "A",
                         "result": "1-0", "counted": False, "engine_error": True}])
        games = re.load_games(p, FOCUS)
        check(games == [], "uncounted/engine-error games excluded from statistics")


def test_null_controls():
    scores = uniform_openings(60, 20, 2, 2)  # focus A1 view: s=0.647
    # A1 (2000) vs A2 (2100) should measure A1 - A2 ~ +117 - ... construct so the
    # measured diff equals published: give A1 score 0.647 vs A2 -> d = +111.
    games = []
    for oname, w, l, d in scores:
        seq = ["1-0"] * w + ["0-1"] * l + ["1/2-1/2"] * d
        for res in seq:
            games.append({"opening": oname, "white": "A1", "black": "A2",
                          "result": res, "counted": True, "engine_error": False})
    s = 21.0 / 24.0  # 20 wins + 2 draws out of 24 per opening
    d_meas = -400.0 * math.log10(1.0 / s - 1.0)
    # Published diff crafted to match exactly -> pass.
    e1 = pool_entry("A1", 2000, 30)
    e2 = pool_entry("A2", 2000 - d_meas, 30)
    res = re.control_anchor_vs_anchor(games, e1, e2, 1000, 5)
    check(res["pass"] and abs(res["error"]) < 1e-6, "null control exact recovery passes")
    # Published diff off by 100 -> fail.
    e3 = pool_entry("A2", 2000 - d_meas + 100, 30)
    res2 = re.control_anchor_vs_anchor(games, e1, e3, 1000, 5)
    check(not res2["pass"], "null control off by 100 Elo fails")
    # Self-match: fair scores -> pass; biased -> fail.
    fair = make_games("Opp", uniform_openings(60, 10, 10, 4))
    r = re.control_self_match(fair, FOCUS, 1000, 5)
    check(r["pass"], "fair self-match passes")
    biased = make_games("Opp", uniform_openings(60, 30, 2, 2))
    r2 = re.control_self_match(biased, FOCUS, 1000, 5)
    check(not r2["pass"], "biased self-match fails")


# ---------------------------------------------------------------------------
# Full gate end-to-end (subprocess, fail closed both ways)
# ---------------------------------------------------------------------------


def anchor_openings(prefix, base_w, l, n=60):
    """Heterogeneous per-opening (w, l, d) with 34 games per opening, common names
    across anchors (the joint bootstrap requires identical opening suites)."""
    out = []
    for i in range(n):
        w = base_w + (i % 3)
        d = 34 - w - l
        out.append((f"{prefix}{i:03d}", w, l, d))
    return out


def build_gate_inputs(td, self_bias=False):
    # Transitively consistent world: published A1=1900, A2=2000, A3=2100 and
    # manufactured Flawless scores imply d(A1-A2) = (F-A2)-(F-A1) = -100, which
    # the anchor-vs-anchor control must then recover.
    scores = {
        "A1": anchor_openings("x", 25, 6),   # d(F-A1) ~ +233 -> F ~ 2133
        "A2": anchor_openings("x", 21, 9),   # d(F-A2) ~ +137
        "A3": anchor_openings("x", 15, 12),  # d(F-A3) ~ +41
    }
    anchors = [("A1", 1900), ("A2", 2000), ("A3", 2100)]
    pool = {
        "rating_source": "CCRL 40/15 list",
        "list_publication_date": "2026-11-13",
        "retrieval_date": "2026-11-14",
        "time_control": "40 moves in 15 minutes",
        "engines": [pool_entry(n, e, 30) for n, e in anchors],
    }
    pj = os.path.join(td, "pool.json")
    json.dump(pool, open(pj, "w"))
    for batch in ("A", "B"):
        for n, _e in anchors:
            games = make_games(n, scores[n])
            write_jsonl(os.path.join(td, f"{batch}-{n}.games.jsonl"), games)
    # anchor-vs-anchor control: A1 vs A2 with d(A1-A2) = -95.6 ~= published -100.
    ctrl = []
    for oname, w, l, d in anchor_openings("c", 10, 19):
        seq = ["1-0"] * w + ["0-1"] * l + ["1/2-1/2"] * d
        for res in seq:
            ctrl.append({"opening": oname, "white": "A1", "black": "A2", "result": res,
                         "counted": True, "engine_error": False})
    write_jsonl(os.path.join(td, "ctrl-anchor.jsonl"), ctrl)
    self_scores = uniform_openings(60, 2, 30, 2) if self_bias else uniform_openings(60, 10, 10, 4)
    write_jsonl(os.path.join(td, "ctrl-self.jsonl"), make_games("Opp", self_scores))
    return pj


def gate_args(td, pj, batch_b=None, out="gate.json"):
    names = ("A1", "A2", "A3")
    return [sys.executable, os.path.join(HERE, "rating_estimator.py"), "gate",
            "--anchor-json", pj, "--focus", FOCUS,
            "--batch-a"] + [f"{n}={os.path.join(td, f'A-{n}.games.jsonl')}" for n in names] + \
           ["--batch-b"] + (batch_b or [f"{n}={os.path.join(td, f'B-{n}.games.jsonl')}" for n in names]) + \
           ["--control-anchor", os.path.join(td, "ctrl-anchor.jsonl"),
            "--control-anchor-names", "A1", "A2",
            "--control-self", os.path.join(td, "ctrl-self.jsonl"),
            "--min-games", "2000", "--threshold", "2000",
            "--bootstrap", "2000", "--seed", "20261114",
            "--out", os.path.join(td, out)]


def test_gate_full():
    with tempfile.TemporaryDirectory() as td:
        pj = build_gate_inputs(td, self_bias=False)
        proc = subprocess.run(gate_args(td, pj), capture_output=True, text=True, timeout=600)
        res = json.load(open(os.path.join(td, "gate.json")))
        check(proc.returncode == 0, f"gate passes on strong evidence (rc={proc.returncode})")
        check(res["pass"] is True, "gate verdict PASS")
        check(res["results"]["batch_a"]["ci95_calibrated"][0] > 2000, "A lower bound > 2000")
        check(res["results"]["batch_b"]["ci95_calibrated"][0] > 2000, "B lower bound > 2000")
        check(res["results"]["combined"]["ci95_calibrated"][0] > 2000, "combined lower bound > 2000")
    with tempfile.TemporaryDirectory() as td:
        pj = build_gate_inputs(td, self_bias=True)  # self-match control poisoned
        proc = subprocess.run(gate_args(td, pj), capture_output=True, text=True, timeout=600)
        res = json.load(open(os.path.join(td, "gate.json")))
        check(proc.returncode != 0, "gate FAILS when a null control fails")
        check(res["pass"] is False, "verdict FAIL recorded")
        check(any("self-match" in c["check"] and not c["pass"] for c in res["checks"]),
              "failed control named in checks")
    with tempfile.TemporaryDirectory() as td:
        pj = build_gate_inputs(td, self_bias=False)
        out = os.path.join(td, "gate.json")
        # Missing batch-B evidence -> must fail closed.
        proc = subprocess.run(
            gate_args(td, pj, batch_b=["A1=/nonexistent/B-A1.games.jsonl"]),
            capture_output=True, text=True, timeout=600)
        check(proc.returncode != 0, "missing evidence -> gate refuses (fail closed)")


def main():
    test_eps_conversion()
    test_gls_math()
    test_joint_bootstrap_correlation()
    test_boundaries_rejected()
    test_batch_estimate_recovery()
    test_saturation_flagged()
    test_shared_calibration()
    test_missing_invalid_evidence()
    test_null_controls()
    test_gate_full()
    print(f"\n{PASS} checks passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
