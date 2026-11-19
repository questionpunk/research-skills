# Fixtures for survey-crosstabs

Synthetic inputs and published worked examples, no respondent data. Expected values were computed
independently of the script: from the publication, or in base R 4.x (`chisq.test`, `prop.test(correct = FALSE)`,
`t.test`, `p.adjust`, `fisher.test`) reading the same CSV. The R script is reproduced in section 5.

## 1. `agresti_party_gender.input.csv` (aggregated, `--count-col count`)

Agresti (2007) party identification by gender, the example in R's `chisq.test` help page.
Females: Democrat 762, Independent 327, Republican 468; males 484, 239, 477; n = 2,757.
Expected: **X² = 30.0701, df = 2, p = 2.9536 × 10⁻⁷.**

## 2. `aspirin_mi.input.csv` (aggregated)

Physicians' Health Study: placebo 189 heart attacks of 11,034, aspirin 104 of 11,037 (Agresti 2007).
Expected: R `prop.test(c(189, 104), c(11034, 11037), correct = FALSE)` X² = **25.0139**, p = **5.692 × 10⁻⁷**;
z = √25.0139 = 5.0014. With two answers, the "No" row repeats the "Yes" comparison, so tests run = 1.

## 3. `basic.input.csv`: satisfaction by plan, weights, multi-select

135 rows: `respondent_id, plan, satisfaction, features, weight`. Satisfaction is written half with labels
(`5 - Very satisfied`) and half as bare numbers. 3 rows have no satisfaction answer, 2 have no plan.

| satisfaction | Free | Pro | Team |
|---|---|---|---|
| 1 | 10 | 5 | 1 |
| 2 | 10 | 5 | 2 |
| 3 | 15 | 10 | 3 |
| 4 | 10 | 20 | 6 |
| 5 | 5 | 20 | 8 |
| base | 50 | 60 | 20 |

Total base 132 (130 + 2 with no plan). Team (20) is under the small-base threshold of 30, so only Free (A) vs
Pro (B) is tested.

Unweighted, from R:

- Chi-square on the 5×3 table: **X² = 19.4064, df = 8, p = 0.012831.** R warns (some expected counts under 5);
  Cochran's rule (more than 20% under 5) is not met: 3 of 15.
- Free vs Pro, `prop.test(correct = FALSE)`: answer 1 p = 0.075832, 2 p = 0.075832, 3 p = 0.096601,
  4 p = 0.117942, 5 p = **0.0036406**. Welch t on the means (2.80 vs 3.75): p = **0.00013858**.
- Holm over those six tests (`--family table`): answer 5 **0.018203**, mean **0.00083148**, the others 0.30333.
  So Pro carries letter A on "5 - Very satisfied" and on the mean, nothing else.

Weighted by `weight` (from R, same formulas written independently):

- Free: Σw = 70.2, Kish n_eff = **48.0316**, share of 5 = **0.102564**. Pro: Σw = 56.0, n_eff = **57.6471**,
  share of 5 = 0.335714, weighted mean 3.764286. Team: n_eff = 19.2087.
- Pooled z on answer 5 with effective bases: **z = −2.83696**, p = 0.0045545.
- Overall Kish n_eff over all 135 rows: **125.4105**.

Nets: Top 2 (4 or 5) = 15/50 = 30% for Free, 40/60 = 66.7% for Pro, by hand.

## 4. `employee_pulse.input.csv`: anonymity rule

41 synthetic employees, `team, engaged`:

| engaged | Engineering | Sales | Legal | Operations |
|---|---|---|---|---|
| Agree | 12 | 7 | 2 | 4 |
| Neutral | 5 | 3 | 1 | 1 |
| Disagree | 3 | 2 | 0 | 1 |
| base | 20 | 12 | 3 | 6 |

With `--anonymity` (k = 5), by hand: Legal (3) is hidden. Hidden alone it would be Total minus the shown groups,
so the smallest other group, Operations (6), is hidden with it (together 9 people, and the Agree row's Legal and
Operations cells can trade one person for another). Cells under 5: Engineering Disagree (3), Sales Neutral (3),
Sales Disagree (2). Engineering then has one hidden cell, which its base would give away, so its smallest other
cell (Neutral, 5) is hidden too. The test checks every hidden cell by brute force. The chi-square is withheld
because Engineering and Sales have hidden cells. Shown: Engineering Agree 60%, Sales Agree 58%, the Total column.
With k = 13, Legal, Operations and Sales are hidden.

## 5. R script used

`r_reference.R` (base R only; run from this folder with `Rscript r_reference.R`) prints every R value
quoted above.
