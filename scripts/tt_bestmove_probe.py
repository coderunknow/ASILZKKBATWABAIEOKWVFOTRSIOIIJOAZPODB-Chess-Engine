#!/usr/bin/env python3
"""TT stress probe: one engine process, a small hash, and many searches in sequence, so the table is
shared across positions and collisions occur. Every `bestmove` must be a legal move in python-chess,
and the first move of the deepest `info ... pv` line must equal `bestmove`. Random legal positions
from random games. Needs python-chess (pip install chess==1.11.2).

Usage: tt_bestmove_probe.py <engine> <positions> <depth> <seed> [hash_mb]
Exit status 0 when there are no failures.
"""
import random
import subprocess
import sys

import chess

exe = sys.argv[1]
n = int(sys.argv[2])
depth = int(sys.argv[3])
seed = int(sys.argv[4])
hash_mb = int(sys.argv[5]) if len(sys.argv) > 5 else 1
random.seed(seed)


def random_positions(count):
    out = []
    while len(out) < count:
        b = chess.Board()
        for _ in range(random.randint(4, 120)):
            moves = list(b.legal_moves)
            if not moves or b.is_game_over():
                break
            b.push(random.choice(moves))
        if not b.is_game_over():
            out.append(b.fen())
    return out


p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)


def send(line):
    p.stdin.write(line + "\n")
    p.stdin.flush()


def read_until_bestmove():
    lines = []
    for line in p.stdout:
        lines.append(line.rstrip("\n"))
        if line.startswith("bestmove"):
            return lines
    raise RuntimeError("engine closed stdout before bestmove")


send("uci")
for line in p.stdout:
    if line.startswith("uciok"):
        break
send(f"setoption name Hash value {hash_mb}")
send("isready")
for line in p.stdout:
    if line.startswith("readyok"):
        break

failures = 0
checked = 0
for fen in random_positions(n):
    board = chess.Board(fen)
    legal = {m.uci() for m in board.legal_moves}
    send(f"position fen {fen}")
    send(f"go depth {depth}")
    lines = read_until_bestmove()
    best = lines[-1].split()[1]
    deepest_pv = None
    for l in lines:
        if l.startswith("info") and " pv " in l:
            deepest_pv = l.split(" pv ", 1)[1].split()
    checked += 1
    if best not in legal:
        failures += 1
        print("ILLEGAL bestmove", best, "in", fen)
    elif deepest_pv and deepest_pv[0] != best:
        failures += 1
        print("PV/bestmove mismatch", best, deepest_pv[:3], "in", fen)
send("quit")
p.wait(timeout=30)
print("positions", checked, "hash_mb", hash_mb, "depth", depth, "failures", failures, "exit", p.returncode)
sys.exit(1 if failures or p.returncode != 0 else 0)
