#!/usr/bin/env python3
"""Identity, count and robustness regressions for candidate self-control certification."""
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
from certify_candidate_control import certify, load_candidate_control


def file_sha256(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class CandidateControlCertificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = os.path.join(
            self.temp.name,
            f"benches/evidence/candidates/{cq.CANDIDATE_SHA256}/self-control",
        )
        os.makedirs(self.directory)
        self.games_path = os.path.join(self.directory, "games.jsonl")
        self.manifest_path = os.path.join(self.directory, "manifest.json")
        control = cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH))["self_control"]
        with open(os.path.join(ROOT, control["suite"]), encoding="utf-8") as handle:
            opening_names = [
                line.split("|", 1)[0].strip()
                for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
        games = []
        for opening_index, opening_name in enumerate(opening_names):
            for repetition in range(2):
                for pair in ("AB", "BA"):
                    index = len(games)
                    games.append({
                        "opening": opening_name,
                        "white": "flawless",
                        "black": "flawless",
                        "result": "1/2-1/2",
                        "counted": True,
                        "engine_error": False,
                        "adjudicated": True,
                        "schedule_index": index,
                        "replay_depth": 0,
                        "replay_of_schedule_index": None,
                        "repetition": repetition,
                        "color_pair": pair,
                        "_shard_id": f"candidate-self-control-CTRL-candidate-self-control-{index // 4}",
                    })
        with open(self.games_path, "w", encoding="utf-8", newline="\n") as handle:
            for game in games:
                handle.write(json.dumps(game, sort_keys=True) + "\n")
        self.target = "1234567890abcdef1234567890abcdef12345678"
        manifest = {
            "batch": "CTRL",
            "anchor": control["anchor_id"],
            "engine_sha256": cq.CANDIDATE_SHA256,
            "anchor_sha256": cq.CANDIDATE_SHA256,
            "opening_suite_sha256": control["suite_sha256"],
            "time_control": {"mode": "clock", "period_moves": 40, "period_seconds": 900.0},
            "evidence_purpose": "candidate-self-control",
            "candidate_sha256": cq.CANDIDATE_SHA256,
            "dispatch_seed": control["dispatch_seed"],
            "target_commit": self.target,
            "repetitions": 2,
            "evidence_class": "candidate-null-control",
            "n_counted": 240,
            "n_attempts": 240,
            "n_engine_errors": 0,
            "n_unadjudicated": 0,
            "n_shards": 60,
            "shard_ids": [f"candidate-self-control-CTRL-candidate-self-control-{i}" for i in range(60)],
            "merged_sha256": file_sha256(self.games_path),
        }
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)

    def test_valid_engine_error_retry_is_provenanced_and_accepted(self):
        with open(self.games_path, encoding="utf-8") as handle:
            games = [json.loads(line) for line in handle if line.strip()]
        counted = games[0]
        failed = dict(counted, counted=False, engine_error=True, replay_depth=0,
                      replay_of_schedule_index=None)
        replay = dict(counted, replay_depth=1,
                      replay_of_schedule_index=counted["schedule_index"])
        games[0:1] = [failed, replay]
        with open(self.games_path, "w", encoding="utf-8", newline="\n") as handle:
            for game in games:
                handle.write(json.dumps(game, sort_keys=True) + "\n")
        with open(self.manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["n_attempts"] += 1
        manifest["n_engine_errors"] += 1
        manifest["merged_sha256"] = file_sha256(self.games_path)
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        design = cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH))
        counted_games, _ = load_candidate_control(
            self.games_path, design=design, target_commit=self.target
        )
        self.assertEqual(len(counted_games), 240)

    def test_counted_self_control_requires_explicit_adjudication_provenance(self):
        with open(self.games_path, encoding="utf-8") as handle:
            games = [json.loads(line) for line in handle if line.strip()]
        del games[0]["adjudicated"]
        with open(self.games_path, "w", encoding="utf-8", newline="\n") as handle:
            for game in games:
                handle.write(json.dumps(game, sort_keys=True) + "\n")
        with open(self.manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["merged_sha256"] = file_sha256(self.games_path)
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        with self.assertRaisesRegex(ValueError, "boolean counted/error/adjudication provenance"):
            certify(self.games_path, bootstrap=1000, target_commit=self.target)

    def test_complete_candidate_self_control_certifies_all_registered_seeds(self):
        report = certify(self.games_path, bootstrap=1000, target_commit=self.target)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["seed_robust"])
        self.assertTrue(report["all_registered_seeds_pass"])
        self.assertEqual(report["counted_games"], 240)
        self.assertFalse(report["eligible_for_confirmatory_dispatch"])

    def test_wrong_candidate_identity_fails_closed(self):
        with open(self.manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["candidate_sha256"] = "0" * 64
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        with self.assertRaisesRegex(ValueError, "manifest identity mismatch"):
            certify(self.games_path, bootstrap=1000)

    def test_wrong_target_commit_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "target commit differs"):
            certify(self.games_path, bootstrap=1000, target_commit="0" * 40)

    def test_raw_game_tampering_fails_hash_check(self):
        with open(self.games_path, "a", encoding="utf-8") as handle:
            handle.write("{}\n")
        with self.assertRaisesRegex(ValueError, "merged_sha256"):
            certify(self.games_path, bootstrap=1000)

    def test_missing_game_fails_exact_count(self):
        with open(self.games_path, encoding="utf-8") as handle:
            lines = handle.readlines()
        with open(self.games_path, "w", encoding="utf-8") as handle:
            handle.writelines(lines[:-1])
        with open(self.manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["merged_sha256"] = file_sha256(self.games_path)
        manifest["n_counted"] = 239
        manifest["n_attempts"] = 239
        with open(self.manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        with self.assertRaisesRegex(ValueError, "exactly 240 counted"):
            certify(self.games_path, bootstrap=1000)

    def test_non_candidate_path_is_not_accepted(self):
        other = os.path.join(self.temp.name, "generic-screening", "games.jsonl")
        os.makedirs(os.path.dirname(other))
        with open(other, "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        with self.assertRaisesRegex(ValueError, "candidate-qualified immutable path"):
            from certify_candidate_control import load_candidate_control
            load_candidate_control(other, design=cq.load_design(os.path.join(ROOT, cq.DESIGN_PATH)))


if __name__ == "__main__":
    unittest.main()
