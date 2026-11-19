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

## 2026-11-18 — campaign runner analysed the wrong perspective

- **Observed:** the STRENGTH-1 campaign log reported SPEED-1 at 0.375 and
  HIST-1 at 0.594. Recomputing from the raw JSONL gave the opposite signs for
  the candidates (SPEED-1 0.625, HIST-1 0.406).
- **Root cause:** `/home/user/tc/run_campaign.sh` called
  `scripts/stats.py --focus "$wname"`, where `wname` was the *white* engine
  name (`base`). The registration specifies "score from the candidate's
  perspective", so the sign of the reported effect was inverted.
- **Correction:** the raw game records were never modified. The registered
  estimator (same script, same seed 20261118, same 10,000 opening-clustered
  bootstrap resamples) was re-run with `--focus <candidate>` on the same
  records. The runner now takes the candidate name as an explicit argument.
- **Guard added:** the analysis focus is a required, explicit parameter of the
  runner rather than a positional one, and the result record states which
  perspective was used.

## 2026-11-18 — evaluation ablation "off" branches did not match the base

- **Observed:** the first EVAL-NONE build produced a different bench signature
  (`e581eaf7b92b50e9`, 2,512,920 nodes) from the parent tree
  (`8370f143c3b76fb4`, 2,697,573 nodes), so the ablation control was not a
  faithful reproduction of the base evaluation.
- **Root cause:** when the feature flags were introduced, the rook and queen
  "off" branches were written with the *endgame* weight in both the midgame and
  endgame slots (`2,5` and `1,9` instead of `2,2` and `1,1`). The base
  evaluation used one weight for both phases.
- **Correction:** the off branches now reproduce the base weights exactly. The
  control was rebuilt and re-verified: EVAL-NONE reproduces the parent
  signature `8370f143c3b76fb4` and node count 2,697,573 exactly.
- **Lesson applied:** the control-validity check (all flags off must reproduce
  the parent tree bit for bit) is now performed *before* dispatch and is
  recorded in the registration. It is part of the EVAL-1 preconditions.

## 2026-11-18 — "space" evaluation term was computed but never applied

- **Observed:** the evaluation rewrite introduced a space term, but the score
  did not change when it was enabled.
- **Root cause:** `space` was accumulated into a local variable and then folded
  into the `pawns` display field only; it was never added to the midgame or
  endgame totals.
- **Correction:** `space` now has its own component and is added to both
  phase totals. The evaluation breakdown remains an exact decomposition of the
  tapered score.

## 2026-11-18 — candidate-pawn gap was O(pawns on file)

- **Observed:** the candidate-pawn term scanned every friendly pawn ahead on the
  file for each pawn on that file, making the term quadratic in the worst case.
- **Root cause:** the gap was computed by iterating the pawns ahead instead of
  taking the nearest one.
- **Correction:** the nearest friendly pawn ahead is found directly from the
  bitboard (lowest set bit for White, highest for Black). The term is now O(1)
  per pawn and is colour-symmetric, which the new antisymmetry test confirms.

## 2026-11-18 — outpost test used the wrong pawn-attack table (both directions)

- **Observed:** the outpost term counted pieces that were not defended and
  ignored pieces that were attacked by an enemy pawn. The error was invisible
  to the existing evaluation gates: the evaluator stayed antisymmetric under
  the board flip (the defect is itself symmetric), stayed finite, and the
  breakdown still summed to the total.
- **Root cause:** the pawn-attack table is *directional*. The set of squares
  from which a pawn of colour C attacks square X is
  `PAWN_ATTACKS_[other(C)][X]`. The outpost test used the wrong table in both
  of its two lookups:
  - "defended by one of our own pawns" used
    `pawn_attacks_lookup(color, sq) & pawns`. For a White piece on d5 that is
    `PAWN_ATTACKS_WHITE[d5] = {c6, e6}` — the squares a White pawn
    *standing on d5* would attack. The pawns that actually *defend* d5 stand
    on c4/e4, which is `PAWN_ATTACKS_BLACK[d5]`.
  - "no enemy pawn attacks it" used
    `pawn_attacks_lookup(them, sq) & enemy_pawns`. For the same piece that is
    `PAWN_ATTACKS_BLACK[d5] = {c4, e4}` — the squares a Black pawn
    *standing on d5* would attack. The Black pawns that actually *attack* d5
    stand on c6/e6, which is `PAWN_ATTACKS_WHITE[d5]`.

  Both lookups therefore asked "is this square attacked by a pawn of the same
  colour as the piece".
- **Correction:** commit `c702066`. The two lookups now use the opposite
  tables, and the code comments say which colour each one means. The "no
  enemy pawn can step forward to attack it" test already looked at the right
  squares and is unchanged.
- **Regression test added:** `outpost_requires_defence_and_safety_in_the_right_direction`
  in `tests/eval_quality.rs` pins the two directions down with four
  positions — a defended and unattacked knight on d5 is an outpost; an
  undefended one is not; one attacked by a Black pawn on e6 is not; and one
  that a Black pawn on e7 can step forward to attack is not. The test was
  verified to FAIL on the pre-fix source and PASS on the fixed source.
- **Consequence:** the evaluation values change, so the searched tree changes:
  the depth-10 bench signature moves from `03e46bba31f35591` to
  `b58979ca90492208` and the node count from 3,445,466 to 3,666,233. Every
  binary built for the EVAL-1 campaign was made from the defective source, so
  the whole EVAL-1 campaign was **withdrawn** and re-registered as EVAL-2 with
  fresh binaries. The withdrawn raw records are retained unmodified under
  `/home/user/matches/eval-*-invalidated-outpostbug/` and must not be cited.
- **Lesson applied:** an antisymmetry test cannot catch a defect that is
  itself symmetric. Terms that consult a *directional* table need a test that
  exercises each direction separately, not only a test that checks the whole
  evaluator's symmetry.

## 2026-11-18 — evaluation cost grew ~40-50% per evaluation with the new terms

- **Observed:** the depth-10 bench fell from ~832k NPS to ~715k NPS after the
  evaluation upgrade, even though the tree got smaller (3,445,466 nodes
  versus 3,666,233 is not a like-for-like comparison, but the per-evaluation
  cost measured directly rose from ~265 ns to ~365 ns).
- **Root cause:** two separate inefficiencies. (1) The slider attack masks
  were computed twice per evaluation: `eval_color` runs once per side, and
  for side X it computed the masks for X's own pieces (mobility) and again for
  Y's pieces (king safety); the second call then computed the same masks
  again. (2) The pawn-structure section recomputed, for every pawn, values
  that depend only on the pawn's square.
- **Correction:** commit `815ca47`. The masks are computed once per side and
  shared; the pawn-structure section uses lookup tables (`FILE_NEIGHBOURS`,
  `BEHIND_SQUARE`, `BEHIND_DIAGONALS`, `SIDE_FILES`); and `evaluate` no
  longer routes through the ten-component `breakdown` taper, which cost ten
  integer divisions per evaluation for values the search discarded.
- **Verification:** the bench signature and node count are **unchanged** at
  `b58979ca90492208` / 3,666,233, which proves the evaluation values did not
  change — the searched tree is identical. Measured cost fell from 1219 ns to
  1077 ns (minimum of 20 runs summed over the four `bench_eval` positions),
  about 12 %.
- **Lesson applied:** a performance change that alters no value can be
  verified exactly, by comparing the bench signature and node count. That
  check was used instead of a hand-written equivalence test.

---

## 2026-11-19 — CTRL-2-R self-match null control FAILED (ENGINE-1 identity)

### Hypothesis / what was expected

`docs/RATING_PROTOCOL.md` §5 requires the candidate self-match control to be
"consistent with a score of 0.5 under the registered binomial confidence
criterion". The recovered CTRL-2-R evidence (240 counted games, 60 opening
clusters, 40 AB / 40 BA, zero engine errors) was expected to satisfy it, and
it does not.

### Exact implementation and identity

- Run: GitHub Actions `rating-run` run **43820392119**, dispatch revision 13,
  commit `8e21435`, completed/successful, all 120 shard jobs green, the
  aggregate-and-commit-evidence job skipped.
- Engine: ENGINE-1, binary SHA-256
  `9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428`
  (frozen in the dispatch and verified by the strict aggregator).
- Opening suite: `benches/rating-openings-batchA.txt`, SHA-256
  `2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96`.
- Time control: 40 moves / 900 s repeating. Seed 20261125.
- Recovered to `benches/evidence/control/flawless-self-r/` (games.jsonl 240
  records, manifest with 120 shard ids, `merged_sha256`
  `8b643304e20433cd0a8b1c7ec96c114b097a459fff70012c28b997020a8bbf79`).
- Aggregation was performed on a GitHub runner by `evidence-bridge` run
  **44465050400** (the sandbox cannot reach the artifact blob host), with the
  strict fail-closed `scripts/aggregate_shards.py`.

### Methodology

`scripts/rating_estimator.py control --mode self-match` — the registered
tool, unchanged — with the registered 10,000-resample opening-cluster
bootstrap and seed 20261114.

### Raw evidence and outcome

| Quantity | Value |
|---|---|
| Counted games | 240 (60 openings x 4 games: 2 AB + 2 BA each) |
| Engine errors | 0 |
| Unadjudicated | 0 |
| Schedule indices | 0–239, each exactly once |
| Seat-A perspective score | **0.4604166667** |
| 95 % cluster-bootstrap CI | **[0.4208333333, 0.4979166667]** |
| White-perspective score | 0.5229166667 |
| **Verdict** | **FAIL — the CI does not contain 0.5** |

### Root-cause analysis (verified, not assumed)

The deficit is **entirely in the decisive games**: every draw contributes
exactly 0.5 from either seat, and the 125 drawn games sit exactly at 0.5. Among
the 115 checkmate games the seat-A score is 0.4174 (47/115).

At the cluster level the seat score has mean 0.4604 with a cluster SD of
0.1535 over 60 clusters, i.e. SE 0.0198 and **z = -2.00** (two-sided
p ≈ 0.046). The registered percentile bootstrap CI misses 0.5 by 0.0021 at the
upper end.

Two candidate causes were investigated:

1. **A harness asymmetry in the AB/BA opening handling — REJECTED.** The
   opening suite header says "Colors reversed (AB/BA) for every line" and the
   manifest claims "exact color reversal", which reads as if the suite line
   were replayed with the colours swapped. It is not: `apply_opening` replays
   the line White-first in both halves and only the *engine commands* are
   swapped. This was checked directly against the raw records — the first
   `len(line)` moves of every BA game are byte-identical to the AB game of the
   same opening, in all four recovered evidence sets.
   It was then shown that the harness is **correct** and the suite header is
   ambiguous: from the post-opening position P, let `w` = P(the side to move
   wins) and `d` = P(draw) for two identical engines. The standard
   convention gives seat-A score
   `(w + d/2 + (1-w-d) + d/2)/2 = 1/2` **exactly**, for any `w` and `d`,
   while a *mirrored* opening convention gives `w + d/2`, which is above 0.5
   whenever White has the advantage. The registered control's 0.5 expectation
   is therefore only meaningful under the convention the harness implements.
   Mirroring the line would have *broken* the control. **No harness change is
   warranted, and none was made.**
2. **Sampling fluctuation — CONSISTENT WITH THE DATA.** With an unbiased
   estimator, a z of -2.00 at a 5 % two-sided level is an unlucky but ordinary
   outcome for a single control.

The other recovered control does not fail: the anchor-vs-anchor control
(CTRL-1, topple-0.1.1 vs topple-0.2.1, 240 games) recovers the published
difference of -115 Elo as -125.3 Elo, an error of **-10.3 Elo** against the
registered ±75 tolerance, and the earlier pre-ENGINE-1 self-match (120 games)
passes at 0.5146 with CI [0.4813, 0.5500].

### Consequence

- **ENGINE-1 is disqualified as a rated candidate.** Its self-match null
  control failed, and §5 requires that any result failing a null control
  invalidates the affected batch. ENGINE-1 was never aggregated into a
  canonical batch in any case (its evidence job was skipped), so no ENGINE-1
  number is reported anywhere.
- **No Flawless rating may be reported from the ENGINE-1 evidence.** The
  recovered SCREEN-3 and CTRL-2-R records remain valid *historical* evidence
  and are used only for the variance/selection model of a prospective power
  assessment, never as gate evidence.
- **The V1 candidate requires its own controls.** The candidate-specific
  self-match and anchor-vs-anchor controls must be run against the exact
  frozen V1 binary before any confirmatory dispatch. The control's 5 %
  false-positive rate is a known cost and is handled by running the control
  on the candidate, not by relaxing it.

### Uncertainty

The z = -2.00 is a point reading on a 240-game, 60-cluster sample; the true
effect could be anywhere in the CI [-0.079, -0.002]. The analysis does not
distinguish "a real 0.04 seat deficit" from "an unlucky draw", and it does
not need to: either way the registered control fails for this identity and
the identity is not used for rating.

### What was learned

- A null control can fail for the right reason and still be the correct
  instrument. The temptation was to "fix" the harness; the arithmetic showed
  the harness was right and the mirrored convention would have been wrong.
- The `fen` field in a match record is the **final** position, not the start
  position. Replaying a game's `moves` from its own `fen` fails on every
  record and means nothing; the games start from the standard position with
  the suite line applied.
- The opening suite's "Colors reversed (AB/BA) for every line" header is
  ambiguous and reads as if the line were mirrored. It should be reworded to
  say that the line is replayed as written and only the engine seats are
  swapped. **Not yet done — the suite files are frozen evidence and must not
  be edited in place; the wording is corrected in the append-only protocol
  notes instead.**

### Next experiment

Run candidate-specific self-match and anchor-vs-anchor controls against the
exact frozen V1 candidate binary, on the registered 40/15 control, with the
registered AB/BA schedule and the registered bootstrap seed, before any
confirmatory dispatch.

## 2026-11-19 — Sandbox restore: commit history, toolchain and worktrees lost again

- Attempt: continue the Phase B audit from the restored workspace.
- What happened: the sandbox was restored to the initial clone state. `git log` showed only the base
  commit `5e36b06`, the PR #2 commits (`adda48e` and its ancestors) were no longer in the local
  object store, the extra worktrees (`wt-baseline`, `wt-fixed`, `wt-eval2`, `wt-mate`) were gone,
  `/home/user/.toolchain`, `/home/user/.venv` and `/home/user/tc` were gone, and `/tmp` was empty.
  The working tree still held the whole PR #2 change as uncommitted modifications.
- Recovery: `git fetch origin arena/8259ce1c-flawlesschess` restored the history (`adda48e` and its
  ancestors). Every file that the restore had left untracked was verified byte-identical to its
  `adda48e` blob before the branch pointer was moved with `git reset --mixed adda48e`; the working
  tree was not touched by the reset. The Rust toolchain was restored from the pinned PyPI mirror
  (`arena-rust-toolchain` 1.97.0 plus the three data wheels) with `/home/user/tc/fetch.py`, and the
  Python environment with `python-chess` 1.11.2 in `/home/user/.venv`.
- Result: the workspace is back at the state the audit started from. The uncommitted PVS re-search
  probe that had been in `/home/user/wt-fixed` was lost with the worktree and was rewritten from
  scratch.
- Lesson: the unpushed working tree is the only copy of an uncommitted change. Recreate the
  toolchain from the pinned mirror before doing anything else, and verify byte identity of a
  restored tree against the remote before trusting it.

## 2026-11-19 — Phase B audit: the PVS scout bound was used as a move score

- Attempt: audit `src/search.rs` against the PVS algorithm, then measure the root score against the
  exact value of the best single move over the Batch A opening list.
- What happened: the re-search that converts a scout bound into a move value was guarded by
  `reduction > 0`, so an unreduced non-first move never got one and its null-window bound was used
  as the move's score. At depth 2 the root score was below the best move's value in 7 of the first 8
  Batch A positions, with gaps up to 172 centipawns, and the root chose a different move than the
  best one in the same positions. The pre-PR-2 baseline satisfies the invariant exactly, so this
  was introduced with the search rework.
- The same defect also produced a bogus mate claim: the King's Gambit Accepted position of the
  Batch A suite (after 1.e4 e5 2.f4 exf4) reported `score mate 15` at depth 3, which is not a
  forced mate at all. The bound propagated into the mate range and was formatted as a mate
  distance.
- Result: fixed in `708d53c`. The full-window re-search is now performed for every non-first move
  that beats alpha. Two regression tests were added and verified to fail against the old code.
- Uncertainty: the residual differences between the root score and the value of the best single
  move at depth 5 are the late-move-reduction and pruning approximations, not unverified bounds.
  They are inherent to the search and are not treated as defects.
- Lesson: a null-window scout result is a bound. Promoting it to a score is a correctness bug that
  a score-consistency invariant catches immediately, and the invariant must be tested at a depth
  where the deliberate approximations are switched off.

## 2026-11-19 — Phase B audit: the move-ordering bands overlapped

- Attempt: check that the documented ordering bands ("sound captures outrank killers, losing
  captures are deliberately demoted below ordinary quiet moves") hold for every reachable value of
  the history tables.
- What happened: they did not. A quiet move scores `50_000 + history + cont_history +
  cont_history2`, and each entry is clamped to `+/- 8192`, so the quiet band reaches down to
  25_424. A losing capture scored `40_000 + see` with `see` in `[-10_000, -1]` plus the
  capture-history refinement (at most `8192 / 4 = 2048`), so it could reach 27_952 and be ordered
  above a quiet move. A capture-promotion was worse: the promotion bonus of up to 20_225 was added
  to losing captures as well and pushed them to 48_177 .. 62_272, in the middle of the quiet band.
- Result: fixed in `61dd642`. The bands are now laid out so that they cannot overlap whatever the
  history tables hold, and the layout is documented next to the constants. Two regression tests
  check the invariant directly and fail against the old bases.
- Lesson: an ordering band described in prose is not a band. The bands must be derived from the
  clamped value ranges of the tables that feed them, and the layout must be checked by a test that
  fills the tables with both extremes.

## 2026-11-19 — Phase B audit: the quiescence did not record its captures on the search path

- Attempt: classify the open question "quiescence does not update `self.path`".
- What happened: the search path is documented as "path[p] is the move made at ply p", but only the
  main search wrote to it. From the second quiescence level on, the counter-move lookup and the
  continuation-history lookup were made for a move from an unrelated earlier branch, so the
  counter-move bonus could land on a capture that is not the counter move.
- Classification: the effect is confined to the ordering inside the quiescence. The quiescence's
  returned value is the maximum over the captures it searched and does not depend on the order, so
  the value stays a valid bound; only the place of the beta cutoff moves. It is a quality defect,
  not a correctness defect.
- Result: fixed in `018e920`. The quiescence records the capture it plays and restores the
  previous entry afterwards. The bench node count moves from 3413870 to 3413723.
- Lesson: the path is an input to the ordering, so every level of the search has to maintain it.

## 2026-11-19 — Phase C audit: the mate-score band was narrower than the reachable mate range

- Attempt: complete the TT mate-distance normalisation trace and decide whether the mate-distance handling was sound.
- What happened: the mate-score band was `MATE_SCORE - 100` in three places (the transposition table, the UCI score formatter and the search's pruning guards), while the search's ply limit is `MAX_PLY = 128`. The search returns a static evaluation at `ply >= MAX_PLY` *before* it looks for mate, so the deepest checkmate node it can reach is at ply `MAX_PLY - 1` and the longest mate it can report is 127 plies from the root. A mate 100 plies or more from the root therefore fell **outside** the band, and the band was 28 plies too narrow in each direction.
- Classification: **correctness defect**, not a quality defect. Two distinct failures:
  (1) the transposition table did not recognise such a score as a mate score, so it stored it in root-relative form and returned it unchanged when the entry was probed at a different ply. The mate distance was then wrong by exactly the ply difference — a mate 101 plies away, stored at ply 0 and re-used at ply 50, was reported as 101 plies away instead of 151. Reproduced directly against the table's public API.
  (2) the UCI layer printed such a mate as a centipawn score (`cp 29899`), which is not a score the format can represent and which a GUI would render as a nonsensical evaluation rather than a mate.
  The search's own pruning guards shared the same band, so a null move could be attempted with a mate beta (a mate 100–127 plies away yields a beta in `[MATE_SCORE - 127, MATE_SCORE - 100]`). That is a third consequence of the same root cause.
- Result: fixed in `32ad8ab`. The band is now `MATE_SCORE - MAX_PLY`, derived from the search's ply limit rather than from an arbitrary constant, and it is defined once in `eval::MATE_BOUND` and used by the search, the table and the UCI layer. The fix is **behaviour-neutral for ordinary positions**: the depth-10 bench signature and node count are unchanged at `c64d148d39181140` / 3,413,723, because a depth-10 search can never reach a mate 100 plies away. `tests/mate_distance.rs` adds eight regressions, four of which fail against the pre-fix source.
- Lesson: a threshold that classifies a *kind of score* must be derived from the range the producer can actually emit. `MATE_SCORE - 100` looks like a safe margin; it was in fact a band 28 plies narrower than the reachable range, and the same constant was duplicated in three modules, so the three copies agreed with each other and were all wrong together.

## 2026-11-19 — EVAL-3 screening: the audited tree is measurably stronger than the pre-audit tree

- Attempt: measure whether the three audited search fixes also make the engine stronger, not merely correct.
- What happened: with the identities pinned before dispatch (candidate `540a10df…` / bench `c64d148d39181140`; control `2b41a8e6…` / bench `b58979ca90492208`), the candidate scored **60.5/80 = 0.756**, 95% CI [0.662, 0.838], Elo difference **+197**, 95% CI **[+117, +285]**, over 80 games on 20 opening clusters with exact AB/BA reversal and zero engine errors.
- Classification: not a failure. The registered decision rule (95% CI lower bound > 0 Elo) is met with a wide margin, and the result was reproduced by two independent code paths (`scripts/stats.py` and a separate recomputation against the raw JSONL).
- Result: recorded in `PREREGISTRATION.md` (EVAL-3 result record) and the raw evidence is preserved under `benches/evidence/screening-eval3/`. The result is screening evidence on a shared 2-vCPU sandbox at a fixed 100 ms/move time control; it is not a rating and it does not substitute for the >2,000 Elo gate.
- Lesson: the mechanical root-consistency measurements of the audit (root score below the value of the chosen move in 5/12 and 8/12 positions; MultiPV best understated in 7/12) predicted a real strength gap. A correctness audit that measures the *symptom* it fixed gives a falsifiable strength prediction, which the screening campaign then tested.

## 2026-11-19 — the self-match null-control verdict is seed-dependent at the boundary

### What was found

While reviewing the minimum candidate-specific control set, the committed
CTRL-2-R self-match evidence was re-aggregated with the registered tool
(`scripts/rating_estimator.py control --mode self-match`, unchanged) to check
that the committed control evidence still reproduces. It does — but only for the
exact seed the verdict was recorded with.

| Seed | Seat-A score | 95 % CI | Verdict |
|---|---|---|---|
| 20261114 (registered) | 0.46041666666666664 | [0.42083333333333334, **0.4979166666666667**] | **FAIL** — CI does not contain 0.5 |
| 20261125 (the dispatch seed) | 0.46041666666666664 | [0.42083333333333334, **0.5**] | PASS — CI contains 0.5 |

Across 300 consecutive seeds the recorded evidence gives **177 PASS and 123
FAIL**. The point estimate is seed-independent (0.46041666666666664 = 110.5/240);
only the interval's endpoint moves, and it takes only two values, 0.4979167 and
0.5 — adjacent points on the grid the bootstrap mean lives on.

### Root cause

The self-match criterion is "the 95 % CI contains 0.5", and the CI is a
percentile cluster bootstrap. With *n* clusters of four games the resampled
mean is a multiple of 1/(8n), so the bootstrap distribution is a coarse grid.
The 97.5 % percentile for this evidence falls at ≈ 0.4992 — *between* the grid
points 0.4979167 and 0.5. The discrete rank index `int(0.975 * n_boot)`
therefore lands on one or the other depending on the seed. The number of
bootstrap resamples at or above 0.5 has mean `n_boot * Φ(z)` and standard
deviation ≈ 16 at `n_boot = 10,000`, so the verdict flips whenever that count
straddles the rank threshold — a band of roughly ±0.027 SE in z.

This is not a Monte-Carlo artifact and more replicates do not remove it:

| Bootstrap replicates | Seeds tried | FAIL | PASS | Flip rate | Upper bound values seen |
|---|---|---|---|---|---|
| 1,000 | 60 | 35 | 25 | 58.3 % | 0.4958333, 0.4979167, 0.5, 0.5020833 |
| 10,000 | 60 | 27 | 33 | 45.0 % | 0.4979167, 0.5 |
| 50,000 | 24 | 13 | 11 | 54.2 % | 0.4979167, 0.5 |

The flip band in z is ≈ ±0.027 SE **independently of the control size**, so a
larger control would not reduce how often a genuinely fair candidate lands in
it (≈ 0.3 % of fair candidates); what makes the rare ambiguous case safe is
certifying the verdict across a registered seed set, not collecting more games.

The **anchor-vs-anchor** control does not have this problem: it is decided by
comparing the measured point estimate with the published difference under the
±75 Elo tolerance and uses no bootstrap interval, so its verdict is identical
for 40 different seeds (`d_measured = -125.3211`, `error = -10.3211`, PASS).

### Impact on the recorded verdicts

**None — every recorded verdict stands unchanged.** The CTRL-2-R FAIL was
recorded with the registered seed 20261114 and reproduces byte-identically. The
pre-ENGINE-1 self-match PASS reproduces byte-identically at its recorded seed
and is unanimous across all 16 registered seeds (16/16 PASS), so it is not
affected. CTRL-1 reproduces byte-identically and is seed-independent by
construction.

What the analysis adds is the *characterisation* of the ENGINE-1 outcome: it is
a borderline result (clustered z ≈ −2.00 against a 1.96 threshold) reported by
a knife-edge test, not evidence that the ENGINE-1 binary is biased in colour.
The disqualification of ENGINE-1 as a rated candidate is a conservative
consequence of the registered criterion and is **not** reversed.

### Fix

Registered prospectively (before any candidate control is dispatched) in
`PREREGISTRATION.md` § "RATING-100 control-robustness amendment" and
`docs/RATING_PROTOCOL.md`: the self-match verdict is certified across the
registered seed set `20261114 … 20261129`, and a verdict that is not unanimous
is reported as **NOT ROBUST** and treated by the gate as **unavailable** —
never as PASS and never as FAIL. The amendment is a strengthening only, so it
cannot rescue a failing control. `scripts/rating_estimator.py` now reports
`seed_robust` for both null controls, and the gate requires it.
