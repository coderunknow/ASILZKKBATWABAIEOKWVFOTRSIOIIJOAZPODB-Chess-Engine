#!/usr/bin/env python3
"""Malformed-input robustness probe: the engine must not panic, hang, or print non-UCI text.

Each case is one interactive session: send the hostile line, then `isready`, expect `readyok`
within a bounded time, then `quit` (exit 0). A panic shows up as a non-zero exit or a
'panicked' message on stderr. Usage: python3 scripts/uci_malformed_probe.py <exe>
"""
import subprocess, sys, time

EXE = sys.argv[1]
CASES = [
    "position fen",
    "position fen not/a/valid/fen w - - 0 1",
    "position fen 8/8/8/8/8/8/8/8 w - - 0 1",
    "position fen rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 99999999999999999999 1",
    "position fen 4k3/8/8/8/8/8/8/4K3 w - - 0 99999999999999999999",
    "position startpos moves e2e5",
    "position startpos moves e2e4 e2e4 zzzz",
    "position startpos moves",
    "position",
    "go depth 99999999999999999999",
    "go depth 0",
    "go depth -3",
    "go movetime 99999999999999999999",
    "go movetime -5",
    "go wtime -5 btime -5 winc 99999999999999 binc 0",
    "go wtime 0 btime 0",
    "go nodes 0",
    "go nodes 18446744073709551615 movetime 50",
    "go searchmoves zzzz",
    "go movestogo 0 wtime 1000 btime 1000",
    "setoption",
    "setoption name",
    "setoption name Hash value",
    "setoption name Hash value -1",
    "setoption name Hash value 99999999999999",
    "setoption name MultiPV value 0",
    "setoption name MultiPV value 300",
    "setoption name Threads value 0",
    "debug on",
    "debug off",
    "ucinewgame ucinewgame",
    "stop",
    "ponderhit",
    "",
    "   ",
    "\x00\x01\x02",
    "é" * 50,
]

def run(line):
    p = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(input=(f"uci\n{line}\nisready\nquit\n").encode("utf-8", "replace"), timeout=20)
    except subprocess.TimeoutExpired:
        p.kill(); return "HANG", "", ""
    out = out.decode("utf-8", "replace"); err = err.decode("utf-8", "replace")
    if p.returncode != 0:
        return f"EXIT {p.returncode}", out, err
    if "panicked" in err.lower() or "panic" in err.lower():
        return "PANIC", out, err
    if "readyok" not in out:
        return "NO_READYOK", out, err
    bad = [l for l in out.splitlines() if l and not l.startswith(("id ", "option ", "uciok", "readyok", "info ", "bestmove "))]
    if bad:
        return f"NON_UCI_STDOUT {bad[:2]}", out, err
    return "OK", out, err

fails = 0
for c in CASES:
    t = time.monotonic()
    status, out, err = run(c)
    dt = time.monotonic() - t
    flag = "" if status == "OK" else "  <-- "
    if status != "OK": fails += 1
    print(f"{status:24s} {dt:5.2f}s  {c[:70]!r}{flag}")
    if status not in ("OK",) and err.strip():
        print("      stderr:", err.strip().splitlines()[0][:160])
print(f"{len(CASES)-fails}/{len(CASES)} OK")
sys.exit(1 if fails else 0)
