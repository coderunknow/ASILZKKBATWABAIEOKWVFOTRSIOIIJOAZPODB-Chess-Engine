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
import re
import sys


def fail(msg: str) -> None:
    print(f"AGGREGATE-REJECT: {msg}", file=sys.stderr)
    raise SystemExit(1)


def validate_candidate_schedule(
    games: list[dict], purpose: str, anchor: str, expected_openings: list[str] | None = None,
    batch: str = "",
) -> None:
    """Require exact schedule, seat, shard and retry provenance for every attempt."""
    if purpose == "candidate-screening":
        expected_games, games_per_opening = 100, 2
        if batch not in ("A", "B"):
            fail("candidate-screening aggregation requires Batch A or B")
    elif purpose == "candidate-self-control":
        expected_games, games_per_opening = 240, 4
        if batch != "CTRL":
            fail("candidate-self-control aggregation requires batch CTRL")
    else:
        return
    if expected_openings is None or len(expected_openings) != expected_games // games_per_opening:
        fail(f"{purpose}: registered opening suite has the wrong number of clusters")
    attempts_by_index: dict[int, dict[int, dict]] = {}
    counted_by_index: dict[int, dict] = {}
    by_opening: dict[str, list[dict]] = {}
    for game in games:
        index = game.get("schedule_index")
        replay = game.get("replay_depth")
        if type(index) is not int or not 0 <= index < expected_games:
            fail(f"{purpose}: invalid attempt schedule_index {index!r}")
        if type(replay) is not int or replay not in (0, 1):
            fail(f"{purpose}: invalid replay_depth {replay!r} at schedule_index {index}")
        if (type(game.get("counted")) is not bool
                or type(game.get("engine_error")) is not bool
                or type(game.get("adjudicated")) is not bool):
            fail(f"{purpose}: attempt {(index, replay)} lacks boolean counted/error/adjudication provenance")
        attempts = attempts_by_index.setdefault(index, {})
        if replay in attempts:
            fail(f"{purpose}: duplicate attempt {(index, replay)}")
        attempts[replay] = game
        replay_of = game.get("replay_of_schedule_index")
        if ((replay == 0 and replay_of is not None)
                or (replay == 1 and (type(replay_of) is not int or replay_of != index))):
            fail(f"{purpose}: attempt {(index, replay)} has inconsistent replay provenance")
        expected_pair = "AB" if index % 2 == 0 else "BA"
        expected_repetition = (index % games_per_opening) // 2
        if type(game.get("repetition")) is not int:
            fail(f"{purpose}: attempt {(index, replay)} has a non-integer repetition identity")
        expected_opening = expected_openings[index // games_per_opening]
        if purpose == "candidate-screening":
            expected_white, expected_black = (("flawless", anchor) if expected_pair == "AB"
                                              else (anchor, "flawless"))
            expected_shard = f"candidate-screening-{batch}-{anchor}-{index // 2}"
        else:
            expected_white, expected_black = "flawless", "flawless"
            expected_shard = f"candidate-self-control-CTRL-candidate-self-control-{index // 4}"
        if (str(game.get("white", "")).casefold() != expected_white
                or str(game.get("black", "")).casefold() != expected_black
                or game.get("color_pair") != expected_pair
                or game.get("repetition") != expected_repetition):
            fail(f"{purpose}: attempt {(index, replay)} has incorrect seat or repetition identity")
        if game.get("opening") != expected_opening:
            fail(f"{purpose}: attempt {(index, replay)} does not match registered opening {expected_opening!r}")
        if game.get("_shard_id") != expected_shard:
            fail(f"{purpose}: attempt {(index, replay)} has incorrect shard identity")
        if game.get("counted") is True:
            if game.get("engine_error") or game.get("adjudicated") is not True:
                fail(f"{purpose}: engine-error or not-explicitly-adjudicated record marked counted at {index}")
            if game.get("result") not in ("1-0", "0-1", "1/2-1/2"):
                fail(f"{purpose}: counted attempt at schedule_index {index} has invalid result")
            if index in counted_by_index:
                fail(f"{purpose}: duplicate counted schedule_index {index}")
            counted_by_index[index] = game
            by_opening.setdefault(expected_opening, []).append(game)
        elif not game.get("engine_error"):
            fail(f"{purpose}: uncounted non-error attempt at schedule_index {index}")
    if set(counted_by_index) != set(range(expected_games)):
        fail(f"{purpose}: expected exactly {expected_games} counted schedule slots")
    if len(by_opening) != expected_games // games_per_opening:
        fail(f"{purpose}: expected {expected_games // games_per_opening} opening clusters")
    for index in range(expected_games):
        initial = attempts_by_index.get(index, {}).get(0)
        replay = attempts_by_index.get(index, {}).get(1)
        if initial is None:
            fail(f"{purpose}: schedule slot {index} has no initial attempt")
        if initial.get("engine_error"):
            if initial.get("counted") is True or replay is None:
                fail(f"{purpose}: failed initial attempt {index} lacks its registered replay")
            if replay.get("engine_error") or replay.get("counted") is not True:
                fail(f"{purpose}: replay of failed initial attempt {index} did not yield a valid counted result")
        elif initial.get("counted") is not True or replay is not None:
            fail(f"{purpose}: schedule slot {index} has an invalid or unnecessary replay")
    for opening, cluster in by_opening.items():
        indices = sorted(game["schedule_index"] for game in cluster)
        if len(cluster) != games_per_opening or indices != list(range(indices[0], indices[0] + games_per_opening)):
            fail(f"{purpose}: opening {opening!r} does not have one complete contiguous paired cluster")
        if indices[0] % games_per_opening != 0:
            fail(f"{purpose}: opening {opening!r} is split across schedule clusters")


def validate_candidate_shard_commit(meta: dict, purpose: str, target_commit: str, shard_path: str) -> None:
    """Bind candidate shard provenance to the frozen source/harness commit."""
    if purpose in {"candidate-screening", "candidate-self-control"}:
        if meta.get("git_commit") != target_commit:
            fail(
                f"shard {shard_path}: git_commit {meta.get('git_commit')!r} "
                f"!= frozen target commit {target_commit!r}"
            )


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
    ap.add_argument("--opening-suite", default="")
    ap.add_argument("--evidence-purpose", default="")
    ap.add_argument("--candidate-sha256", default="")
    ap.add_argument("--dispatch-seed", type=int)
    ap.add_argument("--target-commit", default="")
    ap.add_argument("--repetitions", type=int)
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()
    candidate_purposes = {"candidate-screening", "candidate-self-control"}
    candidate_openings = None
    if args.evidence_purpose in candidate_purposes:
        if not args.opening_suite or not os.path.isfile(args.opening_suite):
            fail("candidate evidence requires the registered opening-suite file")
        if sha256_file(args.opening_suite) != args.opening_suite_sha256:
            fail("candidate opening-suite file hash differs from the registered identity")
        candidate_openings = []
        with open(args.opening_suite, encoding="utf-8") as suite_file:
            for raw in suite_file:
                line = raw.strip()
                if line and not line.startswith("#"):
                    if "|" not in line:
                        fail(f"invalid candidate opening-suite line {line!r}")
                    candidate_openings.append(line.split("|", 1)[0].strip())
        if len(set(candidate_openings)) != len(candidate_openings):
            fail("candidate opening suite has duplicate cluster names")
        if not re.fullmatch(r"[0-9a-f]{64}", args.candidate_sha256 or ""):
            fail("candidate evidence requires a valid candidate SHA-256")
        if args.candidate_sha256 != args.engine_sha256:
            fail("candidate SHA-256 must equal the aggregated candidate engine SHA-256")
        if not re.fullmatch(r"[0-9a-f]{40}", args.target_commit or ""):
            fail("candidate evidence requires the full frozen target commit")
        if args.dispatch_seed is None or args.repetitions is None or args.repetitions <= 0:
            fail("candidate evidence requires its preregistered dispatch seed and repetitions")
    elif args.candidate_sha256:
        fail("candidate SHA-256 may only be attached to candidate qualification evidence")

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
        validate_candidate_shard_commit(
            meta, args.evidence_purpose, args.target_commit, sd
        )
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
    validate_candidate_schedule(
        merged_games, args.evidence_purpose, args.anchor, candidate_openings, args.batch
    )

    if len(hw_models) > 1:
        # Documented environment (benches/anchor-pool.json, docs/ENVIRONMENT.md):
        # hosted runners are MIXED (Azure EPYC 9V74 / AWS Xeon 6975P-C, same
        # 4 vCPU/15GiB shape). Hardware is calibration METADATA recorded per
        # shard (with the SF10 factor), not an identity field; transferability
        # is validated by the two null controls. Fail only if a shard lacks it.
        if any(m in ("None", "unknown", "") for m in hw_models):
            fail(f"shard missing hardware calibration record: {hw_models}")
        print(f"WARNING: mixed runner hardware across shards (documented, recorded): {sorted(hw_models)}")

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
        "time_control": {
            "mode": "clock",
            "period_moves": args.tc_moves,
            "period_seconds": args.tc_seconds,
        },
        "shard_ids": sorted(seen_shard_ids),
        "n_shards": len(seen_shard_ids),
        "n_attempts": len(merged_games),
        "n_counted": counted,
        "n_engine_errors": total_engine_errors,
        "n_unadjudicated": total_unadj,
        "hardware_cpu_model": sorted(hw_models),
        "merged_sha256": sha256_file(args.out),
    }
    if args.evidence_purpose:
        manifest["evidence_purpose"] = args.evidence_purpose
    if args.evidence_purpose in candidate_purposes:
        manifest.update({
            "candidate_sha256": args.candidate_sha256,
            "dispatch_seed": args.dispatch_seed,
            "target_commit": args.target_commit,
            "repetitions": args.repetitions,
            "evidence_class": "selection-only" if args.evidence_purpose == "candidate-screening"
                              else "candidate-null-control",
        })
    with open(args.manifest, "w") as f:
        json.dump(manifest, f, indent=2)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
