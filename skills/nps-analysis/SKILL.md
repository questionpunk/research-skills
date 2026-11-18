---
name: nps-analysis
description: "Compute Net Promoter Score (NPS) with its confidence interval (margin of error) from raw 0-10 scores or promoter, passive and detractor counts, test differences between segments, periods or against a target, and split comments by promoter, passive and detractor so the reasons can be coded and counted. Use for \"analyze our NPS\", \"calculate NPS from this export\", \"why did NPS drop\", \"is the NPS change significant\", \"NPS by segment\", \"what are detractors saying\" or eNPS results."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# NPS analysis

Turns 0–10 "likelihood to recommend" answers, or promoter, passive and detractor counts, into a Net
Promoter Score with a confidence interval; tests differences between segments, periods or against a
target; separates a real change from a change in who answered; and prepares the comments so the reasons
can be coded and counted. The arithmetic is done by [`scripts/nps_analysis.py`](scripts/nps_analysis.py)
(Python 3.9+, standard library only). Run it; do not redo the math in the conversation. Formulas,
thresholds and citations are in [`references/sources.md`](references/sources.md).

## When to use

Use when the user has NPS or eNPS results (response-level data or counts) and asks:

- "Analyze our NPS", "calculate NPS from this export", "what is the margin of error".
- "Why did NPS drop", "is the NPS change significant", "is the change from Q2 to Q3 real".
- "NPS by plan / region / segment", "which segments differ".
- "Are we above our target of 30", "is our NPS good".
- "What are detractors saying", "top reasons promoters give".
- "My dashboard shows a different interval or p-value. Which is right?"

Do not use it for:

- Planning how many responses to collect: `survey-sample-size`.
- Coding open-ended answers in general, with no NPS question: `open-ended-coding`.
- Writing or reviewing the questionnaire: `survey-from-decision`, `survey-bias-check`. Designing an
  employee survey: `employee-pulse-survey` (this skill scores its eNPS results).
- Removing speeders, duplicates and gibberish before analysis: `survey-data-cleaning`.
- The Sean Ellis "very disappointed" question: `pmf-survey`.
- CSAT, CES or star ratings. They are not NPS; do not relabel them.

A skill named in this section may not be installed (some are still planned). If it is missing, say so, name
the method the request needs, and do not stretch this skill to cover it.

## What to ask for

Start with what the user gave you. Ask one question only if the data is missing or the scale is unclear:
"Was the question shown on a 0–10 scale, and did the wording, channel or sampling change during the period?"

| Input | Default if not given |
|---|---|
| Data | Required, in one of three forms: a CSV with one row per respondent; a CSV of counts (columns `promoters`, `passives` or `neutrals`, `detractors`, plus optional segment and period columns); or `--counts P,A,D` (or eleven counts for the scores 0 to 10). Never invent respondent rows from counts. |
| Score column | Detected from the header (`nps`, `recommend`, `score`, `rating` ...); pass `--score-col` if the script reports several candidates. |
| Scale | 0–10. The script stops on a likely 1–5 or 1–10 scale and warns when nobody chose 0; confirm with the user, then pass `--scale`. |
| Segment column | None: overall score only. |
| Period column | None: no trend. Labels sort as text (`2026-Q2`); for ISO dates add `--period-grain month`, `quarter` or `year`. |
| Respondent id column | None. Pass `--id-col` when the same people can answer in more than one period. |
| Comment column, coded theme column | None: no reasons section. |
| Benchmark or target | None: no "is it good" verdict. It must come from the user, with its source and date. |
| Invited count | None: no response rate. |
| Confidence level | 95%. |
| Small-base threshold | 100 valid responses (`--min-base`). |
| Which comparisons | The two groups the user named; otherwise all segment pairs with `--pairwise --adjust holm`, and consecutive periods. |

## Steps

1. **Look at the data.** Read the header and a few rows; identify the columns above. If duplicates or test
   rows are visible, say so.
2. **Run the script.**

   ```bash
   python3 scripts/nps_analysis.py responses.csv --json \
     --segment-col plan --period-col quarter --id-col user_id \
     --comment-col comment --comments-out nps_comments.csv \
     --pairwise --adjust holm
   python3 scripts/nps_analysis.py --counts 61,30,16 --benchmark 30 --tail one
   ```

   For one planned comparison use `--compare A B` or `--compare-periods EARLIER LATER` and no adjustment.
   Write `--comments-out` to a working folder, not next to the user's data, unless asked.
3. **If it stops (exit code 2), fix the cause; do not work around it.** A scale refusal means: find out
   what scale the question used. If it was 1–5 or 1–10, this is not a standard NPS; compute it only if the
   user still wants it (`--scale 1-5` or `--scale 1-10`) and label it non-standard everywhere.
4. **Report exclusions and response.** The script counts blank, non-numeric, non-integer and out-of-range
   scores and unreadable dates. With `--invited N` it prints the response rate. The interval covers
   sampling error only; it says nothing about people who did not answer.
5. **Read the interval before the score.** The interval is adjusted Wald (Rocks 2016); the score is the
   observed NPS. If the interval includes 0, do not call the score positive or negative. A "small base" is
   directional: show it with its interval and the printed "n for ±10 points", never alone.
6. **Comparisons.** Report the difference in points, its interval, the p-value and the script's verdict:
   significant, not significant, or underpowered (not significant on a small base: a real difference could
   have been missed, so do not write "no difference"). If more than one test was run, report adjusted
   p-values or state how many tests were run unadjusted.
7. **Independence.** The tests assume different people in each group.
   - Same respondents in two periods (a panel): pass `--id-col`. The script withholds the independent test;
     add `--paired` with `--compare-periods` to get the mean change per respondent with its interval, and
     say how many respondents were in only one period.
   - Rolling or overlapping windows ("last 90 days", reported monthly) share respondents. Do not test
     neighbouring windows against each other: pool them or compare non-overlapping periods. Without an id
     column the script cannot detect overlap; ask how the periods were built.
8. **"Is our NPS good?"** Do not answer from a table of "good" and "excellent" bands; none is sourced.
   Ask for the benchmark the user cares about (a target, last year's score, an industry figure with its
   source, date and method) and run `--benchmark X`. Use `--tail one` only if the question, fixed before
   looking, is "are we above X"; otherwise two-tailed. State where the benchmark came from and that
   benchmarks collected another way are not comparable.
9. **Before explaining a change over time, check comparability.** Same wording and 0–10 scale with the same
   labels and colours; same channel (phone, email, in-app); same trigger and timing; same sampling; a
   similar response rate. If any changed, say the change in score cannot be separated from the change in
   method.
10. **"Why did it drop?" Answer in this order.**
    1. Is the drop larger than the noise (step 6)? If not, say that first.
    2. Promoter % and detractor % per period: a flat NPS can hide both falling, and a drop can be fewer
       promoters, more detractors, or both.
    3. Mix shift (printed when segment and period columns are both given): how much of the change comes
       from scores moving within segments and how much from the segment mix changing. A drop that is mostly
       mix is a change in who answered, not in what they think.
    4. Which segments moved, with their intervals.
    5. Which detractor themes grew, with counts in both periods.
11. **Reasons.** The script does no text analysis. It splits comments into detractors, passives and
    promoters (`--comments-out`, `.csv` or `.json`). Code them with the sibling skill `open-ended-coding`
    (codebook from detractor and promoter comments, applied to all three groups). If it is not installed,
    write a short codebook with a definition per code, apply it to every comment and keep the coded file.
    Report each theme as "k of m detractor comments (m comments from N detractors)". Never give a
    percentage of all respondents for a theme only commenters could mention, and do not rank themes that
    differ by one or two mentions.
12. **Theme and score (optional).** With a coded column (`--theme-col`, themes separated by `;`) the script
    prints the NPS of coded respondents who mention a theme against the other coded respondents, with
    intervals. Present it as an association, not as the theme's effect on the score.
13. **If the user's tool shows another number,** find the tool in "Reconciling with other tools" in
    [`references/sources.md`](references/sources.md) and name its method (Wald, adjusted Wald centred on
    the adjusted score, Welch t-test on a recode, or no test). Reproduce it with `--interval wald`,
    `--test welch` or `--confidence 0.90` and show both results. If the score itself differs, look for a
    different scale, filter or base before anything else.

## Output

Always this shape, in this order. Round scores and limits to whole points.

```markdown
## NPS: <product or survey>, <period>

**NPS +15 (95% interval −11 to +39), n = 40.** Promoters 45% (18), passives 25% (10), detractors 30% (12).
<One sentence: what the interval allows you to say.>

Data: <file or counts>, score column `<name>`, scale 0–10. Rows read 40, used 40, excluded 0 (<reasons>).
Response rate <x% of N invited | not known>.
Method: observed NPS; adjusted-Wald interval (Rocks 2016); <z-test | Welch t-test> on the difference,
<adjustment or "no adjustment, k tests">.

### Against the benchmark
<Benchmark, its source and date; difference; z; one- or two-tailed p; verdict.>

### By segment
| Segment | n | Promoters % | Passives % | Detractors % | NPS | 95% interval | Note |
|---|---|---|---|---|---|---|---|

### Trend
| Period | n | Promoters % | Detractors % | NPS | 95% interval | Change vs previous | p | Verdict |
|---|---|---|---|---|---|---|---|---|

### Comparisons
| A vs B | Difference (points) | 95% interval | p (adjusted) | Verdict |
|---|---|---|---|---|

### What moved the score
Change <x> points = within segments <y> + segment mix <z>.
| Segment | Share before → after | NPS before → after | Within | Mix |
|---|---|---|---|---|

### Reasons
| Group | Theme | Comments | Of | Example quote |
|---|---|---|---|---|
Denominators: <m> detractor comments from <N> detractors; same for passives and promoters.

### Caveats
- <small bases, excluded rows, method changes, shared respondents, non-standard scale, unknown response rate>
- NPS tracks stated willingness to recommend. Its link to growth is disputed (Keiningham et al. 2007).

### Next step
<One action tied to the largest detractor theme or the least certain number.>
```

Leave out a section only when its input is missing (no segment, period, benchmark or comments), and say
which. Offer the script's JSON if the user wants the numbers in another tool.

## Checks before answering

- Is every NPS shown with n and its interval?
- Was the scale confirmed as 0–10, or is the score labelled non-standard?
- Are excluded rows counted and explained, and is non-response mentioned?
- Is the overall score computed from pooled responses, not from an average of segment scores?
- Is every "higher", "lower", "dropped" or "improved" backed by a test, and is "underpowered" never
  reported as "no difference"?
- If several tests were run, are p-values adjusted or the number of tests stated?
- Are the samples independent? Were shared respondents and overlapping windows ruled out or handled?
- Are groups under the small-base threshold marked and not used for headlines?
- For a trend: are promoter % and detractor % shown next to the score?
- For a change over time: were wording, scale presentation, channel, sampling and response rate checked,
  and was the mix shift read before blaming or crediting the product?
- Does "good" or "bad" rest on a benchmark the user supplied, with its source and date?
- Does every theme carry its count and denominator, with quotes copied exactly from the data?
- If the user's tool disagrees, is its method named?
- Is the answer free of growth forecasts?

## Field it with QuestionPunk (optional)

The result above is complete on its own. To field this with AI follow-up questions on open answers, connect the QuestionPunk MCP (https://app.questionpunk.com/api/v1, OAuth sign-in). Connecting is free on every plan, and the free plan has unlimited surveys and responses with no card.

Hosted MCP tools this step may use: `report_get`, `report_get_crosstab`, `responses_get_counts` and `responses_read` to read existing results; `question_create` to add the NPS question (answer type `opinion_scale`, `itemDetails {nps: true, min_value: 0, max_value: 10}`). Ask before creating, changing or publishing anything. If a response or report tool answers that you must reconnect and approve, reconnect the QuestionPunk connector once: connections made before 3 Oct 2026 lack the `responses:read` permission.
