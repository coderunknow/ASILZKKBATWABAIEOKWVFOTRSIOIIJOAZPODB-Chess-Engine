#!/usr/bin/env python3
"""Prospective sensitivity analysis for the proposed 100-game/50-cluster design.

This is a planning diagnostic, not a substitute for the registered joint
opening-cluster bootstrap on actual confirmatory evidence. It deliberately
blocks dispatch because the third-anchor cluster distribution and the disjoint
Batch-B subset have not yet been observed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
from collections import defaultdict

SCREENING_SUITE_SHA256 = "2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96"
SCREENING_ENGINE_SHA256 = "9663697da62e33229d516af3681c442e268287c59d6b97ff2cd13256b564d428"
SCREENING_ANCHORS = ("topple-0.1.1", "topple-0.2.1")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()



def read_screening_manifest(games_path: str, expected_anchor: str) -> dict:
    manifest_path = os.path.join(os.path.dirname(games_path), "manifest.json")
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read screening manifest {manifest_path}: {exc}") from exc

    if manifest.get("batch") != "A" or manifest.get("anchor") != expected_anchor:
        raise ValueError(
            f"{manifest_path}: expected Batch A anchor {expected_anchor!r}, "
            f"got {manifest.get('batch')!r}/{manifest.get('anchor')!r}"
        )
    if manifest.get("opening_suite_sha256") != SCREENING_SUITE_SHA256:
        raise ValueError(f"{manifest_path}: suite hash differs from registered SCREEN-2")
    if manifest.get("n_counted") != 120 or manifest.get("n_attempts") != 120:
        raise ValueError(f"{manifest_path}: expected 120 counted games and 120 attempts")
    engine_sha = manifest.get("engine_sha256", "")
    if not re.fullmatch(r"[0-9a-f]{64}", engine_sha):
        raise ValueError(f"{manifest_path}: missing or malformed engine SHA-256")
    if engine_sha != SCREENING_ENGINE_SHA256:
        raise ValueError(
            f"{manifest_path}: this report is preregistered only for SCREEN-2 / ENGINE-1 "
            f"({SCREENING_ENGINE_SHA256}); observed {engine_sha}"
        )
    if manifest.get("merged_sha256") != sha256_file(games_path):
        raise ValueError(f"{manifest_path}: merged_sha256 does not match games.jsonl")
    attempts = counted = 0
    with open(games_path, encoding="utf-8") as games_file:
        for line_no, raw in enumerate(games_file, 1):
            if not raw.strip():
                continue
            try:
                game = json.loads(raw)
            except ValueError as exc:
                raise ValueError(f"{games_path}:{line_no}: invalid JSON game record") from exc
            attempts += 1
            if game.get("counted") is True and not game.get("engine_error") and game.get("adjudicated") is not False:
                counted += 1
    if attempts != 120 or counted != 120:
        raise ValueError(
            f"{games_path}: expected 120 raw attempts and 120 valid counted games; "
            f"got {attempts} attempts / {counted} counted"
        )
    return manifest


def read_screening_engine_sha(games_a: str, games_b: str) -> str:
    manifest_a = read_screening_manifest(games_a, SCREENING_ANCHORS[0])
    manifest_b = read_screening_manifest(games_b, SCREENING_ANCHORS[1])
    if manifest_a["engine_sha256"] != manifest_b["engine_sha256"]:
        raise ValueError("SCREEN-2 anchor manifests do not use the same frozen engine binary")
    return manifest_a["engine_sha256"]


def load_cluster_scores(path: str, focus: str = "flawless") -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    with open(path, encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            game = json.loads(raw)
            if game.get("counted") is not True or game.get("engine_error") or game.get("adjudicated") is False:
                continue
            result = game.get("result")
            if result == "1-0":
                white_score = 1.0
            elif result == "0-1":
                white_score = 0.0
            elif result == "1/2-1/2":
                white_score = 0.5
            else:
                raise ValueError(f"{path}:{line_no}: counted game has invalid result {result!r}")
            white = str(game.get("white", "")).casefold()
            black = str(game.get("black", "")).casefold()
            if white == focus.casefold():
                score = white_score
            elif black == focus.casefold():
                score = 1.0 - white_score
            else:
                raise ValueError(f"{path}:{line_no}: neither side is focus engine {focus!r}")
            opening = game.get("opening")
            if not isinstance(opening, str) or not opening:
                raise ValueError(f"{path}:{line_no}: missing opening label")
            grouped[opening].append(score)
    if not grouped:
        raise ValueError(f"no counted opening clusters in {path}")
    if any(len(values) != 2 for values in grouped.values()):
        raise ValueError(f"{path}: screening input must contain two counted games per opening cluster")
    return {name: sum(values) / len(values) for name, values in grouped.items()}


def mean_sd(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return mean, math.sqrt(variance)


def sample_correlation(a: list[float], b: list[float]) -> float:
    ma, sa = mean_sd(a)
    mb, sb = mean_sd(b)
    covariance = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (len(a) - 1)
    return covariance / (sa * sb)


def invert(matrix: list[list[float]]) -> list[list[float]]:
    n = len(matrix)
    work = [row[:] + [1.0 if i == j else 0.0 for j in range(n)]
            for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(work[row][col]))
        if abs(work[pivot][col]) < 1e-12:
            raise ValueError("singular sensitivity covariance matrix")
        work[col], work[pivot] = work[pivot], work[col]
        divisor = work[col][col]
        work[col] = [x / divisor for x in work[col]]
        for row in range(n):
            if row == col:
                continue
            factor = work[row][col]
            work[row] = [x - factor * y for x, y in zip(work[row], work[col])]
    return [row[n:] for row in work]


def quadratic(weights: list[float], matrix: list[list[float]]) -> float:
    return sum(weights[i] * weights[j] * matrix[i][j]
               for i in range(len(weights)) for j in range(len(weights)))


class DeterministicRng:
    """Small deterministic LCG + Box-Muller; keeps reports reproducible cross-platform."""
    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF

    def uniform(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return (self.state + 0.5) / 4294967296.0

    def normal(self) -> float:
        u = max(1e-12, self.uniform())
        v = self.uniform()
        return math.sqrt(-2.0 * math.log(u)) * math.cos(2.0 * math.pi * v)


def scenario(
    theta: float,
    inflation: float,
    third_corr: float,
    *,
    ratings: list[float],
    calibration_sd: list[float],
    first_two_sd: list[float],
    first_two_corr: float,
    clusters: int,
    replicates: int,
) -> dict:
    scores = [1.0 / (1.0 + 10.0 ** ((rating - theta) / 400.0)) for rating in ratings]
    slopes = [400.0 / (math.log(10.0) * p * (1.0 - p)) for p in scores]
    cluster_sd = [first_two_sd[0], first_two_sd[1], max(first_two_sd)] 
    cluster_sd = [x * inflation for x in cluster_sd]
    corr = [
        [1.0, first_two_corr, third_corr],
        [first_two_corr, 1.0, third_corr],
        [third_corr, third_corr, 1.0],
    ]
    match = [
        [corr[i][j] * cluster_sd[i] * cluster_sd[j] * slopes[i] * slopes[j] / clusters
         for j in range(3)]
        for i in range(3)
    ]
    calibration = [
        [calibration_sd[i] ** 2 if i == j else 0.0 for j in range(3)]
        for i in range(3)
    ]
    total = [[match[i][j] + calibration[i][j] for j in range(3)] for i in range(3)]
    inv_total = invert(total)
    row_sums = [sum(row) for row in inv_total]
    denominator = sum(row_sums)
    weights = [x / denominator for x in row_sums]
    var_match = quadratic(weights, match)
    var_cal = quadratic(weights, calibration)
    z95 = 1.959963984540054
    se_batch = math.sqrt(var_match + var_cal)
    se_combined = math.sqrt(var_match / 2.0 + var_cal)
    half_batch = z95 * se_batch
    half_combined = z95 * se_combined

    seed = (20261116 + round(theta * 10) + round(inflation * 100)
            + round(third_corr * 100)) & 0xFFFFFFFF
    rng = DeterministicRng(seed)
    sd_match = math.sqrt(var_match)
    sd_cal = math.sqrt(var_cal)
    passed_all = 0
    passed_batch_a = 0
    passed_batch_b = 0
    passed_combined = 0
    for _ in range(replicates):
        common_cal = sd_cal * rng.normal()
        noise_a = sd_match * rng.normal()
        noise_b = sd_match * rng.normal()
        a_pass = theta + common_cal + noise_a - half_batch > 2000.0
        b_pass = theta + common_cal + noise_b - half_batch > 2000.0
        c_pass = theta + common_cal + (noise_a + noise_b) / 2.0 - half_combined > 2000.0
        passed_batch_a += a_pass
        passed_batch_b += b_pass
        passed_combined += c_pass
        passed_all += a_pass and b_pass and c_pass

    return {
        "assumed_true_rating": theta,
        "cluster_sd_inflation": inflation,
        "third_anchor_opening_correlation": third_corr,
        "assumed_scores_vs_anchors": scores,
        "batch_match_se_elo": math.sqrt(var_match),
        "shared_calibration_se_elo": math.sqrt(var_cal),
        "batch_95_half_width_elo": half_batch,
        "combined_95_half_width_elo": half_combined,
        "power_batch_a": passed_batch_a / replicates,
        "power_batch_b": passed_batch_b / replicates,
        "power_combined": passed_combined / replicates,
        "power_all_three_gates": passed_all / replicates,
        "gls_weights": weights,
        "monte_carlo_replicates": replicates,
    }


def read_suite_names(path: str) -> list[str]:
    names = []
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                if "|" not in line:
                    raise ValueError(f"{path}: invalid opening-suite line {line!r}")
                names.append(line.split("|", 1)[0].strip())
    if len(names) != 50 or len(set(names)) != 50:
        raise ValueError(f"{path}: expected exactly 50 unique opening clusters")
    return names


def analyze(
    games_a: str,
    games_b: str,
    pool_path: str,
    suite_a: str,
    suite_b: str,
    replicates: int = 250_000,
) -> dict:
    screening_engine_sha256 = read_screening_engine_sha(games_a, games_b)
    clusters_a = load_cluster_scores(games_a)
    clusters_b = load_cluster_scores(games_b)
    names_a = read_suite_names(suite_a)
    names_b = read_suite_names(suite_b)
    if set(names_a) & set(names_b):
        raise ValueError("new Batch A and Batch B opening suites are not disjoint")
    missing = [name for name in names_a if name not in clusters_a or name not in clusters_b]
    if missing:
        raise ValueError(f"screening evidence missing selected Batch A opening clusters: {missing[:5]}")
    common = names_a
    scores_a = [clusters_a[name] for name in common]
    scores_b = [clusters_b[name] for name in common]
    mean_a, sd_a = mean_sd(scores_a)
    mean_b, sd_b = mean_sd(scores_b)
    rho = sample_correlation(scores_a, scores_b)

    with open(pool_path, encoding="utf-8") as handle:
        pool = json.load(handle)
    wanted = ["topple-0.1.1", "topple-0.2.1", "akimbo-0.1.1"]
    by_key = {engine["key"]: engine for engine in pool["engines"]}
    anchors = [by_key[key] for key in wanted]
    ratings = [float(engine["published_elo"]) for engine in anchors]
    calibration_sd = [float(engine["published_error"]) / 1.96 for engine in anchors]

    grid = []
    for theta in (2050.0, 2100.0, 2150.0, 2200.0):
        for inflation in (1.0, 1.5, 2.0):
            for third_corr in (0.0, 0.25, 0.5):
                grid.append(scenario(
                    theta, inflation, third_corr,
                    ratings=ratings,
                    calibration_sd=calibration_sd,
                    first_two_sd=[sd_a, sd_b],
                    first_two_corr=rho,
                    clusters=50,
                    replicates=replicates,
                ))

    return {
        "design": "rating-100-v1",
        "date": "2026-11-17",
        "engine_sha256": screening_engine_sha256,
        "screening_engine_scope": (
            "Derived from SCREEN-2 / ENGINE-1 only; this power assessment does not apply "
            "to ENGINE-2 (SEE ordering) or any other binary SHA-256."
        ),
        "status": "BLOCKED",
        "eligible_for_confirmatory_dispatch": False,
        "opening_suites": {
            "amended_a": suite_a,
            "amended_b": suite_b,
            "batch_a_sha256": sha256_file(suite_a),
            "batch_b_sha256": sha256_file(suite_b),
        },
        "screening_inputs": {
            "source": [games_a, games_b],
            "screening_engine_sha256": screening_engine_sha256,
            "screening_engine_label": "ENGINE-1 (time-management remediation)",
            "raw_screening_games_per_anchor": [sum(1 for _ in open(games_a, encoding="utf-8") if _.strip()),
                                               sum(1 for _ in open(games_b, encoding="utf-8") if _.strip())],
            "selected_batch_a_subset_games_per_anchor": 100,
            "selected_batch_a_opening_clusters": len(common),
            "registered_batch_b_opening_clusters": len(names_b),
            "batch_a_and_batch_b_opening_suites_disjoint": True,
            "cluster_score_means": [mean_a, mean_b],
            "cluster_score_sd": [sd_a, sd_b],
            "observed_opening_difficulty_correlation": rho,
            "third_anchor_full_distribution_available": False,
            "batch_b_new_suite_distribution_available": False,
        },
        "calibration": {
            "anchors": wanted,
            "published_elo": ratings,
            "published_95_ci_half_width": [float(engine["published_error"]) for engine in anchors],
            "sd_after_dividing_ci95_by_1_96": calibration_sd,
            "shared_between_batches": True,
        },
        "model": {
            "method": "delta-method multivariate-normal sensitivity model",
            "sample_units": 50,
            "paired_games_per_cluster": 2,
            "batch_match_noise_independent": "assumed because Batch A/B opening suites are disjoint",
            "calibration_error_shared_between_batches": True,
            "anchor_covariance": (
                "Observed cluster correlation is used for the first two anchors. "
                "The third anchor is assigned the larger observed marginal cluster SD; "
                "its correlation with each observed anchor is varied over 0, 0.25, and 0.5."
            ),
            "cluster_sd_inflation_grid": [1.0, 1.5, 2.0],
            "assumed_true_rating_grid": [2050, 2100, 2150, 2200],
            "bootstrap_method_for_final_evidence": "unchanged registered opening-cluster bootstrap + GLS",
            "power_definition": (
                "Both independent batch lower bounds and the combined lower bound "
                "must all be strictly greater than 2000 Elo."
            ),
            "monte_carlo_replicates_per_cell": replicates,
        },
        "scenarios": grid,
        "conclusion": (
            "The 100-game design can be well powered under optimistic variance and a large "
            "true margin, but power degrades sharply under plausible variance inflation or "
            "a true rating close to 2000. The third-anchor distribution and the disjoint "
            "Batch-B cluster distribution are unobserved. Therefore the prospective analysis "
            "is sensitivity-only, not a sufficient basis to certify dispatch. Keep the design "
            "non-dispatchable until those inputs are empirically justified or the owner accepts "
            "an explicitly exploratory campaign."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games-a", default="benches/evidence/screening-2/topple-0.1.1/games.jsonl")
    parser.add_argument("--games-b", default="benches/evidence/screening-2/topple-0.2.1/games.jsonl")
    parser.add_argument("--pool", default="benches/anchor-pool.json")
    parser.add_argument("--suite-a", default="benches/rating-openings-100-batchA.txt")
    parser.add_argument("--suite-b", default="benches/rating-openings-100-batchB.txt")
    parser.add_argument("--replicates", type=int, default=250_000)
    parser.add_argument("--out", default="benches/rating-100-power-assessment.json")
    args = parser.parse_args()
    if args.replicates < 1000:
        parser.error("--replicates must be >= 1000")
    report = analyze(args.games_a, args.games_b, args.pool, args.suite_a,
                     args.suite_b, args.replicates)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(f"power assessment: {report['status']} — wrote {args.out}; "
          "confirmatory dispatch remains blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
