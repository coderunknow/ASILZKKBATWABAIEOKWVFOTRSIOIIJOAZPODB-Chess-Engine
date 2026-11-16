#!/usr/bin/env python3
"""verify_run1_both_paths.py — independently verify run 43714600687's committed
SCREEN-2 evidence via BOTH recovery download paths:

  A (gh CLI):        `gh run download` → strict aggregate → byte-compare vs committed
  B (REST fallback): forced REST artifact-zip download (gh hidden) → same checks

Both paths must produce byte-identical games.jsonl AND match the committed copy.
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, types

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import recover_screen2 as rec

RUN = "43714600687"
COMMITTED = os.path.join(rec.REPO, "benches", "evidence", "screening-2", "topple-0.1.1", "games.jsonl")
h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()

def aggregate(rdir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    r = subprocess.run(["python3", os.path.join(rec.REPO, "scripts", "aggregate_shards.py"),
                        "--shards-root", rdir, "--batch", "A", "--anchor", "topple-0.1.1",
                        "--engine-sha256", rec.PINNED_ENGINE,
                        "--anchor-sha256", rec.ANCHORS[0][1],
                        "--opening-suite-sha256", rec.SUITE,
                        "--tc-moves", "40", "--tc-seconds", "900",
                        "--expected-shards", "60",
                        "--out", os.path.join(out_dir, "games.jsonl"),
                        "--manifest", os.path.join(out_dir, "manifest.json")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-600:])
        sys.exit(f"AGGREGATION FAILED ({rdir})")
    man = json.load(open(os.path.join(out_dir, "manifest.json")))
    return man

results = {}
# --- Path A: gh CLI ---
dA = os.path.join(tempfile.gettempdir(), f"vr2-A-{RUN}")
shutil.rmtree(dA, ignore_errors=True)
assert rec.download_run(RUN, dA, expect=60), "path A download failed"
aggA = tempfile.mkdtemp(prefix="vr2-aggA-")
manA = aggregate(dA, aggA)
results["A"] = (manA["n_shards"], manA["n_counted"], h(os.path.join(aggA, "games.jsonl")))

# --- Path B: REST fallback (gh forcibly hidden) ---
dB = os.path.join(tempfile.gettempdir(), f"vr2-B-{RUN}")
shutil.rmtree(dB, ignore_errors=True)
saved = rec.subprocess.run
rec.subprocess.run = lambda cmd, **kw: types.SimpleNamespace(returncode=1) if cmd[:2] == ["which", "gh"] \
    else saved(cmd, **kw)
try:
    assert rec.download_run(RUN, dB, expect=60), "path B download failed"
finally:
    rec.subprocess.run = saved
rest_agg = tempfile.mkdtemp(prefix="vr2-aggB-")
manB = aggregate(dB, rest_agg)
results["B"] = (manB["n_shards"], manB["n_counted"], h(os.path.join(rest_agg, "games.jsonl")))

committed_hash = h(COMMITTED)
print(f"committed games.jsonl sha256 = {committed_hash}")
for k, (ns, nc, hh) in results.items():
    print(f"path {k}: n_shards={ns} n_counted={nc} aggregated sha256={hh} "
          f"byte_match_committed={hh == committed_hash}")
ok = results["A"][2] == results["B"][2] == committed_hash and \
    results["A"][:2] == results["B"][:2] == (60, 120)
print("OVERALL:", "PASS — both download paths reproduce the committed evidence byte-identically" if ok else "FAIL")
sys.exit(0 if ok else 1)
