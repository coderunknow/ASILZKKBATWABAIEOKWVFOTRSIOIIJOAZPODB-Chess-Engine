# AGENTS_LOG.md (append-only)

## 2026-11-14 — Session start (Phase 0)

- Agent: autonomous principal engineer (Arena Agent Mode).
- Actions: repository inspection (git status/log/branch/remote); environment probe; network reachability
  matrix; Rust 1.99.0 installed from npm under `/home/user/.toolchain/sysroot`; python-chess 1.11.2 in
  `/home/user/.venv` as test-only oracle (GPL-3.0+).
- Starting SHA: `98b1a00203183d9c7ccb175f7d6eb8f5ef5eb429`. No files modified at inspection time.
- Created: STATUS.md, AGENTS.md, ARCHITECTURE.md (RFC), docs/ENVIRONMENT.md, docs/adr/0001,
  DESIGN_LOG.md, AGENTS_LOG.md, FAILURE_LEDGER.md placeholder, initial docs skeleton.
- Next: Phase 2 — Rust project scaffold, bitboards, FEN, movegen, make/unmake, perft.

## 2026-11-14 — Phase 3/4/UCI session

- Built: eval.rs (tapered classical), tt.rs (Zobrist 8B TT), search.rs (ID/PVS/aspiration/quiescence/
  null-move/futility/LMR/killers/history/MultiPV/TT-PV), uci.rs (worker-thread search, stop/ponder/
  ponderhit, Hash/Threads/MultiPV options, clock time management soft/hard with movestogo clamp).
- main.rs: added `uci`, `eval [fen]` (breakdown), `bench_eval` subcommands.
- Build: `cargo build --release` clean (one unused-const warning, fixed). `cargo test --release` 14/14 PASS.
- Smoke tests: UCI handshake; mate-in-1 found (`bestmove b1b8`); Kiwipete MultiPV 3 to depth 10;
  abort/stop/ponderhit paths verified with nonblocking stdin reader; ~0.9M nps; 2 vCPU sandbox.
- Fixed two UCI-layer bugs found by smoke testing: (1) bestmove only printed on next stdin command
  (UCI protocol violation) → worker now prints bestmove directly; (2) mate-score formatting could
  overflow (`mate 499`) → clamped; (3) aborted root scores were used to build result → discarded.
- Committed: pending (this checkpoint not yet committed — see STATUS.md "Next preregistered task").

## 2026-11-14 — CI + benchmark harness + LMR panic fix

- Set up `.github/workflows/ci.yml` (Ubuntu+Windows: fmt, clippy -D warnings, release tests,
  release build, UCI handshake, perft d3). CI green on PR #1 (both OSs). Kilo bot: insufficient
  credits (not a code issue).
- Smoke match exposed LMR table out-of-bounds panic → engine silently lost on time.
  Fixed table bounds + worker catch_unwind fallback bestmove. 2-game smoke: engine wins both.
- Wrote match.py/stats.py + 20 verified openings; launched probe-001 (40 games vs SF 19 WASM,
  Skill 0, movetime 100ms) in background.
- Raw evidence committed to benches/ for reproducibility.

## 2026-11-14 — CI + probes session (cont.)

- PR #1 opened (branch pushed). CI: ubuntu-latest + windows-latest both green (fmt/clippy/tests/
  release build/UCI handshake/perft d3). Third-party Kilo bot: insufficient credits — reported as
  not a code issue.
- probes 001/002/003 committed with raw PGN/JSONL evidence.
- UCI fuzz (6 trials × 25 random commands, grammar of 30) — 0 crashes/hangs.
- Engine bracket: between SF-Skill-5 and SF-Skill-10 (pinned SF 19 WASM, 100 ms/move). No absolute
  rating claim; v1.0.0 gates untouched.

## 2026-11-14 — Environment rebuild + strength experiment

- Sandbox workspace was re-materialized (git HEAD reverted to 98b1a00; toolchain/venv/opponents lost).
  Restored branch ref + index from origin (tip 1dc2500) — working tree matched exactly, nothing lost.
  Toolchain reinstalled from npm (same versions); venv + python-chess reinstalled; pinned SF WASM
  re-fetched and hash-verified identical. FAILURE_LEDGER entry recorded.
- Re-ran all gates post-rebuild: fmt/clippy/tests/diftest PASSED; CI still green (PR #1).
- Implemented `cargo run --release -- bench` (fixed depth 10, 12 positions, deterministic signature).
- Search experiment: RFP + check extensions. All gates pass. A/B: +80 Elo (CI [-9,+168], 40 games).
- probe-004 (RFP+CE build) vs SF Skill 5, 40 games @100ms: 14/14/12 score 0.525 (CI [0.412,0.637]).

## 2026-11-14 — Identity migration to Flawless

- `flawless` package/binary/crate; `id name Flawless`; `id author coderunknow (Apache-2.0)`.
- CI workflow smoke tests de-masked (removed `|| true` swallowers); binary path updated.
- Historical raw evidence keeps the old identifiers by policy (see ADR-0002).
- Environment note: sandbox workspace was re-materialized (git HEAD → 98b1a00, toolchain/venv/
  opponents lost); restored branch ref + index from origin (a01fcaf), rebuilt toolchain from npm
  (rustc/cargo 1.99.0), and re-verified lld execute bits for linking; episode recorded in
  FAILURE_LEDGER.md.
- Repository was observed as `coderunknow/Flawless-Chess-Engine` (externally renamed); the old
  URL auto-redirects. This project did not and does not rename the repository.

## 2026-11-14 — Audit passes 1-2, docs integrity, panic-fallback e2e verification

- b85b3f7 FAILED CI (Clippy `write_with_newline` — shell pipe hid it locally); fixed in 837361f;
  lesson recorded: never chain a gating command through a pipe that swallows its exit status;
  CI is the backstop, not the first line of defense.
- CI for head-era commits: 43562935232 (b4acfcd SUCCESS), 43563085939 (bbb31f9 SUCCESS),
  43563499046 (b85b3f7 FAILURE), 43563628232 (44c8369 SUCCESS).
- Panic-fallback path verified end-to-end with a synthetic panic engine: games flagged
  engine_error=true with engine_error_turns; stats.py excludes them ("no scorable games after
  exclusions"). Normal 4-game match unaffected (4/4 vs SF19-lite Skill 0 @ 100ms).
- Match runner harvest fix (early-return paths dropped panic markers) committed 972161d.
- Docs integrity pass: ARCHITECTURE TT 16→8 bytes, SEE claims removed (zero SEE in code; roadmap),
  CLI docs match reality, fuzz status made reproducible (tests/uci_smoke.rs), ENVIRONMENT
  snapshot-restore runbook, RATING_PROTOCOL.md pre-registered (not executed; gate BLOCKED).
- 2026-11-14 commit b85b3f7 also contained a corrupted shell-chained clippy run; 837361f is the fix.
- 2026-11-14 workspace restore wiped target/ + toolchain + venv (~07:43Z); git repaired via
  `git fetch origin` (tip 13a316e) + re-applied uncommitted fixes; zero history lost.
- 2026-11-14 Copilot cloud agent pushed 6c749d8 (rustfmt fix identical to concurrent local work);
  its push did not auto-trigger CI; this session re-triggered CI with a log-only push. Never merged.
- 2026-11-14 local toolchain unavailable offline; rustfmt canonicality verified via npm WASM
  rustfmt (rustfmt@0.1.0) + CI; DIFTEST/bench re-verification PENDING until toolchain returns.
- 2026-11-14 MSRV job green with RUSTUP_TOOLCHAIN=1.80.0 + --locked (msrv job: 1.80.0 accepted
  the ep-hash/UCI changes without code changes).
- 2026-11-14 CI root cause via annotations-only channel: clippy `-D` driver args need the
  `cargo clippy ... -- -D warnings` separator; removing it produced `unexpected argument '-D'
  found`, masked as a clippy failure until json→`::error::` annotations surfaced it; real error
  was clippy::manual_range_contains @ src/position.rs:699 (fixed 2c777b5). CI fully green since
  2c777b5 / cd9b7d9 (msrv + ubuntu + windows). When logs are blocked, use the
  check-runs annotations API; do NOT retry gh run view --log / gh run download (blob storage EOF).
- 2026-11-14 workspace restore #3: toolchain/venv/opponents/node_modules wiped; full npm rebuild
  per docs/ENVIRONMENT.md (verified byte-identical SF WASM hashes); tests 29/29, diftest PASSED,
  bench signature unchanged fc907eba40b7869f with 2,221,199 nodes (-43%); clippy too_many_arguments
  fixed via StoreRequest; CodeRabbit 5903125228 (13 findings) dispositioned in source/docs;
  RATING_PROTOCOL Amendment §9 (strict > 2,000; both batches + combined pass; ≥2,000
  games/anchor/batch) appended; CI now uploads bench signature + binary SHA-256 + manifest.

- 2026-11-14 (rating-infra segment): workspace restore #4 clobbered local git to 98b1a00 +
  wiped .venv/toolchain; recovered history via `git fetch` + `git reset origin/<branch>`
  (working tree byte-identical to 0b70906, zero loss). PR #1 returned to Draft (gh pr ready
  --undo) — the earlier "not marked ready" claim was wrong; GitHub had it open/non-draft.
  match.py v2: clock TC (--tc 40/15 repeating, movestogo, elapsed charging, flag, ponder off,
  add/reset policy), 60x17x2 scheduling + shard slicing, engine-error record/immediate-replay/
  abort-after-2, move-cap unadjudicated, manifest v2 (pre + finalized), suite hash, anchor-schema
  hardening. scripts/test_match.py 104/104. tests/clock_smoke.rs + uci clock_limits tests: cargo
  33/33, clippy/fmt clean. scripts/rating_estimator.py (§9.6-9.8 joint bootstrap/GLS/combined/
  null-controls/fail-closed gate) + scripts/test_rating_estimator.py 46/46; scripts/aggregate_shards.py
  (fail-closed §5.2 rules, smoke-verified). Workflows: anchor-research.yml (CCRL 40/15 fetch from
  hosted runner), rating-run.yml, rating-gate.yml (stable fail-closed rating-gate job). Toolchain
  rebuilt from npm (rustc/cargo/clippy/rustfmt 1.99.0; remember chmod +x on bin/ and
  lib/rustlib/*/bin/* — npm strips exec bits and the linker needs gcc-ld/ld.lld executable).

- 2026-11-14 (seg 10 continued — anchor research → verified build ladder):
  anchor-research.yml extended 4× (error-convention extraction, candidate version rows,
  release-tag probes, lower-band rows, homepage links [regex fixed after empty match],
  full tag lists, buildable-family rows). Runner annotations (check 132426702372 /
  132427366210 / 132428391521 / 4ab675d-series) delivered: error convention "95% confidence
  intervals" (→ pool error_convention ci95); version↔rating maps for akimbo/Topple/Weiss/
  Demolito/FabChess/Igel/Halogen/Stash/Pirarucu/Raven/WyldChess/Monolith/Carballo; 342
  lower-band rows (1700–2200). Sandbox CAN reach api.github.com + codeload.github.com →
  tag verification + source downloads done locally. Built + UCI-smoked 4 anchors locally:
  Raven 0.50 (2081±25, id-string "Raven 0.40" caveat), Topple v0.2.1 (2439±14, exact id),
  akimbo v0.1.1 (2441±19, exact id), WyldChess v1.2 (2445±21). Ladder rungs identified:
  Raven 0.70 (2242), Topple 0.1.1 (2324), Raven 0.80 (2341), Raven 0.90 (2451), WyldChess 1.1
  (2474). Excluded with reason: Carballo 0.5/0.8 (no tags before v0.9), Pirarucu (Kotlin
  toolchain unreachable), Counter/CounterGo (version mapping ambiguous). Leads pending
  identity verification: Vice 1.0 (1997±21), Monolith 0.3 (2387), Daydreamer 1.5 (2298),
  Stash 14.0 (2085). benches/anchor-research-20261114.md records all provenance. STATUS.md
  Rating-status section updated (blocker + next actions revised). DESIGN_LOG adversarial
  review entry added (mission §3.8). Commits: 5823fff, d25b683, 82ca55b, 4ab675d, + docs.

- 2026-11-14 (seg 11 — anchor verification complete; pool frozen): workspace restore #5
  recovered via fetch+reset (d023ee8 intact on origin). Lower-band identity research:
  Vice 1.0 unverifiable (bluefeversoft/vice = "Vice 1.2" + Chapter 97+ branches only),
  Rival 1.18/Bubble 1.5/Schola 1.1.0 no verifiable repos (exclusions recorded), wowl 1.3.7
  FOUND (eric-ycw/wowl tag v1.3.7, MIT, CCRL 1849±22/630g). Built all ladder candidates
  locally (11 binaries; 3 hash-reproducible across the restore). anchor-verify.yml written
  (matrix rebuild + UCI id + SHA-256 + LICENSE + verify-flawless bench-signature + SF10
  calibration vs i7-4770K reference 2054ms/3,939,338 nodes from Tors3/CCRL_ScirptsTests).
  5 runner failures diagnosed and fixed via annotations (see FAILURE_LEDGER 2026-11-14 entry).
  Ravens excluded (no license at tested revisions). SF10 factor k=1.0291 → 40/15 wall-clock
  within ~3% of CCRL equivalence. RUNNER-VERIFIED POOL FROZEN: benches/anchor-pool.json
  (Wowl 1.3.7=1849±22, Topple 0.1.1=2324±17, Topple 0.2.1=2439±14, akimbo 0.1.1=2441±19,
  WyldChess 1.2=2445±21, WyldChess 1.1=2474±21; all ci95; run 43597866181 artifacts).
  rating-run.yml acquire step implemented (artifact download + hash-verify, rebuild fallback).
  MERGE_READINESS.md created (§7 checklist with evidence). Local gates: pool schema ✓ (match.py
  fail-closed validator), YAML ✓, test_match 104/104, test_rating_estimator 46/46, cargo 33/33.
  Commits: 5b2cc78, 5a77079, 59c8a0c, 5fd73b1, 086feb8, 0d8287b + this.
254. designed + implemented rating-run dispatch mechanism from the actual repo state (marker-file `benches/dispatch.json` + strict `resolve` job + matrix fan-out); fixed leftover fail-closed `exit 1` stub in the acquire step (would have failed every shard after successful verification); engine hash policy: pilot uses "freeze" (first runner build records hash), confirmatory requires literal frozen hash; wrote PREREGISTRATION.md with PILOT-1 (4 games, 2 shards x 2, excluded from gate evidence) BEFORE dispatch; local validation: YAML OK, dispatch schema OK, suite hash 2c4a54d8... matches, sh syntax OK.
255. dispatched PILOT-1 via marker-file push (workflow: rating-run, paths filter benches/dispatch.json); local engine build at 1127969 rustc 1.99.0 = 9d7b22d5d1af0c56b0d56f908edd679b8628d90126d2fe5efc3c4faf24144208 (local only — runner hash is the one that will be frozen via annotations/manifest).
256. run 43601528240 (c9399fd): resolve+checkout+build+freeze+suite+anchor-acquisition all GREEN (engine freeze hash fd75726dd3166640ddec75d94c416320b47c83e8d14bfa6309aed398d55b8e1d, reproducible across 2 runner builds); match.py step exited 2 (argparse: 'unrecognized arguments: uci') — ROOT-CAUSED LOCALLY: shell word-splitting of --white-cmd './target/release/flawless uci' (match.py splits the single cmd string internally); fixed step to drive match.py via python argv list + stderr->annotations capture (run logs unreachable from sandbox: blob endpoints EOF; annotations API is the working observation channel). dispatch.json rev 3 pins the frozen engine hash; re-dispatched.
257. PR-thread dispositions completed (verified against current code, replies + resolution via GraphQL addPullRequestReviewThreadReply/resolveReviewThread): DS covariance=valid/fixed (§9.6-8 + joint-bootstrap GLS estimator), DW Windows pipe=valid/fixed (reader-thread+Event), D5 TT halfmove=valid/fixed (tt.rs flag + regression), D- uci.rs:433 race=INVALID as described (flush-mutex proof) + NEW jittered stress regression ponderhit_or_stop_racing_search_end_emits_exactly_one_bestmove (30 trials, exactly-once bestmove without follow-up input), EC uci_smoke drain=valid/fixed (post-exit drain_reader + full-line scan). All 11 review threads resolved. Full suites: Rust 34 (lib 6 incl. tt regression + clock_smoke 3 + correctness 21 + uci_smoke 4), test_match 104/104, test_rating_estimator 46/46. MERGE_READINESS updated (2 checkboxes ticked with evidence).
258. registered CTRL-1 + CTRL-2 null controls in PREREGISTRATION.md BEFORE dispatch (thresholds = mission-defined: CTRL-1 published diff within +/-75 Elo; CTRL-2 0.5 within 95% binomial CI); generalized rating-run.yml engine slots (white_engine/black_engine: 'flawless' or pool key; confirmatory constrained to flawless-vs-anchor; control must use batch CTRL); dispatched CTRL-1 (rev 4): topple-0.1.1 vs topple-0.2.1, 240 games, 120 shards x 2, seed 20261115.
259. dispatched CTRL-2 (rev 5): flawless vs flawless self-match, 240 games, 120 shards x 2, seed 20261116.
260. dispatch-mechanism semantics hardened: GitHub's pull_request paths filter matches the WHOLE PR diff (dispatch.json differs from main forever) -> every push re-triggered the marker config; additionally the 4bb6016 push event (CTRL-1 rev 4) was DROPPED entirely by GitHub (no workflow ran; rapid successive pushes) so CTRL-1 never dispatched, while 9e01bf1 (no marker change) re-dispatched the pilot config (run 43603558950; cancel blocked: 403 actions:write — it runs to completion, extra exploratory data only). FIX: resolve now requires the TOP commit of the push to touch benches/dispatch.json ("dispatch push" = one commit moving the marker), else run=false and the shard matrix skips. Re-dispatched CTRL-1 as rev 6 (identical config).
261. estimator match-identity fix: frozen pool `name` fields are non-unique (two 'Topple', two 'WyldChess') while match.py records game engine names = pool `key`; added `anchor_label(entry)` (key-first, name fallback) at all game-matching sites in rating_estimator.py (batch_estimate lookup, control_anchor_vs_anchor, run_gate + control CLI lookups) — frozen pool kept BYTE-IDENTICAL; regression test `test_anchor_label_key_matching` (4 checks). aggregate_shards.py: mixed-runner hardware now WARNING + recorded (documented mixed environment: Azure EPYC 9V74 / AWS Xeon 6975P-C; metadata not identity; transferability validated by null controls; missing hardware record still fails). Suites via CORRECT runners: test_rating_estimator 50/50, test_match 104/104. NOTE correction: earlier "unittest" gate invocations ran 0 tests (see FAILURE_LEDGER false-green entry) — CI always ran the real runners.
262. added `evidence` job to rating-run.yml: after all shards of a dispatch succeed, a runner downloads the run's shard artifacts (blob endpoints unreachable from the sandbox), runs the STRICT aggregate_shards.py (fail-closed hash/TC/suite/shard-count checks), and bot-commits raw per-game evidence (benches/evidence/<purpose>/<label>/games.jsonl + manifest.json w/ merged_sha256) to the PR branch with rebase-retry — satisfies RATING_PROTOCOL §1.3 'reproducible from committed raw evidence' and makes evidence readable by the analysis stage. In-flight runs (pilots, CTRL-1/CTRL-2) predate this job -> a standalone evidence-bridge dispatch will collect them after completion (planned next). YAML OK.
263. wrote evidence-bridge.yml (collects artifacts from EXISTING runs: fail-closed on run completed+success, strict aggregation, disjoint evidence dirs per run, marker-file dispatch on benches/evidence-request.json with the same top-commit gate). Planned entries once runs complete: pilot 43602273258 -> evidence_purpose 'pilot'; duplicate pilot 43603558950 -> 'pilot-dup'; CTRL-2 43603826611; CTRL-1 43604654709.
