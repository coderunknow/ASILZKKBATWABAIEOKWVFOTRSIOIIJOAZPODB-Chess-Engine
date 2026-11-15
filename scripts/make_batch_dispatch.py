#!/usr/bin/env python3
"""Generate a confirmatory batch dispatch.json (marker-file dispatch for rating-run.yml).

SHAPE-1: a batch is 2040 games = 1020 shards x 2 games, dispatched as FOUR runs of
255 shard-indices each (GitHub matrix cap 256). One marker commit per run:
  run 1: --from-index 0 --to-index 255
  run 2: --from-index 255 --to-index 510
  run 3: --from-index 510 --to-index 765
  run 4: --from-index 765 --to-index 1020
Evidence: each run commits benches/evidence/confirmatory/<anchor>/run-<run_id>/;
scripts/merge_batch_runs.py produces the canonical benches/evidence/batch{A,B}/<anchor>/
after run 4 (strict cross-run validation; SHAPE-1 addendum).

Usage: python3 make_batch_dispatch.py --hash <64hex> --batch A --seed 20261121
       [--anchor topple-0.1.1] [--revision 13] [--shards 1020]
       [--from-index 0 --to-index 255] [--reps 17]
Batch B: --batch B --seed 20261122 (suite batchB).
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
    ap.add_argument("--shards", type=int, default=1020,
                    help="TOTAL shards for the batch (1020 x 2 games = 2040, SHAPE-1)")
    ap.add_argument("--from-index", type=int, default=0)
    ap.add_argument("--to-index", type=int, default=None,
                    help="exclusive upper bound of THIS run's shard_indices "
                         "(default: --shards, i.e. a single-run dispatch)")
    ap.add_argument("--reps", type=int, default=17)
    args = ap.parse_args()
    assert len(args.hash) == 64 and all(c in "0123456789abcdef" for c in args.hash), "bad hash"
    hi = args.to_index if args.to_index is not None else args.shards
    assert 0 <= args.from_index < hi <= args.shards, "bad index slice"
    assert 60 * args.reps * 2 == args.shards * 2, \
        "shards x 2 must equal 60 x reps x 2 (2040 at reps=17)"
    indices = list(range(args.from_index, hi))
    suite_path, suite_sha = SUITES[args.batch]
    dispatch = {
        "schema": 1,
        "revision": args.revision,
        "purpose": "confirmatory",
        "description": (f"Confirmatory Batch {args.batch} vs {args.anchor}: 60 openings x "
                        f"{args.reps} paired reps x AB/BA = {60*args.reps*2} games "
                        f"(SHAPE-1: {args.shards} shards x 2; this run = indices "
                        f"[{args.from_index},{hi}) = {len(indices)} shards), preregistered "
                        f"(PREREGISTRATION.md BATCH-A/B + SHAPE-1 addendum + gate-plan.json), "
                        f"engine hash pinned from SCREEN-2."),
        "preregistration": "PREREGISTRATION.md#batch-a--batch-b-registered-2026-11-14",
        "target_commit": "auto",
        "engine_sha256": args.hash,
        "batch": args.batch,
        "anchor_id": args.anchor,
        "white_engine": "flawless",
        "black_engine": args.anchor,
        "shard_count": args.shards,
        "shard_indices": indices,
        "opening_suite": suite_path,
        "opening_suite_sha256": suite_sha,
        "repetitions": args.reps,
        "seed": args.seed,
        "tc": "40/15",
    }
    with open("benches/dispatch.json", "w") as f:
        json.dump(dispatch, f, indent=2)
    print(f"wrote benches/dispatch.json rev {args.revision}: batch {args.batch} vs {args.anchor}, "
          f"indices [{args.from_index},{hi}) of {args.shards}, seed {args.seed}, hash {args.hash[:12]}…")

if __name__ == "__main__":
    main()
