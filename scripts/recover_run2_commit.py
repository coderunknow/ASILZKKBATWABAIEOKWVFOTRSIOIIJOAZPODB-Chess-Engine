#!/usr/bin/env python3
"""recover_run2_commit.py — one-shot SCREEN-2R run-2 recovery:

  1. recover_screen2.py 43714600687 43714620645+<RETRY> (merged-slot strict aggregation)
  2. If topple-0.2.1 evidence is not yet committed, commit the freshly aggregated
     manifest+games (from /tmp/scr2-agg-topple-0.2.1) to the PR branch and push.
  3. Re-run recover_screen2.py to confirm bytes_match_committed=True for BOTH anchors.

Usage: python3 scripts/recover_run2_commit.py <retry_run_id>
"""
import os, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij"
if len(sys.argv) != 2:
    sys.exit(__doc__)
retry = sys.argv[1]

env = dict(os.environ, GITHUB_TOKEN_FILE="/home/z/my-project/upload/folder/d8bc2a7f/Github Token.txt")

def run(cmd, **kw):
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, env=env, **kw)

r1 = run(["python3", os.path.join(REPO, "scripts", "recover_screen2.py"),
          "43714600687", f"43714620645+{retry}"])
agg_games = "/tmp/scr2-agg-topple-0.2.1/games.jsonl"
agg_man = "/tmp/scr2-agg-topple-0.2.1/manifest.json"
dest = os.path.join(REPO, "benches", "evidence", "screening-2", "topple-0.2.1")
# Gate on the AGGREGATION ITSELF (not recover's overall exit code, which also
# includes the expected pre-commit bytes_match=False): 60 shards, 120 games,
# pinned engine hash, zero engine errors — only then may evidence be committed.
import json, hashlib
man = json.load(open(agg_man)) if os.path.exists(agg_man) else {}
agg_ok = (man.get("n_shards") == 60 and man.get("n_counted") == 120
          and man.get("n_engine_errors") == 0
          and man.get("engine_sha256") == "9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428"
          and os.path.exists(agg_games)
          and sum(1 for _ in open(agg_games)) == 120)
if not agg_ok:
    print("AGGREGATION INVALID — not committing anything (fail closed)")
    sys.exit(1)
if os.path.exists(os.path.join(dest, "games.jsonl")):
    print("topple-0.2.1 evidence already committed — skipping commit step")
else:
    os.makedirs(dest, exist_ok=True)
    import shutil
    shutil.copy(agg_games, os.path.join(dest, "games.jsonl"))
    shutil.copy(agg_man, os.path.join(dest, "manifest.json"))
    for cmd in (["git", "add", "benches/evidence/screening-2/topple-0.2.1"],
                ["git", "commit", "-m",
                 f"evidence: raw per-game results (screening-2 A topple-0.2.1, merged runs 43714620645+{retry}; canonical recovery via recover_screen2.py)"],
                ["git", "push", "origin", f"HEAD:refs/heads/{BRANCH}"]):
        rc = run(cmd, cwd=REPO).returncode
        if rc != 0 and not (cmd[0] == "git" and cmd[1] == "commit"):
            sys.exit(f"FAILED: {cmd}")
print("\n=== re-verify committed evidence ===")
r2 = run(["python3", os.path.join(REPO, "scripts", "recover_screen2.py"),
          "43714600687", f"43714620645+{retry}"])
sys.exit(r2.returncode)
