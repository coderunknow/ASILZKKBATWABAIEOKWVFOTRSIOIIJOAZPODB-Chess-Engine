# MISSION_CHECKPOINT.md — authoritative resume document

Facts here are verified state, not plans. Historical records: AGENTS_LOG.md, DESIGN_LOG.md, FAILURE_LEDGER.md (append-only).

## Status

- Mission status: **ACTIVE / INCOMPLETE**
- Current milestone: **V1 (strictly above 2,000 Elo)**. V2 (>3,000) not started.
- Current work item: validate and commit the RATING-100 / exact-slot-recovery / SEE-ordering implementation, then run final-head CI and fresh review. Separately recover the skipped aggregate evidence from the completed CTRL-2-R and SCREEN-3 shard artifacts; do not apply the anchor rule until those artifacts are strictly re-aggregated and committed.

## Identity

- PR: https://github.com/coderunknow/FlawLessChess/pull/1 (open, **draft**, not merged)
- Branch: `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`
- Base: `main` @ `98b1a00203183d9c7ccb175f7d6eb8f5ef5eb429`
- Current verified PR head before this implementation commit: `dcd00605d728f0ee02aa887a144cecd866edef18` (API-checked 2026-11-17; PR remains open/draft/unmerged).

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
