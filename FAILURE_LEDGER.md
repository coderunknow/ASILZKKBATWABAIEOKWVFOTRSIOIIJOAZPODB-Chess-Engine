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
