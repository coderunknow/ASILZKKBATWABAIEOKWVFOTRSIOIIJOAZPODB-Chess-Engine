# FAILURE_LEDGER.md (append-only)

No failures recorded yet. Entries must include: what was attempted, why, exact commit/binary,
conditions, raw evidence location, result + uncertainty, suspected mechanism (labeled as hypothesis),
what was learned, next experiment.

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
