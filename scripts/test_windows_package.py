#!/usr/bin/env python3
"""Host-independent verification tests for the Windows delivery package."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from test_pe_imports import build_pe
from verify_windows_package import MEMBERS, PACKAGE_NAME, verify_package

SOURCE = "1234567890abcdef1234567890abcdef12345678"


class WindowsPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        self.stage = os.path.join(self.root, "stage")
        os.makedirs(self.stage)
        self.archive = os.path.join(self.root, PACKAGE_NAME)
        self.binary = build_pe(["KERNEL32.dll"])
        binary_sha = hashlib.sha256(self.binary).hexdigest()
        files = {
            "flawless.exe": self.binary,
            "SHA256SUMS.txt": f"{binary_sha}  flawless.exe\n".encode(),
            "TEST_README.md": b"Verify SHA256SUMS.txt and BUILD_MANIFEST.json before use.\n",
            "BUILD_MANIFEST.json": json.dumps({
                "engine": "Flawless", "binary_file": "flawless.exe",
                "binary_sha256": binary_sha, "binary_size_bytes": len(self.binary),
                "source_commit": SOURCE, "external_dependencies": [],
                "target_triple": "x86_64-pc-windows-msvc",
                "rust_toolchain": "rustc 1.99.0", "cargo_toolchain": "cargo 1.99.0",
                "imported_dlls": ["KERNEL32.dll"],
            }).encode(),
        }
        self.files = files
        for name, data in files.items():
            with open(os.path.join(self.stage, name), "wb") as handle:
                handle.write(data)
        self._write_zip(files)

    def _write_zip(self, files):
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for name, data in files.items():
                package.writestr(name, data)
        with open(self.archive, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        with open(self.archive + ".sha256", "w", encoding="utf-8", newline="\n") as handle:
            handle.write(f"{digest}  {PACKAGE_NAME}\n")

    def test_valid_package_matches_hash_manifest_and_staging(self):
        output = os.path.join(self.root, "extracted")
        report = verify_package(
            self.archive, source_commit=SOURCE, staged_dir=self.stage, extract_dir=output,
        )
        self.assertEqual(report["binary_sha256"], hashlib.sha256(self.binary).hexdigest())
        self.assertEqual(report["members"], sorted(MEMBERS))
        self.assertEqual(sorted(os.listdir(output)), sorted(MEMBERS))

    def test_missing_or_extra_zip_member_is_rejected(self):
        self._write_zip({**self.files, "unexpected.txt": b"unexpected"})
        with self.assertRaisesRegex(ValueError, "exact required set"):
            verify_package(self.archive, source_commit=SOURCE)
        self._write_zip({name: data for name, data in self.files.items() if name != "TEST_README.md"})
        with self.assertRaisesRegex(ValueError, "exact required set"):
            verify_package(self.archive, source_commit=SOURCE)

    def test_manifest_commit_mismatch_is_rejected(self):
        manifest = json.loads(self.files["BUILD_MANIFEST.json"])
        manifest["source_commit"] = "0" * 40
        files = dict(self.files, **{"BUILD_MANIFEST.json": json.dumps(manifest).encode()})
        self._write_zip(files)
        with self.assertRaisesRegex(ValueError, "source commit"):
            verify_package(self.archive, source_commit=SOURCE)

    def test_checksum_manifest_mismatch_is_rejected(self):
        files = dict(self.files, **{"SHA256SUMS.txt": b"0" * 64 + b"  flawless.exe\n"})
        self._write_zip(files)
        with self.assertRaisesRegex(ValueError, "SHA256SUMS"):
            verify_package(self.archive, source_commit=SOURCE)

    def test_non_amd64_pe_format_is_rejected(self):
        binary = bytearray(self.binary)
        pe_offset = int.from_bytes(binary[0x3C:0x40], "little")
        binary[pe_offset + 4:pe_offset + 6] = (0x14C).to_bytes(2, "little")
        binary_sha = hashlib.sha256(binary).hexdigest()
        manifest = json.loads(self.files["BUILD_MANIFEST.json"])
        manifest.update({"binary_sha256": binary_sha, "binary_size_bytes": len(binary)})
        files = dict(self.files)
        files["flawless.exe"] = bytes(binary)
        files["SHA256SUMS.txt"] = f"{binary_sha}  flawless.exe\n".encode()
        files["BUILD_MANIFEST.json"] = json.dumps(manifest).encode()
        self._write_zip(files)
        with self.assertRaisesRegex(ValueError, "AMD64 PE32\\+"):
            verify_package(self.archive, source_commit=SOURCE)

    def test_external_crt_dependency_is_rejected(self):
        binary = build_pe(["KERNEL32.dll", "VCRUNTIME140.dll"])
        binary_sha = hashlib.sha256(binary).hexdigest()
        manifest = json.loads(self.files["BUILD_MANIFEST.json"])
        manifest.update({
            "binary_sha256": binary_sha,
            "binary_size_bytes": len(binary),
            "imported_dlls": ["KERNEL32.dll", "VCRUNTIME140.dll"],
        })
        files = dict(self.files)
        files["flawless.exe"] = binary
        files["SHA256SUMS.txt"] = f"{binary_sha}  flawless.exe\n".encode()
        files["BUILD_MANIFEST.json"] = json.dumps(manifest).encode()
        self._write_zip(files)
        with self.assertRaisesRegex(ValueError, "C runtime DLL"):
            verify_package(self.archive, source_commit=SOURCE)

    def test_outer_zip_checksum_is_enforced(self):
        with open(self.archive + ".sha256", "w", encoding="utf-8") as handle:
            handle.write(f"{'0' * 64}  {PACKAGE_NAME}\n")
        with self.assertRaisesRegex(ValueError, "ZIP checksum"):
            verify_package(self.archive, source_commit=SOURCE)


if __name__ == "__main__":
    unittest.main()
