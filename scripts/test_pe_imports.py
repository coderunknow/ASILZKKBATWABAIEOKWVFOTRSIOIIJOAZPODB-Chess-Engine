#!/usr/bin/env python3
"""Regression tests for scripts/pe_imports.py.

Run: python3 scripts/test_pe_imports.py   (no external dependencies)

The Windows release workflow uses the parser to *verify* that the delivered
executable does not depend on a C runtime the recipient would have to install
separately. The parser therefore has to be right about two things: it must
find the imports of a real PE image, and it must refuse anything that is not
one.

The tests build a minimal but structurally valid PE32+ image in memory, so
the parser is exercised against real headers, a real section table and a real
import descriptor table rather than against a mock.
"""

import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pe_imports

PASS = 0
FAIL = 0


def check(cond: bool, msg: str) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {msg}")


def build_pe(imports: list[str]) -> bytes:
    """Build a minimal PE32+ image with the given imported DLL names.

    Layout:
      0x0000  DOS header (MZ) with e_lfanew -> 0x80
      0x0080  PE signature + COFF header + optional header (PE32+)
      0x0200  section table entry (.text)
      0x0400  section data: import descriptors, ILT, name strings
    """
    pe_offset = 0x80
    section_table = 0x200
    section_raw = 0x400
    file_alignment = 0x200
    section_alignment = 0x1000
    section_rva = 0x1000

    name_bytes = b""
    name_rvas: list[int] = []
    blob = bytearray()

    # The import descriptors come first, then the lookup table, then names.
    descriptor_size = 20 * (len(imports) + 1)
    ilt_rva = section_rva + descriptor_size
    ilt_offset = section_raw + descriptor_size
    names_offset = ilt_offset + 8 * (len(imports) + 1)
    for name in imports:
        name_rvas.append(section_rva + (names_offset - section_raw) + len(name_bytes))
        name_bytes += name.encode("ascii") + b"\0"

    # Import descriptor table.
    for index, name_rva in enumerate(name_rvas):
        blob += struct.pack(
            "<IIIII",
            ilt_rva + 8 * index,  # OriginalFirstThunk
            0,  # TimeDateStamp
            0,  # ForwarderChain
            name_rva,  # Name
            ilt_rva + 8 * index,  # FirstThunk
        )
    blob += b"\0" * 20  # terminating null descriptor

    # Import lookup table: one hint/name RVA per import, null-terminated.
    for name_rva in name_rvas:
        blob += struct.pack("<II", name_rva, 0)
    blob += b"\0" * 8

    # The imported names.
    blob += name_bytes
    while len(blob) % 8:
        blob += b"\0"

    dos = bytearray(0x80)
    dos[0:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, pe_offset)

    coff = bytearray()
    coff += struct.pack("<HHIIIHH", 0x8664, 1, 0, 0, 0, 240, 0x0022)

    optional = bytearray()
    optional += struct.pack("<H", pe_imports.PE32_PLUS_MAGIC)
    optional += struct.pack("<BB", 14, 0)  # linker version
    optional += struct.pack("<III", len(blob), 0, 0)  # sizes of code/data
    optional += struct.pack("<II", section_raw, 0)  # entry point + base of code
    optional += struct.pack("<Q", 0x140000000)  # image base
    optional += struct.pack("<II", section_alignment, file_alignment)
    optional += struct.pack("<HHHHHH", 6, 0, 0, 0, 6, 0)  # OS/image/subsystem versions
    optional += struct.pack("<III", 0, 0x2000, 0x1000)  # reserved, image size, headers
    optional += struct.pack("<I", 0)  # checksum
    optional += struct.pack("<HH", 3, 0x8160)  # subsystem = console, dll flags
    optional += struct.pack("<QQQQ", 0x100000, 0x1000, 0x100000, 0x1000)  # stack/heap
    optional += struct.pack("<II", 0, 16)  # loader flags, number of rva and sizes
    # 16 data-directory entries; the import directory is index 1.
    data_dirs = bytearray(16 * 8)
    struct.pack_into("<II", data_dirs, 8 * IMPORT_DIRECTORY_INDEX, section_rva, descriptor_size)
    optional += data_dirs

    section = bytearray()
    section += b".text\0\0\0"
    section += struct.pack("<IIII", len(blob), section_rva, len(blob), section_raw)
    section += struct.pack("<IIHHI", 0, 0, 0, 0, 0x60000020)

    header = bytearray(pe_offset + 4 + len(coff) + len(optional))
    header[0:len(dos)] = dos
    header[pe_offset : pe_offset + 4] = b"PE\0\0"
    header[pe_offset + 4 : pe_offset + 4 + len(coff)] = coff
    header[pe_offset + 4 + len(coff) : pe_offset + 4 + len(coff) + len(optional)] = optional
    header[section_table : section_table + len(section)] = section

    image = bytearray(section_raw)
    image[0 : len(header)] = header
    image += blob
    return bytes(image)


IMPORT_DIRECTORY_INDEX = 1


def main() -> int:
    # --- a PE image with two imports -------------------------------------
    image = build_pe(["KERNEL32.dll", "VCRUNTIME140.dll"])
    imports = pe_imports.parse_imports(image)
    check(imports == ["KERNEL32.dll", "VCRUNTIME140.dll"], f"both imports must be found, got {imports}")

    # --- an image with a single import -----------------------------------
    imports = pe_imports.parse_imports(build_pe(["api-ms-win-crt-runtime-l1-1-0.dll"]))
    check(imports == ["api-ms-win-crt-runtime-l1-1-0.dll"], f"a single import must be found, got {imports}")

    # --- a non-PE file is refused ----------------------------------------
    for payload, label in [
        (b"not a pe file at all", "plain text"),
        (b"MZ" + b"\0" * 100, "an MZ header with no PE signature"),
        (b"", "an empty file"),
    ]:
        try:
            pe_imports.parse_imports(payload)
            check(False, f"{label} must be refused")
        except ValueError:
            check(True, f"{label} must be refused")

    # --- a truncated PE image is refused ----------------------------------
    try:
        pe_imports.parse_imports(image[: len(image) // 2])
        check(False, "a truncated PE image must be refused")
    except ValueError:
        check(True, "a truncated PE image must be refused")

    # --- the command line interface --------------------------------------
    with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as handle:
        handle.write(image)
        path = handle.name
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "pe_imports.py"), path],
            capture_output=True,
            text=True,
            check=False,
        )
        check(proc.returncode == 0, f"the CLI must succeed, got rc={proc.returncode}")
        check("VCRUNTIME140.dll" in proc.stdout, "the CLI must print the imported DLL")

        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "pe_imports.py"), path, "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        check(proc.returncode == 0, "the --json CLI must succeed")
        parsed = json.loads(proc.stdout)
        check(parsed["imports"] == ["KERNEL32.dll", "VCRUNTIME140.dll"], "--json must list the imports")

        junk = path + ".txt"
        with open(junk, "wb") as handle:
            handle.write(b"not a pe file")
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "pe_imports.py"), junk],
            capture_output=True,
            text=True,
            check=False,
        )
        check(proc.returncode == 2, "a non-PE file must exit non-zero")
        check("not a PE image" in proc.stderr, "the CLI must explain the refusal")
        os.unlink(junk)
    finally:
        os.unlink(path)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
