# Wording patterns for common measures

Start from these and replace the bracketed parts with the respondent's own words for the thing. Type names
match [question-type-chooser.md](question-type-chooser.md). The label sets are common practice; sources are in
[sources.md](sources.md).

## Label sets

Use the same set every time the same kind of scale appears in one survey.

| Scale | Labels, in order |
|---|---|
| 5-point unipolar (amount of one thing) | Not at all [important] / Slightly / Moderately / Very / Extremely [important] |
| 7-point bipolar (two opposites) | Extremely dissatisfied / Moderately dissatisfied / Slightly dissatisfied / Neither satisfied nor dissatisfied / Slightly satisfied / Moderately satisfied / Extremely satisfied |
| 7-point bipolar, ease | Extremely difficult / Moderately difficult / Slightly difficult / Neither easy nor difficult / Slightly easy / Moderately easy / Extremely easy |
| 7-point bipolar, comparison | Much worse / Somewhat worse / Slightly worse / About the same / Slightly better / Somewhat better / Much better |

Name both ends in the question stem of a bipolar item ("How satisfied or dissatisfied…", "How easy or
difficult…") so the stem does not lean one way.

## Patterns

| Measure | Wording | Type |
|---|---|---|
| Screener by behaviour | "Which of these have you done in the last [30 days]? Select all that apply." (the qualifying behaviour hidden among three or four others, "None of these" last) | multiple select |
| Filter before a block | "Have you [contacted support] in the last [3 months]?" Yes / No (a fact, so yes/no is acceptable) | single choice |
| Behaviour frequency | "In the last [7 days], how many times did you [order from us]? Enter 0 if none." | open number |
| Recency | "When did you last [do X]?" Today or yesterday / In the last 7 days / In the last 30 days / Longer ago / Never | single choice |
| Current solution | "The last time you needed to [job], what did you use?" (complete list of alternatives, "Nothing, I did not do it") | single choice |
| Overall satisfaction | "Overall, how satisfied or dissatisfied are you with [product]?" | rating, 7-point bipolar |
| Attribute satisfaction | "How satisfied or dissatisfied are you with each of these?" rows: [delivery time], [price], … (after the overall item) | grid, 7-point bipolar |
| Ease of a task | "The last time you [task], how easy or difficult was it?" | rating, 7-point bipolar |
| Importance | "How important is it to you that [outcome]?" | rating, 5-point unipolar |
| Problem prevalence | "In the last [30 days], how many times did [problem] happen to you? Enter 0 if never." | open number |
| Problem severity (only those with 1 or more) | "The last time it happened, how much of a problem was it for you?" Not a problem at all / A slight problem / A moderate problem / A serious problem / An extremely serious problem | rating, 5-point unipolar |
| Choice between the decision's options | "Which would help you more?" [Outcome A in the respondent's terms] / [Outcome B] / No preference | forced choice |
| Most important item (6 or fewer) | "Which one of these matters most to you when you [job]?" | single choice |
| Reason for a rating | "What is the main reason for your answer?" (optional, directly after the rating) | open text |
| Reason for a behaviour | "What was the main reason you [cancelled / chose X]?" (open first; a closed list only once earlier answers supply it) | open text |
| Unmet need | "What is the one thing you could not do with [product] the last time you tried?" | open text |
| Awareness | "Before today, had you heard of [feature]?" Yes, and I have used it / Yes, but I have not used it / No | single choice |
| Recommendation (tracked) | "How likely are you to recommend [product] to a friend or colleague?" 0 = Not at all likely … 10 = Extremely likely. Keep verbatim; see `nps-analysis` | keep existing type |
| Disappointment (product-market fit) | Use the `pmf-survey` wording unchanged | keep existing type |
| Satisfaction with one interaction (CSAT, tracked) | "How satisfied or dissatisfied were you with [the support you received today]?" There is no single standard CSAT wording or scale: if the user already tracks one, keep theirs verbatim; if not, use this with the 7-point satisfaction labels and say which points count as "satisfied" | keep existing type, or rating, 7-point bipolar |
| Customer effort, statement form (CES 2.0, tracked) | "[Company] made it easy for me to handle my issue." 1 = Strongly disagree … 7 = Strongly agree. Keep verbatim; see the note below | keep existing type |
| Customer effort, original form (CES 1.0, tracked) | "How much effort did you personally have to put forth to handle your request?" 1 = Very low effort … 5 = Very high effort. Only for a user who already tracks this version | keep existing type |
| Customer effort, not tracked before | "How easy or difficult was it to [get your issue resolved] today?" with the 7-point ease labels. Not comparable with published CES figures; say so | rating, 7-point bipolar |
| Device or context of use | "In the last [7 days], on which of these did you use [product]? Select all that apply." Phone / Tablet / Laptop or desktop / None of these | multiple select |
| Share of use | "Of the last 10 times you used [product], how many were on a phone?" | open number |
| Tenure segment | "How long have you been a [customer]?" Less than 1 month / 1 to 5 months / 6 to 11 months / 1 year or more | single choice |
| Role or company segment | "Which of these best describes your [role]?" (the bands the business already uses, "Something else") | single choice |
| Closing | "Is there anything else you want us to know about [topic]?" (counts towards the open-text limit; leave it out unless a shell uses it) | open text |

## Tracked metrics and the agree/disagree rule

The CES 2.0 item is an agree/disagree statement, the format this skill otherwise avoids because some people
agree with statements whatever they say. The two rules are reconciled this way, and the plan must say which
case applies in section 9:

- **The user already tracks the metric, or must compare with someone else's figures:** keep the wording and
  scale verbatim. Comparability over time needs constant wording, and a constant bias does not hide a
  change. Do not read the level as free of that bias, and do not compare it across groups known to differ
  in how readily they agree.
- **No history and no outside comparison needed:** use the construct-specific ease item above. It measures
  the same thing without the statement format; it is not "CES" and must not be labelled as such.

The same logic covers the 0–10 recommendation question and any in-house item with a trend behind it.

## Rewrites

| Draft | Problem | Rewrite |
|---|---|---|
| "Would you use a mobile app if we built one?" | Prediction; invites yes | "Of the last 10 times you used [product], how many were on a phone?" |
| "Do you agree that our support is helpful?" | Agree/disagree; leading | "The last time you contacted support, how satisfied or dissatisfied were you with the answer you got?" |
| "How often do you use the reports? Often / Sometimes / Rarely / Never" | Vague quantifiers | "In the last 7 days, on how many days did you open a report? Enter 0 if none." |
| "How satisfied are you with the speed and reliability of delivery?" | Two things | Two grid rows: "Delivery time", "Delivery arriving on the promised day" |
| "How much would you pay for premium?" | Not answerable as asked | Leave out; `pricing-research-plan` |
| "What features should we add?" | Respondent as designer | "What is the one thing you could not do with [product] the last time you tried?" |
| "Don't you think the new design is better?" | Negation; leading | "Compared with the previous design, is the new design better or worse for [task]?" (7-point comparison) |

## Introduction

Two or three sentences: the topic in the respondent's terms and the time from the length estimate; how the
answers are used; whether answers are anonymous or linked to the account. Example: "We are deciding what to
improve in [product] next and want to hear how you used it recently; it takes about [M] minutes. Your
answers are combined with others and are not used to sell you anything. They are anonymous: we cannot see
who gave which answer." When the link is personal, say the true thing instead: "Your answers are stored
with your account so we do not have to ask what plan you are on; only the research team sees them." Never
promise anonymity for a personal link. Do not describe the options being decided in a way that reveals a
preferred answer.
