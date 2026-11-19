---
name: kano-analysis
description: "Designs and analyzes Kano surveys: writes the functional and dysfunctional question pair for each feature, classifies every answer with Kano's evaluation table (attractive, one-dimensional, must-be, indifferent, reverse, questionable), assigns each feature its category with Fong's test for a clear winner, and computes Better/Worse coefficients with intervals for a quadrant chart. Use for \"Kano model\", \"Kano survey\", \"Kano analysis\", \"which features are must-haves vs delighters\", \"feature prioritization survey\" or \"better worse coefficients\"."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# Kano analysis

Sorts features into must-be, one-dimensional (more is better), attractive (delighters), indifferent and reverse
from paired survey questions. [`scripts/kano_analysis.py`](scripts/kano_analysis.py) (Python 3.9+, standard
library only) writes the question pairs (`design`) and does the classification, Fong's test, Better/Worse and
intervals (`analyze`). Run it; do not classify answers in the conversation. Method, page references and
thresholds: [`references/sources.md`](references/sources.md).

Kano tells you what kind of requirement a feature is, not how much it is worth. Do not rank features on close
Better/Worse values: Berger et al. (1993) warn their uncertainty is "tens of percent". The script prints an
interval per feature; it shows one feature's uncertainty and is not a test of the gap between two features.

## When to use

- "Run a Kano survey", "design Kano questions for these features".
- "Analyze our Kano results", "which features are must-haves vs delighters", "Better/Worse coefficients",
  "Kano quadrant chart".
- A Kano export from QuestionPunk, Qualtrics, SurveyMonkey or a spreadsheet with two answers per feature.
- "Our tool says X is attractive, is that right?" (reconcile the table, code order, category rule and ties:
  "Why tools disagree" in [`references/sources.md`](references/sources.md)).

Do not use it for:

| Request | Use instead |
|---|---|
| Rank many features by preference or trade-off | `maxdiff-design`, `maxdiff-analysis` |
| Feature bundles and willingness to pay | `conjoint-design`, `conjoint-analysis`; price alone: `van-westendorp-analysis` |
| Rating-scale importance or satisfaction items | `likert-analysis` |
| Satisfaction or effort ratings (CSAT, CES) | `csat-ces-analysis` |
| Writing the rest of the questionnaire | `survey-from-decision`, `survey-bias-check` |
| How many respondents to recruit | `survey-sample-size` |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and do
not stretch this skill to cover it.

## What to ask for

Designing: the feature list, who the respondents are, and whether to add self-stated importance. Analyzing: the
file, and the fieldwork dates if the user knows them. Ask at most one question, and only when it blocks the run; the usual one is "Do your answer codes run 1 =
like to 5 = dislike, or the other way round?" when the export holds bare numbers and no labels.

| Input | Default |
|---|---|
| Answers | Codes 1 like, 2 must-be, 3 neutral, 4 live with, 5 dislike (Berger's order, which QuestionPunk uses), or the answer text. Text wins over a number in "1 - I dislike it"; a number with a label the script does not know ("1 - Strongly disagree") is unreadable. |
| Columns | Detected: QuestionPunk export headers (`Q3 \| Dark mode: functional`), or names ending `_f`/`_d`, `functional`/`dysfunctional`. Otherwise `--pair 'Feature=fcol,dcol[,importance_col]'`, `--long` with `--feature-col`, `--functional-col`, `--dysfunctional-col` (optional `--importance-col`, and `--respondent-col` to count people), or `--qp-answer-col`. Quote a column name that holds a comma: `--pair 'Dark="If you had dark mode, how...","If you had no dark mode, how..."'`. |
| Importance | Read when present (Berger's 1-9); mean shown next to each feature. Use it to order features within a category. |
| Segments | None. Offer `--segment-col` (plan, role, experience) when answers are spread over categories. |
| Small base | Under 30 answers per feature flagged. |

## Steps

Run the script by its path inside this skill's folder (the folder this SKILL.md is in), not relative to the
user's working directory: `python3 <skill-dir>/scripts/kano_analysis.py`. The examples below are written from
the skill folder (`scripts/...`, `fixtures/...`) and run as written there.

First run, to check the install and your reading of the table, on a bundled ten-respondent example:

```bash
python3 scripts/kano_analysis.py analyze fixtures/spec_example.input.csv
```

Expected rows: `Save progress and resume later | 10 (10) | must-be | yes |` with Better 0.10 and Worse −0.80,
and `Dark mode | 10 (8) | one-dimensional (tie with A) | no (O vs A) |` with Better 1.00 and Worse −0.50.

**Designing a survey**

1. Name each feature as one customer benefit, as a noun phrase the template can use ("cross-device note sync",
   not "sync and sharing"); edit the drafts into natural sentences afterwards.
2. Draft and check the pairs:

   ```bash
   python3 scripts/kano_analysis.py design --features "Cross-device note sync;Dark mode" \
     --product "the app" --importance
   python3 scripts/kano_analysis.py design --wording fixtures/wording_check.input.csv
   ```

   The drafts are a template: edit them into natural sentences about the benefit, save them as
   `feature,functional,dysfunctional`, and re-check with `--wording`. Each `CHECK:` line is advisory: fix it,
   or keep the wording and say why (a performance contrast such as "arrives today" / "arrives next week" has no
   negation word and is still a valid pair). Keep Berger's five answers word for word, in the same order for
   both questions, not numbered on screen. Ask the dysfunctional question straight after its functional one.
   Run a pilot of 5-10 people: many questionable or "other" reactions mean the wording is unclear. In a
   self-completed survey, show one worked example before the first pair. Deliver the questionnaire the script
   prints, with each `CHECK:` resolved or explained.

**Analyzing results**

1. Look at the header and a few rows: which columns hold each feature's pair, codes or text, importance, any
   segment column.
2. Run:

   ```bash
   python3 scripts/kano_analysis.py analyze fixtures/spec_example.input.csv   # detected columns
   python3 scripts/kano_analysis.py analyze fixtures/custom_columns.input.csv \
     --pair "Save progress and resume later=save_like,save_without,save_importance" \
     --pair "Dark mode=dark_like,dark_without" --segment-col plan
   python3 scripts/kano_analysis.py analyze fixtures/spec_example_answer_text.input.csv --qp-answer-col Q3
   python3 scripts/kano_analysis.py analyze fixtures/long_format.input.csv --long --feature-col feature \
     --functional-col functional --dysfunctional-col dysfunctional --respondent-col respondent
   python3 scripts/kano_analysis.py analyze --counts fixtures/berger_fig16.input.csv   # feature,A,O,M,I,R,Q
   ```

   Swap in the user's file. Add `--json` for full precision. `--chart kano.svg` writes a quadrant chart to a
   new file in a working folder; it refuses an existing file unless you pass `--overwrite`, and never replaces
   the input.
3. If it exits with code 2, fix the cause it names: a CSV line with an unclosed quote, unpaired or doubled
   columns (pass `--pair`), a feature or `--pair` given twice, more than 5% unreadable answers (map them;
   `--allow-unreadable` only after looking), counts that are blank, fractional or not numbers (counts must be
   whole numbers; percentages are not counts), or duplicate column names.
4. If the script warns about Reverse answers, check the codebook (which number is "I like it") and that the
   functional question is the "has it" form. If the codes were reversed, confirm with the user and rerun with
   `--code-order dislike-first`. If both are right, keep the reverse result: it is a finding (some respondents
   do not want the feature), so check it by segment and decide whether to drop the feature, target it, or make
   it optional.
5. Read the table and notes, then write the answer below.

## How to read the results

- **Category** is the most frequent class. "(tie with X)" means classes had equal counts (two or more) and
  M > O > A > I > R > Q picked the label: report it as a tie, not as that category.
- **Clear?** Fong's test at z = 1.65 (two-sided 90%): "no (A vs O)" means the top two classes are statistically
  indistinguishable ("A vs M/O": two classes tie for second); report the feature as "attractive or
  one-dimensional", and look at segments. On a small base a "yes" is weak evidence.
- **Better** (0 to 1): how much having it raises satisfaction. **Worse** (0 to −1): how much lacking it
  hurts. Must-be: low Better, strongly negative Worse. Attractive: high Better, Worse near 0.
- **n (base):** n is every answer; the base (A + O + M + I) is what Better and Worse divide by. A base well
  below n means many R or Q answers.
- **Priorities.** Read the categories in Berger's order of impact, M > O > A > I (p. 11): a missing must-be
  hurts most, one-dimensional features are where you compete, attractive ones differentiate, indifferent ones
  can wait. Reverse means some respondents actively do not want it.
- **Questionable over 10%:** the pair is unclear or respondents were not paying attention; reword and pilot.
  Swapping the questions or the code order does not change Q.
- **Spread answers** (no clear winner, Better and Worse both moderate) usually mean segments disagree.
- Categories can shift as features become common, so date the result.

## Output

```markdown
## Kano results: <product>, n = <respondents> (<date of fieldwork, if known>)

| Feature | n (base) | Category | Clear? | A% | O% | M% | I% | R% | Q% | Better (<level> CI) | Worse (<level> CI) | Importance |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

**Must-be:** <features>: missing them costs satisfaction; adding them earns little.
**One-dimensional:** <features>. **Attractive:** <features>. **Indifferent:** <features>: can wait.
**Reverse:** <features>: some respondents do not want them; drop, target or make optional.
**Not clear:** <features where Fong's test fails, with the candidate classes; list them only here, not above>.
**Segments:** <where a segment's category differs, with n>.

**Method:** Kano evaluation table (Berger et al. 1993); category = mode, ties M > O > A > I; Fong's test at
1.65; Better = (A + O)/(A + O + M + I), Worse = −(O + M)/(A + O + M + I); <level> Wilson intervals per feature
(not tests between features). Codes: <order>.
**Caveats:** <small bases, Q rates, reverse answers and what the codebook check found, unreadable answers>.
Chart: <path, if written>.
```

## Common mistakes

- Reading numeric codes in the wrong direction (A, O and M all turn into Reverse; I and Q do not change).
- Re-wording or re-ordering the five answers, numbering them on screen, or separating the two halves of a pair.
- Asking about a feature ("has an AI assistant") instead of the benefit; wording moves the category.
- Ranking features on close Better/Worse values (per-feature intervals do not test the gap between features).
- Treating a reverse result as a coding error without checking the codebook, or dropping it once checked.
- Calling a feature attractive when Fong's test says it is not a clear winner.
- Treating Kano as a measure of value or willingness to pay.

## Checks before answering

- Did every count, category and coefficient come from the script run on this file?
- Is the code order stated, and was a Reverse-heavy result checked against the codebook and kept if real?
- Are ties and features that fail Fong's test labelled as such?
- Are Better and Worse shown with intervals, and are close features not ranked against each other?
- Are small bases, high Q rates and reverse modes repeated from the notes?
- For a design: are the five answers Berger's wording in a fixed order, with each pair checked?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `survey_get` (question ids), `question_create` (each half of a pair as a multiple-choice question; the Kano question type itself is created in the app, see [`references/fielding.md`](references/fielding.md)), `responses_read` (answers; `answerFormat: "numeric"` for `--qp-answer-col`), `responses_get_counts` (to reconcile the count). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.

Page `responses_read` with `cursor` = `page.nextCursor` until it is null, filter to the intended response type and completion status (`responseType: "real"` drops synthetic responses only, so remove your own test responses too), and reconcile the row count before computing.
