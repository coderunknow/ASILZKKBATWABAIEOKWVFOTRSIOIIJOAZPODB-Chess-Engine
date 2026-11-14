# STATUS — ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB Chess Engine

**Project state: `ACTIVE`** (V1 is NOT complete; the 2,000 Elo release gate has not been met and has not been measured)

**Current branch:** `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`
**Starting commit (verified 2026-11-14):** `98b1a00203183d9c7ccb175f7d6eb8f5ef5eb429` (only an Apache-2.0 `LICENSE` present)
**Engine identity (UCI):** `ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB`
**License:** Apache-2.0 (preserved)

## Checklist (binary acceptance criteria — see TASK in prompt)

- [x] Repository recon complete (Phase 0)
- [x] Starting commit / remote state verified and recorded
- [x] Rust toolchain available (1.99.0, installed from npm `@toolchain-bin/*` because static.rust-lang.org is unreachable; see `docs/ENVIRONMENT.md`)
- [x] Architecture RFC published (Phase 1) — see ARCHITECTURE.md (accepted for v1 scope)
- [x] Chess foundation correct: perft gates pass (startpos, Kiwipete, positions 3–5; pos4 d6 = 706045033)
- [x] Differential testing vs python-chess (pinned 1.999, GPL-3.0+, test-only oracle) — DIFTEST PASSED, 76,240 positions, 305 d3 perft comparisons, 0 mismatches
- [x] UCI protocol implemented and smoke-tested (async stop via worker thread + AtomicBool, clocks, MultiPV, ponder/ponderhit) — not yet fuzzed
- [x] Search baseline: iterative deepening + alpha-beta + TT (8-byte) + quiescence + null-move + LMR + aspiration + MultiPV (uncommitted until this phase checkpoint; see below)
- [x] Classical evaluation baseline (tapered PSTs, mobility, bishop pair, king zone, tempo); NNUE interface deferred, NNUE NOT default
- [ ] Benchmark harness (fixed-node + fixed-time) reproducible — partial (`bench_eval` works; full match runner not yet written)
- [ ] CI green on Linux + Windows (fmt, clippy -D warnings, tests, release build) — not started
- [ ] Match infrastructure: paired openings, color reversal, opening-clustered CIs — partial (planned scripts; not implemented)
- [ ] Rating estimate ≥ 2000 with opening-clustered 95% CI lower bound ≥ 2000 over ≥2 batches (**NOT MET / NOT MEASURED**)
- [ ] Correctness, reliability, documentation, release gates (see TESTING.md)
- [ ] v1.0.0 stable release (**NOT AUTHORIZED — gate not passed**)

## Hard constraints / environment notes

- No crates.io access (blocked): the engine is implemented with **zero external dependencies** (pure `std`).
- No static.rust-lang.org access: toolchain installed from npm packages `@toolchain-bin/{rustc,cargo,rust-std,rustfmt,clippy}-1.99.0-x86_64-unknown-linux-gnu` into `/home/user/.toolchain/sysroot`.
- Reference machine (target): Windows 10 LTSC 2021, i5-7300U (4 threads), 8 GB RAM. This dev sandbox: 2 vCPU, ~4 GB RAM, Linux.
- Opponent binaries for anchored rating testing are limited; see BENCHMARKING.md for the honest state of rating evidence.

## Next preregistered task

Phase 3 checkpoint (eval + TT + search + UCI) is built and smoke-tested but UNCOMMITTED as of this writing. Next preregistered task: (1) commit Phase 3 checkpoint (eval+search+tt+uci+main wiring, with UCI bestmove-worker fix); (2) set up GitHub Actions CI (fmt, clippy -D warnings, tests, release build, Windows+Linux) and get it actually green; (3) write match/benchmark harness (paired openings + reversed colors + opening-clustered CI) or honestly record INCONCLUSIVE strength evidence. Do NOT claim playing strength or touch v1.0.0 gates until measured.
