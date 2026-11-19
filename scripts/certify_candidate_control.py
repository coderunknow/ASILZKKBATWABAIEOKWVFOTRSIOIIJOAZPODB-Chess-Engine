#!/usr/bin/env python3
"""Validate and certify the registered candidate self-match null control.

This produces an evidence-backed control report only. It cannot authorize
confirmatory dispatch, certify prospective power, or reinterpret screening.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import candidate_qualification as cq
from rating_estimator import CONTROL_ROBUSTNESS_SEEDS, control_self_match, load_games


def raw_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_candidate_control(games_path: str, *, design: dict[str, Any], target_commit: str | None = None) -> tuple[list[dict], dict]:
    control = design["self_control"]
    expected_sha = design["candidate"]["engine_sha256"]
    expected_relative = cq.candidate_evidence_path(expected_sha, "candidate-self-control")
    normalized_path = os.path.normpath(games_path)
    expected_suffix = os.path.normpath(os.path.join(expected_relative, "games.jsonl"))
    if normalized_path != expected_suffix and not normalized_path.endswith(os.sep + expected_suffix):
        raise ValueError("candidate self-control evidence is not in its candidate-qualified immutable path")
    manifest_path = os.path.join(os.path.dirname(games_path), "manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    expected = {
        "batch": "CTRL",
        "anchor": control["anchor_id"],
        "engine_sha256": expected_sha,
        "anchor_sha256": expected_sha,
        "opening_suite_sha256": control["suite_sha256"],
        "time_control": {
            "mode": "clock", "period_moves": 40, "period_seconds": 900.0,
        },
        "evidence_purpose": "candidate-self-control",
        "candidate_sha256": expected_sha,
        "dispatch_seed": control["dispatch_seed"],
        "repetitions": control["paired_repetitions_per_cluster"],
        "evidence_class": "candidate-null-control",
        "n_shards": control["shards"],
    }
    actual = {key: manifest.get(key) for key in expected}
    if actual != expected:
        raise ValueError(f"candidate self-control manifest identity mismatch: {actual!r}")
    expected_shards = {
        f"candidate-self-control-CTRL-candidate-self-control-{index}"
        for index in range(control["shards"])
    }
    shard_ids = manifest.get("shard_ids")
    if not isinstance(shard_ids, list) or set(shard_ids) != expected_shards or len(shard_ids) != len(expected_shards):
        raise ValueError("candidate self-control shard identity set is incomplete or unexpected")
    committed_target = manifest.get("target_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", committed_target):
        raise ValueError("candidate self-control manifest is missing a full target commit")
    if target_commit is not None and committed_target != target_commit:
        raise ValueError("candidate self-control target commit differs from the requested identity")
    if manifest.get("merged_sha256") != raw_sha256(games_path):
        raise ValueError("candidate self-control manifest merged_sha256 does not match raw games")

    games = load_games(games_path, "flawless")
    expected_games = control["total_counted_games"]
    if len(games) != expected_games or manifest.get("n_counted") != expected_games:
        raise ValueError(f"candidate self-control requires exactly {expected_games} counted games")
    raw_records = []
    with open(games_path, encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                raw_records.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid self-control JSONL record on line {line_no}") from exc
    if manifest.get("n_attempts") != len(raw_records):
        raise ValueError("candidate self-control n_attempts does not match raw records")
    if manifest.get("n_engine_errors") != sum(bool(item.get("engine_error")) for item in raw_records):
        raise ValueError("candidate self-control n_engine_errors does not match raw records")
    if manifest.get("n_unadjudicated") != sum(item.get("adjudicated") is False for item in raw_records):
        raise ValueError("candidate self-control n_unadjudicated does not match raw records")
    # Qualification commands are run from the repository root, as are all CI
    # test entry points; verify the suite file against its frozen digest.
    suite = os.path.abspath(control["suite"])
    if cq.sha256_file(suite) != control["suite_sha256"]:
        raise ValueError("candidate self-control opening-suite file hash differs from preregistration")
    with open(suite, encoding="utf-8") as handle:
        expected_openings = [
            line.split("|", 1)[0].strip()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if len(expected_openings) != control["opening_clusters"] or len(set(expected_openings)) != len(expected_openings):
        raise ValueError("registered self-control opening suite has invalid cluster count or duplicates")

    attempts_by_index: dict[int, dict[int, dict]] = {}
    for item in raw_records:
        index = item.get("schedule_index")
        replay_depth = item.get("replay_depth")
        if type(index) is not int or not 0 <= index < expected_games:
            raise ValueError(f"candidate self-control attempt has invalid schedule index {index!r}")
        if type(replay_depth) is not int or replay_depth not in (0, 1):
            raise ValueError("candidate self-control replay depth is outside the registered one-replay policy")
        if (type(item.get("counted")) is not bool
                or type(item.get("engine_error")) is not bool
                or type(item.get("adjudicated")) is not bool):
            raise ValueError(f"candidate self-control attempt {(index, replay_depth)} lacks boolean counted/error/adjudication provenance")
        attempts = attempts_by_index.setdefault(index, {})
        if replay_depth in attempts:
            raise ValueError(f"candidate self-control duplicates attempt {(index, replay_depth)}")
        attempts[replay_depth] = item
        replay_of = item.get("replay_of_schedule_index")
        if ((replay_depth == 0 and replay_of is not None)
                or (replay_depth == 1 and (type(replay_of) is not int or replay_of != index))):
            raise ValueError(f"candidate self-control attempt {(index, replay_depth)} has inconsistent replay provenance")
        expected_opening = expected_openings[index // 4]
        expected_pair = "AB" if index % 2 == 0 else "BA"
        expected_repetition = (index % 4) // 2
        if type(item.get("repetition")) is not int:
            raise ValueError(f"candidate self-control attempt {(index, replay_depth)} has non-integer repetition identity")
        expected_shard = f"candidate-self-control-CTRL-candidate-self-control-{index // 4}"
        if (item.get("opening") != expected_opening
                or str(item.get("white", "")).casefold() != "flawless"
                or str(item.get("black", "")).casefold() != "flawless"
                or item.get("color_pair") != expected_pair
                or item.get("repetition") != expected_repetition
                or item.get("_shard_id") != expected_shard):
            raise ValueError(f"candidate self-control attempt {(index, replay_depth)} has incorrect schedule identity")
        if item.get("counted") is not True and not item.get("engine_error"):
            raise ValueError("candidate self-control contains an uncounted non-error attempt")
        if item.get("engine_error") and item.get("counted") is True:
            raise ValueError("candidate self-control engine-error attempt is marked counted")
    for index in range(expected_games):
        initial = attempts_by_index.get(index, {}).get(0)
        replay = attempts_by_index.get(index, {}).get(1)
        if initial is None:
            raise ValueError(f"candidate self-control slot {index} has no initial attempt")
        if initial.get("engine_error"):
            if initial.get("counted") is True or replay is None:
                raise ValueError(f"candidate self-control failed initial attempt {index} lacks a replay")
            if replay.get("engine_error") or replay.get("counted") is not True:
                raise ValueError(f"candidate self-control replay {index} did not yield the counted result")
        elif initial.get("counted") is not True or replay is not None:
            raise ValueError(f"candidate self-control slot {index} has an invalid or unnecessary replay")

    by_index: dict[int, dict] = {}
    by_opening: dict[str, list[dict]] = {}
    for game in games:
        index = game.get("schedule_index")
        if type(index) is not int or not 0 <= index < expected_games or index in by_index:
            raise ValueError(f"candidate self-control has invalid or duplicate schedule index {index!r}")
        if game.get("counted") is not True or game.get("engine_error") or game.get("adjudicated") is not True:
            raise ValueError(f"candidate self-control schedule index {index} is not explicitly adjudicated and counted")
        if str(game.get("white", "")).casefold() != "flawless" or str(game.get("black", "")).casefold() != "flawless":
            raise ValueError(f"candidate self-control schedule index {index} has incorrect engine identities")
        pair = "AB" if index % 2 == 0 else "BA"
        if game.get("color_pair") != pair or game.get("repetition") != (index % 4) // 2:
            raise ValueError(f"candidate self-control schedule index {index} has wrong AB/BA or repetition metadata")
        expected_shard = f"candidate-self-control-CTRL-candidate-self-control-{index // 4}"
        if game.get("_shard_id") != expected_shard:
            raise ValueError(f"candidate self-control schedule index {index} has incorrect shard identity")
        opening = game.get("opening")
        wanted_opening = expected_openings[index // 4]
        if opening != wanted_opening:
            raise ValueError(f"candidate self-control schedule index {index} does not match {wanted_opening!r}")
        by_index[index] = game
        by_opening.setdefault(opening, []).append(game)
    if set(by_index) != set(range(expected_games)):
        raise ValueError("candidate self-control schedule does not cover the exact 0..239 index range")
    if len(by_opening) != 60 or any(len(cluster) != 4 for cluster in by_opening.values()):
        raise ValueError("candidate self-control must contain 60 complete four-game opening clusters")
    return games, manifest


def certify(games_path: str, *, bootstrap: int = 10000, target_commit: str | None = None) -> dict:
    design = cq.load_design(cq.DESIGN_PATH)
    games, manifest = load_candidate_control(games_path, design=design, target_commit=target_commit)
    result = control_self_match(games, "flawless", bootstrap, CONTROL_ROBUSTNESS_SEEDS[0])
    seeds = result.get("seed_robustness", {})
    all_pass = (
        result.get("seed_robust") is True
        and seeds.get("seeds") == list(CONTROL_ROBUSTNESS_SEEDS)
        and seeds.get("n_pass") == len(CONTROL_ROBUSTNESS_SEEDS)
        and seeds.get("unanimous") is True
        and all(item.get("pass") is True for item in seeds.get("per_seed", []))
    )
    return {
        "schema": 1,
        "status": "PASS" if result.get("pass") is True and all_pass else "BLOCKED",
        "candidate_sha256": design["candidate"]["engine_sha256"],
        "target_commit": manifest["target_commit"],
        "evidence_path": games_path,
        "evidence_manifest_sha256": raw_sha256(os.path.join(os.path.dirname(games_path), "manifest.json")),
        "games_sha256": manifest["merged_sha256"],
        "counted_games": len(games),
        "seed_robust": result.get("seed_robust") is True,
        "all_registered_seeds_pass": all_pass,
        "registered_seed_results": seeds,
        "control_result": result,
        "eligible_for_confirmatory_dispatch": False,
        "note": "This certifies only the candidate self-match null control; it is not a power PASS or dispatch authorization.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", required=True, help="candidate-qualified self-control games.jsonl")
    parser.add_argument("--bootstrap", type=int, default=10000)
    parser.add_argument("--target-commit", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.bootstrap < 1000:
        parser.error("--bootstrap must be >= 1000")
    try:
        report = certify(args.games, bootstrap=args.bootstrap, target_commit=args.target_commit)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(f"candidate self-control: {report['status']} — seed_robust={report['seed_robust']}; "
          "no dispatch authority")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
