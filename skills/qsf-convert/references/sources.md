# QSF convert: sources and evidence

Checked on 2026-11-12; corrections and the codebook and logic additions marked 2026-11-19.

Contents: what Qualtrics says; file structure; Advanced Format TXT; question types; other shapes; codebook;
measured on the 55 exports; sources; sample set; where practitioners disagree; pitfalls. Qualtrics publishes no schema for the QSF format, so there is no primary
specification to cite. The facts below come from three kinds of evidence, in this order of weight:

1. **Real exports.** 55 `.qsf` files written by Qualtrics and published in public GitHub repositories
   (1,595 question elements). Every structural fact marked "exports" was measured on this set. The files
   were only read; none is redistributed here (see "Sample set").
2. **Open-source code that reads or writes QSF** and is used in practice.
3. **Qualtrics' own support pages**, for what the product does (not for the file format).

The structural check in
the script (`validate`) proves that a file is internally consistent and shaped like the exports. It cannot
prove that Qualtrics accepts it.

## What Qualtrics says

- QSF export contains "all of your survey formatting and settings" and no responses; questions in the
  trash are included. Import always creates a new survey (Survey tab, Tools, Import/Export, Import survey;
  or a new project from a file).
- "Do not edit the QSF file! Editing the file can corrupt the contents and make it unable to upload to your
  account." Generating a file is a stronger form of what this warning covers. That is why the skill tells
  the user to import into a test survey first.
- Qualtrics documents one plain-text import format, TXT with `[[AdvancedFormat]]` tags (MC, Matrix, TE, CS,
  RO, DB, blocks, page breaks). It is the documented fallback when a generated QSF is refused. It has no
  tags for skip logic or display logic.
- Skip logic "can only be used to send respondents forward in the survey, not backward", and only "to
  questions within the same block", to the end of the block or to the end of the survey. To reach another
  block, skip to the end of the block and use branch or display logic.

Sources: [Import and export surveys](https://www.qualtrics.com/support/survey-platform/survey-module/survey-tools/import-and-export-surveys/),
[Skip logic](https://www.qualtrics.com/support/survey-platform/survey-module/question-options/skip-logic/).

## File structure and where each fact comes from

| Fact | Evidence |
|---|---|
| Top level is a JSON object with exactly `SurveyEntry` and `SurveyElements` | Exports: 55 of 55. Testa guide |
| `SurveyEntry` carries 17 keys: SurveyID, SurveyName, SurveyDescription, SurveyOwnerID, SurveyBrandID, DivisionID, SurveyLanguage, SurveyActiveResponseSet, SurveyStatus, SurveyStartDate, SurveyExpirationDate, SurveyCreationDate, CreatorID, LastModified, LastAccessed, LastActivated, Deleted | Exports: all 17 keys in 55 of 55. Unset dates are `0000-00-00 00:00:00`; Deleted is null in 55 of 55 |
| `SV_`, `RS_` and `UR_` ids have 15 letters or digits after the prefix | Exports: 55 of 55 (one file has `UR_PLACEHOLDER`). Block ids vary in length in exports (353 of 468 have 15); the script writes 15 everywhere |
| Each element has SurveyID, Element, PrimaryAttribute, SecondaryAttribute, TertiaryAttribute, Payload | Exports: all elements. Testa guide |
| `BL` (PrimaryAttribute "Survey Blocks") appears once. Its Payload is a **list in 32 exports and an object keyed "0", "1", ... in 23** | Exports. QuestionPunk's importer and the Testa guide handle both |
| A block has Type (`Default`, `Standard`, `Trash`), Description, ID (`BL_...`), BlockElements; `SubType` is `""` on most Standard blocks | Exports: 468 blocks. sumtxt/qsf `create_block.R` writes the same keys |
| A Trash block named "Trash / Unused Questions" exists in 53 of 55 exports and is not in the flow | Exports. Qualtrics: trash questions are exported |
| BlockElements entries are `{"Type": "Question", "QuestionID": "QIDn"}` or `{"Type": "Page Break"}` | Exports: 1,593 question entries, 323 page breaks. sumtxt/qsf `attach_question.R` |
| `FL` (PrimaryAttribute "Survey Flow") appears once: `{"Type": "Root", "FlowID": "FL_1", "Flow": [...], "Properties": {"Count": n}}`. The first block is listed as `{"Type": "Block", "ID", "FlowID", "Autofill": []}`, later ones as `"Type": "Standard"` | Exports: 55 roots; node types Standard 349, Block 82, EmbeddedData 139, Group 79, BlockRandomizer 32, EndSurvey 35, Branch 31, WebService 18, Randomizer 1 |
| `Properties.Count` is a high-water mark of flow ids, not a length | Exports (for example Count 28 with 13 blocks). The script writes the number of nodes including the root, which is the same thing in a new file |
| `QC` (PrimaryAttribute "Survey Question Count"): the count is a **string in SecondaryAttribute**, Payload is null. It is **not** the number of `SQ` elements: equal in 24 exports, larger in 30, smaller in 1. It equals the highest QID number in 40 of the 55 (see "Where practitioners disagree") | Exports. In a new file with QID1..QIDn both readings give n, which is what the script writes |
| `SO` (Survey Options), `SCO` (Scoring), `STAT` (Survey Statistics), `RS` (response set; its PrimaryAttribute equals `SurveyEntry.SurveyActiveResponseSet` in 52 of 55) | Exports: SO, STAT, QC, RS in 55 of 55; SCO in 54. Values written by the script are the most common ones in the set and equal the sumtxt/qsf template |
| `PROJ` with PrimaryAttribute "CORE", TertiaryAttribute "1.1.0", Payload `{"ProjectCategory": "CORE", "SchemaVersion": "1.1.0"}` | Exports: 46 of 55 in this form; 2 more carry an older `1.0.0` form and 7 have none |
| `PL` (Preview Link, a UUID) | Exports: 37 of 55. Not written by the script: the sumtxt/qsf template, built for import, has none. |
| Other codes seen: `NT` notes, `QG`, `QGO`, `QO` quotas, `BR` | Exports. Read and reported, never written |
| `SQ`: one per question; PrimaryAttribute is the QuestionID (equal to Payload.QuestionID in 1,595 of 1,595); SecondaryAttribute is the question text as plain text, cut to about 100 characters | Exports. Testa guide: "the first 99 characters"; the script cuts to 99 |
| Payload keys in every question: QuestionText, DataExportTag, QuestionID, QuestionType, Selector, QuestionDescription, Language. Nearly always: Configuration (1,557), Validation, NextChoiceId, NextAnswerId, DataVisibility | Exports |
| `Choices` is an object keyed by choice id, `{"1": {"Display": "..."}}`; keys need not be 1..n; **display order is `ChoiceOrder`**, whose entries are strings in 538 questions and integers in 417 | Exports. The script writes strings |
| `NextChoiceId` is greater than every choice key | Exports: 978 of 981. A text or descriptive question with no choices commonly carries 4, which the script copies |
| A write-in on a multiple-choice option is `"TextEntry": "true"`; an exclusive option is `"ExclusiveAnswer": true` | Exports: 45 MC choices with `"true"`; exclusive in the QualtricsTools sample survey |
| Matrix: statements in `Choices`/`ChoiceOrder`, scale points in `Answers`/`AnswerOrder`; usual Configuration `{"QuestionDescriptionOption": "UseText", "TextPosition": "inline", "ChoiceColumnWidth": 25, "RepeatHeaders": "none", "WhiteSpace": "OFF", "MobileFirst": true}` | Exports: 63 of 125 Likert matrices carry exactly this Configuration |
| Validation: `{"Settings": {"ForceResponse": "ON" or "OFF", "ForceResponseType": "ON", "Type": "None"}}`; request response is `"RequestResponse"` in both fields; descriptive text carries `{"Settings": {"Type": "None"}}` | Exports (195 of the first 263 questions use the ON/OFF form). sumtxt/qsf `construct_validation.R` writes the same three shapes |
| Skip logic lives **on the block element**, not in the question: `{"Type": "Question", "QuestionID", "SkipLogic": [{SkipLogicID, ChoiceLocator, Condition, SkipToDestination, Locator, SkipToDescription, Description, QuestionID}]}` | Exports: 75 rules, all on block elements, none in a question payload. Conditions: Selected 59, NotSelected 9, Displayed 3, Empty 2, NotEmpty 2. Destinations: a QID 40, `ENDOFBLOCK` 22, `ENDOFSURVEY` 13. sumtxt/qsf `add_skiplogic.R` |
| The locator names the **choice key**: `q://QID1/SelectableChoice/2` | Exports: 62 of 75 skip rules, 210 of 244 display conditions |
| Display logic: `{"0": {"0": {LogicType: "Question", QuestionID, QuestionIsInLoop: "no", ChoiceLocator, Operator, QuestionIDFromLocator, LeftOperand, Type: "Expression", Description}, "1": {..., "Conjuction": "Or"}, "Type": "If"}, "Type": "BooleanExpression", "inPage": false}` | Exports: 193 questions; 190 have one group; operators Selected 204, NotSelected 7 on question conditions. sumtxt/qsf `construct_displaylogic.R` |
| The joining key is spelled **`Conjuction`** | Exports: 34 of 34 joined conditions; never "Conjunction". sumtxt/qsf uses the same spelling |

## Advanced Format TXT (the documented import format)

From Qualtrics' "Import and export surveys" page, checked 2026-11-12. The script writes only these tags:

| Tag | Use |
|---|---|
| `[[AdvancedFormat]]` | First line of the file |
| `[[Question:MC:SingleAnswer:Vertical]]`, `[[Question:MC:MultipleAnswer:Vertical]]`, `[[Question:MC:DropDown]]` | Multiple choice (the page also lists `Horizontal`, `Select`, `MultiSelect`) |
| `[[Question:Matrix:SingleAnswer]]`, `[[Question:Matrix:MultipleAnswer]]` | Matrix |
| `[[Question:TE:SingleLine]]`, `[[Question:TE:Essay]]`, `[[Question:TE:Form]]` | Text entry |
| `[[Question:CS]]`, `[[Question:RO]]`, `[[Question:DB]]` | Constant sum, rank order, descriptive text |
| `[[ID:name]]` | "Specifies the question ID"; the page's example is `[[ID:q1]]`. The script writes the question's tag |
| `[[Choices]]`, `[[Answers]]` | One choice (or matrix statement) and one scale point per line |
| `[[AdvancedChoices]]` with `[[Choice:n]]`, `[[AdvancedAnswers]]` with `[[Answer:n]]` | Choices and scale points with recode value n |
| `[[Block:name]]`, `[[PageBreak]]` | Blocks and page breaks |
| `[[ED:field]]`, `[[ED:field:value]]` | Embedded data |

- Tags go on their own line. The page's full sample has blank lines between questions; it states no rule
  about them. HTML is allowed in the text.
- The page lists no tag for skip logic, display logic, validation (forced response, totals), write-in boxes,
  exclusive options, sliders, NPS, multi-line text boxes or text matrices, and `[[Randomize]]` only for the
  Simple format. The script therefore treats all of these as "TXT cannot hold it" and chooses QSF when a
  survey uses one. The page does not say that these are impossible, only gives no tag.
- "TXT will add on to the existing survey you are importing into": import a TXT file into a new, empty
  survey. The file must be UTF-8 (UTF-16 "won't upload properly").
- Path: Survey tab, Tools, Import/Export, Import survey.

## Question types

| Markdown tag | QuestionType / Selector / SubSelector | Exports with this triple |
|---|---|---|
| `[single]` | MC / SAVR / TX | 47 |
| `[multi]` | MC / MAVR / TX | 19 |
| `[dropdown]` | MC / DL / none | 4 |
| `[text]` | TE / SL / none | 30 |
| `[text-long]` | TE / ML / none | 11 |
| `[essay]` | TE / ESTB / none | 11 |
| `[info]` | DB / TB / none | 42 |
| `[matrix]` | Matrix / Likert / SingleAnswer | 27 |
| `[matrix-multi]` | Matrix / Likert / MultipleAnswer | 7 |
| `[slider]` | Slider / HSLIDER / none | 12 |
| `[nps]` | MC / NPS / none | **1** |
| `[rank]` | RO / DND / TX | **1** (the question sits in that survey's trash) |
| `[form]` | TE / FORM / none | 13 |
| `[matrix-text]` | Matrix / TE / Short | 3 (6 questions) |
| `[sum]` | CS / VRTL / TX | **1** |

- Slider Configuration copied from the most common export form (18 questions): CSSliderMin 0, CSSliderMax
  100, GridLines 10, SnapToGrid false, NumDecimals "0", ShowValue true, NotApplicable false, MobileFirst
  true. `CustomStart` is false in 8 questions and true elsewhere (true goes with start positions, which the
  script does not write). Exports with a range of 1 to 5 and 1 to 7 have GridLines 4 and 6, so the script
  writes the width of the range, capped at 10. `Labels` is `[]` or an object like `Choices`.
- NPS, from the one export: `Choices` is a **list** of 11 entries with Display "0" to "10", `ChoiceOrder` is
  "0" to "10", there is no SubSelector, and `ColumnLabels` holds the two end labels with `IsLabelDefault`
  (defaults "Not at all likely", "Extremely likely"), NextChoiceId 11. The NPS scale itself (0 to 10) is
  Reichheld's; see the `nps-analysis` skill for scoring.

- Text form: `Choices` holds the fields; 25 of 37 fields in exports carry only `Display`, which is what the
  script writes. Field sizes and field validation are reported, not carried.
- Text matrix: statements in `Choices`, column headings in `Answers`, Configuration as for Likert without
  `WhiteSpace` (the form in the exports).
- Constant sum, from the one export: `Labels` `[]`, `ClarifyingSymbolType` "None", and a required total as
  `Validation` `{"Settings": {"EnforceRange": "OFF", "Type": "ChoicesTotal", "ChoiceTotal": "1000"}}`.
- Read with a warning, written as the vertical type: MC selectors SAHR (seen), MACOL (seen), SACOL, MAHR,
  SB, MSB. A Likert matrix with dropdowns (SubSelector `DL`, 1 export) is read as `[matrix]` with a warning.
- Side by side (4 exports): the columns are in `AdditionalQuestions`, each a small question payload
  (`QuestionType` Matrix, `Selector` Likert, own `Answers`, ids like `QID74#1`) over the parent's `Choices`.
  `to-md` writes each Likert column as its own matrix question and says so. Writing side by side is not
  supported.
- Not supported, reported by `to-md` with the question id: other matrix kinds (Profile, MaxDiff), timing,
  meta, captcha, file upload, signature, graphics.

## Other shapes the script writes

| Markdown | Shape | Evidence |
|---|---|---|
| `{code:n}` on options | `RecodeValues` `{"1": "1", "2": "0"}` keyed by choice id; on a Likert matrix keyed by `Answers` id | Exports: 161 multiple-choice questions carry it (values are strings in 138, integers in 23; whole numbers in 140 of 161); 5 matrices key it by scale point |
| `{var:name}` on matrix rows | `ChoiceDataExportTags` `{"1": "q1_recent_1"}` (otherwise `false`) | Exports: 5 matrices |
| `> randomize: options` / `rows` | `Randomization` `{"Advanced": null, "TotalRandSubset": "", "Type": "All"}` | Exports: 117 questions in exactly this form (MC 96, Likert matrix 14, slider 4, constant sum 1). Not seen on a dropdown, so the script refuses it there |
| `> embedded: field` | Flow element `{"Type": "EmbeddedData", "FlowID", "EmbeddedData": [{"Description", "Type": "Recipient", "Field", "VariableType": "String", "DataVisibility": [], "AnalyzeText": false}]}` | Exports: 125 fields in this form |
| `> embedded: field = value` | The same with `"Type": "Custom"` and `"Value"` | Exports: 282 fields in this form |

Evidenced but **not written** (documented limits): block randomizers (32 in exports; the Markdown has no
grouping of blocks), branches, end-of-survey elements, quotas, loop and merge, side by side.

`to-md` keeps choice coding wherever it can: when the export values of a question (recode value, or the
choice id when there is none) are not 1, 2, 3 in display order, every option gets `{code:n}`.
On a Likert matrix, `RecodeValues` keys that name no column (left over from a deleted column) are ignored.
Row ids of a matrix, column ids of a text matrix and choice ids of the other types are judged in display
order (`ChoiceOrder`, `AnswerOrder`); when they are not 1, 2, 3 the report warns that a rebuilt survey
renumbers them.

Text and HTML: a `<` passes through `to-qsf` as markup only when it opens an element named in the HTML
Living Standard's element index (plus obsolete `font`, `center`, `strike`, `tt`, `big`, and namespaced or
custom names such as Word's `<o:p>`) or a comment; any other `<` is written as `&lt;`. An `&` passes
through only when it starts a numeric reference or a named reference in the standard's table of named
character references (Python's `html.entities.html5`). `to-md` decodes references, except a `<` or `&`
that would read as markup again. These are rules of this script, chosen so that text such as `<None>`
reaches respondents as written.

## Codebook

`codebook` lists one row per variable: the export tag, the question text, and `value=label` pairs using
`RecodeValues` where present. Names with a suffix (`tag_1` for a multi-answer choice, a slider bar or a form
field; `tag_1_TEXT` for a write-in box; `tag_1` for a matrix row without its own export tag; `tag_1_2` for
one cell of a multiple-answer or text-box matrix; `tag#1_2` for column 1, row 2 of a side-by-side question;
`tag_NPS_GROUP` for the detractor, passive and promoter group of an NPS question) follow the usual Qualtrics
data-export naming. The exports support this indirectly (row export tags such as `q1_recent_1` on a
question tagged `q1_recent`), and Qualtrics' matrix-table page says a text-entry or multiple-answer matrix
exports one column per box
(https://www.qualtrics.com/support/survey-platform/survey-module/editing-questions/question-types-guide/standard-content/matrix-table/,
not re-read on 2026-11-19); the NPS group column and its 1/2/3 coding are as Qualtrics' NPS question page
describes them, also not re-read. No data file was compared: the script tells the user to check the names
against a real export. Embedded-data fields declared in the flow are listed; response metadata columns
(StartDate, EndDate, Progress, Duration, Finished, ResponseId and the like) are not.

## Measured on the 55 exports (1,595 questions)

| | First pass | Second pass |
|---|---|---|
| Converted with nothing reported | 397 | 481 |
| Converted with changes reported | 761 | 713 |
| Not converted | 437 | 401 |

Of the 401 not converted: 188 sit in a Trash block, 144 are page timers, 32 sit in no block, 18 are
profile matrices, and the rest are file upload, meta, graphics, captcha and MaxDiff. The most common
reported changes are HTML formatting removed (305 questions), an empty or repeated export tag (190), piped
text (186), question JavaScript (160) and a horizontal layout (119). The new `validate` checks (logic
pointing at a missing choice, a joined condition without `Conjuction`) fire on none of the 55. Since
2026-11-19 a missing choice is an error rather than a warning; the order-list checks (a key listed twice
or left out) and the check for display logic on a later question were added then and were not re-run on
the 55, so `validate` may now warn on some real exports.

## Sources

- Qualtrics, "Import and export surveys":
  https://www.qualtrics.com/support/survey-platform/survey-module/survey-tools/import-and-export-surveys/
- Qualtrics, "Skip logic":
  https://www.qualtrics.com/support/survey-platform/survey-module/question-options/skip-logic/
- Christian Testa, "Quickly understanding QSF files" (2017; written for the QualtricsTools R package; a
  reader's map that says nothing about import): https://gist.github.com/ctesta01/d4255959dace01431fb90618d1e8c241
- sumtxt/qsf, an R package that builds QSF files for import (GPL-3.0; read for evidence, no code copied):
  https://github.com/sumtxt/qsf (`R/add_skiplogic.R`, `R/construct_displaylogic.R`,
  `R/construct_validation.R`, `R/create_block.R`, `R/attach_question.R`, `data-raw/frame-template.qsf`)
- Qualtrics Community, "When generating a custom-built QSF, how can I ensure it meets formatting
  requirements?" (2019, unanswered; reports that the format changes without notice and that uploads then
  fail): https://community.qualtrics.com/custom-code-12/when-generating-a-custom-built-qsf-how-can-i-ensure-it-meets-formatting-requirements-6596
- WHATWG, HTML Living Standard, "Index: Elements" and "Named character references":
  https://html.spec.whatwg.org/multipage/indices.html#elements-3 and
  https://html.spec.whatwg.org/multipage/named-characters.html (element list typed from the index; not
  re-read on 2026-11-19)
- GitHub code search for public exports: https://github.com/search?q=SurveyElements+extension%3Aqsf&type=code

## Sample set

55 exports from 40 public repositories, found with the code search above on 2026-11-12. Among them:
ctesta01/QualtricsTools (sample surveys, no licence file), sumtxt/qsf (GPL-3.0),
cmu-delphi/delphi-epidata (MIT), uwescience/HackWeek-Toolkit (CC-BY-4.0),
UW-Madison-DSI/open_source_survey_results (MIT), willgreenland/surveyhelper (MIT), tt-econ/bace and
tilltnet/egor (AGPL-3.0), leeper/conjoint-example and HEGSRR/OR-Replicability-in-Geography-Survey (no
licence stated). Because many have no licence or a copyleft one, **no downloaded file is in this
repository**. `fixtures/export.input.qsf` is written by hand to mirror their structure.

No list of the 55 file paths and hashes is published with the skill: the files were not kept after the
check, so the measurements below cannot be re-run from this repository. Re-running them needs a new search
and will not find exactly the same files.

How the script was checked against the set (not part of the test suite, since the files are not
redistributed): `validate` reports no error on any of the 55; `to-md` runs on all 55; and for all 55,
`to-md`, then `to-qsf`, then `to-md` again gives the same Markdown (comments aside), with and without
`--keep-html`. Every rebuilt file passes `validate --strict`. In the set, 56 of 74 skip rules and 137 of
171 display rules inside shown blocks fall in the supported subset. `codebook` runs on all 55, and
`to-qualtrics` on the Markdown of each picks TXT for 6 and QSF for 49.

One independent reader was also run: the QuestionPunk app's own QSF parser reads the file built from
`fixtures/survey.input.md` and lists all 12 screens, their options, both display rules and the block
names. That shows a second program reads the file as intended. It is not evidence about Qualtrics.

## Where practitioners disagree

- **NPS in logic.** No sampled export had skip or display logic on an NPS question. The script writes it
  with the multiple-choice locator (`q://QIDn/SelectableChoice/6` for a score of 6), because NPS stores its
  choices keyed by score, and says to check it after import.
- **Display logic on the same page.** Qualtrics' display-logic page describes an "In page" option for a
  rule that tests a question on the same page; without it the rule is evaluated when the page loads
  (https://www.qualtrics.com/support/survey-platform/survey-module/question-options/display-logic/, not
  re-read on 2026-11-19). The script writes rules without "In page" (the form in the exports), so it warns
  and the user adds `---`. Unconfirmed: what Qualtrics does on import with such a rule.
- **Is `PL` needed?** One published QSF-building skill says a build without it was refused; the sumtxt/qsf
  template has none and 18 of 55 exports lack it. Not settled.
- **Do ids need exactly 15 characters?** The same skill reports a refusal with 16-character ids. Exports
  agree for survey, response-set and user ids; block ids vary. Writing 15 everywhere satisfies both.
- **`ForceResponseType`.** One skill calls it invalid in a basic validation block; it is present in most
  exports and in sumtxt/qsf. The script follows the exports.
- **Dropdown SubSelector.** One skill writes `TX`; the 4 exports with a dropdown have none. The script
  follows the exports.
- **Is `QC` a count?** Often described as "the number of questions". In the 55 exports it equals the number
  of `SQ` elements in 24, is larger in 30 and smaller in 1, and it equals the highest QID number in 40. The
  script writes n for a new file with QID1..QIDn, which satisfies both readings, and `validate` only warns
  when `QC` is below the number of questions.

## Pitfalls

- Assuming the `BL` payload is a list (it is an object in 23 of 55 exports).
- Sorting choices by key instead of reading `ChoiceOrder` and `AnswerOrder`.
- Building a locator from the choice's position instead of its key.
- Writing "Conjunction" instead of `Conjuction`.
- Putting skip logic in the question payload instead of the block element.
- Skipping to a question in another block, or backwards.
- Treating `QC` or the flow `Count` as lengths.
- Defining a question that no block lists, or a block the flow does not list: both vanish without an error.
- Using SecondaryAttribute as the question text (it is cut short).
- Dropping HTML, recode values, randomization, translations, quotas, embedded data or branches without
  saying so. `to-md` lists each one.
- Renumbering questions while leaving piped text (`${q://QID3/...}`) pointing at the old numbers.
- Re-saving the file as UTF-16; Qualtrics' importers expect UTF-8. The script writes ASCII-only JSON.
