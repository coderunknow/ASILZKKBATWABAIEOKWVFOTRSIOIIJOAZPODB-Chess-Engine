#!/usr/bin/env python3
"""merge_batch_runs.py — produce the canonical confirmatory batch evidence dir
from the per-run evidence dirs committed by the rating-run `evidence` job
(benches/evidence/confirmatory/<anchor>/run-<run_id>/).

Fail-closed checks:
  * every run dir carries games.jsonl + manifest.json
  * identical identities across runs: engine/anchor binary SHA-256, suite SHA-256,
    tc, seed, batch, purpose, white/black names, schedule_sha256
  * every counted game's schedule_index covered EXACTLY once (no gaps, no dupes);
    uncounted replays are excluded and must reference a counted schedule_index
  * per-run game counts sum to the registered total (default 2040)
Output: <out>/games.jsonl (sorted by schedule_index) + manifest.json with
merged_sha256 over the canonical bytes and per-run provenance.
"""
import hashlib, json, os, sys

def die(msg):
    print(f"merge_batch_runs: FAIL — {msg}", file=sys.stderr)
    sys.exit(1)

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-root", required=True,
                    help="benches/evidence/confirmatory/<anchor>/ containing run-*/ dirs")
    ap.add_argument("--out", required=True, help="canonical dir, e.g. benches/evidence/batchA/<anchor>")
    ap.add_argument("--expected-games", type=int, default=2040)
    a = ap.parse_args()

    runs = sorted(d for d in os.listdir(a.runs_root) if d.startswith("run-"))
    if not runs:
        die(f"no run-* dirs under {a.runs_root}")
    # Identity keys are the ones aggregate_shards.py actually writes into each
    # run manifest. (An earlier key list — white_name/black_name/time_control/
    # schedule/n_scheduled — matched no manifest field, so the identity check
    # compared all-None dicts and could never fire. Caught in the pre-campaign
    # audit 2026-11-16; see FAILURE_LEDGER.)
    id_keys = ("batch", "anchor", "engine_sha256", "anchor_sha256",
               "opening_suite_sha256")
    all_games, provenance, ident0 = [], [], None
    total_planned = 0
    for r in runs:
        base = os.path.join(a.runs_root, r)
        gp, mp = os.path.join(base, "games.jsonl"), os.path.join(base, "manifest.json")
        if not (os.path.exists(gp) and os.path.exists(mp)):
            die(f"{r}: missing games.jsonl or manifest.json")
        man = json.load(open(mp))
        ident = {k: man.get(k) for k in id_keys}
        if ident0 is None:
            ident0 = ident
        elif ident != ident0:
            die(f"{r}: identity differs from first run: {ident} vs {ident0}")
        games = [json.loads(l) for l in open(gp) if l.strip()]
        counted = [g for g in games if g.get("counted")]
        replays = [g for g in games if not g.get("counted")]
        for g in replays:
            if "replay_of_schedule_index" not in g:
                die(f"{r}: uncounted game without replay_of_schedule_index: {g}")
        prov = {"run": r, "n_counted": len(counted), "n_replay": len(replays),
                "run_games_sha256": hashlib.sha256(open(gp, "rb").read()).hexdigest(),
                "manifest": man.get("merged_sha256")}
        if prov["manifest"] != prov["run_games_sha256"]:
            die(f"{r}: manifest merged_sha256 does not match games.jsonl bytes")
        provenance.append(prov)
        total_planned += len(counted)
        all_games += counted

    idx = [g["schedule_index"] for g in all_games]
    if len(set(idx)) != len(idx):
        die(f"duplicate schedule_index values across runs ({len(idx)} games, {len(set(idx))} unique)")
    if sorted(idx) != list(range(a.expected_games)):
        missing = sorted(set(range(a.expected_games)) - set(idx))
        extra = sorted(set(idx) - set(range(a.expected_games)))
        die(f"schedule coverage broken: {len(missing)} missing (first: {missing[:5]}), "
            f"{len(extra)} out-of-range (first: {extra[:5]}), total counted {len(idx)}")

    all_games.sort(key=lambda g: g["schedule_index"])
    os.makedirs(a.out, exist_ok=True)
    gp = os.path.join(a.out, "games.jsonl")
    with open(gp, "w") as f:
        for g in all_games:
            f.write(json.dumps(g, sort_keys=True) + "\n")
    sha = hashlib.sha256(open(gp, "rb").read()).hexdigest()
    man = dict(ident0)
    man.update({
        "merged_sha256": sha,
        "n_counted": len(all_games),
        "n_runs": len(runs),
        "provenance": provenance,
        "merge_rule": "counted games only; schedule_index must cover 0..n-1 exactly once",
    })
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump(man, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"merge_batch_runs: OK — {len(all_games)} counted games from {len(runs)} runs -> {a.out} "
          f"(merged_sha256 {sha[:16]}…)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
