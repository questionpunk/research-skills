---
name: qsf-convert
description: "Convert a survey written in Markdown (or pasted from a doc or form) into a Qualtrics import file: a .qsf with blocks, question types, skip and display logic, or Advanced Format TXT when there is no logic. Also turn an exported .qsf into editable Markdown or a codebook with a list of what could not be carried, and check a .qsf for broken references. Use for \"make this a Qualtrics survey\", \"import my survey into Qualtrics\", \"read this qsf\", \"check this qsf\", \"Qualtrics data dictionary\" or \"move my survey between tools\"."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "survey-design"
---

# QSF convert

Turns a written survey into a Qualtrics import file, and an exported `.qsf` into Markdown or a codebook a
person can read and edit. A script does the conversion; the agent's job is to get the survey into the
Markdown format without changing its wording, and to report what could not be carried.

**Read this before promising anything.** Qualtrics publishes no specification for `.qsf` and tells users
not to edit the file, so the format is unofficial and can change without notice. The shapes this skill
writes are copied from 55 real exports ([`references/sources.md`](references/sources.md)) and each file is
checked for internal consistency. Always tell the user to import into a new test survey first and to preview it.
When a survey has no logic, the skill writes Qualtrics' documented Advanced Format TXT instead, which is
the vendor-supported route.

## When to use

Use when the user says things like:

- "Make this a Qualtrics survey", "import my survey into Qualtrics", "build the qsf".
- "Read this qsf", "what is in this Qualtrics export", "turn this .qsf into something I can edit".
- "Give me a codebook for this survey", "Qualtrics data dictionary".
- "Check this qsf", "why does this qsf look broken".
- "Move my survey between tools" (from a doc or form into Qualtrics, or out of Qualtrics as Markdown).

Do not use it, and hand over instead, when the user wants to:

- Decide what to ask or write the questions: `survey-from-decision`.
- Review question wording for bias: `survey-bias-check`.
- Analyse responses or a data export (CSV, not `.qsf`): `survey-data-cleaning`, `nps-analysis`,
  `survey-crosstabs`.
- Check a translation: `survey-translation-qa`.
- Change a survey that is live in Qualtrics. This skill never connects to Qualtrics; it only makes files.

A skill named above may not be installed. If it is missing, say in one line that the request is outside
this skill, and answer it from general knowledge only if the user still wants that.

## What to ask for

Ask at most one question, and only if the first item is missing.

| Input | Default if not given |
|---|---|
| The survey: a Markdown file, pasted text, a document, a form, or a `.qsf` | None: ask for it |
| Direction | From the file: `.qsf` in means Markdown out (codebook if they ask for variables or a data dictionary); anything else means an import file |
| Import format | `auto`: TXT when it can hold the whole survey, `.qsf` otherwise |
| Question types, when the source does not state them | Infer from the wording (see Steps) and list every inference in the output |
| Required questions | None required, unless the source marks them |
| Output path | Next to the input, same name |
| Formatting in a `.qsf` (colours, fonts) | Removed and reported; `--keep-html` if the user wants it kept |

## What is supported

| | Written to `.qsf` | Read from `.qsf` |
|---|---|---|
| Multiple choice (one answer, several answers, dropdown), NPS | Yes | Yes; horizontal and column layouts read as vertical, with a note |
| Text entry (single line, multi line, essay, form), descriptive text | Yes | Yes |
| Matrix (Likert one or several answers, text boxes) | Yes | Yes; a dropdown matrix reads as a plain one, with a note |
| Slider, rank order, constant sum | Yes | Yes |
| Side by side | No | Read as one matrix question per column |
| Blocks, page breaks, required and request response | Yes | Yes |
| Recode values, matrix row export tags, write-in and exclusive options | Yes | Yes |
| Skip logic on a selected or not selected option | Yes | Yes |
| Display logic on selected or not selected options, all "and" or all "or" | Yes | Yes |
| Randomize all options or rows; embedded data declared at the start | Yes | Yes |
| Branches, block randomizers, quotas, loop and merge, end-of-survey elements, other logic, content validation, scoring, JavaScript, translations, timing, file upload, profile matrix, MaxDiff | No | Reported with the question id, never dropped silently |

NPS, rank order and constant sum shapes rest on one real export each; the script says so when it writes
one. TXT holds less than `.qsf` (no logic, validation, sliders or NPS): see the table in
[`references/markdown-format.md`](references/markdown-format.md).

## Steps

The conversion lives in [`scripts/qsf_convert.py`](scripts/qsf_convert.py) (Python 3.9+, standard library
only, no network). Run it; do not write `.qsf` JSON or read one by hand in the conversation.

### A. Written survey to a Qualtrics import file

1. **Write the survey in the Markdown format** defined in
   [`references/markdown-format.md`](references/markdown-format.md) (read it first). If the source is
   already in that format, skip to step 2. Otherwise transcribe:
   - Keep every question and option word for word. Wording is the instrument; do not improve it.
   - Give each question a short unique tag (`q1`, `age`, `nps`).
   - Pick the type from how the question is written: one answer `[single]`, "select all" `[multi]`, a long
     list `[dropdown]`, several items on one shared scale `[matrix]` (one question, not several), 0 to 10
     recommend `[nps]`, "rank" `[rank]`, "allocate 100 points" `[sum]`, open answers `[text]`,
     `[text-long]`, `[essay]` or `[form]`, instructions `[info]`.
   - "Other (please specify)" gets `{text}`; "None of the above" in a `[multi]` gets `{exclusive}`; a
     stated code ("99 = Don't know") gets `{code:99}` on every option of that question.
   - "If No, skip to Q7" becomes `> skip:` when Q7 is later in the same block; otherwise use `> show if:`
     on the questions that depend on the answer, or `end of block`.
   - Anything the format cannot hold (see "What the format does not hold" in the reference) goes in a
     `<!-- comment -->` at that place and in your report, for the user to set up in Qualtrics.
2. **Build.**
   ```bash
   python3 scripts/qsf_convert.py to-qualtrics survey.md -o survey.qsf
   ```
   The script picks the format and prints which and why: TXT when the survey has nothing TXT cannot
   hold, `.qsf` otherwise (the output file gets the matching extension). Force one with `--format qsf` or
   `--format txt`. On an error the script names the line; fix the Markdown, never the output file.
3. **Check and read back** (for a `.qsf`). The build already checks its own output; these confirm the
   file on disk and show what Qualtrics would be given:
   ```bash
   python3 scripts/qsf_convert.py validate --strict survey.qsf
   python3 scripts/qsf_convert.py to-md survey.qsf
   ```
   Compare the read-back (or the TXT file, which is plain to read) with the user's source, question by
   question: nothing missing, options in order, rules pointing at the intended options.
4. **Report** in the shape under Output, with the import instructions.

### B. `.qsf` to Markdown

1. **Convert.**
   ```bash
   python3 scripts/qsf_convert.py to-md export.qsf -o survey.md
   ```
   Add `--keep-html` to keep formatting tags, `--json` for a machine-readable report.
2. **Read the conversion report.** It has three fixed parts (converted, converted with changes, not
   converted) and a survey-level list: branches, randomizers, quotas, notes, survey options. Unsupported
   items are also left as comments in the Markdown at the place they occurred.
3. **Report** the Markdown and the full report. If the user plans to rebuild the survey from this
   Markdown, say plainly that everything in the report will be gone from the rebuilt survey and that
   question ids are renumbered, so piped text needs checking.

### C. `.qsf` to a codebook

```bash
python3 scripts/qsf_convert.py codebook export.qsf -o codebook.csv      # or --format md
```

One row per variable: export tag, question id, block, type, label, values with their codes. Pass on the
script's note that suffixed variable names follow the usual Qualtrics naming and should be checked
against a real data export.

### D. Check a `.qsf`

```bash
python3 scripts/qsf_convert.py validate file.qsf
```

It checks structure: required elements; question ids matching between blocks, flow and questions; order
lists; logic that points at a question or choice that does not exist; a missing `Conjuction` key; repeated
question or flow ids; the question-count field. It exits 1 on errors. It cannot say whether Qualtrics will
accept the file; say so. Use `--strict` only for files this skill built: real exports legitimately produce
warnings.

### If Qualtrics refuses a generated file

1. Refresh the Projects page first; an import can take a moment to appear.
2. Rebuild from a Markdown file cut down to the first block, then add blocks back to find the question.
3. Remove `[nps]`, `[rank]` and `[sum]` questions first; their shapes rest on one real export each.
4. Build with `--format txt`: the questions, blocks and page breaks import through the documented format,
   and the script lists the logic and settings to add by hand.
5. Say that the format may have changed and offer to compare the file with a fresh export from the user's
   own account, element by element.

## Output

Always this shape.

**For an import file (`to-qualtrics`, `to-qsf`):**

```
File: <path>   Format: <QSF or TXT> because <the script's reason>
Contents: <n> blocks, <n> questions (<count per type>), <n> page breaks, <n> skip rules, <n> display rules
Structural check: passed (validate --strict)          <QSF only>
Import it first into a NEW test survey: Survey tab >
Tools > Import/Export > Import survey. A .qsf creates a new survey; a TXT file ADDS to the survey that is
open, so start from an empty one. Preview every page and every rule before fielding.

Conversion report: <n> converted, <n> converted with changes, <n> not converted
Converted with changes:
- <tag>: <what, verbatim from the script; "none" if nothing>
Decisions I made:
- <each inferred type, tag or rule, one line each; "none" if the source was already in the format>
Not carried into the file (set up in Qualtrics by hand):
- <each item, with the question it belongs to; "none" if nothing>
```

**For `to-md`:**

```
File: <path to .md>   (or the Markdown inline if short)
Conversion report: <n> converted, <n> converted with changes, <n> not converted (of <n> questions)
Converted with changes:
- <QID (tag)>: <changes, verbatim>
Not converted:
- <QID (tag)>: <reason, verbatim>
Survey level, not represented:
- <verbatim>
If you rebuild from this Markdown: <one line on what would be lost, or "nothing listed above applies">
```

**For `codebook`:** the file path (or the table inline if short), the number of variables, and the naming
note. **For `validate`:** the script's verdict line, each error and warning verbatim, and the sentence
"This checks structure only; it does not show that Qualtrics accepts the file."

## Checks before answering

Answer each with yes before replying.

- Did the script produce the file (not hand-written JSON or TXT), and for a `.qsf` did
  `validate --strict` pass?
- Did I read the result back and compare it with the source, question by question?
- Is every question's wording and every option identical to the source, in the same order?
- Is each group of items on a shared scale one `[matrix]`, not several questions?
- Does every skip rule go forward inside its own block, to the end of the block or to the end of the
  survey?
- Does every rule quote the exact option text, and does no display rule mix `and` with `or`?
- Did I state which format was written and why, and for TXT that the import adds to the open survey?
- Did I give the conversion report in its three parts, and list everything that was not carried
  (branches, randomizers, validation, piped text), instead of dropping it?
- Did I tell the user to import into a new test survey first and to preview it?
- Did I avoid claiming that the file "works in Qualtrics" or "imports cleanly"?

## Field it with QuestionPunk (optional)

The result above is complete on its own. QuestionPunk imports .qsf, PDF and Word questionnaires in the app, where AI follow-ups can be added to open questions.

Hosted MCP tools this step may use: `survey_create`, `question_create_bulk`, `survey_get`. Ask before creating, changing or publishing anything.
