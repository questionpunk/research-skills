# Gabor-Granger analysis: method sources

Every formula, threshold and convention in `SKILL.md` and `scripts/gabor_granger_analysis.py`, with where it
comes from. "Not fetched" means the citation was confirmed from an index or a citing paper but the text itself
was not read; "convention of this skill" means no published source sets the value.

Contents: Method · Formulas · Thresholds and defaults · Answer coding · Pitfalls · Sources

## Method

- **Gabor-Granger (buy-response) method.** Respondents say whether they would buy a described product at a
  series of prices; the share who would buy at each price is the buy-response (demand) curve, and price x
  share is a revenue index. Attributed to André Gabor and Clive Granger's Nottingham price enquiries
  (Gabor and Granger 1961, 1964, 1966). The 1961 paper is their price-consciousness enquiry; the buy-response
  curve is usually cited to their 1964 and 1966 papers (bibliographic records confirmed; texts not read).
- **Ladder versions.** Every respondent answers every price (full ladder); an adaptive ladder starts at a
  random price and moves up after "would buy" and down after "would not", stopping at the highest price the
  respondent accepts (Wikipedia "Gabor-Granger method", citing SurveyKing; secondary, read 2026-11-19); or a
  monadic test where each respondent sees one price. The script reads all three.
- **Top-2 box as "would buy".** On a 5-point purchase-intent scale, "definitely" or "probably would buy"
  counts as buying in the adaptive procedure described above (same secondary source). Convention, not a
  rule from the original papers; `--buy-box 1` is the stricter top box.

## Formulas

| Quantity | Formula | Source |
|---|---|---|
| Take rate at price p | buyers at p / respondents answering at p (or the mean of calibrated values) | Definition of the buy-response curve |
| Wilson interval | (p̂ + z²/2n ± z·√(p̂(1−p̂)/n + z²/4n²)) / (1 + z²/n); limits set to 0 when x = 0 and 1 when x = n | Wilson (1927); evaluated as method 3 in Newcombe (1998) |
| Monotone demand curve | Weighted least-squares fit under "never rises with price", weights = respondents at each price, by pool-adjacent-violators | Ayer et al. (1955); Barlow et al. (1972) |
| Revenue index | price x monotone take rate | SurveyMonkey worked example (price x cumulative %) |
| Profit index | (price − unit cost) x monotone take rate | Contribution margin x volume; the unit cost is the user's |
| Arc elasticity | [(q₂ − q₁) / ((q₁ + q₂)/2)] / [(p₂ − p₁) / ((p₁ + p₂)/2)] | Allen (1934), the midpoint formula (not fetched) |
| Optimum | The tested price with the highest index; ties reported, lowest shown | Convention of this skill: no interpolation between tested prices, because the curve between them is not observed |
| Raw-curve optimum | When pooling moves the optimum, the price that maximizes price x raw take rate is named too | Convention of this skill, for the price-as-quality case (Gabor and Granger 1966) |
| Bootstrap | Monadic test: respondents resampled with replacement within each price cell (cell sizes are fixed by design). Ladder: respondents resampled as a whole, because the prices a respondent is asked depend on their answers. Percentile intervals for the raw and the monotone take rate; share of samples in which each price is the optimum, a tie splitting that sample's vote equally | Efron and Tibshirani (1993), percentile method; stratified resampling for fixed cell sizes (Davison and Hinkley 1997, section 3.2). The tie split is a convention of this skill |
| Percentile | Take-rate intervals: linear interpolation between order statistics (Hyndman-Fan type 7, R's default). Optimum interval: inverse empirical distribution (type 1), so its ends are tested prices | Hyndman and Fan (1996) |
| Counts from one group (`--counts-sample same`) | With one base N and buyers b₁ ≥ b₂ ≥ … ≥ bₖ at ascending prices, bₖ − bₖ₊₁ people accept up to price k (bₖ₊₁ = 0) and N − b₁ accept none; the group is rebuilt from these drops | Arithmetic of cumulative buy-response counts (the SurveyMonkey example is one group of 200) |

Imputation on an adaptive ladder: a respondent who would buy at p is taken to buy at every lower price, and
one who would not buy at p is taken not to buy at any higher price. This is the monotonicity the adaptive
procedure itself assumes when it stops asking. A filled cell takes the answer value of the nearest asked price
that implies it, and counts in n and in the Wilson interval as if asked (`n_observed` gives the answers
given). Nothing is filled for monadic data, under `--design full`, or with `--intent-weights` (a calibrated
value at one price only bounds the value at another). The design is never inferred from a few blanks: when
most respondents answered one price and some answered several, the script stops and asks (`--design`).
Convention of this skill.

Inconsistent respondent: the answer at a higher price is more positive than at a lower one: "would buy" at
the higher and not at the lower price, or with `--intent-weights` a higher calibrated value.

## Thresholds and defaults

| Value | Where | Source |
|---|---|---|
| Small base: under 100 answers given at a price (filled cells not counted) | `--min-base 100` | Review heuristic adapted from Pew Research Center (2022), which does not report groups under about 100 effective interviews because the margin of error passes 10 points (page read for the sibling `nps-analysis`). Raw answers are not effective interviews; the flag is a prompt to read the curve as directional |
| No optimum named under 10 answers at any price | `MIN_N_FOR_OPTIMUM` | Convention of this skill |
| Unstable optimum: the named price wins in under 50% of bootstrap samples | warning | Convention of this skill (a majority rule) |
| Stop when more than 5% of non-blank answers cannot be read | `UNREADABLE_STOP_SHARE` | Convention of this pack (same rule as `nps-analysis`) |
| Inconsistent respondents excluded by default; warning above 10% | `--inconsistent` | Convention of this skill (a review heuristic, not a published rule), matching the exclusion default of `van-westendorp-analysis`; the warning asks for a rerun with `--inconsistent keep` because price read as quality is a real cause |
| 1,000 bootstrap replicates, 95% | `--bootstrap`, `--confidence` | Efron and Tibshirani (1993) suggest at least about 1,000 for percentile intervals |
| Seed 20261119 | `--seed` | Arbitrary fixed value so runs repeat |

## Answer coding

- Yes/no answers: `yes, y, true, 1, buy` and `no, n, false, 0`.
- Intent labels are read by their words: "definitely would buy" (5), "probably would buy" (4), "might or might
  not" (3), "probably would not" (2), "definitely would not" (1); "very likely" ... "very unlikely" map the
  same way, and "neither likely nor unlikely" is the midpoint. Negatives are read in every spelling ("will
  not", "wouldn't", "won't", curly apostrophes). A label that reads as positive but contains a negation is
  not guessed: it is unreadable. A numeric prefix such as `5 - Definitely would buy` is ignored in favour of
  the words.
- Seven-point and unipolar likelihood scales ("extremely / very / somewhat likely ...", "moderately",
  "slightly") have more points than the 5-point reading; the script stops and asks for the labels in order
  (`--intent-scale 'A|B|...'`). Convention of this skill, so no two scale points are merged silently.
- Bare numeric codes are never assumed: `--intent-scale` lists them from "definitely would buy" down
  (most tools: `5,4,3,2,1`). Two codes (yes/no stored as 1/2) take `--intent-scale YES,NO`.
- Calibration (`--intent-weights`): the purchase probability per scale point, supplied by the user. The
  script ships no default weights, because published calibrations vary by category and study (Jamieson and
  Bass 1989; Morwitz, Steckel and Gupta 2007). Without weights the output says "stated intent, not
  calibrated".

## Pitfalls

- **Stated intent overstates purchase.** Purchase-intention answers predict sales imperfectly and usually
  overstate them (Jamieson and Bass 1989; Morwitz, Steckel and Gupta 2007). The revenue index ranks prices;
  it is not a sales forecast.
- **The optimum can only be a tested price.** If it is the highest or lowest price, the ladder probably did
  not reach the real optimum.
- **Ladder order effects.** Asking every respondent every price in ascending order invites anchoring;
  randomized start prices (adaptive) or monadic cells reduce it. The script cannot detect it.
- **Price as a quality signal.** A respondent who buys at a higher price but not a lower one may be reading
  price as quality (Gabor and Granger 1966), not answering carelessly. Report the count; do not drop them
  silently.
- **Gabor-Granger ignores competitors.** Each price is judged alone; for trade-offs against features or
  competitors use conjoint (`conjoint-design`, `conjoint-analysis`).

## Worked examples reproduced

- SurveyMonkey, "The Gabor-Granger method: how to build the survey and calculate the demand curve"
  (surveymonkey.com/learn/product-development/gabor-granger/, read 2026-11-19): 200 respondents; would buy at
  $10, $15, $20, $25, $30 = 190, 164, 118, 74, 36; revenue index 9.5, 12.3, 11.8, 9.25, 5.4; peak at $15.
  Reproduced exactly in `tests/` (`fixtures/surveymonkey_published.expected.json`).
- Newcombe (1998) Table I, Wilson method without continuity correction: 81/263 → 0.2553 to 0.3662;
  15/148 → 0.0624 to 0.1605; 0/20 → 0 to 0.1611; 1/29 → 0.0061 to 0.1718 (values as printed in the DescTools
  `BinomCI` documentation and re-derived by bisection in the tests).
- Arc elasticity: price rising from 4 to 6 while quantity falls from 120 to 80 gives elasticity −1.0 by the
  midpoint method. This is the textbook example in Mankiw, *Principles of Economics*, chapter 5 (from memory;
  edition and page not re-checked), and is re-derived by hand in the tests.

## Sources

1. Gabor, A. and Granger, C. W. J. (1961). On the price consciousness of consumers. *Journal of the Royal
   Statistical Society Series C (Applied Statistics)* 10(3):170-188. doi:10.2307/2985208. Confirmed via RePEc
   (econpapers.repec.org, RePEc:bla:jorssc:v:10:y:1961:i:3:p:170-188); not fetched.
2. Gabor, A. and Granger, C. W. J. (1966). Price as an indicator of quality: report on an enquiry.
   *Economica* 33(129):43-70. doi:10.2307/2552272. Volume, issue and first page confirmed via Crossref; last
   page from citing reference lists; not fetched.
3. Gabor, A. and Granger, C. W. J. (1964). Price sensitivity of the consumer. *Journal of Advertising
   Research* 4(4):40-44. doi:10.1080/00218499.1964.12519754. Confirmed via Crossref; not fetched.
4. Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of
   the American Statistical Association* 22(158):209-212.
5. Newcombe, R. G. (1998). Two-sided confidence intervals for the single proportion: comparison of seven
   methods. *Statistics in Medicine* 17:857-872.
6. Ayer, M., Brunk, H. D., Ewing, G. M., Reid, W. T. and Silverman, E. (1955). An empirical distribution
   function for sampling with incomplete information. *Annals of Mathematical Statistics* 26(4):641-647.
   Not fetched.
7. Barlow, R. E., Bartholomew, D. J., Bremner, J. M. and Brunk, H. D. (1972). *Statistical Inference under
   Order Restrictions*. Wiley. The max-min formula used as the independent check in the tests is the
   standard closed form of isotonic regression given there (chapter 1; page not re-checked).
8. Allen, R. G. D. (1934). The concept of arc elasticity of demand. *Review of Economic Studies*
   1(3):226-229. Not fetched.
9. Efron, B. and Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman and Hall.
   Davison, A. C. and Hinkley, D. V. (1997). *Bootstrap Methods and their Application*. Cambridge University
   Press (stratified resampling, section 3.2; section number from memory, not re-checked).
10. Hyndman, R. J. and Fan, Y. (1996). Sample quantiles in statistical packages. *The American Statistician*
    50(4):361-365.
11. Jamieson, L. F. and Bass, F. M. (1989). Adjusting stated intention measures to predict trial purchase of
    new products: a comparison of models and methods. *Journal of Marketing Research* 26(3):336-345. Volume,
    issue and first page confirmed via Scilit; last page and findings not read.
12. Morwitz, V. G., Steckel, J. H. and Gupta, A. (2007). When do purchase intentions predict sales?
    *International Journal of Forecasting* 23(3):347-364. Not fetched.
13. Pew Research Center (2022). Why Pew Research Center typically can't report the views of smaller U.S.
    religious groups. https://www.pewresearch.org/short-reads/2022/08/08/why-pew-research-center-typically-cant-report-the-views-of-smaller-u-s-religious-groups/
14. SurveyMonkey. The Gabor-Granger method: how to build the survey and calculate the demand curve.
    https://www.surveymonkey.com/learn/product-development/gabor-granger/ (read 2026-11-19; illustrative data).
15. Wikipedia. Gabor-Granger method. https://en.wikipedia.org/wiki/Gabor%E2%80%93Granger_method (read
    2026-11-19; secondary, cites SurveyKing).
