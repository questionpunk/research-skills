# Fixtures for nps-analysis

Synthetic inputs (no respondent data) with expected outputs worked out independently of the script: by hand
arithmetic shown below, or from a published worked example. Pairs are named `<case>.input.csv` and
`<case>.expected.json`; `edge_cases.expected.json` covers the small edge-case inputs. Notation: P, A, D are
the counts of promoters (9–10), passives (7–8) and detractors (0–6); z = 1.959964 for 95%.

Formulas (see `../references/sources.md`):

- NPS = (P − D)/n. Variance of one response: Var = p_pro + p_det − (p_pro − p_det)².
- Wald: NPS ± z·√(Var/n).
- Adjusted Wald (default): P' = P + 0.75, D' = D + 0.75, n' = n + 3, then the Wald formula on the adjusted
  values. The script reports the observed NPS and this interval.

## 1. `basic.input.csv`: overall score and interval

40 rows, columns `respondent_id, nps_score, plan, quarter, comment`. Counts by cell:

| plan | quarter | P | A | D | n |
|---|---|---|---|---|---|
| smb | 2026-Q2 | 6 | 3 | 3 | 12 |
| enterprise | 2026-Q2 | 1 | 3 | 4 | 8 |
| smb | 2026-Q3 | 9 | 2 | 2 | 13 |
| enterprise | 2026-Q3 | 2 | 2 | 3 | 7 |
| **all** | | **18** | **10** | **12** | **40** |

Observed NPS = (18 − 12)/40 = 0.15 → **+15.0**.

Wald: p_pro = 0.45, p_det = 0.30. Var = 0.45 + 0.30 − 0.15² = 0.7275. SE = √(0.7275/40) = √0.0181875 =
0.134861. Margin = 1.959964 × 0.134861 = 0.264323. Interval 0.15 ± 0.2643 → **−11.43 to +41.43**.

Adjusted Wald: P' = 18.75, D' = 12.75, n' = 43. p_pro = 18.75/43 = 0.436047, p_det = 12.75/43 = 0.296512.
Adjusted NPS = 0.139535. Var = 0.436047 + 0.296512 − 0.139535² = 0.732558 − 0.019470 = 0.713088.
SE = √(0.713088/43) = √0.0165834 = 0.128777. Margin = 1.959964 × 0.128777 = 0.252398.
Interval 0.139535 ± 0.252398 → **−11.29 to +39.19**.

## 2. `basic.input.csv`: two segments, smb vs enterprise

smb: n = 25, P = 15, A = 5, D = 5 → NPS = 10/25 = **+40.0**.
enterprise: n = 15, P = 3, A = 5, D = 7 → NPS = −4/15 = **−26.67**. Observed difference **+66.67**.

The overall +15.0 is the pooled score; the plain mean of the two segment scores would be +6.67, which is
wrong because the segments differ in size.

Adjusted Wald (default):

- smb: P' = 15.75, D' = 5.75, n' = 28. p_pro = 0.562500, p_det = 0.205357, NPS' = 0.357143.
  Var = 0.767857 − 0.127551 = 0.640306. Var/n' = 0.0228681. SE = 0.151222, margin 0.296390 →
  **+6.08 to +65.35**.
- enterprise: P' = 3.75, D' = 7.75, n' = 18. p_pro = 0.208333, p_det = 0.430556, NPS' = −0.222222.
  Var = 0.638889 − 0.049383 = 0.589506. Var/n' = 0.0327503. SE = 0.180971, margin 0.354696 →
  **−57.69 to +13.25**.
- Difference of adjusted scores = 0.357143 + 0.222222 = 0.579365 (**57.94** points).
  SE_diff = √(0.0228681 + 0.0327503) = √0.0556184 = 0.235836. z = 0.579365/0.235836 = **2.457**.
  Two-sided p = 2·(1 − Φ(2.4566)) = **0.0140**. Interval of the difference: 0.579365 ± 1.959964 × 0.235836
  = 0.579365 ± 0.462229 → **+11.71 to +104.16**.

Wald (`--interval wald`): Var_smb = 0.6 + 0.2 − 0.4² = 0.64, Var/n = 0.0256. Var_ent = 0.2 + 0.466667 −
0.266667² = 0.595556, Var/n = 0.0397037. SE_diff = √0.0653037 = 0.255546. z = 0.666667/0.255546 =
**2.609**, p = **0.0091**. Interval 0.666667 ± 0.500860 → **+16.58 to +116.75**.

## 3. `basic.input.csv`: two periods and comments

2026-Q2: n = 20, P = 7, D = 7 → **0.0**. 2026-Q3: n = 20, P = 11, D = 5 → **+30.0**.

Adjusted Wald: Q2: P' = D' = 7.75, n' = 23, NPS' = 0, Var = 2 × 0.336957 = 0.673913, Var/n' = 0.0293006.
Q3: P' = 11.75, D' = 5.75, n' = 23, p_pro = 0.510870, p_det = 0.250000, NPS' = 0.260870, Var = 0.760870 −
0.068053 = 0.692817, Var/n' = 0.0301225. SE_diff = √0.0594231 = 0.243768. z = 0.260870/0.243768 =
**1.070**, p = **0.2846**: a 30-point rise that is not significant at n = 20 per period.

Comments were counted from the file with `awk`, not with the script: promoters 13 of 18 left a comment,
passives 8 of 10, detractors 10 of 12.

## 4. `measuringu_gtm_webex.input.csv`: published worked example

Lewis and Sauro (MeasuringU, 2021) publish only the category counts from a 2019 survey of online-meeting
products, so the scores inside each category in this file are arbitrary: GoToMeeting 8 detractors,
13 passives, 15 promoters (n = 36); WebEx 12, 12, 7 (n = 31). Published values, 90% confidence
(z = 1.645), as proportions:

- Intervals (https://measuringu.com/nps-confidence-intervals/): GoToMeeting NPS 0.19, adjusted 0.18,
  interval −0.02 to 0.38; WebEx NPS −0.16, adjusted −0.15, interval −0.36 to 0.07.
- Test (https://measuringu.com/nps-significance-test/): adjusted difference 0.33, SE 0.180, Z = 1.815,
  p = 0.07, 90% interval of the difference 0.03 to 0.62.

Run with `--segment-col product --compare GoToMeeting WebEx --confidence 0.90`. The test allows the
published rounding (±0.005).

## 5. `three_segments.input.csv`: all pairs with Bonferroni and Holm

free: P = 10, A = 10, D = 20; pro: 20, 10, 10; team: 16, 12, 12; n = 40 each. Adjusted Wald, n' = 43:

- free: NPS' = (10.75 − 20.75)/43 = −0.232558, Var = 0.732558 − 0.054083 = 0.678475, Var/n' = 0.0157785.
- pro: NPS' = +0.232558, same variance.
- team: NPS' = (16.75 − 12.75)/43 = 0.093023, Var = 0.686047 − 0.008653 = 0.677393, Var/n' = 0.0157533.

| pair | difference | SE_diff | z | p |
|---|---|---|---|---|
| free vs pro | −0.465116 | √0.0315570 = 0.177643 | 2.6183 | 0.008838 |
| free vs team | −0.325581 | √0.0315318 = 0.177572 | 1.8335 | 0.066726 |
| pro vs team | 0.139535 | 0.177572 | 0.7858 | 0.431989 |

Bonferroni (m = 3): p × 3, capped at 1 → 0.026513, 0.200177, 1.0.
Holm: sort ascending and multiply by 3, 2, 1, keeping the running maximum → 0.026513, 0.133452, 0.431989.

## 6. Edge cases (`edge_cases.expected.json`)

- `all_promoters.input.csv` (ten scores of 9 or 10; nobody chose 0, which at this size is a warning):
  NPS = +100. Wald: Var = 1 + 0 − 1² = 0, so the interval is 100 to 100 (zero width; the script notes it).
  Adjusted Wald: P' = 10.75, D' = 0.75, n' = 13. NPS' = 10/13 = 0.769231. Var = 0.884615 − 0.591716 =
  0.292899. SE = √(0.292899/13) = 0.150102, margin 0.294195 → +47.50 to +106.34, upper limit clipped to
  **+100**.
- `single_response.input.csv` (one score of 9): NPS = +100. Adjusted Wald: P' = 1.75,
  D' = 0.75, n' = 4. NPS' = 0.25. Var = 0.625 − 0.0625 = 0.5625. SE = √(0.5625/4) = 0.375, margin 0.734986
  → −48.50 to +98.50. Every answer is a promoter, and a population of only promoters (+100) gives this
  sample with certainty, so the upper limit is moved to **+100**: **−48.50 to +100**.
- `empty_segment.input.csv`: finance has two rows, a blank and `n/a`, so n = 0: no score, left out of the
  tests. sales: 10, 9, 0, 7 → (2 − 1)/4 = **+25.0**. support: 10, 6, 8 → (1 − 1)/3 = **0.0**.
- `dirty.input.csv`: 12 rows; excluded are one blank, one `N/A` (not a number), one `7.5` (not a whole
  number), and `11` and `-1` (out of range). `9.0` counts as 9. Seven valid scores: 10, 9, 9, 0, 7, 8, 3 →
  P = 3, A = 2, D = 2, NPS = 1/7 = **+14.29**.
- `scale_1_5.input.csv`: 5, 5, 5, 5, 4, 4, 3, 2, 1, 5. Refused without a flag. With `--scale 1-5`
  (5 = promoter, 4 = passive, 1–3 = detractor): P = 5, A = 2, D = 3 → **+20.0**, flagged as non-standard.
- `scale_1_10.input.csv`: 10, 9, 9, 10, 8, 7, 7, 6, 3, 1. Ten answers with no 0: computed as 0–10 with a
  warning. P = 4, A = 3, D = 3 → **+10.0**, the same with `--scale 1-10`.
- `scale_1_10_large.input.csv`: 200 answers cycling 1 to 10, no 0, lowest score 1: refused without
  `--scale` (strong evidence of a 1–10 scale).
- `dates.input.csv`: ISO dates bucketed with `--period-grain quarter`: three rows in 2026-Q1, three in
  2026-Q2, and `15/07/2026` left out of the period table as a bad period (counted, never dropped
  silently). Its score (8) still counts in the overall result, so overall n = 7.

## 7. Counts input and the benchmark test (published example)

- `--counts 18,10,12` and `--counts 1,0,1,1,2,3,4,5,5,8,10` (how many chose 0, 1, ... 10: detractors
  1+0+1+1+2+3+4 = 12, passives 5+5 = 10, promoters 8+10 = 18) must give the section 1 result.
- `counts_cells.input.csv` holds the four cells of the section 1 table as counts (with `Neutrals` as the
  passive column), so sections 1 to 3 apply unchanged. `counts_bad.input.csv` has the word `four` as a
  count and must fail.
- `benchmark_measuringu.expected.json`: Lewis and Sauro (MeasuringU, 6 July 2021,
  https://measuringu.com/nps-benchmark-test/): 61 promoters, 30 passives, 16 detractors, n = 107.
  Published: adjusted NPS 0.41, Var 0.546, SE 0.070; one-tailed tests against 40%, 30%, 20%:
  Z = 0.129 (p = 0.449), 1.548 (p = 0.061), 2.967 (p = 0.002); one-sided 95% lower bound 0.29.
  Check by hand: P' = 61.75, D' = 16.75, n' = 110; NPS' = 45/110 = 0.409091; Var = 0.713636 − 0.167355 =
  0.546281; SE = √(0.546281/110) = 0.070471; (0.409091 − 0.30)/0.070471 = 1.548. Two-tailed p against 30
  = 2 × 0.0608 = **0.1216**.
- Wald benchmark against 0 for section 1 (`--interval wald --benchmark 0`): z = 0.15/0.134861 = **1.1123**,
  two-tailed p = **0.2660**.
- n needed for a ±10 point margin at the section 1 variance: adjusted Wald 1.959964² × 0.713088/0.10² − 3 =
  270.93 → **271**; Wald 3.841459 × 0.7275/0.01 = 279.47 → **280**. The published example (n = 107) is not
  a small base, so no hint is printed for it.
- `--invited 200` on `basic.input.csv`: 40/200 = **20.0%**.

## 8. Mix shift, `basic.input.csv` or `counts_cells.input.csv`, 2026-Q2 to 2026-Q3

| segment | share Q2 | share Q3 | NPS Q2 | NPS Q3 |
|---|---|---|---|---|
| smb | 12/20 = 0.60 | 13/20 = 0.65 | (6 − 3)/12 = +25.00 | (9 − 2)/13 = +53.85 |
| enterprise | 8/20 = 0.40 | 7/20 = 0.35 | (1 − 4)/8 = −37.50 | (2 − 3)/7 = −14.29 |

Check: Q2 = 0.60 × 25 + 0.40 × (−37.5) = 0; Q3 = 0.65 × 53.846 + 0.35 × (−14.286) = 35 − 5 = 30.

- Within segments: smb 0.625 × (53.846 − 25) = **18.03**; enterprise 0.375 × (−14.286 + 37.5) = **8.71**;
  total **26.73**.
- Mix: smb ½(25 + 53.846) × 0.05 = 39.423 × 0.05 = **1.97**; enterprise ½(−37.5 − 14.286) × (−0.05) =
  **1.29**; total **3.27**.
- 26.73 + 3.27 = **30.00**, the change in the pooled score.

One-period segment (inline test): period 1 has only segment a (5 promoters, 5 detractors, NPS 0); period 2
has a unchanged and b with 10 promoters. Pooled 0 → +50. Within = 0; mix = ½(0 + 0) × (0.5 − 1) +
½(100 + 100) × (0.5 − 0) = **50**.

## 9. Welch t-test on the published data (`--test welch`)

GoToMeeting, recode: 15 at +100, 13 at 0, 8 at −100. Mean 700/36 = 19.444. Sum of squares 23 × 10⁴ =
230,000. s² = (230,000 − 36 × 19.444²)/35 = (230,000 − 13,611.1)/35 = 6,182.54 (SD 78.6; published 0.79).
WebEx: mean −500/31 = −16.129; s² = (190,000 − 31 × 16.129²)/30 = (190,000 − 8,064.5)/30 = 6,064.52
(SD 77.9; published 0.78).

SE = √(6,182.54/36 + 6,064.52/31) = √(171.737 + 195.630) = **19.17**. t = 35.573/19.167 = **1.856**.
ν = 367.367²/(171.737²/35 + 195.630²/30) = 134,958/(842.68 + 1,275.70) = **63.71**.
Published cross-check: a standard t-test on the same data gives t(65) = 1.86, p = .07 (MeasuringU), so the
Welch p-value must round to 0.07. The t distribution itself is tested against NIST table values.

## 10. `paired.input.csv`: change per respondent

Ten ids answer in both waves; u11 and u12 only in wave 1, u13 only in wave 2. Recode changes
(wave 2 − wave 1): 7→9 +100, 8→10 +100, 5→7 +100, 9→10 0, 10→9 0, 8→8 0, 3→4 0, 7→8 0, 9→8 −100,
2→10 +200. So 4 moved up, 5 unchanged, 1 moved down.

Mean = (300 + 0 − 100 + 200)/10 = **40**. Squared deviations: 3 × 60² + 5 × 40² + 140² + 160² =
10,800 + 8,000 + 19,600 + 25,600 = 64,000. sd = √(64,000/9) = **84.33**. SE = 84.327/√10 = **26.67**.
t = 40/26.667 = **1.50**, df 9. NIST table: 95% two-sided critical value 2.262, so the interval is
40 ± 60.32 → **−20.32 to +100.32**; and 1.383 < 1.50 < 1.833 puts the two-sided p between 0.10 and 0.20.

Without `--paired` the period test is withheld because 10 ids are in both waves.

## 11. `themes.input.csv`: NPS with and without a coded theme

Twelve coded rows, three uncoded (left out). "price" is coded on the scores 2, 3, 6, 7, 9: P = 1, A = 1,
D = 3 → **−40.0**. The other seven coded rows score 9, 10, 10, 8, 9, 5, 7: P = 4, A = 2, D = 1 →
3/7 = **+42.86**. Difference **−82.86**.

Adjusted Wald, price: P' = 1.75, D' = 3.75, n' = 8: NPS' = −0.25, Var = 0.6875 − 0.0625 = 0.625,
SE = √(0.625/8) = 0.279508, margin 0.547827 → **−79.78 to +29.78**. Rest: P' = 4.75, D' = 1.75, n' = 10:
NPS' = 0.30, Var = 0.65 − 0.09 = 0.56. Difference of adjusted scores −0.55; SE = √(0.078125 + 0.056) =
0.366231; margin 0.717800 → **−126.78 to +16.78**.

"support": scores 3, 10, 10, 9, 5 → (3 − 2)/5 = **+20.0**; rest 2, 6, 7, 9, 9, 8, 7: P = 2, D = 2 → **0.0**.
"ease of use": 9, 9, 10, 8, 7 → 3/5 = **+60.0**; rest 2, 3, 6, 7, 10, 9, 5: P = 2, D = 4 → −2/7 = **−28.57**.
