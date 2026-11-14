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
- [ ] Architecture RFC published (Phase 1) — in progress
- [ ] Chess foundation correct: perft gates pass (startpos, Kiwipete, positions 3–5)
- [ ] Differential testing vs python-chess (pinned 1.11.2, GPL-3.0+, test-only oracle)
- [ ] UCI protocol implemented and tested (async stop, clocks, MultiPV, ponder)
- [ ] Search baseline: iterative deepening + alpha-beta + TT + quiescence
- [ ] Classical evaluation baseline; NNUE interface designed, NNUE NOT default
- [ ] Benchmark harness (fixed-node + fixed-time) reproducible
- [ ] CI green on Linux + Windows (fmt, clippy -D warnings, tests, release build)
- [ ] Match infrastructure: paired openings, color reversal, opening-clustered CIs
- [ ] Rating estimate ≥ 2000 with opening-clustered 95% CI lower bound ≥ 2000 over ≥2 batches (**NOT MET / NOT MEASURED**)
- [ ] Correctness, reliability, documentation, release gates (see TESTING.md)
- [ ] v1.0.0 stable release (**NOT AUTHORIZED — gate not passed**)

## Hard constraints / environment notes

- No crates.io access (blocked): the engine is implemented with **zero external dependencies** (pure `std`).
- No static.rust-lang.org access: toolchain installed from npm packages `@toolchain-bin/{rustc,cargo,rust-std,rustfmt,clippy}-1.99.0-x86_64-unknown-linux-gnu` into `/home/user/.toolchain/sysroot`.
- Reference machine (target): Windows 10 LTSC 2021, i5-7300U (4 threads), 8 GB RAM. This dev sandbox: 2 vCPU, ~4 GB RAM, Linux.
- Opponent binaries for anchored rating testing are limited; see BENCHMARKING.md for the honest state of rating evidence.

## Next preregistered task

Complete Phase 1 architecture RFC (ARCHITECTURE.md), then Phase 2 foundation: Cargo project, bitboards, movegen, FEN, make/unmake, perft — and get perft gates passing.
