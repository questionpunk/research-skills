# Creating the MaxDiff question in QuestionPunk

Optional. Read this only when the user has asked to field the study in QuestionPunk and has agreed to the
question being created. If a call is rejected, show the error to the user and send them to the editor
instead of guessing.

## What the question takes, and what it does with the design

A QuestionPunk MaxDiff question stores the item list, the items per set and the number of sets. It then
draws a balanced set of sets for each respondent by itself (one version per respondent) and saves the sets
shown with each answer. **It does not import a design file.** So:

- pass the item list, `items_per_set` and `num_sets` from this skill's result;
- keep `design.csv` as the design record for a paper version, another tool, or a comparison;
- after fielding, the sets each respondent saw come from the responses, not from `design.csv`.

The diagnostics this skill prints (pair counts, positions, connectivity, BIBD) describe `design.csv`.
They apply to the QuestionPunk study only if the same sets are fielded, which this question type does not
do; for the fielded study run `--check` on the sets exported after fieldwork.

## Steps

1. `survey_get` with the survey id: read `versions.current` (needed as `surveyVersion`), the survey language
   and the number of existing questions (to choose `surveyItemIndex`).
2. Show the user the payload below, filled in, and ask for a yes.
3. `question_create` with that payload. The result returns the next survey version.

## Payload for `question_create`

```json
{
  "surveyId": "<survey id>",
  "surveyVersion": 12,
  "lang": "en",
  "surveyItemIndex": 3,
  "item": {
    "text": "Which of these is most important to you, and which is least important, when choosing a time-tracking tool for your team?",
    "answer_type": "max_diff",
    "required": true,
    "itemDetails": {
      "items_per_set": 4,
      "num_sets": 9,
      "best_label": "Most important",
      "worst_label": "Least important",
      "randomize_sets": true
    },
    "textItemDetails": {
      "answer_options": [
        "Automatic timers", "Invoices from tracked time", "Calendar integration", "Offline mode",
        "Project budgets", "Team timesheets", "Mobile app", "Billable-rate tracking",
        "Idle-time detection", "Reports for clients", "Payroll export", "Approval workflow"
      ],
      "best_label": "Most important",
      "worst_label": "Least important"
    }
  }
}
```

Field rules:

| Field | Rule |
|---|---|
| `itemDetails.items_per_set` | whole number; validation accepts 2 to 10, but the question is saved with the value clamped to 3 to 6 |
| `itemDetails.num_sets` | whole number, 1 to 50; saved as at least items / items per set, rounded up, so every item can appear |
| `itemDetails.best_label`, `worst_label` | text; required here and again in `textItemDetails` (the second pair is the translatable one respondents see) |
| `itemDetails.randomize_sets` | `true` or `false`; required. `true` (the editor's default) shuffles the order the sets are shown in; `false` keeps the generated order. Neither changes which items share a set |
| `textItemDetails.answer_options` | the items, as an array of strings, in list order; at most 60. The example has 12 items, 4 per set and 9 sets (3 x 12 / 4) |
| `itemDetails.delayedSendSeconds` | optional, 0 to 999 |

Send all five `itemDetails` fields and all three `textItemDetails` fields: the connector adds no defaults
for this question type, and unknown fields are rejected.

## When to use the editor instead

- The call is rejected and the message does not name a field you can correct.
- The user wants more than 50 sets, fewer than 3 or more than 6 items per set, an anchor question, or a
  fixed design identical for every respondent.
- The survey has several languages: add the question in the primary language, then let the user translate
  in the editor.

On a published survey a new question is live at once. Say so before creating it, and prefer adding the
question while the survey is still a draft.
