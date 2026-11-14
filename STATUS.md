# STATUS — Flawless Chess Engine

**Project state: `ACTIVE`** (V1 is NOT complete; the 2,000 Elo release gate has not been met and has NOT been measured — no calibrated absolute rating exists; see "Rating status" below)

**Current branch:** `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`
**Starting commit (verified 2026-11-14):** `98b1a00203183d9c7ccb175f7d6eb8f5ef5eb429` (only an Apache-2.0 `LICENSE` present)
**Engine identity (UCI):** `Flawless`
**License:** Apache-2.0 (preserved)

## Checklist (binary acceptance criteria — see TASK in prompt)

- [x] Repository recon complete (Phase 0)
- [x] Starting commit / remote state verified and recorded
- [x] Rust toolchain available (1.99.0, installed from npm `@toolchain-bin/*` because static.rust-lang.org is unreachable; see `docs/ENVIRONMENT.md`)
- [x] Architecture RFC published (Phase 1) — see ARCHITECTURE.md (accepted for v1 scope)
- [~] Chess foundation: perft claims scoped to evidence — pos4 d6 = 706045033 PASS (committed `benches/perft_pos4_d6.*`); startpos d3 = 8902 PASS (CI every push/PR, both OSs); full-depth cells for startpos/Kiwipete/pos3/pos5 remain PENDING in TESTING.md (earlier wording here overstated; corrected 2026-11-14)
- [x] Differential testing vs python-chess (pinned 1.11.2, GPL-3.0+, test-only oracle) — DIFTEST PASSED, 76,240 positions, 305 d3 perft comparisons, 0 mismatches
- [x] UCI protocol implemented and smoke-tested (async stop via worker thread + AtomicBool, clocks, MultiPV, ponder/ponderhit) — fuzzed smoke-level (seeded, deterministic; tests/uci_smoke.rs) — see TESTING.md; deep fuzzing NOT performed
- [x] Search baseline: iterative deepening + alpha-beta + TT (8-byte) + quiescence + null-move + LMR + aspiration + MultiPV (uncommitted until this phase checkpoint; see below)
- [x] Classical evaluation baseline (tapered PSTs, mobility, bishop pair, king zone, tempo); NNUE interface deferred, NNUE NOT default
- [x] Benchmark harness (fixed-time `movetime`/`depth`, paired openings, color reversal, opening-clustered CI) — `scripts/match.py` + `scripts/stats.py` + `benches/openings-20.txt`; verified end-to-end (smoke-match 2/2 wins vs SF 19 WASM Skill 0)
- [x] CI green on Linux + Windows (fmt, clippy -D warnings, release tests, release build, UCI handshake, UCI bestmove smoke, perft d3 sanity) + MSRV (1.80) job — PR #1, runs 43562935232 / 43563085939 / 43563499046 (clippy-fix regression, caught by CI, fixed in 837361f) / 43563628232 / 44c8369-era all green (except the known-bad b85b3f7); Kilo Code Review bot fails for account credits (not a code issue); CodeRabbit manually triggered (incremental) — see "Reviews" below
- [x] Match infrastructure: paired openings, color reversal, opening-clustered bootstrap CIs — `scripts/match.py` + `scripts/stats.py` (used for probes); panic-fallback games flagged `engine_error` and excluded from stats by default
- [x] **Rating harness v2 (2026-11-14)**: true UCI clock TC (`--tc 40/15` repeating schedule, `wtime/btime/winc/binc/movestogo`, actual-elapsed charging, flag fall, ponder off, `add`/`reset` period policy), deterministic repetition scheduling (60×17×2=2,040/anchor/batch) + exact AB/BA reversal, deterministic shard slicing (`--shard-index/--shard-count`), engine-error record→immediate-replay→abort-after-2 policy, move-cap recorded unadjudicated (never a silent draw), manifest v2 written before game 1 and finalized after (interrupted runs stay `in_progress`), opening-suite SHA-256 + schedule hash + shard identity in manifest, anchor-pool schema hardening (rejects TBD/null/placeholders, malformed SHA-256, ambiguous uncertainty conventions, unverified licenses/binaries). Regression suites: `scripts/test_match.py` (**104/104**), `tests/clock_smoke.rs` + `uci::tests::clock_limits_*` (Flawless clock-management verification; **33/33** cargo tests)
- [x] **Rating estimator (2026-11-14)**: `scripts/rating_estimator.py` implements RATING_PROTOCOL §9.6–9.8 — joint opening-cluster bootstrap (≥10,000, same cluster draw across anchors), per-anchor logistic d_a, σ_matched = SD of joint replicates, published-error → SD convention conversion (sd/se/ci95/ci90/ci99), GLS over Σ_m+Σ_c with documented diagonal-WLS fallback, separate match-only vs match+calibrated CIs, batch combination that pools match noise but adds shared calibration ONCE, null controls (anchor-vs-anchor ±75 Elo; self-match ~0.5), fail-closed `gate` subcommand that recomputes from raw evidence. Regression suite `scripts/test_rating_estimator.py` (**46/46**). Shard aggregator `scripts/aggregate_shards.py` (fail-closed §5.2 rejection rules; smoke-verified both directions)
- [x] **Rating workflows (2026-11-14)**: `anchor-research.yml` (fetch official CCRL 40/15 list from a hosted runner — open egress — with full provenance), `rating-run.yml` (workflow_dispatch shard execution, frozen commit/engine-hash/suite-hash verification, hardware capture, fails CLOSED until a verified anchor pool exists), `rating-gate.yml` (stable `rating-gate` job: aggregate+verify then independent estimator recomputation; SUCCESS only if all three lower CI bounds strictly > 2,000 and both null controls pass). Note: GitHub delivers `workflow_dispatch`/`workflow_run` only to workflow files on the default branch (main has only `LICENSE`), so remote runs go through `pull_request`-path triggers until merge; the permanent dispatch path is `gh workflow run`.
- [x] Identity migration to Flawless (ADR-0002) — historical evidence kept under old identifiers
- [x] Correctness audit pass 1 + 2 (mate>draw precedence, quiesce/RFP terminals, searchmoves MultiPV=1, clock_limits panic, panic-fallback plumbing) — all reproduced by regression tests; bench signature `d790483532d87af0` → `3086f65159758c9d`
- [x] UCI integration smoke + seeded deterministic fuzz (`tests/uci_smoke.rs`)
- [ ] Absolute rating > 2,000 (two-sided 95% CI lower bound STRICTLY GREATER THAN 2,000, per docs/RATING_PROTOCOL.md §9 amendment) — NOT MEASURED, NOT MET (no calibrated pool reachable from sandbox; see "Rating status")
- [ ] Reviews: CodeRabbit FINISHED/finding closure pending its completion; Copilot BLOCKED (quota, lower-effort retry needs web UI); Codex RATE_LIMITED; Qodo BLOCKED (trial ended); Kilo BLOCKED (credits)
- [x] PR #1 returned to **Draft** (2026-11-14, `gh pr ready --undo` verified): open, unmerged, draft=true. Earlier "not marked ready" claim was inaccurate (GitHub had it open/non-draft); corrected. PR stays open+unmerged; never merge/tag/release without explicit authorization.
- [ ] Correctness, reliability, documentation, release gates (see TESTING.md)
- [ ] v1.0.0 stable release (**NOT AUTHORIZED — gate not passed**)

## Hard constraints / environment notes

- No crates.io access (blocked): the engine is implemented with **zero external dependencies** (pure `std`).
- No static.rust-lang.org access: toolchain installed from npm packages `@toolchain-bin/{rustc,cargo,rust-std,rustfmt,clippy}-1.99.0-x86_64-unknown-linux-gnu` into `/home/user/.toolchain/sysroot`.
- Reference machine (target): Windows 10 LTSC 2021, i5-7300U (4 threads), 8 GB RAM. This dev sandbox: 2 vCPU, ~4 GB RAM, Linux.
- Opponent binaries for anchored rating testing are limited; see BENCHMARKING.md for the honest state of rating evidence.

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
