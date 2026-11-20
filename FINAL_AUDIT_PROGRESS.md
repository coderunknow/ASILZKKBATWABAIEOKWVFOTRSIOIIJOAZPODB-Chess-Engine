# FINAL_AUDIT_PROGRESS.md — FlawLessChess 0.1.0 release mission ledger

Branch: `arena/f668bde4-flawlesschess` (branched from `c25e65e` of `arena/2d2d30b4-flawlesschess`)
Base PR: #3 (`arena/2d2d30b4-flawlesschess`, OPEN, DRAFT (title ends "(draft)"), base `main`). Its head is NOT this branch.
Baseline HEAD at start: `c25e65efc0c6223f58701d529775726db13ebedd` (verified; remote PR head matches)
Toolchain: Rust 1.99.0 installed from npm `@toolchain-bin/*` into `/home/user/.toolchain/sysroot` (`source /home/user/.toolchain/env`)
Baseline (c25e65e): `cargo build --release` OK; `cargo test --release` OK. Correct counts from the post-fix run: lib 19 (base) / 22 (final), clock_smoke 3, correctness 21 (base), movetime_smoke 11, uci_smoke 11. The old "lib 21" baseline line was not a verified count and is superseded by the logs in `/tmp/gates/`.

Status legend: NOT STARTED / IN PROGRESS / BLOCKED / COMPLETED / VERIFIED

## Phase A — reconnaissance & audit

| ID | Task | Status | Findings / evidence | Next action |
|---|---|---|---|---|
| A1 | Branch/remote/PR state | VERIFIED | Branch == c25e65e == PR #3 head; PR #3 +10,609/-40 over main; 43 files. CodeRabbit (9336913 & c25e65e), Codex (c25e65e), Kilo ACTION_REQUIRED (billing) | — |
| A2 | Toolchain install | VERIFIED | rustc/cargo 1.99.0, clippy 0.1.99, rustfmt 1.10.0 | — |
| A3 | Read src/search.rs, uci.rs, position.rs, movegen.rs, types.rs, tt.rs, attack.rs | COMPLETED | see suspect list S-* below | probe each suspect |
| A4 | Read src/eval.rs, src/main.rs | COMPLETED | main.rs CLI reviewed; eval colour symmetry tested directly (303 pairs, `static_evaluation_is_colour_symmetric`) | — |
| A5 | Read tests/*, scripts/windows_artifact.py, CI workflows | COMPLETED | CI: ci.yml has 3 jobs (test ubuntu/windows, msrv 1.80, windows-x64-artifact). CodeRabbit PR #3 items on 9336913 were fixed in c25e65e (BESTMOVE_RE ponder, finish(eof=False), selfplay --only, ENGINE_ERROR record); the CI `persist-credentials` nitpick is fixed here | — |

## Suspect list (from audit, to be reproduced in Phase B)

- S-01 (FIXED, F-04) `setoption name Hash value 4096` is accepted, but `TranspositionTable::resize` clamps to 2^27 entries = 1 GiB. Effective size silently capped (tt.rs:98).
- S-02 `clock_limits`: `usable / mtg + inc / 2` can overflow u64 for huge wtime + increment (release wraps silently) (uci.rs:608).
- S-03 `go wtime N` without `btime` (or vice versa) → no clock limit, search runs to depth 64 (uci.rs:305/308).
- S-04 UCI stdin loop terminates on the first non-UTF-8 line (`while let Some(Ok(line))`) — engine silently exits (uci.rs:92).
- S-05 `MoveList::push` bound is only `debug_assert!` (types.rs:228); pseudo-legal move count >256 would panic in release via index OOB → reproduce with dense FEN.
- S-06 `searchmoves` with only illegal moves (NOT REPRODUCED; process test `illegal_only_searchmoves_still_returns_a_legal_move`).
- S-07 `go ponder nodes N` node cap after ponderhit (NOT REPRODUCED with ponderhit sent immediately: 4,559 nodes for cap 5,000; process test `ponder_node_cap_is_enforced_after_ponderhit`).
- S-08 `go nodes N`: NO overshoot observed (stops at or below N). Observed UNDERSHOOT: 651 nodes for N=1000, 4,126 for 5,000, 17,024 for 20,000, 81,210 for 100,000. Cause not analysed. Not a defect in the cap (upper bound holds). LOW.
- S-09 `is_repetition` scans whole history per node (position.rs:746). LOW perf.
- S-10 Aspiration loop termination: relies on invariant score > -INF. VERIFY (LOW).
- S-11 (FIXED, F-06) `Threads` non-1 values now reported on stdout. Test `threads_other_than_one_is_reported_on_stdout`.
- S-12 (VERIFIED, no defect) FEN castling rights are not checked against placement; stale rights generate no castling move; correct rights generate exactly the castles. Tests `stale_castling_rights_without_rooks_generate_no_castling`, `castling_rights_with_rooks_generate_exactly_the_castles`, `castling_right_is_ignored_when_king_is_off_its_home_square`.
- S-13 `resize` / `setoption Hash` allocation peak (old+new table both live) and `ucinewgame` clears full table each call (perf, LOW).

## Phase B/C — reproduced findings and fixes (batch 1)

| Finding | Severity | Evidence | Root cause | Fix | Verification |
|---|---|---|---|---|---|
| F-01 (S-05) Legal-looking FEN crashes engine: `position fen KQQQQQBk/Q5RB/Q6Q/Q6Q/Q6Q/Q6Q/Q1QQ3Q/QR3QQQ w - - 0 1` + `go` → panic, exit 101 | HIGH | Reproduced on c25e65e via `flawless uci` (main-thread generate_legal) and `moves` batch | FEN accepted >16 pieces/side; pseudo-legal moves 256+ overflow fixed `MoveList` (types.rs push used debug_assert only) | FEN material check (≤16 pieces/side, ≤8 pawns, promoted ≤ missing pawns, `position.rs::material_is_reachable`); MOVE_LIST_CAPACITY=512 with bound 335 documented; push uses hard assert | tests `impossible_material_fen_is_rejected_without_crashing`, correctness `fen_rejects_material…`, `move_list_capacity…`; perft refs unchanged |
| F-02 (S-04) Non-UTF-8 input byte ends the UCI session (engine exits silently) | HIGH | `printf '\xff\xfe x\nisready\n' \| flawless` → no readyok, exit | `lines()` returns Err → `while let Some(Ok)` ends loop | byte-level bounded reader `read_bounded_line`; lossy UTF-8; oversized lines (>64 KiB) dropped with info string | `non_utf8_input_line_does_not_end_the_session`, `oversized_input_line_is_dropped_and_session_continues`, unit tests |
| F-03 (S-03) `go wtime N` alone (or `btime` alone) has NO limit: search runs to depth 64 until stop/EOF | HIGH | `printf 'go wtime 2000'` searched to depth 13 and beyond; bestmove only at EOF | clock_limits only when both clocks present; else unlimited | side-to-move clock governs; opponent clock defaults to it; unlimited only if side-to-move clock absent (bare go semantics) | `single_side_clock_bounds_the_search` (0.1 s); `clock_limits_saturate…` |
| F-04 (S-01) Hash 4096 advertised/accepted but TT silently capped at 1 GiB (2^27 entries) | MEDIUM | probe: TT::new(4096) RSS 1,050,324 kB == TT::new(1024) | clamp(…, 1<<27) in tt.rs | advertise & accept Hash 1..=1024 (`MAX_HASH_MB`), reject larger with info string on stdout | `hash_limit_is_advertised_and_enforced` |
| F-05 (S-02) clock_limits `usable/mtg + inc/2` u64 overflow (wraps in release) | LOW | arithmetic audit; reachable only with ~u64::MAX clocks + large increment | unchecked add | saturating_div/saturating_add | unit test `clock_limits_saturate_instead_of_wrapping` |
| F-06 setoption rejection messages went to stderr only (invisible to GUIs) | LOW | `setoption Hash 4096` printed nothing on stdout | eprintln! | `info string` on stdout | covered by F-04 test |
| F-07 Search worker thread used default 2 MiB stack while MoveList grew to 4 KiB per frame | LOW (defence) | design review | — | 16 MiB worker stack (`SEARCH_STACK_BYTES`) | build + tests |

Verified unchanged: `bench` signature `141943aa23b3fc68` and node count 2,530,885 identical to base c25e65e; NPS within noise (≈360–414k on this 2-vCPU box for both builds).
Verified: perft CPW references (startpos d1–d4, Kiwipete d1–d3, pos3 d1–d4, pos4 d1–d3, pos5 d1–d3, pos6 d1–d3) — all match; now permanent tests in tests/correctness.rs.
Verified (process level, unchanged behaviour): illegal-only `searchmoves` returns a legal move; `go ponder nodes N` honours the node cap after ponderhit.
Local gates after batch 1: `cargo fmt --check` OK; `cargo clippy --all-targets -- -D warnings` OK; `cargo test --release` all green (22 lib, 3 clock, 30 correctness, 11 movetime, 11 uci_smoke, 6 protocol_regressions).

## Phase B/C — batch 2 (differential testing, checker validation, process tests)

Commit 49fdecf holds batch 1. Batch 2 is the next commit on this branch.

| Finding | Severity | Evidence | Root cause | Fix | Verification |
|---|---|---|---|---|---|
| F-08 Positions with two checkers on one line through the king, or with three checkers, were ACCEPTED (e.g. `1b4NQ/8/7R/3q4/3P1bn1/3k1K1P/3p4/2B1bN1q w - - 0 1`, queens d5 and h1 both checking Kf3 along one diagonal) | LOW–MEDIUM (unreachable input accepted; no crash) | Found by differential fuzzing against python-chess `Status.IMPOSSIBLE_CHECK` / `TOO_MANY_CHECKERS`: 14 oracle-invalid positions were accepted before the fix; 0 after | `from_fen` checked only that the side not to move is not in check | Reject >2 checkers and 2 checkers aligned with the king between them (`king_between_aligned`) | tests `fen_rejects_two_checkers_on_one_line_through_the_king`, `fen_rejects_more_than_two_checkers`, `fen_accepts_a_legal_double_check_from_knight_and_queen` |
| NOTE (not a defect) The material rule (F-01) rejects some positions that python-chess accepts | — | Each of the 3–26 rejections per seed is justified by the independent necessary condition (≤16 pieces, ≤8 pawns, excess over start counts ≤ missing pawns); no unjustified rejection in any seed | — | — | `scripts/fuzz_legal_differential.py` "justified by material bound" count |
| EP-01 Full game with en passant was NOT verified in batch 1 | — | Saved self-play games contain 0 en passant captures (checked with python-chess) | — | New referee-based probe `scripts/fullgame_en_passant_probe.py`: forced `e5f6` via `go searchmoves`, then engine-vs-engine to the rule end | runs: 91 plies, 1 ep, threefold (seed-free, 20 ms/move); 47 plies, 1 ep, 2 castles (150 ms/move); 70 plies, 1 ep, 1 castle (final gate run); CI step added |
| S-14 Search is not colour-symmetric at depth 4 for 2 of 40 random positions (e.g. `3r1rn1/pb2kpp1/Bppp4/3p2pP/P2KP1P1/1RQ2N2/1bP2P2/7R w - - 0 27`: 446 vs 493 cp). Depths 1–3 are equal. | LOW (open, informational) | `scripts/eval_symmetry_probe.py` (interactive, deterministic) | Expected for null-move pruning, LMR and move-order ties; NOT an evaluation asymmetry: the static evaluation is symmetric on the same two positions (`static_evaluation_is_colour_symmetric`, 303 pairs) | None (search heuristics are not required to be symmetric). Not proven to be heuristic-only; open. | probe prints SEARCH-MISMATCH; hard gate is the Rust test |
| UCI-NOTE `go` + `quit` in one stdin burst returns an UNSEARCHED fallback `bestmove` (first legal move, e.g. `a2a3`), because `quit` stops the search before any iteration completes | not a defect of the protocol (quit abandons the search) | Reproduced: `go depth 4` + `isready` + `quit` in one burst → 0 info lines; with a 3 s wait before `isready` → 4 info lines | test-method artifact (already documented in CHANGELOG) | none; probes wait for `bestmove` before `quit` | `uci_bestmove_smoke.py`, `eval_symmetry_probe.py` |

Fuzzing and differential evidence (this session, release build of the batch-2 tree):
- `scripts/fuzz_legal_differential.py` seeds 1–6 (games 40/150/150/150/150/150) plus placement fuzz: 157,000+ positions checked against python-chess legal move sets, all agree (0 mismatches); 0 oracle-invalid positions accepted; every engine rejection of an oracle-valid position justified by the material bound; en passant positions present in every seed (293–1,073 each).
- `scripts/fuzz_uci_grammar.py` seeds 1–5 (150 + 4×300 sessions = 1,350 random UCI sessions, valid and malformed commands, random FENs, go variants, binary garbage): 0 hangs, 0 crashes, 0 missing handshakes, 0 bad exit codes.
- `scripts/eval_symmetry_probe.py`: 40 positions at depth 4, 2 informational search mismatches (S-14).

Gate evidence on the batch-2 tree (logs in /tmp/gates/): `cargo fmt --all -- --check` rc 0; `cargo clippy --release --all-targets -- -D warnings` rc 0; `cargo clippy --all-targets -- -D warnings` rc 0; `cargo test --release --locked` all green (lib 22, clock 3, correctness 37, movetime 11, protocol_regressions 8, uci_smoke 11); `cargo test --locked` (debug) all green; Python suites test_match 111/111, test_rating_estimator 65/65, test_reduced_sample 7/7, test_make_batch_dispatch 7/7, test_power_analysis OK, test_merge_batch_runs PASS, test_windows_artifact OK, test_aggregate_60 PASS, test_recover_download PASS; verify_opening_subsets rc 0; power_analysis JSON assertions (CI) ok; uci_bestmove_smoke ok; uci_protocol_probe 12/12; uci_malformed_probe 37/37; selfplay_games rc 0; fullgame_en_passant_probe PASS; resource_probe rc 0 (peak RSS 21/56/82 MiB at Hash 16/64/256; exit 0); perft 3 = 8902; bench signature 141943aa23b3fc68, 2,530,885 nodes.

Not run locally: MSRV 1.80 (toolchain unavailable on the npm mirror; CI `msrv` job is the check of record); Windows x64 build and smoke (CI `windows-x64-artifact` job is the check of record; no local Windows); GUI tests (no GUI is part of this release; see docs/WINDOWS_GUI_TEST.md, which states that no GUI test has been run).

## Phase E — PR #4 review triage (CodeRabbit on b3a9480; Codex: no findings; Qodo and Kilo: billing-blocked, not counted)

CodeRabbit posted 12 inline comments and 1 nitpick. All are addressed in the next commit. Each fix was checked by a test, a self-test, or a rerun.

| Item | File | Triage | Fix and evidence |
|---|---|---|---|
| Major: final `isready` reply not required | scripts/fuzz_uci_grammar.py | VALID (the membership check passed on an earlier `readyok`; one dead `if` block) | `isready` removed from the generator; each session must give exactly one `readyok`; seeds 11 and 21 pass |
| Malformed or extra `bestmove` accepted by prefix | scripts/windows_artifact.py | VALID, CI-critical (a malformed second reply was dropped by the regex filter) | Count all `bestmove` lines over the full transcript; require one, matching `BESTMOVE_RE`; 3 new tests (`test_second_legal_bestmove_is_rejected`, `test_second_malformed_bestmove_is_rejected`, `test_malformed_single_bestmove_is_rejected`); fake-session `finish()` now drains like the real one; 22/22 |
| Second `bestmove` not counted | scripts/uci_protocol_probe.py, scripts/uci_malformed_probe.py | VALID | Protocol probe: at most one `bestmove` on the full transcript (in `close()`). Malformed probe: count after drain. Self-test with a fake engine that prints two replies: FAIL "2 bestmove lines" / EXTRA_BESTMOVE x2 |
| No deadline on the forced depth search | scripts/fullgame_en_passant_probe.py | VALID | `Limit(depth=3, time=5.0)` (python-chess applies `timeout + limit.time`) |
| Shutdown failure passes | scripts/fullgame_en_passant_probe.py | VALID | `quit()` errors fail the probe; exit code read from `eng.protocol.returncode`; rerun exit 0 with exit code checked |
| Reply wait blocks forever | scripts/eval_symmetry_probe.py | VALID | Reader thread and queue; every wait has a deadline; kill and reap on any failure |
| Stdin write can block the Rust test | tests/protocol_regressions.rs | VALID | Writer thread owns stdin; test thread never blocks on write; `quit` closes the channel; 8/8 |
| Cleanup on failure | benches/movetime-20261119/measure_movetime.py | VALID | try/finally kills and reaps the engine; logic unchanged |
| Knight placed on g1 (single check, not the double check the test names) | tests/correctness.rs | VALID (nitpick, a real error in my test) | FEN changed to `4k3/8/8/8/8/8/3q2n1/4K3 w - - 0 1` (checkers d2 and g2, verified with python-chess: 2 checkers, legal e1d2 e1f1); test asserts the exact move list |
| Windows GUI guide names the PR #3 head | docs/WINDOWS_GUI_TEST.md | VALID | Points to the release PR's head run; the candidate c64b743 is excluded |
| RC audit: manifest and checksum alone cannot check the exe | docs/audit/2026-11-19-v0.1.0-release-candidate.md | VALID | Blocker item now asks for `flawless.exe`, `BUILD-MANIFEST.txt`, `SHA256SUMS.txt` |
| Unescaped pipe in ledger row F-02 | FINAL_AUDIT_PROGRESS.md | VALID | Pipe escaped; all F-rows have 6 cells |
| CI `persist-credentials` | .github/workflows/ci.yml | done in 49fdecf/b3a9480 | — |
