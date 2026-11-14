# Changelog

All notable changes are documented here. SemVer 2.0.0. Versions before the V1 release gate are `0.x`.

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
  `bench signature` (current: `d790483532d87af0`, 2,798,466 nodes); node count is the regression signal.
- Not committed tags; v1.0.0 NOT authorized.

## [0.1.0-dev.1] — 2026-11-14

- Project bootstrap: repository recon, environment record, architecture RFC, ADRs, docs skeleton.
- No engine code yet. Perft gates pending. Not released.
