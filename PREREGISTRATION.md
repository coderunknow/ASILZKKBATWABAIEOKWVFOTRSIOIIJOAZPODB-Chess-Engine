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
