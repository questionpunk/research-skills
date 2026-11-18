#!/usr/bin/env python3
"""Regenerates the generated fixtures. Standard library only; the output is the same on every run.

  python3 fixtures/generate_fixtures.py            # rewrite the three files next to this script
  python3 fixtures/generate_fixtures.py --check    # exit 1 if a file on disk differs

Files:
  logit_pairs.input.csv        20 sets that all show items A and B; A is best in 15 (closed-form MLE)
  logit_sequential.input.csv   105 sets that all show A, B, C, with the six (best, worst) outcomes in
                               exactly the proportions the sequential model gives at u = (2 ln 2, ln 2, 0)
  synthetic.input.csv          120 simulated respondents answering from the known utilities in TRUE_UTILITIES

Nothing here imports the analysis script, so the fixtures stay independent of it. Only random.random() is
used for randomness: its sequence for a given seed is stable across Python versions, unlike shuffle/sample.
"""
import argparse
import math
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent

# (best, worst) -> number of sets, for sets that all show A, B, C. See README.md, "logit_sequential".
SEQUENTIAL_COUNTS = [("A", "B", 20), ("A", "C", 40), ("B", "A", 6), ("B", "C", 24), ("C", "A", 5), ("C", "B", 10)]

SYNTHETIC_SEED = 20261112
SYNTHETIC_RESPONDENTS = 120
# Known utilities (zero-centred) the synthetic respondents answer from.
TRUE_UTILITIES = {
    "item1": 1.6, "item2": 1.2, "item3": 0.8, "item4": 0.4, "item5": 0.0,
    "item6": -0.4, "item7": -0.8, "item8": -1.2, "item9": -1.6,
}
# Base block of a cyclic design on 9 items: adding 0..8 (mod 9) gives 9 sets of 4 in which every item
# appears 4 times.
BASE_BLOCK = (0, 1, 3, 7)


def long_rows(respondent, set_id, items, best, worst, extra=()):
    return [[respondent, *extra, str(set_id), item, "1" if item == best else "0", "1" if item == worst else "0"]
            for item in items]


def logit_pairs():
    rows = [["respondent", "set", "item", "best", "worst"]]
    outcomes = ["A"] * 15 + ["B"] * 5  # which item is best in each of the 20 sets
    for n, best in enumerate(outcomes):
        respondent, set_id = f"p{n // 2 + 1:02d}", n % 2 + 1
        worst = "B" if best == "A" else "A"
        rows.extend(long_rows(respondent, set_id, ["A", "B"], best, worst))
    return rows


def logit_sequential():
    rows = [["respondent", "set", "item", "best", "worst"]]
    outcomes = [(best, worst) for best, worst, count in SEQUENTIAL_COUNTS for _ in range(count)]
    for n, (best, worst) in enumerate(outcomes):
        respondent, set_id = f"q{n // 3 + 1:02d}", n % 3 + 1
        rows.extend(long_rows(respondent, set_id, ["A", "B", "C"], best, worst))
    return rows


def choose(rng, labels, weights):
    """Pick one label with probability proportional to its weight, using one random.random() call."""
    target = rng.random() * sum(weights)
    running = 0.0
    for label, weight in zip(labels, weights):
        running += weight
        if target < running:
            return label
    return labels[-1]


def synthetic():
    rng = random.Random(SYNTHETIC_SEED)
    names = list(TRUE_UTILITIES)
    rows = [["respondent", "segment", "set", "item", "best", "worst"]]
    for r in range(SYNTHETIC_RESPONDENTS):
        respondent = f"s{r + 1:03d}"
        segment = "new" if r % 2 == 0 else "returning"  # carries no information: same utilities
        # A random relabelling of the cyclic design for this respondent.
        order = [name for _, name in sorted((rng.random(), name) for name in names)]
        for set_index in range(len(names)):
            block = [order[(offset + set_index) % len(names)] for offset in BASE_BLOCK]
            shown = [name for _, name in sorted((rng.random(), name) for name in block)]  # screen order
            # Sequential best-then-worst choice from the known utilities.
            best = choose(rng, shown, [math.exp(TRUE_UTILITIES[name]) for name in shown])
            rest = [name for name in shown if name != best]
            worst = choose(rng, rest, [math.exp(-TRUE_UTILITIES[name]) for name in rest])
            rows.extend(long_rows(respondent, set_index + 1, shown, best, worst, extra=(segment,)))
    return rows


FILES = {
    "logit_pairs.input.csv": logit_pairs,
    "logit_sequential.input.csv": logit_sequential,
    "synthetic.input.csv": synthetic,
}


def render(rows):
    return "".join(",".join(row) + "\n" for row in rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with the files on disk instead of writing")
    args = parser.parse_args(argv)
    stale = []
    for name, build in FILES.items():
        text = render(build())
        path = HERE / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.name} ({text.count(chr(10)) - 1} rows)")
    if stale:
        print("out of date: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
