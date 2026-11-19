#!/usr/bin/env python3
"""Regression tests for scripts/collect_eval_results.py.

Run: python3 scripts/test_collect_eval_results.py   (no external dependencies)

`collect_eval_results.py` re-audits each raw evidence set with
`scripts/audit_pair.py`, computes the Elo statistics with `scripts/stats.py`,
and then applies the registered decision rules:

  * EVAL-ALL vs EVAL-NONE: KEPT if the 95% CI lower bound is > 0 Elo;
  * per feature X: EVAL-ALL's point estimate compared against EVAL-NO-X.

The decision rules are registered rules about a *complete and correctly
scheduled* evidence set. An evidence set that failed its audit does not
satisfy them, so a failed audit must never produce a decision — not even
when the surviving statistics would point to "KEPT". Failed results stay in
the raw output for diagnostics.

These tests build synthetic records so they can assert on the failure paths,
which the real evidence never exhibits.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PASS = 0
FAIL = 0


def check(cond: bool, msg: str) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {msg}")


OPENINGS = [f"Opening {i}" for i in range(20)]


def build_games(tag: str, *, reversed_schedule: bool, win_rate: float = 0.75) -> list:
    """80 counted games for one pair.

    The registered schedule is 20 openings x 2 repetitions x 2 colours, and
    every (opening, repetition) slot carries BOTH colours.

    `reversed_schedule=False` builds the exact scenario a global AB/BA
    balance cannot catch: openings 0-9 are played AB only and openings 10-19
    BA only. The totals still balance 40/40 and every opening still has the
    registered multiplicity, but no opening is colour-reversed at all. The
    audit must reject it.
    """
    games = []
    for i, opening in enumerate(OPENINGS):
        for repetition in range(2):
            pairs = [("AB" if i < 10 else "BA")] if not reversed_schedule else ["AB", "BA"]
            for color_pair in pairs:
                white = tag if color_pair == "AB" else "base"
                black = "base" if color_pair == "AB" else tag
                games.append(
                    {
                        "opening": opening,
                        "repetition": repetition,
                        "color_pair": color_pair,
                        "counted": True,
                        "engine_error": False,
                        "reason": "checkmate",
                        "result": "1/2-1/2",
                        "white": white,
                        "black": black,
                    }
                )
    # Give the focus engine a clearly positive score without making it
    # degenerate (a perfect score has an unbounded Elo estimate).
    n_win = int(round(len(games) * win_rate))
    for index, game in enumerate(games):
        won = index < n_win
        focus_is_white = game["white"] == tag
        if won:
            game["result"] = "1-0" if focus_is_white else "0-1"
        else:
            game["result"] = "0-1" if focus_is_white else "1-0"
    return games


def write_pair(root: str, tag: str, games: list) -> None:
    directory = os.path.join(root, tag)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, "games.jsonl"), "w", encoding="utf-8") as handle:
        for game in games:
            handle.write(json.dumps(game) + "\n")


def run_collect(root: str) -> str:
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "collect_eval_results.py"), root],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout + proc.stderr


def main() -> int:
    tmp = tempfile.mkdtemp()
    try:
        # --- a failed audit on EVAL-ALL must not produce "KEPT" ----------
        root = os.path.join(tmp, "failed-all")
        os.makedirs(root)
        write_pair(root, "eval-all", build_games("eval-all", reversed_schedule=False))
        write_pair(
            root,
            "eval-no-mobility-taper",
            build_games("eval-no-mobility-taper", reversed_schedule=True),
        )
        out = run_collect(root)
        check("EVAL-ALL                   score" in out, "EVAL-ALL must be reported")
        check("audit=FAIL" in out, "the unreversed schedule must fail its audit")
        check("KEPT" not in out, "a failed audit must never print KEPT")
        check(
            "UNAVAILABLE (EVAL-ALL failed its audit)" in out,
            "the decision must be reported as unavailable",
        )
        check(
            "UNAVAILABLE (EVAL-ALL failed its audit)" in out.split("Per-feature")[-1],
            "the per-feature path must also refuse to decide",
        )
        # The raw results are still written for diagnostics.
        raw_path = os.path.join(root, "eval2_results.json")
        check(os.path.exists(raw_path), "the raw results must still be written")
        with open(raw_path, encoding="utf-8") as handle:
            raw = json.load(handle)
        check("EVAL-ALL" in raw, "the failed result must be kept for diagnostics")
        check(raw["EVAL-ALL"]["audit"] == "FAIL", "the audit verdict must be recorded")

        # --- a failed audit on an ablation must not decide the feature ---
        root = os.path.join(tmp, "failed-ablation")
        os.makedirs(root)
        write_pair(root, "eval-all", build_games("eval-all", reversed_schedule=True))
        write_pair(
            root,
            "eval-no-mobility-taper",
            build_games("eval-no-mobility-taper", reversed_schedule=False),
        )
        out = run_collect(root)
        check("audit=FAIL" in out, "the ablation must fail its audit")
        check(
            "UNAVAILABLE (ablation failed its audit)" in out,
            "the feature decision must be reported as unavailable",
        )
        check("RETAINED" not in out, "a failed ablation must never print RETAINED")
        check("HARMFUL" not in out, "a failed ablation must never print HARMFUL")

        # --- a clean run still applies the registered rules ---------------
        root = os.path.join(tmp, "clean")
        os.makedirs(root)
        write_pair(root, "eval-all", build_games("eval-all", reversed_schedule=True))
        write_pair(
            root,
            "eval-no-mobility-taper",
            build_games("eval-no-mobility-taper", reversed_schedule=True),
        )
        out = run_collect(root)
        check("audit=PASS" in out, "a reversed schedule must pass its audit")
        check("KEPT" in out, "a clean positive result must still print KEPT")
        check("UNAVAILABLE" not in out, "a clean run must not report UNAVAILABLE")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
