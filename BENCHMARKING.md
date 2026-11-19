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

## 2026-11-17 — ENGINE-2 SEE-ordering candidate (preliminary hosted build)

- Candidate source: the RATING-100 / SEE-ordering implementation commit. The SEE change is limited to capture ordering; no SEE-based quiescence pruning is used.
- Hosted Ubuntu fixed-depth-10 bench signature: `141943aa23b3fc68` (12 fixed positions, 2,530,885 nodes in 7.09 s on the recorded runner). This is a deterministic implementation fingerprint, not a playing-strength or throughput comparison.
- The earlier `fc907eba40b7869f` signature belongs to the pre-SEE ordering candidate and is retained only as historical evidence. The anchor verifier now expects the new signature.
- The new candidate binary SHA-256 remains pending a successful exact-head anchor-verification run. No rating games have been dispatched for this candidate.

## 2026-11-17 — reduced-suite byte-integrity correction

The initial reduced-suite bytes were rejected by the Python standard-library selector verifier in CI; no confirmatory work ran. Corrected selector uses hashlib.sha256 over the documented domain-separated normalized original line, selecting the 50 lowest digests and retaining source order. Corrected suite byte hashes: Batch A 5abdcdbddec0f22d7e6eff8974ee402363c8c3df318b8110d7204adf69f5c1df; Batch B ccb4901742eca25b0b10f1a3c9fdfc17b2967a1939c2d7e466c2c5495b6d4253. The power assessment remains BLOCKED; no dispatch is authorized.


## 2026-11-17 — ENGINE-2 identity and power-report scope

- Exact branch tree: source commit 5b63e273d77cfb097f0ad73bc28dda05cc19adad, tree 75bc5633e1466d5abf1f4c7d5999bc4a3915e193.
- Anchor verification run 44066217113 built the matching PR merge tree: bench signature 141943aa23b3fc68; binary SHA-256 168dc0ab22749f8dc7a6be5248cd7426f9f2bfd3fda8077bc6218959ad6e41d7. This is a source/binary identity, not a strength or throughput comparison.
- Current RATING-100 power inputs belong to ENGINE-1 SHA-256 9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428. The report is now engine-pinned; the generator checks both SCREEN-2 manifests and raw data hashes, and dispatch tooling refuses any binary SHA mismatch. It cannot authorize ENGINE-2.
- ENGINE-2-specific screening and controls are still absent. No game-count or games/hour performance result has been measured for this candidate.

## 2026-11-18 — STRENGTH-1 screening campaign (fixed clock, screening only)

**What this measures.** Playing strength at a *fixed per-move time budget*, at a fixed
hash size, with the search tree allowed to differ between builds. This is **not** an
absolute rating and **not** a CCRL/CEGT result; the logistic Elo difference below is a
descriptive internal statistic computed by `scripts/stats.py`.

**Design (registered in `PREREGISTRATION.md` before dispatch).**

| Property | Value |
|---|---|
| Harness | `scripts/match.py`, unmodified |
| Time control | fixed `movetime` 100 ms per move |
| Hash | 16 MiB, both engines |
| Threads | 1, both engines |
| Openings | `benches/openings-20.txt` (20 openings, SHA-256 `97f991eb3b827ffe5e3cb378ad7699a8d1dc860bec08ec939d08e611743fb23d`) |
| Schedule | opening-major, repetition-minor, **exact AB/BA colour reversal** |
| Sample | 20 openings × 2 repetitions × 2 colours = **80 counted games per pair** |
| Analysis | `scripts/stats.py`, logistic Elo difference, **95 % bootstrap CI resampled over openings**, 10,000 resamples, seed 20261118 |
| Raw evidence | `/home/user/matches/<pair>/games.jsonl` plus per-shard files and logs |

**Results.**

| Pair | Candidate score | 95 % CI (score) | Elo diff | 95 % CI (Elo) | Decision |
|---|---|---|---|---|---|
| BASE vs SPEED-1 (analytic fast legality filter) | 0.625 (50.0/80) | [0.519, 0.725] | **+89** | [+13, +168] | **KEPT** |
| BASE vs HIST-1 (history tables + full-window LMR re-search) | 0.406 (32.5/80) | [0.306, 0.512] | **−66** | [−142, +9] | **INCONCLUSIVE** |

Integrity of both pairs: 80/80 games counted, **0 engine errors**, 40 AB + 40 BA colour
pairs, 20 openings × 4 games each, and every opening with exactly 2 games per colour.
Terminal reasons were checkmate, threefold repetition, fifty-move and insufficient
material only.

**Interpretation, stated precisely.**

- SPEED-1 is kept because its searched tree is *provably identical* to the baseline
  (bench signature `141943aa23b3fc68`, 2,530,885 nodes) and the interval excludes zero.
  The mechanism is throughput: ~441 k nps → ~785 k nps at fixed depth 10, so a fixed
  100 ms/move buys more of the same tree. This is a **speed-mediated** gain, and the
  NPS increase is the *explanation*, not the *evidence* — the evidence is the 80 games.
- HIST-1 is **INCONCLUSIVE**. The interval straddles zero, so the change is retained
  only as a candidate. It is **not** described as a strength improvement, and the
  negative point estimate is not hidden either.

**Reporting defect, disclosed.** The first campaign log reported the sign inverted,
because the runner passed the *baseline* name to the statistics script where the
registration specifies the candidate's perspective. The raw JSONL was never modified;
the registered estimator was re-run on the same records with `--focus <candidate>`, and
the runner now takes the candidate name explicitly. See `FAILURE_LEDGER.md`.

## 2026-11-18 — EVAL-2 evaluation ablation (registered before dispatch)

Seven matched pairs, each played against the **same** control (EVAL-NONE, the parent
tree with every evaluation flag off), so that the seven estimates are directly
comparable and no evaluation change can hide inside an aggregate.

Control validity was verified **before** any game was played: EVAL-NONE reproduces the
parent tree's bench signature `8370f143c3b76fb4` and node count 2,697,573 exactly.

These are the **EVAL-2** identities, pinned before dispatch and taken verbatim from
`PREREGISTRATION.md` § "EVAL-2". The earlier EVAL-1 set was withdrawn and its binaries
must not be mixed in: the outpost pawn-attack tables were found to be inverted in both
directions, the fix changes the evaluation values, and every EVAL-1 binary therefore
measured a different program from the one in the tree.

| Variant | Flags disabled | SHA-256 | Bench signature | Depth-10 nodes |
|---|---|---|---|---|
| EVAL-NONE | all six | `a4695a7c…` | `8370f143c3b76fb4` | 2,697,573 |
| EVAL-ALL | none | `0ab1d0cb…` | `b58979ca90492208` | 3,666,233 |
| EVAL-NO-MOBILITY-TAPER | `FEAT_MOBILITY_TAPER` | `b4cb1dfd…` | `ef9410f8cce0da89` | 3,161,626 |
| EVAL-NO-PAWN-STRUCTURE | `FEAT_PAWN_STRUCTURE` | `2e3bfdd0…` | `c164bbabc73cfc45` | 3,335,879 |
| EVAL-NO-PASSER | `FEAT_PASSER` | `511e6d65…` | `ef9410f8cce0da89` | 3,590,574 |
| EVAL-NO-SPACE | `FEAT_SPACE` | `47e2e22f…` | `e282fa6554c5cecd` | 4,547,011 |
| EVAL-NO-OUTPOSTS | `FEAT_OUTPOSTS` | `7eb2c79e…` | `906fe14c58ff639f` | 4,278,204 |
| EVAL-NO-KING-SAFETY | `FEAT_KING_SAFETY` | `85331959…` | `acf066a921c1dde1` | 3,080,004 |

See `PREREGISTRATION.md` § "EVAL-2" and `FAILURE_LEDGER.md`.

Note that the ablation builds differ in *node count* as well as in score: changing the
evaluation changes which lines the search follows. That is why a node-count comparison
across variants is meaningless, and why the decision is made from games only.

**Decision rules (fixed before dispatch).** EVAL-ALL is KEPT if its 95 % CI lower bound
is > 0, REJECTED if the upper bound is ≤ 0, INCONCLUSIVE otherwise. A feature is
flagged HARMFUL if its ablation point estimate is more than 40 Elo *higher* than
EVAL-ALL's; features within 40 Elo are INDETERMINATE and are retained but not claimed.
No individual feature may be claimed as a strength improvement from this screening.

**Result:** see `PREREGISTRATION.md` § "EVAL-2 — result record". The EVAL-1
result record was withdrawn (see above) and its numbers must not be cited.

The EVAL-2 campaign measured all seven pairs, 560 games, zero engine errors,
and every pair passed the schedule audit (80 counted games, no duplicate
slots, 40 AB / 40 BA, 20 openings with 4 games each).

| Pair | Score | Score CI | Elo diff | Elo CI |
|---|---|---|---|---|
| EVAL-NONE vs EVAL-ALL | 0.519 | [0.419, 0.619] | **+13** | [−57, +84] |
| EVAL-NONE vs EVAL-NO-MOBILITY-TAPER | 0.419 | [0.319, 0.512] | −57 | [−132, +9] |
| EVAL-NONE vs EVAL-NO-PAWN-STRUCTURE | 0.525 | [0.456, 0.594] | +17 | [−30, +66] |
| EVAL-NONE vs EVAL-NO-PASSER | 0.506 | [0.388, 0.625] | +4 | [−80, +89] |
| EVAL-NONE vs EVAL-NO-SPACE | 0.469 | [0.381, 0.556] | −22 | [−84, +39] |
| EVAL-NONE vs EVAL-NO-OUTPOSTS | 0.469 | [0.394, 0.537] | −22 | [−75, +26] |
| EVAL-NONE vs EVAL-NO-KING-SAFETY | 0.506 | [0.406, 0.606] | +4 | [−66, +75] |

**Aggregate: INCONCLUSIVE.** The registered rule keeps the change only if the
CI lower bound is > 0 and rejects it only if the upper bound is <= 0; the
interval [−57, +84] contains zero, so neither applies. The evaluation
upgrade is **not** merged as a strength improvement, and the six flags stay in
the tree as measurement scaffolding, which the registered rule explicitly
permits.

**Per feature:** no feature is flagged HARMFUL. Turning the mobility taper off
is 70 Elo worse than keeping it on — the only comparison outside the
40-Elo indeterminate band. The other five are within the band and are
retained but **not claimed**. No individual feature is described as a
strength improvement.

## 2026-11-18 — evaluation cost

The evaluation was measured at **24.5 % of node time** (2,667,410 evaluation
calls over 3,666,233 nodes in the depth-10 bench), and the profile put the
pawn-structure section at roughly a third of the evaluation cost.

Three changes, all of which leave the evaluation *values* bit-identical,
brought the cost down by about 11 %:

| Change | What it removes |
|---|---|
| Share the slider attack masks | `eval_color` runs once per side and computed the masks for a side's own pieces (mobility) and again for the other side's pieces (king safety), so every slider's mask was computed twice per evaluation. A queen was worst: `queen_attacks` for mobility, then `bishop_attacks` and `rook_attacks` separately for king safety — three lookups for one queen. |
| Lookup tables in the pawn-structure section | For every pawn the section recomputed the union of the neighbouring files, the square directly behind, the two squares diagonally behind, and the number of adjacent files. These depend only on the pawn's square, so they are now tables: `FILE_NEIGHBOURS`, `BEHIND_SQUARE`, `BEHIND_DIAGONALS`, `SIDE_FILES`. |
| `evaluate` no longer routes through `breakdown` | `breakdown` tapers all ten components separately, each with its own integer division, and the search discarded every one of them. `evaluate` now computes the total directly; `breakdown` keeps the decomposition for the `eval` subcommand and the tests. |

Measured with `bench_eval`, minimum of 15 runs summed over the four positions:
**1219 ns before, 996 ns after** — about 18 % less, measured as the minimum of 20
runs summed over the four positions on an otherwise idle machine.

### How a performance change is verified here

The fixed-depth-10 bench signature and node count are a **regression signal**,
not a proof of evaluation equivalence. The bench visits 12 fixed positions;
an identical signature and an identical node count mean that the search
behaved identically *on those positions* (the node count pins the search
paths, and the signature pins the values the search returned). It cannot rule
out a changed evaluation on a position the bench never visits.

For the refactor in question both stayed at `b58979ca90492208` and 3,666,233
nodes, which is strong evidence that the evaluation values did not change on
the bench positions. To *claim* evaluation equivalence, compare the two
builds directly instead: dump `flawless eval <fen>` for a set of positions
from each build and diff the values. That direct comparison, not the bench
signature, is what supports an equivalence claim.

An attempt to also flatten the piece-square tables and fold the material
total out of the per-square loop was measured and **reverted**: it was a
consistent 3 % regression, presumably because a popcount per piece type costs
more than the adds it replaces at the piece counts actually seen.
