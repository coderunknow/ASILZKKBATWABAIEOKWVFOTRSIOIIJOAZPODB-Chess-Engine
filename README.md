# README — ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB Chess Engine

An independent, from-scratch chess engine written in Rust. **Not a Stockfish derivative.**

- **Engine name (UCI):** `ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB`
- **License:** Apache-2.0 (see `LICENSE`)
- **Status:** development (`0.x`). See `STATUS.md` for the live checklist and `CHANGELOG.md` for releases.

## Quick start

```bash
export PATH=/home/user/.toolchain/sysroot/bin:$PATH   # build sandbox only; any Rust ≥ 1.75 works
cargo build --release
./target/release/asilzkkbbatwabaieokwvfotrsioiijoazpodb          # starts UCI mode on stdin/stdout
```

Commands (CLI): `perft <depth> [fen]` · `bench [depth]` · `eval [fen]` · `pgn <file>` · `uci` (default).

## What works (V1 scope)

Standard chess legal move generation · FEN · PGN (basic) · UCI (MultiPV, Hash, Threads=1, ponder) ·
perft · iterative-deepening alpha-beta with aspiration windows, transposition table, quiescence search,
move ordering, null-move pruning, late-move reductions · classical tapered evaluation · benchmark CLI ·
Windows + Linux release builds · CI.

## What does NOT work / is deferred

SMP search (`Threads` is capped at 1 and reports as such) · NNUE (classical eval only; NNUE is a
documented future step) · Chess960 · opening books · syzygy tablebases · any claim of an official
CCRL/CEGT rating (any measurement is a *private, CCRL-anchored estimate*).

## Documentation map

`ARCHITECTURE.md` (RFC) · `docs/adr/` · `TESTING.md` · `BENCHMARKING.md` · `RESEARCH_ROADMAP.md` ·
`DESIGN_LOG.md` · `AGENTS_LOG.md` · `FAILURE_LEDGER.md` · `STATUS.md` · `CHANGELOG.md` · `AGENTS.md`

## Building on Windows

Install VS Build Tools (C++ workload) or MinGW-w64, plus Rust via rustup, then `cargo build --release`.
Windows binaries are produced by CI (see `.github/workflows/ci.yml`).
