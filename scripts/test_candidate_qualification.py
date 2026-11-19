#!/usr/bin/env python3
"""Regressions for the immutable candidate-specific qualification design."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import candidate_qualification as cq


class PreregistrationTests(unittest.TestCase):
    def test_committed_design_and_suite_hashes_validate(self):
        design = cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH))
        self.assertEqual(design["status"], "PREREGISTERED_NOT_DISPATCHED")
        cq.verify_suite_files(ROOT)

    def test_missing_lf_hash_stability_rule_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, ".gitattributes"), "w", encoding="utf-8") as handle:
                handle.write("/benches/rating-openings-100-batchA.txt text eol=lf\n")
            with self.assertRaisesRegex(ValueError, "LF line-ending rule"):
                cq.verify_suite_files(directory)

    def test_exact_screening_count_and_identity_are_registered(self):
        design = cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH))
        screening = design["screening"]
        self.assertEqual(screening["total_counted_games"], 600)
        self.assertEqual(len(screening["anchors"]) * len(screening["batches"]), 6)
        self.assertEqual(cq.CANDIDATE_SHA256, design["candidate"]["engine_sha256"])

    def test_screening_count_cannot_be_weakened(self):
        design = cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH))
        changed = copy.deepcopy(design)
        changed["screening"]["total_counted_games"] = 599
        with self.assertRaisesRegex(ValueError, "exactly 600"):
            cq.validate_design(changed)

    def test_screening_evidence_cannot_be_relabelled_confirmatory(self):
        design = cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH))
        changed = copy.deepcopy(design)
        changed["screening"]["evidence_class"] = "confirmatory"
        with self.assertRaisesRegex(ValueError, "selection-only"):
            cq.validate_design(changed)

    def test_self_control_requires_all_registered_bootstrap_seeds(self):
        design = cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH))
        changed = copy.deepcopy(design)
        changed["self_control"]["bootstrap_seeds"].pop()
        with self.assertRaisesRegex(ValueError, "seed set"):
            cq.validate_design(changed)

    def test_screening_paths_are_candidate_batch_and_anchor_qualified(self):
        path = cq.candidate_evidence_path(
            cq.CANDIDATE_SHA256, "candidate-screening", batch="B", anchor="akimbo-0.1.1"
        )
        self.assertEqual(
            path,
            f"benches/evidence/candidates/{cq.CANDIDATE_SHA256}/screening/batchB/akimbo-0.1.1",
        )
        self.assertNotIn("benches/evidence/screening/", path)

    def test_self_control_path_is_candidate_qualified_and_distinct(self):
        screening = cq.candidate_evidence_path(
            cq.CANDIDATE_SHA256, "candidate-screening", batch="A", anchor="topple-0.1.1"
        )
        control = cq.candidate_evidence_path(cq.CANDIDATE_SHA256, "candidate-self-control")
        self.assertNotEqual(screening, control)
        self.assertEqual(control, f"benches/evidence/candidates/{cq.CANDIDATE_SHA256}/self-control")

    def test_paths_reject_identity_drift_and_unregistered_cells(self):
        with self.assertRaisesRegex(ValueError, "preregistered candidate"):
            cq.candidate_evidence_path("0" * 64, "candidate-screening", batch="A", anchor="topple-0.1.1")
        with self.assertRaisesRegex(ValueError, "registered batch"):
            cq.candidate_evidence_path(cq.CANDIDATE_SHA256, "candidate-screening", batch="CTRL", anchor="topple-0.1.1")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            cq.candidate_evidence_path(cq.CANDIDATE_SHA256, "confirmatory")


if __name__ == "__main__":
    unittest.main()
