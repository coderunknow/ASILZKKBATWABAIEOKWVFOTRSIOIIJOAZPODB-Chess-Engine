# README — Flawless Chess Engine

An independent, from-scratch chess engine written in Rust. **Not a Stockfish derivative.**

- **Engine name (UCI):** `Flawless`
- **License:** Apache-2.0 (see `LICENSE`)
- **Status:** development (`0.x`). V1 gates NOT met — and **no calibrated absolute rating exists in
  either direction** (it has not been measured; see `STATUS.md`). In-sandbox relative probes vs pinned
  Stockfish 19 WASM (e.g. ~0.44–0.53 score vs Skill 5) are internal trend signals only, never an Elo
  rating. No official CCRL/CEGT rating exists. See `STATUS.md` for the live checklist and
  `CHANGELOG.md` for releases.

## Quick start

```bash
cargo build --release   # Rust ≥ 1.80 (MSRV); rust-toolchain.toml pins 1.99.0
cargo +1.80 build --release   # force the MSRV toolchain instead of the pinned one
./target/release/flawless                  # no arguments: UCI mode on stdin/stdout (for GUIs)
./target/release/flawless uci              # same as above, explicit
./target/release/flawless perft 6          # perft from startpos
./target/release/flawless bench            # fixed-depth-10 search benchmark + signature
./target/release/flawless --help           # list the commands
```

Launching the executable **without arguments starts UCI mode** — the form conventional UCI GUIs use
when they start a custom engine. Explicit subcommands remain available and unchanged.

Commands (CLI): `perft <depth> [fen]` · `divide <depth> [fen]` · `bench` · `bench_eval` · `eval [fen]` · `moves` · `hash` · `uci` · `--version` · `--help` / `-h`.

## What works (V1 scope)

Standard chess legal move generation · FEN · PGN export from match tooling (no PGN reader exists) ·
UCI (MultiPV, Hash, Threads=1, ponder) ·
perft · iterative-deepening alpha-beta with aspiration windows, transposition table, quiescence search,
move ordering, null-move pruning, late-move reductions · classical tapered evaluation · benchmark CLI ·
Windows + Linux release builds · CI.

## What does NOT work / is deferred

SMP search (`Threads` is capped at 1 and reports as such) · NNUE (classical eval only; NNUE is a
documented future step) · Chess960 · opening books · syzygy tablebases · any claim of an official
CCRL/CEGT rating (none exists — all probes so far are in-sandbox internal estimates with pinned
opponents; do not present them as official ratings).

## Documentation map

`ARCHITECTURE.md` (RFC) · `docs/adr/` · `TESTING.md` · `BENCHMARKING.md` · `RESEARCH_ROADMAP.md` ·
`DESIGN_LOG.md` · `AGENTS_LOG.md` · `FAILURE_LEDGER.md` · `STATUS.md` · `CHANGELOG.md` · `AGENTS.md`

## Building on Windows

Install VS Build Tools (C++ workload) or MinGW-w64, plus Rust via rustup, then `cargo build --release`.
Windows builds are exercised by CI (fmt, clippy, tests, release build, UCI handshake, perft sanity).
CI also builds a Windows x64 executable (`x86_64-pc-windows-msvc`) and uploads it as a workflow
artifact named `flawless-windows-x64-<commit-sha>` containing `flawless.exe`, `SHA256SUMS.txt` and
`BUILD-MANIFEST.txt`. These are CI build artifacts, not a GitHub Release; the repository does not
publish binaries (see `.github/workflows/ci.yml`).
