# MISSION_CHECKPOINT.md — authoritative resume document

Facts here are verified state, not plans. Historical records: AGENTS_LOG.md, DESIGN_LOG.md, FAILURE_LEDGER.md (append-only).

## Status

- Mission status: **ACTIVE / INCOMPLETE**
- Current milestone: **V1 (strictly above 2,000 Elo)**. V2 (>3,000) not started.
- Current work item: the Phase C audit of PR #2 found and fixed a fourth defect (the
  mate-score band was narrower than the reachable mate range, so the transposition
  table reported the wrong mate distance for long mates and the UCI layer printed
  them as centipawn scores), and the registered EVAL-3 screening campaign confirmed
  that the audited tree is about **+197 Elo** (95% CI [+117, +285]) stronger than the
  pre-audit tree. The next items are to freeze the exact candidate binary, obtain the
  exact-SHA CodeRabbit review and the owner's Windows acceptance, and then run the
  candidate controls, the candidate-specific power assessment and Batch A/B.

## Identity

- PR: PR #1 (https://github.com/coderunknow/FlawLessChess/pull/1) was **merged** on
  2026-11-14 by the repository owner; it is closed and is not the vehicle for this work.
  A new **Draft** PR is required for the 2026-11-18 branch and is not yet open.
- PR #2 (https://github.com/coderunknow/FlawLessChess/pull/2) is **open**, **draft**,
  mergeable, base `main` @ `5e36b06`, head `6755cc1` (API-verified 2026-11-19).
- Branch: `arena/8259ce1c-flawlesschess`
- Base: `main` @ `5e36b06a7b0d7417d57205e52010ea98529b2a4f` (re-verified against the
  remote on 2026-11-18)
- Local head at this checkpoint: `6755cc1` (the audit fixes `708d53c`, `61dd642`,
  `018e920`, the workflow re-pin `50ec354`, the mate-band fix `32ad8ab`, and the EVAL-3
  registration, result and documentation `96e7ca8`, `16f6826`, `521a605`, `6755cc1`).
- **The Windows artifact has not been produced and the owner has not tested a binary:
  `OWNER_TEST_PENDING` remains in force.**

## 2026-11-18 work item (supersedes the 2026-11-17 item above)

- Current work item: finish the EVAL-1 ablation campaign, apply the registered
  decision rules per evaluation feature, push the resulting series, open the Draft PR,
  run CI at the exact head SHA, and produce the Windows x86-64 delivery ZIP.
- STRENGTH-1 screening is COMPLETE and its result is recorded:
  SPEED-1 **KEPT** (+89 Elo, CI [+13, +168]); HIST-1 **INCONCLUSIVE**
  (−66 Elo, CI [−142, +9]).
- EVAL-1 (evaluation ablation, seven matched pairs against one control) is
  **RUNNING**; the decision rules were registered before dispatch.

## 2026-11-18 frozen identities

- BASE binary (`5e36b06`): SHA-256 `a5d9aa980b624ce958b3fc399513a5029c99187f16d673a5490a615d184eff99`;
  bench signature `141943aa23b3fc68`; 2,530,885 nodes.
- SPEED-1 binary (`cd17da0`): SHA-256 `d99756b13b640b8142eff2fa5c1b2dbfd39caf0dfc17ea01845dbf0193ed18c3`;
  identical signature and node count to BASE.
- HIST-1 binary: SHA-256 `9302fb61810adc10f4833a0278d860089467de2a88e37f0a4b140ba038f606a6`;
  signature `8370f143c3b76fb4`; 2,697,573 nodes.
- EVAL-1 control (EVAL-NONE, all flags off): SHA-256
  `1fa874d230537b311b12b730417e2faaae033640663a7d8b1bec9a3d216a5a0c`; reproduces the
  HIST-1 signature and node count exactly (control validity verified before dispatch).
- EVAL-1 candidate (EVAL-ALL): SHA-256
  `7fddfc05e3d60d681dcdf1422c1ba5e79a2e56a52fe596b3fb82ceffbbab3dc3`;
  signature `03e46bba31f35591`; 3,445,466 nodes.

## Workflow state (API-verified 2026-11-17)

| Run | Workflow | Commit | Purpose | State |
|---|---|---|---|---|
| 43820392119 | rating-run | 8e21435 (dispatch rev 13) | CTRL-2-R, `flawless-self-r`, 120 shards × 2 games, seed 20261125, engine 9663697d… | completed success: resolver + 120/120 shard jobs succeeded; aggregate-and-commit-evidence SKIPPED |
| 43820645420 | rating-run | 9890407 (dispatch rev 14) | SCREEN-3 vs `akimbo-0.1.1`, 60 shards × 2 games, seed 20261126, TC 40/15 | completed success: resolver + 60/60 shard jobs succeeded; aggregate-and-commit-evidence SKIPPED |

Both runs have shard artifacts, but neither produced a canonical committed aggregate. Do not treat the artifacts as gate evidence until strict aggregation, identity validation, and byte-level verification are completed. Neither run is in progress and neither was cancelled.

## Frozen identities

- ENGINE-1 candidate (CTRL-2-R, SCREEN-2R, SCREEN-3, and now Batch A/B per BATCH-HASH): `9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428`
- Pre-fix candidate (CTRL-2, SCREEN-1/2, historical only): `fd75726dd3166640ddec75d94c416320b47c83e8d14bfa6309aed398d55b8e1d`
- Batch A suite `benches/rating-openings-batchA.txt`: `2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96`
- Batch B suite `benches/rating-openings-batchB.txt`: `744a3981cc312a676ba259962309858b7d2fc645094bf2dccf5391e77f2f9dd4`
- RATING-100 Batch A suite `benches/rating-openings-100-batchA.txt`: `abf1627495d3ad9c42240f076921e2453e5e30cac42782856ea5f0673ca60239`
- RATING-100 Batch B suite `benches/rating-openings-100-batchB.txt`: `f7414154ce2fe38faeac15dadc9f9c250245a54e908422e37451d089ff352219`
- RATING-100 power report `benches/rating-100-power-assessment.json`: `731e9937d4355341d384e6b4f97017f9e611f73c` (BLOCKED; not dispatchable).
- Anchor pools: `benches/anchor-pool.json` (V1), `benches/anchor-pool-3000.json` (V2).

## Verified in this session (2026-11-17)

- SCREEN-2R selection estimates reproduced from committed raw evidence: topple-0.1.1 2176.8, topple-0.2.1 2236.4, mean 2206.6. Selection-only, not an absolute Flawless rating.
- SCREEN-3 mechanical anchor choice remains `akimbo-0.1.1`, but its completed shard jobs were not aggregated because the evidence job was skipped. Do not use it to finalize the anchor set yet.
- CTRL-2-R shard jobs all succeeded, but its aggregation job was skipped. The registered self-match CI has not been evaluated.
- The RATING-100 suites are exact deterministic 50-row subsets of original Batch A/B, disjoint and with byte hashes fixed in PREREGISTRATION.md. Proposed arithmetic: 600 counted games for 3 anchors × 2 batches × 100, vs the historical 12,240.
- Prospective power status is BLOCKED: the two available selected-subset anchors have cluster SD 0.26578 / 0.29662 and correlation 0.15888; the third-anchor cluster distribution and disjoint Batch-B cluster variance are not measured. At a 2,100 Elo true-rating alternative, sensitivity power for all three strict lower-bound decisions is only 63–77% without variance inflation and drops to 22–31% at 1.5× SD / 8.7–12.4% at 2× SD.
- Exact schedule-index recovery is implemented in the candidate code so an interrupted AB/BA pair can resume only the missing leg without duplicating a counted index.
- Current source changes are not yet committed or CI-tested. No confirmatory dispatch, gate plan, merge, tag or release has occurred.

## Pending work (priority order)

1. Complete source review and tests for RATING-100 suites, power report, exact schedule-index recovery, workflow evidence capture and SEE ordering-only search change. Push with expected-head guard; run full CI on exact new SHA.
2. Request fresh CodeRabbit review at exact new SHA; verify every finding against current code, fix valid issues, rerun CI after repairs.
3. Recover CTRL-2-R and SCREEN-3 shard artifacts; run strict aggregation; verify every manifest and hash; commit canonical raw evidence; only then evaluate self-match CI and third-anchor screening estimate. Do not claim PASS based on shard job success alone.
4. Reapply the unchanged anchor-selection rule only after SCREEN-3 raw evidence is committed and verified. Build a gate plan only when the selected anchor set and all controls are valid.
5. Keep RATING-100 confirmatory dispatch BLOCKED until a reviewed, evidence-backed prospective power PASS covers the actual engine hash, all three anchors and the disjoint A/B suites. If it remains underpowered, continue design research without weakening CI/threshold/TC/controls.
6. After all conditions are met, update MERGE_READINESS and ask the owner whether the mission is complete. PR remains draft; never merge.

## Projection (NOT evidence)

- The 100-game amendment reduces scheduled counted games by 95.0980% (12,240 → 600 for three anchors and two batches) if the same three-anchor design is ultimately authorized. This is not a measured runtime or throughput projection.
- The existing pilot's 29.43/29.53 min/game figures are historical exploratory estimates, not a guarantee for the changed engine or runner configuration.

## Documentation inconsistencies (recorded, not auto-fixed)

- `AGENTS.md` names the repository `coderunknow/Flawless-Chess-Engine`; GitHub reports `coderunknow/FlawLessChess`. The owner declined repository-name changes.
- Dispatch rev 14 description carries pre-fix SCREEN-2R numbers (see above).
- STATUS.md header and the MERGE_READINESS null-control and screening items were stale and were corrected in the reconciliation commit. No evidence was changed.
- Node.js 20 deprecation warnings on `actions/checkout@v4` and `actions/upload-artifact@v4`. Non-blocking now.

## External blockers

- Runner capacity: SCREEN-3 resolve waited about 5 h. Queue latency is the throughput constraint. Do not launch duplicate runs.
- CodeRabbit status not yet checked in this session.
- GitHub token expires 2026-11-22 05:35 UTC. Renewal requires the owner. Never write the token into the repo, logs, or memory.

## Decisions still required from the owner

- None blocking.

## Exact resume procedure

1. Read AGENTS.md, this file, and the newest segments of AGENTS_LOG.md and DESIGN_LOG.md.
2. `git fetch origin`, checkout `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`, reconcile local and remote HEAD.
3. Query runs: `GET /repos/coderunknow/FlawLessChess/actions/runs/43820392119/jobs` and `.../43820645420/jobs` (paginate with per_page=100).
4. The previously in-progress CTRL-2-R and SCREEN-3 runs are now terminal; their evidence jobs were skipped. Recover and verify their existing shard artifacts before deriving any screening/control statistic. Do not duplicate or cancel completed runs.
5. Authentication: the owner supplies the token for the session. Use a credential helper that reads it at call time. Never persist it in `.git/config`, the repo, logs, or memory.

## Latest validation checkpoint — 2026-11-17 10:07Z

- Implementation commit `7d368cd74e8d559ab0782c88f3fbaeb05fcd12a0` was pushed and verified as PR #1 head (open, draft, unmerged).
- CI run `44061648187`: Rust 1.80 MSRV PASS; Linux and Windows stopped at rustfmt in SEE helper layout before tests. The exact rustfmt diffs are fixed in the follow-up source blob.
- Anchor verification run `44061648150`: binary built, measured bench signature `141943aa23b3fc68`, then failed because the verifier still expected historical `fc907eba40b7869f`. The expected signature is corrected in the follow-up; binary SHA-256 remains pending successful verification.
- Rating-gate run `44061648153`: FAILED CLOSED because no gate plan or canonical rating evidence exists; this is not a rating estimate.
- Rating-run run `44061648184`: resolver success, shard matrix and evidence job skipped because `benches/dispatch.json` was untouched; no new tournament games ran.
- No confirmatory dispatch, merge, tag or release has occurred. RATING-100 remains BLOCKED.

## Latest verified checkpoint — 2026-11-17 10:31Z

- Remote branch / PR #1 head: fe6d34067e776ca64e676617c2102966675b4744; PR open, draft, unmerged. This is the commit before the suite-hash correction being prepared in this session.
- 44062359630 (CI) failed on both Ubuntu and Windows only at scripts/verify_opening_subsets.py because the initial reduced-suite generation helper used an incomplete SHA-256 constant table. Both jobs passed Rust fmt, clippy and Rust tests (groups 12/3/21/4); Python tests passed 111/111, 65/65, 7/7, 5/5 and merge self-test. No correct CI pass may be claimed until the fixed suites pass the verifier at the new exact branch HEAD.
- Anchor verification 44062359732 succeeded for the PR merge tree 4cdf57c5e0d898e9accc6ec9d51ef00d82290575: depth-10 bench signature 141943aa23b3fc68, binary SHA-256 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7. This is not yet bound to a source branch SHA; verify the PR merge tree and branch tree have identical compiler inputs or rerun anchor verification after the correction commit.
- The corrected opening-suite byte hashes prepared for the next commit are Batch A 5abdcdbddec0f22d7e6eff8974ee402363c8c3df318b8110d7204adf69f5c1df and Batch B ccb4901742eca25b0b10f1a3c9fdfc17b2967a1939c2d7e466c2c5495b6d4253. The selector is 50 lowest standard SHA-256 digests with original suite order retained; 50 unique openings per batch, no overlap.
- 44062359728 rating-gate failed closed because no gate plan/canonical evidence exists. 44062359655 rating-run resolver succeeded, but its shard and evidence jobs were skipped because dispatch.json was unchanged. No confirmatory games ran.
- SCREEN-3 (43820645420) and CTRL-2-R (43820392119) remain terminal with all shard jobs successful but the evidence jobs skipped. Their artifacts are not canonical committed evidence and have not been promoted to rating/control results.
- RATING-100 power remains BLOCKED. No confirmatory dispatch, merge, tag or release is authorized; PR remains Draft.


## Latest verified checkpoint — 2026-11-17 10:37Z

- PR #1 / arena branch HEAD at the start of the engine-identity guard change: 5b63e273d77cfb097f0ad73bc28dda05cc19adad (open, draft, unmerged). All commits were pushed through fast-forward expected-HEAD updates.
- CI run 44066217195 on that exact commit: overall SUCCESS. Ubuntu, Windows and Rust 1.80 all succeeded. Python regression suites: match 111/111, estimator 65/65, reduced-sample 7/7, dispatch recovery 5/5; merge self-test all cases; selector verifier reports 50/50 unique openings, no overlap, expected SHA values; power smoke produced 36 scenarios with BLOCKED status.
- Anchor verification 44066217113: 13/13 jobs succeeded. Verify-flawless built merge commit 7434e948357eda05f9435e430c37da082f202741; that commit's second parent is 5b63e273d77cfb097f0ad73bc28dda05cc19adad and its tree exactly matches the source branch tree 75bc5633e1466d5abf1f4c7d5999bc4a3915e193. Verified binary SHA-256 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7; bench signature 141943aa23b3fc68.
- The power report is engine-pinned to SCREEN-2 / ENGINE-1 binary SHA 9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428. A new guard is being added so the power generator verifies the original screening manifests/raw hashes and the dispatch tool/workflow reject any power report whose engine SHA differs from the requested binary.
- ENGINE-2 is identified by binary SHA 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7, but its own screening and candidate-specific controls are not yet run. The RATING-100 campaign remains BLOCKED pending third-anchor and Batch-B variance evidence, plus a reviewed power PASS. No confirmatory games, merge, tag or release.

## 2026-11-17 — latest checkpoint after provenance-guard CI

- Branch / PR head at checkpoint: 29b627ed49aecbf9e2746e45a39c4d6a6342302b; PR open, draft, unmerged.
- Commit 29b627e added the engine-SHA provenance guard: screen2 manifest and raw-game verification in power_analysis.py; dispatcher CLI and rating-run workflow compare the report SHA against the requested engine binary. Power file currently stays BLOCKED and is sourced from ENGINE-1 hash 9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428, not ENGINE-2.
- CI 44067364552: MSRV passed; Linux failed in the new test_power_analysis suite (3/4) because a test expected the later A/B hash mismatch message while the guard correctly rejected the unregistered engine hash at the earlier manifest allowlist. Existing match/estimator/reduced-sample/dispatch-recovery tests passed; recovery tests 7/7. Correct the expectation and rerun full CI.
- Anchor verification 44067364568 passed 13/13, reproduced bench signature 141943aa23b3fc68 and binary SHA-256 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7. rating-run resolver succeeded and skipped shard/evidence jobs; rating-gate failed closed because no gate plan/evidence is available.
- RATING-100 remains BLOCKED. No confirmatory games were launched, no candidate-specific ENGINE-2 screen/control has been run, and the PR stays Draft.

## Latest checkpoint — 2026-11-17 10:47Z

- Branch / PR head at checkpoint: c564c5ccc690ec61ea87898c196e0a1f614f1f64; PR open, Draft, unmerged.
- CI 44067826990: Rust/MSRV passed; Linux passed; Windows failed only at the prospective-power smoke because Windows checked out two raw SCREEN-2 games.jsonl files with CRLF, whereas committed manifest hashes were computed on Linux LF bytes. This is a line-ending portability issue, not changed game content. A fix is prepared: canonicalize only JSONL line endings for hashing, add LF attributes to the exact evidence files, and regression-test CRLF compatibility plus record tampering.
- Anchor verification 44067826881 succeeded 13/13; binary SHA-256 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7; bench signature 141943aa23b3fc68.
- rating-run resolver succeeded with shards/evidence skipped. rating-gate failed closed for absent gate plan/evidence. No games dispatched.
- RATING-100 remains BLOCKED and ENGINE-2 lacks its own screening/controls.

## Latest verified checkpoint — 2026-11-17 11:55Z (this session, segment 25 start)

- Remote PR #1 / arena branch head at session start: `03d2066b3ae2cf33c6246280bd4c5c5ced86985d`
  (API-verified: open, **draft**, unmerged, mergeable=true, 144 commits, 133 changed files).
- CTRL-2-R run **43820392119** (dispatch rev 13) and SCREEN-3 run **43820645420** (dispatch rev 14)
  are BOTH TERMINAL (`completed success`, resolver + all shard jobs green, aggregate-and-commit-evidence
  SKIPPED). Nothing in progress on those controls; no conflicting dispatch permitted or needed.
- Exact-head CI at `03d2066`: run **44068565273 = SUCCESS** (Ubuntu, Windows, Rust 1.80). rating-gate
  run **44068565038 = FAILED CLOSED** (no gate plan/canonical evidence — expected, not a code defect).
  anchor-verify 44068565067 and evidence-bridge 44068565055 succeeded. No new tournament games ran.
- Sandbox toolchain rebuilt from static.rust-lang.org (crates.io not needed; zero-dependency crate):
  rustc/cargo/rustfmt 1.99.0 + clippy 0.1.99 + gcc/g++ 12.2.0, python venv with python-chess 1.11.2.
  Baseline re-measured at head: bench 2,530,885 nodes / 8.76 s = 288,912 nps, signature
  `141943aa23b3fc68`; `cargo test --release` 40/40; fmt + clippy `-D warnings` clean.
- Repo "About" description FIXED via API (PATCH 200, verified on the repo page):
  "Flawless: an original, from-scratch Rust chess engine (Apache-2.0). Not a Stockfish derivative."
  README/LICENSE/Cargo.toml already describe the engine as original; no Stockfish-based wording found
  (historical evidence keeps old identifiers per ADR-0002, untouched).
- Manual review at `03d2066` recorded in `REVIEW_MANUAL_03d2066.md`: 15 findings (3 HIGH, 7 MEDIUM,
  5 LOW; 3 LOW accepted with rationale). Each HIGH/MEDIUM finding is reproduced against the head binary.
- Local opponent set for PRELIMINARY internal estimates only (never gate evidence): SF19-lite WASM
  (hashes re-verified identical to BENCHMARKING.md: js ccb130d7…, wasm ee4f115b…), plus from-source
  MIT anchors Wowl 1.3.7 (sha256 cd6a8c76…) and Topple 0.2.1 (sha256 b131ed7a…) built here with
  g++ 12.2.0. These local builds are NOT the pinned/verified gate binaries; they are used only for
  internal trend/estimate purposes and labelled as such everywhere.
- Batch A/B confirmatory runs are OUT OF SCOPE this round: no gate plan is created, no dispatch.json
  change, no >2,000 gate claim. Budget for this round: experiments capped at 40-120 paired games per
  change (fixed movetime / fixed-depth harness), no open-ended matches, no confirmatory shards.

## Segment 26 — manual-review fixes at `3ebf617` (session of 2026-11-17)

- Toolchain reproduced from npm `@toolchain-bin/*` per docs/ENVIRONMENT.md: rustc/cargo 1.99.0, rustfmt 1.10.0, clippy 0.1.99. Engine has zero external dependencies (offline build).
- Baseline at `3ebf617`: fmt clean, clippy `-D warnings` clean, `cargo test --release` 40/40 green, bench signature `141943aa23b3fc68`, 2,530,885 nodes (depth 10, 12 positions).
- R-01 (LMR re-search sign): NOT REPRODUCED. The re-search line already negates (`s = -self.search(...)`) since commit 387a13ed. No code change; see REVIEW_MANUAL_3ebf617.md.
- R-02 + R-12 (draw rules, mate precedence, TT probe before terminal): FIXED. Repetition is a draw only at ply > 0, so the root is always searched. Fifty-move is a claimable draw: the node is searched, its value is clamped to >= DRAW, TT score cutoffs and pruning are skipped there. Quiesce uses the same rule via a wrapper. Three regression tests added (`search::draw_rule_tests`); two fail on the pre-fix code.
- Bench after the fix: signature unchanged (`141943aa23b3fc68`), because no bench position reaches these draw paths. Gates after the fix: fmt clean, clippy clean, 43/43 tests green.
- Reproduction note: UCI tests must send `quit` only after `bestmove`; piping `quit` right after `go` stops the search. This invalidates the R-06 reproduction in the review.

- R-03 (ep legality probe cloned the position and history and generated all legal moves per make_move): FIXED. The probe now tests king safety for the single en-passant capture on the resulting occupancy. Equivalence test `position::ep_legality_tests` compares it with the old full probe over all positions reachable to depth 3 from 6 FENs (>1,000 ep positions, pin cases included): identical.
- R-10 (magic_ready scanned 64 entries on every slider lookup): FIXED (readiness cached at build time).
- Bench after R-03/R-10: signature unchanged (`141943aa23b3fc68`, 2,530,885 nodes). Perft spot checks match CPW: startpos d4 197,281; Kiwipete d3 97,862; pos4 d3 9,467. Gates: fmt clean, clippy clean, 44/44 tests green.
- Throughput (single runs, 1-CPU sandbox, noisy): 243k nps before R-02, 350k nps after R-03/R-10. Not a validated measurement; re-measure on the reference machine.

- R-07 (illegal move in `position` silently truncated the position, then searched it): FIXED. `position` is all-or-nothing; a rejected command keeps the old position out of the search and sets a flag, and the next `go` answers `bestmove 0000` until a valid `position` arrives. Test `uci_smoke::rejected_position_yields_null_bestmove_until_fixed`.
- Gates: fmt clean, clippy clean, 45/45 tests green. Bench signature unchanged (`141943aa23b3fc68`).

- R-08 (soft budget checked only after a completed iteration; measured elapsed up to ~1.7x soft): FIXED with a predictive check. Before starting an iteration the engine estimates its duration as 3x the previous iteration and stops if that would pass the soft budget; completed iterations are always kept. Measured elapsed/soft over a clock matrix (30 s and 60 s clocks, movestogo 40, three positions): before 1.7x (1,209/703 ms, 2,494/1,406 ms, 2,432/1,406 ms); after 0.5x-1.5x (376, 911, 534, 969, 1,042, 1,075 ms; worst case is one iteration whose time grew more than 3x, bounded by the hard limit). Not covered by a unit test because wall-clock tests are flaky; verification is the measurement above.
- Gates: fmt clean, clippy clean, 45/45 tests green. Bench signature unchanged (`141943aa23b3fc68`).

- R-05 (claimed i16 clamp of mate scores at high ply): NOT REPRODUCED as stated. MATE_SCORE (30,000) + MAX_PLY (128) = 30,128 < i16::MAX. Added regression tests `tt::mate_score_range_tests` that pin the invariant and the exact round trip at ply 127.
- Verification run at the head after R-08 (before this commit): CPW perft matrix subset (22 counts across startpos, Kiwipete, positions 3-5) exact; DIFTEST default (300 games) PASSED, 2,321 perft-checked positions, 0 mismatches (python-chess 1.11.2, from index version 1.999 per docs/ENVIRONMENT.md); DIFTEST subset (60 games, seed 1234) PASSED.
- MSRV 1.80 build: NOT VERIFIED. No Rust 1.80 toolchain is available through the npm mirror and rustup is blocked. Blocker recorded.

- 2026-11-18 — the outpost term used the wrong pawn-attack table in both of its
  lookups (the table is directional: the squares from which a pawn of colour C
  attacks square X are `PAWN_ATTACKS_[other(C)][X]`). The defect is symmetric
  under the board flip, so the antisymmetry gate was satisfied by a wrong
  evaluator — a symmetry test cannot catch a defect that is itself symmetric.
  FIXED in `c702066`, with a regression test that was verified to fail on the
  pre-fix source, plus `pawn_attack_direction_convention_holds` and
  `every_term_has_the_right_direction`.
- Consequence: the evaluation values change, so the searched tree changes
  (bench signature `03e46bba31f35591` → `b58979ca90492208`, 3,445,466 →
  3,666,233 nodes). The EVAL-1 campaign was **withdrawn** because every one of
  its binaries was built from the defective source; the raw records are
  retained unmodified and are not citable. Re-registered and re-dispatched as
  EVAL-2 with seven fresh binaries.
- Evaluation cost: measured at 24.5 % of node time. Three value-identical
  commits cut it by about 18 % (1219 ns → 996 ns per evaluation, idle machine,
  minimum of 20 runs over the four `bench_eval` positions): sharing the slider
  attack masks between the mobility and king-safety terms, replacing the
  per-pawn square-dependent recomputation with lookup tables, and a
  `const FULL` parameter so the fast path stops writing the per-component
  fields it discards. Verified by an unchanged bench signature and node count
  throughout, and additionally by a zero-difference component breakdown over
  ten positions.
- EVAL-2 result (560 games, zero engine errors, all seven pairs passing the
  schedule audit): **EVAL-ALL vs EVAL-NONE is INCONCLUSIVE** (+13 Elo, CI
  [−57, +84]). The evaluation upgrade is not merged as a strength improvement;
  the six flags remain as measurement scaffolding. No feature is HARMFUL;
  turning the mobility taper off is 70 Elo worse than keeping it on, the only
  comparison outside the 40-Elo indeterminate band.
- Gates at the head: fmt clean, clippy `-D warnings` clean, the full release
  test suite green (including 5 evaluation gates and 5 fast-legality tests),
  all 23 fast-perft counts matching, CI green on Linux/Windows/Rust 1.80, and
  anchor verification passing 13/13 with the corrected signature.

## Latest validated checkpoint — 2026-11-19 (Phase B source audit)

- The sandbox had been restored to the initial clone state: the PR #2 history, the extra
  worktrees, the Rust toolchain and the Python environment were gone, and the working tree
  held the whole PR #2 change as uncommitted modifications. The history was recovered with
  `git fetch`; every restored file was verified byte-identical to its `adda48e` blob
  before the branch pointer was moved with `git reset --mixed adda48e`. The pinned Rust
  toolchain (1.97.0) was restored from the PyPI mirror with `tc/fetch.py`; the Python
  environment is `/home/user/.venv` with python-chess 1.11.2. The local toolchain has no
  `rustdoc`, so `cargo test --doc` cannot run here; the crate has no doc examples, so the
  doctest suite is empty and CI (full toolchain) is unaffected.
- **Three search defects were found and fixed.** Each fix has a regression test that was
  verified to fail against the pre-fix source.
  - `708d53c` — the PVS scout bound was used as a move score. The re-search that turns the
    bound into a value was guarded by `reduction > 0`, so an unreduced non-first move kept
    its null-window bound. At depth 2 (late move reductions off) the old code reports a root
    score below the best move's value in 7 of the first 8 Batch A positions, with gaps up to
    172 centipawns; the fixed code is exact in every position, as the pre-PR-2 baseline is.
    The same defect made the engine claim `score mate 15` for a non-mate position.
  - `61dd642` — the move-ordering bands overlapped: a losing capture could be ordered
    above a quiet move (27_952..42_047 against 25_424..74_576) and the promotion bonus
    pushed losing capture-promotions into the quiet band. The bands are now disjoint by
    construction and documented next to the constants.
  - `018e920` — the quiescence did not record its captures on the search path, so from the
    second quiescence level on the counter-move and continuation-history lookups used a
    stale previous move. Classified as a quality defect: the returned value is the maximum
    over the captures searched and stays a valid bound.
- Bench signature `b58979ca90492208` → `c64d148d39181140`; nodes 3,666,233 → 3,413,723.
  The `anchor-verify` workflow pins that signature and was re-pinned in `50ec354`.
- Gates at `018e920`: `cargo fmt --all -- --check` clean, `cargo clippy --release
  --all-targets -- -D warnings` clean, 67 Rust tests green (26 lib + 3 + 21 + 7 + 5 + 5),
  release build and bench green. The seven Python harness suites pass (111, 65, 7, 7, OK,
  all cases, 22) and `verify_opening_subsets.py` plus the power-analysis assertions pass
  unchanged. CI run 44490892522 (Linux/Windows/MSRV) succeeded, evidence-bridge 44490892665
  succeeded, the Windows release artifact 44490892622 succeeded, and `rating-gate`
  44490892498 failed closed for the expected reason (no `benches/gate-plan.json`).
- **What the audit changed for the campaign.** Every binary produced from the old source is
  now a different program: the search tree changed, so the bench signature, the node count
  and the binary hashes all moved. ENGINE-1 (SHA `9663697d…`) and the CTRL-2-R / SCREEN-3
  evidence belong to the pre-fix source and are not evidence about the candidate. EVAL-3
  must be dispatched against the exact frozen candidate binary with a newly registered
  campaign, as the protocol already requires.

## Latest validated checkpoint — 2026-11-19 (Phase C mate-distance audit and EVAL-3)

### The fourth defect: the mate band was narrower than the reachable mate range

The mate-score band was `MATE_SCORE - 100` in three modules — the transposition table, the
UCI score formatter and the search's pruning guards — while the search's ply limit is
`MAX_PLY = 128`. The search returns a static evaluation at `ply >= MAX_PLY` *before* it looks
for mate, so the deepest checkmate node it can reach is at ply `MAX_PLY - 1` and the longest
mate it can report is 127 plies from the root. A mate 100 plies or more from the root
therefore fell **outside** the band, which was 28 plies too narrow.

Two consequences, both reproduced directly:

- **The transposition table reported the wrong mate distance.** Not recognising the score as
  a mate score, the table stored it in root-relative form and returned it unchanged when the
  entry was probed at a different ply. A mate 101 plies away, stored at ply 0 and re-used at
  ply 50, was reported as 101 plies away instead of 151 — wrong by exactly the ply difference.
- **The UCI layer printed long mates as centipawn scores** (`cp 29899` instead of a mate).

The search's own null-move guard shared the band, so a null move could also be attempted with
a mate beta. Fix: `32ad8ab` — the band is now `MATE_SCORE - MAX_PLY`, derived from the
search's ply limit rather than an arbitrary constant, defined once in `eval::MATE_BOUND` and
used by the search, the table and the UCI layer.

The fix is **behaviour-neutral for ordinary positions**: the depth-10 bench signature and node
count are unchanged at `c64d148d39181140` / 3,413,723, because a depth-10 search can never
reach a mate 100 plies away. `tests/mate_distance.rs` adds eight regressions; **four of them
were verified to fail against the pre-fix source**.

### EVAL-3 — registered before dispatch, screened after

| | |
|---|---|
| Candidate | audited tree, `540a10df5f3617e156b289ec9c9475704b18596dd6ec3400c7a31c0f6f2f492f`, bench `c64d148d39181140`, 3,413,723 nodes |
| Control | pre-audit tree (`adda48e`), `2b41a8e6b21294eac87bc21698d27dc354e2e60593613ff1715da85efd4a41e5`, bench `b58979ca90492208`, 3,666,233 nodes |
| Design | 80 games, 20 openings, 2 repetitions, exact AB/BA, fixed movetime 100 ms, hash 16 MiB, opening-clustered bootstrap (seed 20261118, 10,000 resamples) |
| Integrity | 80/80 counted, **0 engine errors**, 0 uncounted, 0 duplicate slots, 40 AB / 40 BA, 20 distinct openings — audit verdict **PASS** |
| Score | **60.5 / 80 = 0.756**, 95% CI **[0.662, 0.838]** |
| Elo difference | **+197**, 95% CI **[+117, +285]** |
| Decision | the registered rule (95% CI lower bound > 0 Elo) is met: the audited tree is **stronger** than the pre-audit tree |

Reproduced twice by independent code paths (`scripts/stats.py` and a separate recomputation
against the raw JSONL). Raw evidence preserved under `benches/evidence/screening-eval3/`
(`games.jsonl` SHA-256 `a336d82543feccb741df6b0364d9511fb4667e4d2bfe2c9aa5cf273f211a47df`).

**This is screening evidence on a shared 2-vCPU sandbox at a fixed 100 ms/move time control.**
It is not a rating, it is not comparable to a campaign run on an idle machine or under the
40/15 clock, and it does not substitute for the >2,000 Elo gate.

### Validation at this checkpoint

- `cargo fmt --all -- --check` clean; `cargo clippy --release --all-targets -- -D warnings`
  clean; `cargo build --release --locked` green; bench green.
- **75 Rust test cases** pass (26 lib + 3 clock_smoke + 21 correctness + 7 eval_quality +
  5 fast_legality + 8 mate_distance + 5 uci_smoke), up from 67. The doctest suite remains
  unrunnable locally because the restored toolchain has no `rustdoc`; the crate has no doc
  examples, so that suite is empty.
- The seven Python harness suites, the opening-subset verification and the power-analysis
  assertions all still pass.
- Bench signature `c64d148d39181140`, node count 3,413,723 — **unchanged** by the mate-band
  fix, so the `anchor-verify` pin is still correct and does not need re-pinning.
- Hosted-runner candidate identity at the exact head `b3dabc3` (anchor-verify run
  `44491236384`, merge commit `fe915cd9e590b59043abbfdfe27b62e476a07eb7`, tree identical to
  the head tree): bench signature `c64d148d39181140`, binary SHA-256
  `4daa6bcea2bac0e74dbfca748daaef4dc33340ae0321ff7ae6a106d790b4f549`, built with rustc
  1.99.0. The sandbox build differs in SHA only because of the compiler version; the identical
  bench signature is the proof that the searched tree is identical.

### Workflow state at `b3dabc3` (API-verified)

| Workflow | Run | Outcome |
|---|---|---|
| CI | 44491236462 | success |
| anchor-verify | 44491236384 | success |
| Windows Release Artifact | 44491236340, 44491228676 | success |
| evidence-bridge | 44491236403 | success |
| rating-gate | 44491236401 | failure — **expected**: it fails closed while `benches/gate-plan.json` does not exist |

### Remaining blockers, in priority order

1. Re-query the workflow outcomes at the new head after the Phase C commits are pushed.
2. Freeze the exact candidate binary and record its SHA-256 in the checkpoint and the status file.
3. Exact-SHA CodeRabbit review; owner Windows acceptance (`OWNER_TEST_PENDING`).
4. Candidate controls, the candidate-specific power assessment (still `BLOCKED` and
   candidate-SHA guarded), and Batch A/B.
5. All three unrounded Elo lower-bound gates above 2,000 Elo.
6. **PR #2 must never be merged automatically.** It stays Draft until the owner decides.

## 2026-11-19 — compute-cost estimate added (planning only)

`scripts/estimate_campaign_cost.py` + `scripts/test_estimate_campaign_cost.py` (26 checks) added and
the report committed at `benches/confirmatory-cost-estimate.json`; CI runs the suite and pins the
report as reproducible and non-authorizing. Estimates: campaign **574.0 runner-hours** (p05 536.4,
p95 614.0) over 600 counted games / 300 shards; wall-clock span 14.9 h at the measured 40-way
concurrency, 21.9 h in sequential waves; 3.06 % shard-timeout risk; USD 0 actual (public repo,
standard runners), notional USD 206.6. Gate-path prerequisites **799.5 runner-hours / 840 games**;
grand total **1,373.5 runner-hours / 1,440 counted games**. Batch B durations are modelled, not
measured, and all timings come from the ENGINE-1 binary — both recorded as assumptions.

No gate changed: the power report is still `BLOCKED` and ENGINE-1-guarded, no gate plan or dispatch
exists, PR #2 stays Draft, and the candidate-specific controls + candidate-specific power PASS +
three unrounded Elo lower bounds > 2,000 remain required before any dispatch.
