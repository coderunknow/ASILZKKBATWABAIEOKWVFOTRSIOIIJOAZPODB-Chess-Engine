# TESTING.md — correctness & reliability gates

Status legend: `PASS` (evidence below) / `FAIL` / `PENDING`.

## Move generation — perft (release build)

| Position | FEN | d1..dN | Expected | Status |
|---|---|---|---|---|
| Startpos | `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1` | 1–6 | 20, 400, 8902, 197281, 4865609, 119060324 | ALL PASS 2026-11-14 (d3 = 8902 additionally asserted in CI every push/PR, both OSs) |
| Kiwipete | `r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1` | 1–5 | 48, 2039, 97862, 4085603, 193690690 | ALL PASS 2026-11-14 |
| CPW pos 3 | `8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1` | 1–6 | 14, 191, 2812, 43238, 674624, 11030083 | ALL PASS 2026-11-14 |
| CPW pos 4 | `r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1` | 1–6 | 6, 264, 9467, 422333, 15833292, 706045033 | ALL PASS 2026-11-14 (d6 log `benches/perft_pos4_d6.log`) |
| CPW pos 5 | `rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8` | 1–5 | 44, 1486, 62379, 2103487, 89941194 | ALL PASS 2026-11-14 |

Full raw record: `benches/perft_full_20261114.md` (27/27 exact matches; python-chess
oracle cross-check MATCH at all five positions d3 + startpos d4 via the now-committed
`scripts/perft_oracle.py`).

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
(unknown options ignored), `quit`. Randomized command-sequence fuzz is now a committed, deterministic
test: `tests/uci_smoke.rs` (seeded splitmix64, 6 trials × 25 commands over a ~19-token grammar, plus an
unknown-command tolerance test and a handshake/quit test) — 0 crashes, 0 hangs; runs in CI via `cargo test`.
It replaces the earlier one-off session check that was not reproducible from the repo.
Deep/black-box fuzzing (e.g. cargo-fuzz/libFuzzer): NOT performed (no network access to crates.io; zero-dependency policy).
Panic resilience: search thread wrapped in `catch_unwind`; on internal panic the engine emits a legal fallback
`bestmove` and a stdout `info string search thread panicked; emitting fallback bestmove` marker (GUI never
hangs); match runner tags such games `engine_error` and stats.py excludes them by default.
CI additionally runs a UCI handshake + perft d3 sanity on every push/PR (both OSs).

## Static quality

`cargo fmt --check` · `cargo clippy --all-targets -- -D warnings` · `cargo test` ·
`cargo build --release` (Linux + Windows in CI) · `cargo deny`-style dependency audit (zero deps ⇒ trivial) ·
license scan (zero deps + Apache-2.0 headers).

## CI

`.github/workflows/ci.yml` — ubuntu-latest & windows-latest: fmt, clippy -D warnings, release tests,
release build, UCI handshake, perft d3 sanity — green on PR #1 (runs 43549500632, 43550978076).

## Running the suites (exact commands)

The two Python suites use custom `main()` runners with `check()` counters — they contain NO
`unittest.TestCase` classes, so `python -m unittest` discovers **0 tests** (false green; see
FAILURE_LEDGER 2026-11-14). Run them as scripts (CI does exactly this):

```
python3 scripts/test_match.py            # 104 checks
python3 scripts/test_rating_estimator.py # 53 checks
```

Rust: `cargo test --release` (lib 6 + clock_smoke 3 + correctness 21 + uci_smoke 4).

## Evidence policy

Raw outputs are stored under `benches/` and summarized in `STATUS.md` / `BENCHMARKING.md`. No test
result is claimed without a command + output line.

## Rating harness & estimator regression suites (2026-11-14)

| Suite | Scope | Status |
|---|---|---|
| `scripts/test_match.py` (104 checks) | clock-TC parsing + repeating period (`add`/`reset`) + flag; 60×17×2=2,040 schedule determinism + shard partitioning; engine-error record/immediate-replay/abort-after-2; move-cap unadjudicated (`*`) vs explicit draw policy; manifest v2 finalization (in_progress→completed/aborted); opening-suite hash; anchor-schema hardening (template rejected; TBD/null/bad-hash/ambiguous-convention/unverified-license all rejected) | PASS 2026-11-14 |
| `tests/clock_smoke.rs` (3) + `uci::tests::clock_limits_*` (2) | Flawless clock management: full `go wtime/btime/winc/binc/movestogo` commands return a legal bestmove within budget (crash-net bounds from `clock_limits`); increment + movestogo continuation; `clock_limits` invariants (soft ≤ t, hard ≥ soft, hard ≤ cap, movestogo 0 no-panic) | PASS 2026-11-14 (cargo 35/35) |
| `scripts/test_rating_estimator.py` (53 checks, incl. `verify_evidence`) | balanced-match recovery; perfect/zero boundary rejection; known anchor diffs; correlated opening difficulty (joint bootstrap covariance > 0); uncertainty conversion sd/se/ci90/ci95/ci99; GLS weights + singular fallback; shared calibration added once across batches; combined CI math; missing/invalid evidence rejection; fixed-seed reproducibility; null-control verdicts; full fail-closed gate (PASS on strong evidence; FAIL on poisoned control; FAIL on missing evidence); committed-evidence verification (`verify_evidence.py`: tampered bytes / suite-hash divergence / identity mismatch all fail closed) | PASS 2026-11-14 (53/53) |
| `scripts/aggregate_shards.py` | fail-closed §5.2 rules (missing shards, duplicate shard ids/games, engine/anchor/suite hash mismatches, TC mismatches, incomplete records, hardware divergence) | smoke-verified both directions 2026-11-14 |

Gate note: `scripts/rating_estimator.py gate` independently recomputes every reported number
from raw `games.jsonl` evidence (never trusts a hand-entered rating). It is the implementation
behind the `rating-gate` check (`.github/workflows/rating-gate.yml`) and fails closed on any
missing artifact.

## Evidence pipeline push regression suite (2026-11-15)

| Suite | Scope | Status |
|---|---|---|
| `scripts/test_evidence_push.sh` (10 checks) | evidence-commit push from DETACHED HEAD (actions/checkout ref=sha): explicit refspec `HEAD:refs/heads/$BRANCH` publishes; concurrent remote advancement → rebase-retry publishes; wrong-branch safeguard refuses non-arena destinations; static guard that both `evidence-bridge.yml` and `rating-run.yml` keep the explicit refspec and never reintroduce `git push origin "$BRANCH"` | PASS 2026-11-15 (10/10) |

| `clock_limits_engine1_no_flag_death_march` (src/uci.rs) | ENGINE-1 time-management regression: full 40-move period simulation with per-move overhead stays within the clock and preserves the reserve; hard limits can never flag; starved-period trigger (small clock, large movestogo) cannot overspend | PASS 2026-11-15 (cargo 35/35) |
