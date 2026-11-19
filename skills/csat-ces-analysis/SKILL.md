---
name: csat-ces-analysis
description: "Computes CSAT and Customer Effort Score (CES) from ratings or counts: the top-2-box share with a Wilson interval and the mean, CES on the 7-point agree or ease scale or the original 1-5 effort scale (lower is better), with the convention printed so numbers reconcile with Zendesk or Qualtrics; tests differences between agents, channels, segments or periods and against a target; and splits comments by satisfied, neutral and dissatisfied. Use for \"calculate CSAT\", \"CSAT from this export\", \"customer effort score\", \"CES results\", \"is our CSAT drop significant\" or post-ticket surveys."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# CSAT and CES analysis

Turns satisfaction (CSAT) or customer effort (CES) ratings into a share with a confidence interval and a mean,
compares agents, channels, segments or periods, tests against a target, and splits comments by satisfied,
neutral and dissatisfied so the reasons can be coded. The arithmetic is done by
[`scripts/csat_ces_analysis.py`](scripts/csat_ces_analysis.py) (Python 3.9+, standard library only); do not
redo the math in the conversation. Formulas, tool conventions and citations:
[`references/sources.md`](references/sources.md).

There is no single CSAT formula. Every number this skill reports carries its convention (scale, which points
count as satisfied, interval method), so it can be reconciled with Zendesk or Qualtrics.

## When to use

- "Calculate CSAT from this export", "what's our CSAT", "CSAT by agent / channel / team".
- "Customer effort score", "CES results", "how easy do customers find support".
- "Is our CSAT drop significant", "did October beat September", "are we above our 85% target".
- Post-ticket, post-chat, post-call or post-interaction survey ratings; Zendesk good/bad ratings.
- "Zendesk shows a different number than my spreadsheet."

Do not use it for:

| Request | Use instead |
|---|---|
| 0-10 "how likely to recommend" | `nps-analysis` (never relabel NPS as CSAT or the reverse) |
| Several agree/disagree items, a multi-item scale, Cronbach's alpha | `likert-analysis` |
| SUS, UMUX-Lite, SEQ after a usability test | `ux-scale-scoring` |
| Coding the comments into themes | `open-ended-coding` (this skill only splits them) |
| Speeders, duplicates, test rows | `survey-data-cleaning` first |
| How many responses to collect | `survey-sample-size` |
| Weighting to a population, banner tables | `survey-weighting`, `survey-crosstabs` |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and do
not stretch this skill to cover it.

## What to ask for

Start from what the user gave you. Ask one question when the scale or metric is not in the file or the
questionnaire: "What was the exact question and its scale, both end labels included (for example 1 = very
dissatisfied to 5 = very satisfied)?" The scale cannot be read from the answers: if nobody chose an end point,
a 7-point question looks like a 5-point one.

| Input | Default if not given |
|---|---|
| Data | A CSV with one row per answer (any delimiter, UTF-8 or UTF-16, Qualtrics 3-row header detected), or `--counts` per scale point, lowest first. Never invent rows from a percentage. |
| Metric | `csat`. `ces` for the 7-point "made it easy" agree or ease item (higher = easier); `ces5` for the original 1-5 "how much effort" item (lower = better). |
| Rating column | Detected by name (`csat`, `satisfaction`, `effort`, `rating`, `score` ...); `--score-col` if several match. |
| Scale | `--scale MIN-MAX` from the questionnaire; numeric CSAT stops without it. Text labels ("Very satisfied", "Strongly agree", "Good, I'm satisfied") set it through a printed built-in map, and stop when they fit more than one scale; `--labels` sets it from its lowest and highest points. Labelled numbers ("1 - Very dissatisfied" ... "5 - Very satisfied") set it from the lowest and highest labelled codes when both labels read as end points (very, extremely, strongly, completely, not at all) and no plain number falls outside them; the scale line says so, and otherwise the script stops. If the questionnaire had more points than anyone chose, pass `--scale`. CES is 1-7 and CES 1.0 is 1-5 unless `--scale` says otherwise. |
| Satisfied band | Top-2 box (4-5 on 1-5, 6-7 on 1-7, 9-10 on 0-10); top-1 on 2-4 point scales; CES top 3 of 7 (5-7); CES 1.0 low effort 1-2. Points outside both boxes are "neutral" only when they are the single midpoint, otherwise "middle". Override with `--positive` / `--negative`. |
| Segment, period, comment, customer id columns | None. |
| Target | None: no "is it good" verdict. `--target` (share, 85 or 0.85) or `--target-mean` must come from the user with its source. |
| Confidence, small base | 95%; 100 answers (`--min-base`). |

## Steps

1. **Look at the file.** Header and a few rows: the rating column, how answers are written, segment and date
   columns, comments, customer or ticket ids. Note visible test rows.
2. **Run the script** by its path inside this skill's folder (`<skill-dir>` below), keeping input and output
   paths relative to the user's project. Check it first on the shipped fixture, which should print
   `satisfied 75.0% (59.8% to 85.8%)` on n = 40:

   ```bash
   python3 <skill-dir>/scripts/csat_ces_analysis.py <skill-dir>/fixtures/basic.input.csv --scale 1-5
   python3 <skill-dir>/scripts/csat_ces_analysis.py ratings.csv --scale 1-5 --json \
     --segment-col agent --period-col month --id-col customer_id \
     --comment-col comment --comments-out work/csat_comments.csv \
     --pairwise --adjust holm
   python3 <skill-dir>/scripts/csat_ces_analysis.py ces.csv --metric ces --segment-col channel --compare chat phone
   python3 <skill-dir>/scripts/csat_ces_analysis.py --counts 4,6,10,40,40 --target 85 --tail below
   ```

   Periods must sort as time (`2026-09`, `2026-Q3`, `wave2`) or be given with `--period-order`. Consecutive
   periods are tested automatically; `--compare-periods EARLIER LATER` tests one pair. Rows with no period
   stay in the overall result and out of the trend. Write `--comments-out` to a working folder; the script
   refuses to overwrite its input.
3. **If it exits with code 2, fix the cause, not the data.** It stops when more than 5% of non-blank answers
   cannot be read on the scale (wrong column, wrong scale, unknown text labels), when it has no scale for
   numeric answers, when text labels fit more than one scale, on duplicate column names, ragged rows and an
   unreadable encoding. Ask for the scale and pass `--scale`, or map unknown labels with
   `--labels "Unhappy=1,Okay=2,Happy=3"`; `--allow-unreadable` only when those rows really are junk, and say
   how many were dropped.
4. **Check the convention lines** at the top of the output: metric, scale and where it came from, satisfied
   and dissatisfied points, label map, rows used and excluded by reason. If it warns that nobody chose an end
   point, confirm the scale against the questionnaire before reporting.
5. **Read the interval before the share.** Report the share with n and its Wilson interval. Under the small
   base, call it directional. Agent-level CSAT on 20 tickets has an interval about 33 points wide; do not
   rank agents on it.
6. **Comparisons.** Report the difference in points, its Newcombe interval, the test used (z, or Fisher exact
   when expected counts are small), the p-value and the verdict, significant or not significant. With
   `--adjust`, segment comparisons and period comparisons are adjusted as two separate families; the output
   names the family and its size, and every other p-value (Welch, target) is raw. A result that is not
   significant is never "no difference": say what the interval allows (on a small base it is wide).
7. **Independence.** The tests assume one answer per independent customer. `--id-col` checks repeats of
   whatever that column holds, and the output names the column: ticket or case ids are unique per ticket, so
   they cannot catch a customer who answered on several tickets (the script notes this when the column name
   looks like a ticket id). Use a customer id for this check. If it shows repeat answers or the same
   customers in two periods, say the p-values are approximate; for a large share of repeats, keep one answer per customer (ask which) and rerun. The same
   holds for a panel surveyed in both periods: ask whether the waves are the same people.
8. **"Is our CSAT good?"** Ask for the target or benchmark, its source and how it was collected, then run
   `--target X` (one-tailed `--tail above` or `below` only if that direction was the question before
   looking; for CES 1.0 lower is better). A fixed goal is a target; last year's score is an estimate with its
   own error, so compare the two waves with `--period-col` instead. Do not quote "good CSAT is 75-85%"
   tables: none has a stated method.
9. **"Why did it drop?"** In order: is the drop larger than the noise (step 6); did dissatisfied rise or
   satisfied fall (both shares are printed); did the mix of channels or agents change (with both
   `--segment-col` and `--period-col` the script prints each segment's share of every period and its
   satisfaction there); did the survey change (wording, scale, trigger, channel, response rate). Then the
   comments.
10. **Comments.** The script splits them (`--comments-out`, `.csv` or `.json`) and counts commenters per
    group, with the distinct values of `--id-col` when given (customers only if it holds customer ids). Code
    them with `open-ended-coding`; if it is not installed, write a short codebook with a definition per code,
    apply it to every comment and keep the coded file. Report a theme as "k of m dissatisfied comments (from N
    dissatisfied answers, C customers)", giving C only from a customer id column.
11. **If another tool shows a different number,** match the convention first (see "Tool conventions" in
    [`references/sources.md`](references/sources.md)): Zendesk counts 1-3 as bad on a 5-point scale, but its
    percentage good equals the top-2-box share here; a dashboard mean is not a share; a 60-day rolling
    window is not a calendar month.

## Output

Use this shape and order. Shares to one decimal, means to two.

```markdown
## CSAT: <survey or queue>, <period>

**CSAT 75.0% satisfied (95% CI 59.8% to 85.8%), n = 40** [small base]. Neutral 10.0%, dissatisfied 15.0%.
Mean 3.88 on 1-5 (3.49 to 4.26).
<One sentence on what the interval allows you to say.>

Convention: "<question wording>", scale 1-5 (<from the questionnaire | labels>), satisfied = 4-5 (top-2 box), base = all
valid answers. Rows read 42, used 40, excluded 2 (blank 1, N/A 1). Response rate <x% | not known>.
Method: Wilson score intervals; Newcombe intervals for differences; <z | Fisher exact> tests; <adjustment>.

### By <agent | channel | segment>
| Segment | n | Satisfied % | 95% CI | Dissatisfied % | Mean | Note |
|---|---|---|---|---|---|---|

### Trend
| Period | n | Satisfied % | 95% CI | Change vs previous (points) | 95% CI of change | p (adjusted) | Verdict |
|---|---|---|---|---|---|---|---|

### Comparisons
| A vs B | Difference (points) | 95% CI | Test | p (adjusted) | Verdict |
|---|---|---|---|---|---|

### Against the target
<Target, its source; share vs target; tail; p; verdict.>

### Reasons
| Group | Theme | Comments | Of | Example quote |
|---|---|---|---|---|

### Caveats
- <small bases, repeat customers, excluded rows, scale or wording changes, response rate>

### Next step
<One action tied to the largest dissatisfied theme or the least certain number.>
```

For CES, title it "CES", name the version and rename the columns (Easy %, Difficult %): "CES (7-point,
'made it easy', higher = easier): 56.7% easy (95% CI 39.2% to 72.6%), n = 30". For CES 1.0 the mean is the
headline: "CES 1.0 (1-5 effort, lower = better): mean 2.65 (95% CI 2.40 to 2.90), n = 100", with the
low-effort share (1-2) as this skill's secondary convention. Leave out a section only when its input is
missing.

## Common mistakes

- Averaging agent or channel scores to get the overall. The overall is pooled over answers.
- Comparing a 5-point CSAT with a 7- or 10-point one, a share with a mean, or CES 1.0 with CES 2.0 (they run
  in opposite directions).
- Calling a 3-point change "a drop" with no test, or "no difference" when it is not significant.
- Ranking agents with 10 to 30 ratings each.
- Testing many pairs and reporting the smallest raw p-value.
- Treating the share of satisfied commenters as the share of satisfied customers.

## Checks before answering

- Is every share shown with n and its interval, and is the scale and satisfied band stated?
- Was the scale taken from the questionnaire, and any text-label map printed and checked against it?
- Are excluded rows counted by reason, and is the response rate (or that it is unknown) stated?
- Is every "up", "down" or "better" backed by a comparison with a verdict, adjusted if several were run?
- Are small bases marked and kept out of headlines?
- Were repeat customers and overlapping periods checked?
- Does "good" rest on a target the user supplied, with its source?
- Does every theme count carry its denominator, with quotes copied exactly?
- If another tool disagrees, is the convention difference named?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `question_create` (the rating: `opinion_scale` with `itemDetails {min_value: 1, max_value: 5}` for CSAT, `max_value: 7` for CES, `max_value: 5` for CES 1.0, end labels in `textItemDetails`); `responses_get_counts` and `report_get` (totals); `responses_read` (rows for this script). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.

Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type and completion status (`responseType: "real"`, `status: "completed"`; exclude synthetic and test responses), and reconcile the row count before computing: give `responses_get_counts` and `report_get` the same filters. Use `answerFormat: "numeric"` and write one row per response, one column per question id (plus any segment and date columns) to a CSV, then pass `--scale` with the question's `min_value` and `max_value`.
