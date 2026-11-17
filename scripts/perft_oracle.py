#!/usr/bin/env python3
"""perft_oracle.py — independent perft counts via python-chess (pinned 1.11.2).

Cross-checks the engine's `perft`/`divide` subcommands against a different
move-generation implementation (python-chess, GPL-3.0+, TEST-ONLY — never
linked into the engine). Usage:

    python3 scripts/perft_oracle.py <depth> [fen]
    python3 scripts/perft_oracle.py --check <depth> [fen]   # also runs the engine

Reference counts: Chess Programming Wiki "Perft Results" page.
"""
from __future__ import annotations

import subprocess
import sys

import chess


def perft(board: chess.Board, depth: int) -> int:
    if depth == 0:
        return 1
    if depth == 1:
        return board.legal_moves.count()
    total = 0
    for mv in board.legal_moves:
        board.push(mv)
        total += perft(board, depth - 1)
        board.pop()
    return total


def main() -> int:
    args = sys.argv[1:]
    run_engine = False
    if args and args[0] == "--check":
        run_engine = True
        args = args[1:]
    if not args:
        print(__doc__)
        return 2
    depth = int(args[0])
    fen = args[1] if len(args) > 1 else chess.STARTING_FEN
    board = chess.Board(fen)
    if not board.is_valid():
        print(f"invalid FEN: {fen}", file=sys.stderr)
        return 2
    nodes = perft(board, depth)
    print(f"oracle perft({depth}) = {nodes}  (python-chess {chess.__version__})")
    if run_engine:
        out = subprocess.run(
            ["./target/release/flawless", "perft", str(depth), fen],
            capture_output=True, text=True, check=True).stdout
        print(out.strip())
        if f"= {nodes} " not in out and f"= {nodes}\n" not in out and f"= {nodes}" not in out:
            print("MISMATCH between engine and oracle", file=sys.stderr)
            return 1
        print("MATCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
