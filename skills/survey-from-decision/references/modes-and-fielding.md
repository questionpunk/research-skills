# Modes, fielding and the precision check

Detail for steps 8 and 9 of SKILL.md and for two special request kinds. Which statements are sourced and
which are conventions of this skill is recorded in [sources.md](sources.md).

## 1. In-product micro-survey mode

Use this mode when the channel is inside the product or directly after a transaction (after a purchase, a
support contact, the first use of a feature). Everything in SKILL.md still applies: a decision, a rule
written first, a table shell, a left-out list. What changes:

| Item | Micro-survey rule |
|---|---|
| Budget | 1 to 3 questions |
| Rules and hypotheses | 1 rule; 1 or 2 hypotheses (the 2-to-4 range does not apply) |
| First question | Closed and answerable in one click (single choice or a rating); it carries the rule's metric |
| Open text | At most 1, optional, shown after the closed question and only to the answers it explains |
| Trigger | After the event the question is about has finished, never in the middle of a task, and once per person per period you name |
| Introduction | None; the question is the prompt. Say whether the answer is linked to the account in the footer or privacy note |
| Segments | From product records, never asked |
| Output | The short form (five or fewer questions), so sections 2–3 and 8–9 are merged |
| Base | State who can see the prompt (people who reached that screen), which is narrower than "users" |

People who answer an in-product prompt are those who reached the screen and chose to respond. Report the
result as describing them, and say how many saw the prompt.

Outline of a micro-survey plan (thresholds are illustrations):

- Decision: the product lead decides this month whether to keep the new export flow or rework it.
- Existing data: analytics show how many exports finish, not how hard the flow felt. Method: a count of a
  reported experience, so a survey fits; the reasons come from the optional open answer.
- Rule 1: if at least 70% of people who completed an export choose one of the three "easy" points, we keep
  the flow; at or below 50%, we rework it; in between, we watch session recordings of difficult exports.
- H1: at least 70% find it easy. H2: difficulty is concentrated in exports with more than one file.
- Q1 (shown when an export completes): "How easy or difficult was it to export your file just now?" with
  the seven ease labels. Q2 (only after a "difficult" answer, optional): "What made it difficult?"
- Left out: overall satisfaction (`no shell`); "Which formats do you want?" (`no shell`); number of files
  exported (`records answer it`).
- T1: ease distribution, Total and by number of files (from records). T2: coded reasons.
- Length: Q1 1 point + Q2 3 points = 4 points ÷ 8 = 0.5 minutes; 2 questions; budget 1 to 3 questions.

## 2. Standard-metric requests (CSAT, CES, NPS)

A metric is not a decision. Run the decision test; if the request is only "a CSAT survey", ask the one
question, or take the assumed decision "which one touchpoint or segment to improve first".

- The metric question keeps its tracked wording and scale from [wording-patterns.md](wording-patterns.md).
  If the user already runs it with different wording, keep theirs: a changed question breaks the trend.
- The rule names the metric the way the user scores it ("% choosing the top two points", "mean of 1 to 7").
  Scoring a 0–10 recommendation question is `nps-analysis`.
- One metric per survey. A metric the rule does not use goes to section 5 with the reason `no shell`.
- Add what makes the number usable: the event it refers to, a segment column from records, and one
  optional open "main reason" directly after it.
- A score moving between two waves is a difference between two samples; send the question "is this change
  real" to `survey-sample-size`.

## 3. Fielding line

State three things in section 7. The defaults are conventions of this skill.

| Item | Default | Notes |
|---|---|---|
| Sender | A named person the respondents already deal with, from an address that accepts replies | State the name and role |
| Reminders | One, a few days after the invitation, only to people who have not answered | State the number |
| Incentive | None for customers and members; a panel pays its own rate | If one is offered, the same for everyone, stated in the introduction, and never tied to favourable answers |

Also state the field period (first and last day) so the cut-off is not chosen after seeing results.

## 4. Coverage and non-response

Two different gaps; name both in section 7.

- **Coverage:** who is not on the list at all (cancelled customers, people who never signed up, users
  without an email address). The result cannot speak for them.
- **Non-response:** who is on the list but less likely to answer (light users, the mildly satisfied, people
  on a phone during the working day). Say in which direction that could move the rule's metric.
- **The check:** pick one variable known for everyone on the list (plan, tenure, orders in the last 3
  months) and compare its distribution among responders with the whole list. A clear difference goes into
  the report next to the result; weighting is outside this skill.

## 5. Precision check for the decision rule

A rule whose thresholds sit closer together than the survey's margin of error cannot send the result to
one zone.

1. Take the narrowest gap in the rules, in percentage points: upper minus lower threshold, or the minimum
   lead in a ranking rule.
2. Estimate the realistic number of responses: invitations × the response rate this list and channel
   produced before. If there is no earlier rate, write `ASSUMED` and ask the owner; do not borrow a
   benchmark.
3. Look up the margin of error for a percentage near 50% at 95% confidence, 0.98 ÷ √n:

   | Responses (n) | 50 | 100 | 200 | 400 | 1,000 |
   |---|---|---|---|---|---|
   | Margin of error, points | 14 | 10 | 7 | 5 | 3 |

4. If the gap is narrower than that margin, write "Rule [n] cannot be resolved at this sample". Then either
   widen the thresholds (with the owner) or state that the in-between fallback is the expected outcome.
5. If the realistic number is unknown, give the floor instead: the n at which the margin equals the gap,
   (0.98 ÷ gap)² with the gap as a fraction.

   | Gap, points | 20 | 15 | 10 | 5 |
   |---|---|---|---|---|
   | Floor, responses | 25 | 43 | 97 | 385 |

This is a screen, not a sample-size calculation. It ignores three things that `survey-sample-size` handles:
each segment column needs its own n; a lead between two options measured on the same respondents needs
more than the floor; a small list needs fewer responses than the table says (finite-population correction).

## 6. Pretest and soft launch

- **Pretest** with a few people like the respondents, watching or talking them through it. It checks three
  things: they understand each question the way you meant it, they get to the end, and they are the right
  people (the screener lets in who it should). Rewrite and repeat for any question that failed.
- **Soft launch:** send to a small first batch and stop. Check that routing sends people where the design
  record says, that no question is skipped by everyone, that open answers are on topic, and that the
  median time is near the estimate. Then send the rest. Do not change a question that feeds a rule after
  the soft launch unless you discard the first batch.
