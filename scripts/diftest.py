#!/usr/bin/env python3
"""Differential test: engine legal move generation vs python-chess (pinned oracle).

Generates random games with a fixed seed, collects positions along them, and compares
the exact legal move set at each position. Optionally deep-checks with perft.

Usage:
  python3 scripts/diftest.py [--games 300] [--seed 1234] [--perft-every 25] [--perft-depth 2] [--binary PATH]
"""
import argparse
import random
import subprocess
import sys
import time

import chess

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
DEFAULT_BIN = REPO_ROOT / "target" / "release" / "flawless"
START_FEN = chess.STARTING_FEN


def gen_positions(games: int, seed: int):
    rng = random.Random(seed)
    fens = []
    move_applied = 0
    for _ in range(games):
        board = chess.Board()
        for _ in range(200):
            fens.append(board.fen())
            move = rng.choice(list(board.legal_moves)) if not board.is_game_over() else None
            if move is None:
                break
            board.push(move)
            move_applied += 1
    return fens, move_applied


def engine_moves(fens, binary):
    inp = "\n".join(fens) + "\n"
    out = subprocess.run([str(binary), "moves"], input=inp, text=True,
                         capture_output=True, timeout=600)
    if out.returncode != 0:
        print("engine exited with", out.returncode, out.stderr, file=sys.stderr)
        sys.exit(2)
    results = {}
    for line in out.stdout.splitlines():
        if not line.startswith("ok "):
            continue
        # "ok <count> <uci ...>"; the FENs contain no "ok " prefix so we key by line order below
        parts = line.split(" ", 2)
        count = int(parts[1])
        moves = parts[2].split() if len(parts) > 2 else []
        results.setdefault("rows", []).append((count, moves))
    return results.get("rows", [])


def py_perft(board, depth):
    if depth == 0:
        return 1
    if depth == 1:
        return board.legal_moves.count()
    nodes = 0
    for m in board.legal_moves:
        board.push(m)
        nodes += py_perft(board, depth - 1)
        board.pop()
    return nodes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--perft-every", type=int, default=25, help="perft-check every Nth position (0=never)")
    ap.add_argument("--perft-depth", type=int, default=2)
    ap.add_argument("--binary", default=str(DEFAULT_BIN))
    args = ap.parse_args()

    t0 = time.time()
    fens, applied = gen_positions(args.games, args.seed)
    print(f"generated {len(fens)} positions from {args.games} random games ({applied} moves) in {time.time()-t0:.1f}s")

    t0 = time.time()
    rows = engine_moves(fens, args.binary)
    t1 = time.time()
    if len(rows) != len(fens):
        print(f"FAIL: engine answered {len(rows)} rows for {len(fens)} fens", file=sys.stderr)
        sys.exit(2)
    print(f"engine answered {len(rows)} positions in {t1-t0:.1f}s")

    mismatches = 0
    checked = 0
    for fen, (count, moves) in zip(fens, rows):
        board = chess.Board(fen)
        expected = sorted(m.uci() for m in board.legal_moves)
        got = sorted(moves)
        checked += 1
        if got != expected:
            mismatches += 1
            if mismatches <= 5:
                only_got = sorted(set(got) - set(expected))
                only_exp = sorted(set(expected) - set(got))
                print(f"MISMATCH fen={fen}\n  engine-only={only_got}\n  oracle-only={only_exp}")
    print(f"movegen comparison: {checked} positions, {mismatches} mismatches")

    perft_checked = 0
    perft_mismatch = 0
    if args.perft_every and args.perft_depth > 0:
        idxs = list(range(0, len(fens), args.perft_every))
        for i, j in enumerate(idxs):
            if i % 50 == 0:
                print(f"  perft progress {i}/{len(idxs)}")
            fen = fens[j]
            board = chess.Board(fen)
            exp = py_perft(board, args.perft_depth)
            out = subprocess.run([args.binary, "perft", str(args.perft_depth), fen],
                                 capture_output=True, text=True, timeout=120)
            if out.returncode != 0:
                print(f"perft failed for {fen}: {out.stderr}")
                perft_mismatch += 1
                continue
            # output: "perft(d) = N  (...)"
            got = int(out.stdout.split("=")[1].split()[0])
            perft_checked += 1
            if got != exp:
                perft_mismatch += 1
                print(f"PERFT MISMATCH fen={fen} depth={args.perft_depth} engine={got} oracle={exp}")
        print(f"perft comparison: {perft_checked} positions d={args.perft_depth}, {perft_mismatch} mismatches")

    if mismatches or perft_mismatch:
        print("DIFTEST FAILED")
        sys.exit(1)
    print("DIFTEST PASSED")


if __name__ == "__main__":
    main()
