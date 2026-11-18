# Survey from a decision: method sources

Checked against the sources below on 2026-11-12. Each entry says what was read: the primary text, the
publisher's page, or only secondary accounts.

## The method

Decision-first ("backward") survey design fixes the end of the study before the questionnaire:

1. The decision, its owner, the options and the date.
2. The decision rule: which result leads to which action, written before fielding.
3. The hypotheses the rule depends on.
4. The analysis: the empty tables ("table shells") that will hold the results.
5. The questions: only those that fill a cell of a shell, select the population, or define a column.
6. Population, sample, order, length, pretest.

Where each part comes from:

- **Start from how the result will be used, then the report, then the analysis, then the data.** Andreasen
  (1985). The HBR page confirms author, title and issue (May 1985) and the premise. Secondary accounts
  (The Decision Lab; the Center for Advanced Hindsight worksheet adapted from the article) agree that the
  first two steps are deciding how the results will be implemented and what the final report will contain,
  and that later steps specify the analyses needed to fill in the report and the data those analyses need.
- **One question that carries the decision.** Jarrett (2021) calls it the Most Crucial Question and frames the
  goal step as "What decision will you make based on these answers?" and "What number do you need for the
  decision?" (her 2021 webinar slides, slides 14–16, read directly). Her seven steps are Goals, Sample,
  Questions, Questionnaire, Fieldwork, Responses, Reports (slide 22). The Survey Octopus (slides 19 and 61)
  pairs "what you want to ask about / the reason you're doing it / the questions you ask / the answers you
  get / the answers you use" with "who you want to ask / the list that you sample from / the sample you ask
  / the ones who respond / the ones whose responses you can use", meeting at "the number", with one error
  type per gap (lack of validity, measurement, processing; coverage, sampling, non-response, adjustment).
- **Question wording, scales and order.** Krosnick and Presser (2010), read in full from the authors' PDF.
- **Order, pretesting, burden.** Pew Research Center and AAPOR guidance, read from their pages.
- **Respondent motivation (cost, benefit, trust).** Dillman, Smyth and Christian (2014).

## Thresholds and rules the skill uses

| Rule in SKILL.md or references | Value | Source and what it says |
|---|---|---|
| Length estimate | points ÷ 8 = minutes online | Versta Research (2011): 1 point per short simple question; 1 per grid row; 1 per two options of a multiple-select; 2 per answer needing mental calculation; 3 per short phrase or sentence expected in an open answer; 1 per three sentences of instructions; divide by 8, "the number of simple questions asked per minute". A practitioner heuristic, not a study. |
| Length budget, default | 7 minutes and 15 questions | SurveyMonkey (Chudoba): across its surveys, abandon rates rose "for surveys that took more than 7-8 minutes to complete", with completion "dropping anywhere from 5% to 20%"; its cumulative bands put questions 11–15 at 5 to 7 minutes. Vendor data, undated, self-selected surveys. |
| Length budget, paid panel | 10 minutes | Revilla and Ochoa (2017): panelists' median "ideal" length was 10 minutes. Revilla and Höhne (2020) found 10 to 15 minutes in two German panels. |
| Length ceiling | 20 minutes | Revilla and Ochoa (2017): median "maximum" length 20 minutes (20 to 28 in Revilla and Höhne 2020). Versta: "no more than 15 or 20 minutes". Galesic and Bosnjak (2009): the longer the stated length (10, 20 or 30 minutes), the fewer respondents started and completed, and answers late in the questionnaire were faster, shorter and more uniform. |
| Cross-check on length | question count bands | SurveyMonkey (Chudoba): question 1 averages 75 seconds, question 2 40 seconds, questions 3–10 about 30 seconds each, 11–15 about 25, 16–25 about 21, 26–30 about 19; stated totals: up to 10 questions 2 to 5 minutes, 11–15 5 to 7, 16–25 7 to 9, 26–30 9 to 10. |
| Rating scale length | 7 points bipolar, 5 points unipolar | Krosnick and Presser (2010, section 9.3): "7-point scales are probably optimal in many instances"; reliability rises from 2 to 3 to 5 points and gains beyond 7 are minimal. The chapter does not state the 5-unipolar / 7-bipolar split. |
| Scale labels | every point labelled with words | Krosnick and Presser (section 9.4): "reliability is higher when all points are labeled with words than when only some are"; labels should divide the continuum into roughly equal units. |
| No agree/disagree, true/false or yes/no for attitudes | use construct-specific options | Krosnick and Presser (section 9.4): "a better approach to eliminating acquiescence is to avoid using agree/disagree, true/false, and yes/no questions altogether"; their review puts the acquiescence effect at about 10% on average. Pew: offer "a choice between alternative statements". |
| Quantities asked as open numbers | no vague quantifiers or pre-set ranges | Krosnick and Presser (section 9.2): the way ranges are cut biases answers; "open questions are usually preferable to closed items for measuring quantities". |
| Closed lists must be comprehensive | "Other" does not rescue a short list | Krosnick and Presser (section 9.2): respondents "restrict their answers to the substantive choices that are explicitly offered"; if the list is unknown, ask the open form. Pew: run a pilot with open questions and build the closed options from it. |
| No "don't know" on attitude items; filter instead | filter questions for non-applicable items | Krosnick and Presser (section 9.6): "preferable to encourage people to report their attitude"; conventional wisdom item: include filter questions so people are not asked what does not apply. |
| Question order | on-topic easy opener; group by topic; general before specific; sensitive and demographic items last | Krosnick and Presser (sections 9.1 and 9.9): the six order rules of conventional wisdom, and "background and demographic characteristics most often come at the end". Pew: demographics "should not be asked near the beginning" unless needed for eligibility or routing; begin with "simple questions that respondents will find interesting and engaging"; a questionnaire "should be grouped by topic and unfold in a logical order". |
| General item before its specifics | overall rating precedes attribute ratings | Krosnick and Presser (section 9.9.2): general items are more open to influence from specific ones than the reverse. They add a qualification: a preceding block can also fix the meaning of a general item, so the order is a choice to state, not a law. |
| Wording rules | eight rules | Krosnick and Presser (section 9.1): simple familiar words; simple syntax; unambiguous; specific and concrete; exhaustive and mutually exclusive options; not leading or loaded; one thing at a time; no single or double negations. |
| Pretest before fielding | with people like the respondents | AAPOR: "Before fielding a survey, it is important to pretest the questionnaire", with respondents similar to those in the survey. Pew: "an essential step". Krosnick and Presser (section 9.10). |
| Keep wording of a tracked question | replicate rather than improve | Krosnick and Presser (section 9.11): comparisons over time need constant wording, even when the old wording departs from best practice. |
| Precision screen for the decision rule | margin of error = 0.98 ÷ √n; floor n = (0.98 ÷ gap)² | The normal-approximation margin of error for a proportion at 95% confidence, 1.96 × √(p(1 − p) ÷ n), at its widest (p = 0.5). Textbook result (for example Cochran, 1977, *Sampling Techniques*, 3rd ed., chapter 3); the tables in `modes-and-fielding.md` are that arithmetic rounded (n = 100 gives 9.8 points; a 10-point gap gives 96.04, rounded up to 97). |
| Tracked metric kept verbatim (CES, CSAT, 0–10 recommendation) | exception to the no-agree/disagree rule | Krosnick and Presser (section 9.11): borrowing a question that departs from best practice is appropriate when comparison needs constant wording; the comparison holds if the response error is constant across surveys, and they note acquiescence may differ between groups (for example by education). |
| Customer Effort Score wordings | CES 1.0: 1–5 effort question; CES 2.0: 1–7 agreement with an "made it easy" statement | Dixon, Freeman and Toman (2010) introduced the measure; CEB (now Gartner) replaced it with the statement form in 2013. Wordings as widely reproduced. |
| Pretest checks | comprehension, completion, right respondents | AAPOR and Pew (pretest with people like the respondents; pilot tests). Krosnick and Presser (section 9.10) on what conventional pretests and cognitive interviews detect. The three-part wording and the soft launch are conventions. |
| Response-rate planning figures | not used as thresholds | Jarrett's slides (slide 44) give "up to 20%" for an emailed one-off survey to a selected group and "maybe 5%" for a routine post-transaction email. Illustrative; the skill sends sample planning to `survey-sample-size`. |

## Structural conventions of this skill (no external source)

These numbers exist so that two runs produce the same structure. They are editorial choices, not findings:

- 2 to 4 options in the decision; 1 to 3 decision rules (at most one modifier); 3 or 4 candidate options
  when the decision is assumed; 2 to 4 hypotheses; 1 to 3 questions per hypothesis; at most 2 open-text
  questions; at most 2 segment variables; at least 3 entries under "left out".
- IDs `H1`, `Q1`, `T1` and the roles `S`, `D`; the three rule forms (threshold with an inconclusive zone,
  ranking with a minimum gap, modifier). The inconclusive zone follows from sampling error: a result whose
  interval straddles a threshold cannot support either action.
- Recall periods used in defaults and wording patterns ("last 7 days", "last 30 days", "last 3 months",
  "last 4 weeks", "of the last 10 times") are examples of a named recent period; pick the shortest period
  in which the behaviour normally occurs. No source fixes these values.
- Lists of 6 or fewer items are handled with a "which one matters most" question and longer lists are sent
  to `maxdiff-design`; grids are capped at 5 rows. Both cut-offs are editorial.
- Length is rounded up to the next half minute; the introduction quotes it rounded up to a whole minute and
  has 2 or 3 sentences (topic and time; use; anonymous or linked).
- In-product micro-survey mode: 1 to 3 questions, 1 rule, 1 or 2 hypotheses, at most 1 open-text question,
  first question closed and one click, shown after the event. Editorial; common practice among in-product
  survey tools, but no vendor response-rate figure is used, because those are correlational data from one
  vendor's customers.
- Short form: sections 2–3 and 8–9 merge when the question table has five or fewer rows.
- Fielding defaults: a named sender, one reminder a few days later to non-responders, no incentive, a field
  period fixed in advance. Conventions. The ten-day period in the worked
  example is an illustration.
- Roles `S`, `D`, `O`; the `O` question is required when options or a closed list are assumed.
- An overall rating is asked only when already tracked or named by a rule as its metric.
- The non-response check (compare responders with the list on one variable known for everyone) and the
  soft launch to a small first batch are standard practice stated here without a specific source.
- Exclusion criteria are written before fielding and applied with `survey-data-cleaning`; this skill sets
  no numeric cut-offs for them.
- One open answer is counted as one sentence (3 points) in the length estimate; the introduction as 1 point.
- Thresholds in the worked example (30%, 15%, 50%, 25%, a median of 2 days) are illustrations. A real
  threshold comes from the decision owner (break-even, capacity, cost), never from this file.

## Where practitioners disagree

- **Five or seven points.** Krosnick and Presser favour 7; Pew advises "four or perhaps five at most" answer
  choices (written mainly for choices read aloud); many product teams use 5 everywhere for small screens.
  The skill uses 7 bipolar and 5 unipolar and keeps an existing tracker's scale unchanged.
- **Seconds per question.** Versta's 8 simple questions a minute (7.5 seconds each) and SurveyMonkey's
  roughly 30 seconds a question differ by a factor of four. Versta counts work per item for practised panel
  respondents; SurveyMonkey's averages cover every question type and include page loads and reading. The
  skill reports the Versta estimate and cross-checks the question count against SurveyMonkey's bands.
- **Midpoints and "don't know".** Krosnick and Presser find offering a midpoint desirable and advise against
  an explicit no-opinion option on attitude items; others add "don't know" to avoid forced guesses on
  factual items. The skill filters first and allows "Not sure" only on factual items.
- **General before specific.** The funnel order is conventional; Krosnick and Presser show cases where
  specifics first make the general item better defined.
- **Agree/disagree in tracked metrics.** CES 2.0 is an agree/disagree statement, the format Krosnick and
  Presser advise against. Practitioners keep it for comparability with their own history and with published
  figures; the skill does the same for a tracked metric and offers a construct-specific ease item when
  there is no history.
- **How short.** Jarrett argues for the smallest survey that answers the Most Crucial Question; panel
  studies tolerate 10 to 20 minutes. The skill defaults to the short end and states the budget.

## Sources

- Andreasen, A. R. (1985). "'Backward' Market Research." *Harvard Business Review*, May–June 1985.
  https://hbr.org/1985/05/backward-market-research
- Jarrett, C. (2021). *Surveys That Work: A Practical Guide for Designing and Running Better Surveys*.
  Rosenfeld Media. https://rosenfeldmedia.com/books/surveys-that-work/ ; slides (CC BY-SA 4.0):
  https://www.effortmark.co.uk/wp-content/uploads/2021/03/Surveys-that-work-webinar-for-FocusVision.pdf
- Krosnick, J. A., & Presser, S. (2010). "Question and Questionnaire Design." In P. V. Marsden & J. D.
  Wright (Eds.), *Handbook of Survey Research* (2nd ed., pp. 263–313). Emerald.
  https://web.stanford.edu/dept/communication/faculty/krosnick/docs/2010/2010%20Handbook%20of%20Survey%20Research.pdf
- Dillman, D. A., Smyth, J. D., & Christian, L. M. (2014). *Internet, Phone, Mail, and Mixed-Mode Surveys:
  The Tailored Design Method* (4th ed.). Wiley.
- Pew Research Center, "Writing Survey Questions." https://www.pewresearch.org/writing-survey-questions/
- AAPOR, "Best Practices for Survey Research." https://aapor.org/standards-and-ethics/best-practices/
- Length: Galesic, M., & Bosnjak, M. (2009). *Public Opinion Quarterly*, 73(2), 349–360.
  https://doi.org/10.1093/poq/nfp031 ; Revilla, M., & Ochoa, C. (2017). "Ideal and maximum length for a web
  survey." *International Journal of Market Research*, 59(5), 557–565; Revilla, M., & Höhne, J. K. (2020).
  https://doi.org/10.1177/1470785320943049 ; Versta Research (2011), "How to Estimate the Length of a
  Survey." https://verstaresearch.com/newsletters/how-to-estimate-the-length-of-a-survey/ ; Chudoba, B.,
  "How much time are respondents willing to spend on your survey?" SurveyMonkey.
  https://www.surveymonkey.com/curiosity/survey_completion_times/

- Dixon, M., Freeman, K., & Toman, N. (2010). "Stop Trying to Delight Your Customers." *Harvard Business
  Review*, July–August 2010. https://hbr.org/2010/07/stop-trying-to-delight-your-customers ; Gartner,
  "Effortless Experience" (CES in its current form).
  https://www.gartner.com/en/customer-service-support/insights/effortless-experience

## Pitfalls

- No decision owner, or a "decision" that names no alternative actions.
- A threshold set after seeing the data.
- Asking respondents to make the decision or predict their own behaviour ("Should we build X?", "Would you
  use X?", "Would you pay $Y?").
- A question with no table shell; a table shell with no hypothesis.
- Subgroup comparisons the sample cannot support.
- Surveying when records or analytics already hold the answer.
- A closed list invented at a desk instead of taken from interviews, tickets or an open pilot question.
- Agree/disagree batteries, double-barrelled items, vague quantifiers ("regularly"), long recall periods.
- Surveying only the people who are easy to reach (current active users) when the decision is about others.
