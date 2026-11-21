#!/usr/bin/env python3
"""Clock-through-a-game probe: the engine plays both sides of a game with running clocks.

Each move is sent as `go wtime W btime B winc I binc I` (and `movestogo` when set). The probe measures
the wall time from the `go` line to `bestmove` and deducts it, adds the increment, and checks that the
side that just moved still has time left. A flag (clock below zero) fails the probe, as does an
illegal move. Only the GUI-visible contract is checked: the engine, the clocks, and the legality of each
move (python-chess). Requires python-chess.

Usage: selfplay_clock_probe.py <engine> <base_ms> <inc_ms> [plies] [movestogo]
Exit status 0 when no clock flags and no illegal moves.
"""
import subprocess
import sys
import time

import chess

exe = sys.argv[1]
base = int(sys.argv[2])
inc = int(sys.argv[3])
plies = int(sys.argv[4]) if len(sys.argv) > 4 else 150
mtg = int(sys.argv[5]) if len(sys.argv) > 5 else None

p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
p.stdin.write("uci\nisready\n")
p.stdin.flush()
for line in p.stdout:
    if line.startswith("readyok"):
        break

board = chess.Board()
clock = {chess.WHITE: base, chess.BLACK: base}
min_left = {chess.WHITE: base, chess.BLACK: base}
total_think = 0
failures = []
p.stdin.write("ucinewgame\n")
for ply in range(plies):
    if board.is_game_over():
        break
    side = board.turn
    cmd = f"position fen {board.fen()}\ngo wtime {clock[chess.WHITE]} btime {clock[chess.BLACK]} winc {inc} binc {inc}"
    if mtg:
        cmd += f" movestogo {mtg}"
    t0 = time.monotonic()
    p.stdin.write(cmd + "\n")
    p.stdin.flush()
    best = None
    for line in p.stdout:
        if line.startswith("bestmove"):
            best = line.split()[1]
            break
    spent = (time.monotonic() - t0) * 1000.0
    total_think += spent
    if best is None:
        failures.append(f"ply {ply}: no bestmove")
        break
    if best == "0000" or chess.Move.from_uci(best) not in board.legal_moves:
        failures.append(f"ply {ply}: illegal bestmove {best} in {board.fen()}")
        break
    clock[side] -= int(spent)
    clock[side] += inc
    min_left[side] = min(min_left[side], clock[side])
    if clock[side] <= 0:
        failures.append(f"ply {ply}: {'white' if side else 'black'} flagged ({clock[side]} ms)")
        break
    board.push(chess.Move.from_uci(best))

p.stdin.write("quit\n")
p.stdin.flush()
p.wait(timeout=30)
print(f"plies {ply + 1} base {base} inc {inc} mtg {mtg} think {total_think / 1000:.2f}s "
      f"left W {clock[chess.WHITE]} B {clock[chess.BLACK]} min W {min_left[chess.WHITE]} min B {min_left[chess.BLACK]} "
      f"failures {len(failures)}")
for f in failures:
    print("FAIL", f)
sys.exit(1 if failures or p.returncode != 0 else 0)
