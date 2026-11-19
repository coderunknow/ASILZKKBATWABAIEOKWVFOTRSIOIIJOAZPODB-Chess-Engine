#!/usr/bin/env python3
"""Exact-count and identity regressions for candidate evidence aggregation."""
from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from aggregate_shards import validate_candidate_schedule, validate_candidate_shard_commit


def schedule(purpose: str) -> list[dict]:
    per_cluster = 2 if purpose == "candidate-screening" else 4
    clusters = 50 if purpose == "candidate-screening" else 60
    anchor = "topple-0.1.1"
    records = []
    for cluster in range(clusters):
        for local in range(per_cluster):
            index = cluster * per_cluster + local
            ab = index % 2 == 0
            records.append({
                "counted": True,
                "result": "1/2-1/2",
                "schedule_index": index,
                "opening": f"opening-{cluster}",
                "color_pair": "AB" if ab else "BA",
                "repetition": (index % per_cluster) // 2,
                "white": "flawless" if ab or purpose == "candidate-self-control" else anchor,
                "black": anchor if ab and purpose == "candidate-screening" else "flawless",
                "engine_error": False,
                "adjudicated": True,
                "replay_depth": 0,
                "replay_of_schedule_index": None,
                "_shard_id": (f"candidate-screening-A-{anchor}-{index // per_cluster}"
                              if purpose == "candidate-screening"
                              else f"candidate-self-control-CTRL-candidate-self-control-{index // per_cluster}"),
            })
    return records


class CandidateScheduleTests(unittest.TestCase):
    def assert_rejected(
        self, games: list[dict], purpose: str, anchor: str, message: str,
        expected_openings: list[str] | None = None,
    ):
        if expected_openings is None:
            clusters = 50 if purpose == "candidate-screening" else 60
            expected_openings = [f"opening-{index}" for index in range(clusters)]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            validate_candidate_schedule(
                games, purpose, anchor, expected_openings,
                "A" if purpose == "candidate-screening" else "CTRL",
            )
        self.assertIn(message, stderr.getvalue())

    def test_screening_requires_exact_complete_100_game_schedule(self):
        validate_candidate_schedule(
            schedule("candidate-screening"), "candidate-screening", "topple-0.1.1",
            [f"opening-{i}" for i in range(50)], batch="A",
        )

    def test_self_control_requires_exact_complete_240_game_schedule(self):
        validate_candidate_schedule(
            schedule("candidate-self-control"), "candidate-self-control", "candidate-self-control",
            [f"opening-{i}" for i in range(60)], batch="CTRL",
        )

    def test_opening_order_must_match_registered_suite(self):
        games = schedule("candidate-screening")
        games[0]["opening"] = "unregistered"
        games[1]["opening"] = "unregistered"
        self.assert_rejected(
            games, "candidate-screening", "topple-0.1.1", "does not match registered opening",
            [f"opening-{i}" for i in range(50)],
        )

    def test_missing_counted_game_fails_closed(self):
        games = schedule("candidate-screening")[:-1]
        self.assert_rejected(games, "candidate-screening", "topple-0.1.1", "exactly 100 counted")

    def test_duplicate_schedule_index_fails_closed(self):
        games = schedule("candidate-self-control")
        games[-1]["schedule_index"] = 0
        self.assert_rejected(games, "candidate-self-control", "candidate-self-control", "duplicate attempt")

    def test_wrong_pair_order_fails_closed(self):
        games = schedule("candidate-screening")
        games[0]["color_pair"] = "BA"
        self.assert_rejected(games, "candidate-screening", "topple-0.1.1", "incorrect seat or repetition identity")

    def test_wrong_engine_seat_fails_closed(self):
        games = schedule("candidate-screening")
        games[0]["black"] = "another-engine"
        self.assert_rejected(games, "candidate-screening", "topple-0.1.1", "incorrect seat or repetition identity")

    def test_counted_record_requires_explicit_adjudication(self):
        games = schedule("candidate-screening")
        del games[0]["adjudicated"]
        self.assert_rejected(
            games, "candidate-screening", "topple-0.1.1",
            "lacks boolean counted/error/adjudication provenance",
        )

    def test_repetition_identity_must_be_an_integer_not_boolean(self):
        games = schedule("candidate-self-control")
        games[2]["repetition"] = True
        self.assert_rejected(
            games, "candidate-self-control", "candidate-self-control",
            "non-integer repetition identity",
        )

    def test_counted_provenance_fields_must_be_booleans(self):
        games = schedule("candidate-screening")
        games[0]["engine_error"] = "false"
        self.assert_rejected(
            games, "candidate-screening", "topple-0.1.1",
            "lacks boolean counted/error/adjudication provenance",
        )

    def test_counted_attempt_must_have_a_final_game_result(self):
        games = schedule("candidate-screening")
        games[0]["result"] = "*"
        self.assert_rejected(
            games, "candidate-screening", "topple-0.1.1", "has invalid result",
        )

    def test_valid_engine_error_replay_is_accepted(self):
        games = schedule("candidate-screening")
        counted = games[0]
        failed = dict(counted, counted=False, engine_error=True, replay_depth=0,
                      replay_of_schedule_index=None)
        replay = dict(counted, replay_depth=1,
                      replay_of_schedule_index=counted["schedule_index"])
        games[0:1] = [failed, replay]
        validate_candidate_schedule(
            games, "candidate-screening", "topple-0.1.1",
            [f"opening-{i}" for i in range(50)], batch="A",
        )

    def test_unnecessary_retry_is_rejected(self):
        games = schedule("candidate-screening")
        retry = dict(games[0], counted=False, engine_error=True, replay_depth=1,
                     replay_of_schedule_index=games[0]["schedule_index"])
        games.append(retry)
        self.assert_rejected(games, "candidate-screening", "topple-0.1.1", "invalid or unnecessary replay")

    def test_failed_attempt_identity_is_validated(self):
        games = schedule("candidate-screening")
        games[0]["counted"] = False
        games[0]["engine_error"] = True
        games[0]["black"] = "unregistered-anchor"
        self.assert_rejected(games, "candidate-screening", "topple-0.1.1", "incorrect seat or repetition identity")

    def test_candidate_shard_must_match_frozen_source_commit(self):
        meta = {"git_commit": "a" * 40}
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            validate_candidate_shard_commit(meta, "candidate-screening", "b" * 40, "shard-0")
        self.assertIn("git_commit", stderr.getvalue())
        validate_candidate_shard_commit(meta, "historical-screening", "b" * 40, "shard-0")

    def test_non_candidate_purposes_are_not_reinterpreted(self):
        validate_candidate_schedule([], "historical-screening", "topple-0.1.1")


if __name__ == "__main__":
    unittest.main()
