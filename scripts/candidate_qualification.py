#!/usr/bin/env python3
"""Candidate-bound preregistration and evidence-path helpers.

This module only validates the committed design and derives collision-safe
paths. It does not dispatch games or grant qualification/dispatch authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

DESIGN_PATH = "benches/candidate-qualification.json"
CANDIDATE_SHA256 = "0a9ddd9151dcd810d768708ddad1af7a85b93eca727749fd65b5c9e7cbca71b5"
SCREENING_ANCHORS = ("topple-0.1.1", "topple-0.2.1", "akimbo-0.1.1")
SUITES = {
    "A": (
        "benches/rating-openings-100-batchA.txt",
        "5abdcdbddec0f22d7e6eff8974ee402363c8c3df318b8110d7204adf69f5c1df",
        20261119,
    ),
    "B": (
        "benches/rating-openings-100-batchB.txt",
        "ccb4901742eca25b0b10f1a3c9fdfc17b2967a1939c2d7e466c2c5495b6d4253",
        20261120,
    ),
}
SELF_SUITE = (
    "benches/rating-openings-batchA.txt",
    "2c4a54d8a16f36d597cb2378ff74c1faafc636568647a257313274bd0969fc96",
)
SELF_BOOTSTRAP_SEEDS = tuple(range(20261114, 20261130))


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_design(path: str = DESIGN_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        design = json.load(handle)
    validate_design(design)
    return design


def validate_design(design: dict[str, Any]) -> None:
    candidate = design.get("candidate", {})
    if candidate.get("engine_sha256") != CANDIDATE_SHA256:
        raise ValueError("candidate qualification design is bound to the wrong binary SHA-256")
    if design.get("status") != "PREREGISTERED_NOT_DISPATCHED":
        raise ValueError("candidate qualification design must remain not-dispatched until evidence exists")
    tc = design.get("time_control", {})
    if tc != {
        "mode": "clock", "period_moves": 40, "period_seconds": 900.0,
        "increment_seconds": 0.0, "tc_policy": "add", "ponder": False,
    }:
        raise ValueError("candidate design time control differs from registered 40/15")

    screening = design.get("screening", {})
    if tuple(screening.get("anchors", ())) != SCREENING_ANCHORS:
        raise ValueError("candidate screening anchors differ from the preregistered three-anchor set")
    if screening.get("opening_clusters_per_batch") != 50 \
            or screening.get("paired_repetitions_per_cluster") != 1 \
            or screening.get("games_per_cluster") != 2 \
            or screening.get("shards_per_anchor_batch") != 50 \
            or screening.get("counted_games_per_anchor_batch") != 100 \
            or screening.get("anchor_batch_cells") != 6 \
            or screening.get("total_counted_games") != 600:
        raise ValueError("candidate screening must be exactly 600 counted games in six 100-game cells")
    if screening.get("evidence_class") != "selection-only":
        raise ValueError("candidate screening evidence must remain selection-only")
    batches = screening.get("batches", {})
    for batch, (suite, suite_sha, seed) in SUITES.items():
        item = batches.get(batch, {})
        if (item.get("suite"), item.get("suite_sha256"), item.get("dispatch_seed")) != (suite, suite_sha, seed):
            raise ValueError(f"candidate screening Batch {batch} registration drift")
    if batches.get("A", {}).get("suite_sha256") == batches.get("B", {}).get("suite_sha256"):
        raise ValueError("candidate screening suites must be distinct")

    control = design.get("self_control", {})
    if control.get("evidence_class") != "candidate-null-control" \
            or control.get("white_engine") != "flawless" \
            or control.get("black_engine") != "flawless":
        raise ValueError("candidate self-control must be the candidate binary against itself")
    if (control.get("suite"), control.get("suite_sha256")) != SELF_SUITE:
        raise ValueError("candidate self-control suite identity drift")
    if control.get("opening_clusters") != 60 \
            or control.get("paired_repetitions_per_cluster") != 2 \
            or control.get("games_per_cluster") != 4 \
            or control.get("shards") != 60 \
            or control.get("total_counted_games") != 240:
        raise ValueError("candidate self-control must be exactly 240 games across 60 clusters")
    if tuple(control.get("bootstrap_seeds", ())) != SELF_BOOTSTRAP_SEEDS:
        raise ValueError("candidate self-control bootstrap seed set differs from preregistration")
    separation = design.get("separation", {})
    if separation.get("screening_is_confirmatory") is not False \
            or separation.get("screening_may_be_reused_as_gate_evidence") is not False \
            or separation.get("historical_engine1_self_control_reusable") is not False \
            or separation.get("valid_anchor_vs_anchor_control_reusable") is not True:
        raise ValueError("candidate evidence-separation controls are incomplete")


def candidate_evidence_path(candidate_sha256: str, purpose: str, *, batch: str = "", anchor: str = "") -> str:
    """Derive the only canonical path for a registered candidate evidence class."""
    if candidate_sha256 != CANDIDATE_SHA256 or not re.fullmatch(r"[0-9a-f]{64}", candidate_sha256):
        raise ValueError("candidate evidence path requires the preregistered candidate SHA-256")
    root = f"benches/evidence/candidates/{candidate_sha256}"
    if purpose == "candidate-screening":
        if batch not in SUITES or anchor not in SCREENING_ANCHORS:
            raise ValueError("candidate screening path requires a registered batch and anchor")
        return f"{root}/screening/batch{batch}/{anchor}"
    if purpose == "candidate-self-control":
        if batch or anchor not in ("", "candidate-self-control"):
            raise ValueError("candidate self-control path does not take a batch or external anchor")
        return f"{root}/self-control"
    raise ValueError(f"unsupported candidate evidence purpose {purpose!r}")


def verify_suite_files(repo_root: str = ".") -> None:
    attributes_path = os.path.join(repo_root, ".gitattributes")
    try:
        with open(attributes_path, encoding="utf-8") as handle:
            attributes = {line.strip() for line in handle if line.strip() and not line.lstrip().startswith("#")}
    except OSError as exc:
        raise ValueError("candidate evidence requires committed LF line-ending rules") from exc
    if "/benches/evidence/candidates/** text eol=lf" not in attributes:
        raise ValueError("candidate evidence must have a committed LF line-ending rule for stable raw hashes")
    for path, expected, _seed in SUITES.values():
        if sha256_file(os.path.join(repo_root, path)) != expected:
            raise ValueError(f"{path}: SHA-256 differs from candidate preregistration")
    if sha256_file(os.path.join(repo_root, SELF_SUITE[0])) != SELF_SUITE[1]:
        raise ValueError(f"{SELF_SUITE[0]}: SHA-256 differs from candidate self-control preregistration")


def main() -> int:
    design = load_design()
    verify_suite_files()
    print(f"candidate design valid; status={design['status']}; games=600 screening + 240 self-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
