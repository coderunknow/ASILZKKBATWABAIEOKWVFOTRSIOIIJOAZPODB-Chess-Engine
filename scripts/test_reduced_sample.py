#!/usr/bin/env python3
"""Regression checks for the reduced confirmation sample validator (stdlib only)."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from reduced_sample import SampleDesignError, validate_counted_sample


def rows():
    out = []
    for oi in range(50):
        opening = f"opening-{oi:02d}"
        for pair in ("AB", "BA"):
            out.append({
                "opening": opening, "schedule_index": oi * 2 + (pair == "BA"),
                "color_pair": pair, "counted": True, "engine_error": False,
                "adjudicated": True, "result": "1/2-1/2",
            })
    return out


def rejects(data, label, **kw):
    try:
        validate_counted_sample(data, **kw)
    except SampleDesignError:
        print("PASS", label)
    else:
        raise AssertionError(label + " should be rejected")


def main():
    args = dict(exact_games=100, required_openings=50, games_per_opening=2,
                expected_openings=[f"opening-{i:02d}" for i in range(50)])
    report = validate_counted_sample(rows(), **args)
    assert report["n_counted"] == 100 and report["n_openings"] == 50
    print("PASS exact 100/50 paired design")

    bad = rows()[:-1]
    rejects(bad, "missing counted slot (including unadjudicated case)", **args)
    bad = rows()
    bad[0]["engine_error"] = True
    rejects(bad, "counted engine-error record", **args)
    bad = rows()
    bad[-1]["schedule_index"] = 0
    rejects(bad, "duplicate/missing schedule index", **args)
    bad = rows()
    bad[1]["color_pair"] = "AB"
    rejects(bad, "AB/BA reversal violation", **args)
    bad = rows()
    bad[0]["opening"] = "unregistered-opening"
    rejects(bad, "registered opening mismatch", **args)
    bad = rows()
    bad[0]["result"] = "*"
    rejects(bad, "unadjudicated result counted", **args)
    print("reduced_sample: 7/7 PASS")


if __name__ == "__main__":
    main()
