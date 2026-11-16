#!/usr/bin/env python3
"""Statistics for match JSONL output: score, Elo difference, opening-clustered 95% bootstrap CI + bootstrap SD.

Method: after pairing games by opening, we bootstrap over *openings* (not individual
games) so the confidence interval respects opening clustering — paired openings produce
correlated game scores within a cluster. Elo difference uses the logistic model
  Elo = -400 * log10(1/s - 1),  s in (0, 1)
where s is the score fraction; s = 0.5 -> 0, s -> 1 -> +inf (reported as a bound).

This is a descriptive statistic over the games played. It is NOT a CCRL rating and
must not be presented as one.
"""
import argparse
import json
import math
import random
import sys
from collections import defaultdict


def load(path: str, include_engine_error: bool = False) -> tuple[list[dict], int]:
    games = []
    skipped = 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            g = json.loads(line)
            # Unadjudicated terminations (e.g. move_cap '*') are NEVER scored.
            if g.get("result") not in ("1-0", "0-1", "1/2-1/2"):
                skipped += 1
                continue
            # Engine-error attempts and other uncounted games are recorded in the
            # evidence stream but excluded from statistics unless explicitly included
            # for diagnostics (never for gate evidence).
            if (g.get("engine_error") or g.get("counted") is False) and not include_engine_error:
                skipped += 1
                continue
            games.append(g)
    return games, skipped


def elo_from_score(s: float) -> float:
    # Interior scores only; boundary handling lives in fmt_elo (never a clamped number).
    s = min(max(s, 1e-9), 1 - 1e-9)
    return -400.0 * math.log10(1.0 / s - 1.0)


def fmt_elo(s: float) -> str:
    # Boundary scores carry NO finite Elo estimate: report the boundary, never a clamped
    # number. Applies equally to point estimates and bootstrap interval endpoints.
    if s <= 0.0:
        return "boundary: zero observed score, true value unbounded below (no finite estimate)"
    if s >= 1.0:
        return "boundary: perfect observed score, true value unbounded above (no finite estimate)"
    return f"{elo_from_score(s):+.0f}" 


def score_of(result: str, perspective: str) -> float:
    if result == "1/2-1/2":
        return 0.5
    if perspective == "white":
        return 1.0 if result == "1-0" else 0.0
    return 1.0 if result == "0-1" else 0.0


def analyze(games: list[dict], focus: str):
    """focus: name of the engine whose score we analyze (from White's perspective-aware pairing)."""
    by_opening: dict[str, list[dict]] = defaultdict(list)
    for g in games:
        by_opening[g["opening"]].append(g)

    clusters: list[tuple[float, int]] = []  # (sum of scores from focus perspective, n games)
    for opening, gs in by_opening.items():
        tot = 0.0
        for g in gs:
            if g["white"] == focus:
                tot += score_of(g["result"], "white")
            elif g["black"] == focus:
                tot += score_of(g["result"], "black")
            else:
                raise ValueError(f"focus engine {focus!r} not present in game {g}")
        clusters.append((tot, len(gs)))
    return by_opening, clusters


def bootstrap_ci(clusters, n_boot: int, seed: int):
    rng = random.Random(seed)
    n = len(clusters)
    # cluster-level totals
    sums = [c[0] for c in clusters]
    ns = [c[1] for c in clusters]
    total_score = sum(sums)
    total_games = sum(ns)
    point = total_score / total_games if total_games else 0.5
    s_boot = []
    for _ in range(n_boot):
        ts = 0.0
        tg = 0
        for _ in range(n):
            i = rng.randrange(n)
            ts += sums[i]
            tg += ns[i]
        s_boot.append(ts / tg if tg else 0.5)
    # Standard deviation of the bootstrap distribution (Elo inference uses SDs, not
    # CI half-widths); also returned for downstream anchor math.
    mean = sum(s_boot) / len(s_boot)
    var = sum((x - mean) ** 2 for x in s_boot) / len(s_boot)
    s_sd = math.sqrt(var)
    s_boot.sort()
    lo = s_boot[int(0.025 * n_boot)]
    hi = s_boot[int(0.975 * n_boot) - 1]
    return point, lo, hi, s_sd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--focus", required=True, help="engine name to analyze")
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=20261114)
    ap.add_argument("--include-engine-error", action="store_true",
                    help="include games flagged engine-error (default: excluded, reported separately)")
    args = ap.parse_args()

    games, skipped = load(args.jsonl, include_engine_error=args.include_engine_error)
    if skipped:
        print(f"engine-error games excluded from statistics: {skipped}")
    if not games:
        print("no scorable games after exclusions", file=sys.stderr)
        return 2
    by_opening, clusters = analyze(games, args.focus)
    total_games = sum(c[1] for c in clusters)
    total_score = sum(c[0] for c in clusters)
    s, s_lo, s_hi, s_sd = bootstrap_ci(clusters, args.bootstrap, args.seed)
    print(f"games: {total_games}   openings (clusters): {len(clusters)}")
    print(f"score: {total_score:.1f}/{total_games}  = {s:.3f}")
    print(f"opening-clustered 95% bootstrap CI for score: [{s_lo:.3f}, {s_hi:.3f}]   bootstrap SD of score: {s_sd:.4f}")
    print(f"Elo difference (logistic): {fmt_elo(s)}   CI: [{fmt_elo(s_lo)}, {fmt_elo(s_hi)}]")
    print("NOTE: descriptive internal statistic, not a CCRL/CEGT rating. Do not present as official.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
