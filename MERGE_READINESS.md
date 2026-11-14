# MERGE_READINESS checklist — PR #1 (Flawless V1)

Policy (mission §7): an item is checked ONLY with verifiable evidence. Unmet items stay
unchecked; the mission stays `ACTIVE / INCOMPLETE` until every applicable item is verified.
Never merge/tag/release without explicit user authorization (§9).

Current PR head: see `git log --oneline -1` / `gh pr view 1 --json headRefOid`.

## Correctness & reliability

- [x] Project correctness and reliability audit complete — engine audit pass recorded in
      DESIGN_LOG.md (2026-11-14 adversarial review entry + TT clock-unsafety verification);
      differential perft 76,240 positions 0 mismatches (BENCHMARKING.md / AGENTS_LOG.md);
      full Rust suite 33/33, match.py 104/104, rating_estimator 46/46 at `d023ee8`.
- [x] Critical/major findings fixed or technically dispositioned — CodeRabbit review 5903125228
      (13 findings) dispositioned in AGENTS_LOG.md; TT halfmove-clock finding verified FIXED in
      src/tt.rs (clock-safe flag + probe suppression + regression test
      `clock_unsafe_entries_suppress_score_but_keep_move`).
- [x] Regression tests added for repaired defects — TT clock test (src/tt.rs), clock smoke
      (tests/clock_smoke.rs), shard partition + e2e manifest (scripts/test_match.py),
      estimator degenerate-Σ_m + covariances (scripts/test_rating_estimator.py).
- [ ] Full CI matrix green on the exact FINAL head SHA — must be re-verified at the final head
      after all remaining work (last fully green: 43587593326 at `4d91741`; newer heads pending).
- [ ] No known unresolved correctness or security blockers — 5 PR review threads still open
      (2 outdated): covariance-between-anchors (verdict: handled by joint opening-cluster
      bootstrap — needs thread reply + doc cross-ref), match.py Windows pipe reader (outdated
      scope: rating runs execute on Linux runners; disposition pending), search.rs TT halfmove
      (verified fixed — thread to resolve), uci.rs:433 hold/output race (verification pending),
      uci_smoke wait robustness (outdated; disposition pending).

## Rating methodology (docs/RATING_PROTOCOL.md §9)

- [x] Rating methodology fully implemented and independently tested — scripts/rating_estimator.py
      (46/46) + scripts/aggregate_shards.py + match.py harness v2 (104/104).
- [x] Official anchor provenance verified — CCRL 40/15 list 2026-11-13 captured with HTTP 200,
      3,912,738 bytes, SHA-256 ce365c55b2869502de6addeada4c261d3bd2f50a5a9aef484db9f571aabe15f0;
      uncertainty convention = 95% CI (list text); record in benches/anchor-research-20261114.md.
- [x] ≥3 exact-version anchor binaries rebuilt and hash-verified on hosted runners — 6/6 anchors
      in anchor-verify.yml run 43597866181 (image ubuntu24 20261111.370.1, gcc 13.3.0):
      Wowl 1.3.7, Topple 0.1.1, Topple 0.2.1, akimbo 0.1.1, WyldChess 1.2, WyldChess 1.1.
- [x] Real `benches/anchor-pool.json` frozen and verified — 6 anchors, span 1849–2474, all
      runner SHA-256 + source SHA-256 + licenses + ci95 conventions; passes match.py
      fail-closed schema validation; exclusions recorded with reasons in the pool file.
- [x] SF10 hardware calibration complete — SF10 (official sf_10) bench on ubuntu-24.04 runner:
      3 runs 1998/1984/1996 ms vs i7-4770K reference 2054 ms for 3,939,338 nodes
      (Tors3/CCRL_ScirptsTests ccrl_bench.py) → factor k=1.0291, equivalent TC 40/14.58 min;
      batches play 40/15 wall-clock with the ~3% deviation documented (pool `calibration` block).
- [ ] Throughput pilots complete — pilot shards via rating-run.yml NOT YET RUN (next step).
- [ ] Both null controls pass — anchor-vs-anchor (published diff ±75 Elo) and color-swapped
      self-match (score consistent with 0.5): NOT YET RUN.
- [ ] Batch A independently passes the strict rating gate — NOT RUN (needs ≥2,000 completed
      games per eligible anchor; 60×17×2=2,040 games/anchor planned).
- [ ] Batch B independently passes the strict rating gate — NOT RUN (fresh disjoint openings).
- [ ] Combined calibrated 95% CI independently passes — NOT RUN.
- [ ] Every lower bound is strictly greater than 2,000, without rounding — NOT MEASURED.
- [ ] ≥2,000 completed games per eligible anchor per batch — NOT YET COLLECTED.
- [ ] Raw tournament evidence committed and reproducible — pending batch execution
      (aggregate_shards + estimator recompute from raw shards; never from STATUS.md).

## Reviews & repository integrity

- [ ] CodeRabbit completed review on the exact final head SHA — last substantive review
      5903125228 at f07c4633; manual re-review at final head to be requested (path previously
      rate-limited: "manual review required for this OSS repository").
- [ ] All relevant CodeRabbit findings dispositioned — 13/13 of 5903125228 dispositioned
      (AGENTS_LOG.md); 5 review threads need replies/resolution after verification.
- [ ] Documentation and PR description match the final implementation — STATUS.md updated at
      d023ee8+; PR body refresh pending at final head.
- [ ] All mandatory GitHub branch-protection and review conditions satisfied — verify at merge
      time (repository rules; required checks where permitted, else documented privileged action).
- [ ] PR is no longer a draft and is genuinely ready for review/merge — PR #1 is currently
      **Draft** by policy until every checklist item is verified.

## Authorization record

- No merge, tag, or release has been performed. Those require explicit user authorization
  separate from merge-readiness (mission §9).
