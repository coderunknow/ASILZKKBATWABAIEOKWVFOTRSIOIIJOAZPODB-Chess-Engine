# RESEARCH_ROADMAP.md

## Long-term ambition (not a promise)

Reach sustainable **> 3500 Elo** on a named, credible scale (CCRL 40/15 as primary reference).
This requires: top-tier search, NNUE-class evaluation trained on large high-quality data, and many
months of compute — all currently out of reach of this sandbox. We build the *path*, measure honestly,
and never claim the milestone without a qualifying measurement.

## Phase plan toward strength

1. **Foundation correctness** (V1 hard gate): perft + differential + UCI robustness. *(Now)*
2. **Classical baseline**: ID + AB + TT + quiescence + ordering + null move + LMR. Validate each feature
   with preregistered fixed-node + fixed-time experiments. Target: competitive club-strength core.
3. **Evaluation quality**: tapered classical eval with pawn structure, king safety, mobility.
   Texel-style tuning of eval terms (self-play + game database where license permits).
4. **Bench & puzzles**: fixed-node regression suite; tactical suite (WAC-like) for pruning-bug detection.
5. **Match infrastructure**: pinned pool (Stockfish WASM pinned from npm as *opponent only*, plus
   self-play null controls); paired openings; opening-clustered CIs.
6. **NNUE stage (only after classical baseline is stable)**: small (256×2) → larger nets; training data
   from self-play + (if license-compatible) open datasets; Stockfish as *teacher* (positions/evals only —
   permitted role; never code, never weights). NNUE activated only after reproducible strength win.
7. **Scaling**: search features (SEE-based pruning, history-based move ordering variants, countermove,
   probcut, singular extensions) with ablation each; eval terms with Texel tuning; eventually SPSA.
8. **Rating evidence**: continuous measurement vs pinned anchors; ≥2 confirmation batches; publish CIs;
   escalate CCRL submission only via official channels and conditions.

## Known gaps vs 3,500 Elo path

- NNUE architecture + data pipeline (months of compute).
- SMP + large search tuning.
- Endgame tablebase integration.
- Human-knowledge refinements (contempt, fortress handling).

## Tracking

Each milestone recorded in `STATUS.md` with measured strength, uncertainty, and failed attempts in
`FAILURE_LEDGER.md`.
