#!/usr/bin/env python3
"""recover_screen2.py — repo-portable SCREEN-2 evidence recovery + verification.

Reproduces from a fresh checkout what the hosted evidence job commits, so a
failed/incomplete evidence push can be recovered and independently checked:

  1. Downloads all shard artifacts of a completed rating-run via `gh run download`
     (fallback: artifact-zip REST download with $GITHUB_TOKEN).
  2. Strict-aggregates them with scripts/aggregate_shards.py (frozen identity checks).
  3. Byte-compares the aggregated games.jsonl with the committed evidence copy.
  4. Checks the ENGINE-1 flag-rate acceptance (<= 10 flag losses / 120 games).
  5. Reports the runner-built engine binary SHA-256 for pinning in PREREGISTRATION.md.

Usage:
  python3 scripts/recover_screen2.py <run_id_vs_topple-0.1.1> <run_id_vs_topple-0.2.1>

A single anchor slot also accepts '+'-joined run IDs whose artifacts are MERGED
into one shards-root before aggregation (single-shard retry recovery):
  python3 scripts/recover_screen2.py 43714600687 43714620645+<retry_run_id>

Environment: requires `gh` on PATH (or GITHUB_TOKEN for the REST fallback).
Anchor identities/hashes below are the FROZEN pool entries (benches/anchor-pool.json);
they are hard-coded here to keep this recovery script independent of dispatch inputs.
"""
import hashlib, json, math, os, subprocess, sys, tempfile, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_REPO = "coderunknow/FlawLessChess"
ANCHORS = {0: ("topple-0.1.1", "db75d4d816710b77810fb3b5d544b0f6f025542ff992a1c12301d7dffad5ffac"),
           1: ("topple-0.2.1", "c5443e6f81aef3bfa033ee6233e2064c9fcc50c64cd41f74adbbf66d61c38ac6")}
SUITE = "2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96"
PINNED_ENGINE = "9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428"
PUBLISHED = {"topple-0.1.1": 2324, "topple-0.2.1": 2439}

def _token():
    t = os.environ.get("GITHUB_TOKEN", "")
    if t:
        return t
    tf = os.environ.get("GITHUB_TOKEN_FILE", "")
    if tf and os.path.exists(tf):
        return open(tf).read().strip()
    return ""

def _curl_api(path, out_path=None):
    t = _token()
    if not t:
        sys.exit("no gh on PATH and neither GITHUB_TOKEN nor GITHUB_TOKEN_FILE set")
    cmd = ["curl", "-sSL", "--fail", "-H", f"Authorization: Bearer {t}",
           f"https://api.github.com/{path.lstrip('/')}"]
    if out_path:
        cmd += ["-o", out_path]
    r = subprocess.run(cmd, capture_output=not out_path, text=not out_path)
    if r.returncode != 0:
        sys.exit(f"curl api failed for {path}: {getattr(r, 'stderr', '')[:300]}")
    return r

def api(path, *extra):
    if subprocess.run(["which", "gh"], capture_output=True).returncode == 0:
        out = subprocess.run(["gh", "api", path, *extra], capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit(f"gh api failed: {out.stderr[:300]}")
        return json.loads(out.stdout)
    r = _curl_api(path)
    return json.loads(r.stdout)

def _shard_meta_count(root):
    import glob
    return len(glob.glob(os.path.join(root, "**", "meta.json"), recursive=True))

def download_run(run, dest, expect=None):
    """Pull all artifacts of a workflow run into dest/ (gh preferred, curl fallback).

    expect = number of shard meta.json files the run must yield; when the gh CLI
    path under-delivers (its artifact listing is paginated and silently truncates
    for runs with >30 artifacts), fall through to the paginated REST fallback."""
    os.makedirs(dest, exist_ok=True)
    if subprocess.run(["which", "gh"], capture_output=True).returncode == 0 and \
       subprocess.run(["gh", "run", "download", run, "-D", dest, "-R", ENGINE_REPO],
                      capture_output=True, text=True).returncode == 0 and \
       (expect is None or _shard_meta_count(dest) >= expect):
        return True
    arts, page = [], 1
    while True:
        resp = api(f"repos/{ENGINE_REPO}/actions/runs/{run}/artifacts?per_page=100&page={page}")
        arts.extend(resp["artifacts"])
        if len(resp["artifacts"]) < 100:
            break
        page += 1
    for a in arts:
        # Artifact zips are BINARY: download to a file (curl -o keeps the stream
        # in binary mode). Reading r.stdout in text mode would corrupt the zip
        # (and the pre-fix code passed b"" to ZipFile whenever stdout was a str,
        # so this fallback could never succeed).
        zpath = os.path.join(dest, f"{a['id']}.zip")
        _curl_api(f"repos/{ENGINE_REPO}/actions/artifacts/{a['id']}/zip", out_path=zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(os.path.join(dest, a["name"]))
        os.remove(zpath)
    if expect is not None and _shard_meta_count(dest) < expect:
        sys.exit(f"download_run: only {_shard_meta_count(dest)} of {expect} shard metas after both paths")
    return True

def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    engine_hashes, overall = set(), True
    for idx, spec in enumerate(sys.argv[1:]):
        anchor, anchor_sha = ANCHORS[idx]
        runs = spec.split("+")
        primary, retries = runs[0], runs[1:]
        info = api(f"repos/{ENGINE_REPO}/actions/runs/{primary}")
        ok = info.get("status") == "completed" and info.get("conclusion") == "success"
        print(f"run {primary} (vs {anchor}): {info.get('status')}/{info.get('conclusion')} ok={ok}")
        # In a merged-retry slot the primary's workflow conclusion is EXPECTED to
        # be failure (documented infra failure; that is why the retry exists) —
        # artifact-level verification via the strict aggregation is the gate.
        if not retries:
            overall &= ok
        # Merged-retry slot: primary run + '+'-joined retry runs (single-shard
        # infra-failure recovery). Retry runs only contribute artifacts; the
        # strict aggregation below is the actual gate, so their workflow
        # conclusion (evidence job skipped) is reported but not gating —
        # BUT they must be terminal before we aggregate.
        rdir = os.path.join(tempfile.gettempdir(), f"scr2-{primary}")
        if retries:
            rdir = os.path.join(tempfile.gettempdir(), f"scr2-slot{idx}-merged")
            os.makedirs(rdir, exist_ok=True)
        # Per-run shard expectation: a single-run slot needs all 60; in a merged
        # slot the primary run legitimately holds only 60-len(retries) shards —
        # the retries supply the rest (each retry run = 1 shard here).
        download_run(primary, os.path.join(rdir, f"run-{primary}") if retries else rdir,
                     expect=60 if not retries else 60 - len(retries))
        for rr in retries:
            rinfo = api(f"repos/{ENGINE_REPO}/actions/runs/{rr}")
            rstate = f"{rinfo.get('status')}/{rinfo.get('conclusion')}"
            print(f"retry run {rr} (vs {anchor}): {rstate}")
            if rinfo.get("status") != "completed":
                print(f"RETRY RUN {rr} NOT TERMINAL — refusing to aggregate partial artifacts")
                overall = False
                continue
            download_run(rr, os.path.join(rdir, f"run-{rr}"), expect=1)
        if _shard_meta_count(rdir) != 60:
            sys.exit(f"merged shards-root holds {_shard_meta_count(rdir)} of 60 shard metas — fail closed")
        out_dir = os.path.join(tempfile.gettempdir(), f"scr2-agg-{anchor}")
        os.makedirs(out_dir, exist_ok=True)
        # discover the runner engine hash from shard manifests, then strict-aggregate
        import glob
        eng = None
        for m in glob.glob(os.path.join(rdir, "**", "meta.json"), recursive=True):
            d = json.load(open(m))
            eng = d.get("white_artifact", {}).get("sha256")
            if eng: break
        if not eng:
            sys.exit("cannot discover runner engine hash from shard manifests")
        if eng != PINNED_ENGINE:
            print(f"HASH MISMATCH: runner built {eng}, pin is {PINNED_ENGINE} — fail closed")
            overall = False
            continue
        engine_hashes.add(eng)
        agg = subprocess.run(["python3", os.path.join(REPO, "scripts", "aggregate_shards.py"),
                              "--shards-root", rdir, "--batch", "A", "--anchor", anchor,
                              "--engine-sha256", eng, "--anchor-sha256", anchor_sha,
                              "--opening-suite-sha256", SUITE, "--tc-moves", "40",
                              "--tc-seconds", "900", "--expected-shards", "60",
                              "--out", os.path.join(out_dir, "games.jsonl"),
                              "--manifest", os.path.join(out_dir, "manifest.json")],
                             capture_output=True, text=True)
        if agg.returncode != 0:
            print(f"AGGREGATION FAILED for {anchor}: {agg.stderr[-400:]}"); overall = False; continue
        man = json.load(open(os.path.join(out_dir, "manifest.json")))
        committed = os.path.join(REPO, "benches", "evidence", "screening-2", anchor, "games.jsonl")
        h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
        match = os.path.exists(committed) and h(committed) == h(os.path.join(out_dir, "games.jsonl"))
        print(f"  aggregated {man['n_counted']} games; engine_sha256={eng[:16]}…; "
              f"bytes_match_committed={match}")
        overall &= match
        games = [json.loads(l) for l in open(os.path.join(out_dir, "games.jsonl")) if l.strip()]
        # Flawless seat-perspective score: decisive by result+color, draws ALWAYS 0.5
        # (the pre-fix lambda scored flawless-as-black draws 1.0, inflating the
        # score/estimate printout — caught by cross-checking make_gate_plan.py;
        # flag-loss counting and committed evidence were never affected).
        def score(g):
            w = 1.0 if g["result"] == "1-0" else (0.0 if g["result"] == "0-1" else 0.5)
            return w if g["white"].casefold().startswith("flawless") else 1.0 - w
        losses = [g for g in games if score(g) == 0.0]
        flags = sum(1 for g in losses if g.get("reason") == "flag")
        s = sum(score(g) for g in games) / len(games)
        d = -400 * math.log10(1 / s - 1) if 0 < s < 1 else float("inf")
        print(f"  flawless W={sum(1 for g in games if score(g)==1.0)} L={len(losses)} "
              f"D={sum(1 for g in games if score(g)==0.5)}; flag losses={flags} "
              f"(<=10: {'PASS' if flags <= 10 else 'FAIL'}); score={s:.4f} "
              f"est={PUBLISHED[anchor] + d:.1f}")
        overall &= flags <= 10
    print(f"\nengine hashes: {sorted(engine_hashes)}")
    print(f"OVERALL: {'PASS' if overall and len(engine_hashes) == 1 else 'ATTENTION REQUIRED'}")
    return 0 if overall else 1

if __name__ == "__main__":
    sys.exit(main())
