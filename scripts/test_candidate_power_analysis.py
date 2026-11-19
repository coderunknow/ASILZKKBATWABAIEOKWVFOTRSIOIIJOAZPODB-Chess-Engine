#!/usr/bin/env python3
"""Candidate-bound power analysis input and non-authorization regressions."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import candidate_qualification as cq
from certify_candidate_control import certify
from estimate_candidate_campaign_cost import attempt_cluster_durations, estimate_candidate_campaign_cost
from power_analysis import analyze_candidate, read_candidate_screening_cell


class CandidatePowerAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.design = cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH))
        with open(os.path.join(ROOT, "benches/anchor-pool.json"), encoding="utf-8") as handle:
            self.pool_obj = json.load(handle)
        self.pool = {entry["key"]: entry for entry in self.pool_obj["engines"]}
        self.evidence_root = os.path.join(
            self.temp.name, f"benches/evidence/candidates/{cq.CANDIDATE_SHA256}/screening"
        )
        self.self_control_path = os.path.join(
            self.temp.name, f"benches/evidence/candidates/{cq.CANDIDATE_SHA256}/self-control/games.jsonl"
        )
        os.makedirs(os.path.dirname(self.self_control_path), exist_ok=True)
        self.target = "1234567890abcdef1234567890abcdef12345678"
        control = self.design["self_control"]
        with open(os.path.join(ROOT, control["suite"]), encoding="utf-8") as handle:
            control_openings = [
                line.split("|", 1)[0].strip()
                for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
        control_records = []
        for opening_index, opening in enumerate(control_openings):
            for repetition in range(2):
                for pair in ("AB", "BA"):
                    index = len(control_records)
                    control_records.append({
                        "opening": opening, "white": "flawless", "black": "flawless",
                        "result": "1/2-1/2", "counted": True, "engine_error": False,
                        "adjudicated": True, "schedule_index": index,
                        "replay_depth": 0, "replay_of_schedule_index": None,
                        "repetition": repetition, "color_pair": pair,
                        "_shard_id": f"candidate-self-control-CTRL-candidate-self-control-{index // 4}",
                        "wall_seconds": 10.0,
                    })
        with open(self.self_control_path, "w", encoding="utf-8", newline="\n") as handle:
            for record in control_records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        self.control_manifest_path = os.path.join(os.path.dirname(self.self_control_path), "manifest.json")
        control_manifest = {
            "batch": "CTRL", "anchor": control["anchor_id"],
            "engine_sha256": cq.CANDIDATE_SHA256, "anchor_sha256": cq.CANDIDATE_SHA256,
            "opening_suite_sha256": control["suite_sha256"],
            "time_control": {"mode": "clock", "period_moves": 40, "period_seconds": 900.0},
            "evidence_purpose": "candidate-self-control", "candidate_sha256": cq.CANDIDATE_SHA256,
            "dispatch_seed": control["dispatch_seed"], "target_commit": self.target,
            "repetitions": 2, "evidence_class": "candidate-null-control",
            "n_counted": 240, "n_attempts": 240, "n_engine_errors": 0,
            "n_unadjudicated": 0, "n_shards": 60,
            "shard_ids": [f"candidate-self-control-CTRL-candidate-self-control-{i}" for i in range(60)],
            "merged_sha256": self._sha(self.self_control_path),
        }
        with open(self.control_manifest_path, "w", encoding="utf-8") as handle:
            json.dump(control_manifest, handle)
        self.control_report = os.path.join(os.path.dirname(self.self_control_path), "certificate.json")
        certificate = certify(self.self_control_path, bootstrap=1000, target_commit=self.target)
        with open(self.control_report, "w", encoding="utf-8") as handle:
            json.dump(certificate, handle)
        self._write_all_cells()

    @staticmethod
    def _sha(path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _write_all_cells(self):
        for batch, (suite, suite_sha, seed) in cq.SUITES.items():
            suite_path = os.path.join(ROOT, suite)
            with open(suite_path, encoding="utf-8") as handle:
                names = [
                    line.split("|", 1)[0].strip()
                    for line in handle
                    if line.strip() and not line.lstrip().startswith("#")
                ]
            for anchor_index, anchor in enumerate(cq.SCREENING_ANCHORS):
                directory = os.path.join(self.evidence_root, "batch" + batch, anchor)
                os.makedirs(directory, exist_ok=True)
                games_path = os.path.join(directory, "games.jsonl")
                records = []
                for opening_index, opening in enumerate(names):
                    score_band = (opening_index + anchor_index + (0 if batch == "A" else 1)) % 3
                    for slot in range(2):
                        index = opening_index * 2 + slot
                        pair = "AB" if slot == 0 else "BA"
                        if score_band == 0:
                            result = "1-0" if pair == "AB" else "0-1"
                        elif score_band == 1:
                            result = "1/2-1/2"
                        else:
                            result = "0-1" if pair == "AB" else "1-0"
                        records.append({
                            "opening": opening,
                            "white": "flawless" if pair == "AB" else anchor,
                            "black": anchor if pair == "AB" else "flawless",
                            "result": result,
                            "counted": True,
                            "engine_error": False,
                            "adjudicated": True,
                            "schedule_index": index,
                            "repetition": 0,
                            "replay_depth": 0,
                            "replay_of_schedule_index": None,
                            "color_pair": pair,
                            "wall_seconds": 10.0 + (opening_index % 5),
                            "_shard_id": f"candidate-screening-{batch}-{anchor}-{opening_index}",
                        })
                with open(games_path, "w", encoding="utf-8", newline="\n") as handle:
                    for record in records:
                        handle.write(json.dumps(record, sort_keys=True) + "\n")
                manifest = {
                    "batch": batch,
                    "anchor": anchor,
                    "engine_sha256": cq.CANDIDATE_SHA256,
                    "anchor_sha256": self.pool[anchor]["sha256"],
                    "opening_suite_sha256": suite_sha,
                    "time_control": {"mode": "clock", "period_moves": 40, "period_seconds": 900.0},
                    "evidence_purpose": "candidate-screening",
                    "candidate_sha256": cq.CANDIDATE_SHA256,
                    "dispatch_seed": seed,
                    "target_commit": self.target,
                    "repetitions": 1,
                    "evidence_class": "selection-only",
                    "n_counted": 100,
                    "n_attempts": 100,
                    "n_engine_errors": 0,
                    "n_unadjudicated": 0,
                    "n_shards": 50,
                    "shard_ids": [f"candidate-screening-{batch}-{anchor}-{i}" for i in range(50)],
                    "merged_sha256": self._sha(games_path),
                }
                with open(os.path.join(directory, "manifest.json"), "w", encoding="utf-8") as handle:
                    json.dump(manifest, handle)

    def test_all_six_cells_produce_candidate_bound_blocked_sensitivity(self):
        report = analyze_candidate(
            evidence_root=self.evidence_root,
            pool_path=os.path.join(ROOT, "benches/anchor-pool.json"),
            suite_a=os.path.join(ROOT, cq.SUITES["A"][0]),
            suite_b=os.path.join(ROOT, cq.SUITES["B"][0]),
            self_control_report=self.control_report,
            candidate_sha256=cq.CANDIDATE_SHA256,
            replicates=1000,
        )
        self.assertEqual(report["engine_sha256"], cq.CANDIDATE_SHA256)
        self.assertEqual(report["screening_inputs"]["counted_games"], 600)
        self.assertTrue(report["screening_inputs"]["third_anchor_full_distribution_available"])
        self.assertTrue(report["screening_inputs"]["batch_b_new_suite_distribution_available"])
        self.assertEqual(len(report["scenarios"]), 12)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertFalse(report["eligible_for_confirmatory_dispatch"])
        self.assertIsNone(report["approval"])

    def test_wrong_candidate_binary_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "SHA differs"):
            analyze_candidate(
                evidence_root=self.evidence_root,
                pool_path=os.path.join(ROOT, "benches/anchor-pool.json"),
                suite_a=os.path.join(ROOT, cq.SUITES["A"][0]),
                suite_b=os.path.join(ROOT, cq.SUITES["B"][0]),
                self_control_report=self.control_report,
                candidate_sha256="0" * 64,
                replicates=1000,
            )

    def test_missing_screening_cell_fails_closed(self):
        missing = os.path.join(self.evidence_root, "batchB", "akimbo-0.1.1", "games.jsonl")
        os.unlink(missing)
        with self.assertRaises(FileNotFoundError):
            analyze_candidate(
                evidence_root=self.evidence_root,
                pool_path=os.path.join(ROOT, "benches/anchor-pool.json"),
                suite_a=os.path.join(ROOT, cq.SUITES["A"][0]),
                suite_b=os.path.join(ROOT, cq.SUITES["B"][0]),
                self_control_report=self.control_report,
                candidate_sha256=cq.CANDIDATE_SHA256,
                replicates=1000,
            )

    def test_candidate_screening_requires_explicit_adjudication_and_typed_provenance(self):
        games_path = os.path.join(self.evidence_root, "batchA", "topple-0.1.1", "games.jsonl")
        manifest_path = os.path.join(os.path.dirname(games_path), "manifest.json")
        with open(games_path, encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle if line.strip()]
        del records[0]["adjudicated"]
        with open(games_path, "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["merged_sha256"] = self._sha(games_path)
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        with self.assertRaisesRegex(ValueError, "boolean counted/error/adjudication provenance"):
            read_candidate_screening_cell(
                games_path, batch="A", anchor="topple-0.1.1",
                suite_path=os.path.join(ROOT, cq.SUITES["A"][0]),
                suite_sha256=cq.SUITES["A"][1], dispatch_seed=cq.SUITES["A"][2],
                pool=self.pool, candidate_sha256=cq.CANDIDATE_SHA256,
            )

    def test_candidate_screening_accepts_exact_engine_error_retry(self):
        games_path = os.path.join(self.evidence_root, "batchA", "topple-0.1.1", "games.jsonl")
        manifest_path = os.path.join(os.path.dirname(games_path), "manifest.json")
        with open(games_path, encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle if line.strip()]
        successful = records[0]
        failed = dict(successful, counted=False, engine_error=True, replay_depth=0,
                      replay_of_schedule_index=None, wall_seconds=3.0)
        replay = dict(successful, replay_depth=1,
                      replay_of_schedule_index=successful["schedule_index"], wall_seconds=5.0)
        records[0:1] = [failed, replay]
        with open(games_path, "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["n_attempts"] += 1
        manifest["n_engine_errors"] += 1
        manifest["merged_sha256"] = self._sha(games_path)
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        result = read_candidate_screening_cell(
            games_path, batch="A", anchor="topple-0.1.1",
            suite_path=os.path.join(ROOT, cq.SUITES["A"][0]),
            suite_sha256=cq.SUITES["A"][1], dispatch_seed=cq.SUITES["A"][2],
            pool=self.pool, candidate_sha256=cq.CANDIDATE_SHA256,
        )
        self.assertEqual(result["n_counted"], 100)
        self.assertEqual(result["n_attempts"], 101)

    def test_candidate_screening_rejects_unnecessary_retry(self):
        games_path = os.path.join(self.evidence_root, "batchA", "topple-0.1.1", "games.jsonl")
        manifest_path = os.path.join(os.path.dirname(games_path), "manifest.json")
        with open(games_path, encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle if line.strip()]
        retry = dict(records[0], counted=False, engine_error=True, replay_depth=1,
                     replay_of_schedule_index=records[0]["schedule_index"], wall_seconds=3.0)
        records.append(retry)
        with open(games_path, "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["n_attempts"] += 1
        manifest["n_engine_errors"] += 1
        manifest["merged_sha256"] = self._sha(games_path)
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        with self.assertRaisesRegex(ValueError, "unnecessary replay"):
            read_candidate_screening_cell(
                games_path, batch="A", anchor="topple-0.1.1",
                suite_path=os.path.join(ROOT, cq.SUITES["A"][0]),
                suite_sha256=cq.SUITES["A"][1], dispatch_seed=cq.SUITES["A"][2],
                pool=self.pool, candidate_sha256=cq.CANDIDATE_SHA256,
            )

    def test_cost_projection_includes_failed_attempt_wall_time(self):
        attempts_path = os.path.join(self.temp.name, "retry-attempts.jsonl")
        attempts = [
            {"opening": "cluster-1", "counted": False, "engine_error": True, "wall_seconds": 6.0},
            {"opening": "cluster-1", "counted": True, "engine_error": False, "wall_seconds": 9.0},
            {"opening": "cluster-1", "counted": True, "engine_error": False, "wall_seconds": 4.0},
        ]
        with open(attempts_path, "w", encoding="utf-8") as handle:
            for attempt in attempts:
                handle.write(json.dumps(attempt) + "\n")
        durations = attempt_cluster_durations(attempts_path, counted_games_per_opening=2)
        self.assertEqual(durations, {"cluster-1": 19.0})

    def test_candidate_cost_estimate_is_bound_and_non_authorizing(self):
        report = estimate_candidate_campaign_cost(
            evidence_root=self.evidence_root,
            self_control_games=self.self_control_path,
            self_control_report=self.control_report,
            pool_path=os.path.join(ROOT, "benches/anchor-pool.json"),
            replicates=1000,
            concurrency=20,
        )
        self.assertEqual(report["candidate_sha256"], cq.CANDIDATE_SHA256)
        self.assertEqual(report["screening"]["counted_games"], 600)
        self.assertEqual(report["self_control"]["counted_games"], 240)
        self.assertEqual(report["confirmatory_campaign"]["counted_games"], 600)
        self.assertFalse(report["authorizes_dispatch"])
        self.assertFalse(report["eligible_for_confirmatory_dispatch"])
        self.assertEqual(report["status"], "PLANNING_ONLY")
        self.assertIn("estimated_runner_hours", report["screening"])
        self.assertIn("runner_hours_estimate_mean", report["confirmatory_campaign"])
        self.assertNotIn("runner_hours_measured", report["screening"])
        self.assertFalse(report["authorizes_dispatch"])

    def test_nonrobust_self_control_blocks_power_analysis(self):
        with open(self.control_report, encoding="utf-8") as handle:
            report = json.load(handle)
        report["all_registered_seeds_pass"] = False
        with open(self.control_report, "w", encoding="utf-8") as handle:
            json.dump(report, handle)
        with self.assertRaisesRegex(ValueError, "not a unanimous PASS"):
            analyze_candidate(
                evidence_root=self.evidence_root,
                pool_path=os.path.join(ROOT, "benches/anchor-pool.json"),
                suite_a=os.path.join(ROOT, cq.SUITES["A"][0]),
                suite_b=os.path.join(ROOT, cq.SUITES["B"][0]),
                self_control_report=self.control_report,
                candidate_sha256=cq.CANDIDATE_SHA256,
                replicates=1000,
            )


if __name__ == "__main__":
    unittest.main()
