# Fixtures for screener-writer

All synthetic.

## `good.md` / `good.json`

A screener for a 12-person interview study about work tools: four criteria (one an exclusion), one question
per criterion (employment status and industry apart, so a part-time market researcher is still screened out),
every non-target answer on a single-select routed to terminate, a company-size quota (4-6, 4-6, 2-4 against a
total of 12: minimums 10, maximums 16, so it can fill), behavioural questions with the target answers among
distractors and shuffled, and an articulation question. Expected: no
errors, no warnings, one SC16 suggestion on the multi-select. `good.json` is the same screener in the JSON
layout; both must give identical findings.

## `bad.md` + `bad.expected.json`

The same kind of study with planted mistakes, each listed in `bad.expected.json`:

| Rule | Where | Planted mistake |
|---|---|---|
| SC01 | C3 | "Lives in the United States" has no question |
| SC02 | Q4 | Names criterion C9, which does not exist |
| SC03 | Q3 | "Over 10" has no action |
| SC04 | Q4 | "Notion" jumps back to Q2 |
| SC08 | Q2 | "Do you use Asana every week?" Yes/No |
| SC10 | Q4 | The qualifying option is 72 characters; distractors are single words |
| SC11 | Q2, title | "Asana" in the question and the title |
| SC13 | Q4 | Multi-select without "None of these" |
| SC14 | Q3 (2) | "1-3" overlaps "3-10"; "Over 10" overlaps "12 or more" |
| SC15 | screener | Usability study without an articulation question |
| SC16 | Q4 | Suggestion: flag people who tick everything |
| SC17 | quota | Cell maximums 3 + 3 + 2 = 8 < total 10 |
| SC18 | quota | "12 or more" qualifies but is in no cell |
| SC19 | Q2 | The open job-title question comes before the knock-out question |
| SC21 | Q2 | "We are looking for people who use Asana" |
| SC22 | C2 | "1-3" reports routes to continue, so someone managing 1 to 3 people still qualifies |

## `nngroup_examples.md`

Whitenton (2019): "Do you play online games?" (flagged SC08 and SC11) and a multiple-choice question with
plausible distractors (walking, ride sharing, taxis) for a scooter study (passes, apart from the SC16
suggestion). See `../references/sources.md`, "Worked example".
