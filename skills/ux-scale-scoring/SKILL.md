---
name: ux-scale-scoring
description: "Scores standard usability questionnaires from a CSV: SUS (0-100, standard or all-positive wording, with checks for miscoded data), UMUX-Lite (raw, read on the SUS grades, plus the historical SUS-equivalent), SEQ and raw NASA-TLX, with confidence intervals, the SUS curved grade, percentile and adjective from published benchmarks, and tests of two designs (independent or paired) or against a target such as 68. Use for \"SUS score\", \"System Usability Scale results\", \"calculate SUS\", \"UMUX-Lite\", \"single ease question\", \"NASA-TLX\", \"usability questionnaire results\" or \"is our SUS above average\"."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# UX scale scoring

Scores the standard post-test and post-task usability questionnaires correctly, with intervals, published
benchmarks and the right test for the study design. The arithmetic is done by
[`scripts/ux_scale_scoring.py`](scripts/ux_scale_scoring.py) (Python 3.9+, standard library only); do not
score by hand in the conversation, where the alternating SUS items are the usual source of errors. Formulas, benchmarks and citations:
[`references/sources.md`](references/sources.md).

| Instrument | `--instrument` | Answers | Score |
|---|---|---|---|
| System Usability Scale, alternating wording | `sus` | 10 items, 1-5 | 0-100, average 68 |
| SUS, all-positive wording | `sus-positive` | 10 items, 1-5 | 0-100 |
| UMUX-Lite | `umux-lite` | 2 items, 1-7 | 0-100, read on the SUS grades; regression SUS-equivalent secondary |
| Single Ease Question | `seq` | 1 item after each task, 1-7 | mean, 1-7 |
| Raw NASA-TLX | `tlx` | 6 subscales, 0-100 | 0-100, lower is better |

## When to use

- "Calculate our SUS", "SUS score from this export", "System Usability Scale results".
- "Is our SUS above average / above 68", "what grade is a 72", "how does this compare to benchmarks".
- "Did the redesign improve SUS", "compare SUS for design A and B", "SEQ by task".
- "UMUX-Lite score", "convert UMUX-Lite to SUS", "NASA-TLX workload".

Do not use it for:

| Request | Use instead |
|---|---|
| A home-grown agree/disagree battery, Cronbach's alpha | `likert-analysis` |
| CSAT, CES or NPS after a test | `csat-ces-analysis`, `nps-analysis` |
| How many participants to test | `survey-sample-size` |
| SUPR-Q or other licensed instruments | Not this skill: their norms are licensed |
| Task success, time on task, observed problems | Not this skill |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and do
not stretch this skill to cover it.

## What to ask for

Ask only what changes the scoring, in one message, when the file does not say: "Were all ten SUS items worded
positively, or did they alternate? Did the same people rate both designs? For SEQ, which end was 'very
easy'?" SUS is given once after the test, SEQ after each task. The ten SUS items in order are Brooke's
(1996): 1 use frequently, 2 unnecessarily complex, 3 easy to use, 4 need technical support, 5 well
integrated, 6 too much inconsistency, 7 learn quickly, 8 cumbersome, 9 confident, 10 needed to learn a lot;
check the export's column order against them.

| Input | Default if not given |
|---|---|
| Data | CSV, one row per participant (per participant and design in a within-subjects study), one column per item. Any delimiter, UTF-8 or UTF-16, Qualtrics header detected. |
| Instrument | Required (`--instrument`). |
| Item columns | Detected: SUS columns numbered 1 to 10 (`SUS1`, `sus_10`, `Q5_1` ... `Q5_10`); UMUX-Lite by "capabilities" and "easy"; TLX by subscale names. Otherwise `--items` in questionnaire order. |
| Scale | Fixed by the instrument: SUS 1-5 (nothing else is the SUS); UMUX-Lite and SEQ 1-7 (`--scale 1-5` for a 5-point UMUX-Lite); TLX 0-100 (`--scale 1-21` for the paper form). Text labels ("Strongly agree") are read with the printed map of that scale only. |
| Design or task column, participant id | None. With both and the same people rating each design, use `--paired`. |
| Target | None. For "above average" on SUS, 68 with `--tail above`. |
| Direction of a comparison | Two-sided. A one-sided question fixed before the data ("is the new design better?") is `--compare NEW OLD --tail above` (A minus B); not with `--pairwise`, and run a one-sided `--target` separately. |
| Skipped SUS items | Participant excluded and counted. `--impute-midpoint` scores one skipped item as 3 (`--max-imputed` to allow more, with the user's agreement) and prints the complete-case result beside it: overall, per group and for each comparison. |
| Confidence, small base | 95%; 12 participants (`--min-base`, this skill's reporting convention). |

## Steps

1. **Look at the file.** Header and a few rows: the item columns and their order, the answer scale, design
   or task and participant columns. Check the questionnaire wording if you have it: alternating or
   all-positive SUS, which UMUX-Lite item is which, how TLX performance was anchored.
2. **Run the script** by its path inside this skill's folder (`<skill-dir>` below), keeping input and output
   paths relative to the user's project. Check it first on Brooke's published example, which should print
   `mean 55.0` and grade D:

   ```bash
   python3 <skill-dir>/scripts/ux_scale_scoring.py <skill-dir>/fixtures/brooke_1996.input.csv --instrument sus
   python3 <skill-dir>/scripts/ux_scale_scoring.py sus.csv --instrument sus --json
   python3 <skill-dir>/scripts/ux_scale_scoring.py sus.csv --instrument sus --group-col design --compare old new \
     --paired --id-col participant
   python3 <skill-dir>/scripts/ux_scale_scoring.py sus.csv --instrument sus --target 68 --tail above
   python3 <skill-dir>/scripts/ux_scale_scoring.py sus.csv --instrument sus --group-col design --compare new old \
     --tail above
   python3 <skill-dir>/scripts/ux_scale_scoring.py umux.csv --instrument umux-lite --items capabilities,ease
   python3 <skill-dir>/scripts/ux_scale_scoring.py seq.csv --instrument seq --group-col task --pairwise --adjust holm
   python3 <skill-dir>/scripts/ux_scale_scoring.py tlx.csv --instrument tlx --scale 1-21 --group-col condition \
     --compare A B
   ```

   `--scores-out work/scores.csv` writes one score per participant (the folder is created; the input is never
   overwritten).
3. **If it exits with code 2, fix the cause.** It stops when more than 5% of item answers are off the scale
   (often a 7-point "SUS", which it refuses to score as SUS), when text labels do not fit the instrument's
   scale, when labelled SEQ answers put "easy" at 1 (ask, then `--seq-reversed`), when it cannot find the
   items, on duplicate columns and on ragged rows. Do not rescale a 7-point SUS to make it fit; report it as a non-standard
   questionnaire without SUS benchmarks.
4. **Read the checks before the score.** Item columns and their order as printed, rows scored and excluded,
   and for SUS: the odd/even item correlation (negative is expected for the alternating version), the count
   of participants who agreed with both positive and negative items, and straight-liners. If the script
   warns that the data look all-positive, confirm the wording and rerun with `--instrument sus-positive`.
   Remove flagged participants (`--drop-flagged`) only with the user's agreement, and report both results.
5. **Report the mean with its interval, then the benchmark.** SUS: mean, 95% interval, curved grade with the
   grades at the interval's ends, approximate percentile, closest adjective. Grades and percentiles compare
   the product's mean with other products' means; they say nothing about individual users. UMUX-Lite: the raw
   score leads, read on the SUS grades as its author now recommends; the regression SUS-equivalent
   (0.65 x + 22.9, 7-point only) is secondary and historical, and it squeezes every score into 22.9-87.9.
   Its interval is the transformed interval of the mean, with no prediction error. Percentiles are
   interpolated between grade boundaries and adjectives are the closest Bangor mean: say so. When the script
   notes that the grade and adjective disagree (62.0 is a D but closest to "Good"), report both with their
   sources or the grade alone. With one participant there is no interval: report the score alone.
6. **Comparisons.** Same participants rated both designs → `--paired` (paired t); different people → the
   default Welch t. Rows without a participant id are never paired; the output counts them. With
   `--group-col` the pooled line ("All participants (pooled across the design groups)") mixes the designs, so
   it gets no grade, percentile or adjective; in a paired study it has no interval or target test either.
   Report each design and the difference. A one-sided compare (`--tail above`) prints a one-sided bound
   instead of an interval. Report the difference, its interval, p and the verdict, significant or not
   significant; below the small base read the interval, and never write "no difference". With more than two
   designs or tasks use `--pairwise --adjust holm`; `--adjust` also covers the target tests, as their own
   family.
7. **"Is it above average?"** `--target 68 --tail above` for SUS, decided before looking at the data. For SEQ
   and TLX there is no benchmark in this skill; use the user's target or a previous round.

## Output

```markdown
## SUS: <product>, <round or date>

**SUS 76.3 (95% CI 65.1 to 87.4), n = 12.** Grade B (C to A+ across the interval), about the 77th percentile
of published study means; closest adjective "Good" (Bangor et al. 2009).
<One sentence: what the interval allows you to say, e.g. above the average of 68 or not distinguishable.>

Scoring: standard alternating SUS, Brooke (1996); items sus_1 to sus_10, answers 1-5. Rows 13, scored 12,
excluded 1 (incomplete). Checks: odd/even correlation -0.96; 0 agreed with both tones; 1 straight-liner.

### By design or task
| Design | n | Mean | 95% CI | SD | Grade | Percentile |
|---|---|---|---|---|---|---|

### Comparison
| A vs B | Test | Difference | 95% CI | p | Verdict |
|---|---|---|---|---|---|

### Against the target
<Target and why; tail; t; p; verdict.>

### Caveats
- <small base; flagged or straight-lined participants; imputed items; non-standard wording; regression caveat for UMUX-Lite>
```

SEQ is reported per task with one decimal more (means on 1-7). TLX: say "lower is better" and whether the
score is raw (unweighted). Leave out a section when its input is missing.

## Common mistakes

- Scoring SUS items with the wrong polarity, or averaging the ten answers: run the script.
- Calling a 7-point or reworded questionnaire "SUS" and grading it against SUS norms.
- Using Welch (independent) t on a within-subjects study, or paired t on different people.
- Reading "percentile 77" as "77% of users were satisfied".
- Reporting a grade without the interval: with a dozen participants a "B" can span C to A+.
- Treating UMUX-Lite raw and the regression SUS-equivalent as the same number.
- Testing a pooled mean of a within-subjects study as if every row were a different person.

## Checks before answering

- Is the instrument and its wording version (alternating or all-positive) stated?
- Did the printed item order match the questionnaire?
- Are every mean's n and interval shown, and are small bases called directional?
- Were the miscoding checks read, and is any exclusion agreed and reported both ways?
- Is the comparison test right for the design (paired vs independent), with a verdict, adjusted if several?
- Do grades, percentiles and adjectives come from the script and refer to the mean, with their sources?
- For UMUX-Lite, does the raw score lead, with the regression SUS-equivalent marked as secondary?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `question_create_bulk` (the items as separate `opinion_scale` questions in questionnaire order, `itemDetails {min_value: 1, max_value: 5}` for SUS, `max_value: 7` for UMUX-Lite and SEQ, end labels in `textItemDetails`; `opinion_scale` stops at 10 points, so raw TLX needs a 0-100 `slider` per subscale); `responses_get_counts` (totals); `responses_read` (rows for this script). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.

Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type and completion status (`responseType: "real"`, `status: "completed"`; exclude synthetic and test responses), and reconcile the row count with `responses_get_counts` under the same filters before computing. Answers come keyed by question id: with `answerFormat: "numeric"`, write one row per response and one column per item, in questionnaire order, to a CSV. For a within-subjects study keep the same participant id across designs.
