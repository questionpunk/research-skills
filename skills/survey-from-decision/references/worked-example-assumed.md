# Worked example: a topic-only request (the ASSUMED path)

A synthetic case. The request: *"Customer feedback survey for a coffee subscription."* Gaps and thresholds
here are illustrations; see [sources.md](sources.md).

## How the steps ran

- **Decision test:** a topic, no actions. The first reply was only the one question: *"What will you do
  differently depending on what the survey shows? Name the two or three options you are choosing between.
  Once I have that I will write the decision rule, the questions and the empty result tables."*
- **The answer was "not sure, just draft it".** So the assumed decision for "customer or user feedback" was
  taken, four candidate options were named, and both were marked `ASSUMED`.
- **Rule form:** "which one first" is a ranking rule, so every option got the same kind of metric: the
  share of subscribers who had that option's problem.
- **Overall satisfaction** was drafted and removed: the user does not track it and the rule does not name
  it, so by the rule in step 5 it goes to section 5.
- **The `O` question** is required because the options are `ASSUMED`.
- **Identity:** personal links, so tenure and delivery counts come from records and no `D` question is asked.

## The output

# Survey plan: coffee subscription, what to fix first

## 1. Decision and decision rule

Decision (`ASSUMED`): The requester will decide before the next planning cycle which one of four areas to
fix first next quarter: delivery, coffee selection, changing or pausing an order, or price
(options `ASSUMED`).

Existing data: Order records give delivery counts, tenure and carrier dates; support tickets show
complaints from the few who write in. Neither shows how common each problem is among all subscribers.

Method: A count of how common four named problems are, so a survey fits. The four areas are a guess; if no
tickets or interviews support them, run a round of interviews first with `ai-interview-guide`. Q6 guards
against a missed area but does not replace that.

Rule 1 (ranking): The metric for each area is the share of subscribers who had its problem (defined in
section 6). We fix first the area with the highest share, if it leads the next area by at least 10 points.
If none leads by 10 points, or if a theme outside the four areas is named in Q6 by more subscribers than
the leading area, we run interviews on the top two before choosing. (`ASSUMED: confirm before fielding`.)

## 2. Objective

Estimate the share of subscribers who had a delivery, coffee, order-change or price problem in the last 3
months, to decide which one area to fix first.

## 3. Hypotheses

- H1: Late delivery is the most common problem (favours delivery).
- H2: Receiving coffees they do not want again is the most common problem (favours coffee selection).
- H3: Difficulty skipping, pausing or changing an order is the most common problem (favours order changes).
- H4: Seeing the subscription as worse value than buying in a shop is the most common problem (favours
  price).

All four feed rule 1.

## 4. Questions

Design record:

| # | Wording | Type | Options | Why | Serves | Analysis |
|---|---------|------|---------|-----|--------|----------|
| Q1 | Of your last 3 deliveries, how many arrived later than the day you were told? Enter 0 if none. | open number | open number (deliveries, 0–3) | Shows how many subscribers get late deliveries | H1 | T1 row "Delivery": % with 1 or more |
| Q2 | Of the last 3 coffees we sent you, how many would you want to receive again? Enter 0 if none. | open number | open number (coffees, 0–3) | Shows how many get coffee they do not like | H2 | T1 row "Coffee selection": % with 1 or fewer |
| Q3 | In the last 3 months, how many times did you want to skip, pause or change a delivery? Enter 0 if never. | open number | open number (times) | Finds who tried to change an order | H3 | Filter for Q4; T2 |
| Q4 | The last time you wanted to do that, how easy or difficult was it? | rating, 7-point bipolar | Extremely difficult / Moderately difficult / Slightly difficult / Neither easy nor difficult / Slightly easy / Moderately easy / Extremely easy / I did not try | Shows how many found changing an order hard | H3 | T1 row "Order changes": % of all subscribers choosing a "difficult" point |
| Q5 | Compared with buying coffee of similar quality in a shop, is your subscription better or worse value for money? | rating, 7-point bipolar | Much worse / Somewhat worse / Slightly worse / About the same / Slightly better / Somewhat better / Much better | Shows how many see the price as poor value | H4 | T1 row "Price": % choosing a "worse" point |
| Q6 | In the last 3 months, what was the most annoying thing about your subscription, if anything? | open text | open text (optional) | Catches a problem we did not think of | O | T3: % per coded theme; % naming a theme outside the four areas |

Questionnaire (respondent view):

We are deciding what to improve in your coffee subscription next and want to know how the last few
deliveries went; it takes about 2 minutes. Your answers are combined with other subscribers' answers to
choose what we fix first. They are stored with your account so we do not have to ask how long you have
been a subscriber; only the research team sees them.

1. Of your last 3 deliveries, how many arrived later than the day you were told? Enter 0 if none.
   [number, 0 to 3]
2. Of the last 3 coffees we sent you, how many would you want to receive again? Enter 0 if none.
   [number, 0 to 3]
3. In the last 3 months, how many times did you want to skip, pause or change a delivery? Enter 0 if never.
   [number]
   (If 0, go to question 5.)
4. The last time you wanted to do that, how easy or difficult was it?
   - Extremely difficult
   - Moderately difficult
   - Slightly difficult
   - Neither easy nor difficult
   - Slightly easy
   - Moderately easy
   - Extremely easy
   - I did not try
5. Compared with buying coffee of similar quality in a shop, is your subscription better or worse value
   for money?
   - Much worse
   - Somewhat worse
   - Slightly worse
   - About the same
   - Slightly better
   - Somewhat better
   - Much better
6. In the last 3 months, what was the most annoying thing about your subscription, if anything? (optional)
   [text]

Thank you. We will use the answers to choose what to fix first.

## 5. Questions deliberately left out

| Question a team would add | Reason |
|---|---|
| "Overall, how satisfied are you with your subscription?" | `no shell`: not tracked, and rule 1 does not name it |
| "How likely are you to recommend us?" (0–10) | `no shell`: not tracked; if it is, keep it verbatim and score with `nps-analysis` |
| "How likely are you to cancel in the next 3 months?" | `respondents cannot report it reliably`: a prediction |
| "Would you pay more for faster delivery?" | `belongs to another method`: `pricing-research-plan` |
| "How long have you been a subscriber?" and "How many deliveries have you had?" | `records answer it`: linked to the account |
| "Which new coffees should we add?" | `no shell`: no option of the decision depends on it |

## 6. Analysis plan

- Rule 1: for each area, the share of the base with the problem, with its confidence interval:
  - Delivery: Q1 of 1 or more.
  - Coffee selection: Q2 of 1 or fewer.
  - Order changes: Q3 of 1 or more and a "difficult" point in Q4. Subscribers with Q3 = 0 count as no
    problem; "I did not try" is reported on its own line in T2 and counts as no problem.
  - Price: one of the three "worse" points in Q5.
  Rank the four shares; compare the lead of the first over the second with the 10-point gap.
- The four definitions are not equally strict, and each cut-off moves an area's share. They are fixed here
  before fielding and confirmed by the owner together with the gap.
- Check: Q1 against carrier dates in the order records for the same subscribers.
- Open answers (Q6): coded with `open-ended-coding`; any theme outside the four areas is compared with the
  leading area's share (rule 1's fallback).
- Exclusions, fixed before fielding: responses that stop before Q5; a second response from the same link
  (keep the first); Q1 or Q2 above 3. Applied with `survey-data-cleaning`; counts per reason are reported.

T1. Subscribers with each problem, last 3 months. Base: all responders. Feeds H1–H4 and rule 1.

| | Total | Subscribed under 6 months | 6 months or more |
|---|---|---|---|
| n (base) | __ | __ | __ |
| Delivery: 1 or more of the last 3 late | __% (± __) | __% | __% |
| Coffee selection: would want again 1 or fewer of the last 3 | __% (± __) | __% | __% |
| Order changes: wanted a change and found it difficult | __% (± __) | __% | __% |
| Price: worse value than a shop | __% (± __) | __% | __% |
| **Lead of the first over the second (rule 1)** | __ points | | |

T2. Changing an order. Base: all responders. Feeds H3.

| | Total |
|---|---|
| Wanted to skip, pause or change 1 or more times | __% |
| … of those: found it difficult / neither / easy / did not try | __% / __% / __% / __% |

T3. Most annoying thing (coded). Base: responders who answered Q6. Feeds rule 1's fallback.

| Theme | Inside the four areas? | % of all responders | Example quote |
|---|---|---|---|
| __ | yes / no | __% | __ |

## 7. Target population and sample

- Population: active subscribers with 3 or more deliveries in the last 3 months (selected from order
  records, so no screener question is asked).
- Source and who it misses: the subscriber list. It misses people who cancelled, who are the most likely to
  have had a serious problem, and new subscribers with fewer than 3 deliveries.
- Channel: email with a personal link. Segments: tenure, from records.
- Fielding: sent by a named person on the customer team from an address that accepts replies; one reminder
  after a few days to those who have not answered; no incentive.
- Non-response: subscribers with a recent problem are more likely to answer, which raises every share but
  not necessarily their order. Check: compare responders with the full list on tenure and on late
  deliveries according to carrier dates.
- Precision: the ranking gap is 10 points, so the floor is 97 responses, and a lead between two areas
  measured on the same people needs more than the floor. List size and past response rate were not given
  (`ASSUMED`). If fewer than 97 respond, rule 1 cannot be resolved and its interview fallback applies.
  `survey-sample-size` computes the n.

## 8. Estimated length

Introduction 1 + Q1 2 + Q2 2 + Q3 2 + Q4 1 + Q5 1 + Q6 3 = 12 points ÷ 8 = 1.5 minutes; 6 questions; budget
7 minutes and 15 questions. Within budget.

## 9. Assumptions and defaults used

- Decision and the four options: `ASSUMED` (the requester did not name a decision).
- The 10-point gap and the four problem definitions: `ASSUMED: confirm before fielding`.
- Owner "the requester"; date "before the next planning cycle".
- Population default: current customers. Channel default: email to the customer list.
- Fielding defaults: named sender, one reminder, no incentive. Identity: linked to the account.
- Segment: the product's plans are not known, so tenure, from records.
- No tracked metric exists (`ASSUMED`); if one does, add it verbatim and move it out of section 5.

## 10. Pre-launch checklist

- [ ] Decision owner confirmed the decision, the four options, the rule and every ASSUMED value
- [ ] Each question fills a cell of a table shell
- [ ] Wording and options reviewed with `survey-bias-check`
- [ ] Sample size computed with `survey-sample-size`
- [ ] Pretested with a few people like the respondents: they understand each question, they finish, and
      they are the right people
- [ ] Completed once on a phone; timed against section 8
- [ ] Soft launch to a small first batch; routing and the first answers checked before the full send
- [ ] Rule, hypotheses, table shells and exclusion criteria saved with a date before the first response

## What to copy from this example

- An assumed decision is written down as assumed, in section 1 and again in section 9 and the checklist.
- A ranking rule needs one comparable metric per option; the definitions sit in the analysis plan, fixed
  before fielding.
- The satisfaction question a "customer feedback survey" usually opens with is in section 5.
- The open question is there to prove the option list wrong, and the rule says what happens if it does.
