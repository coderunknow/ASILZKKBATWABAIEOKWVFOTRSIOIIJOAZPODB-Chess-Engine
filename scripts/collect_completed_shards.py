#!/usr/bin/env python3
"""Copy only fully completed match.py shard artifacts into a clean aggregate root.

Incomplete/aborted artifacts remain in the original Actions download directory.
This helper does not rewrite them. Duplicate completed shard IDs are rejected;
recovery is represented by a separate run-* evidence directory.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="unmodified Actions artifact download root")
    ap.add_argument("--out", required=True, help="new/empty directory for completed shards")
    args = ap.parse_args()
    if os.path.exists(args.out) and os.listdir(args.out):
        ap.error(f"output directory must be empty: {args.out}")
    os.makedirs(args.out, exist_ok=True)

    completed = []
    seen_ids = set()
    for root, _dirs, files in os.walk(args.source):
        if "meta.json" not in files:
            continue
        meta_path = os.path.join(root, "meta.json")
        try:
            with open(meta_path) as f:
                meta = json.load(f)
        except (OSError, ValueError) as e:
            print(f"collect: ignoring unreadable metadata {meta_path}: {e}", file=sys.stderr)
            continue
        if meta.get("completion_status") != "completed":
            continue
        shard_id = meta.get("shard_id")
        if not shard_id:
            raise SystemExit(f"collect: completed artifact has no shard_id: {meta_path}")
        if shard_id in seen_ids:
            raise SystemExit(f"collect: duplicate completed shard_id {shard_id!r}; preserve and reconcile manually")
        seen_ids.add(shard_id)
        if not all(os.path.isfile(os.path.join(root, name)) for name in ("games.jsonl", "games.pgn")):
            raise SystemExit(f"collect: completed shard {shard_id} is missing games.jsonl/games.pgn")
        completed.append((shard_id, root))

    for index, (shard_id, root) in enumerate(sorted(completed)):
        dest = os.path.join(args.out, f"shard-{index:04d}")
        shutil.copytree(root, dest)
    # Empty collection is a recoverable checkpoint; caller records zero and skips aggregation.
    print(len(completed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
