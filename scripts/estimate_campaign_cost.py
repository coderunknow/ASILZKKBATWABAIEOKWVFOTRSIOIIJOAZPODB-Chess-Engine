#!/usr/bin/env python3
"""Compute-cost estimate for the RATING-100 confirmatory rating campaign.

This is a PLANNING DIAGNOSTIC. It never authorizes a dispatch, never edits
`benches/rating-100-power-assessment.json`, and never changes the status of
the fail-closed rating gate. It reads committed per-game wall-clock evidence,
verifies its identity, and fails closed on any drift.

Two cost quantities are reported:

* RUNNER-HOURS — the aggregate compute actually consumed. Independent of
  scheduling; this is what a billing system would meter.
* WALL-CLOCK SPAN — how long the campaign takes, derived by greedy
  longest-processing-time-first list scheduling over the empirical
  job-duration distribution, at several concurrency levels and under both
  dispatch execution modes.

Because the repository is public and the campaign runs on standard
GitHub-hosted runners (`ubuntu-24.04`), the metered runner-minutes carry no
monetary charge. A notional dollar valuation at the published standard-runner
rate is still computed so the estimate stays meaningful if visibility or
runner class ever changes.

Evidence identity is verified exactly as the prospective power report does it:
frozen candidate/screening binary SHA-256, frozen anchor SHA-256 from the
anchor pool, opening-suite SHA-256, attempt/count totals, and the merged
raw-game digest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from typing import NoReturn

# --- Registered design constants (RATING-100 / rating-100-v1) -------------
COUNTED_GAMES_PER_ANCHOR_PER_BATCH = 100
OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH = 50
GAMES_PER_CLUSTER = 2  # one AB leg and one BA leg
BATCHES = ("A", "B")
SHARD_TIMEOUT_MINUTES = 350
CONTROL_GAMES = 240  # 120 shards x 2 games
CONTROL_SHARDS = 120

SCREENING_SUITE_SHA256 = "2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96"
SCREENING_ENGINE_SHA256 = "9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428"

# The registered CCRL 40/15 repeating clock. Every wall-clock measurement the
# estimate rests on was taken under exactly this control, so evidence recorded
# under any other control is not transferable and must fail closed.
EXPECTED_TIME_CONTROL = {"mode": "clock", "period_moves": 40, "period_seconds": 900.0}

# How the time control is pinned for each screening anchor.
#   "manifest" — the evidence manifest itself records the control and it must
#                match the registered 40/15 clock exactly.
#   "prereg"   — the evidence manifest predates the `time_control` field (the
#                SCREEN-2R manifests were written by an older aggregator). The
#                control is pinned from the registered provenance in
#                PREREGISTRATION.md instead. If such a manifest ever does
#                carry a `time_control`, it is checked and must match.
# Either way a manifest that *states* a different control fails closed.
SCREENING_TIME_CONTROL_SOURCE = {
    "topple-0.1.1": ("prereg", "PREREGISTRATION.md#screen-2 (120 games, TC 40/15, seed 20261123)"),
    "topple-0.2.1": ("prereg", "PREREGISTRATION.md#screen-2 (120 games, TC 40/15, seed 20261124)"),
    "akimbo-0.1.1": ("manifest", "benches/evidence/screening-3/akimbo-0.1.1/manifest.json"),
}

SCREENING_ANCHORS = ("topple-0.1.1", "topple-0.2.1", "akimbo-0.1.1")

SUITES = {
    "A": (
        "benches/rating-openings-100-batchA.txt",
        "5abdcdbddec0f22d7e6eff8974ee402363c8c3df318b8110d7204adf69f5c1df",
    ),
    "B": (
        "benches/rating-openings-100-batchB.txt",
        "ccb4901742eca25b0b10f1a3c9fdfc17b2967a1939c2d7e466c2c5495b6d4253",
    ),
}

# Hosted-run observations, measured from the GitHub Actions job API on the
# completed SCREEN-3 (run 43820645420) and CTRL-2-R (run 43820392119) runs.
#   * per-shard job overhead: job wall time minus summed game wall time,
#     over 60 matched shards (mean 34.8 s, max 50.9 s)
#   * account-wide peak concurrency across two overlapping runs: exactly 40
OBSERVED_JOB_OVERHEAD_SECONDS = 35.0
OBSERVED_JOB_OVERHEAD_MAX_SECONDS = 51.0
OBSERVED_ACCOUNT_PEAK_CONCURRENCY = 40

# Standard GitHub-hosted Linux runner price (USD per minute, 2-core). Used
# only to translate runner-hours into a notional monetary figure.
STANDARD_LINUX_RUNNER_USD_PER_MINUTE = 0.006

BOOTSTRAP_REPLICATES = 20000
BOOTSTRAP_SEED = 20261119


def die(message: str) -> "NoReturn":
    """Fail closed. The message is carried on the SystemExit so that callers
    (and the regression tests) can assert on the specific rejection reason."""
    raise SystemExit(f"estimate_campaign_cost: BLOCKED — {message}")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_jsonl_records(path: str) -> str:
    """Hash UTF-8 JSONL with record terminators normalized to LF.

    Git may check out tracked JSONL as CRLF on Windows while the manifest
    digest was produced on Linux from LF bytes. Universal-newline decoding
    preserves record content and ordering while normalizing only terminators.
    """
    digest = hashlib.sha256()
    with open(path, "r", encoding="utf-8", newline=None) as handle:
        for chunk in iter(lambda: handle.read(1 << 20), ""):
            digest.update(chunk.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))
    return digest.hexdigest()


def read_suite_names(path: str, wanted_sha: str) -> list[str]:
    if sha256_file(path) != wanted_sha:
        die(f"{path}: SHA-256 does not match the preregistered suite hash")
    with open(path, encoding="utf-8") as handle:
        names = [
            line.partition("|")[0].strip()
            for line in handle
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if len(names) != OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH:
        die(f"{path}: expected exactly {OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH} opening clusters")
    if len(set(names)) != len(names):
        die(f"{path}: opening cluster names are not unique")
    return names


def load_anchor_pool(pool_path: str) -> dict[str, dict]:
    try:
        with open(pool_path, encoding="utf-8") as handle:
            pool = json.load(handle)
    except (OSError, ValueError) as exc:
        die(f"cannot read frozen anchor pool: {exc}")
    by_key: dict[str, dict] = {}
    for entry in pool.get("engines", []):
        key = entry.get("key")
        sha = entry.get("sha256", "")
        if not key or not re.fullmatch(r"[0-9a-f]{64}", sha):
            die(f"frozen anchor pool entry {key!r} has no valid frozen binary SHA-256")
        by_key[key] = entry
    return by_key


def read_screening_evidence(games_path: str, *, expected_anchor: str, pool: dict[str, dict]) -> dict:
    """Verify one screening evidence directory and return its measured games.

    Fails closed on identity drift: frozen engine binary, frozen anchor
    binary, opening-suite hash, attempt/count totals, and the merged raw-game
    digest must all match the committed manifest and the frozen pool.
    """
    manifest_path = os.path.join(os.path.dirname(games_path), "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as exc:
        die(f"cannot read screening manifest {manifest_path}: {exc}")

    if manifest.get("batch") != "A" or manifest.get("anchor") != expected_anchor:
        die(
            f"{manifest_path}: expected Batch A anchor {expected_anchor!r}, "
            f"got {manifest.get('batch')!r}/{manifest.get('anchor')!r}"
        )
    if manifest.get("opening_suite_sha256") != SCREENING_SUITE_SHA256:
        die(f"{manifest_path}: opening-suite hash differs from the registered screening suite")
    engine_sha = manifest.get("engine_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", engine_sha):
        die(f"{manifest_path}: missing or malformed engine SHA-256")
    if engine_sha != SCREENING_ENGINE_SHA256:
        die(
            f"{manifest_path}: this evidence carries {engine_sha[:12]}…, not the registered "
            f"screening binary {SCREENING_ENGINE_SHA256[:12]}…"
        )
    if manifest.get("merged_sha256") != sha256_jsonl_records(games_path):
        die(f"{manifest_path}: merged_sha256 does not match the committed games.jsonl")

    anchor_entry = pool.get(expected_anchor)
    if anchor_entry is None:
        die(f"{expected_anchor!r} is not present in the frozen anchor pool")
    if manifest.get("anchor_sha256") != anchor_entry["sha256"]:
        die(f"{manifest_path}: anchor binary SHA-256 differs from the frozen anchor pool")

    records = []
    counted = 0
    engine_errors = 0
    unadjudicated = 0
    shard_ids: set[str] = set()
    with open(games_path, encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                game = json.loads(raw)
            except ValueError as exc:
                die(f"{games_path}:{line_no}: invalid JSON game record: {exc}")
            records.append(game)
            if game.get("engine_error"):
                engine_errors += 1
            if game.get("adjudicated") is False:
                unadjudicated += 1
            shard_id = game.get("_shard_id")
            if not isinstance(shard_id, str) or not shard_id:
                die(f"{games_path}:{line_no}: game record has no _shard_id")
            shard_ids.add(shard_id)
            if game.get("counted") is True and not game.get("engine_error") and game.get("adjudicated") is not False:
                counted += 1

    if manifest.get("n_attempts") != len(records):
        die(f"{manifest_path}: n_attempts disagrees with games.jsonl")
    if manifest.get("n_counted") != counted:
        die(f"{manifest_path}: n_counted disagrees with games.jsonl")
    if manifest.get("n_engine_errors") != engine_errors:
        die(f"{manifest_path}: n_engine_errors disagrees with games.jsonl")
    if manifest.get("n_unadjudicated") != unadjudicated:
        die(f"{manifest_path}: n_unadjudicated disagrees with games.jsonl")
    if manifest.get("n_shards") != len(shard_ids):
        die(f"{manifest_path}: n_shards disagrees with the distinct shard ids in games.jsonl")
    declared_shards = manifest.get("shard_ids")
    if not isinstance(declared_shards, list) or set(declared_shards) != shard_ids:
        die(f"{manifest_path}: shard_ids disagrees with the distinct shard ids in games.jsonl")
    if len(records) != len(shard_ids) * GAMES_PER_CLUSTER:
        die(
            f"{manifest_path}: {len(records)} games across {len(shard_ids)} shards is not "
            f"{GAMES_PER_CLUSTER} games per shard"
        )
    if manifest.get("time_control") is not None:
        if manifest.get("time_control") != EXPECTED_TIME_CONTROL:
            die(
                f"{manifest_path}: time control {manifest.get('time_control')!r} is not the "
                f"registered 40/15 repeating clock"
            )
        tc_source = "manifest"
    else:
        tc_source, tc_provenance = SCREENING_TIME_CONTROL_SOURCE[expected_anchor]
        if tc_source != "prereg":
            die(f"{manifest_path}: the time control is not recorded and cannot be pinned")

    return {
        "manifest": manifest,
        "records": records,
        "n_attempts": len(records),
        "n_counted": counted,
        "n_shards": len(shard_ids),
        "time_control_source": tc_source,
    }


def pair_durations_by_opening(records: list[dict]) -> dict[str, float]:
    """Return summed AB+BA wall-clock seconds per opening cluster.

    The RATING-100 design plays exactly one AB leg and one BA leg per opening
    cluster, so a cluster's job cost is the sum of its two legs.
    """
    grouped: dict[str, list[float]] = {}
    for game in records:
        if game.get("counted") is not True or game.get("engine_error") or game.get("adjudicated") is False:
            continue
        if game.get("color_pair") not in ("AB", "BA"):
            die(f"counted game has an unusable color_pair {game.get('color_pair')!r}")
        opening = game.get("opening")
        wall = game.get("wall_seconds")
        if not isinstance(opening, str) or not opening:
            die("counted game is missing its opening label")
        if not isinstance(wall, (int, float)) or wall <= 0:
            die(f"counted game {opening!r} has an unusable wall_seconds {wall!r}")
        grouped.setdefault(opening, []).append(float(wall))
    for opening, legs in grouped.items():
        if len(legs) != GAMES_PER_CLUSTER:
            die(f"opening {opening!r} has {len(legs)} counted legs, expected {GAMES_PER_CLUSTER}")
    return {opening: sum(legs) for opening, legs in grouped.items()}


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("empty sample")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return sorted_values[int(pos)]
    frac = pos - low
    return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac


class DeterministicRng:
    """Small deterministic LCG; keeps reports reproducible across platforms."""

    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF

    def uniform(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return (self.state + 0.5) / 4294967296.0

    def randint(self, n: int) -> int:
        return min(n - 1, int(self.uniform() * n))


def bootstrap_cell(population: list[float], n_draws: int, rng: DeterministicRng, replicates: int) -> dict:
    """Bootstrap the total cost of drawing `n_draws` clusters with replacement."""
    if not population:
        die("cannot bootstrap an empty cluster population")
    totals = []
    for _ in range(replicates):
        totals.append(sum(population[rng.randint(len(population))] for _ in range(n_draws)))
    totals.sort()
    return {
        "n_draws": n_draws,
        "replicates": replicates,
        "mean": mean(totals),
        "median": quantile(totals, 0.5),
        "p05": quantile(totals, 0.05),
        "p95": quantile(totals, 0.95),
        "min": totals[0],
        "max": totals[-1],
    }


def greedy_makespan(job_seconds: list[float], workers: int) -> float:
    """Greedy longest-processing-time-first list scheduling.

    Deterministic and conservative: it mirrors how a matrix fan-out behaves
    when every job is queued at once and the runner pool drains the longest
    jobs first.
    """
    if workers <= 0:
        die("concurrency must be positive")
    if not job_seconds:
        return 0.0
    free = [0.0] * workers
    for duration in sorted(job_seconds, reverse=True):
        idx = min(range(workers), key=lambda i: free[i])
        free[idx] += duration
    return max(free)


def estimate(
    *,
    games_by_anchor: dict[str, str],
    pool_path: str,
    suite_a: str,
    suite_b: str,
    replicates: int,
    concurrency_levels: list[int],
    replay_allowance: float,
) -> dict:
    pool = load_anchor_pool(pool_path)
    names_a = read_suite_names(suite_a, SUITES["A"][1])
    names_b = read_suite_names(suite_b, SUITES["B"][1])
    if set(names_a) & set(names_b):
        die("Batch A and Batch B opening suites are not disjoint")

    per_anchor: dict[str, dict] = {}
    cells: list[dict] = []
    confirmatory_job_seconds: list[float] = []
    gate_path_job_seconds: list[float] = []
    rng = DeterministicRng(BOOTSTRAP_SEED)

    for anchor in SCREENING_ANCHORS:
        games_path = games_by_anchor[anchor]
        evidence = read_screening_evidence(games_path, expected_anchor=anchor, pool=pool)
        pairs = pair_durations_by_opening(evidence["records"])
        if len(pairs) < OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH:
            die(f"{anchor}: only {len(pairs)} measured opening clusters, need at least 50")

        selected_a = {name: pairs[name] for name in names_a if name in pairs}
        if len(selected_a) != OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH:
            die(
                f"{anchor}: screening evidence covers {len(selected_a)} of the 50 registered "
                "Batch A opening clusters"
            )
        population = list(pairs.values())
        anchor_rng = DeterministicRng(BOOTSTRAP_SEED + sum(ord(c) for c in anchor))

        # Batch A: the 50 registered clusters were measured directly.
        batch_a_point = sum(selected_a.values())
        batch_a_boot = bootstrap_cell(population, OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH, anchor_rng, replicates)
        # Batch B: never timed; exchangeability with Batch A is assumed.
        batch_b_boot = bootstrap_cell(population, OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH, anchor_rng, replicates)

        for batch in BATCHES:
            point = batch_a_point if batch == "A" else None
            boot = batch_a_boot if batch == "A" else batch_b_boot
            cells.append({
                "anchor": anchor,
                "batch": batch,
                "counted_games": COUNTED_GAMES_PER_ANCHOR_PER_BATCH,
                "shards": OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH,
                "directly_measured": batch == "A",
                "point_seconds": point,
                "bootstrap_mean_seconds": boot["mean"],
                "bootstrap_p05_seconds": boot["p05"],
                "bootstrap_p95_seconds": boot["p95"],
            })

        measured = sorted(pairs.values())
        per_anchor[anchor] = {
            "evidence": games_path,
            "screening_engine_sha256": SCREENING_ENGINE_SHA256,
            "measured_clusters": len(pairs),
            "measured_attempts": evidence["n_attempts"],
            "measured_counted": evidence["n_counted"],
            "measured_shards": evidence["n_shards"],
            "time_control": {
                "expected": EXPECTED_TIME_CONTROL,
                "source": evidence["time_control_source"],
                "provenance": SCREENING_TIME_CONTROL_SOURCE[anchor][1],
            },
            "cluster_pair_seconds": {
                "mean": mean(measured),
                "median": quantile(measured, 0.5),
                "p05": quantile(measured, 0.05),
                "p95": quantile(measured, 0.95),
                "max": measured[-1],
            },
            "batch_a": {
                "clusters": OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH,
                "directly_measured": True,
                "point_seconds": batch_a_point,
                "bootstrap": batch_a_boot,
            },
            "batch_b": {
                "clusters": OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH,
                "directly_measured": False,
                "assumption": (
                    "Batch B cluster durations are modelled as exchangeable with the anchor's "
                    "observed Batch A population; Batch B has never been timed."
                ),
                "bootstrap": batch_b_boot,
            },
        }

        # Confirmatory jobs: one job per opening cluster, two games per job.
        # Batch A draws from the 50 measured registered clusters; Batch B draws
        # from the anchor's measured population under the exchangeability
        # assumption.
        for batch in BATCHES:
            source = [selected_a[name] for name in names_a] if batch == "A" else population
            for _ in range(OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH):
                job = source[rng.randint(len(source))] + OBSERVED_JOB_OVERHEAD_SECONDS
                confirmatory_job_seconds.append(job)
                gate_path_job_seconds.append(job)

    # ---- campaign totals -------------------------------------------------
    total_game_seconds = sum(
        (cell["point_seconds"] if cell["point_seconds"] is not None else cell["bootstrap_mean_seconds"])
        for cell in cells
    )
    total_shards = sum(cell["shards"] for cell in cells)
    total_games = sum(cell["counted_games"] for cell in cells)

    # Timeout risk: a shard exceeds the 350-minute job timeout when its two
    # games plus overhead exceed the limit.
    timeout_limit = SHARD_TIMEOUT_MINUTES * 60.0
    exceed = 0
    for _ in range(replicates):
        a = confirmatory_job_seconds[rng.randint(len(confirmatory_job_seconds))] - OBSERVED_JOB_OVERHEAD_SECONDS
        b = confirmatory_job_seconds[rng.randint(len(confirmatory_job_seconds))] - OBSERVED_JOB_OVERHEAD_SECONDS
        if a + b + OBSERVED_JOB_OVERHEAD_SECONDS > timeout_limit:
            exceed += 1
    timeout_rate = exceed / replicates

    runner_hours = total_game_seconds / 3600.0
    overhead_hours = (total_shards * OBSERVED_JOB_OVERHEAD_SECONDS) / 3600.0
    total_runner_hours = runner_hours + overhead_hours
    per_game_seconds = runner_hours / total_games if total_games else 0.0
    replay_hours = total_games * replay_allowance * per_game_seconds

    # ---- wall-clock span --------------------------------------------------
    # Mode 1 (concurrent): all six dispatches are pushed and run together,
    # sharing one account-wide concurrency budget.
    concurrent_spans = {}
    for workers in concurrency_levels:
        concurrent_spans[str(workers)] = greedy_makespan(confirmatory_job_seconds, workers) / 3600.0

    # Mode 2 (sequential waves): one dispatch at a time, 50 shards per wave.
    # The dispatch marker is a single file, so this is the conservative mode.
    wave_jobs = len(confirmatory_job_seconds) // (len(BATCHES) * len(SCREENING_ANCHORS))
    sequential_spans = {}
    for workers in concurrency_levels:
        waves = []
        for wave in range(len(BATCHES) * len(SCREENING_ANCHORS)):
            chunk = confirmatory_job_seconds[wave * wave_jobs:(wave + 1) * wave_jobs]
            waves.append(greedy_makespan(chunk, workers) / 3600.0)
        sequential_spans[str(workers)] = {
            "per_wave_hours": waves,
            "total_hours": sum(waves),
        }

    # ---- gate-path prerequisites ----------------------------------------
    # Candidate-specific screening must cover all three anchors on BOTH the
    # 50-opening Batch A subset and the disjoint 50-opening Batch B subset, so
    # the prospective power report has a measured cluster-level distribution
    # for every anchor in every batch instead of an assumed Batch B one.
    screening_cells = len(SCREENING_ANCHORS) * len(BATCHES)
    screening_games = screening_cells * COUNTED_GAMES_PER_ANCHOR_PER_BATCH
    control_games = CONTROL_GAMES
    screening_hours = screening_games * per_game_seconds
    control_hours = control_games * per_game_seconds

    return {
        "report": "confirmatory-campaign-cost-estimate",
        "schema": 1,
        "date": "2026-11-19",
        "status": "PLANNING_ONLY",
        "authorizes_dispatch": False,
        "authority_note": (
            "This report is a compute-cost planning diagnostic. It is not a prospective power "
            "assessment, it does not change the status of benches/rating-100-power-assessment.json "
            "(BLOCKED), and it does not authorize any confirmatory dispatch. The fail-closed "
            "requirements are unchanged: candidate-specific controls and a reviewed "
            "candidate-specific power PASS must exist before dispatch; exact identity and suite "
            "hashes are enforced; exactly 600 counted games are required; all three unrounded "
            "Elo lower bounds must exceed 2,000; and no pull request is merged automatically."
        ),
        "design": {
            "sample_design": "rating-100-v1",
            "counted_games_per_anchor_per_batch": COUNTED_GAMES_PER_ANCHOR_PER_BATCH,
            "opening_clusters_per_anchor_per_batch": OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH,
            "games_per_cluster": GAMES_PER_CLUSTER,
            "batches": list(BATCHES),
            "anchors": list(SCREENING_ANCHORS),
            "time_control": "40/15 repeating wall-clock",
            "shard_job_timeout_minutes": SHARD_TIMEOUT_MINUTES,
            "expected_total_counted_games": total_games,
            "expected_total_shard_jobs": total_shards,
            "dispatch_count": len(BATCHES) * len(SCREENING_ANCHORS),
        },
        "timing_basis": {
            "screening_engine_sha256": SCREENING_ENGINE_SHA256,
            "screening_engine_label": "ENGINE-1 (time-management remediation)",
            "screening_opening_suite_sha256": SCREENING_SUITE_SHA256,
            "measured_games": sum(a["measured_counted"] for a in per_anchor.values()),
            "measured_source_runs": [43820645420, 43820392119],
            "observed_job_overhead_seconds": OBSERVED_JOB_OVERHEAD_SECONDS,
            "observed_job_overhead_max_seconds": OBSERVED_JOB_OVERHEAD_MAX_SECONDS,
            "observed_account_peak_concurrency": OBSERVED_ACCOUNT_PEAK_CONCURRENCY,
            "transfer_caveats": [
                "All wall-clock measurements come from the ENGINE-1 binary. The confirmatory "
                "campaign runs a different candidate binary, and NO candidate-specific 40/15 "
                "wall-clock timing evidence exists yet, so the engine-to-engine duration "
                "transfer is unmeasured.",
                "Batch B has never been timed at all; its durations are modelled as "
                "exchangeable with the anchor's observed Batch A population.",
                "The candidate is expected to change game length, because the 40/15 repeating "
                "wall-clock schedule ends on move count and decisive result, not on a fixed "
                "duration. A stronger candidate can produce longer or shorter games.",
            ],
        },
        "per_anchor": per_anchor,
        "cells": cells,
        "confirmatory_campaign": {
            "counted_games": total_games,
            "shard_jobs": total_shards,
            "game_runner_hours": runner_hours,
            "job_overhead_runner_hours": overhead_hours,
            "total_runner_hours": total_runner_hours,
            "runner_hours_p05": sum(
                (cell["bootstrap_p05_seconds"]) for cell in cells
            ) / 3600.0,
            "runner_hours_p95": sum(
                (cell["bootstrap_p95_seconds"]) for cell in cells
            ) / 3600.0,
            "replay_allowance_fraction": replay_allowance,
            "replay_allowance_runner_hours": replay_hours,
            "total_runner_hours_with_allowance": total_runner_hours + replay_hours,
            "standard_runner_usd_notional": (
                (total_runner_hours + replay_hours) * 60.0 * STANDARD_LINUX_RUNNER_USD_PER_MINUTE
            ),
            "billing_note": (
                "The repository is public and the campaign uses standard GitHub-hosted runners, "
                "so these runner-minutes are unmetered and cost USD 0. The dollar figure is a "
                "notional valuation at the published standard-runner rate."
            ),
            "wall_clock_span_hours": {
                "concurrent_dispatches": concurrent_spans,
                "sequential_dispatch_waves": sequential_spans,
                "note": (
                    "concurrent_dispatches: all six dispatches run together against one "
                    "account-wide concurrency budget. sequential_dispatch_waves: one dispatch "
                    "at a time, 50 shards per wave, which is the conservative mode because the "
                    "dispatch marker is a single file."
                ),
            },
            "timeout_risk": {
                "shard_timeout_minutes": SHARD_TIMEOUT_MINUTES,
                "bootstrap_exceedance_rate": timeout_rate,
                "bootstrap_replicates": replicates,
                "note": (
                    "Probability that a two-game shard exceeds the 350-minute job timeout. An "
                    "exceeded shard fails and is re-run into a fresh output directory, which "
                    "costs a further pair of games."
                ),
            },
        },
        "gate_path_prerequisites": {
            "note": (
                "Cost of the candidate-specific evidence that must exist before any confirmatory "
                "dispatch can be considered. These runs are NOT authorized by this report; they "
                "are costed so the owner can weigh them."
            ),
            "candidate_specific_screening": {
                "cells": screening_cells,
                "counted_games": screening_games,
                "shard_jobs": screening_cells * OPENING_CLUSTERS_PER_ANCHOR_PER_BATCH,
                "runner_hours": screening_hours,
                "rationale": (
                    "The prospective power report is BLOCKED partly because the third anchor's "
                    "cluster-level distribution is unmeasured and partly because the disjoint "
                    "Batch B subset has no measured distribution. Screening all three anchors "
                    "on both 50-opening subsets supplies both, so the Batch B exchangeability "
                    "assumption becomes a measurement."
                ),
            },
            "candidate_self_match_control": {
                "counted_games": control_games,
                "shard_jobs": CONTROL_SHARDS,
                "runner_hours": control_hours,
                "candidate_dependent": True,
                "rationale": (
                    "The registered self-match null control seats the candidate against itself, "
                    "so it must be re-run for the candidate binary. The committed "
                    "flawless-self-r evidence carries the ENGINE-1 binary and does not transfer."
                ),
            },
            "anchor_vs_anchor_control": {
                "counted_games": 0,
                "shard_jobs": 0,
                "runner_hours": 0.0,
                "candidate_dependent": False,
                "rationale": (
                    "Neither seated engine is the candidate, so the committed anchor-vs-anchor "
                    "control evidence remains valid and is reused; no new games are needed."
                ),
            },
            "total_prerequisite_runner_hours": screening_hours + control_hours,
            "total_prerequisite_counted_games": screening_games + control_games,
        },
        "grand_total": {
            "counted_games": total_games + screening_games + control_games,
            "runner_hours": total_runner_hours + screening_hours + control_hours,
            "standard_runner_usd_notional": (
                (total_runner_hours + screening_hours + control_hours)
                * 60.0
                * STANDARD_LINUX_RUNNER_USD_PER_MINUTE
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--games",
        action="append",
        default=None,
        metavar="ANCHOR=PATH",
        help="screening evidence path for an anchor (repeatable)",
    )
    parser.add_argument("--pool", default="benches/anchor-pool.json")
    parser.add_argument("--suite-a", default=SUITES["A"][0])
    parser.add_argument("--suite-b", default=SUITES["B"][0])
    parser.add_argument("--replicates", type=int, default=BOOTSTRAP_REPLICATES)
    parser.add_argument(
        "--concurrency",
        action="append",
        type=int,
        default=None,
        help="concurrency level to model (repeatable)",
    )
    parser.add_argument(
        "--replay-allowance",
        type=float,
        default=0.0,
        help="fractional allowance for uncounted replay attempts",
    )
    parser.add_argument("--out", default="benches/confirmatory-cost-estimate.json")
    args = parser.parse_args()

    if args.replicates < 1000:
        parser.error("--replicates must be >= 1000")
    if not 0.0 <= args.replay_allowance <= 1.0:
        parser.error("--replay-allowance must be within [0, 1]")
    concurrency_levels = args.concurrency or [10, 20, 38, 40]
    for level in concurrency_levels:
        if level < 1:
            parser.error("--concurrency levels must be positive")

    default_games = {
        "topple-0.1.1": "benches/evidence/screening-2/topple-0.1.1/games.jsonl",
        "topple-0.2.1": "benches/evidence/screening-2/topple-0.2.1/games.jsonl",
        "akimbo-0.1.1": "benches/evidence/screening-3/akimbo-0.1.1/games.jsonl",
    }
    games_by_anchor = dict(default_games)
    if args.games:
        for item in args.games:
            if "=" not in item:
                parser.error(f"--games expects ANCHOR=PATH, got {item!r}")
            anchor, path = item.split("=", 1)
            if anchor not in SCREENING_ANCHORS:
                parser.error(f"--games anchor {anchor!r} is not a registered screening anchor")
            games_by_anchor[anchor] = path

    report = estimate(
        games_by_anchor=games_by_anchor,
        pool_path=args.pool,
        suite_a=args.suite_a,
        suite_b=args.suite_b,
        replicates=args.replicates,
        concurrency_levels=sorted(set(concurrency_levels)),
        replay_allowance=args.replay_allowance,
    )
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    campaign = report["confirmatory_campaign"]
    grand = report["grand_total"]
    span = campaign["wall_clock_span_hours"]
    print(f"confirmatory campaign: {campaign['counted_games']} counted games "
          f"in {campaign['shard_jobs']} shard jobs")
    print(f"  runner-hours: {campaign['total_runner_hours']:.1f} "
          f"(p05 {campaign['runner_hours_p05']:.1f}, p95 {campaign['runner_hours_p95']:.1f})")
    for level, hours in span["concurrent_dispatches"].items():
        print(f"  wall-clock span, concurrent dispatches, concurrency {level}: {hours:.1f} h")
    for level, waves in span["sequential_dispatch_waves"].items():
        print(f"  wall-clock span, sequential waves, concurrency {level}: {waves['total_hours']:.1f} h")
    print(f"  shard-timeout exceedance rate: "
          f"{campaign['timeout_risk']['bootstrap_exceedance_rate']:.4f}")
    print(f"gate-path prerequisites: "
          f"{report['gate_path_prerequisites']['total_prerequisite_runner_hours']:.1f} runner-hours")
    print(f"grand total: {grand['runner_hours']:.1f} runner-hours, "
          f"{grand['counted_games']} counted games; wrote {args.out}")
    print("PLANNING ONLY — this report does not authorize any dispatch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
