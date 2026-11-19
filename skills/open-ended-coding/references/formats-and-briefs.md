# File formats, logs and briefs

Detail for [`../SKILL.md`](../SKILL.md). Sources for every number: [`sources.md`](sources.md).

## Files

| File | Columns | Notes |
|---|---|---|
| Responses | an id column, an answer column, optional segment columns | One row per respondent. If there is no id column, add `id` = row number before anything else and tell the user. UTF-8; columns separated by commas, or by `;`, tab or pipe (detected when the header has no comma, or set with `--csv-delimiter`). Output files use commas. |
| Batch of codes | `id,codes`, optionally `rationale` | What you write while coding (step 6): codes only, never the answer text; a blank answer gets `NO_ANSWER`. An LLM coder's `rationale` (the words that triggered the codes) is ignored by `merge` and never goes to the second coder. `merge responses.csv --adjudicated batch_01.csv --adjudicated batch_02.csv --final-col codes --out coded.csv` adds the `codes` column by id. |
| Codebook | `code,label,definition,include,exclude,example_quote` and optionally `parent` | Fixed. One row per code. `OTHER` and `UNCODABLE` may be listed with a label and definition only. `parent` names a net (a roll-up of codes); a net's name must not be a code. |
| Coded file | the responses file plus `codes`, optionally `sentiment` | Codes separated by `;`. Alternative: one 0/1 column per code with a common prefix (`--code-prefix code_`) or listed (`--code-cols`). `sentiment`, if you fill it, holds one of positive, negative, neutral, mixed per codable answer (`counts --sentiment-col`); the script counts it and never computes it. |
| Disagreements | `id,text,codes_A,codes_B,...,in_dispute,final_codes` (the id column keeps the name given with `--id-col`) | Written by `agreement --disagreements`. Fill `final_codes`, then `merge`. |
| Quotes | `id,code,quote` | The quotes that will appear in the report. Checked word for word against the answer in that row. |
| Second coder's file | `id`, the answer, `codes` | Starts as the output of `sample` (id and answer only). |

Codes are case-sensitive. Use short upper-case names without spaces (`PRICE`, `SLOW_SUPPORT`) and never
the code separator or a comma inside a code: a cell `"PRICE, SPEED"` is refused, because without a
codebook it would otherwise count as one new code. With several codes in one cell, the CSV holds
`4,The app is slow and the price went up,SPEED;PRICE` (quote the cell only if it contains a comma).

### Reserved codes

| Code | Meaning | Rule |
|---|---|---|
| `NO_ANSWER` | The answer is blank. | Never combined. With `--text-col`, a blank answer with no code is counted as `NO_ANSWER` automatically. |
| `UNCODABLE` | Something was typed but it has no usable content: "n/a", ".", "asdf", an answer to a different question, text in a language nobody on the project can read. | Never combined. Counted inside "answered", shown on its own line. |
| `OTHER` | A real answer that fits no code. | May be combined with a code when one part of the answer fits and another does not. |

"Nothing", "none" and "no" are answers when the question was "what would you change?": give them a real
code such as `NOTHING_TO_CHANGE`, not `UNCODABLE`. `validate` warns when an answer that is only "none",
"n/a", "idk" or similar carries a substantive code, so a person looks; it does not check "nothing" or "no".

## Saturation log

`saturation coded_sample.csv` prints this log from the coded codebook sample, rows in the order you read
them (draw the sample with `--shuffle` so that order is random, not the export's order by date). Base =
the first 50 answers; a run = the next 25, and the run moves forward one answer at a time, as in Guest et
al. (2020). A code is new in a run when it first appears in one of the run's rows. Stop adding codes when
a run's new codes are at most 5% of the codes found in the base (with fewer than 20 base codes that means
no new code). For a smaller sample pass `--base` and `--run` (the file must hold at least one base and
one run) and say which values you used; `--step 25` gives non-overlapping runs. Reserved codes are not
counted as new codes. Every row must carry a code: an uncoded row stops the command, since an unread
answer cannot show that nothing new turned up. With `--text-col`, blank answers count as `NO_ANSWER` and
are skipped (they cannot show a new code); `--codebook` checks the codes against the codebook.

| Batch | Answers read | New codes | Codes so far | New ÷ base codes |
|---|---|---|---|---|
| Base | 1–50 | 9 | 9 | |
| Run 1 | 51–75 | 2 | 11 | 22% |
| Run 2 | 52–76 | 2 | 11 | 22% |
| ... | | | | |
| Run 13 | 63–87 | 0 | 11 | 0%: stop; saturation at answer 62 (+25) |

If no run meets the rule, draw 50 more answers (`sample --exclude` the earlier sample `--shuffle`),
append them in their drawn order to the end of the coded sample, code them and rerun. If the file is
exhausted first, say that saturation was not reached and the codebook covers what was there.

## Codebook change log

Keep this next to the codebook. Any change to a definition after coding started means recoding every row
that could be affected, and re-testing agreement on a fresh sample.

| Version | Change | Reason | Rows recoded |
|---|---|---|---|
| v1 | 11 codes frozen after the sample | | |
| v2 | `SUPPORT` split into `SLOW_SUPPORT` and `RUDE_SUPPORT` | kappa 0.48; coders disagreed on tone versus delay | all rows coded `SUPPORT` |
| v3 | `PRICE` include: "the price went up" counts; exclude: "not worth it" with no mention of cost goes to `VALUE` | Row 4 ("The app is slow and the price went up") was coded `PRICE` by one coder and not by the other; the decision the coding supports is a pricing change, so a price rise must count | all rows coded `PRICE` or `VALUE` |

Write each borderline decision like v3: the row that raised it, what was decided, and why, in terms of
the decision the coding supports. The next coder reads these lines with the codebook.

## Brief for a blind second coder

Give the second coder (a person, or a fresh agent context with no access to this conversation) exactly
this and two files: the codebook and the sample from `sample` (id and answer only).

```text
You are the second coder on a set of survey answers. Work alone; do not ask what the first coder did.

Question the respondents answered: "<question wording>"
Files: codebook.csv (code, label, definition, include, exclude, example_quote) and sample.csv (id, answer).

For every row of sample.csv, add a column `codes`:
- Assign every code whose definition the answer meets. Separate codes with ";". A code counts once per
  answer however often the theme is mentioned.
- Use only codes from the codebook. Do not invent, merge or rename codes.
- Follow `include` and `exclude` literally. When an answer is on the border, the `exclude` text decides.
- A real answer that fits no code: OTHER. No usable content ("n/a", gibberish, off-topic): UNCODABLE.
  A blank answer: NO_ANSWER. UNCODABLE and NO_ANSWER are never combined with another code.
- Every row gets at least one code. Do not skip rows and do not change the id or the answer.

Return sample.csv with the `codes` column filled, and a separate list of ids where you hesitated, with
the two codes you were choosing between.
```

The list of hesitations is the most useful part: it points at the definitions to tighten.

## Disagreement review

After `agreement`, list the rows where the code sets differ, with both codings side by side. For each code
flagged for revision, read its disagreements and write one sentence on the cause:

- the definition is vague → rewrite `definition`, add the disputed case to `include` or `exclude`;
- two codes overlap → merge them, or move the boundary in both `exclude` fields;
- the code hides two ideas → split it;
- one coder missed a second theme in long answers → remind both of the "every code that applies" rule.

Then bump the codebook version, recode, and test again on a fresh sample.

## Adjudication

1. `agreement ... --disagreements disagreements.csv` writes one row per response whose code sets differ:
   the answer (with `--text-col`), each coder's codes, the codes in dispute and an empty `final_codes`.
2. Decide each row by the codebook, not by who coded it. When a person is one of the coders, the person
   decides, or two people discuss; a model does not adjudicate its own disagreement with a person.
   A row that cannot be decided from the codebook is a codebook problem: fix the definition (new
   version, recode) instead of forcing a choice.
3. Fill `final_codes` (the full final code set of the row, `;` between codes).
4. `merge coded.csv --adjudicated disagreements.csv --out coded_final.csv` writes the decisions back.
   Rows with an empty `final_codes` stop the merge unless `--allow-pending`.
5. Report agreement as measured before adjudication, and say how disagreements were resolved.

## Reporting checklist for agreement

| Item | State |
|---|---|
| Measure | Cohen's kappa and/or Krippendorff's alpha, per code on present/absent; percent agreement beside it |
| Coders | How many; each one a person or an LLM; for an LLM the model, date, where the prompt is kept and whether a rationale was requested; whether the second coder was blind to the first coding |
| Sample | How many answers were double-coded, what share of answered rows, how drawn (random, seed, stratified, topped up for rare codes) |
| Values | Per code with the 95% interval; the lowest code; codes not tested; the bootstrap settings |
| Reading | The thresholds applied and that they are conventions |
| Disagreements | How resolved (who decided), and that the figures are pre-resolution |
| Codebook | Version tested; changes made after the test and whether the test was repeated |
| Reference coder | With `--gold`: who the reference is, and precision, recall, F1 per code |

## Script options by subcommand

| Subcommand | Options beyond `--id-col`, `--codes-col`, `--delimiter`, `--json` (and `--code-cols` / `--code-prefix` for 0/1 columns, in `saturation`, `validate`, `counts` and `agreement`) |
|---|---|
| `sample` | `--text-col` (required), `--n` (with `--all-if-fewer`: take all when fewer) or `--fraction` (with `--at-least N`: never fewer than N, or all), `--seed`, `--shuffle` (seeded random row order), `--exclude FILE` (repeatable), `--include-blank`, `--stratify-col` (proportional allocation), `--top-up-min K --top-up-out FILE` (a rare-code audit: extra rows, picked from the first coder's codes, written apart from the random sample; not used for kappa or alpha), `--all-columns`, `--out` |
| `saturation` | `--base`, `--run`, `--step` (default 1), `--threshold`, `--text-col`, `--codebook` |
| `validate` | `--codebook` (required), `--text-col`, `--source FILE` (every respondent coded once, same answer text), `--source-text-col`, `--quotes FILE` (`...` or `…` at either end is allowed) |
| `counts` | `--codebook`, `--text-col`, `--segment-col`, `--min-base`, `--mentions` (share of code assignments), `--sentiment-col`, health check: `--rare-below`, `--broad-above`, `--other-above`, `--top-pairs` |
| `agreement` | two or more files, or `--gold FILE` plus one or more; `--codebook`, `--text-col`, `--sample FILE` (compare on the sample's ids; each coder must have coded all of them), `--coder-info ID,human` / `ID,llm,MODEL` (once per coder, gold first), `--codebook-version`, `--bootstrap N` (0 = off), `--seed`, `--allow-unmatched`, `--disagreements FILE` |
| `merge` | `--adjudicated FILE` (repeatable; adds the codes column when the input has none), `--out FILE`, `--final-col`, `--codebook`, `--allow-pending` |

Every subcommand takes `--csv-delimiter` (the column separator of the files it reads; a file whose
header does not contain it, such as a comma file this script wrote, is still detected). `--delimiter`,
alias `--code-sep`, is the separator between codes inside one cell. No output file may be one of the
inputs. With `--text-col`, `agreement` stops when the same id carries different answer text in two files
(or in the `--sample` file): the coders did not see the same answer.

`counts` gives a Wilson 95% interval for each share of those who answered, overall and per segment cell.
It does not test differences between segments, and it is unweighted.
