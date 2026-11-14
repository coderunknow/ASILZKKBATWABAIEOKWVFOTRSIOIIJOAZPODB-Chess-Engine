# DESIGN_LOG.md (append-only)

## 2026-11-14 — Phase 0/1 kickoff

- Verified repository state: starting commit `98b1a00` ("Initial commit"), tree contains only `LICENSE`
  (Apache-2.0). Branch `arena/b756c5f1-asilzkkbatwabaieokwvfotrsioiij`. No tags, no workflows, no other branches.
- Environment: crates.io + static.rust-lang.org unreachable → zero-dependency Rust, toolchain from npm
  `@toolchain-bin/*` (see `docs/ENVIRONMENT.md`).
- Decisions: bitboards + startup-generated magic sliders (ADR-0001); pseudo-legal movegen with
  make/unmake legality filter; single-threaded V1 with future-SMP-safe encapsulation; NNUE deferred
  behind classical baseline; honest `Threads max 1`.
- Risks recorded: (1) rating gate unlikely to be measurable in this sandbox; will report INCONCLUSIVE
  rather than claim pass. (2) Toolchain provenance: npm redistribution of official binaries, checksums
  recorded in ENVIRONMENT.md.

## 2026-11-14 — Phase 3/4/UCI checkpoint (search + evaluation + UCI)

- Decisions: classical tapered eval first (MG/EG PSTs, mobility baselines, bishop pair, king-zone,
  tempo=12 cp); NNUE deliberately NOT built yet (no measured win, no teacher pipeline).
- TT: Zobrist 8-byte entries, power-of-two, generation aging, ply-relative mate scores, TT-move
  extraction for PV recovery (no separate PV array).
- Search: ID + aspiration (depth ≥ 6, ±25 initial, widen ×3+20) + PVS + quiescence (delta 200,
  MVV-LVA) + null-move (depth ≥ 3, non-PV, beta < MATE_BOUND, non-pawn material) + futility
  (depth ≤ 2) + LMR (r = ln d · ln n · 0.6, re-search on fail-high) + killers/history.
  Repetition (2-fold path), 50-move, insufficient material are draws inside search; no-legal-moves
  handled for mate/stalemate.
- UCI: single worker thread; `go` returns immediately; `stop` sets AtomicBool and joins; bestmove
  printed by the worker so it appears even without further stdin commands (fixed — previously
  bestmove was only printed on the next stdin line / EOF, violating the UCI protocol).
- Abort safety: root scores after an abort are discarded; mate scores reported only for genuinely
  mate-bounded |score| ≥ MATE_SCORE−100 (clamped otherwise).
- UCI smoke: depth-limited search on Kiwipete (FEN r3k2r/...) reaches depth 8–10 with MultiPV 3;
  mate-in-1 FEN (6k1/8/6K1/8/8/8/8/1Q6 w - - 0 1) → `bestmove b1b8` at any depth; ~0.9M nps
  single-threaded in sandbox.
- Known gaps (honest): no strength measurement yet; no match/CI; `Threads` hard-capped at 1;
  UCI not fuzzed; see STATUS.md / FAILURE_LEDGER.md (no rating claims).

## 2026-11-14 — First strength probes + CI + match infrastructure

- GitHub Actions CI (Windows+Linux: fmt, clippy -D warnings, release tests, release build, UCI
  handshake, perft d3) — green on PR #1. Kilo review bot fails (insufficient account credits);
  not a code verdict.
- Match infrastructure implemented (`scripts/match.py`, `scripts/stats.py`); 20 verified openings;
  paired games with color reversal; opening-clustered bootstrap 95% CIs.
- Two engine bugs found by benchmarking and fixed: (1) LMR table out-of-bounds panic at depth 64 /
  move-count 64+ (thread died, GUI starved → timeout loss); (2) no fallback bestmove on thread
  panic (worker now wraps search in catch_unwind and emits legal fallback; main thread rebuilds TT).
- Probes vs pinned Stockfish 19 WASM (movetime 100 ms): SF Skill 0 → 40/40 wins (checkmates);
  SF Skill 5 → 11/13/16 (≈ −44 Elo diff); SF Skill 10 → 1/7/32 (≈ −359). Engine is between
  pinned Skill 5 and Skill 10; far from any 2000-Elo gate; results are in-sandbox internal
  estimates only, never to be presented as official ratings.
- NNUE still NOT built; classical eval unchanged pending measured need.

## 2026-11-14 — Search strength experiment: reverse futility pruning + check extensions

- Change (src/search.rs): (1) reverse futility pruning at depth ≤ 3, non-PV, not in check,
  mate-bound-safe (s − 150·depth ≥ beta → fail high); (2) check extension — when in check, child
  searches are made at depth−1+1 instead of depth−1.
- Correctness re-verified: fmt/clippy −D warnings/tests 18/18/diftest PASSED.
- bench signature changed a7a9f01893e9f1a5 → d790483532d87af0 (2,798,466 nodes @ depth 10) — expected.
- A/B (benches/ab-004-rfp-checkext, 40 paired games vs the previous build at movetime 50 ms):
  ours-rfp-cext 18 W / 13 D / 9 L vs ours-before → score 0.613, opening-clustered 95% bootstrap CI
  [0.487, 0.725], logistic Elo diff +80 (CI [−9, +168]). Positive direction; NOT conclusive at this
  sample size/TC; lesson: treat as directional only, keep change since standard and safe, verify
  no correctness regressions (all gates pass).

## 2026-11-14 — Identity migration to Flawless

- Engine public identity migrated from ASILZKKBATWABAIEOKWVFOTRSIOIIJOAZPODB to Flawless (user
  decision; repo now exists as `coderunknow/Flawless-Chess-Engine`, old name auto-redirects).
- Package/library/binary renamed to `flawless`; `flawless::` crate paths; `id name Flawless`;
  `id author coderunknow (Apache-2.0)` keeps authorship (not the product name).
- ADR-0002 recorded. Historical benchmark artifacts/PGNs/append-only logs NOT rewritten (old name
  retained there deliberately). Branch name unchanged (mission: do not rename existing branch).
- Verified: build OK, UCI id line reports Flawless, 18/18 tests pass.

## 2026-11-14 — Audit pass 1: terminal/draw precedence + panic-fallback plumbing

Defects found and fixed (all reproduced by failing→passing tests in tests/correctness.rs):

1. `search()` returned `DRAW_SCORE` for repetition/fifty-move nodes BEFORE detecting checkmate —
   a mated position at halfmove ≥ 100 (or reached off a repeating path) scored as a draw.
   Fix: insufficient-material remains an immediate draw (FIDE dead position); repetition/fifty-move
   shortcuts now require `!in_check`; the no-legal-moves terminal check runs BEFORE null-move/
   futility/RFP and scores mate as -MATE+ply (mate precedence, FIDE 9.6.2). Stalemate → DRAW_SCORE.
2. `quiesce()` applied the stand-pat beta cutoff and delta pruning BEFORE the terminal check —
   a stalemate qsearch node could return a fail-high (beta) or a bogus upper bound (alpha).
   Fix: generate legal moves first; terminal check before any stand-pat cutoff.
3. Reverse futility pruning could fire on a terminal (stalemate) node returning `beta` — now
   unreachable (terminal check precedes RFP).
4. `go searchmoves X` was silently ignored by the MultiPV=1 search path (root restriction was
   only applied to the MultiPV>1 enumeration, not to the PVS main line). Fix: root filter applied
   at ply 0 inside `search()` via a `root_moves` field on `Searcher`; `go searchmoves` with an
   empty move list now falls back to all legal moves instead of emitting `bestmove 0000`.
5. Panic fallback (search thread dies): engine now emits a GUI-visible
   `info string search thread panicked; emitting fallback bestmove` on stdout; match.py detects it,
   tags the game `engine_error=true` with `engine_error_turns`; stats.py excludes such games from
   statistics unless `--include-engine-error` is passed. Previously the fallback was invisible
   (marker went to stderr, which match.py devnull'd) so panicking games were counted as normal.
6. CI: removed remaining `|| true` masks on smoke steps; added a UCI bestmove smoke (depth 2) and
   an MSRV (Rust 1.80) job; Windows + Linux both run smoke tests at runtime.

Consequences:
- bench signature changed d790483532d87af0 → 3086f65159758c9d (2,317,474 nodes): positions 4/6/7
  PVs shifted after the unsound-pruning removal and mate-precedence fix (deterministic per build).
- 24/24 tests incl. 6 new audit regressions. DIFTEST (perft d=2, 2321 positions): 0 mismatches.
- The bench change is a correctness consequence, NOT an optimization; no strength gain claimed.

## 2026-11-14 — CodeRabbit 13a316e findings addressed + sandbox restore survival incident

Context: workspace restore (~07:43Z) wiped `target/`, the entire Rust toolchain
(`/home/user/.toolchain`, `.rustup`, `.cargo`) and the Python venv (`python-chess`). Only the repo
(excluding `target/`) and a base-only `.git` pack survived.

Recovery (no data lost from history — remote is authoritative):
- `.git` objects for the branch were missing locally; `git fetch origin` restored them (tip
  `13a316e` verified). Uncommitted source fixes on disk were preserved and re-applied.
- Toolchain is unrecoverable offline (static.rust-lang.org unreachable; npm `rustc@1.74.0` too old
  for `std::sync::LazyLock`/MSRV 1.80 semantics). Local builds are IMPOSSIBLE until a toolchain
  returns; verification moved to (a) CI and (b) a pinned npm WASM rustfmt
  (`rustfmt@0.1.0`, only for files without `let-else`; its `single_line_if_else_max_width` rule = 50).
- Copilot cloud agent ("Agent Merge on PR #1") pushed `6c749d8` "Fix rustfmt CI formatting diffs"
  (co-authored copilot-swe-agent[bot]) with the same two canonical transforms this session derived
  (position.rs if-else expansion; search.rs if-condition collapse). Local duplicate was discarded.
- Bot push does not auto-trigger `pull_request` CI (GITHUB_TOKEN recursion guard) and
  `workflow_dispatch` is 403 for this integration — CI for 6c749d8 was re-triggered by an ordinary
  session push instead. PR remains OPEN, never merged by this project.

Engine/UCI fixes (9548467, 15526ed, 6c749d8):
- FIDE "same position" ep-hash (file included only when an ep capture is actually legal, incl.
  rank-pin probes); unpack FEN validation for ep squares and side-to-move-attacking-king rejection;
  castling emission now requires the king on e1/e8.
- Mate takes precedence over claimable draws; draws honored in check and in qsearch; NOT-in-check
  draw fast path before the TT probe; TT score cutoffs disabled past halfmove ≥ 90; delta pruning
  is per-capture (victim + promotion swing), sound vs the stand_pat<alpha queen-capture example;
  restricted-root (`go searchmoves`) scores never stored as unrestricted TT bounds; root PV head
  comes from an explicit `root_best`.
- `go infinite`/`go ponder`/bare `go`: clock/node abort inert until ponderhit/stop (should_stop_now);
  bestmove printed exactly once per `go`; ponder holds bestmove until ponderhit/stop; ponderhit
  converts to timed search; `bestmove 0000` on NULL; clock caps soft ≤ remaining, hard ∈ [soft, cap].
- match.py: deadline-safe buffered line reader; broken pipes → engine-error losses (never batch
  crashes); full-move-history `position startpos moves ...`; batch artifacts write-fresh-only with
  refusal to overwrite; meta.json records artifact binary path + SHA-256 and git commit.
- stats.py: 0/1 scores are boundary notation, never clamped finite "Elo" (probe-001 +2400 artifact).
- CI: MSRV job explicit RUSTUP_TOOLCHAIN=1.80.0 + --locked; informational bench step (signature may
  be read from run logs). Note bench signature pending re-measurement on this tree — expect it to
  differ from `fc907eba40b7869f` (3,899,001 nodes @ d10, pre-per-capture-delta-pruning measurement).

Process honesty:
- DIFTEST/bench local verification NOT re-run (needs toolchain + venv, both gone) — PENDING.
- Kilo ACTION_REQUIRED remains a billing limitation, not a code issue. CodeRabbit SKIPPED (bot
  auto-skip); its findings are being addressed commit-by-commit regardless.

2026-11-14 (clippy root cause + CI diagnostics channel):
- CI clippy (deny warnings) failed on ubuntu-latest and windows-latest for several pushes with
  no retrievable log (`gh run view --log*`, `gh api .../actions/jobs/<id>/logs`, and
  `gh run download` all EOF against productionresults*.blob.core.windows.net). Root cause was
  isolated by temporarily rewriting the clippy step to `--message-format=json` piped through an
  embedded python3 converter that re-emitted each level=error compiler-message as an `::error>`
  check annotation (plus a raw head/tail dump in `::notice::`/`::error::`); the annotations API
  (`gh api repos/<owner>/<repo>/commits/<sha>/check-runs` + `/check-runs/<id>/annotations` on
  api.github.com) is the only working diagnostics channel this environment has. The converter's
  first run surfaced `error: unexpected argument '-D' found` — the edit had dropped the `--`
  separator before driver args (`cargo clippy -- -D warnings`, not `cargo clippy ... -D warnings`);
  annotations then showed the true error: `src/position.rs:699` `clippy::manual_range_contains`
  (`if f < 0 || f > 7` → `if !(0..=7).contains(&f)`, fixed in 2c777b5). A prior speculative
  `needless_range_loop` fix (da178a6, `legal.iter()`) was real but not the failure.
- With the fix in place the whole workflow is green (msrv, ubuntu-latest, windows-latest, run
  43574593496 on 2c777b5). The temporary clippy scaffold (continue-on-error + tee + artifact
  upload + verdict step) was removed and the plain step restored (cd9b7d9); run 43574700347
  confirms green with the restored simple step. The JSON→annotations converter remains documented
  here for future log-blocked episodes.
- apt-get is unusable (deb.debian.org unreachable, partial lists root-owned); local toolchain
  remains unavailable. CI is the build oracle. Bench signature still requires a real build;
  informational CI bench step remains the channel, but its output is not machine-readable here
  without log access — re-measurement remains PENDING until toolchain or log access returns.

2026-11-14 (workspace restore #3 — full rebuild, all gates re-verified):
- /home/user/.toolchain, .venv, /home/user/opponents, node_modules wiped again; only pushed origin
  state survived. Rebuilt exactly per docs/ENVIRONMENT.md: npm @toolchain-bin pins
  (rustc/cargo 1.99.0, clippy 0.1.99, rustfmt 1.10.0) + `install.sh --prefix` per component +
  execute-bit fix; venv (python-chess 1.11.2); pinned SF 19 WASM reinstalled and SHA-256 verified
  identical to BENCHMARKING.md (ccb130d7…/ee4f115b…); opponents/ mirrored and re-hashed.
- Local verification on the restored tree (first real build since the wipe):
  `cargo test --release --locked` 29/29 green; `cargo fmt --all --check` clean; clippy 1.99.0
  found ONE latent error invisible while CI logs were blocked: tt::store grew to 8 args
  (clippy::too_many_arguments, -D warnings) — fixed by bundling `StoreRequest` (key, best_move,
  score, depth, bound, ply, halfmove); CI failure on db174e4 (ubuntu exit 101 / windows exit 1)
  was exactly this. CodeRabbit review-2 instrumentation was NOT required in the SAME run — the
  local toolchain displaced blind debugging; the temporary diagnostic step remains on the branch
  pending CI green, then returns to the plain step.
- DIFTEST re-run (seed 20261114, 300 games): legal-move sets identical, perft-d2 2295/2295,
  0 mismatches — PASSED. Bench re-measured (db174e4): signature UNCHANGED `fc907eba40b7869f`
  (depth/score/PV stable) with 2,221,199 nodes @ d10 — 43% fewer nodes than the recorded
  3,899,001, i.e. the per-capture delta-pruning rework is active and effective; 8.56 s,
  259,619 nps on 2 vCPU. BENCHMARKING.md updated.
- CodeRabbit review 5903125228 (13 findings) dispositioned: src (null-move ep-hash inclusion,
  in-check draw-before-TT, restricted-root extract_pv confinement, CLOCK-UNSAFE TT entries for
  fifty-move-horizon subtrees, ponderhit/worker flush mutex, smoke-test drain-after-exit),
  scripts (select-free reader thread, launcher+script artifact hashing, O_EXCL batch reservation,
  stats.py boundary endpoints as no-finite-estimate + bootstrap SD), docs (STATUS de-clamp;
  RATING_PROTOCOL Amendment §9: strict > 2,000 gate, both batches + combined must pass,
  ≥ 2,000 games/anchor/batch, no predictions/clamping, sequential-stopping rules, SD-based
  σ_matched, covariance-aware GLS combination, batch combination retaining shared calibration).
