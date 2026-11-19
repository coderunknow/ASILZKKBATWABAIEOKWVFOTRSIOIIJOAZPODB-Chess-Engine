#!/usr/bin/env python3
"""Verify the built Windows delivery ZIP, its hashes, manifest, and PE imports.

This validator is run on the Windows release runner against the exact ZIP that
will be uploaded. It is also platform-independent, so the ZIP checks are
regression-tested in CI on other hosts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any

from pe_imports import parse_imports

PACKAGE_NAME = "flawless-windows-x86_64.zip"
MEMBERS = ("BUILD_MANIFEST.json", "SHA256SUMS.txt", "TEST_README.md", "flawless.exe")
CRT_DLL = re.compile(r"^(?:vcruntime|msvcp|msvcr|ucrtbase|api-ms-win-crt)", re.IGNORECASE)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_pe_architecture(data: bytes) -> None:
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError("packaged executable is not a PE image")
    pe_offset = int.from_bytes(data[0x3C:0x40], "little")
    if pe_offset + 26 > len(data) or data[pe_offset:pe_offset + 4] != b"PE\0\0":
        raise ValueError("packaged executable has an invalid PE header")
    machine = int.from_bytes(data[pe_offset + 4:pe_offset + 6], "little")
    optional_magic = int.from_bytes(data[pe_offset + 24:pe_offset + 26], "little")
    if machine != 0x8664 or optional_magic != 0x20B:
        raise ValueError("packaged executable must be AMD64 PE32+")


def verify_package(
    zip_path: str,
    *,
    source_commit: str,
    staged_dir: str | None = None,
    extract_dir: str | None = None,
) -> dict[str, Any]:
    archive = Path(zip_path)
    if archive.name != PACKAGE_NAME:
        raise ValueError(f"unexpected package filename {archive.name!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("expected source commit must be a full lowercase 40-character SHA")
    sidecar = Path(str(archive) + ".sha256")
    expected_zip_sha = sidecar.read_text(encoding="utf-8").split()
    if len(expected_zip_sha) != 2 or expected_zip_sha[1] != archive.name:
        raise ValueError("ZIP checksum sidecar must name exactly the delivery ZIP")
    zip_bytes = archive.read_bytes()
    if expected_zip_sha[0] != sha256(zip_bytes):
        raise ValueError("ZIP checksum sidecar does not match the delivery archive")

    try:
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
            if len(names) != len(set(names)) or set(names) != set(MEMBERS):
                raise ValueError(f"package members differ from the exact required set: {names!r}")
            bad_member = package.testzip()
            if bad_member is not None:
                raise ValueError(f"ZIP CRC check failed for {bad_member!r}")
            contents = {name: package.read(name) for name in MEMBERS}
    except zipfile.BadZipFile as exc:
        raise ValueError("delivery file is not a valid ZIP archive") from exc

    manifest = json.loads(contents["BUILD_MANIFEST.json"].decode("utf-8"))
    binary = contents["flawless.exe"]
    binary_sha = sha256(binary)
    sums_lines = contents["SHA256SUMS.txt"].decode("utf-8").splitlines()
    if sums_lines != [f"{binary_sha}  flawless.exe"]:
        raise ValueError("packaged SHA256SUMS.txt does not uniquely and correctly checksum flawless.exe")
    if manifest.get("engine") != "Flawless" or manifest.get("binary_file") != "flawless.exe":
        raise ValueError("build manifest engine or binary filename identity mismatch")
    if manifest.get("source_commit") != source_commit:
        raise ValueError("build manifest source commit differs from the checked-out release commit")
    if manifest.get("binary_sha256") != binary_sha:
        raise ValueError("build manifest binary SHA-256 differs from the packaged executable")
    if manifest.get("binary_size_bytes") != len(binary):
        raise ValueError("build manifest binary size differs from the packaged executable")
    if manifest.get("external_dependencies") != []:
        raise ValueError("build manifest must declare zero external runtime dependencies")
    if not str(manifest.get("target_triple", "")).startswith("x86_64-pc-windows-msvc"):
        raise ValueError("build manifest target is not x86_64 Windows MSVC")
    if not str(manifest.get("rust_toolchain", "")).startswith("rustc "):
        raise ValueError("build manifest is missing the Rust compiler version")
    if not str(manifest.get("cargo_toolchain", "")).startswith("cargo "):
        raise ValueError("build manifest is missing the Cargo version")

    verify_pe_architecture(binary)
    imports = parse_imports(binary)
    declared_imports = manifest.get("imported_dlls")
    if declared_imports != imports:
        raise ValueError("build manifest imported_dlls differs from the packaged PE import table")
    if any(CRT_DLL.match(name) for name in imports):
        raise ValueError("packaged executable imports a C runtime DLL")

    readme = contents["TEST_README.md"].decode("utf-8")
    if "SHA256SUMS.txt" not in readme or "BUILD_MANIFEST.json" not in readme:
        raise ValueError("packaged test readme omits the checksums or build manifest")

    if staged_dir is not None:
        stage = Path(staged_dir)
        for name in MEMBERS:
            if (stage / name).read_bytes() != contents[name]:
                raise ValueError(f"ZIP member {name!r} differs from the release staging file")

    if extract_dir is not None:
        output = Path(extract_dir)
        output.mkdir(parents=True, exist_ok=True)
        for name, data in contents.items():
            (output / name).write_bytes(data)
        if sorted(path.name for path in output.iterdir()) != sorted(MEMBERS):
            raise ValueError("extracted package directory contains unexpected files")

    return {
        "zip_sha256": sha256(zip_bytes),
        "binary_sha256": binary_sha,
        "binary_size_bytes": len(binary),
        "source_commit": source_commit,
        "members": sorted(MEMBERS),
        "imported_dlls": imports,
        "external_dependencies": manifest["external_dependencies"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--staged-dir")
    parser.add_argument("--extract-dir")
    args = parser.parse_args()
    try:
        result = verify_package(
            args.zip, source_commit=args.source_commit,
            staged_dir=args.staged_dir, extract_dir=args.extract_dir,
        )
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"::error title=Windows package verification failed::{exc}")
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
