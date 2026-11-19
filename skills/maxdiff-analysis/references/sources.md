# MaxDiff analysis: method sources

Checked on 2026-11-12. "Verified" means the statement was read in the source itself on that day
(web page or the PDF text), not in a summary of it. Derivations are in [method.md](method.md).

## Formulas and thresholds

| # | What the skill uses | Source | Status |
|---|---|---|---|
| 1 | Best rate `B/shown`, worst rate `W/shown`, score = best rate minus worst rate | [S1] "the percent of times each item was selected best less the percent of times each item was selected worst"; [S2] "subtract an item's worst count proportion from its best count proportion" | Verified |
| 2 | Best-minus-worst score `(B - W) / shown`, written `std.BW_i = (B_i - W_i) / (N r)` with `N` respondents and `r` appearances each | [S3], package overview | Verified |
| 3 | Score range -1 to +1 | [S1]: net score from 100 (always best) to -100 (always worst), in percent | Verified |
| 4 | Counts are complete information only in a balanced design; with imbalance the logit is "more complete and robust" | [S1], section "Individual-Level Logit" | Verified |
| 5 | Maxdiff (pair) model `P(b, w) = exp(u_b - u_w) / sum_{r != s} exp(u_r - u_s)` | [S4] Definition 4, eq. (3), with `b(x) = exp(u_x)`, stated there to agree with Marley & Louviere (2005); same formula in [S3] | Verified |
| 6 | Marginal model: best by `exp(u)`, worst by `exp(-u)`, both normalised over all shown items | [S5], section "The Logit Equation and MaxDiff" (worked example with four items, worst likelihoods summing over all four); [S10] p. 14-15: best and worst "coded as separate and independent sets", "All elements in the design matrix are multiplied by -1 in the set describing worsts" | Verified |
| 7 | Marginal sequential model: as 6, with the best item deleted from the worst choice set (the script's default) | [S3]: `model = "sequential"`, "deleting an item selected as the best in the worst choice set (that is, using a marginal sequential model)"; [S3] attributes the marginal models to Hensher, Rose & Greene (2015), Appendix 6B | Verified in [S3]; the book itself was not read |
| 8 | Aggregate logit pools respondents "as if a single respondent had completed a very long interview"; one item fixed at 0 for identification; standard errors are square roots of the variances of the estimates | [S5] | Verified |
| 9 | Raw logit utilities are interval-scaled; exponentiate to get a ratio scale | [S5] | Verified |
| 10 | Share of preference `exp(u_i) / sum_t exp(u_t)` | [S3], citing Cohen (2003), Cohen & Neira (2004), Lusk & Briggeman (2009) | Verified in [S3] |
| 11 | Probability scale: zero-centre, `exp(U_i) / (exp(U_i) + a - 1)`, `a` = items shown per set, then rescale to sum to 100 | [S10] p. 13, "Probability-Based Rescaling Procedure": the formula is printed as text, "Ui = zero-centered raw logit weight for item i", "a = Number of items shown per set", "we rescale the transformed values to sum to 100". [S6] has the same text with the formula as an image | Verified |
| 12 | Utility magnitude grows with respondent consistency, so raw utilities are not comparable between groups | [S5], section "Zero-Centered Interval Scale" | Verified |
| 13 | Minimum base 200 respondents, or 200 per subgroup that will be compared (`MIN_BASE = 200`) | [S7]: "at least 200 respondents or 200 respondents per sub-group" | Verified |
| 14 | Each item shown about 3 times per respondent gives stable scores even by counting | [S7] | Verified |
| 18 | Root likelihood: RLH, best value 1.0, worst "the reciprocal of the number of choices available in the average task" (0.25 for four items per set) | [S5] | Verified |
| 19 | RLH as `exp(LL / T)` and its chance level `exp(LL0 / T)`; for the sequential model with `a` items per set the chance level is `1 / sqrt(a (a - 1))` | Derived in [method.md](method.md), section 8, from the definition in row 18 | Derivation ours |
| 20 | Likelihood-ratio chi-square `2 (LL_model - LL_null)`, degrees of freedom = number of estimated parameters; the null model "predicts equal likelihood for each concept in each task" | [S11], section 12.2 A, eq. (1) | Verified |
| 21 | McFadden pseudo-R2 `1 - LL / LL0` | McFadden (1974) [S12] | Standard; not re-read |
| 25 | Marginal model is a composite likelihood: no chi-square reference or model SE; bootstrap kept | Varin, Reid & Firth (2011) [S14]; the redundancy is exact with two items per set (method.md, section 2) | Not re-read; the two-item case is derived |
| 22 | Best and worst answers may differ in scale; probability scores get "flatter" with noise, so groups that differ in noise should not be compared directly | [S10] p. 14 and footnote | Verified |
| 23 | Anchored MaxDiff (a utility threshold from a direct or indirect anchor question) exists as a separate method | [S10], "Anchored MaxDiff" | Verified; not implemented |
| 24 | Average share = 100 / number of items | Arithmetic: the shares sum to 100 | n/a |
| 15 | Bootstrap: resample whole respondents; percentile interval | Efron & Tibshirani (1993) [S8] | Standard; not re-read |
| 16 | Default 1000 bootstrap replicates (`BOOTSTRAP_REPLICATES = 1000`) | Common practice for percentile intervals, usually attributed to [S8] | Convention; not re-read |
| 17 | A finite estimate exists exactly when the "ranked above" graph is strongly connected | Derived in [method.md](method.md), section 5; the analogous condition for Bradley-Terry and Plackett-Luce models is attributed to Ford (1957) and Hunter (2004) [S9] | Derivation ours |

### Implementation constants (not from the literature)

These are numerical settings of the script, chosen by us. For comparison, Sawtooth's aggregate logit
stops after 20 iterations or when the gradient or likelihood change is below 1 in the fifth decimal [S5].

- `MAX_ITERATIONS = 50` Newton-Raphson iterations; `MAX_HALVINGS = 30` step halvings.
- `STEP_TOLERANCE = 1e-8` (largest change in a utility); `GRADIENT_TOLERANCE = 1e-6` per choice task.
- Cholesky pivot floor `1e-12`; likelihood-decrease slack `1e-12` relative.
- `SEED = 12345`: an arbitrary fixed default so that runs repeat. `CI_LEVEL = 95`.
- `MAX_FAILED_REPLICATE_SHARE = 0.05`: when more than 5% of bootstrap replicates have no finite logit
  estimate, utility and share intervals are withheld. The same 5% applies to an item's counting-score
  interval (replicates in which no resampled respondent saw it) and to a segment difference (replicate
  pairs lost in either segment). A convention of this script; no published threshold was found.
- `MAX_EXCLUDED_SHARE = 0.5`: above half of the sets excluded, the script stops unless
  `--allow-exclusions` is given. A convention of this script.
- A group with fewer than 2 respondents gets no bootstrap: every resample would be the same person.
- Bootstrap replicates skip the covariance matrix and the null log-likelihood, and a replicate whose
  warm-started fit stalls is refitted once from zero before it counts as failed.
- Long-format flags `0.0/1.0` and `FALSE/TRUE` are read as 0/1; the delimiter (comma, semicolon or tab)
  is read from each file's header unless `--delimiter` is given.
- `prob_higher_above` (share of bootstrap replicates in which the higher-ranked of two items stays
  higher) and the bootstrap interval of a difference between items or segments are ordinary uses of the
  bootstrap replicates, defined in [method.md](method.md), section 7. They are descriptive; the script
  reports no p-values.
- Percentiles use linear interpolation between order statistics (the common "type 7" definition).
- Fixture numbers (0.25 recovery tolerance, 120 simulated respondents, seed 20261112) are explained in
  [`../fixtures/README.md`](../fixtures/README.md).
- The run-time example in [input-formats.md](input-formats.md) (about 40 seconds) was measured once on
  one laptop on 2026-11-12.

## Sources

- **[S1]** Orme, B. (2009). *MaxDiff Analysis: Simple Counting, Individual-Level Logit, and HB.* Sawtooth
  Software Research Paper. https://content.sawtoothsoftware.com/assets/8e69929d-a089-4b93-a9f3-d4c64d156642
- **[S2]** Sawtooth Software, Discover help, "MaxDiff scores".
  https://sawtoothsoftware.com/help/discover/analysis/maxdiff/maxdiff-scores
- **[S3]** Aizaki, H. *support.BWS: Tools for Case 1 Best-Worst Scaling* (R package reference manual).
  https://cran.r-project.org/web/packages/support.BWS/support.BWS.pdf . Companion paper: Aizaki, H. &
  Fogarty, J. (2023). R packages and tutorial for case 1 best-worst scaling. *Journal of Choice
  Modelling*, 46, 100394. https://doi.org/10.1016/j.jocm.2022.100394
- **[S4]** Marley, A. A. J., Flynn, T. N. & Louviere, J. J. (2008). Probabilistic models of set-dependent
  and attribute-level best-worst choice. *Journal of Mathematical Psychology*, 52(5), 281-296. Author
  version read: https://opus.lib.uts.edu.au/bitstream/10453/8292/1/2007005449.pdf . It restates the
  maxdiff model of Marley, A. A. J. & Louviere, J. J. (2005). Some probabilistic models of best, worst,
  and best-worst choices. *Journal of Mathematical Psychology*, 49(6), 464-480.
  https://doi.org/10.1016/j.jmp.2005.05.003
- **[S5]** Sawtooth Software, Lighthouse Studio manual, "MaxDiff aggregate logit analysis".
  https://sawtoothsoftware.com/help/lighthouse-studio/manual/maxdiff-aggregate-logit-analysis.html
- **[S6]** Sawtooth Software, Lighthouse Studio manual, "MaxDiff analysis using CBC/HB" (rescaling).
  https://sawtoothsoftware.com/help/lighthouse-studio/manual/maxdiff-analysis-cbc-hb.html
- **[S7]** Sawtooth Software, "MaxDiff calculator and design guidelines".
  https://sawtoothsoftware.com/resources/maxdiff-calculator
- **[S10]** Sawtooth Software (2020). *The MaxDiff System Technical Paper*, version 9. Sawtooth
  Software Technical Paper Series.
  https://content.sawtoothsoftware.com/assets/cb58ce5e-9d49-4d3c-b066-24bb735ad26d
- **[S11]** Chrzan, K. & Orme, B. *Becoming an Expert in Conjoint Analysis*, chapter 12, "Statistical
  Testing". Sawtooth Software. https://content.sawtoothsoftware.com/assets/b7d7e6e1-4dfe-4e89-814a-cc495bf435b1
- **[S12]** McFadden, D. (1974). Conditional logit analysis of qualitative choice behavior. In
  P. Zarembka (ed.), *Frontiers in Econometrics*, 105-142. Academic Press.
- **[S13]** Displayr, `flipMaxDiff` R package, `R/maxdiff.R` (read as a downloaded source file).
  https://github.com/Displayr/flipMaxDiff
- **[S14]** Varin, C., Reid, N. & Firth, D. (2011). An overview of composite likelihood methods.
  *Statistica Sinica* 21, 5-42. https://utstat.toronto.edu/reid/research/A09-300_edited_varin.pdf
- **[S8]** Efron, B. & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap.* Chapman & Hall.
- **[S9]** Hunter, D. R. (2004). MM algorithms for generalized Bradley-Terry models. *Annals of
  Statistics*, 32(1), 384-406. https://doi.org/10.1214/aos/1079120141 ; Ford, L. R. (1957). Solution of
  a ranking problem from binary comparisons. *American Mathematical Monthly*, 64(8), 28-33.
- Louviere, J. J., Flynn, T. N. & Marley, A. A. J. (2015). *Best-Worst Scaling: Theory, Methods and
  Applications.* Cambridge University Press. Background; not read for this skill.

## Where practitioners disagree

- **Whether to blend best and worst answers at all.** [S10] notes "debate regarding the correctness" of
  the combined model and that best and worst parameters and scale may differ, while reporting that it
  works well in practice. `--model best-only` is the check.
- **Which model for the worst answer.** Sawtooth codes the marginal form (row 6); the
  academic literature starts from the maxdiff pair model (row 5); [S3] offers all three. The script
  defaults to the sequential form because it is a proper probability model of how the answer is given.
  They give different utility scales and can order close items differently even on balanced data
  (method.md, section 2), so name the model with the ranking.
- **Counts or a model.** [S1] finds counting scores "highly correlated and nearly linear" with HB at
  the sample level in one study of 287 respondents, and recommends a model when designs are not
  balanced. Counts are the transparent check; the logit is the estimate.
- **Which share scale.** Share of preference (row 10) answers "picked best out of all items"; Sawtooth's
  probability scale (row 11) answers "picked best out of a typical set". They rank items identically
  and give different numbers.
- **Aggregate logit or hierarchical Bayes.** HB is the usual estimator for individual-level scores,
  with mixed logit and latent class (Latent Gold) as alternatives [S1]; aggregate logit is the
  "top-line diagnostic" and the option for sparse designs [S5]. Aggregate logit gives no individual
  utilities, so it cannot feed segmentation, TURF or per-respondent filters.
- **Sample size.** 200 per reported group is Sawtooth's guideline [S7], a rule of thumb rather than a
  derived threshold. Other practitioners use smaller numbers; none were found in a primary source.

## Pitfalls

- Reporting counting scores from an unbalanced design as if they were utilities (row 4).
- Comparing raw utilities between segments or studies: scale differs with consistency (row 12). Compare
  shares or ranks.
- Calling a share "probability scale" or "share of preference" without saying which formula (rows 10-11).
- Bootstrapping or computing standard errors over sets instead of respondents: sets from one person are
  not independent, so intervals come out too narrow.
- Reading the order of two items whose intervals overlap as established, or treating scores that sum
  to 100 as independent (raising one lowers the others).
- Assuming best and worst answers follow the same utilities; compare `--model best-only`.
- Reading shares as absolute appeal. Scores are relative to the items tested: the top item of a weak
  list is still weak, and a share cannot be carried over to a study with a different item list.
- Comparing segments by overlapping per-segment intervals or t-tests on shares; and forgetting that a
  noisier segment has flatter shares even with the same preferences (row 22).
- Judging fit by an RLH cut-off. Compare RLH with its chance level for the model and set size (rows
  18-19).
- Treating a position-coded export as labels, or the reverse (the script never guesses the coding).
- Silently dropping incomplete or contradictory sets. Report how many were excluded and why.
- Fitting a logit when an item is always worst or always best in a group (separation): the estimate is
  infinite and software that does not check returns a large arbitrary number.
- Presenting pooled results as if every respondent agreed. Aggregate logit hides disagreement between
  respondents; segment cuts show only the differences you thought to cut by.
