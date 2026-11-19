# Screener file format

Read this before writing the screener file the linter checks, or when the linter exits with code 2.

Contents: Markdown layout · Actions and routing · Quotas · JSON layout

## Markdown layout

A complete file that lints with 0 errors and 0 warnings:

```markdown
# Screener: Work tools study

study: interview
platform: own panel
topic words: project management, Asana, Trello
intro: A 45-minute paid conversation about how you work. This questionnaire takes about 3 minutes.

## Criteria
- C1: Works full time or part time
- C2: Has used a project management tool at work in the past month
- C3: Does not work in market research, UX research or advertising (exclude)

## Quotas
total: 12
- Company size (Q4): "1 to 49 employees" 4-6; "50 to 999 employees" 4-6; "1,000 or more employees" 2-4

## Questions

### Q1 [single] (C1) randomize
Which of these best describes your current employment?
- Employed full time -> continue
- Employed part time -> continue
- Not currently employed -> terminate
- Full-time student -> terminate

### Q2 [single] (C3) randomize
Which industry do you mainly work in?
- Healthcare -> continue
- Software or technology -> continue
- Market research or UX research -> terminate
- Advertising or a marketing agency -> terminate
- Another industry -> continue

### Q3 [multi] (C2) randomize
Which of these have you used at work in the past month? Select all that apply.
- Google Sheets -> continue
- Asana -> qualify
- Trello -> qualify
- Zoom -> continue
- Confluence -> continue
- None of these -> terminate

### Q4 [single]
How many people work at your organization, across all locations?
- 1 to 49 employees -> continue
- 50 to 999 employees -> continue
- 1,000 or more employees -> continue
- Don't know -> terminate

### Q5 [open] articulation
Tell us about the last time you had to keep a group project on track at work.
```

- Header keys: `study` (interview, usability, focus group, diary, survey ...), `platform` (optional; `Prolific`
  adds the panel note), `topic words` (words that would reveal what the study is about), `intro`.
- A question heading is `### Q<number> [type] (criteria) flags`. Types: `single`, `multi`, `open`, `numeric`.
  Criteria are the ids from the Criteria list, comma-separated; give each criterion its own question (a
  single-select tied to two criteria gets SC24). Flags: `randomize` (option order is shuffled when fielded) and
  `articulation` (on an `[open]` question: the one that checks someone can describe their experience).
- The question text is every plain line under the heading; options are `- ` bullets. `require:` or
  `qualify if:` lines are refused: put the rule in the options' actions.
- `topic words` are only for the linter: it flags them in question text, the title and the intro. They are
  not shown to respondents.
- A criterion marked `(exclude)` is a disqualifier (competitors, market researchers, recent participants); its
  question needs at least one `terminate` option.

## Actions and routing

Each option ends with `->` and one action:

| Action | Meaning |
|---|---|
| `continue` | Go to the next question. On a question with `qualify` options it is a distractor: alone it does not pass |
| `qualify` | A target answer; go to the next question |
| `terminate` | Screen the person out |
| `goto Q7` | Skip forward to Q7 (backward jumps are errors) |

Single-select and numeric: the chosen option's action applies, so a distractor routed to `continue` lets that
person through. On a question that screens a criterion, route every non-target answer to `terminate` (the
linter reports SC22 with the route that slips through). Multi-select: any selected `terminate` option screens
out, and when the question has `qualify` options at least one must be selected; if several selected options
`goto`, the earliest target applies. Open questions continue (read the answers before inviting). Someone who
reaches the end without a terminate qualifies, and every such route must pass a screening question for every
criterion.

Numeric questions list their answer ranges as options (`- 0-4 -> terminate`, `- 5-9 -> qualify`,
`- 10 or more -> qualify`); the linter checks they neither overlap nor leave gaps, assuming whole numbers
(`Under 5` ends at 4, `Over 5` starts at 6), and flags reversed ranges. It cannot know the lowest or highest
possible value, so check by hand that the first and last ranges reach them.

## Quotas

`total:` is the number of participants to recruit. Each quota line names the single-select question it splits
and its cells: `"option text" MIN-MAX`, or one number for an exact count; join options with `+` to put them
in one cell (`"Owner" + "Manager" 3-5`). Option text must match the question's option exactly (case and spaces
are ignored; curly quotes are fine). The linter checks that cells name real options on a route that can
qualify, that no option is in two cells, that every non-terminating option has a cell, and that the minimums
add to at most the total and the maximums of the cells that can fill to at least it. Each quota group is
checked on its own: with two groups (crossed quotas), check by hand that the combinations you need can occur.

## JSON layout

```json
{
  "title": "Work tools study", "study": "interview", "platform": "", "intro": "...",
  "topic_words": ["project management", "Asana"],
  "criteria": [{"id": "C1", "text": "Works full time or part time", "exclude": false}],
  "quotas": {"total": 12, "groups": [{"name": "Company size", "question": "Q4",
             "cells": [{"options": ["1 to 49 employees"], "min": 4, "max": 6}]}]},
  "questions": [{"id": "Q1", "type": "single", "text": "...", "criteria": ["C1"], "randomize": true,
                 "articulation": false,
                 "options": [{"text": "Employed full time", "action": "continue"}]}]
}
```

Required: `id` on every criterion and question, `text` on every option, `question` and `cells` (each with
`options` and `min`) on every quota group; a missing field exits 2 with its location. `fixtures/good.json` is
`fixtures/good.md` in this layout; the linter gives both the same findings.
