# Changelog

All notable changes are documented here. SemVer 2.0.0. Versions before the V1 release gate are `0.x`.

## [Unreleased] — Flawless identity migration + correctness audit (2026-11-14)

- **Identity migration** (ADR-0002): engine, package, library and binary renamed to **Flawless**;
  `id name Flawless`; `id author coderunknow (Apache-2.0)` (authorship unchanged). Repository
  observed as `coderunknow/Flawless-Chess-Engine` (externally renamed; this project did not rename
  it; old URL auto-redirects). Historical benchmark evidence, PGNs and append-only logs keep the old
  identifiers by policy.
- **Audit pass 1 (correctness)** — each defect reproduced by a failing→passing test:
  (1) checkmate now outranks the fifty-move and repetition draw rules in search (FIDE 9.6.2);
  (2) quiescence: terminal (mate/stalemate) check moved before stand-pat cutoffs and delta pruning;
  (3) main search: no-legal-moves terminal check moved before null-move/futility/RFP, and claimable
  draw rules require !in_check — mate can no longer be pruned or mis-scored as a draw;
  (4) `go searchmoves` was silently ignored by the MultiPV=1 PVS path — root restriction now
  enforced at ply 0 for both MultiPV paths; empty `searchmoves` falls back to all legal moves;
  (5) panic-fallback turns are now detectable by the match runner (`engine_error` / `engine_error_turns`
  in JSONL), excluded from stats by default, and the engine emits a GUI-visible stdout marker;
  (6) bench signature `d790483532d87af0` → `3086f65159758c9d` (2,317,474 nodes) — expected consequence.
- **Audit pass 2**: `clock_limits` `u64::clamp` min>max panic at `t<30ms` fixed; UCI bestmove smoke
  (depth 2) and MSRV (Rust 1.80) CI jobs added; remaining `|| true` masks removed from CI.
- **Tests**: 24 integration + 4 unit tests, incl. seeded deterministic UCI fuzz (`tests/uci_smoke.rs`)
  replacing the non-reproducible one-off fuzz claim.
- **Reviews**: CodeRabbit manually triggered (incremental; see PR #1) — review in progress/recorded
  by SHA; Codex documented retry attempted — usage-limited; Copilot quota (lower-effort retry needs
  web UI, API cannot request); Qodo/Kilo billing-blocked (not code findings).
- Absolute Elo remains **UNKNOWN**; the ≥2,000 Elo release gate is NOT measured and NOT met;
  no calibrated pool reachable from this sandbox. v1.0.0 NOT authorized.

## [Unreleased] — Phase 3 (evaluation) + Phase 4 (search) + UCI (2026-11-14)

- Tapered classical evaluation (`src/eval.rs`): material + PST (MG/EG), mobility baselines,
  bishop pair, king-zone pressure (MG only), tempo bonus. `bench_eval` reports ~100–500 ns/eval.
- Zobrist transposition table (`src/tt.rs`): 8-byte entries, power-of-two sizing, generation aging,
  mate-score ply-relative adjustment, TT-move extraction for PV recovery.
- Alpha-beta search (`src/search.rs`): iterative deepening + aspiration windows + PVS + quiescence
  (delta-pruning, MVV-LVA ordering), null-move pruning (non-PV, non-check, non-pawn material),
  futility pruning (depth ≤ 2, non-PV), LMR (log-based table, re-search on fail-high), killer +
  history heuristics, MultiPV full-window root iterations, TT-based PV extraction, seldepth tracking.
- UCI layer (`src/uci.rs`): full V1 command set — `position` (startpos/fen/bare fen + moves),
  `go` (depth/nodes/movetime/infinite/wtime/btime/winc/binc/movestogo/searchmoves/ponder), `stop`,
  `ponderhit`, `setoption` (Hash, MultiPV honest, Threads capped at 1), `ucinewgame`, `debug`.
  Search runs on a worker thread; `bestmove` is printed by the worker as soon as search ends
  (fixed: previously `bestmove` was only emitted on the next stdin command / EOF).
- `stop_and_join`: aborts search via shared AtomicBool, joins worker, hands the TT back to the
  main thread exactly once per `go`.
- Abort safety: root move scores collected after an abort are discarded (they are garbage), preventing
  corrupt PV/TT handoff after `stop` / `quit` / time abort.
- `format_score`: mate scores only reported when genuinely mate-bounded (|score| ≥ MATE_SCORE−100),
  clamped rather than overflowing.
- Score 13/12 cp found at depth 6 from startpos (b1c3); ~900k nps in-sandbox (2 vCPU).
- No claim of playing strength yet; perft/diftest gates unchanged (14/14 tests pass).
- UCI worker now catches search-thread panics and always emits a bestmove (GUI never hangs);
  LMR table sized to worst case ([MAX_PLY+1][256]) — fixes move-30 search-thread panic on
  high-material/mate positions.
- Match harness: `scripts/match.py` (UCI game runner: paired openings, color reversal,
  adjudication, PGN+JSONL evidence) + `scripts/stats.py` (logistic Elo diff, opening-clustered
  95% bootstrap CI) + `benches/openings-20.txt` (20 openings, both colors).
- GitHub Actions CI (`.github/workflows/ci.yml`): Ubuntu + Windows, fmt, clippy -D warnings,
  release tests, release build, UCI handshake, perft d3 sanity — green on PR #1.
- Strength probes vs pinned Stockfish 19 WASM (Skill 0/5/10, movetime 100 ms, 20 paired openings ×2 colors):
  40/40 checkmate wins vs Skill 0; 11/13/16 vs Skill 5 (Elo diff −44, CI [−127,+35]); 1/7/32 vs Skill 10
  (Elo diff −359, CI [−512,−269]). Internal in-sandbox bracket; not a CCRL/CEGT rating.
- UCI fuzz: 6 trials × 25 commands — 0 crashes, 0 hangs.
- Search experiment (kept, directional): reverse futility pruning (depth ≤ 3, non-PV,
  mate-bound-safe) + check extensions. A/B vs previous build: score 0.613 (Elo +80, CI overlapping 0);
  vs pinned SF Skill 5 score improved 0.438 → 0.525 (CI overlapping). Not conclusive at 40 games.
- `bench`: fixed-depth-10 search benchmark over 12 fixed positions; deterministic FNV-1a
  `bench signature` (current: `3086f65159758c9d`, 2,317,474 nodes; see DESIGN_LOG 2026-11-14 audit entry); node count is the regression signal.
- Not committed tags; v1.0.0 NOT authorized.

## [0.1.0-dev.1] — 2026-11-14

- Project bootstrap: repository recon, environment record, architecture RFC, ADRs, docs skeleton.
- No engine code yet. Perft gates pending. Not released.
