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
  `bench signature` (current: `b58979ca90492208`, 3,666,233 nodes; see DESIGN_LOG 2026-11-18 audit entry); node count is the regression signal.
- Not committed tags; v1.0.0 NOT authorized.

## [0.1.0-dev.1] — 2026-11-14

- Project bootstrap: repository recon, environment record, architecture RFC, ADRs, docs skeleton.
- No engine code yet. Perft gates pending. Not released.

## [Unreleased] — 2026-11-18 (screening work on PR #2; no release authorized)

- **Fixed:** the outpost evaluation term used the wrong pawn-attack table in
  both of its lookups. The pawn-attack table is directional — the squares from
  which a pawn of colour C attacks square X are `PAWN_ATTACKS_[other(C)][X]` —
  and both lookups read that other table, so the term asked "is this square
  attacked by a pawn of the same colour as the piece?" twice. It was rewarding
  undefended pieces and counting attacked ones. The defect is symmetric under
  the board flip, so the antisymmetry gate was satisfied by a wrong evaluator.
  Commit `c702066`; new gate `outpost_requires_defence_and_safety_in_the_right_direction`
  in `tests/eval_quality.rs`, verified to fail on the pre-fix source.
- **Withdrawn:** the EVAL-1 ablation campaign. Every EVAL-1 binary was built
  from the defective source, so the whole campaign measured a program that is
  not in the tree. The raw records are retained unmodified under
  `/home/user/matches/eval-*-invalidated-outpostbug/` and are not citable.
  Re-registered and re-dispatched as **EVAL-2** with seven fresh binaries
  (`PREREGISTRATION.md`).
- **Performance:** the evaluation cost dropped about 18 % (1219 ns → 996 ns per
  evaluation, min of 15 runs over the four `bench_eval` positions) with **no
  change to any evaluation value** — the bench signature and node count are
  unchanged at `b58979ca90492208` / 3,666,233. Commit `815ca47`: the slider
  attack masks are computed once per side and shared between the mobility and
  king-safety terms (they were computed twice per evaluation); the
  pawn-structure section uses square-indexed lookup tables; and `evaluate` no
  longer routes through the ten-component `breakdown` taper.
- **CI:** the `anchor-verify` workflow pinned the pre-fix bench signature, which
  is why run 44327388368 failed. It now pins `b58979ca90492208`; anchor
  verification passes 13/13 (run 44333865340).

- **EVAL-2 result:** the seven-pair evaluation ablation campaign completed
  (560 games, zero engine errors, every pair passing the schedule audit).
  **EVAL-ALL vs EVAL-NONE: INCONCLUSIVE** — score 0.519, CI [0.419, 0.619],
  Elo +13, CI [−57, +84]. The registered rule keeps the change only if the CI
  lower bound is > 0 and rejects it only if the upper bound is <= 0, so the
  evaluation upgrade is **not merged as a strength improvement**; the six
  feature flags stay in the tree as measurement scaffolding. No individual
  feature is claimed: none is flagged HARMFUL, and turning the mobility taper
  off is 70 Elo worse than keeping it on — the only comparison outside the
  40-Elo indeterminate band. This is screening evidence at a fixed 100 ms/move
  clock, not a rating.

## [Unreleased] — 2026-11-19 (search audit on PR #2; no release authorized)

Three search defects were found by auditing `src/search.rs` against the PVS
algorithm and the documented move-ordering bands, and by measuring the root
score against the exact value of the best single move. Each fix ships with a
regression test that was verified to fail against the pre-fix source.

- **Fixed:** the PVS scout result was used as a move score. The scout searches
  with the null window `(-alpha-1, -alpha)`, so its result is a bound, and the
  re-search that turns the bound into a value was guarded by `reduction > 0`.
  An unreduced non-first move therefore kept its bound as its score, which
  lowered the node's best score, the alpha update and the score the root
  reports, and could make the root pick a move worse than one it had already
  evaluated. At depth 2, where late move reductions are off, the old code
  reported a root score below the best move's value in 7 of the first 8 Batch A
  positions, with gaps up to 172 centipawns; the fixed code is exact in every
  position, as the pre-PR-2 baseline is. The same defect made the engine claim
  `score mate 15` for a position that is not a forced mate. Commit `708d53c`.
- **Fixed:** the move-ordering bands overlapped. A quiet move can score as low
  as 25_424 and a losing capture as high as 42_047, so a losing capture could
  be ordered above a quiet move — the opposite of the documented intent — and
  the promotion bonus pushed losing capture-promotions into the middle of the
  quiet band. The bands are now laid out so that they cannot overlap whatever
  the history tables hold, and the layout is documented next to the constants.
  Commit `61dd642`.
- **Fixed:** the quiescence never recorded the captures it played on the
  search path, so from the second quiescence level on the counter-move and
  continuation-history lookups were made for a move from an unrelated branch.
  The effect is confined to the ordering inside the quiescence — the returned
  value is the maximum over the captures searched and stays a valid bound.
  Commit `018e920`.
- `bench` signature `b58979ca90492208` → `c64d148d39181140`, nodes 3,666,233 →
  3,413,723. The `anchor-verify` workflow pins the signature and was updated
  to the new value.

## [Unreleased] — 2026-11-19 (mate-distance fix + EVAL-3 screening result; no release authorized)

- **Fixed:** the mate-score band was `MATE_SCORE - 100`, narrower than the search's
  own ply limit `MAX_PLY` (128). A mate 100 plies or more from the root fell outside
  the band, and two things went wrong at once:
  (1) the transposition table did not recognise it as a mate score, so it stored it in
  root-relative form and returned it unchanged when the entry was probed at a
  different ply — the mate distance was silently wrong by exactly the ply difference
  (a mate 101 plies away, re-used at ply 50, was reported as 101 plies away instead of
  151); and
  (2) the UCI layer printed it as a centipawn score (`cp 29899`) instead of a mate.
  The band is now `MATE_SCORE - MAX_PLY`, derived from the search's ply limit rather
  than an arbitrary constant, and lives in one place (`eval::MATE_BOUND`) that the
  search, the transposition table and the UCI layer all use. The deepest checkmate
  node the search can reach is at `MAX_PLY - 1`, so the new band covers every
  reachable mate score. Commit `32ad8ab`.
  This is **behaviour-neutral for ordinary positions**: the depth-10 bench signature
  and node count are unchanged at `c64d148d39181140` / 3,413,723. The only reachable
  change is in the deep-mate case, where the null-move guard now correctly refuses to
  run with a mate beta.
- **Tests:** `tests/mate_distance.rs` adds 8 regressions (four of which fail against
  the pre-fix source): exhaustive mate-distance normalisation over the whole reachable
  range, the concrete cross-ply transposition case, the UCI score format at the band
  edge, the width of the band itself, plus end-to-end checks that the real engine
  reports `mate 1` / `mate 2` through the protocol and that the mate distance is
  stable when the table is reused. Rust test count 67 → 75.
- **EVAL-3 (registered before dispatch, screened after):** the audited tree beat the
  pre-audit tree **60.5/80 = 0.756**, 95% CI [0.662, 0.838], Elo difference **+197**,
  95% CI **[+117, +285]** — 80 games, 20 opening clusters, exact AB/BA colour
  reversal, zero engine errors, audit verdict PASS. The registered decision rule
  (95% CI lower bound > 0 Elo) is met. This is screening evidence on a shared
  2-vCPU sandbox at a fixed 100 ms/move time control; it is not a rating and does
  not substitute for the >2,000 Elo gate. Raw evidence:
  `benches/evidence/screening-eval3/`.
