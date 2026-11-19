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



def sha256_jsonl_records(path: str) -> str:
    """Hash UTF-8 JSONL with line endings normalized to LF for cross-OS stability.

    Git may check out tracked JSONL as CRLF on Windows. The manifest digest is
    created on Linux from LF bytes. Universal-newline decoding preserves all
    record content and ordering while normalizing only record terminators.
    """
    digest = hashlib.sha256()
    with open(path, "r", encoding="utf-8", newline=None) as handle:
        for chunk in iter(lambda: handle.read(1 << 20), ""):
            digest.update(chunk.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))
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
    if manifest.get("merged_sha256") != sha256_jsonl_records(games_path):
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
    cluster_sd_override: list[float] | None = None,
    correlation_override: list[list[float]] | None = None,
    score_covariances: list[list[list[float]]] | None = None,
) -> dict:
    scores = [1.0 / (1.0 + 10.0 ** ((rating - theta) / 400.0)) for rating in ratings]
    slopes = [400.0 / (math.log(10.0) * p * (1.0 - p)) for p in scores]
    cluster_sd = cluster_sd_override or [first_two_sd[0], first_two_sd[1], max(first_two_sd)]
    if len(cluster_sd) != 3:
        raise ValueError("power scenario requires exactly three anchor cluster SDs")
    cluster_sd = [x * inflation for x in cluster_sd]
    corr = correlation_override or [
        [1.0, first_two_corr, third_corr],
        [first_two_corr, 1.0, third_corr],
        [third_corr, third_corr, 1.0],
    ]
    if len(corr) != 3 or any(len(row) != 3 for row in corr):
        raise ValueError("power scenario requires a 3x3 opening-correlation matrix")
    if score_covariances is not None:
        if len(score_covariances) != 2 or any(
            len(matrix) != 3 or any(len(row) != 3 for row in matrix)
            for matrix in score_covariances
        ):
            raise ValueError("candidate power requires separate 3x3 score covariance matrices for both batches")
        match_batches = [[
            [score_covariances[batch][i][j] * slopes[i] * slopes[j]
             * inflation * inflation / clusters for j in range(3)]
            for i in range(3)
        ] for batch in range(2)]
    else:
        match = [
            [corr[i][j] * cluster_sd[i] * cluster_sd[j] * slopes[i] * slopes[j] / clusters
             for j in range(3)]
            for i in range(3)
        ]
        match_batches = [match, match]
    match_average = [[(match_batches[0][i][j] + match_batches[1][i][j]) / 2.0
                      for j in range(3)] for i in range(3)]
    calibration = [
        [calibration_sd[i] ** 2 if i == j else 0.0 for j in range(3)]
        for i in range(3)
    ]
    total = [[match_average[i][j] + calibration[i][j] for j in range(3)] for i in range(3)]
    inv_total = invert(total)
    row_sums = [sum(row) for row in inv_total]
    denominator = sum(row_sums)
    weights = [x / denominator for x in row_sums]
    var_match_a = quadratic(weights, match_batches[0])
    var_match_b = quadratic(weights, match_batches[1])
    var_cal = quadratic(weights, calibration)
    z95 = 1.959963984540054
    se_batch_a = math.sqrt(var_match_a + var_cal)
    se_batch_b = math.sqrt(var_match_b + var_cal)
    se_combined = math.sqrt((var_match_a + var_match_b) / 4.0 + var_cal)
    half_batch_a = z95 * se_batch_a
    half_batch_b = z95 * se_batch_b
    half_combined = z95 * se_combined

    seed = (20261116 + round(theta * 10) + round(inflation * 100)
            + round(third_corr * 100)) & 0xFFFFFFFF
    rng = DeterministicRng(seed)
    sd_match_a = math.sqrt(var_match_a)
    sd_match_b = math.sqrt(var_match_b)
    sd_cal = math.sqrt(var_cal)
    passed_all = 0
    passed_batch_a = 0
    passed_batch_b = 0
    passed_combined = 0
    for _ in range(replicates):
        common_cal = sd_cal * rng.normal()
        noise_a = sd_match_a * rng.normal()
        noise_b = sd_match_b * rng.normal()
        a_pass = theta + common_cal + noise_a - half_batch_a > 2000.0
        b_pass = theta + common_cal + noise_b - half_batch_b > 2000.0
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
        "assumed_cluster_score_sd": cluster_sd,
        "assumed_opening_correlation_matrix": corr,
        "batch_a_match_se_elo": sd_match_a,
        "batch_b_match_se_elo": sd_match_b,
        "shared_calibration_se_elo": sd_cal,
        "batch_a_95_half_width_elo": half_batch_a,
        "batch_b_95_half_width_elo": half_batch_b,
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


def read_candidate_screening_cell(
    games_path: str, *, batch: str, anchor: str, suite_path: str,
    suite_sha256: str, dispatch_seed: int, pool: dict[str, dict], candidate_sha256: str,
) -> dict:
    """Verify one exact candidate-qualified 100-game screening cell."""
    from candidate_qualification import candidate_evidence_path

    expected_relative = candidate_evidence_path(
        candidate_sha256, "candidate-screening", batch=batch, anchor=anchor
    )
    normalized = os.path.normpath(games_path)
    expected_suffix = os.path.normpath(os.path.join(expected_relative, "games.jsonl"))
    if normalized != expected_suffix and not normalized.endswith(os.sep + expected_suffix):
        raise ValueError(f"{games_path}: not at its candidate-qualified screening path")
    manifest_path = os.path.join(os.path.dirname(games_path), "manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    anchor_entry = pool.get(anchor)
    if anchor_entry is None:
        raise ValueError(f"{anchor}: absent from the frozen anchor pool")
    expected_fields = {
        "batch": batch,
        "anchor": anchor,
        "engine_sha256": candidate_sha256,
        "anchor_sha256": anchor_entry["sha256"],
        "opening_suite_sha256": suite_sha256,
        "time_control": {"mode": "clock", "period_moves": 40, "period_seconds": 900.0},
        "evidence_purpose": "candidate-screening",
        "candidate_sha256": candidate_sha256,
        "dispatch_seed": dispatch_seed,
        "repetitions": 1,
        "evidence_class": "selection-only",
        "n_counted": 100,
        "n_shards": 50,
    }
    observed = {key: manifest.get(key) for key in expected_fields}
    if observed != expected_fields:
        raise ValueError(f"{manifest_path}: candidate screening identity/count mismatch: {observed!r}")
    target = manifest.get("target_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", target):
        raise ValueError(f"{manifest_path}: missing full frozen target commit")
    if manifest.get("merged_sha256") != sha256_file(games_path):
        raise ValueError(f"{manifest_path}: merged_sha256 does not match games.jsonl")

    names = read_suite_names(suite_path)
    if sha256_file(suite_path) != suite_sha256:
        raise ValueError(f"{suite_path}: suite hash differs from candidate preregistration")
    expected_shards = {f"candidate-screening-{batch}-{anchor}-{i}" for i in range(50)}
    shard_ids = manifest.get("shard_ids")
    if not isinstance(shard_ids, list) or set(shard_ids) != expected_shards or len(shard_ids) != 50:
        raise ValueError(f"{manifest_path}: candidate screening shard IDs are incomplete or unexpected")

    records = []
    with open(games_path, encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, 1):
            if not raw.strip():
                continue
            try:
                records.append(json.loads(raw))
            except ValueError as exc:
                raise ValueError(f"{games_path}:{line_no}: malformed JSON record") from exc
    if manifest.get("n_attempts") != len(records):
        raise ValueError(f"{manifest_path}: n_attempts does not match raw games")
    if manifest.get("n_engine_errors") != sum(bool(g.get("engine_error")) for g in records):
        raise ValueError(f"{manifest_path}: n_engine_errors does not match raw games")
    if manifest.get("n_unadjudicated") != sum(g.get("adjudicated") is False for g in records):
        raise ValueError(f"{manifest_path}: n_unadjudicated does not match raw games")

    counted: dict[int, dict] = {}
    attempts: dict[int, dict[int, dict]] = {}
    for game in records:
        index = game.get("schedule_index")
        replay = game.get("replay_depth")
        if type(index) is not int or not 0 <= index < 100 or type(replay) is not int or replay not in (0, 1):
            raise ValueError(f"{games_path}: invalid candidate screening schedule/replay identity")
        if (type(game.get("counted")) is not bool
                or type(game.get("engine_error")) is not bool
                or type(game.get("adjudicated")) is not bool):
            raise ValueError(f"{games_path}: attempt at slot {index} lacks boolean counted/error/adjudication provenance")
        per_slot = attempts.setdefault(index, {})
        if replay in per_slot:
            raise ValueError(f"{games_path}: duplicate candidate screening attempt {(index, replay)}")
        per_slot[replay] = game
        replay_of = game.get("replay_of_schedule_index")
        if ((replay == 0 and replay_of is not None)
                or (replay == 1 and (type(replay_of) is not int or replay_of != index))):
            raise ValueError(f"{games_path}: inconsistent replay provenance at schedule index {index}")
        expected_pair = "AB" if index % 2 == 0 else "BA"
        expected_white, expected_black = (("flawless", anchor) if expected_pair == "AB"
                                          else (anchor, "flawless"))
        if type(game.get("repetition")) is not int:
            raise ValueError(f"{games_path}: attempt at slot {index} has non-integer repetition identity")
        if (game.get("color_pair") != expected_pair or game.get("repetition") != 0
                or str(game.get("white", "")).casefold() != expected_white
                or str(game.get("black", "")).casefold() != expected_black):
            raise ValueError(f"{games_path}: attempt at slot {index} has incorrect seat or engine identity")
        if game.get("opening") != names[index // 2]:
            raise ValueError(f"{games_path}: attempt at slot {index} does not match the registered suite order")
        if game.get("_shard_id") != f"candidate-screening-{batch}-{anchor}-{index // 2}":
            raise ValueError(f"{games_path}: attempt at slot {index} has incorrect shard identity")
        if game.get("counted") is not True:
            if not game.get("engine_error"):
                raise ValueError(f"{games_path}: uncounted non-error attempt in candidate screening")
            continue
        if index in counted or game.get("engine_error") or game.get("adjudicated") is not True:
            raise ValueError(f"{games_path}: duplicate or not-explicitly-adjudicated counted schedule index {index}")
        if game.get("result") not in ("1-0", "0-1", "1/2-1/2"):
            raise ValueError(f"{games_path}: counted slot {index} has invalid result")
        counted[index] = game
    if set(counted) != set(range(100)):
        raise ValueError(f"{games_path}: expected exactly 100 counted schedule slots")
    for index in range(100):
        initial = attempts.get(index, {}).get(0)
        replay = attempts.get(index, {}).get(1)
        if initial is None:
            raise ValueError(f"{games_path}: slot {index} has no initial attempt")
        if initial.get("engine_error"):
            if initial.get("counted") is True or replay is None:
                raise ValueError(f"{games_path}: failed initial attempt at slot {index} lacks a valid replay")
            if replay.get("engine_error") or replay.get("counted") is not True:
                raise ValueError(f"{games_path}: replay at slot {index} did not yield the counted result")
        elif initial.get("counted") is not True or replay is not None:
            raise ValueError(f"{games_path}: slot {index} has an invalid or unnecessary replay")

    clusters: dict[str, list[float]] = {name: [] for name in names}
    for index, game in counted.items():
        if game["color_pair"] == "AB":
            score = 1.0 if game["result"] == "1-0" else 0.0 if game["result"] == "0-1" else 0.5
        else:
            score = 1.0 if game["result"] == "0-1" else 0.0 if game["result"] == "1-0" else 0.5
        clusters[game["opening"]].append(score)
    if any(len(scores) != 2 for scores in clusters.values()):
        raise ValueError(f"{games_path}: every registered opening needs exactly one AB/BA pair")
    return {
        "manifest": manifest,
        "cluster_scores": {name: sum(scores) / len(scores) for name, scores in clusters.items()},
        "n_attempts": len(records),
        "n_counted": len(counted),
        "target_commit": target,
    }


def analyze_candidate(
    *, evidence_root: str, pool_path: str, suite_a: str, suite_b: str,
    self_control_report: str, candidate_sha256: str, replicates: int,
) -> dict:
    """Candidate-specific empirical sensitivity; always non-authorizing.

    It requires all six preregistered screening cells and a robust candidate
    self-control certificate. Screening estimates remain selection-only; the
    result is a prospective sensitivity diagnostic and is BLOCKED pending the
    separately registered decision rule and independent review.
    """
    from candidate_qualification import CANDIDATE_SHA256, SCREENING_ANCHORS, SUITES, load_design

    if candidate_sha256 != CANDIDATE_SHA256:
        raise ValueError("candidate power analysis SHA differs from preregistered candidate")
    design = load_design("benches/candidate-qualification.json")
    with open(pool_path, encoding="utf-8") as handle:
        pool_obj = json.load(handle)
    pool = {entry["key"]: entry for entry in pool_obj["engines"]}
    suite_paths = {"A": suite_a, "B": suite_b}
    names_a = read_suite_names(suite_a)
    names_b = read_suite_names(suite_b)
    if set(names_a) & set(names_b):
        raise ValueError("candidate Batch A and Batch B opening suites are not disjoint")
    cells: dict[tuple[str, str], dict] = {}
    target_commits: set[str] = set()
    for batch, (registered_suite, suite_sha, dispatch_seed) in SUITES.items():
        if os.path.normpath(suite_paths[batch]) != os.path.normpath(registered_suite):
            # Allow absolute paths for tests and local workflows, but require
            # the exact bytes and basename of the registered suite.
            if os.path.basename(suite_paths[batch]) != os.path.basename(registered_suite):
                raise ValueError(f"candidate Batch {batch} suite path differs from preregistration")
        for anchor in SCREENING_ANCHORS:
            games_path = os.path.join(evidence_root, "batch" + batch, anchor, "games.jsonl")
            cell = read_candidate_screening_cell(
                games_path, batch=batch, anchor=anchor, suite_path=suite_paths[batch],
                suite_sha256=suite_sha, dispatch_seed=dispatch_seed, pool=pool,
                candidate_sha256=candidate_sha256,
            )
            cells[(batch, anchor)] = cell
            target_commits.add(cell["target_commit"])
    if len(target_commits) != 1:
        raise ValueError("candidate screening cells do not share one exact frozen target commit")

    with open(self_control_report, encoding="utf-8") as handle:
        control = json.load(handle)
    from candidate_qualification import candidate_evidence_path, SELF_BOOTSTRAP_SEEDS
    expected_control_path = os.path.join(
        candidate_evidence_path(candidate_sha256, "candidate-self-control"), "games.jsonl"
    )
    certificate_path = os.path.normpath(control.get("evidence_path", ""))
    certificate_seed_rows = control.get("registered_seed_results", {}).get("per_seed", [])
    control_games_path = control.get("evidence_path", "")
    control_manifest_path = os.path.join(os.path.dirname(control_games_path), "manifest.json")
    if not os.path.isfile(control_games_path) or not os.path.isfile(control_manifest_path):
        raise ValueError("candidate self-control certificate points to missing committed evidence")
    if (control.get("games_sha256") != sha256_file(control_games_path)
            or control.get("evidence_manifest_sha256") != sha256_file(control_manifest_path)):
        raise ValueError("candidate self-control certificate hashes do not match its committed evidence")
    if (control.get("status") != "PASS"
            or control.get("candidate_sha256") != candidate_sha256
            or control.get("seed_robust") is not True
            or control.get("all_registered_seeds_pass") is not True
            or control.get("counted_games") != 240
            or control.get("eligible_for_confirmatory_dispatch") is not False
            or not certificate_path.endswith(os.path.normpath(expected_control_path))
            or control.get("registered_seed_results", {}).get("seeds") != list(SELF_BOOTSTRAP_SEEDS)
            or len(certificate_seed_rows) != len(SELF_BOOTSTRAP_SEEDS)
            or not all(row.get("pass") is True for row in certificate_seed_rows)
            or not re.fullmatch(r"[0-9a-f]{64}", control.get("games_sha256", ""))
            or not re.fullmatch(r"[0-9a-f]{64}", control.get("evidence_manifest_sha256", ""))):
        raise ValueError("candidate self-control certificate is absent, non-robust, or not a unanimous PASS")
    if control.get("target_commit") != next(iter(target_commits)):
        raise ValueError("candidate self-control and screening target commits differ")

    with open(pool_path, encoding="utf-8") as handle:
        pool_obj = json.load(handle)
    wanted = list(SCREENING_ANCHORS)
    anchors = [next(entry for entry in pool_obj["engines"] if entry["key"] == key) for key in wanted]
    ratings = [float(entry["published_elo"]) for entry in anchors]
    calibration_sd = [float(entry["published_error"]) / 1.96 for entry in anchors]
    pooled_scores: dict[str, list[float]] = {key: [] for key in wanted}
    batch_statistics = {}
    cell_summaries = {}
    correlations = []
    score_covariances = []
    batch_means = {}
    for batch in ("A", "B"):
        names = list(cells[(batch, wanted[0])]["cluster_scores"])
        score_vectors = [[cells[(batch, key)]["cluster_scores"][name] for name in names] for key in wanted]
        batch_means[batch] = [sum(vector) / len(vector) for vector in score_vectors]
        batch_sd = [mean_sd(vector)[1] for vector in score_vectors]
        if any(sd <= 0 for sd in batch_sd):
            raise ValueError(f"candidate Batch {batch} has a zero-variance anchor; empirical covariance is not estimable")
        for index, key in enumerate(wanted):
            cell_summaries[f"{batch}/{key}"] = {
                "opening_clusters": len(score_vectors[index]),
                "cluster_score_mean": batch_means[batch][index],
                "cluster_score_sd": batch_sd[index],
            }
            pooled_scores[key].extend(score_vectors[index])
        corr = [[1.0 if i == j else sample_correlation(score_vectors[i], score_vectors[j])
                 for j in range(3)] for i in range(3)]
        covariance = [[
            sum((score_vectors[i][k] - batch_means[batch][i])
                * (score_vectors[j][k] - batch_means[batch][j]) for k in range(len(names)))
            / (len(names) - 1)
            for j in range(3)] for i in range(3)]
        correlations.append(corr)
        score_covariances.append(covariance)
        batch_statistics[batch] = {
            "cluster_score_mean": batch_means[batch],
            "cluster_score_sd": batch_sd,
            "opening_correlation_matrix": corr,
        }
    pooled_sd = [mean_sd(pooled_scores[key])[1] for key in wanted]
    corr_matrix = [[sum(matrix[i][j] for matrix in correlations) / 2.0 for j in range(3)]
                   for i in range(3)]
    for i in range(3):
        corr_matrix[i][i] = 1.0

    scenarios = []
    for theta in (2050.0, 2100.0, 2150.0, 2200.0):
        for inflation in (1.0, 1.5, 2.0):
            scenarios.append(scenario(
                theta, inflation, corr_matrix[0][2], ratings=ratings,
                calibration_sd=calibration_sd, first_two_sd=pooled_sd[:2],
                first_two_corr=corr_matrix[0][1], clusters=50, replicates=replicates,
                cluster_sd_override=pooled_sd, correlation_override=corr_matrix,
                score_covariances=score_covariances,
            ))

    return {
        "design": "rating-100-v1",
        "date": "2026-11-18",
        "engine_sha256": candidate_sha256,
        "screening_engine_scope": "Candidate-specific screening distributions; selection-only and not gate evidence.",
        "status": "BLOCKED",
        "eligible_for_confirmatory_dispatch": False,
        "opening_suites": {
            "amended_a": suite_a,
            "amended_b": suite_b,
            "batch_a_sha256": SUITES["A"][1],
            "batch_b_sha256": SUITES["B"][1],
        },
        "screening_inputs": {
            "source": {f"{batch}/{anchor}": cells[(batch, anchor)]["manifest"]["merged_sha256"]
                       for batch in ("A", "B") for anchor in wanted},
            "candidate_engine_sha256": candidate_sha256,
            "target_commit": next(iter(target_commits)),
            "counted_games": 600,
            "cells": cell_summaries,
            "cross_anchor_statistics_by_batch": batch_statistics,
            "batch_a_and_batch_b_opening_suites_disjoint": True,
            "self_control_certificate_sha256": sha256_file(self_control_report),
            "self_control_seed_robust": True,
            "self_control_all_registered_seeds_pass": True,
            "self_control_counted_games": 240,
            "third_anchor_full_distribution_available": True,
            "batch_b_new_suite_distribution_available": True,
        },
        "calibration": {
            "anchors": wanted,
            "published_elo": ratings,
            "published_95_ci_half_width": [float(entry["published_error"]) for entry in anchors],
            "sd_after_dividing_ci95_by_1.96": calibration_sd,
            "shared_between_batches": True,
        },
        "model": {
            "method": "candidate-evidence empirical cluster SD/correlation sensitivity with multivariate-normal GLS approximation",
            "sample_units": 50,
            "paired_games_per_cluster": 2,
            "cluster_sd_inflation_grid": [1.0, 1.5, 2.0],
            "assumed_true_rating_grid": [2050, 2100, 2150, 2200],
            "bootstrap_method_for_final_evidence": "unchanged registered opening-cluster bootstrap + GLS",
            "power_definition": "Both batch lower bounds and combined lower bound strictly exceed 2,000 Elo.",
            "monte_carlo_replicates_per_cell": replicates,
            "limitations": [
                "The true candidate rating remains unknown and is evaluated over a sensitivity grid.",
                "Normal-approximation power is a diagnostic, not an evidence-backed PASS.",
                "An independently reviewed prospective decision rule and approval are required before dispatch.",
            ],
        },
        "scenarios": scenarios,
        "conclusion": "Candidate-specific empirical inputs are present, but this diagnostic never grants power PASS or dispatch authority; independent review and an explicit preregistered decision rule remain required.",
        "approval": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games-a", default="benches/evidence/screening-2/topple-0.1.1/games.jsonl")
    parser.add_argument("--games-b", default="benches/evidence/screening-2/topple-0.2.1/games.jsonl")
    parser.add_argument("--pool", default="benches/anchor-pool.json")
    parser.add_argument("--suite-a", default="benches/rating-openings-100-batchA.txt")
    parser.add_argument("--suite-b", default="benches/rating-openings-100-batchB.txt")
    parser.add_argument("--replicates", type=int, default=250_000)
    parser.add_argument("--candidate-specific", action="store_true",
                        help="analyze the six preregistered candidate screening cells; never authorizes dispatch")
    parser.add_argument("--candidate-sha256", default="0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5")
    parser.add_argument("--candidate-evidence-root", default=(
        "benches/evidence/candidates/0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5/screening"))
    parser.add_argument("--self-control-report", default=(
        "benches/evidence/candidates/0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5/self-control/certificate.json"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    if args.replicates < 1000:
        parser.error("--replicates must be >= 1000")
    if args.candidate_specific:
        try:
            report = analyze_candidate(
                evidence_root=args.candidate_evidence_root, pool_path=args.pool,
                suite_a=args.suite_a, suite_b=args.suite_b,
                self_control_report=args.self_control_report,
                candidate_sha256=args.candidate_sha256, replicates=args.replicates,
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            parser.error(f"candidate-specific power analysis BLOCKED: {exc}")
        output = args.out or "benches/candidate-rating-100-power-assessment.json"
    else:
        report = analyze(args.games_a, args.games_b, args.pool, args.suite_a,
                         args.suite_b, args.replicates)
        output = args.out or "benches/rating-100-power-assessment.json"
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(f"power assessment: {report['status']} — wrote {output}; "
          "confirmatory dispatch remains blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
