# MERGE_READINESS — PR #2 / v1.0.0 qualification checkpoint

**Verified state as of 2026-11-19 UTC. This replaces the stale PR #1 checklist below; it is not a release authorization.**

## Decision

- **Mission: ACTIVE / INCOMPLETE. PR #2 is not merge-ready. Do not merge, tag, or release.**
- **Absolute Elo: not yet measurable from valid evidence.** The strict requirement is Batch A, Batch B, and combined calibrated 95% lower bounds each strictly greater than 2,000 without rounding. None exists for the current candidate.
- v1.0.0 is **not authorized**. No release artifact or release notes may be published as stable. Live GitHub verification found no tags or Releases.

## Live identity and review

- PR: https://github.com/coderunknow/FlawLessChess/pull/2 — OPEN, DRAFT; GitHub says `MERGEABLE`, merge state `UNSTABLE`, no review decision.
- Base: `main` at `5e36b06a7b0d7417d57205e52010ea98529b2a4f`.
- Remote PR head: `b9d3979d16d9ae5f7cf0ce596c1910622249fde8`.
- Local branch: `arena/8259ce1c-flawlesschess`, same committed HEAD as remote, with uncommitted changes in workflows, qualification/power/aggregation scripts, tests and docs. These worktree changes have not been pushed or checked by hosted CI.
- The only formal CodeRabbit review is `COMMENTED` at older commit `6f8c5b61e06d07340d4be66b9df21649bd967cdf`; it is not an approval or an exact-head review. Two still-current findings on `audit_pair.py` and `collect_eval_results.py` were fixed in source, regression-tested locally, replied to, and resolved in GitHub. A fresh exact-final-head review remains outstanding.

## Exact-remote-head workflow state

For `b9d3979`:

- CI run `44513810575`: Ubuntu, Windows, and Rust 1.80 MSRV jobs passed.
- Windows Release Artifact run `44513810693` (the prior committed workflow): runner job passed; artifact `14523729486` exists. Its real-Windows build and pre-package binary checks passed (PE imports, UCI, bestmove, perft, stop, bench) and archive generation completed. The artifact download failed, so the ZIP contents and checksum/manifest equality were not verified.
- The dirty worktree now adds `scripts/verify_windows_package.py` and a Windows workflow step to validate the actual ZIP members, archive checksum, packaged executable hash/PE imports, manifest, and to rerun UCI/search/perft from the extracted package. Its seven host-independent package regressions pass locally, but this new Windows-runner step has not run. No human GUI acceptance is claimed.
- Anchor verification run `44513810723`: passed.
- Rating gate run `44513810716`: failed closed because `benches/gate-plan.json` and qualifying canonical rating evidence are absent. This is expected and is not a passed rating gate.
- Evidence Bridge run `44513810594`: job reports success, but its collection/upload steps were skipped by the top-commit marker gate; no evidence was collected or uploaded.
- Attempted to download and inspect the Windows artifact; the artifact blob request ended with EOF. Therefore its packaged contents/checksums have not been independently inspected here. The workflow's Windows tests are not a substitute for that inspection.

## Local checks on the current dirty worktree

- All 17 `scripts/test_*.py` suites passed locally with Python 3.11 and python-chess 1.11.2, including candidate qualification, aggregation, control certification, power/cost analysis, and seven Windows ZIP verifier regressions.
- All six workflow YAML files parsed; all 7 unique embedded Python heredocs compiled; candidate preregistration validator passed; `git diff --check` passed. Git attribute checks confirm all candidate evidence paths retain LF line endings so raw evidence/certificate hashes remain stable across Windows checkouts.
- Rust was unchanged by the current worktree patch. Local `cargo`/`rustc` are absent in this restored sandbox, so Rust checks were not rerun locally. The exact remote head's Linux/Windows/MSRV CI remains the available Rust validation, but does not validate the dirty Python/workflow changes.
- The candidate validator accepts the design as `PREREGISTERED_NOT_DISPATCHED`; this validates the plan only, not evidence or gate authority.

## Rating evidence — hard stop

- Candidate binary SHA-256 designated by the plan: `0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5`.
- No candidate screening, self-control, or confirmatory games/evidence exist under the candidate-qualified evidence root.
- No candidate-specific independent power PASS, `benches/gate-plan.json`, or Batch A/B gate results exist. Historical screening, self-play, other engine binaries, fixed-time probes, bench nodes/signatures, and old controls cannot replace these.
- Registered 600-game selection screen and separate 240-game self-control remain unrun. Existing cost planning places the required campaign far beyond the runner budget; neither the sample sizes nor any other registered condition may be weakened.

## Runner budget accounting

A measured GitHub Actions API audit of branch `arena/8259ce1c-flawlesschess` workflow runs created since 2026-11-18 00:00 UTC found **136 runs / 481 started-and-completed jobs / 16,878 seconds = 281.3 runner-minutes** summed across jobs. Parallel jobs are counted separately. This exceeds the user's 60-minute cumulative ceiling; it is not a campaign-runtime estimate. The user's continue instruction authorizes local review, not additional hosted work beyond the cap; do not launch another run unless the runner limit is explicitly changed.

Cost context from the checked-in planning report `benches/confirmatory-cost-estimate.json`: **799.5 estimated runner-hours of prerequisite candidate screening/control** (571.1 screening + 228.4 self-control), plus **574.0 estimated runner-hours for confirmation**, or **1,373.5 estimated runner-hours total**. These are planning estimates transferred from 360 ENGINE-1 games, not measurements of the preregistered candidate; Batch B was modelled as exchangeable with Batch A, and no candidate-specific timing report can be produced until candidate evidence exists. The report authorizes no dispatch. This is far beyond the 60-minute ceiling even before considering the actual measured usage already above it.

## Required to change this decision

A future authorized continuation must first reconcile the over-budget runner situation, complete exact-head review and CI of the currently uncommitted patch, validate packaged Windows and Linux binaries/checksums/manifests, and satisfy every registered candidate control, independent power, gate-plan, Batch A/B and combined-bound requirement. No threshold, sample size, clock, suite, anchor, seed, exclusion, or statistical method may be weakened.
