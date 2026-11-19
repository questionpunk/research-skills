---
name: open-ended-coding
description: "Builds a codebook from open-ended survey answers, applies it to every row of a CSV with a definition for every code, counts themes with honest denominators, pulls verbatim quotes with row ids, and checks coder agreement (Cohen's kappa, Krippendorff's alpha) on a double-coded sample, human or LLM. Use for \"code these responses\", \"themes from open-ended answers\", \"thematic analysis of survey comments\", \"categorize or tag free-text feedback\", \"analyze NPS comments or verbatims\", \"inter-rater reliability\" or \"does the LLM coding agree with mine\"."
license: MIT
metadata:
  version: "0.2.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# Open-ended coding

Turns a column of free-text survey answers into a codebook, a coded file, a frequency table with stated
denominators, verbatim quotes with row ids, and a coder-agreement check with confidence intervals.

You do the coding: reading, defining codes, assigning them to every row. The script does the arithmetic
that goes wrong in conversation: [`scripts/open_ended_coding.py`](scripts/open_ended_coding.py) (Python
3.9+, standard library only). Run it; do not redo the math yourself. Run it by its path inside this skill's
directory: the commands below write `scripts/open_ended_coding.py`, meaning
`python3 <skill-dir>/scripts/open_ended_coding.py` from wherever the data is. References:

- [`references/sources.md`](references/sources.md): formulas, thresholds, citations, what is convention.
- [`references/formats-and-briefs.md`](references/formats-and-briefs.md): file formats, the second
  coder's brief, adjudication, the reporting checklist, every script option.
- [`references/llm-coding.md`](references/llm-coding.md): what studies of LLM coders found.

## When to use

Use when the user has open-ended answers, one row per respondent, and asks:

- "Code these responses", "categorize or tag this free-text feedback", "build a code frame".
- "Themes from the open-ended answers", "thematic analysis of survey comments".
- "Analyze the NPS comments / verbatims", "how many people mentioned price".
- "Inter-rater reliability", "what is the kappa between these coders".
- "Does the LLM coding agree with mine", "check the model's tags against my sample".

Do not use it for:

- The NPS score, its interval or trend: `nps-analysis` (it sends the comments here).
- Removing speeders, duplicates and gibberish rows first: `survey-data-cleaning`.
- Writing the question or the interview guide: `survey-from-decision`, `ai-interview-guide`.
- Significance tests between segments, or cross-tabs of closed questions. `counts` cuts code shares by a
  segment with an interval per cell; it does not test the differences.
- Sentiment scoring or topic models. This skill can count a sentiment column you filled; it does not
  score text.
- Weighted estimates. `counts` is unweighted; it takes no survey weight column.

### Which kind of analysis is this?

| The user wants | Do |
|---|---|
| Counts: "how many said what", comparable across waves or segments, many short answers | **Codebook coding** (this skill): fixed definitions, every row coded, agreement measured. |
| Meaning: an interpretive account of a few long interviews, themes developed by one analyst | **Reflexive thematic analysis** (Braun and Clarke). Not this skill: no fixed codebook, no kappa. Say so; offer codebook coding only if counts are what they need. |

Never call this skill's output "Braun and Clarke thematic analysis": they reject agreement statistics
for their method.

A skill named in this section may not be installed. If it is missing, say so, name the method the request
needs, and do not stretch this skill to cover it.

## What to ask for

Start from what the user gave you. Ask one question only if the file or the question wording is missing:
"Which column holds the answers, what exactly were respondents asked, and what decision should the coding
inform?" The question says what is on-topic; the decision says which distinctions the codes must keep.

| Input | Default if not given |
|---|---|
| CSV, one row per respondent, with the answer column | Required. Pasted text: save it as CSV with `id` = line number and say so. |
| Id column | `id`. None in the file: add `id` = row number and say so. |
| Question wording | Required to judge what is on-topic. Use the column header if it is the full question. |
| Decision the coding supports | Ask once; if unknown, say the codebook follows the respondents' own distinctions. |
| Existing codebook | None: build one from a sample. If given, convert it to the fixed format, keep its codes. |
| Codes per response | Every code that applies, each counted once per response. One code only if asked. |
| Nets (parent codes) | None. Add a `parent` column to the codebook if the user wants roll-ups. |
| Segment column | None: overall counts only. |
| Second coder | A person codes the sample blind if one is available; otherwise a fresh-context pass, labelled as such. |
| Double-coded sample | 20% of answered rows, at least 30 (all rows if fewer): `--fraction 0.2 --at-least 30`. |
| Small-base threshold | 30 (`--min-base`): below it, counts only. |
| Seeds | 1 for the codebook sample, 2 for the pilot, 3 for the double-coded sample (a new seed per draw), 1 for the bootstrap. Report them. |

## Steps

The order is fixed: sample, draft codebook, pilot, freeze a version, code everything, double-code,
adjudicate, count. Do not skip or reorder. One exception: when the user brings files that are already
coded and asks only for agreement, start at step 8 (then step 9 if they want the disputes settled) and
report only the summary line, `### Agreement` and `### Caveats`.

1. **Look at the file.** Read the header and some rows; count rows and blanks. Say so if duplicates or
   test rows are visible. Rows are respondents: never drop blank rows, they are a category. Files are read
   as UTF-8 (a BOM is fine); a semicolon, tab or pipe between columns is detected when the header has no
   comma, and `--csv-delimiter` sets it. `--delimiter` (alias `--code-sep`) is the separator between codes
   inside the `codes` cell, not between columns.
2. **Sample** for the codebook: 100 answered rows, or all of them if fewer, in a seeded random order.

   ```bash
   python3 scripts/open_ended_coding.py sample responses.csv --text-col answer --n 100 --all-if-fewer --shuffle --seed 1 --out sample_codebook.csv
   ```

3. **Draft the codebook.** Read the sample top to bottom (the shuffled order) and code it as you go, in
   the respondents' terms: save it as `sample_codebook_coded.csv` with a `codes` column added, every row
   you have read coded. Then check the stopping rule (base of 50 answers, runs of 25 moving one answer at a
   time, stop at 5% new codes or fewer):

   ```bash
   python3 scripts/open_ended_coding.py saturation sample_codebook_coded.csv
   ```

   It refuses rows with no code: an unread row is not evidence. Under 75 rows, pass a smaller `--base`
   and `--run` and say which. If the rule is not met, draw 50 more (`--exclude sample_codebook_coded.csv
   --shuffle`), append them to the end of the coded sample, code them and rerun. Merge codes you cannot
   tell apart; split a code holding two ideas a reader would act on differently. Write one row per code:

   | Column | Content |
   |---|---|
   | `code` | Short upper-case name, no spaces: `PRICE` |
   | `label` | What the reader sees in the table |
   | `definition` | One or two sentences: what the respondent is saying |
   | `include` | Cases that count, especially borderline ones |
   | `exclude` | Near misses, and which code takes them instead |
   | `example_quote` | One answer from the data, word for word |

   A code without `include` and `exclude` is not finished. Reserved codes: `OTHER` (a real answer that
   fits no code), `UNCODABLE` (typed, no usable content), `NO_ANSWER` (blank).
4. **Pilot.** Code 30 fresh answers with the draft and have the second coder (the one step 7 uses) do
   the same, then compare informally. Fix definitions that were read two ways.

   ```bash
   python3 scripts/open_ended_coding.py sample responses.csv --text-col answer --exclude sample_codebook_coded.csv --n 30 --all-if-fewer --seed 2 --out pilot.csv
   ```

   If it reports no eligible answers, the codebook sample used them all: skip the pilot, say so, and let
   the double-coded sample in step 7 be the first test.
5. **Freeze version 1.** From here every change is a new version with a line in the change log, and
   **any change to a definition means recoding every row it could affect** and re-testing agreement.
6. **Code every row** in batches small enough that you read each answer in full; with thousands of rows
   keep going batch by batch, and never swap reading for keyword rules. For each batch write `id,codes`
   (`;` between codes) to a batch file, blank answers included as `id,NO_ANSWER`; never retype the
   answers. An LLM coder may add a `rationale` column (the words that triggered each code, see
   [`references/llm-coding.md`](references/llm-coding.md)); `merge` ignores it. Assign every code whose
   definition is met; `exclude` decides borderline cases; never invent a code mid-pass (use `OTHER`);
   `UNCODABLE` and `NO_ANSWER` stand alone. Answers in another language are coded in that language. Counts
   come from the fully coded file, never from the sample. Merge the batches by id, then validate against
   the original file until clean:

   ```bash
   python3 scripts/open_ended_coding.py merge responses.csv --adjudicated batch_01.csv --adjudicated batch_02.csv --final-col codes --out coded.csv
   python3 scripts/open_ended_coding.py validate coded.csv --codebook codebook.csv --text-col answer --source responses.csv
   ```

   `--source` confirms that every respondent is in the coded file with the same answer text. Fix the rows
   it lists; do not edit the codebook to make errors disappear.
7. **Double-code a blind sample** of answers that neither built nor piloted the codebook (the output
   holds only id and answer; `--stratify-col` spreads the draw over segments):

   ```bash
   python3 scripts/open_ended_coding.py sample coded.csv --text-col answer --exclude sample_codebook_coded.csv --exclude pilot.csv --fraction 0.2 --at-least 30 --seed 3 --out sample_second.csv
   ```

   The share is of the answers not excluded; report the sample's share of all answered rows. If it draws
   fewer than 30 (a small file), rerun without the `--exclude` options and say in the report that the
   agreement sample overlaps the rows used to build the codebook. Never reuse an earlier seed on the same
   file: the draw would repeat the codebook sample.

   `--top-up-min 5 --top-up-out audit_rare.csv` also writes rows for rare codes to a separate audit file.
   They are chosen from your codes, so they are coded blind too but kept out of kappa and alpha: read
   them only for disagreements.

   - **A person is available:** stop here and hand them `sample_second.csv`, `codebook.csv` and the
     [brief](references/formats-and-briefs.md#brief-for-a-blind-second-coder); they code it without
     seeing your codes, and you continue when they return it. This is the only check that says whether a
     model's reading matches a human's.
   - **No person:** give the [brief](references/formats-and-briefs.md#brief-for-a-blind-second-coder),
     the codebook and the sample to a fresh context that has seen neither
     this conversation nor your codes: a subagent, or where the client has none, a new chat or session
     given only those three files. If neither is possible, say the second pass was not blind. **An LLM
     coding twice is not double coding**: it shows whether the definitions can be applied consistently,
     nothing more. Label it "same-model second pass" everywhere and recommend a human check before a
     decision that rests on a close count.
8. **Compute agreement** and write out the disputed rows:

   ```bash
   python3 scripts/open_ended_coding.py agreement coded.csv second_coded.csv --sample sample_second.csv \
     --codebook codebook.csv --text-col answer --disagreements disagreements.csv \
     --coder-info "claude-run1,llm,MODEL" --coder-info "anna,human" --codebook-version v1
   ```

   With a person's coding as the reference, pass it as `--gold human.csv` (listed first in
   `--coder-info`) to add precision, recall and F1 per code. Three or more files give alpha per code and
   a pairwise kappa table. Read the result per code, with its interval:
   - kappa under 0.60 or alpha under 0.667: revise the code (tighten, merge or split), new version,
     recode, test again on a fresh sample (`--exclude sample_second.csv`);
   - alpha from 0.667 to 0.800, or an interval that crosses a band (marked `*`): report as tentative;
   - "not tested": neither coder used the code in the sample. Say so; do not report it as agreement;
   - "on every row": every coder gave the code to every answer, so kappa and alpha are undefined. Report
     the percent agreement and say the sample could not test the code;
   - "high agreement, low kappa": a rare code. Judge it on positive agreement and the disputed rows.

   Agreement is kappa or alpha with percent agreement beside it. Chi-square, Pearson's r and Cronbach's
   alpha are not agreement measures; do not report them as inter-rater reliability.
9. **Adjudicate.** For each row in `disagreements.csv`, decide the final codes by the codebook (a person
   decides when one is involved) and fill `final_codes`. Then:

   ```bash
   python3 scripts/open_ended_coding.py merge coded.csv --adjudicated disagreements.csv --out coded_final.csv
   ```

   Agreement figures stay as measured before adjudication.
10. **Count**, and read the codebook health section it prints:

    ```bash
    python3 scripts/open_ended_coding.py counts coded_final.csv --codebook codebook.csv --text-col answer --segment-col plan
    ```

    Use the numbers as printed. `--` means the base is under the threshold: report "7 of 17" and do not
    compare segments flagged `SMALL BASE`. If health flags `OTHER`, a code on most answers, or two codes
    that mostly occur together, fix the codebook (new version, recode) before reporting. Report nets
    from the nets table, never by adding code counts.
11. **Pick quotes.** For each top code choose 2–3 answers that show its range. Copy them word for word
    with the row id into `quotes.csv` (`id,code,quote`) and check them. Trim with "..." only at the ends
    (the check ignores them there); never join two answers.

    ```bash
    python3 scripts/open_ended_coding.py validate coded_final.csv --codebook codebook.csv --text-col answer --source responses.csv --quotes quotes.csv
    ```

    After the check, replace names, emails and phone numbers with `[name]`, `[email]`, `[phone]` in the
    quotes and in the codebook's example quotes you show, and say quotes were redacted.

Exit code 2 means bad input: fix the cause the message names. `--json` works on every subcommand.

## Output

Always this shape, in this order (an agreement-only request: the summary line, `### Agreement` and
`### Caveats`).

```markdown
## Open-ended coding: "<question wording>"

**<Top code label>: 7 of 17 who answered.** <One sentence on what the table shows and how firm it is.>
(With 30 or more who answered: "<n> of <base> (<x>%, 95% interval <low> to <high>)".)

Data: <file>, answer column `<name>`. 20 respondents; 17 answered, 3 blank (No answer); 2 of the answers uncodable.
Method: codebook v<k> built from a random sample of <n> answers (seed <s>), applied to every row.

### Codebook (v<k>)
| Code | Label | Definition | Include | Exclude | Example quote |

### Frequencies
| Code | n | % of all respondents (N) | % of those who answered (n) | 95% interval |
| ... / Other / Uncodable |
Responses can carry several codes, so shares add up to more than 100%. <Small-base note.>
<Nets, if any: | Net | Codes | n | % of those who answered | 95% interval |, from the nets table.>

### By <segment> (only if asked)
| Code | <segment A> n (%, 95% interval) of <base> | <segment B> n (%, 95% interval) of <base> | Note |

### Quotes
**<Label>** (n = 7)
- "<verbatim>" (row 12)

### Agreement
Coders: <id, human or LLM with model>; <id, ...>. Codebook v<k>. <m> answers double-coded (<x>% of
answered), drawn at random (seed <s>). Disagreements resolved by <who, how>.
| Code | Used by A / B | % agreement | Kappa (95% interval) | Alpha (95% interval) | Reading |
<For rare codes add positive agreement, negative agreement and PABAK; with --gold, precision, recall, F1.>
Lowest code: <code>, kappa <k>. <Codes revised and re-tested; codes not tested; tentative codes.>

### Caveats
- <Open-ended answers come from those who chose to type; blanks are not "no opinion".>
- <Same-model second pass, if so. Small bases. Translation. Redaction. Model and prompt for LLM coding.>
- Files: codebook.csv, coded_final.csv, quotes.csv, second_coded.csv, disagreements.csv.
```

## Checks before answering

Coding and counts:

- Does every code have a definition, include, exclude and an example quote from the data?
- Did `validate --source` finish with 0 errors on the final file, after the last codebook change?
- Is every row coded, including blanks (`NO_ANSWER`) and non-answers (`UNCODABLE`)?
- Does every percentage name its base, with both bases shown (all respondents, those who answered)?
- Is it stated that multi-code shares add up to more than 100%, and are nets counted once per respondent?
- Is every percentage on a base under 30 replaced by a count, including in segment columns?
- Are all numbers copied from the script output, none computed in conversation?
- Was `OTHER` re-read, is it shown in the table, and were the health flags dealt with or reported?
- Is each quote word for word with its row id, and did `validate --quotes` pass before redaction?
- If the codebook changed after coding started, were the affected rows recoded and agreement re-tested?

Agreement report (state each of these):

- The measure (Cohen's kappa, Krippendorff's alpha) and that it is per code on present/absent?
- Who the coders were: person or LLM, and for an LLM the model and where the prompt is kept?
- How many answers were double-coded, what share that is, and how they were drawn (and that rare-code
  audit rows, if any, are outside the figures)?
- The value per code with its 95% interval, and the lowest code, not only a mean?
- How disagreements were resolved, and that the figures are from before resolution?
- That a same-model second pass is called that, and codes with undefined kappa are "not tested" or "on
  every row"?
- That bands are conventions (Landis and Koch call theirs arbitrary), quoted with the interval?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `survey_list` and `survey_get` (find the survey and its open-ended question), `responses_get_counts` (expected total), `responses_read` and `report_load_more_answers` (the answers to code), `responses_export` (a file of all responses). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.

Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type and completion status (exclude synthetic and test responses), and reconcile the row count before coding.
