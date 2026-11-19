# CSAT and CES analysis: method sources

Checked on 2026-11-19. Each entry says how it was checked: "read" means the page or paper was opened and the
quoted rule found in it; "via" means the value was confirmed through a named secondary source; "not
re-checked" means the citation is from the standard literature and was not opened this session.

Contents: Metric definitions · Tool conventions · Intervals · Comparisons · Target test · Thresholds ·
Pitfalls · References

## Metric definitions

### CSAT

- There is no single standard CSAT question or formula. The common form asks overall satisfaction on a
  labelled 5-point scale (very dissatisfied to very satisfied) and reports the **percentage of satisfied
  answers, 4 and 5 (top-2 box), out of all answers** (Qualtrics, read). Some teams report the mean instead;
  Qualtrics notes means are possible but "CSAT scores are more usually expressed as a percentage". The script
  prints both, and the share is the headline.
- Satisfied band, this skill's default: the top two points on a scale of 5 or more points, the top point on a
  scale of 2 to 4 points; dissatisfied is the mirror image. Points outside both boxes are called "neutral"
  only when they are the scale's single midpoint (3 on 1-5); otherwise "middle (neither box)", because on a
  1-4 or 1-7 scale they include answers such as "satisfied" or "somewhat satisfied". The JSON keeps the key
  `neutral` for that residual and names it in `convention.middle_label`. The denominator is all valid
  answers. `--positive` and `--negative` override the bands.
- **The scale comes from the questionnaire, never from the answers seen** (this skill's rule). Answers show
  only the points someone chose: fifty 4s and fifty 5s fit a 1-5 and a 1-7 scale, and the satisfied share is
  100% on one and 0% on the other. So the scale is `--scale`, the metric's fixed scale (CES 1-7, CES 1.0
  1-5), the lowest and highest points of `--labels`, or the one built-in label map that fits the text
  answers; when text labels fit maps of different lengths (the five labels of a 5-point satisfaction scale
  also appear on the 7-point one) or numbers come with no scale, the script stops and asks. `--counts`
  gives the number of points directly (5 counts = 5 points), so only the numbering is assumed and printed.
- CSAT is not the ACSI. The American Customer Satisfaction Index is a 0-100 score estimated from three
  10-point questions in a latent-variable model with its own weights (Fornell et al. 1996, not re-checked;
  theacsi.com methodology page returned 403). A top-2-box CSAT is not comparable to an ACSI score.

### CES 1.0 (`--metric ces5`)

- Dixon, Freeman and Toman (2010), sidebar "Introducing the Customer Effort Score" (read): "CES is measured by
  asking a single question: 'How much effort did you personally have to put forth to handle your request?'
  It is scored on a scale from 1 (very low effort) to 5 (very high effort)." **Lower is better.** The
  article reports no top-box rule. The mean is the headline (printed first); the share of 1-2 ("low
  effort") and 4-5 ("high effort") is this skill's secondary convention.

### CES 2.0 (`--metric ces`)

- The later form is an agreement statement, usually "The company made it easy for me to handle my issue",
  on a 7-point scale from strongly disagree to strongly agree, higher is better; reports give the share who
  agree (5, 6 or 7) or the mean. Attributed to CEB/Gartner and to Dixon, Toman and DeLisi (2013).
  **Not confirmed from a primary source this session:** searches returned only secondary pages (vendor blogs),
  which disagree on the wording, and some describe a 1-7 "very difficult" to "very easy" ease scale instead.
  A reviewer pointed to CEB's published starter kit, the questionnaire and anchors in Appendix D of *The
  Effortless Experience* bonus PDF (gildan-bonus-content.s3.amazonaws.com/GIL1093_EffortlessExperience/
  GIL1093_EffortlessExperience_BonusPDF.pdf; not opened here). Both forms run 1-7 with higher = easier, so the
  same script settings fit both; say which wording was asked.
- The skill's "easy" band (top 3 of 7) and "difficult" band (bottom 3) follow those secondary descriptions. The
  bands count from the ends of the scale, so a 0-6 export of the same 7 categories gets 4-6 and 0-2.

## Tool conventions (for reconciling numbers)

| Tool | What it reports | How checked |
|---|---|---|
| Qualtrics | (number of 4s and 5s / number of responses) × 100 on 1-5 | qualtrics.com "What is CSAT", read |
| Zendesk | Good ratings / all ratings. Configured scales map to good and bad: 1-2 → 2 good; 1-3 → 3 good, 1-2 bad; 1-5 → 4-5 good, 1-3 bad. "Offered" = survey sent, not rated; "Unoffered" = not sent | support.zendesk.com article 4408846011546, read. Score formula (good / rated × 100) and 60-day window: via Zendesk community and third-party guides, not on the page read |
| Medallia | Not confirmed; programs configure their own CSAT definitions | not found |

Zendesk counts 3 on a 5-point scale as "bad", but its percentage is still good / all rated, so the share is
the same as top-2 box here. Zendesk shows no "dissatisfied" band of its own; this skill's dissatisfied share
(1-2) is smaller than Zendesk's "bad" share (1-3) on the same data. The script counts "Offered" and
"Unoffered" rows apart from other non-answers and prints the response rate rated / (rated + offered).

## Intervals

- **Share: Wilson score interval** (Wilson 1927, not re-checked; formula in fixtures/README.md). Chosen over
  the Wald interval p̂ ± z·√(p̂(1−p̂)/n), which has poor coverage for small n and for shares near 0 or 100%
  (Agresti and Coull 1998; Newcombe 1998a, not re-checked). Limits are set to exactly 0 when x = 0 and 100%
  when x = n. Published check: Newcombe (1998a) Table I examples 81/263, 15/148, 0/20, 1/29, values
  confirmed via the DescTools `BinomCI` documentation and by bisection; reproduced in
  `fixtures/wilson_newcombe_1998a.expected.json`.
- **Mean: Student t interval**, mean ± t₍₁₋α/2, n−1₎·s/√n, clipped to the ends of the scale. Not printed
  for a two-point (good/bad) scale, where a mean has no use beyond the share.

## Comparisons

- **Difference of two shares: Newcombe (1998b) method 10**, the hybrid score interval built from the two
  Wilson intervals: L = d − √((p̂₁ − l₁)² + (u₂ − p̂₂)²), U = d + √((u₁ − p̂₁)² + (p̂₂ − l₂)²). Published check:
  56/70 vs 48/80 → 0.0524 to 0.3339; 9/10 vs 3/10 → 0.1705 to 0.8090 (values via the m-Py/propint test
  suite, which cites the paper; reproduced in `fixtures/newcombe_good_bad.*`).
- **p-value, default (`--test auto`): pooled two-proportion z-test** (equal to Pearson's chi-square on the
  2×2 table without continuity correction; Agresti 2013, not re-checked), **switching to Fisher's exact
  test** when any expected count is under 5 (Cochran 1954 rule, not re-checked). Fisher two-sided p sums
  the probabilities of all tables with the observed margins that are no more likely than the observed table
  (the rule R's `fisher.test` uses, with relative tolerance 1e-7). The "any expected count under 5" switch is
  the common textbook convention (Agresti 2013, not re-checked); Cochran's own 2×2 recommendation was
  narrower (Fisher when N < 20, or 20-40 with the smallest expected count under 5; via review, not
  re-checked). Check: Fisher's tea-tasting table
  [[3,1],[1,3]] gives p = 0.4857 (Fisher 1935; Agresti 2013). Because the interval (Newcombe) and the test
  (z or Fisher) are different methods, a difference can rarely be "significant" with an interval that just
  touches 0, or the reverse; report both.
- **Difference of means: Welch t-test** (Welch 1947, not re-checked) with Welch-Satterthwaite df; printed
  next to the share test as raw supporting detail, not used for the verdict and not adjusted. Not printed
  when either side has fewer than 5 answers.
- **Verdicts:** "significant" (p < α, using the adjusted p when `--adjust` is set) or "not significant". A
  side under the small-base threshold is flagged `small_base`; it is not called "underpowered", because
  power depends on the effect size the reader cares about, not on n alone. Report the interval instead. No
  verdict when either side has fewer than 5 answers (this skill's convention).
- **Independence.** All tests assume each answer comes from a different, independently sampled customer.
  Several tickets from one customer, or the same panel in two periods, break that; pass `--id-col` to count
  repeats. The script then warns and does not correct the p-values.
- **Many comparisons:** Holm (1979) step-down or Bonferroni (`--adjust`) within two families fixed in
  advance: the segment share tests, and the period share tests (the trend or the named pair). Each tested
  comparison records `family` and `family_size`. The Welch mean tests and the target tests are not in a
  family and are labelled raw. Holm: sort ascending, multiply the i-th p-value by (m − i + 1), take the
  running maximum, cap at 1.

## Target test

- Score test of the share against a fixed target p₀: z = (p̂ − p₀)/√(p₀(1 − p₀)/n), one- or two-tailed;
  tail probabilities from erfc so far-tail p-values do not round to 0. The **two-tailed** test rejects at
  level α exactly when p₀ lies outside the two-sided (1 − α) Wilson interval (test
  `test_target_test_agrees_with_wilson`). A one-tailed test at α matches a two-sided (1 − 2α) interval, so
  it can be significant while the printed 95% interval still contains the target (41/100 vs 59: 59.0%,
  interval 49.2-68.1%, one-tailed p = 0.036). When n·p₀ or n·(1 − p₀) is under 5 the exact binomial tail is
  used instead (two-sided: twice the smaller tail, capped at 1); it is more conservative and can disagree with
  the Wilson interval. No verdict under 5 answers. `--target-mean` runs a one-sample t-test on the mean.
- The target must come from the user with its source and date. A fixed business goal is a target. Last
  year's score is an estimate with its own sampling error: compare the two waves as periods (both samples
  and their sizes) instead of testing against last year's figure as if it were fixed. This skill ships no
  "good CSAT" table: published bands (for example 75-85%) come from vendor blogs with no stated method.

## Thresholds

- **Small base, n under 100** (`--min-base`). Pew Research Center (2022) generally does not report groups
  with an effective sample under 100, because the margin of error is then generally above 10 percentage
  points (page read for the sibling `nps-analysis`; same rule). It is a reporting-precision flag, not a power
  rule. At n = 100 and 50% the Wilson half-width is about 9.6 points. Some historical Zendesk agent-ranking
  charts left out agents with fewer than 30 ratings (via a reviewer's reading of a Zendesk/GoodData
  whitepaper, not opened here); that is a display rule for those charts, not a precision rule.
- **Stop at more than 5% unreadable answers** (non-numeric, non-integer or off-scale, among non-blank
  answers): this skill's convention, shared with `nps-analysis`, so a mislabelled answer category is not
  dropped silently. Blanks and explicit non-answers (`N/A`, `Don't know`) are excluded and counted, not
  refused. A label map that reads all but a few stray text answers (a typo, "test") is still used; the stray
  ones count towards the 5%.

## Pitfalls

- Comparing a top-2-box CSAT with a mean CSAT, or a 5-point with a 7-point or 10-point CSAT. Convert nothing:
  report each with its convention.
- Comparing CES 1.0 (1-5, lower is better) with CES 2.0 (1-7, higher is better). They run in opposite
  directions.
- Reading the overall score as the mean of agent or channel scores. The overall share is pooled over
  answers; segments of different sizes make the two differ.
- Ranking agents on tiny bases. Twenty tickets at 80% satisfied give a Wilson interval from 58% to 92%.
- Treating a response-rate change as a satisfaction change. Post-ticket surveys answered by a few percent of
  customers lean towards the very satisfied and the very angry.

## References

1. Dixon, M., Freeman, K. and Toman, N. (2010). Stop Trying to Delight Your Customers. *Harvard Business
   Review* 88(7/8), 116-122. (Read: CES question and 1-5 scale in the sidebar.)
2. Dixon, M., Toman, N. and DeLisi, R. (2013). *The Effortless Experience*. Portfolio/Penguin. (Not read;
   CES 2.0 wording and 7-point scale attributed to it by secondary sources.)
3. Qualtrics. What is CSAT and how do you measure it?
   https://www.qualtrics.com/experience-management/customer/satisfaction-score/ (read).
4. Zendesk. CSAT survey results (good and bad mapped to configured scales).
   https://support.zendesk.com/hc/en-us/articles/4408846011546 (read).
5. Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of
   the American Statistical Association* 22, 209-212. (Not re-checked.)
6. Agresti, A. and Coull, B. A. (1998). Approximate is better than "exact" for interval estimation of
   binomial proportions. *The American Statistician* 52(2), 119-126. (Not re-checked.)
7. Newcombe, R. G. (1998a). Two-sided confidence intervals for the single proportion: comparison of seven
   methods. *Statistics in Medicine* 17, 857-872. (Table I values via DescTools `BinomCI` docs.)
8. Newcombe, R. G. (1998b). Interval estimation for the difference between independent proportions:
   comparison of eleven methods. *Statistics in Medicine* 17, 873-890. (Examples via
   https://rdrr.io/github/m-Py/propint/src/tests/testthat/test_Two_Independent_Props_CI.R, read.)
9. Fisher, R. A. (1935). *The Design of Experiments*. Oliver and Boyd. (Tea-tasting example; not re-checked.)
10. Cochran, W. G. (1954). Some methods for strengthening the common χ² tests. *Biometrics* 10, 417-451.
    (Not re-checked.)
11. Agresti, A. (2013). *Categorical Data Analysis*, 3rd ed. Wiley. (Not re-checked.)
12. Welch, B. L. (1947). The generalization of "Student's" problem when several different population
    variances are involved. *Biometrika* 34, 28-35. (Not re-checked.)
13. Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of
    Statistics* 6, 65-70. (Not re-checked.)
14. Pew Research Center (2022). Why Pew Research Center typically can't report the views of smaller U.S.
    religious groups. https://www.pewresearch.org/short-reads/2022/08/08/why-pew-research-center-typically-cant-report-the-views-of-smaller-u-s-religious-groups/
    (read for `nps-analysis`).
15. Fornell, C., Johnson, M. D., Anderson, E. W., Cha, J. and Bryant, B. E. (1996). The American Customer
    Satisfaction Index: nature, purpose, and findings. *Journal of Marketing* 60(4), 7-18. (Not re-checked.)
16. CEB (Corporate Executive Board). *The Effortless Experience* bonus materials, Appendix D: Customer Effort
    Score v2 questionnaire and anchors.
    https://gildan-bonus-content.s3.amazonaws.com/GIL1093_EffortlessExperience/GIL1093_EffortlessExperience_BonusPDF.pdf
    (cited by a reviewer; not opened here).
