#!/usr/bin/env python3
"""Apply the PREREGISTERED anchor-selection rule to screening-2 evidence and emit
benches/gate-plan.json (plus a human-readable justification on stdout).

The rule (PREREGISTRATION.md, frozen 2026-11-14, unchanged):
  pick >= 3 pool anchors with expected |d| <= 400 around the screening estimate
  and straddling it within +-200 where the pool permits; include the widest
  available low/high discriminators. If the frozen pool cannot satisfy the rule
  at the screening estimate, the nearest compliant set is chosen and justified —
  never tuned to the outcome.

Inputs: benches/evidence/screening-2/<anchor>/games.jsonl (+ manifests with the
pinned engine hash), benches/anchor-pool.json.
Output: benches/gate-plan.json (schema 1) or exit 1 with the documented tension.

This tool NEVER tunes thresholds and never reports a rating.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

ENGINE_FOCUS = "flawless"


def elo_from_score(s: float) -> float:
    if s <= 0.0 or s >= 1.0:
        return math.inf if s >= 1.0 else -math.inf
    return -400.0 * math.log10(1.0 / s - 1.0)


def focus_score(g: dict) -> float:
    w = 1.0 if g["result"] == "1-0" else (0.0 if g["result"] == "0-1" else 0.5)
    if g["white"].casefold().startswith(ENGINE_FOCUS):
        return w
    return 1.0 - w


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchors", nargs="+", required=True,
                    help="screened anchor keys (evidence must exist for each)")
    ap.add_argument("--evidence-root", default="benches/evidence/screening-2")
    ap.add_argument("--pool", default="benches/anchor-pool.json")
    ap.add_argument("--suite-sha256", default="2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96")
    ap.add_argument("--suite-b", default="744a3981cc312a676ba259962309858b7d2fc645094bf2dccf5391e77f2f9dd4")
    ap.add_argument("--threshold", type=float, default=2000.0)
    ap.add_argument("--min-games", type=int, default=2000)
    ap.add_argument("--bootstrap-seed", type=int, default=20261121)
    ap.add_argument("--control-av", default="benches/evidence/control/topple-0.1.1-vs-topple-0.2.1/games.jsonl")
    ap.add_argument("--control-self", default="benches/evidence/control/flawless-self-r/games.jsonl")
    ap.add_argument("--out", default="benches/gate-plan.json")
    args = ap.parse_args()

    pool = json.load(open(args.pool))
    entries = {e["key"]: e for e in pool["engines"]}
    engine_sha = None

    # 1. Per-anchor screening estimates (point estimates; selection-only).
    # --anchors accepts either "<key>" (evidence under --evidence-root/<key>,
    # the SCREEN-2/SCREEN-2R layout) or "<key>=<dir>" (explicit evidence dir,
    # e.g. SCREEN-3's benches/evidence/screening-3/<key> — the registered rule
    # is unchanged; only the evidence location is named explicitly).
    ests = []
    per_anchor = []
    for spec in args.anchors:
        key, _, override = spec.partition("=")
        base = override if override else os.path.join(args.evidence_root, key)
        games_path = os.path.join(base, "games.jsonl")
        man = json.load(open(os.path.join(base, "manifest.json")))
        if engine_sha is None:
            engine_sha = man["engine_sha256"]
        elif man["engine_sha256"] != engine_sha:
            sys.exit(f"engine hash differs between screening manifests: {man['engine_sha256']}")
        games = [json.loads(l) for l in open(games_path) if l.strip()]
        counted = [g for g in games if g.get("counted") and not g.get("engine_error")]
        n_flags = sum(1 for g in counted if g.get("reason") == "flag"
                      and not (g["white"].casefold().startswith(ENGINE_FOCUS)))
        s = sum(focus_score(g) for g in counted) / len(counted)
        d = elo_from_score(s)
        R = entries[key]["published_elo"]
        ests.append(R + d)
        per_anchor.append({"key": key, "n": len(counted), "score": s, "d": d,
                           "published": R, "abs": R + d,
                           "flawless_flag_wins": n_flags})
        print(f"{key}: n={len(counted)} score={s:.4f} d={d:+.1f} published={R} "
              f"abs={R + d:.1f} (anchor flag losses to flawless: {n_flags})")

    est = sum(ests) / len(ests)
    print(f"\nSCREENING ESTIMATE est = {est:.1f}")

    # 2. Registered selection rule, applied mechanically.
    non_sat = [k for k, e in entries.items() if abs(est - e["published_elo"]) <= 400.0]
    print(f"non-saturating pool anchors (|est - R_a| <= 400): {sorted(non_sat)}")
    if len(non_sat) < 3:
        print("\nRULE UNSATISFIABLE: fewer than 3 non-saturating anchors at the frozen pool.")
        print("Registered escape clause: document the tension; nearest compliant set would be:")
        near = sorted(entries, key=lambda k: abs(est - entries[k]["published_elo"]))[:3]
        for k in near:
            e = entries[k]
            print(f"   {k}: R={e['published_elo']} expected_d={est - e['published_elo']:+.0f} "
                  f"(saturating={abs(est - e['published_elo']) > 400})")
        sys.exit(2)

    lo_band = [k for k in non_sat if est - 200 <= entries[k]["published_elo"] <= est + 200]
    chosen = set(lo_band)
    # widest discriminators available among non-saturating anchors
    chosen.add(min(non_sat, key=lambda k: entries[k]["published_elo"]))
    chosen.add(max(non_sat, key=lambda k: entries[k]["published_elo"]))
    anchors = sorted(chosen, key=lambda k: entries[k]["published_elo"])
    print(f"straddling within ±200: {sorted(lo_band)}; widest low/high discriminators included")
    print(f"SELECTED ANCHOR SET: {anchors}")

    # 3. Emit the machine plan (schema 1, consumed by rating-gate.yml).
    ctrl_av_path, ctrl_self_path = args.control_av, args.control_self
    av_names = ("topple-0.1.1", "topple-0.2.1")
    plan = {
        "schema": 1,
        "focus": ENGINE_FOCUS,
        "engine_sha256": engine_sha,
        "threshold": args.threshold,
        "min_games": args.min_games,
        "bootstrap": 10000,
        "bootstrap_seed": args.bootstrap_seed,
        "batches": {
            "A": {"suite_sha256": args.suite_sha256, "anchors": anchors},
            "B": {"suite_sha256": args.suite_b, "anchors": anchors},
        },
        "controls": {
            "anchor_vs_anchor": {
                "evidence": ctrl_av_path,
                "names": list(av_names),
                "white_sha256": entries[av_names[0]]["sha256"],
                "black_sha256": entries[av_names[1]]["sha256"],
                "suite_sha256": args.suite_sha256,
            },
            "self_match": {
                "evidence": ctrl_self_path,
                "white_sha256": engine_sha,
                "black_sha256": engine_sha,
                "suite_sha256": args.suite_sha256,
            },
        },
        "selection": {
            "rule": "PREREGISTRATION.md BATCH-A/B anchor set rule (frozen 2026-11-14, unchanged)",
            "screening_estimate": est,
            "per_anchor": per_anchor,
            "selected": anchors,
        },
    }
    with open(args.out, "w") as f:
        json.dump(plan, f, indent=2)
    print(f"\ngate plan written to {args.out} (engine_sha256 {engine_sha[:12]}…)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
