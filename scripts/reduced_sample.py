#!/usr/bin/env python3
"""Fail-closed validator for the 100-counted-game / 50-opening design.

This validates counted schedule slots, not scheduled attempts. An engine-error
attempt may be excluded when its successful replay is counted; an unadjudicated
game remains uncounted and therefore leaves a required slot missing.
"""
from __future__ import annotations


class SampleDesignError(ValueError):
    pass


def validate_counted_sample(
    games: list[dict],
    *,
    exact_games: int,
    required_openings: int,
    games_per_opening: int,
    expected_openings: list[str] | None = None,
) -> dict:
    counted = [g for g in games if g.get("counted") is True]
    if any(g.get("engine_error") for g in counted):
        raise SampleDesignError("a counted game is marked engine_error")
    if any(g.get("adjudicated") is False for g in counted):
        raise SampleDesignError("a counted game is marked unadjudicated")
    if any(g.get("result") not in ("1-0", "0-1", "1/2-1/2") for g in counted):
        raise SampleDesignError("a counted game has a non-adjudicated result")
    if len(counted) != exact_games:
        raise SampleDesignError(
            f"counted games {len(counted)} != exact requirement {exact_games}"
        )

    indices = [g.get("schedule_index") for g in counted]
    if any(type(i) is not int for i in indices):
        raise SampleDesignError("a counted game is missing an integer schedule_index")
    if sorted(indices) != list(range(exact_games)):
        raise SampleDesignError(
            f"counted schedule_index coverage must be exactly 0..{exact_games - 1}"
        )
    if len(set(indices)) != len(indices):
        raise SampleDesignError("duplicate counted schedule_index")

    by_opening: dict[str, list[dict]] = {}
    for g in counted:
        opening = g.get("opening")
        if not isinstance(opening, str) or not opening:
            raise SampleDesignError("a counted game has no opening-cluster label")
        by_opening.setdefault(opening, []).append(g)
    if len(by_opening) != required_openings:
        raise SampleDesignError(
            f"distinct counted opening clusters {len(by_opening)} != {required_openings}"
        )
    for opening, rows in by_opening.items():
        if len(rows) != games_per_opening:
            raise SampleDesignError(
                f"{opening}: counted games {len(rows)} != {games_per_opening}"
            )
        pairs = [g.get("color_pair") for g in rows]
        if games_per_opening == 2 and sorted(pairs) != ["AB", "BA"]:
            raise SampleDesignError(f"{opening}: requires exactly one AB and one BA game")

    if expected_openings is not None:
        if len(expected_openings) != required_openings or len(set(expected_openings)) != required_openings:
            raise SampleDesignError("registered opening suite does not contain the required unique labels")
        expected_set = set(expected_openings)
        if set(by_opening) != expected_set:
            missing = sorted(expected_set - set(by_opening))
            extra = sorted(set(by_opening) - expected_set)
            raise SampleDesignError(f"opening suite mismatch: missing={missing[:5]} extra={extra[:5]}")
        by_index = {g["schedule_index"]: g for g in counted}
        for index in range(exact_games):
            g = by_index[index]
            expected_opening = expected_openings[index // games_per_opening]
            expected_pair = "AB" if index % 2 == 0 else "BA"
            if g["opening"] != expected_opening or g.get("color_pair") != expected_pair:
                raise SampleDesignError(
                    f"schedule index {index}: expected {expected_opening}/{expected_pair}, "
                    f"got {g.get('opening')}/{g.get('color_pair')}"
                )

    return {
        "n_counted": len(counted),
        "n_openings": len(by_opening),
        "games_per_opening": games_per_opening,
        "schedule_indices": [0, exact_games - 1],
        "paired_color_reversals": required_openings if games_per_opening == 2 else None,
    }
