#!/usr/bin/env python3
"""List the DLLs a Windows PE executable imports.

Used by the Windows release workflow to *verify* the packaging claim instead
of asserting it: the delivered `flawless.exe` must not depend on a C runtime
that the recipient would have to install separately.

The parser is deliberately dependency-free (no pefile, no Windows APIs) so it
runs on any platform, which is what lets the regression tests exercise it.

Usage:
    pe_imports.py <file.exe> [--json]

Prints one imported DLL name per line, sorted. With --json it prints a JSON
object with "path" and "imports".

Exit codes:
    0  the file parsed and its imports were listed
    2  the file is not a readable PE image, or has no import directory
"""

import json
import struct
import sys

# IMAGE_DIRECTORY_ENTRY_IMPORT is index 1 in the optional header's data
# directory.
IMPORT_DIRECTORY_INDEX = 1

# A PE32+ optional header has this Magic value. PE32 (32-bit) has 0x10B.
PE32_PLUS_MAGIC = 0x20B
PE32_MAGIC = 0x10B


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def parse_imports(data: bytes) -> list[str]:
    """Return the sorted list of DLL names imported by a PE image.

    Raises ValueError when the image is not a PE file or when it has no
    import directory.
    """
    if len(data) < 0x40 or data[:2] != b"MZ":
        raise ValueError("not a PE image: missing the MZ signature")
    pe_offset = _u32(data, 0x3C)
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise ValueError("not a PE image: missing the PE signature")

    coff = pe_offset + 4
    number_of_sections = _u16(data, coff + 2)
    optional_header_size = _u16(data, coff + 16)
    optional = coff + 20
    if optional + optional_header_size > len(data):
        raise ValueError("truncated PE optional header")

    magic = _u16(data, optional)
    if magic == PE32_PLUS_MAGIC:
        directory_offset = optional + 112
    elif magic == PE32_MAGIC:
        directory_offset = optional + 96
    else:
        raise ValueError(f"unknown PE optional-header magic 0x{magic:04x}")

    sections_offset = optional + optional_header_size
    if directory_offset + 8 * (IMPORT_DIRECTORY_INDEX + 1) > len(data):
        raise ValueError("truncated PE data directory")

    import_rva = _u32(data, directory_offset + 8 * IMPORT_DIRECTORY_INDEX)
    import_size = _u32(data, directory_offset + 8 * IMPORT_DIRECTORY_INDEX + 4)
    if import_rva == 0 or import_size == 0:
        raise ValueError("the PE image has no import directory")

    sections = []
    for index in range(number_of_sections):
        base = sections_offset + 40 * index
        if base + 40 > len(data):
            raise ValueError("truncated PE section table")
        virtual_size = _u32(data, base + 8)
        virtual_address = _u32(data, base + 12)
        raw_size = _u32(data, base + 16)
        raw_offset = _u32(data, base + 20)
        sections.append((virtual_address, max(virtual_size, raw_size), raw_offset))

    def to_offset(rva: int) -> int:
        for virtual_address, size, raw_offset in sections:
            if virtual_address <= rva < virtual_address + size:
                return raw_offset + (rva - virtual_address)
        raise ValueError(f"RVA 0x{rva:x} is not inside any section")

    names: set[str] = set()
    descriptor = to_offset(import_rva)
    while True:
        if descriptor + 20 > len(data):
            raise ValueError("truncated import descriptor table")
        # Each descriptor is 20 bytes; the table is terminated by an all-zero
        # descriptor.
        if data[descriptor : descriptor + 20] == b"\0" * 20:
            break
        name_rva = _u32(data, descriptor + 12)
        if name_rva == 0:
            break
        name_offset = to_offset(name_rva)
        end = data.index(b"\0", name_offset)
        names.add(data[name_offset:end].decode("ascii", errors="replace"))
        descriptor += 20

    if not names:
        raise ValueError("the PE image imports nothing")
    return sorted(names)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    as_json = "--json" in argv[1:]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    path = args[0]
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        imports = parse_imports(data)
    except (OSError, ValueError) as exc:
        print(f"pe_imports: {path}: {exc}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps({"path": path, "imports": imports}, indent=2))
    else:
        for name in imports:
            print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
