# Conjoint analysis: method sources

Every formula, threshold and convention in `SKILL.md` and `scripts/conjoint_analysis.py`, with its source.
"Not fetched" means the citation is known from indexes or citing work but the text was not read for this
skill; "convention of this skill" means no published source sets the value.

Contents: Model · Derived quantities · AMCE and marginal means · Segments · Thresholds · Worked examples · Pitfalls · Sources

## Model

- **Conditional (multinomial) logit.** P(choose j in task t) = exp(x_tj β) / Σ_k exp(x_tk β), estimated by
  maximum likelihood (McFadden 1974; Train 2009, chapter 3). Aggregate: one β for everyone.
- **Coding.** Dummy coding with the first level of each attribute as reference (the spec order, or a
  numeric-aware sort); a none alternative gets an alternative-specific constant and zeros elsewhere (Train
  2009, chapter 2). `--price-attr` / `--linear` estimate one coefficient per unit of a numeric attribute.
  Main effects only: no interactions (Brand × Price).
- **Linear attributes are centered** on the mean tested value before fitting. The likelihood is unchanged (a
  shift of x is absorbed by the none constant, and cancels within a task without one), but the none constant
  then stays near the centered none utility, so adding $1,000 to every price cannot push it past the
  separation bound, and the information matrix is not computed from large, nearly equal numbers. Standard
  reparameterization; reported utilities are already centered (below).
- **Numbers in levels.** A level's number is read with the pack-wide rule: a comma followed by exactly three
  digits is a thousands separator (`$1,299` = 1299), any other comma is a decimal comma (`4,5` = 4.5), and a
  minus sign counts only when it does not follow a letter or digit (`Plan-2` = 2). A linear level with no
  number or more than one (`100 GB ($20)`, `$40-$70`) is refused. The same parser reads `--product` prices.
  Convention of this pack.
- **Estimation.** Newton-Raphson with step halving, Cholesky solves and convergence on both the largest step
  (1e-9) and the score per task (1e-7), copied in approach from this pack's `maxdiff-analysis`. Identical tasks
  are pooled (sufficient statistics). The log-likelihood is globally concave, so the maximum is unique when it
  exists (Train 2009, section 3.7).
- **Separation.** When a level (or combination) is always or never chosen against its competitors, the
  likelihood has no finite maximum. The script stops (exit 3) when any utility difference passes 25 on the
  utility scale or the information matrix stops being positive definite after the first step, and names the
  levels never or always chosen. The bound of 25 is an implementation constant (e^25 odds).
- **Standard errors.** Model-based: square roots of the diagonal of the inverse information. Reported and
  used by default: cluster-robust sandwich H⁻¹(G/(G−1) Σ_r g_r g_rᵀ)H⁻¹ with respondents as clusters, because
  one respondent's tasks are not independent (Cameron and Miller 2015). With one respondent the model-based
  covariance is used and flagged.
- **Numerical gradients** for the delta method use a central difference with step 10⁻⁶ × max(|β|, 1/range)
  for a linear attribute (10⁻⁶ × max(|β|, 1) otherwise), so a price effect of 10⁻⁶ per dollar is not crossed by
  its own step. Implementation constant.
- **Bootstrap (`--bootstrap N`).** Respondents resampled with replacement, the logit refitted from the
  full-sample estimate, percentile intervals (Efron and Tibshirani 1993). Off by default for speed;
  intervals are withheld when more than 5% of refits fail (convention, same as `maxdiff-analysis`).

## Derived quantities

| Quantity | Formula | Source |
|---|---|---|
| Zero-centered part-worths | u_l − mean of the attribute's u (reference level u = 0); linear: β(v − mean v) at the tested values | Orme (2010) |
| None utility | β_none − Σ_q mean_q(u), so concept and none utilities share one scale | Algebra of the centering |
| Importance | range of an attribute's part-worths / sum of ranges × 100 | Orme (2010); Sawtooth "Attribute importances" (not fetched). Computed from aggregate utilities; Sawtooth's HB reports average individual importances, which are larger for weak attributes |
| WTP | −(u_level − u_reference) / β_price, in price units | Chapman and Feit (2015), ch. 13 (reproduced below); Train (2009) ch. 3 for the ratio |
| Share of preference | 100 · exp(V_i) / Σ exp(V_k), none included when estimated | Train (2009); Orme (2010) |
| Intervals on derived values | Delta method with numerical gradients on the robust covariance; percentile bootstrap when requested | Standard; Fieller intervals would be better for WTP and are not implemented |
| Fit | McFadden R² = 1 − LL/LL₀ (LL₀ = equal probabilities); RLH = exp(LL / tasks) | McFadden (1974); Sawtooth RLH definition |

WTP is withheld when the price coefficient is not negative with |β| above z·SE: a ratio with a denominator
near zero has no useful interval (convention of this skill). The decision is made before any ratio is taken;
a bootstrap resample whose price effect is at or above zero gives no WTP, and a WTP bootstrap interval is
withheld when more than 5% of refits give none. The simulator refuses linear prices outside the tested range
and products that a spec prohibition rules out. Delta-method intervals for shares and importances are cut
at 0 and 100; near a tie between levels the importance interval is too narrow (the range is not
differentiable there), so use `--bootstrap` for importances of weak attributes. RLH by chance is
exp(LL₀ / tasks), the geometric mean of 1 / alternatives per task.

## AMCE and marginal means (`--amce`)

- **AMCE.** OLS of chosen (0/1, concept rows only) on an intercept and every attribute's level dummies, with
  CR1 cluster-robust standard errors by respondent (Stata's small-sample factor G/(G−1)·(N−1)/(N−K)). Under
  independent uniform randomization this estimates the average marginal component effect (Hainmueller,
  Hopkins and Yamamoto 2014). With one attribute it equals the difference in marginal means exactly (tested).
- **Marginal means.** Share of concepts with a level that were chosen, with a cluster-robust SE of the mean.
  Use these, not AMCEs, to compare subgroups, because AMCEs depend on the reference level (Leeper, Hobolt and
  Tilley 2020). With `--segment`, marginal means are computed per segment, and each segment's difference from
  the first segment gets SE √(SE₁² + SE₂²) (segments hold different respondents, so the estimates are
  independent).
- **Assignment checks.** The AMCE assumes each profile was drawn independently (Hainmueller, Hopkins and
  Yamamoto 2014). Two checks, neither proof of randomization: (1) association between attributes within the
  shown concepts, largest Cramér's V above 0.10 (convention), which catches prohibitions and can also occur by
  chance in a small sample; (2) within-task overlap: the share of concept pairs in a task with the same level,
  against Σ_l p_l² expected from independent draws with the observed level frequencies. A balanced,
  minimal-overlap design has V near 0 but overlap far below Σ p_l²; the script warns when the observed share
  is under 80% of the expected one (convention of this skill). Ask how the design was generated.

## Segments

- Separate logits per segment and a cluster-robust Wald test of one β for all:
  W = Σ_g (β_g − β̄)ᵀ V_g⁻¹ (β_g − β̄), β̄ = (Σ V_g⁻¹)⁻¹ Σ V_g⁻¹ β_g, df = (G − 1)p, with V_g each segment's
  respondent-clustered covariance; for two segments W = (β₁ − β₂)ᵀ(V₁ + V₂)⁻¹(β₁ − β₂) (tested). A
  likelihood-ratio test would treat every task as independent and over-reject when people answer several
  tasks (Cameron and Miller 2015); the Wald form with clustered covariances does not (a person repeating the
  same task 20 times gives the same p-value, tested). Chi-square upper tail by the regularized incomplete
  gamma (Press et al. 2007, section 6.2). Not computed when a segment's clustered covariance is singular
  (fewer respondents than parameters).
- A segment difference in scale (choice consistency) also rejects the test and makes raw utilities
  incomparable (Swait and Louviere 1993). Importances and WTP are ratios of utilities, so a common scale
  factor cancels; simulated shares are not ratios and change with scale (a more consistent segment gives
  more extreme shares). Compare importances and WTP first; read share differences as preference plus
  consistency.

## Thresholds

| Value | Source |
|---|---|
| Small base: under 300 respondents overall, under 200 per segment | Sawtooth "Sample size rules of thumb" (read 2026-11-19): 300 per study, 200 per subgroup |
| Stop when more than 5% of tasks are excluded | Convention of this pack |
| None chosen in more than half the tasks: warning | Convention of this skill |
| AMCE independence warning at Cramér's V 0.10 | Convention of this skill (Cohen's "small" w) |
| AMCE overlap warning below 80% of the independent-draw overlap | Convention of this skill |
| A linear attribute whose levels are exactly 1..k or 0..k−1: "looks like level codes" note | Convention of this skill |
| Seed 20261119 | Arbitrary fixed value |

## Worked examples reproduced

1. **SAS "Choice of Chocolate Candies"** (Kuhfeld 2010, "Discrete Choice" chapter; data in SAS sample
   "Discrete Choice 1", support.sas.com, read 2026-11-19: ten subjects choose one of the eight candies of the
   2³ factorial, chosen profiles 5 6 7 5 2 6 2 6 6 6). Published estimates Dark 1.38629, Soft −2.19722,
   Nuts 0.84730 with SEs 0.79057, 1.05409, 0.69007. The estimates in the report were not re-read; they equal
   ln 4, ln(1/9) and ln(7/3), which follow in closed form from the choices, and the SEs equal
   1/√(n p (1 − p)). Reproduced to five decimals in `tests/` (`fixtures/candy_stacked.csv`).
2. **Chapman and Feit (2015), chapter 13, minivan CBC** (simulated data, 200 respondents × 15 tasks × 3
   concepts; chapter page read 2026-11-19). `mlogit(choice ~ 0 + seat + cargo + eng + price)`: seat7
   −0.535280 (SE 0.062360), seat8 −0.305840 (0.061129), cargo3ft 0.477449 (0.050888), enghyb −0.811282
   (0.060130), engelec −1.530762 (0.067456), price35 −0.913656 (0.060601), price40 −1.725851 (0.069631),
   log-likelihood −2581.6. With numeric price: price −0.1733053 (0.0069398), log-likelihood −2582.1, WTP for
   cargo3ft 2750.601 dollars (prices in thousands). This script reproduces every printed digit, including
   the model-based SEs and WTP 2.750601. The dataset is not shipped (its licence is not stated), so this
   check is not in `tests/`; the command is in `fixtures/README.md`.
3. **Independent checks in `tests/`.** The Newton maximum is confirmed by a derivative-free coordinate
   golden-section search; known simulated utilities are recovered within 3 SE; AMCE = difference in marginal
   means for one randomized attribute; shares and importances recomputed by hand.

## Pitfalls

- **IIA.** Logit shares split share proportionally, so a near-copy of a product takes share from everyone
  rather than mostly from the product it copies (Train 2009, section 3.3.1). Aggregate simulators overstate
  shares for differentiated niche products; HB or latent-class models do better and are not implemented.
- **Aggregate versus individual.** One β averages over people with opposite preferences; an attribute can
  look unimportant because half love and half hate a level. Check segments or counts.
- **WTP from conjoint** depends on the price range and levels tested and tends to be higher than market WTP
  (Orme 2010; Chapman and Feit 2015 caution the same). Report it as a relative measure.
- **Importance depends on the levels chosen**: widen a range and the attribute becomes more important.
- **Shares are not market shares** without calibration for awareness, distribution and the none option.

## Sources

1. McFadden, D. (1974). Conditional logit analysis of qualitative choice behavior. In P. Zarembka (ed.),
   *Frontiers in Econometrics*, 105-142. Academic Press.
2. Train, K. E. (2009). *Discrete Choice Methods with Simulation*, 2nd ed. Cambridge University Press.
   https://eml.berkeley.edu/books/choice2.html
3. Hainmueller, J., Hopkins, D. J. and Yamamoto, T. (2014). Causal inference in conjoint analysis.
   *Political Analysis* 22(1):1-30.
4. Leeper, T. J., Hobolt, S. B. and Tilley, J. (2020). Measuring subgroup preferences in conjoint experiments.
   *Political Analysis* 28(2):207-221.
5. Orme, B. K. (2010; 4th ed. 2020). *Getting Started with Conjoint Analysis*. Research Publishers. Edition
   not confirmed; not fetched.
6. Chapman, C. and Feit, E. M. (2015). *R for Marketing Research and Analytics*, chapter 13. Springer.
   Chapter page: https://r-marketing.r-forge.r-project.org/Instructor/Chapter13/Chapter13-ChapmanFeit.html
   (read 2026-11-19); data: http://r-marketing.r-forge.r-project.org/data/rintro-chapter13conjoint.csv
7. Kuhfeld, W. F. (2010). *Marketing Research Methods in SAS* (MR-2010), "Discrete Choice". SAS Institute.
   Sample code: https://support.sas.com/documentation/onlinedoc/stat/ex_code/121/mlogit01.html (read
   2026-11-19).
8. Swait, J. and Louviere, J. (1993). The role of the scale parameter in the estimation and comparison of
   multinomial logit models. *Journal of Marketing Research* 30(3):305-314. Not fetched.
9. Cameron, A. C. and Miller, D. L. (2015). A practitioner's guide to cluster-robust inference. *Journal of
   Human Resources* 50(2):317-372.
10. Efron, B. and Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman and Hall.
11. Press, W. H., Teukolsky, S. A., Vetterling, W. T. and Flannery, B. P. (2007). *Numerical Recipes*, 3rd ed.,
    section 6.2. Cambridge University Press.
12. Sawtooth Software (2020). Sample size rules of thumb for choice-based conjoint (CBC).
    https://www.sawtoothsoftware.com/resources/blog/posts/sample-size-rules-of-thumb (read 2026-11-19).
13. Export layouts for Sawtooth, Qualtrics and Conjointly in `input-formats.md` are general descriptions,
    **not checked** against the tools' current exports. Sawtooth's none concept written with 0 in every
    attribute is from review reports, not a read export. Qualtrics documents a raw conjoint data export and
    a separate individual-utilities export (support page "Exporting Raw Conjoint Data", not fetched for this
    skill); only raw choices can be analyzed here. The QuestionPunk answer layout was read from the
    app's source (`conjointScoring.ts`, `decodeConjointAnswer`) in the QuestionPunk monorepo, not from a live
    export.
