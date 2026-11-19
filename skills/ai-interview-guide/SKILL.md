---
name: ai-interview-guide
description: "Turns research goals or an existing discussion guide or interview script into a brief an AI moderator can run for customer or user research: goal, must-ask questions, probes and probe depth, skip rules, topics to avoid, a consent screen with AI disclosure and a short opener, length, and a paste-ready interviewer prompt, with leading questions rewritten. Use for \"interview 30 customers\", \"async user interviews\", \"AI-moderated interviews\", \"write the prompt for my AI interviewer\" or \"run my discussion guide at scale\"."
license: MIT
metadata:
  version: "0.2.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "interviews"
---

# AI interview guide

Writes the brief an AI moderator needs to run customer or user research interviews without a person in the
room: what to find out, which questions to ask, how deep to probe each one, when to move on or skip, what
never to do, and what to say at the start and the end. The brief is vendor-neutral: it says where each part
goes in a hosted AI-interview tool, and ends with a prompt for a custom LLM.

A human interviewer repairs a weak guide while talking. An AI moderator follows the brief literally in
every session, so each flaw and each repeated question shows up in every interview.

## When to use

Use it when the user wants to:

- interview many customers, users, churned customers or prospects without moderating each session
  ("interview 30 customers", "async user interviews", "AI-moderated interviews");
- turn research goals, a discussion guide or an interview script into something an AI moderator can run,
  in text or voice ("run my discussion guide at scale");
- have interview questions checked and rewritten before an AI asks them;
- write the prompt for their own AI interviewer.

Do not use it for the cases below. A skill named here may not be installed; then say so and use the
fallback in brackets.

- A questionnaire with fixed options, or a count of how many people think something: `survey-from-decision`
  (say interviews cannot count, and suggest a survey).
- Wording problems in a survey, not an interview: `survey-bias-check` (review the wording by hand).
- Existing transcripts that need themes and counts: `open-ended-coding` (code with a codebook, count
  participants per code).
- Job interviews, hiring scorecards or interview practice: outside this pack.

Handled here, with care: screening questions (turn the participant facts from step 2 into questions that
do not give away the qualifying answer); a switch-timeline interview about a purchase (order the questions
along the timeline: first thought, looking, deciding, first use); a study whose main subject is health,
income or illegal behaviour (keep every question skippable and have the brief reviewed for ethics and
privacy before fielding).

## What to ask for

Ask at most one question, and only this one, when the request does not say it: **"What will you decide or
do differently once these interviews are done?"** Ask it alone and wait for the answer. If the user does
not know or says to go ahead, continue, write "Decision: not stated" and list it under open points.

Take every other input from the request, or use the default and say so:

| Input | Default when missing |
|---|---|
| Research goal | Restate the request in one or two sentences |
| Existing guide or draft questions | None; write the questions from the goal |
| Participant profile | The people named in the request, as checkable facts (did what, when) |
| Number of interviews | The user's number; otherwise about 12 per homogeneous segment |
| Modality | Text |
| Time budget | 20 minutes; never above 30 for panel respondents |
| Product background, glossary | What the request says; list gaps as open points |
| Language and tone | The language of the request; plain and neutral |
| Sensitive areas | Infer from the topic and list them for the user to confirm |
| Organisation, incentive, contact, retention period | `[...]` placeholders, listed as open points |

Numbers are explained, and labelled as findings or conventions, in
[references/sources.md](references/sources.md).

## Steps

1. **Fix the goal and the decision.** One or two sentences each, plus "not in scope". If the goal is a
   count or a percentage, say interviews will not give it and point to `survey-from-decision`.

2. **Describe the participants** as facts a screener can check ("cancelled in the last 90 days after at
   least 3 deliveries"). Split into segments when people differ in a way that matters to the decision.
   Saturation figures (9 to 17 interviews) come from homogeneous groups, so plan about 12 completed, usable
   interviews per segment. Keep the user's total and divide it across segments; if that leaves fewer than
   about 9 per segment, keep the total and put the trade-off (fewer segments or more interviews) in the
   open points. The per-segment review in the field-monitoring list decides whether to stop, narrow the
   claim or continue.

3. **Write the context block for the moderator:** what the product or service is in two or three plain
   sentences, a glossary of terms and acronyms, the words participants use for things, and the recruitment
   facts the moderator can take as given. Leave out the hypotheses and the options being decided.

4. **List what the study must learn** as a short list of learning objectives tied to the decision. A
   question that serves none is cut or marked `if time`.

5. **Collect candidate questions.** With a guide: copy every question exactly, in the user's order.
   Without one: draft them from the objectives. The request's own wording ("why they left") is a research
   question for the team, never a question to put to participants word for word.

6. **Rewrite each question** until none of these problems applies, and record every change in the rewrite
   table. Say which questions passed unchanged.

   | Problem | How to spot it | Rewrite pattern |
   |---|---|---|
   | Leading | Contains the answer, a judgement or a cause ("was price the reason") | Remove the assumption; ask what happened |
   | Closed | Answerable with yes, no or one word | "Tell me about…", "Walk me through…" |
   | Rating or scale | "How satisfied…", "on a scale of 1 to 10", "how much did you enjoy" | Ask for a specific episode; leave counting and rating to a survey |
   | Hypothetical or future | "Would you", "will you", "if we" | Ask about the last time it actually occurred: what they did, used or paid |
   | Double-barreled | Two questions, or two objects joined by "and" or "or" | Split; keep what the objective needs, make the rest a probe |
   | Generalising | "Usually", "in general", "how often" | Anchor to one occasion: "the last time…" |
   | Jargon or internal names | Words the participant would not use | Their words; describe the thing |
   | Pitching | Describes or defends the product | Delete the description; ask about the problem it was meant to solve |
   | "Why" about an action or omission | "Why didn't you…", "Why did you cancel" | "What led to…", "What was going on when…" |

   A plain "why" is acceptable only about a view or preference the participant has just stated ("Why that
   one?"). About something they did or did not do, it reads as a demand to justify; use "what" or "how".
   A rewrite may not change what the question is for. If no honest rewrite serves the objective (a demand
   forecast from "would you pay"), say so and cut it. A rewrite may become a probe under another question.
   In a concept-reaction study, show the stimulus with minimal framing, ask for the first impression before
   any preference or comparison, place it after the past-behaviour questions, and never report the reaction
   as evidence of demand. Attach the stimulus to its question ("show only at this question"), never to the
   context block, so the moderator cannot reveal it early.

7. **Order the questions as a funnel:** an easy warm-up about the participant's own context; the broad
   story ("walk me through the last time…"); the specific topics; any direct check; last, always, "Is there
   anything I did not ask about that I should have?". Then make a redundancy pass: no two questions may
   ask for the same account, because the moderator will ask both.

8. **Set a probe depth for every question,** not one flat limit:

   | Depth | Follow-ups (this skill's convention) | Use for |
   |---|---|---|
   | none | 0 | Warm-up, a short factual check needed for routing, the last question |
   | light | up to 1 | Context the decision does not turn on |
   | deep | up to 3 | The few questions the decision turns on |

   Tools name and count their levels differently. In the tool, choose the setting nearest to the brief's
   depth for each question, and never pair detailed probing instructions with a no-follow-up setting.

9. **Fit the list to the time budget.** Plan about one interviewer turn per minute (a figure from typed
   interviews; time a voice pilot). A question costs at most one turn plus its follow-ups: none 1, light 2,
   deep 4. The sum is a ceiling and must stay at or under the budget: in 20 minutes, for example, a
   warm-up, three deep and three light questions and the last question (1 + 12 + 6 + 1 = 20). Then try to
   cut two more questions (a practitioner heuristic): if the decision survives without them, they go.
   Promise no completion rate or acceptable length; no source supports a figure.

10. **For each question write probes, a "done when" rule and a skip or branch rule.** Give each probe its
    trigger. A question asks no more follow-ups than its depth allows; alternative probes for different
    triggers are fine if marked "ask at most [n]". A `none` question has no probes.

    | Probe trigger | Example cue | Probe |
    |---|---|---|
    | Vague answer | "it was fine", "too expensive" | "Think of the last time. What happened?" / "What does 'expensive' mean for you here?" |
    | Emotion | "annoyed", "relieved", "gave up" | "What happened just before that?" |
    | Contradiction | Loved it, yet cancelled | "Earlier you said X, and now Y. How do those fit together?" |
    | First mention of a workaround or substitute | "I just used a spreadsheet" | "Walk me through how you do that, step by step." |

    - **Done when:** the condition that lets the moderator move on before the depth is used up, stated as
      what the answer must contain ("one specific occasion, and what led to it"). To go one level deeper on
      a reason, use "What makes that important to you?".
    - **Skip / branch if:** in plain language. "Skip if the participant already described cancelling."
      "If they name another service, ask how they came to choose it."
    - **Failure stops, for all questions:** move on after two "I don't know" answers, a repeated answer or
      discomfort; if the participant cannot answer, ask once from a different angle.

11. **Write the avoid list.** Study-specific items: sensitive areas, the hypotheses and the decision, names
    the moderator must not introduce first, personal data it must not request, anything that sounds like
    an offer. Say what happens when the participant raises a sensitive topic unprompted: one neutral
    sentence, no probing, on to the next question. The general behaviour rules (one question per turn, no
    leading, praise, advice, pitching or promises) go into the custom-LLM prompt, see step 14.

12. **Write the consent screen, the opener and the closing,** word for word. Disclosure and consent sit on
    a fixed screen *before* the session: the interviewer is an AI, not a person; who runs the study and
    why; how long it takes; that it is recorded or kept as a transcript, and whether audio or video is
    stored; who reads it and that an AI model provider processes it; how answers are used and whether
    quotes are anonymous; how long it is kept; that the participant may skip a question or stop; how to ask
    for deletion. For voice or video, the consent button names the recording, since some places require
    every party's agreement to be recorded. Consent asked mid-conversation leaves unconsented partial
    sessions when someone declines. The moderator's opener is then short: one sentence repeating that it is
    an AI, and question 1, which every question list then marks as already asked. Only when the setup has
    no screen does the opener carry the full text and wait for agreement. The closing thanks, says what
    happens next, gives a contact, praises nothing and promises nothing. Leave `[...]` for unknown facts;
    invent no retention period or incentive. Say once: not legal advice.

13. **Choose the modality,** and for voice the sub-mode (real-time or turn-based), with the trade-off for
    this study in two or three lines. Default to text. The comparison is in
    [references/hosted-tools-and-modality.md](references/hosted-tools-and-modality.md).

14. **Assemble the brief** from [references/brief-template.md](references/brief-template.md). It ends with
    two alternatives, and they differ on purpose:
    - **Hosted tool:** the placement table (which part goes into which kind of field) and a short block of
      study-specific instructions addressed to the moderator. Hosted moderators already ask one question
      at a time and stay neutral; a few concrete instructions work better than long general guidance.
    - **Custom LLM:** the paste-ready prompt with the full behaviour rules, skip and stop handling, the end
      signals, the safety exit and the answers to "are you a human?" and to attempts to instruct the
      moderator, with every cross-reference replaced by its text.
    Both must repeat the brief exactly: same questions, order, depths, probe triggers, glossary and rules.
    If the user names only one target ("write the prompt for my AI interviewer"), write that one and say
    the other is available.

15. **Add the test plan and the analysis plan** (see Output), then run the checks.

A complete example, from a pasted guide to the finished brief, is in
[references/worked-example.md](references/worked-example.md).

## Output

Always these six parts, in this order, each under its own heading:

1. **AI interview brief**: the filled template, sections 1 to 10 (goal and decision; participants; context
   for the moderator; must-ask questions with depth, probes, "done when" and skip rules; probe rules; avoid
   list; consent screen and opener; closing; length and modality; hosted-tool placement and custom-LLM
   prompt).
2. **Rewrite table**: `# | Original question | Problem | Rewrite | Why`. One row per original question
   that changed or was cut, then a line listing the questions kept, cut and added. With no guide and no
   draft questions from the user: "No guide supplied; nothing to rewrite."
3. **Test plan**: the self-run, the five test participants, the pilot checklist, the field-monitoring list
   and the coverage log from [references/test-and-monitor.md](references/test-and-monitor.md), copied in
   full with the study's numbers filled in. The order is fixed: take the interview yourself, role-play the
   test participants, pilot 3 to 5 real interviews, revise, launch, monitor.
4. **Analysis plan**: three to five lines. The unit is the interview. Keep the coverage log. Code
   transcripts with a codebook and count participants, not mentions (`open-ended-coding` does this, if
   installed). When themes are compared, compare unprompted first mentions only, and report mentions
   after a cue separately. Quotes illustrate a theme, they do not size it. Hypothetical answers are not
   evidence of demand.
5. **Open points**: placeholders to fill, assumptions made, what interviews cannot answer here.
6. **Evidence**: one line: AI-moderated interviewing is supported by a few recent studies, not a settled
   literature; the pilot is the real check.

## Checks before answering

Each check is a statement that must be true. Fix any that is not before sending.

- The decision is stated, or marked "not stated" and listed as an open point.
- You asked the user at most one question.
- Every must-ask question serves a named learning objective, and none repeats another.
- Every must-ask question is open, about one thing, free of a suggested answer, and about something that
  already happened, or marked as a reaction question. Exempt: the opener's warm-up when it is a factual
  check needed for routing, and the closing "anything I did not ask" question.
- The rewrite table quotes each original exactly, and each rewrite keeps its purpose.
- Every question has a probe depth, triggers for its probes, a "done when" rule and a skip or branch rule
  (or "never").
- The maximum turns (none 1, light 2, deep 4) stay at or under the turn budget.
- Every "why" is about a view or preference just stated, none about an action or omission, and the context
  block holds no hypothesis.
- The avoid list covers the study's sensitive areas and offers, and says what to do when one comes up.
- Disclosure and consent are on a screen before the session and say AI, recording, who processes and reads
  it, use, retention, the right to skip or stop, and deletion; the opener is short.
- The last question is "anything I did not ask", and the closing praises and promises nothing.
- The modality (and the voice sub-mode) is chosen, with the trade-off for this study.
- The hosted block holds only study-specific instructions; the custom prompt holds the behaviour rules,
  skip and stop handling, end signals, safety exit, the "are you a human?" answer and the rule for
  instruction attempts, with no unfilled cross-reference.
- Both match the brief word for word, and question 1 is not asked twice.
- The test plan (self-run first), the analysis plan and the open points are there.
- Every sibling skill you name comes with what to do if it is not installed.
- Every number comes from [references/sources.md](references/sources.md), conventions and vendor
  conventions are called that, and nothing promises a completion rate, sample size or saturation beyond
  the sources.

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `survey_create` and `question_create` (the consent question and the interview question, mapped in [references/questionpunk-fields.md](references/questionpunk-fields.md)), `survey_get` (read back against the brief), `survey_publish` (open it after the pilot), `responses_read` (pilot transcripts for the checklist; page with `nextCursor` until it is exhausted, keep real, completed responses only, and reconcile the count with the pilot before grading). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
