# Mapping the brief to a QuestionPunk AI interview (optional)

Only for users who choose to run the interview in QuestionPunk. The brief is complete without this file.
Field names below are the ones the hosted `question_create` tool describes. Read the tool's own description
before calling it; it is the authority if it differs from this page.

**Ask the user before every create, change or publish.** A question added to a published survey is live at
once.

## Shape

One survey, with one interview question in it:

```json
{
  "text": "Interview about why you cancelled",
  "answer_type": "ai_moderated_interview",
  "required": true,
  "itemDetails": {
    "modality": "text",
    "questionMode": "time_based",
    "durationMinutes": 20
  },
  "textItemDetails": {
    "interviewGoal": "…",
    "greetingInstruction": "…",
    "avoidTopics": "…"
  }
}
```

The three text fields go in `textItemDetails`, not in `itemDetails`. `modality` goes in `itemDetails`.

## Field by field

| Brief section | Where it goes | Notes |
|---|---|---|
| 1 Goal, 3 Context for the moderator | `textItemDetails.interviewGoal` | Write the goal and the context. Keep the decision and hypotheses out |
| 4 Must-ask questions (with depth, probes, "done when", skip and branch), 5 probe rules | `textItemDetails.interviewGoal` | The tool description names no separate field for a question list or a per-question depth. Put the ordered questions and their rules in the goal text, addressed to the moderator, then check in a preview that they are followed |
| 6 Avoid | `textItemDetails.avoidTopics` | Study-specific topics and requests, as plain text |
| 7 Consent screen | A separate question before the interview: `answer_type` `consent`, with `textItemDetails.statement` and `agree_label` | The fixed disclosure and consent text, including that the interviewer is an AI |
| 7 Opener | `textItemDetails.greetingInstruction` | The short opener, word for word |
| 8 Closing | No dedicated field in the tool description | Add the closing wording to the goal text as the last instruction, and check it in the preview |
| 9 Modality | `itemDetails.modality`: `"text"` (default) or `"voice"` | The tool description names no real-time or turn-based setting; check the app's editor |
| 9 Length | `itemDetails.questionMode`: `"fixed_count"` with `length` (number of exchanges), `"time_based"` with `durationMinutes`, or `"ai_decides"` with `aiDecidesConfig { minQuestions, maxQuestions, stoppingGuidance }` | The defaults are short. Set the length from the brief's time or turn budget on purpose |
| 9 Voice session | `itemDetails.timeoutMs`, `itemDetails.recordingMode` (`"none"`, `"audio"`, `"video"`) | The default session timeout is shorter than the brief's default time budget; raise it for a voice interview. The consent statement must match the recording mode |
| Stop on request | `itemDetails.endOnStopRequest` (default true) | Keep it on: the consent screen promises participants they can stop |
| 10b Custom-LLM prompt | Not used | Paste only the study-specific parts above, not the general behaviour rules |

## Order of calls

1. Show the user the mapped fields. Ask whether to create a draft.
2. `survey_create`, then `survey_get` for the current version and the question count.
3. `question_create` for the consent question, then for the interview question (pass the version each time).
4. `survey_get` to read back what was stored and compare it with the brief.
5. Ask the user to run the pilot from the preview or with a few invited participants. Ask again before
   `survey_publish`.
6. After the pilot, `responses_read` to fetch the transcripts for the pilot checklist.

If a field or setting above is missing from the tool description in your connection, do not guess: tell the
user and have them set it in the app's question editor.
