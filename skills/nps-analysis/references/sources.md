# NPS analysis: method sources

Checked against the sources below on 2026-11-12 (second pass the same day). Each entry says how it was checked.

## Formulas

Notation: n valid responses; P, A, D the counts of promoters, passives and detractors; p_pro = P/n,
p_det = D/n. The script works in proportions (−1 to +1) and prints points (−100 to +100).

### The score

- Question: "How likely is it that you would recommend [X] to a friend or colleague?", answered 0–10.
  Promoters 9–10, passives 7–8, detractors 0–6 (Reichheld 2003, as restated in Rocks 2016 section 1 and
  Sauro 2017). Employee NPS (eNPS) uses the same scale and arithmetic.
- NPS = p_pro − p_det = (P − D)/n, from −100 to +100 in points. Passives count in n only.

### Variance (Rocks 2016, section 1.4)

- Var = p_pro + p_det − (p_pro − p_det)².
- Why: score each respondent +1, 0 or −1. The mean is the NPS, the mean of the squares is p_pro + p_det, so
  the variance is p_pro + p_det − NPS². This is the multinomial variance of a difference of two shares from
  the same sample; it already contains the covariance between the two shares.
- Range 0 (everyone in one category) to 1 (half promoters, half detractors). Two samples with the same NPS
  can have different variances, so an interval cannot be derived from the score alone.
- Across 1,098 company-year distributions in the Satmetrix US consumer data the mean NPS was 0.26 (SD 0.24)
  and the mean variance 0.59 (SD 0.12) (Rocks 2016, section 3.1.2). MeasuringU found adjusted variances
  from 0.40 to 0.76 in 18 datasets and uses 0.67 as a realistic maximum (Lewis and Sauro 2021c).

### Intervals

- **Wald** (Rocks 2016, equation 1): NPS ± z·√(Var/n), z = 1.96 for 95% (1.645 for 90%). Offered as
  `--interval wald` because many tools use it. Rocks: "The Wald and Goodman tests perform poorly; their use
  should be avoided." Its 95% interval covered the true score 82% of the time at n = 5, 91% at n = 15,
  93% at n = 30 and 94.4% at n = 100 on the observed distributions (Rocks 2016, Table 1). With variance 0 it
  has zero width.
- **Adjusted Wald, AW(3, T)** (Rocks 2016, section 2.1.3 and conclusion; the script's default): add ¾ to
  the promoter count, ¾ to the detractor count and 3/2 to the passive count, so n grows by 3; then apply
  the Wald formula to the adjusted values:
  p'_pro = (P + ¾)/(n + 3), p'_det = (D + ¾)/(n + 3), NPS' = p'_pro − p'_det,
  Var' = p'_pro + p'_det − NPS'², interval NPS' ± z·√(Var'/(n + 3)).
  Rocks calls it the best-performing adjusted Wald, with "good performance across the n values and
  confidence levels examined"; coverage was 94.8% to 95.1% from n = 5 to n = 300 (Table 1). Lewis and Sauro
  (2021a) recommend the same method and describe it step by step.
- The interval is centred on the adjusted score NPS', which is pulled slightly towards 0. The script
  reports the observed NPS as the score and the adjusted-Wald limits as the interval (the presentation
  Lewis and Sauro use), and clips the limits to −100 and +100.
- Rocks also finds an iterative score interval performs well; it needs a numerical search and is slightly
  conservative below n = 20. Not implemented.

### Difference between two independent scores (Lewis and Sauro 2021b)

- SE_diff = √(Var₁/n₁ + Var₂/n₂); z = |NPS₁ − NPS₂|/SE_diff; two-sided p = 2·(1 − Φ(z)).
  Interval of the difference: (NPS₁ − NPS₂) ± z_crit·SE_diff.
- Lewis and Sauro use the adjusted values (NPS', Var', n + 3) for each group throughout. The script does the
  same by default and uses the unadjusted values with `--interval wald`.
- Published check: GoToMeeting (D 8, A 13, P 15, n = 36) vs WebEx (12, 12, 7, n = 31): adjusted difference
  0.33, SE 0.180, Z = 1.815, p = 0.07; 90% interval 0.03 to 0.62. The script reproduces it
  (`fixtures/measuringu_gtm_webex.*`).
- The test assumes the two samples are independent. For the same respondents measured twice, and for
  rolling windows that share respondents, it is not valid: the shared answers make the two scores
  correlated. Pool overlapping windows or test only non-overlapping periods. With `--id-col` the script
  finds ids present in both periods and withholds the test; without it, it cannot detect overlap and
  prints a note.
- Verdicts printed by the script: "significant"; "underpowered" when the test is not significant and at
  least one side is under the small-base threshold; otherwise "not significant". The middle label is this
  skill's wording for "a real difference could easily have been missed", not a power calculation.

### Score against a benchmark (Lewis and Sauro 2021d)

- z = (NPS' − benchmark)/√(Var'/(n + 3)) on the adjusted values. One-tailed p = 1 − Φ(z) when the question
  is "are we above the benchmark" (their default, critical z 1.645 at α = 0.05); two-tailed
  p = 2·(1 − Φ(|z|)) otherwise. The script's default is two-tailed; `--tail one` tests "above" only.
  The one-sided lower bound is NPS' − z₁·SE with z₁ = 1.645 for 95%.
- Published check: 61 promoters, 30 passives, 16 detractors (n = 107): NPS' = 0.41, Var' = 0.546,
  SE = 0.070; against 40%, 30% and 20%: Z = 0.129 (p = 0.449), 1.548 (p = 0.061), 2.967 (p = 0.002);
  one-sided 95% lower bound 0.29. The script reproduces all of it (`fixtures/benchmark_measuringu.*`).
- "Is our NPS good?" is answered with this test against a benchmark the user supplies, with its source,
  date and collection method. This skill ships no table of "good" scores: none could be sourced.

### Welch t-test on the recode (`--test welch`)

- Recode promoters +100, passives 0, detractors −100. The mean is the NPS; the sample variance is
  s² = 100²·Var·n/(n − 1). t = (NPS₁ − NPS₂)/√(s₁²/n₁ + s₂²/n₂), with Welch–Satterthwaite degrees of
  freedom ν = (s₁²/n₁ + s₂²/n₂)² / [(s₁²/n₁)²/(n₁ − 1) + (s₂²/n₂)²/(n₂ − 1)] (Welch 1947).
  This is the test Qualtrics CX dashboards document for NPS. No adjusted-Wald correction is applied.
- The two-sided p-value is I_x(ν/2, ½) at x = ν/(ν + t²), where I is the regularized incomplete beta
  function, computed with a continued fraction. Checked against the NIST t table: t = 2.228 (ν = 10),
  2.086 (ν = 20), 2.000 (ν = 60) give p = 0.05; 1.690 (ν = 35) gives 0.10; the 95% critical value at
  ν = 9 is 2.262 and the 90% value at ν = 30 is 1.697.
- Cross-check on the GoToMeeting and WebEx data: Lewis and Sauro (2021a, 2021b) report SDs of 0.79 and
  0.78 and a standard t-test of t(65) = 1.86, p = .07; Welch by hand gives t = 1.856, ν = 63.7.

### Paired change (`--paired`)

- For respondents who answered in both periods (linked by `--id-col`): d = recode(later) − recode(earlier),
  one of −200, −100, 0, +100, +200. Report the mean of d with a paired t interval:
  mean ± t(n − 1)·sd/√n, and the two-sided p-value from the same t distribution (the paired form of
  Student's t-test). The mean change equals the change in NPS among the linked respondents.
- This applies a standard paired t-test to the three-point recode, the same idea as the "means method"
  interval Lewis and Sauro (2021a) compare with adjusted Wald. No source was found that validates it for
  NPS specifically; with few pairs treat the p-value as approximate. Respondents present in only one
  period are counted and left out, so the paired result describes those who stayed, not the whole base.

### Mix shift between two periods (Kitagawa 1955)

- With segment shares w and segment scores NPS_s, the pooled score is Σ w_s·NPS_s. The change between two
  periods splits exactly into
  within segments = Σ ½(w_s,earlier + w_s,later)·(NPS_s,later − NPS_s,earlier) and
  mix = Σ ½(NPS_s,earlier + NPS_s,later)·(w_s,later − w_s,earlier).
  The two terms add up to the change in the pooled score (identity: a₁b₁ − a₀b₀ = ā·Δb + b̄·Δa).
- A segment present in only one period has no change of its own; the script carries its score to the other
  period, so its whole effect lands in the mix term.
- Per-segment mix terms depend on the level of the score (they are not centred), so read the mix total and
  the share changes, not a single segment's mix value. The decomposition is descriptive: it has no interval.

### Sample size for a target margin

- Rearranging the interval: n = z²·Var/e², minus 3 for adjusted Wald (the convention Lewis and Sauro
  2021c use in their sample-size formulas). The script prints this for small bases with e = 10 points
  (the margin Pew's reporting rule is built on) at the observed variance. It is a rough guide; planning
  belongs to the sibling skill `survey-sample-size`.

### Many comparisons

- With m tests at level α and no real differences, about m·α come out significant by chance.
- Bonferroni: adjusted p = min(1, m·p).
- Holm (1979): sort the p-values ascending, multiply the i-th by (m − i + 1), take the running maximum and
  cap at 1. It controls the same family-wise error rate as Bonferroni and never rejects fewer hypotheses.
- The script applies the adjustment across every two-group test in one run (segment pairs, period pair,
  trend steps). The benchmark test and the theme table are not part of that family.
  The default is no adjustment with a printed warning, because one planned comparison needs none.

## Thresholds

- **Small base: n under 100** (`--min-base`, default 100). Pew Research Center (2022) generally reports
  only groups with an effective sample size of at least 100, because below it the margin of error is
  generally more than 10 percentage points; it shows such groups with a confidence interval when it shows
  them, and does not publish groups with fewer than 100 raw interviews or an effective sample size under 50.
  That rule is for percentages. An NPS is less precise than a percentage at the same n: with the mean
  variance 0.59, the 95% margin is 1.96·√(0.59/n) = about 15 points at n = 100, 7.5 at n = 400 and 4.8 at
  n = 1,000 (arithmetic from the Wald formula above). The script flags small bases; it does not suppress
  them, because the interval already shows the uncertainty.
- **Default confidence 95%** (z = 1.96): convention. Lewis and Sauro's examples use 90%.

## Scale checks

- NPS is defined on 0–10. Sauro (2017) had 520 people (512 after cleaning) answer the 0–10, a 1–10 and a
  1–5 version: against 0–10 the score moved by about 4 points on average either way, and by up to 14 points
  for one brand; on 1–10 scores were the same or higher for 10 of 11 brands. Mappings he tested, used by
  `--scale`: 1–10 → promoters 9–10, passives 7–8, detractors 1–6; 1–5 → promoters 5, passives 4,
  detractors 1–3.
- Detection in the script (conventions of this skill, not published rules):
  - a 0 among the answers → 0–10;
  - no 0 and a highest score of 5 or lower → stop: a 1–5 scale is likely;
  - no 0, a lowest score of exactly 1 and at least 200 valid answers → stop: a 1–10 scale is likely. The
    200 is a convention: small 0–10 samples often contain no 0, large ones rarely do, and no source gives
    the share of zeros, so the cut-off is a judgement that prefers a warning to a false stop;
  - otherwise no 0 → compute as 0–10 and warn.
  Counts input cannot be checked; the output says so.
- Whole numbers only. A value such as 7.5 is usually an average of several answers or another metric, so it
  is excluded and counted. `9.0` is read as 9.

## Critiques and comparability

- **Predictive claims are disputed.** Reichheld (2003) presented the measure as the best single predictor
  of growth. Keiningham, Cooil, Andreassen and Aksoy (2007), with longitudinal data from 21 firms and more
  than 15,500 interviews, could not replicate the claimed superiority over other satisfaction and loyalty
  measures. Report NPS as a tracked attitude measure, not as a growth forecast.
- **Presentation changes the score.** Colour-coding the scale: in a within-subjects study (n = 184) the
  three-colour version raised mean likelihood-to-recommend by about 1% to 3%; in a between-subjects study
  (n = 229) detractors were 32% without colour and 24% with three colours (Sauro 2019). Sauro's conclusion
  in both studies: keep the presentation constant.
- **Channel.** Telephone respondents are more likely than respondents in other modes to give the most
  positive answers, and not more likely to give the most negative ones (Ye, Fulton and Tourangeau 2011,
  meta-analysis). Moving a survey from phone to web or in-app can lower NPS with no change in opinion.
- **Culture and language.** Response styles differ by country: acquiescence, extreme and middle responding
  vary with country-level traits, and answering in English rather than the native language produces more
  middle responses (Harzing 2006, 26 countries). Compare a country with itself over time before comparing
  countries.
- **Benchmarks.** Published benchmarks mix scales, channels, sampling and timing. Scale format alone moves
  the score by about 4 points (Sauro 2017). Prefer your own trend with a fixed method, and test against an
  outside number only when its source, date and method are known.
- **Non-response.** Every interval here covers sampling error only. A low or shifting response rate
  changes who answers; no formula in this file corrects for that.

## Reconciling with other tools

When a tool shows another interval or verdict for the same counts, name its method. The score itself
should match everywhere; if it does not, look for a different scale, filter or base first.

| Tool | Method it documents | To match it | Checked |
|---|---|---|---|
| MeasuringU articles (Lewis and Sauro 2021a, b, d) | Adjusted Wald (n + 3; ¾, 3/2, ¾); interval centred on the adjusted NPS; examples at 90%; p < .10 accepted as a criterion for industrial research | Default settings. Same limits and tests; this script reports the observed NPS as the score where they report the adjusted one (`nps_adjusted` in the JSON). Use `--confidence 0.90` for their examples | Pages read; examples reproduced |
| R package `NPS` 1.1 (Rocks; archived from CRAN on 2022-06-10) | Wald only; `nps.test` one-sample null fixed at 0, two-sample z-test on the same variance; 95% default | `--interval wald`; one-sample: `--benchmark 0` (two-tailed) | Source of 1.1 read |
| Qualtrics CX dashboards | Recode to 100 / 0 / −100, then a two-tailed Welch independent-samples t-test | `--test welch` | Support page read |
| SurveyMonkey | Significance testing lists Multiple Choice, Dropdown, Matrix/Rating Scale and Ranking questions, not NPS; 95% level; at least 30 responses per compared option | No equivalent; say the tool does not test NPS | Help page read |
| Genroe spreadsheet and article | Wald with the same variance, written as the mean square of +1/0/−1 scores; "different" when the gap exceeds 1.96·√(SE₁² + SE₂²); also a chi-squared test on the three counts | `--interval wald`; the chi-squared test is not implemented | Article read; spreadsheet cells not opened |
| Dashboards with no interval | None | Report this skill's interval and say the tool shows none | n/a |

`--interval wald` gives the same interval and z-test as R `NPS` 1.1 and the Genroe formula. The default
gives MeasuringU's limits and p-values.

## Where practitioners disagree

- **Which interval.** Many tools still print the Wald interval or none. Rocks and MeasuringU recommend
  adjusted Wald; Rocks rates an iterative score interval about as well. Others treat the +1/0/−1 scores as
  a mean and use a t interval; Lewis and Sauro (2021a) found it slightly wider (90% width 0.44 vs 0.40 on
  the GoToMeeting data) and close to a bootstrap.
- **Adjust for multiple comparisons or not.** Exploratory dashboards rarely adjust; confirmatory readouts
  should. The script warns and leaves the choice to the analyst.
- **Minimum base.** Common floors range from 30 to 100; this skill uses Pew's 100 and always shows the
  interval.
- **Non-standard scales.** Some vendors compute "NPS" on 1–5 or 1–10; Sauro's data says the result is not
  interchangeable with 0–10.

## Sources

1. Reichheld, F. F. (2003). The One Number You Need to Grow. *Harvard Business Review* 81(12).
   https://hbr.org/2003/12/the-one-number-you-need-to-grow (definition; full text paywalled, see "Not
   verified").
2. Rocks, B. (2016). Interval Estimation for the "Net Promoter Score". *The American Statistician* 70(4),
   365–372. doi:10.1080/00031305.2016.1158124. Preprint: https://arxiv.org/abs/1601.07235 (read in full
   from the preprint: variance, Wald, AW(3, T), Table 1, conclusion).
3. Lewis, J. R. and Sauro, J. (2021a). Confidence Intervals for Net Promoter Scores. MeasuringU,
   5 January 2021. https://measuringu.com/nps-confidence-intervals/ (page, byline and date read; worked
   example reproduced).
4. Lewis, J. R. and Sauro, J. (2021b). How to Statistically Compare Two Net Promoter Scores. MeasuringU,
   2 February 2021. https://measuringu.com/nps-significance-test/ (page, byline and date read; worked
   example reproduced).
5. Lewis, J. R. and Sauro, J. (2021c). Sample Sizes for Comparing Net Promoter Scores. MeasuringU.
   https://measuringu.com/nps-sig-test-sample-size/ (page read; variance range 0.40–0.76 and 0.67).
6. Sauro, J. (2017). Changing the Net Promoter Scale: How Much Does It Matter? MeasuringU.
   https://measuringu.com/nps-scale-change/ (page read).
7. Sauro, J. (2019). Does Coloring Response Categories Affect Responses? MeasuringU.
   https://measuringu.com/coloring-responses/ (page read).
8. Keiningham, T. L., Cooil, B., Andreassen, T. W. and Aksoy, L. (2007). A Longitudinal Examination of Net
   Promoter and Firm Revenue Growth. *Journal of Marketing* 71(3), 39–51. doi:10.1509/jmkg.71.3.39
   (abstract and summaries read, not the full text).
9. Holm, S. (1979). A Simple Sequentially Rejective Multiple Test Procedure. *Scandinavian Journal of
   Statistics* 6(2), 65–70. https://www.jstor.org/stable/4615733 (citation confirmed; procedure as commonly
   stated).
10. Pew Research Center (2022). Why Pew Research Center typically can't report the views of smaller U.S.
    religious groups.
    https://www.pewresearch.org/short-reads/2022/08/08/why-pew-research-center-typically-cant-report-the-views-of-smaller-u-s-religious-groups/
    (page read).
11. Ye, C., Fulton, J. and Tourangeau, R. (2011). More Positive or More Extreme? A Meta-Analysis of Mode
    Differences in Response Choice. *Public Opinion Quarterly* 75(2), 349–365. doi:10.1093/poq/nfr009
    (abstract read).
12. Harzing, A.-W. (2006). Response Styles in Cross-National Survey Research: A 26-Country Study.
    *International Journal of Cross Cultural Management* 6(2), 243–266. doi:10.1177/1470595806066332
    (abstract and the author's summary read).
13. Lewis, J. R. and Sauro, J. (2021d). How to Compare a Net Promoter Score with a Benchmark. MeasuringU,
    6 July 2021. https://measuringu.com/nps-benchmark-test/ (page, byline and date read; three tests
    reproduced).
14. Kitagawa, E. M. (1955). Components of a Difference Between Two Rates. *Journal of the American
    Statistical Association* 50(272), 1168–1194 (citation and the symmetric two-component form confirmed
    from summaries, not the full text).
15. Welch, B. L. (1947). The Generalization of "Student's" Problem when Several Different Population
    Variances are Involved. *Biometrika* 34(1/2), 28–35 (citation confirmed; formula as commonly stated).
16. NIST/SEMATECH e-Handbook of Statistical Methods, 1.3.6.7.2, Upper critical values of Student's t
    distribution. https://www.itl.nist.gov/div898/handbook/eda/section3/eda3672.htm (table read).
17. Qualtrics. Significance Testing in Simple Charts and Simple Tables (CX).
    https://www.qualtrics.com/support/vocalize/widgets/significance-testing-in-simple-charts-simple-tables-cx/
    (page read).
18. SurveyMonkey Help. Significant differences.
    https://help.surveymonkey.com/en/surveymonkey/analyze/significant-differences/ (page read).
19. Genroe. How to calculate NPS Margin of Error and other Statistics.
    https://www.genroe.com/blog/how-to-calculate-margin-of-error-and-other-stats-for-nps/5994 (page read).
20. Rocks, B. R package `NPS`, version 1.1 (2014). https://cran.r-project.org/src/contrib/Archive/NPS/
    (source read; archive listing and removal notice read).

## Pitfalls

- Computing the margin of error as if promoter and detractor shares were two independent percentages, or as
  the margin of a single percentage. Use the variance above.
- Averaging segment or period scores instead of pooling the responses (weights each segment equally).
- Running an independent-samples test on the same respondents measured twice, or on rolling windows that
  share respondents.
- Reading a flat score as "nothing changed" when promoter and detractor shares both moved.
- Explaining a change in the pooled score without checking whether the segment mix changed.
- Answering "is this good" from an unsourced band table instead of a dated, sourced benchmark.
- Reading the NPS gap between people who mention a theme and the rest as the theme's causal effect.
- Calling a change real without an interval: at n = 100 per period the margin is about 15 points each.
- Testing every pair of segments and reporting the one that came out significant.
- Computing NPS on a 1–5 or 1–10 scale, or on averages, and comparing it with 0–10 scores.
- Comparing periods after the wording, scale presentation, channel, trigger or sampling changed.
- Ignoring a response-rate shift: who answers changes with it, and so can the score.
- Reporting decimals at small n (one respondent moves the score by 100/n points).
- Reporting comment themes without the denominator (of how many comments, from how many respondents).
- Treating the score as a forecast of growth, or comparing it with a benchmark collected another way.
