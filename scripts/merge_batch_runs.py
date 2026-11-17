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
    ap.add_argument("--suite", default=None,
                    help="registered opening suite; required for the exact 100-game design")
    a = ap.parse_args()
    expected_openings = None
    if a.expected_games == 100:
        if not a.suite:
            die("--suite is required for the 100-game/50-opening design")
        with open(a.suite, encoding="utf-8") as handle:
            expected_openings = [
                line.partition("|")[0].strip()
                for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
        if len(expected_openings) != 50 or len(set(expected_openings)) != 50:
            die("registered suite must contain exactly 50 unique opening clusters")

    if not os.path.isdir(a.runs_root):
        die(f"runs root does not exist: {a.runs_root}")
    if os.path.exists(a.out):
        die(f"refusing to overwrite existing canonical evidence directory: {a.out}")
    runs = sorted(d for d in os.listdir(a.runs_root) if d.startswith("run-"))
    if not runs:
        die(f"no run-* dirs under {a.runs_root}")
    # Identity keys are the ones aggregate_shards.py actually writes into each
    # run manifest. (An earlier key list — white_name/black_name/time_control/
    # schedule/n_scheduled — matched no manifest field, so the identity check
    # compared all-None dicts and could never fire. Caught in the pre-campaign
    # audit 2026-11-16; see FAILURE_LEDGER.)
    id_keys = ("batch", "anchor", "engine_sha256", "anchor_sha256",
               "opening_suite_sha256", "time_control")
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
        if man.get("time_control") != {
            "mode": "clock", "period_moves": 40, "period_seconds": 900.0
        }:
            die(f"{r}: time_control is not the preregistered 40/15 wall-clock format")
        games = [json.loads(l) for l in open(gp, encoding="utf-8") if l.strip()]
        counted = [g for g in games if g.get("counted") is True]
        if man.get("n_attempts") != len(games):
            die(f"{r}: manifest n_attempts {man.get('n_attempts')} != games.jsonl records {len(games)}")
        if man.get("n_counted") != len(counted):
            die(f"{r}: manifest n_counted {man.get('n_counted')} != recomputed {len(counted)}")
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

    idx = [g.get("schedule_index") for g in all_games]
    if any(type(value) is not int for value in idx):
        die("a counted game has a missing/non-integer schedule_index")
    if len(set(idx)) != len(idx):
        die(f"duplicate schedule_index values across runs ({len(idx)} games, {len(set(idx))} unique)")
    if sorted(idx) != list(range(a.expected_games)):
        missing = sorted(set(range(a.expected_games)) - set(idx))
        extra = sorted(set(idx) - set(range(a.expected_games)))
        die(f"schedule coverage broken: {len(missing)} missing (first: {missing[:5]}), "
            f"{len(extra)} out-of-range (first: {extra[:5]}), total counted {len(idx)}")

    all_games.sort(key=lambda g: g["schedule_index"])
    if expected_openings is not None:
        if len(expected_openings) != 50 or len(set(expected_openings)) != 50:
            die("registered opening suite must contain exactly 50 unique labels")
        if len({g.get("opening") for g in all_games}) != 50:
            die("counted records must cover exactly the 50 registered opening clusters")
        for index, game in enumerate(all_games):
            expected_opening = expected_openings[index // 2]
            expected_pair = "AB" if index % 2 == 0 else "BA"
            if game.get("opening") != expected_opening or game.get("color_pair") != expected_pair:
                die(f"schedule index {index}: expected {expected_opening}/{expected_pair}, "
                    f"got {game.get('opening')}/{game.get('color_pair')}")
            if game.get("engine_error") or game.get("adjudicated") is False:
                die(f"counted schedule index {index} has engine_error/unadjudicated metadata")
            if game.get("result") not in ("1-0", "0-1", "1/2-1/2"):
                die(f"counted schedule index {index} has invalid result {game.get('result')!r}")
            if str(game.get("white", "")).casefold() != "flawless" or str(game.get("black", "")).casefold() != str(a.anchor).casefold():
                die(f"counted schedule index {index} has wrong seated engine identities")
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
        "merge_rule": "counted games only; schedule_index must cover 0..n-1 exactly once; "
                       "50 registered openings × AB/BA",
    })
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump(man, f, indent=2, sort_keys=True)
        f.write("\n")
    print(f"merge_batch_runs: OK — {len(all_games)} counted games from {len(runs)} runs -> {a.out} "
          f"(merged_sha256 {sha[:16]}…)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
