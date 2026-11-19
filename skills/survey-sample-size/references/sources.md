# Survey sample size: method sources

Checked on 2026-11-12. Each entry says how it was checked: **primary** (the source itself was read) or
**secondary** (a reproduction or summary of the source was read).
Worked examples that reproduce the numbers are in [`../fixtures/README.md`](../fixtures/README.md).

Notation: z is the standard normal quantile (1.96 for 95% confidence or a two-sided alpha of 0.05; 1.645
for a one-sided alpha of 0.05; 0.8416 for 80% power; 1.2816 for 90% power). The script computes with the
exact quantile (`statistics.NormalDist`) and prints it to six decimals (1.959964). p is a proportion, q = 1 − p,
e the margin of error (half the width of the confidence interval), N the population size.

## Formulas

### Margin of error on a proportion (`proportion`)

- n0 = z² p q / e². Cochran's formula. With p = 0.5 and 95% confidence: 384.16, so **385** for ±5 points
  and 1067.11, so **1,068** for ±3 points.
- Finite population correction: n = n0 / (1 + (n0 − 1)/N). Example: N = 2,000 gives **323**.
- Reverse: e = z √(p q / n) × √((N − n)/(N − 1)). At p = 0.5, 95%: n = 80 gives ±11.0 points, n = 100
  gives ±9.8, n = 400 gives ±4.9.
- p = 0.5 is the default because p q is largest there, so it gives the largest n.
- Small counts. When the smaller category is expected to hold fewer than 10 responses (n p or n q under
  10), or when an observed count is given with `--x`, the script prints a **Wilson score interval** instead
  of a symmetric margin: centre (p + z²/2n) / (1 + z²/n), half-width z / (1 + z²/n) × √(p q / n + z²/4n²)
  (Wilson 1927). Example: 3 of 20 gives 5.2% to 36.0%, where the symmetric formula would give −0.6% to
  30.6%. The documented alternative is the Agresti–Coull interval (1998): ñ = n + z², p̃ = (x + z²/2)/ñ,
  p̃ ± z √(p̃(1 − p̃)/ñ); it is slightly wider and simpler to do by hand. Formulas secondary (Wikipedia,
  "Binomial proportion confidence interval", which cites Wilson 1927, Agresti and Coull 1998 and Brown, Cai
  and DasGupta 2001). The cut-off of 10 and the note at expected cell counts under 5 for two proportions
  are textbook conventions.
- Planning in the small-count region. When the n from Cochran's formula would leave fewer than 10 expected
  responses in the smaller category, the +/- formula claims precision the data cannot give (p = 0.001,
  ±5 points: Cochran says 2 responses, whose Wilson interval for 0 of 2 runs from 0% to 66%). The script
  then returns the smallest n whose Wilson interval at p reaches no more than e from p on either side
  (75 for that example). Brown, Cai and DasGupta (2001) show the Wald interval's coverage collapses for p
  near 0 or 1 and recommend Wilson there. The "both sides within e" criterion is this script's choice.
- In every mode the n returned is the first whole n that the reverse command (`--n`) calls sufficient:
  the script checks n − 1 and n with the same margin function the reverse command uses.
- Census. When `--n` equals `--population`, every member responded: the script reports the percentage as
  exact, with no sampling error (Cochran 1977, ch. 2: the finite population correction is 0 at n = N).
- Source: Israel 1992 (primary; it reproduces Cochran 1963 and gives the 385 and 323 examples). The
  reverse formula is the same equation solved for e.
- The correction matters little when the sample is a small fraction of the population. The usual cut-off
  is a sampling fraction of 5% (Cochran 1977, ch. 2).

### Margin of error on a mean (`mean`)

- n0 = (z σ / e)², with the same finite population correction. Example: σ = 15, e = 2, 95% gives 216.09,
  so **217**.
- Source: Illowsky and Dean, *Introductory Statistics* (OpenStax), section 8.1 (primary, read in the Lumen
  Learning copy of that section).
- Below about n = 30 the analysis should use a t interval, which is wider. The 30 is the usual textbook
  convention, not a sharp threshold.

### Design effect (`--deff`)

- Weighting (Kish): deff = 1 + CV²(w) = n Σw² / (Σw)²; effective sample size n_eff = (Σw)² / Σw² = n / deff.
- Clustering (Kish): deff = 1 + (m − 1) ρ, with m the average cluster size and ρ the intraclass correlation.
- The script multiplies Cochran's n0 by deff and then applies the finite population correction to that,
  n = m / (1 + (m − 1)/N) with m = n0 × deff, and divides a given n by deff before computing a margin of
  error. With these two steps the planned n and the reverse margin are exact inverses: solving
  e = z √(p q deff / n) √((N − n)/(N − 1)) for n gives n = m N / (N − 1 + m). Example: N = 500, deff 2,
  ±5 points: **304** (304 gives ±4.98 points; 303 gives ±5.003).
- Source: Kish 1965 (secondary: the formulas as reproduced in the Wikipedia article "Design effect").

### Two proportions, n per group (`compare --p1 --p2`)

- Default (`--variance pooled`): n = [z_α √(2 p̄ q̄) + z_β √(p1 q1 + p2 q2)]² / (p1 − p2)², p̄ = (p1 + p2)/2.
  Pooled variance under the null hypothesis, separate variances under the alternative, **no** continuity
  correction, equal group sizes. z_α is z(1 − α/2) for a two-sided test and z(1 − α) for a one-sided one.
  This is the formula of Fleiss, Levin and Paik (2003, ch. 4), and it is what R's `power.prop.test` solves.
  - 0.35 vs 0.50, α = 0.05 two-sided, power 80%: 169.3, so **170** per group (CUHK calculator page, which
    prints the formula's arithmetic and attributes it to Fleiss; primary for the example).
  - 0.50 vs 0.40: 387.3, so **388** per group (same page).
  - 0.50 vs 0.75, power 90%: **76.7** (R documentation for `power.prop.test`; primary for the example).
- `--variance unpooled`: n = (z_α + z_β)² (p1 q1 + p2 q2) / (p1 − p2)². Separate variances under both
  hypotheses; slightly smaller n (0.50 vs 0.60: 385 instead of 388). It is the formula most often written
  out in short guides, because it needs no pooled proportion.
- `--variance baseline`: n = [z_α √(2 p1 q1) + z_β √(p1 q1 + p2 q2)]² / (p1 − p2)². The null variance
  uses the baseline p1 only. This is the formula in the JavaScript of Evan Miller's A/B sample size
  calculator (primary: page source, function `num_subjects`), which also rounds to the nearest whole number
  where this script rounds up. 0.20 vs 0.25 gives 1030.2.
- `--method arcsine` (or `--h`): Cohen's effect size h = |2 asin √p1 − 2 asin √p2| and
  n = 2 (z_α + z_β)² / h² per group. This is what R's `pwr.2p.test` and statsmodels' `NormalIndPower`
  compute. Published examples: 0.10 vs 0.05 gives n = 423.7; 0.55 vs 0.50 gives n = 1564.5 (pwr vignette,
  primary for the examples). Cohen's conventions for h and for d are 0.2 small, 0.5 medium, 0.8 large (pwr
  vignette, secondary for Cohen 1988).
- `--lift L`: p2 = p1 (1 + L), a relative change; the calculation is then the same.
- `--continuity`: n′ = (n/4) [1 + √(1 + 4/(n |p1 − p2|))]², the Fleiss correction for equal groups
  (0.50 vs 0.60: 408 instead of 388). It adds about 2/|p1 − p2| per group. Secondary: the form was
  confirmed in summaries of calculators that cite Fleiss, Levin and Paik; the book was not read.
- Reverse (smallest detectable difference for a given n): the script searches for the p2 nearest p1 whose
  required n is at most the given n. Published check: n = 50 per group, p1 = 0.5, 90% power gives
  p2 = 0.8026 (R documentation for `power.prop.test`).
- Power for a given n and difference: the same equation solved for power,
  Φ[(|p1 − p2| √n − z_α s0) / s1] + Φ[(−|p1 − p2| √n − z_α s0) / s1] for a two-sided test, where s0 and
  s1 are the two square-root terms of the n formula. The second term is the chance of a significant result
  in the wrong direction: R's `power.prop.test` adds it with `strict = TRUE` and leaves it out by default
  (primary: R documentation, argument `strict`). It is negligible unless the difference is tiny (100 per
  group, 0.5 vs 0.5001: 0.050 with it, 0.025 without). The required n is solved with the usual one-tail
  approximation. Published check: n = 50, 0.50 vs 0.75 gives power 0.740 (R documentation). With the continuity correction the script first undoes it:
  n = (n′ − c)² / n′, c = (1 + 1/r) / (2 |p1 − p2|), which is the correction formula solved for n.
- Unequal groups, r = n2/n1 (`--ratio`, or `--n` with `--n2`): the variance of the difference is
  p̄ q̄ (1/n1 + 1/n2) under the null and p1 q1/n1 + p2 q2/n2 under the alternative, so
  n1 = [z_α √((1 + 1/r) p̄ q̄) + z_β √(p1 q1 + p2 q2 / r)]² / (p1 − p2)², p̄ = (p1 + r p2)/(1 + r), n2 = r n1,
  and the continuity correction becomes n1′ = (n1/4) [1 + √(1 + 2(1 + 1/r)/(n1 |p1 − p2|))]². With r = 1
  these are the equal-group formulas above. For h and d the effect is multiplied by √(n1 n2/(n1 + n2)).
  Published check for the last: h = 0.2, n1 = 543, n2 = 675 gives power 0.934 (pwr vignette,
  `pwr.2p2n.test`). The pooled and continuity forms with r are derived here and attributed to Fleiss, Levin
  and Paik.
- Several comparisons (`--comparisons m`): each test is run at α/m (Bonferroni). m = K − 1 for K groups
  against one control, K(K − 1)/2 for all pairs. The correction controls the family-wise error rate and
  "can be conservative if there is a large number of tests and/or the test statistics are positively
  correlated" (Wikipedia, "Bonferroni correction", secondary; Dunn 1961). Example: 0.50 vs 0.60 with three
  comparisons needs 517 per group instead of 388.
- Not covered: paired comparisons (the same respondents measured twice, or two answers from each
  respondent). Those use McNemar's test for percentages and a paired t test for means, and need the
  correlation between the two measurements; they usually need fewer respondents than this formula says.

### Two means, n per group (`compare --d`, or `--diff` with `--sd`)

- n = 2 (z_α + z_β)² / d², d = difference / SD (Cohen's d). At α = 0.05 two-sided and 80% power this is
  15.7 / d². Normal approximation to the two-sample t test, equal SDs, equal group sizes.
- The script adds Guenther's (1981) correction for the t distribution, z_α² / 4 per group (0.96 at
  α = 0.05), and reports both. d = 0.5: 63 by the normal approximation, **64** corrected. d = 0.8: 25,
  **26** corrected. d = 0.2: 393, **394** corrected.
- Cohen's (1988) conventions: d = 0.2 small, 0.5 medium, 0.8 large. They are conventions for when nothing
  better is known, not targets.
- With unequal groups (r = n2/n1): n1 = (1 + 1/r)(z_α + z_β)² / d² + z_α² / (2(1 + r)). The correction
  term spreads Guenther's z_α²/2 on the total across the two groups; it equals z_α²/4 when r = 1.
- Power for a given n: Φ[d √((n1 − correction) / (1 + 1/r)) − z_α], plus the same with −d for a two-sided
  test. Cross-check against exact noncentral-t
  software: n1 = 28, n2 = 35, d = 0.5 gives 0.493 here and 0.4925 in the pwr vignette (`pwr.t2n.test`).
- Power is for the difference assumed before fielding. Computing it afterwards from the observed difference
  ("post-hoc" or "observed" power) adds nothing: it is a function of the p-value. The script prints this
  warning and does not offer the calculation as a separate feature.
- Source: Guenther and Cohen. The uncorrected formula is the standard one and matches
  the hand arithmetic in the fixtures.

### Gap between two answers in the same sample (`gap`)

- For two shares of one question in one sample (42% chose A, 37% chose B), the shares are negatively
  correlated: Var(p1 − p2) = [(p1 + p2) − (p1 − p2)²] / (n − 1), so e = z √(that). Franklin 2007 (primary;
  he adapts it from Kish 1965, pp. 498–501).
- Published examples: n = 441, 30% vs 26% gives ±0.0698; n = 735, 31% vs 25% gives ±0.054 (Franklin 2007).
- The n at which a given gap exceeds its margin is the same equation solved for n: z² [(p1 + p2) −
  (p1 − p2)²] / (p1 − p2)² + 1.

### Net Promoter Score (`nps`)

- Score each respondent +1 (promoter, 9–10), 0 (passive) or −1 (detractor, 0–6). The NPS is the mean and
  its variance is Var = p_pro + p_det − (p_pro − p_det)² (Rocks 2016, section 1.4; primary through the
  sibling skill `nps-analysis`, which read the preprint in full).
- Margin: n0 = z² Var / e², then the design effect and finite population correction as for a proportion.
  40% promoters and 20% detractors: Var = 0.56, so ±5 NPS points at 95% needs **861**, against 385 for a
  single percentage. Reverse: e = z √(Var deff / n).
- Two independent scores: n per group = (z_α + z_β)² (Var1 + Var2) / d², d the NPS difference as a
  proportion. Lewis and Sauro (2021c, primary) give the same formula and subtract 3 when the analysis uses
  the adjusted-Wald test, which adds 3; the script keeps the 3. Their example: d = 0.10, Var1 + Var2 = 2,
  α = 0.05 two-sided, 80% power: 1,568 per group after −3 with z rounded to 2.802; the script gives 1,570.
- Default variance 0.67: MeasuringU's realistic maximum (adjusted variances 0.40 to 0.76 in 18 data sets;
  Lewis and Sauro 2021c). The absolute maximum is 1 (half promoters, half detractors).
- Under 30 responses the normal approximation is poor (Rocks 2016, Table 1); the script says to use the
  adjusted-Wald interval of `nps-analysis` instead.
- Two different samples (two waves, two segments) are independent: use `compare`.
- `nps --table` (this skill's choice of rows): n at ±3, 5, 7 and 10 NPS points with `--margin`; the margin
  at half, one, two and four times `--n` (as `proportion`); n per group (and power at `--n`) for 5, 10, 15
  and 20 point differences with `--diff`. Each row uses the formula above.

### Subgroups (`subgroups`)

- Total n = minimum base / smallest subgroup's share, rounded up.
- Default minimum base **100**: Sudman 1976 suggests 100 or more in each major subgroup and 20 to 50 in
  minor ones (secondary). A base of 100 gives ±9.8 points at p = 0.5, 95%.
- For conjoint and MaxDiff use 200 per subgroup (below).
- With `--margin` the base is the Cochran n for that margin at p = 0.5 (±10 points: 97), and the quota table
  lists, per subgroup, the total needed (base / share), the expected n at the chosen total, and its margin.
- `check` reports, for a given n: the overall margin, the smallest subgroup's margin or Wilson interval, and
  the smallest difference two equal halves of the sample could detect (the `compare` formulas with n/2 per
  group).

### Invitations (`invites`)

- Invitations = completes / (deliverability × response rate × incidence × completion rate).
- Here response rate = starts / delivered invitations, incidence = starters who qualify, completion rate =
  qualified starters who finish. This is plain funnel arithmetic, not a published formula.
- `--removal-rate`: the share of completed responses dropped in data cleaning. Completes to collect =
  usable completes / (1 − removal rate). The rate is the user's own; no default is assumed.
- The formal definitions of response, cooperation, refusal and eligibility rates are in AAPOR's *Standard
  Definitions*. No default response rate is given: rates vary too much by list, channel and incentive.

## Rules of thumb (not power calculations)

### Choice-based conjoint (`conjoint`)

- Johnson's rule: n t a / c ≥ **500**, where n = respondents, t = tasks, a = alternatives per task (not
  counting None), c = number of analysis cells: the largest number of levels in any attribute for main
  effects, the largest product of levels of any two attributes for two-way interactions. For aggregate
  full-profile CBC. Orme 2010/2019, ch. 7, p. 64 (primary).
- "500 was intended to be a minimum threshold"; **1,000** or more representations per main-effect level is
  better. Orme, ch. 7, p. 64 (primary).
- Example: 100 respondents × 10 tasks × 3 concepts / 3 brands = 1,000. Orme, ch. 7, p. 64 (primary).
- At least **300** respondents when subgroups are not compared; about **200** per group when they are (four
  segments: 4 × 200 = 800); 30 to 60 for investigational work; typical studies run from about 150 to 1,200.
  Orme, ch. 7, p. 65 (primary). Sawtooth's blog repeats "300 respondents per study, 200 per subgroup"
  and "at least 500 appearances per level" (primary).

### MaxDiff (`maxdiff`)

- Show **4 or 5** items per set, and no more than half of the items. Sawtooth, Lighthouse Studio manual
  (primary). Default **4** (3 for 6 or 7 items), the same default as the `maxdiff-design` skill, so that
  a hand-off between the two sizes the same design; pass the design's `--per-set` and `--sets` when it
  exists.
- Sets per respondent: enough for each item to appear **3** to 5 times; the minimum for individual-level
  (HB) scores is **3K/k** sets, K = items, k = items per set. The software warns under **2** times per
  respondent. Lighthouse Studio manual (primary).
- Sparse designs (each item seen once or less per respondent) can still give population-level scores when
  each item is seen by the segment or population of interest "at least **500** times and preferably **1000**
  times". Lighthouse Studio manual (primary).
- "Most MaxDiff surveys will have at least **200** respondents", or 200 per subgroup compared. Sawtooth
  MaxDiff calculator and design guidelines (primary).
- The rule the script uses, shared with `maxdiff-design` and `maxdiff-analysis`: "at least 300 respondents
  in total" and "at least 200 for every separately reportable subgroup", raised for more than about 30
  items (the post doubles both at 60 items). Sawtooth, "MaxDiff Sample Size Calculation Best Practices"
  (blog, primary as quoted by the `maxdiff-design` skill). The 200 above is the lower figure the same
  company gives elsewhere. Scaling by K/30 above 30 items is this script's reading of the doubling example.
- The 500/1000 rule counts **item exposures**, not respondents, and is written for sparse designs analysed
  with pooled models. The script applies it only when each item is shown fewer than 2 times per respondent
  (where Sawtooth's software warns and individual-level estimates are not supported); otherwise the
  respondent floors above decide.

## Qualitative studies: saturation (ranges, not formulas)

- Hennink and Kaiser 2022, systematic review of 23 articles: studies using empirical data reached saturation
  within **9–17 interviews** or **4–8 focus group discussions**, "particularly those with relatively
  homogenous study populations and narrowly defined objectives"; multi-country research, meta-themes and
  meaning saturation needed more. Across the tests, saturation came at 12–13 interviews on average
  (primary: abstract and discussion).
- Guest, Bunce and Johnson 2006: in 60 interviews, saturation occurred within the first **12**, and the
  basic elements for metathemes were present by **6** (abstract, secondary). Hennink and Kaiser's table
  summarises it as 12 interviews for 88% of codes.
- Hennink, Kaiser and Marconi 2017: in 25 interviews, code saturation ("heard it all") at **9**, meaning
  saturation ("understand it all") at **16 to 24** (abstract, secondary).
- Guest, Namey and Chen 2020: a way to report saturation rather than a fixed count. After a base of 4 to 6
  interviews, each run of 2 or 3 further interviews is compared with the base; stop when the run adds
  ≤5% (or 0%) new information. In their two homogeneous datasets the ≤5% threshold was met at 6 to 8
  interviews plus the run (primary).
- These counts are per fairly homogeneous group. A study with several distinct segments needs the range in
  each segment. The `interviews` command multiplies the cited range by the number of segments (9–17
  interviews or 4–8 focus groups per segment; 16–24 interviews when the goal is depth of meaning) and labels
  the result as guidance.

### The saturation check (`saturation`)

Guest, Namey and Chen 2020 (primary), as implemented:

- **Base size**: the first interviews, whose unique codes form the denominator. The paper tests 4, 5 and 6
  and says "a default base size of four interviews is sufficient". Default **4**.
- **Run length**: the number of consecutive interviews in which new codes are counted. The paper offers 2
  or 3. Default **2**. Runs overlap: each shifts forward by one interview.
- **New information threshold**: new codes in the run / codes in the base. The paper proposes **≤5%** or
  0%. Default 0.05.
- Saturation is reported at the last interview before the first run that meets the threshold, as "n+run".
  The paper's example: base of 4 interviews with 37 codes; interviews 5–6 add 7 (19%); 6–7 add 4 (11%); the
  next run adds 1 (under 5%), so saturation is reached at interview 6, reported as "6+2".
- "Saturation should initially be assessed after six interviews" (4 + 2). A run length of 3 or the 0%
  threshold is the stricter choice.
- Input to the script: for each interview, in order, the number of codes first seen in that interview. An
  empty entry stops the run with the interview's number (an interview with no new codes is 0, not blank);
  a file may be one column, or name its column `new_codes` (or `--column`); comma, semicolon and tab files
  and a UTF-8 byte-order mark are read.

## Why other calculators give slightly different numbers

All figures below were recomputed with this script or by hand (fixtures N and R); α = 0.05 two-sided,
80% power, per group.

| Comparison | This skill (pooled, default) | `--variance unpooled` | `--method arcsine` (R `pwr.2p.test`, statsmodels `NormalIndPower`) | `--variance baseline` (Evan Miller's calculator, rounds to nearest) |
|---|---|---|---|---|
| 0.20 vs 0.25 | 1,094 | 1,091 | 1,092 | 1,030.2 → he shows 1,030; rounded up 1,031 |
| 0.50 vs 0.60 | 388 | 385 | 388 | 390.1 → 390; rounded up 391 |
| 0.70 vs 0.55 | 163 (176 with `--continuity`) | 160 | 162 | 150.4 → 150; rounded up 151 |

- In these three examples the pooled, unpooled and arcsine results agree within about 2%. That is not a
  general bound: far from 0.5 they can differ by more (0.05 vs 0.50: 15 pooled, 12 unpooled, 13 arcsine
  per group). They are three approximations to the same test; none is "the" answer.
- The baseline-variance formula gives a visibly different n when the two proportions are far from 0.5 on the
  same side, because it ignores the second proportion in the null variance.
- R's `power.prop.test` uses the pooled formula and matches the default (it reports the unrounded n).
- Margin-of-error calculators that use z rounded to two decimals differ by a response or two: with z = 1.65
  for 90% and 2.58 for 99%, ±5 points gives 273 and 666; with exact z (1.645, 2.576) it gives **271** and
  **664**. SurveyMonkey's calculator page lists 1.65 and 2.58 (primary for the table of z-scores).
- Some planners subtract z² from Cochran's n (n = z² p q / e² − z², which sizes an adjusted-Wald interval):
  381 instead of 385 at ±5 points. The difference is 4 responses at 95% whatever the margin.
- Calculators that round to the nearest whole number can show one fewer than this script, which always
  rounds up.

## Where practitioners disagree

- **Pooled or unpooled variance, continuity correction or not.** All three two-proportion formulas are in
  use and differ by a few percent (388, 385 and 408 per group for 0.50 vs 0.60). Match the planned test:
  the default matches an uncorrected chi-square or z test; use `--continuity` for a corrected chi-square or
  Fisher's exact test. Critics hold that the corrected formula overstates n.
- **Margins of error for opt-in samples.** AAPOR (2012): "it is impossible to develop statistically valid
  margins of sampling error from nonprobability surveys" such as opt-in online panels. Later AAPOR guidance
  allows model-based precision measures when the model is described. Many commercial reports still quote
  the simple-random-sample margin as a rough guide. With `--opt-in` the script relabels its statement as a
  simple-random-sample benchmark and says no design-based margin applies to the actual sample.
- **Order of FPC and design effect.** Some texts apply the finite population correction first and the
  design effect second. That n is not the inverse of the margin formula (N = 500, deff 2, ±5 points: 435,
  which the margin formula says gives ±2.4 points), so the script inflates by the design effect first.
- **Conjoint.** Johnson's rule is for aggregate models. For hierarchical Bayes, and for anything beyond a
  ballpark, Sawtooth recommends simulating the design with random respondents and checking standard errors
  (main effects below 0.05, interactions below 0.1).
- **Saturation.** Malterud, Siersma and Guassora (2016, "information power") and Braun and Clarke (2021)
  argue against fixed saturation counts, especially for reflexive thematic analysis. Treat the ranges above
  as starting points to justify, not targets to hit.
- **Subgroup minimums.** 100 per subgroup is a convention. A subgroup comparison that must detect a stated
  difference needs the `compare` calculation instead, which usually asks for more.

## Sources

1. Israel, G. D. (1992). *Determining Sample Size* (PEOD-6). University of Florida IFAS Extension.
   https://edis.ifas.ufl.edu/publication/PD006 (reproduces Cochran, W. G., *Sampling Techniques*, Wiley,
   2nd ed. 1963, 3rd ed. 1977.)
2. Fleiss, J. L., Levin, B., and Paik, M. C. (2003). *Statistical Methods for Rates and Proportions*, 3rd ed.,
   Wiley, ch. 4. Worked examples checked at https://www2.ccrb.cuhk.edu.hk/stat/epistudies/x2.htm and
   https://stat.ethz.ch/R-manual/R-devel/library/stats/html/power.prop.test.html
3. Orme, B. (2010, 2019). *Getting Started with Conjoint Analysis*, ch. 7, "Sample Size Issues for Conjoint
   Analysis", pp. 57–66. Research Publishers.
   https://content.sawtoothsoftware.com/assets/dd3f6a38-285f-441f-a88c-678d7c8aaffb ; Sawtooth Software,
   "Sample size rules of thumb": https://sawtoothsoftware.com/resources/blog/posts/sample-size-rules-of-thumb
4. Sawtooth Software. Lighthouse Studio manual, "Designing a MaxDiff study":
   https://sawtoothsoftware.com/help/lighthouse-studio/manual/maxdiff-designing-study.html ; "MaxDiff
   calculator and design guidelines": https://sawtoothsoftware.com/resources/maxdiff-calculator
5. Hennink, M., and Kaiser, B. N. (2022). Sample sizes for saturation in qualitative research: A systematic
   review of empirical tests. *Social Science & Medicine*, 292, 114523.
   https://doi.org/10.1016/j.socscimed.2021.114523
6. Guest, G., Bunce, A., and Johnson, L. (2006). How many interviews are enough? An experiment with data
   saturation and variability. *Field Methods*, 18(1), 59–82. https://doi.org/10.1177/1525822X05279903 ;
   Guest, G., Namey, E., and Chen, M. (2020). A simple method to assess and report thematic saturation in
   qualitative research. *PLOS ONE*, 15(5), e0232076. https://doi.org/10.1371/journal.pone.0232076

Also cited:

- Illowsky, B., and Dean, S. *Introductory Statistics* (OpenStax), section 8.1.
  https://openstax.org/books/introductory-statistics-2e/pages/8-1-a-single-population-mean-using-the-normal-distribution
- Kish, L. (1965). *Survey Sampling*. Wiley. Formulas as in https://en.wikipedia.org/wiki/Design_effect
- AAPOR (2012). "Understanding a credibility interval and how it differs from the margin of sampling error
  in a public opinion poll".
  https://aapor.org/statements/understanding-a-credibility-interval-and-how-it-differs-from-the-margin-of-sampling-error-in-a-public-opinion-poll/
- AAPOR. *Standard Definitions*. https://aapor.org/standards-and-ethics/standard-definitions/
- Hennink, M. M., Kaiser, B. N., and Marconi, V. C. (2017). Code saturation versus meaning saturation: How
  many interviews are enough? *Qualitative Health Research*, 27(4), 591–608.
  https://doi.org/10.1177/1049732316665344
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences*, 2nd ed.; Cohen, J. (1992). A
  power primer. *Psychological Bulletin*, 112(1), 155–159.
- Guenther, W. C. (1981). Sample size formulas for normal theory t tests. *The American Statistician*, 35(4),
  243–244.
- Sudman, S. (1976). *Applied Sampling*. Academic Press.
- Malterud, K., Siersma, V. D., and Guassora, A. D. (2016). Sample size in qualitative interview studies:
  Guided by information power. *Qualitative Health Research*, 26(13), 1753–1760.
- Braun, V., and Clarke, V. (2021). To saturate or not to saturate? *Qualitative Research in Sport, Exercise
  and Health*, 13(2), 201–216.

- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of the
  American Statistical Association*, 22(158), 209–212. Agresti, A., and Coull, B. A. (1998). Approximate is
  better than "exact" for interval estimation of binomial proportions. *The American Statistician*, 52(2),
  119–126. Brown, L. D., Cai, T. T., and DasGupta, A. (2001). Interval estimation for a binomial proportion.
  *Statistical Science*, 16(2), 101–133. Formulas as in
  https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval
- Franklin, C. H. (2007). *The "Margin of Error" for Differences in Polls*. University of Wisconsin, Madison.
  https://abcnews.com/images/PollingUnit/MOEFranklin.pdf
- Rocks, B. (2016). Interval estimation for the "Net Promoter Score". *The American Statistician*, 70(4),
  365–372. Preprint: https://arxiv.org/abs/1601.07235
- Lewis, J. R., and Sauro, J. (2021b). How to statistically compare two Net Promoter Scores. MeasuringU.
  https://measuringu.com/nps-significance-test/ ; (2021c). Sample sizes for comparing Net Promoter Scores.
  https://measuringu.com/nps-sig-test-sample-size/ (page read: formula n = s² Z² / d² − 3 and the
  1,568 example)
- Sawtooth Software. "MaxDiff Sample Size Calculation Best Practices".
  https://sawtoothsoftware.com/resources/blog/posts/maxdiff-sample-size
- Champely, S. *pwr: Basic Functions for Power Analysis*, vignette.
  https://cran.r-project.org/web/packages/pwr/vignettes/pwr-vignette.html
- Miller, E. Sample Size Calculator. https://www.evanmiller.org/ab-testing/sample-size.html
- Dunn, O. J. (1961). Multiple comparisons among means. *Journal of the American Statistical Association*,
  56(293), 52–64. Summary as in https://en.wikipedia.org/wiki/Bonferroni_correction
- SurveyMonkey. Sample size calculator. https://www.surveymonkey.com/mp/sample-size-calculator/

## Pitfalls

- Reporting "20% ± 35 points" from 5 responses. Under about 10 responses in the smaller category, report the
  count or a Wilson interval.
- Calling a 5-point lead "outside the margin of error" by comparing it with the survey's ±margin. The gap
  between two answers has its own, larger margin (`gap`).
- Computing power after the study from the observed difference.
- Sizing a before/after or within-respondent comparison with the independent-groups formula.

- Quoting a margin of error for an opt-in or convenience sample as if it were a random sample.
- Using the overall n for a claim about a subgroup. Each reported subgroup has its own, smaller n.
- Forgetting the design effect when the data will be weighted: the effective n is n / deff.
- Applying the finite population correction when the sample is under 5% of the population (it changes
  nothing), or forgetting it for a small population (it can cut n by a lot).
- Using a margin-of-error n to plan a comparison. Detecting a 5-point difference between two groups takes
  about four times the n per group that a ±5-point margin takes overall.
- Giving percentages where proportions are expected (5 instead of 0.05).
- Rounding n to the nearest whole number instead of up.
- Planning completes but not invitations: response rate, incidence and completion rate multiply.
- Reading an expected subgroup count as a guarantee. Without a quota it falls short about half the time.
- Treating the conjoint and MaxDiff rules as power calculations, or the 500 minimum as a target. The 500
  counts exposures (MaxDiff) or representations per level (conjoint), not respondents.
- Sizing an NPS like a single percentage: its variance is larger, so ±5 points takes about twice the n.
- Treating qualitative saturation ranges as statistical sample sizes, or reporting percentages from 12
  interviews.
- Several planned comparisons at α = 0.05 each without adjusting α.
