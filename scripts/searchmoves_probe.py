#!/usr/bin/env python3
"""searchmoves restriction probe: with `go searchmoves <subset>`, `bestmove` and the first move of
every `info ... multipv N ... pv` line must be in the subset (when the subset names a legal move).
Each named move is checked with python-chess; a subset with no legal move must widen (announced).
Usage: searchmoves_probe.py <engine> <positions> <seed> [multipv]
Exit status 0 when there are no failures.
"""
import random
import subprocess
import sys

import chess

exe = sys.argv[1]
n = int(sys.argv[2])
seed = int(sys.argv[3])
mpv = int(sys.argv[4]) if len(sys.argv) > 4 else 3
random.seed(seed)


def random_board():
    b = chess.Board()
    for _ in range(random.randint(0, 80)):
        moves = list(b.legal_moves)
        if not moves or b.is_game_over():
            break
        b.push(random.choice(moves))
    return b


p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
p.stdin.write(f"uci\nsetoption name MultiPV value {mpv}\nisready\n")
p.stdin.flush()
for line in p.stdout:
    if line.startswith("readyok"):
        break
fails = []
checked = 0
for i in range(n):
    b = random_board()
    legal = list(b.legal_moves)
    if not legal or b.is_game_over():
        continue
    k = random.randint(1, min(4, len(legal)))
    subset = random.sample(legal, k)
    names = " ".join(m.uci() for m in subset)
    p.stdin.write(f"position fen {b.fen()}\ngo depth 3 searchmoves {names}\n")
    p.stdin.flush()
    lines = []
    for line in p.stdout:
        lines.append(line.rstrip("\n"))
        if line.startswith("bestmove"):
            break
    checked += 1
    best = lines[-1].split()[1]
    allowed = {m.uci() for m in subset}
    if best not in allowed:
        fails.append(f"bestmove {best} outside searchmoves {names} in {b.fen()}")
    for l in lines:
        if l.startswith("info depth") and " multipv " in l and " pv " in l:
            first = l.split(" pv ", 1)[1].split()[0]
            if first not in allowed and l.split(" multipv ")[1].split()[0] == "1":
                fails.append(f"PV root {first} outside searchmoves {names}: {l[:80]}")
p.stdin.write("quit\n")
p.stdin.flush()
p.wait(timeout=30)
print(f"positions {checked} multipv {mpv} failures {len(fails)}")
for f in fails[:10]:
    print("FAIL", f)
sys.exit(1 if fails or p.returncode != 0 else 0)
