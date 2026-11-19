# Survey data cleaning: method sources

Checked against the sources on 2026-11-12. "Read" means the text of the source itself was read; "secondary"
means the claim was confirmed only in another paper or page that reports it.

## Thresholds the script uses

| Check | Default | Flag to change it | Source |
|---|---|---|---|
| Speeder | duration below 1/3 of the median duration | `--speed-fraction` | Qualtrics panel practice; Miller et al. 2020 |
| Speeder, stricter variant | below 0.5 of the median | `--speed-fraction 0.5` | Greszki et al. 2015; Leiner 2019 |
| Speeder, page times | page speed index above 2.0 (page factors capped at 3) | `--page-time-cols`, `--rsi-cutoff` | Leiner 2019 |
| Speeder, per item | no default; duration per answered item is reported | `--min-per-item` | Huang et al. 2012 (secondary) |
| Straight-lining | every item in a grid has the same answer, or zero variability over the answered items | `--longstring-fraction`, `--longstring-min` | Kim et al. 2019 (simple nondifferentiation); Dunn et al. 2018 |
| Straight-lining, stricter variant | run longer than 0.5 of the items | `--longstring-fraction 0.5` | Curran 2016 |
| Smallest grid that can be flagged | 4 items | `--min-grid-items` | Convention: no published minimum, see "Straight-lining" |
| Pattern candidates (report only) | grids of 6 or more items | `--pattern-min-items` | Convention, see "Patterned answers" |
| Attention checks | 2 failed checks; 1 when only one check exists, a screening convention (Prolific allows a single failed check only in studies under 5 minutes) | `--attention-min-fails` | Prolific policy |
| Attention check left blank | counted as failed; `unshown` when skip logic may have hidden it | `--attention-blank` | Convention, see "Attention checks" |
| Duplicate (counted) | a later row repeating an earlier id, email or user-named key column | `--dup-cols` | Definition, see "Duplicates" |
| Identical answers, shared IP (candidates) | a later row identical in every column but the id; a later row with an earlier IP | `--dup-ignore`, `--dup-cols` | Definition, see "Duplicates"; counted only when confirmed |
| Item non-response | more than 0.5 of the question columns blank | `--max-missing` | AAPOR Standard Definitions (example rule) |
| Open answers (candidates, counted only when confirmed) | fewer than 3 characters; no vowels; a character 4 times in a row; 4 neighbouring keys; the same text of 20 or more characters from 2 or more respondents; word overlap of 0.8 or more between two such answers | `--open-min-chars`, `--repeat-run`, `--keyboard-run`, `--paste-min-chars`, `--similar-text` | No published threshold: see "Open answers" |
| Platform bot score (report only) | `Q_RecaptchaScore` below 0.5, ignored when `Q_RecaptchaStatus` is "error" | `--recaptcha-min` | Qualtrics fraud detection page |
| High-share warning | a check, the 2+ flag group or the removal above 0.12 of respondents | `--warn-share` | Comparison point from Meade & Craig 2012; a convention, see "Sample-level summary" |
| Removal | none; only with `--drop-if`; the recommended rule is `count>=2`, previewed with `--preview` first | `--drop-if`, `--preview` | see "Removal policy" |

## Speeders

- **Greszki, Meyer & Schoen 2015** (read, in the authors' manuscript). They measure speed per page against
  the median page time, and use three cut-offs because "the ultimate choice of a specific threshold is
  somewhat arbitrary": more than 30, 40 or 50 percent faster than the median, i.e. below 0.7, 0.6 or 0.5 of
  it. The 50 percent criterion is "rather hard" and "insensitive to 'false positives'"; it flagged about 8%
  of respondents in one survey and 4% in the other, the 30 percent criterion about 21%. Removing speeders
  did not change marginal distributions and barely changed model coefficients.
- **Leiner 2019** (read). Completion time was the most reliable non-reactive indicator of careless answers.
  Relative speed index: for each page, the sample's median page time divided by the respondent's time;
  page factors are capped at 3 and averaged. A page time of 0 gets the cap, the limit of median/time as the
  time falls to 0 (1 when the median is 0 too); that limit is this skill's reading. A cut-off of about 1.3 separated his careless and careful
  groups, but his "pragmatic recommendation is to use a much more lenient cut-off of 2.0", i.e. twice as
  fast as the typical respondent, which equals 0.5 of the median. He warns that speed is not a valid
  indicator when the questionnaire asks for facts or knowledge, because experts answer faster.
- **Industry practice: 1/3 of the median.** Qualtrics' panel team screens out respondents who take less
  than one third of the median time of the soft launch and calls this an industry standard (secondary: the
  page text was seen only in search results). Miller et al. 2020 (read) describe their two Qualtrics
  samples as cleaned by "speeding checks (i.e., respondents with survey duration of ≤ one-third of the
  median duration of survey)".
- **Disagreement and the default.** Sources range from 0.7 to 1/3 of the median, and Greszki et al. say the
  choice is arbitrary. The script has one total duration per respondent, not page times, so it defaults
  to the rule that is defined on total duration and flags the fewest people: below 1/3 of the median.
  0.5 is the academic alternative. The median is used, not the mean, because completion times are heavily
  skewed (Leiner reports skewness 12 for one study).
- **Page times and paths.** Greszki et al. and Leiner both work with page times, and Greszki et al.
  computed "separate page medians for those with and without follow-up questions" because respondents on
  a shorter path "are naturally faster" (read). `--page-time-cols` gives Leiner's index; `--speed-by`
  computes every median within a path or device group. No source gives a minimum group size; the group
  sizes are printed.
- **Per item.** Huang et al. 2012 call under 2 seconds per item a conservative cut-off (secondary, quoted
  in Jones et al. 2023, who found it flagged nobody in their data and used 3 and 4 seconds). The script
  reports duration per answered item and flags on it only when the user sets `--min-per-item`; it cannot
  know the unit of the duration column or how many items a respondent was shown.
- Pew 2020 (read) defined speeding as under three minutes against a seven-minute median and found that 76%
  of bogus respondents passed both that speed check and an attention check. Speed alone misses most fraud.

## Straight-lining

- **Long string** (Johnson 2005, as quoted by Leiner 2019, read): "the length of the longest sequence of
  the same answer within an item battery". The R package `careless` (manual read) computes the same thing:
  the "maximum uninterrupted string of identical responses". The script computes it per grid; a blank
  breaks the run.
- **Kim, Dykema, Stevenson, Black & Moberg 2019** (abstract read; indicator definitions from the `resquin`
  R manual, which implements them). Five indicators: simple nondifferentiation (1 if all answers in the
  battery have the same value), mean root of pairs, maximum identical rating, standard deviation of
  battery, scale point variation. The paper notes there is no standard measurement technique. The script's
  default is simple nondifferentiation, the strictest definition.
- **Curran 2016** (secondary, quoted in Jones et al. 2023, read): a starting point for a problematic string
  is "one that is greater than half the length of the total scale being considered"; for 32 items, 17 or
  more. This is `--longstring-fraction 0.5`.
- **Meade & Craig 2012** (abstract read): about 10–12% of an undergraduate sample responded carelessly;
  long strings identified only a small group; they recommend instructed-response items plus consistency
  indices and multivariate outlier analysis.
- **Leiner 2019**: the longest string was among the weaker indicators in his studies.
- **Minimum grid size: 4 items, a convention.** No source read here gives a minimum. A short grid, or one
  where all items point the same way, can be answered identically by an attentive respondent, and with two
  or three items it routinely is. Four is this skill's choice: the smallest size at which the stricter
  variant (a run longer than half the grid) still needs three identical answers in a row. Grids below the
  minimum are reported (run length, variability) but never flagged. Raise it for single-direction grids.
- **Intra-individual response variability** is the "standard deviation of responses across a set of
  consecutive item responses for an individual" (Dunn, Heggestad, Shanock & Theilgard 2018, p. 108, as
  quoted in the `careless` manual, read). The same manual notes that Dunn et al. treat low values as the
  sign of straight-lining while Marjanovic et al. 2015 treat high values as the sign of random answering.
  No fixed cut-off was found in anything read here, so the script reports the value per grid (sample
  standard deviation of the answered items) and flags only a value of exactly zero over at least
  `--min-grid-items` answered items, which is straight-lining by definition. It counts under the
  straight-lining flag, not as a second flag.

## Patterned answers

- Leiner 2019 (read) names "diagonal lines" next to straight lines as response patterns and scored them
  with his own algorithm. No published cut-off was found.
- The script marks a fully answered numeric grid as a candidate when the answers repeat a block of two or
  more values through the whole grid (1-2-1-2-1-2) or move by exactly one step every time with at least
  three steps in one direction (1-2-3-4-5-4). Both definitions and the 6-item minimum are this skill's
  conventions; 6 is the shortest grid in which a block of two repeats three times. Candidates are
  report-only and never count toward the flag count, because attentive answers can form these shapes.

## Duplicates

- The script counts as a `duplicate` a later row that repeats an earlier value in the id column or in an
  identifying key column (email, or a column the user names). These are definitions, not thresholds.
- Two weaker signals are candidates, counted only when a reviewer confirms them: `identical_answers`, a
  later row identical to an earlier one in every column except the id, and `shared_ip`. Identical answers
  are not evidence of a duplicate submission on their own: in a one-question yes/no survey every second
  "Yes" is identical to the first, and in any short closed-ended survey the number of possible answer
  patterns is small. Corroborating evidence (an id, an email, a long open answer, matching timestamps)
  is what a reviewer looks for before confirming. This split is this skill's convention; Pew 2020 (below)
  likewise had a researcher review every suspected duplicate before acting on it.
- Pew 2020 (read) found duplicates by comparing open answers (three or more highly similar answers out of
  six, then a human review): 0.3% of interviews overall, 1.1% in the crowdsourced sample.
- The R package `careless` also offers even-odd consistency and psychometric synonyms and antonyms. They
  need a questionnaire with several multi-item scales and are out of scope here; use that package.
- A shared IP is not proof of a duplicate: households, offices, universities and mobile carriers share
  addresses, so `shared_ip` is a candidate, not a counted flag. Emails and IPs are personal data; keep the
  flags file with the same care as the export.

## Attention checks

- **Prolific's attention and comprehension check policy** (read): in studies of 5 minutes or longer,
  "participants must fail at least two checks to be rejected"; shorter studies "can use a single failed
  check to reject". Valid checks are instructional manipulation checks and nonsensical items. "Attention
  checks shouldn't rely on speed."
- **Berinsky, Margolis & Sances 2014** (abstract and the authors' journal summary read): passing a screener
  correlates with respondent characteristics (women and older respondents passed more often), so excluding
  failers changes who is in the sample. They recommend several screeners instead of one and presenting
  "results for both attentive and inattentive respondents". In their surveys 60 to 70 percent passed a
  given screener.
- **Disagreement.** Meade & Craig recommend instructed-response items; Berinsky et al. caution against
  simply dropping failers; Leiner found that a manipulation check also misidentified many careful
  respondents. The default needs two failures; with one check in the survey a single failure flags. That
  fallback is a screening convention, not Prolific's rule for studies of 5 minutes or longer, and the log
  says so.
- **Blank checks.** No source read here says whether a blank attention item is a failure. When the item
  was required or always shown, a blank is a skipped instruction and the default counts it as failed;
  when skip logic may have hidden it, a blank is "not shown" (`--attention-blank unshown`). Either way the
  respondents with a blank check are listed. This is the skill's convention.

## Item non-response

- AAPOR Standard Definitions give as an example rule: complete = more than 80% of applicable questions
  answered, partial = 50% to 80%, break-off = less than 50% (secondary: an AAPOR webinar handout and the
  SAGE Encyclopedia of Survey Research Methods; the handout presents these as examples and says the rule
  must be set in advance). The default flags the break-off range: more than 0.5 blank.
- The script cannot see skip logic. A blank cell that the respondent was never shown counts as blank;
  restrict the columns with `--item-cols` when the survey branches.
- Form metadata columns (`Timestamp` in Google Forms, `Submitted At`, `Start time`, `Completion time` and
  similar names) are not questions and are left out of the default question columns; this list of names
  is the skill's convention. Optional open-text questions stay in: a blank there is still item
  non-response; pass `--item-cols` to leave them out when they were optional.

## Open answers

No published numeric threshold exists for these heuristics; the defaults are this skill's own choices, set
so that only near-empty or mechanical answers are caught, and every hit is a candidate for a person to
read, not a verdict.

- Fewer than 3 characters: catches "x", "-", "ok", and also a fair "No".
- No vowels (Latin letters only; skipped when the answer has other letters).
- The same character 4 times in a row: "www" is the longest run in ordinary text. Digits are ignored.
- 4 neighbouring keys on one QWERTY row in one direction ("asdf", "poiu"). "erty" and "wert" are exempt
  because they occur in words such as "property" and German "Wert".
- The same text of 20 or more characters from two or more respondents: shorter repeats ("nothing", "no
  comment") are normal.
- Near-duplicates: word overlap (Jaccard index: shared distinct words divided by all distinct words of the
  two answers) of 0.8 or more between two answers that are each at least 20 characters long. Pew 2020
  (read) treated "highly similar" open answers as its evidence for duplicate respondents and had a
  researcher review every pair; it gives no numeric similarity cut-off, so 0.8 is a convention.
- These candidates count toward removal only when a reviewer confirms one (`--confirm`). Pew 2020 had a
  researcher review every flagged pair, and a fair "No" or "CRM" must not reach a `count>=2` rule
  together with one other weak signal unread.
- **Near-duplicate search.** To avoid comparing every pair, the script uses exact prefix filtering
  (Bayardo, Ma & Srikant 2007): with words ordered rarest first, two answers whose word overlap is at
  least t must share a word among the first |x| − ⌈t·|x|⌉ + 1 words of each, so only those pairs are
  compared, because the overlap |x ∩ y| is at least t·|x ∪ y| ≥ t·|x|. The result is identical to
  comparing every pair (the test suite checks this against the all-pairs comparison). Citation checked
  against the Crossref record; the paper's text was not re-read for this revision.
- Off-topic, copied-from-the-question and machine-written answers need a reader; the script does not
  attempt them. Pew 2020 used open answers as its strongest evidence of bogus respondents.

## Platform exports and fraud fields

- **Qualtrics CSV layout** ("Understanding your dataset", read): three header rows (internal names, question
  text, import ids); data starts on the fourth row. `Status`: 0 = IP Address (a normal response), 1 = Survey
  Preview, 2 = Survey Test, 4 = Imported, 16 = Offline, 17 = Offline Preview, 256 = Synthetic; the Spam
  statuses are deprecated. `Finished`: 1 / True = reached an end point, 0 / False = left before one.
  `Duration (in seconds)` includes time away from the survey. The page does not show the third row's cell
  format; the script recognises it by cells that start with `{"ImportId"`, the form seen in exports.
- The script sets aside previews, tests and synthetic responses (`Status` 1, 2, 17, 256 or the matching
  labels) and unfinished rows
  (`Finished` 0 / False): they are listed in the log, get no flags, do not enter any median, and stay in
  the file unless the user removes them with `--drop-if not_screened`.
- **Qualtrics fraud detection fields** (read). `Q_RecaptchaScore` runs from 0 to 1: "A score of greater
  than or equal to 0.5 means the respondent is likely a human"; it "should be disregarded if
  Q_RecaptchaStatus is 'error'", and it is set to its default of 1 when the survey ends too quickly or
  reCAPTCHA fails to load, so a high score is weak evidence. `Q_BallotBoxStuffing`: "If true (1), it
  means the response is likely a duplicate." `Q_DuplicateRespondent`: true = a duplicate under the
  threshold the survey owner configured. The RelevantID fields (`Q_RelevantIDDuplicate`,
  `Q_RelevantIDDuplicateScore`, `Q_RelevantIDFraudScore`, `Q_RelevantIDLastStartDate`) were deprecated on
  30 June 2025 and record only 0, false or blank for newer responses; the script does not use them.
- These fields are reported in their own columns and do not count toward the flag count: they come from
  the platform's settings, not from the answers, and an absent column is reported as "not present".

## Sample-level summary

- The log gives the share flagged by each check, the share with one or more and two or more flags, and
  the pairs of flags that occur together.
- **Comparison point 0.12, a convention.** Meade & Craig 2012 (abstract read) estimate that about 10–12%
  of their undergraduate sample responded carelessly. The script warns when a single check, the group
  with two or more flags, or the removal exceeds 0.12. This is not a quality band: panels, incentives and
  survey length move the rate, and Berinsky et al. saw 30 to 40 percent fail a single screener. The
  warning means "look at the threshold and the sample source", not "the data are bad".
- **Who is removed.** Berinsky et al. 2014: screener failure correlates with respondent characteristics.
  `--compare-cols` tabulates the removed (or two-or-more-flag) group against the rest on the named
  columns. It gives counts, no significance test.

## Reviewer decisions

- `--clear` removes a flag and `--confirm` makes a candidate count; both are recorded in the log. The
  checks table reports the hits before review, the ids cleared or confirmed, and the final count and
  share, and the high-share warnings use the final counts, so the table and the removal agree.

## Rules fixed in advance

- A threshold in a pre-registration, an analysis plan or a panel contract overrides every default here;
  the defaults are for studies that fixed nothing. AAPOR's Standard Definitions material says the rule
  for a complete or partial case must be set a priori (secondary), and Prolific's policy binds what may be
  rejected on that panel (read).
- A rule chosen after looking at the results can be tuned, knowingly or not, toward a preferred result.
  The log records, per rule, what the user stated with `--set-before`: yes, no (post hoc), or not stated.
  The script cannot check the statement.

## Removal policy

- **Several indicators, not one.** Curran 2016 (secondary) recommends a multiple-hurdle approach: several
  indicators that catch different behaviours, each with a conservative cut-off. Leiner 2019 (read): "the
  accuracy of isolated non-reactive indicators is limited" and a combination should let "each indicator
  only [identify] particularly abnormal cases in its own respect". Meade & Craig 2012 recommend combining
  indicators. Prolific requires two failed checks. No study was found that compares "two or more flags"
  with single-flag removal, so `count>=2` is a conservative convention, not a tested optimum.
- **Removal has costs.** Greszki et al. 2015: removing speeders hardly changed results. Leiner 2019:
  removing probable careless records "means to also remove some valid questionnaires", and it matters more
  in a representative sample. Berinsky et al. 2014: removal shifts sample composition.
- **Report it.** AAPOR Disclosure Standards, item III.A.10 "How the Data Were Processed and Procedures to
  Ensure Data Quality" (read): "Describe validity checks, where applicable, including but not limited to
  whether the researcher added attention checks, logic checks, or excluded respondents who straight-lined
  or completed the survey under a certain time constraint", and "any data imputation or other data
  exclusions or replacement will also be discussed."
- **Run results both ways.** Berinsky et al. 2014 (results for attentive and inattentive respondents);
  Greszki et al. 2015 compared every result with and without speeders.

## Sources

1. Greszki, R., Meyer, M., & Schoen, H. (2015). Exploring the effects of removing "too fast" responses and
   respondents from web surveys. *Public Opinion Quarterly*, 79(2), 471–503.
   https://doi.org/10.1093/poq/nfu058 (manuscript:
   https://www.sowi.uni-mannheim.de/media/Lehrstuehle/sowi/Schoen/PDFs/Greszki_Meyer_Schoen_2014_Impact_of_Speeding.pdf)
2. Leiner, D. J. (2019). Too fast, too straight, too weird: Non-reactive indicators for meaningless data in
   internet surveys. *Survey Research Methods*, 13(3), 229–248.
   https://ojs.ub.uni-konstanz.de/srm/article/view/7403
3. Curran, P. G. (2016). Methods for the detection of carelessly invalid responses in survey data. *Journal
   of Experimental Social Psychology*, 66, 4–19. https://doi.org/10.1016/j.jesp.2015.07.006
4. Meade, A. W., & Craig, S. B. (2012). Identifying careless responses in survey data. *Psychological
   Methods*, 17(3), 437–455. https://doi.org/10.1037/a0028085
5. Kim, Y., Dykema, J., Stevenson, J., Black, P., & Moberg, D. P. (2019). Straightlining: Overview of
   measurement, comparison of indicators, and effects in mail–web mixed-mode surveys. *Social Science
   Computer Review*, 37(2), 214–233. https://doi.org/10.1177/0894439317752406
6. Berinsky, A. J., Margolis, M. F., & Sances, M. W. (2014). Separating the shirkers from the workers?
   *American Journal of Political Science*, 58(3), 739–753. https://doi.org/10.1111/ajps.12081 (authors'
   summary: https://ajps.org/2015/03/16/methods-to-identify-inattentive-respondents/)

Supporting:

- Prolific, attention and comprehension check policy:
  https://researcher-help.prolific.com/en/articles/445153-prolific-s-attention-and-comprehension-check-policy
- AAPOR Disclosure Standards: https://www.aapor.org/standards-and-ethics/disclosure-standards
- Pew Research Center (2020), two common checks fail to catch most bogus cases:
  https://www.pewresearch.org/methods/2020/02/18/two-common-checks-fail-to-catch-most-bogus-cases/
- Miller, C. A., Guidry, J. P. D., Dahman, B., & Thomson, M. D. (2020). A tale of two diverse Qualtrics
  samples. *Cancer Epidemiology, Biomarkers & Prevention*, 29(4), 731–735.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8758054
- Jones, E. A., Wind, S. A., Tsai, C.-L., & Ge, Y. (2023). Comparing person-fit and traditional indices
  across careless response patterns in surveys. *Applied Psychological Measurement*, 47(5–6), 365–385.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10552731
- Qualtrics, understanding your dataset:
  https://www.qualtrics.com/support/survey-platform/data-and-analysis-module/data/download-data/understanding-your-dataset/
- Qualtrics, fraud detection:
  https://www.qualtrics.com/support/survey-platform/survey-module/survey-checker/fraud-detection/
- Dunn, A. M., Heggestad, E. D., Shanock, L. R., & Theilgard, N. (2018). Intra-individual response
  variability as an indicator of insufficient effort responding. *Journal of Business and Psychology*.
  https://doi.org/10.1007/s10869-017-9514-9
- R package `careless` (longstring, irv): https://cran.r-project.org/package=careless
- Bayardo, R. J., Ma, Y., & Srikant, R. (2007). Scaling up all pairs similarity search. *Proceedings of the
  16th International Conference on World Wide Web*, 131–140. https://doi.org/10.1145/1242572.1242591
- R package `resquin`, `resp_nondifferentiation`: https://rdrr.io/cran/resquin/man/resp_nondifferentiation.html
- Qualtrics, quality measures within your survey:
  https://www.qualtrics.com/panels-project/quality-measures-within-your-survey

## Pitfalls

- Deleting rows without a record: flag first, remove only by a stated rule, keep the removed rows.
- Removing on one indicator: each indicator alone misclassifies careful respondents.
- Treating a long string as proof on a short grid or one with no reverse-worded items.
- Using the mean duration, or one cut-off across survey paths of very different length.
- Using speed on a survey of facts or knowledge, where experts are legitimately fast.
- Treating a shared IP, or identical answers in a short survey, as proof of duplication.
- Counting blanks from skip logic as non-response.
- Treating open-answer heuristics as verdicts; "No" can be a complete answer.
- Removing respondents and reporting only the cleaned result.
- Reading a Qualtrics export with its two extra header rows as data, or screening preview and test rows.
- Reading an absent platform fraud column as "passed", or a reCAPTCHA score of 1 as proof of a human.
- One speed cut-off across paths or devices of different length (use `--speed-by`).
- Choosing thresholds after seeing which respondents they remove.
- Expecting this skill to impute, trim outliers, reverse-code or score scales: it does none of these.
