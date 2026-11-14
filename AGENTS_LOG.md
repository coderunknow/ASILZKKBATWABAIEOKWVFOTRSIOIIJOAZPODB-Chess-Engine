# AGENTS_LOG.md (append-only)

## 2026-11-14 — Session start (Phase 0)

- Agent: autonomous principal engineer (Arena Agent Mode).
- Actions: repository inspection (git status/log/branch/remote); environment probe; network reachability
  matrix; Rust 1.99.0 installed from npm under `/home/user/.toolchain/sysroot`; python-chess 1.11.2 in
  `/home/user/.venv` as test-only oracle (GPL-3.0+).
- Starting SHA: `98b1a00203183d9c7ccb175f7d6eb8f5ef5eb429`. No files modified at inspection time.
- Created: STATUS.md, AGENTS.md, ARCHITECTURE.md (RFC), docs/ENVIRONMENT.md, docs/adr/0001,
  DESIGN_LOG.md, AGENTS_LOG.md, FAILURE_LEDGER.md placeholder, initial docs skeleton.
- Next: Phase 2 — Rust project scaffold, bitboards, FEN, movegen, make/unmake, perft.

## 2026-11-14 — Phase 3/4/UCI session

- Built: eval.rs (tapered classical), tt.rs (Zobrist 8B TT), search.rs (ID/PVS/aspiration/quiescence/
  null-move/futility/LMR/killers/history/MultiPV/TT-PV), uci.rs (worker-thread search, stop/ponder/
  ponderhit, Hash/Threads/MultiPV options, clock time management soft/hard with movestogo clamp).
- main.rs: added `uci`, `eval [fen]` (breakdown), `bench_eval` subcommands.
- Build: `cargo build --release` clean (one unused-const warning, fixed). `cargo test --release` 14/14 PASS.
- Smoke tests: UCI handshake; mate-in-1 found (`bestmove b1b8`); Kiwipete MultiPV 3 to depth 10;
  abort/stop/ponderhit paths verified with nonblocking stdin reader; ~0.9M nps; 2 vCPU sandbox.
- Fixed two UCI-layer bugs found by smoke testing: (1) bestmove only printed on next stdin command
  (UCI protocol violation) → worker now prints bestmove directly; (2) mate-score formatting could
  overflow (`mate 499`) → clamped; (3) aborted root scores were used to build result → discarded.
- Committed: pending (this checkpoint not yet committed — see STATUS.md "Next preregistered task").

## 2026-11-14 — CI + benchmark harness + LMR panic fix

- Set up `.github/workflows/ci.yml` (Ubuntu+Windows: fmt, clippy -D warnings, release tests,
  release build, UCI handshake, perft d3). CI green on PR #1 (both OSs). Kilo bot: insufficient
  credits (not a code issue).
- Smoke match exposed LMR table out-of-bounds panic → engine silently lost on time.
  Fixed table bounds + worker catch_unwind fallback bestmove. 2-game smoke: engine wins both.
- Wrote match.py/stats.py + 20 verified openings; launched probe-001 (40 games vs SF 19 WASM,
  Skill 0, movetime 100ms) in background.
- Raw evidence committed to benches/ for reproducibility.

## 2026-11-14 — CI + probes session (cont.)

- PR #1 opened (branch pushed). CI: ubuntu-latest + windows-latest both green (fmt/clippy/tests/
  release build/UCI handshake/perft d3). Third-party Kilo bot: insufficient credits — reported as
  not a code issue.
- probes 001/002/003 committed with raw PGN/JSONL evidence.
- UCI fuzz (6 trials × 25 random commands, grammar of 30) — 0 crashes/hangs.
- Engine bracket: between SF-Skill-5 and SF-Skill-10 (pinned SF 19 WASM, 100 ms/move). No absolute
  rating claim; v1.0.0 gates untouched.

## 2026-11-14 — Environment rebuild + strength experiment

- Sandbox workspace was re-materialized (git HEAD reverted to 98b1a00; toolchain/venv/opponents lost).
  Restored branch ref + index from origin (tip 1dc2500) — working tree matched exactly, nothing lost.
  Toolchain reinstalled from npm (same versions); venv + python-chess reinstalled; pinned SF WASM
  re-fetched and hash-verified identical. FAILURE_LEDGER entry recorded.
- Re-ran all gates post-rebuild: fmt/clippy/tests/diftest PASSED; CI still green (PR #1).
- Implemented `cargo run --release -- bench` (fixed depth 10, 12 positions, deterministic signature).
- Search experiment: RFP + check extensions. All gates pass. A/B: +80 Elo (CI [-9,+168], 40 games).
- probe-004 (RFP+CE build) vs SF Skill 5, 40 games @100ms: 14/14/12 score 0.525 (CI [0.412,0.637]).

## 2026-11-14 — Identity migration to Flawless

- `flawless` package/binary/crate; `id name Flawless`; `id author coderunknow (Apache-2.0)`.
- CI workflow smoke tests de-masked (removed `|| true` swallowers); binary path updated.
- Historical raw evidence keeps the old identifiers by policy (see ADR-0002).
- Environment note: sandbox workspace was re-materialized (git HEAD → 98b1a00, toolchain/venv/
  opponents lost); restored branch ref + index from origin (a01fcaf), rebuilt toolchain from npm
  (rustc/cargo 1.99.0), and re-verified lld execute bits for linking; episode recorded in
  FAILURE_LEDGER.md.
- Repository was observed as `coderunknow/Flawless-Chess-Engine` (externally renamed); the old
  URL auto-redirects. This project did not and does not rename the repository.
