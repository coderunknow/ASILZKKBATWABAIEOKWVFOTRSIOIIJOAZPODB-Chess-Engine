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
