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
