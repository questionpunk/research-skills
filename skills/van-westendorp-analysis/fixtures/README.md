# Fixtures for van-westendorp-analysis

Every `<case>.input.csv` has a `<case>.expected.json`. The expected values were worked out by hand below, or
come from a published example. None were produced by the script. All data is synthetic or published; there
is no real respondent data.

| Case | What it checks | Where the expected values come from |
|---|---|---|
| `basic` | The four intersections, both range definitions, the curve table | Hand arithmetic, section 1 |
| `inconsistent` | Exclusion and count of out-of-order and incomplete respondents | Hand arithmetic, section 2 |
| `nms` | Newton-Miller-Smith trial and revenue curves, both variants | Hand arithmetic, section 3 |
| `nms_interior` | Revenue peak between two observed prices; a flat (coinciding) segment | Hand arithmetic, section 4 |
| `conjointly_published` | A published 10-respondent example with a tied respondent | Conjointly guide, section 5 |
| `orme_smith` | A published one-respondent Newton-Miller-Smith example | Orme (Sawtooth Software), section 6 |
| `r_conventions` (input: `basic.input.csv`) | `--compat r`, `--compat r-1.3.0`, `--boundary`, `--no-interpolate`, `--tie min` | Hand arithmetic under rules read in the R package source, section 7 |
| `segments` | `--segment`, and `--tie` on a flat run | Hand arithmetic, section 8 |
| `weighted` | `--weight` in the curves and in the Newton-Miller-Smith trial | Hand arithmetic, section 9 |
| `three_question` | No too-cheap column | Hand arithmetic, section 10 |
| `basic` with `--max-price`, `--min-price`, `--at`, `--curves-csv` | Counted price-limit exclusion, shares at a candidate price, curve export | Hand arithmetic, section 11 |
| `nms` with `--nms-preset`, `--nms-too-cheap-prob` | Weight presets and end probabilities | Hand arithmetic, section 12 |
| `ipp_below_opp`, `no_width`, `tie_run` | Degenerate-result warnings; all four `--tie` rules on a three-price run | Hand arithmetic, section 13 |

Provenance in one line: `conjointly_published` and `orme_smith` are published examples (URLs in their
sections); every other input file was invented for this skill. The bootstrap has no expected values: its
test checks that the same seed gives the same output and that each point lies inside its interval.

## Rules used in every derivation

- Grid: every distinct price any analysed respondent gave, in ascending order.
- Too cheap(p) = number of respondents whose too-cheap price is **≥ p**. Cheap(p) = number whose cheap price
  is **≥ p**. Expensive(p) = number whose expensive price is **≤ p**. Too expensive(p) = number whose
  too-expensive price is **≤ p**. Not cheap = n − Cheap. Not expensive = n − Expensive.
- For two curves f and g, d(p) = f(p) − g(p) on the grid.
  - d = 0 at exactly one grid price: that price is the crossing ("exact").
  - d changes sign between neighbouring grid prices p1 and p2: crossing = p1 + (p2 − p1) × d1 / (d1 − d2)
    ("interpolated").
  - d = 0 at several neighbouring grid prices from a to b: the curves coincide there, and the crossing is
    reported as (a + b) / 2 with the interval ("flat").

## 1. `basic` (10 respondents)

| id | too cheap | cheap | expensive | too expensive |
|---|---|---|---|---|
| R01 | 2 | 4 | 6 | 8 |
| R02 | 3 | 5 | 8 | 10 |
| R03 | 4 | 6 | 8 | 12 |
| R04 | 4 | 7 | 10 | 12 |
| R05 | 5 | 8 | 10 | 14 |
| R06 | 6 | 9 | 12 | 15 |
| R07 | 7 | 10 | 12 | 16 |
| R08 | 8 | 10 | 14 | 18 |
| R09 | 9 | 12 | 15 | 20 |
| R10 | 10 | 14 | 16 | 20 |

Sorted answers:

- too cheap: 2, 3, 4, 4, 5, 6, 7, 8, 9, 10
- cheap: 4, 5, 6, 7, 8, 9, 10, 10, 12, 14
- expensive: 6, 8, 8, 10, 10, 12, 12, 14, 15, 16
- too expensive: 8, 10, 12, 12, 14, 15, 16, 18, 20, 20

Cumulative counts out of 10 (multiply by 10 for percentages):

| Price | Too cheap (≥) | Cheap (≥) | Expensive (≤) | Too expensive (≤) | Not cheap | Not expensive |
|---|---|---|---|---|---|---|
| 2 | 10 | 10 | 0 | 0 | 0 | 10 |
| 3 | 9 | 10 | 0 | 0 | 0 | 10 |
| 4 | 8 | 10 | 0 | 0 | 0 | 10 |
| 5 | 6 | 9 | 0 | 0 | 1 | 10 |
| 6 | 5 | 8 | 1 | 0 | 2 | 9 |
| 7 | 4 | 7 | 1 | 0 | 3 | 9 |
| 8 | 3 | 6 | 3 | 1 | 4 | 7 |
| 9 | 2 | 5 | 3 | 1 | 5 | 7 |
| 10 | 1 | 4 | 5 | 2 | 6 | 5 |
| 12 | 0 | 2 | 7 | 4 | 8 | 3 |
| 14 | 0 | 1 | 8 | 5 | 9 | 2 |
| 15 | 0 | 0 | 9 | 6 | 10 | 1 |
| 16 | 0 | 0 | 10 | 7 | 10 | 0 |
| 18 | 0 | 0 | 10 | 8 | 10 | 0 |
| 20 | 0 | 0 | 10 | 10 | 10 | 0 |

Intersections:

- **OPP** = too cheap × too expensive. d = TC − TE: at 9, 2 − 1 = +1; at 10, 1 − 2 = −1.
  OPP = 9 + (10 − 9) × 1 / (1 − (−1)) = 9 + 0.5 = **9.50**.
- **IPP** = cheap × expensive. d = C − E: at 9, 5 − 3 = +2; at 10, 4 − 5 = −1.
  IPP = 9 + (10 − 9) × 2 / (2 − (−1)) = 9 + 2/3 = **9.6667**.
- **PMC, original** = too cheap × not cheap. d = TC − NC: at 7, 4 − 3 = +1; at 8, 3 − 4 = −1.
  PMC = 7 + (8 − 7) × 1 / (1 − (−1)) = **7.50**.
- **PME, original** = too expensive × not expensive. d = TE − NE: at 10, 2 − 5 = −3; at 12, 4 − 3 = +1.
  PME = 10 + (12 − 10) × (−3) / (−3 − 1) = 10 + 2 × 0.75 = **11.50**.
- **PMC, narrower** = too cheap × expensive. d = TC − E: at 7, 4 − 1 = +3; at 8, 3 − 3 = 0; at 9, 2 − 3 = −1.
  Zero at one grid price: PMC = **8.00** (exact).
- **PME, narrower** = too expensive × cheap. d = TE − C: at 10, 2 − 4 = −2; at 12, 4 − 2 = +2.
  PME = 10 + (12 − 10) × (−2) / (−2 − 2) = 10 + 1 = **11.00**.

Acceptable range: original **7.50 to 11.50**; narrower **8.00 to 11.00**.

## 2. `inconsistent` (13 rows)

The 10 rows of `basic` plus:

| id | too cheap | cheap | expensive | too expensive | Status |
|---|---|---|---|---|---|
| R11 | 5 | 12 | 9 | 15 | Inconsistent: cheap 12 > expensive 9 |
| R12 | 6 | 8 | 14 | 11 | Inconsistent: expensive 14 > too expensive 11 |
| R13 | (blank) | 9 | 12 | 16 | Incomplete |

Default run: 13 read, 1 incomplete, 2 inconsistent (R11, R12), 10 analysed. The analysed rows are the `basic`
rows, so every price point equals section 1.

With `--keep-inconsistent`: 12 analysed (R13 stays out, it has no too-cheap price). OPP by hand:
too cheap answers 2, 3, 4, 4, 5, 5, 6, 6, 7, 8, 9, 10, so TC(9) = 2 and TC(10) = 1. Too expensive answers
8, 10, 11, 12, 12, 14, 15, 15, 16, 18, 20, 20, so TE(9) = 1 and TE(10) = 2. d(9) = +1, d(10) = −1, and
OPP = 9 + 1 × 1 / 2 = **9.50**. (11 joins the grid, but the crossing is before it.)

## 3. `nms` (4 respondents, default weights 5 → 0.70, 4 → 0.50, 3 → 0.30, 2 → 0.10, 1 → 0)

| id | too cheap | cheap | expensive | too expensive | intent at cheap | intent at expensive |
|---|---|---|---|---|---|---|
| N1 | 10 | 20 | 30 | 40 | 5 → 0.70 | 3 → 0.30 |
| N2 | 10 | 20 | 40 | 50 | 4 → 0.50 | 2 → 0.10 |
| N3 | 20 | 30 | 40 | 60 | 5 → 0.70 | 4 → 0.50 |
| N4 | 20 | 30 | 50 | 60 | 3 → 0.30 | 1 → 0 |

Rule (original variant): probability 0 at and below too cheap and at and above too expensive; the stated
probabilities at the cheap and expensive prices; straight lines in between.

Purchase probability of each respondent at each grid price:

| Price | N1 | N2 | N3 | N4 | Sum | Trial = sum / 4 | Revenue index = price × trial |
|---|---|---|---|---|---|---|---|
| 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 0.70 | 0.50 | 0 | 0 | 1.20 | 0.30 | 6.00 |
| 30 | 0.30 | 0.30 | 0.70 | 0.30 | 1.60 | 0.40 | 12.00 |
| 40 | 0 | 0.10 | 0.50 | 0.15 | 0.75 | 0.1875 | 7.50 |
| 50 | 0 | 0 | 0.25 | 0 | 0.25 | 0.0625 | 3.125 |
| 60 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Interpolated cells: N2 at 30 is halfway between (20, 0.50) and (40, 0.10) = 0.30. N4 at 40 is halfway between
(30, 0.30) and (50, 0) = 0.15. N3 at 50 is halfway between (40, 0.50) and (60, 0) = 0.25.

Highest trial: **30** (0.40). Highest revenue index: **30** (12.00). No segment has a higher value inside it:
on 20 to 30 the trial rises, so revenue rises to 30; on 30 to 40 trial(p) = 0.40 − 0.02125 × (p − 30) =
1.0375 − 0.02125p, revenue = 1.0375p − 0.02125p², whose vertex 1.0375 / 0.0425 = 24.4 lies left of the
segment, so revenue falls from 30 onwards.

Modified variant (`--nms-variant modified`): below the cheap price the probability stays at the cheap-price
value. At 10 every respondent is below cheap: (0.70 + 0.50 + 0.70 + 0.30) / 4 = **0.55**, revenue 5.50. At 20:
N1 0.70, N2 0.50, N3 0.70 (20 is below its cheap price 30), N4 0.30, trial **0.55**, revenue 11.00. From 30
upwards nothing changes. On 20 to 30, trial(p) = 0.55 − 0.015 × (p − 20) = 0.85 − 0.015p and revenue =
0.85p − 0.015p², with its vertex at 0.85 / 0.03 = **28.3333**, inside the segment. There trial = 0.85 − 0.425
= 0.425 and revenue = 28.3333 × 0.425 = **12.0417**, above the 12.00 at 30. So the modified variant reports a
revenue-maximizing price of 28.33, between two observed prices.

## 4. `nms_interior` (1 respondent)

V1: too cheap 10, cheap 20 (intent 5 → 0.70), expensive 30 (intent 4 → 0.50), too expensive 100.

| Price | Trial | Revenue index |
|---|---|---|
| 10 | 0 | 0 |
| 20 | 0.70 | 14.00 |
| 30 | 0.50 | 15.00 |
| 100 | 0 | 0 |

Highest trial: **20** (0.70). Highest revenue among observed prices: **30** (15.00).

Between 30 and 100 the trial is 0.50 × (100 − p) / 70, so revenue = p × (100 − p) / 140, a parabola with its
vertex at p = **50**: revenue = 50 × 50 / 140 = **17.857143**, trial = 0.50 × 50 / 70 = **0.357143**. (On 20 to
30, trial = 1.1 − 0.02p, vertex 1.1 / 0.04 = 27.5, revenue 27.5 × 0.55 = 15.125, lower.) The script reports
50 as the revenue-maximizing price and 30 as the highest among observed prices.

Flat segment, same file: grid 10, 20, 30, 100. Too cheap counts 1, 0, 0, 0; too expensive counts 0, 0, 0, 1.
d = +1, 0, 0, −1: zero at 20 and at 30, so the curves coincide from 20 to 30 and OPP is reported as
(20 + 30) / 2 = **25.00** with status `flat` and a warning.

## 5. `conjointly_published` (published example, 10 respondents)

Source: Conjointly, "How to manually calculate Van Westendorp PSM's results",
<https://conjointly.com/guides/manual-calculation-of-van-westendorp/> (read 2026-11-12). The input is the
guide's example table (the respondent and four price columns; its two intent columns use Conjointly's own 0 to 4 scale and
method, which this skill does not reproduce). Conjointly uses the narrower range definition, so the fixture
runs with `--range-definition narrower`.

The guide's cumulative table matches the rules above. Counts out of 10 at the prices that matter:

| Price | Too cheap | Cheap | Expensive | Too expensive |
|---|---|---|---|---|
| 5.00 | 3 | 7 | 1 | 0 |
| 5.50 | 2 | 6 | 2 | 0 |
| 6.00 | 2 | 6 | 3 | 0 |
| 6.50 | 1 | 5 | 4 | 0 |
| 7.00 | 1 | 5 | 5 | 1 |
| 8.00 | 0 | 4 | 6 | 2 |
| 8.50 | 0 | 3 | 6 | 3 |
| 9.00 | 0 | 1 | 6 | 4 |
| 10.00 | 0 | 0 | 7 | 5 |

| Point | Curves | d around the crossing | Result | Published |
|---|---|---|---|---|
| OPP | too cheap × too expensive | 6.50: +1; 7.00: 0; 8.00: −2 | 7.00 | $7.00 |
| IPP | cheap × expensive | 6.50: +1; 7.00: 0; 8.00: −2 | 7.00 | $7.00 |
| PME (narrower) | too expensive × cheap | 8.00: −2; 8.50: 0; 9.00: +3 | 8.50 | $8.50 |
| PMC (narrower) | too cheap × expensive | 5.00: +2; 5.50: 0; 6.00: −1 | 5.50 | see note |

Note on the lower bound: the guide's chart callout reads "Lower end of range $6.50", but its own cumulative
table has too cheap = expensive = 20% at $5.50 (and 10% against 40% at $6.50), and the callout's pointer and
the shaded band start at $5.50. The fixture expects 5.50, the value the published table gives.

Original definition on the same data (hand arithmetic, not published): PMC = too cheap × not cheap: at 4.00,
4 − 0 = +4; at 5.00, 3 − 3 = 0; at 5.50, 2 − 4 = −2, so **5.00**. PME = too expensive × not expensive: at
8.50, 3 − 4 = −1; at 9.00, 4 − 4 = 0; at 10.00, 5 − 3 = +2, so **9.00**.

Respondent 5 gave $8.00 as both the cheap and the expensive price. The default rule (≤) keeps that respondent,
as the guide does; `--strict` excludes them (1 inconsistent, 9 analysed).

## 6. `orme_smith` (published example, 1 respondent)

Source: Bryan Orme, "Pricing Research Tools You Must Know" (Sawtooth Software slides), Newton-Miller-Smith
example, <https://content.sawtoothsoftware.com/assets/edbf9432-d508-4d30-a0b6-58ccc77d4bd1> (read 2026-11-12).

"Smith says $100 is too cheap and $200 is too expensive. She definitely would buy (75% probability) at her
acceptably cheap price of $130. She might or might not buy (10% probability) at her acceptably expensive
price of $175." The slides put her probability at 0% at and outside $100 and $200 and interpolate in between.
The example uses the deflated weights 75%, 25%, 10%, 0%, 0%, so the fixture runs with
`--nms-weights 0.75,0.25,0.10,0,0` ("definitely" = 5, "might or might not" = 3).

| Price | Trial | Revenue index |
|---|---|---|
| 100 | 0 | 0 |
| 130 | 0.75 | 97.50 |
| 175 | 0.10 | 17.50 |
| 200 | 0 | 0 |

Highest trial and highest revenue are both at **130** (the revenue values are our arithmetic; the slides give
the probabilities). No segment peaks inside: revenue rises from 100 to 130; on 130 to 175 the vertex is at
about 91 and on 175 to 200 it is at 100, both left of their segments, so revenue falls after 130.

## 7. `r_conventions` (the `basic` data under the R package's rules)

Input: `basic.input.csv`. All 10 respondents are strictly ordered, so `--strict` excludes no one. The rules
below were read in the source of the R package `pricesensitivitymeter` (see `references/tool-conventions.md`);
the numbers are our hand arithmetic, not R output.

**Exclusive boundary** (`--boundary exclusive`): the falling curves count answers strictly above p; the
rising curves are unchanged (≤ p). Counts out of 10:

| Price | Too cheap (>) | Cheap (>) | Expensive (≤) | Too expensive (≤) | Not cheap | Not expensive |
|---|---|---|---|---|---|---|
| 2 | 9 | 10 | 0 | 0 | 0 | 10 |
| 3 | 8 | 10 | 0 | 0 | 0 | 10 |
| 4 | 6 | 9 | 0 | 0 | 1 | 10 |
| 5 | 5 | 8 | 0 | 0 | 2 | 10 |
| 6 | 4 | 7 | 1 | 0 | 3 | 9 |
| 7 | 3 | 6 | 1 | 0 | 4 | 9 |
| 8 | 2 | 5 | 3 | 1 | 5 | 7 |
| 9 | 1 | 4 | 3 | 1 | 6 | 7 |
| 10 | 0 | 2 | 5 | 2 | 8 | 5 |
| 12 | 0 | 1 | 7 | 4 | 9 | 3 |
| 14 | 0 | 0 | 8 | 5 | 10 | 2 |
| 15 | 0 | 0 | 9 | 6 | 10 | 1 |
| 16 | 0 | 0 | 10 | 7 | 10 | 0 |
| 18 | 0 | 0 | 10 | 8 | 10 | 0 |
| 20 | 0 | 0 | 10 | 10 | 10 | 0 |

**Forced ends** (`--boundary exclusive-forced-ends`): at and below a question's lowest answer, its falling
curve is set to 10 and its rising curve to 0. Lowest answers: too cheap 2, cheap 4, expensive 6, too
expensive 8. Four cells change: too cheap at 2 becomes 10 (was 9); cheap at 4 becomes 10 (was 9), so not
cheap at 4 becomes 0; expensive at 6 becomes 0 (was 1), so not expensive at 6 becomes 10; too expensive at 8
becomes 0 (was 1). Every other cell is as in the table.

**`--compat r`** = strict, forced ends, lower end on ties, linear interpolation:

- OPP: d = TC − TE: at 8, 2 − 0 = +2 (forced; unforced 2 − 1 = +1); at 9, 1 − 1 = 0; at 10, 0 − 2 = −2.
  Exact: **9.00**.
- IPP: d = C − E: at 9, 4 − 3 = +1; at 10, 2 − 5 = −3. IPP = 9 + 1 × 1 / (1 + 3) = **9.25**.
- PMC (original): d = TC − NC: at 6, 4 − 3 = +1; at 7, 3 − 4 = −1. PMC = 6 + 1 × 1 / 2 = **6.50**.
- PME (original): d = NE − TE: at 10, 5 − 2 = +3; at 12, 3 − 4 = −1. PME = 10 + 2 × 3 / 4 = **11.50**.
- Narrower PMC: d = TC − E: at 7, 3 − 1 = +2; at 8, 2 − 3 = −1. 7 + 1 × 2 / 3 = **7.6667**.
- Narrower PME: d = C − TE: at 9, 4 − 1 = +3; at 10, 2 − 2 = 0; at 12, 1 − 4 = −3. Exact: **10.00**.

**`--compat r-1.3.0`** = strict, exclusive boundary without forced ends, no interpolation (the first grid
price at which the rising curve is at or above the falling one), lower end on ties:

| Point | Rising ≥ falling first holds at | Check of the price before |
|---|---|---|
| OPP (TE ≥ TC) | **9**: 1 ≥ 1 | 8: 1 ≥ 2 is false |
| IPP (E ≥ C) | **10**: 5 ≥ 2 | 9: 3 ≥ 4 is false |
| PMC original (NC ≥ TC) | **7**: 4 ≥ 3 | 6: 3 ≥ 4 is false |
| PME original (TE ≥ NE) | **12**: 4 ≥ 3 | 10: 2 ≥ 5 is false |
| PMC narrower (E ≥ TC) | **8**: 3 ≥ 2 | 7: 1 ≥ 3 is false |
| PME narrower (TE ≥ C) | **10**: 2 ≥ 2 | 9: 1 ≥ 4 is false |

**Explicit flags** `--strict --boundary exclusive-forced-ends --no-interpolate --tie min`: the four forced
cells are at prices 2, 4, 6 and 8, and none of the six comparisons above changes (at 8, OPP compares 0 ≥ 2
and narrower PMC compares 3 ≥ 2, as before). Same results: OPP 9, IPP 10, PMC 7, PME 12.

## 8. `segments` (`--segment plan`)

`basic` plus a `plan` column: R01 to R05 are `starter`, R06 to R10 are `team`. The overall result is section 1.

**starter** (5 respondents). Sorted: too cheap 2, 3, 4, 4, 5; cheap 4, 5, 6, 7, 8; expensive 6, 8, 8, 10, 10;
too expensive 8, 10, 12, 12, 14. Counts out of 5:

| Price | Too cheap (≥) | Cheap (≥) | Expensive (≤) | Too expensive (≤) | Not cheap | Not expensive |
|---|---|---|---|---|---|---|
| 2 | 5 | 5 | 0 | 0 | 0 | 5 |
| 3 | 4 | 5 | 0 | 0 | 0 | 5 |
| 4 | 3 | 5 | 0 | 0 | 0 | 5 |
| 5 | 1 | 4 | 0 | 0 | 1 | 5 |
| 6 | 0 | 3 | 1 | 0 | 2 | 4 |
| 7 | 0 | 2 | 1 | 0 | 3 | 4 |
| 8 | 0 | 1 | 3 | 1 | 4 | 2 |
| 10 | 0 | 0 | 5 | 2 | 5 | 0 |
| 12 | 0 | 0 | 5 | 4 | 5 | 0 |
| 14 | 0 | 0 | 5 | 5 | 5 | 0 |

- OPP: TC − TE: at 5, +1; at 6, 0; at 7, 0; at 8, −1. Flat from 6 to 7: midpoint **6.50** (`--tie min` 6,
  `--tie max` 7).
- IPP: C − E: at 7, 2 − 1 = +1; at 8, 1 − 3 = −2. 7 + 1 × 1 / 3 = **7.3333**.
- PMC original: TC − NC: at 4, +3; at 5, 1 − 1 = 0; at 6, −2. Exact **5.00**.
- PME original: NE − TE: at 8, 2 − 1 = +1; at 10, 0 − 2 = −2. 8 + 2 × 1 / 3 = **8.6667**.
- Narrower: PMC = TC − E: at 5, +1; at 6, −1: **5.50**. PME = C − TE: at 7, +2; at 8, 1 − 1 = 0; at 10, −2:
  exact **8.00**.

**team** (5 respondents). Sorted: too cheap 6, 7, 8, 9, 10; cheap 9, 10, 10, 12, 14; expensive 12, 12, 14,
15, 16; too expensive 15, 16, 18, 20, 20. Counts out of 5:

| Price | Too cheap (≥) | Cheap (≥) | Expensive (≤) | Too expensive (≤) | Not cheap | Not expensive |
|---|---|---|---|---|---|---|
| 6 | 5 | 5 | 0 | 0 | 0 | 5 |
| 7 | 4 | 5 | 0 | 0 | 0 | 5 |
| 8 | 3 | 5 | 0 | 0 | 0 | 5 |
| 9 | 2 | 5 | 0 | 0 | 0 | 5 |
| 10 | 1 | 4 | 0 | 0 | 1 | 5 |
| 12 | 0 | 2 | 2 | 0 | 3 | 3 |
| 14 | 0 | 1 | 3 | 0 | 4 | 2 |
| 15 | 0 | 0 | 4 | 1 | 5 | 1 |
| 16 | 0 | 0 | 5 | 2 | 5 | 0 |
| 18 | 0 | 0 | 5 | 3 | 5 | 0 |
| 20 | 0 | 0 | 5 | 5 | 5 | 0 |

- OPP: TC − TE: at 10, +1; at 12, 0; at 14, 0; at 15, −1. Flat from 12 to 14: midpoint **13.00**.
- IPP: C − E: at 10, +4; at 12, 2 − 2 = 0; at 14, −2. Exact **12.00**. (IPP is below OPP here, so the
  script adds that warning for this segment.)
- PMC original: TC − NC: at 9, +2; at 10, 1 − 1 = 0; at 12, −3. Exact **10.00**.
- PME original: NE − TE: at 14, 2 − 0 = +2; at 15, 1 − 1 = 0; at 16, −2. Exact **15.00**.
- Narrower: PMC = TC − E: at 10, +1; at 12, −2: 10 + 2 × 1 / 3 = **10.6667**. PME = C − TE: at 14, +1; at
  15, −1: **14.50**.

## 9. `weighted` (`--weight weight`)

| id | too cheap | cheap | expensive | too expensive | intent at cheap | intent at expensive | weight |
|---|---|---|---|---|---|---|---|
| W1 | 1 | 2 | 3 | 4 | 5 → 0.70 | 3 → 0.30 | 1 |
| W2 | 2 | 3 | 4 | 5 | 4 → 0.50 | 2 → 0.10 | 3 |
| W3 | 3 | 4 | 5 | 6 | 5 → 0.70 | 3 → 0.30 | 1 |
| W4 | 4 | 5 | 6 | 7 | 3 → 0.30 | 1 → 0 | 1 |

Total weight 6. Each curve adds weights instead of counting respondents:

| Price | Too cheap (≥) | Cheap (≥) | Expensive (≤) | Too expensive (≤) | Not cheap | Not expensive |
|---|---|---|---|---|---|---|
| 1 | 6 | 6 | 0 | 0 | 0 | 6 |
| 2 | 5 | 6 | 0 | 0 | 0 | 6 |
| 3 | 2 | 5 | 1 | 0 | 1 | 5 |
| 4 | 1 | 2 | 4 | 1 | 4 | 2 |
| 5 | 0 | 1 | 5 | 4 | 5 | 1 |
| 6 | 0 | 0 | 6 | 5 | 6 | 0 |
| 7 | 0 | 0 | 6 | 6 | 6 | 0 |

- OPP: TC − TE: at 3, +2; at 4, 1 − 1 = 0; at 5, −4. Exact **4.00**.
- IPP: C − E: at 3, 5 − 1 = +4; at 4, 2 − 4 = −2. 3 + 1 × 4 / 6 = **3.6667**.
- PMC original: TC − NC: at 3, 2 − 1 = +1; at 4, 1 − 4 = −3. 3 + 1 / 4 = **3.25**.
- PME original: NE − TE: at 4, 2 − 1 = +1; at 5, 1 − 4 = −3. 4 + 1 / 4 = **4.25**.

Without weights IPP differs: C(3) = 3, E(3) = 1, d = +2; C(4) = 2, E(4) = 2, d = 0: exact **4.00**.

Weighted Newton-Miller-Smith trial = Σ weight × probability / 6:

| Price | W1 (×1) | W2 (×3) | W3 (×1) | W4 (×1) | Weighted sum | Trial |
|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | 0.70 | 0 | 0 | 0 | 0.70 | 0.116667 |
| 3 | 0.30 | 0.50 | 0 | 0 | 0.30 + 1.50 = 1.80 | 0.30 |
| 4 | 0 | 0.10 | 0.70 | 0 | 0.30 + 0.70 = 1.00 | 0.166667 |
| 5 | 0 | 0 | 0.30 | 0.30 | 0.60 | 0.10 |
| 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| 7 | 0 | 0 | 0 | 0 | 0 | 0 |

(Every price is one of each respondent's own four prices or outside them, so no cell is interpolated.)
Highest trial: **3** (0.30). Revenue index: 2 → 0.2333, 3 → **0.90**, 4 → 0.6667, 5 → 0.50. On 3 to 4 the
trial is 0.70 − 0.13333p, vertex 0.70 / 0.26667 = 2.6, left of the segment, so the maximum stays at 3.

## 10. `three_question` (no too-cheap column)

`basic` without the `too_cheap` column. Consistency rule: cheap ≤ expensive ≤ too expensive; all 10 pass.
The grid loses 2 and 3 (they were only too-cheap answers); the cheap, expensive and too-expensive counts at
the remaining prices are those of section 1.

- IPP = cheap × expensive: **9.6667**, as in section 1.
- PME original = too expensive × not expensive: **11.50**; narrower = too expensive × cheap: **11.00**.
- OPP and PMC need the too-cheap curve under both definitions: no value, status `unavailable`, and a warning.

## 11. `basic` with limits, `--at` and `--curves-csv`

`--max-price 18` excludes R09 and R10 (both have a too-expensive price of 20): 2 outside the limits, 8
analysed. Sorted: too cheap 2, 3, 4, 4, 5, 6, 7, 8; cheap 4, 5, 6, 7, 8, 9, 10, 10; expensive 6, 8, 8, 10,
10, 12, 12, 14; too expensive 8, 10, 12, 12, 14, 15, 16, 18.

- OPP: at 7, TC 2 − TE 0 = +2; at 8, 1 − 1 = 0; at 9, 0 − 1 = −1. Exact **8.00**.
- IPP: at 8, C 4 − E 3 = +1; at 9, 3 − 3 = 0; at 10, 2 − 5 = −3. Exact **9.00**.

`--min-price 3` excludes R01 (too cheap 2): 1 outside the limits, 9 analysed.

`--at 9` (all 10 respondents; 9 is a grid price, row 9 of section 1): too cheap 2/10, cheap 5/10, expensive
3/10, too expensive 1/10, not cheap 5/10, not expensive 7/10. Neither too cheap nor too expensive: too-cheap
price below 9 (R01 to R08) and too-expensive price above 9 (all but R01) = R02 to R08 = **7/10**.

`--at 9.5` (not a grid price; counted directly): too-cheap answers ≥ 9.5: 10 → 1/10. Cheap ≥ 9.5: 10, 10,
12, 14 → 4/10. Expensive ≤ 9.5: 6, 8, 8 → 3/10. Too expensive ≤ 9.5: 8 → 1/10. Not cheap 6/10, not expensive
7/10. Neither: 1 − 1/10 − 1/10 = **8/10**.

`--curves-csv`: 15 data rows, one per grid price, with the shares of the section 1 table (counts ÷ 10).

## 12. `nms` with a preset and with an end probability

`--nms-preset orme-cpg` (5 → 0.75, 4 → 0.25, 3 → 0.10, 2 → 0, 1 → 0): N1 0.75 at 20 and 0.10 at 30; N2 0.25
at 20 and 0 at 40; N3 0.75 at 30 and 0.25 at 40; N4 0.10 at 30 and 0 at 50.

| Price | N1 | N2 | N3 | N4 | Sum | Trial |
|---|---|---|---|---|---|---|
| 10 | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 0.75 | 0.25 | 0 | 0 | 1.00 | 0.25 |
| 30 | 0.10 | 0.125 | 0.75 | 0.10 | 1.075 | 0.26875 |
| 40 | 0 | 0 | 0.25 | 0.05 | 0.30 | 0.075 |
| 50 | 0 | 0 | 0.125 | 0 | 0.125 | 0.03125 |
| 60 | 0 | 0 | 0 | 0 | 0 | 0 |

(N2 at 30 is halfway from 0.25 to 0; N4 at 40 halfway from 0.10 to 0; N3 at 50 halfway from 0.25 to 0.)

`--nms-too-cheap-prob 0.2` with the default weights: at 10, N1 and N2 are at their too-cheap price and N3
and N4 below theirs, so all four are 0.20: trial **0.20**. At 20: N1 0.70, N2 0.50, N3 and N4 at their
too-cheap price 0.20: 1.60 / 4 = **0.40**. At 30 nothing changes: **0.40**.

## 13. Small degenerate cases

`ipp_below_opp` (A and B: 1, 2, 3, 10; C: 8, 9, 9.5, 10). Counts out of 3:

| Price | Too cheap (≥) | Cheap (≥) | Expensive (≤) | Too expensive (≤) |
|---|---|---|---|---|
| 1 | 3 | 3 | 0 | 0 |
| 2 | 1 | 3 | 0 | 0 |
| 3 | 1 | 1 | 2 | 0 |
| 8 | 1 | 1 | 2 | 0 |
| 9 | 0 | 1 | 2 | 0 |
| 9.5 | 0 | 0 | 3 | 0 |
| 10 | 0 | 0 | 3 | 3 |

OPP: TC − TE = 3, 1, 1, 1, 0, 0, −3: flat from 9 to 9.5, midpoint **9.25**. IPP: C − E: at 2, +3; at 3,
1 − 2 = −1: 2 + 1 × 3 / 4 = **2.75**. IPP is below OPP, so the warning appears.

`no_width` (one respondent: 1, 2, 2, 3). Grid 1, 2, 3. Too cheap 1, 0, 0; cheap 1, 1, 0; expensive 0, 1, 1;
too expensive 0, 0, 1; not cheap 0, 0, 1; not expensive 1, 0, 0. PMC original: TC − NC = +1, 0, −1: exact
**2.00**. PME original: NE − TE = +1, 0, −1: exact **2.00**. PMC equals PME, so the warning appears.

`tie_run` (T1: 1, 2, 5, 6; T2: 1, 3, 5, 6). Grid 1, 2, 3, 5, 6. Too cheap 2, 0, 0, 0, 0; too expensive
0, 0, 0, 0, 2. TC − TE = +2, 0, 0, 0, −2: the curves coincide at 2, 3 and 5. `--tie min` **2**, `--tie max`
**5**, `--tie midpoint` (2 + 5) / 2 = **3.50**, `--tie mean` (2 + 3 + 5) / 3 = **3.3333**.
