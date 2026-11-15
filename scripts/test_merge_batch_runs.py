#!/usr/bin/env python3
"""test_merge_batch_runs.py — synthetic self-test for merge_batch_runs.py.
Builds two fake run dirs (8 counted games + 1 replay), asserts the merge
succeeds with full coverage, then asserts fail-closed on: duplicate schedule
index, identity mismatch, and missing manifest. Exits nonzero on any failure."""
import json, os, shutil, subprocess, sys, tempfile, hashlib

ROOT = tempfile.mkdtemp(prefix="mergetest-")

def game(i, counted=True, replay_of=None):
    return {"schedule_index": i, "counted": counted,
            "replay_of_schedule_index": replay_of, "result": "1/2-1/2",
            "white": "flawless", "black": "topple-0.1.1", "opening": "o1",
            "reason": " adjud. " if counted else "replay"}

def manifest(tc=None):
    return {"white_name": "flawless", "black_name": "topple-0.1.1",
            "time_control": tc or {"mode": "clock", "period_moves": 40},
            "openings_file_sha256": "suite", "schedule": {"schedule_sha256": "sched"},
            "n_scheduled": 8, "merged_sha256": None}

def write_run(name, games, man):
    d = os.path.join(ROOT, "runs", name)
    os.makedirs(d, exist_ok=True)
    gp = os.path.join(d, "games.jsonl")
    with open(gp, "w") as f:
        for g in games:
            f.write(json.dumps(g, sort_keys=True) + "\n")
    man = dict(man)
    man["merged_sha256"] = hashlib.sha256(open(gp, "rb").read()).hexdigest()
    with open(os.path.join(d, "manifest.json"), "w") as f:
        json.dump(man, f)

def run_merge(expect_fail=False):
    out = os.path.join(ROOT, "canon")
    shutil.rmtree(out, ignore_errors=True)
    r = subprocess.run([sys.executable, "scripts/merge_batch_runs.py",
                        "--runs-root", os.path.join(ROOT, "runs"),
                        "--out", out, "--expected-games", "8"],
                       capture_output=True, text=True)
    if expect_fail:
        assert r.returncode != 0, f"expected FAIL, got success: {r.stdout}"
        return r.stderr.strip()
    assert r.returncode == 0, f"expected OK, got: {r.stderr}"
    canon = [json.loads(l) for l in open(os.path.join(out, "games.jsonl"))]
    man = json.load(open(os.path.join(out, "manifest.json")))
    assert [g["schedule_index"] for g in canon] == list(range(8))
    assert man["n_counted"] == 8 and man["n_runs"] == 2
    assert man["merged_sha256"] == hashlib.sha256(open(os.path.join(out, "games.jsonl"), "rb").read()).hexdigest()
    return r.stdout.strip()

# 1. happy path: run-A covers 0-3 + a replay of 3, run-B covers 4-7
write_run("run-1", [game(i) for i in range(4)] + [game(3, counted=False, replay_of=3)], manifest())
write_run("run-2", [game(i) for i in range(4, 8)], manifest())
print("case1 OK:", run_merge())

# 2. duplicate schedule index across runs -> fail closed
write_run("run-2", [game(i) for i in range(3, 7)], manifest())
print("case2 (dup) OK:", run_merge(expect_fail=True))

# 3. identity mismatch (different tc) -> fail closed
write_run("run-2", [game(i) for i in range(4, 8)], manifest(tc={"mode": "clock", "period_moves": 20}))
print("case3 (identity) OK:", run_merge(expect_fail=True))

# 4. manifest bytes mismatch -> fail closed
d = os.path.join(ROOT, "runs", "run-2", "games.jsonl")
with open(d) as f: games = [json.loads(l) for l in f]
write_run("run-2", games, manifest())
os.chmod(d, 0o644)
with open(d, "a") as f: f.write("\n")
print("case4 (bytes) OK:", run_merge(expect_fail=True))

# 5. gap in coverage -> fail closed
write_run("run-2", [game(i) for i in range(5, 8)], manifest())
print("case5 (gap) OK:", run_merge(expect_fail=True))

shutil.rmtree(ROOT, ignore_errors=True)
print("merge_batch_runs self-test: ALL CASES PASS")
