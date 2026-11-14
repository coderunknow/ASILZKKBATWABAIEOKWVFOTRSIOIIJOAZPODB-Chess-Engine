# BENCHMARKING.md — measurement policy & infrastructure

## Measurement categories (never conflate)

1. Fixed-node search efficiency (nodes to reach depth at fixed search).
2. Fixed-time playing strength (games, Elo vs pool).
3. NPS / microbenchmarks (mach reproduces only the implementation, not strength).
4. Tactical suite results (e.g., WAC-style puzzles once wired).
5. Rating estimates vs a pinned opponent pool.

## Pinned environment template (record per experiment)

- Commit SHA, binary SHA-256, build flags (`-C target-cpu`? none — portable default), profile.
- UCI options: Hash, Threads, MultiPV.
- Opponent(s): name, version, binary SHA-256, options.
- Time control; opening suite + seed; color-reversal plan; adjudication rules.
- Hardware + OS; date; operator (agent session id).

## Rating policy (see ARCHITECTURE §9)

- Primary reference scale: CCRL 40/15 (i7-4770k equivalence; Stockfish 10 calibration reference;
  ponder disabled; same hash policy; generic opening books). As close as resources permit locally.
- Secondary: CEGT 40/20. **No cross-scale subtraction.**
- All local results are labeled *private estimate, CCRL-anchored*; never official ratings.
- Paired openings, reversed colors, opening-clustered bootstrap CIs, ≥2 confirmation batches,
  staged sample sizes (200–500 / 1,000–2,000 / 4,000–6,600).
- Null controls included (e.g., baseline vs itself must score ≈ 50%).

## Infrastructure in this repo

- `cargo run --release -- bench` — fixed-node (or fixed-depth) benchmark; prints nodes/s and a checksum
  of the main search line; used for regression tracking.
- `cargo run --release -- perft <depth> [fen]`.
- `scripts/match.py` — game runner (UCI subprocess), writes PGN + JSONL records, supports opening books
  (FEN list), color reversal, adjudication (resign/50-move/insufficient), and paired mode.
- `scripts/stats.py` — Elo estimate + opening-clustered bootstrap 95% CI from PGN/JSONL.
- `scripts/diftest.py` — differential correctness vs python-chess.

## Current status (2026-11-14)

No rated games exist yet. Opponent availability is limited by the sandbox network (only github.com /
codeload.github.com / api.github.com / pypi.org / files.pythonhosted.org / registry.npmjs.org).
Candidate anchored opponents: Stockfish WASM from npm (`stockfish@…`, to be pinned and hash-verified
before any match) — its exact CCRL equivalence is NOT claimed; only internal A/B strength measurements.
Any Elo number produced here is an in-sandbox estimate with stated uncertainty, not an official rating.

## Raw evidence retention

`benches/<experiment-id>/` contains: PGN, JSONL, match config, engine logs, stats output, binary hashes.
Never overwrite; new batches go in new directories.
