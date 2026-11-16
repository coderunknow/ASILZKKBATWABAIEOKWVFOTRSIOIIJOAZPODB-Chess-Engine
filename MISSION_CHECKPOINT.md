# MISSION_CHECKPOINT.md — authoritative resume document

Maintained for resumption by a fresh AI session. Facts here are verified state, not plans.
Historical records: AGENTS_LOG.md, DESIGN_LOG.md, FAILURE_LEDGER.md (append-only).

## Status

- Mission status: **ACTIVE / INCOMPLETE**
- Current milestone: **V1 (strictly above 2,000 Elo)**. V2 (>3,000) not started.
- Current work item: wait for CTRL-2-R and SCREEN-3 to reach terminal state, then aggregate strictly and apply the frozen selection rule.

## Identity

- PR: https://github.com/coderunknow/FlawLessChess/pull/1 (open, **draft**, not merged)
- Branch: `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`
- Base: `main` @ `98b1a00203183d9c7ccb175f7d6eb8f5ef5eb429`
- Last verified remote head (before this checkpoint): `74c3294da9df10236c10b5e9218cd279f3c974e7` (verified 2026-11-16 ~13:37Z via API)
- Local HEAD and remote head after this checkpoint: see "Last successful push" below.

## Last successful push

- Not yet recorded. Updated by the commit that introduced this file.

## Workflow state (API-verified 2026-11-16 ~13:38Z)

| Run | Workflow | Commit | Purpose | State |
|---|---|---|---|---|
| 43820392119 | rating-run | 8e21435 (dispatch rev 13) | CTRL-2-R self-match null control, `flawless-self-r`, seed 20261125 | in progress: 113/120 shard jobs succeeded, 7 in progress, 0 failed; evidence job not yet run |
| 43820645420 | rating-run | 9890407 (dispatch rev 14) | SCREEN-3 vs `akimbo-0.1.1`, 60 shards x 2 games, seed 20261126, TC 40/15 | in progress: resolve succeeded 12:07:58Z (was queued 06:59:56Z); 33 shards in progress, 27 queued, 0 failed |
| 43864633370 | rating-run | 74c3294 | no-op resolve (top commit does not touch `benches/dispatch.json`) | queued |
| 43864633449 | rating-gate | 74c3294 | verification | failure, fail-closed: `benches/evidence/rating-gate-result.json` and gate plan absent (expected until SCREEN-3 is terminal and gate plan exists) |
| 43864633390 | anchor-verify | 74c3294 | anchor verification | success |
| 43864633336 | anchor-research | 74c3294 | anchor research | success |
| 43864633461 | CI | 74c3294 | build/test | success |
| 43864633473 | evidence-bridge | 74c3294 | evidence bridge | success |

Queued and in-progress jobs are NOT complete. Do not describe them as completed evidence.

## Frozen identities (from committed files)

- SCREEN-3 engine_sha256: `9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428` (benches/dispatch.json rev 14)
- SCREEN-3 opening suite: `benches/rating-openings-batchA.txt`, sha256 `2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96`
- Anchor pools: `benches/anchor-pool.json` (V1), `benches/anchor-pool-3000.json` (V2). Pool hashes and binary hashes must be re-verified before use.

## Completed (verified evidence)

- Token authentication and PR #1 metadata re-verified (2026-11-16 ~13:37Z).
- Repository cloned fresh; PR branch checked out at `74c3294`.
- Earlier committed evidence and results are listed in AGENTS_LOG.md (segments 16-23) and DESIGN_LOG.md. Those entries were not re-audited in this checkpoint.

## Pending work (priority order)

1. CTRL-2-R terminal: confirm all 120 shard jobs succeed, confirm the evidence commit (or recovery via `scripts/recover_screen2.py` pattern) is on the branch, verify the CTRL-2-R pass criteria in `PREREGISTRATION.md` before judging it.
2. SCREEN-3 terminal: confirm all 60 shard jobs; aggregate strictly (no partial mixing); record estimates; apply the frozen selection rule from `PREREGISTRATION.md` (SCREEN-3 section).
3. Gate decision:
   - If the frozen rule yields at least 3 non-saturating anchors: commit `benches/gate-plan.json`, validate it independently, push it BEFORE any confirmatory dispatch; then Batch A (rev 15+) and Batch B, each with its own preregistration and identity.
   - If unsatisfiable: follow the registered escape clause (ENGINE-2 registration with SCREEN-2 as measured baseline).
4. Reconcile `STATUS.md` and `MERGE_READINESS.md` with actual run state (not yet done).
5. V2 (>3,000): implement the optional `pool_file` dispatch field, `make_gate_plan.py` and estimator pool consistency, and `benches/gate-plan-3000.json` per GATE-PLAN-V2. Implementation was deferred past the 2,000 gate (PREREGISTRATION amendment 00e7401).
6. Final CI on the exact final head, CodeRabbit review at final head (if the service permits), then Ready-for-Review conversion. Never merge.

## Open technical issues

- None blocking at this checkpoint.
- Runner capacity: SCREEN-3 resolve waited about 5 h behind CTRL-2-R. Queue latency is the main throughput constraint; do not launch duplicate runs.

## Documentation inconsistencies (recorded, not auto-fixed)

- `AGENTS.md` names the repository `coderunknow/Flawless-Chess-Engine`. GitHub reports `coderunknow/FlawLessChess`. The owner declined repository-name changes, so references are left as they are.
- Node.js 20 deprecation warnings on `actions/checkout@v4` and `actions/upload-artifact@v4`. Non-blocking now; update before forced cutover.

## External blockers

- None confirmed in this checkpoint. CodeRabbit status not yet checked in this session.
- GitHub token expiry: 2026-11-22 05:35 UTC (from API response header). Renewal requires the owner. The token must never be written into the repository, logs, or memory.

## Decisions still required from the owner

- None at this checkpoint.

## Exact resume procedure

1. Read AGENTS.md, this file, and the last segments of AGENTS_LOG.md and DESIGN_LOG.md.
2. `git fetch origin` and checkout `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`; reconcile local and remote HEAD.
3. Query run states: `GET /repos/coderunknow/FlawLessChess/actions/runs/43820392119/jobs` and `.../43820645420/jobs` (paginate; use per_page=100).
4. If both runs are terminal, go to pending item 1 or 2. If still in progress, do not dispatch anything; record a checkpoint and resume later.
5. Authentication: the owner-supplied token must be provided for the session. Use a credential helper that reads it at call time; never persist it in `.git/config`, the repo, or logs.
