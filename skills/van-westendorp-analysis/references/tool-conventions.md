# Why another tool gives different numbers

The same answers give different price points in different tools because five conventions vary. This table
records what each tool does, where we could establish it, and the flags that make this skill's script follow
it. Checked 2026-11-12; citations are in [sources.md](sources.md).

| Convention | This script (default) | R `pricesensitivitymeter` 1.3.3 (CRAN) | R `pricesensitivitymeter` up to 1.3.0 | Conjointly | Sawtooth Software | Most published agent skills |
|---|---|---|---|---|---|---|
| Consistency rule | too cheap ≤ cheap ≤ expensive ≤ too expensive; violators excluded and counted | strict < ; violators excluded by default (`validate = TRUE`) | same as 1.3.3 | worked example keeps a respondent with cheap = expensive; rule not stated | not stated | usually ≤, often not stated |
| Falling curves (too cheap, cheap) at price p | share with answer ≥ p | share with answer > p; at and below the lowest answer set to 100% | share with answer > p | share with answer ≥ p | not stated | varies; some build all four curves rising, which is wrong |
| Rising curves (expensive, too expensive) at p | share with answer ≤ p | share with answer ≤ p; at and below the lowest answer set to 0% | share with answer ≤ p | share with answer ≤ p | not stated | varies |
| Crossing between observed prices | linear interpolation | linear interpolation (`identify_intersection`, confirmed by an R run) | first observed price at which the rising curve is at or above the falling one | read from the plotted lines; worked example crosses at observed prices | not stated | read from a chart, or a fixed price grid |
| Curves coincide over several prices | midpoint, with the interval and a warning | a crossing at each sign change of the difference: the run's first price, and its last price only when the curves part again before the highest observed price; `intersection_method` picks among them (default `"min"`; max, mean) | same | not stated | not stated | not handled |
| PMC and PME | original: too cheap × not cheap, too expensive × not expensive; narrower range always printed too | original by default; narrower optional | same as 1.3.3 | narrower: too cheap × expensive, too expensive × cheap | four-line chart: "furthest left" and "furthest right" intersection, which is the narrower pair | narrower (six of the seven that define them) |
| Name of cheap × expensive | IPP, with the alias IDP | IDP | IDP | "normal" or "indifference" price point | IPP | IPP or IDP |
| Purchase-intent weights | 70/50/30/10/0, presets and custom | 70/50/30/10/0, custom | same | rating ÷ 5 (0 to 80%), own demand method | Excel template: 70/50/30/10/0 as reported by the R package; Orme's slides show 75/25/10/0/0 for packaged goods | none computes the extension |

## Flags that follow another tool

| To compare with | Run |
|---|---|
| R `pricesensitivitymeter` 1.3.3, default arguments | `--compat r` (= `--strict --boundary exclusive-forced-ends --tie min`, with R's rule for coinciding curves). Checked against an R run. 1.3.1 and 1.3.2 (the pinned ends date from 1.3.1) were neither read nor run |
| R `pricesensitivitymeter` 1.3.0 and earlier, default arguments | `--compat r-1.3.0` (= `--strict --boundary exclusive --no-interpolate --tie min`) |
| R with `acceptable_range = "narrower"` | add `--range-definition narrower` |
| R with `intersection_method = "max"` or `"mean"` | add `--tie max` or `--tie mean` (with `--compat r` they pick from R's crossings, not from the whole run) |
| Conjointly's price points | `--range-definition narrower` (defaults otherwise). The published 10-respondent example reproduces: `fixtures/conjointly_published` |
| Conjointly's or R's purchase-intent curves | R: default weights, `--intent-scale 5,4,3,2,1` (R's default `pi_scale`), and `--nms-too-cheap-prob` / `--nms-too-expensive-prob` for its two end settings. R's `price_optimal_revenue` searches the observed prices only: compare it with the script's "highest among the observed prices only" line (`revenue_max_on_grid`); the script's headline revenue price can lie between observed prices. Conjointly's demand method is different and is not reproduced |
| A tool that reports only one range | The script prints both ranges and labels them; compare with the matching one |

What the presets do not cover: R's `interpolate = TRUE` (it first fills the curves on a 0.01 price step,
then finds the crossing; on the fixtures below it gave the same price points as `interpolate = FALSE`, and
on `nms_interior` its revenue price, 50, matched the script's headline one), R's `intersection_method = "median"`, survey-design
weighting (`psm_analysis_weighted`, not run), and any tool's plotting.

How the R rules were established: read in the CRAN source of versions 1.3.3 and 1.3.0, then checked
against R 4.5.1 with `pricesensitivitymeter` 1.3.3 on 2026-11-19. On 11 fixture files, both range
definitions and `intersection_method` min, max and mean (66 runs), `--compat r` with the matching flags gave
R's four price points, analysed count, Newton-Miller-Smith trial curve, highest-trial price and
highest-revenue observed price to 1e-9: `fixtures/r_psm_1_3_3.expected.json`, R script in
`fixtures/README.md` section 14. The R run found one rule the source reading had missed: when the curves
coincide up to the highest observed price, R reports the run's first price whatever `intersection_method`
says, and `--compat r` now does the same. `--compat r-1.3.0` is still read from the source only.

The hand-worked example under these rules is in `fixtures/README.md`, section 7.
