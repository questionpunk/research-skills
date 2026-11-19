# Fixtures for kano-analysis

Published worked examples and a synthetic ten-respondent example. No respondent data. Expected values come from
the publications or from hand arithmetic below, not from the script.

Answer codes: 1 like, 2 must-be, 3 neutral, 4 live with, 5 dislike (Berger et al. 1993, p. 6). Each pair is
(functional, dysfunctional). Better = (A + O)/(A + O + M + I); Worse = −(O + M)/(A + O + M + I).

## 1. `berger_fig16.input.csv`: Berger et al. (1993), Fig. 16, p. 18

Seven customer requirements with their A, M, O, I counts and printed coefficients (read 2026-11-19 from the
journal issue PDF on walden-family.com):

| CR | A | M | O | I | Better | Worse |
|---|---|---|---|---|---|---|
| 6 | 53 | 20 | 35 | 6 | .77 | −.48 |
| 5 | 40 | 17 | 33 | 24 | .64 | −.44 |
| 4 | 59 | 8 | 26 | 18 | .77 | −.31 |
| 3 | 55 | 3 | 20 | 30 | .69 | −.21 |
| 2 | 69 | 4 | 16 | 27 | .73 | −.17 |
| 1 | 40 | 2 | 2 | 60 | .40 | −.04 |
| 7 | 63 | 1 | 1 | 20 | .75 | −.02 |

Check by hand for CR6: (53 + 35)/114 = 0.7719; −(35 + 20)/114 = −0.4825.

## 2. `matzler_table2_percentages.input.csv`: Matzler and Hinterhuber (1998), Table 2, p. 34

**Edge grip (percentages):** Table 2 prints rounded **percentages** A 7, O 33, M 50, I 10 with Better **0.40**
and Worse **−0.83** (Table 1, p. 33, has the unrounded 7.0, 32.3, 49.3, 9.5, R 0.3, Q 1.5; read 2026-11-19 from
the PDF on hinterhuber.com). Better (7 + 33)/100 = 0.40, Worse −(33 + 50)/100 = −0.83, category M. The paper does
not give respondent counts, so the row is entered as if n were 100: the coefficients and category are checked,
but Fong's test and the intervals on this row mean nothing.

**Raverta and Loera (2026), Table 2, n = 107** (first author Pericle Raverta, checked in the Crossref record): the
tests call Fong's test directly with the two most frequent counts recorded by QuestionPunk's method spec. The
publisher page refused automated reads on 2026-11-19, so the other counts in the table were not re-checked and
no fixture reproduces the rows.

- taste 42 vs 41: 1.65·√(83 × 131/214) = **11.761**, |a − b| = 1, not a clear winner.
- save money 63 vs 24: 1.65·√(87 × 127/214) = **11.856**, |a − b| = 39, clear.
- made in your country 52 vs 42: 1.65·√(94 × 120/214) = **11.981**, |a − b| = 10, not clear.

## 3. `spec_example.input.csv`: ten respondents, QuestionPunk export headers

Headers as QuestionPunk's wide CSV export writes them (`Q3 | <feature>: functional`, `: dysfunctional`,
`: category`).

**Save progress and resume later:** (2,5) M, (3,5) M, (2,5) M, (4,5) M, (2,5) M, (3,5) M, (2,5) M, (1,5) O,
(3,3) I, (2,4) I. Counts M 7, O 1, I 2 → **M**. Better = 1/10 = **0.10**; Worse = −8/10 = **−0.80**.
Fong: 1.65·√(9 × 11/20) = **3.671**; |7 − 2| = 5 → clear.

**Dark mode:** (1,5) O, (1,3) A, (1,5) O, (1,4) A, (1,2) A, (1,5) O, (1,3) A, (1,5) O, (1,1) Q, (3,1) R.
Counts A 4, O 4, Q 1, R 1. A and O tie; M > O > A > I gives **O**. Better = 8/8 = **1.00**; Worse = −4/8 =
**−0.50** (R and Q left out of the base). Fong: a = b = 4 → never clear (threshold 3.615).

## 4. `spec_example_answer_text.input.csv`

The same answers as one text column per respondent, the way QuestionPunk's `responses_read` renders a Kano
answer: one line per feature, `Feature: <functional> / <dysfunctional> · <importance>/9`. The first feature uses
Berger's wording, the second the numeric codes (`answerFormat: "numeric"`). Importance for respondent i
(0-based) is i mod 9 + 1 for the first feature (mean 4.6) and 9 − (i mod 9) for the second. `plan` splits
the respondents 5 and 5.

## 5. `custom_columns.input.csv`

The same ten respondents as section 3 under column names nothing detects (`save_like`, `save_without`,
`save_importance`, `dark_like`, `dark_without`), for the `--pair` example in SKILL.md. Importance is i mod 9 + 1
(mean 4.6), and `plan` splits them 5 and 5.

## 6. `wording_check.input.csv`

Two question pairs for `design --wording`. The first passes. The second ("arrives today" / "arrives next week")
gets an advisory `CHECK:` for having no negation word, although it is a valid performance contrast: the
researcher keeps it and says why.
