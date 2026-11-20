#!/usr/bin/env python3
"""Malformed-input robustness probe: the engine must not panic, hang, or print non-UCI text.

Each case is one interactive session: send the hostile line, then `isready`, expect `readyok`
within a bounded time, then `quit` (exit 0). A panic shows up as a non-zero exit or a
'panicked' message on stderr. Usage: python3 scripts/uci_malformed_probe.py <exe>
"""
import queue, subprocess, sys, threading, time

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
    """One interactive session. `go` lines are followed by a wait for `bestmove` (bounded)
    before `quit`; sending `go` and `quit` in one burst lets quit stop the search at depth 0,
    which would hide a missing or illegal bestmove."""
    p = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out_lines, err_chunks = [], []
    threading.Thread(target=lambda: err_chunks.append(p.stderr.read()), daemon=True).start()
    q = queue.Queue()
    def reader():
        for raw in iter(p.stdout.readline, b""):
            q.put(raw.decode("utf-8", "replace").rstrip("\r\n"))
        q.put(None)
    threading.Thread(target=reader, daemon=True).start()

    def send(s):
        p.stdin.write((s + "\n").encode("utf-8", "replace")); p.stdin.flush()

    def until(pred, timeout):
        end = time.monotonic() + timeout
        while True:
            r = end - time.monotonic()
            if r <= 0:
                return None
            try:
                l = q.get(timeout=min(r, 0.2))
            except queue.Empty:
                continue
            if l is None:
                return None
            out_lines.append(l)
            if pred(l):
                return l

    def finish(status):
        err = b"".join(err_chunks).decode("utf-8", "replace") if err_chunks else ""
        return status, "\n".join(out_lines), err

    try:
        send("uci")
        if until(lambda l: l == "uciok", 10) is None:
            p.kill(); return finish("NO_UCIOK")
        send(line)
        is_go = line.split()[:1] == ["go"]
        if is_go:
            send("isready")
            if until(lambda l: l == "readyok", 10) is None:
                p.kill(); return finish("EOF_BEFORE_READYOK")
            # A search with no effective limit (an unparseable depth/movetime/searchmoves is
            # treated as absent) runs until `stop`. Give limited searches 2 s to answer on their
            # own; otherwise send `stop` and require the bestmove afterwards.
            got = until(lambda l: l.startswith("bestmove"), 2)
            stopped = False
            if got is None:
                send("stop")
                stopped = True
                got = until(lambda l: l.startswith("bestmove"), 15)
            if got is None:
                p.kill(); return finish("NO_BESTMOVE")
            if stopped:
                out_lines.append("# probe-note: unlimited search ended by stop")
            if got.split()[1:2] == []:
                p.kill(); return finish("EMPTY_BESTMOVE")
        send("isready")
        if until(lambda l: l == "readyok", 10) is None:
            p.kill(); return finish("NO_READYOK")
        send("quit")
        try:
            code = p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill(); return finish("HANG")
    finally:
        if p.poll() is None:
            p.kill()
    status, out, err = finish("OK")
    if code != 0:
        return f"EXIT {code}", out, err
    if "panic" in err.lower():
        return "PANIC", out, err
    bad = [l for l in out.splitlines() if l and not l.startswith(("id ", "option ", "uciok", "readyok", "info ", "bestmove ", "# probe-note"))]
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
