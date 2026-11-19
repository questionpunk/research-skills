---
name: survey-weighting
description: "Weights a survey sample to known population totals by raking (iterative proportional fitting) or cell weighting: reads target margins, rakes to a stated tolerance, trims extreme weights and re-rakes, and reports the design effect, Kish effective sample size, weight distribution and weighted estimates, writing a new file and never overwriting the data. Also reports the design effect of existing weights. Use for \"weight my survey\", \"raking\", \"rim weighting\", \"rake to census\", \"post-stratification\", \"my sample has too many women or young people\", \"design effect\" or \"effective sample size\"."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# Survey weighting

Gives each respondent a weight so the sample matches known population shares (sex, age, region, plan tier,
company size), then says what the weighting cost in precision. [`scripts/survey_weighting.py`](scripts/survey_weighting.py)
(Python 3.9+, standard library only) rakes or cell-weights, trims on request, and writes a copy of the data with
a weight column. Run it; do not compute weights in the conversation. Formulas, defaults and citations:
[`references/sources.md`](references/sources.md).

Weighting corrects the mix of the sample on the variables you weight on. It does not fix who chose not to
answer for other reasons. Unequal weights also cost precision: Kish's design effect (1 + CV²) is the usual
approximation of that cost. For an outcome closely related to the weighting variables, calibration can instead
reduce the variance, so outcome-specific uncertainty needs the sampling design (replicate weights or
linearization), not this script. Say what weighting fixes and what it costs.

## When to use

- The sample's mix is off ("too many women / older people / free users") and population shares are known.
- The user needs the design effect or effective sample size of a set of weights, or the weights trimmed.
- Before `survey-crosstabs` or any other analysis that should be weighted.

Do not use it for:

| Request | Use instead |
|---|---|
| Tables and significance tests with existing weights | `survey-crosstabs` (`--weight`) |
| How many respondents to collect, or quotas to set | `survey-sample-size` |
| Removing speeders, duplicates and bots | `survey-data-cleaning` first: weight the clean data |
| Propensity or matching adjustments for opt-in panels | Not this skill: name the method and stop |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and do
not stretch this skill to cover it.

## What to ask for

The targets are the one input you must not invent. Ask: "What population should the sample represent, and where
do the target shares come from (source and year)?" If the user has none, help them find an official source
(a census or statistics office table, the CRM's customer counts) and confirm the categories match the
questionnaire before running anything. Also ask which one or two outcome questions matter most, to compare
unweighted and weighted with `--estimate` (categorical answers only: it reports shares, not means).

Targets file, raking (`target` may be named `percent`, `share` or `count` to state the unit) or cells:

```text
variable,category,percent        gender,age,count
gender,Female,51                 Female,18-54,30000
gender,Male,49                   Female,55+,21000
age,18-54,62                     ...
age,55+,38
```

| Input | Default |
|---|---|
| Data | Respondent-level CSV (any delimiter, UTF-8 or UTF-16, Qualtrics header detected). Clean it first. |
| Targets | Required: `--targets FILE` with `variable,category,target`, or `--target 'gender:Female=51;Male=49'` per variable. A file with one column per variable plus `target` means cell weighting. |
| Target unit | From the target column's name (`percent`, `share`, `count`), a `%` sign, `--target-unit`, or else the total (1 = shares, 100 = percents, other = counts). Shares or percents that miss 100% by more than rounding are refused (`--rescale-targets` to rescale); totals near but not at 1 or 100 are refused as ambiguous; count totals that disagree need `--scale-total` or `--scale-mean-one`. `1,020` is refused (thousands or decimal comma?). |
| Method | Raking for margins; cell weighting for a joint table. |
| Base weights | None (all 1). Use `--base-weight` for design or panel weights. `--base-weight COL` alone (no targets) reports the design effect and effective n of existing weights and writes nothing. |
| Category mismatch | Refused; map with `--collapse 'age:55+=55-64;65+'`, which combines the data values and any matching target categories. Matching to targets ignores case and spacing (a warning names spellings that differ). |
| Missing values on a weighting variable | Refused; after asking, map them with `--collapse 'age:Unknown=NA;(blank)'` (to a category that has a target) or pass `--missing skip-margin`. |
| Base weights that are blank, zero or unreadable | Those rows are excluded, refused over 5% of rows (`--allow-drop`). Their weight cell in the output is blank. |
| Tolerance, iterations | Margins within 1e-6 of target; up to 1,000 iterations. |
| Trimming | None. Offered when the largest weight passes 5 × the mean (`--trim-max 5`). Raking only: cell weights are not trimmed (a warning says so). |
| Output | No file unless `--out`; weights average 1, or sum to the population total when targets are counts (`--scale-total N` or `--scale-mean-one` to choose). |
| No-answer codes | Blank, NA, N/A, #N/A, NaN, NULL, None. `--na` replaces this list. |

## Steps

Run the script by its path inside this skill's folder (the folder this SKILL.md is in), not relative to the
user's working directory: `python3 <skill-dir>/scripts/survey_weighting.py`. Examples write `scripts/...` and
run from the skill folder.

0. **First run: check the install on the bundled fixture.**

   ```bash
   python3 scripts/survey_weighting.py fixtures/panel.input.csv --targets fixtures/panel.targets.csv --estimate q1
   ```

   Expected: converged in 3 iterations; Kish effective n 166.6 of 200, design effect 1.200, weights 0.505 to
   2.375; q1 = Yes 41.5% unweighted, 47.6% weighted (40.2% to 55.1%). Anything else means the wrong file or
   folder.
1. **Check the inputs.** Read the header and a few rows. List each weighting variable's values and compare them
   with the target categories. Note missing values, and look at categories under about 2% of the sample or the
   targets: check their support and definitions with the user, and whether combining one with a neighbour would
   change what the margin controls, before collapsing.
2. **Dry run (no file)** on the user's data and targets files:

   ```bash
   python3 scripts/survey_weighting.py sample.csv --targets targets.csv
   ```

3. **If it exits with code 2, fix the cause.** Unmatched categories: `--collapse`. A target category with no
   respondents, or "the targets cannot all be met" (zero targets that remove everyone a later margin needs):
   collapse or fix the targets (raking cannot create people). "Did not converge": two variables are nearly the
   same in the sample; collapse or drop one. Target units or totals refused: ask the user which they meant. Do
   not edit respondents' answers.
4. **Read the diagnostics.** Margins: weighted equals target. Weights: design effect, Kish effective n, max/mean,
   max/min, and the mean weight per category (which groups were scarce). Warnings.
5. **Trim only if needed, and compare.** If max/mean is above 5 or the design effect is far above what the user
   can afford, rerun with `--trim-max 5` (and `--trim-min 0.2` if tiny weights matter) and show key estimates
   both ways with `--estimate q1 q2`. After trimming the margins are re-raked and checked again (exit 2 if they
   no longer match). If the warnings say the cap was not met, or a weight is under 0.01 × the mean, the margins
   need those weights: collapse sparse categories or weight on fewer variables; bounded calibration (R
   `survey::calibrate` with bounds) is the next step and is not in this script.
6. **Write the weights.**

   ```bash
   python3 scripts/survey_weighting.py sample.csv --targets targets.csv --trim-max 5 \
     --out sample_weighted.csv --estimate q1
   ```

   The output is the input rows plus a `weight` column (`--weight-col` to rename), UTF-8 comma CSV. It refuses to
   write over the input, the targets file or an existing file (`--overwrite` for the last). Write it to a
   working folder.
7. **Hand off.** Tables: `python3 <crosstabs-skill-dir>/scripts/survey_crosstabs.py sample_weighted.csv --rows q1
   --banner region --weight weight` (the `survey-crosstabs` skill), which reports weighted and effective bases.
   Rows excluded for an unusable base weight have a **blank** weight: crosstabs excludes and counts them too,
   and needs `--allow-drop` exactly when weighting did (over 5% of rows). Rows in a zero-target category have
   weight **0**: both tools keep them in the unweighted base. Answer categories are keyed the same way in both
   (exact text, or the numeric code when every answer has one); if weighting warned that spellings such as
   `Female`/`female` were matched to one target, standardise them before tabulating by that variable.

## Output

```markdown
## Weighting: <survey>, <n> respondents

**Targets:** <variables>, from <source, year>, for <population>.
**Method:** raking on <k> variables, converged in <i> iterations (margins within <tol>) | cell weighting.
<Trimmed at <R> × mean and re-raked (cap met | cap not met: largest <x> × mean) | Not trimmed.>

| Variable | Category | n | Before weighting | Target | Weighted | Mean weight |
|---|---|---|---|---|---|---|

**Cost in precision:** design effect from unequal weighting <deff> (Kish, 1 + CV²), effective n <n_eff> of <n>
(<eff>%). Weights from <min> to <max> (max <x> × mean).

**What changed:** <one or two key estimates, unweighted vs weighted, with intervals>.

**Caveats:** <weighting variables only; intervals use the Kish approximation; collapsed categories; trimming;
missing values handled how>.

Weights saved to `<path>`, column `<name>`.
```

## Common mistakes

- Inventing or guessing target shares, or taking them from a different population (all adults for a survey of
  customers).
- Category definitions that do not match the questionnaire (age bands, "Other" gender, region boundaries).
- Weighting on many variables with small cells, which inflates the design effect for little bias reduction.
- Reporting the weighted total as the sample size, or significance tests on weighted counts.
- Trimming silently, or comparing waves weighted on different variables or targets.
- Claiming weights make an opt-in sample representative: they fix only the weighted variables.
- Writing over the user's data file.

## Checks before answering

- Did the targets come from the user or a named source, with the population and date stated?
- Do all margins match their targets (or is the trimming trade-off stated)?
- Are the design effect and effective n reported next to n?
- Are collapsed categories, missing-value handling and trimming stated?
- Is the largest weight relative to the mean reported, trimming offered when it passes 5, and an unmet cap or a
  weight under 0.01 × the mean stated?
- Were weighted estimates shown next to unweighted ones, with intervals labelled as approximate?
- Was the output written to a new file, never the input?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `responses_read` (the answers, including the weighting variables) and `responses_get_counts` (to reconcile the total). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.

Page `responses_read` with `cursor` = the previous `page.nextCursor` until it is null, filter to the intended response type and completion status (`responseType: "real"` excludes synthetic AI responses, not people testing the live link: drop those by ID or date), map `answers[questionId]` to named CSV columns, and reconcile the row count with `page.total` (or `responses_get_counts` with the same filters; not when `questionIds` is passed, which skips responses that answered none of those questions) before weighting. The weights stay in your output file.
