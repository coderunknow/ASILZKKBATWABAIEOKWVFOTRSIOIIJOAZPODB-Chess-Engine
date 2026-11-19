# RATING_PROTOCOL — Pre-registration for the V1 release gate (≥ 2,000 Elo, absolute)

**Status: PREREGISTERED, NOT EXECUTED.** This document fixes the methodology BEFORE any rating run.
Date of pre-registration: 2026-11-14. If this protocol is ever amended, the amendment must be a new
append-only commit that supersedes this section, with reasons — never an in-place edit.

## 1. Objective (binary)

V1 may be tagged only if the two-sided 95% confidence interval of Flawless's **calibrated absolute
rating** has a **lower endpoint ≥ 2,000 Elo** against a credible, documented pool. One batch is never
enough; at least **two independent confirmation batches** are required, each satisfying the bound,
and the combined estimate must also satisfy it.

## 2. Pool requirements (all mandatory)

- Rated opponents from an authoritative, documented source (CCRL 40/15 list, or CEGT 40/20 — one
  scale only; no cross-scale pooling). Blitz-only sources are not acceptable for a 40/15-style claim.
- Each anchor: exact name, version, **binary SHA-256**, its published Elo and its published ± error at
  the list's time control, list publication date, and retrieval date. Stockfish "Skill Level" settings
  are NOT an Elo anchor and may not be used for the gate.
- ≥ 3 anchors spanning at least the interval [estimate − 200, estimate + 200], and ≥ 1 anchor below
  every plausible gate-failing value and ≥ 1 above every plausible gate-passing value.

## 3. Match design (fixed in advance)

- Time control: as close to the anchor list's control as hardware allows (target CCRL 40/15-class;
  document the actual control; do not mix controls in one batch). Fixed-movetime runs may be used for
  *screening only* and never for the gate.
- Openings: a fixed public opening suite, minimum 60 distinct lines (≥ 4 plies each), FEN-verified,
  drawn from a published source (suite name + hash). Every opening is played as a pair (colors
  reversed). Opening list identical across batches and opponents.
- Color balance: exact AB/BA reversal for every opening pair.
- Hardware/software: reference behavior must run on one documented machine class; record CPU, RAM,
  OS, commit SHA of the engine, and every nondeterminism source. Record NPS of both engines.
- Game adjudication: standard FIDE termination rules + claimable 50-move/3-fold claims enforced by
  the arbiter; flag-on-time → loss; crashes/timeouts of OUR engine → game recorded as engine_error and
  **replayed**; after 2 such failures at the same anchor the batch is aborted as invalid. Opponent
  crashes are recorded and the game repeated (or the anchor dropped and replaced per §2 — never silently
  rescored).
- Raw evidence: every game as PGN + one JSONL line (opening, colors, result, reason, wall time,
  engine-error flags, node counts). Evidence directory committed under `benches/rating-<batch>/` with
  `meta.json` (config, hashes, seeds).

## 4. Statistical method (fixed in advance)

- Per-anchor game score s_a = (wins + 0.5·draws)/n_a. Pairing by opening; cluster = opening (both
  colors). Confidence intervals by **cluster bootstrap** (10,000 resamples, fixed seed 20261114),
  not by treating games as iid.
- Absolute anchoring: estimate absolute Elo(Flawless) by weighted least squares on anchor points
  (Flawless − anchor Elo differences vs anchor Elo), weights = 1/(clustered-CI half-width)².
- Calibration uncertainty propagation: anchor published ± values included in the variance budget
  (add anchor variance in quadrature to the clustered-CI variance, then re-scale). Report both:
  (a) CI using match noise only; (b) CI including anchor calibration error. **Gate requires (b) ≥ 2,000.**
- Two confirmation batches (≥ 1,000 games each per batch at screening-grade only if batch A already
  clears; otherwise ≥ 2,000 each). Batch B must use the same anchors but a **disjoint shuffled
  sub-suite** of openings and a different fixed bootstrap seed, and must reproduce the bound independently.
  Combined estimate = inverse-variance weighted mean of the batch estimates.
- Decision rule: PASS iff (i) both batches individually show lower endpoint ≥ 2,000 (anchor-calibrated CI),
  (ii) combined shows lower endpoint ≥ 2,000, (iii) no anchor used as gate evidence has
  |Flawless − anchor| > 400 Elo (else the anchor saturates and must be replaced), (iv) all evidence
  committed and reproducible. Otherwise FAIL/INCONCLUSIVE — never a partial credit.

## 5. Null controls (anti-self-deception)

- Opponent-vs-opponent control batch (e.g. anchor₁ vs anchor₂) must recover their published Elo
  difference within ±75 Elo; otherwise the measurement system is broken and no Flawless number may be
  reported.
- Engine-vs-itself with swapped colors must score within the binomial CI of 0.5.
- Any result failing a null control invalidates the affected batch entirely.

## 6. Exclusions and hygiene

- Never tune engine parameters, openings, or anchor selection to change the outcome after seeing results.
- Never exclude games because of their outcome; only engine_error games (§3) may be excluded, and the
  exclusion count must be printed with the result.
- Never present in-sandbox Stockfish-Skill-Level probes as absolute Elo.
- Never claim an official CCRL/CEGT rating; the output is a private, CCRL/CEGT-anchored estimate and
  must be labeled as such wherever published.
- Failures and null-control violations are recorded in FAILURE_LEDGER.md.

## 7. Current execution state (2026-11-14)

**NOT EXECUTED — BLOCKED.** No calibrated anchor binaries or documented-rating opponent pool with
verifiable Elo are obtainable from this sandbox (network restricted to github.com/api.github.com/
codeload/npm/pypi; CCRL/CEGT list pages with methodology are readable only where allowed, and no
ratable opponent binary can be legally/technically fetched and verified here; multi-thousand-game
matches exceed sandbox compute). Everything outside this gate continues; the V1 gate remains open.
Next action: run §3–§6 on a machine with access to ratable opponents (e.g. CEGT-rated binaries from
their official distributed packages, or CCRL-anchored opponents distributed with documented Elo), then
commit `benches/rating-batchA/` and `benches/rating-batchB/`, update STATUS.md with exact numbers and
CIs, and only then reconsider release authorization.

## 8. Amendment (2026-11-14) — pre-registration clarifications, no methodology change

Append-only amendment per the amendment rule above. Reasons: CodeRabbit review on `13a316e`
identified two §3↔§4 contradictions and an under-specified equation; this section supersedes only
those points and changes nothing else.

1. **Openings: identical within a batch, disjoint across batches.** §3's "Opening list identical
   across batches and opponents" is superseded and contradicted by §4; the governing rule is:
   - Within one batch, every anchor and the null controls face the **same** pre-registered suite,
     playing the **same** AB/BA pairs (required for anchor comparability and for the
     opponent-vs-opponent control in §5).
   - **Batch B uses a disjoint, pre-registered opening suite** (no line shared with batch A), with a
     different fixed bootstrap seed. The combined estimate is then not suite-specific. Amended §4
     text stands; amended §3 text is void to this extent.
2. **Absolute-anchoring equations, made explicit.** For anchor *a* with published rating R_a ± ε_a
   (published error, same control), per-anchor score s_a (0 < s_a < 1):
     d_a = −400 · log10(1/s_a − 1)                       (Flawless − a, Elo points)
     σ_a² = σ²_matched,a + ε_a²                           (quadrature; σ_matched from the clustered
                                                           bootstrap CI of d_a, i.e. transform both
                                                           CI endpoints through the logistic and use
                                                           the half-width)
     Flawless ≈ Σ_a w_a (R_a + d_a) / Σ_a w_a,            w_a = 1/σ_a²
     Var(Flawless) ≈ 1 / Σ_a w_a.
   Report both CI variants of §4. Anchors with |d_a| > 400 saturate and are excluded from the gate
   (they remain valid for screening, labeled as such).
3. **Zero and perfect scores.** s_a = 0 or s_a = 1 carries **no finite estimate**: record the anchor
   as a boundary result (unbounded d_a), exclude it from the WLS (no finite point exists), and treat
   the anchor as ineligible for gate evidence; replace it with an anchor nearer the current
   estimate. Never report clamped values (e.g. "+2400") as point estimates. Bootstrap CIs that
   include 0 or 1 are reported as boundary endpoints, not clamped numbers. `scripts/stats.py`
   implements exactly this for descriptive statistics; the gate computation in §4 inherits the rule.
4. **Everything else in §§1–7 is unchanged.** In particular the two-sided 95% CI lower-endpoint
   ≥ 2,000 requirement and the no-official-rating labeling remain absolute.

## 9. Amendment (2026-11-14) — acceptance-gate hardening + estimator corrections

Append-only amendment per the amendment rule at the top of this file. The original
preregistration (§§1–7, pre-registered 2026-11-14) and Amendment §8 are preserved verbatim and
remain in force except where this section explicitly supersedes them. Two reasons for this
amendment:

- **Reason 1 (governance).** The release-gate owner hardened the acceptance criteria for the
  V1 > 2,000 Elo mission: the pass threshold is now strictly greater than 2,000 Elo on the
  lower bound of a two-sided 95% confidence interval, both confirmation batches must pass, the
  combined estimate must pass, and each batch must include at least 2,000 completed games per
  anchor. The original §1/§4 wording ("≥ 2,000", and a 1,000-game screening tier) is superseded
  by items 1–4 below.
- **Reason 2 (methodology).** CodeRabbit review 5903125228 (2026-11-14T08:24Z, head
  `f07c46337e6cafd84cd73357145810c3b017ce15`) identified three defects in the estimator
  definitions, adopted here as items 6–8: (i) σ_matched was defined via the bootstrap CI
  half-width instead of a standard deviation; (ii) anchor estimates were combined as
  independent despite sharing the opening-suite difficulty; (iii) batch combination ignored the
  fact that both batches reuse the same published anchor ratings, so their calibration errors
  are shared and must not be inverse-variance-pooled away.

Superseded text, in full, and its replacements:

1. **Acceptance threshold: strictly greater than 2,000.** §1 and §4 pass conditions now read
   "> 2,000 Elo", not "≥ 2,000 Elo". A lower confidence endpoint exactly at 2,000.0 Elo is NOT
   a pass. All acceptance decisions use unrounded values; rounding is never applied to a
   pass/fail decision.
2. **Both batches and the combined estimate must pass.** The gate requires ALL THREE:
   Batch A two-sided 95% CI lower bound > 2,000; Batch B two-sided 95% CI lower bound >
   2,000; combined estimate two-sided 95% CI lower bound > 2,000 — each including
   anchor-calibration uncertainty. Failure of any one is FAIL/INCONCLUSIVE. §4's decision rule
   (i)–(iv) is amended accordingly and remains a conjunction, never a summary.
3. **Minimum evidence per batch.** Each confirmation batch must contain at least **2,000
   completed games per eligible anchor** (≥ 6,000 games per batch with the three-anchor pool).
   The "≥ 1,000 games (screening-grade)" tier in §4 is void. Anchors must be verified per
   §2 before contributing games; an anchor failing verification cannot contribute to either
   batch and cannot be replaced mid-batch after seeing its results (§6).
4. **No predictions; no boundary clamping.** A rating may be reported only from completed,
   adjudicated games. Predicted, extrapolated, pattern-estimated, or clamped values (e.g.
   "1.000 score → +2400") are never estimates and never appear as point estimates or interval
   endpoints. Boundary outcomes (score exactly 0 or exactly 1) are recorded as
   non-finite/uninformative results; the anchor is then ineligible for gate evidence and must
   be replaced by a nearer calibrated anchor. This restates §8.3 and extends it to every
   reported number, including batch-level and combined summaries.
5. **Sequential stopping and sample extension.** The sample size per anchor per batch (≥ 2,000)
   is fixed before Batch A starts and does not move during collection. If either batch fails
   the gate, the remedy is a NEW pre-registered batch on fresh openings with its own seed —
   never "more games until the interval clears" on the same batch with the same decision rule.
   Any optional interim analysis uses an error-spending (Lan–DeMets alpha-spending)
   sequential procedure fixed in advance, or Bonferroni correction across the planned number
   of looks; naive repeated testing at nominal 95% is invalid and invalidates the batch.
   After an amended plan with an explicit error-spend schedule is committed, the batch may
   extend in fixed increments (e.g. +200 games per anchor) with always-valid p-values
   (mixture methods); unplanned extensions keep the original 95% gate and are reported as
   exploratory, never as the confirmatory result. Engine binaries, openings, anchors,
   time controls, and seeds never change between the interim look and the extension except as
   committed in that pre-registered amendment.
6. **σ_matched is a standard deviation, not a CI half-width.** For anchor *a*, from the joint
   cluster bootstrap replicate set of the Flawless−anchor Elo differences
   d_a^(1..B):  σ_matched,a = SD(d_a^(1..B)) (sample standard deviation across the B joint
   replicates; B ≥ 10,000, fixed seed). Published anchor errors ε_a are expressed on the same
   SD scale: an error published as a 95% normal half-width is divided by 1.96; an error
   already published as a standard deviation or standard error is used as-is; any other
   published coverage convention is converted with the matching quantile (e.g. /1.645 for 90%,
   /2.576 for 99%) and the convention is documented per anchor. σ_a² = σ_matched,a² + ε_a²
   (quadrature), superseding the half-width construction in §8.2.
7. **Covariance-aware anchor combination.** Anchor estimates d_a share the opening-suite
   difficulty, so their match-noise components are correlated even though the anchors'
   published-rating errors are independent. Combine anchors with generalized least squares
   over the joint bootstrap: in each joint replicate, resample opening clusters ONCE and
   recompute every anchor's d_a, yielding the B×A replicate matrix D and the match-noise
   covariance matrix Σ_m = Cov(D) (A = number of anchors). Calibration covariance
   Σ_c = diag(ε_a²) (published anchor errors treated as mutually independent across lists;
   if two anchors share one list and overlap its uncertainty, record and add that covariance
   off-diagonal). Total covariance Σ = Σ_m + Σ_c. The absolute estimate is
   Flawless = (1ᵀ Σ⁺ (R + d)) / (1ᵀ Σ⁺ 1) with pseudo-inverse Σ⁺ (Σ is positive-definite in
   practice; use an explicit check and fall back to the diagonal WLS of §8.2 with a printed
   warning if the joint bootstrap is degenerate). Var(Flawless) = 1 / (1ᵀ Σ⁺ 1). Report
   match-only and match+calibration intervals separately. Supersedes the diagonal-weighting
   sentence of §4 and the weight definition w_a = 1/σ_a² in §8.2.
8. **Batch combination retains shared calibration uncertainty.** §4's "Combined estimate =
   inverse-variance weighted mean of the batch estimates" is void as written. Both batches
   reuse the same published anchor ratings, so their calibration-error component is shared and
   does not decrease by pooling. Compute per batch b ∈ {A, B}: estimate θ_b, match-only
   variance v_b (anchor-calibration excluded), and the common calibration variance c (from
   item 7's GLS, identical anchors). Combined match-only variance
   v = (1/v_A + 1/v_B)⁻¹; combined estimate
   θ = (θ_A/v_A + θ_B/v_B) / (1/v_A + 1/v_B). Combined interval: θ ± 1.96·sqrt(v + c).
   The match-noise components pool inverse-variance; the calibration component is added ONCE.
   Batch A and Batch B are always reported separately as well.
9. **Records.** Every gate run appends: SHA-256 of the engine binary and of every anchor
   binary, git commit, full anchor references with retrieval dates, hardware/OS, time control,
   suite name + hash, game counts, W/D/L, bootstrap seed, and the null-control outcomes —
   committed under `benches/rating-<batch>/` with raw PGN and JSONL. A third party must be
   able to recompute every reported number from the committed evidence alone.

Everything else in §§1–8 stands unamended. In particular §5 null controls
(opponent-vs-opponent within ±75 Elo of the published difference; engine self-match with
reversed colors consistent with 0.5; any failed null control invalidates the affected batch)
and the exclusions of §6 remain absolute.


## Append-only sample-size amendment — 2026-11-16 (RATING-100)

This amendment supersedes only the larger per-anchor sample-size floor for future BATCH-A/B confirmatory runs. It does not rewrite earlier protocol clauses or historical registrations.

- A new batch/anchor evidence set must contain exactly 100 counted games on 50 distinct opening clusters. Each cluster has exactly two counted games: one AB and one BA color reversal. Attempts caused by engine errors remain uncounted and retain the existing replay rules. Unadjudicated records remain uncounted.
- Batch A and Batch B use precommitted disjoint 50-opening subsets derived from the original Batch A and Batch B suites. The same mechanically selected anchor set is required in both batches. Actual suite bytes and SHA-256 hashes are frozen before dispatch.
- For three eligible anchors, the expected total becomes 3 × 2 batches × 100 = 600 counted games, versus the historical 12,240-game design (95.0980% reduction).
- All non-sample-size requirements remain unchanged: 40/15 repeating wall-clock time control; exact binary identity and SHA-256 verification; FIDE adjudication/replay treatment; joint opening-cluster bootstrap; GLS; calibration uncertainty conversion and propagation; shared calibration uncertainty across batches; both null controls and their thresholds; and the strict, unrounded two-sided 95% calibrated CI lower-bound requirement for Batch A, Batch B and combined estimate, each strictly greater than 2,000 Elo.
- The actual evidence verifier must validate 100 counted schedule indices exactly once, all 50 opening labels, and one AB plus one BA counted game per opening. Scheduled-attempt totals alone are insufficient.
- Prospective power status is currently BLOCKED in benches/rating-100-power-assessment.json: only two anchors have complete screening distributions on the selected 50-opening subset, while the third-anchor covariance and the disjoint Batch-B cluster distribution remain unobserved. The sensitivity model is not a substitute for the actual bootstrap and cannot authorize dispatch. The dispatch tooling rejects confirmatory execution until a committed, evidence-backed power assessment explicitly marks eligibility true.

The 2026-11-14 BATCH-A/B entries remain immutable historical records. This amendment does not permit reuse of screening games as confirmation evidence, does not weaken the confidence-bound rule, and does not authorize a confirmatory run while the power assessment is BLOCKED.

- **Partial-slot recovery (RATING-100 implementation note, 2026-11-17):** a shard may have one counted AB/BA leg and a missing other leg after an interrupted/aborted attempt. Recovery must schedule only the missing frozen `schedule_index`, not rerun the complete two-game shard. The match runner accepts an explicit sorted set of schedule indices constrained to its deterministic shard slice; the dispatcher derives missing indices from committed run manifests. Canonical aggregation still requires every counted schedule index 0–99 exactly once, exactly the registered 50 opening clusters and one counted AB plus one counted BA record per cluster. Duplicate counted indices, identity drift and wrong time controls fail closed.
- **Evidence capture default:** rating-run configs that omit `run_evidence` now default to evidence capture on; only explicit false disables the evidence job. This does not retroactively repair runs whose evidence jobs were skipped.


### RATING-100 suite-byte correction — 2026-11-17 (append-only)

CI run 44062359630 rejected the initially generated reduced suite files because their selection generator used an incorrect SHA-256 helper. Those bytes are superseded. The canonical selection is the output of Python `hashlib.sha256` using the domain-separated selector and original-order retention described in PREREGISTRATION.md. The currently registered bytes are Batch A `5abdcdbddec0f22d7e6eff8974ee402363c8c3df318b8110d7204adf69f5c1df` and Batch B `ccb4901742eca25b0b10f1a3c9fdfc17b2967a1939c2d7e466c2c5495b6d4253`. `scripts/verify_opening_subsets.py` recomputes the selection and fails closed on any changed line, ordering, hash or cross-batch overlap. This correction does not authorize any confirmatory dispatch; prospective power remains BLOCKED.


### Engine-binary provenance guard for the prospective power report — 2026-11-17

The committed RATING-100 sensitivity report is derived from SCREEN-2 / ENGINE-1, whose frozen binary SHA-256 is 9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428. The power-analysis script verifies both screening manifests, their merged raw-game hashes, the registered suite hash, the 120/120 attempt/count totals, the same binary hash and the two registered anchor identities before producing the report. The report records that engine SHA.

Both make_batch_dispatch.py and the confirmatory resolver in rating-run.yml require the report's engine SHA-256 to equal the binary SHA requested for dispatch. Reusing this report for ENGINE-2 or any different binary fails closed. ENGINE-2's binary identity is now measured, but its candidate-specific screening, controls and prospective power assessment have not been run; no games are authorized by this note.


### Confirmatory campaign compute-cost estimate — 2026-11-19 (append-only, planning only)

`scripts/estimate_campaign_cost.py` estimates the compute cost of the RATING-100 confirmatory
campaign from the committed per-game wall-clock evidence. It reads the SCREEN-2 (`topple-0.1.1`,
`topple-0.2.1`) and SCREEN-3 (`akimbo-0.1.1`) records, each 120 counted games at the 40/15
repeating wall-clock time control, and verifies the frozen engine binary SHA-256, the frozen
anchor binary SHA-256 from `benches/anchor-pool.json`, the opening-suite SHA-256, the
attempt/count totals and the merged raw-game digest before it computes anything; any drift fails
closed. The generated report is committed at `benches/confirmatory-cost-estimate.json` and is
reproduced by `scripts/test_estimate_campaign_cost.py`.

For the registered design — exactly 100 counted games per anchor per batch, 50 opening clusters,
one AB and one BA leg per cluster, three anchors, two batches, therefore 600 counted games in 300
shard jobs — the estimate is:

- **574.0 runner-hours** in total (bootstrap p05 536.4, p95 614.0): 571.1 h of game time and 2.9 h
  of per-shard job overhead, measured at 35 s per job by matching 60 hosted shard jobs against
  their recorded per-game wall time.
- **Wall-clock span** 14.9 h at the 40-way account concurrency observed across the completed
  screening and control runs, and 21.9 h if the six dispatches are executed one wave at a time.
  Concurrency was measured, not assumed: the account-wide peak was exactly 40 concurrent jobs
  across two overlapping runs.
- **Shard-timeout risk**: the bootstrap probability that a two-game shard exceeds the
  350-minute job timeout is 3.06 %. An exceeded shard fails and is re-run into a fresh output
  directory, costing a further pair of games.
- **Money**: the repository is public and the campaign runs on standard GitHub-hosted runners
  (`ubuntu-24.04`), so the metered runner-minutes carry no charge. The notional valuation at the
  published standard-runner rate is USD 206.6 for the campaign and USD 494.5 for the full
  gate-path program; runner-hours and wall-clock span are the meaningful cost quantities.

The candidate-specific evidence that must exist before any dispatch is costed separately at
**799.5 runner-hours over 840 games**: 600 screening games covering all three anchors on both the
Batch A 50-opening subset and the disjoint Batch B 50-opening subset, which is what turns the
currently-assumed Batch B distribution into a measurement, plus a candidate-specific self-match
null control. The anchor-vs-anchor null control seats no candidate engine, so its committed
evidence remains valid and is reused; no new games are needed for it. The full gate-path program
is therefore 1,373.5 runner-hours over 1,440 counted games.

This estimate is a **planning diagnostic and authorizes nothing**. It does not change the status
of `benches/rating-100-power-assessment.json`, which remains `BLOCKED` and remains guarded to the
ENGINE-1 binary SHA-256; it creates no gate plan and no dispatch marker. The fail-closed
requirements of this protocol are unchanged: candidate-specific controls and a reviewed
candidate-specific power assessment marked eligible must exist before any confirmatory dispatch;
exact binary identity and opening-suite hashes are enforced by the dispatcher and the resolver;
exactly 600 counted games on 50 opening clusters with one AB plus one BA leg per cluster are
required; and the strict, unrounded two-sided 95% calibrated CI lower bound requirement for
Batch A, Batch B and the combined estimate, each strictly greater than 2,000 Elo, is untouched.

Two transfers behind the estimate are unmeasured and are recorded as assumptions rather than
facts: every wall-clock measurement comes from the ENGINE-1 binary while the confirmatory campaign
runs a different candidate binary, and no candidate-specific 40/15 wall-clock timing evidence
exists yet; and Batch B has never been timed at all, so its durations are modelled as exchangeable
with the anchor's observed Batch A population.
