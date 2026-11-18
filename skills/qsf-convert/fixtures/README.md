# Fixtures for qsf-convert

All files are synthetic. No real respondent data and no downloaded export is stored here; the real exports
used as evidence (see `../references/sources.md`, "Sample set") carry mixed or no licences, so they were
only read. Every `expected` file was written by hand before it was compared with the script's output.

## Markdown to QSF

- `survey.input.md`: every first-pass question type, two skip rules, two display rules, a write-in
  option, an exclusive option, a page break and two blocks.
- `survey.expected.json`: the fields the built `.qsf` must contain. A whole expected `.qsf` cannot be
  written by hand because survey and block ids are hashes of the input, so the test asserts these fields
  as a subset (`null` means the key must be absent or null). Where each value comes from:
  - Question ids: questions are numbered in file order, so `used` is QID1, `features` QID2, `role` QID3,
    `intro` QID4, `nps` QID5, ... `story` QID12. Twelve questions give `QC` = "12".
  - Choice keys are positions: in `used`, Yes = 1, No = 2, Not sure = 3. So the rule `if "No" -> end of
    survey` is locator `q://QID1/SelectableChoice/2` with destination `ENDOFSURVEY`, and `if "Not sure" ->
    role` is `q://QID1/SelectableChoice/3` with destination `QID3`.
  - `show if: used is "Yes" or role is not "Designer"` on `why` (QID10): condition 0 is
    `q://QID1/SelectableChoice/1` `Selected`; condition 1 is Designer, the third option of `role` (QID3),
    so `q://QID3/SelectableChoice/3` `NotSelected` with `"Conjuction": "Or"`.
  - Text: `Reports & exports` is stored as `Reports &amp; exports`, `Price < value` as
    `Price &lt; value`; the two text lines of `features` are joined with `<br>`; the `<strong>` in `intro`
    passes through and is removed from the plain `QuestionDescription`.
  - Flow: root `FL_1`, the two blocks as `FL_2` (`Block`) and `FL_3` (`Standard`), so `Count` is 3. The
    Trash block is in `BL` but not in the flow.
  - Slider `effort`: range 1 to 7 gives `CSSliderMin` 1, `CSSliderMax` 7 and `GridLines` 6 (the width of
    the range, as in exports with that range).
  - Type triples, validation shapes and the NPS shape: the tables in `references/sources.md`.

## Markdown to Advanced Format TXT

- `plain.input.md`: a survey with nothing TXT cannot hold: ten question types that have a TXT tag, recode
  values on one question and on one matrix scale, two embedded data fields, a page break and two blocks.
- `plain.expected.txt`: written by hand from the tag list in `references/sources.md`: one
  `[[Question:...]]` line per question with the subtype of its Markdown type, `[[ID:tag]]`, the text (the
  two lines of `thanks` joined with `<br>`, `&` as `&amp;`), then `[[Choices]]`, or `[[AdvancedChoices]]`
  with `[[Choice:n]]` where the options carry `{code:n}` (`rating`: 1, 0, 99), and for the matrix
  `[[AdvancedAnswers]]` with `[[Answer:0]]` and `[[Answer:1]]`.
- The tests also build the same file as a `.qsf` and assert by hand-stated values: `RecodeValues`
  `{"1": "1", "2": "0", "3": "99"}` on `rating` (keys are positions, values the codes), `{"1": "0", "2":
  "1"}` on the `agree` scale, and none on `topics`.

## QSF to Markdown, report and codebook

- `export.input.qsf`: written by hand to mirror real exports. It has what a reader must survive: the block
  list as an object with sparse keys ("0", "1", "4", "7"), a Trash block holding a question, integer and
  string order lists, choice keys with a gap (1, 2, 4) shown in the order 1, 4, 2, matrix rows shown in the
  order 2, 1 with row export tags, recode values, HTML in texts, an NPS question with `Choices` as a list,
  a side-by-side question with two columns, a text matrix, a text form, a constant sum with a total and
  randomization, a `QC` of 20 with 15 questions, a note element, and a flow with embedded data, a branch
  and an end-of-survey element.
- `export.expected.md`: by reading the file above against `references/markdown-format.md`:
  - The flow starts with one embedded data field of the plain form, so it becomes `> embedded: source`.
  - `commute` options follow `ChoiceOrder` [1, 4, 2]: Yes, Sometimes, No. Their recode values are 1, 2
    and 0, which is not 1, 2, 3 in display order, so each option carries `{code:n}`.
  - Its skip rules name choice keys 2 (No, to the end of the block) and 1 (Yes, not selected, to QID4).
    QID4's export tag `commute mins` has a space, so it becomes `q4`; QID12 repeats the tag `commute`, so
    it becomes `q12`.
  - `modes` has randomization of type All (`> randomize: options`) and display logic on keys 1 and 4 of
    QID2 joined by `Or`: Yes or Sometimes.
  - `agree` rows follow `ChoiceOrder` ["2", "1"] and carry their export tags as `{var:name}`.
  - The side-by-side question QID8 has two Likert columns over rows Route A and Route B, so it becomes
    `sbs_1` (one answer per row, forced response ON in that column) and `sbs_2` (several answers per row),
    each with the parent text followed by the column text.
  - `hours` is a text matrix, `contact` a text form, `split` a constant sum with total 100 and
    randomization.
  - Outside the supported subset, so written as comments: the skip rule on a text answer (QID4), display
    logic on embedded data (QID6), the timing question (QID10), the branch and the end-of-survey element.
  - The `<span>` in QID3 is removed; the `<b>` in QID1 is kept; `&amp;` becomes `&`.
- `export.expected-report.json`: one fragment per item the Markdown cannot hold (14; the test requires a
  warning for each and no others), and the fixed conversion report: 8 questions converted with nothing to
  report (QID1, 2, 5, 7, 11, 13, 14, 15), 5 converted with changes (QID3 lost a `<span>`; QID4 lost its
  tag, number validation and skip rule; QID6 lost its display logic; QID8 was split; QID12 lost its
  repeated tag and custom label), and 2 not converted (QID9 in the Trash, QID10 a page timer). 8 + 5 + 2
  is the 15 questions in the file.
- `export.expected-codebook.csv`: one row per variable, by hand: `commute` with values from the recodes
  (`1=Yes; 2=Sometimes; 0=No`); one `modes_n` row per multi-answer choice plus `modes_3_TEXT` for the
  write-in; the two `agree` rows under their export tags with the scale as values; `overall_1` for the
  slider bar; one row per side-by-side column (`sbs#1`, `sbs#2`, the tags in the file); `hours_n`,
  `contact_n`, `split_n` for the text matrix, form and constant sum. Descriptive text (QID1) and the
  Trash question (QID9) have no row.
