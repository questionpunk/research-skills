---
name: van-westendorp-analysis
description: "Computes a Van Westendorp price sensitivity meter (PSM) from a CSV of survey answers: optimal (OPP) and indifference (IPP/IDP) price points, PMC, PME and the acceptable price range, plus the optional Newton-Miller-Smith purchase-intent extension. Flags inconsistent respondents and prints the convention used, so results can be compared with R, Conjointly or Sawtooth. Use for \"Van Westendorp\", \"price sensitivity meter\", \"PSM analysis\", \"acceptable price range\", \"willingness to pay survey\" or \"what should we charge\" when you have four-question pricing survey data."
license: MIT
metadata:
  version: "0.2.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "pricing-research"
---

# Van Westendorp analysis

Turn a Van Westendorp price sensitivity meter (PSM) survey into the four price points, the acceptable price
range under both common definitions and, when purchase-intent answers exist, the Newton-Miller-Smith trial
and revenue curves. A script does the arithmetic and prints the conventions it used, so the result can be
compared with R, Conjointly or Sawtooth. Method notes and sources: [references/sources.md](references/sources.md).

The method measures price **perception**, not demand. It gives a range to test, not a price to ship.

## When to use

Use it when the user has respondent-level answers to the pricing questions and asks for:

- "Run Van Westendorp on this CSV", "price sensitivity meter", "PSM analysis"
- "What is the acceptable price range", "find OPP / IPP (IDP) / PMC / PME"
- "Analyze our willingness to pay survey" or "what should we charge", with data of this shape attached
- "Add the Newton-Miller-Smith extension", "which price maximizes revenue", with two purchase-intent columns
- "Why does R / Conjointly / my spreadsheet give a different range for the same data?"

Do not use it for:

| Request | Use instead |
|---|---|
| "Which pricing study should I run?", yes/no answers to a price ladder (Gabor-Granger), conjoint choice tasks | Not covered: say so and name the method |
| Speeders, straight-liners, duplicates in the whole survey | `survey-data-cleaning` |
| "How many respondents do I need?" | `survey-sample-size` |
| Pricing strategy, tiers or packaging with no survey data | Not this skill |

**No data yet:** give the user the survey below and stop. Never invent, simulate or extend responses, and
do not estimate crossings from a chart or from aggregated percentages: the script needs one row per
respondent.

The four questions (Orme, Sawtooth Software; wording and order can vary), each answered with a price in one
currency for one clearly described product and billing period:

1. "At what price would Item X be so inexpensive that you would doubt its quality?" (too cheap)
2. "At what price would you consider Item X a good value?" (cheap)
3. "At what price is Item X beginning to get expensive, but you would still consider buying it?" (expensive)
4. "At what price would Item X be so expensive you would never consider it?" (too expensive)

Optional, for the Newton-Miller-Smith extension: purchase intent on a 5-point scale ("definitely would buy"
to "definitely would not buy"), asked once at the respondent's own cheap price and once at their own
expensive price.

A skill named here may not be installed. If it is missing, say so, name the method the request needs,
and do not stretch this skill to cover it.

## What to ask for

Ask one question at most. If the currency or the billing period is not clear from the file, that is the
question: "Are these prices in <currency> per <period>?" Everything else has a default:

| Input | Default |
|---|---|
| File | The CSV the user gave: one row per respondent, a header row |
| Price columns | Found by name. If the script cannot tell, it stops and lists the columns: then ask which is which. No too-cheap column: the three-question variant runs and says so |
| Range definition | Headline `original` (Van Westendorp 1976); the `narrower` range is always printed beside it |
| Inconsistent respondents | Excluded and counted. Equal neighbouring prices count as consistent |
| Purchase-intent columns | Used when two are found. The scale direction is never assumed: confirm from the codebook or the answer labels which code means "definitely would buy" and pass `--intent-scale` highest first (QuestionPunk: 5) |
| Purchase-probability weights | 70%, 50%, 30%, 10%, 0% for the five scale points, highest first |
| Segments, weights | None. If the file has a segment or weight column, offer `--segment` or `--weight` |
| Outliers | Kept. The script prints min, median and max per question; exclude only with a limit the user agrees to |
| Comparison with another tool | None. If the user compares with R or Conjointly, see step 5 |

## Steps

1. **Look at the file.** Read the header and a few rows. Confirm one row per respondent. Note the currency
   marker, the decimal mark, how missing answers are written, and any segment or weight column.
2. **Run the script** by its path inside this skill's directory, from the user's working directory (so
   the chart lands next to their data):

   ```bash
   python3 <skill-dir>/scripts/van_westendorp_analysis.py answers.csv --json --chart psm.svg
   python3 <skill-dir>/scripts/van_westendorp_analysis.py answers.csv --json --intent-scale 5,4,3,2,1
   ```

   Add flags only when needed:

   | Situation | Flag |
   |---|---|
   | Columns not found or ambiguous | `--too-cheap COL --cheap COL --expensive COL --too-expensive COL` |
   | Intent columns not found | `--intent-cheap COL --intent-expensive COL` |
   | Prices written as `8,50`; cells such as `NA` mean no answer | `--decimal comma`; `--na NA,N/A` |
   | Compare segments | `--segment COL` (one table row per segment, each with its own warnings) |
   | Respondent weights | `--weight COL` |
   | Agreed price limits (for example joke answers) | `--min-price P --max-price P` (excluded respondents are counted) |
   | "How does price P look?" | `--at P` (share on each curve, and the share finding P neither too cheap nor too expensive) |
   | How stable are the points? | `--bootstrap 1000 --seed 1` (95% percentile intervals) |
   | Other tool reports too cheap × expensive and too expensive × cheap | `--range-definition narrower` (only swaps which range is the headline) |
   | Strict ordering; out-of-order respondents kept | `--strict`; `--keep-inconsistent` |
   | Intent columns present | `--intent-scale 5,4,3,2,1` (or `1,2,3,4,5` when 1 means "definitely would buy"); required. Other weights: `--nms-preset orme-cpg` or `--nms-weights` |
   | Rows under the header that are not answers | Qualtrics' question-text and ImportId rows are skipped automatically (said in the warnings); otherwise `--skip-rows N` |
   | Demand should not fall to zero below the cheap price | `--nms-variant modified` |
   | Export the curves | `--curves-csv curves.csv` |

   Without `--json` the script prints a readable report; `--curves` adds the cumulative table.
3. **If the script exits with an error, fix the cause, not the data.** It refuses non-numeric prices,
   multipliers and units (`1.5k`, `10 mo`), rows with more fields than the header, ambiguous columns,
   off-scale intent answers and an unstated intent direction. Do not edit answers to make it run; ask the
   user.
4. **Read the result.** Check the column mapping it printed, the respondent counts, the min / median / max
   of each question and every warning. Zero or absurd prices: tell the user and let them choose a limit.
5. **Comparing with another tool.** Tools differ in five conventions (consistency rule, curve boundary,
   interpolation, tie rule, PMC/PME definition); [references/tool-conventions.md](references/tool-conventions.md)
   has the table and the flags. For R `pricesensitivitymeter` run `--compat r` (read from the package
   source, not yet checked against an R run, so say so); for Conjointly read the narrower range. Say which
   conventions each number uses; do not call either tool wrong.
6. **Write the answer** in the shape below. Copy numbers from the script; do not recompute or re-round.

How each value is computed is in [references/sources.md](references/sources.md); hand-checked examples are
in [fixtures/README.md](fixtures/README.md).

## Output

Always this shape, in this order:

```markdown
## Van Westendorp result: <product>, <currency> per <billing period>

**Respondents:** <read> read, <incomplete> incomplete, <outside limits> outside the price limits,
<inconsistent> inconsistent (<excluded or kept>), <analysed> analysed.

| Price point | Price | Curves that cross | What it means |
|---|---|---|---|
| PMC, point of marginal cheapness | <x> | <pair> | Below this, more people are on the first curve of the pair than the second (original: too cheap vs not cheap; narrower: too cheap vs expensive): lower end of the range |
| OPP, optimal price point | <x> | too cheap × too expensive | As many reject it as too cheap as reject it as too expensive |
| IPP, indifference price point (IDP) | <x> | cheap × expensive | As many find it cheap as find it expensive |
| PME, point of marginal expensiveness | <x> | <pair> | Above this, more people are on the first curve of the pair than the second (original: too expensive vs not expensive; narrower: too expensive vs cheap): upper end of the range |

**Acceptable price range, original definition** (too cheap × not cheap; too expensive × not expensive):
<low> to <high>
**Acceptable price range, narrower definition** (too cheap × expensive; too expensive × cheap):
<low> to <high>

**By segment** (only with --segment): one row per segment with n, PMC, OPP, IPP, PME.

**Newton-Miller-Smith extension** (only when intent columns exist; weights <list>, <variant> variant,
n = <n>): highest trial at <price> (<trial>%); highest revenue index at <price> (<trial>% trial). When the
script says a highest value is approached just below or above a price, report it that way.

**Conventions:** <curve boundary>; <interpolation and tie rule>; <consistency rule>; <weights>;
<compat preset, if any>.

**Warnings:** <each warning from the script, or "none">

**How to read this:** <2 to 4 sentences: the range to test, where the current or planned price sits in it,
and what a stronger method would add>

Chart: <path to the SVG, if written>
```

Keep prices to two decimals, as the script prints them. A point without a value keeps its row, with the
script's reason ("curves do not cross", "needs the too-cheap question"). With `--bootstrap`, add the interval
after each price.

## Checks before answering

Answer each with yes before sending. If one is no, fix it or say so in the answer.

- Did every number come from the script's output for this file, with nothing recomputed by hand?
- If there was no respondent-level data, did you give the survey and stop, without inventing responses?
- Is the column mapping the script printed correct (too cheap is the lowest question, too expensive the highest)?
- Are the counts of incomplete, out-of-limit and inconsistent respondents in the answer, with excluded or kept?
- Are both ranges given, each labelled with its definition and curve pairs?
- Are the conventions stated, and for a comparison with another tool, were they matched first?
- Is every script warning repeated (small sample, coinciding curves, no crossing, ties, zero prices, zero
  weights, IPP below OPP, a range-width interval reaching zero, reversed intent, a peak next to a tied
  price)?
- If fewer than 100 respondents were analysed, overall or in a segment, is that result called directional?
- Is OPP described as the price where equal shares reject it as too cheap and as too expensive, and not
  as the price fewest people reject, the revenue maximum, the profit maximum or "the right price"? (For
  the share rejecting a candidate price on either ground, use `--at`.)
- If the extension ran, was the intent scale direction confirmed from the codebook, not assumed?
- Does the answer say the method measures price perception, not demand?
- If the extension ran, are the purchase-probability weights stated as an assumption, and is the revenue
  figure called an index based on stated intent?
- Are currency and billing period stated, as confirmed by the user or flagged as unknown?
- If the file mixes segments, does the answer say the pooled result may fit neither segment?
- Does the reading recommend confirming the price with a stronger method (a monadic price test,
  Gabor-Granger or conjoint) before a final decision?
- Was the survey data left unedited, with no answers trimmed without the user's agreement?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `template_lookup` and `template_create_survey_from` (the pricing-research survey), `responses_read` (ids, status, type), `response_get_details` (each response's `van_westendorp` `rawAnswer`; reshape as in [references/sources.md](references/sources.md), "QuestionPunk answers"). Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type and completion status (exclude synthetic and test responses), and reconcile the row count before computing. Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
