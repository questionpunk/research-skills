# Fixtures for conjoint-design

Synthetic only.

## `plan_spec.txt`

A made-up meal-kit subscription: Brand (3 levels), Meals per week (3), Delivery (2), Price per week (4), with
one prohibition (4 meals at $40). Text spec format (`../references/design-method.md`, section 1).

## `plan_design.csv`

Written by

```text
python3 scripts/conjoint_design.py design fixtures/plan_spec.txt --tasks 8 --concepts 3 --none --versions 20 --seed 7 --out fixtures/plan_design.csv
```

20 versions × 8 tasks × 3 concepts plus a `none` row per task, concepts in shuffled on-screen order. The tests regenerate it with the same seed and
compare the bytes, so a change to the generator shows up as a test failure. `conjoint-analysis` ships a copy of
this file (and of the spec) and simulates respondents' choices on it, which is how the two skills are kept in
agreement on the file format.

Expected properties (checked in `tests/`): every level of every attribute appears within 10% of perfect
balance; no task repeats a level of Brand, Meals per week or Price per week (Delivery has 2 levels for 3
concepts, so its overlap is unavoidable); no concept is 4 meals at $40; no task shows the same concept twice;
relative D-efficiency above 90% (96.5% for this seed).

Hand check of the sample size for this spec: c = 4 (Price), t = 8, a = 3, so n ≥ 500 × 4 / 24 = 83.3 → 84,
and 167 for 1,000 exposures. From the design itself the least shown level (a price, 119 times over 20
versions) appears 5.95 times per respondent, so 500 / 5.95 → 85 and 169; the study floor of 300 applies.
