#!/usr/bin/env python3
"""Shard aggregator + verifier for rating batches (RATING_PROTOCOL §9 / mission §5.2).

FAIL-CLOSED: every rejection rule exits non-zero with a reason. This tool NEVER
produces a partial or softened result.

Given a directory tree of completed shard outputs (each a match.py out-dir with
meta.json + games.jsonl + games.pgn), it verifies and merges them into one
batch-level games.jsonl + manifest for the estimator:

  REJECTS: missing shards, duplicate shard identifiers, duplicate games,
  incorrect engine hashes (vs frozen value), incorrect anchor hashes, different
  opening-suite hashes within a batch, unexpected time controls, incomplete
  games, missing metadata, inconsistent hardware calibration.

Usage:
  python3 scripts/aggregate_shards.py --shards-root benches/rating-A/A1 \
      --batch A --anchor A1 --engine-sha256 <64hex> --anchor-sha256 <64hex> \
      --opening-suite-sha256 <64hex> --tc-moves 40 --tc-seconds 900 \
      --expected-shards 4 --out merged/A1.games.jsonl --manifest merged/A1.manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys


def fail(msg: str) -> None:
    print(f"AGGREGATE-REJECT: {msg}", file=sys.stderr)
    raise SystemExit(1)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shards-root", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--engine-sha256", required=True, help="frozen Flawless binary SHA-256")
    ap.add_argument("--anchor-sha256", required=True, help="frozen anchor binary SHA-256")
    ap.add_argument("--opening-suite-sha256", required=True)
    ap.add_argument("--tc-moves", type=int, required=True)
    ap.add_argument("--tc-seconds", type=float, required=True)
    ap.add_argument("--expected-shards", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    # Discover shard dirs: any subdir of shards-root containing meta.json.
    shard_dirs = []
    for root, _dirs, files in os.walk(args.shards_root):
        if "meta.json" in files:
            shard_dirs.append(root)
    shard_dirs.sort()
    if len(shard_dirs) != args.expected_shards:
        fail(f"missing shards: found {len(shard_dirs)} of {args.expected_shards} under {args.shards_root}")

    seen_shard_ids: set[str] = set()
    merged_games: list[dict] = []
    seen_game_keys: set[tuple] = set()
    suite_hashes: set[str] = set()
    hw_models: set[str] = set()
    total_engine_errors = 0
    total_unadj = 0

    for sd in shard_dirs:
        meta = json.load(open(os.path.join(sd, "meta.json")))
        if meta.get("completion_status") != "completed":
            fail(f"shard {sd}: incomplete ({meta.get('completion_status')!r})")
        sid = meta.get("shard_id")
        if not sid:
            fail(f"shard {sd}: missing shard_id")
        if sid in seen_shard_ids:
            fail(f"duplicate shard identifier {sid!r}")
        seen_shard_ids.add(sid)
        if meta.get("batch_id") != args.batch:
            fail(f"shard {sd}: batch_id {meta.get('batch_id')!r} != {args.batch!r}")

        # Engine identity: some artifact of the white side must match the frozen hash.
        white_hashes = [a.get("sha256") for a in meta.get("white_artifact", {}).get("artifacts", [])]
        black_hashes = [a.get("sha256") for a in meta.get("black_artifact", {}).get("artifacts", [])]
        if args.engine_sha256 not in white_hashes:
            fail(f"shard {sd}: frozen engine hash {args.engine_sha256} not among white artifacts")
        if args.anchor_sha256 not in black_hashes:
            fail(f"shard {sd}: frozen anchor hash {args.anchor_sha256} not among black artifacts")

        sh = meta.get("openings_file_sha256")
        if sh != args.opening_suite_sha256:
            fail(f"shard {sd}: opening-suite hash {sh} != frozen {args.opening_suite_sha256}")
        suite_hashes.add(sh)

        tc = meta.get("time_control", {})
        if tc.get("mode") != "clock" or tc.get("period_moves") != args.tc_moves \
                or float(tc.get("period_seconds")) != args.tc_seconds:
            fail(f"shard {sd}: unexpected time control {tc}")

        hw = meta.get("hardware", {}) or {}
        hw_models.add(str(hw.get("cpu_model")))

        games_path = os.path.join(sd, "games.jsonl")
        if not os.path.exists(games_path):
            fail(f"shard {sd}: missing games.jsonl")
        n_lines = 0
        for ln, line in enumerate(open(games_path), 1):
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            g = json.loads(line)
            if not g.get("moves") or not g.get("result"):
                fail(f"shard {sd}:{ln}: incomplete game record")
            if g.get("result") not in ("1-0", "0-1", "1/2-1/2", "*"):
                fail(f"shard {sd}:{ln}: unknown result {g.get('result')!r}")
            key = (sid, g.get("schedule_index"), g.get("replay_depth"))
            if key in seen_game_keys:
                fail(f"duplicate game record {key}")
            seen_game_keys.add(key)
            if g.get("engine_error"):
                total_engine_errors += 1
            if g.get("adjudicated") is False:
                total_unadj += 1
            g["_shard_id"] = sid
            merged_games.append(g)
        if n_lines != meta.get("n_attempts"):
            fail(f"shard {sd}: {n_lines} game lines != manifest n_attempts {meta.get('n_attempts')}")

    if len(suite_hashes) > 1:
        fail(f"multiple opening-suite hashes within one batch: {suite_hashes}")
    if len(hw_models) > 1:
        fail(f"inconsistent hardware calibration across shards: {hw_models}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        for g in merged_games:
            f.write(json.dumps(g) + "\n")

    counted = sum(1 for g in merged_games if g.get("counted"))
    manifest = {
        "batch": args.batch,
        "anchor": args.anchor,
        "engine_sha256": args.engine_sha256,
        "anchor_sha256": args.anchor_sha256,
        "opening_suite_sha256": args.opening_suite_sha256,
        "shard_ids": sorted(seen_shard_ids),
        "n_shards": len(seen_shard_ids),
        "n_attempts": len(merged_games),
        "n_counted": counted,
        "n_engine_errors": total_engine_errors,
        "n_unadjudicated": total_unadj,
        "hardware_cpu_model": sorted(hw_models),
        "merged_sha256": sha256_file(args.out),
    }
    with open(args.manifest, "w") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
