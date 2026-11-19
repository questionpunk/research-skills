# Worked example: a topic-only request (the ASSUMED path)

A synthetic case. The request: *"Customer feedback survey for a coffee subscription."* Gaps and thresholds
here are illustrations; see [sources.md](sources.md).

Contents: how the steps ran; the output (sections 1 to 10); what to copy from this example.

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
- **Identity:** personal links (`ASSUMED`), so tenure and delivery counts come from records and no `D`
  question is asked. Who can see the answers is not known, so the introduction keeps a placeholder.
- **The open answer** cannot be ranked against the four prompted shares: a theme volunteered by some is not
  comparable with a problem everyone was asked about. It can only nominate a fifth area for a later,
  comparable question.

## The output

# Survey plan: coffee subscription, what to fix first

## 1. Decision and decision rule

Decision (`ASSUMED`): The requester will decide before the next planning cycle which one of four areas to
fix first next quarter: delivery, coffee selection, changing or pausing an order, or price
(options `ASSUMED`).

Existing data: Order records give delivery counts, tenure and carrier dates; support tickets show
complaints from the few who write in. Neither shows how common each problem is among all subscribers.
Carrier dates record the carrier's scans, not whether the box reached the subscriber on the day they were
told, so Q1 asks the subscriber and the dates serve as a check.

Method: A count of how common four named problems are, so a survey fits. The four areas are a guess; if no
tickets or interviews support them, run a round of interviews first with `ai-interview-guide`. Q6 guards
against a missed area but does not replace that.

Rule 1 (ranking): The metric for each area is the share of subscribers who had its problem (defined in
section 6). We fix first the area with the highest share, if it leads the next area by at least 10 points
and the 95% interval of that lead excludes zero. Otherwise we run interviews on the top two before
choosing. (`ASSUMED: confirm before fielding`.)

Rule 2 (threshold): If the most-mentioned theme outside the four areas is volunteered in Q6 by 10% or more
of all responders, we add it as a fifth area, with its own closed question, in the next round before
ranking it. If it is at or below 5%, we do not. In between, the owner reads the quotes and decides. It
never changes this round's choice. (`ASSUMED: confirm before fielding`.)

Each rule is read on its 95% interval: rule 2's add and don't-add actions are taken only when the whole
interval is at or above 10% or at or below 5%; otherwise the owner reads the quotes. Rule 1's lead needs the
10-point gap and an interval that excludes zero.

## 2. Objective

Estimate the share of subscribers who had a delivery, coffee, order-change or price problem (in their last
3 deliveries, the last 3 months, or their current view of value; see section 6), to decide which one area
to fix first.

## 3. Hypotheses

- H1: Late delivery is the most common problem (favours delivery).
- H2: Receiving coffees they do not want again is the most common problem (favours coffee selection).
- H3: Difficulty skipping, pausing or changing an order is the most common problem (favours order changes).
- H4: Seeing the subscription as worse value than buying in a shop is the most common problem (favours
  price).

All four feed rule 1. Q6 feeds rule 2 directly; no hypothesis is needed for it, since it only nominates an
area for the next round.

## 4. Questions

Design record:

| # | Wording | Type | Options | Why | Serves | Analysis |
|---|---------|------|---------|-----|--------|----------|
| Q1 | Of your last 3 deliveries, how many arrived later than the day you were told? Enter 0 if none. | open number | open number (deliveries) [0–3] | Shows how many subscribers get late deliveries | H1 | T1 row "Delivery": % with 1 or more |
| Q2 | Of the last 3 coffees we sent you, how many would you want to receive again? Enter 0 if none. | open number | open number (coffees) [0–3] | Shows how many get coffee they do not like | H2 | T1 row "Coffee selection": % with 1 or fewer |
| Q3 | In the last 3 months, how many times did you try to skip, pause or change a delivery? Enter 0 if never. | open number | open number (times) [if 0, go to Q5] | Finds who tried to change an order | H3 | Filter for Q4; T2 |
| Q4 | The last time you tried to do that, how easy or difficult was it? | rating, 7-point bipolar | Extremely difficult / Moderately difficult / Slightly difficult / Neither easy nor difficult / Slightly easy / Moderately easy / Extremely easy | Shows how many found changing an order hard | H3 | T1 row "Order changes": % of all subscribers choosing a "difficult" point |
| Q5 | Compared with buying coffee of similar quality in a shop, is your subscription better or worse value for money? | rating, 7-point bipolar | Much worse / Somewhat worse / Slightly worse / About the same / Slightly better / Somewhat better / Much better | Shows how many see the price as poor value | H4 | T1 row "Price": % choosing a "worse" point |
| Q6 | In the last 3 months, what was the most annoying thing about your subscription, if anything? | open text | open text [optional] | Catches a problem we did not think of | O | T3: % of all responders per coded theme (blank = not mentioned) |

Questionnaire (respondent view):

We are deciding what to improve in your coffee subscription next and want to know how the last few
deliveries went; it takes about 2 minutes. Your answers are combined with other subscribers' answers to
choose what we fix first. [PRIVACY: confirm in the survey tool that answers are stored with the account and
who can see them, then say so, e.g. "They are stored with your account so we do not have to ask how long
you have been a subscriber; [named team] can see them."]

1. Of your last 3 deliveries, how many arrived later than the day you were told? Enter 0 if none.
   [number, 0 to 3]
2. Of the last 3 coffees we sent you, how many would you want to receive again? Enter 0 if none.
   [number, 0 to 3]
3. In the last 3 months, how many times did you try to skip, pause or change a delivery? Enter 0 if never.
   [number]
   (If 0, go to question 5.)
4. The last time you tried to do that, how easy or difficult was it?
   - Extremely difficult
   - Moderately difficult
   - Slightly difficult
   - Neither easy nor difficult
   - Slightly easy
   - Moderately easy
   - Extremely easy
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
| "Would you pay more for faster delivery?" | `belongs to another method`: a price study (Van Westendorp, `van-westendorp-analysis`) |
| "How long have you been a subscriber?" and "How many deliveries have you had?" | `records answer it`: linked to the account |
| "Which new coffees should we add?" | `no shell`: no option of the decision depends on it |

## 6. Analysis plan

- Rule 1: for each area, the share of the base with the problem, with its confidence interval:
  - Delivery: Q1 of 1 or more.
  - Coffee selection: Q2 of 1 or fewer.
  - Order changes: Q3 of 1 or more and a "difficult" point in Q4. Subscribers with Q3 = 0 count as no
    problem.
  - Price: one of the three "worse" points in Q5.
  Rank the four shares; compare the lead of the first over the second with the 10-point gap.
- The four definitions are not equally strict and do not cover the same period (the last 3 deliveries for
  Q1 and Q2, the last 3 months for Q3, a current view for Q5; with 3 or more deliveries in 3 months the
  first two sit inside the third). Each cut-off and window moves an area's share. They are fixed here
  before fielding and confirmed by the owner together with the gap.
- Check: Q1 against carrier dates in the order records for the same subscribers.
- Rule 1's lead: the difference between the first and second shares, measured on the same subscribers,
  with a paired 95% interval (it depends on how many had one of the two problems but not the other).
- Open answers (Q6): coded with `open-ended-coding`. Every theme is a share of all responders, counting a
  blank answer as "not mentioned"; the number who answered Q6 is reported beside it. Rule 2 reads these
  shares; they are never ranked against the four prompted shares.
- Exclusions, fixed before fielding: responses that stop before Q5; a second response from the same link
  (keep the first); Q1 or Q2 above 3. Applied with `survey-data-cleaning`; counts per reason are reported.

T1. Subscribers with each problem (windows as defined above). Base: all responders. Feeds H1–H4 and rule 1.

| | Total | Subscribed under 6 months | 6 months or more |
|---|---|---|---|
| n (base) | __ | __ | __ |
| Delivery: 1 or more of the last 3 late | __% (95% interval __–__) | __% | __% |
| Coffee selection: would want again 1 or fewer of the last 3 | __% (95% interval __–__) | __% | __% |
| Order changes: tried a change and found it difficult | __% (95% interval __–__) | __% | __% |
| Price: worse value than a shop | __% (95% interval __–__) | __% | __% |
| **Lead of the first over the second (rule 1)** | __ points (95% interval __ to __) | | |

T2. Changing an order. Base: all responders. Feeds H3.

| | Total |
|---|---|
| Tried to skip, pause or change 1 or more times | __% |
| … of those: found it difficult / neither / easy | __% / __% / __% |

T3. Most annoying thing (coded). Base: all responders; a blank answer counts as not mentioning the theme.
Feeds rule 2.

| | Inside the four areas? | % of all responders (95% interval) | Example quote |
|---|---|---|---|
| n (base) / answered Q6 | | __ / __ | |
| [theme] | yes / no | __% (__–__) | __ |

## 7. Target population and sample

- Population: active subscribers with 3 or more deliveries in the last 3 months (selected from order
  records, so no screener question is asked).
- Source and who it misses: the subscriber list. It misses people who cancelled, who are the most likely to
  have had a serious problem, and new subscribers with fewer than 3 deliveries.
- Channel: email with a personal link to everyone on the list who qualifies (whole list, not a sample);
  whoever answers is self-selected. Segments: tenure, from records.
- Fielding: sent by a named person on the customer team from an address that accepts replies; one reminder
  after a few days to those who have not answered; no incentive; open for ten days from the first email.
- Non-response: subscribers with a recent problem are more likely to answer, which raises every share but
  not necessarily their order. Check: compare responders with the full list on tenure and on late
  deliveries according to carrier dates.
- Precision: rule 1 compares two shares answered by the same subscribers, so its precision depends on how
  many had one of the two problems but not the other, which is not known before fielding. In the worst
  case (everyone had exactly one of the two), a 10-point half-width on the lead needs about 385
  responses. List size and past response rate were not given (`ASSUMED`), so the sample is undetermined
  until the soft launch shows that share; recompute then with modes-and-fielding.md section 5. Replies are
  self-selected, so the intervals are model-based approximations.

## 8. Estimated length

Introduction 1 + Q1 2 + Q2 2 + Q3 2 + Q4 1 + Q5 1 + Q6 3 = 12 points ÷ 8 = 1.5 minutes; 6 questions; budget
7 minutes and 15 questions. Within budget.

## 9. Assumptions and defaults used

- Decision and the four options: `ASSUMED` (the requester did not name a decision).
- The 10-point gap and the four problem definitions: `ASSUMED: confirm before fielding`.
- Owner "the requester"; date "before the next planning cycle".
- Population default: current customers. Channel default: email to the customer list.
- Fielding defaults: named sender, one reminder, no incentive. Identity: linked to the account (`ASSUMED`);
  who can see the answers is left as a `[PRIVACY: …]` placeholder.
- Segment: the product's plans are not known, so tenure, from records.
- No tracked metric exists (`ASSUMED`); if one does, add it verbatim and move it out of section 5.

## 10. Pre-launch checklist

- [ ] Decision owner confirmed the decision, the four options, the rules and every ASSUMED value
- [ ] Privacy line checked against the survey tool's settings (linked to the account, who sees answers)
- [ ] Each question fills a cell of a table shell
- [ ] Wording and options reviewed with `survey-bias-check`
- [ ] Sample size recomputed after the soft launch with the paired calculation in modes-and-fielding.md
      section 5 (rule 1 is a paired lead, outside `survey-sample-size`)
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
- The open question is there to prove the option list wrong, and rule 2 says what happens if it does,
  without ranking a volunteered theme against prompted ones.
