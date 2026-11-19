# Survey crosstabs: method sources

Checked 2026-11-19. Each entry says how it was checked. "Convention of this skill" marks a choice no primary
source makes for us; it is a flag the user can change.

## Contents

- Column percentages and bases
- Pairwise column-proportion tests and letters
- Multiple comparisons
- Chi-square test of independence
- Intervals
- Means
- Weights and effective sample size
- Small bases
- Anonymity rule (small cells)
- Reconciling with other tools
- Sources

## Column percentages and bases

- Column percentage = weighted count in the cell / weighted base of the column. Unweighted, the weight is 1.
- A respondent with no answer to the row question is left out of every base in that table; a respondent with no
  banner value is counted in Total only, so Total can exceed the sum of the groups. Both counts are printed.
- Coded labels: an answer is read as a numeric code only when the number is followed by an explicit delimiter
  (`-`, `–`, `—`, `:`, `=`, `.`, `)`) or written in parentheses: "5 - Very satisfied", "(5) Very satisfied". So
  "1 week", "18 to 24" and "50k-75k" stay separate text answers, and two different labels on one code ("1. Jan",
  "1. Feb") make the column text, not codes. Convention of this skill, shared with `survey-weighting` so the two
  key categories the same way.
- Numbers: "0,75" is read as a decimal comma, "1,020,000" as comma thousands; "1,020" could be either, so a
  weight written that way stops the run. Counts (`--count-col`) are whole numbers, so "1,000" is 1000 there.
  Convention of this skill.
- Multi-select rows: the base is everyone who answered the question; each option is a yes/no share of that base,
  so shares add to more than 100% and no chi-square is computed (the options are not mutually exclusive).
- Reporting the base with every percentage follows the AAPOR Code of Professional Ethics and Practices (2021),
  section III.A (disclose sample sizes and the bases of percentages). Read from aapor.org in an earlier pass of
  this pack; not re-fetched today.

## Pairwise column-proportion tests and letters

- Pooled two-proportion z-test (Agresti 2007, section 2.2; Fleiss, Levin and Paik 2003, chapter 3):
  p̄ = (n₁p₁ + n₂p₂)/(n₁ + n₂), z = (p₁ − p₂)/√(p̄(1 − p̄)(1/n₁ + 1/n₂)), two-sided p = 2(1 − Φ(|z|)),
  computed as erfc(|z|/√2) so it stays above 0 in the far tail (95/100 vs 5/100 gives 4.1 × 10⁻³⁷, the same as
  the one-df chi-square).
  z² equals Pearson's X² on the 2×2 table, which is what R `prop.test(..., correct = FALSE)` reports; the tests
  check this identity and reproduce R on the fixtures.
- Published check: Physicians' Health Study, placebo 189 of 11,034 heart attacks, aspirin 104 of 11,037
  (Agresti 2007, Table 2.3; the table number is from memory of the text, the counts and X² = 25.01 were
  reproduced in R `prop.test`). The script gives z = 5.001, p = 5.69 × 10⁻⁷.
- When any expected count n·p̄ or n·(1 − p̄) in the pair is under 5, the normal approximation is doubtful
  (Cochran 1954); the default `--test auto` then uses Fisher's exact test, two-sided as the sum of the
  probabilities of tables no more likely than the one observed (the R `fisher.test` convention; Fisher's
  tea-tasting table gives p = 0.4857). With weights there is no exact test, so the pair is left untested.
- Letters: each banner group gets a letter; a letter in a cell means that cell's share is significantly higher
  than the share in the lettered group. This is the IBM SPSS Custom Tables "compare column proportions"
  layout (the higher column carries the letter of the lower), Bonferroni-adjusted within each row by default in
  SPSS. Source read: spss-tutorials.com, "SPSS Chi-Square Test with Pairwise Z-Tests" (a tutorial that
  reproduces SPSS's p-values by hand). **IBM's own documentation page could not be read** (it rendered empty);
  whether SPSS pools the proportion in exactly this form is not confirmed from IBM. A reviewer reports that
  IBM's "Comparing column proportions" example (SPSS Statistics 31) leaves out answers whose share in a group
  is 0 or 1; this script tests them, so `--adjust bonferroni --family row --test z` matches SPSS's adjustment,
  not necessarily its letters. **Not confirmed by reading IBM's page here.**
- Letters are assigned once per banner from every row with a group, in alphabetical (or `--order`) order, so a
  group keeps its letter in every table of a run. With more than 26 groups letters continue AA, AB, ...; JSON
  gives each cell's letters as a list of tokens.
- Total is not tested against its own groups: a group is part of Total, so the two samples are not independent.
- Only groups of the same banner variable are compared with each other.

## Multiple comparisons

- Holm (1979) step-down: sort the m p-values; adjusted p₍ᵢ₎ = max over j ≤ i of min(1, (m − j + 1)p₍ⱼ₎).
  Controls the familywise error rate and is never less powerful than Bonferroni. Default of this skill.
- Benjamini and Hochberg (1995) step-up: adjusted p₍ᵢ₎ = min over j ≥ i of min(1, m·p₍ⱼ₎/j). Controls the false
  discovery rate. **Read in the original:** section 3.2, p. 295, 15 p-values from a thrombolysis trial; at 0.05
  Bonferroni rejects 3 hypotheses and the FDR procedure rejects 4 (p₍₄₎ = 0.0095 ≤ 4/15 × 0.05 = 0.013).
  Reproduced in the tests, along with R `p.adjust` values for Holm and BH.
- Bonferroni: min(1, m·p).
- Family: by default every pairwise test in one table (all answers × all pairs of groups, plus the mean row) is
  one family. `--family row` adjusts each answer row separately, as SPSS does. Convention of this skill: the
  table is the question the user asked, so it is the family. With exactly two answers the second row's tests
  repeat the first row's, so each comparison is counted once.

## Chi-square test of independence

- Pearson X² = Σ (O − E)²/E with E = row total × column total / grand total, df = (r − 1)(c − 1); p from the
  upper tail of the chi-square distribution, computed as the regularized upper incomplete gamma Q(df/2, X²/2)
  (series and continued fraction, Press et al. 2007, section 6.2). Checked against the 5% critical values for
  df 1, 2, 10 and 30.
- Published check: Agresti (2007) party identification by gender (females 762, 327, 468; males 484, 239, 477):
  X² = 30.07, df = 2, p = 2.95 × 10⁻⁷. This is the example in R's `chisq.test` help page (read today).
- Reliability rule (Cochran 1954): the approximation is doubtful when more than 20% of expected counts are under
  5 or any is under 1. The script prints a warning and, for an unweighted 2×2 table, Fisher's exact p. R's
  `chisq.test` warns when any expected count is under 5, a stricter rule; the fixture `basic` triggers R's
  warning but not Cochran's.
- Groups hidden by the anonymity rule are left out of the chi-square, and the chi-square (and Fisher's p) is
  withheld when any cell of the tested groups is hidden: with the bases and the other cells shown, X² is a
  function of the hidden counts and can be solved for them (a reviewer's example: two groups of 10, one with 0
  answers of category 1, X² = 20x/(20 − x) gave x = 2).
- `--test none` gives percentages only: no letters and no chi-square.
- With weights: the weighted table is rescaled so its total equals the Kish effective n of the respondents in
  the tested groups, then the Pearson formula is applied. That is the Pearson X² of the weighted shares on a
  sample of n_eff; it equals the weighted X² divided by the Kish design effect only when the weights sum to n.
  Rao and Scott (1981, 1984) correct X² with the design effects of the cell proportions, which need the sampling
  design; one overall Kish factor assumes the same design effect in every cell and ignores strata, clusters and
  replicate weights. So this is an approximation, labelled as one in the output; for a complex sample report
  percentages only (`--test none`) or use the R `survey` package's `svychisq`.
- With weights, a 2×2 table's z-test uses each group's own effective n, while the chi-square uses the pooled
  effective n of the tested groups, so z² and X² differ slightly (unweighted they are equal).

## Intervals

- Wilson (1927) score interval for each cell share on the column's base (effective base when weighted):
  (p + z²/2n ± z√(p(1 − p)/n + z²/4n²))/(1 + z²/n). Hand check: 30 of 40 gives 59.81% to 85.81%.
- Means: mean ± t(1 − α/2, n − 1)·s/√n, with n the effective base when weighted.

## Means

- Added with `--means` for rows whose answers are numeric codes (labels such as "5 - Very satisfied" are read
  by their number). Weighted mean Σwx/Σw; SD √(Σw(x − m)²/Σw × n_eff/(n_eff − 1)).
- Pairwise Welch (1947) t-test with Welch-Satterthwaite df; checked against R `t.test` on the fixture
  (p = 0.000139 for Free vs Pro). When neither group has any spread (every answer the same in both) the
  Welch t and df are undefined, so the pair is reported as not tested rather than given p = 0 (R `t.test` stops
  with an error in that case). Whether a mean is the right summary of a rating scale is a judgment the sibling
  `likert-analysis` covers.

## Weights and effective sample size

- Kish (1965, section 11.7; restated in Kish 1992) effective sample size n_eff = (Σw)²/Σw², equivalently
  n/(1 + cv²) with cv the coefficient of variation of the weights (population form). The design effect from
  weighting is n/n_eff = 1 + cv². The tests check the identity independently. Battaglia, Hoaglin and Frankel
  (2009) restate deff = 1 + cv² (read today on surveypractice.org).
- Tests on weighted data use each group's effective n in place of n and the weighted shares (the "effective
  base" approach). The approximation ignores any correlation between the weights and the answers and any
  clustering; it is usually conservative for raked weights. Convention of this skill, stated in the output.
- Rescaling all weights by a constant changes nothing (tested); effective bases are compared with the small-base
  cutoff with a relative tolerance of 10⁻⁹ so floating-point rounding (29.999999999999996) does not drop a test.
  Equal positive weights are recognized and give exactly the unweighted results, Fisher's exact test included
  (tested). All-zero weights stop the run.
- Weights should come from `survey-weighting` or the data provider; this script does not create them.

## Small bases

- Default 30 (`--small-base`): a column with a smaller (effective) base is flagged "!" and not tested.
  **Convention of this skill**, chosen because many research suppliers flag bases under 30 and the normal
  approximation is poor below it for shares far from 50%. No primary source sets 30 for crosstabs; Pew Research
  Center uses a larger minimum for reported subgroups in its own work (see `nps-analysis` sources). Change it
  with `--small-base`.

## Anonymity rule (small cells)

- Threshold rule (Hundepool et al. 2012, chapter 5, "Magnitude tabular data" and chapter 4 on frequency tables):
  a cell with fewer than k contributors is a disclosure risk and is suppressed (primary suppression); other
  cells are then suppressed so the primary ones cannot be recovered from row or column totals (secondary or
  complementary suppression). The book is the standard text of the Eurostat-funded ESSnet on statistical
  disclosure control. **Chapter numbers are from the table of contents seen in a catalogue listing, not the
  book itself.**
- k = 5 by default. **Vendor convention, not a standard:** 15Five's help centre gives 5 as its default
  minimum respondent threshold, lowerable to 3 or 4 with a warning; Dialog (support.dialog.nl) hides groups
  under 5 and also hides a larger segment when a smaller protected group would otherwise be exposed. Read
  today via search summaries. Qualtrics EX and Culture Amp defaults were **not confirmed**.
- What the script does (`--anonymity [K]`, unweighted counts of people):
  1. Refuses the run when the whole file has fewer than K respondents, and hides a whole table (answer labels
     included, since a listed answer shows someone chose it) when fewer than K people answered that question.
  2. Hides any group with fewer than K respondents, and any group passed with `--hide`; then, while the hidden
     groups together have fewer than K people, hides the smallest shown group too (Total minus the shown groups
     would otherwise reveal the hidden ones together).
  3. Hides every cell with 1 to K − 1 respondents. Zero cells are shown.
  4. Checks exactly what a reader could work out, then hides more until nothing is pinned down (below).
  5. Hides a net or mean in any column with a hidden cell, withholds pairwise tests involving hidden cells, and
     withholds the chi-square when any tested group has a hidden cell.
  6. Within one run, a group hidden in any table of a banner is hidden in every table of that banner, so tables
     cannot be subtracted from each other. Across waves, pass the same groups with `--hide`.
  7. Warns when everyone in a shown group gave the same answer (group attribute disclosure, Hundepool et al.
     2012), without hiding it.
- The exact check (step 4). The reader is assumed to know every count the JSON prints, that a hidden cell in a
  shown group or in Total is at least 1 (zeros are printed), that a hidden group has at least one member, and
  how many respondents have no banner value (printed as "No <banner>"). For a single-choice table each
  respondent is one unit of flow: source → group → answer → Total. Printed numbers are fixed; each hidden number
  (cell, Total cell, the no-banner remainder's cells, a hidden group's base) is an arc with its lower bound. Two
  tables that agree with everything printed differ by a circulation, which decomposes into cycles that each
  respect the bounds (conformal decomposition of network flows; Ahuja, Magnanti and Orlin 1993, flow decomposition, section number
  from memory). So
  a hidden value can take another value exactly when a cycle through its arc exists in the residual graph, which
  a graph search finds. The script hides more until (a) no hidden count of 1 to K − 1 has a single possible
  value, and (b) no hidden group, or no-banner remainder, of fewer than K people can only have given one answer.
  It prefers the smallest shown cell in the same row or column that resolves the case, then whole groups.
  Multi-select tables use the same check with group and Total sums left free, each hidden group's cells bounded
  by the hidden groups' combined base; tested against a separate brute force (`test_random_multi_select_tables`).
- Tested against an independent brute force that enumerates every integer table consistent with the printed
  JSON (`tests/test_survey_crosstabs.py`, class `AnonymityRecovery`, including 60 random single-choice and 25 random multi-select
  tables; about 1,000 more random tables were checked the same way during development).
- Limits, stated in the output where they apply: the check models counts, not weighted totals, so with
  `--weight` a reader with the weights could narrow hidden values (release unweighted tables for employee
  surveys); it protects the tables of one run, not extra cuts or other files released alongside; and it is a
  heuristic for which cells to add, not an optimal pattern (tau-ARGUS solves that as an optimisation problem).

## Reconciling with other tools

| Tool | Default | Reproduce with |
|---|---|---|
| IBM SPSS Custom Tables, compare column proportions | z-test, Bonferroni within each row | `--adjust bonferroni --family row --test z` |
| R `prop.test(correct = FALSE)` / `chisq.test(correct = FALSE)` | Pearson, no continuity correction | default (R's 2×2 `chisq.test` applies Yates by default: pass `correct = FALSE` in R) |
| Unadjusted letters (many dashboards) | none | `--adjust none` |
| Weighted tests on the actual weighted counts (inflated n) | none | not offered: it overstates significance |

Not confirmed: the defaults of Q Research Software, Displayr, Qualtrics Crosstabs IQ and Excel add-ins. Ask the
user what their tool does before calling either result wrong.

## Sources

- Agresti, A. (2007). *An Introduction to Categorical Data Analysis*, 2nd ed. Wiley. (Party-by-gender example
  via the R `chisq.test` help page, read 2026-11-19; aspirin counts reproduced in R.)
- AAPOR (2021). Code of Professional Ethics and Practices. aapor.org.
- Battaglia, M. P., Hoaglin, D. C. & Frankel, M. R. (2009). Practical considerations in raking survey data.
  *Survey Practice* 2(5). doi:10.29115/SP-2009-0019. Read 2026-11-19.
- Ahuja, R. K., Magnanti, T. L. & Orlin, J. B. (1993). *Network Flows: Theory, Algorithms, and Applications*.
  Prentice Hall. Flow decomposition and residual-graph cycles; standard result, not re-read today.
- Benjamini, Y. & Hochberg, Y. (1995). Controlling the false discovery rate. *JRSS B* 57(1):289-300. Read
  (scanned original), p. 295.
- Cochran, W. G. (1954). Some methods for strengthening the common χ² tests. *Biometrics* 10(4):417-451.
  Rule as restated by Agresti (2007); original not read.
- Fleiss, J. L., Levin, B. & Paik, M. C. (2003). *Statistical Methods for Rates and Proportions*, 3rd ed.
  Wiley. Not re-read today.
- Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scand J Stat* 6(2):65-70. Formula
  checked against R `p.adjust`.
- Hundepool, A. et al. (2012). *Statistical Disclosure Control*. Wiley. Not read in full (see above).
- Kish, L. (1965). *Survey Sampling*. Wiley. Kish, L. (1992). Weighting for unequal Pᵢ. *J Official Stat*
  8(2):183-200. Formula as restated by Battaglia et al. (2009).
- Press, W. H. et al. (2007). *Numerical Recipes*, 3rd ed., section 6.2 (incomplete gamma). Algorithm only.
- R Core Team. `chisq.test`, `prop.test`, `fisher.test`, `p.adjust`, `t.test` (stats package, R 4.x). Used to
  compute the fixture expectations independently.
- Rao, J. N. K. & Scott, A. J. (1981). The analysis of categorical data from complex sample surveys. *JASA*
  76:221-230; (1984) *Ann Stat* 12(1):46-60. Not read today; cited for the idea of dividing X² by a design
  effect.
- Welch, B. L. (1947). The generalization of Student's problem. *Biometrika* 34:28-35.
- Wilson, E. B. (1927). Probable inference. *JASA* 22:209-212.
- UK Government Analysis Function, "Statistical disclosure control for tables produced from surveys"
  (analysisfunction.civilservice.gov.uk). Cited by a reviewer for withholding statistics computed from
  protected cells; not read here.
- 15Five help centre, "How does engagement survey confidentiality work in 15Five?"; Dialog support, "How is the
  anonymity of engagement results ensured?". Read via search summaries 2026-11-19.
- spss-tutorials.com, "SPSS Chi-Square Test with Pairwise Z-Tests". Read via search summary 2026-11-19.
