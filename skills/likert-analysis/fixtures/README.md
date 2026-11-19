# Fixtures for likert-analysis

Two published examples and one synthetic file. Expected values were worked out independently of the script:
from the publication, by hand counts, by a second method (Hoyt's ANOVA for alpha, pair counting for U,
the midrank variance for the Mann-Whitney z), or by brute-force enumeration.

## 1. `kromrey_2008.input.csv`: alpha and its Feldt interval (published)

Kromrey, Romano and Hibbard (2008), SAS Global Forum paper 230-2008: 12 respondents answering 5 dichotomous
items (`10000, 11000, 11100, 11110, 11111, 00000`, twice). Their Table 1: **α = 0.833**, Feldt 95%
interval **0.616 to 0.945**. Run with `--items X1,X2,X3,X4,X5 --scale 0-1 --alpha`.

By hand: the totals are 1, 2, 3, 4, 5, 0 (twice), mean 2.5, so s²ₜ = 2 × 17.5/11 = 3.1818. Item means are
5/6, 4/6, 3/6, 2/6, 1/6 and the item variances (n − 1 = 11) 12/11 × p(1 − p) = 0.1515, 0.2424, 0.2727,
0.2424, 0.1515, sum 1.0606. α = 5/4 × (1 − 1.0606/3.1818) = 1.25 × 0.66667 = **0.8333**.
Feldt: 1 − α̂ = 0.16667; F(11, 44) has 2.5% and 97.5% quantiles 0.3283 and 2.3015, so the interval is
1 − 0.16667 × 2.3015 = **0.616** to 1 − 0.16667 × 0.3283 = **0.945**, matching the published values.

## 2. `mann_whitney_hollander_wolfe.expected.json`: Mann-Whitney (published)

Hollander and Wolfe (1973, p. 69), the example in R's `wilcox.test` help: x = 0.80, 0.83, 1.89, 1.04, 1.45,
1.38, 1.91, 1.64, 0.73, 1.46; y = 1.15, 0.88, 0.90, 0.74, 1.21. **W = U = 35**; exact one-sided ("greater")
p = 0.1272, two-sided **0.2544**. No ties, both groups under 50, so the exact null distribution applies.
Counting pairs by hand: each x beats this many y values: 0.80→1, 0.83→1, 1.89→5, 1.04→3, 1.45→5, 1.38→5,
1.91→5, 1.64→5, 0.73→0, 1.46→5, total **35**.

## 3. `engagement.input.csv`: four agree items, one reverse-worded, two teams (synthetic)

40 respondents (`north` R01-R20, `south` R21-R40), items `eng_1`-`eng_4` on 1-5. Generated once with a
seeded random generator (a latent trait plus noise; `eng_3` written reversed, as for "I often think about
quitting"), then frozen. Every third row is exported as text labels ("Strongly agree" ...) to test the
`agree5` map; one blank (R06 `eng_1`) and one `N/A` (R23 `eng_4`).

Counts per item (1 to 5):

| Item | n | 1 | 2 | 3 | 4 | 5 | Top 2 | Mean |
|---|---|---|---|---|---|---|---|---|
| eng_1 | 39 | 1 | 4 | 17 | 15 | 2 | 17 | 3.333 |
| eng_2 | 40 | 1 | 6 | 18 | 9 | 6 | 15 | 3.325 |
| eng_3 | 40 | 5 | 15 | 11 | 4 | 5 | 9 | 2.725 |
| eng_4 | 39 | 5 | 6 | 11 | 16 | 1 | 17 | 3.051 |

- eng_1 top box 17/39 = 43.6%, Wilson 95% **29.30 to 59.02** (bisection).
- Alpha on the 38 complete respondents, as answered: **−0.985** (Hoyt ANOVA gives the same). eng_3 has the
  only strongly negative corrected item-total correlation, so the script names it. With `--reverse eng_3`:
  **α = 0.882**, and every corrected item-total r is positive.
- North vs south, items as answered (`--reverse` changes only the reliability check and the scale score),
  normal approximation (`--mw-method normal`), U by counting pairs and z from the midrank variance
  n₁n₂/(N(N − 1)) · Σ(rᵢ − (N + 1)/2)²: eng_1 U = 277.5, z = 2.6365, p = 0.00838; eng_2 U = 276, p = 0.03052;
  eng_3 U = 105 (= 20 × 20 − 295, the reversed item's U), z = −2.6620, p = 0.00777; eng_4 U = 286.5,
  p = 0.00454. Run with `--scale 1-5`: the text answers ("Agree", "Neither agree nor disagree") also fit the
  7-point agree map, so the script asks for the scale. The default
  (`auto`) uses the exact conditional test here because both teams have under 50 answers; the tests check
  that method against brute-force enumeration on small samples.
