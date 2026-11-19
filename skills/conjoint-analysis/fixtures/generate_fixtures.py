"""Writes the synthetic fixtures of conjoint-analysis (seeded, standard library only).

python3 fixtures/generate_fixtures.py   (from the skill folder)

plan_design.csv is the design conjoint-design wrote with:
  conjoint_design.py design plan_spec.txt --tasks 8 --concepts 3 --none --versions 20 --seed 7 --out plan_design.csv
plan_responses.csv: 400 simulated respondents choosing by a known logit (TRUE_* below).
candy_stacked.csv: the published SAS "Choice of Chocolate Candies" example (fixtures/README.md).
one_attribute_stacked.csv: a fully randomized one-attribute design for the AMCE identity test.
"""
import csv
import math
import pathlib
import random

HERE = pathlib.Path(__file__).resolve().parent
TRUE_BRAND = {"FreshBox": 0.0, "GreenPlate": 0.3, "HomeChef": -0.2}
TRUE_MEALS = {"2": 0.0, "3": 0.5, "4": 0.6}
TRUE_DELIVERY = {"Weekly": 0.0, "Every two weeks": -0.4}
TRUE_PRICE_PER_DOLLAR = -0.05
TRUE_NONE = -3.0


def gumbel(rng):
    return -math.log(-math.log(rng.random()))


def plan():
    design = {}
    with open(HERE / "plan_design.csv", newline="") as handle:
        for r in csv.DictReader(handle):
            design.setdefault((r["version"], r["task"]), []).append(r)
    rng = random.Random(11)
    rows = []
    for i in range(400):
        version = str(i % 20 + 1)
        segment = "family" if i % 4 == 0 else "single"
        for t in range(1, 9):
            best, best_u = None, None
            for r in design[(version, str(t))]:
                if r["concept"] == "none":
                    u = TRUE_NONE
                else:
                    u = (TRUE_BRAND[r["Brand"]] + TRUE_MEALS[r["Meals per week"]] + TRUE_DELIVERY[r["Delivery"]]
                         + TRUE_PRICE_PER_DOLLAR * float(r["Price per week"].strip("$")))
                u += gumbel(rng)
                if best_u is None or u > best_u:
                    best, best_u = r["concept"], u
            rows.append([f"r{i + 1:03d}", version, t, best, segment])
    with open(HERE / "plan_responses.csv", "w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["respondent", "version", "task", "choice", "segment"])
        w.writerows(rows)


def candy():
    # Profiles in the SAS order: Dark, Soft, Nuts counted in binary (000 ... 111); choices 5 6 7 5 2 6 2 6 6 6.
    choices = [5, 6, 7, 5, 2, 6, 2, 6, 6, 6]
    with open(HERE / "candy_stacked.csv", "w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["respondent", "task", "concept", "Chocolate", "Center", "Nuts", "chosen"])
        for s, c in enumerate(choices, start=1):
            for k in range(1, 9):
                bits = k - 1
                w.writerow([s, 1, k, "Dark" if bits & 4 else "Milk", "Soft" if bits & 2 else "Chewy",
                            "Nuts" if bits & 1 else "No Nuts", 1 if k == c else 0])


def one_attribute():
    rng = random.Random(5)
    with open(HERE / "one_attribute_stacked.csv", "w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(["respondent", "task", "concept", "Color", "chosen"])
        for r in range(1, 61):
            for t in range(1, 5):
                colors = [rng.choice(["Blue", "Red", "Green"]) for _ in range(2)]
                u = [{"Blue": 0.0, "Red": 0.4, "Green": -0.3}[c] + gumbel(rng) for c in colors]
                pick = 0 if u[0] >= u[1] else 1
                for k, c in enumerate(colors):
                    w.writerow([f"p{r}", t, k + 1, c, 1 if k == pick else 0])


if __name__ == "__main__":
    plan()
    candy()
    one_attribute()
