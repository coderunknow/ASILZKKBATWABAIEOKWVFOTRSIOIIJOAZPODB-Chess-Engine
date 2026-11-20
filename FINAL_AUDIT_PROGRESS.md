# FINAL_AUDIT_PROGRESS.md — FlawLessChess 0.1.0 release mission ledger

Branch: `arena/f668bde4-flawlesschess` (branched from `c25e65e` of `arena/2d2d30b4-flawlesschess`)
Base PR: #3 (`arena/2d2d30b4-flawlesschess`, OPEN, non-draft as of 2026-11-20, base `main`)
Baseline HEAD at start: `c25e65efc0c6223f58701d529775726db13ebedd` (verified; remote PR head matches)
Toolchain: Rust 1.99.0 installed from npm `@toolchain-bin/*` into `/home/user/.toolchain/sysroot` (`source /home/user/.toolchain/env`)
Baseline: `cargo build --release` OK; `cargo test --release` OK (21 lib + 11 movetime + 11 uci_smoke + correctness/clock per log).

Status legend: NOT STARTED / IN PROGRESS / BLOCKED / COMPLETED / VERIFIED

## Phase A — reconnaissance & audit

| ID | Task | Status | Findings / evidence | Next action |
|---|---|---|---|---|
| A1 | Branch/remote/PR state | VERIFIED | Branch == c25e65e == PR #3 head; PR #3 +10,609/-40 over main; 43 files. CodeRabbit (9336913 & c25e65e), Codex (c25e65e), Kilo ACTION_REQUIRED (billing) | — |
| A2 | Toolchain install | VERIFIED | rustc/cargo 1.99.0, clippy 0.1.99, rustfmt 1.10.0 | — |
| A3 | Read src/search.rs, uci.rs, position.rs, movegen.rs, types.rs, tt.rs, attack.rs | COMPLETED | see suspect list S-* below | probe each suspect |
| A4 | Read src/eval.rs, src/main.rs | IN PROGRESS | main.rs CLI reviewed; eval.rs skimmed (constants fine) | eval symmetry probe (Phase E) |
| A5 | Read tests/*, scripts/windows_artifact.py, CI workflows | NOT STARTED | | |

## Suspect list (from audit, to be reproduced in Phase B)

- S-01 `setoption name Hash value 4096` is accepted, but `TranspositionTable::resize` clamps to 2^27 entries = 1 GiB. Effective size silently capped (tt.rs:98).
- S-02 `clock_limits`: `usable / mtg + inc / 2` can overflow u64 for huge wtime + increment (release wraps silently) (uci.rs:608).
- S-03 `go wtime N` without `btime` (or vice versa) → no clock limit, search runs to depth 64 (uci.rs:305/308).
- S-04 UCI stdin loop terminates on the first non-UTF-8 line (`while let Some(Ok(line))`) — engine silently exits (uci.rs:92).
- S-05 `MoveList::push` bound is only `debug_assert!` (types.rs:228); pseudo-legal move count >256 would panic in release via index OOB → reproduce with dense FEN.
- S-06 `searchmoves` with only illegal moves — code falls back to all legal moves (search.rs:249). Regression test exists. VERIFY at process level.
- S-07 `go ponder nodes N` node cap after ponderhit (uci.rs:456). VERIFY at process level.
- S-08 `go nodes N` checked only every 1024 nodes → overshoot up to ~1023 nodes (search.rs:133). LOW.
- S-09 `is_repetition` scans whole history per node (position.rs:746). LOW perf.
- S-10 Aspiration loop termination: relies on invariant score > -INF. VERIFY (LOW).
- S-11 `Threads` option advertised min 1 max 1; non-1 values ignored with stderr note. Documentation must be explicit (LOW).
- S-12 FEN accepts castling rights without rook/king (movegen guards it; verify no corruption).
- S-13 `resize` / `setoption Hash` allocation peak (old+new table both live) and `ucinewgame` clears full table each call (perf, LOW).

## Phase B/C — reproduced findings and fixes (batch 1)

| Finding | Severity | Evidence | Root cause | Fix | Verification |
|---|---|---|---|---|---|
| F-01 (S-05) Legal-looking FEN crashes engine: `position fen KQQQQQBk/Q5RB/Q6Q/Q6Q/Q6Q/Q6Q/Q1QQ3Q/QR3QQQ w - - 0 1` + `go` → panic, exit 101 | HIGH | Reproduced on c25e65e via `flawless uci` (main-thread generate_legal) and `moves` batch | FEN accepted >16 pieces/side; pseudo-legal moves 256+ overflow fixed `MoveList` (types.rs push used debug_assert only) | FEN material check (≤16 pieces/side, ≤8 pawns, promoted ≤ missing pawns, `position.rs::material_is_reachable`); MOVE_LIST_CAPACITY=512 with bound 335 documented; push uses hard assert | tests `impossible_material_fen_is_rejected_without_crashing`, correctness `fen_rejects_material…`, `move_list_capacity…`; perft refs unchanged |
| F-02 (S-04) Non-UTF-8 input byte ends the UCI session (engine exits silently) | HIGH | `printf '\xff\xfe x\nisready\n' | flawless` → no readyok, exit | `lines()` returns Err → `while let Some(Ok)` ends loop | byte-level bounded reader `read_bounded_line`; lossy UTF-8; oversized lines (>64 KiB) dropped with info string | `non_utf8_input_line_does_not_end_the_session`, `oversized_input_line_is_dropped_and_session_continues`, unit tests |
| F-03 (S-03) `go wtime N` alone (or `btime` alone) has NO limit: search runs to depth 64 until stop/EOF | HIGH | `printf 'go wtime 2000'` searched to depth 13 and beyond; bestmove only at EOF | clock_limits only when both clocks present; else unlimited | side-to-move clock governs; opponent clock defaults to it; unlimited only if side-to-move clock absent (bare go semantics) | `single_side_clock_bounds_the_search` (0.1 s); `clock_limits_saturate…` |
| F-04 (S-01) Hash 4096 advertised/accepted but TT silently capped at 1 GiB (2^27 entries) | MEDIUM | probe: TT::new(4096) RSS 1,050,324 kB == TT::new(1024) | clamp(…, 1<<27) in tt.rs | advertise & accept Hash 1..=1024 (`MAX_HASH_MB`), reject larger with info string on stdout | `hash_limit_is_advertised_and_enforced` |
| F-05 (S-02) clock_limits `usable/mtg + inc/2` u64 overflow (wraps in release) | LOW | arithmetic audit; reachable only with ~u64::MAX clocks + large increment | unchecked add | saturating_div/saturating_add | unit test `clock_limits_saturate_instead_of_wrapping` |
| F-06 setoption rejection messages went to stderr only (invisible to GUIs) | LOW | `setoption Hash 4096` printed nothing on stdout | eprintln! | `info string` on stdout | covered by F-04 test |
| F-07 Search worker thread used default 2 MiB stack while MoveList grew to 4 KiB per frame | LOW (defence) | design review | — | 16 MiB worker stack (`SEARCH_STACK_BYTES`) | build + tests |

Verified unchanged: `bench` signature `141943aa23b3fc68` and node count 2,530,885 identical to base c25e65e; NPS within noise (≈360–414k on this 2-vCPU box for both builds).
Verified: perft CPW references (startpos d1–d4, Kiwipete d1–d3, pos3 d1–d4, pos4 d1–d3, pos5 d1–d3, pos6 d1–d3) — all match; now permanent tests in tests/correctness.rs.
Verified (process level, unchanged behaviour): illegal-only `searchmoves` returns a legal move; `go ponder nodes N` honours the node cap after ponderhit.
Local gates after batch 1: `cargo fmt --check` OK; `cargo clippy --all-targets -- -D warnings` OK; `cargo test --release` all green (22 lib, 3 clock, 30 correctness, 11 movetime, 11 uci_smoke, 6 protocol_regressions).
