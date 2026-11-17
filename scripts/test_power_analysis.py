#!/usr/bin/env python3
"""Manifest identity tests for the RATING-100 prospective power assessment."""
import hashlib
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from power_analysis import SCREENING_ENGINE_SHA256, SCREENING_SUITE_SHA256, read_screening_engine_sha

ENGINE_SHA = SCREENING_ENGINE_SHA256


def write_anchor(root: str, anchor: str, engine_sha: str) -> str:
    directory = os.path.join(root, anchor)
    os.makedirs(directory)
    games_path = os.path.join(directory, "games.jsonl")
    with open(games_path, "w", encoding="utf-8", newline="\n") as handle:
        for _ in range(120):
            handle.write(json.dumps({"counted": True}) + "\n")
    with open(games_path, "rb") as handle:
        games_sha = hashlib.sha256(handle.read()).hexdigest()
    manifest = {
        "batch": "A",
        "anchor": anchor,
        "engine_sha256": engine_sha,
        "opening_suite_sha256": SCREENING_SUITE_SHA256,
        "n_counted": 120,
        "n_attempts": 120,
        "merged_sha256": games_sha,
    }
    with open(os.path.join(directory, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle)
    return games_path


class ScreeningIdentityTests(unittest.TestCase):
    def test_matching_manifests_return_frozen_engine_hash(self):
        with tempfile.TemporaryDirectory() as td:
            games_a = write_anchor(td, "topple-0.1.1", ENGINE_SHA)
            games_b = write_anchor(td, "topple-0.2.1", ENGINE_SHA)
            self.assertEqual(read_screening_engine_sha(games_a, games_b), ENGINE_SHA)

    def test_different_engine_hashes_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            games_a = write_anchor(td, "topple-0.1.1", ENGINE_SHA)
            games_b = write_anchor(td, "topple-0.2.1", "8" * 64)
            with self.assertRaisesRegex(ValueError, "same frozen engine binary"):
                read_screening_engine_sha(games_a, games_b)

    def test_games_file_hash_must_match_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            games_a = write_anchor(td, "topple-0.1.1", ENGINE_SHA)
            games_b = write_anchor(td, "topple-0.2.1", ENGINE_SHA)
            with open(games_a, "a", encoding="utf-8") as handle:
                handle.write("{}\n")
            with self.assertRaisesRegex(ValueError, "merged_sha256"):
                read_screening_engine_sha(games_a, games_b)

    def test_anchor_identity_must_match_registered_source(self):
        with tempfile.TemporaryDirectory() as td:
            games_a = write_anchor(td, "unexpected-anchor", ENGINE_SHA)
            games_b = write_anchor(td, "topple-0.2.1", ENGINE_SHA)
            with self.assertRaisesRegex(ValueError, "expected Batch A anchor"):
                read_screening_engine_sha(games_a, games_b)


if __name__ == "__main__":
    unittest.main()
