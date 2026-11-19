# Fixtures for gabor-granger-analysis

Synthetic inputs (no respondent data) and one published example. Expected values were worked out by hand
below, independently of the script. z = 1.959964 for 95%.

## 1. SurveyMonkey published example (`--counts`)

From SurveyMonkey's Gabor-Granger guide (`../references/sources.md`, source 14): 200 respondents; would buy at
$10, $15, $20, $25, $30 = 190, 164, 118, 74, 36. Shares 95%, 82%, 59%, 37%, 18%. Revenue index = price x
share = 9.5, 12.3, 11.8, 9.25, 5.4; the peak is **$15**, as the guide says. The 200 are one group
answering every price, so the run uses `--counts-sample same`: the group is rebuilt from the drops (10
none, 26 up to $10, 46 up to $15, 44 up to $20, 38 up to $25, 36 up to $30), and 200 respondents are read. The curve already falls at
every step, so the monotone fit equals the raw shares. Expected: `surveymonkey_published.expected.json`.

## 2. `wide_basic.input.csv`: yes/no full ladder, adaptive row, inconsistent row

Prices 10, 20, 30, 40 (columns `price_10` ... `price_40`). 20 full-ladder respondents whose highest
accepted price is: none ×2, 10 ×4, 20 ×6, 30 ×5, 40 ×3. Plus:

- r21 (adaptive): asked 20 → yes, 30 → no; 10 and 40 blank. Filled: 10 → yes (buys at a higher price),
  40 → no (refused a lower price). 2 imputed cells; r21 is a "highest = 20" respondent.
- r22 (inconsistent): no, no, yes, yes. Buys at 30 but not at 10: excluded by default.

Read 22, inconsistent 1, analysed 21. n is 21 at every price; answers given (`n_observed`) are 20, 21, 21, 20 (r21's two filled cells). Buyers: 10 → 2·0 + 4 + 6 + 5 + 3 + 1 = 19; 20 → 6 + 5 + 3 + 1 = 15;
30 → 5 + 3 = 8; 40 → 3. Take rates 19/21, 15/21, 8/21, 3/21 (already falling).

Revenue index 190/21 = 9.0476, 300/21 = 14.2857, 240/21 = 11.4286, 120/21 = 5.7143 → optimum **20**.
With `--unit-cost 12`: (10 − 12)·19/21 = −1.8095, 8·15/21 = 5.7143, 18·8/21 = 6.8571, 28·3/21 = 4.0000 →
optimum **30**: a cost moves the best price up.

Arc elasticity 10 → 20: ((15 − 19)/17) / ((20 − 10)/15) = −0.23529 / 0.66667 = **−0.35294**.

Wilson for 15/21: p̂ = 0.714286, z²/n = 0.182927, denominator 1.182927; centre = (0.714286 + 0.091464) /
1.182927 = 0.681150; half-width = 1.959964·√(0.009718 + 0.002178)/1.182927 = 0.180716 → **0.5004 to
0.8619** (the tests re-derive it by bisection).

## 3. `qualtrics_intent.input.csv`: Qualtrics export, BOM, semicolons, CRLF, intent labels

Three header rows (column ids, question text, ImportId); prices only in the question text ($9.99, $14.99,
$19.99 a month). Ten respondents answer a 5-point intent scale written as labels, some with a numeric prefix
(`5 - Definitely would buy`). D = definitely, P = probably, M = might or might not, PN = probably not,
DN = definitely not.

| Price | D | P | M | PN | DN | Top-2 | Calibrated (0.7, 0.5, 0.3, 0.1, 0) |
|---|---|---|---|---|---|---|---|
| 9.99 | 4 | 3 | 2 | 0 | 1 | 7/10 = 0.70 | 2.8 + 1.5 + 0.6 = 4.9 → 0.49 |
| 14.99 | 2 | 3 | 2 | 2 | 1 | 5/10 = 0.50 | 1.4 + 1.5 + 0.6 + 0.2 = 3.7 → 0.37 |
| 19.99 | 1 | 2 | 1 | 2 | 4 | 3/10 = 0.30 | 0.7 + 1.0 + 0.3 + 0.2 = 2.2 → 0.22 |

Top-2 revenue: 6.993, 7.495, 5.997 → **14.99**. Calibrated: 4.8951, 5.5463, 4.3978 → **14.99**. The
calibration weights are illustrative, not a recommendation.

## 4. `monadic_long.input.csv`: one price per respondent, raw curve not monotone

Long format, no id column, so each row is a respondent. Prices 5, 10, 15, ten respondents each; buyers 6, 7,
2. Raw 0.6, 0.7, 0.2 rises from 5 to 10, so pool-adjacent-violators pools them: (6 + 7)/20 = 0.65.
Monotone 0.65, 0.65, 0.20; revenue 3.25, 6.5, 3.0 → optimum **10**. Nothing is imputed (monadic).

## 5. `max_price.input.csv`: highest acceptable price per respondent

Ladder 10, 20, 30. Values: none ×2, 10 ×2, 20 ×3, 25 ×1 (not on the ladder: buys at 10 and 20), 30 ×3, one
blank (no answer, excluded). Read 12, analysed 11. Take 9/11, 7/11, 3/11; revenue 8.182, 12.727, 8.182 →
optimum **20**.
