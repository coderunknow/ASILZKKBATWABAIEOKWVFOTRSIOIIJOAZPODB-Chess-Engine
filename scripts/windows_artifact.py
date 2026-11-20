#!/usr/bin/env python3
"""Stage, verify and describe the Windows x64 release executable for CI.

Used by .github/workflows/ci.yml (job `windows-x64-artifact`). It is deliberately
strict: every check either passes or the script exits non-zero, so a broken or
mis-targeted executable can never be packaged silently.

Steps (in order):
  1. Confirm the executable exists, is non-empty, and is a PE file whose COFF
     machine type is 0x8664 (x86-64). A Linux ELF or a 32-bit build fails here.
  2. Smoke-test the exact file: zero-argument UCI startup (handshake, isready,
     position startpos, go depth 2 -> legal bestmove, quit -> exit 0), explicit
     `uci` startup, `perft 3` = 8902, `--help` (exit 0), unknown command (exit 2).
  3. Copy the executable into the output directory as `flawless.exe`.
  4. Write SHA256SUMS.txt and BUILD-MANIFEST.txt, then re-verify the checksum of
     the staged copy against the manifest.

Standard library only (no third-party dependencies).
"""

import argparse
import datetime
import hashlib
import os
import queue
import re
import shutil
import struct
import subprocess
import sys
import threading

EXE_NAME = "flawless.exe"
EXPECTED_MACHINE = 0x8664  # IMAGE_FILE_MACHINE_AMD64
EXPECTED_TARGET = "x86_64-pc-windows-msvc"
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
SMOKE_TIMEOUT = 120  # seconds, per child process
# Group 1 is the selected move. An optional " ponder <move>" suffix is valid UCI.
BESTMOVE_RE = re.compile(
    r"^bestmove ([a-h][1-8][a-h][1-8][qrbn]?)(?: ponder [a-h][1-8][a-h][1-8][qrbn]?)?$"
)


class CheckError(Exception):
    pass


def fail(msg):
    raise CheckError(msg)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pe_machine(path):
    """Return the COFF machine field of a PE file, validating the headers."""
    with open(path, "rb") as f:
        head = f.read(4096)
    if len(head) < 0x40 or head[:2] != b"MZ":
        fail(f"{path} is not a PE file (missing MZ header)")
    (e_lfanew,) = struct.unpack_from("<I", head, 0x3C)
    if e_lfanew + 6 > len(head):
        with open(path, "rb") as f:
            f.seek(e_lfanew)
            head = f.read(64)
        e_lfanew = 0
    sig = head[e_lfanew : e_lfanew + 4]
    if sig != b"PE\x00\x00":
        fail(f"{path} has no PE\\0\\0 signature at offset {e_lfanew:#x}")
    (machine,) = struct.unpack_from("<H", head, e_lfanew + 4)
    return machine


def run_engine(exe, args, stdin_text):
    """Run the engine to completion with a bounded wait; return (code, stdout, stderr).

    Only for commands that exit by themselves (CLI subcommands). UCI sessions use
    Session below, because `quit` stops an in-flight search.
    """
    try:
        proc = subprocess.run(
            [exe] + args,
            input=stdin_text.encode("ascii"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=SMOKE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        fail(f"`{os.path.basename(exe)} {' '.join(args)}` did not exit within {SMOKE_TIMEOUT}s")
    except OSError as e:
        fail(f"could not execute {exe}: {e}")
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n"),
        proc.stderr.decode("utf-8", "replace").replace("\r\n", "\n"),
    )


class Session:
    """Interactive UCI session: write a command, then wait for its reply.

    A reader thread feeds stdout lines into a queue so every wait is bounded.
    The caller must send `quit` only after the search reply has been read,
    because `quit` stops an in-flight search.
    """

    def __init__(self, exe, args):
        try:
            self.proc = subprocess.Popen(
                [exe] + args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as e:
            fail(f"could not execute {exe}: {e}")
        self.lines = []
        self.q = queue.Queue()
        self.stderr_chunks = []
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self):
        for raw in iter(self.proc.stdout.readline, b""):
            self.q.put(raw.decode("utf-8", "replace").rstrip("\r\n"))
        self.q.put(None)  # EOF marker

    def _read_stderr(self):
        self.stderr_chunks.append(self.proc.stderr.read())

    def send(self, cmd):
        try:
            self.proc.stdin.write((cmd + "\n").encode("ascii"))
            self.proc.stdin.flush()
        except OSError as e:
            self.kill()
            fail(f"could not send {cmd!r} to engine: {e}")

    def read_until(self, pred, what):
        """Collect stdout lines until pred(line) is true; return all lines read."""
        import time

        deadline = time.monotonic() + SMOKE_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.kill()
                fail(f"timed out after {SMOKE_TIMEOUT}s waiting for {what}; stdout so far: {self.lines[-5:]}")
            try:
                line = self.q.get(timeout=min(remaining, 0.25))
            except queue.Empty:
                continue
            if line is None:
                fail(f"engine closed stdout while waiting for {what}; stdout: {self.lines[-5:]}")
            self.lines.append(line)
            if pred(line):
                return self.lines

    def finish(self):
        """Close stdin (EOF), wait for a clean exit, and drain all remaining stdout.

        Every stdout line written before exit is appended to self.lines, so checks that
        run afterwards see the complete transcript, including output after bestmove.
        """
        import time

        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            code = self.proc.wait(timeout=SMOKE_TIMEOUT)
        except subprocess.TimeoutExpired:
            self.kill()
            fail(f"engine did not exit within {SMOKE_TIMEOUT}s after quit/EOF")
        deadline = time.monotonic() + SMOKE_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                fail(f"stdout did not reach EOF within {SMOKE_TIMEOUT}s after exit")
            try:
                line = self.q.get(timeout=min(remaining, 0.25))
            except queue.Empty:
                continue
            if line is None:
                break
            self.lines.append(line)
        return code

    def kill(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()

    def stderr_text(self):
        return b"".join(self.stderr_chunks).decode("utf-8", "replace").replace("\r\n", "\n")


def check_uci_lines_only(label, lines):
    allowed = ("uciok", "readyok", "id ", "option name ", "info ", "bestmove ")
    for line in lines:
        if line == "":
            continue
        if not line.startswith(allowed):
            fail(f"{label}: non-UCI text on stdout: {line!r}")
        if "usage" in line:
            fail(f"{label}: usage banner leaked to stdout: {line!r}")


def uci_session_bestmove(exe, args, label):
    """Handshake, isready, position startpos, go depth 2, wait for bestmove, then quit.

    Returns (handshake_lines, bestmove_token, exit_code, all_lines). quit is sent only
    after the bestmove line has been read, so the search is complete when the engine is
    stopped. The search must also have reported a completed depth-2 iteration: a
    depth-0 fallback move (e.g. from a stop that arrived early) is rejected.
    """
    s = Session(exe, args)
    try:
        s.send("uci")
        hs = list(s.read_until(lambda l: l == "uciok", f"{label}: uciok"))  # snapshot
        s.send("isready")
        s.read_until(lambda l: l == "readyok", f"{label}: readyok")
        s.send("position startpos")
        s.send("isready")
        s.read_until(lambda l: l == "readyok", f"{label}: readyok after position")
        s.send("go depth 2")
        s.read_until(lambda l: l.startswith("bestmove"), f"{label}: bestmove")
        s.send("quit")
        code = s.finish()  # drains all stdout through EOF
    finally:
        s.kill()
    lines = s.lines
    check_uci_lines_only(label, lines)
    bestmoves = [m for m in (BESTMOVE_RE.match(l) for l in lines) if m]
    if len(bestmoves) != 1:
        fail(f"{label}: expected exactly one bestmove line, got {len(bestmoves)}")
    if not any(l.startswith("info depth 2 ") for l in lines):
        fail(f"{label}: no completed `info depth 2` line before bestmove; search did not reach depth 2")
    return hs, bestmoves[0].group(1), code, lines


def smoke_test(exe):
    """Exercise the exact executable. Returns a dict of evidence values."""
    evidence = {}

    # --- 1. zero-argument launch: the GUI shape (Process.start(path, [])) ---
    hs, bestmove, code, _ = uci_session_bestmove(exe, [], "no-argument launch")
    if code != 0:
        fail(f"no-argument session exited with {code}")
    if "id name Flawless" not in hs:
        fail("no-argument launch: missing `id name Flawless`")

    # Cross-check the bestmove against the engine's own legal-move generator.
    code_m, mv_out, _ = run_engine(exe, ["moves"], START_FEN + "\n")
    if code_m != 0 or not mv_out.startswith("ok "):
        fail(f"`moves` command failed: exit {code_m}, out={mv_out!r}")
    legal = mv_out.split()[2:]
    if bestmove not in legal:
        fail(f"bestmove {bestmove} is not legal from startpos (legal={legal})")
    evidence["no_args_bestmove"] = bestmove
    evidence["startpos_legal_moves"] = len(legal)

    # --- 2. explicit `uci` launch must match the zero-argument handshake ---
    hs2, bestmove2, code2, _ = uci_session_bestmove(exe, ["uci"], "explicit uci launch")
    if code2 != 0:
        fail(f"explicit `uci` session exited with {code2}")
    if hs != hs2:
        fail("handshake differs between no-argument and explicit `uci` launch")
    if bestmove2 not in legal:
        fail(f"explicit uci bestmove {bestmove2} is not legal from startpos")
    evidence["handshake_identical"] = True

    # --- 3. no commands at all: the process must wait, then exit 0 on EOF ---
    s = Session(exe, [])
    try:
        import time

        time.sleep(0.5)
        if s.proc.poll() is not None:
            fail(f"no-argument launch exited before receiving any command (code {s.proc.returncode})")
        code3 = s.finish()  # EOF: engine must exit 0; drains any stdout it wrote
    finally:
        s.kill()
    if s.lines:
        fail(f"no-argument launch wrote stdout before any command: {s.lines!r}")
    if code3 != 0:
        fail(f"no-argument launch: EOF exit code {code3}; stderr={s.stderr_text()!r}")

    # --- 4. existing CLI behaviour ---
    code4, out4, _ = run_engine(exe, ["perft", "3"], "")
    if code4 != 0 or "perft(3) = 8902" not in out4:
        fail(f"perft 3 mismatch: exit {code4}, out={out4!r}")
    evidence["perft3"] = "8902"

    code5, out5, _ = run_engine(exe, ["--help"], "")
    if code5 != 0 or "usage:" not in out5:
        fail(f"--help: exit {code5}, out={out5!r}")

    code6, out6, err6 = run_engine(exe, ["no-such-command"], "")
    if code6 != 2 or out6.strip():
        fail(f"unknown command: exit {code6} (want 2), stdout={out6!r}")
    if "unknown command" not in err6:
        fail(f"unknown command: stderr lacks diagnostic: {err6!r}")

    return evidence


def bench_signature(exe):
    """Informational only: the depth-10 bench signature of this Windows build.

    A failure or timeout here must not block staging; it is recorded as unavailable.
    """
    try:
        code, out, _ = run_engine(exe, ["bench"], "")
    except CheckError as e:
        return f"unavailable ({e})"
    if code != 0:
        return f"unavailable (bench exit {code})"
    m = re.search(r"bench signature: ([0-9a-f]{16})", out)
    return m.group(1) if m else "unavailable (signature not printed)"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--exe", required=True, help="path to the built flawless.exe")
    ap.add_argument("--out-dir", required=True, help="artifact staging directory")
    ap.add_argument("--commit", required=True, help="expected git commit SHA")
    ap.add_argument("--rustc-version-file", required=True)
    ap.add_argument("--run-id", default="local")
    ap.add_argument("--run-attempt", default="0")
    ap.add_argument("--skip-bench", action="store_true")
    args = ap.parse_args(argv)

    try:
        # 0. Source identity: the checkout must be exactly the commit being reported.
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if head.returncode == 0:
            head_sha = head.stdout.decode().strip()
            if head_sha != args.commit:
                fail(f"checkout HEAD {head_sha} != --commit {args.commit}")

        try:
            with open(args.rustc_version_file, encoding="utf-8") as f:
                rustc_v = f.read()
        except OSError as e:
            fail(f"cannot read --rustc-version-file {args.rustc_version_file}: {e}")
        host = re.search(r"^host: (\S+)$", rustc_v, re.M)
        rustc_line = rustc_v.splitlines()[0] if rustc_v.strip() else "unknown"
        if not host or host.group(1) != EXPECTED_TARGET:
            fail(f"rustc host is {host.group(1) if host else 'unknown'}, want {EXPECTED_TARGET}")

        # 1. Executable exists, non-empty, and is an x86-64 PE.
        exe = os.path.abspath(args.exe)
        if not os.path.isfile(exe):
            fail(f"executable not found: {exe}")
        size = os.path.getsize(exe)
        if size == 0:
            fail("executable is empty")
        machine = pe_machine(exe)
        if machine != EXPECTED_MACHINE:
            fail(f"PE machine is {machine:#06x}, expected {EXPECTED_MACHINE:#06x} (x86-64)")
        print(f"ok: PE x86-64 (machine 0x{machine:04x}), {size} bytes")

        # 2. Smoke-test the exact file that will be packaged.
        evidence = smoke_test(exe)
        print(f"ok: smoke test passed: {evidence}")
        bench = "skipped" if args.skip_bench else bench_signature(exe)
        print(f"info: bench signature (informational): {bench}")

        # 3. Stage.
        os.makedirs(args.out_dir, exist_ok=True)
        staged = os.path.join(args.out_dir, EXE_NAME)
        shutil.copyfile(exe, staged)

        # 4. Checksums and manifest, then re-verify the staged copy.
        digest = sha256_file(staged)
        if digest != sha256_file(exe):
            fail("staged copy differs from built executable")
        sums_path = os.path.join(args.out_dir, "SHA256SUMS.txt")
        with open(sums_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(f"{digest}  {EXE_NAME}\n")

        manifest_path = os.path.join(args.out_dir, "BUILD-MANIFEST.txt")
        built_utc = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        lines = [
            "Flawless Windows x64 release build manifest",
            f"git_commit={args.commit}",
            f"target_triple={EXPECTED_TARGET}",
            f"rustc={rustc_line}",
            "cargo_build_command=cargo build --release --locked",
            "release_profile=[profile.release] lto=fat codegen-units=1 debug=false panic=unwind",
            f"executable={EXE_NAME}",
            f"executable_sha256={digest}",
            f"executable_bytes={size}",
            f"pe_machine=0x{machine:04x} (x86-64)",
            f"smoke_test=passed ({evidence})",
            f"bench_signature_depth10={bench}",
            f"ci_run_id={args.run_id}",
            f"ci_run_attempt={args.run_attempt}",
            f"built_utc={built_utc}",
        ]
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")

        # Re-verify from disk exactly as a downloader would.
        with open(sums_path, encoding="utf-8") as f:
            recorded, name = f.read().split()
        if name != EXE_NAME or recorded != sha256_file(os.path.join(args.out_dir, EXE_NAME)):
            fail("SHA256SUMS.txt does not match the staged executable")
        print(f"ok: {EXE_NAME} sha256={digest}")
        print(f"ok: staged in {os.path.abspath(args.out_dir)}")
        return 0
    except CheckError as e:
        print(f"::error::windows artifact check failed: {e}")
        print(f"FAILED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
