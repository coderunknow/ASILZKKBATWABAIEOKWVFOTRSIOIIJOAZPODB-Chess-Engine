#!/usr/bin/env python3
"""Clock sweep: random clocks, including increments larger than the clock (F-23).

For each sampled (time, increment, movestogo) the engine must answer within the usable clock:
the planned spend is `t - reserve`, where reserve = clamp(t/16, 300 ms, 8 s), plus a fixed
margin for process I/O. A violation means a move could flag on a real GUI clock.

Usage: clock_sweep_probe.py <engine> [cases] [seed]
Exit status 0 when no case exceeds its bound, 1 otherwise.
"""
import random
import subprocess
import sys
import time

MARGIN_MS = 60  # process start-up and I/O; generous for a loaded CI runner


def reserve_ms(t):
    return min(max(t // 16, 300), 8000)


def run_case(engine, t, inc, mtg, side_white):
    own = "wtime" if side_white else "btime"
    other = "btime" if side_white else "wtime"
    args = f"{own} {t} {other} {t} " + (f"winc {inc} binc {inc}" if inc else "")
    if mtg is not None:
        args += f" movestogo {mtg}"
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    if side_white:
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
    p = subprocess.Popen([engine], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    p.stdin.write(f"uci\nisready\nposition fen {fen}\n")
    p.stdin.flush()
    while True:
        line = p.stdout.readline()
        if not line or line.startswith("readyok"):
            break
    t0 = time.monotonic()
    p.stdin.write(f"go {args}\n")
    p.stdin.flush()
    bm = None
    for line in p.stdout:
        if line.startswith("bestmove"):
            bm = line.split()[1]
            break
    elapsed = (time.monotonic() - t0) * 1000.0
    try:
        p.stdin.write("quit\n")
        p.stdin.flush()
    except OSError:
        pass
    p.wait(timeout=30)
    return bm, elapsed, args


def main():
    engine = sys.argv[1]
    cases = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    rng = random.Random(seed)
    failures = 0
    for i in range(cases):
        t = rng.choice([200, 400, 900, 1500, 3000, 6000])
        inc = rng.choice([0, 0, 50, t // 2, t, 2 * t])
        mtg = rng.choice([None, None, 1, 2, 40])
        side_white = rng.random() < 0.5
        bm, elapsed, args = run_case(engine, t, inc, mtg, side_white)
        bound = max(t - reserve_ms(t), 20) + MARGIN_MS
        ok = bm is not None and bm != "0000" and elapsed <= bound
        if not ok:
            failures += 1
        print(f"{'PASS' if ok else 'FAIL'} t={t:5d} inc={inc:5d} mtg={str(mtg):4s} "
              f"elapsed={elapsed:8.1f} ms bound={bound:6d} ms bestmove={bm} [{args}]")
    print(f"{cases - failures}/{cases} cases within the usable clock; failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
