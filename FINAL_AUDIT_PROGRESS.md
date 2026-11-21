# FINAL_AUDIT_PROGRESS.md — FlawLessChess 0.1.0 release mission ledger

Branch: `arena/f668bde4-flawlesschess` (branched from `c25e65e` of `arena/2d2d30b4-flawlesschess`)
Base PR: #3 (`arena/2d2d30b4-flawlesschess`, OPEN, DRAFT, base `main`) is SUPERSEDED by PR #4 (`arena/f668bde4-flawlesschess`, not draft, the release PR). PR #3 is not the release vehicle and stays draft. Its head is NOT this branch.
Baseline HEAD at start: `c25e65efc0c6223f58701d529775726db13ebedd` (verified; remote PR head matches)
Toolchain: Rust 1.99.0 installed from npm `@toolchain-bin/*` into `/home/user/.toolchain/sysroot` (`source /home/user/.toolchain/env`)
Baseline (c25e65e): `cargo build --release` OK; `cargo test --release` OK. Verified test counts (`#[test]` per commit): unit tests in src/: 19 at c25e65e, 22 at 3a280df; tests/correctness.rs 21 (c25e65e), 30 (49fdecf), 37 (3a280df); tests/protocol_regressions.rs absent (c25e65e), 6 (49fdecf), 8 (3a280df), 9 (working tree after the searchmoves change); clock_smoke 3, movetime_smoke 11, uci_smoke 11 unchanged. The old "lib 21" baseline line was not a verified count and is superseded by the logs in `/tmp/gates/`.

Status legend: NOT STARTED / IN PROGRESS / BLOCKED / COMPLETED / VERIFIED

## Phase A — reconnaissance & audit

| ID | Task | Status | Findings / evidence | Next action |
|---|---|---|---|---|
| A1 | Branch/remote/PR state | VERIFIED | Branch == c25e65e == PR #3 head; PR #3 +10,609/-40 over main; 43 files. CodeRabbit (9336913 & c25e65e), Codex (c25e65e), Kilo ACTION_REQUIRED (billing) | — |
| A2 | Toolchain install | VERIFIED | rustc/cargo 1.99.0, clippy 0.1.99, rustfmt 1.10.0 | — |
| A3 | Read src/search.rs, uci.rs, position.rs, movegen.rs, types.rs, tt.rs, attack.rs | COMPLETED | see suspect list S-* below | probe each suspect |
| A4 | Read src/eval.rs, src/main.rs | COMPLETED | main.rs CLI reviewed; `evaluate`, `eval_color`, `breakdown` read in full (phase, mirror via `sq ^ 56`, side-to-move sign, pawns, king safety, rook files). Colour symmetry tested directly (303 pairs, `static_evaluation_is_colour_symmetric`, passes). The search-level mismatch S-14 is diagnosed in Phase G: cause LMR, not evaluation | — |
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
| F-08 Positions with two checkers on one line through the king, or with three checkers, were ACCEPTED (e.g. `1b4NQ/8/7R/3q4/3P1bn1/3k1K1P/3p4/2B1bN1q w - - 0 1`, queens d5 and h1 both checking Kf3 along one diagonal) | MEDIUM (unreachable input accepted; no crash) | Found by differential fuzzing against python-chess `Status.IMPOSSIBLE_CHECK` / `TOO_MANY_CHECKERS`: 14 oracle-invalid positions were accepted before the fix; 0 after | `from_fen` checked only that the side not to move is not in check | Reject >2 checkers and 2 checkers aligned with the king between them (`king_between_aligned`) | tests `fen_rejects_two_checkers_on_one_line_through_the_king`, `fen_rejects_more_than_two_checkers`, `fen_accepts_a_legal_double_check_from_knight_and_queen` |
| NOTE (not a defect) The material rule (F-01) rejects some positions that python-chess accepts | — | Each of the 3–26 rejections per seed is justified by the independent necessary condition (≤16 pieces, ≤8 pawns, excess over start counts ≤ missing pawns); no unjustified rejection in any seed | — | — | `scripts/fuzz_legal_differential.py` "justified by material bound" count |
| EP-01 Full game with en passant was NOT verified in batch 1 | — | Saved self-play games contain 0 en passant captures (checked with python-chess) | — | New referee-based probe `scripts/fullgame_en_passant_probe.py`: forced `e5f6` via `go searchmoves`, then engine-vs-engine to the rule end | runs: 91 plies, 1 ep, threefold (seed-free, 20 ms/move); 47 plies, 1 ep, 2 castles (150 ms/move); 70 plies, 1 ep, 1 castle (final gate run); CI step added |
| S-14 Search is not colour-symmetric at depth 4 for 2 of 40 random positions (`3r1rn1/pb2kpp1/Bppp4/3p2pP/P2KP1P1/1RQ2N2/1bP2P2/7R w - - 0 27`: 446 vs 493 cp; `1q3bnr/r5p1/n1k2p1p/p1p1pQ2/1BN5/2P2bPP/p2P1KR1/3R2N1 b - - 3 27`: 1284 vs 1262 cp). Mismatches by depth: 0 at depth 2, 1 at depth 3 (48 vs 45), 2 at depth 4. | LOW, not a defect (informational) | `scripts/eval_symmetry_probe.py` | DIAGNOSED (Phase G). Static evaluation is equal on each pair (`flawless eval`: 353/353, 743/743, and 44/44 for the depth-3 pair). Disabling LMR alone makes both depth-4 pairs symmetric (446/446, 1262/1262); disabling null-move pruning alone does not (446/493, 1284/1262). Cause: LMR reduces by move index, and the mirror position generates moves in a different order. | No search change. Search is not required to be colour-symmetric; the hard gate is the static test. | probe prints SEARCH-MISMATCH; hard gate is `static_evaluation_is_colour_symmetric` |
| UCI-NOTE `go` + `quit` in one stdin burst returns an UNSEARCHED fallback `bestmove` (first legal move, e.g. `a2a3`), because `quit` stops the search before any iteration completes | not a defect of the protocol (quit abandons the search) | Reproduced: `go depth 4` + `isready` + `quit` in one burst → 0 info lines; with a 3 s wait before `isready` → 4 info lines | test-method artifact (already documented in CHANGELOG) | none; probes wait for `bestmove` before `quit` | `uci_bestmove_smoke.py`, `eval_symmetry_probe.py` |

Fuzzing and differential evidence (this session, release build of the batch-2 tree):
- `scripts/fuzz_legal_differential.py` seeds 1–6 (games 40/150/150/150/150/150) plus placement fuzz: 157,000+ positions checked against python-chess legal move sets, all agree (0 mismatches); 0 oracle-invalid positions accepted; every engine rejection of an oracle-valid position justified by the material bound; en passant positions present in every seed (293–1,073 each).
- `scripts/fuzz_uci_grammar.py` seeds 1–5 (150 + 4×300 sessions = 1,350 random UCI sessions, valid and malformed commands, random FENs, go variants, binary garbage): 0 hangs, 0 crashes, 0 missing handshakes, 0 bad exit codes.
- `scripts/eval_symmetry_probe.py`: 40 positions at depth 4, 2 informational search mismatches (S-14).

Gate evidence on the batch-2 tree (logs in /tmp/gates/): `cargo fmt --all -- --check` rc 0; `cargo clippy --release --all-targets -- -D warnings` rc 0; `cargo clippy --all-targets -- -D warnings` rc 0; `cargo test --release --locked` all green (lib 22, clock 3, correctness 37, movetime 11, protocol_regressions 8, uci_smoke 11); `cargo test --locked` (debug) all green; Python suites test_match 111/111, test_rating_estimator 65/65, test_reduced_sample 7/7, test_make_batch_dispatch 7/7, test_power_analysis OK, test_merge_batch_runs PASS, test_windows_artifact OK, test_aggregate_60 PASS, test_recover_download PASS; verify_opening_subsets rc 0; power_analysis JSON assertions (CI) ok; uci_bestmove_smoke ok; uci_protocol_probe 12/12; uci_malformed_probe 37/37; selfplay_games rc 0; fullgame_en_passant_probe PASS; resource_probe rc 0 (peak RSS 21/56/82 MiB at Hash 16/64/256; exit 0); perft 3 = 8902; bench signature 141943aa23b3fc68, 2,530,885 nodes.

Not run locally: MSRV 1.80 (toolchain unavailable on the npm mirror; CI `msrv` job is the check of record); Windows x64 build and smoke (CI `windows-x64-artifact` job is the check of record; no local Windows); GUI tests (no GUI is part of this release; see docs/WINDOWS_GUI_TEST.md, which states that no GUI test has been run).

## Phase E — PR #4 review triage (CodeRabbit on b3a9480; Codex on b3a9480: no findings; Qodo and Kilo: billing-blocked, not counted)

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

## Phase F — release gate status (head 3a280df, PR #4)

| Gate | Status | Evidence |
|---|---|---|
| G1 CI on the exact final commit | PASS for `3a280df` only; must be re-run on the final SHA | `gh pr checks 4` on `3a280df`: 17 pass (ubuntu-latest, windows-latest, msrv (rust 1.80), windows x64 release artifact, verify-flawless, sf10-calibration, 11 build-* anchor jobs). CodeRabbit: skipping. Kilo Code Review: fail (billing; not bypassed). Runs 44741770006 (CI) and 44741769812 (anchor-verify). |
| G2 CodeRabbit review on the final head | NOT OBTAINED | The review of `b3a9480` (12 comments) is addressed. Re-review requests on `3a280df` (12:4x and 13:19Z, `@coderabbitai review`) returned "Review rate limited". Not claimed. |
| G3 Windows artifact: SHA-256 and manifest checked against the executable | NOT VERIFIED (sandbox limit; retried 13:26Z, still EOF) | The artifact `flawless-windows-x64-3a280dff77fcf1042dd49789b7442e63fd50a496` and the job logs are served from `productionresultssa10.blob.core.windows.net`, which this sandbox cannot reach (EOF on download and log fetch). The CI steps that build the exe, check the PE machine type, smoke-test the exact exe, and write `SHA256SUMS.txt` and `BUILD-MANIFEST.txt` all succeeded. The bytes were not inspected locally. |
| G4 GUI smoke test | NOT APPLICABLE | The release contains the UCI engine executable only. No GUI is shipped. `docs/WINDOWS_GUI_TEST.md` is an optional user test and has not been run. |
| G5 Local gates on the final tree | PASS on `8370bed` (Phase H) | Earlier logs in /tmp/gates/ were produced before the searchmoves change and do not count for the final commit. |
| G6 MSRV 1.80 | PASS in CI | msrv job success on 3a280df. Not run locally (toolchain unavailable). |

Decision: the release is NOT published and PR #4 is NOT merged. G2 and G3 are open. Merge, tag `v0.1.0`, and the GitHub Release wait for G2 (CodeRabbit on the final head) and G3 (artifact verified by the user or by a retry from a network that can reach the artifact host).

## Phase G — post-PR-#4 work on head 3a280df

| Item | Result | Evidence |
|---|---|---|
| Codex P2 on `src/search.rs:250`: `go searchmoves` with no legal named move widens to all legal moves, outside the requested set (UCI says it restricts) | PARTLY ACCEPTED. Widening kept by decision (DESIGN_LOG 2026-11-20); now announced on stdout | Null move (`bestmove 0000`) is the defect the mission names. Engine now prints `info string searchmoves names no legal move in this position; searching all legal moves` before the search. `illegal_only_searchmoves_still_returns_a_legal_move` asserts the notice; new control `legal_searchmoves_are_respected_without_widening_notice`. `cargo test --test protocol_regressions`: 9 passed. Manual: `go depth 2 searchmoves e2e5 d2d9` → notice + `bestmove a2a3`; `searchmoves e2e4` → no notice. Recorded as F-09 in FAILURE_LEDGER and in README Known limitations. |
| S-14 search colour-symmetry mismatch (A4 open item) | DIAGNOSED: Late Move Reductions (move-index-dependent). Not a defect | Depth sweep, same 40 positions, seed 2026: depth 2 → 0 mismatches; depth 3 → 1 (48 vs 45); depth 4 → 2. Static eval equal on each mismatched pair (`flawless eval`). Scratch build outside the repo: LMR off → both depth-4 pairs symmetric (446/446, 1262/1262); NMP off only → mismatch remains (446/493, 1284/1262). Logs: /tmp/probe_d4.txt. Not changed. |
| Windows artifact retry | NOT VERIFIED (blocked) | `gh run download 44741770006 --name flawless-windows-x64-3a280dff77fcf1042dd49789b7442e63fd50a496` at 13:26Z: EOF from `productionresultssa10.blob.core.windows.net`; curl to the same host returns no HTTP status. |
| CodeRabbit re-review | NOT OBTAINED | Rate-limited again (13:19Z). |
| Docs | DONE | README Known limitations (Hash 1–1024 MiB; searchmoves behaviour). ARCHITECTURE.md L71 (Hash range 1–1024). `docs/WINDOWS_GUI_TEST.md` already names the release PR head and excludes c64b743 (3a280df). AGENTS_LOG L513 remains historical. |
| Ledger checks | DONE | F-08 is in FAILURE_LEDGER (batch-2 section) and in this file (batch-2 table, severity MEDIUM). AGENTS_LOG correction entry appended for the batch-1 clippy and protocol-test counts. |
| Final gates on the final commit | DONE for `8370bed` | See Phase H. |

## Phase H — final gates on source commit 8370bed (release decision)

Source commit: `8370bed8b8914c907d2a3ff2af5d4f2d4bed0e5` (pushed as a fast-forward `3a280df..8370bed`). Working tree clean before the gate run (`dirty_files 0`). Gate script: `/tmp/gates/run_final.sh`; logs and `summary.txt`: `/tmp/gates/final/`.

| Gate | Command | Result |
|---|---|---|
| fmt | `cargo fmt --all -- --check` | rc 0 |
| clippy | `cargo clippy --release --all-targets -- -D warnings`; `cargo clippy --all-targets -- -D warnings` | rc 0; rc 0 |
| build | `cargo build --release --locked` | rc 0 |
| tests | `cargo test --release --locked` | rc 0: lib 22, clock 3, correctness 37, movetime 11, protocol_regressions 9, uci_smoke 11 |
| tests (debug) | `cargo test --locked` | rc 0 (same suites; movetime 31 passed, 6 ignored, see log) |
| Python suites | test_match, test_rating_estimator, test_reduced_sample, test_make_batch_dispatch, test_power_analysis, test_merge_batch_runs, test_windows_artifact, test_aggregate_60, test_recover_download | all rc 0 |
| opening subsets / power | `verify_opening_subsets.py`; `power_analysis.py --replicates 1000` | rc 0; rc 0 |
| bench | `flawless bench` | signature `141943aa23b3fc68`, 2,530,885 nodes |
| perft | `flawless perft 3` | 8902 |
| UCI probes | `uci_bestmove_smoke.py`; `uci_protocol_probe.py` (12/12); `uci_malformed_probe.py` (37/37) | rc 0 each |
| self-play | `selfplay_games.py --tc 3000+50` | rc 0 |
| full game, en passant | `fullgame_en_passant_probe.py` | PASS: 91 plies, en_passant=1, castles=2, threefold |
| resource | `resource_probe.py 1000 16 64 256` | rc 0 |
| fuzz UCI grammar | seeds 9 (120 sessions), 21 (300 sessions) | rc 0; rc 0 |
| fuzz legal differential | seeds 7 (60 games), 1 (40 games) | rc 0; rc 0 |

CI on `8370bed`: run 44747171541 (CI) success; run 44747171587 (anchor-verify) success. `gh pr checks 4`: 17 pass (ubuntu-latest, windows-latest, msrv (rust 1.80), windows x64 release artifact, verify-flawless, sf10-calibration, 11 build-* anchor jobs). CodeRabbit: skipping. Kilo Code Review: fail (billing; not bypassed).

Reviews on `8370bed`:
- CodeRabbit: `@coderabbitai review` (13:46Z) → "Review rate limited". NO CodeRabbit review of `8370bed` exists. Not claimed. The three inline comments that appear on this commit are the earlier batch re-anchored; CodeRabbit's replies say they were addressed in `3a280df`. Checked in the code: `measure_movetime.py` has try/finally cleanup; `uci_malformed_probe.py` counts bestmove over the complete drained transcript; `uci_protocol_probe.py` `close()` counts bestmove over the complete transcript after quit.
- Codex: the P2 on `search.rs:250` (searchmoves widening) was answered on the PR (comment 7041115063). Decision kept: widening announced on stdout, `bestmove 0000` still refused. Codex has not re-reviewed; the disagreement is recorded, not hidden.

Windows artifact `flawless-windows-x64-3a280dff77fcf1042dd49789b7442e63fd50a496`: NOT VERIFIED. The CI artifact job succeeded for `3a280df` (all 8 steps), but the artifact download fails with EOF from `productionresultssa10.blob.core.windows.net` (retried 13:26Z). Manifest and SHA256 were not inspected.

GUI: not part of the release; GUI test not run (`docs/WINDOWS_GUI_TEST.md` is optional and unexecuted).

### Release decision

NOT RELEASED. PR #4 is NOT merged. Tag `v0.1.0` and the GitHub Release "FlawLessChess 0.1.0" are NOT created. Reason: two hard gates are open.
1. CodeRabbit review on the final head: not obtained (rate-limited).
2. Windows x64 artifact manifest and SHA256 verification: not possible from this sandbox.

All other gates pass on `8370bed`. Release becomes possible once both are closed. Either close them and re-run CI on the final SHA, or the user verifies the artifact from a network that can reach the blob host and accepts the CodeRabbit state.

Note on SHAs (historical, as of this phase): the ledger commit `8557a5d` that recorded this phase changed only `FINAL_AUDIT_PROGRESS.md` on top of `8370bed`; check with `git diff --stat 8370bed 8557a5d`. The gates above validate `8370bed` only. Later source changes are NOT covered by them; each later phase records its own gates on its own SHA.


## Phase I — final gates on source commit 7d5b489 (release decision, supersedes Phase H)

Source commit: `7d5b489405b8b5c513c284532a0865bb1dc7a472` (pushed as a fast-forward `8557a5d..7d5b489`). Changes since Phase H: S-14 colour-relative tie-break in `src/search.rs`; exact `go nodes` cap (S-08); `out_line!` output path that exits 0 on a closed stdout (F-10); new tests; anchor-verify bench signature `849a85bf7e8e1eba`; CHANGELOG, README, ARCHITECTURE, BENCHMARKING, FAILURE_LEDGER, DESIGN_LOG. Gate script: `/tmp/gates/run_final.sh` (rerun on this SHA); logs and `summary.txt` with `commit 7d5b489…` and `dirty_files 0`: `/tmp/gates/final/`. The Phase H run is archived at `/tmp/gates/final-8370bed/`.

| Gate | Command | Result |
|---|---|---|
| fmt | `cargo fmt --all -- --check` | rc 0 |
| clippy | `cargo clippy --release --all-targets -- -D warnings`; `cargo clippy --all-targets -- -D warnings` | rc 0; rc 0 (0 warnings in both logs) |
| build | `cargo build --release --locked` | rc 0 |
| tests | `cargo test --release --locked` | rc 0 (lib 22, clock 3, correctness 39, movetime 11, protocol_regressions 12, uci_smoke 11) |
| tests (debug) | `cargo test --locked` | rc 0 |
| Python suites | all `scripts/test_*.py` in ci.yml, plus test_aggregate_60 and test_recover_download | all rc 0 |
| opening subsets / power | `verify_opening_subsets.py`; `power_analysis.py --replicates 1000` | rc 0; rc 0 |
| bench | `flawless bench` | signature `849a85bf7e8e1eba`, 2,311,407 nodes (6.22 s, 371k nps on this runner) |
| perft | `flawless perft 3` | 8902 |
| UCI probes | `uci_bestmove_smoke.py` (b1c3 at depth 2); `uci_protocol_probe.py` (12/12); `uci_malformed_probe.py` (37/37) | rc 0 each |
| self-play | `selfplay_games.py --tc 3000+50` | rc 0 |
| full game, en passant | `fullgame_en_passant_probe.py` | rc 0, PASS (every engine move legal; game reached its end) |
| resource | `resource_probe.py 1000 16 64 256` | rc 0 (peak RSS 56.9 MiB at Hash 64, 88.0 MiB at Hash 256, 1 s movetime) |
| fuzz UCI grammar | seeds 9 (100 sessions), 21 (100 sessions), 11 (100 sessions) | failures=0 each |
| fuzz legal differential | seeds 1–7 (40 games each) | RESULT PASS each |
| search symmetry (informational) | `eval_symmetry_probe.py --positions 120 --depth 4` | 0 mismatches (was 6 before S-14 fix) |
| closed stdout | `protocol_regressions::closed_stdout_ends_the_process_quietly` | PASS; FAILS on the pre-fix source (exit-status assertion, test line 500; the old build panicked on the closed pipe) |

Mutation checks: the S-14 correctness tests fail on the pre-fix `search.rs` (cap 1 searched 1024 nodes; a recorded pair gave 446 vs 493). `closed_stdout` fails on the pre-fix `src/`.

CI on `7d5b489`: run 44753627798 (CI) success — `ubuntu-latest`, `windows-latest`, `msrv (rust 1.80)`, `windows x64 release artifact` all success. Run 44753628577 (anchor-verify) success. Kilo Code Review: `action_required` (billing; not bypassed).

Reviews on `7d5b489`:
- CodeRabbit: `@coderabbitai review` posted on PR #4 (comment 7042039996, 14:27Z). CodeRabbit replied "Review triggered" (comment 7042042371) and its check run stayed `in_progress` for about 3 minutes. No review with `commit_id` `7d5b489` exists at the time of writing. **G2 NOT OBTAINED. Not claimed.**
- Codex: P2 reply on the searchmoves widening (comment 7041115063, 13:46Z) is visible on PR #4. Codex has not re-reviewed `7d5b489`.

Windows artifact `flawless-windows-x64-7d5b489405b8b5c513c284532a0865bb1dc7a472` (artifact 14635798399, 206,405 bytes, not expired; run 44753627798): `gh run download -R coderunknow/FlawLessChess -n …` failed twice (EOF from `productionresultssa16.blob.core.windows.net`). The retry limit is reached and nothing more is attempted in this session. **G3 NOT VERIFIED.** The manifest and SHA256 were not inspected. The Windows-artifact tooling passes its own unit tests (`scripts/test_windows_artifact.py`, rc 0), but that does not verify this artifact.

GUI: not part of the release. No GUI test was run and no GUI result is claimed (`docs/WINDOWS_GUI_TEST.md` is unexecuted).

### Findings disposition (this phase)

- EPIPE / closed stdout (F-10, LOW): found in the audit's pipe probe. Scope: in scope, because a GUI closing the pipe is a normal shutdown path. **Fixed** (`out_line!`, exit 0). Regression test added.
- S-14 (MEDIUM): **Fixed** by a colour-relative tie-break. LMR stays on: disabling it also gives 0/120 but costs 18× the nodes. Bench reference updated.
- S-08 (LOW): **Fixed**. `go nodes N` spends exactly N nodes. Regression tests added.
- S-07 ponder cap: not reproduced. The regression test now asserts the exact cap after `ponderhit`.
- S-06 illegal-only `searchmoves`: not reproduced. The regression test asserts the stdout notice and the legal move. Remaining decision: widening versus refusing is recorded in DESIGN_LOG 2026-11-20.

### Release decision

NOT RELEASED. PR #4 is NOT merged. Tag `v0.1.0` and the GitHub Release "FlawLessChess 0.1.0" are NOT created. Open hard gates:
1. G2 CodeRabbit review on the final head: NOT OBTAINED for `7d5b489` (triggered, no review yet).
2. G3 Windows x64 artifact manifest and SHA256: NOT VERIFIED (blob host returns EOF from this sandbox).

All other gates pass on `7d5b489`. G5 local gates pass on `7d5b489`. G6 MSRV 1.80 passes in CI on `7d5b489`. G4 GUI is N/A.

Note on SHAs: the ledger commit that records this phase changes only `FINAL_AUDIT_PROGRESS.md`. The source tree is identical to `7d5b489`; check with `git diff --stat 7d5b489 HEAD`.

## Phase J — CodeRabbit findings on 7d5b489, fixes, and final-head gates on c6fc956 (release still blocked)

Commits: `7d5b489` (Phase I source) → `6102643` (Phase I ledger, docs only) → `c4fb22f` (CodeRabbit fixes) → `c6fc956` (CI fix for the closed-stdout test). This phase's ledger commit changes only `FINAL_AUDIT_PROGRESS.md`, `FAILURE_LEDGER.md`, `CHANGELOG.md`, and the audit document's action items; `git diff --stat c6fc956 HEAD` shows which.

**CodeRabbit review on 7d5b489 (obtained, 14:37Z, 4 actionable + 1 outside-diff comments, all checked against the code):**
- F-11 oversized input line dropped without marking the position invalid (valid, LOW). Fixed in `src/uci.rs`: a dropped line sets `position_invalid`; a later valid `position` clears it. Test `oversized_position_line_does_not_leave_the_old_position_in_use` fails on the `7d5b489` source and passes now.
- T-01 ponder test asserted an exact count, but the search is uncapped until `ponderhit` is processed (valid, timing-dependent). The test now asserts termination and a monotonic node count. Exact caps are asserted in the non-ponder tests.
- T-02 closed-stdout test read the handshake without a deadline and had no kill-on-failure (valid). It now uses the bounded `Engine` harness; `Engine::drop` kills the child.
- D-01 audit document's action items named the superseded head `c64b743` (valid, Major). Updated to refer to the final release commit; the historical gate table is unchanged.
- The Phase H "Note on SHAs" claimed current HEAD was source-identical to `8370bed` (valid). Corrected.

**CI failure on c4fb22f (CI-1):** `Tests (release)` failed on ubuntu-latest (exit 101) and windows-latest (exit 1); msrv, the Windows artifact job, and anchor-verify passed. Logs could not be downloaded (results host EOF) and a rerun was refused (HTTP 403). Cause, inferred from the code and not reproduced: the rewritten closed-stdout test sent three `isready` lines after closing the reader. One read can drain all three `readyok` lines, leaving the engine with nothing to write after the close, so it waits on stdin and never exits. Fix in `c6fc956`: keep sending `isready` until the engine exits. Evidence: 30/30 isolated runs of the test pass; 12 and 10 runs of the protocol suite pass (idle and under CPU load); the full release suite passes; CI on `c6fc956` passes. The CI-1 cause is inferred, and CI passing on `c6fc956` is the only evidence that the fix works.

**Final-head local gates on `c6fc956`** (`/tmp/gates/run_final.sh`, `summary.txt` shows `commit c6fc956…` and `dirty_files 0`; every step rc=0 through DONE): fmt; clippy release and debug (0 warnings); `cargo build --release --locked`; `cargo test --release --locked` (22, 3, 39, 11, 13, 11 passed); `cargo test --locked`; the `scripts/test_*.py` suites (rating_estimator: 65 checks passed, 0 failed; the `FAIL null control` lines are its negative-control fixtures); verify_opening_subsets; power_analysis; bench `849a85bf7e8e1eba` (2,311,407 nodes); perft 3 = 8902; uci_bestmove_smoke; uci_protocol_probe; uci_malformed_probe (37/37); selfplay; fullgame_en_passant (PASS); resource_probe; fuzz_uci_grammar seeds 9 and 21 (0 failures); fuzz_legal_differential seeds 1 and 7 (RESULT PASS).

**CI on `c6fc956`:** run 44757861918 (CI) success: ubuntu-latest, windows-latest, msrv (rust 1.80), windows x64 release artifact all success. Run 44757861893 (anchor-verify) success.

**Windows artifact `flawless-windows-x64-c6fc956e74c28df82682c67eaa76b27a31183ca0`** (artifact 14640410894, 206,468 bytes, not expired; run 44757861918): `gh run download` failed on the first attempt and on the single allowed retry (EOF from the blob host). **G3 NOT VERIFIED** for `c6fc956`. The manifest and SHA256 were not inspected.

**CodeRabbit on `c6fc956`:** review requested on PR #4 (comment at 14:57Z-ish, head stated in the comment). Result: "Review rate limited" (check run `completed neutral`, title "Review rate limited"; steps skipped). No review for `c4fb22f` or `c6fc956` exists. **G2 NOT OBTAINED** for the final head. The earlier review on `7d5b489` is real and its findings are addressed above; it is not a review of the final head.

**Gate summary for the final head `c6fc956`:** G1 CI PASS. G2 CodeRabbit NOT OBTAINED (rate-limited). G3 Windows artifact NOT VERIFIED (EOF). G4 GUI N/A. G5 local gates PASS. G6 MSRV 1.80 PASS in CI.

**Release decision:** NOT RELEASED. PR #4 is NOT merged. No tag `v0.1.0`, no GitHub Release. Open gates: G2 and G3. Next check: when CodeRabbit posts a review with `commit_id` `c6fc956`, triage it; if its findings change source, that is a new SHA and the full gate set and CI run again. The Windows artifact needs a network that can reach the blob host, or the user verifies it directly.

## Phase K — audit stretch to 10:00 UTC+7 (2026-11-21): F-14 evidence, F-18 CI fix, restore recovery

Commits (branch `arena/f668bde4-flawlesschess`, PR #4): `a400e80` (F-16/F-17, pushed earlier; CI failed on Windows clippy)
→ `ffd6b04` (F-18: Unix-only pipe test gated with `cfg(unix)`, pushed; CI success on all four jobs). The docs commit that
adds this section is the final head; its source tree is identical to `ffd6b04` (no `src/`, `tests/`, `scripts/`, or
`Cargo.toml` change, checked by `git diff --stat ffd6b04 HEAD -- src tests scripts Cargo.toml`).

**Sandbox restore (2026-11-21 ~01:56 UTC):** the clone was rebuilt at `c25e65e`; `origin` still held `a400e80`, so no pushed
commit was lost. The unpushed F-18 commit survived as working-tree changes (verified exactly the two files), and was
recommitted. The Rust toolchain (`@toolchain-bin` pins) and the venv (`chess==1.11.2`) were reinstalled. See FAILURE_LEDGER.md.

**CI:** `a400e80` run 44777328791 failed on `windows-latest` at `Clippy (deny warnings)` (job 136430504382): the F-13 test
used a Unix-only pipe binding without a `cfg` gate. Fixed in `ffd6b04` (F-18). Run 44853133810 on `ffd6b04`: success for
`ubuntu-latest`, `windows-latest`, `msrv (rust 1.80)`, and `windows x64 release artifact`. anchor-verify 44853133745: success.

**Local gates on `ffd6b04`** (`/tmp/gates/final-ffd6b04/summary.txt`, `commit ffd6b04…`, `dirty_files 0`): 34 of 34 rows rc=0.
Release tests 107 passed, 0 failed; debug tests 101 passed, 0 failed; clippy release and debug with `-D warnings` clean;
`cargo fmt --check` clean; bench signature `849a85bf7e8e1eba`; `time_budget_probe` 8/8; `uci_extreme_args_probe` 0 failures;
perft random differential seeds 2 and 8: 0 mismatches (seeds 8 and 9 were read earlier: 0 mismatches each); legal
differential seeds 1 and 7: 0 failures; search sweep debug seed 3 and release seed 2: PASS; full-game en passant PASS;
UCI grammar fuzz seeds 9 and 21: 0 failures.

**Findings in this stretch:**
- F-14 (LOW, fixed in `df6417d`): the earlier "not reproduced" note was wrong. Pre-fix build `0d4fda1` gives an empty PV at
  the insufficient-material root (nodes 4). HEAD searches the root (nodes 24-52, PV present). Regression test fails on the
  pre-fix build with "empty PV".
- F-18 (LOW, CI portability, fixed in `ffd6b04`): see CI above.
- F-19 (hardening, not a reproduced defect): lock poisoning recovery in the flush paths. No regression test.
- F-11 mutation check: removing the fix makes its regression test fail (`bestmove b1c3` instead of `0000`). Verified.
- RSS at Hash 1024: 1007 MiB after 29 searches and still rising; not shown to plateau (see FAILURE_LEDGER.md).

**Probes run (scratch, outside the repo unless noted):**
- MultiPV 256 on start position, K v K, and a 17-move position: lines equal the legal-move count (20, 5, 17); exit 0.
- Responsiveness: `isready` during `go infinite` on Kiwipete (Hash 256): `readyok` in under 1 ms; `stop` answered in under 1 ms (5 trials).
- Mate sign: side being mated gets `score mate -1` (probe on `a400e80`, four positions, earlier in this session).
- Codex review on `a400e80` (`src/search.rs:283`, P2): repeats F-09 (`searchmoves` with no legal named move). Kept the documented
  decision (refuse null move, widen to legal moves, announce on stdout). Open design point for the user.

**Gate summary for the final head (source `ffd6b04`):**
G1 CI: PASS (run 44853133810 and anchor-verify 44853133745).
G2 CodeRabbit on final head: see the PR comment for the request result; NOT CLAIMED unless a review with that commit_id is received.
G3 Windows artifact `flawless-windows-x64-ffd6b04dc03bb3d0616941e13bc49b1cb798d36b` (14686132529, 211,374 bytes): NOT VERIFIED (blob EOF on `gh run download` and REST zip).
G4 GUI: N/A (no GUI in the release).
G5 local gates: PASS on `ffd6b04` (34/34).
G6 MSRV 1.80: PASS in CI on `ffd6b04`.

**Release decision: NOT RELEASED.** PR #4 is not merged. No tag `v0.1.0`, no GitHub Release. G3 is not verified, and G2 has no
review on the final head. Both must pass before any release step.

**Open items (not claimed fixed):** Codex P2 `searchmoves` design point (F-09); RSS plateau at Hash 1024 not shown; `go ponder
movetime` clock start (DESIGN_LOG); kilo billing-blocked (not bypassed).

**Addendum (same stretch, 09:12–09:20 UTC+7):** fresh seeds, all PASS with 0 failures (scratch runs of the repo scripts, logs in
`/tmp/audit/k/`): perft random differential seeds 10 and 11 (30 games, depth 3); search sweep release seeds 4 and 5 (50 positions,
depth 4); legal differential seed 11 (40 games); UCI grammar seed 51 (150 sessions). Probes: CRLF line endings accepted
(`uci`, `isready`, `position`, `go depth 3` answered); promotion without a piece letter (`a7a8`) rejected with an info string,
`a7a8q` and `a7a8N` accepted. CI on `ce9f8d4` (docs-only on `ffd6b04`): CI success, anchor-verify success. CodeRabbit review
requested on `ce9f8d4` (comment 7055699579); the trigger was acknowledged, no review yet at this entry.
