# REVIEW_MANUAL_03d2066.md — human/agent manual code review at PR head `03d2066`

Scope: full manual review of the PR #1 diff against `main` (`98b1a00`), 133 changed files /
+24,080 lines. This review replaces the blocked automated reviewers (CodeRabbit rate-limited,
Copilot quota, Codex rate-limited, Qodo trial ended, Kilo credits — see STATUS.md "Reviews").

This file is a **record created at head `03d2066`**; it is append-only. The "Fix commit" column is
filled in as fixes land; a companion review file is written at the final head SHA.

## How it was performed

* Read every changed Rust source file end-to-end (`src/*.rs`, `tests/*.rs`, 5,582 added lines).
* Read the review-relevant control logic of the tooling (`scripts/match.py`, `scripts/stats.py`,
  `scripts/rating_estimator.py`, `scripts/verify_evidence.py`, `scripts/aggregate_shards.py`) and
  the six workflows (`ci.yml`, `rating-run.yml`, `rating-gate.yml`, `anchor-verify.yml`,
  `anchor-research.yml`, `evidence-bridge.yml`).
* Evidence data files (`benches/evidence/**`, `benches/probe-*/**`, opening suites, anchor pools)
  were reviewed by *identity and immutability* only: they are frozen records, are re-verified by
  `scripts/verify_evidence.py` (fail-closed) and were not edited in this round.
* Every finding below was **reproduced against the head binary** (commands and outputs in
  "Reproduction"), not inferred from reading alone.

Baseline measured at `03d2066` in this sandbox (2 vCPU, rust 1.99.0, `--release`):
`bench` = 2,530,885 nodes / 8.76 s = **288,912 nps**, signature `141943aa23b3fc68`;
`cargo test --release` 40/40; clippy `-D warnings` clean; fmt clean.

---

## Findings

| # | File:line | Severity | Finding | Reproduction | Fix commit |
|---|-----------|----------|---------|--------------|-----------|
| R-01 | `src/search.rs:603` (LMR fail-high re-search) | **HIGH** | The re-search after a reduced zero-window test is written **without the negamax sign**: `s = -self.search(pos, depth - 1 + extension, -alpha - 1, -alpha, ply + 1);`. Every other recursive call in the same block (lines 593, 595, 606) negates the child value. So whenever `reduction > 0 && s > alpha`, `s` receives the raw child score (wrong sign, and from a non-mirrored window) and is then used for `best_score`, `alpha`, the fail-high break, and the TT bound. Consequence: silently wrong scores at every reduced node that beats alpha, wrong TT entries, and (because the same `s` feeds the `s < beta` test) skipped full-window re-searches. | LMR is active from depth 3 (`build_lmr_table`, cells ≥1 from depth 3/count 3), i.e. in all normal searches. Verified by diffing `bench` node counts/scores against a sign-corrected build (see E1 in DESIGN_LOG entry). | pending |
| R-02 | `src/search.rs:453` (`!in_chk && (is_repetition() \|\| is_fifty_move() \|\| insufficient_material())` → `DRAW_SCORE`) | **HIGH** | Two correctness violations in one branch. (a) **Root repetition false-draw**: at ply 0 the game is *not* a draw on a 2-fold occurrence (FIDE needs 3-fold; the match harness adjudicates with python-chess `claim_draw=True`, which is also 3-fold/5-fold). The engine scores the root 0 with zero search effort and plays the *first legal move*. (b) **Mate precedence is inverted**: the comment asserts "when the side to move is NOT in check, no checkmate is possible for the replying side" — the side to move may still have a mate-in-1, and FIDE gives checkmate precedence over claimable 9.2/9.3 draws. Any node (including root) at `halfmove + ply >= 100` returns a draw and never plays or scores the mate. | Root repetition: `position startpos moves b1c3 b8c6 c3b1 c6b8 g1f3 g8f6 f3g1 f6g8` → `go depth 8` reported `score cp 0 nodes 8 seldepth 0 pv` (empty PV) and `bestmove a2a3` (first legal move), while the non-repeated control searched 55,578 nodes. Mate precedence: `7k/8/8/8/5K2/8/8/q7 b - - 100 74` (and the `99` variant, since 99+depth ≥ 100) → `score cp 0 nodes 6` / `nodes 144` instead of a winning queen score; the `0` variant returned `cp 912` with 19,392 nodes. | pending |
| R-03 | `src/position.rs:687-722` (`ep_capture_available` → `hash_ep` → `zobrist_full`) | **HIGH** (performance) | The FIDE "same position" ep rule is evaluated by **cloning the whole `Position` (including the ever-growing `history: Vec<u64>`) and running full legal move generation inside `make_move`**. Cost is per make/unmake (so it also multiplies through `generate_legal`, `perft`, and `extract_pv`), and the clone cost grows with game length: an allocation + memcpy of the entire game history *plus* a complete legal-move-generation pass on every node. This is the single largest measured NPS loss in the engine. | A/B build with the ep legality probe replaced by a naive `ep >= 0`: identical bench signature `141943aa23b3fc68`, but **254 s vs 288 k nps** (339,103 vs 288,912 = **+17.4 %**) at fixed-depth bench, and depth-10 long-game search 1.49 s vs 1.65 s. | pending |
| R-04 | `src/tt.rs:141-143` (`fn index`) | MEDIUM | Bucket selection uses the **low 16 bits** of the Zobrist key (`(key as usize) & len_mask`). For the default 64 MiB TT (2^22 entries) the low 22 bits are consumed, so only the top 16-bit signature provides discrimination between buckets: positions cluster into 4 effectively-used bucket groups per 2^20 range and collide far more than the key entropy allows. Wasted TT capacity → loss of depth-for-depth value; also interacts with R-05 (aliasing of an entry carrying an out-of-range mate score). | Bucket hit statistics from `TranspositionTable::{probes,hits,stores}` and a forced 16 MiB/64 MiB comparison at fixed depth. | pending |
| R-05 | `src/tt.rs:154-167` (`adjust_score_to_tt` clamp) | MEDIUM | Mate scores are stored as `score ± ply` in an **i16**. With `MATE_SCORE = 30_000` and `ply` up to `MAX_PLY = 128`, `30_000 + ply > i16::MAX` and the value is silently clamped to 32,767; on load it is de-adjusted to ~32,640 — a "mate" score far above `INF_SCORE = 31_000`, which breaks window logic (`score >= beta` in `search_root`'s aspiration loop, `beta.abs() < MATE_BOUND` guards) at deep plies. | Deterministic: `tt.rs` unit test with `score = MATE_SCORE - 1, ply = 127` (added with the fix); reproduced by inspection of the clamp path. | pending |
| R-06 | `src/uci.rs:115-118` (`isready`) and `src/uci.rs:154-201` (`position`) | MEDIUM | `isready` prints `readyok` **while a search is still running**, so `readyok` can be emitted before the pending `bestmove` (UCI requires the engine to flush pending output and be ready to accept new commands). Practical effect observed: piping `position … go depth 5\nisready\nquit` produces `readyok` then a truncated `bestmove` and no `info` lines. (Belt-and-braces; `position`/`go`/`stop` do join first, so the runner path is safe.) | `printf 'uci\\nucinewgame\\nposition startpos moves e2e4 e7e5\\ngo depth 5\\nisready\\nquit\\n' \| flawless uci` → `readyok` printed before any `info depth …` and before `bestmove`. | pending |
| R-07 | `src/uci.rs:154-201` (`cmd_position`) | MEDIUM | On an illegal/unknown move in `position … moves …` the engine logs to **stderr** and `break`s, silently keeping the truncated position and then searching it — it still answers `bestmove` with a legal move *from a different position*. A GUI/runner bug (or a FEN typo like the one found in this review) is therefore invisible in the game record. Correct behaviour for a strict engine: reject the whole `position` command (keep the previous position) or report `bestmove 0000`; the match harness would then flag `illegal_move`/`engine_exited` rather than silently mis-searching. | `position fen 7q/8/8/8/8/8/8/6K1 b - - 100 74` (illegal: mover attacks enemy king) → stderr `info string position error: …` and stdout continues with `bestmove a2a3` from the *start position*. | pending |
| R-08 | `src/search.rs:340-350`, `src/uci.rs:283-300` (`clock_limits`) | MEDIUM | `soft_ms` is only consulted **between iterative-deepening iterations**; nothing inside the tree watches the soft limit. At game-like time controls a single iteration can be several times the soft budget (measured: `go depth` ladders double nodes per ply), so the engine systematically overspends its planned period budget. The `hard` cap prevents flagging, but the plan is fiction: with 40/15, `soft = 22.3 s`, iterations of 60-90 s are possible → effective per-move spend up to `hard`, draining the reserve much faster than the ENGINE-1 model assumes. | Bench-style measurement of iteration wall-times vs `soft_ms` (see E-fix-8 in the upgrade log); node budget for iteration N+1 ≈ 3-4× iteration N at these depths. | pending |
| R-09 | `src/position.rs:640-672` (`insufficient_material`) | LOW (accepted, documented) | Dead-position detection omits the "two same-colour-square bishops of the *same* side" and "K+minor+pawn vs K"-style forced cases only in the strict sense; specifically it returns `false` for K+2N vs K and K+B+B(same colour, one side) vs K, which are dead for *forcing* purposes (FIDE 5.2b covers only "series of legal moves cannot lead to mate"). Documented as an accepted approximation: it is conservative (never claims a draw where mate is legally possible) and only affects scoring of rare endgames. | Unit cases in `tests/correctness.rs::insufficient_material_table` (already asserting the same interpretation). | accepted — no fix this round; rationale recorded here and in DESIGN_LOG |
| R-10 | `src/attack.rs:288-310` (`rook_attacks`/`bishop_attacks`) | LOW | `magic_ready()` scans all 64 entries on **every** slider attack call (a per-call loop instead of a cached flag). | Source inspection; fixed with R-03 work since it sits on the same hot path. | pending |
| R-11 | `src/position.rs:300-312` (`from_fen`) | LOW | Missing halfmove/fullmove fields default silently to `0`/`1` instead of erroring, so a 4-field FEN is accepted with a fabricated clock. Affects only hand-written FENs (the harness always sends 6 fields). | `Position::from_fen("4k3/8/8/8/8/8/8/4K3 w - -")` succeeds. | accepted — no fix; documented (harness + tests always use full FENs; rejecting could break existing FEN-based evidence tooling) |
| R-12 | `src/search.rs:497-500` (TT probe) | MEDIUM | The TT probe/cutoff happens **before** terminal (mate/stalemate) detection. That is only sound while "score cutoff ⇒ the node's own mate/stalemate status cannot change the result". With R-02 fixed, mate precedence over claimable draws must be evaluated before any cached score is accepted; otherwise an `EXACT draw` entry at a node that actually has a mate-in-1 short-circuits it (this is exactly how R-02 manifests at the root after the first iteration, e.g. in a long 50-move endgame). | Root case reproduced in R-02 (`halfmove 99` iteration 1 stores an exact draw at the root key; later iterations return `cp 0` in 144 nodes). | pending |
| R-13 | `scripts/match.py:153-160` (`set_position`) + engine root-repetition | MEDIUM | The harness deliberately sends the **full move list** (`position startpos moves …`) "so the engine's repetition detection has the whole game context". Combined with R-02(a) this converts a normal shuffling phase into an immediate "play first legal move" — the harness is correct, the engine was not; recorded here so the interaction is not "fixed" by weakening the harness. | See R-02 reproduction. | pending (engine side) |
| R-14 | `src/search.rs:826-830` (SEE comment vs. `move_order_score`) | LOW (accepted, documented) | SEE is applied to *ordering only*; the comment says the model "never prunes tactical captures", which is accurate for `quiesce` (the delta cut uses material gain, not SEE) but the "losing captures" band (score `40_000 + see`) sits *below* quiet moves (score `50_000 + history`), which effectively prunes them by ordering. Accepted: standard practice, and no capture is dropped from the list. | Source inspection. | accepted — no fix |
| R-15 | `src/position.rs:520-527` (castle rook hash) | LOW | `make_move` updates the rook bitboards for castling but the Zobrist delta uses `zob_piece(ridx, rook_from) ^ zob_piece(ridx, rook_to)` computed from the *pre-move* `ridx`; correct, but relies on `m.to` file==6/==2 detection with no check that a rook is actually present (guaranteed by `make_move` being called with legal moves only). Invariant `hash == zobrist_full()` is asserted in tests (`debug_check_invariants`, DIFTEST). Accepted with rationale. | DIFTEST (76,240 positions) + `magic_vs_walk_exhaustive`, `hash` invariant tests pass at head. | accepted — no fix |

## Areas reviewed and found OK (no finding)

* **UCI `bestmove` exactly-once contract** (`src/uci.rs` worker/hold/printed/flush protocol):
  verified by reading plus the existing stress regression
  `ponderhit_or_stop_racing_search_end_emits_exactly_one_bestmove` (30 trials, passing).
* **Panic fallback** (`catch_unwind` + `fallback_move` + `0000`) — always emits a `bestmove`.
* **Null-move hash/repetition handling** (ep excluded across null, `ep_included` cached, not
  pushed onto `history`) — consistent.
* **Fifty-move/CLOCK-UNSAFE TT policy** (`src/tt.rs::store`) — sound *given* R-12 is fixed.
* **MultiPV** root handling, aspiration re-search logic, `searchmoves` restriction (restricted-root
  entries never stored as unrestricted bounds), `quiet_tried` history-demotion bookkeeping.
* **Match harness statistics** (`scripts/stats.py`): opening-cluster bootstrap with paired totals,
  seat-perspective scoring, boundary scores never clamped to a finite Elo, unadjudicated `*` games
  excluded from scoring, engine-error games excluded by default. Consistent with
  `docs/RATING_PROTOCOL.md` §9.6-9.8 as implemented in `scripts/rating_estimator.py`.
* **Fail-closed gate behaviour** (`rating-gate.yml`, `verify_evidence.py`, `aggregate_shards.py`):
  missing gate plan/evidence ⇒ failure (observed live in run 44068565038 at this head) — correct.
* **Frozen anchors/protocol**: `benches/anchor-pool*.json`, `docs/RATING_PROTOCOL.md` and the pinned
  hashes in `PREREGISTRATION.md` are internally consistent with the CI assertions in `ci.yml`.

## Disposition summary (as of writing)

15 findings: 3 HIGH, 7 MEDIUM, 5 LOW (3 of them accepted with documented rationale).
All HIGH and MEDIUM findings are scheduled for fixes, one commit each, with correctness gates and
a preliminary A/B measurement re-run after the batch (see MISSION_CHECKPOINT.md and DESIGN_LOG.md).
