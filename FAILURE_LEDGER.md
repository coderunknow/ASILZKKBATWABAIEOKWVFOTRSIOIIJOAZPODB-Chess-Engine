# FAILURE_LEDGER.md (append-only)

<!-- 2026-11-14 (audit): the "No failures recorded yet" preamble was stale — the file already
contained entries. Entries are append-only and remain the live record. Required entry format:
what was attempted, why, exact commit/binary, conditions, raw evidence location,
result + uncertainty, suspected mechanism (hypothesis), what was learned, next experiment. -->

## 2026-11-14 — UCI bestmove never printed without trailing stdin input

- Attempt: `printf 'uci\nposition fen <kiwipete>\ngo depth 10\nquit\n' | engine uci` returned
  only `bestmove a2a3`-style fallback; an interactive session with `go depth 3` on a mate-in-1 FEN
  showed `score mate 1 pv b1b8` but NO bestmove line within 20 s.
- Root cause (hypothesis, verified): main thread blocked on blocking `stdin.lines().next()`; it never
  reaped the worker on natural completion. `stop_and_join` was only called on the *next* command.
  Fix: worker thread prints `bestmove [ponder X]` immediately after `search_root` returns;
  `stop_and_join` now only joins and stores the TT handoff; abort discards garbage root scores.
- Conditions: Rust 1.99.0 release build, Linux, 2 vCPU. No rating relevance.
- Result: fixed and smoke-verified (mate-in-1 prints `bestmove b1b8`; stop/ponderhit verified).
- Lesson: UCI engines must emit bestmove autonomously on search completion; never tie bestmove
  emission to the next GUI input.

## 2026-11-14 — Search worker panic (LMR table out-of-bounds) loses the game on the board

- Attempt: 40-game benchmark vs pinned Stockfish 19 WASM (Skill 0), opening `openings-20.txt`,
  `go movetime 100` per side.
- What happened: at game 1, move 30, our engine failed to reply for 300 s (harness timeout →
  `timeout_forfeit`, recorded 0-1). Root-caused to a thread panic printed to stderr:
  `index out of bounds: the len is 64 but the index is 64` at src/search.rs:484.
- Root cause: LMR reduction table `[[i32; 64]; 64]` indexed by `[depth][searched_count]` with
  **depth up to 64** (max_depth clamp) and **searched_count ≥ 64** (up to 218 legal moves).
  Two independent out-of-bounds paths.
- Fix: table enlarged to `[MAX_PLY+1][256]`; use-site indices clamped; and the UCI worker now wraps
  the whole search in `catch_unwind`, emitting a legal fallback `bestmove` on panic so the GUI
  never hangs. (The position — a mate-in-3 found at depth 16 — now searches cleanly at ~1.9M nps.)
- Result: match re-run; 2-game smoke passes (engine wins both, mate scores sane); full probe
  `benches/probe-001-sf19lite-skill0` launched.
- Lesson: any panic inside the search thread must not desynchronize the UCI loop — always emit
  bestmove; index tables must be sized for the true worst case (218 legal moves, depth 64).

## 2026-11-14 — Sandbox workspace reset (git HEAD reverted to 98b1a00; toolchain and venv lost)

- Attempt: continue session after a runtime interruption.
- What happened: `git log` showed only the starting commit `98b1a00` and all project files appeared
  as untracked; `/home/user/.toolchain` (Rust 1.99.0) and `/home/user/.venv` (python-chess) and
  `/home/user/opponents/` were gone. The repo working tree itself was intact.
- Recovery (all verified): origin still held branch tip `1dc2500`; re-pointed local branch ref and
  rebuilt the index with `git update-ref` + `git reset` — working tree matched the commit exactly
  (no data lost). Toolchain reinstalled from npm `@toolchain-bin/*` tarballs (rustc/cargo 1.99.0,
  clippy 0.1.99, rustfmt 1.10.0) — same versions as before; venv recreated (python-chess 1.11.2);
  pinned Stockfish 19 WASM reinstalled and SHA-256 re-verified identical (ccb130d7…, ee4f115b…).
- Lesson: push every commit immediately; keep raw-evidence artifacts committed; document toolchain
  provenance so it can be rebuilt from npm without network to rust-lang.org; the branch on origin is
  the source of truth.

## 2026-11-14 — Sandbox workspace re-materialized for the second time

- Attempt: continue the project after an interruption (Phase 1 start).
- What happened: git HEAD reverted to `98b1a00`; all tracked files showed as untracked;
  `/home/user/.toolchain`, `/home/user/.venv`, `/home/user/opponents/` wiped. CI/PR state on origin
  was unaffected.
- Root cause (hypothesis): sandbox host recycles the writable overlay between sessions; only the
  repository snapshot pushed to origin (and the mission-provided starting commit) are durable.
- Recovery: `git update-ref` to origin tip + `git reset` (index rebuild) — worktree verified clean
  vs a01fcaf; toolchain reinstalled from npm (same pinned versions); venv recreated; pinned SF
  WASM reinstalled and hash-verified (ccb130d7…/ee4f115b…); lld execute bits restored for lld-backed
  linking; full gate suite re-run.
- Lesson: push early and often; everything not pushed is at risk; keep this rebuild sequence
  documented (docs/ENVIRONMENT.md); verify gates after every restore.

## 2026-11-14 — Sandbox workspace reset (third materialization); full rebuild verified

- Attempt: continue Phase "CodeRabbit closure + re-verification".
- What happened: `/home/user/.toolchain`, `/home/user/.venv`, `/home/user/opponents`, and
  `node_modules` were wiped AGAIN; only the repository snapshot survived. This time the rebuild ran
  the full documented sequence and every gate was RE-VERIFIED before any commit: toolchain reinstall
  (@toolchain-bin pins: rustc/cargo 1.99.0, clippy 0.1.99, rustfmt 1.10.0 + find -exec chmod 755),
  venv (python-chess 1.11.2), pinned Stockfish 19 WASM reinstalled (hashes ccb130d7… / ee4f115b…
  re-verified byte-identical to BENCHMARKING.md), opponents/ mirrored, DIFTEST re-run
  (2295 perft-d2 positions, 0 mismatches, PASSED), bench re-measured (signature unchanged
  `fc907eba40b7869f`, 2,221,199 nodes), `cargo test --release --locked` 29/29 green, clippy clean.
- Latent defect found & fixed in the process: tt::store grew to 8 arguments (clippy too_many_arguments,
  -D warnings) — CI had gone blind to it (log access blocked); fixed by bundling a StoreRequest
  struct; the annotations-2.0 diagnostic step confirmed the exact error in one run.
- Lesson (unchanged, reinforced): after every restore, rebuild AND re-run gates before claiming
  anything; a green-looking CI rerun on a wiped tree proves nothing about local state.
- Also on restore #3: `git add -A` swept a locally-installed GPL Stockfish WASM tree (npm
  stockfish@19.0.1) into commit d6dc221 after node_modules was reinstalled for verification;
  removed in f0a2a55 (.gitignore now covers node_modules/). History keeps the blobs (no
  force-push — PR head stability); no further node_modules may be committed. Opponent remains
  pinned OUTSIDE the repo (/home/user/opponents, hash-verified).

## 2026-11-14 — Rating-anchor verification investigation (gate remains BLOCKED)

- Attempt: determine whether ANY eligible calibrated anchor (CCRL 40/15 preferred, CEGT 40/20,
  or another recognized list) can be verified from this sandbox.
- Commands and ACTUAL outputs:
  - `curl -I https://www.computerchess.org.uk/ccrl/40-15/` → 000 (blocked)
  - `curl -I https://www.cegt.net/40-15-chessengine-rating-list-6/` → 000 (blocked)
  - `curl -I https://ccrl40-15.herokuapp.com/` → 000 (blocked)
  - `gh api "search/repositories?q=ccrl+40%2F15"` → derivative mirrors only
    (`ahmad-luqman/chess-engine-nnue` scripts/anchors-ccrl.txt: user-maintained CCRL *Blitz*
    roster — cinnamon2.2a 2071, cinnamon2.3 2212, blunder7.4 2532, akimbo0.4 2723 — NOT the
    authoritative list, wrong scale (Blitz ≠ 40/15), ratings unverifiable, binaries local-only)
  - `gh api "search/repositories?q=cegt+chess"` → no usable rating list
  - `gh api "search/code?q=CCRL+40%2F15"` → index files only (CPWOffline/exported/CCRL.html is a
    hub page, wgArticleId 32, revision 24555 — no rating table; "Engine Rating Lists.html" is an
    index of external lists, external links all point to blocked hosts)
- Consequence: no anchor satisfies §2/§9 eligibility — verified name, version, SHA-256, published
  rating + error with convention, list publication date, retrieval date, and matching TC — so no
  gate batch may run and no absolute rating may be claimed. Anchoring from memory or from derivative
  GitHub files would be fabrication and is refused.
- Additional blocker (unchanged): ≥ 2,000 games × ≥ 3 anchors × 2 batches at 40/15-class TC
  (≥ 12,000 games; at CCRL 40/15 that is 40 moves per 15 minutes per game — infeasible on 2 vCPU).
- Next action for the gate (unchanged): execute RATING_PROTOCOL §§3–9 on a machine with access to
  the authoritative CCRL/CEGT lists and ratable opponent binaries (or their licensed redistribution),
  then commit benches/rating-batchA and benches/rating-batchB and update STATUS.md with the
  measured result and CIs.

- 2026-11-14: `cp -a <empty-var>/. sysroot/` after a failed `find` copied the filesystem root
  into /home/user/.toolchain/sysroot (unremovable cgroup pseudo-files inside). Cause: empty
  substitution in cp source. Fix: rm -rf + rebuild from npm packages; ALWAYS guard `cp` sources
  as non-empty. Also: npm strips execute bits — chmod +x sysroot/bin/* and
  sysroot/lib/rustlib/*/bin/* (incl. gcc-ld/) or linking fails with "cannot find 'ld'".
- 2026-11-14: synthetic anchor-vs-anchor null-control fixture was internally inconsistent
  (manufactured A1-vs-A2 games implied d=+235 while published diff was -100) -> control failed
  (correctly). Fix: build transitively consistent synthetic worlds (per-anchor score patterns
  matching published gaps). Uniform per-opening score clusters make Sigma_m degenerate (zero
  variance) and force the GLS fallback — synthetic fixtures must use heterogeneous clusters.

## 2026-11-14 — Anchor-verify hosted pipeline: 5 iterative failures resolved (evidence preserved)

- Attempt: rebuild all candidate anchors on hosted runners (anchor-verify.yml) with UCI identity
  + SHA-256 + license checks (mission §3.2).
- Failures, in order, each diagnosed via check-run annotations (the only runner readout):
  1. `ls LICENSE* COPYING* license*` exit-6 trap: unmatched globs make `ls` fail even when
     LICENSE matched. Fixed with `shopt -s nullglob` array test.
  2. `sed 's/\n/%0A/g'` line-based annotation escaping never matches (sed is line-oriented);
     replaced with python replace() chunking.
  3. WyldChess download 404: tags are `v1.2`/`v1.1` (script derived `1.2`). Fixed prefix.
  4. Raven binaries abort at startup on Ubuntu 24.04 (`*** buffer overflow detected ***`,
     rc=134): upstream `parsefen` 1-byte VLA overrun (position.c:27, ASAN: dynamic-stack-
     buffer-overflow, strcpy into `char fen[strlen(ofen)]`). Hardened gcc13/_FORTIFY_SOURCE=3
     traps it; author-era builds did not. Anchor source NEVER patched; built with
     -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 as documented accommodation (research evidence).
  5. SF10 node-count parse missed `Nodes searched  :` spacing → regex fixed; calibration job
     green (factor k=1.0291 vs i7-4770K).
- Raven 0.50–0.90 then EXCLUDED anyway: NO license file at any tested revision (LICENSE.md
  GPL-3.0 only added 2025-02-07 at HEAD) — unverifiable license under the fail-closed rule.
- Result: 6/6 pool anchors green on runners (run 43597866181) + verify-flawless (bench
  signature fc907eba40b7869f reproduced) + sf10-calibration. Pool frozen in
  benches/anchor-pool.json; rating-run acquire step implemented (artifact download + hash
  verify, rebuild fallback, fail-closed).
- Lesson: annotate real stderr/rc on every runner step; glob-listing tests must use nullglob;
  pin tag names verbatim from the tags API; license must exist at the EXACT revision.
## 2026-11-14 (seg-12) rating-run dispatch run 43601200490 (9ec9fb7) — FAILED, remediated

- Symptom: marker-file dispatch FIRED correctly (resolve job validated schema, matrix fanned out shard0+shard1), but both shard jobs failed at "Verify checkout is the frozen commit" (job names rendered "---shard1" = empty purpose/batch/anchor).
- Root cause: the resolve step wrote the `config` job output DOUBLE-encoded (`json.dumps(json.dumps(cfg))`); `fromJson` then yielded a JSON *string*, so `.resolved_target_commit` was null and actions/checkout fell back to the PR merge commit — SHA mismatch against the resolved target (expected fail-closed behavior doing its job).
- Fix: single-encode `config` (`json.dumps(cfg)`); dispatch.json revision bumped to 2 to deliberately re-dispatch (marker-file mechanism).
- Related historical note: run 43586802869 (10:45, head f53cb9c, job pilot-or-shard, 9s failure) came from the pre-rewrite rating-run.yml and is superseded by this mechanism; not investigated further.
## 2026-11-14 (seg-12) FALSE-GREEN local gate invocation — corrected

- `python -m unittest test_match` / `python -m unittest test_rating_estimator` run **0 tests** (both files use custom `main()` runners with `check()` counters, no unittest.TestCase). My local-gate claims invoking them ("104/104, 46/46 (unittest)") were mis-described: the counts are real but came from the proper runners (`python scripts/test_match.py` -> 104 checks; `python scripts/test_rating_estimator.py` -> 46 checks then, 50 now). CI (.github/workflows/ci.yml) was never affected — it runs the suite files directly. Correct invocation recorded; AGENTS_LOG entry 251/257 wording superseded by this entry.

## 2026-11-15 — Evidence-commit pushes failed from DETACHED HEAD ("src refspec ... does not match any") — FIXED + regression-tested

- Affected executions (all observed live):
  - evidence-bridge rev 2, run `43611827091` (head 93abb1e): aggregated pilot + pilot-dup
    evidence successfully, FAILED at the "Commit evidence to the branch" step — the commit
    existed only on the ephemeral runner and was never pushed (runner commits 6cbfdd2/0cb06ef
    are NOT on the remote branch).
  - SCREENING-1 run `43609372547` and SCREENING-2 run `43609636030`: all 15 shard jobs
    completed and uploaded shard artifacts + aggregate mirror artifacts, but the in-run
    `evidence` job failed at its commit step for the same reason → run conclusion = failure
    (fail-closed; no partial evidence claimed). Aggregate mirrors WERE uploaded (if: always()).
- Root cause: both workflows check out with `actions/checkout@v4` at
  `ref: ${{ github.event.pull_request.head.sha }}` → DETACHED HEAD. The publish step then ran
  `git push origin "$BRANCH"` — a local-ref refspec that matches no branch in detached HEAD,
  failing with `error: src refspec arena/... does not match any`. The preceding
  `git pull --rebase origin "$BRANCH"` succeeded (rebase onto the fetched remote branch works
  detached), which masked the real defect until the push step failed 5/5 retries.
- Fix (both `evidence-bridge.yml` and the `evidence` job in `rating-run.yml`):
  1. publish with the EXPLICIT refspec `HEAD:refs/heads/$BRANCH` (valid from detached HEAD);
  2. wrong-branch safeguard: refuse any destination that is not the PR's `arena/*` branch
     (never main, never another branch);
  3. verified rebase-retry loop for concurrent evidence commits: fetch the remote tip,
     `git rebase origin/$BRANCH` (patch-identical commits are dropped → idempotent no-op
     push), abort-with-diagnostics on conflict; ancestor-state check prevents force-like
     surprises;
  4. push/pull attempt diagnostics logged each attempt;
  5. evidence-bridge gained an `if: always()` aggregate mirror upload so an Actions-side
     aggregation can never again be lost to a failed commit.
- Regression coverage: `scripts/test_evidence_push.sh` (T1 detached-HEAD explicit-refspec
  push; T2 concurrent-advance rebase-retry; T3 wrong-branch refusal; T4 static guard on both
  workflow files) — 10/10 PASS 2026-11-15.
- Hosted verification: evidence-bridge revision 3 (deliberate marker dispatch) re-collected
  all recovered runs and its commit step PUSHED successfully from Actions — recorded in
  AGENTS_LOG.md with the run id. Not a green light for anything beyond pipeline correctness.

## 2026-11-15 — Estimator self-match metric could not implement the registered CTRL-2 definition — FIXED + regression-tested

- Observation: CTRL-2 (flawless vs identical binary, 240 games) evaluated from the committed
  evidence scored 0.6604 white-perspective, CI [0.571, 0.746] — outside the registered
  0.5-in-CI acceptance. The `control_self_match` implementation derives the score from engine
  NAME matching, which is degenerate for self-match records (both labels identical, "Flawless"):
  every game took the white branch, so the metric measured the CHESS color advantage, not the
  seat-symmetry quantity the registration defines ("identical binary must score 0.5 within its
  95% binomial CI" — the color advantage cancels only under the schedule's AB/BA seat reversal).
- Fix: when both seat labels are identical, the seat perspective is taken from the recorded
  `color_pair` field (AB: seat A white; BA: seat A black) — `self_match_seat_score()`; missing
  `color_pair` fails closed; `white_perspective_score` is reported for transparency. The
  registered threshold (0.5 in 95% CI) is UNCHANGED. Regression tests:
  `test_self_match_seat_perspective` + updated `test_focus_label_case_insensitive`.
- Re-evaluation (seed 20261116, unchanged inputs): seat-perspective score 0.5146, 95% CI
  [0.4792, 0.5500] → 0.5 inside → CTRL-2 PASS. White-perspective 0.6604 recorded as the
  chess color advantage (consistent with ~55-58% typical white edge plus a second-side time
  penalty; see the flag-race entry below).
- Related fix in the same change: focus-engine matching is now case-insensitive
  (`same_engine`, casefold) — the harness historically seated the focus engine under the
  display name "Flawless" while the estimator focus and pool keys are lowercase; the old
  exact-match `load_games` would have failed closed on ALL committed flawless evidence (and
  would have failed any confirmatory gate). Labels are display metadata; engine identity is
  the manifest-verified binary SHA-256; no two pool keys differ by case. Suite: 65/65.

## 2026-11-15 — SCREENING-1/2 root-cause: ~95% of Flawless losses are FLAG FALLS (time forfeits) — engine time-management defect identified

- Raw evidence (benches/evidence/screening/*): SCREENING-1 end reasons = 113 flag / 4 checkmate
  / 3 repetition; SCREENING-2 = 114 flag / 4 checkmate / 1 repetition / 1 stalemate. Flawless
  lost 116/120 and 118/120, ALL decisive losses but 3-4 by flag. Winner remaining clock at
  flag ≈ 2 s; loser (Flawless) at −1 ms. Flag plies concentrate in period 3 (p10/p50/p90 =
  81/84/87). The self-match (CTRL-2) shows the same regime: 199/240 flag ends.
- Root cause (code inspection, src/uci.rs clock_limits): `soft = clamp(t/mtg, 20, 30_000).min(t)`
  with `hard = min(6*soft, max(t-30, soft))`. The 30 s soft cap makes the engine OVERSPEND its
  period plan in the late period (soft pinned at 30 s while the clock shrinks below the plan),
  and hard = 6×soft permits single-move spends down to a ~30 ms remaining clock. Across the
  observed long games (83+ plies) the engine reaches period 3 with ~zero reserve and loses the
  flag race against anchors that budget with reserves. This is an implementation defect, not
  evidence that the search/eval strength equals a 1632-Elo level: the 100 ms-movetime probes
  (STATUS.md) measured search/eval strength without clock effects.
- Secondary observation (harness): in the self-match the second side to move loses flag races
  138:61 — a small per-move time-charging asymmetry (~tens of ms/move) consistent with the
  move-loop's second-side latency. The seat-perspective control passes (0.5146 ∈ CI); after
  reserve-bearing engine time management lands, flag races become rare and the asymmetry's
  impact shrinks; recorded here for the harness audit trail.
- Remediation: registered as ENGINE-1 (see PREREGISTRATION.md) BEFORE any new games: replace
  the budget formula with a reserve-bearing one (never plan past the period, keep a safety
  reserve, bound the hard limit), add clock-allocation regression tests, re-verify suites,
  re-screen the new candidate (SCREEN-2, fresh seeds), and only then re-apply the anchor
  selection rule. Batch A/B dispatch is DEFERRED — see PREREGISTRATION.

## 2026-11-15 — ENGINE-1 implemented and locally verified (registered 2026-11-15 before implementation)

- Change: `src/uci.rs clock_limits` replaced with the registered reserve-bearing budget:
  reserve = clamp(t/16, 300 ms, 8 s); soft = max(20 ms, (t−reserve)/mtg) with the old
  30 s upper clamp removed; hard = min(4·soft, (t−reserve)/2, t−reserve/2), floored at soft.
  Full-period utilization for repeating 'add' schedules is retained; a safety reserve now
  absorbs per-move overhead and the hard limit can no longer consume the whole clock.
- Verification (ENGINE-1 acceptance 1–3):
  (1) NEW regression test `clock_limits_engine1_no_flag_death_march` — full 40-move period
      simulation with 60 ms/move overhead completes with the reserve intact; no hard-limited
      move can flag; sudden-death drain stays within budget; the old starved-period trigger
      (45 s clock, movestogo lost) no longer overspends;
  (2) all suites green: cargo test --release 35/35 (lib 7 incl. the new test + clock_smoke 3
      + correctness 21 + uci_smoke 4), cargo fmt --check clean, cargo clippy --all-targets
      -D warnings clean, scripts/test_match.py 104/104, scripts/test_rating_estimator.py 65/65;
  (3) bench signature UNCHANGED `fc907eba40b7869f` (2,221,199 nodes @ depth 10) — the clock
      fix touches time allocation only; search/eval are byte-identical, so all prior
      correctness verification (perft 27/27, differential 76,240 positions) remains valid.
- Acceptance (4)/(5) are hosted/local play checks: SCREEN-2 (flag rate ≤ 10/120 per registered
  criterion) and the SF19-lite skill-5 A/B probe — to be recorded when executed. The new
  engine binary hash is UNFROZEN until the runner build records it (freeze mode), then pinned
  in PREREGISTRATION before any confirmatory dispatch.

## 2026-11-15 — anchor-verify ANCHOR-2 legs: 3 iterative failures resolved via runner annotations (evidence preserved)

- Run 43692582888 (head 4dbeeec): stockfish-5/8 rc=5 UCI ID MISMATCH — the SF id line is
  "Stockfish N 64"; I had wrongly embedded the AUTHOR banner into EXPECTED_ID (local smoke
  misread the banner line as the id). leorik-2.5 rc=4 BINARY MISSING — the repo root holds
  only Leorik.sln; the engine project is Leorik.Engine/ so `dotnet publish` at root has no
  project. akimbo-0.5.0 + weiss-1.2 + all 6 pool legs green on the first attempt.
- Run 43693256193 (head 56ef6a5): SF legs rc=0 (id now matches, binary recorded) but the
  WORKFLOW license step failed: "no LICENSE file" — the license glob is case-sensitive and
  SF ships `Copying.txt` (the pool anchors happened to use exact-case LICENSE/COPYING);
  leorik still BINARY MISSING — dotnet names the apphost after the PROJECT
  (publish/Leorik.Engine).
- Run 43693679899 (head 932ae99): SUCCESS — all 11 legs green; license glob now matches
  Copying*; leorik publishes its engine project and the apphost path corrected.
- Lessons: expected UCI ids must come from the actual id-name line (captured via the
  diagnostic run), not the banner; C# repos publish the ENGINE project, not the solution
  root; case-sensitive license globs must include Copying* for SF-family tags. All three
  fixes are in scripts/anchor_build.sh / anchor-verify.yml with annotated diagnosis trails.

## SCREEN-2-TIMEOUT (recorded 2026-11-15)

- **Experiment id:** SCREEN-2 (runs 43685671431 vs topple-0.1.1 seed 20261123; 43686056730
  vs topple-0.2.1 seed 20261124), marker rev 10.
- **Baseline SHA:** ENGINE-1 candidate, runner-built binary
  9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428 (30 builds, byte-identical).
- **Configuration:** 15 shards × 8 sequential games per run; TC 40/15 repeating 'add';
  batch-A suite 2c4a54d8…; workflow timeout-minutes 330.
- **Hypothesis under test:** ENGINE-1 flag rate ≤ 10/120 per screening + screening estimates.
- **Outcome:** FAILED (execution shape, not engine): all 30 shard jobs killed at the 330-min
  workflow timeout (started 06:29:43Z, killed 11:59:43Z/12:05Z); evidence jobs skipped
  (strict 15-shard aggregation precondition unmet).
- **Raw evidence location:** 30 artifacts (15 per run) downloaded to /tmp/scr2-<run_id> at
  inspection time; per-shard manifests + games.jsonl + games.pgn + runner-hardware.txt.
  Partial stats: 174 counted games, 1 flag, 0 engine errors, identities verified.
- **Measured uncertainty (selection-only, partial):** vs topple-0.1.1 score 0.3547 (n=86)
  → est ≈ 2428; vs topple-0.2.1 score 0.1724 (n=87) → est ≈ 2712. NOT acceptance evidence;
  recorded as exploratory signal only.
- **Failure/rejection reason:** shard sizing used PILOT-1's 29.43 min/game (old candidate,
  flag-shortened games); the fixed clock makes games run full-length (measured mean 52.0,
  max 147.5 min) ⇒ 8-game shards cannot fit any hosted timeout.
- **Lessons for subsequent experiments:** size every shard from MEASURED durations of the
  actual binary (SHAPE-1: 2 games/job, timeout 350; batches 1020 × 2 in 4 runs of 255;
  CTRL-2-R 120 × 2); a timeout kills jobs silently — check run conclusions, not just
  artifact presence; recovery = re-run failed jobs, never mix partial evidence.
- **2026-11-16 — SCREEN-2R run 2 (43714620645, vs topple-0.2.1), job 132843722744 (shard 17): FAILED, cause = runner/infrastructure failure.**
  Evidence: match step ("Run tournament shard (match.py)") frozen with conclusion=null;
  job window 17:20:05Z→19:33:10Z (~2h13m — longer than every successful sibling shard);
  NO error lines, NO artifact (upload step never ran), NO check-run annotation; the job
  log blob is gone (404 BlobNotFound) and the job is absent from the run logs archive
  (120 files = 59 shards x 2). This is a runner-level interruption mid-match, NOT an
  engine/harness failure (identical binaries completed 58/59 sibling shards + all 60 of
  run 1; aggregate job correctly skipped by needs.shard.result gate).
  Remediation: single-shard retry with identical frozen identity (marker rev 12, only
  shard_indices=[17]; seed 20261124, tc 40/15, pinned engine hash, suite hash, shard_count
  60 → shard 17 covers global indices 34,35). Workflow gained a marker-level run_evidence
  flag (this dispatch sets run_evidence=false) so the retry does NOT commit partial
  evidence at the canonical path; canonical aggregation happens offline via
  recover_screen2.py with merged artifacts (59 + 1) and explicit evidence commit.
  Tooling defects found & fixed during recovery prep (scripts/test_recover_download.py +
  scripts/verify_run1_both_paths.py): (a) REST artifact fallback passed b"" to ZipFile
  (text-mode stdout) — fallback could never succeed; now downloads zips to files (binary).
  (b) artifacts listing / gh download are paginated (default 30) — gh path silently
  truncated 60 shards to 29; now paginate (per_page=100) + post-download shard-count
  check with REST top-up. Both paths independently verified on run 43714600687:
  byte-identical aggregation matching committed evidence f4fc95c7c32f587b (120 games).
- **2026-11-16 ~07:00Z — SCREEN-2R run-2 recovery SUCCESS.** Retry run 43806800011 (shard 17
  only, run_evidence=false) completed/success; artifact downloaded via REST fallback path;
  merged 59+1 artifacts strict-aggregated fail-closed (60 shards, 120 counted games, engine
  hash = pin 9663697d…, 0 engine errors, 0 replays). Recovered evidence committed as 0cdeedf
  (benches/evidence/screening-2/topple-0.2.1/) and re-verified byte-identical on a second
  full recovery pass (bytes_match_committed=True for BOTH anchors; recover_screen2.py
  OVERALL: PASS). Result: W30 L82 D8, 0 flag losses (≤10 PASS), score 0.2833 →
  est = 2277.8 vs topple-0.2.1 (published 2439). Two tooling expectation bugs fixed during
  recovery (merged-slot per-run shard expectations; driver commit gate now validates the
  aggregation manifest rather than recover's overall exit code).
- **2026-11-16 ~07:25Z — draw-scoring bug in recover_screen2.py's REPORTING lambda (caught by cross-check, no evidence contamination).**
  The inline score lambda `((result=="1-0") == flawless_is_white ? 1.0 : draw? 0.5 : 0.0)`
  scored flawless-as-black DRAWS as 1.0 instead of 0.5, inflating the printed score/estimate:
  reported 0.3625/0.2833 (est 2225.9/2277.8) instead of the CORRECT 0.3000/0.2375
  (est 2176.8/2236.4; combined est 2206.6). make_gate_plan.py's focus_score (the registered
  perspective) is correct and was used as the reference; recover_screen2.py now matches it
  exactly (re-verified: identical scores on both anchors). UNAFFECTED: committed raw evidence
  (aggregate_shards.py output), manifest fields, flag-loss counts (decisive losses only),
  byte-match checks, and the SCREEN-3 anchor choice (ordering of |est−R_a| unchanged:
  akimbo-0.1.1 = 234.4 < wyldchess-1.2 = 238.4 < wyldchess-1.1 = 267.4; wowl = 357.6).
  The rev-14 marker description quotes the old numbers; its anchor/seed/sampling are correct
  (resolver does not validate description text) — this ledger entry is the authoritative
  correction. Same lambda in scripts/dry_validate_run2_59.py fixed too.
  NOTE for the 2000-gate: all screening estimates are selection-only; the gate uses
  confirmatory evidence via rating_estimator.py (audited separately vs §9).
- **2026-11-16 ~08:35Z — merge_batch_runs.py identity check was vacuous (found in pre-campaign
  audit, FIXED + regression-tested).** The cross-run identity comparison used manifest keys
  (white_name/black_name/time_control/openings_file_sha256/schedule/n_scheduled) that no
  per-run manifest actually contains (aggregate_shards.py writes batch/anchor/engine_sha256/
  anchor_sha256/opening_suite_sha256/...), so every identity compared equal on None and the
  promised drift detection could never fire. id_keys now match the real manifest shape and
  test_merge_batch_runs.py case 3 drifts engine_sha256 across runs (verified fail-closed).
  Defense-in-depth unchanged: verify_evidence.py re-checks engine/anchor/suite hashes at the
  canonical dir post-merge.
## 2026-11-17 — implementation defects caught before branch update

- **Incorrect first-pass opening subsets:** the initial 50-row candidate files did not match the stated SHA-256 lowest-50 selector. Recomputed both subsets from the original committed 60-row suites, discarded the first drafts, created exact deterministic subsets retaining source order, and added an automated verifier for selector, byte hashes and Batch A/B disjointness. Do not use the discarded suite hashes.
- **Workflow resolver validation order / source escaping:** an early draft checked shard count/repetition before parsing them and included a literal escaped newline in a Python source list. Reordered validation after parsing and corrected the malformed source line before commit.
- **Cross-batch evidence path collision:** the first evidence path used only the anchor key, so Batch A and Batch B could share a per-run evidence root. Updated to `confirmatory/batchA/<anchor>/run-<id>` and `confirmatory/batchB/<anchor>/run-<id>`.
- **One-leg recovery gap:** a two-game shard could count one color leg and abort before the reverse-color leg; rerunning the whole shard could duplicate the counted game. Added exact schedule-index selection to match.py, dispatcher-generated per-shard missing-index maps, and merge-level exact slot verification.
- **Skipped evidence jobs in completed screening/control workflows:** SCREEN-3 run 43820645420 and CTRL-2-R run 43820392119 completed all resolver/shard jobs but each skipped `aggregate-and-commit-evidence`. Their artifacts are not canonical committed evidence. Resolver config now defaults evidence capture on; only explicit `run_evidence: false` opts out. Historical runs are not retroactively relabelled or claimed aggregated.
- **SEE pruning reconsidered:** removed SEE-negative capture pruning from quiescence before implementation. SEE's pin-legality model is approximate; the candidate uses SEE for ordering only. No performance or Elo effect is asserted before testing.

## 2026-11-17 — validation issues caught before follow-up commit

- **Rustfmt:** first hosted CI found five formatting diffs in SEE helpers on Linux and Windows. Fixed to match rustfmt output exactly; no algorithm change.
- **Bench fingerprint:** the SEE ordering changed the deterministic depth-10 signature from the old `fc907eba40b7869f` to the measured `141943aa23b3fc68`. The old anchor-verifier expectation was stale; update it to the new measured fingerprint and rerun verification. Do not claim the candidate binary hash until the successful run writes it.
- **Evidence boundary:** rating-gate failure was the expected fail-closed result with no gate plan; rating-run resolver skipped all shards because `benches/dispatch.json` was unchanged. Neither failure is evidence of a rating or game result.

## 2026-11-17 — SHA-256 subset-generation defect caught by CI

- Symptom: Linux and Windows CI both rejected Batch A in scripts/verify_opening_subsets.py on run 44062359630. The failure occurred after Rust fmt, clippy, Rust tests and all Python regression suites had passed.
- Root cause: the one-off JavaScript helper used to select the 50 lowest SHA-256 digests omitted SHA-256 round constants. Therefore the selected opening sets were not the sets defined by the registered standard SHA-256 selector, despite the first helper's self-consistent output hashes. The repository's hashlib implementation correctly detected the mismatch.
- Containment: no confirmatory dispatch occurred; the power report remained BLOCKED; no games or rating results were created from these bad suites. The faulty files and hash pins are superseded, not reused.
- Correction: regenerated both suites with the standard SHA-256 constants and byte-tested hashes; Batch A 5abdcdbddec0f22d7e6eff8974ee402363c8c3df318b8110d7204adf69f5c1df, Batch B ccb4901742eca25b0b10f1a3c9fdfc17b2967a1939c2d7e466c2c5495b6d4253. Updated verifier pins, dispatch-tool pins, machine-readable report, CI assertions, append-only preregistration/protocol correction, and explicit LF checkout rules. The corrected suite bytes remain PENDING until hosted CI passes the verifier on the new commit.


## 2026-11-17 — resolution of selector CI failure and new engine provenance guard

- Corrected suites passed the deterministic selector check on both Ubuntu and Windows in CI 44066217195; each suite has 50 unique openings, zero overlap, and the exact registered byte SHA-256.
- Exact-head CI 44066217195 passed: Linux, Windows and MSRV 1.80; all Rust, Python harness, estimator, reduced-sample, dispatch-recovery, power-manifest, merge, suite selector and power smoke checks. The previous run 44062359630 remains a historical failure and is not overwritten.
- Added a fail-closed provenance guard so SCREEN-2 power data cannot be used for a different engine binary: both source manifests must prove the same ENGINE-1 hash, exact original screening-suite hash, 120 counted games/120 attempts and correct merged raw-game hashes; the dispatcher and workflow compare the report's engine SHA with the actual dispatch SHA.
- ENGINE-2 binary hash is now measured and pinned to source tree 75bc5633e1466d5abf1f4c7d5999bc4a3915e193 (branch source commit 5b63e273d77cfb097f0ad73bc28dda05cc19adad): 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7. No candidate-specific games or controls have been run.

## 2026-11-17 — provenance regression expected-error mismatch

- **Observed:** CI run 44067364552 on commit 29b627e failed the new power-analysis test suite (3/4 tests); the failing case expected an error string mentioning the later same-engine comparison.
- **Root cause:** the test supplied a non-SCREEN-2 engine hash. The production guard correctly rejected it earlier in read_screening_manifest because the power model is explicitly registered only for SCREEN-2 / ENGINE-1. The test asserted the wrong layer of the fail-closed path.
- **Correction:** change the expected message to "preregistered only for SCREEN-2". No production logic was changed or relaxed. Full CI on the follow-up exact HEAD is required before declaring validation green.

## 2026-11-17 — CRLF/LF mismatch in power evidence hash verification

- Observed: CI 44067826990 passed Ubuntu but Windows failed with merged_sha256 mismatch on a committed SCREEN-2 games.jsonl file.
- Root cause: tracked JSONL evidence was converted from LF to CRLF by Windows checkout; manifest hashes represent the original Linux LF bytes.
- Fix: hash canonical UTF-8 JSONL text after converting CRLF/CR line terminators to LF only. Add repository attributes forcing LF for the two SCREEN-2 evidence JSONL files. Add a test for CRLF checkout compatibility and another proving actual record edits still fail the SHA check.
- No data or benchmark result has been rewritten; no confirmatory dispatch occurred.

## 2026-11-17 — manual review disposition (session 2)

- Findings R-01, R-04, R-05, R-06 from REVIEW_MANUAL_03d2066.md did NOT reproduce at head 3ebf617 (reasons in REVIEW_MANUAL_071f875.md). The original file is unchanged; the dispositions live in the companion file.
- Fixed with evidence: R-02, R-03, R-07, R-08, R-10, R-12, R-13 (engine side).
- R-08 residual: one iteration whose time grows more than 3x can still overrun soft; bounded by the hard limit. Not eliminated.
- MSRV 1.80 build NOT VERIFIED: no 1.80 toolchain available (npm mirror has none; rustup blocked). Open blocker.
- Binary-identity blocker: R-02/R-03/R-07/R-08/R-10 change the engine binary. The ENGINE-1 hash frozen in PREREGISTRATION.md no longer identifies this code. Any gate or confirmatory evidence for the new behaviour needs a new candidate hash registered before dispatch. Not done; requires a decision.
- rating-gate (failed at 3ebf617 and at 071f875): cause not yet investigated; left as fail-closed.


## 2026-11-19 — GUI launch with no arguments exits 2 (UCI startup incompatibility)

- **Attempted:** CrispChess Extended (2.3.2-dev6+23, Windows 10 LTSC 2021) registered a custom engine `flawlessv1 patch2.exe`. The generic UCI launcher starts it with `Process.start(path, [])` and then sends `uci`.
- **Observed (raw evidence: user bundle `diagnostic-report.zip`, `application.log` and `errors.json`, 2026-11-19T21:12:56 local):** `engine.process.started` followed about 40 ms later by `engine.process.lost`, then `initialize.failed` with `Engine "flawlessv1 patch2.exe" exited while searching (exit code 2)` and stderr `usage: Flawless [uci|perft …]`.
- **Conditions:** the user's Windows binary's commit is not recorded in the bundle; its stderr reports `Flawless 0.1.0-dev.1`. The startup code of `main` at `5e36b06` has the same behaviour (verified locally). Local reproduction: Linux, Rust 1.99.0, release build, same commit: `flawless` with no arguments → exit 2 with usage on stderr; `flawless uci` → full handshake.
- **Root cause (verified from source and behaviour):** `src/main.rs`, the `None =>` arm of the argument match printed usage and called `std::process::exit(2)`. The engine's default startup was therefore not UCI.
- **Why the existing tests missed it:** `tests/uci_smoke.rs` always started the binary with the `uci` argument, so no test launched the engine the way GUIs do.
- **Result:** fixed in the session branch. Regression tests (no-argument lifecycle and handshake parity) fail on the old `src/main.rs` and pass on the fix. Exact-head CI and the Windows artifact are recorded in the audit report.
- **Learned:** a UCI engine must treat "no arguments" as UCI mode. Tests that only exercise the explicit subcommand cannot cover GUI launch behaviour.
- **Next experiment:** run the Windows artifact `flawless.exe` under a real UCI GUI launcher (CrispChess Extended) to confirm the engine is added without the exit-2 error. Not done in this session: no GUI is available here.

## 2026-11-19 — UCI smoke could accept a depth-0 bestmove when `quit` follows `go` in the same input

- **Attempted:** pipe `uci / isready / position startpos / go depth 2 / quit` into the release binary, as the CI smoke steps and the first version of the artifact checker did.
- **Observed:** the pipe run prints `bestmove a2a3` and no `info` lines. The same position in an interactive session (wait for each reply) prints `info depth 1` and `info depth 2`, then `bestmove b1c3 ponder b8c6`. Found during CodeRabbit review of PR #3 at `df0097e` (finding: "Wait for bestmove before sending quit").
- **Root cause (verified from source):** `src/uci.rs` `quit` calls `stop_and_join`, which sets the stop flag. Input already buffered when the search starts therefore stops it at depth 0, and the fallback root move is printed. The pipeline does not wait for a search reply.
- **Impact:** the existing CI step "UCI bestmove smoke test (search depth 2)" checks only the bestmove shape and legality, so it passes on a depth-0 result. It proves less than its name says. The Rust lifecycle test in `tests/uci_smoke.rs` is not affected: it reads `bestmove` before sending `quit`.
- **Conditions:** Linux, Rust 1.99.0, release build, commit `df0097e`. Engine behaviour is unchanged by this session; the pre-existing CI step was not changed.
- **Fix in this session:** `scripts/windows_artifact.py` now drives an interactive session and sends `quit` only after `bestmove` is read, with bounded waits. Its `bestmove` parser accepts the `ponder` suffix.
- **Open:** the existing ci.yml pipe-based smoke step should be made interactive or removed in favour of the Rust test. Not changed here; flagged for a decision.
- **Learned:** a protocol smoke test must synchronise on replies. A bestmove that is merely legal does not prove a search ran.

## 2026-11-19 — resolution: pipe-based bestmove smoke replaced by a synchronised check

- The CI step "UCI bestmove smoke test (search depth 2)" is replaced by `scripts/uci_bestmove_smoke.py`. It waits for each reply, sends `quit` only after `bestmove`, and requires a completed `info depth 2` line before `bestmove`. A depth-0 fallback is rejected; `scripts/test_windows_artifact.py` covers both paths.
- The Windows artifact smoke test uses the same session and depth check.
- Verification of the new step: local run against the release binary passed (`info depth 2 … bestmove b1c3 ponder b8c6`). The CI result is recorded in the audit report.

## 2026-11-19 — CodeRabbit a7b7eda findings: harness false-passes (fixed)

- Three checker bugs could hide defects in the Windows artifact harness: aliased handshake snapshot, unchecked stdout after `quit`, and an unreachable no-command stdout check. None affected the engine, which passed all probes. Fixed in the harness; regression tests added.

## 2026-11-19 — repeat of the quit-in-same-input pattern during the release validation

- An early movetime measurement sent `go` and `quit` in one stdin burst, so the engine returned a depth-0 fallback (`bestmove a2a3`) and gave a misleading "6–10% of budget" result. Caught before any conclusion was drawn. All timing claims now use interactive waits. The probe scripts document this.

## 2026-11-19 — FIXED: `go movetime N` returned after 39–100% of N

- Root cause: `src/search.rs` iterative deepening stopped when `now + 3 × last_iteration > soft_budget`. With `movetime`, soft equals the full budget, so the search stopped early (measured 39–100% of N, depth 7–16).
- Severity: medium (play strength and time use; no illegal moves, no hang).
- Fix: `fixed_time` flag disables the prediction stop for fixed-time searches only. Clock searches unchanged.
- Regression: `tests/movetime_smoke.rs` (restoring the old rule makes 2 tests fail: `movetime_uses_its_budget_within_tolerance` at 81 ms for 200 ms, and `repeated_movetime_searches_in_one_process`).
- Note: an earlier measurement of this symptom used `quit` in the same input as `go`, which is an invalid method (see the entry above). The fixed numbers use interactive waits.

## 2026-11-19 — FIXED: ponderhit answered at once after `go ponder movetime N`

- Root cause: `cmd_go` stored `last_clocks` on every `go`, including zeros when no clock was sent; `ponderhit` then recalculated a budget of about 20 ms from those zeros. Measured 1 ms (movetime ponder) on the candidate head before the fix.
- Severity: medium (ponder with GUIs that send `go ponder movetime`).
- Regression: `ponder_movetime_ponderhit_keeps_the_movetime_deadline` (fails on the previous uci.rs).

## 2026-11-20 — FINAL AUDIT: defects reproduced and fixed on arena/f668bde4-flawlesschess

- F-01 HIGH: a legal-looking dense FEN (`KQQQQQBk/Q5RB/Q6Q/Q6Q/Q6Q/Q6Q/Q1QQ3Q/QR3QQQ w - - 0 1`) crashed `go` with exit 101 (move-list overflow at types.rs). Fixed: FEN material limits + capacity 512 + hard push check. Regression tests added.
- F-02 HIGH: a non-UTF-8 stdin line ended the UCI session silently. Fixed: byte-level bounded reader. Regression tests added.
- F-03 HIGH: `go wtime N` alone had no time limit. Fixed: single-side clock bounds the search. Regression test added.
- F-04 MEDIUM: Hash 4096 was accepted but the table was silently capped at 1 GiB (RSS identical for 1024 and 4096). Fixed: advertised and accepted maximum is 1024. Regression test added.
- F-05 LOW: `clock_limits` could wrap on huge clocks. Fixed with saturating arithmetic. Unit test added.
- F-06 LOW: option rejection messages went to stderr only. Fixed: stdout info strings. Test added.
- NOT REPRODUCED (kept as regression tests): illegal-only `searchmoves` returned `bestmove 0000` (it returns a legal move); `go ponder nodes N` ignored its cap after `ponderhit` (with ponderhit sent immediately the search stops near N). Ponder node-cap test added.
- OBSERVATION (not a defect, not fixed): `go nodes N` stops below N (e.g. about 651 nodes for N=1000, 81,210 for N=100000). The cap is an upper bound and is not exceeded. The cause of the undershoot was not analysed.
- OPEN: MSRV 1.80 could not be run locally (the 1.80.0 toolchain is not on the npm mirror). The CI `msrv` job is the check of record.

## 2026-11-20 — FINAL AUDIT batch 2: checker validation and verification tools

- F-08 (MEDIUM): `from_fen` accepted positions with three checkers on the side to move, or two checkers on one line through its king (e.g. `1b4NQ/8/7R/3q4/3P1bn1/3k1K1P/3p4/2B1bN1q w - - 0 1`). Found by differential fuzzing against python-chess (14 such positions accepted in the seed-1 differential run: 40 random games plus placement fuzz). Fixed in `from_fen`. Regression tests added.
- EP-01: no saved self-play game contained an en passant capture, so full-game en passant was unverified. Added `scripts/fullgame_en_passant_probe.py` (python-chess referee, forced en passant, engine-vs-engine to the rule end). Passes; added to CI.
- S-14 (OPEN, informational): search is not colour-symmetric at depth 4 for 2 of 40 random positions (446 vs 493 cp, and 1284 vs 1262 cp). The static evaluation is symmetric on the same positions. Not treated as a bug; to be investigated only if a search defect is suspected.
- TEST ARTIFACT (not a defect): sending `go` and `quit` in one stdin burst returns the unsearched fallback move. Probes wait for `bestmove` before `quit`. Already documented in CHANGELOG.

## 2026-11-20 — PR #4 review findings in the audit harness (fixed)

- The UCI fuzzer accepted a session when any earlier `readyok` appeared, so a dropped final `isready` could pass. Fixed: exactly one `readyok` per session, generator never emits `isready`.
- The Windows artifact checker dropped a malformed extra `bestmove` before counting (regex filter). Fixed: count over the whole transcript first; regression tests added.
- The protocol and malformed probes validated only the first `bestmove`. Fixed; self-tested against a fake engine that prints two replies.
- Probes waited without a deadline (eval symmetry, en passant forced search) and the en passant probe ignored a failed quit. Fixed.
- The Rust protocol harness could block on a stdin write before its reply deadline. Fixed with a writer thread.
- A test named "double check" used a position with a single check (knight on g1). Fixed; the position is now a verified double check.

## 2026-11-20 — final-head review and symmetry diagnosis

- F-09 (LOW, UCI wording): Codex P2 on `3a280df` (`src/search.rs`): `go searchmoves` with no legal named move widens the search to all legal moves, outside the requested set. Decision recorded in DESIGN_LOG 2026-11-20. Fixed in part: the widening is now announced on stdout (`info string`). Kept by design: a null move is the defect the mission names. Tests: `illegal_only_searchmoves_still_returns_a_legal_move` (now asserts the notice), `legal_searchmoves_are_respected_without_widening_notice` (control).
- S-14 DIAGNOSED (informational, not a defect): the depth-4 search mismatch comes from Late Move Reductions. Evidence: static evaluation equal on each pair (`flawless eval`: 353/353 and 743/743; the depth-3 pair 44/44). In a scratch build outside the repo, disabling LMR makes both depth-4 pairs symmetric (446/446, 1262/1262); disabling null-move pruning alone does not (446/493 and 1284/1262). Mechanism: LMR reduces by move index, and the mirror position generates moves in a different order. No search change made; the hard symmetry gate is `static_evaluation_is_colour_symmetric`.
- Windows artifact `flawless-windows-x64-3a280dff77fcf1042dd49789b7442e63fd50a496`: retried at 13:26Z; `gh run download` still fails with EOF from `productionresultssa10.blob.core.windows.net` (curl to that host returns no HTTP status). Unverified. Not retried again in this session.

## 2026-11-20 — S-14 fixed, F-10 found (closed stdout), gate status

- S-14 FIXED (MEDIUM, supersedes the "informational, not a defect" wording above): a colour-relative tie-break
  (`relative_move_key` in `src/search.rs`) removes the depth-4 colour mismatch. Results: depth 4, 120 positions,
  default seed: 6 mismatches before, 0 after. Depth 5, 60 positions, seed 2027: 5 before, 0 after. The 11 recorded
  pairs in `tests/data/search_symmetry_pairs.tsv` pass (they fail on the previous `search.rs`). Cause: equal-score
  moves were ordered by raw square numbers, so the mirror could be searched in a different order; LMR is not
  the fix (disabling it gives 0/120 but costs 18× the nodes). Bench signature `849a85bf7e8e1eba`, 2,311,407 nodes.
- F-10 FIXED (LOW): when the reader closed stdout, the next `println!` panicked (`failed printing to stdout: Broken
  pipe`, exit 101). Found by the audit's pipe probe. All protocol output now uses `out_line!` (`src/lib.rs`), which
  exits 0 on a failed write. Regression: `protocol_regressions::closed_stdout_ends_the_process_quietly` (fails on
  the previous code). Scope: the engine has no other way to end on a closed pipe, so this is in scope and fixed.
- S-08 FIXED (LOW): `go nodes N` overshoot of up to 1,023 nodes came from checking the cap only every 1024 nodes.
  The node cap is now checked per node. Probe before the fix: N=1000 → 1024 nodes, N=5000 → 5,121. Now exact.
- Verification of this entry: fmt, clippy, and `cargo test --release --locked` pass on the working tree (see
  FINAL_AUDIT_PROGRESS.md for the SHA and the exact commands). The Windows artifact and CodeRabbit status are
  unchanged by this entry (NOT VERIFIED and NOT OBTAINED).

## 2026-11-20 — CodeRabbit review of 7d5b489 (five findings, all checked against code)

- F-11 (LOW, valid, fixed): an oversized input line was dropped without marking the position invalid. A dropped `position` left the old position in place, so a later `go` searched the wrong position and printed a bestmove. Fix: the TooLong branch sets `position_invalid`; a later valid `position` clears it. Test: `protocol_regressions::oversized_position_line_does_not_leave_the_old_position_in_use`.
- T-01 (test, valid, fixed): `ponder_node_cap_is_enforced_after_ponderhit` asserted an exact count, but the ponder search is uncapped until `ponderhit` is processed, so the count could pass the cap first (timing-dependent). The test now asserts termination and monotonic node count; exact caps are asserted in the non-ponder tests.
- T-02 (test, valid, fixed): `closed_stdout_ends_the_process_quietly` read the handshake without a deadline and had no kill-on-failure. It now uses the bounded harness; `Engine` kills the child on drop.
- D-01 (docs, valid, fixed): the audit document's blocker list still named the superseded head `c64b743`; the Phase H "Note on SHAs" claimed current HEAD was source-identical to `8370bed`. Both corrected; the historical gate table is unchanged.
- CI-1 (test, fixed): CI on c4fb22f failed in `Tests (release)` on ubuntu-latest (exit 101) and windows-latest (exit 1); `msrv`, the windows artifact job and anchor-verify passed. Logs could not be downloaded (results host EOF) and a rerun was refused (403), so the failing test was not seen directly. Cause (inferred from the code, not reproduced): `closed_stdout_ends_the_process_quietly` sent three `isready` lines after closing the reader. The reader can drain all three `readyok` lines in one read, close stdout, and leave the engine with nothing left to write, so the engine would wait on stdin and never exit. Fix: keep sending `isready` until the engine exits (the first write after the close fails). Locally: 30/30 isolated runs and the full release suite pass; the CI failure is not reproduced. Status: the cause is inferred; re-run CI on the next SHA is the check.

## 2026-11-20 (late) — Audit stretch: F-12, F-13 (corrected), F-14, S-08 provenance, CI hardening

- F-12 FIXED (MEDIUM): the batch modes `flawless moves` and `flawless hash` stopped at the first stdin line that was not
  valid UTF-8 (`lines()` plus `break`), so every later FEN got no reply. Probe before the fix: three input lines, one
  output line. Fix: `for_each_stdin_line` reads bytes with the bounded reader (64 KiB cap). A bad or overlong line gets one
  `error input line is not valid UTF-8 or too long` reply and the batch continues. Regression: `tests/cli_batch.rs`
  (3 tests). The two non-UTF-8 tests fail on the previous `main.rs`; the overlong-line test passes on both (coverage only).
- F-13 FIXED (LOW), with a CORRECTED reproduction. Earlier notes said closed stderr (`2>&-`) made the engine exit 101.
  That could not be reproduced in this sandbox: Rust's runtime reopens fds 0-2 at startup (a probe shows `fd 2` present
  and writes returning `Ok`). The real panic is a FAILED WRITE to stderr. With stderr a pipe whose reader is gone (EPIPE),
  the previous binary exits 101 before `readyok` on an oversized input line; the fixed binary exits 0 and answers
  `readyok`. Fix: `flawless::err_line!` (`src/lib.rs`) ignores write errors; all 17 diagnostic `eprintln!` sites in
  `uci.rs` and `main.rs` use it. Regression: `protocol_regressions::stderr_write_failure_does_not_stop_the_session_on_an_oversized_line`
  (fails on HEAD: no `readyok`; passes on the fix). The test uses a raw `pipe()` binding (test code only, with SAFETY comments).
- F-14 FIXED (LOW): in single-PV mode, a root position with insufficient material (K v K, K+B v K, K v K+N) returned after
  one node with an EMPTY PV. `bestmove` was then the first root move in move order, not a move from the search. Probe on
  HEAD: `info depth 1 seldepth 0 multipv 1 score cp 0 nodes 1 nps 1 time 0 pv ` (empty) and `bestmove e1d1`. Fix in
  `search()` (`src/search.rs`): the insufficient-material draw applies only at `ply > 0`, as the repetition rule already
  does, so the root is searched and yields a PV. The fixed build gives `pv e...` with nodes 6-13. Regression:
  `protocol_regressions::insufficient_material_root_is_searched_and_yields_a_pv` (fails on HEAD: "empty PV").
  No illegal move was ever produced (255 random insufficient-material positions, 0 illegal bestmoves on HEAD).
  Side effect: the bench node total changes from 2,311,407 to 2,311,437 (position 9, an insufficient-material
  position, now searches 40 nodes instead of 10). The bench SIGNATURE is unchanged (`849a85bf7e8e1eba`), because the
  signature covers (fen, depth, bestmove) only and bestmove is the same. BENCHMARKING.md is updated.
- Earlier false alarm, closed: an intermediate probe showed `go depth 3` on K v K answering `info nodes 1` with no
  depth line. Cause: the probe sent `go` and `quit` in one burst, and `quit` stopped the search before its first
  iteration. This is a probing artifact: wait for `bestmove` before sending `quit`. Not an engine defect.
- S-08 PROVENANCE: the overshoot came from the cap check `check_time` running only when `nodes & 1023 == 1023`. That
  mask was introduced in `7c065c2` (2026-11-14, "Phase 3/4 checkpoint"), found by `git log -S"nodes & 1023"` after a
  deepen of the shallow clone. It predates this audit and the base commit `c25e65e`.
- F-11 MUTATION CHECK (was pending): removing `self.position_invalid = true;` from the TooLong branch makes
  `oversized_position_line_does_not_leave_the_old_position_in_use` fail (`bestmove b1c3` where `0000` is expected).
  With the line, it passes. The regression is effective.
- CI-1 (cause still INFERRED, not reproduced): 40 runs of `closed_stdout_ends_the_process_quietly` under two CPU-bound
  processes on the current code: 0 failures. The inferred cause is unchanged (a reader that drained several `readyok`
  lines, so the engine had nothing to write and was waiting on stdin). The current test waits for exit, not for a line,
  so it does not depend on that timing.
- Hardening (no reproduced defect): the three `flush` mutex `unwrap()`s in `uci.rs` now recover a poisoned lock
  (`lock_ignoring_poison`). The guarded value is `()`, so there is no state to protect. The `unwrap()`s at
  `uci.rs` L333, L661, and L664 are guarded by an `is_some()`/`is_ok()` check on the line above, so they cannot panic.
  `position.rs:177` (`unreachable!("occupancy out of sync")`): reached only if the occupancy and piece boards disagree.
  New test `correctness::piece_bitboards_stay_in_sync_over_random_games` walks 160 random legal games (make and unmake)
  and checks every ply. Passes in release and debug (debug enables the `debug_assert!` sites).
- CI hardening: `ci.yml` has an explicit `permissions: contents: read` (the test workflow pushes nothing). All four
  `dtolnay/rust-toolchain@master` references (ci.yml x3, rating-run.yml x1) are pinned to the commit `master` pointed to
  on 2026-11-20, `df2a88e9fe4098bad09cb42c3dec7187f15861fc`. The same code runs; it can no longer change silently.
- Probes passed on this tree (not a gate by themselves; see FINAL_AUDIT_PROGRESS.md for the exact list): random-position
  perft differential seeds 2-7 (0 mismatches); debug search sweep seeds 2-6 (`scripts/search_sweep.py`, 0 failures);
  UCI grammar fuzz seeds 31-34 (200 sessions each, 0 failures); legal differential seeds 8-10 (all agree; 19 rejections,
  each justified by the material bound, checked by an independent necessary condition in the harness).
- Known limit, documented as a design choice (not changed): `position fen` rejects some legal-looking FENs that cannot
  arise from a real game (more than 16 pieces per side, more than 8 pawns, or promoted pieces above the missing pawns).
  DESIGN_LOG 2026-11-20 states the trade-off.
- Resource checks: 1,200 `go` cycles: threads 1-2, fds 3, RSS flat at about 69 MiB (Hash 64). Hash 1024: RSS grows only
  while the table fills (the table is lazily zeroed); increments fall from +90 to +9 MiB per 4 s search; the 1 GiB table
  is a single fixed allocation, so RSS cannot exceed it plus baseline. Resizing down releases the old table (1024 → 64
  gives 5 MiB).
- `ponderhit` with `go ponder movetime N`: the movetime deadline counts from `go`, so a `ponderhit` at 0.3 s of a
  1000 ms movetime answers at about 1.15 s, not 1.0 s after the hit. This matches the regression test
  `ponder_movetime_ponderhit_keeps_the_movetime_deadline` and is a deliberate, documented choice. Open question for
  GUI conformance: some GUIs expect the clock to start at `ponderhit`. Not changed in this stretch.

## 2026-11-20 (late, stretch 2) — F-15: negative clock or movetime made the search unbounded

- F-15 FIXED (MEDIUM, time management): `go wtime -1000 btime -1000` and `go movetime -5` searched with NO time limit and
  never answered without `stop`. `wtime`, `btime`, and `movetime` were parsed as `u64`, so `-1000` failed to parse and the
  token was dropped, which means "no clock". A GUI that reports a flagged clock as a negative number would therefore lose
  on time. Fix: `parse_time_ms` in `src/uci.rs`. A negative value is 0 (the time is already gone, so the engine answers
  at once, as `wtime 0` already did). A digits-only value above `u64::MAX` saturates to `u64::MAX`, not dropped. Winc/binc
  use the same parser. Non-numeric values are still ignored, as before.
  Regression: `protocol_regressions::negative_time_values_answer_at_once` (fails on HEAD: no bestmove within 5 s).
- Found by `scripts/uci_extreme_args_probe.py` (new, committed). 39 cases: `go` with 0, 1, negative, u64::MAX, i64::MAX,
  and malformed limits, plus 14 `setoption` values (Hash, MultiPV, Threads, Clear Hash, missing values). Result after the
  fix: 0 failures. Unbounded cases answer after `stop` (checked). Not defects by UCI design: `go depth 99999999999`,
  `go movetime 18446744073709551615`, and the other u64-maximum values are searches with an effectively infinite
  limit; `stop` ends them.
- Known limitation (not changed, LOW): `go mate N` is parsed but not implemented. The search runs until `stop`, as
  for `go infinite`. A GUI that expects a mate search will get a search without a mate target. Implementing it is a
  feature, not an audit fix.
- Informational: `go depth 0`, `go depth -1`, and `go nodes 0` answer at once with a root move that was not searched
  (a zero budget). UCI does not define those values. No illegal move is produced.
- Probe defect, NOT an engine defect (`scripts/time_budget_probe.py`, committed in 1d2cd24): `read_until` called
  `select()` on the raw stdout descriptor while `readline()` had already buffered the rest of the handshake. The
  probe then waited for data that was already in its buffer and failed with `no 'uciok' within 10s; saw ['id name
  Flawless']`. Fixed with a reader thread and a queue (no `select()` on a buffered stream). Two runs after the fix: 8/8
  each. Gate run on df6417d recorded `time_budget_probe rc=1` before this fix. Only this probe had the pattern (grep).
- Scratch checks (in `/tmp/fuzz`, not in the repository): `uci_fuzz.py` seeds 41 (150 sessions), 42, 43, 44 (300 each):
  0 failures. `fuzz_fen.py` seeds 1, 2 (3,000 FEN lines each through `moves`): every line answered, rc 0. The repository
  has no `scripts/fuzz_uci.py`; the queue item named a file that was never committed.

## 2026-11-20 (late, stretch 3) — F-16 and F-17: allocation refusal aborted or panicked the engine

- F-16 FIXED (MEDIUM, resources): a refused transposition-table allocation aborted the process (SIGABRT, rc 134, no
  `readyok`). Reproduced: `ulimit -v 400000` then `setoption name Hash value 1024` after `uci`. Rust aborts on a failed
  `vec!` allocation, so the GUI saw a crashed engine. The same happens at start-up under a limit below the default 64 MiB.
  Fix (`src/tt.rs`): `try_resize` and `try_new` reserve the size first with `try_reserve_exact` (a refusal becomes an
  error), then do the usual zeroed allocation. The table stays lazily zeroed; idle RSS after Hash 1024 is 4 MiB (unchanged).
  No `unsafe`. Fix (`src/uci.rs`): `setoption Hash` that cannot be allocated prints
  `info string option Hash N MiB could not be allocated; keeping M MiB` and keeps the old table. Start-up and the
  fallback re-allocation halve the size until the allocator accepts it (announced on stdout); a refusal at 1 MiB exits 1
  with a message on stderr (there is no memory for any search).
  Regression: `protocol_regressions::hash_allocation_refusal_does_not_abort_the_engine` (Linux only; fails on 2b10cd2 with a
  signal exit, passes on the fix).
- F-17 FIXED (MEDIUM, resources): when the OS refused the search thread (`WouldBlock`, under the same limit), `go` hit
  `expect("spawn search thread")` and the engine exited 101. Fix: on a failed spawn, the engine answers with the fallback
  move (the first legal move, or `0000` with no legal move) and prints `info string search thread unavailable (...)`
  on stdout. Limitation: under such pressure the engine answers without searching. Covered by the same regression test
  (50 MB case, which halves the table and then cannot spawn the thread).
- Checked after the fix: 400 MB limit + Hash 1024: readyok, exit 0, legal bestmove; 50 MB and 30 MB limits: exit 0,
  legal bestmove. No limit: bestmove unchanged (`b1a3` at depth 4 from startpos, identical before and after).
- F-18 FIXED (LOW, CI portability): CI `windows-latest` failed at `Clippy (deny warnings)` on `2b10cd2` (run 44775302570,
  job 136423393755; Ubuntu, MSRV and the Windows artifact job passed). Cause: the F-13 regression test
  `stderr_write_failure_does_not_stop_the_session_on_an_oversized_line` used `std::os::unix::io` and a raw `pipe` binding
  without a `cfg(unix)` gate, so the Windows build failed to compile. The `Read` import, used only by that test, would
  also have been an unused import under `-D warnings`. Fix (`tests/protocol_regressions.rs`): the test and its
  `extern "C"` block are `#[cfg(unix)]`; `Read` moved into the test body. The test still runs on Linux (17/17 pass).
  Not verifiable locally: no Windows target is installed, so the fix is confirmed by the CI run on the new head.
  Log for CI job 136423393755 downloads failed with EOF; the step result and annotation were used instead.
- F-14 EVIDENCE ADDED (2026-11-21 re-check; the classification above stands): the earlier note "not reproduced" was
  wrong. It looked only at bestmove legality, which is legal in both builds because the fallback picks the first legal
  move. Comparing the pre-fix build (`0d4fda1`) with HEAD on five insufficient-material roots (K v K, K+N v K, K+B v K,
  K+B v k as Black, K+N v k as Black), `go depth 4`, single PV: pre-fix gives `info depth 4 seldepth 0 ... nodes 4 ... pv`
  (empty) and bestmove legal; HEAD gives `seldepth 1`, nodes 24-52, a non-empty PV whose first move is the bestmove.
  The regression test `insufficient_material_root_is_searched_and_yields_a_pv` fails on `0d4fda1` with
  "empty PV" and passes on HEAD. Interior nodes keep the draw rule, so scores are unchanged (0).
- F-19 (LOW, hardening, NOT a reproduced defect): the three `flush` mutex `unwrap()`s in `src/uci.rs` now recover a
  poisoned lock (`lock_ignoring_poison`, introduced in `df6417d`). The guarded value is `()`, so a poisoned lock holds no
  state to protect. No regression test: the path needs a panic while the lock is held, and there is no way to produce one
  through the protocol. Recorded so the change is traceable; not claimed as a fixed defect.
- F-09 RE-RAISED (not a new defect): Codex review on `a400e80` (`src/search.rs:283`, P2) repeats the F-09 point that
  `go searchmoves` with no legal named move should preserve the empty intersection or reject. The documented decision
  (DESIGN_LOG 2026-11-20) is kept: refuse the null move, search the legal moves, and announce the widening on stdout.
  Reason: the earlier known defect was a `bestmove 0000` answer, and UCI requires a bestmove. This is a
  design disagreement and stays open for the user; it is not silently changed.
- ENVIRONMENT EVENT (2026-11-21 ~01:56 UTC): a sandbox restore left the repo as a fresh clone at `c25e65e` with the
  working tree restored. The local commits `1d2cd24`..`a400e80` were not in the clone, but `origin` held `a400e80`, so
  nothing pushed was lost. The one unpushed commit (`0105db2`, F-18) survived as working-tree changes, which were
  verified byte-for-byte against `a400e80` (exactly the two F-18 files) and recommitted as `ffd6b04` (same tree; new
  hash, since commit metadata differs). `/home/user/.toolchain` and `/home/user/.venv` were gone and were reinstalled from
  the pinned `@toolchain-bin` npm tarballs (rustc, cargo, rust-std, clippy 0.1.99, rustfmt 1.10.0; install.sh --prefix)
  and `chess==1.11.2` from PyPI. `/tmp/gates` scripts were lost; the gate script was rebuilt from the same steps.
- F-11 MUTATION CHECK DONE (2026-11-21): on a copy of HEAD with the `self.position_invalid = true;` line removed from the
  `LineRead::TooLong` arm, `oversized_position_line_does_not_leave_the_old_position_in_use` FAILS (`go` answers
  `bestmove b1c3`, i.e. it searches the old position; expected `bestmove 0000`). On the fix it passes.
- F-18 VERIFIED IN CI: run 44853133810 on `ffd6b04` (CI): success on ubuntu-latest, windows-latest, msrv (rust 1.80), and
  the windows x64 release artifact job. anchor-verify 44853133745: success. The failure on `a400e80` (run 44777328791,
  job 136430504382) was the same `Clippy (deny warnings)` step on Windows.
- RSS AT HASH 1024 (sustained search; `/tmp/audit/rss1024.py`, one process, `go movetime 2000-3000` per round, four
  positions): idle 4.8 MiB; after round 1, 272 MiB; round 12, 964 MiB; round 29, 1007 MiB, still rising at about 1-3
  MiB per round. Consistent with lazily zeroed table pages being touched as the 1024 MiB table fills, so the ceiling
  should be roughly table size plus overhead (earlier hash-cycle measurement: 1029-1046 MiB). NOT proven capped: no
  plateau was observed in the time available. Not a leak claim: the table size is fixed and no second table is
  allocated (`hash_cycle.py`: 30 resizes, exit 0).
- G3 (Windows artifact, `ffd6b04`, artifact 14686132529, 211,374 bytes): `gh run download` and the REST artifact zip both
  failed with EOF from the blob host. NOT VERIFIED. No manifest or SHA256 was checked from the downloaded file.
- F-20 OPEN (MAJOR, resources; found by CodeRabbit on `ce9f8d4`, `src/tt.rs:143`; verified in the code): `try_resize`
  reserves the size in a temporary `Vec` and drops it, then allocates the real table with `vec![0u64; entries]`. If that
  second allocation is refused, Rust aborts (allocation error path) instead of returning `TableAllocError`. So the F-16 fix
  is incomplete in a narrow window. NOT reproduced. Fix options: (a) keep the reserved `Vec` and fill it (fallible, but
  it touches every page, so RSS at Hash 1024 jumps to about 1 GiB at resize; this changes the idle-RSS claim and needs a
  decision); (b) keep lazy zeroing and document the window. Needs a source change and a full gate run.
- F-21 OPEN (MINOR, found by CodeRabbit; `src/uci.rs:596`; verified in the code): the F-17 spawn-failure fallback prints
  the unrestricted first legal move even when `go searchmoves` restricts the search. Not reproduced at run time (needs a
  refused spawn); code-verified. Fix: choose the fallback from the legal named moves. Needs a source change and a full gate.
- F-22 OPEN (MINOR, found by CodeRabbit; `src/uci.rs:599`; verified in the code): on spawn failure, `go infinite` and
  `go ponder` print `bestmove` at once and skip the output hold used for `stop`/`ponderhit`. Not reproduced at run time;
  code-verified. Fix: hold the fallback until `stop` or `ponderhit`. Needs a source change and a full gate.
- HARNESS FIXES (scripts only, found by CodeRabbit on `ce9f8d4`, verified): `scripts/time_budget_probe.py`: the black-only
  case sent `wtime` as well, so it did not test a lone `btime`; now sends `btime 1500` only (8/8 pass, black case 26.9 ms).
  `scripts/search_sweep.py` and `scripts/uci_extreme_args_probe.py`: `readline()` blocked without a deadline; both now read
  stdout in a thread and enforce the deadline while waiting (`search_sweep` seed 2, 20 positions, PASS; extreme-args probe
  0 failures). Targeted runs only; no full gate rerun for these harness changes.
- PROVENANCE ADDENDUM (CodeRabbit ledger comments on `ce9f8d4`; raw logs from earlier runs were lost in the 2026-11-21
  restore, so this says what is and is not still available):
  - F-11: fix in `c4fb22f` (`src/uci.rs`, TooLong arm). Regression fails on the `7d5b489` source (per the earlier review
    reply). Mutation check this stretch: a copy of HEAD (`ffd6b04`) with the `position_invalid = true` line removed gives
    `bestmove b1c3` where `0000` is expected; the regression test FAILS there and PASSES on the fix. Output was on the
    terminal, not saved to a file; the copy is `/tmp/mut_f11` (outside the repo).
  - F-12: fix in `df6417d`. The failing copy was `/tmp/mut4` (HEAD before the fix); its output is not retained.
  - F-15: fix in `2b10cd2`. The failing build was the pre-fix HEAD (`df6417d`); output not retained. Probe rerun on the
    fixed code: `scripts/uci_extreme_args_probe.py` 0 failures on `ffd6b04` and again after the harness change.
  - F-16/F-17: failing revision `2b10cd2` (signal exit under `ulimit -v`); fixed in `a400e80`. Resource-check outputs
    `/tmp/audit/vlim_*`, `vfix_*`, `vf2_*` were lost in the restore. Regression test passes on `ffd6b04` (CI success).
  - Current evidence (retained after this stretch): `/tmp/gates/final-ffd6b04/` (34 rows, rc=0) and `/tmp/audit/k/`.
- F-21 FIXED (MINOR, found by CodeRabbit on `ce9f8d4`, `src/uci.rs`; reproduced): with the search thread refused,
  `go searchmoves d2d4` answered `bestmove a2a3` (the first legal move in generation order, excluded by searchmoves) on the
  pre-fix code, under `ulimit -v 50000` (debug build of the pre-fix HEAD, `/tmp/mut_f11`). Fix: the fallback is the first
  legal move that is in `searchmoves`; if none is legal, the widened first legal move (as the search does). Regression:
  `protocol_regressions::spawn_fallback_respects_searchmoves` (Linux): fails on the pre-fix code (`bestmove a2a3`), passes on
  the fix (`bestmove d2d4`). F-22 (fallback bypasses the output hold for `go infinite`/`go ponder`) remains OPEN.
- F-20 FIXED (MAJOR, resources; found by CodeRabbit and Codex on `ce9f8d4`, `src/tt.rs:143-144`; code-verified, not
  reproduced): `try_resize` released a probe reservation and then allocated the table with `vec![0; n]`. If that second
  allocation was refused, Rust aborted. Fix: `zeroed_entries` (`src/tt.rs`) makes one `std::alloc::alloc_zeroed` call,
  checks for null, and returns `TableAllocError` on refusal. This is the only `unsafe` in `src/`; the invariants are in its
  doc comment (DESIGN_LOG "stretch 4", BENCHMARKING.md). The table stays lazily zeroed; `clear()` is no longer run on
  resize. Tests: unit `zeroed_entries_are_zero_and_sized`, `zeroed_entries_reject_impossible_sizes`,
  `try_resize_sets_the_entry_count_and_resets_counters`; process `hash_allocation_refusal_does_not_abort_the_engine`.
  Benchmark: first `go` 1.8–2.9 ms before and after; idle RSS 4.8 MiB before and after.
- F-22 FIXED (MINOR, protocol; found by CodeRabbit on `ce9f8d4`, `src/uci.rs:611`; reproduced): when the search thread
  was refused, `go infinite` (and `go ponder`, bare `go`) printed `bestmove` at once. Pre-fix build (debug copy of the
  pre-fix code): `bestmove a2a3` during the 1 s after `go infinite`, before `stop`. Fix: `pending_answer` holds the
  answer; `stop_and_join` prints it on `stop`, `quit`, EOF, or the next `go`, exactly once. Fixed-time and fixed-depth
  searches still answer at once, as before. Regression: `protocol_regressions::refused_thread_holds_bestmove_for_go_infinite_until_stop`
  (fails on the pre-fix code with "bestmove printed before stop", passes on the fix).
- REVIEW TRIAGE (CodeRabbit `ce9f8d4`, comments from 2026-11-20 that were still on the PR; checked against the current code):
  - `scripts/uci_malformed_probe.py` (every bestmove on the complete transcript): already handled. The probe counts all replies
    (`EXTRA_BESTMOVE`). Checked with a fake engine that prints each bestmove twice: the probe reports the extra replies.
  - `scripts/uci_protocol_probe.py` (count after draining): already handled. Same fake engine: `2 bestmove lines on stdout`
    failures.
  - `benches/movetime-20261119/measure_movetime.py` (cleanup when a measurement fails): already handled. `run()` runs the
    kill, wait, and close in a `finally` (lines 21-27), which covers `queue.Empty` and startup timeouts.
  - Codex `src/search.rs:283-284` (`searchmoves` with no legal named move): the F-09 design decision, kept (see above).
