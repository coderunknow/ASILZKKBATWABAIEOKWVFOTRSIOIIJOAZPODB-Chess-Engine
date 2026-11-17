#!/usr/bin/env python3
"""preview_estimate.py — SELECTION-ONLY uncertainty preview (NOT a gate run).

Runs the registered estimator's batch_estimate on the SCREENING evidence
(120 games/anchor) to (a) prove the estimator end-to-end on real repo evidence
and (b) preview CI width for campaign planning. Output goes to stdout only;
nothing is committed and no acceptance decision is made (gate needs >=3 anchors
x >=2040 games each from BOTH batches — none of which exist yet).
"""
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from rating_estimator import batch_estimate

pool = json.load(open("benches/anchor-pool.json"))
entries = [e for e in pool["engines"] if e["key"] in ("topple-0.1.1", "topple-0.2.1")]
games_by = {}
for e in entries:
    g = [json.loads(l) for l in open(f"benches/evidence/screening-2/{e['key']}/games.jsonl") if l.strip()]
    games_by[e["key"]] = g

res = batch_estimate(games_by, entries, "flawless", n_boot=10000, seed=20261121)
print("PREVIEW (selection-only, 120 games/anchor — NOT gate evidence):")
for p in res["per_anchor"]:
    print(f"  {p['name']}: d={p['d_flawless_minus_anchor']:+.1f} sigma_matched={p['sigma_matched']:.1f} "
          f"sigma_total={p['sigma_total']:.1f} eligible={p['gate_eligible']}")
print(f"theta={res['theta']:.1f} mode={res['mode_total']} "
      f"CI95_match=[{res['ci95_match_only'][0]:.1f},{res['ci95_match_only'][1]:.1f}] "
      f"CI95_cal=[{res['ci95_calibrated'][0]:.1f},{res['ci95_calibrated'][1]:.1f}]")
print(f"var_match={res['var_match']:.1f} var_cal={res['var_cal']:.1f}")
