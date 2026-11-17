#!/usr/bin/env python3
"""dry_validate_run2_59.py — download run 43714620645's artifacts and strict-aggregate
at expected=59 (fail-closed dry run): proves the 59 available shards are internally
consistent (unique ids, hashes, tc, suite) and reports the partial score/flag stats.
The canonical 60-shard aggregation happens via recover_screen2.py after the retry."""
import json, os, subprocess, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import recover_screen2 as rec

RUN = "43714620645"
d = os.path.join(tempfile.gettempdir(), f"dry59-{RUN}")
rec.download_run(RUN, d, expect=59)
agg = tempfile.mkdtemp(prefix="dry59-agg-")
r = subprocess.run(["python3", os.path.join(rec.REPO, "scripts", "aggregate_shards.py"),
                    "--shards-root", d, "--batch", "A", "--anchor", "topple-0.2.1",
                    "--engine-sha256", rec.PINNED_ENGINE,
                    "--anchor-sha256", rec.ANCHORS[1][1],
                    "--opening-suite-sha256", rec.SUITE,
                    "--tc-moves", "40", "--tc-seconds", "900",
                    "--expected-shards", "59",
                    "--out", os.path.join(agg, "games.jsonl"),
                    "--manifest", os.path.join(agg, "manifest.json")],
                   capture_output=True, text=True)
if r.returncode != 0:
    print(r.stderr[-800:])
    sys.exit("59-SHARD DRY AGGREGATION FAILED — inspect before retry completes")
man = json.load(open(os.path.join(agg, "manifest.json")))
games = [json.loads(l) for l in open(os.path.join(agg, "games.jsonl"))]
flw = lambda g: g["white"].casefold().startswith("flawless")
def score(g):
    w = 1.0 if g["result"] == "1-0" else (0.0 if g["result"] == "0-1" else 0.5)
    return w if g["white"].casefold().startswith("flawless") else 1.0 - w
losses = [g for g in games if score(g) == 0.0]
flags = sum(1 for g in losses if g.get("reason") == "flag")
s = sum(score(g) for g in games) / len(games)
import math
d_hat = -400 * math.log10(1 / s - 1) if 0 < s < 1 else float("inf")
idx = sorted(g["schedule_index"] for g in games)
missing = sorted(set(range(120)) - set(idx))
print(f"n_shards={man['n_shards']} n_counted={man['n_counted']} engine_errors={man['n_engine_errors']}")
print(f"W={sum(1 for g in games if score(g)==1.0)} L={len(losses)} D={sum(1 for g in games if score(g)==0.5)} "
      f"flags={flags} score={s:.4f} partial_est={2439 + d_hat:.1f}")
print(f"schedule_index coverage: min={idx[0]} max={idx[-1]} unique={len(set(idx))}; "
      f"missing-for-shard17: {[i for i in missing if 34 <= i <= 35]} (games 34,35 pending)")
print("DRY-RUN: PASS — 59 shards internally consistent; retry shard 17 completes the set")
