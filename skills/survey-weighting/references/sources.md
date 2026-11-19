# Survey weighting: method sources

Checked 2026-11-19. Each entry says how it was checked. "Convention of this skill" marks a default no primary
source sets.

## Contents

- Raking (iterative proportional fitting)
- Convergence
- Cell weighting (post-stratification)
- Base weights, missing values and collapsing
- Trimming
- Design effect and effective sample size
- Weighted estimates and their intervals
- Choosing variables and targets
- Sources

## Raking (iterative proportional fitting)

- Start from base weights w (1 for every respondent unless `--base-weight`). For each raking variable in turn,
  multiply the weight of every respondent in category k by (target share of k × weight total) / (current
  weighted total of k). One pass over all variables is one iteration. Repeat until every margin is within the
  tolerance. This is the algorithm of Deming and Stephan (1940); Battaglia, Hoaglin and Frankel (2009) describe
  it step by step (read today) with an example from the IHB SAS raking macro.
- **Published worked example reproduced.** Battaglia et al. (2009), Exhibit 1 (read today as the image on
  surveypractice.org): two variables (3 and 2 categories), design weights summing to 44,850.82, control totals
  summing to 62,800.30, tolerance 1, "terminated at iteration 3". The exhibit prints margins only, so the 3×2
  table of design weights was solved from the iteration-1 margins and the iteration-2 VARIABLE1 margins
  (6 equations, 6 unknowns; `fixtures/README.md`). The script then reproduces, to the printed 2 decimals, the
  iteration-2 VARIABLE2 margins (30,708.98; 32,091.32) and the iteration-3 margins (22,154.09; 16,533.34;
  24,112.87 and 30,697.40; 32,102.90), none of which were used in the solve.
- With count targets that agree on one population total (within 1%), the script rakes straight to the totals
  (as the macro does), so the weights sum to the population. With shares or percents, weights are rescaled to
  average 1. Count totals that disagree are refused until the user picks a scale (`--scale-total`,
  `--scale-mean-one`): convention of this skill, so no population total is guessed.
- Target units (convention of this skill): the target column's name (`percent`, `share`, `count`), a `%` sign or
  `--target-unit` states the unit; otherwise a total within 0.01 of 1 means shares, within 1 of 100 means
  percents (rounding), and any other total means counts, except totals from 0.9 to 1.1 or 90 to 110, which are
  refused as ambiguous. Shares or percents outside the rounding slack are refused unless `--rescale-targets`.
  Numbers: `51,5` is a decimal comma, `1,020,000` and `1,020.5` use thousands commas, and `1,020` is refused
  because it could be either.
- Infeasible targets: if a category with a positive target has no weight left during raking (zero targets on
  one margin removed everyone another margin needs), the script stops instead of reporting all-zero weights.
  Before reporting or writing, it checks that the weights are finite, non-negative and have a positive total,
  and that every margin is within the tolerance (also after trimming).
- Raking matches the margins, not the joint distribution: the interaction structure of the starting table is
  kept. For two variables this means the odds ratio of the sample table is preserved (Mosteller 1968; Bishop,
  Fienberg and Holland 1975; neither re-read). The tests check this property directly.
- Independent check: a raking loop written separately in base R (`fixtures/r_reference.R`) gives the same
  weights for the `panel` fixture to 10 or more decimals.

## Convergence

- Default tolerance: every margin within 1 × 10⁻⁶ of its target share; default cap 1,000 iterations.
  Convention of this skill: raking is cheap, so exact margins cost nothing. Battaglia et al. (2009): raking
  "generally converges after a small number of iterations, say 3 to 10"; tolerances may be absolute (a total
  within 1) or relative (within 0.1 percentage point); set an iteration cap "(e.g., 75)".
- Iteration counts differ by when the check runs. The IHB macro checks the margins at the start of an
  iteration and reports "iteration 3"; this script checks at the end of each full pass and reports 2 passes for
  the same weights (tested).
- No convergence usually means the targets conflict with the sample's structure (for example every woman in
  the sample is young, but the targets need 50% women and 30% young). The script refuses and asks for
  collapsing or dropping a variable.

## Cell weighting (post-stratification)

- Weight = base weight × (target share of the cell × weight total) / (base-weighted total of the cell). Every
  cell then matches its target exactly (Kish 1965; Lohr 2010, not re-read today).
- Needs the joint population distribution and at least one respondent in every cell with a positive target.
  Cells with fewer than 5 respondents are flagged: their weights are unstable. Convention of this skill, not a
  published rule for post-stratification (Cochran's line of 5 is for chi-square expected counts and is not the
  basis here). Some weighting guidance asks for 20 or more respondents per cell; that figure was **not
  confirmed** against a source, so the script does not use it. Treat cells of 5 to 20 as worth a second look.
- Raking needs only the margins and copes with more variables; it is "the standard weighting method used by
  Pew Research Center and many other public pollsters" (Mercer, Lau and Kennedy 2018, read today).

## Base weights, missing values and collapsing

- `--base-weight`: design or selection weights to start from (for example 1/probability of selection, or a
  panel provider's weight). Rows with a missing, zero or unreadable base weight are refused when more than 5%
  of rows (pack rule), else excluded and counted. Excluded rows get a blank weight cell in the output, which
  `survey-crosstabs` excludes under the same 5% rule; rows in a zero-target category get weight 0, which it keeps
  in the unweighted base. Convention of this pack, chosen so the two skills report the same bases.
- `--collapse` mappings apply before the missing-value check, so a missing code (`NA`) or a blank (`(blank)`)
  can be mapped to a category on purpose.
- Missing raking values are refused by default. `--missing skip-margin` keeps those respondents' weights
  unchanged on that margin and applies the target shares to the respondents with a known value. Convention of
  this skill; the alternative is to impute the value before raking (Battaglia et al. 2009 discuss imputation of
  raking variables; not re-read in detail).
- Collapse categories that are small in the sample or the targets: "Small categories in the sample or in the
  control totals (say under 2%) are potential candidates for collapsing"; convergence "may be slow if any
  categories contain fewer than 1% of the sample cases" (Battaglia et al. 2009, read today). The script warns
  under 2% and refuses a target category with no respondents. The 2% line marks a candidate to inspect, not a
  rule: combining categories changes what the margin controls.

## Trimming

- `--trim-max R` caps weights at R × the mean weight, `--trim-min R` floors them; the weights are then re-raked
  and the cycle repeats until both the bounds and the margins hold (Battaglia et al. 2009 describe trimming to a
  lower bound L and an upper bound U inside the raking loop, "to reduce the mean squared error (MSE) of the key
  outcome estimates", and give no values for L and U).
- R = 5 is a common choice: Izrael, Battaglia and Frankel (2009), "Extreme survey weight adjustment as a
  component of sample balancing (a.k.a. raking)", list flagging weights over 4 or 5 times the mean as one
  common procedure and say "there are no strict rules". **Read only via a search-result summary; the paper (SAS
  Global Forum 2009, paper 247-2009 per the SAS proceedings URL support.sas.com/resources/papers/proceedings09/
  247-2009.pdf) was not opened by this skill's author.** The script warns above 5 × the mean but does not trim
  unless asked.
- The cap applies to the final weight relative to the mean. With unequal `--base-weight` design weights this can
  trim legitimate selection weights; capping the raking adjustment (final / base weight) instead is the other
  convention Izrael et al. describe (search summary only). This script caps final weights; say so when base
  weights vary widely.
- Respondents with weight 0 (a zero-target category) are left at 0 by trimming and not floored by `--trim-min`.
- Trimming trades bias for variance. Report estimates with and without trimming when they differ.
- When re-raking pulls weights back past the cap, the cap is reported as not met (the margins win). The script
  also warns when a positive weight is under 0.01 × the mean (convention of this skill: such a respondent counts
  for almost nothing, a sign that the margins are squeezing a sparse cell). The remedy beyond collapsing is
  bounded calibration (Deville and Särndal 1992; R `survey::calibrate` with `bounds`, Lumley 2010; not re-read),
  which this script does not implement.

## Design effect and effective sample size

- Kish (1965; 1992) design effect from unequal weighting: deff = n Σw²/(Σw)² = 1 + cv², with cv the coefficient
  of variation of the weights (population form, divisor n). Effective sample size n_eff = (Σw)²/Σw² = n/deff.
  Battaglia et al. (2009) restate deff = 1 + cv² (read today). Tested as an identity and against R.
- Battaglia et al. (2009) also use the ratio of the largest to the smallest weight as a diagnostic; printed.
- Flag above deff 2 (convention of this skill: the weighted sample is then worth half its size).
- With only `--base-weight COL` (no targets) the script reports these diagnostics for the existing weights and
  changes nothing.
- The variance uses two passes (mean first), so equal weights give a design effect of exactly 1, never below.
- Kish's deff covers unequal weights only. Clustering and stratification add their own design effects, which
  this script cannot see. It is an approximation, not a rule that weighting always loses precision: calibration
  to variables related to an outcome can reduce that outcome's variance (Deville and Särndal 1992; Lumley 2010;
  not re-read).
- Max/min is undefined when any weight is 0 (a zero-target category); the script reports it as undefined and
  counts the zero weights instead of dividing by the smallest positive weight.

## Weighted estimates and their intervals

- Weighted share = Σw over respondents in the category / Σw over respondents who answered. If that Σw is 0 (all
  who answered are in zero-target categories), no weighted estimate exists and the script says so.
- A coded answer label needs a delimiter or parentheses after the code (`5 - Very likely`, `5: Yes`, `5) Yes`,
  `(5) Yes`), so `1 week`, `18 to 24` and `50k-75k` stay distinct. Convention of this pack.
- Answer categories are keyed as `survey-crosstabs` keys them: by numeric code when every answer has one (`5`
  and `5 - Very likely` are one category), otherwise by the exact trimmed text (`Yes` and `YES` are two).
  Matching data values to target categories ignores case and spacing, and the script warns when it merged
  spellings that crosstabs would keep apart. Convention of this pack.
- Interval: Wilson (1927) on the Kish effective n. **An approximation** (convention of this skill): it ignores
  that raking reduces variance for outcomes correlated with the raking variables, and it ignores clustering.
  For publication-grade standard errors use replicate weights or linearization (R `survey` package,
  `svydesign` + `rake` + `svymean`; Lumley 2010). Not run here: the `survey` package was not installed on the
  build machine, so the script was **not** compared with `survey::rake`.
- Quantiles in the weight summary use linear interpolation (R type 7, its default); checked against R.

## Choosing variables and targets

- Pew's experiment (Mercer, Lau and Kennedy 2018, read today) raked opt-in samples on a core set (age, sex,
  education, race and Hispanic ethnicity, census division) and an expanded set adding political and civic
  variables; the choice of variables mattered more than the method. Weighting removes bias only on what it
  adjusts for and on outcomes related to those variables.
- Targets must describe the same population the survey claims to represent (adults, customers, employees),
  come from a named source with a date, and use the same category definitions as the questionnaire.

## Sources

- Battaglia, M. P., Hoaglin, D. C. & Frankel, M. R. (2009). Practical considerations in raking survey data.
  *Survey Practice* 2(5). doi:10.29115/SP-2009-0019. Read 2026-11-19, including Exhibit 1. (Some copies add
  D. Izrael as an author; the journal page lists three.)
- Bishop, Y. M. M., Fienberg, S. E. & Holland, P. W. (1975). *Discrete Multivariate Analysis*. MIT Press. Not
  read; cited for IPF properties.
- Deville, J.-C. & Särndal, C.-E. (1992). Calibration estimators in survey sampling. *JASA* 87(418):376-382.
  Not re-read; cited for calibration and bounded calibration.
- Deming, W. E. & Stephan, F. F. (1940). On a least squares adjustment of a sampled frequency table when the
  expected marginal totals are known. *Ann Math Stat* 11(4):427-444. Not read; the algorithm as restated by
  Battaglia et al. (2009).
- Izrael, D., Battaglia, M. P. & Frankel, M. R. (2009). Extreme survey weight adjustment as a component of
  sample balancing (a.k.a. raking). SAS Global Forum, paper 247-2009. Search summary only.
- Kish, L. (1965). *Survey Sampling*. Wiley. Kish, L. (1992). Weighting for unequal Pᵢ. *J Official Stat*
  8(2):183-200. Formula as restated by Battaglia et al. (2009).
- Kolenikov, S. (2014). Calibrating survey data using iterative proportional fitting (raking). *Stata Journal*
  14(1):22-59. Not read; further reading on raking with bounds (`ipfraking`).
- Lohr, S. L. (2010). *Sampling: Design and Analysis*, 2nd ed. Brooks/Cole. Not re-read.
- Lumley, T. (2010). *Complex Surveys: A Guide to Analysis Using R*. Wiley. Not re-read.
- Mercer, A., Lau, A. & Kennedy, C. (2018). For weighting online opt-in samples, what matters most? Pew Research
  Center ("How different weighting methods work", read 2026-11-19).
- Mosteller, F. (1968). Association and estimation in contingency tables. *JASA* 63:1-28. Not read; property
  tested directly.
- Wilson, E. B. (1927). Probable inference. *JASA* 22:209-212.
