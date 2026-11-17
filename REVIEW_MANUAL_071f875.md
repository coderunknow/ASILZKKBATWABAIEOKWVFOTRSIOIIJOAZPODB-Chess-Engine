# REVIEW_MANUAL_071f875.md — disposition of the manual review (code head 071f875)

Companion to REVIEW_MANUAL_03d2066.md (append-only; its statuses are NOT edited). This file records what
happened to each of the 15 findings, verified at code head 071f875. Verification rule: a finding is
"fixed" only with a before/after reproduction; a finding that does not reproduce is recorded as
"not reproduced" with the evidence, not silently closed.

| # | Severity (original) | Disposition | Commit | Evidence |
|---|---|---|---|---|
| R-01 | HIGH | NOT REPRODUCED (false positive) | — | The LMR re-search line already negates the child score (`s = -self.search(...)`), unchanged since 387a13ed. |
| R-02 | HIGH | FIXED | 5980d53 | Root repetition is searched (`bestmove` from search, not first legal move). Fifty-move claimable: node searched, value clamped to >= DRAW. Mate-in-1 at halfmove 100 now `mate 1`. 3 regression tests, 2 fail on pre-fix code. |
| R-03 | HIGH (perf) | FIXED | 81ad551 | Exact single-capture king-safety test replaces clone + full legal probe. Equivalence test over >1,000 ep positions (incl. pins): identical. Bench signature unchanged. |
| R-04 | MEDIUM | NOT REPRODUCED | — | Index uses bits 0..21 and the check uses bits 48..63 (disjoint). Zobrist keys are uniform, so low bits do not cluster. |
| R-05 | MEDIUM | NOT REPRODUCED | 071f875 (tests) | MATE_SCORE 30000 + MAX_PLY 128 = 30128 < i16::MAX; no clamp is reachable. Round-trip regression tests added. |
| R-06 | MEDIUM | NOT REPRODUCED (spec-compliant) | — | UCI requires `readyok` to be answered during a search without stopping it. The reproduction sent `quit` right after `go`, which stops the search. |
| R-07 | MEDIUM | FIXED | 1ec9eeb | `position` is all-or-nothing; rejected commands make the next `go` answer `bestmove 0000`. Integration test added. |
| R-08 | MEDIUM | FIXED (predictive) | b39df4e | Predicts next-iteration time as 3x the last one. Clock matrix: elapsed/soft from up to 1.7x to 0.5x-1.5x. Residual overrun bounded by the hard limit. Not unit-tested (wall-clock). |
| R-09 | LOW | ACCEPTED (unchanged) | — | As in the original review. |
| R-10 | LOW | FIXED | 81ad551 | Magic readiness cached at build time. |
| R-11 | LOW | ACCEPTED (unchanged) | — | As in the original review. |
| R-12 | MEDIUM | FIXED | 5980d53 | TT score cutoffs are skipped at claimable fifty-move nodes; mate precedence holds (see R-02). |
| R-13 | MEDIUM | FIXED (engine side) | 5980d53 | Harness unchanged on purpose (sends the full move list); the engine's root-repetition handling was the defect. |
| R-14 | LOW | ACCEPTED (unchanged) | — | As in the original review. |
| R-15 | LOW | ACCEPTED (unchanged) | — | As in the original review. |

## Corrections to the original review

- R-02(b) said the position with halfmove 100 should show a winning queen score. That expectation was wrong.
  Under FIDE 9.2/9.3 the side to move may claim the fifty-move draw, and once the clock is >= 100 either side
  can claim at its turn, so the claim-aware value is max(DRAW, search) = 0. The fixed engine returns 0 there.
  The mate-precedence part of R-02(b) is real and is fixed.
- R-06 reproduction method was invalid (see above).

## Re-run gates at 071f875

- `cargo fmt --check`: clean. `cargo clippy --all-targets -- -D warnings`: clean.
- `cargo test --release`: 45 passed at 1ec9eeb; the R-05 tests add 2 more at 071f875.
- Perft: 22 CPW reference counts exact (startpos d1-d5, Kiwipete d1-d4, positions 3-5). Full 27-entry matrix not re-run here.
- DIFTEST: default 300 games PASSED (2,321 perft-checked positions, 0 mismatches; python-chess 1.11.2).
- Bench: signature `141943aa23b3fc68`, unchanged from the baseline.
- UCI smoke: 5/5.
- MSRV 1.80: NOT VERIFIED (no 1.80 toolchain available here). Open blocker.
