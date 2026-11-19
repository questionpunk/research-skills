# Modes, fielding and the precision check

Detail for steps 8 and 9 of SKILL.md and for three special request kinds (micro-surveys, standard metrics,
standalone screeners). Which statements are sourced and
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
| Output | The micro output below, not the ten sections |
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

**Micro output.** Five headed parts, in this order:

```markdown
# Micro-survey plan: [short name]
## 1. Decision and rule     (decision, existing data, method, the one rule with its fallback, H1–H2)
## 2. Trigger and base      (the event, frequency cap per person, who can see the prompt)
## 3. Questions             (design record as in SKILL.md section 4; respondent view with no introduction
                            and the privacy line in the footer)
## 4. Analysis              (the shells, the interval rule, what is read from records, the exclusions, and
                            the left-out list with at least 3 entries as in SKILL.md step 6)
## 5. Length and checklist  (points and minutes, every ASSUMED item, the pilot criterion, the checklist below)
```

Checklist for a micro-survey:

- [ ] Owner confirmed the rule and every ASSUMED threshold
- [ ] Privacy line in the footer checked against the tool's settings
- [ ] Prompt shown only after the event has finished, at most once per person per period
- [ ] Pilot criterion fixed before launch: e.g. the first [n] prompts show, the answer rate and the median
      time are read, and the routing to the open question is checked
- [ ] Rule, shell and exclusions saved with a date before the first response

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

## 5. Decision criterion and precision check

**At analysis (written in section 6 before fielding).** Compute a 95% interval for each rule's metric; for
a share use the Wilson interval, which stays accurate for small bases and shares near 0% or 100%. A zone's
action is taken only when the whole interval is inside the zone; an interval that crosses a threshold takes
the fallback. A ranking leader is chosen only when its lead over the next option is at least the gap and
the 95% interval of that lead excludes zero. Example: thresholds 40% and 50%, 45 of 50 say yes: the Wilson
interval is 78.6% to 95.7%, wholly above 50%, so the action is taken even though n is small. 51 of 100 gives
41.3% to 60.6%, which crosses 50%: fallback.

**At planning (section 7).** Give the result each action needs at the realistic number of responses, so the
owner sees what the survey can and cannot settle.

1. Estimate the realistic number of responses: invitations × the response rate this list and channel
   produced before. If there is no earlier rate, write `ASSUMED`, list it in section 9 for the owner to
   supply before fielding (do not stop to ask), and do not borrow a benchmark.
2. For a share, the widest 95% half-width is 0.98 ÷ √n:

   | Responses (n) | 50 | 100 | 200 | 400 | 1,000 |
   |---|---|---|---|---|---|
   | Half-width, points | 14 | 10 | 7 | 5 | 3 |

   With that half-width h, action A needs a result of at least the upper threshold + h, action B at most
   the lower threshold − h; anything between takes the fallback. If the owner expects the true share to sit
   about d points from a threshold, n ≥ (0.98 ÷ d)² (d as a fraction) only makes clearing it possible: the
   result lands on the far side about half the time. For an 80% chance, plan n ≥ (1.40 ÷ d)²:

   | Distance from the threshold, points | 20 | 15 | 10 | 5 |
   |---|---|---|---|---|
   | Responses for a 50% chance | 25 | 43 | 97 | 385 |
   | Responses for an 80% chance | 50 | 88 | 197 | 785 |

   For bases under about 30 the half-width is rough; say so and rely on the Wilson interval at analysis.
3. For a lead between two options answered by the same people (a ranking rule), what matters is how many
   people have one but not the other. With q the share who have exactly one of the two (from a pilot or the
   soft launch), the 95% half-width of the lead is about 1.96 × √(q ÷ n), so n ≈ 3.84 × q ÷ h². With no
   estimate of q, use q = 1 (each person has one or the other, never both): about 385 responses for a
   10-point half-width. At analysis use Newcombe's interval for a paired difference (his method 10, built
   from Wilson intervals). The rule compares the observed first and second options, whichever they turn
   out to be; because the leader is picked from the data, this is a screen, not a correction for picking
   the winner. If neither q nor the list size is known, write "sample undetermined until the soft launch"
   instead of a number.
4. Each segment column needs its own n; read a column only when its base supports the rule.
5. Metrics other than one share or a paired lead (worst-case 95% half-widths; d and h as fractions):

   | Metric | Interval at analysis | Planning half-width |
   |---|---|---|
   | Difference between two segments (independent groups of n₁ and n₂) | Newcombe's hybrid Wilson interval | 0.98 × √(1/n₁ + 1/n₂); 1.39 ÷ √n each when equal. `survey-sample-size` gives the n |
   | NPS (% promoters − % detractors) | `nps-analysis` | 1.96 ÷ √n, twice that of a share: 20 points at n = 100 |
   | Mean of a rating or an amount | t interval, mean ± 1.96 × s ÷ √n | 1.96 × s ÷ √n, s from a pilot or past data; no s, no planning number |
   | Median | Recast it as a share ("% with 2 or more") | Use the share rows above |

**What the interval means.** These formulas assume a random sample, or everyone on a list with few
non-responders. Replies to an email to a list, an in-product prompt or an opt-in panel are self-selected:
report the responding base and the selection limits, and call the interval a model-based approximation.
Do not apply a finite-population correction for the list size to self-selected replies; it holds only for
a random sample drawn from the list. `survey-sample-size` computes the n for a single share and for two
independent groups; paired comparisons are outside it.

## 6. Pretest and soft launch

- **Pretest** with a few people like the respondents, watching or talking them through it. It checks three
  things: they understand each question the way you meant it, they get to the end, and they are the right
  people (the screener lets in who it should). After each question ask: "In your own words, what was this
  asking?", "How did you arrive at your answer?" and "Was any answer missing for you?". Rewrite and repeat
  for any question that failed.
- **Soft launch:** send to a small first batch and stop. Check that routing sends people where the design
  record says, that no question is skipped by everyone, that open answers are on topic, and that the
  median time is near the estimate. Then send the rest. Do not change a question that feeds a rule after
  the soft launch unless you discard the first batch.

## 7. Standalone recruiting screener

A screener that only picks people for interviews, a test or a panel estimates nothing, so it has no rule,
hypotheses or shells. Output instead: who qualifies, in one sentence; the `S` questions, behavioural and in
a named period, with the qualifying answer hidden among others ([wording-patterns.md](wording-patterns.md),
"Screener by behaviour"); for each question the answers that qualify and those that end the screener; the
number of people wanted, per quota group if there are any; consent to be contacted and how. Length,
privacy line, pretest and soft launch are as above.
