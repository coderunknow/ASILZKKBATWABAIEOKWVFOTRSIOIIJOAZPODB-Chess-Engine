#!/usr/bin/env python3
"""Collect the EVAL-2 ablation results and apply the registered decision rules.

Runs `scripts/stats.py` on each pair, re-audits the raw records with
`scripts/audit_pair.py`, and prints the table that goes into
`PREREGISTRATION.md`.

The registered decision rules are:
  * EVAL-ALL vs EVAL-NONE: KEPT if the candidate's 95% CI lower bound is > 0
    Elo difference; REJECTED if the 95% CI upper bound is <= 0; INCONCLUSIVE
    otherwise.
  * Per feature X: the feature is KEPT only if EVAL-ALL's point estimate is
    >= EVAL-NO-X's. An ablation that scores more than 40 Elo HIGHER than
    EVAL-ALL is flagged HARMFUL. A difference within 40 Elo is INDETERMINATE
    and the feature is retained, but only the aggregate result may be claimed.

Usage: collect_eval_results.py [matches-root]
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PAIRS = [
    ("EVAL-ALL", "eval-all"),
    ("EVAL-NO-MOBILITY-TAPER", "eval-no-mobility-taper"),
    ("EVAL-NO-PAWN-STRUCTURE", "eval-no-pawn-structure"),
    ("EVAL-NO-PASSER", "eval-no-passer"),
    ("EVAL-NO-SPACE", "eval-no-space"),
    ("EVAL-NO-OUTPOSTS", "eval-no-outposts"),
    ("EVAL-NO-KING-SAFETY", "eval-no-king-safety"),
]

HARMFUL_MARGIN = 40.0


def parse_stats(text: str) -> dict:
    """Pull the score, CI and Elo out of the stats.py report."""
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("score:"):
            # "score: 41.5/80  = 0.519"
            body = line.split(":", 1)[1]
            count, _, frac = body.partition("=")
            out["score"] = float(count.split("/")[0])
            out["games"] = int(count.split("/")[1])
            out["score_frac"] = float(frac)
        elif "bootstrap CI for score:" in line:
            lo, hi = line.split("[")[1].split("]")[0].split(",")
            out["score_lo"] = float(lo)
            out["score_hi"] = float(hi)
        elif line.startswith("Elo difference"):
            out["elo"] = float(line.split(":")[1].split()[0])
            lo, hi = line.split("[")[1].split("]")[0].split(",")
            out["elo_lo"] = float(lo)
            out["elo_hi"] = float(hi)
    return out


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "/home/user/matches"
    py = sys.executable
    results = {}

    for label, tag in PAIRS:
        path = os.path.join(root, tag, "games.jsonl")
        if not os.path.exists(path):
            print(f"{label}: no evidence at {path}")
            continue
        # Re-audit the raw records.
        audit = subprocess.run(
            [py, os.path.join(HERE, "audit_pair.py"), path, tag, "80"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        verdict = "PASS" if "verdict         : PASS" in audit else "FAIL"

        proc = subprocess.run(
            [py, os.path.join(HERE, "stats.py"), path, "--focus", tag,
             "--bootstrap", "10000", "--seed", "20261118"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            print(f"{label}: stats.py failed: {proc.stderr.strip()[:200]}")
            continue
        st = parse_stats(proc.stdout)
        st["audit"] = verdict
        results[label] = st
        print(
            f"{label:26s} score {st.get('score_frac', float('nan')):.3f} "
            f"CI [{st.get('score_lo', float('nan')):.3f}, {st.get('score_hi', float('nan')):.3f}] "
            f"Elo {st.get('elo', float('nan')):+.0f} "
            f"CI [{st.get('elo_lo', float('nan')):+.0f}, {st.get('elo_hi', float('nan')):+.0f}] "
            f"audit={verdict}"
        )

    # --- the aggregate decision -----------------------------------------
    # A registered decision may only be taken on evidence that passed its
    # own audit. Failed audits stay in `results` for diagnostics, but they
    # must not produce a decision: the registered rule is about a complete,
    # correctly scheduled evidence set, not about whatever statistics happen
    # to survive a failed audit.
    allr = results.get("EVAL-ALL")
    if allr:
        if allr.get("audit") != "PASS":
            decision = "UNAVAILABLE (EVAL-ALL failed its audit)"
            print(f"\nEVAL-ALL vs EVAL-NONE decision: {decision}")
        else:
            if allr["elo_lo"] > 0:
                decision = "KEPT"
            elif allr["elo_hi"] <= 0:
                decision = "REJECTED"
            else:
                decision = "INCONCLUSIVE"
            print(f"\nEVAL-ALL vs EVAL-NONE decision: {decision}")

        # --- the per-feature decisions -----------------------------------
        print("\nPer-feature comparison (EVAL-ALL point estimate vs the ablation):")
        for label, _ in PAIRS:
            if label == "EVAL-ALL":
                continue
            r = results.get(label)
            if not r:
                print(f"  {label:26s} (no evidence)")
                continue
            if allr.get("audit") != "PASS":
                print(f"  {label:26s} UNAVAILABLE (EVAL-ALL failed its audit)")
                continue
            if r.get("audit") != "PASS":
                print(f"  {label:26s} UNAVAILABLE (ablation failed its audit)")
                continue
            delta = allr["elo"] - r["elo"]
            if delta < -HARMFUL_MARGIN:
                verdict = "HARMFUL"
            elif abs(delta) <= HARMFUL_MARGIN:
                verdict = "INDETERMINATE (retained, not claimed)"
            else:
                verdict = "RETAINED"
            print(f"  {label:26s} {allr['elo']:+.0f} vs {r['elo']:+.0f} "
                  f"(diff {delta:+.0f}) -> {verdict}")

    with open(os.path.join(root, "eval2_results.json"), "w") as fh:
        json.dump(results, fh, indent=2, sort_keys=True)
    print(f"\n(raw results written to {os.path.join(root, 'eval2_results.json')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
