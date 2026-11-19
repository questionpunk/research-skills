# Mapping the brief to a QuestionPunk AI interview (optional)

Only for users who choose to run the interview in QuestionPunk. The brief is complete without this file.
Field names below are the ones the hosted `question_create` tool describes. Read the tool's own description
before calling it; it is the authority if it differs from this page.

**Ask the user before every create, change or publish.** A question added to a published survey is live at
once.

## Shape

One survey, with a consent question and then one interview question. The settings differ by modality.

Text interview of 20 minutes:

```json
{
  "text": "Interview about your time with Larder Box",
  "answer_type": "ai_moderated_interview",
  "required": true,
  "itemDetails": { "modality": "text", "questionMode": "time_based", "durationMinutes": 20 },
  "textItemDetails": { "interviewGoal": "…", "greetingInstruction": "…", "avoidTopics": "…" }
}
```

Voice interview of 20 minutes: `timeoutMs` (the session length in milliseconds) is required, and the
typed-interview settings `durationMinutes`, `endOnStopRequest` and `timeBasedCompletionConfig` are rejected:

```json
{
  "text": "Interview about your time with Larder Box",
  "answer_type": "ai_moderated_interview",
  "required": true,
  "itemDetails": { "modality": "voice", "timeoutMs": 1200000, "recordingMode": "audio" },
  "textItemDetails": { "interviewGoal": "…", "greetingInstruction": "…", "avoidTopics": "…" }
}
```

The three text fields go in `textItemDetails`, not in `itemDetails`. `modality` goes in `itemDetails`. The
tool description says each voice interview uses the survey owner's credits for every minute it runs: tell
the user before creating one.

## Field by field

| Brief section | Where it goes | Notes |
|---|---|---|
| 1 Goal, 3 Context for the moderator | `textItemDetails.interviewGoal` | Write the goal and the context. Keep the decision and hypotheses out |
| 4 Must-ask questions (with depth, probes, "done when", skip and branch), 5 probe rules | `textItemDetails.interviewGoal` | The tool description names no separate field for a question list or a per-question depth. Put the ordered questions and their rules in the goal text, addressed to the moderator, with question 1 marked "already asked in the greeting", then check in a preview that they are followed |
| 6 Avoid | `textItemDetails.avoidTopics` | Study-specific topics and requests, as plain text |
| 7 Consent screen | A separate question before the interview: `answer_type` `consent`, `required: true`, with `textItemDetails.statement` and `agree_label` | The fixed disclosure and consent text, including that the interviewer is an AI. In the preview, check that declining does not reach the interview |
| 7 Opener | `textItemDetails.greetingInstruction` | The short opener, word for word |
| 8 Closing | No dedicated field in the tool description | Add the closing wording to the goal text as the last instruction, and check it in the preview |
| 9 Modality | `itemDetails.modality`: `"text"` (default) or `"voice"` | The tool description names no real-time or turn-based setting; check the app's editor |
| 9 Length, text | `itemDetails.questionMode`: `"fixed_count"` with `length` (number of exchanges), `"time_based"` with `durationMinutes`, or `"ai_decides"` with `aiDecidesConfig { minQuestions, maxQuestions, stoppingGuidance }` | The defaults are short. Set the length from the brief's time or turn budget on purpose. The tool description does not say whether `minQuestions` and `maxQuestions` count exchanges or main questions; check in the preview |
| 9 Length, voice | `itemDetails.timeoutMs`, required: minutes × 60,000 (1,200,000 for 20 minutes; the tool accepts 60,000 to 14,400,000) | Do not send `durationMinutes`, `endOnStopRequest` or `timeBasedCompletionConfig` with voice; they are rejected |
| 9 Recording | `itemDetails.recordingMode` (`"none"`, `"audio"`, `"video"`) | The consent statement and its agree label must name the recording mode |
| Stop on request, text | `itemDetails.endOnStopRequest` (default true) | Keep it on. With it on, a clear request to stop gets one question, whether to end or keep going, and a clear yes ends the interview; say so if the consent screen promises stopping at any time |
| 10b Custom-LLM prompt | Not used | Paste only the study-specific parts above, not the general behaviour rules |

## Order of calls

1. Show the user the mapped fields. Ask whether to create a draft.
2. `survey_create`, then `survey_get` for the current version and the question count.
3. `question_create` for the consent question, then for the interview question. Each call returns the next
   survey version: pass that one to the next call, not the version from step 2.
4. `survey_get` to read back what was stored and compare it with the brief.
5. Ask the user to run the pilot from the preview or with a few invited participants. Ask again before
   `survey_publish`.
6. After the pilot, `responses_read` to fetch the transcripts for the pilot checklist. Page with `cursor` =
   `page.nextCursor` until it is null, keep real responses only, and reconcile the count with the pilot.
   Answers over 4,000 characters come back cut with a marker: for those, take the full transcript from
   `responses_export` before grading coverage.

If a field or setting above is missing from the tool description in your connection, do not guess: tell the
user and have them set it in the app's question editor.
