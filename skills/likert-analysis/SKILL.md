---
name: likert-analysis
description: "Analyzes Likert and other rating-scale items from a CSV: full distributions, top-2 and bottom-2 box with Wilson intervals, medians and means with guidance on which to lead with, a diverging stacked bar table, reverse-coded item detection, Cronbach's alpha with a Feldt interval and alpha-if-item-deleted, and group comparisons (Mann-Whitney per item, box differences, Welch t on the scale score). Use for \"analyze Likert data\", \"agree/disagree results\", \"satisfaction scale results\", \"Cronbach's alpha\", \"is my scale reliable\", \"top-2-box\" or \"how should I report a 5-point scale\"."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# Likert analysis

Turns agree/disagree and other rating-scale items into distributions, top and bottom boxes with intervals,
medians and means, a diverging bar table, a reliability check for multi-item scales, and group comparisons.
The arithmetic is done by [`scripts/likert_analysis.py`](scripts/likert_analysis.py) (Python 3.9+, standard
library only); do not compute alpha or rank tests in the conversation. Formulas, conventions and citations:
[`references/sources.md`](references/sources.md).

## When to use

- "Analyze these Likert / agree-disagree / satisfaction items", "summarize this matrix question".
- "Top-2-box for each statement", "how should I report a 5-point scale", "mean or median?".
- "Is my scale reliable", "Cronbach's alpha", "which item should I drop", "is item 3 reverse-coded?".
- "Do managers and staff answer differently", "compare teams on these items".
- Employee, course-evaluation, attitude and opinion batteries.

Do not use it for:

| Request | Use instead |
|---|---|
| One overall CSAT or CES question, Zendesk ratings | `csat-ces-analysis` |
| 0-10 likelihood to recommend | `nps-analysis` |
| SUS, UMUX-Lite, SEQ, NASA-TLX | `ux-scale-scoring` (published scoring and benchmarks) |
| Factor analysis, building a new validated scale | Not this skill (needs a psychometrics package) |
| Banner tables across many questions | `survey-crosstabs` |
| Weighting to population totals first | `survey-weighting` |
| The same people measured twice (before/after, two conditions) | Not this skill: its tests assume independent groups |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and do
not stretch this skill to cover it.

## What to ask for

Ask what changes the analysis, in one message: "What is the answer scale, with both end labels? Do these
items form one scale (meant to be summed), and are any worded negatively? If you compare groups, are they
different people, or the same people asked twice?" The scale cannot be read from the answers (if nobody chose
an end point the scale looks shorter), and the group tests are only for different people.

| Input | Default if not given |
|---|---|
| Data | CSV, one row per respondent, one column per item (any delimiter, UTF-8 or UTF-16, Qualtrics header detected). |
| Items | Required: `--items q1,q2,...` or `--items-prefix engage_`. |
| Scale | `--scale MIN-MAX` from the questionnaire; numeric answers stop without it. Text labels set it through a printed built-in map and stop when they fit more than one scale; `--labels` sets it from its lowest and highest points. Labelled numbers ("1 - Strongly disagree" ... "5 - Strongly agree") set it from the lowest and highest labelled codes when both labels read as end points (very, extremely, strongly, completely, not at all) and no plain number falls outside them; the scale line says so, and otherwise the script stops. If the questionnaire had more points than anyone chose, pass `--scale`. |
| Text answers | Read with a printed label map (agree 4/5/7-point, satisfied 5/7-point, frequency, importance); `--labels "Low=1,Mid=2,High=3"` for others. |
| Bipolar or unipolar | Agree and satisfied labels are bipolar (middle = neutral); frequency and importance are unipolar (middle is not neutral). For numbers, pass `--unipolar` when the scale runs from none to a lot. |
| Box width | Top-2 / bottom-2 on 4+ point scales; `--box 3` for top-3 on a 7-point scale. |
| Scale or separate items | Separate items. `--alpha` (all items) or `--scale-items COL,...` (a subset of two or more) when they form one scale. |
| Reverse-worded items | None; `--reverse COL,...` recodes as min + max − x in the reliability check and scale score only; item results stay as answered. |
| Group column | None; `--group-col COL` with `--compare A B` or `--pairwise --adjust holm` (blank groups are left out of `--pairwise`). |
| Confidence, small base | 95%; 100 answers (`--min-base`). |

## Steps

1. **Look at the file.** Header and a few rows: which columns are the items, how answers are written
   (numbers, "4 - Agree", "Agree"), the group column, and whether "N/A" or "Don't know" appear (they are
   excluded and counted, never scored as the midpoint).
2. **Run the script** by its path inside this skill's folder (`<skill-dir>` below), keeping input and output
   paths relative to the user's project. Check it first on the shipped fixture, which should print
   `Cronbach's alpha 0.882`:

   ```bash
   python3 <skill-dir>/scripts/likert_analysis.py <skill-dir>/fixtures/engagement.input.csv \
     --items-prefix eng_ --scale 1-5 --alpha --reverse eng_3
   python3 <skill-dir>/scripts/likert_analysis.py survey.csv --items-prefix q_ --scale 1-5 --json
   python3 <skill-dir>/scripts/likert_analysis.py survey.csv --items-prefix eng_ --scale 1-5 --alpha \
     --reverse eng_3 --group-col team --pairwise --adjust holm --table-out work/likert_table.csv --json
   python3 <skill-dir>/scripts/likert_analysis.py survey.csv --items q1,q2,q3 --unipolar \
     --labels "Not at all=1,A little=2,Somewhat=3,Quite a bit=4,Very much=5"
   ```

   Use `--json` for group comparisons: it carries every group's per-item summaries and intervals.

3. **If it exits with code 2, fix the cause.** It stops when more than 5% of non-blank answers cannot be read
   on the scale, overall or in any one item (unknown labels, wrong scale, a text column among the items),
   when numeric answers come with no `--scale` (labelled numbers without end-point labels at both ends
   count as numeric), when text labels fit more than one scale, on duplicate
   columns and on ragged rows. Ask for the scale or fix the label map; use `--allow-unreadable` only for
   genuinely unusable answers, and report how many.
4. **Check the convention lines:** items, scale and its source, bipolar or unipolar, label map, box points,
   reversed items, excluded answers by reason.
5. **Describe each item by its distribution first.** Lead with the top box (and bottom box) with its
   interval and the diverging bar; give the median; give the mean as a secondary summary. A single item is
   ordinal, so do not rank items by mean alone: two items with mean 3.0 can be one polarised and one
   neutral.
6. **Multi-item scale (`--alpha`).**
   - Read the corrected item-total correlations first. A negative one means the item runs against the rest:
     check its wording. If it is negatively worded, rerun with `--reverse`. Never reverse an item only
     because alpha improves.
   - Report alpha with its Feldt interval and n of complete respondents. 0.70 is a convention, not a pass
     mark; above about 0.95 can mean redundant items. Alpha does not show the items measure one thing.
   - "Which item should I drop?" Show alpha-if-item-deleted together with the item's wording and purpose.
     Dropping changes what the scale measures; it is the user's call.
   - For the scale score (mean of items), the mean and t interval are appropriate.
7. **Group comparisons** (different people in each group only). Per item: Mann-Whitney U (exact when both
   groups have under 50 answers; R's default uses the normal approximation on ties, so pass
   `--mw-method normal` to match R), the probability of superiority with half credit for ties as the effect
   size, and the top-box difference with its interval and its own test. For the scale score: Welch t on the
   mean. `--adjust holm` covers every one of those tests. Exact tests on many 7- to 11-point items with
   groups of 30 to 49 can take minutes; `--mw-method normal` is the fast approximation. Report verdicts,
   significant or not significant; on a small base read the interval, and never write "no difference".
8. **Chart.** `--table-out` writes the diverging table (percent per point, below/at/above the midpoint, top
   box, median, mean; unreadable items as empty rows) for any charting tool. On a bipolar scale centre the
   bars on the neutral point and show the neutral share; on a unipolar scale use plain stacked bars.

## Output

```markdown
## <Survey>: <battery name>, n = <respondents>

Scale 1-5 (Strongly disagree to Strongly agree, read from labels); top box = 4-5. Rows 40; answers excluded 2
(blank 1, N/A 1). Reversed in the scale score only: eng_3 ("I often think about quitting"); its row shows
agreement with that wording.

| Item | n | Disagree (1-2) | Neutral | Agree (4-5) | 95% CI (agree) | Median | Mean |
|---|---|---|---|---|---|---|---|
| eng_1 I feel valued | 39 | 12.8% | 43.6% | 43.6% | 29.3-59.0 | 3 | 3.33 |

### Scale reliability
Cronbach's alpha 0.88 (95% Feldt CI 0.81 to 0.93), 4 items, 38 complete respondents.
| Item | Corrected item-total r | Alpha if deleted |
|---|---|---|
Scale score (mean of items): 3.22 (2.92 to 3.51).

### By group
| Item | North agree % | South agree % | Difference (95% CI) | Mann-Whitney p (Holm) | P(N > S) + ½P(N = S) | Verdict |
|---|---|---|---|---|---|---|

### Caveats
- <small bases; excluded answers; reversed items and why; alpha's limits; labels mapped by the script>
```

On a 7-point scale the top box (6-7, with its interval) is not the whole positive side (5-7, in the
diverging columns): label which one a column shows. Lead the narrative with the items that moved most or
have the most disagreement, with their intervals.
Leave out a section when its input is missing.

## Common mistakes

- Treating "N/A" or "Don't know" as the midpoint.
- Ranking items by mean while ignoring polarised distributions.
- Computing alpha before recoding reverse-worded items, or reversing an item to raise alpha.
- Reporting alpha above 0.70 as proof of validity, or alpha for items that measure different things.
- t-tests on single items with many items and no adjustment; reporting the one that happened to cross 0.05.
- Comparing a 5-point and a 7-point version of an item by mean.

## Checks before answering

- Are scale, label map, box points and reversed items stated, and was the map checked against the
  questionnaire?
- Does every item show n, the distribution or the box shares with intervals, and the median?
- Were non-answers excluded and counted rather than scored?
- For a scale: are reverse-worded items recoded, alpha shown with its interval and complete n, and item
  drops left to the user?
- Are the groups different people, and are group differences backed by tests, adjusted for every test run,
  with small bases read through their intervals?
- Were all numbers copied from the script output?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `question_create` (a Likert grid as a `matrix` question with `textItemDetails {rows: [statements], columns: [the labels, lowest first]}`; one item as an `opinion_scale` with explicit `itemDetails {min_value: 1, max_value: 5}`, since it defaults to 1-10; a 4-point item as labelled choices); `responses_get_counts` (totals); `responses_read` (rows for this script). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.

Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type and completion status (`responseType: "real"`, `status: "completed"`; exclude synthetic and test responses), and reconcile the row count with `responses_get_counts` under the same filters before computing. Answers come keyed by question id, and matrix answers as "Row: label" strings: write one row per response and one column per statement to a CSV, then pass `--scale` and the label map.
