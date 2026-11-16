# MISSION_CHECKPOINT.md — authoritative resume document

Facts here are verified state, not plans. Historical records: AGENTS_LOG.md, DESIGN_LOG.md, FAILURE_LEDGER.md (append-only).

## Status

- Mission status: **ACTIVE / INCOMPLETE**
- Current milestone: **V1 (strictly above 2,000 Elo)**. V2 (>3,000) not started.
- Current work item: wait for CTRL-2-R (run 43820392119) and SCREEN-3 (run 43820645420) to reach terminal state, then aggregate strictly and apply the frozen rule.

## Identity

- PR: https://github.com/coderunknow/FlawLessChess/pull/1 (open, **draft**, not merged)
- Branch: `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`
- Base: `main` @ `98b1a00203183d9c7ccb175f7d6eb8f5ef5eb429`
- Last verified remote head before the reconciliation commit: `e47dbfdf355e8d5287711323da1876279764ffaa` (PR head verified via API 2026-11-16 13:40Z).
- The reconciliation commit's SHA is the branch head after its push; it is verified in the session output and recorded at the next checkpoint.

## Workflow state (API-verified 2026-11-16 13:43Z)

| Run | Workflow | Commit | Purpose | State |
|---|---|---|---|---|
| 43820392119 | rating-run | 8e21435 (dispatch rev 13) | CTRL-2-R, `flawless-self-r`, 120 shards × 2 games, seed 20261125, engine 9663697d… | in progress: 113/120 shards success, 7 in progress, 0 failed; evidence job not run |
| 43820645420 | rating-run | 9890407 (dispatch rev 14) | SCREEN-3 vs `akimbo-0.1.1`, 60 shards × 2 games, seed 20261126, TC 40/15 | in progress: resolve + 1 shard success, 33 running, 26 queued, 0 failed |
| 43864633370 | rating-run | 74c3294 | no-op resolve (not a dispatch) | queued |
| 43877962212 | rating-run | e47dbfd | no-op resolve (not a dispatch) | queued |
| 43864633449 | rating-gate | 74c3294 | fail-closed: no gate plan / rating-gate-result.json (expected) | failure |
| 43864633461 | CI | 74c3294 | build and test | success |
| 43877962180 | CI | e47dbfd | build and test | queued |

Queued and in-progress jobs are NOT complete. Do not describe them as completed evidence.

## Frozen identities

- ENGINE-1 candidate (CTRL-2-R, SCREEN-2R, SCREEN-3, and now Batch A/B per BATCH-HASH): `9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428`
- Pre-fix candidate (CTRL-2, SCREEN-1/2, historical only): `fd75726dd3166640ddec75d94c416320b47c83e8d14bfa6309aed398d55b8e1d`
- Batch A suite `benches/rating-openings-batchA.txt`: `2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96`
- Batch B suite `benches/rating-openings-batchB.txt`: `744a3981cc312a676ba259962309858b7d2fc645094bf2dccf5391e77f2f9dd4`
- Anchor pools: `benches/anchor-pool.json` (V1), `benches/anchor-pool-3000.json` (V2).

## Verified in this session (2026-11-16)

- Screening estimate from raw SCREEN-2R evidence, reproduced with `scripts/make_gate_plan.py --out /tmp/...` (no plan committed): topple-0.1.1 2176.8, topple-0.2.1 2236.4, est 2206.6.
- SCREEN-3 mechanical choice re-verified: among unscreened non-saturating anchors, |est − R| is akimbo-0.1.1 234.4, wyldchess-1.2 238.4, wyldchess-1.1 267.4, wowl-1.3.7 357.6. Choice = akimbo-0.1.1. The same choice holds under the pre-fix estimate (2251.9).
- Dispatch rev 14 description quotes pre-fix numbers (2225.9 / 2277.8, |Δ| ~163–215). Documentation discrepancy only; the choice is unchanged.
- Local test suites on the checkout: `test_rating_estimator.py` 65/65 PASS; `test_aggregate_60.py` PASS (120 games); `test_merge_batch_runs.py` self-test ALL CASES PASS. `test_match.py` NOT run locally: pinned python-chess 1.11.2 is not in this sandbox's package index. CI installs `chess==1.11.2` and runs it.
- PREREGISTRATION BATCH-A/B pinned the pre-fix engine hash. Amendment BATCH-HASH registered (append-only, 2026-11-16, before any batch dispatch) to bind Batch A/B to 9663697d….

## Pending work (priority order)

1. CTRL-2-R terminal: confirm 120/120 shards succeed, obtain the evidence commit (rating-run evidence job or the recovery path), then evaluate the registered criterion (seat-perspective score 0.5 inside the 95% opening-cluster CI, seed 20261125). If it fails, diagnose before any gate.
2. SCREEN-3 terminal: confirm 60/60 shards, aggregate strictly (no partial mixing), then run `make_gate_plan.py --anchors topple-0.1.1 topple-0.2.1 akimbo-0.1.1` on the committed evidence.
3. Gate-plan commit (`benches/gate-plan.json`) and Batch A dispatch in the same commit, only after the BATCH-HASH amendment is on the branch. Then Batch B. Each dispatch needs its own marker revision and identity.
4. V2 (>3,000): pool_file dispatch field, make_gate_plan / estimator pool consistency, `benches/gate-plan-3000.json`, expanded-pool CTRL-1R/CTRL-2R. Deferred until the V1 gate is resolved (GATE-PLAN-V2 amendment, 00e7401).
5. Final-head CI, CodeRabbit review (if the service permits), then Ready for Review only when every MERGE_READINESS item is verified. Never merge.

## Projection (NOT evidence)

- Observed CTRL-2-R throughput: about 226 games in about 6.8 h (≈33 games/h, from run start 06:57Z to 13:45Z).
- V1 minimum sample: ≥3 anchors × 2 batches × 2,040 games ≈ 12,240 games ≈ 370 h (≈15 days) of continuous runner time before queueing and failures. V2 needs more.

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
4. If a run is still in progress, dispatch nothing. Record a checkpoint and resume later.
5. Authentication: the owner supplies the token for the session. Use a credential helper that reads it at call time. Never persist it in `.git/config`, the repo, logs, or memory.
