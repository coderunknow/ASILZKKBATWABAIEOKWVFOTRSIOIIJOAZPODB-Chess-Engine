#!/usr/bin/env python3
"""search_sweep.py — search legality and crash sweep over random reachable positions.

Audit tool (test-only; python-chess is never linked into the engine). For each seed, plays random
legal games with python-chess, then for sampled positions (including check, stalemate-adjacent and
endgame positions) runs the engine through UCI with `go depth D`, and checks:
  * the engine exits cleanly (rc 0) after `quit`, with no panic text on stderr;
  * exactly one `bestmove` line per `go`, and it is a legal move (or 0000 only when no legal move);
  * the `info` score is finite (no overflowed score values).

Usage:
    FLAWLESS_ENGINE=./target/debug/flawless python3 scripts/search_sweep.py <seed> <positions> [depth]

Debug builds check arithmetic overflow, so run the sweep against a debug build as well.
"""
from __future__ import annotations

import os
import random
import re
import subprocess
import sys

import chess

ENGINE = os.environ.get("FLAWLESS_ENGINE", "./target/release/flawless")
SCORE = re.compile(r"score (cp|mate) (-?\d+)")


def search(fen: str, depth: int) -> tuple[list[str], int, str]:
    p = subprocess.Popen([ENGINE, "uci"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True)
    script = f"uci\nisready\nposition fen {fen}\ngo depth {depth}\n"
    out_lines: list[str] = []
    try:
        p.stdin.write(script)
        p.stdin.flush()
        while True:
            line = p.stdout.readline()
            if line == "":
                break
            out_lines.append(line.rstrip("\n"))
            if line.startswith("bestmove"):
                break
        p.stdin.write("quit\n")
        p.stdin.flush()
    except BrokenPipeError:
        pass
    try:
        rest, err = p.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        p.kill()
        rest, err = p.communicate()
        raise RuntimeError(f"engine did not exit after quit on {fen!r}")
    out_lines += [l for l in rest.splitlines()]
    return out_lines, p.returncode, err


def main() -> int:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    depth = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    rnd = random.Random(seed)
    checked = failures = 0
    for i in range(count):
        board = chess.Board()
        for _ in range(rnd.randint(0, 120)):
            if board.is_game_over(claim_draw=True):
                break
            board.push(rnd.choice(list(board.legal_moves)))
        fen = board.fen()
        legal = list(board.legal_moves)
        lines, rc, err = search(fen, depth)
        checked += 1
        problems = []
        if rc != 0:
            problems.append(f"rc={rc}")
        if "panicked" in err or "panic" in err.lower():
            problems.append("panic on stderr: " + err.strip().splitlines()[0][:120])
        bms = [l for l in lines if l.startswith("bestmove")]
        if len(bms) != 1:
            problems.append(f"{len(bms)} bestmove lines")
        elif legal:
            move = bms[0].split()[1]
            if move == "0000" or chess.Move.from_uci(move) not in legal:
                problems.append(f"illegal bestmove {move}")
        else:
            if bms and bms[0].split()[1] != "0000":
                problems.append(f"terminal position answered {bms[0]}")
        for l in lines:
            if l.startswith("info depth") and " score " in l:
                m = SCORE.search(l)
                if m and m.group(1) == "cp" and abs(int(m.group(2))) > 31_000:
                    problems.append(f"cp score out of range: {m.group(2)}")
                if m and m.group(1) == "mate" and abs(int(m.group(2))) > 1_000:
                    problems.append(f"mate distance out of range: {m.group(2)}")
        if problems:
            failures += 1
            print(f"FAIL seed={seed} #{i} fen={fen} :: " + "; ".join(problems))
    print(f"seed={seed} positions={checked} depth={depth} failures={failures}")
    print("RESULT PASS" if failures == 0 else "RESULT FAIL")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
