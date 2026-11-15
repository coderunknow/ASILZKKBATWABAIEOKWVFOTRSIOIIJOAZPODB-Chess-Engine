#!/usr/bin/env python3
"""Generate a confirmatory batch dispatch.json (marker-file dispatch for rating-run.yml).

Usage: python3 make_batch_dispatch.py --hash <64hex> --batch A --seed 20261121
       [--suite benches/rating-openings-batchA.txt --suite-sha256 2c4a54d8...]
       [--anchor topple-0.1.1] [--revision 11] [--shards 255] [--reps 17]
Writes benches/dispatch.json with purpose=confirmatory (resolve job enforces the frozen
hash + full preregistered shape). Batch B: --batch B --seed 20261122 --suite batchB.
"""
import argparse, json, sys

SUITES = {
    "A": ("benches/rating-openings-batchA.txt",
          "2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96"),
    "B": ("benches/rating-openings-batchB.txt",
          "744a3981cc312a676ba259962309858b7d2fc645094bf2dccf5391e77f2f9dd4"),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hash", required=True)
    ap.add_argument("--batch", required=True, choices=["A", "B"])
    ap.add_argument("--seed", required=True, type=int)
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--revision", required=True, type=int)
    ap.add_argument("--shards", type=int, default=255)
    ap.add_argument("--reps", type=int, default=17)
    args = ap.parse_args()
    assert len(args.hash) == 64 and all(c in "0123456789abcdef" for c in args.hash), "bad hash"
    suite_path, suite_sha = SUITES[args.batch]
    dispatch = {
        "schema": 1,
        "revision": args.revision,
        "purpose": "confirmatory",
        "description": (f"Confirmatory Batch {args.batch} vs {args.anchor}: 60 openings x "
                        f"{args.reps} paired reps x AB/BA = {60*args.reps*2} games "
                        f"({args.shards} shards x 8), preregistered (PREREGISTRATION.md "
                        f"BATCH-A/B + gate-plan.json), engine hash pinned from SCREEN-2."),
        "preregistration": "PREREGISTRATION.md#batch-a--batch-b-registered-2026-11-14",
        "target_commit": "auto",
        "engine_sha256": args.hash,
        "batch": args.batch,
        "anchor_id": args.anchor,
        "white_engine": "flawless",
        "black_engine": args.anchor,
        "shard_count": args.shards,
        "shard_indices": list(range(args.shards)),
        "opening_suite": suite_path,
        "opening_suite_sha256": suite_sha,
        "repetitions": args.reps,
        "seed": args.seed,
        "tc": "40/15",
    }
    with open("benches/dispatch.json", "w") as f:
        json.dump(dispatch, f, indent=2)
    print(f"wrote benches/dispatch.json rev {args.revision}: batch {args.batch} vs {args.anchor}, "
          f"{args.shards} shards, seed {args.seed}, hash {args.hash[:12]}…")

if __name__ == "__main__":
    main()
