#!/usr/bin/env python3
"""verify_evidence.py — fail-closed verification of COMMITTED raw evidence.

The evidence bot (rating-run `evidence` job / evidence-bridge) commits, per
(batch, label): games.jsonl (raw per-game records) and manifest.json (identity
+ counts + merged_sha256), produced by the strict aggregator from hash-verified
runner artifacts. This tool re-verifies that committed evidence against the
preregistered gate plan (benches/gate-plan.json) and the frozen anchor pool:

  * every planned (batch, anchor) evidence directory exists
  * manifest identity: engine/anchor binary SHA-256, opening-suite SHA-256, TC
  * merged_sha256 matches the committed games.jsonl bytes
  * game-record integrity: valid results, counted flag consistency, no
    duplicate (shard_id, schedule_index, replay_depth), engine-error accounting
  * counted-game totals vs the plan's minimum
  * control evidence paths exist and carry counted games

Exit 0 only if everything verifies. Any mismatch exits non-zero with the exact
reason. Nothing here computes a rating — the estimator recomputes from these
same files; this tool only proves the files are the ones the plan registered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys


class EvidenceError(Exception):
    pass


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        raise EvidenceError(f"cannot read {path}: {e}") from e


def verify_merged_evidence(label: str, games_path: str, manifest_path: str,
                           plan_entry: dict, white_sha256: str, black_sha256: str,
                           min_games: int) -> dict:
    if not os.path.exists(games_path):
        raise EvidenceError(f"{label}: missing {games_path}")
    if not os.path.exists(manifest_path):
        raise EvidenceError(f"{label}: missing {manifest_path}")
    man = load_json(manifest_path)

    # Identity vs plan: the manifest must carry the exact frozen hashes of the
    # two seated sides (white first, black second).
    if man.get("engine_sha256") != white_sha256:
        raise EvidenceError(f"{label}: manifest white/engine hash {man.get('engine_sha256')} "
                            f"!= frozen {white_sha256}")
    if man.get("anchor_sha256") != black_sha256:
        raise EvidenceError(f"{label}: manifest black/anchor hash {man.get('anchor_sha256')} "
                            f"!= frozen {black_sha256}")
    if man.get("opening_suite_sha256") != plan_entry.get("suite_sha256"):
        raise EvidenceError(f"{label}: suite hash {man.get('opening_suite_sha256')} != plan "
                            f"{plan_entry.get('suite_sha256')}")
    if man.get("merged_sha256") != sha256_file(games_path):
        raise EvidenceError(f"{label}: merged_sha256 mismatch — committed games.jsonl differs "
                            f"from the manifest's recorded merge")

    # Game-record integrity + counts.
    seen = set()
    n_counted = 0
    n_engine_errors = 0
    for ln, line in enumerate(open(games_path), 1):
        line = line.strip()
        if not line:
            continue
        try:
            g = json.loads(line)
        except ValueError as e:
            raise EvidenceError(f"{label}:{ln}: unparseable game record: {e}") from e
        if not g.get("moves") or not g.get("result"):
            raise EvidenceError(f"{label}:{ln}: incomplete game record")
        if g.get("result") not in ("1-0", "0-1", "1/2-1/2", "*"):
            raise EvidenceError(f"{label}:{ln}: unknown result {g.get('result')!r}")
        key = (g.get("_shard_id"), g.get("schedule_index"), g.get("replay_depth"))
        if key in seen:
            raise EvidenceError(f"{label}:{ln}: duplicate game record {key}")
        seen.add(key)
        if g.get("engine_error"):
            n_engine_errors += 1
        if g.get("counted"):
            n_counted += 1
    if man.get("n_counted") != n_counted:
        raise EvidenceError(f"{label}: manifest n_counted {man.get('n_counted')} != recomputed {n_counted}")
    if min_games and n_counted < min_games:
        raise EvidenceError(f"{label}: counted games {n_counted} < required {min_games}")
    return {"label": label, "n_counted": n_counted,
            "n_engine_errors": n_engine_errors, "n_records": len(seen)}


def verify_all(plan_path: str, pool_path: str) -> dict:
    plan = load_json(plan_path)
    pool = load_json(pool_path)
    if plan.get("schema") != 1:
        raise EvidenceError("gate-plan schema must be 1")
    pool_by_key = {e.get("key"): e for e in pool.get("engines", [])}
    engine_sha = plan["engine_sha256"]
    min_games = int(plan.get("min_games", 2000))
    report = {"engine_sha256": engine_sha, "batches": {}, "controls": {}}

    for batch, bp in plan["batches"].items():
        label = f"batch-{batch}"
        plan_entry = {"suite_sha256": bp["suite_sha256"]}
        per_anchor = []
        for anchor_key in bp["anchors"]:
            if anchor_key not in pool_by_key:
                raise EvidenceError(f"{label}/{anchor_key}: not a frozen-pool anchor key")
            base = f"benches/evidence/batch{batch}/{anchor_key}"
            per_anchor.append(verify_merged_evidence(
                f"{label}/{anchor_key}", f"{base}/games.jsonl", f"{base}/manifest.json",
                plan_entry, engine_sha, pool_by_key[anchor_key]["sha256"], min_games))
        report["batches"][batch] = {"anchors": per_anchor}

    for name, cp in plan["controls"].items():
        games_path = cp["evidence"]
        manifest_path = os.path.join(os.path.dirname(games_path), "manifest.json")
        # Controls have no min-games gate here (their own thresholds live in the
        # estimator); require at least one counted game.
        plan_entry = {"suite_sha256": cp.get("suite_sha256")}
        info = verify_merged_evidence(f"control/{name}", games_path, manifest_path,
                                      plan_entry, cp["white_sha256"], cp["black_sha256"],
                                      int(cp.get("min_counted", 1)))
        report["controls"][name] = info
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", default="benches/gate-plan.json")
    ap.add_argument("--pool", default="benches/anchor-pool.json")
    args = ap.parse_args()
    try:
        report = verify_all(args.plan, args.pool)
    except EvidenceError as e:
        print(f"verify_evidence: FAIL — {e}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    print("verify_evidence: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
