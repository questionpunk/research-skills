# Worked example: from a decision to a finished survey

A synthetic case. The request: *"We run a fitness studio with about 400 members. Should we add 6:00 am
classes on weekdays? Write a survey for our members."* The thresholds here are illustrations; see
[sources.md](sources.md). For a request with no decision in it, see
[worked-example-assumed.md](worked-example-assumed.md).

Contents: how the steps ran; the output (sections 1 to 10); what to copy from this example.

## How the steps ran

- **Decision test:** one action that can be taken or not ("add 6:00 am classes"). A decision is present, so
  no question was asked. Thresholds were not given, so they are proposed and marked `ASSUMED`.
- **Step 4 before step 5:** T1 was drawn first. Its "1 or more days" row is the rule 1 metric, which forced
  Q3 to be an open number of days, not "Would you come at 6:00?".
- **What the survey can decide:** members who exercise early elsewhere may never book a class, so the
  survey decides whether to run a trial and how big; trial bookings decide whether classes stay.
- **A question that lost its place:** "How many 7:30 classes did you attend?" was drafted for a table on
  switching, then removed because booking records already hold it.
- **Length:** 12 points, well inside the budget, so nothing was cut for length. Six questions, so the
  short form does not apply.

## The output

# Survey plan: early weekday classes

## 1. Decision and decision rule

Decision: The studio owner will decide before the January timetable is published whether to trial 6:00 am
weekday classes (three a week or one) or keep the current timetable. Whether trial classes stay is decided
by their bookings, not by this survey.

Existing data: Booking records show attendance for every existing class (earliest start 7:30) and each
member's plan, but nothing about workouts members do elsewhere before 7:00.

Method: The decision needs a count of a recent behaviour members can report, so a survey fits. Whether
members would really come at 6:00 is observed behaviour, so only a trial's bookings can settle it.

Rule 1: If the share of active members who did a workout starting before 7:00 on 1 or more weekdays in the
last 7 days is at or above 30%, we trial three 6:00 classes a week for six weeks. If it is at or below 15%,
we keep the timetable. In between, we trial one 6:00 class for four weeks. A trial class stays only if its
bookings reach break-even occupancy. (`ASSUMED: confirm before fielding`; the owner should replace 30% and
15% with the shares that would fill a class to break-even, and give the break-even occupancy.)

Rule 2: If the share of those early exercisers who trained at a gym or studio (ours or another) is at or
above 50%, we act on rule 1 as measured. If it is at or below 25%, the most we do is the one-class trial.
In between, we act on rule 1 after reading the reasons in T3. (`ASSUMED: confirm before fielding`.)

Rule 3 (modifier): If rule 1 says "three classes" and fewer than 50% of early exercisers trained early on
2 or more weekdays, we trial one class instead of three. (`ASSUMED: confirm before fielding`.)

Precedence: rule 2 wins over rule 1 because people who prefer to train at home will not fill a class.

Each rule is read on its 95% interval: a zone's action is taken only when the whole interval is inside it;
an interval that crosses a threshold takes the in-between action. Three classes stand under rule 3 only when
its whole interval is at or above 50%; otherwise one class.

## 2. Objective

Estimate how many active members already work out before 7:00 on weekdays, where and how often, to decide
whether to add 6:00 am classes in January.

## 3. Hypotheses

- H1: At least 30% of active members did a workout starting before 7:00 on a weekday in the last 7 days
  (feeds rule 1; favours adding).
- H2: Most early exercisers train at home or outdoors because they prefer it, not because no class exists,
  so early classes would attract few of them (feeds rule 2; favours keeping the timetable).
- H3: At least half of early exercisers do it on 2 or more weekdays a week, enough to support three classes
  (feeds rule 3).

## 4. Questions

Design record:

| # | Wording | Type | Options | Why | Serves | Analysis |
|---|---------|------|---------|-----|--------|----------|
| Q1 | In the last 4 weeks, how many times did you visit [studio]? Enter 0 if none. | open number | open number (visits) [if 0, end] | Keeps only members who still come | S | Base for T1–T3: members with 1 or more visits |
| Q2 | In the last 7 days, on how many weekdays (Monday to Friday) did you work out anywhere? Enter a number from 0 to 5. | open number | open number (days) [0–5; if 0, go to Q6] | Finds who exercised at all last week | S | Filter for Q3–Q5; those with 0 count as 0 days in T1 |
| Q3 | On how many of those weekdays did your workout start before 7:00 in the morning? Enter 0 if none. | open number | open number (days) [0 to Q2's answer; if 0, go to Q6] | Shows how many members already train before 7:00, and how often | H1, H3 | T1: % with 1 or more, Total and by plan; % with 2 or more among those with 1 or more |
| Q4 | Think of your most recent workout that started before 7:00. Where was it? | single choice | At home / Outdoors / At [studio], using the open gym / At another gym or studio / Somewhere else [randomise, "Somewhere else" last] | Shows whether early exercisers use a gym at all | H2 | T2: % per place; % at any gym or studio |
| Q5 | What is the main reason you worked out there, at that time? | open text | open text [optional] | Tells preference for home apart from having no early class | H2 | T3: % per coded theme |
| Q6 | Which membership do you have? | single choice | Unlimited monthly / Class pack / Something else | Lets us compare the two main plans | D | Column of T1 |

Questionnaire (respondent view):

We are planning next year's timetable and want to know when you worked out recently; it takes about
2 minutes. Your answers are combined with other members' answers to decide class times.
[PRIVACY: confirm in the survey tool whether answers are anonymous or linked to members, and who can see
them; until then, promise nothing.]

1. In the last 4 weeks, how many times did you visit [studio]? Enter 0 if none.
   [number]
   (If 0: that is all we need. Thank you.)
2. In the last 7 days, on how many weekdays (Monday to Friday) did you work out anywhere? Enter a number
   from 0 to 5.
   [number]
   (If 0, go to question 6.)
3. On how many of those weekdays did your workout start before 7:00 in the morning? Enter 0 if none.
   [number]
   (If 0, go to question 6.)
4. Think of your most recent workout that started before 7:00. Where was it?
   - At home
   - Outdoors
   - At [studio], using the open gym
   - At another gym or studio
   - Somewhere else
5. What is the main reason you worked out there, at that time? (optional)
   [text]
6. Which membership do you have?
   - Unlimited monthly
   - Class pack
   - Something else

Thank you. Your answers help us set the January timetable.

## 5. Questions deliberately left out

| Question a team would add | Reason |
|---|---|
| "Would you attend a 6:00 am class?" | `respondents cannot report it reliably`: a prediction, and an easy yes |
| "How many of our 7:30 classes did you attend last week?" | `records answer it`: booking system |
| "Which class types do you want at 6:00?" | `no shell`: decided during the trial, not by this rule |
| "How much more would you pay for early access?" | `belongs to another method`: a price study (Van Westendorp, `van-westendorp-analysis`) |
| "Overall, how satisfied are you with the studio?" | `no shell`: not tracked, and no rule uses it |

## 6. Analysis plan

- Rule 1: metric = % of the base with Q3 of 1 or more (Q2 = 0 counts as 0). Statistic: percentage with its
  Wilson 95% interval. The action is the zone that contains the whole interval; an interval that crosses
  15% or 30% means the one-class trial.
- Rule 2: metric = % of early exercisers (Q3 of 1 or more) answering "At [studio], using the open gym" or
  "At another gym or studio" in Q4, with its Wilson 95% interval, read against 25% and 50% the same way.
- Rule 3: metric = % of early exercisers with Q3 of 2 or more, with its Wilson 95% interval; three classes
  stand only when the whole interval is at or above 50%.
- Open answers (Q5): coded into themes with `open-ended-coding`; themes are read against H2 (preference for
  home or outdoors versus no early class available).
- Exclusions, fixed before fielding: responses that stop before the last question rule 1 needs on their
  route (Q2 when it is 0, Q3 otherwise); responses where Q3 is larger than Q2 or either is above 5. Applied with `survey-data-cleaning`; the number removed for each reason is reported.

T1. Weekday workouts starting before 7:00, last 7 days. Base: active members (Q1 of 1 or more). Feeds H1, H3.
"Something else" in Q6 counts in Total only.

| | Total | Unlimited monthly | Class pack |
|---|---|---|---|
| n (base) | __ | __ | __ |
| 0 days | __% | __% | __% |
| 1 day | __% | __% | __% |
| 2 or more days | __% | __% | __% |
| **1 or more days (rule 1)** | __% (95% interval __–__) | __% | __% |
| **2 or more days, among those with 1 or more (rule 3)** | __% (95% interval __–__) | __% | __% |

T2. Place of the most recent early workout. Base: early exercisers (Q3 of 1 or more). Feeds H2.

| | Total |
|---|---|
| n (base) | __ |
| At home | __% |
| Outdoors | __% |
| At [studio], using the open gym | __% |
| At another gym or studio | __% |
| Somewhere else | __% |
| **Any gym or studio (rule 2)** | __% (95% interval __–__) |

T3. Main reason for the place and time (coded). Base: early exercisers who answered Q5. Feeds H2.

| Theme | % of those answering | Example quote |
|---|---|---|
| __ | __% | __ |

## 7. Target population and sample

- Population: active members (1 or more visits in the last 4 weeks), about 400 on the list.
- Source and who it misses: the member email list. It misses lapsed members and people who never joined
  because of the timetable, the two groups an early class might attract. The result describes current
  members' early-exercise habits; it is not a measure of demand for a class, which only the trial measures.
- Channel: email to everyone on the list; whoever answers is self-selected. Screener: Q1. Segments: plan
  type (Q6), read only if each column's n supports it.
- Fielding: sent by the owner from her own address; one reminder after a few days to members who have not
  answered; no incentive; open for ten days from the first email.
- Non-response: members who train often are more likely to answer a studio survey, which would push the
  rule 1 share up. Check: compare the plan mix of responders (Q6) with the plan mix of the member list.
- Precision: the response rate of this list is not known (`ASSUMED`: about 100 of 400 answer; ask the owner
  what the last member email achieved). At 100 responses the half-width is about 10 points, so rule 1
  points to three classes only for a result of about 40% or more, to keeping the timetable only at about 5%
  or less, and to the one-class trial in between. Rule 2's base is early exercisers only: at about 30 of
  them its half-width is about 18 points, so it acts only above about 68% or below about 7%, and otherwise
  its in-between action applies. Rule 3 reads the same base: with about 30 early exercisers, three classes
  need about 70% (21 of 30) on 2 or more days. Replies are self-selected, so these intervals are model-based
  approximations and no finite-population correction for the list of 400 is applied.
  `survey-sample-size` computes the n for a single share if the owner wants a target.

## 8. Estimated length

Introduction 1 + Q1 2 + Q2 2 + Q3 2 + Q4 1 + Q5 3 + Q6 1 = 12 points ÷ 8 = 1.5 minutes; 6 questions; budget
7 minutes and 15 questions. Within budget.

## 9. Assumptions and defaults used

- Decision owner "the studio owner"; date "before the January timetable is published" (from the request).
- Thresholds in rules 1 and 2: `ASSUMED: confirm before fielding`.
- Population default: current members. Channel default: email to the member list.
- Fielding defaults: owner as sender, one reminder, no incentive. Identity and access: not known, so the
  introduction carries a `[PRIVACY: …]` placeholder and Q6 is asked instead of taken from records.
- Segment default: plan type.
- Q4's list of places: complete for rule 2, which only separates a gym or studio from anywhere else;
  "Somewhere else" holds the rest, so no `O` question is needed.
- Response rate of the list: `ASSUMED`; ask the owner what the last member email achieved.

## 10. Pre-launch checklist

- [ ] Decision owner confirmed the rules, every ASSUMED threshold and the break-even occupancy
- [ ] Privacy line checked against the survey tool's settings (anonymous or linked, who sees answers)
- [ ] Each question fills a cell of a table shell
- [ ] Wording and options reviewed with `survey-bias-check`
- [ ] Sample size computed with `survey-sample-size`
- [ ] Pretested with a few people like the respondents: they understand each question, they finish, and
      they are the right people
- [ ] Completed once on a phone; timed against section 8
- [ ] Soft launch to a small first batch; routing and the first answers checked before the full send
- [ ] Rules, hypotheses, table shells and exclusion criteria saved with a date before the first response

## What to copy from this example

- The rule's metric and the T1 row carry the same words. That is the link between decision and analysis.
- The question most teams would ask first ("Would you attend?") is in section 5, with its reason.
- H2 exists to be able to say no. Without it the survey could only confirm the plan.
- Section 7 names who the list misses, who may not answer, and the result each action needs at the
  expected number of responses.
- The survey decides the size of a trial; bookings decide whether classes stay.
- The respondent view contains no codes; the design record holds them.
