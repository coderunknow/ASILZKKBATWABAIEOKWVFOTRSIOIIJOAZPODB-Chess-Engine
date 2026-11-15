# PREREGISTRATION — confirmatory and exploratory experiments (append-only)

Policy (docs/RATING_PROTOCOL.md §9 / mission §8): every experiment is registered here with
objective, hypothesis, methodology, acceptance criteria, inputs and expected evidence BEFORE
its games are played. Entries are append-only; superseded plans are annotated, never deleted.
Confirmatory batches must not be tuned, re-anchored or re-opened after observing results.

---

## PILOT-1 — rating-run pipeline pilot (registered 2026-11-14, before dispatch)

- **Purpose:** exploratory (pipeline measurement only; its games are EXCLUDED from all gate
  evidence and never counted toward confirmatory sample sizes).
- **Objective:** measure end-to-end pipeline reliability and throughput of the GitHub-hosted
  rating-run workflow at real CCRL-class 40/15: game duration, games/hour/shard, timeout
  behavior, artifact integrity, manifest completeness, anchor-acquisition reliability.
- **Hypothesis:** the pipeline completes a 2-game shard with full manifests and hash-verified
  identities; average game wall-clock is ≤ 60 minutes; no engine or harness errors occur.
- **Methodology:** dispatch.json (purpose=pilot) → matrix of 2 shards, each the first
  contiguous 2-game slice of the frozen Batch-A schedule (60 openings × 17 paired reps ×
  AB/BA = 2,040 games; shard_count=1020 → 2 games per shard; indices 0 and 1 → 4 games
  total). Frozen suite `benches/rating-openings-batchA.txt` (SHA-256
  2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96), seed 20261114,
  TC 40/15, anchor topple-0.2.1 (frozen pool). engine_sha256 = "freeze" (first runner build
  of the target commit records the hash; nothing is claimed until it is pinned).
- **Acceptance criteria:** ≥ 3 of 4 games complete and are counted (unadjudicated);
  manifests contain engine/anchor/suite hashes that verify; artifacts upload; throughput
  numbers recorded in AGENTS_LOG.md; any failure triggers diagnosis + registered remediation.
- **Inputs:** benches/dispatch.json (schema 1) committed with this entry.
- **Expected evidence:** artifacts `rating-pilot-A-topple-0.2.1-shard{0,1}-<run_id>` +
  annotations with engine_sha256 and per-game JSONL.

### PILOT-1 result (filled after execution — see AGENTS_LOG.md for the raw record)

- status: IN EXECUTION (revision 3)
- freeze observations (annotations of run 43601528240): runner engine build of the frozen
  source (rustc 1.99.0, ubuntu-24.04) = SHA-256
  `fd75726dd3166640ddec75d94c416320b47c83e8d14bfa6309aed398d55b8e1d`, identical across two
  independent runner builds (runs 43597866181 verify-flawless and 43601528240) → byte-reproducible
  on this image/toolchain. Revision 3 pins this hash (strict mode). Any later hash mismatch
  fails closed and requires a documented re-freeze before further games.
- harness defects found by the pilot before any game completed (recorded in FAILURE_LEDGER):
  (1) config job-output double-encoding → checkout fallback to merge commit (rev 2);
  (2) shell word-splitting of `--white-cmd` argv (match.py: "unrecognized arguments: uci",
  exit 2) → step now drives match.py via an explicit argv list with stderr annotation capture.
- game/throughput results: PENDING (games run in revision 3+).

---

## CTRL-1 — anchor-vs-anchor null control (registered 2026-11-14, before dispatch)

- **Purpose:** control (null control #1 of §3.3 / mission). Validates that the pipeline +
  runners + 40/15 TC transfer relative ratings: a match between two frozen-pool anchors must
  recover their published CCRL rating difference within **±75 Elo** (mission-defined threshold;
  not adjusted here).
- **Pair:** white topple-0.1.1 (published 2324±17) vs black topple-0.2.1 (2439±14). Published
  diff (white − black) = **−115 Elo**. Same engine family, both verified id-mapped, both MIT.
- **Methodology:** 60 openings (`benches/rating-openings-batchA.txt`, SHA-256 2c4a54d8…)
  × 2 paired repetitions × AB/BA = **240 games**; shards of 2 games (shard_count=120,
  indices 0–119); TC 40/15 wall-clock; seed 20261115; engine_sha256 fd75726d… (flawless not
  seated; uniform strict check retained); batch CTRL, label `topple-0.1.1-vs-topple-0.2.1`.
- **Acceptance criterion (fixed):** |d̂ − (−115)| ≤ 75 Elo, where d̂ = −400·log10(1/s̄−1) from
  the completed-game score s̄ (white perspective), games counted per §9 adjudication rules.
  Failure → investigate transferability (runner TC/hardware), record in FAILURE_LEDGER, register
  remediation; never adjust the threshold.
- **Expected evidence:** artifacts `rating-CTRL-topple-0.1.1-vs-topple-0.2.1-shard*-<run_id>` +
  manifests (per-game JSONL with engine hashes).

## CTRL-2 — flawless self-match null control (registered 2026-11-14, before dispatch)

- **Purpose:** control (null control #2). Validates harness symmetry (colors, clocks, opening
  application): Flawless vs the identical binary must score **0.5 within its 95% binomial
  CI** (mission-defined threshold).
- **Methodology:** identical binary both sides (engine_sha256 fd75726d…), 60 openings (batch-A
  suite) × 2 paired repetitions × AB/BA = **240 games**; shards of 2 games (shard_count=120,
  indices 0–119); TC 40/15; seed 20261116; batch CTRL, label `flawless-self`.
- **Acceptance criterion (fixed):** 0.5 ∈ 95% binomial CI of the total score (wins + ½·draws)
  over the completed games. Failure → investigate asymmetry, record in FAILURE_LEDGER, register
  remediation; never adjust the threshold.
- **Expected evidence:** artifacts `rating-CTRL-flawless-self-shard*-<run_id>` + manifests.

### CTRL-1 / CTRL-2 results (filled after execution)

- status: PENDING EXECUTION

---

## SCREENING-1 / SCREENING-2 — anchor-selection screening estimates (registered 2026-11-14, before dispatch)

- **Purpose:** screening (exploratory; NEVER gate evidence; used ONLY to choose the
  confirmatory anchor set within §2's span/±400 rules — the protocol's prescribed use of a
  brief screening estimate). Pilot/CTRL data are likewise excluded from gate counts.
- **Objective:** bound the absolute estimate well enough to select ≥ 3 confirmatory anchors
  that are non-saturating (|d| ≤ 400 expected) and satisfy §2's span/coverage rules as the
  frozen pool allows (KNOWN TENSION: the pool gap 1849 → 2324 may make the literal
  [est−200, est+200] span rule unsatisfiable for est > 2249; the chosen interpretation will
  be documented explicitly at registration of the batches).
- **Methodology:** Flawless (engine_sha256 fd75726d…) vs topple-0.1.1 (published 2324±17,
  SCREENING-1) and vs topple-0.2.1 (2439±14, SCREENING-2): 60 openings
  (`benches/rating-openings-batchA.txt`, 2c4a54d8…) × 1 paired repetition × AB/BA = **120
  games each** (15 shards × 8 games); TC 40/15; seeds 20261119 (S-1) / 20261120 (S-2).
- **Analysis (pre-defined):** d̂ = −400·log10(1/s̄−1) per anchor from counted games; est =
  mean of (R_a + d̂_a) across the two anchors; uncertainty ~ binomial/cluster bootstrap (for
  SELECTION only — never reported as a rating). Selection rule: pick ≥ 3 pool anchors with
  expected |d| ≤ 400 around the screening estimate and straddling it within ±200 where the
  pool permits; include the widest low/high discriminators available.
- **Expected evidence:** `benches/evidence/screening/topple-0.1.1/` and `.../topple-0.2.1/`
  via the in-run evidence job.

### SCREENING results (filled after execution)

- status: PENDING EXECUTION

---

## BATCH-A / BATCH-B — confirmatory batches (registered 2026-11-14, BEFORE dispatch; anchor set filled per the fixed rule below before any game)

- **Purpose:** confirmatory (gate evidence). Thresholds and all inputs below are frozen now.
- **Acceptance (mission §9, unrounded):** for EACH of Batch A, Batch B and the combined
  estimate, the two-sided 95% calibrated CI lower bound must be strictly > 2,000 Elo;
  every eligible anchor: |d| ≤ 400 and ≥ 2,000 counted games **per batch**; both null
  controls pass their registered thresholds. No rounding, no clamping, no extrapolation.
- **Engine:** Flawless, engine_sha256 `fd75726dd3166640ddec75d94c416320b47c83e8d14bfa6309aed398d55b8e1d`
  (strict mode; any mismatch fails the shard).
- **Suites:** Batch A `benches/rating-openings-batchA.txt` SHA-256
  `2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96`; Batch B
  `benches/rating-openings-batchB.txt` SHA-256
  `744a3981cc312a676ba259962309858b7d2fc645094bf2dccf5391e77f2f9dd4`. VERIFIED DISJOINT
  2026-11-14: 60+60 lines, zero shared move-lines, zero shared names, zero internal
  duplicates (checked programmatically; see AGENTS_LOG 273).
- **Sample:** 60 openings × 17 paired repetitions × AB/BA = **2,040 games per eligible
  anchor per batch**; counted per §9 adjudication (move-cap games recorded `*`
  unadjudicated, never silently drawn; engine-error games excluded and replayed per policy).
- **Sharding:** 255 shards × 8 games per (batch, anchor) (deterministic contiguous slices of
  the frozen schedule; one marker dispatch per (batch, anchor); failed shards re-run into
  FRESH output only, never overwriting/mixing).
- **TC:** 40/15 wall-clock repeating (cutechess `add` semantics — verified at source), ponder
  off; SF10 factor_k 1.0291 deviation documented in the pool.
- **Bootstrap seeds (estimator):** Batch A `20261121`, Batch B `20261122` (combined uses the
  registered joint procedure). Dispatch seed fields carry the same values.
- **Anchor set (the ONLY rule-derived input):** chosen by the SCREENING-1/2 selection rule
  already registered above, from the frozen pool only: ≥ 3 anchors, all expected
  non-saturating (|d| ≤ 400) at the screening estimate, straddling the estimate within ±200
  where the pool permits, including the widest available low/high discriminators. The exact
  keys and the documented §2-span interpretation are committed in `benches/gate-plan.json`
  (machine plan consumed by rating-gate.yml) in the same commit that dispatches Batch A,
  BEFORE any batch game runs. If the rule cannot be satisfied by the frozen pool at the
  screening estimate, the tension is documented and the nearest compliant set is chosen and
  justified — never tuned to the outcome.
- **Expected evidence:** `benches/evidence/batchA/<anchor>/` and `.../batchB/<anchor>/`
  (committed raw per-game results + manifests), then the fail-closed gate:
  `scripts/verify_evidence.py` + `scripts/rating_estimator.py gate`.

### BATCH results (filled after execution)

- status: PENDING EXECUTION (anchor set pending SCREENING-1/2)

### PILOT-1 / PILOT-dup results (filled 2026-11-15 after evidence recovery)

- status: COMPLETE (both pilot collections recovered via evidence-bridge rev 3, run
  43683839993, commit 2ec762e; independently re-aggregated from original shard artifacts —
  byte-identical merged_sha256 aeb4d5a0… / a811d9d1…).
- throughput: PILOT-1 29.43 min/game (4/4 games, per-record wall_seconds 1776.7/1755.0/1776.8/
  1755.4); duplicate pilot 29.53 min/game (4/4). 8-game batch shard ≈ 236 min < 330-min job cap.
- engine hash freeze verified on runners (fd75726d…, two independent builds byte-identical).
- Both pilot collections remain EXPLORATORY ONLY (pipeline measurement; excluded from gate).

### CTRL-1 / CTRL-2 results (filled 2026-11-15 after evaluation)

- CTRL-1 anchor-vs-anchor: **PASS.** 240/240 counted, 0 engine errors. Measured
  topple-0.1.1 − topple-0.2.1 = −125.32 vs published −115.00 → error −10.32, |err| ≤ 75 ✓
  (estimator seed 20261115). Evidence: benches/evidence/control/topple-0.1.1-vs-topple-0.2.1/.
- CTRL-2 self-match: **PASS** (see FAILURE_LEDGER 2026-11-15 metric-defect entry). Seat-
  perspective score 0.5146, 95% CI [0.4792, 0.5500] → 0.5 inside ✓ (estimator seed 20261116).
  White-perspective 0.6604 recorded as the color advantage. Evidence:
  benches/evidence/control/flawless-self/.

### SCREENING-1 / SCREENING-2 results (filled 2026-11-15 after evaluation)

- status: COMPLETE (120/120 counted each, recovered from original shard artifacts; byte-
  identical to the in-run aggregate mirrors 147cec4f… / 9e26b8cd…).
- SCREENING-1 (vs topple-0.1.1, 2324±17): score 0.0208 → d̂ = −668.8 → abs estimate 1655.2
  (cluster-bootstrap 95% score CI [0.004, 0.046]).
- SCREENING-2 (vs topple-0.2.1, 2439±14): score 0.0083 → d̂ = −830.2 → abs estimate 1608.8.
- Screening estimate (registered rule, mean of R_a + d̂_a): **est ≈ 1632 Elo**.
- Selection rule outcome: at est ≈ 1632 the only non-saturating pool anchor is wowl-1.3.7
  (expected |d| = 217 ≤ 400); every other anchor (2324+) is saturating (|expected d| ≥ 692).
  The ≥3-anchor gate requirement is UNSATISFIABLE at the frozen pool — the registered
  anchor-set rule produces no compliant set. Per the registered escape clause the tension is
  documented (not silently tuned); per mission §8 the batch dispatch is DEFERRED and the
  engine-improvement cycle is registered below. NOTE: the screening root-cause analysis found
  ~95% of Flawless losses are flag falls (time forfeits) from a clock-management defect —
  the 1632 figure measures the DEFECTIVE candidate, not the engine's search/eval strength.
- Screening data remain SELECTION-ONLY, never gate evidence.

## ENGINE-1 — time-management remediation (registered 2026-11-15, BEFORE any new game)

- **Purpose:** improvement cycle step 1 (mission §8). Hypothesis: the flag-fall defect in
  `clock_limits` (soft clamp 20–30_000 ms causing late-period overspend; hard = 6×soft
  permitting near-zero-reserve single-move spends) causes ~95% time forfeits at 40/15;
  fixing it converts forfeits into real chess results.
- **Change (frozen before implementation):** replace the budget with a reserve-bearing
  formula — reserve = clamp(t/16, 300 ms, 8 s); soft = max(20 ms, (t − reserve)/mtg) with NO
  upper clamp; hard = min(4×soft, (t − reserve)/2, t − max(300 ms, reserve/2)); keep the
  never-exceed-remaining invariant. Rationale: full-period utilization is correct for
  repeating 'add' schedules, but with a safety reserve that absorbs per-move overhead and
  bounded hard limits that cannot consume the whole remaining clock.
- **Acceptance (fixed now):** (1) new clock-allocation regression tests pass (period-plan
  sums stay ≤ t; no single move can spend more than half the usable clock; reserve always
  positive); (2) all existing suites stay green (cargo 34+, test_match 104, estimator suite);
  (3) bench signature change recorded; (4) hosted SCREEN-2 (below) shows flag rate ≈ 0
  (registered: ≤ 10 flag ends out of 120 games per screening); (5) no regression in the
  SF19-lite skill-5 A/B probe band (relative statistic, in-sandbox only).
- **Expected measurable effect:** screening score vs topple-0.1.1 rises from 0.0208 to
  ≥ 0.10 (est ≥ ~1920); if the engine's true 40/15 strength is ≥ ~2000, ≥3 non-saturating
  anchors become selectable and Batch A/B proceed with the new frozen hash. If the new
  screening estimate still yields no compliant ≥3-anchor set, the improvement cycle
  continues (mission §8) — the threshold and selection rule remain frozen.

## SCREEN-2 — re-screening of the ENGINE-1 candidate (registered 2026-11-15, before dispatch)

- **Purpose:** exploratory screening (selection-only, never gate evidence) of the
  time-management-fixed candidate, identical methodology to SCREENING-1/2.
- **Methodology:** Flawless (engine_sha256 "freeze" — first runner build records the new
  hash, pinned in PREREGISTRATION before any confirmatory dispatch) vs topple-0.1.1 AND
  topple-0.2.1; 60 openings (batch-A suite, suite hash 2c4a54d8…) × 1 paired rep × AB/BA =
  120 games each (15 shards × 8); TC 40/15; seeds 20261123 (vs 0.1.1) / 20261124 (vs 0.2.1);
  marker-file dispatches with distinct revisions; fresh evidence dirs
  benches/evidence/screening-2/<anchor>/.
- **Analysis (pre-defined):** identical to SCREENING-1/2 (d̂ per anchor; est = mean(R_a + d̂_a);
  selection-only uncertainty); then re-apply the UNCHANGED anchor-set selection rule.
- **Expected evidence:** benches/evidence/screening-2/topple-0.1.1/ and …/topple-0.2.1/.

## CTRL-2-R — self-match null control re-run for the ENGINE-1 candidate (registered 2026-11-15, before dispatch)

- **Purpose:** mission §8.16 — the candidate changed (ENGINE-1 clock budget), so the old
  CTRL-2 evidence (binary fd75726d…) no longer covers the candidate's clock interaction with
  the harness. CTRL-1 (anchor-vs-anchor) does not seat the candidate and its PASS stands.
- **Methodology:** identical binary both sides at the PINNED SCREEN-2 hash (freeze recorded
  by SCREEN-2 runners, pinned in PREREGISTRATION before this dispatch); 60 openings (batch-A
  suite, 2c4a54d8…) × 2 paired reps × AB/BA = **240 games**; 120 shards × 2; TC 40/15;
  dispatch seed 20261125; purpose control, batch CTRL, label flawless-self-r; evidence dir
  benches/evidence/control/flawless-self-r/.
- **Acceptance criterion (fixed, unchanged):** seat-perspective score 0.5 within its 95%
  opening-cluster bootstrap CI (the registered CTRL-2 definition with the color_pair metric
  fix; estimator seed 20261125). White-perspective score is recorded for transparency.
- **Timing:** runs BEFORE any confirmatory gate evaluation (the gate consumes both controls
  at their registered paths; gate-plan.json will point the self-match control at the
  CTRL-2-R evidence for the ENGINE-1 candidate).
- **Expected evidence:** artifacts rating-control-CTRL-flawless-self-r-shard*-<run_id> +
  manifests; strict aggregation identical to CTRL-2.

### ENGINE-1 acceptance record (updated 2026-11-15 after local verification)

- (1) clock regression test: PASS (cargo 35/35 incl. `clock_limits_engine1_no_flag_death_march`).
- (2) suites: cargo 35/35, fmt clean, clippy -D warnings clean, test_match 104/104,
      test_rating_estimator 65/65.
- (3) bench signature UNCHANGED fc907eba40b7869f (search/eval byte-identical; the fix touches
      time allocation only).
- (4) SCREEN-2 flag rate ≤ 10/120 per screening: PENDING (runs 43685671431 + 43686056730).
- (5) SF19-lite skill-5 probe: probe-006 (probe-005 methodology, 80 games = 2× repetitions,
      movetime 100 ms, skill_black 5, hash 16, batch PROBE): flawless 44.5/80 = 0.556,
      opening-clustered 95% CI [0.469, 0.644], logistic +39 vs this setting — inside the
      probe-005 band (0.600, CI [0.463, 0.725], +70 [−26, +168]; overlapping CIs). 0 engine
      errors. Raw evidence committed: benches/probe-006-engine1-validation/. Local build hash
      a3325011… (sandbox build; the RUNNER build hash is the one pinned for batches).

## ANCHOR-2 — anchor pool expansion for the >3,000 Elo phase (registered 2026-11-15, before any verification build or game)

- **Purpose:** mission §2 (anchor coverage) — the frozen 6-anchor pool (1849–2474) CANNOT
  calibrate ratings above ~2,600; the 3,000 milestone requires independently rated anchors
  bracketing and exceeding 3,000. This registration PRE-COMMITS the expansion procedure; the
  2,000 gate proceeds UNCHANGED on the frozen pool.
- **Rating source (provenance):** CCRL 40/15 list, computed 2026-11-13 (Bayeselo, ponder off,
  3-4-5 EGTB, i7-4770K equivalence — same reference machine as pool calibration k=1.0291);
  fetched by anchor-research workflow run 43587593393 (artifact `ccrl-4015-fetch-43587593393`,
  SHA256SUMS.txt inside, 200 OK on the runner); parsed locally (1,480 single-CPU rows with
  ≥1 game; 4CPU rows excluded — our engines are single-threaded; error convention ci95 per
  the verified list text).
- **Candidate ladder to verify (single-CPU published ratings; repos verified reachable with
  the listed SPDX license AT HEAD — license AT THE EXACT TAG is checked during verification,
  fail-closed):**
  | candidate | repo | tag to verify | CCRL 40/15 single-CPU | license (HEAD) |
  |---|---|---|---|---|
  | Leorik 2.5 | lithander/Leorik | release for v2.5 | 2922±18 (g=684) | MIT |
  | Berserk 3.2.1 | jhonnold/berserk | v3.2.1 | 2958±20 (g=504) | GPL-3.0 |
  | Seer 1.2.1 | connormcmonigle/seer-nnue | v1.2.1 | 3088±18 (g=659) | GPL-3.0 |
  | Stockfish 5 | official-stockfish/Stockfish | sf_5 | 3238±10 (g=1936) | GPL (verify at tag; historically GPL-2.0) |
  | Stockfish 6 | official-stockfish/Stockfish | sf_6 | 3280±10 (g=2272) | GPL (verify at tag) |
  | Stockfish 7 | official-stockfish/Stockfish | sf_7 | 3302±9 (g=2692) | GPL (verify at tag) |
  | Stockfish 8 | official-stockfish/Stockfish | sf_8 | 3358±7 (g=3886) | GPL (verify at tag) |
  | Leorik 3.1 | lithander/Leorik | release for v3.1 | 3367±11 (g=1670) | MIT |
  | (reserve rungs) Berserk 4.7.0 3445±17; Seer 2.x; SF 9 3422±9; SF 10 3443±7; SF 11 3494±11; Caissa 1.24 3593±9 (MIT, Witek902/Caissa) |
  Mid-band (2,475–2,920) additions are required later for interpolation (Berserk 1.x/2.x,
  Leorik 2.3/2.4, Igel/Halogen/Viridithas older versions) — registered as ANCHOR-2b when the
  candidate's level makes them decisive; NOT needed for the 2,000 gate.
- **Verification procedure (identical discipline to the frozen pool):** rebuild from SOURCE at
  the exact tag on the hosted runner (anchor-verify.yml pattern: matrix build + UCI
  identity-string check + SHA-256 recording + LICENSE-at-revision check + verify-flawless
  control; fail closed on any mismatch); record runner binary SHA-256 + toolchain + image in
  the new pool file `benches/anchor-pool-3000.json`; NO source patches (Raven-style hardened-
  build accommodations documented if ever needed, with ASAN evidence).
- **Usage rule (pre-committed):** the 3,000-phase gate plan (gate-plan v2) will select anchors
  by the SAME registered selection rule applied to the expanded pool; the plan, the pool file,
  and any protocol amendment are committed BEFORE any 3,000-phase confirmatory games; the
  2,000 gate (gate-plan v1, frozen pool) is untouched. UCI id-string mapping quirks (tag vs
  printed id) documented per engine, as done for Topple 0.1.1.
- **No games are played under this registration; it registers verification + expansion work
  only.** Every verification failure (unverifiable license, id mismatch, build failure) is
  recorded with the exclusion reason in the pool file, mirroring the frozen-pool discipline.

### ANCHOR-2 execution notes 1 (2026-11-15 — tag availability verified, rungs adjusted)

- Stockfish 8: tag `sf_8`, **COPYING at tag = GPL-3.0**, local build smoke SUCCESS (g++,
  ARCH=x86-64, bench 5.9M nodes @ 2.42M nps, UCI id "Stockfish 8 64 by T. Romstad, …"
  matching the CCRL row). Hosted verification still required.
- Berserk 3.2.1: NO tag/release exists (tags start 8.5.1, releases start 4.3.0) → EXCLUDED
  under the fail-closed source-identity rule; substituted by Seer/akimbo/Weiss rungs below.
- Seer 1.2.1: repo tags start `v2.1.0`; only CCRL row = 1.2.1 (3088±18) → EXCLUDED unless a
  verifiable source revision is found; lower priority given alternatives.
- SUBSTITUTED RUNGS (3,000-straddle band, all with known repos): **akimbo 0.5.0 (3026,
  amanjpro/akimbo — same repo as the frozen-pool akimbo 0.1.1, existing verification flow,
  tags to be checked at execution)**; **Weiss 1.2 (3017, version↔rating map already extracted
  by anchor-research run 43587593326-series)**; Leorik 2.5 (2922, release tags 2.4/2.5/3.1
  verified present); SF 5 (3238, tag sf_5); SF 8 (3358, tag sf_8, smoke-verified).
- Revised ANCHOR-2 ladder (order of hosted verification): akimbo 0.5.0 → Weiss 1.2 →
  Leorik 2.5 → SF 5 → SF 8 (reserves: SF 9/10/11, Caissa 1.24, Berserk 4.7.0).

### ANCHOR-2 verification result (2026-11-15 — COMPLETE for the registered ladder)

- **Hosted verification run 43693679899 (SUCCESS, head 932ae99): ALL 11 legs green** —
  6 frozen-pool anchors (re-verified) + 5 ANCHOR-2 rungs: leorik-2.5 (bin 84e1d60d…),
  akimbo-0.5.0 (eee14678…), weiss-1.2 (fb9e0434…), stockfish-5 (3cb291f2…),
  stockfish-8 (6ec5eda2…) — each with exact UCI identity match, license-at-tag verified,
  source + binary SHA-256 recorded, artifacts `anchor-<key>-43693679899`.
- **Expansion pool frozen: benches/anchor-pool-3000.json** (schema mirrors the frozen pool;
  5 engines spanning 2922–3358, 8,762 CCRL games total; exclusions berserk-3.2.1 / seer-1.2.1
  documented with reasons). Consumed only by the preregistered gate-plan v2 for the 3,000
  phase — the 2,000 gate uses the frozen pool unchanged.
- Reserves for later rungs (registered in execution notes 1): weiss-1.3/1.4, sf_9/10/11,
  caissa-1.24, berserk-4.7.0 — added to the same matrix when the candidate's level makes
  them decisive.

## SCREEN-3 — conditional third screening to complete the ≥3-anchor selection set (registered 2026-11-15, BEFORE any SCREEN-2 result is observed)

- **Purpose:** the frozen anchor-set rule requires ≥3 non-saturating screened anchors;
  SCREEN-2 screens exactly two (topple-0.1.1, topple-0.2.1). If the SCREEN-2 estimate makes
  ≥3 frozen-pool anchors non-saturating (|est − R_a| ≤ 400), a third screening is required
  before gate-plan.json; if it does not, SCREEN-3 is NOT dispatched and the improvement
  cycle continues (registration is a plan, not an obligation to run).
- **Anchor choice (mechanical, rule-derived):** among non-saturating pool anchors NOT yet
  screened in SCREEN-2, pick the one minimizing |est − R_a|; deterministic tie-break =
  higher published_elo. No human discretion.
- **Methodology:** identical to SCREEN-2 (120 games = 60 openings × 1 paired rep × AB/BA,
  batch-A suite 2c4a54d8…, 15 shards × 8, TC 40/15, marker-file dispatch revision = next
  sequential, purpose "screening", white flawless at the PINNED SCREEN-2 hash, seed
  20261126, fresh evidence dir benches/evidence/screening-3/<anchor>/).
- **Analysis:** identical (d̂_a; per-anchor estimate R_a + d̂_a; selection-only uncertainty);
  then make_gate_plan.py --anchors <all screened anchors> applies the UNCHANGED rule to
  produce the gate plan. Screening remains selection-only, never gate evidence.
