---
name: survey-data-cleaning
description: "Screens a survey export for response quality: flags speeders, straight-liners, duplicates, failed attention checks, gibberish or copy-pasted open answers, inconsistent answers and platform bot or fraud flags. Writes a flags file and a cleaning log, removes rows only by a rule the user approves, and never changes the original. Use for \"clean this survey data\", \"remove bad responses, bots or speeders\", \"careless responding\", \"which responses should I drop\" or before analyzing any survey CSV (Qualtrics, Google Forms or other exports)."
license: MIT
metadata:
  version: "0.2.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# Survey data cleaning

Screen a survey export for low-quality responses, decide removals by a stated rule, and leave a record of
what was done. The script flags; it never deletes on its own and never changes the export.

## When to use

Use when the user has a survey export (one row per respondent) and says things like "clean this survey
data", "remove bad responses, bots or speeders", "check for careless responding", "which responses should
I drop", "find duplicates and straight-liners", or is about to analyze a raw export from Qualtrics,
SurveyMonkey, Google Forms or any other tool.

Do not use for:

- Coding or theming open answers: `open-ended-coding`. This skill only screens them for low effort.
- Scores and significance tests: `nps-analysis` for NPS, `pmf-survey` for the Sean Ellis question; other
  tables and tests are not this skill.
- Checking the questionnaire for biased wording: `survey-bias-check`.
- General data wrangling of non-survey data: not this skill.
- Deciding whom to reject or pay on a panel: the panel's rules govern that; this skill informs it.

**What this skill does not do,** even though general data cleaners do: it does not fill in missing answers
(imputation), trim or cap outliers, reverse-code items, score scales, recode categories or weight the
sample. A legitimate extreme answer is data. If the user asks for these, say they are separate steps that
come after this one, and do not fold them into the cleaning log.

A skill named in this section may not be installed. If it is missing, say so, name the method the request
needs, and do not stretch this skill to cover it.

## What to ask for

Read the header and a few rows first and propose the configuration. Ask one question only if something
cannot be inferred, usually: "Which columns are attention checks, and what is the correct answer to each?"

| Input | Default when not given |
|---|---|
| Export file | required (CSV; comma, semicolon or tab; UTF-8 or Windows-1252) |
| Rules already fixed (pre-registration, analysis plan, panel contract) | none. If any exist they replace the defaults below |
| Respondent id column | a column named `id`, `respondent_id`, `response_id`, `ResponseId`; else row numbers |
| Duration column | a column named `duration`, `duration_sec`, `Duration (in seconds)`; else the speed check is not run |
| Path or device column, page-time columns | none; use them when the survey branches or page timings exist |
| Grids (same-scale item batteries) | none: the script runs no grid check without `--grid`. You propose them from the header and pass them; confirm them in the answer |
| Attention checks, `column=correct answer` | none; never guess the correct answer. Ask whether skip logic could hide a check (then `--attention-blank unshown`) |
| Open-text columns | none: the script screens no text without `--open-cols`. You propose them from the header and cell contents and pass them |
| Consistency rules | none; propose rules only for answers that are logically linked |
| Duplicate key columns | columns named `email`, `ip`, ...; a shared IP is only a candidate |
| Demographic columns to compare | none; suggest the ones the analysis will break results down by |
| Removal rule | none: flags only. Recommend `count>=2` and let the user decide |

## Steps

1. **Ask about fixed rules, once.** A pre-registered exclusion rule, an analysis plan or a panel contract
   wins over every default here. Use their thresholds and pass `--set-before` with the checks they cover
   (`all`, or names such as `speeder,attention_fail,drop`). Rules chosen now, after seeing the data, are
   post hoc; the log says so, and so must the answer.
2. **Look at the file.** Note the id, duration, grid, attention-check, open-text and demographic columns.
   If the survey branches, list the columns everyone saw (`--item-cols`) and the path column
   (`--speed-by`). A Qualtrics export needs no preparation. A SurveyMonkey export with two header rows
   must be reduced to one row of unique column names first; the script stops and says so.
3. **Run the script with flags only** (no `--drop-if`). Run it by its path inside this skill's folder
   (`<skill-dir>` below is the folder holding this `SKILL.md`), from any working directory. This runs on
   the bundled synthetic fixture; for the user's export, swap the file and the column names:

   ```
   python3 <skill-dir>/scripts/survey_data_cleaning.py <skill-dir>/fixtures/planted.input.csv --out-dir cleaned \
     --grid sat=g1..g6 --grid brand=b1..b4 \
     --attention "ac1=Strongly disagree" --attention ac2=4 \
     --open-cols open_feedback --compare-cols uses_product \
     --rule "exp_gt_age: years_experience > age" \
     --rule 'never_but_sessions: uses_product == "Never" and sessions_per_week > 0'
   ```

   It writes `<name>.flags.csv` and `<name>.cleaning-log.md`, and its first output line says which checks
   ran and which did not. It reads comma, semicolon or tab files in UTF-8 (with or without a byte-order
   mark), UTF-16 with a byte-order mark (Excel "Unicode Text") or Windows-1252, and decimal commas in
   semicolon or tab files. All options, the rule syntax and the file formats:
   [references/usage.md](references/usage.md). The calculation lives in
   [`scripts/survey_data_cleaning.py`](scripts/survey_data_cleaning.py) (Python 3.9+, standard library
   only). Run it; do not redo the checks in the conversation.
4. **Read the sample summary before any single respondent.** Share flagged per check, share with two or
   more flags, flags that occur together, and warnings. A check that flags a large share usually means a
   wrong threshold, a wrong column or a bad sample source, not that many bad people.
5. **Read the candidates.** `open_text_candidate` (too short, no vowels, repeated characters, keyboard
   runs, identical or near-identical text from several respondents), `pattern_candidate` (zigzag,
   staircase), `identical_answers` (every answer the same as an earlier row) and `shared_ip` are
   mechanical screens, not verdicts, and do not count toward removal until confirmed. Read each one in
   context and confirm the ones that are low effort or duplicates (`--confirm R04:open_text_candidate`);
   the log records it. A short survey gives identical answers by chance, and households share an IP. Skim
   unflagged answers for off-topic or machine-written text, which the script cannot detect.
6. **Sanity-check the other flags.** Identical answers on a grid with no reverse-worded item may be
   honest. Clear a flag that is wrong (`--clear R05:inconsistent`, or `--clear row=8:duplicate` for one
   row of a repeated id); the checks table then shows hits, cleared and final counts. Speed is weak
   evidence when the survey asks for facts,
   and a respondent on a short path is fast for a good reason. Platform fraud fields report the
   platform's own settings: a column that is absent is "not present", never "passed", and a reCAPTCHA
   score of 1 is also the default when the check did not run.
7. **Propose a removal rule and wait for the user.** Recommend removing respondents with two or more
   counted flags (`count>=2`), plus what the user confirms (duplicates, `not_screened` previews, tests and
   synthetic rows, a platform flag). One flag alone is not enough: each indicator misclassifies careful
   respondents. The script keeps no state between runs and rewrites the flags file and the log each time,
   so every re-run repeats the whole step 3 command plus every `--clear`, `--confirm` and `--set-before`
   given since. Run the exact proposed rule with `--drop-if "<rule>" --preview --compare-cols ...` and
   show who would go, the share of the sample and the composition table, because removal can shift who
   is in the sample. `--preview` writes no clean file.
8. **Only after the user agrees, re-run with `--drop-if` and without `--preview`.** This writes `export.clean.csv` and
   `export.removed.csv` (removed rows with the reason). The export itself is never changed.
9. **Run key results both ways.** Compute the headline numbers on the full file and on the clean file and
   report both. If they differ in a way that changes the conclusion, say so.

Defaults, each with its source or its label as a convention in
[references/sources.md](references/sources.md):

| Check | Default | Change with |
|---|---|---|
| Speeder | duration below 1/3 of the median (0.5 is the stricter academic variant); with page times, speed index above 2.0 | `--speed-fraction`, `--speed-by`, `--page-time-cols`, `--rsi-cutoff`, `--min-per-item` |
| Straight-liner | every item identical, or zero variability over the answered items, in a grid of 4 or more items | `--longstring-fraction 0.5`, `--longstring-min`, `--min-grid-items` |
| Duplicate | later row repeating an earlier id or email (or a key column the user names) | `--dup-cols` |
| Identical answers, shared IP (candidates) | later row identical to an earlier one in every column but the id; later row with an earlier IP | `--dup-ignore`, `--dup-cols` |
| Attention | 2 failed checks; with only one check, 1 failure (a screening convention); blank = failed unless the check may not have been shown | `--attention-min-fails`, `--attention-blank` |
| Open text (candidates) | under 3 characters, no vowels, a character 4 times in a row, 4 neighbouring keys, the same text of 20+ characters from 2+ respondents, or word overlap of 0.8 or more | `--open-min-chars`, `--repeat-run`, `--keyboard-run`, `--paste-min-chars`, `--similar-text` |
| Inconsistent | the user's rules; a rule states the inconsistency | `--rule` |
| Item non-response | more than 0.5 of question columns blank | `--max-missing`, `--item-cols` |
| Pattern (report only) | repeating block or staircase across a grid of 6 or more items | `--pattern-min-items` |
| Platform fields (report only) | `Q_RecaptchaScore` below 0.5 unless its status is an error; `Q_BallotBoxStuffing` or `Q_DuplicateRespondent` true | `--recaptcha-min` |
| Warning | a check, the 2+ flag group or the removal above 0.12 of respondents | `--warn-share` |

Sources disagree on most cut-offs; the defaults are the ones that flag the fewest people. Several (the
grid minimum, the open-text numbers, the pattern definitions, the warning level) have no published
threshold and are conventions: say so when the user asks where a number comes from. Candidates add to the
flag count only when confirmed; platform fields never do.

## Output

Always in this order:

1. **Summary line:** rows in the file, rows set aside (previews, tests, unfinished), respondents screened,
   and how many have 0, 1, 2+ flags.
2. **How the file was read:** encoding, delimiter, export layout, id and duration columns.
3. **Checks table:** check, rule and threshold used (with the computed median and cut-off), set before
   results (yes / no, post hoc / not stated), hits before review, number and share flagged after review,
   ids, and ids cleared or confirmed. Checks that did not run are
   "not run" with the reason; platform fields without a column are "not present".
4. **Sample summary:** warnings, and the flags that occur together.
5. **Judgement calls:** candidates read, flags cleared, and why.
6. **Removal:** the rule, number and share removed, ids, and who is affected on the compared columns; or
   "no rows removed, flags only".
7. **With and without:** the key results on the full and on the clean file, side by side (after removal).
8. **Files:** paths of the flags file, the cleaning log, and, if rows were removed, the clean and removed
   files.
9. **For the methods section:** one or two sentences stating the checks, thresholds, which were fixed in
   advance, and the counts removed.

## Checks before answering

- Was the original export left unchanged, and are removed rows saved with a reason? (yes)
- Did registered or contracted rules replace the defaults, and is every other rule labelled post hoc? (yes)
- Did the user agree to the removal rule before any `--drop-if` run? (yes)
- Is anyone removed on a single indicator? (no, unless the user chose that, and then it is stated)
- Were candidates (open text, patterns, identical answers, shared IP) read, and only confirmed ones
  counted toward removal? (yes)
- Does the answer state every threshold used, the median, and the count and share removed? (yes)
- Are checks that did not run reported as not run, and absent platform columns as not present? (yes)
- Were previews, tests, synthetic and unfinished rows counted and reported, not silently dropped? (yes)
- Were key results reported with and without the removed rows? (yes, when rows were removed)
- Is each flagged grid long enough, and mixed in direction, for identical answers to be implausible, and
  if not, is that said? (yes)
- If the survey branches, were speed medians computed within the path and never-shown columns left out of
  item non-response? (yes)
- Was a shared IP treated as a hint only, and were emails and IPs kept out of the written answer? (yes)
- Did the answer avoid imputing, trimming, reverse-coding or scoring anything? (yes)

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `responses_export` (a CSV download link for the user to save and screen), `responses_read` (answers with ids), `responses_get_counts` (the base to reconcile against), `report_get` (results on the same filter). Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type (`responseType` `real` excludes synthetic responses) and completion status (`status`), and reconcile the row count with `responses_get_counts` on the same filters before screening. QuestionPunk's own fraud filter is `suspiciousLevel` (`clean` excludes suspected fraud); report it as a platform field, not as this skill's check. Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
