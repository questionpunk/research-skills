# PMF survey: method sources

Checked against the sources below on 2026-11-12. Each item says where it comes from; `[S1]`–`[S8]` refer to
the list under "Sources". The second pass of the same day added [S9]–[S12].

## The question

- **Ellis's wording and options** [S1], verbatim: "How would you feel if you could no longer use [product]?"
  with the options "Very disappointed", "Somewhat disappointed", "Not disappointed (it isn't really that
  useful)", "N/A – I no longer use [product]".
- **Superhuman's wording** [S3]: "How would you feel if you could no longer use Superhuman?" with three
  options: "Very disappointed", "Somewhat disappointed", "Not disappointed". No N/A option.
- **Two wordings of the third option.** The Survey.io demo survey [S9] has "Not disappointed (it really
  isn't that useful)" and writes the fourth as "N/A - I no longer use [product]" with a hyphen; the blog page
  [S1] has "(it isn't really that useful)" and an en dash. The script accepts both.
- **Ellis's full Survey.io survey** [S9], 8 questions, verbatim with [product] for the demo's product name:
  1. "How did you discover [product]?" (Blog; Friend or colleague; Search engine; Facebook; Twitter; Other)
  2. "How would you feel if you could no longer use [product]?" (the four options), followed by "Please help
     us understand why you selected this answer."
  3. "What would you likely use as an alternative if [product] were no longer available?" ("I probably
     wouldn't use an alternative"; "I would use:")
  4. "What is the primary benefit that you have received from [product]?"
  5. "Have you recommended [product] to anyone?" ("No"; "Yes (Please explain how you described it)")
  6. "What type of person do you think would benefit most from [product]?"
  7. "How can we improve [product] to better meet your needs?"
  8. "Would it be okay if we followed up by email to request a clarification to one or more of your
     responses?"
  Vohra's three follow-ups [S3] are shorter versions of Ellis's 4, 6 and 7. The template offers Ellis's
  why-probe, alternative and recommendation questions as optional additions.
- **Non-standard wordings.** Pendo's PMF survey offers three options, "Very disappointed", "Mildly
  disappointed", "Not disappointed" [S12]. The benchmark was built on Ellis's options, so the script reports
  a label from another disappointment scale ("Mildly", "Extremely" and so on) as non-standard wording, not
  comparable with the benchmark, and does the same for a numeric column with 5 or more distinct values or
  any code above 4, whole numbers also as exported with ".0" (a rating scale; Ellis's question has 4
  options, so codes 0-4 cover any coding of them). Both detection rules are the skill's.
- The skill's default is Ellis's four options. The N/A option shows when the sample reached people who have
  already left, which the three-option version hides.

## The score and its denominator

- Score = the share answering "very disappointed" [S1][S2]. "Somewhat disappointed" is never added to it:
  Ellis reads that answer as "it is only a 'nice to have'" [S1].
- **Denominator.** Neither Ellis [S1][S2] nor Vohra [S3] says how to treat "N/A – I no longer use
  [product]". Ellis defines the test on "existing users" [S2] and on people who "used your product in the
  last two weeks" [S1], so the skill takes the base as very + somewhat + not disappointed and leaves N/A
  and blank answers out. This is the skill's stated rule, not a quotation. The script prints the rule, the
  N/A count, and the share with N/A kept in the base, so a reader can see both.
- **Practice differs.** CRV's guide leaves N/A out of the denominator, so that only people who still use the
  product count [S11]. Pendo's PMF survey computes "a percentage of positive responses out of the total number
  of responses", with three options and no N/A [S12]. The script prints this next to the score.
- **Counts as input.** `--counts very=..,somewhat=..,not=..[,na=..]` applies the same rule to totals.

## The benchmark (40%)

- [S2], verbatim: "In my experience, achieving product/market fit requires at least 40% of users saying they
  would be 'very disappointed' without your product. Admittedly this threshold is a bit arbitrary, but I
  defined it after comparing results across nearly 100 startups. Those that struggle for traction are always
  under 40%, while most that gain strong traction exceed 40%."
- [S1] words it differently: "over 40%", "there is a great chance you can build sustainable, scalable
  customer acquisition growth", and "determined by comparing results across 100s startups". So Ellis's own
  two pages disagree on "at least" versus "over" and on roughly 100 versus hundreds of startups. The script
  treats exactly 40% by its interval, like any other value.
- Ellis in 2024 [S4]: "the 40% was not something I originally had in there"; "I don't think it's that firm";
  its use is "having some kind of target for the team to be shooting for".
- [S2] adds a condition the number does not cover: the very-disappointed users must "represent a large
  enough target market to build an interesting business".
- **Bands are not Ellis's.** Guides and skills often print bands such as "under 25% / 25–40% / 40% and over".
  No such bands appear in [S1], [S2], [S3] or [S9]. CRV's FAQ calls 25–40% promising but not yet a clear
  signal [S11]; that is a vendor's gloss. Read the interval instead: a score in the 25–39% range on a few
  dozen answers usually has an interval that includes 40% (12 of 40, 30%, gives 18.1% to 45.4%).
- **What the sources say to do below 40%.** Ellis: "keep your burn low and focus all resources on improving
  the percentage of users that say they would be very disappointed" and do not hire sales and marketing
  leaders to fix it [S2]; move the somewhat-disappointed by repositioning around more unique attributes [S1].
  Vohra: segment to the users who are very disappointed, then work the two halves of the roadmap [S3].
- Vohra [S3] reports Ellis's figure as coming from "benchmarking nearly a hundred startups" and cites Hiten
  Shah's 2015 survey of 731 Slack users, 51% very disappointed.

## Who to survey and when

- [S1], verbatim: "I recommend sending the survey to a random sample of people who have: Experienced the
  core of your product offering; Used your product at least twice; Used your product in the last two weeks".
- [S4]: "a random sample of people who've really used your product", used at least twice and within the last
  week or two, so that they have not churned yet.
- Superhuman [S3] surveyed users who "used the product at least twice in the last two weeks", "constantly
  surveyed new users", never surveyed the same user twice, and tracked the score "on a weekly, monthly and
  quarterly basis".
- Question order: earlier questions in a longer survey can prime the answer, so the Real Startup Book
  advises placing the question early or running it alone [S8]. The template puts it first.
- Delivery: the Real Startup Book warns that asking the question through a chatbot or conversational AI can
  change how it is read and make the score incomparable with the benchmark [S8]. The template asks it as a
  plain single-choice question; conversational follow-up belongs to the open questions after it.
- Response rate = people who answered the question / people invited (`--invited`). The script flags a rate
  under 10%, the Real Startup Book's rule of thumb [S8]. The flag does not say the score is too high:
  across 59 studies, the response rate was a poor predictor of nonresponse bias in the estimates
  [S10], so the rate alone gives neither the size nor the direction of the bias. The flag asks for a
  comparison of respondents with invitees on activity or tenure instead.
- Not suited to one-off products (Ellis's examples: a film, a single workshop) [S4].

## How many responses

- **30** (the script's default small-base threshold, `--min-base`): Ellis, "I need at least 30 responses",
  with the admission that he made the number up and later heard it is a common minimum [S4]. He adds that 4
  of 10 saying "very disappointed" is still a signal, but not one to go to market on [S4].
- **About 40**: Vohra, "directionally correct results around 40 respondents" [S3]. He gives no derivation.
- What these sizes mean, computed with the Wilson interval below at 95%: 4 of 10 gives 16.8% to 68.7%;
  12 of 30 gives 24.6% to 57.7%; 16 of 40 gives 26.3% to 55.4%; 60 of 150 gives 32.5% to 48.0%. At the
  suggested minimums a 40% result cannot be told apart from 30% or 50%. That follows from the arithmetic, and
  no PMF source states it.
- For a verdict of "above", the whole interval must clear 40%: at 40 answers, 22 of 40 (55%) gives a lower
  limit of 39.8% (cannot tell) and 23 of 40 (57.5%) gives 42.2% (above). Same arithmetic.
- The same threshold is applied to each segment. A segment under the threshold is flagged "small base" and
  still shown with its interval.

## Confidence interval and verdict

- **Wilson score interval** (Wilson 1927 [S6]), no continuity correction, as printed in the NIST handbook
  [S5], with p = x/n and z the standard normal quantile (1.959964 for 95%):

  ```
  lower, upper = ( p + z²/2n ∓ z·sqrt( p(1−p)/n + z²/4n² ) ) / ( 1 + z²/n )
  ```

- Why Wilson and not the usual p ± z·sqrt(p(1−p)/n): NIST notes the simple form "may not be accurate enough"
  for a small sample or few failures and can give a negative lower limit, and cites Brown, Cai and DasGupta
  (2001) [S7] and Agresti and Coull (1998) as recommending Wilson [S5].
- **Worked example used as a check** [S5]: p̂ = 0.13, N = 200, z = 1.645 gives a lower limit of 0.09577. The
  script reproduces it (`fixtures/README.md`, `tests/test_pmf_survey.py`).
- **Verdict rule** (the skill's, built on the interval): "above" only if the lower limit is over the
  benchmark, "below" only if the upper limit is under it, otherwise "cannot tell". The same rule is applied
  to each segment.
- Limits of the interval: it covers sampling error only, under simple random sampling. It says nothing about
  who chose not to answer. Reading many segment intervals at once will turn up some that clear the benchmark
  by chance; treat a segment result as a lead to confirm on the next wave.

## Change between two waves

- **Interval for the difference of two independent proportions:** Newcombe's (1998) hybrid score interval,
  his method 10, built from the Wilson limits (l1, u1) and (l2, u2) of the two waves, with d = p2 − p1.
  Formula as printed in the NCSS documentation [S10], which says Newcombe compared eleven methods and
  recommended this one over the chi-square methods:

  ```
  lower = d − z·sqrt( l2(1−l2)/n2 + u1(1−u1)/n1 )      upper = d + z·sqrt( u2(1−u2)/n2 + l1(1−l1)/n1 )
  ```

  The script uses the equivalent form d − sqrt((p2−l2)² + (u1−p1)²), d + sqrt((u2−p2)² + (p1−l1)²).
- **Verdict rule** (the skill's): "increased" or "decreased" only if the whole interval is on one side of 0,
  otherwise "cannot tell".
- **When two waves can be compared** (the skill's rule): same question wording and options, same eligibility
  rule, same delivery, and different people in each wave. Otherwise the later wave is a new baseline. The
  interval assumes independent samples; Superhuman never surveyed a user twice [S3].
- Worked case: 12 of 52 (23.1%) then 18 of 53 (34.0%) is +10.9 points with an interval of −6.4 to +27.3
  points: cannot tell (pooled z = 1.23). Arithmetic in `fixtures/README.md`.

## Several segment columns, accounts

- `--segment-col` can be repeated. Every segment interval is read at the stated confidence level one at a
  time, with no correction for the number read, so the script prints how many were read and that some will
  clear or miss the benchmark by chance. This caution is the skill's; no PMF source discusses it.
- `--account-col` (B2B): the script reports the number of accounts and a second score with one vote per
  account. **Vote rule, the skill's own convention:** an account counts as very disappointed when more than
  half of its current-user respondents answered very disappointed; a tie does not count; an account whose
  respondents all answered N/A is outside the base; respondents with no account id are left out of the
  account score and counted separately (they may belong to a known account). No source defines an
  account-level PMF score, and Ellis's 40% was set for users, so the account share is printed without a
  verdict unless the user supplies an account-level target (`--account-benchmark`).
- `--period-col` with `--compare`: the headline score, segments, benefits and accounts are the later
  wave's, so the result answers "where are we now". All waves pooled are shown as a labelled reference
  only, since they mix waves and any rows outside the two compared. With `--id-col` a respondent id in both
  waves stops the comparison: the Newcombe interval assumes independent samples.

## Wording check before the benchmark (the skill's rule)

- The 40% benchmark belongs to Ellis's question and four options [S1][S4]. The script sees the wording when
  the labels are his (any case, dashes, apostrophes or trailing punctuation). Typed counts (`--counts`) and
  labels mapped by hand (`--map`, for example numeric codes) hide it: a mapping such as
  `Satisfied=very` would otherwise clear the benchmark. For those the verdict is "not compared" until the
  user confirms the question and options were Ellis's and `--ellis-wording` is passed.
- A rating scale (five or more distinct numeric codes, or any code above 4) or labels from another
  disappointment scale are never compared, with or without `--ellis-wording`. A five-point scale on which
  only codes 1 to 4 were chosen cannot be told from Ellis's codes by the script, which is why codes need the
  confirmation.
- The N/A option is matched as an option ("N/A ...", "Not applicable", "I no longer use ..."), not as any
  text containing "no longer use": a second header row with the question text would otherwise count as an
  N/A respondent. Such rows (equal to the header, ending in "?", or starting "How would you feel") are
  skipped and counted.

## Prioritizing the next actions (Vohra) [S3]

- Verbatim: "we labelled each potential project as low/medium/high cost, and similarly low/medium/high
  impact." For the half about what holds people back, "the impact was clear from the number of requests any
  given improvement had." For the half about what people love, "we had to intuit the impact." They started
  "with the lowest hanging fruit of low cost, high impact work".

## The Superhuman engine (Vohra 2018) [S3]

1. Four questions: the disappointment question; "What type of people do you think would most benefit from
   Superhuman?"; "What is the main benefit you receive from Superhuman?"; "How can we improve Superhuman for
   you?".
2. Segment. A persona was assigned to each respondent; the team kept the personas that appeared among the
   very-disappointed group. The article does not say how personas were assigned (checked 2026-11-19); the
   skill uses each respondent's own role or records, because the second question describes other people. The score was 22% across everyone and 33% within those personas. The answers to
   the second question describe the high-expectation customer (Julie Supan's term: "the most discerning
   person within your target demographic").
3. Split "somewhat disappointed" by the third question. Superhuman's very-disappointed users named speed as
   the main benefit. Somewhat-disappointed users who also named speed got close attention, and their
   answers to the fourth question showed what held them back. Those who named another benefit were set
   aside ("politely disregard"), as were the not-disappointed.
4. Roadmap: half on what the very-disappointed users love, half on what holds back the somewhat-disappointed
   users who share the main benefit.
5. Repeat and track. The score reached 58% after about three quarters.

The script supports step 2 with `--segment-col` and `--focus-segments`, and step 3 with `--benefit-col` (a
coded main-benefit column; the core benefit defaults to the most common one among very-disappointed
respondents) or `--benefit-match-col`. Coding the open answers is the agent's work.

## Where practitioners disagree, and limits

- **Arbitrary threshold.** Ellis says so himself [S2][S4]. The benchmark came from the startups he worked
  with or that shared results, which is a convenience set of early-stage companies and not a sample of all
  companies. Justin Jackson adds that the survey may be less useful for mature products [S8].
- **Necessary, not sufficient.** Tristan Kromer reports a company that scored above 40% without fit: the
  product "simply didn't work that well", early users answered on "the promise of a solution instead of the
  actual product", and the market was too small. He also reports Ellis saying in 2010 that the threshold was
  necessary but "not enough by itself" [S8].
- **Hypothetical question.** Jackson: people forecast their own feelings poorly; stated disappointment and
  later behaviour differ (his examples: Slack outages, Sunrise Calendar) [S8].
- **Ellis versus Vohra on "somewhat disappointed".** Ellis's rule is to ignore them, to avoid diluting the
  product for must-have users [S4]; his Survey.io page calls them the "key group" to move, by repositioning
  [S1].
  Vohra uses the half of them who share the main benefit [S3]. Ellis has since endorsed that refinement [S4].
- **Survivorship and self-selection.** The sampling rule takes people who are still active, and among those
  only the ones who reply. People who left never count against the score. The Real Startup Book's reading
  is that people who complete a survey skew positive, and that below a 10% response rate the score is
  probably overstated [S8]. The 10% is that book's rule of thumb; the response rate by itself predicts
  nonresponse bias poorly [S10], so the script reports the rate and asks for a check, not a direction.
- **Stated feeling, not behaviour.** The survey records what people say they would feel. Retention and
  activation are the behavioural checks to read beside it (Jackson's point about stated versus actual
  behaviour [S8]). The skill does not compute them.
- **B2B and small bases.** With a few dozen accounts the interval is tens of points wide (see "How many
  responses"), and several respondents from one account are not independent answers. No source resolves
  this; report counts, use `--account-col`, and consider interviews.
- **Segmenting after the fact.** Restricting the score to the personas that scored well raises it by
  construction (22% to 33% in [S3]). It is a targeting decision. The new score becomes evidence once a later
  wave, sampled for that segment, repeats it.

## Sources

- [S1] Sean Ellis, "Using Survey.io", startup-marketing.com (archived copy, 3 Jan 2012):
  https://web.archive.org/web/20120103081730/http://startup-marketing.com/using-survey-io/
- [S2] Sean Ellis, "The Startup Pyramid", startup-marketing.com (archived copy, 8 Jan 2013):
  https://web.archive.org/web/20130108095120/http://www.startup-marketing.com/the-startup-pyramid/
- [S3] Rahul Vohra, "How Superhuman Built an Engine to Find Product/Market Fit", First Round Review, 2018:
  https://review.firstround.com/how-superhuman-built-an-engine-to-find-product-market-fit/
- [S4] Sean Ellis interviewed on Lenny's Podcast, "The original growth hacker reveals his secrets":
  https://www.lennysnewsletter.com/p/the-original-growth-hacker-sean-ellis
- [S5] NIST/SEMATECH e-Handbook of Statistical Methods, section 7.2.4.1, "Confidence intervals":
  https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm
- [S6] E. B. Wilson (1927), "Probable inference, the law of succession, and statistical inference", Journal of
  the American Statistical Association 22(158), 209–212. https://doi.org/10.1080/01621459.1927.10502953
- [S7] L. D. Brown, T. T. Cai, A. DasGupta (2001), "Interval estimation for a binomial proportion",
  Statistical Science 16(2), 101–133. https://doi.org/10.1214/ss/1009213286
- [S8] Critiques: Justin Jackson, "Is the Product-Market Fit survey accurate?" (2019),
  https://justinjackson.ca/product-market-fit-survey ; Tristan Kromer, "Product Market Fit Survey: Why the
  40% Test Gives False Positives" (2014), https://kromatic.com/blog/false-positives-and-product-market-fit/ ;
  Kromatic, The Real Startup Book, "Product-Market Fit Survey",
  https://kromatic.com/real-startup-book/4-evaluative-product-experiments/survey-product-market-fit/

- [S9] Survey.io demo survey, "Customer Development Survey" (archived copy, 31 Dec 2011):
  https://web.archive.org/web/20111231115040/http://www.survey.io:80/survey/demo
- [S10] R. M. Groves, E. Peytcheva (2008), "The Impact of Nonresponse Rates on Nonresponse Bias: A
  Meta-Analysis", Public Opinion Quarterly 72(2), 167–189. https://doi.org/10.1093/poq/nfn011 (citation
  confirmed through Crossref on 2026-11-19; the finding as commonly summarised, the full text not read).
- [S10] NCSS Statistical Software documentation, chapter 514 "Two Proportions" ("C.I. for Difference: Wilson's
  Score as modified by Newcombe"): https://www.ncss.com/wp-content/themes/ncss/pdf/Procedures/NCSS/Two_Proportions.pdf
  Original: R. G. Newcombe (1998), "Interval estimation for the difference between independent proportions:
  comparison of eleven methods", Statistics in Medicine 17, 873–890.
- [S11] CRV, "Product-Market Fit Survey: How to Measure It Properly" (2026):
  https://www.crv.com/content/product-market-fit-survey
- [S12] Pendo help centre, "Product Market Fit (PMF) surveys":
  https://support.pendo.io/hc/en-us/articles/43942701779739

## Pitfalls

- Adding "somewhat disappointed" to the score.
- Surveying everyone on the list, only the keenest users, or people who have left, instead of a random
  sample of recent, repeat users.
- Keeping churned respondents (N/A) in the base without saying so, or dropping them without saying so.
- Calling a result above or below 40% when the interval includes 40%.
- Reading a segment with a handful of respondents as a finding.
- Treating 40% as a law, or a pass as proof of a viable market.
- Changing the question wording or options and still comparing with 40%.
- Narrowing to the best segments and reporting the higher score as if it were the same measurement.
- Reading "25–40%" as an official "nearly there" band.
- Announcing a rise or fall between two waves when the interval for the change includes 0, or comparing waves
  that used different wording, eligibility or delivery.
- Scoring a "Mildly disappointed" or 1–5 scale against 40%.
- Counting ten respondents from one customer as ten independent answers.
