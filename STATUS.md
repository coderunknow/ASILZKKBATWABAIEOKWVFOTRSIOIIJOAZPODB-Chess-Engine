# STATUS — Flawless Chess Engine

**Current project state (verified 2026-11-19 UTC): `ACTIVE / INCOMPLETE`.** V1 is NOT complete. **Absolute Elo: not yet measurable from valid evidence.** The strict 2,000 Elo gate is NOT passed. PR #2 is open and Draft; its remote head is `b9d3979d16d9ae5f7cf0ce596c1910622249fde8` (base `main` at `5e36b06a7b0d7417d57205e52010ea98529b2a4f`). The local worktree contains uncommitted candidate qualification, aggregation, power/cost tooling, workflow, test, and documentation changes; those changes have not received hosted CI or fresh exact-head review. Local Python tests pass, while local Rust tools are absent. Exact-remote-head CI Linux/Windows/MSRV and Windows artifact/anchor checks passed; the rating gate failed closed with no gate plan/evidence, and the Evidence Bridge's evidence steps were skipped. No candidate games/evidence, gate plan, confirmatory batches, merge, tag, or release exist. A measured branch workflow-job sum since 2026-11-18 00:00 UTC is 281.3 runner-minutes, above the 60-minute cumulative cap; the user's continue instruction authorizes local review, not hosted execution beyond the stated cap. No further hosted work is authorized unless the runner limit is explicitly changed. See `MERGE_READINESS.md` for the authoritative current checklist and exact evidence.

**Current branch:** `arena/8259ce1c-flawlesschess`
**Starting commit (re-verified 2026-11-18):** `5e36b06a7b0d7417d57205e52010ea98529b2a4f`
(`origin/main`; PR #1 merged 2026-11-14. The 2026-11-14 start `98b1a002…` is retained
above in the historical record.)
**Engine identity (UCI):** `Flawless`
**License:** Apache-2.0 (preserved)

## Checklist (binary acceptance criteria — see TASK in prompt)

- [x] Repository recon complete (Phase 0)
- [x] Starting commit / remote state verified and recorded
- [x] Rust toolchain available (1.99.0, installed from npm `@toolchain-bin/*` because static.rust-lang.org is unreachable; see `docs/ENVIRONMENT.md`)
- [x] Architecture RFC published (Phase 1) — see ARCHITECTURE.md (accepted for v1 scope)
- [x] Chess foundation: perft COMPLETE 2026-11-14 — full CPW reference matrix 27/27 exact matches (startpos d1–d6, Kiwipete d1–d5, pos3 d1–d6, pos4 d1–d6 incl. d6 = 706,045,033, pos5 d1–d5; raw record `benches/perft_full_20261114.md`); python-chess oracle cross-check MATCH (`scripts/perft_oracle.py`); startpos d3 = 8902 additionally asserted in CI every push/PR, both OSs
- [x] Differential testing vs python-chess (pinned 1.11.2, GPL-3.0+, test-only oracle) — DIFTEST PASSED, 76,240 positions, 305 d3 perft comparisons, 0 mismatches
- [x] UCI protocol implemented and smoke-tested (async stop via worker thread + AtomicBool, clocks, MultiPV, ponder/ponderhit) — fuzzed smoke-level (seeded, deterministic; tests/uci_smoke.rs) — see TESTING.md; deep fuzzing NOT performed
- [x] Search baseline: iterative deepening + alpha-beta + TT (8-byte) + quiescence + null-move + LMR + aspiration + MultiPV (uncommitted until this phase checkpoint; see below)
- [x] Classical evaluation baseline (tapered PSTs, mobility, bishop pair, king zone, tempo); NNUE interface deferred, NNUE NOT default
- [x] Benchmark harness (fixed-time `movetime`/`depth`, paired openings, color reversal, opening-clustered CI) — `scripts/match.py` + `scripts/stats.py` + `benches/openings-20.txt`; verified end-to-end (smoke-match 2/2 wins vs SF 19 WASM Skill 0)
- [x] CI green on Linux + Windows (fmt, clippy -D warnings, release tests, release build, UCI handshake, UCI bestmove smoke, perft d3 sanity) + MSRV (1.80) job — PR #1, runs 43562935232 / 43563085939 / 43563499046 (clippy-fix regression, caught by CI, fixed in 837361f) / 43563628232 / 44c8369-era all green (except the known-bad b85b3f7); Kilo Code Review bot fails for account credits (not a code issue); CodeRabbit manually triggered (incremental) — see "Reviews" below
- [x] Match infrastructure: paired openings, color reversal, opening-clustered bootstrap CIs — `scripts/match.py` + `scripts/stats.py` (used for probes); panic-fallback games flagged `engine_error` and excluded from stats by default
- [x] **Rating harness v2 (2026-11-14)**: true UCI clock TC (`--tc 40/15` repeating schedule, `wtime/btime/winc/binc/movestogo`, actual-elapsed charging, flag fall, ponder off, `add`/`reset` period policy), historical deterministic repetition schedule (60×17×2=2,040/anchor/batch, superseded for future confirmation by append-only RATING-100) + exact AB/BA reversal, deterministic shard slicing (`--shard-index/--shard-count`), engine-error record→immediate-replay→abort-after-2 policy, move-cap recorded unadjudicated (never a silent draw), manifest v2 written before game 1 and finalized after (interrupted runs stay `in_progress`), opening-suite SHA-256 + schedule hash + shard identity in manifest, anchor-pool schema hardening (rejects TBD/null/placeholders, malformed SHA-256, ambiguous uncertainty conventions, unverified licenses/binaries). Regression suites: `scripts/test_match.py` (**104/104**), `tests/clock_smoke.rs` + `uci::tests::clock_limits_*` (Flawless clock-management verification; **34/34** cargo tests incl. the bestmove-handoff stress regression)
- [x] **Rating estimator (2026-11-14)**: `scripts/rating_estimator.py` implements RATING_PROTOCOL §9.6–9.8 — joint opening-cluster bootstrap (≥10,000, same cluster draw across anchors), per-anchor logistic d_a, σ_matched = SD of joint replicates, published-error → SD convention conversion (sd/se/ci95/ci90/ci99), GLS over Σ_m+Σ_c with documented diagonal-WLS fallback, separate match-only vs match+calibrated CIs, batch combination that pools match noise but adds shared calibration ONCE, null controls (anchor-vs-anchor ±75 Elo; self-match ~0.5), fail-closed `gate` subcommand that recomputes from raw evidence. Regression suite `scripts/test_rating_estimator.py` (**53/53**, incl. `scripts/verify_evidence.py` fail-closed checks on committed evidence). Shard aggregator `scripts/aggregate_shards.py` (fail-closed §5.2 rejection rules; smoke-verified both directions)
- [x] **Rating workflows (2026-11-14)**: `anchor-research.yml` (fetch official CCRL 40/15 list from a hosted runner — open egress — with full provenance), `rating-run.yml` (workflow_dispatch shard execution, frozen commit/engine-hash/suite-hash verification, hardware capture, fails CLOSED until a verified anchor pool exists), `rating-gate.yml` (stable `rating-gate` job: aggregate+verify then independent estimator recomputation; SUCCESS only if all three lower CI bounds strictly > 2,000 and both null controls pass). Note: GitHub delivers `workflow_dispatch`/`workflow_run` only to workflow files on the default branch (main has only `LICENSE`), so remote runs go through `pull_request`-path triggers until merge; the permanent dispatch path is `gh workflow run`.
- [x] Identity migration to Flawless (ADR-0002) — historical evidence kept under old identifiers
- [x] Correctness audit pass 1 + 2 (mate>draw precedence, quiesce/RFP terminals, searchmoves MultiPV=1, clock_limits panic, panic-fallback plumbing) — all reproduced by regression tests; bench signature `d790483532d87af0` → `3086f65159758c9d`
- [x] UCI integration smoke + seeded deterministic fuzz (`tests/uci_smoke.rs`)
- [ ] Absolute rating > 2,000 (two-sided 95% CI lower bound STRICTLY GREATER THAN 2,000) — NOT MEASURED, NOT MET. CTRL-1 PASS remains candidate-independent; CTRL-2 PASS applies only to the pre-fix binary. CTRL-2-R run 43820392119: resolver + 120/120 shards succeeded, but aggregate-and-commit-evidence was SKIPPED, so no self-match estimate exists. SCREEN-2R remains selection-only (topple-0.1.1 2176.8, topple-0.2.1 2236.4, mean 2206.6). SCREEN-3 run 43820645420: resolver + 60/60 shards succeeded, but aggregate-and-commit-evidence was SKIPPED, so no third-anchor screening estimate exists. No gate plan or Batch A/B evidence exists.
- [ ] RATING-100 confirmatory sample — NOT AUTHORIZED / BLOCKED. Proposed 100 counted games per anchor per batch (50 opening clusters × AB/BA), with disjoint A/B suites; all historical gate conditions and controls remain unchanged. The delta-method prospective sensitivity report is BLOCKED because full third-anchor covariance and Batch-B cluster variance are absent and power is weak near the 2,000 threshold. No confirmatory dispatch may proceed until a reviewed evidence-backed PASS exists.
- [ ] SEE-based capture ordering candidate — implemented in source but NOT YET BUILT, TESTED, BENCHMARKED OR REVIEWED. No Elo gain or NPS improvement is claimed.
- [ ] Reviews: CodeRabbit review 5903125228 fully dispositioned (13/13 findings; 11/11 threads replied+resolved 2026-11-14); FRESH review at the exact final SHA still required; Copilot BLOCKED (quota, lower-effort retry needs web UI); Codex RATE_LIMITED; Qodo BLOCKED (trial ended); Kilo BLOCKED (credits)
- [x] PR #1 returned to **Draft** (2026-11-14, `gh pr ready --undo` verified): open, unmerged, draft=true. Earlier "not marked ready" claim was inaccurate (GitHub had it open/non-draft); corrected. PR stays open+unmerged; never merge/tag/release without explicit authorization.
- [ ] Correctness, reliability, documentation, release gates (see TESTING.md)
- [ ] v1.0.0 stable release (**NOT AUTHORIZED — gate not passed**)

## Hard constraints / environment notes

- No crates.io access (blocked): the engine is implemented with **zero external dependencies** (pure `std`).
- No static.rust-lang.org access: toolchain installed from npm packages `@toolchain-bin/{rustc,cargo,rust-std,rustfmt,clippy}-1.99.0-x86_64-unknown-linux-gnu` into `/home/user/.toolchain/sysroot`.
- Reference machine (target): Windows 10 LTSC 2021, i5-7300U (4 threads), 8 GB RAM. This dev sandbox: 2 vCPU, ~4 GB RAM, Linux.
- Opponent binaries for anchored rating testing are limited; see BENCHMARKING.md for the honest state of rating evidence.

## 2026-11-18 session — strength work in progress

**Project state: `ACTIVE / INCOMPLETE`.** The strict 2,000 Elo gate is still NOT MET and the
absolute rating remains UNKNOWN. No confirmatory rating batch has been dispatched.

### Completed and measured

- **Analytic fast legality filter** (on `main` as `cd17da0`): the searched tree is provably
  identical (bench signature `141943aa23b3fc68`, 2,530,885 nodes) while throughput rose from
  ~441 k nps to ~785 k nps (+78 %).
- **STRENGTH-1 screening** (80 counted games per pair, exact AB/BA colour reversal, fixed
  100 ms/move, 16 MiB hash, opening-clustered 95 % bootstrap, seed 20261118):

  | Pair | Candidate score | 95 % CI (score) | Elo diff | 95 % CI (Elo) | Decision |
  |---|---|---|---|---|---|
  | BASE vs SPEED-1 | 0.625 | [0.519, 0.725] | +89 | [+13, +168] | **KEPT** |
  | BASE vs HIST-1 | 0.406 | [0.306, 0.512] | −66 | [−142, +9] | **INCONCLUSIVE** |

  All 160 games counted; zero engine errors; balanced colours in every opening.
  These are *screening* results at a fixed clock, not ratings and not absolute Elo.
- **Evaluation rewrite** with six independently measurable features, an exact tapered
  breakdown, and `tests/eval_quality.rs` (antisymmetry, sanity, finiteness).
- **EVAL-1 ablation** registered with fixed decision rules; the control (all flags off)
  reproduces the parent tree's bench signature and node count exactly.

### Explicitly NOT claimed

- No playing-strength claim for HIST-1 (its interval straddles zero).
- No absolute rating, no CCRL/CEGT result, no rating above 2,000 Elo.
- No merged PR, no tag, no release, no Windows artifact delivered yet.
- `OWNER_TEST_PENDING`: the owner has not yet tested a delivered binary.

## Measured strength probes (internal, in-sandbox; NOT a CCRL/CEGT rating)

Pinned opponent: Stockfish 19 WASM `stockfish-19-lite-single` (npm `stockfish@19.0.1`, single-threaded,
hashes recorded in BENCHMARKING.md). TC: 100 ms/move fixed; 20 openings ×2 colors paired; output
committed under `benches/probe-*`.

| Probe | SF setting | Ours W/D/L | Score | 95% opening-clustered CI | Logistic Elo diff vs this setting |
|-------|-----------|------------|-------|---------------------------|-----------------------------------|
| probe-001 | Skill 0 | 40/0/0 | 1.000 | [1.000, 1.000] | boundary: perfect observed score; no finite estimate (unbounded above) |
| probe-003 | Skill 5 (pre-RFP/CE) | 11/13/16 | 0.438 | [0.325, 0.550] | −44 (CI [−127, +35]) |
| probe-002 | Skill 10 | 1/7/32 | 0.113 | [0.050, 0.175] | −359 (CI [−512, −269]) |
| probe-004 | Skill 5 (RFP+CE build) | 14/14/12 | 0.525 | [0.412, 0.637] | +17 (CI [−61, +98]) |
| probe-005 | Skill 5 (post-refactor, 100 ms) | 20/8/12 | 0.600 | [0.463, 0.725] | +70 (CI [−26, +168]) |
| A/B 004 | vs pre-change build, 50 ms | 18/13/9 | 0.613 | [0.487, 0.725] | +80 (CI [−9, +168]) |

Conclusion (honest): our strength is bracketed between pinned SF-Skill-5 and SF-Skill-10 at
movetime 100 ms on this hardware. The RFP+check-extension change moved the needle in the right
direction (+80 in the A/B, +17 vs Skill 5, both CIs wide and overlapping zero at 40–120 games).
Absolute Elo is UNKNOWN and unverifiable from this sandbox — no calibrated anchor was available, so
no absolute number in either direction is supported by evidence; v1.0.0 gates NOT met; rating
estimate = **INCONCLUSIVE**. Do not present these numbers as official ratings.

## Next preregistered task

1. Keep engine development evidence-based: if time permits, probe skill 3/7 to tighten the bracket, or run
   longer-TC probes; do not tune to the probe opponent.
2. ~~NPS / bench regression tracking~~ DONE (2026-11-14): `cargo run --release -- bench` — fixed
   depth 10 over 12 positions, deterministic FNV-1a signature `3086f65159758c9d`
   (2,317,474 nodes); `bench_eval` for eval throughput; CI runs perft d3 + UCI handshake + bestmove smoke.
3. Remaining V1 gaps: benchmark CLI `bench`, time-management validation vs clocks, EF RN search-consistency
   checks, Windows-specific verification (CI covers build only), and documentation of the release gates.
4. NEVER claim v1.0.0 status; never present in-sandbox numbers as CCRL/CEGT.

## Local verification re-run (2026-11-14, workspace restore #3)

Toolchain (npm @toolchain-bin @1.99.0 pins) rebuilt per docs/ENVIRONMENT.md; DIFTEST re-passed
(legal-move sets identical; perft-d2 2295/2295, 0 mismatches, seed 20261114); `cargo test --release`
29/29 green; clippy clean (1 latent too_many_arguments fixed via StoreRequest); bench re-measured:
signature unchanged `fc907eba40b7869f`, 2,221,199 nodes @ d10 (43% reduction; 259,619 nps).

## CI status on current head (2026-11-14, verified via gh run list/view)

- Head `ca61ea6` (PR #1): CI run **43579289640 — SUCCESS** (ubuntu-latest, windows-latest, msrv rust 1.80 all green).
- Head `89189a6` (docs-only): CI run 43579193978 — SUCCESS (all three jobs).
- Head `e769d9a` (PR #1): CI run **43578826380 — SUCCESS** (ubuntu-latest, windows-latest, msrv rust 1.80 all green).
- Head `45f8507`: CI run 43578590768 — SUCCESS (all three jobs).
- Head `1fb14ae`: CI run 43578036659 — SUCCESS (all three jobs).
- (Failures 43577034924 on db174e4 and 43577274974 on 4aa7f06 were the clippy `too_many_arguments`
  episode — fixed by StoreRequest in d6dc221; remote annotations then confirmed the root cause.)
- CodeRabbit re-review: requested 2026-11-14T09:25Z on head `e769d9a` → returned **"Review rate
  limited"** (neutral, e769d9a check-run). The automatic push-review path is disabled for this OSS
  repository ("Review skipped: manual review required for this OSS repository" on 89189a6/ca61ea6).
  `@coderabbitai resume` posted 2026-11-14T09:47Z — awaiting result. **No review pass may be claimed
  until CodeRabbit completes on the exact final head SHA.**
- Evidence pipeline: scripts/match.py now records hardware/OS, per-side artifact SHA-256 (incl.
  dynamically loaded WASM), git commit, adjudication and color-pairing text in meta.json; pre-
  registered ≥60-line opening suites for batch A/B (`benches/rating-openings-batchA.txt`,
  `batchB.txt`, FEN-verified, mutually disjoint); value-free anchor descriptor template
  (`benches/anchor-pool.template.json`). Manifest is now written and closed before the first game
  so provenance survives an interrupted batch (fixed after observing it buffered for a whole run).
- probe-005 (post-refactor regression probe vs SF19-lite Skill 5, committed): 24/40 = 0.600,
  opening-clustered 95% CI [0.463, 0.725], logistic +70 (CI [-26, +168]), 0 engine-error games —
  same band as probe-004 (0.525), no regression. Relative statistic only; not a rating.

## Rating status (absolute; release-gate relevant)

- **Absolute rating: UNKNOWN.** The in-sandbox probes (SF Skill 0/5/10 WASM) are relative comparisons
  vs one unrated-for-our-purposes opponent configuration, not a calibrated absolute scale, and are NOT
  a CCRL/CEGT rating. Stockfish Skill Level is not a calibrated Elo anchor.
- **The V1 release gate (two-sided 95% CI of calibrated absolute rating, lower endpoint STRICTLY
  GREATER THAN 2,000 Elo — amended from ≥ 2,000 on 2026-11-14, docs/RATING_PROTOCOL.md §9;
  vs a credible pool with documented methodology, pinned opponents, paired openings, ≥2 independent
  confirmation batches with ≥2,000 games per anchor per batch, preregistered) is NOT measured and
  NOT met. Nothing may be claimed otherwise.**
- Blocker (exact, UPDATED 2026-11-14 late): the sandbox still cannot reach computerchess.org.uk, but
  GitHub-hosted runners CAN — `anchor-research.yml` has now captured the official CCRL 40/15 list
  (URL `https://computerchess.org.uk/4040/rating_list_all.html`, retrieved 2026-11-14T10:49:28Z,
  HTTP 200, 3,912,738 bytes, SHA-256 `ce365c55b2869502de6addeada4c261d3bd2f50a5a9aef484db9f571aabe15f0`;
  4,873 parsed rows; November 13, 2026 update; "Bayeselo" computed; **published errors are 95%
  confidence intervals** → anchor-pool `error_convention: ci95`). What remains external: (a) selecting
  ≥3 eligible anchors whose EXACT listed versions have legally downloadable binaries (open-source
  candidates mapped: akimbo 0.1.1=2441±19, Topple 0.2.1=2439±14, WyldChess 1.2=2445±21, Halogen 6=
  2441±23, Counter 1.2=2447±14, CT800 1.42=2441±23, Cheese 1.4=2448±17, Kimbo 0.3.0=2439±17 — all
  CCRL 40/15 Nov 13 2026; GitHub homes+licenses resolved via API), plus BELOW-2200 anchors (lower-band
  extraction in progress) so the pool brackets 2,000; (b) the match execution at scale (thousands of
  40/15-class games — GitHub Actions shards per rating-run.yml; local 2-vCPU screening cannot); (c) the
  hardware calibration (Stockfish 10 bench procedure → i7-4770k equivalence) before confirmatory runs.
- Pre-registered protocol for when the gate IS executed: `docs/RATING_PROTOCOL.md` §9.
- Next actions for the gate (in priority order): (1) finish anchor vetting: exact-version binary
  acquisition + SHA-256 + license verification on hosted runners (anchor-research → anchor-verify);
  fill `benches/anchor-pool.json` (NEVER the template) with verified values incl. ci95 conventions;
  (2) run null-control + pilot shards via rating-run.yml to measure throughput and TC equivalence;
  (3) preregister + freeze Batch A/B schedules; (4) execute ≥2 confirmation batches × ≥2,000 games
  per anchor (60×17×2 shards); (5) rating-gate must pass with all three lower bounds > 2,000;
  (6) publish raw evidence + stats; only then evaluate v1.0.0 authorization.

## Reviews (per-reviewer state, head SHA at time of record)

Current head: see `git log --oneline -1`. PR #1 is OPEN, unmerged, **Draft** (converted 2026-11-14).

| Reviewer | State | Notes |
|----------|-------|-------|
| CodeRabbit | re-review requested 2026-11-14T09:25Z → **"Review rate limited"** on e769d9a; push-triggered reviews are DISABLED for this OSS repo ("manual review required for this OSS repository" on 89189a6/ca61ea6); `@coderabbitai resume` posted 2026-11-14T09:47Z — awaiting result. Prior substantive review 5903125228 (13/13 dispositioned) | REVIEW: do not claim pass before the bot completes on this exact final SHA — verify `gh api repos/coderunknow/FlawLessChess/commits/<sha>/check-runs` and map the reviewed SHA; manual review is the only working path (push path disabled), and it is rate limited — retry at the next hour boundary if resume fails |
| GitHub Copilot | BLOCKED | quota insufficient at default effort (2026-11-14). Retry at LOWER effort requested by task but requires the web UI reviewers panel (effort selection); API re-request rejected (`422: not a collaborator`); docs.github.com unreachable from sandbox. No findings recorded. |
| Codex | RATE_LIMITED | documented retry (`@codex review`) attempted 2026-11-14T05:47Z → "You have reached your Codex usage limits for code reviews." Prior run at 05a36c0: code review FAILED (usage limit), no findings available. |
| Qodo | BLOCKED | "Qodo reviews are paused because your trial has ended." (billing-blocked, 2026-11-14). No code findings. |
| Kilo | BLOCKED | "Kilo Code Review could not run — your account is out of credits." (2026-11-14). No code findings. |

Review policy: a reviewer FINISHED only when the service actually completes and findings are dispositioned.

## CHECKPOINT — 2026-11-14T15:10Z (pre-waiting-boundary)

- HEAD `f2176b6` (branch arena/b756c5f1-…, PR #1 open/draft, mergeable).
- Completed this segment: rating-run marker-dispatch mechanism (revs 1–6) + fixes
  (config double-encoding; --white-cmd word-split; top-commit marker gate); PILOT-1
  dispatched + 2 harness defects found/fixed pre-game; runner engine hash frozen
  `fd75726d…` (2 reproducible builds); both null controls REGISTERED + dispatched;
  5 CodeRabbit threads dispositioned + resolved (uci.rs:433 stress regression added);
  estimator key-matching fix (pool names non-unique) + 4 tests (suite 50/50, match 104/104,
  rust 34); aggregate mixed-hardware policy; evidence job + evidence-bridge workflows.
- In flight (server-side): pilot 43602273258 + dup 43603558950 (4+4 games); CTRL-2
  43603826611 (240 games, shards running); CTRL-1 43604654709 (240 games, queued).
  In-flight runs predate the evidence job -> collect via evidence-bridge after completion.
- Next exact actions: (1) poll runs to completion; (2) dispatch evidence-bridge
  (benches/evidence-request.json: 43602273258->pilot, 43603558950->pilot-dup,
  43603826611->control, 43604654709->control); (3) evaluate controls vs fixed thresholds
  (±75 Elo; 0.5 in 95% binomial CI) + pilot throughput; (4) preregister Batch A/B
  (2,040 games/anchor, engine hash fd75726d…, suites hashes frozen, seeds fixed);
  (5) dispatch batches progressively; (6) aggregate + rating_estimator gate (all three
  unrounded lower bounds > 2000); (7) §4 audit finish + fresh CodeRabbit at final SHA;
  (8) MERGE_READINESS + final audit + "Is this complete?".
- Missing evidence: pilot results; CTRL-1/CTRL-2 results; batch A/B games + CIs;
  fresh final-head CodeRabbit review; final full CI on final SHA.

## CHECKPOINT — 2026-11-15T07:00Z (SCREEN-2 in flight; workspace restore #6 session)

- HEAD `c24020b9` on `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij` (PR #1 open/draft/unmerged — verified).
- Completed this segment (all committed):
  1. Evidence pipeline: detached-HEAD push defect FIXED in evidence-bridge.yml + rating-run
     evidence job (explicit refspec HEAD:refs/heads/$BRANCH, arena-branch safeguard, verified
     rebase-retry, bridge aggregate mirror); regression suite scripts/test_evidence_push.sh
     10/10; HOSTED VERIFICATION: evidence-bridge rev 3 run **43683839993 SUCCESS** — pilot,
     pilot-dup, CTRL-1, CTRL-2 evidence committed to the branch (2ec762e).
  2. Evidence recovery COMPLETE: all six datasets committed under benches/evidence/
     (pilot, pilot-dup, control/flawless-self, control/topple-0.1.1-vs-topple-0.2.1,
     screening/topple-0.1.1, screening/topple-0.2.1); every dataset independently
     re-aggregated from original run artifacts = committed bytes (hashes in AGENTS_LOG).
  3. Evaluations: pilot throughput 29.43/29.53 min/game; CTRL-1 PASS (−125.32 vs −115 → err
     −10.3 ≤ 75); CTRL-2 PASS after estimator metric fix (self-match must measure the SEAT
     perspective via recorded color_pair; focus matching case-insensitive; suite 65/65;
     threshold unchanged): 0.5146, CI [0.4792, 0.5500].
  4. SCREENING-1/2 evaluated per the registered rule: est ≈ 1632 Elo (scores 0.0208/0.0083);
     selection rule yields only wowl-1.3.7 non-saturating → Batch A/B DEFERRED (a doomed
     ~300-runner-hour campaign was NOT dispatched; compute not wasted).
  5. Root cause: ~95% of rating losses are FLAG FALLS; src/uci.rs clock_limits overspend
     (soft clamp 20–30_000 ms; hard=6×soft). ENGINE-1 reserve-bearing budget REGISTERED then
     implemented; cargo 35/35, fmt/clippy clean, test_match 104/104, estimator 65/65; bench
     signature UNCHANGED fc907eba40b7869f.
- IN FLIGHT (server-side, GitHub Actions): SCREEN-2 re-screening of the ENGINE-1 candidate —
  rev 9 run **43685671431** (vs topple-0.1.1, seed 20261123) + rev 10 run **43686056730**
  (vs topple-0.2.1, seed 20261124); 15 shards × 8 games each at 40/15; engine_sha256 "freeze"
  (runner build records the new candidate hash); expected wall time ≈ 4–9 h; the evidence job
  (fixed push path) auto-commits benches/evidence/screening-2/<anchor>/ when all 15 shards of
  a run succeed.
- Next exact actions (resume procedure):
  1. `git fetch && git log --oneline -5` — expect 2 evidence commits (screening-2 dirs) after
     the runs complete; verify run conclusions + artifacts (both runs must be SUCCESS).
  2. Verify each screening-2 dataset: strict re-aggregation from the 15 shard artifacts,
     byte-compare vs committed; check flag rate ≤ 10/120 (ENGINE-1 acceptance 4); measure the
     freeze hash from manifests and PIN it in PREREGISTRATION (SCREEN-2 result section).
  3. Evaluate: d̂ per anchor; est = mean(R_a + d̂_a); re-apply the UNCHANGED selection rule.
  4. If ≥3 non-saturating anchors: commit benches/gate-plan.json (rule-derived set + documented
     span interpretation) with the Batch A dispatch revision BEFORE any batch game; update
     dispatch.json (confirmatory, pinned hash, seeds 20261121/20261122, 255 shards × 8,
     suites batchA/batchB); dispatch Batch A then B progressively; re-run CTRL-2 self-match
     with the new binary (registered decision — see ENGINE-1 acceptance notes) before the gate.
  5. If still no compliant set: continue the §8 improvement cycle (next most promising
     independently testable improvement; do not tune to the screening outcome).
  6. Fresh CodeRabbit review at the exact final SHA; CI green there; final manifest.
- Missing evidence: SCREEN-2 results (in flight); new-candidate controls (CTRL-2 re-run with
  the new binary registered as pre-gate requirement); Batch A/B games + CIs; fresh final-SHA
  CodeRabbit review; final full CI.
## Execution state (2026-11-16, segment 22)

- **SCREEN-2R COMPLETE (VERIFIED PASS):** both anchors' 120-game canonical evidence committed
  (topple-0.1.1 via run 43714600687; topple-0.2.1 via merged runs 43714620645+43806800011,
  evidence commit 0cdeedf). Byte-match verified via BOTH download paths; flag losses 0/120
  and 0/120 (acceptance <=10 PASS); 0 engine errors; engine hash = pinned 9663697d... in
  every shard manifest. Corrected screening estimates (after the draw-scoring reporting fix,
  see FAILURE_LEDGER 2026-11-16 ~07:25Z): 2176.8 (topple-0.1.1) and 2236.4 (topple-0.2.1);
  combined est 2206.6 — SELECTION-ONLY, not a rating claim.
- **In flight (server-side):** CTRL-2-R rev 13 = run 43820392119 (self-match, flawless vs
  flawless, 120 shards x 2, seed 20261125; evidence -> benches/evidence/control/flawless-self-r/);
  SCREEN-3 rev 14 = run 43820645420 (akimbo-0.1.1, mechanical anchor choice |est-R|=234.4
  minimum, 60 shards x 2, seed 20261126; evidence -> benches/evidence/screening-3/akimbo-0.1.1/).
- **Gate tooling audited vs RATING_PROTOCOL §9 (VERIFIED PASS):** rating_estimator.py joint
  cluster bootstrap / sigma_matched-as-SD / GLS / shared-calibration batch combination;
  verify_evidence.py identity+count fail-closed; rating-gate.yml strictly->2000 decision on
  all three unrounded CI lower bounds; GLS fallback fails the gate by design.
- **NOT yet done (binary):** CTRL-2-R result; SCREEN-3 result; gate-plan.json commit; Batch A
  revs 15-18; Batch B revs 19-22; merge+verify; 2000 gate; audit closeout; final CodeRabbit
  review at final SHA; final CI matrix; Ready-for-review flip.

## 2026-11-17 — first hosted validation and follow-up

The first PR CI at `7d368cd` passed the Rust 1.80 MSRV job; Linux and Windows stopped at rustfmt in the newly added SEE helpers before tests. The formatter layout has been corrected. Anchor verification recorded the new deterministic depth-10 signature `141943aa23b3fc68`; its expected value has been updated, but the new candidate binary SHA-256 remains pending a successful verification rerun. The rating gate failed closed due to no gate plan, and rating-run skipped all shard jobs; no tournament was dispatched.

## 2026-11-17T10:31Z — validation checkpoint

- Current HEAD at checkpoint: fe6d34067e776ca64e676617c2102966675b4744 (PR open, draft, not merged).
- New RATING-100 selector verifier failure on CI run 44062359630 is contained: both operating systems passed Rust formatting, clippy, Rust unit tests and the Python regression suites, then failed at the exact deterministic opening-subset check. The suite-generator SHA-256 constant defect was fixed; corrected suite hashes are recorded in PREREGISTRATION.md and the machine report. Hosted verification on the corrected commit is pending.
- ENGINE-2 SEE ordering candidate: hosted PR merge-tree bench signature 141943aa23b3fc68, binary SHA-256 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7. This is a deterministic build identity, not an Elo, speedup or playing-strength result.
- RATING-100 remains BLOCKED. The rating gate failed closed because no gate plan/evidence exists; no confirmatory batch was launched.


## 2026-11-17 — exact-head build validation

At commit 5b63e273d77cfb097f0ad73bc28dda05cc19adad, hosted CI run 44066217195 passed on Ubuntu, Windows and Rust 1.80. The amended opening-suite verifier, Python harness/estimator/reduced-sample/dispatch-recovery tests, power-model smoke and engine release/UCI/perft checks all passed. Anchor-verification run 44066217113 succeeded 13/13; the exact source tree built binary SHA-256 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7 with bench signature 141943aa23b3fc68.

The RATING-100 power file is sourced from ENGINE-1 SHA-256 9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428. New manifest and dispatch guards prevent its reuse for ENGINE-2. ENGINE-2 has an identified binary, but its own screening and controls have not been run. RATING-100 remains BLOCKED and no confirmatory games have been dispatched.

## 2026-11-17T10:43Z — provenance guard validation correction

Commit 29b627e added ENGINE-1/ENGINE-2 binary isolation for RATING-100. The first CI rerun caught a regression-test expectation mismatch: an unknown engine hash is rejected by the explicit SCREEN-2 allowlist before the same-binary comparison. Production behavior is the intended stricter fail-closed result; the test expectation is being corrected. The commit is not yet CI-green. Anchor verification 44067364568 remains successful, and no tournament ran.

## 2026-11-17T10:47Z — Windows hash portability correction

CI on c564c5c passed Ubuntu but failed the Windows power-analysis smoke because Windows Git checkout changed raw SCREEN-2 JSONL line endings to CRLF while manifest merged_sha256 was created on Linux LF bytes. The next commit makes hash verification OS-independent by canonicalizing line endings only, retaining the exact JSONL records, and adds tamper/CRLF regression tests. The c564c5 CI run is not green; exact-head rerun pending.

## Session update 2026-11-17 (manual review fixes)

- PR head (code): `071f875`. Commits this session: `5980d53` (R-02, R-12), `81ad551` (R-03, R-10), `1ec9eeb` (R-07), `b39df4e` (R-08), `071f875` (R-05 tests).
- Manual review disposition: `REVIEW_MANUAL_071f875.md`. Of 15 findings: 7 fixed, 4 not reproduced, 4 accepted (unchanged).
- Gates at head: fmt clean, clippy `-D warnings` clean, 45/45 tests (+2 R-05 tests), DIFTEST default 2,321 positions 0 mismatches, perft subset exact, bench signature `141943aa23b3fc68` unchanged.
- Preliminary Elo (internal, not gate evidence): NOT MEASURED this session. No match runs were executed.
- Open: MSRV 1.80 unverified; ENGINE-1 hash no longer matches the code (decision needed); rating-gate fail-closed cause not investigated; R-08 residual overrun.

## 2026-11-18 — outpost pawn-attack defect found, EVAL-1 withdrawn, EVAL-2 dispatched

**The defect.** The outpost term used the wrong pawn-attack table in both of
its lookups. The pawn-attack table is directional — the squares from which a
pawn of colour C attacks square X are `PAWN_ATTACKS_[other(C)][X]` — and both
lookups read that other table. The term therefore asked "is this square
attacked by a pawn of the same colour as the piece?" twice instead of asking
"is it defended by ours?" and "is it attacked by theirs?". For a White piece on
d5 the defending White pawns stand on c4/e4 (`PAWN_ATTACKS_BLACK[d5]`) and the
attacking Black pawns stand on c6/e6 (`PAWN_ATTACKS_WHITE[d5]`); the code read
the opposite table in each case.

**Why it survived the gates.** The defect is symmetric under the board flip, so
the evaluator stayed antisymmetric and the antisymmetry gate was satisfied by a
wrong evaluator. A symmetry test cannot catch a defect that is itself
symmetric. A new gate, `outpost_requires_defence_and_safety_in_the_right_direction`,
exercises the two directions separately with four positions and was verified to
fail on the pre-fix source.

**Consequence.** The evaluation values change, so the tree changes: bench
signature `03e46bba31f35591` → `b58979ca90492208`, node count 3,445,466 →
3,666,233. Every EVAL-1 binary measured a different program from the tree, so
**the EVAL-1 campaign is withdrawn**. The withdrawn raw records are retained
unmodified under `/home/user/matches/eval-*-invalidated-outpostbug/` and are
explicitly not citable.

**Evaluation cost.** The evaluation was 24.5 % of node time and the
pawn-structure section about a third of the evaluation cost. Three
value-identical changes cut the evaluation cost by about 12 % (1219 ns → 1077 ns,
min of 20 runs over the four `bench_eval` positions): sharing the slider
attack masks between the mobility and king-safety terms, replacing the
per-pawn square-dependent recomputation with lookup tables, and stopping
`evaluate` from routing through the ten-component `breakdown` taper. The bench
signature and node count are unchanged, which is the proof that no evaluation
value changed.

**EVAL-2 dispatched** on 2026-11-18 with seven fresh binaries; see
`PREREGISTRATION.md` § "EVAL-2" for the pinned identities, the control
validity check, and the restated decision rules. The anchor-verify workflow's
pinned signature was corrected, and anchor verification now passes (run
44333865340, 13/13 anchors, `bench_signature=b58979ca90492208` recorded on the
runner).

**No strength claim is made from any of this.** SPEED-1 remains the only
KEPT screening result (+89 Elo, CI [+13, +168]); HIST-1 is INCONCLUSIVE; the
evaluation work remains unmeasured until EVAL-2 completes. PR #2 stays Draft
and `OWNER_TEST_PENDING` remains.

## 2026-11-18T15:20Z — EVAL-2 complete: the evaluation upgrade is INCONCLUSIVE

The seven-pair EVAL-2 ablation campaign finished: **560 games, zero engine
errors, every pair passing the schedule audit** (80 counted games, no
duplicate slots, 40 AB / 40 BA, 20 openings with 4 games each).

| Pair | Score | Elo diff | Elo CI |
|---|---|---|---|
| EVAL-NONE vs EVAL-ALL | 0.519 | **+13** | [−57, +84] |
| EVAL-NONE vs EVAL-NO-MOBILITY-TAPER | 0.419 | −57 | [−132, +9] |
| EVAL-NONE vs EVAL-NO-PAWN-STRUCTURE | 0.525 | +17 | [−30, +66] |
| EVAL-NONE vs EVAL-NO-PASSER | 0.506 | +4 | [−80, +89] |
| EVAL-NONE vs EVAL-NO-SPACE | 0.469 | −22 | [−84, +39] |
| EVAL-NONE vs EVAL-NO-OUTPOSTS | 0.469 | −22 | [−75, +26] |
| EVAL-NONE vs EVAL-NO-KING-SAFETY | 0.506 | +4 | [−66, +75] |

**Aggregate decision: INCONCLUSIVE.** The registered rule keeps the change
only if the CI lower bound is > 0 Elo and rejects it only if the upper bound
is <= 0; [−57, +84] contains zero. The evaluation upgrade is therefore **not
merged as a strength improvement**. The six feature flags stay in the tree as
measurement scaffolding, which the registered rule explicitly permits, and no
part of the evaluation is described as a strength improvement anywhere.

**Per feature:** none is flagged HARMFUL. Turning the mobility taper off is
70 Elo worse than keeping it on — the only comparison outside the 40-Elo
indeterminate band. The other five are within the band and are retained but
not claimed.

This is a screening result at a fixed 100 ms/move clock on a shared 2-vCPU
sandbox. It is **not** a rating, not a CCRL/CEGT result, and not an absolute
Elo claim. A confirmatory campaign with a larger sample would be needed to
settle the aggregate, and that is a separate registered experiment which has
not been run.

**Overall standing.** SPEED-1 remains the only KEPT screening result (+89 Elo,
CI [+13, +168]). HIST-1 is INCONCLUSIVE. The evaluation upgrade is
INCONCLUSIVE. The evaluation cost came down about 18 % across three
value-identical commits (1219 ns → 996 ns per evaluation), each verified by
an unchanged bench signature and node count. PR #2 stays Draft and
`OWNER_TEST_PENDING` remains. `benches/rating-100-power-assessment.json`
remains BLOCKED.

## 2026-11-19 — Phase B source audit of PR #2: three search defects fixed

The audit of `src/search.rs` against the PVS algorithm and the documented
move-ordering bands found three defects. Each fix ships with a regression
test that was verified to fail against the pre-fix source.

- **The PVS scout bound was used as a move score** (`708d53c`). The re-search
  that turns the null-window bound into a value was guarded by `reduction > 0`,
  so an unreduced non-first move kept its bound. The root score was then below
  the value of the best move in 7 of the first 8 Batch A positions at depth 2
  (gaps up to 172 centipawns) and the root could pick a worse move; the same
  defect made the engine claim `score mate 15` for a position that is not a
  forced mate. After the fix the root score is exact at depth 2 in every
  position, as it is in the pre-PR-2 baseline.
- **The move-ordering bands overlapped** (`61dd642`). A quiet move can score
  as low as 25_424 and a losing capture as high as 42_047, so a losing
  capture could outrank a quiet move; the promotion bonus pushed losing
  capture-promotions into the quiet band. The bands are now disjoint by
  construction.
- **The quiescence did not record its captures on the search path**
  (`018e920`), so its counter-move and continuation-history lookups used a
  stale previous move from the second quiescence level on.

Bench signature `b58979ca90492208` → `c64d148d39181140`; nodes 3,666,233 →
3,413,723. The `anchor-verify` workflow pins the signature and was re-pinned
in `50ec354`. Gates at `018e920`: fmt clean, clippy `-D warnings` clean, 67
Rust tests green, release build and bench green, the seven Python harness
suites green, CI and the Windows release artifact green.

**Consequence for the campaign.** The searched tree changed, so every binary
built from the pre-fix source is a different program. ENGINE-1 and the
CTRL-2-R / SCREEN-3 evidence describe the old source and are not evidence
about the candidate. EVAL-3 must run against the exact frozen candidate
binary under a newly registered campaign, as `docs/RATING_PROTOCOL.md`
already requires. `benches/rating-100-power-assessment.json` remains BLOCKED
and PR #2 remains Draft with `OWNER_TEST_PENDING` in force.

## 2026-11-19 — Phase C audit: mate-distance fix, and EVAL-3 confirms the audited tree is stronger

**The mate-distance defect (`32ad8ab`).** The mate-score band was `MATE_SCORE - 100` in three
modules while the search's ply limit is `MAX_PLY = 128`, so a mate 100 plies or more from the
root fell outside the band entirely. The transposition table then failed to recognise it as a
mate score, stored it in root-relative form, and returned it unchanged when the entry was probed
at a different ply — reporting the mate distance wrong by exactly the ply difference (a mate 101
plies away, re-used at ply 50, was reported as 101 plies away instead of 151). The UCI layer
printed the same class of score as `cp 29899` instead of a mate, and the search's null-move guard
shared the band and could attempt a null move with a mate beta.

The band is now `MATE_SCORE - MAX_PLY`, derived from the search's own ply limit and defined once
in `eval::MATE_BOUND`. The deepest checkmate node the search can reach is at `MAX_PLY - 1`, so the
new band covers every reachable mate score. The fix is behaviour-neutral for ordinary positions:
the depth-10 bench signature and node count are unchanged at `c64d148d39181140` / 3,413,723.
`tests/mate_distance.rs` adds eight regressions, four of which were verified to fail against the
pre-fix source. Rust test count 67 → 75.

**EVAL-3 (registered before dispatch).** The audited tree was screened against the pre-audit
tree, with both binary hashes, bench signatures and node counts pinned before any game:

| | Result |
|---|---|
| Games / counted / engine errors | 80 / 80 / 0 |
| Colour balance / openings | 40 AB / 40 BA / 20 distinct, 4 each |
| Audit verdict | PASS |
| Score | **60.5/80 = 0.756** |
| 95% CI for the score | **[0.662, 0.838]** |
| Elo difference | **+197** |
| 95% CI for the Elo difference | **[+117, +285]** |

The registered decision rule (95% CI lower bound > 0 Elo) is met with a wide margin: the three
search fixes are not only correctness fixes, they are worth roughly +197 Elo at a fixed 100 ms/move.
The numbers were reproduced by two independent code paths, and the raw evidence is preserved under
`benches/evidence/screening-eval3/`.

This is **screening evidence on a shared 2-vCPU sandbox at a fixed 100 ms/move time control**. It
is not a rating, it is not comparable to a campaign run on an idle machine or under the 40/15
clock, and it does not substitute for the >2,000 Elo gate.

**Consequence for the campaign.** The EVAL-3 result is evidence for the binary it was
played with. The mate-distance fix changes search behaviour outside the ordinary depth-10
benchmark — an unchanged bench signature and node count is a regression signal over the 12
bench positions only, and cannot rule out a changed evaluation or a changed search path on
positions the bench does not visit. EVAL-3 was played at a fixed 100 ms/move budget, where
the search is budget-limited rather than deterministic across builds, so the current tree is
not shown to produce the same games. The candidate's strength must therefore be re-established
on the frozen candidate binary before any confirmatory claim. `benches/rating-100-power-assessment.json`
remains BLOCKED, PR #2 remains Draft, and `OWNER_TEST_PENDING` remains in force.

## 2026-11-19 — confirmatory campaign compute-cost estimate (planning only)

The compute cost of the RATING-100 confirmatory campaign is now estimated from committed evidence
rather than left as a guess. `scripts/estimate_campaign_cost.py` reads the per-game wall-clock
records of SCREEN-2 (`topple-0.1.1`, `topple-0.2.1`) and SCREEN-3 (`akimbo-0.1.1`) — 120 counted
games each at the 40/15 repeating wall-clock time control — and verifies the frozen engine binary
SHA-256, the frozen anchor binary SHA-256, the opening-suite SHA-256, the attempt/count totals and
the merged raw-game digest before computing; any drift fails closed. The report is committed at
`benches/confirmatory-cost-estimate.json` and is pinned by `scripts/test_estimate_campaign_cost.py`
(26 checks, including that the report is non-authorizing and that it does not perturb the power
report or the dispatch marker).

| Quantity | Value |
|---|---|
| Campaign design | 600 counted games, 300 shard jobs, 6 dispatches |
| Game time | 571.1 runner-hours |
| Per-shard job overhead (measured, 35 s/job) | 2.9 runner-hours |
| **Total campaign runner-hours** | **574.0** (bootstrap p05 536.4, p95 614.0) |
| Wall-clock span, 40-way concurrency (observed) | 14.9 h |
| Wall-clock span, one dispatch wave at a time | 21.9 h |
| Probability a 2-game shard exceeds the 350-min timeout | 3.06 % |
| Notional standard-runner valuation | USD 206.6 (**USD 0 actual**: public repo, standard runners) |
| Candidate-specific screening (3 anchors × Batch A + Batch B, 600 games) | 571.1 runner-hours |
| Candidate-specific self-match null control (240 games) | 228.4 runner-hours |
| Anchor-vs-anchor null control | 0 — seats no candidate engine, committed evidence reused |
| **Gate-path prerequisites** | **799.5 runner-hours / 840 games** |
| **Grand total** | **1,373.5 runner-hours / 1,440 counted games** |

Two transfers behind these numbers are unmeasured and are recorded as assumptions, not facts: every
wall-clock measurement comes from the ENGINE-1 binary while the confirmatory campaign would run a
different candidate binary (no candidate-specific 40/15 timing evidence exists yet), and Batch B
has never been timed, so its durations are modelled as exchangeable with the anchor's observed
Batch A population. The 40-way concurrency figure is measured, not assumed: the account-wide peak
was exactly 40 concurrent jobs across the two overlapping screening/control runs.

**No gate changed.** `benches/rating-100-power-assessment.json` is still `BLOCKED` and still
guarded to the ENGINE-1 binary; no gate plan and no confirmatory dispatch exist. The fail-closed
requirements stand unchanged: candidate-specific controls and a reviewed candidate-specific power
PASS must exist before dispatch, exact identity and suite hashes are enforced by the dispatcher and
the resolver, exactly 600 counted games on 50 opening clusters are required, all three unrounded
Elo lower bounds must exceed 2,000, and PR #2 remains Draft and is never merged automatically.

## 2026-11-19 — CodeRabbit findings addressed; Windows packaging now verified

Head `ab690a9` (branch `arena/8259ce1c-flawlesschess`). Exact-head workflow state, API-verified:

| Workflow | Run | Outcome |
|---|---|---|
| CI | 44507672695 | success |
| anchor-verify | 44507672491 | success |
| evidence-bridge | 44507672786 | success |
| Windows Release Artifact | 44507672251, 44507655514 | success |
| rating-gate | 44507672468 | failure — **expected**: it fails closed while `benches/gate-plan.json` does not exist |

**What the review found.** CodeRabbit's eight findings at head `92ae065` were all on pre-existing
files; none touched the new cost estimator. Two were real defects in the tooling and are now fixed:

- `scripts/audit_pair.py` accepted a schedule that reversed **no opening**. The old check was a
  global AB/BA balance, a total game count and a per-opening multiplicity — ten AB-only and ten
  BA-only openings satisfy all three (40/40) while reversing nothing. Reproduced: the old audit
  printed `verdict: PASS` on exactly that evidence. The audit now validates the actual
  `(opening, repetition, color_pair)` slots against the registered schedule, requires every slot to
  carry both colours, and requires contiguous repetition indices `0..n-1` for every opening. The
  registered 20 × 2 × 2 schedule is still accepted; the real EVAL-3 evidence still passes at
  60.5/80 = 0.7562. `scripts/test_audit_pair.py`: 22 → 34 checks.
- `scripts/collect_eval_results.py` could print a registered `KEPT` decision on evidence that had
  **failed its audit**. Both decision paths now require `audit == "PASS"` and report `UNAVAILABLE`
  otherwise; failed results are still kept for diagnostics. New suite
  `scripts/test_collect_eval_results.py` (15 checks).

The remaining findings were over-claims and one data-integrity error, all corrected:
`BENCHMARKING.md` now carries the EVAL-2 identities pinned before dispatch rather than two
withdrawn EVAL-1 ones and is labelled EVAL-2; the fixed-depth bench signature is described as a
regression signal over the 12 bench positions rather than proof of evaluation equivalence; the
claim that the EVAL-2 campaign's games are the current tree's games is withdrawn (that campaign ran
under a fixed 100 ms/move budget, where the search is budget-limited, not deterministic across
builds); the shared-load assumption is carried as an uncertainty rather than asserted; and the
EVAL-3 result is attributed to the binary it was played with.

**Windows packaging is now true rather than asserted.** The "no extra runtime DLLs" claim was
false: the Rust MSVC target links the C runtime dynamically by default. The release build now
links the CRT statically (`-C target-feature=+crt-static`) and a new step *verifies* it —
`scripts/pe_imports.py` parses the produced PE import table and the workflow fails the build if
any C-runtime DLL is imported. The Windows run above confirms it: the static-CRT build succeeds,
the import check reports no C-runtime dependency, and the UCI handshake, bestmove, perft and bench
checks all still pass. `scripts/test_pe_imports.py` (12 checks) exercises the parser against a
synthetic but structurally valid PE32+ image and against non-PE and truncated inputs.

**Consequences.** The Windows artefact's bytes change with the static-CRT link, so the owner's
pending Windows acceptance must be redone against the new artefact. The **Linux candidate binary is
unaffected**: `src/`, `tests/`, `Cargo.toml` and `Cargo.lock` are untouched and `RUSTFLAGS` is set
only in the Windows workflow, so candidate SHA-256
`0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5` and bench signature
`c64d148d39181140` still identify the same program.

**No gate changed.** `benches/rating-100-power-assessment.json` is still `BLOCKED` and still guarded
to the ENGINE-1 binary; no gate plan and no confirmatory dispatch exist; `benches/dispatch.json` is
untouched. Candidate-specific controls, a reviewed candidate-specific power PASS, exact identity and
suite hashes, exactly 600 counted games on 50 opening clusters, and three unrounded Elo lower bounds
above 2,000 all remain required before any dispatch. PR #2 remains Draft and is never merged
automatically.

## 2026-11-19 — minimum candidate-specific control set reviewed; self-match criterion strengthened

Reviewing which null controls the candidate actually needs required re-aggregating the committed
control evidence with the **registered** tool (`scripts/rating_estimator.py control`), and the two
§5 controls turned out to have very different robustness properties.

| Control | Decision rule | Seed-dependent? | Committed verdict | Reuse for the candidate? |
|---|---|---|---|---|
| Anchor-vs-anchor (CTRL-1) | measured point estimate vs published difference, ±75 Elo | **No** — no bootstrap interval | PASS, error **−10.32** Elo | **Yes** — seats no candidate engine, 0 new games |
| Self-match (candidate) | percentile cluster-bootstrap 95 % CI contains 0.5 | **Yes**, at the boundary | — | **Must be re-run** — seats the candidate |

CTRL-1 reproduces identically for 40 bootstrap seeds (`d_measured = -125.3211`, `error = -10.3211`,
PASS), so its committed evidence is valid and is reused.

The self-match control's verdict is **not** seed-independent near the rejection boundary. The
committed CTRL-2-R evidence (ENGINE-1, 240 games, 60 clusters, seat-A score 0.460417) gives:

| Seed | 95 % CI | Verdict |
|---|---|---|
| 20261114 (registered) | [0.4208333333, **0.4979166667**] | **FAIL** — CI misses 0.5 |
| 20261125 (dispatch seed) | [0.4208333333, **0.5**] | PASS — CI contains 0.5 |

Across 300 consecutive seeds it gives 177 PASS / 123 FAIL. The cause is structural: with *n*
clusters of four games the bootstrap mean lives on a grid of 1/(8n), and this data's 97.5 %
percentile falls at ≈ 0.4992 — *between* the grid points 0.4979167 and 0.5 — so the discrete rank
index lands on one or the other depending on the seed. More replicates do not help (flip rate
58 % / 45 % / 54 % at 1,000 / 10,000 / 50,000 replicates), and the flip band is ≈ ±0.027 SE
independently of the control size.

**Every recorded verdict stands unchanged.** CTRL-2-R is still FAIL and ENGINE-1 is still
disqualified as a rated candidate; the pre-ENGINE-1 self-match still passes and passes
*unanimously* (16/16 registered seeds); CTRL-1 still passes. The finding characterises the
ENGINE-1 result as a borderline outcome (clustered z ≈ −2.00 against a 1.96 threshold) of a
knife-edge test, not as evidence that the binary is colour-biased.

**Registered prospectively** (before any candidate control is dispatched): the self-match verdict is
certified across the registered seed set `20261114 … 20261129`; a verdict that is not unanimous is
reported as **NOT ROBUST** and the gate treats the control as **unavailable** — never as PASS and
never as FAIL, so the amendment can never rescue a failing control. The registered control sizes are
unchanged (240 games each); the certification, not a larger control, is what makes the rare
ambiguous case safe. `scripts/rating_estimator.py` now reports `seed_robust` for both null
controls and the gate requires it; `scripts/test_rating_estimator.py` grows from 65 to 83 checks,
including a reproduction test pinning the committed CTRL-1 and CTRL-2-R numbers.

**Minimum candidate-specific control set (final).** The candidate needs (1) 600 screening games
covering all three anchors on both Batch A and the disjoint Batch B — 571.1 runner-hours, which is
also what turns the currently-modelled Batch B distribution into a measurement — and (2) a
240-game candidate-specific self-match control — 228.4 runner-hours — which must additionally
report `seed_robust: true`. The anchor-vs-anchor control needs **0** new games. Gate-path total
**799.5 runner-hours**; grand total **1,373.5 runner-hours / 1,440 counted games**.

No gate changed: the power report is still `BLOCKED` and ENGINE-1-guarded, no gate plan or dispatch
exists, PR #2 remains Draft, and the candidate-specific controls, the reviewed candidate-specific
power PASS and the three unrounded Elo lower bounds above 2,000 all remain required before any
dispatch.

## 2026-11-18 — candidate qualification design and evidence isolation implemented

Registered the candidate-specific screen and self-control design before any candidate game in
`benches/candidate-qualification.json` and appended the human-readable amendment to
`PREREGISTRATION.md`. The registration binds binary SHA-256
`0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5`, bench signature
`c64d148d39181140`, both disjoint 50-opening RATING-100 suites, three anchors, the 40/15 `add`
clock, deterministic AB/BA schedule and seed labels, exactly 600 screening games, plus a distinct
240-game self-match and all 16 registered robustness seeds. Screening is selection-only and cannot
be counted as gate evidence. Historical generic evidence roots and ENGINE-1 self-control are
explicitly excluded; the valid anchor-vs-anchor control remains reusable at zero new games.

The hosted rating workflow now recognizes candidate-only purposes, verifies the design and suite
hashes, requires the exact candidate binary and full target commit, exact batch/anchor/sample/clock
parameters, refuses an already-existing candidate evidence destination before starting a runner,
and writes immutable evidence under the candidate-SHA-qualified paths. `aggregate_shards.py` now
records candidate identity/provenance and checks exact counted schedule coverage, suite ordering,
AB/BA seats, repetitions, engine seats and identities. Added
`scripts/certify_candidate_control.py` to verify the self-control manifest and evidence before
running the registered 16-seed estimator certification; it emits no dispatch authority and requires
all seeds to PASS, not merely a `seed_robust` flag that can also represent unanimous failure.

New regressions cover preregistration immutability, candidate path separation, exact counts, schedule
identity, self-control manifest and seed robustness. All 15 Python suites passed locally; workflow
YAML and three embedded Python blocks parsed/compiled; `git diff --check` passed. The current
candidate dispatch marker remains historical SCREEN-3 and was not changed. No games were run and no
evidence was created. The committed historical power report remains ENGINE-1-only and BLOCKED. Candidate-aware power
and cost-analysis modes are now implemented: both fail closed until all six candidate screening
cells and the unanimous candidate self-control certificate exist; their outputs are explicitly
non-authorizing. No candidate evidence exists yet, so no candidate assessment has been produced.
Independent power review, the pre-Batch-A gate plan and exact confirmatory keys/§2-span registration
remain unfinished. No confirmatory dispatch is authorized.
Owner Windows acceptance and exact-head CodeRabbit recheck remain outstanding; PR #2 remains Draft.

## 2026-11-19 — continuation local audit

Further local-only review tightened candidate evidence retry provenance: all attempts now need the registered slot/opening/seat/shard identity, and retries must follow a failed engine-error attempt. Candidate campaign cost accounting now includes failed-attempt wall time. The Windows release workflow now verifies the actual ZIP and smoke-tests the extracted executable; the seven package-verifier regression tests pass locally, but the new runner step is unverified. All 17 Python suites pass locally, six workflow YAML files parse, 7 unique embedded Python heredocs compile, and candidate-plan validation passes. No hosted workflows or experiments were launched. The rating remains **not yet measurable from valid evidence**; PR #2 remains Draft and no release gate is passed.
