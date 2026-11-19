# Likert analysis: method sources

Checked on 2026-11-19. "Read" means the page or paper was opened and the rule found in it; "via" names the
secondary source a value was confirmed through; "not re-checked" means a standard citation not opened this
session.

Contents: Items and boxes · Medians or means · Diverging bars · Reverse-coded items · Cronbach's alpha ·
Group comparisons · Thresholds · Pitfalls · References

## Items and boxes

- A Likert scale is the sum or mean of several agree/disagree items about one attitude; one such item is a
  "Likert-type item" (Likert 1932, not re-checked). This skill reports items one by one and, with `--alpha`,
  the multi-item scale.
- **Top box / bottom box:** the share of answers in the top (bottom) two points, out of all valid answers to
  the item. Default width 2 on scales of 4 or more points, 1 on 2-3 point scales; `--box` changes it (for
  example top-3 on a 7-point scale). Shares get a **Wilson score interval** (Wilson 1927), which keeps its
  coverage at small n and near 0 or 100% where the Wald interval fails (Newcombe 1998a; Agresti and Coull
  1998; not re-checked).
- Neutral point: the middle point of an odd-length **bipolar** scale (disagree to agree, dissatisfied to
  satisfied); none on an even-length scale. A unipolar scale (never to always, not at all to extremely
  important) has a middle but no neutral point, so the script labels its regions low / middle / high
  (`--unipolar`, or automatically from the frequency and importance label maps; Heiberger and Robbins 2014
  discuss centring on a neutral category, abstract via jstatsoft.org).
- **The scale comes from the questionnaire, never from the answers seen** (this skill's rule, shared with
  `csat-ces-analysis` and `ux-scale-scoring`). Answers show only the points someone chose: 1-4 answers from a
  5-point item would otherwise become a 1-4 scale with the midpoint in the top box. The scale is `--scale`,
  the lowest and highest points of `--labels`, or the one built-in label map that fits the text answers;
  when the labels fit maps of different lengths ("Agree" and "Neutral" are on the 5- and 7-point agree
  scales) or numbers come with no scale, the script stops and asks.
- **Labelled numbers carry the questionnaire's end labels** (this skill's rule, shared by `csat-ces-analysis`,
  `likert-analysis` and `ux-scale-scoring`). Answers such as "1 - Very dissatisfied" ... "5 - Very satisfied"
  set the scale from the lowest and highest labelled codes only when both labels read as end points (very,
  extremely, strongly, completely, totally, entirely, absolutely, highly, at all; never "not very ...") and no
  plain number falls outside them; the scale line names the two labels. An end label on a code nobody chose
  cannot be seen, so a 7-point scale whose "7 - Extremely satisfied" went unused would read as 1-6 if "6 - Very
  satisfied" were chosen: pass `--scale` when the questionnaire had more points.

## Medians or means

- A single Likert-type item is ordinal: the gaps between "agree" and "strongly agree" need not be equal.
  Lead with the distribution and the top/bottom box; the median and mode describe the centre (Sullivan and
  Artino 2013, abstract and excerpts via PMC3886444). The median of an even number of answers whose two
  middle values differ is their midpoint (for example 3.5), which is not a scale point; the script notes it.
- Means and parametric tests are robust for Likert data in practice, including small samples and skewed
  distributions, and are appropriate for **scale scores** built from several items (Norman 2010, abstract via
  doi.org). The script prints the mean with a t interval for every item and for the scale score, and the
  skill tells the agent which to lead with: distribution and box for single items, mean for scale scores.

## Diverging stacked bars

- Heiberger and Robbins (2014) recommend diverging stacked bars, centred on the neutral point, as the primary
  display for Likert items (abstract via jstatsoft.org). The script prints, per item, the percent below,
  at and above the midpoint and a text bar aligned on a common centre column; `--table-out` writes the same
  table for a charting tool, keeping items with no readable answers as empty rows. A
  critique favouring plain 100% stacked bars exists (Datawrapper blog); either is fine if the neutral share is
  shown.

## Reverse-coded items

- A negatively worded item ("I often think about quitting") must be recoded as min + max − x before it joins
  a scale (`--reverse`). The recoding applies only to the reliability check and the scale score: item
  distributions, boxes and item comparisons stay as answered, so "agree" still means agreeing with the
  printed wording. The script flags items whose **corrected item-total correlation** (the item against
  the sum of the other items) is negative: they run against the rest. This is a detection heuristic of this
  skill; it does not prove the item is reverse-worded. Check the wording before recoding, and never reverse
  an item just because alpha rises.
- Items with a corrected item-total r between 0 and 0.3 are listed as weak fits (a common rule of thumb,
  convention of this skill; not a cut-off from a cited source).

## Cronbach's alpha

- α = k/(k − 1) · (1 − Σ s²ᵢ / s²ₜ), with sample variances of the k items and of the total (Cronbach 1951,
  not re-checked). Computed on respondents who answered every scale item (listwise); alpha-if-item-deleted
  uses the same respondents so the two are comparable.
- Independent check in the tests: alpha equals Hoyt's (1941) ANOVA reliability, 1 − MS_residual/MS_persons,
  from a persons × items two-way layout.
- **Feldt interval:** (1 − α)/(1 − α̂) follows F(n − 1, (n − 1)(k − 1)), so the interval is
  1 − (1 − α̂)·F₁₋γ/₂ to 1 − (1 − α̂)·Fγ/₂ with γ = 1 − confidence (Feldt 1965; Feldt, Woodruff and Salih 1987, not re-checked;
  formula as implemented in Kromrey, Romano and Hibbard 2008, read). F quantiles come from bisection on the
  regularized incomplete beta function. The F distribution follows from normal, essentially parallel items;
  on skewed ordinal items treat the interval as model-based, not exact (via review, not re-checked).
- When every respondent has the same total (items that cancel each other out), alpha is undefined, but the
  corrected item-total correlations are still printed: that is where reversed items show up (−1).
- **Published check:** Kromrey et al. (2008) Table 1, 12 respondents × 5 dichotomous items: α = 0.833,
  Feldt 95% interval 0.616 to 0.945 (read; `fixtures/kromrey_2008.*`).
- **Reading alpha:** 0.70 is the conventional "acceptable" value, but it is arbitrary, was not Cronbach's
  rule, and a very high value (above about 0.95) can mean redundant items rather than a better scale;
  alpha assumes the items measure one thing and says nothing about validity (Taber 2018, abstract and the
  author's summaries read). The script prints alpha with its interval and gives no pass/fail verdict.

## Group comparisons

- **Per item: Mann-Whitney U** (Mann and Whitney 1947, not re-checked). U for group A = R_A − n_A(n_A + 1)/2,
  equal to R's `wilcox.test` statistic W. Two-sided p:
  - both groups under 50 answers (`--mw-method auto`): exact. Without ties, the usual rank-sum distribution;
    with ties, the conditional (permutation) distribution given the observed ties. The R-devel
    `wilcox.test` help describes that conditional inference (read). **R 4.5.1 does not do it by default:**
    on tied data `wilcox.test` uses the tie-corrected normal approximation, and `exact = TRUE` warns that it
    cannot compute an exact p (checked here on the engagement fixture: R gives 0.008375 for eng_1, this
    script's default gives 0.00607). SciPy and SPSS defaults also differ on ties (via review, not re-run).
    To match those tools, pass `--mw-method normal`. Two-sided exact p is twice the smaller tail, capped at
    1 (as R does without ties); some tools (coin, SAS) use the distance from the expected rank sum instead,
    which can give a smaller p on skewed, unequal groups (via review, not re-checked).
  - Item means get a t interval clipped to the scale's ends; scale-score intervals are not clipped. All the
    same answers give a zero-width interval, flagged in the output as saying nothing about precision.
  - otherwise: normal approximation with the tie-corrected variance
    n_A n_B/12 · ((N + 1) − Σ(t³ − t)/(N(N − 1))) and a continuity correction of 0.5 (R's `correct = TRUE`).
  - Published check: Hollander and Wolfe (1973, p. 69) permeability data, the R help example: W = 35, exact
    two-sided p = 0.2544 (the help page shows the call; the numbers are R's output, recomputed here).
  - Independent checks in the tests: exact conditional p against brute-force enumeration of every split, and
    the normal approximation against the variance computed directly from the midranks.
- **Effect size:** probability of superiority with half credit for ties, P(A > B) + ½P(A = B) = U/(n_A n_B)
  (Vargha and Delaney's A, not re-checked), printed under that full name because with many ties it differs
  from the strict P(A > B); and the rank-biserial correlation 2U/(n_A n_B) − 1.
- **Independence:** Mann-Whitney, the top-box tests and Welch all assume the two groups are different
  people. For the same people measured twice (before and after, two conditions) these tests are wrong; the
  script has no paired test, so say so and do not run them.
- **Top box per item:** difference of shares with a Newcombe (1998b) hybrid score interval; pooled
  two-proportion z-test, or Fisher's exact test when an expected count is under 5 (Cochran 1954 rule).
- **Scale score:** Welch t-test on the mean of the scale items (Norman 2010 supports parametric tests on
  summed scales), with the same floor of 5 respondents per side as the item tests.
- Many tests: Holm (1979) or Bonferroni (`--adjust`) over every test the run reports: each item's rank test,
  each item's top-box test and the scale-score test, for every pair. Each records `family_size`.

## Thresholds

- **Small base:** under 100 answers per item or group (`--min-base`): Pew Research Center (2022) generally
  does not report groups with an effective sample under 100, because their margin of error is then above
  about 10 points. It is a reporting-precision flag: a result that is not significant on a small base is
  flagged, not called "underpowered", since power depends on the effect size, not on n alone.
- **No verdict** with fewer than 5 answers on either side, for item and scale-score tests alike (convention
  of this skill).
- **Stop at more than 5% unreadable answers** (non-numeric, off-scale) among non-blank answers, overall or in
  any one item, so a mislabelled answer category is not dropped silently (shared pack convention).

## Pitfalls

- Reporting only the mean of a single item, or comparing items by mean when their distributions differ in
  shape (a polarised item and a neutral item can share a mean of 3).
- Building a scale without recoding reverse-worded items, or recoding the wrong ones.
- Treating alpha ≥ 0.70 as proof of a good scale, or reporting alpha for items that measure different things.
- Comparing groups on many items without adjusting, then reporting the smallest p-value.
- Averaging labelled answers without checking the label map (for example "Neutral" = 3 on a 5-point scale but
  4 on a 7-point scale).

## References

1. Likert, R. (1932). A technique for the measurement of attitudes. *Archives of Psychology* 140, 1-55.
   (Not re-checked.)
2. Cronbach, L. J. (1951). Coefficient alpha and the internal structure of tests. *Psychometrika* 16(3),
   297-334. (Not re-checked.)
3. Hoyt, C. (1941). Test reliability estimated by analysis of variance. *Psychometrika* 6, 153-160.
   (Not re-checked.)
4. Feldt, L. S. (1965). The approximate sampling distribution of Kuder-Richardson reliability coefficient
   twenty. *Psychometrika* 30, 357-370. (Not re-checked.)
5. Feldt, L. S., Woodruff, D. J. and Salih, F. A. (1987). Statistical inference for coefficient alpha.
   *Applied Psychological Measurement* 11(1), 93-103. (Not re-checked.)
6. Kromrey, J. D., Romano, J. and Hibbard, S. T. (2008). ALPHA_CI: a SAS macro for computing confidence
   intervals for coefficient alpha. SAS Global Forum 2008, paper 230-2008.
   https://support.sas.com/resources/papers/proceedings/pdfs/sgf2008/230-2008.pdf (read: Feldt formula,
   worked example, Table 1.)
7. Taber, K. S. (2018). The use of Cronbach's alpha when developing and reporting research instruments in
   science education. *Research in Science Education* 48(6), 1273-1296. doi:10.1007/s11165-016-9602-2
   (abstract and author summaries read.)
8. Norman, G. (2010). Likert scales, levels of measurement and the "laws" of statistics. *Advances in Health
   Sciences Education* 15(5), 625-632. doi:10.1007/s10459-010-9222-y (abstract read.)
9. Sullivan, G. M. and Artino, A. R. (2013). Analyzing and interpreting data from Likert-type scales.
   *Journal of Graduate Medical Education* 5(4), 541-542. PMC3886444 (excerpts read.)
10. Heiberger, R. M. and Robbins, N. B. (2014). Design of diverging stacked bar charts for Likert scales and
    other applications. *Journal of Statistical Software* 57(5), 1-32. doi:10.18637/jss.v057.i05
    (abstract read.)
11. Mann, H. B. and Whitney, D. R. (1947). On a test of whether one of two random variables is
    stochastically larger than the other. *Annals of Mathematical Statistics* 18(1), 50-60. (Not re-checked.)
12. Hollander, M. and Wolfe, D. A. (1973). *Nonparametric Statistical Methods*. Wiley. (Example via R
    `wilcox.test` help, https://stat.ethz.ch/R-manual/R-devel/library/stats/html/wilcox.test.html, read.)
13. Vargha, A. and Delaney, H. D. (2000). A critique and improvement of the CL common language effect size
    statistics of McGraw and Wong. *Journal of Educational and Behavioral Statistics* 25(2), 101-132.
    (Not re-checked.)
14. Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of
    the American Statistical Association* 22, 209-212. (Not re-checked.)
15. Agresti, A. and Coull, B. A. (1998). Approximate is better than "exact" for interval estimation of
    binomial proportions. *The American Statistician* 52(2), 119-126. (Not re-checked.)
16. Newcombe, R. G. (1998a). Two-sided confidence intervals for the single proportion. *Statistics in
    Medicine* 17, 857-872; (1998b) Interval estimation for the difference between independent proportions.
    *Statistics in Medicine* 17, 873-890. (Examples via DescTools and m-Py/propint test suites.)
17. Cochran, W. G. (1954). Some methods for strengthening the common χ² tests. *Biometrics* 10, 417-451.
    (Not re-checked.)
18. Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of
    Statistics* 6, 65-70. (Not re-checked.)
19. Pew Research Center (2022). Why Pew Research Center typically can't report the views of smaller U.S.
    religious groups. https://www.pewresearch.org/short-reads/2022/08/08/why-pew-research-center-typically-cant-report-the-views-of-smaller-u-s-religious-groups/
    (read for the pack's `nps-analysis`.)
