# Fixtures for csat-ces-analysis

Synthetic inputs (no respondent data) and published worked examples. Expected values were worked out
independently of the script: by hand arithmetic below, from a published table, or by a second method (Wilson
limits found by bisection on the score statistic instead of the closed form). z = 1.959964 for 95%.

Formulas (see `../references/sources.md`): Wilson interval
(p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n); Newcombe method 10 for a difference
L = d − √((p̂₁ − l₁)² + (u₂ − p̂₂)²), U = d + √((u₁ − p̂₁)² + (p̂₂ − l₂)²).

## 1. `basic.input.csv`: CSAT on 1-5, two channels, two months

Run with `--scale 1-5` (the script never guesses a numeric scale). 42 rows: 40 ratings plus one blank and
one `N/A` (both excluded and counted). Half the ratings are written
with their label (`5 - Very satisfied`), half as bare numbers, to test label-prefixed parsing.

| channel | month | ratings |
|---|---|---|
| email | 2026-09 | 5 5 5 4 4 4 3 2 1 1 |
| email | 2026-10 | 5 5 4 4 4 4 4 3 2 1 |
| chat | 2026-09 | 5 5 5 5 4 4 4 4 3 3 |
| chat | 2026-10 | 5 5 5 5 5 4 4 4 4 2 |

Overall: 5×14, 4×16, 3×4, 2×3, 1×3, n = 40. Satisfied (4-5) = 30 → **75.0%**; dissatisfied (1-2) = 6
→ 15.0%; neutral 4 → 10.0%. Mean = (70 + 64 + 12 + 6 + 3)/40 = 155/40 = **3.875**.

Wilson for 30/40: p̂ = 0.75, z²/n = 3.841459/40 = 0.0960365, denominator 1.0960365.
Centre = (0.75 + 0.0480182)/1.0960365 = 0.728095. Half-width = 1.959964 × √(0.1875/40 + 3.841459/6400)/1.0960365
= 1.959964 × √(0.0046875 + 0.00060023)/1.0960365 = 1.959964 × 0.0727166/1.0960365 = 0.130034.
Interval 0.728095 ± 0.130034 → **59.81% to 85.81%** (bisection: 59.806 to 85.813).

Mean interval: SD = 1.202295 (n − 1 = 39), t₀.₉₇₅,₃₉ = 2.022691 (t table). Margin = 2.022691 × 1.202295/√40
= 0.384513 → **3.4905 to 4.2595**.

email vs chat: 13/20 = 65% vs 17/20 = 85%, difference **−20.0 points**. Pooled p = 30/40 = 0.75,
SE = √(0.75 × 0.25 × (1/20 + 1/20)) = 0.136931, z = −0.20/0.136931 = **−1.4606**, p = **0.1441**. Expected
counts are 15 and 5 per group, none under 5, so the auto test is the z-test. Newcombe interval from the
Wilson limits (43.285, 81.881) and (63.958, 94.763): L = −0.20 − √(0.21715² + 0.09763²) = −0.43808,
U = −0.20 + √(0.16881² + 0.21042²) = 0.06976 → **−43.81 to +6.98 points**. Both sides have 20 answers, under
the small-base threshold of 100, and the test is not significant, so the verdict is **not significant**
with the small-base flag set.

2026-10 vs 2026-09: 16/20 vs 14/20, +10.0 points, z = 0.7303, p = 0.4652, interval −16.56 to +34.94.

Comments (column `comment`, filled on every third rating): dissatisfied 3 of 6, neutral 2 of 4,
satisfied 11 of 30.

## 2. Published single-proportion intervals (`wilson_newcombe_1998a.expected.json`)

Newcombe (1998a), Table I examples, Wilson score interval without continuity correction: 81/263 →
0.2553 to 0.3662; 15/148 → 0.0624 to 0.1605; 0/20 → 0 to 0.1611; 1/29 → 0.0061 to 0.1718. Run with
`--counts F,S --scale 1-2` (F failures first). The 0/20 case also checks that the lower limit is exactly 0.

## 3. `ces7.input.csv`: CES 2.0 text labels, first contact vs repeat contact

Answers are the agree labels (`Strongly agree` …), read with the `agree7` preset. Easy = 5-7.

| resolution | 7 | 6 | 5 | 4 | 3 | 2 | 1 | n | easy |
|---|---|---|---|---|---|---|---|---|---|
| first_contact | 5 | 4 | 3 | 2 | 1 | 0 | 0 | 15 | 12 |
| repeat_contact | 1 | 2 | 2 | 3 | 3 | 2 | 2 | 15 | 5 |

Means: 85/15 = 5.667 and 56/15 = 3.733; overall 141/30 = 4.70. Easy 80.0% vs 33.3%, difference
+46.67 points. Pooled p = 17/30, SE = √(0.566667 × 0.433333 × 2/15) = 0.180950, z = 0.466667/0.180950 =
**2.5791**, p = **0.0099**. Newcombe interval **+11.21 to +68.97**.

## 4. `newcombe_good_bad.input.csv`: Zendesk-style good/bad ratings, Newcombe (1998b) examples

Answers are `Good, I'm satisfied` / `Bad, I'm unsatisfied`, read with the `good-bad` preset (scale 1-2).
Agents A and B reproduce Newcombe's 56/70 vs 48/80 (method 10: **0.0524 to 0.3339**); agents C and D
reproduce 9/10 vs 3/10 (**0.1705 to 0.8090**). For C vs D the expected count of bad ratings is 4 per agent,
under 5, so the auto test is Fisher's exact test: summing the hypergeometric probabilities of every table with
margins (10, 10; 12, 8) no more likely than the observed one gives **p = 0.01977**.

## 5. CES 1.0 counts (in the tests, no file)

`--metric ces5 --counts 20,30,25,15,10`: low effort (1-2) 50/100 = 50.0% (40.38 to 59.62), high effort
(4-5) 25/100 = 25.0%, mean (20 + 60 + 75 + 60 + 50)/100 = **2.65**.

## 6. Fisher's tea-tasting table (in the tests)

Fisher (1935): 3 of 4 cups identified correctly in each direction, table [[3, 1], [1, 3]]. Two-sided exact
p = 34/70 = **0.4857** (the one-sided value is 17/70 = 0.2429).
