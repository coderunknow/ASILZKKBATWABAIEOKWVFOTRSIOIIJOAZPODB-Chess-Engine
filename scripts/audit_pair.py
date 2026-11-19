#!/usr/bin/env python3
"""Audit a match shard directory against the registered screening schedule.

Checks, for one pair:
  * the number of counted games, and that it equals the registered 80;
  * that there are no engine errors and no uncounted/duplicate games;
  * exact AB/BA colour balance (40/40);
  * that every (opening, repetition) slot carries BOTH colours, so each
    opening is genuinely colour-reversed and not merely balanced in total;
  * that all 20 openings are covered, each with the registered multiplicity
    and the same repetition set;
  * the score from the candidate's perspective.

Usage: audit_pair.py <games.jsonl> <candidate-name> [expected-games]
"""

import collections
import json
import sys


def main() -> int:
    path = sys.argv[1]
    focus = sys.argv[2]
    expected = int(sys.argv[3]) if len(sys.argv) > 3 else 80

    games = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                games.append(json.loads(line))

    counted = [g for g in games if g.get("counted")]
    errors = [g for g in games if g.get("engine_error")]
    uncounted = [g for g in games if not g.get("counted")]

    # A schedule slot is (opening, repetition, colour assignment). Playing the
    # same slot twice means a duplicate; the runner sets replay_of_schedule_index.
    slots = collections.Counter(
        (g.get("opening"), g.get("repetition"), g.get("color_pair")) for g in counted
    )
    duplicates = {k: v for k, v in slots.items() if v > 1}

    # The registered schedule requires an exact colour reversal for every
    # (opening, repetition) slot. A global AB/BA balance is NOT sufficient:
    # ten openings played AB-only and ten BA-only balance globally while
    # reversing no opening at all. Check the actual slots, not the totals.
    slot_colours = collections.defaultdict(set)
    opening_reps = collections.defaultdict(set)
    for g in counted:
        slot_colours[(g.get("opening"), g.get("repetition"))].add(g.get("color_pair"))
        opening_reps[g.get("opening")].add(g.get("repetition"))

    unreversed = {k: v for k, v in slot_colours.items() if v != {"AB", "BA"}}
    rep_sets = {frozenset(v) for v in opening_reps.values()}

    colours = collections.Counter(g.get("color_pair") for g in counted)
    openings = collections.Counter(g.get("opening") for g in counted)

    score = 0.0
    for g in counted:
        res = (g.get("result") or "").strip()
        w, b = g.get("white"), g.get("black")
        if res == "1/2-1/2":
            score += 0.5
        elif res == "1-0":
            score += 1.0 if w == focus else 0.0
        elif res == "0-1":
            score += 1.0 if b == focus else 0.0

    print(f"file            : {path}")
    print(f"games in file   : {len(games)}")
    print(f"counted         : {len(counted)} (expected {expected})")
    print(f"engine errors   : {len(errors)}")
    print(f"uncounted       : {len(uncounted)}")
    print(f"duplicate slots : {len(duplicates)}")
    print(f"unreversed slots: {len(unreversed)}")
    print(f"colour balance  : {dict(colours)}")
    print(f"openings        : {len(openings)} distinct, counts {sorted(set(openings.values()))}")
    print(f"repetition sets : {len(rep_sets)} distinct across {len(openings)} openings")
    print(f"score ({focus}) : {score}/{len(counted)} = {score / len(counted):.4f}")

    # The registered schedule requires an exact AB/BA colour reversal, so a
    # colour imbalance is a failure in its own right and not just a
    # cosmetic note.
    balanced = colours.get("AB", 0) == colours.get("BA", 0)

    ok = (
        len(counted) == expected
        and not errors
        and not uncounted
        and not duplicates
        and balanced
        and not unreversed
        and len(rep_sets) == 1
        and len(openings) == 20
        and set(openings.values()) == {expected // 20}
    )
    print("verdict         : " + ("PASS" if ok else "INCOMPLETE/FAIL"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
