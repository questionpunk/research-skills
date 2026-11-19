# PMF survey: template, sampling and data layout

Citations for every rule here are in [sources.md](sources.md).

## The questionnaire

Replace `[product]` with the name users know the product by. Keep the first question and its options word
for word: the 40% benchmark was built on this wording, so a reworded question cannot be compared with it.

**Q1 (single choice, required, options in this order, not randomized)**

How would you feel if you could no longer use [product]?

- Very disappointed
- Somewhat disappointed
- Not disappointed (it isn't really that useful)
- N/A - I no longer use [product]

**Q2 (open text)** What type of people do you think would most benefit from [product]?

**Q3 (open text)** What is the main benefit you receive from [product]?

**Q4 (open text)** How can we improve [product] for you?

Q1 is Sean Ellis's wording with his four options, as on his Survey.io page. His demo survey words the third
option "Not disappointed (it really isn't that useful)"; either wording is his, so pick one and keep it.
Q2 to Q4 are the three follow-ups Rahul Vohra used at Superhuman. Superhuman showed Q1 with three options
and no N/A; use that only if the sample is drawn so that nobody who has left can receive the survey.

**Optional follow-ups from Ellis's original Survey.io survey** (add only the ones you will read):

- After Q1 (open text): "Please help us understand why you selected this answer."
- "What would you likely use as an alternative if [product] were no longer available?" with the options
  "I probably wouldn't use an alternative" and "I would use:" (text). It shows what you would be replaced by.
- "Have you recommended [product] to anyone?" with "No" and "Yes (Please explain how you described it)".
  The explanations are users' own positioning of the product.

Ellis's survey also opened with "How did you discover [product]?" and closed by asking permission to follow
up by email. His versions of Q2 to Q4 are longer: "What type of person do you think would benefit most from
[product]?", "What is the primary benefit that you have received from [product]?", "How can we improve
[product] to better meet your needs?". The full list of 8 is in [sources.md](sources.md).

Rules for the form:

- Q1 comes first, before anything that could colour it (no satisfaction or feature questions ahead of it).
- Q1 is a plain single-choice question on a form. If a chatbot or AI interviewer runs the survey, it still
  shows Q1 with its four options and does not paraphrase it; conversation starts at the open questions.
- Do not add a "neutral" or "don't know" option, and do not turn Q1 into a 1–5 or 0–10 scale.
- Do not make the open questions required; a forced answer is a worse answer.
- Attach the segment from your own records (plan, role, company size, signup month) through a hidden field
  or a join on user id. Asking for it in the survey adds length and missing values.
- Answers must be tied to a user id if you intend to segment, and so that nobody is surveyed twice.

## Who gets it

Draw a **random sample** of users who meet all three conditions:

1. they experienced the core of the product (define the event: sent an invoice, ran a report, and so on);
2. they used it at least twice;
3. they used it in the last two weeks.

Write the three conditions down as a query before sending, and keep the counts: eligible users, invited,
answered. The response rate goes in the report.

Do not send it to the whole mailing list, to a hand-picked list of friendly customers, to people who signed
up and never reached the core feature, or to cancelled accounts. A separate exit survey is the right tool
for people who left.

In B2B, decide before sending whether the unit is the user or the account. If several people per account
answer, report the number of accounts next to the number of respondents.

## When

- First wave: as soon as enough users meet the conditions to expect about 30 answers or more. Below that,
  run it anyway if you want the open answers, and report the score as a rough signal.
- After that: survey each new user once, when they first meet the conditions, and read the score by week,
  month or quarter depending on volume. Never ask the same person twice.
- Not suited to products used once (an event, a single purchase).

## Invitation

Short, plain, and without a hint of the answer you hope for:

> Subject: Two minutes on [product]?
>
> You have been using [product] recently. Four short questions would help us decide what to build next.
> [link]

Avoid "we'd love to hear how much you like [product]" and any incentive tied to a positive answer.

## Data layout for the script

One row per respondent, CSV with a header row, UTF-8.

| Column | Needed | Content |
|---|---|---|
| disappointment answer | yes | The Q1 label as exported. Common variants are recognized; numeric codes need `--map`. |
| segment / persona | no | One value per respondent, from your records (plan, role, CRM). Not from Q2: that answer describes other people. |
| main benefit (coded) | no | One short code per respondent, produced by coding Q3 (for example `speed`). |
| benefit match | no | `yes` / `no`: does this respondent's main benefit match the core benefit. Alternative to the coded column. |
| wave / period | no | One value per respondent (for example `2026-Q1`), to compare two waves. |
| account | no | Company or account id (B2B), to count accounts and score one vote per account. |
| open answers | no | Q2 to Q4 as text. The script ignores them; the agent codes them. |

Recognized labels: "Very disappointed" / "Very"; "Somewhat disappointed" / "Somewhat"; anything starting
with "Not disappointed" (unless it also says "no longer use"); "N/A", "Not applicable" or a label starting
with "no longer use". Case, extra spaces, and dash or apostrophe style do not matter. Anything else stops
the script, in one of two ways:

- **Unknown labels** (typos, codes 1 to 4): map each with `--map "LABEL=very|somewhat|not|na"`.
- **Non-standard wording** ("Mildly disappointed", "Extremely disappointed", a rating scale: 5 or more
  numeric codes, or any code above 4, also when exported as `3.0`): the survey used another scale, so the result is not comparable with the 40% benchmark. Mapping
  the labels with `--map` still gives a score and interval, without a benchmark verdict; use it as your own
  baseline.

## Commands

```
python3 scripts/pmf_survey.py responses.csv
python3 scripts/pmf_survey.py responses.csv --segment-col persona
python3 scripts/pmf_survey.py responses.csv --segment-col persona --benefit-col main_benefit
python3 scripts/pmf_survey.py responses.csv --segment-col persona --focus-segments "Founder,Manager"
python3 scripts/pmf_survey.py responses.csv --benefit-match-col benefit_match
python3 scripts/pmf_survey.py responses.csv --map "1=very" --map "2=somewhat" --map "3=not" --map "4=na" --json
python3 scripts/pmf_survey.py --counts very=16,somewhat=14,not=10,na=8 --invited 400
python3 scripts/pmf_survey.py responses.csv --segment-col persona --segment-col plan
python3 scripts/pmf_survey.py responses.csv --period-col wave --compare "2026-Q1,2026-Q2"
python3 scripts/pmf_survey.py --counts very=18,somewhat=20,not=15 --previous-counts very=12,somewhat=22,not=18
python3 scripts/pmf_survey.py responses.csv --account-col company
```

`--counts` takes totals only, so segments, benefits, periods and accounts need the CSV. `--compare` always
names the earlier period first; the script does not guess the order.

Other options: `--answer-col` (when the header does not contain "disappoint", "no longer use" or "pmf"),
`--core-benefit`, `--benchmark` (default 40), `--confidence` (default 95), `--min-base` (default 30),
`--delimiter` (one character, or `comma`, `semicolon`, `tab`, `pipe`; an Excel `sep=;` first line is read
and skipped).

## Comparing two waves

Compare only when the question and options, the eligibility rule and the delivery were the same in both
waves and nobody answered twice. If any of these changed, report the later wave as a new baseline and do
not quote a change. The script gives the change in points with an interval; "increased" or "decreased" needs
the whole interval on one side of 0.

## B2B: accounts

With `--account-col` the script prints how many accounts stand behind the respondents and a second score
with one vote per account: an account counts as very disappointed when more than half of its current-user
respondents said so (a tie does not count). This vote rule is this skill's convention. Report both scores,
but do not read the gap as large accounts driving the respondent number: the vote rule alone moves the
account share (an account of two with one very and one somewhat counts as not very), so the account share
is a different measure, not the respondent share recounted.

## Reading the segment step (the Superhuman engine)

1. Run with `--segment-col`. Read which segments hold most of the very-disappointed respondents ("share of
   very") and which have a score whose interval clears the benchmark.
2. Describe the committed user from those segments and from the very-disappointed group's Q2 answers.
3. Re-score the chosen segments together with `--focus-segments`. This number is higher by construction:
   it is a decision about whom to build for, and it needs a later wave to confirm it.
4. Code Q3 into a main-benefit column. Run with `--benefit-col`. The core benefit is the most common one
   among very-disappointed respondents.
5. Take the somewhat-disappointed respondents whose benefit matches. Their Q4 answers are what holds them
   back. Set aside the somewhat-disappointed whose benefit differs, and the not-disappointed.
6. Split the plan in two halves: more of what the very-disappointed group values, and removal of what holds
   back the matching somewhat-disappointed group.
7. Label each candidate item low, medium or high for cost and for impact. For blockers, impact comes from
   the number of respondents who asked for it; for "more of what they value" it is a judgement, and say so.
   Start with low cost, high impact.
