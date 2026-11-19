#!/usr/bin/env python3
"""Regression tests for the RATING-100 confirmatory campaign cost estimator.

The estimator is a PLANNING DIAGNOSTIC. These tests pin the properties that
keep it honest: that it fails closed on evidence identity drift, that it never
claims dispatch authority, and that its arithmetic matches an independent
recomputation from the raw per-game records.
"""
import json
import os
import shutil
import statistics
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import estimate_campaign_cost as ecc


REPO = os.path.dirname(HERE)
SCREENING = {
    "topple-0.1.1": "benches/evidence/screening-2/topple-0.1.1/games.jsonl",
    "topple-0.2.1": "benches/evidence/screening-2/topple-0.2.1/games.jsonl",
    "akimbo-0.1.1": "benches/evidence/screening-3/akimbo-0.1.1/games.jsonl",
}


def repo_path(relative: str) -> str:
    return os.path.join(REPO, relative)


def run_estimate(replicates: int = 2000, **kwargs):
    return ecc.estimate(
        games_by_anchor={k: repo_path(v) for k, v in SCREENING.items()},
        pool_path=repo_path("benches/anchor-pool.json"),
        suite_a=repo_path("benches/rating-openings-100-batchA.txt"),
        suite_b=repo_path("benches/rating-openings-100-batchB.txt"),
        replicates=replicates,
        concurrency_levels=[20, 40],
        replay_allowance=kwargs.get("replay_allowance", 0.0),
    )


class DesignConstantsTests(unittest.TestCase):
    def test_registered_design_is_unchanged(self):
        self.assertEqual(ecc.COUNTED_GAMES_PER_ANCHOR_PER_BATCH, 100)
        self.assertEqual(ecc.OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH, 50)
        self.assertEqual(ecc.GAMES_PER_CLUSTER, 2)
        self.assertEqual(ecc.BATCHES, ("A", "B"))
        self.assertEqual(len(ecc.SCREENING_ANCHORS), 3)

    def test_total_counted_games_is_six_hundred(self):
        report = run_estimate()
        self.assertEqual(report["design"]["expected_total_counted_games"], 600)
        self.assertEqual(report["confirmatory_campaign"]["counted_games"], 600)
        self.assertEqual(report["confirmatory_campaign"]["shard_jobs"], 300)


class FailClosedTests(unittest.TestCase):
    """The estimator must refuse evidence whose identity has drifted."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _copy_evidence(self, anchor: str, subdir: str) -> str:
        source = os.path.dirname(repo_path(SCREENING[anchor]))
        target = os.path.join(self.tmp, subdir)
        shutil.copytree(source, target)
        return os.path.join(target, "games.jsonl")

    def _expect_blocked(self, games_path: str, anchor: str, expected: str):
        with self.assertRaises(SystemExit) as ctx:
            ecc.read_screening_evidence(
                games_path,
                expected_anchor=anchor,
                pool=ecc.load_anchor_pool(repo_path("benches/anchor-pool.json")),
            )
        self.assertIn(expected, str(ctx.exception))

    def test_tampered_games_file_is_rejected(self):
        games = self._copy_evidence("topple-0.1.1", "tampered")
        with open(games, "a", encoding="utf-8") as handle:
            handle.write('{"counted": true}\n')
        self._expect_blocked(games, "topple-0.1.1", "merged_sha256")

    def test_wrong_anchor_identity_is_rejected(self):
        games = self._copy_evidence("topple-0.1.1", "wronganchor")
        self._expect_blocked(games, "akimbo-0.1.1", "expected Batch A anchor")

    def test_engine_binary_drift_is_rejected(self):
        games = self._copy_evidence("topple-0.1.1", "engine")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["engine_sha256"] = "0" * 64
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "topple-0.1.1", "not the registered screening binary")

    def test_anchor_binary_drift_is_rejected(self):
        games = self._copy_evidence("topple-0.1.1", "anchordrift")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["anchor_sha256"] = "1" * 64
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "topple-0.1.1", "differs from the frozen anchor pool")

    def test_suite_hash_drift_is_rejected(self):
        games = self._copy_evidence("topple-0.1.1", "suitedrift")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["opening_suite_sha256"] = "2" * 64
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "topple-0.1.1", "opening-suite hash differs")

    def test_count_total_drift_is_rejected(self):
        games = self._copy_evidence("topple-0.1.1", "countdrift")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["n_counted"] = 119
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "topple-0.1.1", "n_counted disagrees")

    def test_attempt_total_drift_is_rejected(self):
        games = self._copy_evidence("topple-0.1.1", "attemptdrift")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["n_attempts"] = 121
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "topple-0.1.1", "n_attempts disagrees")

    def test_engine_error_total_drift_is_rejected(self):
        games = self._copy_evidence("akimbo-0.1.1", "errordrift")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["n_engine_errors"] = 3
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "akimbo-0.1.1", "n_engine_errors disagrees")

    def test_unadjudicated_total_drift_is_rejected(self):
        games = self._copy_evidence("akimbo-0.1.1", "unadjdrift")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["n_unadjudicated"] = 2
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "akimbo-0.1.1", "n_unadjudicated disagrees")

    def test_shard_total_drift_is_rejected(self):
        games = self._copy_evidence("akimbo-0.1.1", "sharddrift")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["n_shards"] = 59
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "akimbo-0.1.1", "n_shards disagrees")

    def test_shard_id_list_drift_is_rejected(self):
        games = self._copy_evidence("akimbo-0.1.1", "shardids")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["shard_ids"] = ["shard-%d" % i for i in range(60)]
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "akimbo-0.1.1", "shard_ids disagrees")

    def test_time_control_drift_is_rejected(self):
        """A different clock makes the wall-clock durations non-transferable."""
        games = self._copy_evidence("akimbo-0.1.1", "tcdrift")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["time_control"] = {
            "mode": "clock",
            "period_moves": 40,
            "period_seconds": 600.0,
        }
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "akimbo-0.1.1", "not the registered 40/15 repeating clock")

    def test_time_control_drift_is_rejected_for_legacy_manifests(self):
        """The SCREEN-2 manifests predate the field but are still checked."""
        games = self._copy_evidence("topple-0.1.1", "tcdrift2")
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["time_control"] = {
            "mode": "clock",
            "period_moves": 40,
            "period_seconds": 300.0,
        }
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "topple-0.1.1", "not the registered 40/15 repeating clock")

    def test_game_without_a_shard_id_is_rejected(self):
        """Every counted game must belong to a shard, so the shard count can be
        cross-checked against the manifest."""
        games = self._copy_evidence("akimbo-0.1.1", "noshard")
        with open(games, encoding="utf-8") as handle:
            lines = [line for line in handle if line.strip()]
        record = json.loads(lines[0])
        record.pop("_shard_id", None)
        lines[0] = json.dumps(record) + "\n"
        with open(games, "w", encoding="utf-8") as handle:
            handle.writelines(lines)
        # Re-hash so the digest check passes and the shard-id check is reached.
        manifest_path = os.path.join(os.path.dirname(games), "manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["merged_sha256"] = ecc.sha256_jsonl_records(games)
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)
        self._expect_blocked(games, "akimbo-0.1.1", "no _shard_id")


class TimeControlTests(unittest.TestCase):
    """The wall-clock durations are only transferable under the registered
    40/15 repeating clock, so the control must be pinned for every anchor."""

    def test_every_anchor_records_the_registered_time_control(self):
        report = run_estimate()
        for anchor in ecc.SCREENING_ANCHORS:
            tc = report["per_anchor"][anchor]["time_control"]
            self.assertEqual(tc["expected"], ecc.EXPECTED_TIME_CONTROL)
            self.assertIn(tc["source"], ("manifest", "prereg"))
            self.assertTrue(tc["provenance"])

    def test_manifest_backed_anchor_pins_the_control_from_the_manifest(self):
        report = run_estimate()
        self.assertEqual(
            report["per_anchor"]["akimbo-0.1.1"]["time_control"]["source"], "manifest"
        )

    def test_legacy_manifest_anchor_pins_the_control_from_the_registration(self):
        report = run_estimate()
        for anchor in ("topple-0.1.1", "topple-0.2.1"):
            tc = report["per_anchor"][anchor]["time_control"]
            self.assertEqual(tc["source"], "prereg")
            self.assertIn("PREREGISTRATION.md", tc["provenance"])


class AuthorityTests(unittest.TestCase):
    """The estimate must never read as a dispatch authorization."""

    def test_report_is_planning_only(self):
        report = run_estimate()
        self.assertEqual(report["status"], "PLANNING_ONLY")
        self.assertIs(report["authorizes_dispatch"], False)
        self.assertIn("does not authorize", report["authority_note"])

    def test_power_assessment_status_is_not_touched(self):
        with open(repo_path("benches/rating-100-power-assessment.json"), encoding="utf-8") as handle:
            before = handle.read()
        run_estimate()
        with open(repo_path("benches/rating-100-power-assessment.json"), encoding="utf-8") as handle:
            after = handle.read()
        self.assertEqual(before, after)

    def test_dispatch_marker_is_not_touched(self):
        with open(repo_path("benches/dispatch.json"), encoding="utf-8") as handle:
            before = handle.read()
        run_estimate()
        with open(repo_path("benches/dispatch.json"), encoding="utf-8") as handle:
            after = handle.read()
        self.assertEqual(before, after)

    def test_no_gate_plan_is_created(self):
        run_estimate()
        self.assertFalse(os.path.exists(repo_path("benches/gate-plan.json")))


class ArithmeticTests(unittest.TestCase):
    """The totals must match an independent recomputation from raw records."""

    def test_runner_hours_match_independent_recomputation(self):
        """Recompute the total from the raw records, independently.

        Batch A is a direct measurement: the sum of the 50 registered clusters.
        Batch B is modelled: 50 clusters drawn from the anchor's measured
        population, whose expectation is 50 x the population mean pair time.
        The Batch B figure comes from a bootstrap, so it carries Monte Carlo
        error; the comparison is made to within that error.
        """
        report = run_estimate()
        with open(repo_path("benches/rating-openings-100-batchA.txt"), encoding="utf-8") as handle:
            names_a = [
                line.partition("|")[0].strip()
                for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
        expected = 0.0
        for anchor, relative in SCREENING.items():
            records = []
            with open(repo_path(relative), encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        records.append(json.loads(line))
            grouped = {}
            for game in records:
                grouped.setdefault(game["opening"], []).append(game["wall_seconds"])
            pairs = {opening: sum(legs) for opening, legs in grouped.items()}
            expected += sum(pairs[name] for name in names_a)  # Batch A, measured
            expected += 50 * statistics.mean(pairs.values())  # Batch B, modelled
        # The bootstrap mean is an unbiased Monte Carlo estimate of the Batch B
        # expectation; half a runner-hour is far above its sampling error at
        # this replicate count and far below any material modelling difference.
        self.assertAlmostEqual(
            report["confirmatory_campaign"]["game_runner_hours"],
            expected / 3600.0,
            delta=0.5,
        )

    def test_batch_a_point_is_the_exact_measured_sum(self):
        """Batch A must be an exact direct measurement, not a modelled figure."""
        report = run_estimate()
        with open(repo_path("benches/rating-openings-100-batchA.txt"), encoding="utf-8") as handle:
            names_a = [
                line.partition("|")[0].strip()
                for line in handle
                if line.strip() and not line.lstrip().startswith("#")
            ]
        for anchor, relative in SCREENING.items():
            records = []
            with open(repo_path(relative), encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        records.append(json.loads(line))
            grouped = {}
            for game in records:
                grouped.setdefault(game["opening"], []).append(game["wall_seconds"])
            pairs = {opening: sum(legs) for opening, legs in grouped.items()}
            expected = sum(pairs[name] for name in names_a)
            self.assertAlmostEqual(
                report["per_anchor"][anchor]["batch_a"]["point_seconds"], expected, places=6
            )

    def test_overhead_is_added_once_per_shard_job(self):
        report = run_estimate()
        campaign = report["confirmatory_campaign"]
        self.assertAlmostEqual(
            campaign["job_overhead_runner_hours"],
            campaign["shard_jobs"] * ecc.OBSERVED_JOB_OVERHEAD_SECONDS / 3600.0,
            places=9,
        )
        self.assertAlmostEqual(
            campaign["total_runner_hours"],
            campaign["game_runner_hours"] + campaign["job_overhead_runner_hours"],
            places=9,
        )

    def test_interval_brackets_the_point_estimate(self):
        report = run_estimate()
        campaign = report["confirmatory_campaign"]
        self.assertLess(campaign["runner_hours_p05"], campaign["total_runner_hours"])
        self.assertGreater(campaign["runner_hours_p95"], campaign["total_runner_hours"])

    def test_batch_a_is_directly_measured_and_batch_b_is_modelled(self):
        report = run_estimate()
        for cell in report["cells"]:
            if cell["batch"] == "A":
                self.assertTrue(cell["directly_measured"])
                self.assertIsNotNone(cell["point_seconds"])
            else:
                self.assertFalse(cell["directly_measured"])
                self.assertIsNone(cell["point_seconds"])
                self.assertGreater(cell["bootstrap_mean_seconds"], 0.0)

    def test_replay_allowance_increases_cost(self):
        base = run_estimate(replay_allowance=0.0)
        with_replay = run_estimate(replay_allowance=0.1)
        self.assertGreater(
            with_replay["confirmatory_campaign"]["total_runner_hours_with_allowance"],
            base["confirmatory_campaign"]["total_runner_hours_with_allowance"],
        )


class SchedulingTests(unittest.TestCase):
    def test_makespan_is_monotonic_in_concurrency(self):
        jobs = [100.0, 200.0, 300.0, 400.0, 500.0]
        previous = None
        for workers in (1, 2, 3, 5):
            span = ecc.greedy_makespan(jobs, workers)
            if previous is not None:
                self.assertLessEqual(span, previous)
            previous = span

    def test_makespan_never_below_the_longest_job(self):
        jobs = [100.0, 250.0, 30.0]
        for workers in (1, 2, 3, 10):
            self.assertGreaterEqual(ecc.greedy_makespan(jobs, workers), 250.0)

    def test_spans_decrease_with_higher_concurrency(self):
        report = run_estimate()
        concurrent = report["confirmatory_campaign"]["wall_clock_span_hours"]["concurrent_dispatches"]
        self.assertLess(concurrent["40"], concurrent["20"])

    def test_timeout_exceedance_rate_is_a_probability(self):
        report = run_estimate()
        rate = report["confirmatory_campaign"]["timeout_risk"]["bootstrap_exceedance_rate"]
        self.assertGreaterEqual(rate, 0.0)
        self.assertLessEqual(rate, 1.0)


class PrerequisiteTests(unittest.TestCase):
    def test_anchor_vs_anchor_control_is_reused(self):
        report = run_estimate()
        control = report["gate_path_prerequisites"]["anchor_vs_anchor_control"]
        self.assertEqual(control["counted_games"], 0)
        self.assertFalse(control["candidate_dependent"])

    def test_self_match_control_is_candidate_dependent(self):
        report = run_estimate()
        control = report["gate_path_prerequisites"]["candidate_self_match_control"]
        self.assertTrue(control["candidate_dependent"])
        self.assertGreater(control["counted_games"], 0)

    def test_screening_covers_both_batches_for_every_anchor(self):
        report = run_estimate()
        screening = report["gate_path_prerequisites"]["candidate_specific_screening"]
        self.assertEqual(screening["cells"], 6)
        self.assertEqual(screening["counted_games"], 600)

    def test_self_match_control_requires_a_seed_robust_verdict(self):
        report = run_estimate()
        control = report["gate_path_prerequisites"]["candidate_self_match_control"]
        self.assertTrue(control["seed_robustness_required"])
        self.assertIn("unavailable", control["verification"])

    def test_anchor_vs_anchor_control_is_seed_independent(self):
        report = run_estimate()
        control = report["gate_path_prerequisites"]["anchor_vs_anchor_control"]
        self.assertFalse(control["seed_robustness_required"])
        self.assertIn("seed-independent", control["rationale"])


class DeterminismTests(unittest.TestCase):
    def test_same_inputs_give_the_same_report(self):
        first = run_estimate()
        second = run_estimate()
        self.assertEqual(
            json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True)
        )


if __name__ == "__main__":
    unittest.main()
