#!/usr/bin/env python3
"""Candidate-specific campaign cost projection from preregistered evidence.

This tool is planning-only. It estimates runner consumption and timeout risk
from the candidate's own six screening cells plus its separately certified
self-control. It never authorizes dispatch or treats screening as rating data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import candidate_qualification as cq
import estimate_campaign_cost as historical_cost
from certify_candidate_control import load_candidate_control
from power_analysis import read_candidate_screening_cell


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attempt_cluster_durations(path: str, *, counted_games_per_opening: int) -> dict[str, float]:
    """Sum wall time for every attempt in each complete opening cluster.

    Uncounted engine-error attempts consume runner time too. Omitting them would
    bias both the measured cost and the confirmatory resampling downward.
    Callers first validate the exact counted schedule and retry provenance.
    """
    grouped: dict[str, list[float]] = {}
    counted_by_opening: dict[str, int] = {}
    with open(path, encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            game = json.loads(raw)
            opening = game.get("opening")
            seconds = game.get("wall_seconds")
            if not isinstance(opening, str) or not opening:
                raise ValueError(f"{path}:{line_no}: attempt lacks opening name")
            if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds <= 0:
                raise ValueError(f"{path}:{line_no}: attempt has invalid wall_seconds")
            grouped.setdefault(opening, []).append(float(seconds))
            if game.get("counted") is True:
                counted_by_opening[opening] = counted_by_opening.get(opening, 0) + 1
    if not grouped or any(counted_by_opening.get(name, 0) != counted_games_per_opening
                          for name in grouped):
        raise ValueError(
            f"{path}: expected exactly {counted_games_per_opening} counted games per opening cluster"
        )
    return {name: sum(values) for name, values in grouped.items()}


def estimate_candidate_campaign_cost(
    *, evidence_root: str, self_control_games: str, self_control_report: str,
    pool_path: str, replicates: int = 20000, concurrency: int = 40,
) -> dict:
    if replicates < 1000:
        raise ValueError("at least 1,000 bootstrap replicates are required")
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    design = cq.load_design(cq.DESIGN_PATH)
    candidate_sha = design["candidate"]["engine_sha256"]
    with open(pool_path, encoding="utf-8") as handle:
        pool_obj = json.load(handle)
    pool = {entry["key"]: entry for entry in pool_obj["engines"]}
    cell_durations: dict[tuple[str, str], list[float]] = {}
    cell_details = {}
    targets = set()
    for batch, (suite_path, suite_sha, dispatch_seed) in cq.SUITES.items():
        for anchor in cq.SCREENING_ANCHORS:
            games_path = os.path.join(evidence_root, "batch" + batch, anchor, "games.jsonl")
            cell = read_candidate_screening_cell(
                games_path, batch=batch, anchor=anchor,
                suite_path=suite_path, suite_sha256=suite_sha,
                dispatch_seed=dispatch_seed, pool=pool, candidate_sha256=candidate_sha,
            )
            durations = attempt_cluster_durations(games_path, counted_games_per_opening=2)
            if set(durations) != set(cell["cluster_scores"]):
                raise ValueError(f"{batch}/{anchor}: timing clusters differ from validated screening clusters")
            cell_durations[(batch, anchor)] = list(durations.values())
            cell_details[f"{batch}/{anchor}"] = {
                "counted_games": 100,
                "opening_clusters": 50,
                "games_sha256": cell["manifest"]["merged_sha256"],
                "cluster_pair_seconds_mean": sum(durations.values()) / len(durations),
                "cluster_pair_seconds_p95": historical_cost.quantile(sorted(durations.values()), 0.95),
            }
            targets.add(cell["target_commit"])
    if len(targets) != 1:
        raise ValueError("all six candidate screening cells must share one target commit")

    with open(self_control_report, encoding="utf-8") as handle:
        certificate = json.load(handle)
    if (certificate.get("status") != "PASS"
            or certificate.get("candidate_sha256") != candidate_sha
            or certificate.get("target_commit") != next(iter(targets))
            or certificate.get("counted_games") != 240
            or certificate.get("seed_robust") is not True
            or certificate.get("all_registered_seeds_pass") is not True):
        raise ValueError("candidate self-control must have a matching unanimous robust PASS certificate")
    if (certificate.get("games_sha256") != sha256_file(self_control_games)
            or certificate.get("evidence_manifest_sha256") != sha256_file(
                os.path.join(os.path.dirname(self_control_games), "manifest.json"))):
        raise ValueError("candidate self-control certificate hashes differ from committed evidence")
    control_games, control_manifest = load_candidate_control(
        self_control_games, design=design, target_commit=next(iter(targets))
    )
    if certificate.get("evidence_path") != self_control_games:
        raise ValueError("candidate self-control certificate points to a different games file")
    control_clusters = attempt_cluster_durations(self_control_games, counted_games_per_opening=4)
    if len(control_clusters) != 60 or len(control_games) != 240:
        raise ValueError("candidate self-control timing evidence is not exactly 240 games/60 clusters")

    rng = random.Random(20261119)
    overhead = historical_cost.OBSERVED_JOB_OVERHEAD_SECONDS
    screening_game_seconds = sum(sum(values) for values in cell_durations.values())
    screening_jobs = 6 * 50
    screening_overhead_seconds = screening_jobs * overhead
    screening_runner_hours = (screening_game_seconds + screening_overhead_seconds) / 3600.0
    control_game_seconds = sum(control_clusters.values())
    control_jobs = 60
    control_overhead_seconds = control_jobs * overhead
    control_runner_hours = (control_game_seconds + control_overhead_seconds) / 3600.0

    campaign_totals = []
    campaign_spans = []
    timeout_count = 0
    total_simulated_jobs = replicates * 300
    timeout_limit = historical_cost.SHARD_TIMEOUT_MINUTES * 60.0
    for _ in range(replicates):
        job_seconds = []
        for cell in cell_durations.values():
            sampled = [cell[rng.randrange(len(cell))] + overhead for _ in range(50)]
            timeout_count += sum(duration > timeout_limit for duration in sampled)
            job_seconds.extend(sampled)
        campaign_totals.append(sum(job_seconds) / 3600.0)
        campaign_spans.append(historical_cost.greedy_makespan(job_seconds, concurrency) / 3600.0)
    campaign_totals.sort()
    campaign_spans.sort()
    confirmatory_runner_hours = historical_cost.mean(campaign_totals)
    total_runner_hours = screening_runner_hours + control_runner_hours + confirmatory_runner_hours
    return {
        "schema": 1,
        "design": "rating-100-v1",
        "status": "PLANNING_ONLY",
        "authorizes_dispatch": False,
        "eligible_for_confirmatory_dispatch": False,
        "candidate_sha256": candidate_sha,
        "target_commit": next(iter(targets)),
        "evidence_class_note": "Screening games are used only to estimate runtime distributions and are permanently excluded from gate evidence.",
        "screening": {
            "counted_games": 600,
            "observed_game_wall_hours": screening_game_seconds / 3600.0,
            "transferred_job_overhead_seconds": screening_overhead_seconds,
            "estimated_runner_hours": screening_runner_hours,
            "shard_jobs": screening_jobs,
            "cells": cell_details,
        },
        "self_control": {
            "counted_games": len(control_games),
            "observed_game_wall_hours": control_game_seconds / 3600.0,
            "transferred_job_overhead_seconds": control_overhead_seconds,
            "estimated_runner_hours": control_runner_hours,
            "shard_jobs": control_jobs,
            "seed_robust": certificate["seed_robust"],
            "all_registered_seeds_pass": certificate["all_registered_seeds_pass"],
            "games_sha256": control_manifest["merged_sha256"],
        },
        "confirmatory_campaign": {
            "counted_games": 600,
            "shard_jobs": 300,
            "runner_hours_estimate_mean": confirmatory_runner_hours,
            "runner_hours_estimate_p05": historical_cost.quantile(campaign_totals, 0.05),
            "runner_hours_estimate_p95": historical_cost.quantile(campaign_totals, 0.95),
            "timeout_exceedance_rate_estimate": timeout_count / total_simulated_jobs,
            "wall_clock_span_hours_estimate": {
                "concurrency": concurrency,
                "mean": historical_cost.mean(campaign_spans),
                "p05": historical_cost.quantile(campaign_spans, 0.05),
                "p95": historical_cost.quantile(campaign_spans, 0.95),
            },
            "bootstrap_replicates": replicates,
            "bootstrap_seed": 20261119,
            "runtime_distribution_source": "observed candidate-screening per-opening attempt durations; includes retries",
        },
        "total_campaign_runner_hours_estimate": total_runner_hours,
        "limitations": [
            "Per-shard overhead is transferred from the previously observed 35-second hosted-run average; it is not measured on this candidate.",
            "Observed candidate game wall time is not the same as summed GitHub job duration; all reported runner totals are estimates, not Actions billing/runtime measurements.",
            "The estimate models the preregistered 100-game-per-anchor-batch confirmation schedule; it authorizes no games.",
            "Independent power review and the committed gate plan remain separate prerequisites.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", default=(
        "benches/evidence/candidates/0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5/screening"))
    parser.add_argument("--self-control-games", default=(
        "benches/evidence/candidates/0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5/self-control/games.jsonl"))
    parser.add_argument("--self-control-report", default=(
        "benches/evidence/candidates/0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5/self-control/certificate.json"))
    parser.add_argument("--pool", default="benches/anchor-pool.json")
    parser.add_argument("--replicates", type=int, default=20000)
    parser.add_argument("--concurrency", type=int, default=40)
    parser.add_argument("--out", default="benches/candidate-confirmatory-cost-estimate.json")
    args = parser.parse_args()
    try:
        report = estimate_candidate_campaign_cost(
            evidence_root=args.evidence_root,
            self_control_games=args.self_control_games,
            self_control_report=args.self_control_report,
            pool_path=args.pool, replicates=args.replicates, concurrency=args.concurrency,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        parser.error(f"candidate-specific cost estimate BLOCKED: {exc}")
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(f"candidate campaign estimate: PLANNING_ONLY; "
          f"{report['total_campaign_runner_hours_estimate']:.1f} estimated runner-hours; no dispatch authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
