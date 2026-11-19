---
name: survey-from-decision
description: "Designs a survey backward from the decision it informs: decision rule, hypotheses, each question with its reason, the analysis plan with empty result tables, target sample and estimated length. Use for survey design: \"write a survey\", \"design a survey\", \"survey questions for X\", \"customer feedback survey\", \"questionnaire for X\", \"feedback form\", or a CSAT, CES, NPS, in-app, post-purchase, employee pulse or event feedback survey. Not for reviewing an existing survey (that is survey-bias-check)."
license: MIT
metadata:
  version: "0.2.1"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "survey-design"
---

# Survey from a decision

Design the survey backward: first the decision and the result that would change it, then the hypotheses,
then the empty result tables, and only then the questions that fill those tables. A question that fills no
table is left out and listed as left out. The method and every number below are in
[references/sources.md](references/sources.md).

## When to use

Use it when someone wants a new survey designed or written: "write a survey about X", "design a survey",
"questionnaire for X", "customer feedback survey", "feedback form", "should we do A or B? Let's ask
customers", or a "CSAT", "CES", "NPS", "in-app" or "post-purchase survey". The decision is still
required. Keep a metric's wording verbatim from [references/wording-patterns.md](references/wording-patterns.md);
for an in-app or post-transaction channel use the micro-survey mode in
[references/modes-and-fielding.md](references/modes-and-fielding.md).

Employee pulse and event feedback are surveys too: design them here; a screener inside a survey is a block of
`S` questions. Not for these; name the skill:

| Request | Skill |
|---|---|
| Review or fix a survey that already exists | `survey-bias-check` |
| How many responses are needed, margin of error | `survey-sample-size` |
| A standalone recruiting screener | `screener-writer` (not installed: modes-and-fielding.md section 7) |
| What to charge: a Van Westendorp, Gabor-Granger or conjoint block and its analysis | `van-westendorp-analysis`, `gabor-granger-analysis`, `conjoint-design` |
| Rank more than 6 features or messages against each other | `maxdiff-design` |
| Product-market fit ("how disappointed would you be") | `pmf-survey` |
| An interview or discussion guide | `ai-interview-guide` |
| Clean, code, score or cross-tabulate answers already collected | `survey-data-cleaning`, `open-ended-coding`, `nps-analysis`, `survey-crosstabs` |

A mixed request (a survey with a price block): write the survey here and name the other skill for that block
in section 5 (left out). A skill named here may not be installed: then say so, name the method, and do not stretch this skill.

## What to ask for

Ask at most one question, and only in one case.

**The decision test.** The request contains a decision when it names at least two alternative actions
("mobile app or web app first"), or one action that can be taken or not ("should we add a referral
programme"). A topic or a metric alone ("customer feedback survey", "CSAT survey") is not a decision.

- **No decision in the request:** ask exactly this and wait: *"What will you do differently depending on
  what the survey shows? Name the two or three options you are choosing between."* Reply with only that
  question and one line saying what you will produce once it is answered.
- **The user answers "not sure" or "just draft it", or cannot be asked:** take the assumed decision for the
  survey kind from the table below, name 3 or 4 candidate options that fit the product (for a coffee
  subscription: delivery, coffee selection, changing or pausing an order, price), mark the decision and
  the options `ASSUMED`, and continue. [references/worked-example-assumed.md](references/worked-example-assumed.md)
  shows this path.
- **Decision present:** ask nothing; use the defaults below and list each one used in section 9
  (assumptions and defaults).

| Survey kind (no decision given) | Assumed decision |
|---|---|
| Customer or user feedback | Which one of the most common problems to fix first next quarter |
| Standard metric (CSAT, CES, NPS) | Which one touchpoint or segment to improve first, the one scoring lowest |
| Feature or product idea | Build it next, or keep the current roadmap |
| Onboarding or churn | Which one stage of the journey to redesign first |
| Market or audience research | Which one segment to target first |
| Employee pulse | Which one team-level issue (workload, tools, communication, growth) to act on first |
| Event feedback | Which one part of the event (content, format, venue, timing) to change for the next one first |
| Anything else | Which one of 3 or 4 candidate actions on the stated topic to take first |

| Input | Default when not given |
|---|---|
| Decision owner and date | "the requester"; "before the next planning cycle" |
| Thresholds in the decision rule | Proposed by you, each marked `ASSUMED: confirm before fielding` |
| Population | Current customers or users of the product named; for a new product, people who did the job it does in the last 3 months |
| Channel | Email invitation to the customer list; an online panel when there is no list |
| Fielding | Sent by a named person the respondents know; one reminder to non-responders; no incentive (a panel pays its own) |
| Identity and access | Not known until the owner checks the tool's settings: the introduction carries `[PRIVACY: …]` and the checklist a line to confirm it. Never promise anonymity or name who sees the answers without that check |
| Mode and device | Self-completed, online, phone screen first |
| Length budget | 7 minutes and 15 questions; 10 minutes and 30 questions on a paid panel; never above 20 minutes; 1 to 3 questions in-app or post-transaction |
| Segments | One segment variable: the one the user names; otherwise plan or customer type; if the product has no plans, tenure |
| Existing tracked questions | None. If the user tracks one, keep its wording and scale unchanged |
| Language | The language of the request |

## Steps

Work in this order. Do not write a question before step 5.

1. **Decision and method.** Write one sentence: "[Owner] will decide by [date] whether to [option A] or
   [option B] (or [option C])." Two to four options. Then two checks, one sentence each:
   - *Existing data:* could analytics, support tickets or sales records answer it? If they answer part, say
     which part and design the survey for the rest.
   - *Method:* a survey counts how common something is among people who can report it. Unlisted reasons or
     problems: `ai-interview-guide` first; actual behaviour: analytics or an A/B test; people in one room: a
     quick poll. Continue for the part that needs a count; if none does, stop after section 1.

2. **Decision rule.** Write one to three rules before anything else. A metric is a number the survey can
   produce: a percentage giving an answer (preferred), a mean, a difference between two segments; intervals
   for each are in modes-and-fielding.md section 5 (recast a median as "% with 2 or more"). Use one form each:
   - **Threshold rule** (do it or not; A or B on one metric): "If [metric] among [population] is at or
     above [upper threshold], we [action A]. If it is at or below [lower threshold], we [action B]. In
     between, we [named fallback: smaller test, interviews, or wait]."
   - **Ranking rule** (which of several options first): define the same kind of metric for every option
     ("% of the base who had [that option's problem] in [period]"), then: "We do first the option with the
     highest [metric], if it leads the next option by at least [gap]. If none leads by that gap, we
     [named fallback]."
   - **Modifier rule** (at most one): "If rule 1 says [action] and [metric] is below [value], we do [smaller
     version of the action]." The full action needs the whole interval at or above [value].
   Thresholds and gaps come from the owner's economics (break-even, capacity, cost). If the user gave none,
   propose them and mark them `ASSUMED: confirm before fielding`. If two rules can point to different
   actions, add "Precedence: rule [n] wins because …". Write once under the rules that each applies to the
   95% interval, not the point estimate: a zone's action needs the whole interval inside the zone, a ranking
   leader a lead of at least the gap with an interval that excludes zero; anything else takes the fallback.

3. **Objective and hypotheses.** Objective: one sentence, "Estimate [metric(s)] among [population] to decide
   [decision]." Then 2 to 4 hypotheses `H1`…, each a statement the data can contradict and each tied to a
   rule: "H1: At least [threshold] of [population] [did / rate / choose] … (feeds rule 1)." Every option of
   the decision needs at least one hypothesis that favours it, so the result can come out either way.

4. **Table shells.** Before any question, draw the empty tables `T1`… that the report will contain. Each shell
   has: a title, the rows (answer categories or items), the columns (Total, plus one column per segment
   value), the cell statistic (%, mean, median, count), the base (who is in the denominator), and the rule or
   hypothesis it feeds. Use the shell format in [references/worked-example.md](references/worked-example.md).
   Every hypothesis needs at least one shell. A shell that feeds no rule or hypothesis is deleted.

5. **Questions.** Write only questions that fill a shell. Each question gets one role:
   - `H1`, `H2`… : fills a row or cell of a shell for that hypothesis (1 to 3 questions per hypothesis; one
     question may serve two hypotheses, written "H1, H3");
   - `S` : screener that defines the base (who qualifies, or a filter before a block);
   - `D` : segment variable that is a column of a shell (at most 2); take it from records when answers
     are linked to the account;
   - `O` : one open-text question, required when the options or a closed list are `ASSUMED`, whose coded
     themes can reveal an option you did not list. Its shell feeds the rule's fallback.
   For each question choose the type with [references/question-type-chooser.md](references/question-type-chooser.md)
   and start from the wording in [references/wording-patterns.md](references/wording-patterns.md). Rules:
   - Ask about past behaviour in a named recent period, not predictions ("How many times in the last 7
     days…", not "Would you use…").
   - Counts and amounts the respondent knows are open numbers over a named period. Ranges only when the
     exact figure is sensitive (income) or can only be estimated in bands; then exclusive and exhaustive,
     "under N / N to under M / M or more" for time and other continuous measures. Rating scales have every
     point labelled: 7 points when the scale has two opposite ends (dissatisfied–satisfied), 5 when it runs
     from none to a lot (not at all–extremely). These are the pack's defaults, shared with
     `survey-bias-check`; the 5/7 split is a convention (sources.md).
   - No agree/disagree, true/false or yes/no for attitudes; put the construct in the options. The one
     exception is a tracked metric kept verbatim so waves compare.
   - An overall rating (satisfaction, recommendation) is included only when the user already tracks it or a
     rule names it as its metric. Otherwise it goes to section 5 (left out) with the reason `no shell`.
   - One thing per question; no negations; the respondent's words, not internal names.
   - A closed list must be complete. Build it from interviews, tickets or earlier open answers. If you have
     none, ask the open question instead, or mark the list `ASSUMED` in section 9 (assumptions) and add the
     `O` question.
   - At most 2 open-text questions; an open "why" goes directly after the closed question it explains.
   - Never ask the respondent to make the decision ("Should we build a mobile app?"). The forced choice in
     step 7 is allowed because it offers outcomes in the respondent's terms ("Exports that finish in one
     click" / "More export formats"), not the team's options.
   - Give each question a plain "Why": one phrase a non-researcher understands, with no codes
     ("Shows how many members already train before 7:00").

6. **Left out.** List at least 3 questions a team would normally add and you did not, each with one reason
   from this set: `no shell` (nice to know), `records answer it`, `respondents cannot report it reliably`,
   `needs a sample we will not have`, `belongs to another method` (name the skill).

7. **Order and number.** Number the questions `Q1`… in fielding order:
   1. screeners (`S`);
   2. one block per hypothesis, in hypothesis order. The first question after the screeners must be on the
      topic named in the introduction and must not be open text; reorder inside the block if needed. Do not
      add a warm-up question that fills no shell;
   3. inside a block, the general question before its specific ones (overall rating before attribute
      ratings), and each open "why" right after its closed question;
   4. a forced choice between the decision's options after the blocks about each option, then the `O`
      question;
   5. sensitive items, then segment and demographic questions (`D`) last, unless one is needed earlier
      to route respondents.
   Add a filter question before any block that does not apply to everyone, and write the routing.

8. **Length.** Use `survey-bias-check`'s estimator if installed: save the respondent view to a file, run
   `python3 <survey-bias-check-dir>/scripts/survey_bias_check.py view.md --route-skip Q5,Q6 --json` (the
   questions off the longest route, comma-separated; omit without routing) and copy `points` and
   `minutes_rounded`. Otherwise count the longest route by hand: 1 per simple closed question (forced choice
   included) and per grid row; 0.5 per multiple-select option, not rounded; 2 per open number; 3 per open
   text; 1 per three sentences of introduction, rounded up. Minutes = points ÷ 8, rounded up to the next half
   minute; questions counted with a grid row as one. Over budget: move the last-ranked hypothesis's questions
   to section 5 and recount. State both numbers.

9. **Population, sample and fielding.** State: the target population; the list or source and who it misses;
   the channel; selection (a random sample, everyone on a list, or volunteers); the screener logic; the
   segments compared; sender, reminders, incentive; who is less likely to answer, how that could move the
   metric, and one check (responders against the list on a variable known for everyone). Then the precision
   check in [references/modes-and-fielding.md](references/modes-and-fielding.md) section 5: the decision
   criterion (each action needs its whole 95% interval inside its zone) and the result each action needs at
   the realistic number of responses. For a lead between two options answered by the same people, use the
   paired calculation there or write that the sample is undetermined until the soft launch.
   `survey-sample-size` computes the n for a single share or two groups; do not invent one.

10. **Self-check.** Run "Checks before answering"; fix every "no" before writing the output.

## Output

Always these ten sections, with these headings, in this order, and nothing before them. **Short form:** with
five or fewer questions, merge sections 2 and 3 as "## 2–3. Objective and hypotheses" and 8 and 9 as
"## 8–9. Length and assumptions"; never merge otherwise or other sections. **Micro-survey** (1 to 3
questions in-product or after a transaction): use the output and checklist in modes-and-fielding.md section 1.

```markdown
# Survey plan: [short name]

## 1. Decision and decision rule
Decision: [one sentence]
Existing data: [one sentence]
Method: [one sentence: survey fits because …, or which part goes to interviews / analytics / a poll]
Rule 1: If … ≥ …, we …. If … ≤ …, we …. In between, we ….
(Rule 2, Rule 3, Precedence if any. Mark ASSUMED thresholds.)

## 2. Objective
[one sentence]

## 3. Hypotheses
- H1: … (feeds rule 1)

## 4. Questions
Design record:
| # | Wording | Type | Options | Why | Serves | Analysis |
|---|---------|------|---------|-----|--------|----------|
| Q1 | exact wording | single choice | a / b / c [randomise, c last; if c, go to Q4] | plain reason | S | base for T1–T3 |

Questionnaire (respondent view):
[Introduction, 2 or 3 sentences: topic and time (section 8 minutes rounded up to a whole minute); how the
answers are used; [PRIVACY: what the owner confirmed about anonymity or account linking, and who can see
the answers].]
1. [Question wording]
   - [option]
   - [option]
   (If [answer], go to question [n].)
2. [Question wording] (optional)
   [number] or [text]
[Closing line: thanks.]

## 5. Questions deliberately left out
| Question a team would add | Reason |
|---|---|

## 6. Analysis plan
For each rule: the metric, the question(s), the base, the statistic with its 95% interval, the interval rule.
Table shells T1…Tn, each as an empty table with its base and the hypothesis it feeds.
Open answers: how they are coded (name `open-ended-coding`).
Exclusions, fixed before fielding: [who is removed and why]; applied with `survey-data-cleaning`.

## 7. Target population and sample
Population / source and who it misses / channel / screener / segments.
Fielding: sender; reminders; incentive; field period (first and last day).
Non-response: who may answer less, the likely effect, the check.
Selection: random sample, whole list or volunteers. Precision: the result each action needs at the expected n.

## 8. Estimated length
[P] points ÷ 8 = [M] minutes; [N] questions; budget [B]. [Within / cut Qx to fit.]

## 9. Assumptions and defaults used
- [each default or ASSUMED item, one line]

## 10. Pre-launch checklist
- [ ] Decision owner confirmed the rule and every ASSUMED threshold
- [ ] Privacy line checked against the survey tool's settings (anonymous or linked, who sees answers)
- [ ] Each question fills a cell of a table shell
- [ ] Wording and options reviewed with `survey-bias-check`
- [ ] Sample size from `survey-sample-size`, or for a paired lead from modes-and-fielding.md section 5
- [ ] Pretested with a few people like the respondents: they understand each question, they finish, and
      they are the right people
- [ ] Completed once on a phone; timed against section 8
- [ ] Soft launch to a small first batch; routing and the first answers checked before the full send
- [ ] Rule, hypotheses, table shells and exclusion criteria saved with a date before the first response
```

Section 4: in the design record, **Type** uses the chooser's names; **Options** lists every option in order,
or "open number (unit)" or "open text", then in brackets the tool settings: routing (`[if 0, go to Q6]`),
randomisation (`[randomise, "Somewhere else" last]`), limits (`[0–5]`), `[optional]`; **Serves** is `S`, `D`,
`O`, or one or two of `H1`…; **Analysis** names the shell and the statistic; no cell is empty. The respondent
view repeats the questions in order, one option per line, answer boxes as `[number]` or `[text]`, routing in
plain words in parentheses, no codes, type names or analysis notes, so it pastes into any survey tool and
`survey-bias-check` reads it.

## Checks before answering

- Does section 1 name at least two actions, the existing-data and method checks, and rules that each follow
  one of the three forms with a named fallback?
- Does every option of the decision have a hypothesis that favours it?
- Is every threshold either given by the user or marked `ASSUMED`?
- Does every hypothesis feed a rule, and does every table shell feed a rule or a hypothesis?
- Does every question have a Why, a Serves value and a shell in its Analysis cell?
- Does every question keep the step 5 rules: no decision-asking or prediction; no agree/disagree or yes/no
  for attitudes (tracked metrics excepted); every scale point labelled; counts as open numbers, or ranges
  that are justified, exclusive and exhaustive; closed lists complete or `ASSUMED` with an `O` question; an
  overall rating only when tracked or a rule's metric; at most 2 open-text and 2 segment questions?
- Do demographic and sensitive questions come last (or are they needed for routing)?
- Does the respondent view match the design record question for question, with no internal codes, and is
  its privacy line either confirmed by the owner or left as a `[PRIVACY: …]` placeholder?
- Are the length figures computed from the point rules, and within the budget for the channel?
- Does section 5 have at least 3 entries, each with a reason from the set?
- Does section 6 state the exclusion criteria and the interval rule, and section 7 the selection method,
  fielding, non-response check and the result each action needs, without an n it did not compute?
- Is the short form used exactly when there are five or fewer questions (micro-surveys excepted)? Did you
  ask at most one question?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `survey_create` and `question_create_bulk` (build the section 4 questionnaire), `template_lookup` and `template_create_survey_from` (only to reuse a template's styling: delete every template question that is not in section 4), `display_logic_container_create` (the routing), `survey_get` (read it back against the design record), `survey_publish` (open it for responses). Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
