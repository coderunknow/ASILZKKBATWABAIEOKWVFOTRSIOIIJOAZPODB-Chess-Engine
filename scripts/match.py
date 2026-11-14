#!/usr/bin/env python3
"""Match runner: play UCI games between two engines, record raw evidence.

Every game is stored as PGN + a JSONL record line with full config, so any batch
is reproducible and auditable. No ratings are computed here (see stats.py).

Usage example:
  python3 scripts/match.py --white-cmd "./target/release/flawless uci" \
      --black-cmd "node /path/to/stockfish-19-lite-single.js" \
      --movetime 100 --openings openings.txt --out benches/<id> [--games 20]
"""
import argparse
import hashlib
import json
import os
import select
import subprocess
import sys
import time
from dataclasses import dataclass

import chess
import chess.pgn


class EngineExited(RuntimeError):
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class EngineSpec:
    name: str
    cmd: list[str]


class UciEngine:
    def __init__(self, spec: EngineSpec, hash_mb: int | None = None, skill: int | None = None):
        self.spec = spec
        self.proc = subprocess.Popen(
            spec.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        self.engine_error_events: list[str] = []
        self._buf = b""
        self._send("uci")
        self._wait_for("uciok", timeout=60.0)
        if hash_mb is not None:
            self._send(f"setoption name Hash value {hash_mb}")
        if skill is not None:
            self._send(f"setoption name Skill Level value {skill}")
        self._send("isready")
        self._wait_for("readyok", timeout=60.0)

    def _send(self, s: str) -> None:
        assert self.proc.stdin is not None
        try:
            self.proc.stdin.write((s + "\n").encode())
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            # Engine died (or its stdin closed) — surface as EngineExited so the game
            # loop records an engine-error loss instead of crashing the whole batch.
            raise EngineExited(f"engine {self.spec.name}: pipe broken while sending {s!r}: {e}") from e

    def _readline(self, timeout: float) -> bytes:
        # Line reassembly from raw chunks: select() only promises *some* bytes, never a
        # complete line — readline() after a readable select() could block forever on a
        # partial line, so we do the split ourselves under a hard deadline.
        assert self.proc.stdout is not None
        fd = self.proc.stdout.fileno()
        deadline = time.time() + timeout
        while True:
            idx = self._buf.find(b"\n")
            if idx != -1:
                line, self._buf = self._buf[: idx + 1], self._buf[idx + 1 :]
                return line
            remaining = deadline - time.time()
            if remaining <= 0:
                raise TimeoutError(f"engine {self.spec.name}: no complete line for {timeout}s")
            r, _, _ = select.select([fd], [], [], remaining)
            if not r:
                raise TimeoutError(f"engine {self.spec.name}: no output for {timeout}s")
            chunk = os.read(fd, 65536)
            if not chunk:
                raise EngineExited(f"engine {self.spec.name} exited (stdout EOF, code {self.proc.poll()})")
            self._buf += chunk

    def _wait_for(self, token: str, timeout: float) -> None:
        t0 = time.time()
        while time.time() - t0 < timeout:
            line = self._readline(max(0.1, timeout - (time.time() - t0))).decode(errors="replace")
            if line.strip().startswith(token):
                return
        raise TimeoutError(f"engine {self.spec.name}: expected {token}")

    def set_position(self, board: chess.Board) -> None:
        # Full move history from the initial position (openings included) so the engine's
        # repetition detection has the whole game context — FEN alone hides prior occurrences.
        moves = " ".join(m.uci() for m in board.move_stack)
        if moves:
            self._send(f"position startpos moves {moves}")
        else:
            self._send("position startpos")

    def go(self, movetime_ms: int | None = None, depth: int | None = None) -> str:
        args = ["go"]
        if movetime_ms is not None:
            args += ["movetime", str(movetime_ms)]
        if depth is not None:
            args += ["depth", str(depth)]
        self._send(" ".join(args))
        while True:
            line = self._readline(300.0).decode(errors="replace").strip()
            if line.startswith("info string") and "panicked" in line:
                self.engine_error_events.append(line)
            if line.startswith("bestmove"):
                parts = line.split()
                return parts[1]

    def quit(self) -> None:
        try:
            self._send("quit")
            self.proc.wait(timeout=5.0)
        except Exception:
            self.proc.kill()


def file_sha256(path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def probe_artifact(cmd_line: str) -> dict:
    """Record which binary (sha256) actually produced a batch — probe archaeology."""
    first = cmd_line.split()[0] if cmd_line.split() else ""
    target = None
    if first and os.path.isfile(first):
        target = first
    else:
        which = os.path.join(os.getcwd(), first)
        if os.path.isfile(which):
            target = which
        else:
            import shutil

            which = shutil.which(first) if first else None
            if which:
                target = which
    return {"cmd": cmd_line, "binary_path": target, "sha256": file_sha256(target) if target else None}


def git_head() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def parse_opening_moves(text: str) -> list[str]:
    return text.split()


def load_openings(path: str) -> list[tuple[str, list[str]]]:
    """Each line: name|moves (space-separated UCI)."""
    out = []
    with open(path) as f:
        for raw in f:
            raw = raw.strip()
            if not raw or raw.startswith("#"):
                continue
            name, moves = raw.split("|", 1)
            out.append((name.strip(), parse_opening_moves(moves.strip())))
    return out


def apply_opening(board: chess.Board, moves: list[str]) -> None:
    for uci in moves:
        move = chess.Move.from_uci(uci)
        assert move in board.legal_moves, f"opening move illegal: {uci} in {board.fen()}"
        board.push(move)


def adjudicate(board: chess.Board) -> tuple[str, str] | None:
    """Returns (result, reason) if the game is over, else None."""
    outcome = board.outcome(claim_draw=True)
    if outcome is not None:
        if outcome.winner is None:
            return "1/2-1/2", outcome.termination.name.lower()
        return ("1-0" if outcome.winner == chess.WHITE else "0-1"), outcome.termination.name.lower()
    return None


def harvest_engine_errors(mover: UciEngine, plies: int, turns: list[int]) -> None:
    """Move any buffered panic-fallback markers from the mover into the turns list."""
    if mover.engine_error_events:
        turns.append(plies)
        mover.engine_error_events = []


def play_game(
    white: UciEngine,
    black: UciEngine,
    opening: tuple[str, list[str]],
    movetime_ms: int | None,
    depth: int | None,
    white_name: str,
    black_name: str,
    max_moves: int = 300,
) -> dict:
    oname, omoves = opening
    board = chess.Board()
    apply_opening(board, omoves)
    move_count = len(board.move_stack)
    engine_error_turns: list[int] = []

    while True:
        if board.is_game_over(claim_draw=True):
            break
        if board.fullmove_number > max_moves:
            break
        mover = white if board.turn == chess.WHITE else black
        t0 = time.time()
        try:
            mover.set_position(board)
            move_uci = mover.go(movetime_ms=movetime_ms, depth=depth)
        except EngineExited:
            harvest_engine_errors(mover, len(board.move_stack) + 1, engine_error_turns)
            loser = "white" if board.turn == chess.WHITE else "black"
            return {
                "opening": oname,
                "white": white_name,
                "black": black_name,
                "result": "1-0" if loser == "black" else "0-1",
                "reason": "engine_exited",
                "moves": [m.uci() for m in board.move_stack],
                "fen": board.fen(),
                "move_count": len(board.move_stack),
                "engine_error": True,
                "engine_error_turns": engine_error_turns,
            }
        except TimeoutError:
            harvest_engine_errors(mover, len(board.move_stack) + 1, engine_error_turns)
            # engine failed to move in time -> loss on time/forfeit
            loser = "white" if board.turn == chess.WHITE else "black"
            return {
                "opening": oname,
                "white": white_name,
                "black": black_name,
                "result": "1-0" if loser == "black" else "0-1",
                "reason": "timeout_forfeit",
                "moves": [m.uci() for m in board.move_stack],
                "fen": board.fen(),
                "move_count": len(board.move_stack),
                "engine_error": True,
                "engine_error_turns": engine_error_turns,
            }
        dt = time.time() - t0
        try:
            move = chess.Move.from_uci(move_uci)
            if move not in board.legal_moves:
                harvest_engine_errors(mover, len(board.move_stack) + 1, engine_error_turns)
                return {
                    "opening": oname,
                    "white": white_name,
                    "black": black_name,
                    "result": "1-0" if board.turn == chess.BLACK else "0-1",
                    "reason": "illegal_move",
                    "moves": [m.uci() for m in board.move_stack],
                    "fen": board.fen(),
                    "move_count": len(board.move_stack),
                    "engine_error": True,
                    "engine_error_turns": engine_error_turns,
                }
        except ValueError:
            harvest_engine_errors(mover, len(board.move_stack) + 1, engine_error_turns)
            return {
                "opening": oname,
                "white": white_name,
                "black": black_name,
                "result": "1-0" if board.turn == chess.BLACK else "0-1",
                "reason": "unparseable_move",
                "moves": [m.uci() for m in board.move_stack],
                "fen": board.fen(),
                "move_count": len(board.move_stack),
                "engine_error": True,
                "engine_error_turns": engine_error_turns,
            }
        board.push(move)
        harvest_engine_errors(mover, len(board.move_stack), engine_error_turns)
        if dt > 30:
            sys.stderr.write(f"slow move {move_uci} ({dt:.1f}s)\n")

    end = adjudicate(board) or ("1/2-1/2", "move_cap")
    return {
        "opening": oname,
        "white": white_name,
        "black": black_name,
        "result": end[0],
        "reason": end[1],
        "moves": [m.uci() for m in board.move_stack],
        "fen": board.fen(),
        "move_count": len(board.move_stack),
        "engine_error": bool(engine_error_turns),
        "engine_error_turns": engine_error_turns,
    }


def color_pair_games(n: int) -> list[str]:
    """Alternate white/black assignment for each game index."""
    return ["AB" if i % 2 == 0 else "BA" for i in range(n)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--white-cmd", required=True)
    ap.add_argument("--black-cmd", required=True)
    ap.add_argument("--white-name", default="engine-white")
    ap.add_argument("--black-name", default="engine-black")
    ap.add_argument("--openings", required=True, help="file with 'name|moves' lines")
    ap.add_argument("--out", required=True, help="output directory (created)")
    ap.add_argument("--movetime", type=int, default=None, help="ms per move (fixed)")
    ap.add_argument("--depth", type=int, default=None, help="fixed search depth (overrides movetime)")
    ap.add_argument("--games", type=int, default=None, help="cap number of games")
    ap.add_argument("--hash", type=int, default=None)
    ap.add_argument("--skill-white", type=int, default=None)
    ap.add_argument("--skill-black", type=int, default=None)
    ap.add_argument("--max-moves", type=int, default=300)
    args = ap.parse_args()

    openings = load_openings(args.openings)
    os.makedirs(args.out, exist_ok=True)
    # Single overwrite policy for ALL batch artifacts (games.pgn used to append while
    # games.jsonl/meta.json truncated): refuse to touch a previously-written batch.
    for name in ("games.pgn", "games.jsonl", "meta.json"):
        p = os.path.join(args.out, name)
        if os.path.exists(p) and os.path.getsize(p) > 0:
            ap.error(f"output artifact exists: {p} — choose a fresh --out directory (refusing to overwrite a batch)")

    pairs = [(o, p) for o in openings for p in ("AB", "BA")]
    if args.games is not None:
        pairs = pairs[: args.games]

    white = UciEngine(EngineSpec(args.white_name, args.white_cmd.split()), hash_mb=args.hash, skill=args.skill_white)
    black = UciEngine(EngineSpec(args.black_name, args.black_cmd.split()), hash_mb=args.hash, skill=args.skill_black)

    pgn_path = os.path.join(args.out, "games.pgn")
    jsonl_path = os.path.join(args.out, "games.jsonl")
    meta = {
        "white_cmd": args.white_cmd,
        "black_cmd": args.black_cmd,
        "white_name": args.white_name,
        "black_name": args.black_name,
        "movetime_ms": args.movetime,
        "depth": args.depth,
        "hash_mb": args.hash,
        "skill_white": args.skill_white,
        "skill_black": args.skill_black,
        "openings_file": os.path.abspath(args.openings),
        "n_games_planned": len(pairs),
        "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # Probe archaeology: which exact binaries produced this batch, and which commit.
        "white_artifact": probe_artifact(args.white_cmd),
        "black_artifact": probe_artifact(args.black_cmd),
        "git_commit": git_head(),
    }
    with open(jsonl_path, "w") as jf, open(pgn_path, "w") as pgn, open(os.path.join(args.out, "meta.json"), "w") as mf:
        json.dump(meta, mf, indent=2)
        for idx, (opening, pair) in enumerate(pairs, 1):
            if pair == "AB":
                w_spec, b_spec = white, black
                wname, bname = args.white_name, args.black_name
                w_skill, b_skill = args.skill_white, args.skill_black
            else:
                w_spec, b_spec = black, white
                wname, bname = args.black_name, args.white_name
                w_skill, b_skill = args.skill_black, args.skill_white
            w = UciEngine(w_spec.spec, hash_mb=args.hash, skill=w_skill)
            b = UciEngine(b_spec.spec, hash_mb=args.hash, skill=b_skill)
            t0 = time.time()
            try:
                result = play_game(w, b, opening, args.movetime, args.depth, wname, bname, args.max_moves)
            finally:
                w.quit()
                b.quit()
            result["wall_seconds"] = round(time.time() - t0, 3)
            result["color_pair"] = pair
            result["game_index"] = idx
            jf.write(json.dumps(result) + "\n")
            jf.flush()

            game = chess.pgn.Game()
            game.headers["Event"] = "benchmark match"
            game.headers["Site"] = "local"
            game.headers["Date"] = time.strftime("%Y.%m.%d", time.gmtime())
            game.headers["Round"] = str(idx)
            game.headers["White"] = wname
            game.headers["Black"] = bname
            game.headers["Opening"] = opening[0]
            game.headers["Result"] = result["result"]
            board = chess.Board()
            apply_opening(board, opening[1])
            node = game
            for uci in opening[1]:
                mv = chess.Move.from_uci(uci)
                node = node.add_variation(mv)
            for uci in result["moves"][len(opening[1]):]:
                mv = chess.Move.from_uci(uci)
                node = node.add_variation(mv)
            game.headers["Result"] = result["result"]
            pgn.write(str(game) + "\n\n")
            pgn.flush()
            print(
                f"[game {idx:3d}/{len(pairs)}] {opening[0]:<28} {wname} vs {bname} -> {result['result']} ({result['reason']})"
            )

    white.quit()
    black.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
