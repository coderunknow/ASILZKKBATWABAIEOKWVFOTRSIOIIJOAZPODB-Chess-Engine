#!/usr/bin/env python3
"""Regression tests for scripts/audit_pair.py.

Run: python3 scripts/test_audit_pair.py   (no external dependencies)

The audit script is the tool that checks a match shard against the registered
screening schedule: counted-game count, engine errors, uncounted records,
duplicate schedule slots, AB/BA colour balance, opening coverage, and the
candidate's score.

These tests build synthetic records rather than reading real evidence, so they
can assert on the *failure* paths -- a dropped game, a duplicated slot, a
colour imbalance, an engine error -- which the real evidence never exhibits.
"""
import json
import os
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


def make_game(opening: str, repetition: int, color_pair: str, result: str) -> dict:
    """One counted record. `color_pair` AB means the candidate is White."""
    white = "cand" if color_pair == "AB" else "base"
    black = "base" if color_pair == "AB" else "cand"
    return {
        "opening": opening,
        "white": white,
        "black": black,
        "result": result,
        "reason": "checkmate",
        "engine_error": False,
        "counted": True,
        "color_pair": color_pair,
        "repetition": repetition,
        "game_index": 0,
    }


def build_full_set() -> list:
    """The registered schedule: 20 openings x 2 repetitions x 2 colours."""
    games = []
    for op in OPENINGS:
        for rep in range(2):
            for pair in ("AB", "BA"):
                # Alternate the result so the candidate's score is 0.5.
                games.append(make_game(op, rep, pair, "1/2-1/2"))
    return games


def run_audit(games: list, expected: int = 80) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        for g in games:
            fh.write(json.dumps(g) + "\n")
        path = fh.name
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "audit_pair.py"), path, "cand", str(expected)],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout
    finally:
        os.unlink(path)


def main() -> int:
    # --- a clean, complete schedule passes -------------------------------
    games = build_full_set()
    out = run_audit(games)
    check("verdict         : PASS" in out, "complete schedule should PASS")
    check("counted         : 80" in out, "80 games should be counted")
    check("engine errors   : 0" in out, "no engine errors expected")
    check("duplicate slots : 0" in out, "no duplicate slots expected")
    check("{'AB': 40, 'BA': 40}" in out, "colour balance should be 40/40")
    check("openings        : 20 distinct" in out, "20 openings expected")
    check("score (cand) : 40.0/80 = 0.5000" in out, "score should be 0.5")

    # --- a dropped game is detected --------------------------------------
    out = run_audit(games[:-1])
    check("verdict         : INCOMPLETE/FAIL" in out, "a dropped game must fail")
    check("counted         : 79" in out, "79 games should be counted")

    # --- a duplicated slot is detected -----------------------------------
    duped = build_full_set() + [build_full_set()[0]]
    out = run_audit(duped)
    check("duplicate slots : 1" in out, "the duplicated slot must be counted")
    check("verdict         : INCOMPLETE/FAIL" in out, "a duplicated slot must fail")

    # --- an engine error is detected -------------------------------------
    broken = build_full_set()
    broken[7] = dict(broken[7])
    broken[7]["engine_error"] = True
    out = run_audit(broken)
    check("engine errors   : 1" in out, "the engine error must be counted")
    check("verdict         : INCOMPLETE/FAIL" in out, "an engine error must fail")

    # --- an uncounted record is detected ---------------------------------
    unc = build_full_set()
    unc[3] = dict(unc[3])
    unc[3]["counted"] = False
    out = run_audit(unc)
    check("uncounted       : 1" in out, "the uncounted record must be counted")
    check("verdict         : INCOMPLETE/FAIL" in out, "an uncounted record must fail")

    # --- a colour imbalance is detected ----------------------------------
    skewed = [g for g in build_full_set() if g["color_pair"] != "BA"]
    out = run_audit(skewed, expected=40)
    check("{'AB': 40}" in out, "the skew should be visible in the colour counts")
    check("verdict         : INCOMPLETE/FAIL" in out, "a colour imbalance must fail")

    # --- a missing opening is detected -----------------------------------
    partial = [g for g in build_full_set() if g["opening"] != OPENINGS[0]]
    out = run_audit(partial, expected=76)
    check("openings        : 19 distinct" in out, "19 openings should be reported")
    check("verdict         : INCOMPLETE/FAIL" in out, "a missing opening must fail")

    # --- a globally balanced but unreversed schedule is detected ----------
    # Ten openings played AB only and ten BA only: the totals balance 40/40
    # and every opening still has the registered multiplicity, yet no opening
    # is colour-reversed at all. A global balance check alone passes this.
    unreversed = []
    for i, op in enumerate(OPENINGS):
        for rep in range(4):
            pair = "AB" if i < 10 else "BA"
            unreversed.append(make_game(op, rep, pair, "1/2-1/2"))
    out = run_audit(unreversed)
    check("counted         : 80" in out, "the unreversed schedule still has 80 games")
    check("colour balance  : {'AB': 40, 'BA': 40}" in out, "the totals really do balance")
    check("unreversed slots: 80" in out, "every slot must be reported unreversed")
    check("verdict         : INCOMPLETE/FAIL" in out, "an unreversed schedule must fail")

    # --- a single missing colour leg is detected --------------------------
    one_leg = [g for g in build_full_set() if not (g["opening"] == OPENINGS[3] and g["repetition"] == 1 and g["color_pair"] == "BA")]
    out = run_audit(one_leg, expected=79)
    check("unreversed slots: 1" in out, "the single unreversed slot must be reported")
    check("verdict         : INCOMPLETE/FAIL" in out, "a missing colour leg must fail")

    # --- inconsistent repetition sets across openings are detected -------
    mixed = build_full_set()
    mixed = [g for g in mixed if not (g["opening"] == OPENINGS[5] and g["repetition"] == 1)]
    mixed += [make_game(OPENINGS[5], 2, "AB", "1/2-1/2"), make_game(OPENINGS[5], 2, "BA", "1/2-1/2")]
    out = run_audit(mixed)
    check("repetition sets : 2 distinct across 20 openings" in out, "the mixed repetition sets must be reported")
    check("verdict         : INCOMPLETE/FAIL" in out, "mixed repetition sets must fail")

    # --- the score is computed from the candidate's perspective -----------
    scored = build_full_set()
    for i, g in enumerate(scored):
        # AB => candidate is White; give the candidate every win as White and
        # every loss as Black. That is 40 wins out of 80 = 0.5 as well, so use
        # a dedicated set instead to make the perspective unambiguous.
        pass
    only_wins = [make_game(OPENINGS[0], 0, "AB", "1-0")]
    out = run_audit(only_wins, expected=1)
    check("score (cand) : 1.0/1 = 1.0000" in out, "a candidate win as White scores 1.0")
    only_loss = [make_game(OPENINGS[0], 0, "AB", "0-1")]
    out = run_audit(only_loss, expected=1)
    check("score (cand) : 0.0/1 = 0.0000" in out, "a candidate loss as White scores 0.0")
    cand_black_win = [make_game(OPENINGS[0], 0, "BA", "0-1")]
    out = run_audit(cand_black_win, expected=1)
    check("score (cand) : 1.0/1 = 1.0000" in out, "a candidate win as Black scores 1.0")

    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
