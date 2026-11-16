#!/usr/bin/env python3
"""test_aggregate_60.py — synthetic 60-shard aggregation rehearsal for the SHAPE-1
screening shape. Builds 60 faithful shard dirs (2 games each, real schema fields),
then asserts aggregate_shards.py accepts them (120 games merged). Proves the strict
aggregator has no 15-shard-specific assumptions before real SCREEN-2R evidence lands."""
import json, os, shutil, subprocess, sys, tempfile

PIN = "9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428"
ANCHOR = "db75d4d816710b77810fb3b5d544b0f6f025542ff992a1c12301d7dffad5ffac"
SUITE = "2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96"

root = tempfile.mkdtemp(prefix="agg60-")
for i in range(60):
    lo, hi = i * 2, (i + 1) * 2
    d = os.path.join(root, f"shard-{i}")
    os.makedirs(d)
    meta = {
        "manifest_version": 2, "completion_status": "completed",
        "shard_id": f"screening-2-A-topple-0.1.1-{i}", "batch_id": "A",
        "n_games_planned": 2, "n_attempts": 2,
        "white_cmd": "./target/release/flawless uci", "black_cmd": "./anchors/topple-0.1.1",
        "white_name": "flawless", "black_name": "topple-0.1.1",
        "white_artifact": {"cmd": "./target/release/flawless uci",
                           "binary_path": "./target/release/flawless",
                           "artifacts": [{"path": "./target/release/flawless", "sha256": PIN}],
                           "sha256": PIN},
        "black_artifact": {"cmd": "./anchors/topple-0.1.1",
                           "binary_path": "./anchors/topple-0.1.1",
                           "artifacts": [{"path": "./anchors/topple-0.1.1", "sha256": ANCHOR}],
                           "sha256": ANCHOR},
        "openings_file_sha256": SUITE,
        "time_control": {"mode": "clock", "period_moves": 40, "period_seconds": 900.0,
                         "increment_seconds": 0.0, "period_policy": "add"},
        "schedule": {"repetitions": 1, "n_scheduled": 120,
                     "shard": {"shard_index": i, "shard_count": 60,
                               "schedule_lo": lo, "schedule_hi": hi}},
        "git_commit": "0" * 40,
        "hardware": {"cpu_model": "SyntheticTestCPU"},
    }
    with open(os.path.join(d, "meta.json"), "w") as f:
        json.dump(meta, f)
    with open(os.path.join(d, "games.jsonl"), "w") as f:
        for si in (lo, hi - 1):
            g = {"opening": "o", "white": "flawless" if si % 2 == 0 else "topple-0.1.1",
                 "black": "topple-0.1.1" if si % 2 == 0 else "flawless",
                 "result": "1/2-1/2", "reason": None, "moves": "e2e4 e7e5", "fen": None,
                 "move_count": 2, "engine_error": False, "error_side": None,
                 "engine_error_turns": [], "adjudicated": None,
                 "clock_ms_at_end": 1000, "wall_seconds": 3000.0,
                 "color_pair": si // 2, "game_index": si, "schedule_index": si,
                 "repetition": 0, "replay_of_schedule_index": None, "replay_depth": 0,
                 "counted": True}
            f.write(json.dumps(g, sort_keys=True) + "\n")

out = os.path.join(root, "agg")
r = subprocess.run([sys.executable, "scripts/aggregate_shards.py",
                    "--shards-root", root, "--batch", "A", "--anchor", "topple-0.1.1",
                    "--engine-sha256", PIN, "--anchor-sha256", ANCHOR,
                    "--opening-suite-sha256", SUITE, "--tc-moves", "40",
                    "--tc-seconds", "900", "--expected-shards", "60",
                    "--out", os.path.join(out, "games.jsonl"),
                    "--manifest", os.path.join(out, "manifest.json")],
                   capture_output=True, text=True)
ok = r.returncode == 0
n = len([l for l in open(os.path.join(out, "games.jsonl"))]) if ok else 0
shutil.rmtree(root, ignore_errors=True)
print(f"aggregate 60-shard synthetic: rc={r.returncode} games={n} {'PASS' if ok and n == 120 else 'FAIL'}")
if not ok:
    print(r.stderr[-600:])
sys.exit(0 if ok and n == 120 else 1)
