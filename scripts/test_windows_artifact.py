#!/usr/bin/env python3
"""Unit tests for scripts/windows_artifact.py (no engine or Windows needed).

Covers the bestmove grammar (including the optional ponder suffix), PE machine
parsing on synthetic headers, and the informational-only bench behaviour.
"""

import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import windows_artifact as wa  # noqa: E402


def synthetic_pe(machine):
    """Minimal PE header: MZ, e_lfanew = 0x80, PE\\0\\0, COFF machine field."""
    buf = bytearray(0x100)
    buf[0:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 0x80)
    buf[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", buf, 0x84, machine)
    return bytes(buf)


class BestmoveGrammar(unittest.TestCase):
    def match(self, line):
        m = wa.BESTMOVE_RE.match(line)
        return m.group(1) if m else None

    def test_bare_bestmove(self):
        self.assertEqual(self.match("bestmove e2e4"), "e2e4")

    def test_promotion(self):
        self.assertEqual(self.match("bestmove a7a8q"), "a7a8q")

    def test_ponder_suffix_keeps_selected_move(self):
        self.assertEqual(self.match("bestmove e2e4 ponder e7e5"), "e2e4")

    def test_rejects_null_and_garbage(self):
        self.assertIsNone(self.match("bestmove 0000"))
        self.assertIsNone(self.match("bestmove e2e4 extra"))
        self.assertIsNone(self.match("bestmove e2e4 ponder"))
        self.assertIsNone(self.match("info bestmove e2e4"))


class PeMachine(unittest.TestCase):
    def write(self, data):
        f = tempfile.NamedTemporaryFile(delete=False)
        f.write(data)
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def test_x86_64(self):
        self.assertEqual(wa.pe_machine(self.write(synthetic_pe(0x8664))), 0x8664)

    def test_i386_is_reported_not_accepted_silently(self):
        self.assertEqual(wa.pe_machine(self.write(synthetic_pe(0x014C))), 0x014C)

    def test_elf_rejected(self):
        elf = b"\x7fELF" + b"\x00" * 200
        with self.assertRaises(wa.CheckError):
            wa.pe_machine(self.write(elf))

    def test_missing_pe_signature_rejected(self):
        data = bytearray(synthetic_pe(0x8664))
        data[0x80:0x84] = b"XX\x00\x00"
        with self.assertRaises(wa.CheckError):
            wa.pe_machine(self.write(bytes(data)))


class BenchIsInformational(unittest.TestCase):
    def test_bench_timeout_does_not_raise(self):
        orig = wa.run_engine

        def boom(*a, **k):
            raise wa.CheckError("did not exit within 120s")

        wa.run_engine = boom
        try:
            result = wa.bench_signature("flawless.exe")
        finally:
            wa.run_engine = orig
        self.assertTrue(result.startswith("unavailable"), result)

    def test_signature_parsed(self):
        orig = wa.run_engine
        wa.run_engine = lambda *a, **k: (0, "bench signature: 141943aa23b3fc68\n", "")
        try:
            self.assertEqual(wa.bench_signature("flawless.exe"), "141943aa23b3fc68")
        finally:
            wa.run_engine = orig


class DepthEvidence(unittest.TestCase):
    """uci_session_bestmove must reject a bestmove with no completed depth-2 info line."""

    def run_with_lines(self, emitted):
        orig = wa.Session

        class Fake:
            def __init__(self, exe, args):
                self.lines = []
                self.feed = list(emitted)
                self.stderr_chunks = []

            def send(self, cmd):
                pass

            def read_until(self, pred, what):
                while self.feed:
                    line = self.feed.pop(0)
                    self.lines.append(line)
                    if pred(line):
                        return self.lines
                raise wa.CheckError(f"no line for {what}")

            def finish(self):
                return 0

            def kill(self):
                pass

        wa.Session = Fake
        try:
            return wa.uci_session_bestmove("flawless", [], "t")
        finally:
            wa.Session = orig

    base = ["id name Flawless", "uciok", "readyok", "readyok"]

    def test_depth2_accepted(self):
        lines = self.base + ["info depth 1 seldepth 1 multipv 1 score cp 37 nodes 53", "info depth 2 seldepth 4 multipv 1 score cp 12", "bestmove b1c3 ponder b8c6"]
        _, bm, code, _ = self.run_with_lines(lines)
        self.assertEqual((bm, code), ("b1c3", 0))

    def test_depth0_fallback_rejected(self):
        lines = self.base + ["bestmove a2a3"]
        with self.assertRaises(wa.CheckError):
            self.run_with_lines(lines)


if __name__ == "__main__":
    unittest.main(verbosity=1)
