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
- [x] Chess foundation correct: perft gates pass (startpos, Kiwipete, positions 3–5; pos4 d6 = 706045033)
- [x] Differential testing vs python-chess (pinned 1.999, GPL-3.0+, test-only oracle) — DIFTEST PASSED, 76,240 positions, 305 d3 perft comparisons, 0 mismatches
- [x] UCI protocol implemented and smoke-tested (async stop via worker thread + AtomicBool, clocks, MultiPV, ponder/ponderhit) — fuzzed smoke-level (seeded, deterministic; tests/uci_smoke.rs) — see TESTING.md; deep fuzzing NOT performed
- [x] Search baseline: iterative deepening + alpha-beta + TT (8-byte) + quiescence + null-move + LMR + aspiration + MultiPV (uncommitted until this phase checkpoint; see below)
- [x] Classical evaluation baseline (tapered PSTs, mobility, bishop pair, king zone, tempo); NNUE interface deferred, NNUE NOT default
- [x] Benchmark harness (fixed-time `movetime`/`depth`, paired openings, color reversal, opening-clustered CI) — `scripts/match.py` + `scripts/stats.py` + `benches/openings-20.txt`; verified end-to-end (smoke-match 2/2 wins vs SF 19 WASM Skill 0)
- [x] CI green on Linux + Windows (fmt, clippy -D warnings, release tests, release build, UCI handshake, UCI bestmove smoke, perft d3 sanity) + MSRV (1.80) job — PR #1, runs 43562935232 / 43563085939 / 43563499046 (clippy-fix regression, caught by CI, fixed in 837361f) / 43563628232 / 44c8369-era all green (except the known-bad b85b3f7); Kilo Code Review bot fails for account credits (not a code issue); CodeRabbit manually triggered (incremental) — see "Reviews" below
- [x] Match infrastructure: paired openings, color reversal, opening-clustered bootstrap CIs — `scripts/match.py` + `scripts/stats.py` (used for probes); panic-fallback games flagged `engine_error` and excluded from stats by default
- [x] Identity migration to Flawless (ADR-0002) — historical evidence kept under old identifiers
- [x] Correctness audit pass 1 + 2 (mate>draw precedence, quiesce/RFP terminals, searchmoves MultiPV=1, clock_limits panic, panic-fallback plumbing) — all reproduced by regression tests; bench signature `d790483532d87af0` → `3086f65159758c9d`
- [x] UCI integration smoke + seeded deterministic fuzz (`tests/uci_smoke.rs`)
- [ ] Absolute rating ≥ 2,000 (two-sided 95% CI lower bound ≥ 2,000) — NOT MEASURED, NOT MET (no calibrated pool reachable from sandbox; see "Rating status")
- [ ] Reviews: CodeRabbit FINISHED/finding closure pending its completion; Copilot BLOCKED (quota, lower-effort retry needs web UI); Codex RATE_LIMITED; Qodo BLOCKED (trial ended); Kilo BLOCKED (credits)
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
| probe-001 | Skill 0 | 40/0/0 | 1.000 | [1.000, 1.000] | +2400 (degenerate clamp) |
| probe-003 | Skill 5 (pre-RFP/CE) | 11/13/16 | 0.438 | [0.325, 0.550] | −44 (CI [−127, +35]) |
| probe-002 | Skill 10 | 1/7/32 | 0.113 | [0.050, 0.175] | −359 (CI [−512, −269]) |
| probe-004 | Skill 5 (RFP+CE build) | 14/14/12 | 0.525 | [0.412, 0.637] | +17 (CI [−61, +98]) |
| A/B 004 | vs pre-change build, 50 ms | 18/13/9 | 0.613 | [0.487, 0.725] | +80 (CI [−9, +168]) |

Conclusion (honest): our strength is bracketed between pinned SF-Skill-5 and SF-Skill-10 at
movetime 100 ms on this hardware. The RFP+check-extension change moved the needle in the right
direction (+80 in the A/B, +17 vs Skill 5, both CIs wide and overlapping zero at 40–120 games). Absolute Elo is UNKNOWN and unverifiable from this sandbox —
certainly NOT 2,000+; v1.0.0 gates NOT met; rating estimate = **INCONCLUSIVE / far below gate**.
Do not present these numbers as official ratings; no CCRL anchor was available.

## Next preregistered task

1. Keep engine development evidence-based: if time permits, probe skill 3/7 to tighten the bracket, or run
   longer-TC probes; do not tune to the probe opponent.
2. ~~NPS / bench regression tracking~~ DONE (2026-11-14): `cargo run --release -- bench` — fixed
   depth 10 over 12 positions, deterministic FNV-1a signature `3086f65159758c9d`
   (2,317,474 nodes); `bench_eval` for eval throughput; CI runs perft d3 + UCI handshake + bestmove smoke.
3. Remaining V1 gaps: benchmark CLI `bench`, time-management validation vs clocks, EF RN search-consistency
   checks, Windows-specific verification (CI covers build only), and documentation of the release gates.
4. NEVER claim v1.0.0 status; never present in-sandbox numbers as CCRL/CEGT.

## Rating status (absolute; release-gate relevant)

- **Absolute rating: UNKNOWN.** The in-sandbox probes (SF Skill 0/5/10 WASM) are relative comparisons
  vs one unrated-for-our-purposes opponent configuration, not a calibrated absolute scale, and are NOT
  a CCRL/CEGT rating. Stockfish Skill Level is not a calibrated Elo anchor.
- **The V1 release gate (two-sided 95% CI of calibrated absolute rating, lower endpoint ≥ 2,000 Elo,
  vs a credible pool with documented methodology, pinned opponents, paired openings, ≥2 independent
  confirmation batches, preregistered) is NOT measured and NOT met. Nothing may be claimed otherwise.**
- Blocker (exact): no reachable calibrated pool from this sandbox. CCRL/CEGT listings are pages with
  documented methodology but match execution at scale (thousands of games, 40/15-class time controls,
  ratable opponent binaries with known CCRL Elo) cannot be downloaded/run here; crates.io/static
  rust-lang.org are unreachable; raw.githubusercontent.com is blocked; only github/codeload/api.github.com,
  npm and pypi registries are reachable. No official rating exists or may be claimed.
- Pre-registered protocol for when the gate IS executed: `docs/RATING_PROTOCOL.md`.
- Next actions for the gate (in priority order): (1) run the preregistered protocol on a machine with
  access to ratable opponent binaries (e.g. licensed CEGT/CCRL-anchored opponents or publicly distributed
  engine binaries with documented CCRL 40/15 Elo), ≥2 confirmation batches; (2) publish raw PGNs + stats;
  (3) only then evaluate v1.0.0 authorization.

## Reviews (per-reviewer state, head SHA at time of record)

Current head: see `git log --oneline -1`. PR #1 is OPEN, unmerged, not draft.

| Reviewer | State | Notes |
|----------|-------|-------|
| CodeRabbit | IN_PROGRESS (triggered 2026-11-14T05:46Z on head bbb31f9) | auto-skip: repo <10 stars; manual trigger `review triggered`; incremental system (does not re-review already-reviewed commits). Findings, if any, will be fixed and re-reviewed. |
| GitHub Copilot | BLOCKED | quota insufficient at default effort (2026-11-14). Retry at LOWER effort requested by task but requires the web UI reviewers panel (effort selection); API re-request rejected (`422: not a collaborator`); docs.github.com unreachable from sandbox. No findings recorded. |
| Codex | RATE_LIMITED | documented retry (`@codex review`) attempted 2026-11-14T05:47Z → "You have reached your Codex usage limits for code reviews." Prior run at 05a36c0: code review FAILED (usage limit), no findings available. |
| Qodo | BLOCKED | "Qodo reviews are paused because your trial has ended." (billing-blocked, 2026-11-14). No code findings. |
| Kilo | BLOCKED | "Kilo Code Review could not run — your account is out of credits." (2026-11-14). No code findings. |

Review policy: a reviewer FINISHED only when the service actually completes and findings are dispositioned.
