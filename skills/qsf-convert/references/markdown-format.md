# Survey Markdown: the format `qsf_convert.py` reads and writes

One file is one survey. The format is line-based and strict: a line the script cannot place is an error
with its line number, never a guess. `to-md` writes exactly this format, so its output can be edited and
passed back to `to-qsf`.

## Example

```markdown
# Product feedback pulse

## Screener

### used [single] required
Have you used the product in the last 30 days?

- Yes
- No
- Not sure

> skip: if "No" -> end of survey
> skip: if "Not sure" -> role

### features [multi] request
Which features did you use?
Select all that apply.

- Reports & exports
- Other {text}
- None of these {exclusive}

> show if: used is "Yes"

### role [dropdown]
What is your role?

- Researcher
- Designer

---

## Experience

### agree [matrix]
How much do you agree with each statement?

Rows:
- It is easy to use
- It saves me time

Columns:
- Disagree
- Neither
- Agree

### effort [slider]
How much effort did setup take?

- Setup

> range: 1 to 7
> labels: Very little | A great deal
```

A longer example with every type is [`../fixtures/survey.input.md`](../fixtures/survey.input.md).

## Lines

| Line | Meaning | Becomes in the .qsf |
|---|---|---|
| `# Title` | Survey name. Once, before the first block | `SurveyEntry.SurveyName` |
| `> embedded: field` or `> embedded: field = value` | Embedded data, declared after the title and before the first block | One embedded-data element at the start of the flow |
| `## Name` | Starts a block | A block in `BL` (first one `Default`, the rest `Standard`) and a node in the flow `FL`, in file order |
| `### tag [type]` | Starts a question. Optional last word `required` or `request` | One `SQ` element; `tag` is the `DataExportTag`; questions are numbered QID1, QID2, ... in file order |
| Text lines under the heading | Question text. A line break is kept; a blank line is a paragraph break | `QuestionText` (line breaks as `<br>`) |
| `- Option` | An answer option, in display order | `Choices` and `ChoiceOrder`, keys "1", "2", ... |
| `Rows:` / `Columns:` | In a matrix: the statements and the scale points, each followed by `- ` lines | `Choices` / `Answers` |
| `> skip: ...` | Skip logic on this question | `SkipLogic` on the block element |
| `> show if: ...` | Display logic on this question | `DisplayLogic` in the question |
| `> range: 1 to 7` | Slider range, whole numbers (default 0 to 100) | `CSSliderMin`, `CSSliderMax` |
| `> labels: A \| B` | Slider scale labels (any number) or the two NPS end labels | `Labels` / `ColumnLabels` |
| `> total: 100` | The total a `[sum]` question must add up to | `Validation` of type `ChoicesTotal` |
| `> randomize: options` or `> randomize: rows` | Show the options (or the matrix rows) in random order | `Randomization` with type `All` |
| `---` | Page break | `{"Type": "Page Break"}` |
| `<!-- ... -->` | Comment; ignored by `to-qsf`. `to-md` uses comments for what it could not represent | Nothing |

Order inside a question: heading, text, options, then `>` rules. Blank lines between parts are optional.

**Tags** start with a letter or digit and may contain letters, digits, `_`, `.` and `-`. They must be
unique. Rules refer to questions by tag.

## Question types

| Tag | Qualtrics question | Needs |
|---|---|---|
| `[single]` | Multiple choice, one answer, vertical | Options |
| `[multi]` | Multiple choice, several answers, vertical | Options |
| `[dropdown]` | Multiple choice as a dropdown list | Options |
| `[text]` | Text entry, single line | Nothing |
| `[text-long]` | Text entry, multi line | Nothing |
| `[essay]` | Text entry, essay box | Nothing |
| `[form]` | Text entry form, one text field per option | Options (the field labels) |
| `[info]` | Descriptive text; no answer, so no `required` | Nothing |
| `[matrix]` | Matrix table, Likert, one answer per row | `Rows:` and `Columns:` |
| `[matrix-multi]` | Matrix table, Likert, several answers per row | `Rows:` and `Columns:` |
| `[matrix-text]` | Matrix table of short text boxes | `Rows:` and `Columns:` |
| `[slider]` | Horizontal slider, one bar per option | Options (at least one) |
| `[nps]` | Net Promoter Score, always 0 to 10 | Nothing |
| `[rank]` | Rank order, drag and drop | Options |
| `[sum]` | Constant sum, one number per option; no `required` | Options |

`required` forces a response. `request` asks once and lets the respondent continue.

Option marks, at the end of an option line:

- `{text}` adds a write-in box to that option (`[single]` and `[multi]` only).
- `{exclusive}` makes the option clear all others (`[multi]` only).
- `{code:5}` sets the value stored for that option (the Qualtrics recode value). Allowed on the options of
  `[single]`, `[multi]`, `[dropdown]` and on the columns of `[matrix]` and `[matrix-multi]`. Whole numbers,
  all different, and on every option of the question or on none. Without codes, options are coded 1, 2, 3
  in the order written, so `to-md` leaves codes out when they are exactly that.
- `{var:name}` sets the export tag of a matrix row. On every row or on none.

`> randomize: options` works on `[single]`, `[multi]` and `[sum]`; `> randomize: rows` on `[matrix]` and
`[matrix-multi]`.

## Rules

**Skip logic**, on `[single]`, `[multi]` and `[dropdown]` questions:

```
> skip: if "Option text" -> end of block
> skip: if "Option text" -> end of survey
> skip: if "Option text" -> later_tag
> skip: if not "Option text" -> end of block
```

The option text must match one option of that question exactly. `not` means "is not selected". A target
tag must be a later question in the same block, because that is all Qualtrics skip logic can do. A
question may have several skip lines.

**Display logic**, on any question, testing `[single]`, `[multi]` or `[dropdown]` questions:

```
> show if: used is "Yes"
> show if: used is "Yes" or role is not "Designer"
> show if: used is "Yes" and role is "Researcher"
```

One line per question. Join conditions with `and` or with `or`, never both in one rule: mixed grouping is
not in the supported subset, so the script refuses it instead of guessing.

Inside quotes, write `\"` for a double quote and `\\` for a backslash.

## Text

- Text is passed to Qualtrics as HTML. `&` and a bare `<` are escaped for you; an HTML tag you type
  (`<strong>`, `<em>`, `<u>`, a link) passes through unchanged. To show a literal `<b`, write `&lt;b`.
- `to-md` turns `<br>` and `<p>` into line breaks, keeps `<strong>`, `<b>`, `<em>`, `<i>` and `<u>` when
  they have no attributes, removes every other tag and says which in a warning. `--keep-html` keeps all
  tags.
- A text line that would look like another kind of line (it starts with `#`, `- `, `>`, `---`, `Rows:`,
  `Columns:` or `\`) is written with a leading backslash: `\- not an option`.
- An option is one line.

## What the format does not hold

`to-qsf` cannot produce these, and `to-md` reports each one it meets (as a warning, and as a comment at
the place it occurred when it has a place):

- Survey flow other than "embedded data first, then every block once, in order": branches, block
  randomizers, groups, end-of-survey elements, web services, quotas, embedded data set later in the flow or
  with a type other than text.
- Skip logic on text or matrix answers; display logic on embedded data, device, counts, entered text,
  other question types, several groups or mixed `and`/`or`; logic on single choices or rows; in-page logic.
- Question types outside the table above (profile matrix, MaxDiff, timing, file upload, signature,
  graphics, captcha). Horizontal or column layouts of multiple choice and dropdown matrices are read as the
  plain type. A side-by-side question is read as one matrix question per column and cannot be written.
- Choice codes that are not whole numbers or that repeat; codes on rank, slider, form and sum options; row
  ids of a matrix that are not 1..n when the rows have no export tags.
- Randomization other than "all, in random order"; randomization of questions in a block; loop and merge;
  carry-forward choices; default answers; scoring; content validation (number, email, custom); field
  sizes; question JavaScript; translations; custom question labels; notes; survey options and look and
  feel.
- Piped text is kept as written (`${q://QID3/...}`), but questions are renumbered, so check every pipe.

## Which import file: QSF or Advanced Format TXT

`to-qualtrics` writes Qualtrics' documented plain-text format when it can hold the whole survey, and a
`.qsf` otherwise, and prints which and why.

| In the Markdown | TXT | QSF |
|---|---|---|
| `[single]`, `[multi]`, `[dropdown]`, `[text]`, `[essay]`, `[form]`, `[info]`, `[matrix]`, `[matrix-multi]`, `[rank]`, `[sum]` | Yes | Yes |
| Blocks, page breaks, `{code:n}`, `> embedded:` | Yes | Yes |
| `[text-long]`, `[matrix-text]`, `[slider]`, `[nps]` | No tag | Yes |
| `required`, `request`, `> skip:`, `> show if:`, `> randomize:`, `> total:`, `{text}`, `{exclusive}`, `{var:name}` | No tag | Yes |

`--format txt` forces TXT: it refuses the four question types without a tag and lists every other item it
leaves out. `--format qsf` (or `to-qsf`) forces QSF.

## Round trip

- Markdown written by `to-md` and passed through `to-qsf` and `to-md` again comes back byte for byte,
  minus its comments.
- Hand-written Markdown comes back with the same content in canonical spacing: one blank line between
  parts, comments removed.
- A real export does **not** come back identical after `to-md` then `to-qsf`: everything in the list
  above is gone and ids are new. Read the warnings before rebuilding a live survey from Markdown.
