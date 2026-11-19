# survey_data_cleaning.py: options and file formats

```
python3 <skill-dir>/scripts/survey_data_cleaning.py INPUT.csv [options]
```

`<skill-dir>` is the folder this skill was loaded from (the one holding `SKILL.md`).

Input: a delimited text file with a header row and one row per respondent. The script stops with an error
(exit code 2) on a missing file, a column name that is not in the header, blank or repeated column names,
a ragged row, a duration or page time that is negative or not a number (0 is allowed: a 0-second bot is
flagged, not rejected), a grid answer of NaN, infinity or a number too large to compute (named by row and
column), an attention column given twice, or an option it cannot read. It never changes the
input.

## What it reads

- **Encoding:** UTF-8, with or without a byte-order mark; UTF-16 with a byte-order mark (Excel "Unicode
  Text"); if the bytes are not valid UTF-8, Windows-1252. The log says which was used. Output files are
  always UTF-8, comma-delimited.
- **Delimiter:** comma, semicolon or tab, detected from the header row (a quoted header may span lines)
  and reported; a tie stops the script and `--delimiter` forces one. Only line breaks end a row: a line
  separator or form feed pasted into an answer stays in its cell.
- **Decimal comma:** in a semicolon- or tab-delimited file, a number written `312,5` reads as 312.5
  (durations, page times, grid answers, rule operands, `Q_RecaptchaScore`). A comma file cannot hold an
  unquoted decimal comma, so there it is not a number.
- **Qualtrics:** the two extra header rows (question text, `{"ImportId": ...}`) are detected, skipped and
  kept in the clean file. With a `Status` or `Finished` column, previews, tests and unfinished responses
  are set aside: listed in the log, given no flags, left out of every median, and kept in the file unless
  `--drop-if not_screened` removes them. `Status` 256 (or `Synthetic`) is a synthetic response and is set
  aside the same way. Qualtrics metadata columns are left out of the question columns: the standard ones
  and Qualtrics' own `Q_` fields (`Q_RecaptchaScore`, `Q_RelevantID...`, `Q_BallotBoxStuffing`,
  `Q_DuplicateRespondent`, `Q_TotalDuration`, `Q_URL`, `Q_Language`, `Q_CHL`, `Q_Straightlining...`,
  `Q_Unanswered...`, `Q_AmbiguousText...`, `Q_DataPolicyViolations`, `Q_EmailOpened`). A question you
  named `Q_1` or `Q_NPS` stays a question.
- **SurveyMonkey:** the two-row header is not merged. The script stops on the blank column names and says
  so; make one header row of unique names first.
- **Google Forms and others:** one header row works as is. Form metadata columns (`Timestamp`,
  `Submitted At`, `Start time`, `Completion time` and similar) are left out of the question columns. With
  no duration column the speed check is reported as not run.

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
| `--dup-cols COLS` | Key columns in which a repeated value marks a duplicate. Default: columns named `email`, `e-mail`, `email_address`, `ip`, `ip_address`, `ipaddress`. A repeated id or email is a counted `duplicate`; a repeated IP is only a `shared_ip` candidate. `none` uses no key columns (repeated ids are still flagged). |
| `--dup-ignore COLS` | Columns left out of the identical-answers comparison (timestamps, durations). |
| `--attention COL=EXPECTED` | An attention check and its correct answer. Case and surrounding spaces are ignored. Repeatable; the same column twice is an error. |
| `--attention-min-fails N` | Failures needed for a flag. Default 2, or 1 when only one check is given. |
| `--attention-blank fail\|unshown` | A blank check: `fail` (default) counts it as failed; `unshown` treats it as never shown (skip logic) and not a failure. Respondents with a blank check are listed either way. |
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
| `--clear ID:CHECK` | A reviewer's decision to clear a flag, on every row with that id that carries it; `row=N:CHECK` clears one row (N as in the flags file's `row` column). Recorded in the log. Repeatable. |
| `--confirm ID:CHECK` | A reviewer's decision that a candidate (`open_text_candidate`, `pattern_candidate`, `identical_answers`, `shared_ip`) is real. It then counts in `flag_count`. Same selectors as `--clear`. Repeatable. |
| `--drop-if RULE` | Write a clean file without the matching rows (see below). |
| `--preview` | With `--drop-if`: report who the rule would remove, the share and the `--compare-cols` table, and write no clean or removed file. |
| `--json` | Print the summary as JSON instead of text. |

## Consistency rules

A rule states the inconsistency: a respondent is flagged when the rule is true.

```
NAME: OPERAND OP OPERAND [and OPERAND OP OPERAND ...]
```

- `OP` is one of `==  !=  <  <=  >  >=`.
- An operand is a column name, a column name in square brackets when it has spaces (`[years in role]`), a
  number (`-5` too), quoted text (`"Never"`), or a column plus or minus a number (`age - 16`). Arithmetic
  is exact (`share + 0.2 == 0.3` holds for 0.1). A cell such as `1/5` is text, not a number.
- Quoted text compares with `==` and `!=` only, ignoring case and surrounding spaces. Two columns with no
  offset compared with `==` or `!=` compare as text when either cell is not a number
  (`fav_brand == least_fav_brand`).
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
`inconsistent`, `high_missing`.

Candidates (own columns; each adds 1 to `flag_count` only after `--confirm`): `open_text_candidate`,
`pattern_candidate`, `identical_answers`, `shared_ip`.

Platform fields (own columns, never in `flag_count`): `platform_bot`, `platform_ballot_stuffing`,
`platform_duplicate`.

Candidates and platform fields can be named in `--drop-if` and `--clear`.

Naming a check that did not run, or whose column is not present, is an error.

For duplicates, only the later rows of a group are flagged, so `--drop-if duplicate` keeps the first.

## Output files

For `survey.csv`:

- `survey.flags.csv`: `row`, `id`, `screened` (yes, or no with the reason), one column per counted check
  (1 flagged, 0 not, blank = not run, not present or not evaluable for this respondent), `flag_count`, the
  candidate and platform columns, `confirmed` (candidates a reviewer confirmed), `missing_share`, then when available `duration_per_item`, `speed_index`,
  `longstring_<grid>`, `irv_<grid>` (variability: sample standard deviation of the answered items), and
  `details`.
- `survey.cleaning-log.md`: input name and SHA-256, how the file was read, rows set aside, each check with
  its rule, threshold, whether it was set before results, hits before review, count, share and ids after
  review, cleared and confirmed ids, what could not be evaluated, flags cleared and candidates confirmed
  by a reviewer, the sample summary with warnings, flags that occur together,
  the composition table, and the removal rule with counts.
- With `--drop-if` and without `--preview`: `survey.clean.csv` (the kept rows, original columns) and `survey.removed.csv`
  (the removed rows plus `removed_reason`).

## `--json` summary

```
{
  "input": "...", "input_sha256": "...", "n_rows": 20, "n_respondents": 20,
  "not_screened": [{"row": 9, "id": "Q09", "reason": "survey preview"}], "notes": ["..."],
  "checks": [{"check": "speeder", "status": "run" | "skipped" | "not present", "rule": "...",
              "threshold": "...", "set_before_results": "yes" | "no (post hoc)" | "not stated",
              "n_initial": 2, "n_flagged": 2, "share_flagged": 0.1, "ids": ["R04", "R20"], "cleared_ids": [],
              "counts_toward_flag_count": true, "kind": "counted" | "candidate" | "platform",
              "median": 600.0, "cutoff": 200.0}, ...],
  "cleared": [{"id": "R05", "row": 5, "check": "inconsistent"}],
  "flag_count_distribution": {"0": 11, "1": 7, "2": 1, "4": 1},
  "sample": {"share_with_1_or_more_flags": 0.75, "share_with_2_or_more_flags": 0.1,
             "warn_share": 0.12, "warnings": ["..."]},
  "flag_overlap": {"speeder + attention_fail": 2},
  "respondents": [{"row": 4, "id": "R04", "flags": ["speeder", "attention_fail"], "flag_count": 2,
                   "report_only": ["open_text_candidate"], "confirmed": []}, ...],
  "drop": null | {"rule": "count>=2", "preview": false, "set_before_results": "not stated", "n_removed": 2, "n_kept": 18,
                  "share_removed": 0.1, "ids": ["R04", "R20"]},
  "composition": null | {"groups": "removed vs kept", "columns": {"region": {"north": {"removed": 5, "kept": 1}}}},
  "files": {"flags": "...", "log": "...", "clean": "...", "removed": "..."}
}
```

Candidate entries also carry `confirmed_ids`; the attention entry carries `blank` and `blank_ids`. The
text output (without `--json`) starts with a `Checks run: ...; Not run: ...` line.

With `--speed-by`, the speeder entry carries `"groups": {"<value>": {"n": 4, "median": 195.0, "cutoff": 65.0}}`
instead of `median` and `cutoff`.

## Limits

- No imputation, no outlier trimming, no reverse-coding, no scale scoring, no weighting.
- No even-odd consistency, psychometric synonyms or Mahalanobis distance; the R package `careless` has them.
- The unit of the duration column is not known to the script; `duration_per_item` is in that unit.
- Near-duplicate text compares only pairs that share a rare word (exact prefix filtering, same result as
  comparing every pair); 20,000 answers take seconds. `--similar-text off` skips it on a first pass.
- The open-text heuristics assume Latin script and a QWERTY keyboard.
- The script cannot see skip logic; name the columns everyone saw with `--item-cols`.
- Flags are computed on the file as given; the median includes the speeders themselves.
