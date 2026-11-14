# TESTING.md — correctness & reliability gates

Status legend: `PASS` (evidence below) / `FAIL` / `PENDING`.

## Move generation — perft (release build)

| Position | FEN | d1..dN | Expected | Status |
|---|---|---|---|---|
| Startpos | `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1` | 1–6 | 20, 400, 8902, 197281, 4865609, 119060324 | PENDING |
| Kiwipete | `r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1` | 1–5 | 48, 2039, 97862, 4085603, 193690690 | PENDING |
| CPW pos 3 | `8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1` | 1–6 | 14, 191, 2812, 43238, 674624, 11030083 | PENDING |
| CPW pos 4 | `r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1` | 1–6 | 6, 264, 9467, 422333, 15833292, 706045033 | PENDING |
| CPW pos 5 | `rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8` | 1–5 | 44, 1486, 62379, 2103487, 89941194 | PENDING |

Reference counts: Chess Programming Wiki "Perft Results" page (public community reference values);
independently cross-verified with python-chess (`scripts/perft_oracle.py`).

## Differential testing vs python-chess (pinned 1.11.2, GPL-3.0+, test-only)

- Random legal-move sequence sampling with deterministic seeds: compare legal move sets, SAN/FEN round
  trips, castling/en-passant/promotion handling, terminal states, 50-move and repetition logic.
- See `scripts/diftest.py`. Target: ≥ 2000 positions per run, zero mismatches.
- Property tests (Rust): make/unmake round trip; incremental vs recomputed hash; Zobrist key consistency;
  mirror evaluation test.

## State & invariant tests

Castling rights through capture/castle/promotion · en passant pin legality · promotions · repetition
detection (positions array) · fifty-move rule · insufficient material (K v K, K+B v K, K+N v K,
K+B v K+B same color bishops) · stalemate · checkmate · search state restoration after `stop`.

## UCI / reliability

Covered today (all verified locally on Rust 1.99.0): `uci` handshake (`id`/`uciok`), `isready`,
`position startpos`/`fen`/`moves`, `go depth`/`movetime`/`infinite`/`wtime,btime,winc,binc,movestogo`,
`stop` mid-search, `ponderhit` (ponder→clock conversion), `ucinewgame`, `setoption Hash/Threads/MultiPV`
(unknown options ignored), `quit`. Randomized command-sequence fuzz: 6 trials × 25 commands from a
30-command grammar — 0 crashes, 0 hangs (2026-11-14). Panic resilience: search thread wrapped in
`catch_unwind`; on internal panic the engine emits a legal fallback `bestmove` (GUI never hangs).
CI additionally runs a UCI handshake + perft d3 sanity on every push/PR (both OSs).

## Static quality

`cargo fmt --check` · `cargo clippy --all-targets -- -D warnings` · `cargo test` ·
`cargo build --release` (Linux + Windows in CI) · `cargo deny`-style dependency audit (zero deps ⇒ trivial) ·
license scan (zero deps + Apache-2.0 headers).

## CI

`.github/workflows/ci.yml` — ubuntu-latest & windows-latest: fmt, clippy -D warnings, release tests,
release build, UCI handshake, perft d3 sanity — green on PR #1 (runs 43549500632, 43550978076).

## Evidence policy

Raw outputs are stored under `benches/` and summarized in `STATUS.md` / `BENCHMARKING.md`. No test
result is claimed without a command + output line.
