# UX scale scoring: method sources

Checked on 2026-11-19. "Read" means the paper or page was opened and the rule found in it; "via" names the
secondary source a value was confirmed through; "not re-checked" means a standard citation that was not
opened this session.

Contents: SUS · All-positive SUS · SUS benchmarks · UMUX-Lite · SEQ · NASA-TLX · Statistics · Thresholds
and conventions · Pitfalls · References

## SUS

- Ten items answered 1 (strongly disagree) to 5 (strongly agree), odd items positive, even items negative.
  "For items 1,3,5,7, and 9 the score contribution is the scale position minus 1. For items 2,4,6,8 and 10,
  the contribution is 5 minus the scale position. Multiply the sum of the scores by 2.5" (Brooke 1996,
  read). Range 0-100. Brooke: "scores for individual items are not meaningful on their own."
- Equivalent form used for the independent check: ((Σ odd − 5) + (25 − Σ even)) × 2.5.
- Skipped items: Brooke tells respondents who cannot answer an item to "mark the centre point of the scale"
  (read). That is an instruction to respondents, not a rule for filling gaps after collection. The script
  excludes participants with skipped items by default; `--impute-midpoint` scores up to `--max-imputed`
  skipped items (default 1, this skill's convention) as 3, writes the count per participant to
  `--scores-out`, and prints the complete-case mean beside the result. Say which was used.
- Published check: Brooke's scored example totals 22 → 55 (`fixtures/brooke_1996.*`).
- A SUS on any scale other than 1-5, or with reworded items beyond small substitutions ("website" for
  "system"), is not the SUS; the benchmarks below do not transfer. The script refuses a non 1-5 SUS.

## All-positive SUS (`--instrument sus-positive`)

- Sauro and Lewis (2011) tested a version with all ten items worded positively. They found respondent and
  researcher coding mistakes in the alternating version (about 13% of questionnaires had respondent errors
  and 11% of datasets had been miscoded by researchers, via the abstract as quoted by secondary sources) and
  similar scores for both versions. Scoring: every item contributes position − 1, sum × 2.5.
- **Miscoding checks (this skill's heuristics, not from the paper):**
  1. Correlation across participants between the mean of the odd items and the mean of the even items. In
     the alternating SUS it should be negative; a value above +0.1 (with 10+ participants) suggests the data
     are the all-positive version, or the even items were already reversed before export. The reverse check
     runs for `sus-positive`.
  2. A participant whose odd-item mean and even-item mean are both 4 or more, or both 2 or less, agreed (or
     disagreed) with statements of opposite tone: a sign of misreading. Counted, kept by default,
     `--drop-flagged` removes them.
  3. Straight-lining (all ten answers equal) is counted; on the alternating SUS it scores exactly 50.

## SUS benchmarks

- **Average 68** (50th percentile) across a large set of studies (Sauro and Lewis 2016; MeasuringU "5 Ways
  to Interpret a SUS Score", Sauro 2018, read). Secondary sources give the SD of study means as 12.5; a
  normal curve with that SD does **not** reproduce the curved grading scale (it puts the 90th percentile at
  84, the table at 80.8), so the script does not use it.
- **Curved grading scale** (Sauro and Lewis 2016; Lewis and Sauro 2018 Table 1), confirmed from the
  MeasuringU page (read); the A+ row also via the JUS 2018 abstract page:

  | Grade | SUS | Percentile |
  |---|---|---|
  | A+ | 84.1-100 | 96-100 |
  | A | 80.8-84.0 | 90-95 |
  | A- | 78.9-80.7 | 85-89 |
  | B+ | 77.2-78.8 | 80-84 |
  | B | 74.1-77.1 | 70-79 |
  | B- | 72.6-74.0 | 65-69 |
  | C+ | 71.1-72.5 | 60-64 |
  | C | 65.0-71.0 | 41-59 |
  | C- | 62.7-64.9 | 35-40 |
  | D | 51.7-62.6 | 15-34 |
  | F | 25.1-51.6 | 2-14 |
  | F | 0-25 | 0-1.9 |

- **Percentile (this skill's convention):** linear interpolation between the lower bounds of the rows
  (score, percentile), anchored at (0, 0) and (100, 100), labelled "interpolated" in the output. Sauro and
  Lewis (2016, Tables 8.4-8.5) publish finer percentile anchors (via review, not opened here); this
  approximation is good to a few points and gives 68 → 50.3. The grades and percentiles describe a
  **study mean** against other studies' means, not one participant.
- **Adjectives** (Bangor, Kortum and Miller 2009): mean SUS of participants choosing each adjective: Worst
  Imaginable 12.5, Awful 20.3, Poor 35.7, OK 50.9, Good 71.4, Excellent 85.5, Best Imaginable 90.9. Values
  confirmed via the reproduction in arXiv:2311.10911 (Table 1; a reviewer also matched them to Bangor et al.
  2009 Table 3). The script prints the adjective whose mean is closest to the score and calls it that
  ("closest Bangor adjective"): it is this skill's assignment rule, not a published one; Sauro and Lewis
  assign adjectives by score ranges, which can differ near the boundaries. Bangor et al. note "OK" may read
  as acceptable although it sits well below average.

## UMUX-Lite

- Two items on a 7-point agree scale: "This system's capabilities meet my requirements" and "This system is
  easy to use" (Lewis, Utesch and Maher 2013, read).
- Score: "subtract 1 from each 7-point item, add them together, then multiply by 100/12" (read). For a
  5-point version the script uses the same rule over its range: Σ(x − 1)/(2 × 4) × 100.
- SUS-equivalent: "UMUX-LITE = .65(UMUX(1,3)) + 22.9", a regression on n = 791 that brought the scores into
  line with the SUS (read). It maps 0-100 onto 22.9-87.9. Lah, Lewis and Šumak (2020) later found the
  regression underestimates SUS at high levels of perceived usability (via search abstracts, not read), and
  Lewis's later work recommends the unadjusted UMUX-Lite as the SUS stand-in (Lewis 2021, chapter preprint
  cited by a reviewer, not opened here). So the script grades the **raw** UMUX-Lite on the SUS curved
  grading scale and prints the regression SUS-equivalent as secondary, for 7-point data only. Its interval is
  the transformed interval of the mean; it carries no prediction or calibration error.

## SEQ

- Single Ease Question after each task, 7 points, 1 = very difficult to 7 = very easy in the current form
  (Sauro and Dumas 2009, not re-checked). The 2009 study placed "very easy" on the left (MeasuringU, "The
  evolution of the SEQ", via review, not opened here), so exports can run either way. Labelled answers with
  "easy" at 1 stop the script; `--seq-reversed` scores them as 8 − x. The script reports the mean with a t interval per task. MeasuringU reports a historical
  average near 5.5 (blog, not re-checked); the script ships no SEQ benchmark: pass `--target`.

## NASA-TLX (raw)

- Six subscales: mental demand, physical demand, temporal demand, performance, effort, frustration, each
  rated 0-100 in steps of 5 (21 marks on the paper form). Performance runs from "perfect" (0) to "failure"
  (100), so on the official form every subscale is "higher = more workload" (Hart and Staveland 1988, not
  re-checked).
- Raw TLX = the unweighted mean of the six subscales, the common simplification of the weighted
  pairwise-comparison score (Hart 2006, not re-checked). Lower is better. Ratings on 1-21 or 0-20 are
  rescaled linearly to 0-100 (`--scale`). If performance was asked as "how successful" with high = good,
  `--reverse-performance` flips it.

## Statistics

- Mean with a Student t interval, mean ± t₍₁₋α/2, n−1₎·s/√n, clipped to the score range. Sauro and Lewis
  (2016) recommend t intervals for questionnaire means at small samples (not re-checked).
- Two independent groups: Welch t-test with Welch-Satterthwaite df (Welch 1947, not re-checked).
- Same participants in both groups (within-subjects): paired t-test on per-participant differences. The
  independent test on paired data throws away the within-person correlation and is much less sensitive
  (see `fixtures/README.md` section 2). Rows without a participant id are never paired. In a paired run the
  overall line pools both designs (each person counted twice), so it gets no interval and no target test.
- Means and SDs use exact summation (`math.fsum`), and identical scores get an SD of exactly 0, so the
  zero-variance rule holds on every Python version (Python 3.9's float sum left a tiny SD and an enormous t).
- Against a target: one-sample t, two-tailed by default; `--tail above` for "is our SUS above 68" when the
  question was fixed before looking.
- p-values from the regularized incomplete beta function (continued fraction); checked against numerical
  integration of the t density in the fixtures.
- Several comparisons: Holm (1979) or Bonferroni (`--adjust`), over the comparisons as one family and the
  target tests (overall and per group) as another. Each records `family_size`.

## Thresholds and conventions

- **Small base: fewer than 12 participants** (`--min-base`), this skill's reporting convention. Its origin is
  Tullis and Stetson (2004), who drew repeated subsamples from one study comparing two websites and found
  that at n = 12 SUS subsamples usually reached the full-sample conclusion (a reviewer reads their Figure 7 as
  100% for SUS and 90% for CSUQ at 12; not re-checked here). That is one comparison of two sites, not a power
  rule for other instruments or effects. Results under it are flagged as a small base, not called
  "underpowered".
- **Stop at more than 5% unreadable item answers** among non-blank answers (shared pack convention): an
  off-scale SUS (7-point) or unknown text labels stop the script rather than silently dropping
  participants.

## Pitfalls

- Averaging item scores, or reporting items as percentages: SUS items are not meaningful alone.
- Comparing SUS with a "SUS" collected on a 7-point or 0-10 scale, or with reworded items.
- Scoring the all-positive version with the alternating formula, or the reverse: the odd/even check catches
  most cases.
- Reading the percentile or grade as a statement about individual users rather than the product's mean.
- Using an independent t-test for a within-subjects study.
- Comparing raw TLX with weighted TLX, or a TLX where performance was reversed with one where it was not.

## References

1. Brooke, J. (1996). SUS: a "quick and dirty" usability scale. In P. W. Jordan, B. Thomas, B. A. Weerdmeester
   and I. L. McClelland (eds), *Usability Evaluation in Industry*, 189-194. Taylor & Francis. (Read: scoring
   rule, centre-point instruction, scored example.)
2. Brooke, J. (2013). SUS: a retrospective. *Journal of Usability Studies* 8(2), 29-40. (Not re-checked.)
3. Bangor, A., Kortum, P. T. and Miller, J. T. (2008). An empirical evaluation of the System Usability Scale.
   *International Journal of Human-Computer Interaction* 24(6), 574-594. (Not re-checked.)
4. Bangor, A., Kortum, P. and Miller, J. (2009). Determining what individual SUS scores mean: adding an
   adjective rating scale. *Journal of Usability Studies* 4(3), 114-123. (Adjective means via
   arXiv:2311.10911 Table 1.)
5. Sauro, J. and Lewis, J. R. (2011). When designing usability questionnaires, does it hurt to be positive?
   *Proceedings of CHI 2011*, 2215-2224. doi:10.1145/1978942.1979266 (abstract via secondary sources.)
6. Lewis, J. R., Utesch, B. S. and Maher, D. E. (2013). UMUX-LITE: when there's no time for the SUS.
   *Proceedings of CHI 2013*, 2099-2102. (Read: items, scoring, regression.)
7. Lah, U., Lewis, J. R. and Šumak, B. (2020). Perceived usability and the modified technology acceptance
   model. *International Journal of Human-Computer Interaction* (2020; volume and pages not confirmed). (Finding via search abstracts.)
8. Sauro, J. and Dumas, J. S. (2009). Comparison of three one-question, post-task usability questionnaires.
   *Proceedings of CHI 2009*, 1599-1608. (Not re-checked.)
9. Hart, S. G. and Staveland, L. E. (1988). Development of NASA-TLX (Task Load Index): results of empirical
   and theoretical research. In P. A. Hancock and N. Meshkati (eds), *Human Mental Workload*, 139-183.
   North-Holland. (Not re-checked.)
10. Hart, S. G. (2006). NASA-Task Load Index (NASA-TLX); 20 years later. *Proceedings of the Human Factors
    and Ergonomics Society Annual Meeting* 50(9), 904-908. (Not re-checked.)
11. Sauro, J. and Lewis, J. R. (2016). *Quantifying the User Experience*, 2nd ed. Morgan Kaufmann. (Curved
    grading scale via ref. 12 and 13.)
12. Lewis, J. R. and Sauro, J. (2018). Item benchmarks for the System Usability Scale. *Journal of Usability
    Studies* 13(3), 158-167. (Table 1 A+ row via search snippet; PDF returned 404.)
13. Sauro, J. (2018). 5 ways to interpret a SUS score. MeasuringU. https://measuringu.com/interpret-sus-score/
    (read: grading table, average 68.)
14. Tullis, T. S. and Stetson, J. N. (2004). A comparison of questionnaires for assessing website usability.
    *Usability Professionals Association Conference*. (Not re-checked.)
15. Welch, B. L. (1947). *Biometrika* 34, 28-35; Holm, S. (1979). *Scandinavian Journal of Statistics* 6,
    65-70. (Not re-checked.)
16. Lewis, J. R. (2021). "Usability and user experience: design and evaluation", chapter 38 (preprint).
    https://measuringu.com/wp-content/uploads/2023/10/2021_UsabilityAndUserExperienceDesignAndEvaluation_Chapter38_Preprint.pdf
    (cited by a reviewer for the recommendation to use unadjusted UMUX-Lite; not opened here).
17. Sauro, J. (n.d.). The evolution of the Single Ease Question (SEQ). MeasuringU.
    https://measuringu.com/evolution-of-seq/ (cited by a reviewer for the anchor order of the 2009 form; not
    opened here).
