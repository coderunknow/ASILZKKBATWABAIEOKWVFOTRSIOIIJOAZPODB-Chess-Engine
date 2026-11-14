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

- `cargo run --release -- bench_eval` — fixed-node eval micro-benchmark (1000 evals/FEN, ~100–500 ns/eval in sandbox).
- `cargo run --release -- perft <depth> [fen]`.
- `cargo run --release -- uci [uci|perft ...]` — full UCI engine; `go movetime/depth/clocks`, `ucinewgame`, MultiPV, ponder.
- `scripts/match.py` — game runner (UCI subprocess), writes PGN + JSONL records, supports opening files
  (`name|moves` UCI lines), color reversal (paired mode), adjudication via python-chess outcomes,
  timeout/illegal-move forfeits, and wall-clock accounting. Verified end-to-end.
- `scripts/stats.py` — score, Elo difference (logistic model), opening-clustered 95% bootstrap CI
  (bootstrap over opening clusters, not games).
- `scripts/diftest.py` — differential correctness vs python-chess.

## Pinned benchmark opponents

- **Stockfish 19 WASM (lite-single, single-threaded)**, npm package `stockfish@19.0.1`
  (`buildVersion 19`, GPL-3.0), files at `node_modules/stockfish/bin/stockfish-19-lite-single.*`.
  SHA-256 (recorded 2026-11-14): `stockfish-19-lite-single.js` ccb130d7ff29408531c47d859a49f91d59d4f482d05a53eb1a3231a4f624c91a,
  `stockfish-19-lite-single.wasm` ee4f115bdb2d32cadf96cada104a05b5ec257d7ad6f57582190b49bc71f096de.
  (Full-strength `stockfish-19.js` also present: 623ee70a10d6dc202375127b49e2e1822635f9ab07693ae7be28e50a787f6218; `stockfish-19.wasm`: a599d78d72e0722d8895be84aca8b492d12e8bba3cdfcbcbc4a64017888c6667).
  Run via `node`. Used ONLY as a pinned benchmark opponent, never as a code source.
  Invoked with `setoption name Skill Level value <0..20>` to build a strength ladder; CCRL-equivalence
  of any skill level is NOT claimed.
- Location on disk: `/home/user/opponents/` (outside the repository; not committed).

## Current status (2026-11-14)

No rated games exist yet. Opponent availability is limited by the sandbox network (only github.com /
codeload.github.com / api.github.com / pypi.org / files.pythonhosted.org / registry.npmjs.org).
Candidate anchored opponents: Stockfish WASM from npm (`stockfish@…`, to be pinned and hash-verified
before any match) — its exact CCRL equivalence is NOT claimed; only internal A/B strength measurements.
Any Elo number produced here is an in-sandbox estimate with stated uncertainty, not an official rating.

## Raw evidence retention

`benches/<experiment-id>/` contains: PGN, JSONL, match config, engine logs, stats output, binary hashes.
Never overwrite; new batches go in new directories.
