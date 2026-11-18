# Open-ended coding: method sources

Checked on 2026-11-12. "Verified" means the statement was read in the source itself (full text or the
author's own PDF) on that date. Skill defaults that no source prescribes are listed separately so nobody
mistakes them for a standard.

## Which tradition this skill follows

Braun and Clarke (2021, pp. 333–335) sort thematic analysis into three families:

- **Coding reliability** approaches: a fixed codebook, several independent coders, agreement measured.
- **Codebook** approaches (framework analysis, template analysis): a structured coding frame, themes
  developed early and refined on the data, agreement not usually treated as the quality measure.
- **Reflexive** thematic analysis (their own): coding is "open and organic, with no use of any coding
  framework"; a research team "is not required or even desirable".

They call measuring coding reliability inside reflexive analysis "illogical, incoherent and ultimately
meaningless". This skill is therefore **not** reflexive thematic analysis and must not be described as
"Braun and Clarke thematic analysis". It sits between the first two families: a codebook built inductively
from a sample (as in the Framework Method, Gale et al. 2013), applied to every answer, counted, and
checked with a second coder. That fits short survey answers where the reader wants "how many said what".
It is the wrong tool for an interpretive study of long interviews.

## Codebook format

- MacQueen et al. (1998) give six parts for each code: the code, a brief definition, a full definition,
  guidelines for when to use it, guidelines for when not to use it, and examples. The skill's fixed
  columns map onto them: `code`, `label` (brief), `definition` (full), `include` (when to use), `exclude`
  (when not to use), `example_quote`.
- Gale et al. (2013), Framework Method, stage 4: codes are grouped into categories that are "clearly
  defined". The same paper: "It is always worth having an 'other' code under each category to avoid
  ignoring data that does not fit." Stage 3: "At least two researchers ... should independently code the
  first few transcripts, if feasible."
- AAPOR (2022, Best Practices for Survey Research): open-ended questions "require coding in order to be
  interpreted quantitatively". AAPOR gives no procedure for the coding itself.

## Sample size for building the codebook, and when to stop adding codes

- Tran et al. (2016) resampled a survey with open-ended questions. The probability that the next
  respondent adds at least one new theme was 32%, 24% and 12% after 30, 50 and 100 respondents. 150
  random respondents found 92% of the themes (interquartile range 91–93%) of the full study.
- Guest, Namey and Chen (2020) define saturation with three numbers: a **base** (the first units
  analysed), a **run** (the next units, in which new information is counted) and a **new-information
  threshold**: new themes in the run divided by the themes in the base, with ≤5% or 0% as the stopping
  levels. They validated it on individual interviews only, with bases of 4 to 6 and runs of 2 to 3.
- Disagreement: saturation is a contested idea. Braun and Clarke reject it for reflexive analysis; Guest
  and colleagues stress that their thresholds are benchmarks, not guarantees. For a survey the practical
  consequence is small: every answer gets coded anyway, so a theme missed in the sample shows up in
  `OTHER`, which is why the skill re-reads `OTHER` after the full pass.

## Counts and denominators

Definitions used by `counts` (plain arithmetic, no source needed):

- all respondents = rows in the file;
- answered = rows with non-blank text = all respondents − `NO_ANSWER`;
- codable = answered − `UNCODABLE`;
- share of a code = respondents carrying the code ÷ base. A response with several codes is counted once
  under each, so the shares add up to more than 100% whenever anyone gave a multi-code answer. They are
  shares of respondents, not of mentions.
- `--mentions` adds share of mentions = the code's count ÷ all code assignments (substantive codes and
  `OTHER`). It adds up to 100% and answers a different question ("what share of everything said").
- A net (codebook column `parent`) = respondents carrying at least one of its codes, each counted once.
  It is at most the sum of its codes' counts and smaller whenever an answer carries two of them.

### Interval on a share

Wilson score interval (Wilson 1927), no continuity correction, as printed in the NIST/SEMATECH
e-Handbook, section 7.2.4.1, with p = x/n and z = 1.959964 for 95%:

lower, upper = ( p + z²/2n ∓ z·sqrt( p(1−p)/n + z²/4n² ) ) / ( 1 + z²/n )

Checked against the handbook's worked example (p̂ = 0.13, N = 200, z = 1.645, lower limit 0.09577); the
sibling skill `pmf-survey` uses the same check. The interval covers sampling error only and assumes a
random sample of the population; it says nothing about coding error or about who chose to answer.
Differences between segments are not tested here: that is the sibling skill `survey-crosstabs`.

### Codebook health check

`counts` flags four signs that a codebook needs work. No source prescribes the cut-offs; they are
conventions and each has a flag:

| Sign | Default | Flag | Reading |
|---|---|---|---|
| Code used fewer than k times | 5 | `--rare-below` | too few answers to report alone; merge or net |
| Code on more than x% of answers | 50 | `--broad-above` | probably two ideas in one code |
| `OTHER` above x% of answers | 10 | `--other-above` | the codebook does not cover the answers (Gale et al. keep "other" so nothing is ignored; a large one means codes are missing) |
| Pairs of codes that occur together | top 5 | `--top-pairs` | if most of one code sits inside another, the definitions overlap |

### Sentiment column

`--sentiment-col` counts a column the coder filled with one of positive, negative, neutral, mixed. The
script does not score sentiment. The four values are a convention.

### Small bases

There is no agreed standard. The script withholds percentages when the base is under 30
(`--min-base`). 30 is a widespread tabulation convention, not a statistical law: the Quantum tabulation
manual's own example is `smbase=30` with the table note "marked bases are very small (under 30): percents
suppressed". Agencies use other cut-offs (the search for this skill found 20 in the numerator and 100 in
the denominator in a US National Cancer Institute guideline; read in a search summary only). Raise
`--min-base` when the reader's house rule is stricter.

## Agreement between two coders

### Cohen's kappa (Cohen 1960)

κ = (p_o − p_e) / (1 − p_e), where p_o is the share of units on which the coders agree and
p_e = Σ_k p_A(k) · p_B(k) uses each coder's own share of category k. Formula verified in McHugh (2012)
and in the worked example below.

- κ is **undefined when p_e = 1** (both coders gave every unit the same single value, for example a
  code neither of them used): the denominator is zero. The script reports "undefined" with the reason.
- Worked example (Wikipedia, "Cohen's kappa", simple example): 50 grant proposals, 20 yes/yes, 5 yes/no,
  10 no/yes, 15 no/no. p_o = 0.70, p_e = 0.5·0.6 + 0.5·0.4 = 0.50, κ = 0.40.
- Same agreement, different kappa (same article): tables (45, 15, 25, 15) and (25, 35, 5, 35) both
  agree on 60% of units; κ is 0.1304 and 0.2593 because p_e is 0.54 and 0.46.

### Reading kappa

| Source | Bands |
|---|---|
| Landis and Koch (1977, p. 165) | < 0.00 poor; 0.00–0.20 slight; 0.21–0.40 fair; 0.41–0.60 moderate; 0.61–0.80 substantial; 0.81–1.00 almost perfect |
| McHugh (2012, Table 3) | 0–0.20 none; 0.21–0.39 minimal; 0.40–0.59 weak; 0.60–0.79 moderate; 0.80–0.90 strong; above 0.90 almost perfect |

- Landis and Koch on their own table: "Although these divisions are clearly arbitrary, they do provide
  useful 'benchmarks' for the discussion of the specific example in Table 1." They offered no evidence
  for the cut points.
- McHugh: the traditional reading "may be too lenient for health related studies because it implies that
  a score as low as 0.41 might be acceptable".
- O'Connor and Joffe (2020): "All such guidelines are ultimately arbitrary, and the researcher must judge
  what represents acceptable agreement for a particular study."
- The kappa paradox (Feinstein and Cicchetti 1990): a code that is rare (or nearly universal) can have
  high percent agreement and a low or negative kappa, because p_e is close to 1. The companion paper
  (Cicchetti and Feinstein 1990) recommends reporting agreement on positives and on negatives next to
  kappa. With a = both coders used the code, b and c = only one did, d = neither:
  positive agreement = 2a / (2a + b + c), negative agreement = 2d / (2d + b + c).
- PABAK, the prevalence-adjusted bias-adjusted kappa (Byrt, Bishop and Carlin 1993) = 2·p_o − 1: kappa
  as it would be with both categories equally common and no bias between coders. It is a companion
  figure, not a replacement: critics note it removes the very effects kappa is meant to reflect, so the
  script prints it next to kappa and never instead of it.
- The script flags "high agreement, low kappa" when percent agreement is 80% or more and kappa is under
  0.40. Both cut-offs are conventions (0.40 is the top of Landis and Koch's "fair").
- **Gwet's AC1 is not implemented.** Its formula could not be read at a primary source during this
  build, so it was left out rather than coded from memory.

### Statistics that are not agreement measures

- **Chi-square** tests whether two codings are associated. Two coders who systematically disagree
  (one says A whenever the other says B) are perfectly associated and never agree.
- **Pearson's r** (and other correlations) measures whether values move together. A coder who always
  scores one point higher correlates perfectly and agrees never.
- **Cronbach's alpha** measures whether the items of a scale hang together (internal consistency). It
  is not Krippendorff's alpha and says nothing about two coders assigning the same code.
- **Percent agreement** is an agreement measure but not chance-corrected; report it next to kappa or
  alpha, not alone.

### Agreement with a reference coder (human versus LLM)

With `--gold`, the first coder is the reference and the other is scored against it per code, with
TP = both used the code, FP = only the compared coder, FN = only the reference:

precision = TP / (TP + FP); recall = TP / (TP + FN); F1 = 2TP / (2TP + FP + FN).

F1 is the same number as positive agreement. These are the standard information-retrieval definitions
(Manning, Raghavan and Schütze 2008, ch. 8). They are descriptive: a "gold" coder is one person's
reading, not the truth. What studies of LLM coding found is in [`llm-coding.md`](llm-coding.md).

### Confidence intervals on kappa and alpha

A percentile bootstrap (Efron and Tibshirani 1993): responses are resampled with replacement, every
statistic is recomputed, and the interval runs from the 2.5th to the 97.5th percentile of the
replicates (linear interpolation between ranks). Whole responses are resampled, so codes that occur
together stay together. Defaults: 2,000 replicates and seed 1 (conventions; the seed is printed).

- A replicate in which a statistic is undefined (a rare code missing from the resample) is dropped; if
  fewer than half of the replicates are defined, no interval is given (the skill's own rule).
- Krippendorff's own bootstrap for alpha (Hayes and Krippendorff 2007) resamples coincidences, not
  units. The two give different intervals on small samples; the script states which one it used.
- With a few dozen double-coded answers the intervals are wide and often span several bands. That is
  the correct picture: the script marks an interval that crosses a band edge.

### More than two coders

Krippendorff's alpha takes any number of coders and rows that some coders skipped. The script reports
alpha per code over all coders and Cohen's kappa for every pair (on the rows both coded). It does not
compute Fleiss' kappa.

### Krippendorff's alpha, nominal (Krippendorff 2011)

Build the coincidence matrix: a unit with m values adds 1/(m − 1) to cell (c, k) for every ordered pair of
values c, k from different coders. With n_c the row totals and n = Σ n_c the number of pairable values:

α = [ (n − 1) · Σ_c o_cc − Σ_c n_c (n_c − 1) ] / [ n (n − 1) − Σ_c n_c (n_c − 1) ]

For two coders and a binary code this reduces to α = 1 − (n − 1) · o_01 / (n_0 · n_1). Alpha handles any
number of coders and missing values; the command line compares two coders, the function takes any number.
Alpha is undefined when all values are the same (the denominator is zero).

Verified against Krippendorff's three worked examples in that paper (see `fixtures/README.md`):
A = 0.095, B = 0.692, C = 0.743.

- Thresholds (Krippendorff 2004, pp. 241–243): rely on α ≥ 0.800; use 0.667 ≤ α < 0.800 only for
  tentative conclusions; below 0.667 do not rely on the variable.
- Kappa versus alpha for two coders: kappa takes chance agreement from each coder's own marginals, alpha
  from the pooled values with a small-sample correction. They are close when the coders use a code about
  equally often and the sample is not tiny; they differ when the coders' rates differ.

### How much to double-code, and what to report

O'Connor and Joffe (2020), verified in the full text:

- "A minimum of two independent coders is necessary". When one person codes most of the data, an
  additional person codes a sample.
- "there is little consensus regarding the proportion of the data set ... Depending on the size of the
  data set, 10–25% of data units would be typical", selected at random.
- The second coder gets a clean file that shows the units but not the first coder's codes.
- Pooling all codes' figures lets weak codes hide behind easy ones; report per code, or at least the range.
- Codes below the threshold are revised or removed, and the revised frame is tested "preferably on a
  different subset of data". Once final, the frame is applied to the whole data set, recoding what was
  coded during the test.
- Percent agreement alone is rejected by methodologists because it ignores chance; Miles and Huberman's
  80% on 95% of codes is the usual citation for a percent standard.

### When the agent is the only coder

A second pass by the same model in a fresh context is not an independent coder. In Krippendorff's terms
it tests stability (the same coder, again) rather than reproducibility (different coders). It still
catches vague definitions, and it is cheap, so the skill runs it when no person is available and labels
the result as a same-model second pass. A person coding the sample blind is the stronger check and the
only one that says anything about whether the model's reading matches a human's.

## Skill defaults that no source prescribes

| Default | Value | Why |
|---|---|---|
| Codebook-building sample | 100 answered rows, all if fewer | Tran et al.: 12% chance of a new theme per extra respondent after 100 |
| Saturation log | base = first 50 sampled answers, runs of 25, stop at ≤5% new codes | Guest et al.'s method scaled from interviews to short answers; an adaptation, not validated |
| Pilot batch | 30 fresh answers coded by both coders, compared informally | O'Connor and Joffe advise a small informal double-coding before the formal test; 30 is this skill's number |
| Top-up of rare codes in the double-coded sample | `--top-up-min 5` suggested | same 5 as the rare-code flag; convention |
| Double-coded sample | 20% of answered rows, at least 30 | inside O'Connor and Joffe's "typical" 10–25%; 30 matches the small-base convention |
| Revise a code | kappa under 0.60 or alpha under 0.667 | McHugh's "weak" boundary; Krippendorff's lower limit |
| Small base | percentages withheld under 30 | tabulation convention, see above |
| Quotes per top code | 2–3 | convention; enough to show range without cherry-picking one |
| Sampling seed | 1 unless given | any fixed value; it is reported so the draw can be repeated |
| Bootstrap | 2,000 replicates, seed 1, no interval if under half the replicates are defined | convention |
| High agreement, low kappa flag | agreement ≥ 80% and kappa < 0.40 | convention |
| Health check | rare under 5 uses, broad over 50%, `OTHER` over 10%, top 5 pairs | conventions, all settable |
| Sentiment values | positive, negative, neutral, mixed | convention |

## Sources

1. Braun, V., & Clarke, V. (2021). One size fits all? What counts as quality practice in (reflexive)
   thematic analysis? *Qualitative Research in Psychology*, 18(3), 328–352.
   https://doi.org/10.1080/14780887.2020.1769238 (see also Braun & Clarke 2006,
   https://doi.org/10.1191/1478088706qp063oa)
2. Gale, N. K., Heath, G., Cameron, E., Rashid, S., & Redwood, S. (2013). Using the framework method for
   the analysis of qualitative data in multi-disciplinary health research. *BMC Medical Research
   Methodology*, 13, 117. https://doi.org/10.1186/1471-2288-13-117
3. O'Connor, C., & Joffe, H. (2020). Intercoder reliability in qualitative research: debates and
   practical guidelines. *International Journal of Qualitative Methods*, 19.
   https://doi.org/10.1177/1609406919899220
4. Krippendorff, K. (2011). *Computing Krippendorff's Alpha-Reliability*.
   https://repository.upenn.edu/asc_papers/43 and Krippendorff, K. (2004). *Content Analysis: An
   Introduction to Its Methodology* (2nd ed.). Sage.
5. Landis, J. R., & Koch, G. G. (1977). The measurement of observer agreement for categorical data.
   *Biometrics*, 33(1), 159–174. https://doi.org/10.2307/2529310 and McHugh, M. L. (2012). Interrater
   reliability: the kappa statistic. *Biochemia Medica*, 22(3), 276–282.
   https://doi.org/10.11613/BM.2012.031
6. Tran, V.-T., Porcher, R., Falissard, B., & Ravaud, P. (2016). Point of data saturation was assessed
   using resampling methods in a survey with open-ended questions. *Journal of Clinical Epidemiology*, 80,
   88–96. https://doi.org/10.1016/j.jclinepi.2016.07.014 and Guest, G., Namey, E., & Chen, M. (2020). A
   simple method to assess and report thematic saturation in qualitative research. *PLOS ONE*, 15(5),
   e0232076. https://doi.org/10.1371/journal.pone.0232076

Also cited:

- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological
  Measurement*, 20(1), 37–46. https://doi.org/10.1177/001316446002000104
- MacQueen, K. M., McLellan, E., Kay, K., & Milstein, B. (1998). Codebook development for team-based
  qualitative analysis. *CAM Journal*, 10(2), 31–36. https://doi.org/10.1177/1525822X980100020301
- Feinstein, A. R., & Cicchetti, D. V. (1990). High agreement but low kappa: I. The problems of two
  paradoxes. *Journal of Clinical Epidemiology*, 43(6), 543–549; Cicchetti & Feinstein (1990), II.
  Resolving the paradoxes, same issue, 551–558.
- Saldaña, J. (2021). *The Coding Manual for Qualitative Researchers* (4th ed.). Sage.
- AAPOR (2022). *Best Practices for Survey Research*.
  https://aapor.org/wp-content/uploads/2022/11/AAPOR-Standards-best-practices_March-2022.pdf
- Byrt, T., Bishop, J., & Carlin, J. B. (1993). Bias, prevalence and kappa. *Journal of Clinical
  Epidemiology*, 46(5), 423–429. https://doi.org/10.1016/0895-4356(93)90018-V
- Hayes, A. F., & Krippendorff, K. (2007). Answering the call for a standard reliability measure for
  coding data. *Communication Methods and Measures*, 1(1), 77–89.
  https://doi.org/10.1080/19312450709336664
- Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference. *Journal of
  the American Statistical Association*, 22(158), 209–212; formula and worked example as printed in the
  NIST/SEMATECH e-Handbook of Statistical Methods, section 7.2.4.1:
  https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm
- Efron, B., & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall.
- Manning, C. D., Raghavan, P., & Schütze, H. (2008). *Introduction to Information Retrieval*, ch. 8.
  Cambridge University Press. https://nlp.stanford.edu/IR-book/
- Dunivin, Z. O. (2024). Scalable qualitative coding with LLMs: chain-of-thought reasoning matches human
  performance in some hermeneutic tasks. arXiv:2401.15170. https://arxiv.org/abs/2401.15170
- Xiao, Z., Yuan, X., Liao, Q. V., Abdelghani, R., & Oudeyer, P.-Y. (2023). Supporting qualitative
  analysis with large language models: combining codebook with GPT-3 for deductive coding. *IUI '23
  Companion*. arXiv:2304.10548. https://arxiv.org/abs/2304.10548
- Wikipedia, "Cohen's kappa" (worked examples): https://en.wikipedia.org/wiki/Cohen%27s_kappa
- Quantum User Guide, "Suppressing percentages and statistics with small bases":
  https://support.unicomsi.com/manuals/quantum/6/User%20Guide/CreatingTables.26.21.html

## Pitfalls

- Reporting a percentage without saying of whom: all invited, all who started, all who answered this
  question, or all codable answers give different numbers.
- Adding up multi-code shares and presenting the total as if it were 100% of respondents.
- Percentages on a base of a dozen answers, most often in a segment cut.
- One kappa computed on joined code strings ("PRICE;SPEED" versus "PRICE"): it punishes partial
  agreement as total disagreement. Compute per code on present/absent.
- Dividing by zero, or printing 0 or 1, when a code was never used: kappa is undefined there.
- A rare code with 95% agreement and kappa near zero read as "coders agree".
- Reporting only the mean kappa, which hides the one code nobody can apply.
- Checking a language model only against itself and calling it inter-coder reliability.
- Changing the codebook after the agreement test without recoding everything and re-testing.
- A large `OTHER` that nobody re-read; it usually holds one or two real themes.
- Reporting a kappa from 30 answers without its interval, or quoting the band when the interval spans
  three bands.
- Presenting chi-square, a correlation or Cronbach's alpha as "inter-rater reliability".
- Adding up the codes of a net and calling the sum "respondents who mentioned the net".
- Two runs of the same language model reported as double coding.
- Paraphrased or stitched "quotes". A quote must be word for word and carry its row id.
- Calling the result "Braun and Clarke thematic analysis" while reporting kappa.
