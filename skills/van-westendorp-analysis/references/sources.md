# Van Westendorp analysis: method sources

Checked against the sources below on 2026-11-12. Every formula, threshold and default in `SKILL.md` and in
`scripts/van_westendorp_analysis.py` is listed here with where it comes from. Choices that are ours, not a source's, are marked
**our convention**.

## The four questions

Wording and order vary between sources. Orme (Sawtooth Software) gives:

- Too cheap: "At what price would Item X be so inexpensive that you would doubt its quality?"
- Cheap (acceptably cheap, bargain): "At what price would you consider Item X a good value?"
- Expensive (acceptably expensive): "At what price is Item X beginning to get expensive, but you would still
  consider buying it?"
- Too expensive: "At what price would Item X be so expensive you would never consider it?"

Answers are open numeric prices in one currency for one clearly described product (and one billing period).
Orme: "If you can, show respondents competitive products and pricing so they can establish better market
context."

## Cumulative curves

On a grid of prices p:

| Curve | Value at p | Direction |
|---|---|---|
| Too cheap | share of respondents whose too-cheap price is ≥ p | falls |
| Cheap | share whose cheap price is ≥ p | falls |
| Expensive | share whose expensive price is ≤ p | rises |
| Too expensive | share whose too-expensive price is ≤ p | rises |
| Not cheap | 1 − cheap | rises |
| Not expensive | 1 − expensive | falls |

- The ≥ / ≤ boundary is the one in Conjointly's manual-calculation guide: for too cheap and cheap, "adding all
  the frequencies greater than or equal to the respective price level"; for expensive and too expensive, "less
  than or equal to". It reads naturally: a respondent who said "too cheap at 5" finds 5 too cheap.
- **Disagreement.** The R package `pricesensitivitymeter` builds the falling curves as 1 − ECDF, the share
  **strictly above** p; from version 1.3.1 it also pins every curve at its lowest answer. The conventions
  differ only at prices respondents actually named, and the difference shrinks as the sample grows, but on a
  small sample the intersections can move by a grid step. `--boundary exclusive` and
  `--boundary exclusive-forced-ends` reproduce the two R behaviours; the per-tool table is in
  [tool-conventions.md](tool-conventions.md).
- Grid: every distinct price given by an analysed respondent (Conjointly guide, step 1; the R package's
  default, `interpolate = FALSE`).

## The four intersections

| Point | Curves | Source |
|---|---|---|
| OPP, optimal price point | too cheap × too expensive | All sources agree |
| IPP, indifference price point (also IDP, "normal price") | cheap × expensive | All sources agree |
| PMC, point of marginal cheapness, **original** | too cheap × not cheap | Van Westendorp 1976, as reported by the R package and Conjointly |
| PME, point of marginal expensiveness, **original** | too expensive × not expensive | Same |
| PMC, **narrower** | too cheap × expensive | Conjointly, Wikipedia, Sawtooth's four-line chart |
| PME, **narrower** | too expensive × cheap | Same |

Acceptable price range = PMC to PME.

**Which definition is Van Westendorp's.** The R package documentation says of its default
`acceptable_range = "original"`: it "uses the definition provided in van Westendorp's paper: The lower end of
the price range (point of marginal cheapness) is defined as the intersection of 'too cheap' and the inverse
of the 'cheap' curve. The upper end of the price range (point of marginal expensiveness) is defined as the
intersection of 'too expensive' and the inverse of the 'expensive' curve." It describes "narrower" as a
definition "applied by some market research companies". Conjointly confirms the same reading from the other
side: it says the original paper proposed using the inverse of "cheap" ("not cheap") in place of the
"expensive" curve, and that Conjointly instead "follows the more commonly accepted approach in the market
research industry". Two independent secondary sources agree, so the script's default is `original`, and
`--range-definition narrower` gives the other. The output always names the curve pairs used and prints the
range under the other definition next to it.

Properties worth knowing:

- The narrower range lies inside the original range whenever every respondent's cheap price is below their
  expensive price: then expensive(p) ≤ not cheap(p) and cheap(p) ≤ not expensive(p) at every p, so too cheap
  meets not cheap before it meets expensive, and too expensive meets cheap before it meets not expensive.
- IPP is the same under both: cheap = expensive exactly where not cheap = not expensive.
- The names promise more than the method delivers. Sawtooth: "there isn't strong reasoning behind these
  names". OPP is where the too-cheap and too-expensive shares are equal. That is not the price fewest
  respondents reject: with one group answering 1, 2, 3, 4 and another 10, 11, 12, 13, OPP is 7, where 0% find
  the price acceptable on both counts, against 50% at 2. Nor is it a profit- or revenue-maximizing price.
  The share rejecting a candidate price on either ground is counted respondent by respondent with `--at`.

## Finding a crossing

For two curves f and g, take d(p) = f(p) − g(p) on the grid. With the curve definitions above, d for each of
the six pairs is monotone (one curve of the pair never rises and the other never falls), so there is at most
one crossing.

- **Sign change between neighbouring grid prices p1 and p2**: linear interpolation,
  p* = p1 + (p2 − p1) × d1 / (d1 − d2). The same formula is in the R package's newer intersection routine
  (`R/psm_utils.R`).
- **d = 0 at exactly one grid price**: that price is the crossing. (Follows from the formula.)
- **d = 0 at several neighbouring grid prices** (the curves coincide, typically where both are 0% because no
  one's too-cheap price reaches as high as anyone's too-expensive price): the script reports the midpoint of
  the interval, the interval itself, and a warning. **Our convention**; no source prescribes one. `--tie`
  offers `min` (lower end, the R package's default `intersection_method`), `max` (upper end), `mean` (mean
  of the observed prices in the run, as in R's older routine) and `midpoint` (default).
- **`--no-interpolate`**: the crossing is the first grid price at which the rising curve is at or above the
  falling one; `--tie` then applies to the run of neighbouring grid prices at which both curves keep those
  values. This is the R package's older routine (`R/psm-utils.R`, the only one up to version 1.3.0).
- **No crossing on the grid**: no value is reported and the script warns. It can happen when inconsistent
  respondents are kept, and also with consistent ones when the curves only touch: if every respondent gives
  the same price to all four questions, under `--boundary exclusive` no curve pair crosses, and under
  `inclusive` PMC and PME do not.

The script works with exact counts (integers, or fractions when respondents are weighted), so "d = 0" is
exact, not a floating-point comparison.

## Consistency of a respondent

- A respondent's four prices should be ordered too cheap, cheap, expensive, too expensive.
- **Strict or not: sources disagree.** The R package requires strict order (`validate = TRUE`: "too cheap <
  cheap < expensive < too expensive"), and removes violators by default. Conjointly's published worked example
  keeps a respondent whose cheap and expensive prices are equal ($8.00 and $8.00), and reproducing its
  published result requires keeping that respondent. Neither cites Van Westendorp for the rule.
- Script default: non-strict (≤), because an equal answer is not a contradiction and the published example
  keeps it; the number of analysed respondents with a tie is reported, and `--strict` applies the R rule.
  **Our choice between two sourced options.**
- Inconsistent respondents are excluded by default (R package default) and always counted, with their ids;
  `--keep-inconsistent` keeps them and says so; they still stay out of the Newton-Miller-Smith curves (**our
  convention**: with prices out of order a respondent's purchase-probability line is not defined), with a
  warning. No source gives a threshold for "too many" exclusions, so the script reports the share and sets
  none.
- Respondents with a missing price are left out and counted separately.

## Three-question variant, weights, segments, price limits

- **No too-cheap question.** Orme: "the 'Too Cheap' and 'Too Expensive' price points are optional". The R
  package accepts an empty too-cheap variable and then returns only the indifference price and the upper
  bound. The script does the same: IPP and PME are reported; OPP and PMC need the too-cheap curve under both
  range definitions and are marked unavailable with a warning. The consistency rule becomes cheap ≤ expensive
  ≤ too expensive. In the Newton-Miller-Smith extension the cheap-price probability is then held for lower
  prices, because there is no too-cheap price to interpolate to (**our convention**).
- **Weights** (`--weight`): every curve value is the sum of the weights of the respondents it counts,
  divided by the total weight; the Newton-Miller-Smith trial is the weighted mean probability. This is the
  ordinary weighted share; the R package offers the same through a survey-design object
  (`psm_analysis_weighted`). The small-sample warning uses the unweighted number of respondents with a
  positive weight. **Our convention:** a respondent with weight 0 is counted in the respondent block and left
  out of everything else (curves, grid, price points, bootstrap, base). Otherwise their prices would add
  grid points and move interpolated crossings although they carry no weight.
- **Segments** (`--segment`): the same analysis on each value of a column, each with its own counts and
  warnings. Nothing is pooled or borrowed between segments.
- **Price limits** (`--min-price`, `--max-price`): respondents with any price outside the limits are
  excluded and counted. The script never trims or caps answers on its own. Respondents with a price of zero
  or less are kept and counted in a warning. **No sourced rule for outliers was found** (competing tools'
  "more than 3× the median" and percentile cut-offs are uncited), so the script prints the minimum, median
  and maximum of each question and leaves the limit to the analyst.
- **Share at a candidate price** (`--at`): the four curve values at that price from the same curve evaluator
  as the grid (so `--compat r`'s pinned ends apply and the two never disagree at a grid price; it also works
  between grid prices), plus the share of respondents who reject the price on neither question. That share
  equals 1 − too cheap(p) − too expensive(p) only when no respondent counts on both curves at p (a respondent
  whose too-cheap and too-expensive prices both equal p counts on both under `inclusive`). Under `--compat r`
  the pinned ends apply to it as well: at or below the lowest too-cheap price nobody is in it, and at or
  below the lowest too-expensive price nobody rejects the price as too expensive.

## Reading the file (our conventions)

- Delimiter: comma, semicolon or tab, whichever splits the header into the most fields (counted by the CSV
  reader, so separators inside quoted names do not count).
- A row with more fields than the header stops the run, unless the extra fields are empty. A thousands
  separator equal to the delimiter (`1,000` in a comma file) would otherwise silently drop a price.
- Qualtrics exports put two rows under the header (question text, `{"ImportId": ...}`); when one of the first
  two rows contains `ImportId` they are skipped with a warning. `--skip-rows` sets the count by hand.
- Next to a price the script accepts a currency symbol, an ISO 4217 code or a few short abbreviations (Rs,
  kr, Fr, TL, NT, RMB). Anything else, such as `k`, `m` or `mo`, is a multiplier or a unit and stops the run.
- The file is read as CSV records, so a quoted cell may hold a line break (Qualtrics question text) and the
  Qualtrics rows are recognised by record, not by physical line.
- Column names: camelCase is split (`piCheap` reads as `pi cheap`). Too cheap: "too cheap", "too
  inexpensive", "so inexpensive", "so cheap", "doubt" (the Orme wording "...that you would doubt its
  quality") or "too low". Too expensive: "too expensive", "so expensive", "never consider" or "too high".
  Then cheap ("cheap", "bargain", "good value", "inexpensive") and expensive. One column cannot fill two
  roles. With no too-cheap column the three-question variant runs, and its warning names the columns not
  used, in case one of them is the too-cheap question under another name.
- The purchase-intent scale direction is never assumed: when the extension runs, `--intent-scale` must be
  given. A reversed 1 to 5 scale would otherwise turn the trial curve upside down without any error.

## QuestionPunk answers

A QuestionPunk `van_westendorp` question stores one JSON object per respondent, which `response_get_details`
returns as `rawAnswer`: `{"too_cheap": "5", "cheap": "10", "expensive": "20", "too_expensive": "30",
"pi_cheap": "4", "pi_expensive": "2"}` (the two `pi_` keys only when purchase intent was asked; prices
without the currency, which is in `answerDetails`). The intent codes run 1 to 5 with 5 = "Definitely would
buy", so pass `--intent-scale 5,4,3,2,1`. Write one CSV row per response with these six keys as the header.
The `responses_read` cell renders the same answer as labelled lines ("Too cheap: 5", ...).

## Bootstrap intervals

- `--bootstrap N --seed S` resamples respondents with replacement N times, recomputes the four points with
  the same conventions, and reports the 2.5th and 97.5th percentiles of each (a 95% percentile interval;
  Efron and Tibshirani 1993, chapter 13). Percentiles use linear interpolation between order statistics
  (position (m − 1) × q among m sorted values; Hyndman and Fan 1996, definition 7).
- The script sets no default N; the examples use 1,000, a common choice for percentile intervals. Fewer
  resamples give rougher interval ends.
- **Range width** (**our convention**): the script also forms PME − PMC within each resample and reports
  the percentile interval of that width with the number of resamples that had both ends. It warns only when
  the width interval reaches zero or below. Comparing the two separate intervals would be wrong: the ends
  move together across resamples, so their intervals can overlap while every resample has a positive width.
- With `--weight`, each resample draws respondents with equal probability and keeps their weights. This is
  not a design-based (replicate-weight) bootstrap; for a weighted sample read the intervals as approximate.
- The intervals describe sampling variation only. They do not cover question wording, sample bias or the
  choice of conventions.

## Newton-Miller-Smith extension

Newton, Miller and Smith (1993) add two purchase-intent questions on a 5-point scale (definitely would buy
... definitely would not buy), asked at the respondent's own cheap and expensive prices (Orme; R package;
Wikipedia). They are not asked at OPP or IPP.

**Purchase-probability weights** (highest intent first):

| Weights | Source | In the script |
|---|---|---|
| 70%, 50%, 30%, 10%, 0% | R package default `pi_calibrated`, which its documentation says is "taken from the Sawtooth Software PSM implementation in Excel" | Default; `--nms-preset sawtooth-excel` |
| 75%, 25%, 10%, 0%, 0% | Orme: "in consumer packaged goods we might use 75%, 25%, 10%, 0%, 0%" | `--nms-preset orme-cpg` |
| 80%, 60%, 40%, 20%, 0% | Conjointly: rating 0 to 4 divided by 5 | `--nms-preset fifths` |

`--nms-weights` takes any other set. There is no single agreed calibration; the weights are an assumption
and the output prints them. The two Sawtooth-related sets differ because they answer different questions:
the first is the default of Sawtooth's template as reported by the R package, the second is Orme's example
of a stronger deflation for packaged goods.

**End probabilities.** Orme's example puts the probability at 0% at the too-cheap and too-expensive prices.
The R package makes both settable (`pi_calibrated_toocheap`, `pi_calibrated_tooexpensive`, default 0);
the script's `--nms-too-cheap-prob` and `--nms-too-expensive-prob` do the same and apply at and beyond
those prices.

**Each respondent's probability by price** (Orme's "Smith" example; R package):

- 0 at the too-cheap price and below, and at the too-expensive price and above;
- the stated (weighted) probability at the cheap price and at the expensive price;
- linear interpolation between those four points.
- **Modified variant** (Orme): "assume purchase intent stays the same at the Acceptably Cheap price and left
  of that price", because zero demand at low prices "seems to violate standard economic principles"; it
  "leads to slightly lower recommended 'optimal price'". Script: `--nms-variant modified`.
- Ties, **our convention**: a stated answer wins over an assumed zero at the same price (for example cheap =
  too cheap), and when cheap = expensive the probability at that price is the mean of the two answers.
  Such a tie makes the respondent's probability jump at that price: the value there differs from the limit
  just below or just above it. The script computes both one-sided limits at every grid price (`trial_just_below`,
  `trial_just_above` in the curve when they differ from the value).

**Curves and maxima** (Orme; R package):

- Trial (the R package calls it reach) at price p = mean probability across respondents.
- Revenue index at p = p × trial (per respondent; multiply by a market size for money).
- Price with the highest trial: the grid price with the highest trial; the lowest such price on a tie (R's
  `which.max` does the same).
- Price with the highest revenue: the trial curve is linear between grid prices (from the limit just above
  the left price to the limit just below the right one, not between the two grid values, which a jump would
  distort), so revenue is a quadratic on each segment and can peak inside it. For a segment with
  trial = a + b·p and b < 0 the peak is at p = −a / (2b) when that lies inside the segment. If a one-sided
  limit next to a tied price beats every value actually reached, the script reports it separately
  (`revenue_max_approached`, `trial_max_approached`, with the side) and warns: the peak is approached just
  below or above that price, not reached at it. The limit from below at the lowest grid price counts too: in
  the modified variant (and without a too-cheap question) a price under every respondent's cheap price keeps
  the cheap-price probability. The limit from above at the highest grid price does not: above it the curve is
  flat at the too-expensive probability. The chart draws the same curve, jumps included. The script reports this exact maximum and, when it is not
  an observed price, also the highest among observed prices, which is what the R package reports
  (`which.max` on the grid). **The exact-segment step is our addition**; it follows from the linear
  interpolation and needs no extra assumption.
- **Disagreement.** Conjointly computes its demand curve differently (a cumulative "at or above" sum of
  likelihoods, with the intent at the expensive price capped at the intent at the cheap price, and a
  proprietary adjustment for very high prices). The script does not reproduce it; it reports how many
  respondents state a higher intent at the expensive price than at the cheap price.

## Sample size

- There is no authoritative minimum. Orme: "Sample size requirements not as large as the other methods; no
  need to get a lot of precision on this exploratory method anyway (use it to establish a price range to test
  later with stronger methods)"; for comparison he gives n = 300 to 500 per cell for a monadic price test.
- Vendor floor used for the warning: SightX, "we recommend a minimum base size of 100. Results with fewer
  than 100 completes are directional." Script default `--min-n 100`, applied to analysed respondents; apply it
  per segment when segments are analysed separately.

## What the method does not tell you (Orme; Sawtooth)

- "PSM lacks empirical support – it's not been rigorously tested against other forms of pricing research."
- The "too cheap" question conflicts with economic theory; the method is "a better measurement of price
  expectations than it is a measure of price sensitivity".
- No competitive context, one product concept at a time, and no account of cost or margin.
- The four curves are not demand curves. Only the Newton-Miller-Smith extension gives a (stated-intent) read
  on demand, and it rests on the assumed weights.
- Orme's recommendation: use it "to establish a price range to test later with stronger methods" (monadic
  tests, Gabor-Granger, conjoint).

## Sources

1. Van Westendorp, P. H. (1976). "NSS-Price Sensitivity Meter (PSM): A new approach to study consumer
   perception of price." Proceedings of the 29th ESOMAR Congress, 139–167. (Not available online; not read
   for this skill: its definitions are taken as the R package documentation and Conjointly report them.)
2. Newton, D., Miller, J., and Smith, P. (1993). "A market acceptance extension to traditional price
   sensitivity measurement." Proceedings of the American Marketing Association Advanced Research Techniques
   Forum. (Not available online.)
3. Alletsee, M. R package `pricesensitivitymeter`: documentation
   <https://rdrr.io/cran/pricesensitivitymeter/man/psm_analysis.html> and source
   <https://github.com/max-alletsee/pricesensitivitymeter>; CRAN sources of version 1.3.3
   (<https://cran.r-project.org/package=pricesensitivitymeter>, published 2025-08-30) and 1.3.0 (CRAN
   archive), read 2026-11-12: `R/psm_data_processing.R`, `R/psm_utils.R`, `R/psm-utils.R`,
   `R/psm_constants.R`, `R/psm_functions.R`, `NEWS.md`.
4. Orme, B. "Pricing Research Tools You Must Know." Sawtooth Software.
   <https://content.sawtoothsoftware.com/assets/edbf9432-d508-4d30-a0b6-58ccc77d4bd1>
5. Sawtooth Software. "Van Westendorp Pricing Model: Definition, How It Works, Examples, and More."
   <https://sawtoothsoftware.com/resources/blog/posts/van-westendorp-pricing-sensitivity-meter>
6. Conjointly. "Van Westendorp Price Sensitivity Meter" <https://conjointly.com/products/van-westendorp/> and
   "How to manually calculate Van Westendorp PSM's results"
   <https://conjointly.com/guides/manual-calculation-of-van-westendorp/>
7. SightX. "Van Westendorp." <https://support.sightx.io/knowledge/van-westendorp> (sample-size floor only.)
8. Wikipedia. "Van Westendorp's Price Sensitivity Meter."
   <https://en.wikipedia.org/wiki/Van_Westendorp%27s_Price_Sensitivity_Meter> (background; it describes the
   narrower definition and notes that "the general explanation of intersecting cumulative frequencies
   varies".)

9. Efron, B. and Tibshirani, R. J. (1993). An Introduction to the Bootstrap. Chapman & Hall. (Percentile
   interval.)
10. Hyndman, R. J. and Fan, Y. (1996). "Sample quantiles in statistical packages." The American
    Statistician 50(4), 361–365. (Quantile definition 7.)


## Pitfalls

- Mixing the two PMC/PME definitions, or reporting a range without saying which one was used.
- Building all four curves as rising cumulative distributions, which reverses the meaning of the two cheap
  curves.
- Using > on one curve and ≥ on another, or changing the boundary between runs.
- Dropping inconsistent respondents without reporting how many, or keeping them without saying so.
- Reading currency strings, decimal commas or blank cells as numbers by guesswork; a stray 0 or 100000
  stretches the grid and the chart.
- Calling OPP "the optimal price" or "the revenue-maximizing price".
- Saying the extension's intent questions are asked at OPP and IPP; they are asked at each respondent's own
  cheap and expensive prices.
- Presenting the Newton-Miller-Smith curves without the weights they assume.
- Pooling segments with different reference prices (for example small business and enterprise): the pooled
  curves cross where neither segment is.
- Reading precision into a small sample: with few respondents one answer moves a curve by several points.
- Comparing numbers with another tool without matching its conventions first
  ([tool-conventions.md](tool-conventions.md)).
- Inventing responses when there is no data. With no data the deliverable is the survey, not a result.
- Trimming "outliers" by an uncited rule, or silently.
