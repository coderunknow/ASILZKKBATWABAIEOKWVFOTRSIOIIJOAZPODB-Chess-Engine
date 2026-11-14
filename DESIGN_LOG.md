# DESIGN_LOG.md (append-only)

## 2026-11-14 — Phase 0/1 kickoff

- Verified repository state: starting commit `98b1a00` ("Initial commit"), tree contains only `LICENSE`
  (Apache-2.0). Branch `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`. No tags, no workflows, no other branches.
- Environment: crates.io + static.rust-lang.org unreachable → zero-dependency Rust, toolchain from npm
  `@toolchain-bin/*` (see `docs/ENVIRONMENT.md`).
- Decisions: bitboards + startup-generated magic sliders (ADR-0001); pseudo-legal movegen with
  make/unmake legality filter; single-threaded V1 with future-SMP-safe encapsulation; NNUE deferred
  behind classical baseline; honest `Threads max 1`.
- Risks recorded: (1) rating gate unlikely to be measurable in this sandbox; will report INCONCLUSIVE
  rather than claim pass. (2) Toolchain provenance: npm redistribution of official binaries, checksums
  recorded in ENVIRONMENT.md.

## 2026-11-14 — Phase 3/4/UCI checkpoint (search + evaluation + UCI)

- Decisions: classical tapered eval first (MG/EG PSTs, mobility baselines, bishop pair, king-zone,
  tempo=12 cp); NNUE deliberately NOT built yet (no measured win, no teacher pipeline).
- TT: Zobrist 8-byte entries, power-of-two, generation aging, ply-relative mate scores, TT-move
  extraction for PV recovery (no separate PV array).
- Search: ID + aspiration (depth ≥ 6, ±25 initial, widen ×3+20) + PVS + quiescence (delta 200,
  MVV-LVA) + null-move (depth ≥ 3, non-PV, beta < MATE_BOUND, non-pawn material) + futility
  (depth ≤ 2) + LMR (r = ln d · ln n · 0.6, re-search on fail-high) + killers/history.
  Repetition (2-fold path), 50-move, insufficient material are draws inside search; no-legal-moves
  handled for mate/stalemate.
- UCI: single worker thread; `go` returns immediately; `stop` sets AtomicBool and joins; bestmove
  printed by the worker so it appears even without further stdin commands (fixed — previously
  bestmove was only printed on the next stdin line / EOF, violating the UCI protocol).
- Abort safety: root scores after an abort are discarded; mate scores reported only for genuinely
  mate-bounded |score| ≥ MATE_SCORE−100 (clamped otherwise).
- UCI smoke: depth-limited search on Kiwipete (FEN r3k2r/...) reaches depth 8–10 with MultiPV 3;
  mate-in-1 FEN (6k1/8/6K1/8/8/8/8/1Q6 w - - 0 1) → `bestmove b1b8` at any depth; ~0.9M nps
  single-threaded in sandbox.
- Known gaps (honest): no strength measurement yet; no match/CI; `Threads` hard-capped at 1;
  UCI not fuzzed; see STATUS.md / FAILURE_LEDGER.md (no rating claims).

## 2026-11-14 — First strength probes + CI + match infrastructure

- GitHub Actions CI (Windows+Linux: fmt, clippy -D warnings, release tests, release build, UCI
  handshake, perft d3) — green on PR #1. Kilo review bot fails (insufficient account credits);
  not a code verdict.
- Match infrastructure implemented (`scripts/match.py`, `scripts/stats.py`); 20 verified openings;
  paired games with color reversal; opening-clustered bootstrap 95% CIs.
- Two engine bugs found by benchmarking and fixed: (1) LMR table out-of-bounds panic at depth 64 /
  move-count 64+ (thread died, GUI starved → timeout loss); (2) no fallback bestmove on thread
  panic (worker now wraps search in catch_unwind and emits legal fallback; main thread rebuilds TT).
- Probes vs pinned Stockfish 19 WASM (movetime 100 ms): SF Skill 0 → 40/40 wins (checkmates);
  SF Skill 5 → 11/13/16 (≈ −44 Elo diff); SF Skill 10 → 1/7/32 (≈ −359). Engine is between
  pinned Skill 5 and Skill 10; far from any 2000-Elo gate; results are in-sandbox internal
  estimates only, never to be presented as official ratings.
- NNUE still NOT built; classical eval unchanged pending measured need.

## 2026-11-14 — Search strength experiment: reverse futility pruning + check extensions

- Change (src/search.rs): (1) reverse futility pruning at depth ≤ 3, non-PV, not in check,
  mate-bound-safe (s − 150·depth ≥ beta → fail high); (2) check extension — when in check, child
  searches are made at depth−1+1 instead of depth−1.
- Correctness re-verified: fmt/clippy −D warnings/tests 18/18/diftest PASSED.
- bench signature changed a7a9f01893e9f1a5 → d790483532d87af0 (2,798,466 nodes @ depth 10) — expected.
- A/B (benches/ab-004-rfp-checkext, 40 paired games vs the previous build at movetime 50 ms):
  ours-rfp-cext 18 W / 13 D / 9 L vs ours-before → score 0.613, opening-clustered 95% bootstrap CI
  [0.487, 0.725], logistic Elo diff +80 (CI [−9, +168]). Positive direction; NOT conclusive at this
  sample size/TC; lesson: treat as directional only, keep change since standard and safe, verify
  no correctness regressions (all gates pass).
