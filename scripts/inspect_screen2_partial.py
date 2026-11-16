#!/usr/bin/env python3
"""inspect_screen2_partial.py — download and inspect the artifacts of CANCELLED
SCREEN-2 runs. Reports per-shard completeness, flag counts, game durations,
and every recorded hash, so the failure can be classified and the runner-built
engine hash can be pinned from REAL evidence. Strict aggregation is intentionally
NOT attempted here (cancelled shards are partial by definition; use
recover_screen2.py only for fully completed runs)."""
import glob, io, json, math, os, subprocess, sys, zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_REPO = "coderunknow/FlawLessChess"

def _token():
    t = os.environ.get("GITHUB_TOKEN", "")
    if not t:
        tf = os.environ.get("GITHUB_TOKEN_FILE", "")
        if tf and os.path.exists(tf):
            t = open(tf).read().strip()
    return t

def api(path):
    t = _token()
    r = subprocess.run(["curl", "-sSL", "--fail", "-H", f"Authorization: Bearer {t}",
                        f"https://api.github.com/{path.lstrip('/')}"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"api failed {path}: {r.stderr[:200]}")
    return json.loads(r.stdout)

def download(run, dest):
    os.makedirs(dest, exist_ok=True)
    arts = api(f"repos/{ENGINE_REPO}/actions/runs/{run}/artifacts")["artifacts"]
    for a in arts:
        rd = subprocess.run(["curl", "-sSL", "--fail", "-H", f"Authorization: Bearer {_token()}",
                             f"https://api.github.com/repos/{ENGINE_REPO}/actions/artifacts/{a['id']}/zip"],
                            capture_output=True)
        if rd.returncode != 0:
            print(f"  download FAILED {a['name']}"); continue
        zipfile.ZipFile(io.BytesIO(rd.stdout)).extractall(os.path.join(dest, a["name"]))
    return len(arts)

def main():
    runs = [(sys.argv[1], "topple-0.1.1", 2324), (sys.argv[2], "topple-0.2.1", 2439)]
    engine_hashes, summary = set(), {}
    for run, anchor, pub in runs:
        dest = os.path.join("/tmp", f"scr2-{run}")
        n = download(run, dest)
        print(f"\n=== run {run} vs {anchor}: {n} artifacts -> {dest}")
        shards = sorted(glob.glob(os.path.join(dest, "**", "meta.json"), recursive=True))
        tot_games = tot_flags = 0
        durs = []
        for m in shards:
            d = json.load(open(m))
            name = os.path.basename(os.path.dirname(m))
            gpath = os.path.join(os.path.dirname(m), "games.jsonl")
            games = [json.loads(l) for l in open(gpath)] if os.path.exists(gpath) else []
            flags = sum(1 for g in games if g.get("reason") == "flag")
            tot_games += len(games); tot_flags += flags
            for key in ("game_seconds", "duration_s", "elapsed_s", "seconds"):
                if games and key in games[0]:
                    durs += [g[key] for g in games]
            # hashes recorded by this shard
            for side in ("white_artifact", "black_artifact"):
                for art in d.get(side, {}).get("artifacts", []):
                    if art.get("sha256") and art.get("name", "").casefold().startswith("flawless"):
                        engine_hashes.add(art["sha256"])
            print(f"  {name}: games={len(games)} flags={flags} "
                  f"engine={d.get('engine_sha256', '?')[:12]} suite={d.get('opening_suite_sha256', '?')[:10]} "
                  f"tc={d.get('tc', '?')} seed={d.get('seed', '?')}")
        print(f"  TOTAL games={tot_games}/120 flags={tot_flags}")
        if durs:
            durs.sort()
            mean = sum(durs) / len(durs)
            print(f"  per-game duration: n={len(durs)} mean={mean/60:.1f}min "
                  f"p50={durs[len(durs)//2]/60:.1f} p90={durs[int(len(durs)*0.9)]/60:.1f} max={durs[-1]/60:.1f}")
        summary[anchor] = (tot_games, tot_flags)
    print(f"\nengine hashes seen: {sorted(engine_hashes)}")
    print(f"summary: {summary}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
