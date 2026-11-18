# Fixtures for survey-bias-check

All questionnaires here are synthetic; no respondent data. The expected files were written by hand from the
rule definitions in `../references/rules.md` before the script was run against them.

| Input | Expected | Purpose |
|---|---|---|
| `flawed.input.md` | `flawed.expected.json` | SB001 to SB014 and SB016 each fire: 27 findings and 1 note |
| `clean.input.md` | `clean.expected.json` | Sits next to each of those rules without breaking it: 0 findings |
| `gaps.input.md` | `gaps.expected.json` | SB017 to SB027 each fire: 17 findings and 1 note |
| `gaps_clean.input.md` | `gaps_clean.expected.json` | Negative cases for SB017 to SB027: 0 findings |
| `unnumbered.input.txt` | `unnumbered.expected.json` | No question numbers: 3 questions, 1 finding |
| `mini.input.json` | `mini.expected.json` | JSON input form: 8 findings, no line numbers |
| `long.input.json` | (in the test) | 27 open questions, so the length rule fires |
| `ranges.cases.json` | (inside the file) | 16 numeric-range cases for SB010 |

## flawed.input.md, question by question

| Q (line) | Expected | Reasoning |
|---|---|---|
| 1 (3) | SB010 overlap, SB016 opening, SB016 required | $50,000 and $100,000 each end one range and start the next (two overlapping pairs). Income opens the survey. It is required (`*`) with no "Prefer not to say". "Under $25,000" ends at 24,999, so it does not overlap. |
| 2 (9) | SB001, SB009 | "speed and reliability". Positive labels: Very satisfied, Satisfied, Somewhat satisfied = 3; negative: Dissatisfied = 1; Neutral is the midpoint. |
| 3 (16) | SB002, SB005 single | "Don't you" and "amazing". One negation ("n't") with yes/no answers. |
| 4 (20) | SB003 | "always". |
| 5 (24) | SB004 | "would you pay" and "If we added". |
| 6 (28) | SB005 double | "not" twice. |
| 7 (32) | SB006 options | Often, Sometimes, Rarely are vague; "Never" is not. "How often" in the stem is not flagged. |
| 8 (38) | SB007 | "SSO" is not defined. Good / Fair / Poor is balanced (1 positive, 1 negative). |
| 9 (43) | SB008, SB010 gap | 34 words (count below). 1-4 ends at 4 and 6-24 starts at 6, so 5 fits nowhere. "Less than 1" ends at 0 and "More than 24" starts at 25: no problem at either end. The "or" is not checked because the answers are ranges. |
| 10 (49) | SB011 none, SB011 other | Select-all with neither "None of these" nor "Other". |
| 11 (55) | SB014 grid | Agree/disagree answers with two lettered rows. |
| 11b (57) | SB005 single | "not" in a statement answered on agree/disagree. |
| 12 (64) | SB012 direction, SB012 length, SB014 single | Q2, Q8 and Q11 run positive first; Q12 runs negative first. Q11 has 5 agreement points, Q12 has 4 (a tie, so the first seen is the reference). |
| 13 (70) | SB013 | 11 named options (Other is not counted); the limit is 10. |
| 14 (84) | SB011 dk | Yes/no question about "your company" with no "Not sure". |

Rules added later (SB017 to SB027) add five entries to this fixture, also listed by hand before they were run:

| Q | Added | Reasoning |
|---|---|---|
| 2 | SB018 experience, SB019 one_sided | "How satisfied" with no "have not used" answer, no earlier filter question and no "overall"; the stem names only the positive side of a two-sided scale. |
| 7 | SB017 no_period | "How often" with no time phrase. "Never" is a zero answer, so SB018 does not fire. |
| 10 | SB017 no_period | "have you used" with no time phrase. |
| 12 | SB027 (note) | Four points, two on each side, no midpoint. |

Totals for the first 16 rules: 3+2+2+1+1+1+1+1+2+2+2+3+1+1 = 23; with the four added findings 27 (5 high,
10 medium, 12 low) and 1 note. High: Q1 overlap, Q2 SB009, Q3 SB002, Q6, Q9 gap = 5.
Medium: Q1 required, Q2 SB001, Q3 SB005, Q4, Q5, Q10 none, Q11, Q11b, Q12 direction, Q12 length = 10.
Low: Q1 opening, Q7, Q8, Q9 SB008, Q10 other, Q12 SB014, Q13, Q14 = 8.

Q9 word count: Thinking(1) about(2) the(3) last(4) time(5) you(6) contacted(7) our(8) support(9) team(10)
by(11) email(12) or(13) by(14) chat(15) about(16) a(17) billing(18) problem,(19) how(20) long(21) did(22)
it(23) take(24) before(25) you(26) received(27) a(28) first(29) reply(30) that(31) addressed(32) your(33)
question?(34).

Length: 12 single-choice questions x 1 = 12; Q10 select-all, 4 options / 2 = 2; Q11 grid, 2 rows = 2.
Total 16 points; 16 / 8 = 2.0 minutes = 120 seconds.

## clean.input.md, why nothing fires

| Q | Near rule | Why it is clean |
|---|---|---|
| 1 | SB001, SB009, SB016 | "satisfied or dissatisfied" is a balanced pair; 2 positive and 2 negative labels; required but not sensitive |
| 2 | SB006, SB010 | Reference period and counts; 0 / 1-2 / 3-5 / 6-7 has no overlap or gap |
| 3 | SB011 | Select-all with "Other" and "None of these" |
| 4 | SB001 | "easy or difficult" is a balanced pair; "terms and conditions" is one concept |
| 5 | SB004 | "How would you rate" is not a hypothetical |
| 6 | SB002, SB011 | "best describes" is not loaded; has "Other" |
| 7 | SB003 | "ever" is not an absolute |
| 8 | SB007, SB011 | "(SSO)" is defined; "Not sure" is offered |
| 9 | SB001, SB004, SB013 | "friend or colleague" is the standard wording; 0-10 is a numeric scale, exempt from the option limit |
| 10 | - | Open question |
| 11, 12 | SB010, SB016 | Ranges meet without overlap; demographics come last, optional, with "Prefer not to say" |

Length: 10 single-choice x 1 = 10; Q3 select-all, 5 options / 2 = 2.5; Q10 open = 3. Total 15.5 points;
15.5 / 8 = 1.9375 minutes = 116.25 seconds (printed as 1.94 and 116.2).

The later rules leave it clean too: Q1 says "overall" (SB018); Q2 and Q3 name a period (SB017); Q7 uses
"ever", a screener; Q9 labels both ends of the 0-10 scale (SB020); it has one open question, not first (SB025).

## gaps.input.md, question by question

| Q (line) | Expected | Reasoning |
|---|---|---|
| intro (3) | SB024 leading, SB024 no_time_estimate | "Experts say" and "We want to show"; no minutes or question count. |
| 1 (5) | SB025 open_first | The first question has no options. Nothing else in the wording. |
| 2 (7) | SB006 options, SB017 no_period, SB018 behaviour | Often and Sometimes are vague; no time phrase; no "Never" and no earlier filter. |
| 3 (11) | SB019 mismatch | A degree question answered Yes / No. SB018 is not checked on yes/no answers. |
| 4 (15) | SB020 | 1 to 5, no labels, no "where 1 is ..." in the stem. Numbers are not a two-sided scale, so no one_sided. |
| 5 (22) | SB021 | "cheated". "Have you ever" is not flagged for a missing period. |
| 6 (26) | SB022 | "None / Other". Three named options, fewer than the four needed for the "no Other" check. |
| 7 (32) | SB023 | "average" and "as a percentage" in a `[number]` question. 14 words. |
| 8 (34) | SB017 long_window | A count over "past 12 months". 0-10 includes zero, so no SB018; 0-10 / 11-50 / 51+ meet exactly. |
| 9 (39) | SB008, SB026 | 24 words (count below). Four load signals: "If", "not counting", an 8-word parenthetical, 4 commas. "last week" is a period. |
| 10 (41) | SB014 grid, SB025 grid_rows, SB027 (note) | Agree/disagree with 11 rows (limit 10); 4 points, no midpoint. The 11 statements are plain. |
| 11-13 | none | Short open questions. |
| survey | SB025 open_count | Open questions: 1, 11, 12, 13 = 4 (limit 3). Q7 and Q9 are `[number]`. |

Totals: 2+1+3+1+1+1+1+1+1+2+2+1 = 17 (high: Q3; medium: intro leading, Q2 SB018, Q4, Q6, Q10 SB014 = 5;
low: 11) and 1 note.

Q9 word count: If(1) you(2) train(3) outdoors,(4) how(5) many(6) hours(7) did(8) you(9) train(10) last(11)
week,(12) not(13) counting(14) warm-ups,(15) cool-downs,(16) stretching(17) (or(18) similar(19) light(20)
activity(21) before(22) a(23) session)?(24).

Length: open Q1, Q11, Q12, Q13 = 4 x 3 = 12; single-choice Q2, Q3, Q4, Q5, Q6, Q8 = 6; number Q7, Q9 =
2 x 2 = 4; grid Q10 = 11 rows. Total 33 points; 33 / 8 = 4.125 minutes = 247.5 seconds.

## gaps_clean.input.md, why nothing fires

| Q | Near rule | Why it is clean |
|---|---|---|
| intro | SB024 | No authority or hypothesis; gives the number of questions and the minutes |
| 1 | SB017, SB018 | "past 7 days"; "0 days" is a zero answer |
| 2 | SB017 | "Have you visited" with "past 30 days" |
| 3 | SB018, SB019 | Q2 is a filter question that shares "gym"; the stem names both sides |
| 4 | SB020, SB008 | "where 1 is ... and 5 is ..." anchors the numbers; exactly 20 words |
| 5 | SB022 | "Other" and "None of these" are separate options |
| 6 | SB023, SB017 | A number question with a period and no computation word |
| 7 | SB021 | "drink water" is not on the sensitive list |
| 8 | SB023 | "typical month" with ranges, no computation word |
| 9 | SB025, SB014, SB018 | 3 rows; item-specific scale, not agree/disagree; filter Q2 shares "gym" |
| 10 | SB025 | One open question, at the end |

Length: single-choice and scale Q1, Q2, Q3, Q4, Q7, Q8 = 6; Q5 select-all, 5 options / 2 = 2.5; Q6 number =
2; Q9 grid = 3 rows; Q10 open = 3. Total 16.5 points; 16.5 / 8 = 2.0625 minutes = 123.75 seconds (printed
as 2.06 and 123.8).

## unnumbered.input.txt

No line starts with a number, so each non-option line ending in "?" is a question: lines 3, 9 and 12 become
Q1, Q2, Q3. Line 1 does not end in "?" and comes first, so it is the introduction; it gives a time ("about 1
minute"). Q2 has "always" (SB003). Q1 says "overall" and names both sides. The script adds one warning that
it numbered the questions itself. Length: 1 + 1 + 3 = 5 points; 5 / 8 = 0.625 minutes = 37.5 seconds.

## mini.input.json

- A: "price and quality" (SB001). Scale balanced 2/2. Added later: SB018 experience and SB019 one_sided, for
  the same reasons as Q2 of the flawed fixture. Totals 8: 2 high, 4 medium, 2 low.
- B: 1-10 and 10-50 share 10 (overlap). 51-200 ends at 200 and "250 or more" starts at 250, so 201-249 fits
  nowhere (gap). Required, but company size is not a sensitive topic.
- C: agree/disagree grid with 2 rows (SB014 grid). Row Cb "I never had to wait for support.": "never" is an
  absolute (SB003) and a single negation on an agree/disagree scale (SB005 single).
- D: open question, nothing.
- Length: A 1 + B 1 + C 2 rows + D 3 = 7 points; 7 / 8 = 0.875 minutes = 52.5 seconds.

## long.input.json

27 open questions x 3 points = 81 points; 81 / 8 = 10.125 minutes. Above the 10-minute ideal and below the
20-minute maximum, so one SB015 finding at low severity. No question has options, so the open-question
checks of SB025 are skipped and a warning says that only wording rules could run.

## ranges.cases.json, worked by hand

Each range becomes [low, high] in whole steps (step 1, or 0.1 when the options use one decimal). Sort by low;
for neighbours A then B: overlap if B.low <= A.high; gap if B.low > A.high + step.

| Case | Intervals | Result |
|---|---|---|
| 18-25, 25-34, 35-44 | [18,25] [25,34] [35,44] | 25 <= 25: overlap (first pair); 35 = 34+1: fine |
| 18-24, 26-34, 35+ | [18,24] [26,34] [35,inf) | 26 > 25: gap; 35 = 34+1: fine |
| 18-24, 25-34, 35-44, 45+ | adjacent | none |
| Under $25,000 ... $100,000 or more | (-inf,24999] [25000,49999] [50000,99999] [100000,inf) | none |
| 0-0.9, 1-1.9, 2-2.9 | step 0.1: 1 = 0.9+0.1, 2 = 1.9+0.1 | none |
| 0-10%, 10-20%, 20-30% | [0,10] [10,20] [20,30] | two overlaps |
| Less than 1 year, 1-3, 5-10, More than 10 | (-inf,0] [1,3] [5,10] [11,inf) | 5 > 4: gap; 11 = 10+1: fine |
| 1,000-4,999, 5,000-9,999, 10,000+ | adjacent | none |
| Over 50, 18-30, 31-50 | sorted: [18,30] [31,50] [51,inf) | none |
| 18-24, 20-30 | 20 <= 24 | overlap |
| 1-5, 6-10, 10 or more | [1,5] [6,10] [10,inf) | 10 <= 10: overlap |
| $10k-$20k, $20k-$30k | [10000,20000] [20000,30000] | overlap |
| 30-20, 31-40 | low above high | reversed; the remaining single range has no neighbour |
| 1–5, 5 to 9, 10+ | [1,5] [5,9] [10,inf) | overlap (first pair); 10 = 9+1: fine |
| Under 18, 18-64, Over 64 | (-inf,17] [18,64] [65,inf) | none |
| Under 18, 18-64, Over 65 | (-inf,17] [18,64] [66,inf) | 66 > 65: gap (65 fits nowhere) |
