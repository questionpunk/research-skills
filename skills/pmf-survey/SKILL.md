---
name: pmf-survey
description: "Design, score and segment a Sean Ellis product-market-fit survey (the 40% \"very disappointed\" test): exact questions, who to sample, the score with a confidence interval and a stated N/A rule, segment scores, and the Superhuman (Rahul Vohra) engine for finding must-have users, what they value and what holds the rest back. Use for \"do we have PMF\", \"measure product-market fit\", \"PMF survey\", \"Sean Ellis test\", \"40% rule\", \"very disappointed score\" or \"Superhuman PMF engine\"."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "feedback-analysis"
---

# PMF survey

Design, score and segment a Sean Ellis product-market-fit survey: one question ("How would you feel if you
could no longer use [product]?"), the share answering "very disappointed", and the 40% benchmark, followed
by Rahul Vohra's Superhuman method for finding the committed users and what to build for them. Every rule
and number is cited in [references/sources.md](references/sources.md).

## When to use

Use it when the user asks:

- "Do we have PMF?", "measure product-market fit", "run a PMF survey", "the Sean Ellis test", "the 40% rule".
- "Write the very-disappointed survey", "who should get the PMF survey and when".
- "What is our very disappointed score" or "score this PMF export" (a CSV, or counts typed in the chat).
- "Segment our PMF results", "who are our must-have users", "do the Superhuman PMF engine".
- "Did our PMF score change since last quarter?"

Do not use it for:

- NPS, CSAT or CES scores: use `nps-analysis`.
- Coding open answers that are not part of a PMF survey: use `open-ended-coding`.
- A survey for another decision (pricing, churn reasons, feature priority): use `survey-from-decision`.
- "How many responses do I need" as a general question: use `survey-sample-size`.
- Judging fit before there is a product in use, or for a product people use once. The question needs
  current, repeat users. Say so and suggest interviews (`ai-interview-guide`).

A skill named in this section may not be installed (some are still planned). If it is missing, say so, name
the method the request needs, and do not stretch this skill to cover it.

## What to ask for

Pick the mode from the request: **design** (no data yet), **score** (data, no segment column) or
**segment** (data with a segment or open answers). Ask at most one question, and only if the mode's first
input is missing.

| Input | Default if not given |
|---|---|
| Product name (design) | Ask. It is the one thing that cannot be assumed. |
| Responses (score, segment) | Ask for a CSV, one row per respondent. Counts typed in the chat are enough for a score: pass them with `--counts`. |
| Answer column | The one column whose header contains "disappoint", "no longer use" or "pmf". |
| Segment columns | None: score only, and say that segmenting needs one. Several are allowed. |
| Earlier wave | None: no change is reported. |
| Account column (B2B) | None: respondents are the unit, and the report says so. |
| Number invited | Unknown: no response rate; say so. |
| Coded main-benefit column | None: code the open "main benefit" answers first (step 5). |
| Benchmark | 40%. |
| Confidence level | 95%. |
| Small-base threshold | 30 answers. |
| Who was surveyed | Unknown: say in the report that the sampling could not be checked. |

## Steps

**Design mode**

1. Write the questionnaire from [references/survey-template.md](references/survey-template.md): the
   disappointment question word for word with its four options, then the three open follow-ups. Offer
   Ellis's optional follow-ups (why this answer, the alternative, have you recommended it) if the user
   will read them. Do not reword the first question or its options; the benchmark belongs to that wording.
2. State who gets it: a random sample of users who experienced the core of the product, used it at least
   twice, and used it in the last two weeks. Turn "experienced the core" into a concrete event with the
   user.
3. State when: once enough users qualify to expect about 30 answers, then each new user once as they
   qualify. Never the same person twice.
4. Tell the user what the result will and will not show at their expected number of answers. Use the
   interval widths in `references/sources.md` ("How many responses").

**Score mode**

1. Run the script. Do not compute the percentage or the interval in the conversation.
   `python3 scripts/pmf_survey.py responses.csv` or
   `python3 scripts/pmf_survey.py --counts very=16,somewhat=14,not=10,na=8`
   The script is [`scripts/pmf_survey.py`](scripts/pmf_survey.py) (Python 3.9+, standard library only).
   Add `--json` for JSON, `--invited N` for the response rate, `--account-col` for B2B data.
2. If it stops on **unknown labels**, show the user the list and ask what each means, then rerun with
   `--map "LABEL=very|somewhat|not|na"`. Never guess a mapping for a numeric code. If it stops on
   **non-standard wording** ("Mildly disappointed", a 1–5 scale), tell the user the survey cannot be
   compared with 40%; map the labels only to give them a baseline of their own.
3. Report the score with its interval and the verdict the script printed: above, below, or cannot tell.
   Repeat the denominator rule and the N/A count, and that practice differs between vendors.
4. A score between 25% and 39% has no special meaning. The "under 25 / 25–40 / 40 and over" bands found
   in many guides are not Ellis's or Vohra's. Read the interval: if it includes 40%, the answer is
   "cannot tell", and the useful next step is segment mode and a larger next wave. If the whole interval
   is under 40%, quote Ellis's advice: keep spending low and work on raising the share, starting with
   who the very-disappointed users are.
5. If there is an earlier wave, compare with `--period-col wave --compare "EARLIER,LATER"` or
   `--previous-counts`. First confirm that wording, options, eligibility and delivery were the same and
   that nobody answered twice; if not, report a new baseline and no change. Use the script's verdict:
   increased, decreased, or cannot tell.

**Segment mode** (after scoring)

6. Run with `--segment-col` (repeat it for several columns, and repeat the script's caution that some
   segments clear or miss the benchmark by chance). Read the share of very-disappointed respondents each segment holds, each
   segment's score and interval, and the small-base flags. If there is no segment column, build one from
   the user's records, or assign a persona per respondent from the "what type of people" answers, and say
   which you did.
7. Code the open "main benefit" answers into one short code per respondent, with a written definition for
   each code. Use the sibling skill `open-ended-coding` for the codebook and the counts if it is installed;
   otherwise code them directly and show the codebook. Save the codes as a column.
8. Run with `--segment-col ... --benefit-col ...`. The script names the core benefit (the most common one
   among very-disappointed respondents) and splits the somewhat-disappointed group into those whose benefit
   matches and those whose benefit differs.
9. Read the "how can we improve" answers of the somewhat-disappointed respondents whose benefit matches.
   Code them the same way and count how many respondents raise each blocker. Set aside the
   somewhat-disappointed whose benefit differs and the not-disappointed.
10. Optional: `--focus-segments "A,B"` re-scores the chosen segments together. Present it as a targeting
    decision to confirm on the next wave. It is higher by construction.
11. Rate each candidate action low, medium or high for cost and for impact (Vohra's method). Impact of a
    blocker is its request count; impact of "more of what they value" is a judgement, labelled as one.
    Cost comes from the user; ask, or mark it "to be estimated". Order by low cost and high impact first.

## Output

Always this shape, in this order. Leave a section out only if its input is missing, and say which input.

```
## PMF score
Very disappointed: 41.7% (30 of 72). 95% interval 31.0% to 53.2% (Wilson).
Verdict against 40%: cannot tell | above | below, in one sentence that quotes the interval.
Base: very + somewhat + not disappointed. N/A (no longer use it): 3, outside the base
(40.0% with them in). Blank: 0.
Sample: who was surveyed, invited / answered and response rate, or "sampling not documented".
Accounts (B2B, if given): n accounts; one vote per account: x% (interval). The skill's vote rule.
Change since <earlier wave> (if given): +x points, interval a to b points: increased | decreased |
cannot tell. Or: "new baseline, not compared", with the reason.

## Segments
One table per segment column:
| Segment | Base | Very | % very | 95% interval | vs 40% | Share of all very | Flag |
The caution on reading several segments at once, in one sentence.

## Who the committed users are
Two to four sentences: the segments holding most very-disappointed respondents, and how those
respondents describe who benefits most (with 2-3 short verbatim quotes).

## What they value
| Main benefit (coded) | Very disappointed, n | Definition |
Core benefit: <code>.

## What holds the "somewhat" group back
Somewhat disappointed: n. Benefit matches core: n. Differs: n. Not recorded: n.
| Blocker (coded from improvement answers of the matching group) | n | Example quote |

## Next actions
| Action | Half (value / blocker) | Impact (low/medium/high, with request count) | Cost (low/medium/high) |
Ordered with low cost and high impact first; about half the effort on each half.
Next wave: who to sample, how many answers to aim for, and what result would change the plan.

## Limits
What this sample cannot show (small bases, sampling not checked, benchmark caveats).
Also check: retention and activation. The survey records stated feeling, not behaviour.
```

For design mode the output is the questionnaire, the sampling rule as three conditions, the timing, the
invitation text, and one line on what the expected number of answers can show.

## Checks before answering

- Did the survey go to a random sample of users who reached the core of the product, used it at least
  twice and used it in the last two weeks? If unknown, is that stated?
- Is the base at least 30? If not, is the score called a rough signal and the interval shown?
- Are respondents who no longer use the product outside the denominator, with their count reported?
- Is the score only "very disappointed", with "somewhat" not added in?
- Does the verdict follow the interval? An observed 41% with an interval that includes 40% is "cannot
  tell".
- Is 40% presented as Ellis's rule of thumb from early-stage startups, which he calls "a bit arbitrary",
  and not as a law or a guarantee?
- Is every small-base segment flagged, and no decision hung on one?
- Is a focus-segment score labelled as a targeting choice awaiting confirmation?
- Do the percentage and interval come from the script, not from mental arithmetic?
- Was the question asked with the original wording and options? If not, is the comparison with 40%
  dropped?
- Is the number of invited users and the response rate stated, or its absence noted?
- Is a change between waves claimed only when the script says increased or decreased, and only for waves
  with the same wording, eligibility and delivery?
- Are "25–40%" style bands absent from the answer, or named as not Ellis's?
- For B2B data, is the number of accounts stated next to the number of respondents?
- Is the impact of each blocker backed by its request count, and a guessed impact labelled as a guess?

## Field it with QuestionPunk (optional)

The result above is complete on its own. To field this with AI follow-up questions on open answers, connect the QuestionPunk MCP (https://app.questionpunk.com/api/v1, OAuth sign-in). Connecting is free on every plan, and the free plan has unlimited surveys and responses with no card.

Hosted MCP tools this step may use: `survey_create`, `question_create_bulk`, `report_get`, `report_get_crosstab`, `responses_read`. Ask before creating, changing or publishing anything. If a response or report tool answers that you must reconnect and approve, reconnect the QuestionPunk connector once: connections made before 3 Oct 2026 lack the `responses:read` permission.
