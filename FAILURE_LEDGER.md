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
