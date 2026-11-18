# survey_data_cleaning.py: options and file formats

```
python3 scripts/survey_data_cleaning.py INPUT.csv [options]
```

Input: a delimited text file with a header row and one row per respondent. The script stops with an error
(exit code 2) on a missing file, a column name that is not in the header, blank or repeated column names,
a ragged row, a duration that is not a positive number, or an option it cannot read. It never changes the
input.

## What it reads

- **Encoding:** UTF-8, with or without a byte-order mark; if the bytes are not valid UTF-8, Windows-1252.
  The log says which was used. Output files are always UTF-8, comma-delimited.
- **Delimiter:** comma, semicolon or tab, detected from the header row and reported; `--delimiter` forces
  one.
- **Qualtrics:** the two extra header rows (question text, `{"ImportId": ...}`) are detected, skipped and
  kept in the clean file. With a `Status` or `Finished` column, previews, tests and unfinished responses
  are set aside: listed in the log, given no flags, left out of every median, and kept in the file unless
  `--drop-if not_screened` removes them. Qualtrics metadata columns are left out of the question columns.
- **SurveyMonkey:** the two-row header is not merged. The script stops on the blank column names and says
  so; make one header row of unique names first.
- **Google Forms and others:** one header row works as is. With no duration column the speed check is
  reported as not run.

## Options

| Option | Meaning |
|---|---|
| `--out-dir DIR` | Where to write the output files. Default: next to the input. |
| `--delimiter NAME` | `auto` (default), `comma`, `semicolon` or `tab`. |
| `--id-col COL` | Respondent id. Default: a column named `id`, `respondent_id`, `response_id`, `ResponseId`; else row numbers (`row1`, ...). |
| `--duration-col COL` | Completion time in any one unit. Default: a column named `duration`, `duration_sec`, `duration_seconds`, `Duration (in seconds)`. Without one the speed check is not run. |
| `--speed-fraction F` | Speeder = duration strictly below F × median. Default `1/3`. Accepts `0.5` or `1/3`. |
| `--speed-by COL` | Compute every speed median within each value of this column (survey path, device). Group sizes are printed. |
| `--page-time-cols COLS` | Per-page times. Adds `speed_index`: the page median divided by the respondent's page time, capped at 3, averaged over pages. |
| `--rsi-cutoff X` | Speeder when `speed_index` is above X. Default 2.0. |
| `--min-per-item X` | Also a speeder when duration per answered question column is below X. No default; `duration_per_item` is always reported. |
| `--grid NAME=COLS` | A battery of items on one scale. `COLS` is `a,b,c` or a range in file order `first..last`. Repeatable. |
| `--min-grid-items N` | Grids with fewer items are reported but never flagged. Default 4. |
| `--pattern-min-items N` | Smallest grid checked for repeating blocks and staircases. Default 6. |
| `--longstring-fraction F` | Flag a run longer than F of the grid's items (`0.5` on 6 items = 4 or more). |
| `--longstring-min K` | Flag a run of K or more, whatever the grid size. Default without either option: every item identical. |
| `--dup-cols COLS` | Key columns in which a repeated value marks a duplicate. Default: columns named `email`, `e-mail`, `email_address`, `ip`, `ip_address`, `ipaddress`. `none` uses no key columns (identical rows and repeated ids are still flagged). |
| `--dup-ignore COLS` | Columns left out of the identical-row comparison (timestamps, durations). |
| `--attention COL=EXPECTED` | An attention check and its correct answer. Case and surrounding spaces are ignored. A blank counts as failed. Repeatable. |
| `--attention-min-fails N` | Failures needed for a flag. Default 2, or 1 when only one check is given. |
| `--open-cols COLS` | Open-text columns to screen. |
| `--open-min-chars N` | Shorter answers are `too_short`. Default 3. |
| `--repeat-run N` | The same non-digit character N times in a row. Default 4. |
| `--keyboard-run N` | N neighbouring keys on one QWERTY row. Default 4. |
| `--paste-min-chars N` | Answers of N or more characters are compared across respondents (identical and near-duplicate). Default 20. |
| `--similar-text X` | Two such answers are near-duplicates when their word overlap (Jaccard) is X or more. Default 0.8; `off` disables. |
| `--rule 'NAME: EXPR'` | An inconsistency (see below). Repeatable. |
| `--item-cols COLS` | Question columns for item non-response and `duration_per_item`. Default: all except the id, duration, duplicate-key, page-time and Qualtrics metadata columns. |
| `--max-missing F` | Flag when the blank share is above F. Default 0.5. |
| `--recaptcha-min X` | `Q_RecaptchaScore` below X is reported as `platform_bot`. Default 0.5. |
| `--warn-share X` | Warn when a check, the group with 2 or more flags, or the removal exceeds this share. Default 0.12. |
| `--set-before WHICH` | Which rules were fixed before the results were seen: `all`, `none`, or a list of check names and `drop`. Recorded in the log as yes / no (post hoc); "not stated" when the option is absent. |
| `--compare-cols COLS` | Tabulate these columns for the removed rows against the kept ones (without `--drop-if`: respondents with 2 or more flags against the rest). |
| `--clear ID:CHECK` | A reviewer's decision to clear one flag; recorded in the log. Repeatable. |
| `--drop-if RULE` | Write a clean file without the matching rows (see below). |
| `--json` | Print the summary as JSON instead of text. |

## Consistency rules

A rule states the inconsistency: a respondent is flagged when the rule is true.

```
NAME: OPERAND OP OPERAND [and OPERAND OP OPERAND ...]
```

- `OP` is one of `==  !=  <  <=  >  >=`.
- An operand is a column name, a column name in square brackets when it has spaces (`[years in role]`), a
  number, quoted text (`"Never"`), or a column plus or minus a number (`age - 16`).
- Quoted text compares with `==` and `!=` only, ignoring case and surrounding spaces.
- `NAME:` is optional; without it rules are called `rule1`, `rule2`, ...
- A rule is "not evaluable" for a respondent when a cell it needs is blank or is not a number; that
  respondent is not flagged by it and is listed in the log. A respondent with no evaluable rule has a
  blank `inconsistent` cell.

Examples (the numbers in them are illustrations for the user to set, not recommendations):

```
--rule "exp_gt_age: years_experience > age"
--rule 'never_but_uses: uses_product == "Never" and sessions_per_week > 0'
--rule "hours: [hours per day] > 24"
```

## Removal rules

`--drop-if` takes terms joined by commas; a respondent matching any term is removed.

- `count>=N`: N or more counted flags.
- `check`: that flag, e.g. `duplicate`.
- `check+check`: all of them, e.g. `speeder+attention_fail`.
- `not_screened`: the previews, tests and unfinished rows that were set aside.

Counted checks (they add to `flag_count`): `speeder`, `straightliner`, `duplicate`, `attention_fail`,
`open_text_candidate`, `inconsistent`, `high_missing`.

Report-only checks (own columns, never in `flag_count`, usable by name in `--drop-if` and `--clear`):
`pattern_candidate`, `platform_bot`, `platform_ballot_stuffing`, `platform_duplicate`.

Naming a check that did not run, or whose column is not present, is an error.

For duplicates, only the later rows of a group are flagged, so `--drop-if duplicate` keeps the first.

## Output files

For `survey.csv`:

- `survey.flags.csv`: `row`, `id`, `screened` (yes, or no with the reason), one column per counted check
  (1 flagged, 0 not, blank = not run, not present or not evaluable for this respondent), `flag_count`, the
  report-only columns, `missing_share`, then when available `duration_per_item`, `speed_index`,
  `longstring_<grid>`, `irv_<grid>` (variability: sample standard deviation of the answered items), and
  `details`.
- `survey.cleaning-log.md`: input name and SHA-256, how the file was read, rows set aside, each check with
  its rule, threshold, whether it was set before results, count, share and ids, what could not be
  evaluated, flags cleared by a reviewer, the sample summary with warnings, flags that occur together,
  the composition table, and the removal rule with counts.
- With `--drop-if` only: `survey.clean.csv` (the kept rows, original columns) and `survey.removed.csv`
  (the removed rows plus `removed_reason`).

## `--json` summary

```
{
  "input": "...", "input_sha256": "...", "n_rows": 20, "n_respondents": 20,
  "not_screened": [{"row": 9, "id": "Q09", "reason": "survey preview"}], "notes": ["..."],
  "checks": [{"check": "speeder", "status": "run" | "skipped" | "not present", "rule": "...",
              "threshold": "...", "set_before_results": "yes" | "no (post hoc)" | "not stated",
              "n_flagged": 2, "share_flagged": 0.1, "ids": ["R04", "R20"],
              "counts_toward_flag_count": true, "median": 600.0, "cutoff": 200.0}, ...],
  "cleared": [{"id": "R11", "check": "open_text_candidate"}],
  "flag_count_distribution": {"0": 5, "1": 13, "3": 1, "5": 1},
  "sample": {"share_with_1_or_more_flags": 0.75, "share_with_2_or_more_flags": 0.1,
             "warn_share": 0.12, "warnings": ["..."]},
  "flag_overlap": {"speeder + attention_fail": 2},
  "respondents": [{"row": 4, "id": "R04", "flags": ["speeder", "..."], "flag_count": 3, "report_only": []}, ...],
  "drop": null | {"rule": "count>=2", "set_before_results": "not stated", "n_removed": 2, "n_kept": 18,
                  "share_removed": 0.1, "ids": ["R04", "R20"]},
  "composition": null | {"groups": "removed vs kept", "columns": {"region": {"north": {"removed": 5, "kept": 1}}}},
  "files": {"flags": "...", "log": "...", "clean": "...", "removed": "..."}
}
```

With `--speed-by`, the speeder entry carries `"groups": {"<value>": {"n": 4, "median": 195.0, "cutoff": 65.0}}`
instead of `median` and `cutoff`.

## Limits

- No imputation, no outlier trimming, no reverse-coding, no scale scoring, no weighting.
- No even-odd consistency, psychometric synonyms or Mahalanobis distance; the R package `careless` has them.
- The unit of the duration column is not known to the script; `duration_per_item` is in that unit.
- Near-duplicate text compares every pair of long answers in a column, which is slow above a few
  thousand respondents; pass `--similar-text off` to skip it.
- The open-text heuristics assume Latin script and a QWERTY keyboard.
- The script cannot see skip logic; name the columns everyone saw with `--item-cols`.
- Flags are computed on the file as given; the median includes the speeders themselves.
