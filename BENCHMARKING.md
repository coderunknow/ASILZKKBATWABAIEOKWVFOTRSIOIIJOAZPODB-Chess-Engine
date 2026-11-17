# BENCHMARKING.md — measurement policy & infrastructure

## Measurement categories (never conflate)

1. Fixed-node search efficiency (nodes to reach depth at fixed search).
2. Fixed-time playing strength (games, Elo vs pool).
3. NPS / microbenchmarks (mach reproduces only the implementation, not strength).
4. Tactical suite results (e.g., WAC-style puzzles once wired).
5. Rating estimates vs a pinned opponent pool.

## Pinned environment template (record per experiment)

- Commit SHA, binary SHA-256, build flags (`-C target-cpu`? none — portable default), profile.
- UCI options: Hash, Threads, MultiPV.
- Opponent(s): name, version, binary SHA-256, options.
- Time control; opening suite + seed; color-reversal plan; adjudication rules.
- Hardware + OS; date; operator (agent session id).

## Rating policy (see ARCHITECTURE §9)

- Primary reference scale: CCRL 40/15 (i7-4770k equivalence; Stockfish 10 calibration reference;
  ponder disabled; same hash policy; generic opening books). As close as resources permit locally.
- Secondary: CEGT 40/20. **No cross-scale subtraction.**
- No batch has yet been run against documented-Elo anchors, so **every result to date is a private
  relative estimate** (opening-clustered CI), NOT "CCRL-anchored" and never an official rating. Only a
  batch meeting all of RATING_PROTOCOL §2–§6 (documented anchors, verified binary SHA-256, null
  controls) may carry a *CCRL-anchored (private)* label.
- Paired openings, reversed colors, opening-clustered bootstrap CIs, ≥2 confirmation batches,
  staged sample sizes (200–500 / 1,000–2,000 / 4,000–6,600).
- Null controls included (e.g., baseline vs itself must score ≈ 50%).

## Infrastructure in this repo

- `cargo run --release -- bench` — fixed-depth-10 search benchmark over 12 fixed positions; prints
  per-position depth/score/nodes and a total + FNV-1a `bench signature` (deterministic for identical
  engine code; node counts are the regression signal). Signature history (all 2026-11-14):
  `d790483532d87af0` → `3086f65159758c9d` (2,317,474 nodes; audit fixes) → `f1aceef5a9dbc812`
  (2,367,196 nodes; FIDE ep-hash semantics + castling-origin-king guard) → `fc907eba40b7869f`
  (3,899,001 nodes; draw/TT/delta-prune corrections — NPS cost accepted for soundness) → **re-measured
  2026-11-14 on db174e4 (restored npm toolchain; `cargo run --release --locked -- bench`): signature
  unchanged (`fc907eba40b7869f`, i.e. depth/score/PV line stable) but 2,221,199 nodes @ d10 — a 43%
  node reduction from the per-capture delta-pruning rework — 8.56 s, 259,619 nps on this 2-vCPU
  sandbox. CI runs an informational bench step which also uploads the signature as an artifact.**
  The stale
  "2,326,103 nodes in ~3.1 s" line was a mixed-build measurement error and has been removed.
- `cargo run --release -- bench_eval` — fixed-node eval micro-benchmark (1000 evals/FEN, ~100–500 ns/eval in sandbox).
- `cargo run --release -- perft <depth> [fen]`.
- `cargo run --release -- uci [uci|perft ...]` — full UCI engine; `go movetime/depth/clocks`, `ucinewgame`, MultiPV, ponder.
- `scripts/match.py` — game runner (UCI subprocess), writes PGN + JSONL records, supports opening files
  (`name|moves` UCI lines), color reversal (paired mode), adjudication via python-chess outcomes,
  timeout/illegal-move forfeits, and wall-clock accounting. Verified end-to-end.
- `scripts/stats.py` — score, Elo difference (logistic model), opening-clustered 95% bootstrap CI
  (bootstrap over opening clusters, not games).
- `scripts/diftest.py` — differential correctness vs python-chess.

## Pinned benchmark opponents

- **Stockfish 19 WASM (lite-single, single-threaded)**, npm package `stockfish@19.0.1`
  (`buildVersion 19`, GPL-3.0), files at `node_modules/stockfish/bin/stockfish-19-lite-single.*`.
  SHA-256 (recorded 2026-11-14): `stockfish-19-lite-single.js` ccb130d7ff29408531c47d859a49f91d59d4f482d05a53eb1a3231a4f624c91a,
  `stockfish-19-lite-single.wasm` ee4f115bdb2d32cadf96cada104a05b5ec257d7ad6f57582190b49bc71f096de.
  (Full-strength `stockfish-19.js` also present: 623ee70a10d6dc202375127b49e2e1822635f9ab07693ae7be28e50a787f6218; `stockfish-19.wasm`: a599d78d72e0722d8895be84aca8b492d12e8bba3cdfcbcbc4a64017888c6667).
  Run via `node`. Used ONLY as a pinned benchmark opponent, never as a code source.
  Invoked with `setoption name Skill Level value <0..20>` to build a strength ladder; CCRL-equivalence
  of any skill level is NOT claimed.
- Location on disk: `/home/user/opponents/` (outside the repository; not committed).

## Completed probes (2026-11-14)

See STATUS.md "Measured strength probes" for the table. Raw evidence: `benches/probe-001-sf19lite-skill0/`
(40 games), `benches/probe-003-sf19lite-skill5/` (40, pre-RFP/CE build, 2026-11-14T03:28:59Z),
`benches/probe-002-sf19lite-skill10/` (40), `benches/probe-004-sf19lite-skill5-rfp/` (40, RFP+CE
build, 2026-11-14T04:26:01Z), `benches/ab-004-rfp-checkext/`
(40 A/B vs pre-change build, movetime 50 ms), `benches/probe-005-postfix-validation/`
(40, post-refactor builds, 100 ms/move; Flawless 24/40 = 0.600, 95% CI [0.463, 0.725],
logistic +70 CI [−26, +168]; engine binary SHA-256 9d7b22d5d1af0c56b0d56f908edd679b8628d90126d2fe5efc3c4faf24144208, git commit 45f8507 in meta.json) — PGN + games.jsonl + meta.json committed.
**Binary-hash caveat:** probe-003 and probe-004 meta.json predate the binary-hashing instrumentation
(added 2026-11-14); they record the probe command line but NOT the probed binary's SHA-256 or the
git commit — their engine identity rests on the recorded cmd + timestamps, not a verifiable hash.
New batches record `white_artifact`/`black_artifact` ({binary path, sha256}) and `git_commit` in
meta.json (see `scripts/match.py`). Method limitations (honest): fixed 100 ms/move, single pinned
WASM opponent, no CCRL-equivalent TC, Skill Level ≠ Elo, 2 vCPU sandbox, bootstrap CIs over 20 opening
clusters only.

## Current status (2026-11-14)

No rated games exist yet. Opponent availability is limited by the sandbox network (only github.com /
codeload.github.com / api.github.com / pypi.org / files.pythonhosted.org / registry.npmjs.org).
Candidate anchored opponents: Stockfish WASM from npm (`stockfish@…`, to be pinned and hash-verified
before any match) — its exact CCRL equivalence is NOT claimed; only internal A/B strength measurements.
Any Elo number produced here is an in-sandbox estimate with stated uncertainty, not an official rating.

## Raw evidence retention

`benches/<experiment-id>/` contains: PGN, JSONL, match config (meta.json incl. binary SHA-256 +
git commit for new batches), engine logs, stats output. Never overwrite; `scripts/match.py` refuses
to write into a directory holding non-empty batch artifacts, and new batches go in new directories.

## Rating batch pre-registration (2026-11-14)

- `benches/rating-openings-batchA.txt`, `benches/rating-openings-batchB.txt` — 60 distinct,
  FEN-legality-verified opening lines each, curated 2026-11-14 from standard opening theory,
  **mutually disjoint**; every line is played as an AB/BA pair (exact color reversal). Batch B is
  used for the independent confirmation batch.
- `benches/anchor-pool.template.json` — schema template for the anchor descriptor embedded in
  batch manifests via `scripts/match.py --anchor-json`. Contains NO anchor values; filling it with
  independently verified CCRL 40/15 or CEGT 40/20 data is a prerequisite for any gate run.
- Batch manifest (`meta.json`) now records: binary SHA-256 for launcher AND every hashed artifact
  (including WASM loaded dynamically, via `--white-artifact`/`--black-artifact`), git commit, CPU/RAM/OS,
  hostname, python version, full adjudication rules, color-pairing rule, and (with `--anchor-json`)
  the complete anchor-pool descriptor. `scripts/match.py` refuses to start unless the anchor pool
  passes the schema check.
## 2026-11-17 — reduced sample design and runner telemetry

RATING-100 reduces the proposed counted sample from 2,040 to 100 games per anchor per batch: 50 opening clusters × one paired repetition × AB/BA. For three anchors and two disjoint batches the arithmetic is 12,240 → 600 counted games (95.0980%). This is a design/sample-count reduction only; it is not evidence of faster chess search, higher games-per-hour, or a stronger engine.

The new workflow records per-shard `/usr/bin/time -v` output and pre/post cgroup values including CPU quota (`cpu.max`), throttling counters (`cpu.stat`), effective cpuset and memory limit. Future throughput reports must compare elapsed wall time, user/system CPU, peak RSS, cpu throttling, runner model/image, actual shard count/concurrency and counted-game totals. Do not infer a concurrency win from vCPU labels alone.

The 100-game design is currently **BLOCKED** for confirmatory use: selected-subset variance is available for only two screening anchors; the third-anchor covariance and disjoint Batch-B cluster distribution remain unmeasured. Near a 2,100 Elo true-rating alternative, the sensitivity analysis shows only ~63–77% power for all three lower-bound conditions without variance inflation, ~22–31% at 1.5× cluster SD and ~8.7–12.4% at 2×. The registered strict 95% lower-bound rule and both null controls are unchanged.
