---
name: survey-crosstabs
description: "Builds crosstabs (banner tables) from a survey CSV: column percentages with bases, significance letters from column-proportion tests with Holm or Benjamini-Hochberg correction, chi-square, intervals, weighted bases with Kish effective n, and an anonymity rule that hides groups and cells under k respondents. Use for \"crosstab this survey\", \"banner table\", \"break results down by segment\", \"is this difference between groups real\", \"significance testing on survey results\" or employee survey results by team."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# Survey crosstabs

Turns a respondent-level survey CSV into banner tables: one question down the side, segments across the top,
column percentages with their bases, letters for differences that survive a multiple-comparison correction, a
chi-square per table, optional means and nets, weights with Kish effective n, and an anonymity rule for
employee surveys. [`scripts/survey_crosstabs.py`](scripts/survey_crosstabs.py) (Python 3.9+, standard
library only) does all the arithmetic. Run it; do not compute percentages or tests in the conversation.
Formulas, thresholds and citations: [`references/sources.md`](references/sources.md).

## When to use

- "Crosstab this survey", "banner table", "break Q5 down by plan / region / age".
- "Is the difference between these groups real?", "significance test these results", "which segments differ?"
- "Weighted crosstabs", "use the weight column", "what is the effective sample size?"
- "Results by team / department / manager" for an employee or pulse survey, where small groups must not be
  identifiable.
- "SPSS / my dashboard shows different letters": reconcile the convention.

Do not use it for:

| Request | Use instead |
|---|---|
| Creating weights (raking to census or panel targets) | `survey-weighting`, then come back with `--weight` |
| NPS, CSAT or CES scores with their own intervals | `nps-analysis`, `csat-ces-analysis` |
| Reliability, distributions and box scores of a rating scale | `likert-analysis` |
| Removing speeders, duplicates and bots first | `survey-data-cleaning` |
| Coding open-ended answers into themes before tabulating | `open-ended-coding` |
| How many respondents per group to collect | `survey-sample-size` |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and do
not stretch this skill to cover it.

## What to ask for

Start from the file. Ask at most one question, and only if it blocks the run: "Which question(s) should go down
the side, and which grouping across the top?" Everything else has a default.

| Input | Default |
|---|---|
| File | Respondent-level CSV (any delimiter, UTF-8 or UTF-16, Qualtrics 3-row header detected). Aggregated counts work with `--count-col`. |
| Row questions (`--rows`) | Required. Run `--list-columns` first to see candidates. |
| Banner (`--banner`) | None: Total only. One respondent must belong to one group (no multi-select banner). |
| Weight column (`--weight`) | None. If the file has one (for example written by `survey-weighting`), use it and say so. Ask whether the sample has strata, clusters or replicate weights: if it does, the letters and chi-square here are approximate, so report percentages only (`--test none`) or use a design-based tool (R `survey`, `svychisq`). |
| Multi-select questions (`--multi`) | None. `--list-columns` marks columns that look multi-select; cells are split on `;` (`--multi-sep`). |
| Nets (`--net 'q1:Top 2=4;5'`) and means (`--means`) | None. Offer them for rating scales. |
| Test, correction, family | Pooled z (Fisher exact when an expected count is under 5), Holm, every test in a table is one family, alpha 0.05. |
| Small base | 30 (effective) respondents: flagged "!" and not tested. |
| Anonymity rule | Off. **Turn it on (`--anonymity`, k = 5) for any employee, HR, student or patient survey**, or whenever a group could identify a person. Ask the user for their organisation's k if they have one, and release unweighted tables for these populations. |

## Steps

Run the script by its path inside this skill's folder (the folder this SKILL.md is in), not relative to the
user's working directory: `python3 <skill-dir>/scripts/survey_crosstabs.py`. Examples write `scripts/...`
and `fixtures/...` relative to that folder.

0. **Check the install** on a bundled fixture before touching the user's file:

   ```bash
   python3 scripts/survey_crosstabs.py fixtures/agresti_party_gender.input.csv --count-col count \
     --rows party --banner gender
   ```

   Expect `X2 = 30.07, df = 2, p = <0.001` (Agresti 2007) and Democrat 49% of females with letter `B`.
1. **Look at the columns.**

   ```bash
   python3 scripts/survey_crosstabs.py fixtures/basic.input.csv --list-columns
   ```

   Pick the row and banner columns. A banner with dozens of values (free-text job titles, ZIP codes) is not a
   banner: ask which grouping the user means or recode it first.
2. **Run the tables.** The examples use the bundled fixtures; put the user's file and columns in their place.

   ```bash
   python3 scripts/survey_crosstabs.py fixtures/basic.input.csv --rows satisfaction features \
     --multi features --banner plan
   python3 scripts/survey_crosstabs.py fixtures/basic.input.csv --rows satisfaction --banner plan \
     --weight weight --means --net 'satisfaction:Satisfied=4;5' --show-ci
   python3 scripts/survey_crosstabs.py fixtures/employee_pulse.input.csv --rows engaged --banner team \
     --anonymity 5 --hide 'team=Operations'
   python3 scripts/survey_crosstabs.py fixtures/aspirin_mi.input.csv --count-col count --rows heart_attack \
     --banner group
   ```

   Text output is Markdown tables; add `--json` for full precision. The script writes no files.
3. **If it exits with code 2, fix the cause, not the data.** Duplicate column names, ragged rows, a missing
   column, or more than 5% of rows with an unreadable weight stop it. Do not pass `--allow-drop` until you have
   looked at those rows and told the user how many will be left out.
4. **Read each table before writing.** Check the bases, the "No answer" and "No <banner>" counts, the "!" small
   bases, the chi-square warning, and every anonymity note.
5. **Write the answer** in the shape below. Copy numbers and letters from the script.

Flags for other situations:

| Situation | Flag |
|---|---|
| Category order is wrong (nominal answers are ordered by size, codes numerically) | `--order 'q1=Yes;No;Not sure'` |
| Cells such as `-99` mean no answer | `--na "" NA -99` |
| Use the same adjustment family as SPSS Custom Tables | `--adjust bonferroni --family row --test z`. This selects the adjustment only; letters can still differ, because SPSS leaves out answers with a share of 0% or 100% in a group and this script skips groups under the small-base cutoff (`--small-base`). |
| Many tables and exploratory reading | `--adjust bh` (false discovery rate) |
| User wants raw, unadjusted letters | `--adjust none`, and say how many tests were run |
| Show intervals | `--show-ci` |
| Percentages only, no tests (complex samples) | `--test none` |
| Keep the same groups hidden across waves (anonymity) | `--hide 'team=Legal;HR'` |

## How to read the results

- **Letters.** "35% A" in the Pro column means Pro's share is significantly higher than group A's after the
  correction. No letter means no detected difference, not "the same". Total is never tested.
- **Bases.** Every percentage is read with its base. Under 30 (effective) the column is directional: report it,
  never headline it.
- **Weights.** Percentages are weighted; bases are shown three ways (unweighted n, weighted base, effective n).
  Tests use the Kish effective n, an approximation (it ignores strata, clusters and how the weights relate to
  the answer). With a design effect of 2, the weighted sample carries about as much information as one half its
  size, and standard errors are about 1.4 times larger; ask whether trimming was considered (`survey-weighting`).
  A weighted pair with a small expected count is not tested (no exact test on weighted data); `--json` gives
  the reason per pair.
- **Chi-square** says whether the question and the banner are associated at all. A significant chi-square with
  no letters, or letters without a significant chi-square, can come from the base cutoff, the correction or the
  different tests; say which groups were tested and with which correction, and do not guess a mechanism. If the
  chi-square warning fires, combine small answers or groups. With weights, the 2×2 z-test and chi-square use
  slightly different effective bases (per group versus pooled), so z² and X² differ a little.
- **Many tables.** The correction applies within a table, not across tables. Say how many tables and tests were
  run, which comparisons were planned before looking, and treat unplanned findings across many tables as leads.
- **Anonymity.** "*" cells and groups are hidden, including complementary ones, and the chi-square is withheld
  when the groups it would test have hidden cells. Never recompute or estimate a hidden value, never describe it
  ("Legal was mostly negative"). Within one run a group hidden in one table is hidden in all of them; across
  waves, pass the same groups with `--hide`. Do not release extra cuts (team × tenure) or weighted tables that
  would let a reader subtract.

## Output

```markdown
## <Question> by <banner>  (<weighted | unweighted>, n = <total base>)

| | Total | <Group> (A) | <Group> (B) | ... |
|---|---|---|---|---|
| Base (n) | ... |
| Effective n (weighted only) | ... |
| <Answer> | 45% | 40% | 52% A | ... |
| Mean (if asked) | ... |

**What differs:** <one sentence per letter that matters, with both percentages and bases>.
**Overall association:** chi-square X² = <x>, df = <d>, p = <p> <and its warning, if any>.
**Not answered:** <n> left out; <n> with no <banner> (Total only).
**Method:** column-proportion z-tests (Fisher exact for small expected counts), <correction> within each
<table|row>, alpha <a>; <k> tests in this table. Small base under <30>: <groups>, not tested.
<Weights: n, effective n, design effect.> <Anonymity: k = <k>; hidden groups and cells, and why.>
```

Repeat the block per table. Lead the answer with the two or three differences that matter for the user's
decision, not with every letter.

## Common mistakes

- Reporting a percentage without its base, or a weighted percentage with the unweighted base as if it were the
  precision.
- Testing a group against Total, or comparing groups from two different banner variables.
- Reading "no letter" as "no difference" for a small base.
- Running tests on the weighted counts as if they were respondents (overstates significance).
- Treating a multi-select question as if its options were exclusive (chi-square, shares adding to 100%).
- Hand-computing a hidden anonymity cell from the Total, or naming a hidden group's result in prose.
- Mixing filters: synthetic, test or incomplete responses left in one table and removed from another.

## Checks before answering

- Did the fixture check in step 0 give the expected numbers?
- Did every number and letter come from the script run on this file?
- Is every percentage reported with its base, and are small bases marked as directional?
- Are the correction, the family and the number of tests stated?
- With weights: are the weighted base and effective n shown, and is the design effect mentioned?
- Are "No answer" and missing-banner counts stated?
- If the chi-square warning fired, is it repeated?
- For any employee or other identifiable population: was `--anonymity` on, and is no hidden value described?
- Are causal words ("because", "drives") avoided? A crosstab shows association only.

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `responses_read` (the answers, for this script), `responses_get_counts` (to reconcile the total), `report_get_crosstab` (a quick hosted cross of two numeric questions; it takes no filters and includes synthetic responses, so use this script for reporting). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
Page `responses_read` with `cursor` = the previous `page.nextCursor` until it is null, map each `answers[questionId]` to a named CSV column, filter to the intended response type and completion status (`responseType: "real"` drops synthetic responses only, so remove the team's own test responses separately), and reconcile the row count against `page.total` before computing.
