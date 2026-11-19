# Fielding a Kano survey on QuestionPunk

Optional. The analysis needs no account; this page is for running the survey on QuestionPunk through its MCP
server (`https://app.questionpunk.com/api/v1`). Ask the user before creating, changing or publishing anything.

## Creating the questions

QuestionPunk has a Kano question type. Either:

- create it with `question_create` (or `question_create_bulk`), answer type `kano`: `textItemDetails.features`
  (2 to 20 short feature names), with `textItemDetails.functional_questions` and
  `textItemDetails.dysfunctional_questions` holding one question per feature in the same order ("If the app has
  dark mode, how would you feel?" / "If the app does not have dark mode, how would you feel?"). Optional
  `itemDetails.ask_importance` (default false; true adds a 1 to 9 importance rating per feature) and
  `itemDetails.randomize_features` (default true). The app supplies Berger's five answers in every language and
  sets the feature ids itself, so don't send `feature_ids`. An existing question can't be changed into a Kano
  question: create a new one. In the app the same question is "Feature Priorities (Kano)" in the add-question
  menu. Or
- build each half of each pair as its own question with `question_create`: answer type `multiple_choice`, and
  `textItemDetails.answer_options` set to Berger's five answers in order ("I like it that way", "It must be that
  way", "I am neutral", "I can live with it that way", "I dislike it that way"). Put each dysfunctional question
  straight after its functional one. Analyze the export with `--pair`.

Use `survey_get` to find the question ids.

## Reading the answers

1. Call `responses_read` with `answerFormat: "numeric"` and `status: "completed"`. Page it: pass
   `cursor` = the previous result's `page.nextCursor` until `nextCursor` is null.
2. `responseType: "real"` leaves out synthetic (AI) responses only. A person testing the live link still
   submits a real response: drop your own and teammates' test responses by id, start time or a known test
   answer before analyzing.
3. Map `answers[questionId]` into named CSV columns, one row per response. A Kano question comes back as one
   `Feature: 1 / 5` line per feature (with `· 7/9` when importance was asked): put it in one column and pass
   `--qp-answer-col`. Paired multiple-choice questions become two columns per feature for `--pair`.
4. Reconcile the row count before computing: the rows you kept should equal `responses_get_counts` for the same
   filters, minus the test responses you dropped. If you passed `questionIds`, compare with the filtered read's
   `page.total` instead, because that filter leaves out responses that answered none of those questions.
