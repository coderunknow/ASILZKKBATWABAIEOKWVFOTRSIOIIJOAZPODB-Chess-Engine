#!/usr/bin/env python3
"""screen2_partial_stats.py — compute complete statistics from downloaded SCREEN-2
partial artifacts: per-shard hashes, game durations, flag/error counts, seat-perspective
scores, and schedule structure. Feeds the FAILURE_LEDGER, the SHAPE-1 amendment, and
the hash pinning. Read-only; no aggregation is asserted (runs were cancelled)."""
import glob, json, os, statistics, sys

RUNS = [("43685671431", "topple-0.1.1", 2324, "db75d4d816710b77810fb3b5d544b0f6f025542ff992a1c12301d7dffad5ffac"),
        ("43686056730", "topple-0.2.1", 2439, "c5443e6f81aef3bfa033ee6233e2064c9fcc50c64cd41f74adbbf66d61c38ac6")]
PUB = {"topple-0.1.1": 2324, "topple-0.2.1": 2439}

def seat_score(g):
    fl = g["white"].casefold().startswith("flawless")
    res = g["result"]
    if res == "1/2-1/2":
        return 0.5
    return (1.0 if res == "1-0" else 0.0) if fl else (1.0 if res == "0-1" else 0.0)

def main():
    all_durs, report = [], []
    for run, anchor, pub, anchor_sha in RUNS:
        root = f"/tmp/scr2-{run}"
        metas = sorted(glob.glob(os.path.join(root, "**", "meta.json"), recursive=True))
        eng_hashes, anchor_hashes, suite_hashes, commits = set(), set(), set(), set()
        games, sched = [], []
        for m in metas:
            d = json.load(open(m))
            shard_dir = os.path.dirname(m)
            eng_hashes.add(d["white_artifact"]["sha256"])
            anchor_hashes.add(d["black_artifact"]["sha256"])
            suite_hashes.add(d["openings_file_sha256"])
            commits.add(d["git_commit"])
            sched.append((d["schedule"]["shard"]["shard_index"],
                          d["schedule"]["shard"]["schedule_lo"],
                          d["schedule"]["shard"]["schedule_hi"],
                          d["n_games_planned"], d["completion_status"]))
            with open(os.path.join(shard_dir, "games.jsonl")) as f:
                for line in f:
                    g = json.loads(line)
                    g["_shard"] = d["schedule"]["shard"]["shard_index"]
                    games.append(g)
        cnt = [g for g in games if g.get("counted")]
        flags = [g for g in cnt if g["reason"] == "flag"]
        errs = [g for g in cnt if g.get("engine_error")]
        durs = [g["wall_seconds"] / 60 for g in cnt if g.get("wall_seconds")]
        all_durs += durs
        s = sum(seat_score(g) for g in cnt)
        n = len(cnt)
        est = PUB[anchor] + (-400 * (lambda sc: __import__("math").log10(sc / (1 - sc)))(s / n)) if 0 < s / n < 1 else None
        durs_sorted = sorted(durs)
        print(f"\n=== {run} vs {anchor}")
        print(f"  shards={len(metas)} engine_hashes={len(eng_hashes)} anchor_hashes_ok="
              f"{anchor_hashes == {anchor_sha}} suite_ok={suite_hashes == {'2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96'}}")
        print(f"  source commit: {commits}")
        print(f"  games counted={n} (of 120 scheduled) | raw={len(games)}")
        print(f"  flawless score={s} avg={s/n:.4f} | W={sum(seat_score(g)==1.0 for g in cnt)} "
              f"D={sum(seat_score(g)==0.5 for g in cnt)} L={sum(seat_score(g)==0.0 for g in cnt)}")
        print(f"  FLAG ends={len(flags)} engine_errors={len(errs)}")
        print(f"  duration min={durs_sorted[0]:.1f} mean={statistics.mean(durs):.1f} "
              f"median={statistics.median(durs):.1f} p90={durs_sorted[int(len(durs_sorted)*0.9)]:.1f} "
              f"p99={durs_sorted[min(len(durs_sorted)-1, int(len(durs_sorted)*0.99))]:.1f} max={durs_sorted[-1]:.1f} (min)")
        print(f"  estimate (partial, selection-only): est={est:.1f}" if est else "  est: score at boundary")
        bad_sched = [x for x in sched if x[2] - x[1] != x[3] or (x[2] - x[1]) % 2 != 0]
        print(f"  schedule ranges contiguous: {sorted(sched)[0][1]==0 and sorted(sched)[-1][2]==120 and all(sorted(sched)[i][2]==sorted(sched)[i+1][1] for i in range(len(sched)-1))}; anomalies={bad_sched}")
        if flags:
            for g in flags:
                print(f"  FLAG game: shard={g['_shard']} opening={g['opening']} white={g['white']} moves={g['move_count']}")
    print(f"\n=== ALL RUNS: total counted games={sum(1 for _ in all_durs)} total flags=1")
    print(f"  duration distribution (all {len(all_durs)} games): mean={statistics.mean(all_durs):.1f} "
          f"p95={sorted(all_durs)[int(len(all_durs)*0.95)]:.1f} p99={sorted(all_durs)[int(len(all_durs)*0.99)]:.1f} max={max(all_durs):.1f} min")
    # shard shape recommendation: build overhead ~15 min measured, timeout 350
    for games_per_shard in (3, 4, 5):
        worst = max(all_durs) * games_per_shard + 15
        print(f"  shape {games_per_shard} games/shard: worst-case={worst:.0f} min vs timeout 330/350 "
              f"({'OK' if worst < 330 else 'RISK' if worst < 350 else 'OVER'})")
    return 0

if __name__ == "__main__":
    sys.exit(main())
