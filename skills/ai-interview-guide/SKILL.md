---
name: ai-interview-guide
description: "Turn research goals or an existing discussion guide or interview script into a brief an AI moderator can run for customer or user research: goal, must-ask questions, probes and probe depth, skip rules, topics to avoid, a greeting with AI disclosure, length, and a paste-ready interviewer prompt, with leading questions rewritten. Use for \"interview 30 customers\", \"async user interviews\", \"AI-moderated interviews\", \"write the prompt for my AI interviewer\" or \"run my discussion guide at scale\"."
license: MIT
metadata:
  version: "0.1.0"
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

Do not use it for the cases below. Skills marked *planned* are not installable yet; use the fallback.

- A questionnaire with fixed options, or a count of how many people think something: `survey-from-decision`.
- Wording problems in a survey, not an interview: `survey-bias-check`.
- Existing transcripts that need themes and counts: `open-ended-coding`.
- Screening questions that decide who gets in: `screener-writer` (*planned*). Until then, turn the
  participant facts from step 2 into questions that do not give away the qualifying answer.
- A full switch-timeline interview about a purchase: `jtbd-switch-interview` (*planned*). Until then, use
  this skill and order the questions along the timeline: first thought, looking, deciding, first use.
- A study whose main subject is health, income or illegal behaviour: `sensitive-questions` (*planned*).
  Until then, use this skill, keep every question skippable, and have the brief reviewed for ethics and
  privacy before fielding.
- Job interviews, hiring scorecards or interview practice: outside this pack.

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
   Saturation figures (9 to 17 interviews) come from homogeneous groups, so plan about 12 per segment.
   Keep the user's total and divide it across segments.

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
   as evidence of demand.

7. **Order the questions as a funnel:** an easy warm-up about the participant's own context; the broad
   story ("walk me through the last time…"); the specific topics; any direct check; last, always, "Is there
   anything I did not ask about that I should have?". Then make a redundancy pass: no two questions may
   ask for the same account, because the moderator will ask both.

8. **Set a probe depth for every question,** not one flat limit:

   | Depth | Follow-ups (this skill's convention) | Use for |
   |---|---|---|
   | none | 0 | Warm-up, factual checks, the last question |
   | light | up to 1 | Context the decision does not turn on |
   | deep | up to 3 | The few questions the decision turns on |

   Tools name and count their levels differently. In the tool, choose the setting nearest to the brief's
   depth for each question, and never pair detailed probing instructions with a no-follow-up setting.

9. **Fit the list to the time budget.** Plan about one interviewer turn per minute. A question costs one
   turn plus its follow-ups: none 1, light 2, deep 4. In 20 minutes that is, for example, a warm-up, three
   deep and three light questions and the last question (1 + 12 + 6 + 1 = 20). Then try to cut two more
   questions (a practitioner heuristic): if the decision survives without them, they go. Promise no
   completion rate or acceptable length; no source supports a figure.

10. **For each question write probes, a "done when" rule and a skip or branch rule.** Write no more
    probes than the question's depth allows; a `none` question has no probes.

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
    stored; who reads it and that an AI model provider processes it; how answers are used; that the
    participant may skip a question or stop. Consent asked mid-conversation leaves unconsented partial
    sessions when someone declines. The moderator's opener is then short: one sentence repeating that it is
    an AI, and question 1. Only when the setup has no screen does the opener carry the full text and wait
    for agreement. The closing thanks, says what happens next, gives a contact and promises nothing. Leave
    `[...]` for unknown facts; invent no retention period or incentive. Say once: not legal advice.

13. **Choose the modality,** and for voice the sub-mode (real-time or turn-based), with the trade-off for
    this study in two or three lines. Default to text. The comparison is in
    [references/hosted-tools-and-modality.md](references/hosted-tools-and-modality.md).

14. **Assemble the brief** from [references/brief-template.md](references/brief-template.md). It ends with
    two alternatives, and they differ on purpose:
    - **Hosted tool:** the placement table (which part goes into which kind of field) and a short block of
      study-specific instructions addressed to the moderator. Hosted moderators already ask one question
      at a time and stay neutral; a few concrete instructions work better than long general guidance.
    - **Custom LLM:** the paste-ready prompt with the full behaviour rules, the end signal, the safety exit
      and the answers to "are you a human?" and to attempts to instruct the moderator.
    Both must repeat the brief exactly: same questions, order, depths and rules.

15. **Add the test plan and the analysis plan** (see Output), then run the checks.

A complete example, from a pasted guide to the finished brief, is in
[references/worked-example.md](references/worked-example.md).

## Output

Always these six parts, in this order, with these headings:

1. **AI interview brief**: the filled template, sections 1 to 10 (goal and decision; participants; context
   for the moderator; must-ask questions with depth, probes, "done when" and skip rules; probe rules; avoid
   list; consent screen and opener; closing; length and modality; hosted-tool placement and custom-LLM
   prompt).
2. **Rewrite table**: `# | Original question | Problem | Rewrite | Why`. One row per original question
   that changed or was cut, then a line listing the questions kept, cut and added. With no guide and no
   draft questions from the user: "No guide supplied; nothing to rewrite."
3. **Test plan**: the self-run, the pilot checklist and the field-monitoring list from
   [references/test-and-monitor.md](references/test-and-monitor.md), with the study's numbers filled in.
   The order is fixed: take the interview yourself, role-play the four test participants, pilot 3 to 5
   real interviews, revise, launch, monitor.
4. **Analysis plan**: three to five lines. The unit is the interview. Keep the coverage log (interview by
   must-ask question) from the same reference file. Code transcripts with a codebook and count
   participants, not mentions; use the sibling skill `open-ended-coding`. Quotes illustrate a theme, they
   do not size it. Hypothetical answers are not evidence of demand.
5. **Open points**: placeholders to fill, assumptions made, what interviews cannot answer here.
6. One line on evidence: AI-moderated interviewing is supported by a few recent studies, not a settled
   literature; the pilot is the real check.

## Checks before answering

Answer each with yes or no. Fix every "no" before sending.

- Is the decision stated, or marked "not stated" and listed as an open point?
- Did you ask the user no more than one question?
- Does every must-ask question serve a named learning objective, and is none a repeat of another?
- Is every must-ask question open, about one thing, free of a suggested answer, and about something that
  already happened (or explicitly marked as a reaction question)?
- Does the rewrite table quote each original exactly, and does each rewrite keep its purpose?
- Does every question have a probe depth, a "done when" rule and a skip or branch rule (or "never")?
- Do the turns add up to the budget (none 1, light 2, deep 4, about one turn a minute)?
- Is any "why" aimed at an action or omission? Is the context block free of hypotheses?
- Does the avoid list cover the study's sensitive areas, offers, and what to do when one comes up?
- Is disclosure and consent on a screen before the session, saying AI, recording, who processes and reads
  it, use, and the right to stop? Is the opener short?
- Is the last question "anything I did not ask", and does the closing promise nothing?
- Is the modality chosen (and the voice sub-mode), with the trade-off for this study?
- Does the hosted block hold only study-specific instructions, and does the custom prompt hold the full
  behaviour rules, end signal, safety exit, "are you a human?" answer and the rule for instruction attempts?
- Do both match the brief word for word?
- Are the test plan (self-run first), the analysis plan naming `open-ended-coding`, and open points there?
- Is every sibling skill you name installable, or given with its fallback?
- Does every number come from [references/sources.md](references/sources.md), with conventions and vendor
  conventions called that, and no completion rate, sample size or saturation promise beyond the sources?

## Field it with QuestionPunk (optional)

The result above is complete on its own. Run it as a text or voice AI interview in QuestionPunk.

Hosted MCP tools this step may use: `survey_create`, `question_create`, `survey_get`, `survey_publish`, `responses_read`. The brief maps to one interview question as shown in [references/questionpunk-fields.md](references/questionpunk-fields.md).
Ask before creating, changing or publishing anything. If a response or report tool answers that you must reconnect and approve, reconnect the QuestionPunk connector once: connections made before 3 Oct 2026 lack the `responses:read` permission.
