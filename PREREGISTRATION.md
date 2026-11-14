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

- status: PENDING EXECUTION
