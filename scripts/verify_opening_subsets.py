#!/usr/bin/env python3
"""Verify deterministic 50-opening subsets, byte hashes, order and disjointness."""
from __future__ import annotations

import argparse
import hashlib


EXPECTED = {
    "A": "5abdcdbddec0f22d7e6eff8974ee402363c8c3df318b8110d7204adf69f5c1df",
    "B": "ccb4901742eca25b0b10f1a3c9fdfc17b2967a1939c2d7e466c2c5495b6d4253",
}


def read_lines(path: str) -> list[str]:
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.lstrip().startswith("#")]


def expected_subset(path: str, batch: str) -> list[str]:
    original = read_lines(path)
    if len(original) != 60 or len(set(original)) != 60:
        raise ValueError(f"{path}: expected 60 unique historical opening lines")
    ranked = sorted(
        original,
        key=lambda line: hashlib.sha256(
            f"FlawLessChess|rating-100|amendment-2026-11-16|sha256-v1|{batch}|{line}".encode()
        ).hexdigest(),
    )
    chosen = set(ranked[:50])
    return [line for line in original if line in chosen]


def verify(original_a: str, original_b: str, suite_a: str, suite_b: str) -> dict:
    expected_a = expected_subset(original_a, "A")
    expected_b = expected_subset(original_b, "B")
    actual_a = read_lines(suite_a)
    actual_b = read_lines(suite_b)
    for label, actual, expected, path in (
        ("A", actual_a, expected_a, suite_a),
        ("B", actual_b, expected_b, suite_b),
    ):
        if actual != expected:
            raise ValueError(f"Batch {label}: selected lines/order differ from deterministic selector")
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        if digest != EXPECTED[label]:
            raise ValueError(f"Batch {label}: SHA-256 {digest} != preregistered {EXPECTED[label]}")
    names_a = [line.split("|", 1)[0] for line in actual_a]
    names_b = [line.split("|", 1)[0] for line in actual_b]
    overlap = sorted(set(names_a) & set(names_b))
    if len(names_a) != 50 or len(names_b) != 50 or overlap:
        raise ValueError(f"opening clusters are not 50+50 disjoint: overlap={overlap}")
    return {
        "batch_a_openings": len(names_a),
        "batch_b_openings": len(names_b),
        "overlap": overlap,
        "batch_a_sha256": EXPECTED["A"],
        "batch_b_sha256": EXPECTED["B"],
        "selector": "SHA-256 domain-separated per original normalized line; lowest 50; original order retained",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-a", default="benches/rating-openings-batchA.txt")
    parser.add_argument("--original-b", default="benches/rating-openings-batchB.txt")
    parser.add_argument("--suite-a", default="benches/rating-openings-100-batchA.txt")
    parser.add_argument("--suite-b", default="benches/rating-openings-100-batchB.txt")
    args = parser.parse_args()
    print(verify(args.original_a, args.original_b, args.suite_a, args.suite_b))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
