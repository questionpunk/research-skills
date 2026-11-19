# Changelog

The pack and each skill use [semver](https://semver.org). A skill's version is in `catalog.json` and in its
`SKILL.md` `metadata.version`.

## 0.2.1 (2026-11-19): third review completed, Van Westendorp checked against R

The third (Gemini) review of `survey-bias-check`, `survey-sample-size`, `ux-scale-scoring` and
`survey-crosstabs` had failed or stopped early in 0.2.0; it was rerun, each finding was reproduced, and every
confirmed script fix has a regression test.

- `van-westendorp-analysis` 0.2.1: `--compat r` checked against R `pricesensitivitymeter` 1.3.3. Its price
  points, trial curve and maxima match R in 66 runs (`fixtures/r_psm_1_3_3.expected.json`). One rule differed
  and now follows R: when curves coincide up to the highest price, `--tie max` and `--tie mean` report the
  run's first price. R's revenue price is the script's "highest among the observed prices only" line.
- `ux-scale-scoring` 0.1.1: a 7-point SUS (labels or a few 6s and 7s) and reversed agree labels now stop
  instead of being scored; SUS columns must be numbered exactly 1 to 10; `--reverse-performance` checks the
  column order; negated SEQ anchors ("Not at all easy") no longer trip the reversed-SEQ stop, and
  `--seq-reversed` is refused on text labels; `--target` with groups tests the groups, not the pooled line
  or blank rows; `--drop-flagged` reports and counts correctly; constant item means give no correlation;
  "NaN", "0_5", decimal TLX sliders and trailing empty Excel columns are handled.
- `survey-sample-size` 0.2.1: no crash on `compare --table` near 0% or 100% or on tiny inputs; a one-sided
  alpha of 0.5 or more is refused; a plan that reaches the population is a census; continuity-corrected
  power no longer jumps; `nps --diff` refuses `--population` and reports its z values; `subgroups` raises
  the base by the design effect; power checks state the power; `check` reports the detectable difference
  that holds in either direction; `gap` is limited to single-select questions and says its n is a 50%-power
  boundary. Docs: NPS comparisons use `nps --diff`, opt-in wording, more examples.
- `survey-crosstabs` 0.1.1: equal weights other than 1 no longer scale the chi-square; anonymity notes no
  longer split hidden cells into small and complementary counts; withheld tables carry no counts or group
  list in `--json`; groups with no answers stay listed under anonymity; repeated `--hide` flags add up;
  "0,750" reads as a decimal; Cramér's V is reported; pipes in labels are escaped.
- `survey-bias-check` 0.2.1: numbered verbal scales ("1 - Very dissatisfied") are checked as rating scales;
  one product name with a digit no longer turns a list ordinal; "Very / Somewhat / Not very / Not at all
  likely" is balanced, and a one-sided scale around a neutral midpoint is flagged. Docs: severity column in
  the output, phone-mode length line, no "behaviour before attitude" rule.
- `survey-from-decision` 0.2.1: SKILL.md under 300 lines; names the pack's screener, pricing and crosstab skills.
- `kano-analysis` and `gabor-granger-analysis` 0.1.1: the in-app question types are named as they appear
  in the add-question menu ("Feature Priorities (Kano)", "Price Ladder").

## 0.2.0 (2026-11-19): ten new skills, every skill reviewed

Ten new skills:

- **Survey design:** `screener-writer`
- **Pricing research:** `gabor-granger-analysis`, `conjoint-design`, `conjoint-analysis`
- **Feedback analysis:** `csat-ces-analysis`, `likert-analysis`, `survey-crosstabs`, `survey-weighting`,
  `kano-analysis`, `ux-scale-scoring`

All 22 skills were reviewed independently by three models, each finding was reproduced against the code, and
every confirmed fix has a regression test. 1,197 script tests pass on Python 3.9 and 3.12. Changes to the
first twelve (each now 0.2.0):

- Wrong answers that used to exit 0 now stop or are fixed: labelled scores (`10 - Extremely likely`), semicolon
  and UTF-16 exports, Qualtrics header rows, duplicate headers, thousands separators, scales guessed from the
  answers people happened to give.
- `survey-sample-size`: design effect and finite population correction applied in the right order (a population
  of 500 with design effect 2 now needs 304, not 435); new `nps` mode.
- `nps-analysis`: exact handling of a +100 or -100 benchmark, no verdicts under 5 responses, repeated-respondent
  checks, full-precision p-values.
- `van-westendorp-analysis`: the Newton-Miller-Smith curves no longer interpolate across tied prices;
  `--intent-scale` is now required for NMS.
- `maxdiff-analysis` and `maxdiff-design`: column order no longer changes the result; one sample-size rule
  shared with `survey-sample-size`.
- `open-ended-coding`: `validate --source` checks every source row was coded once with the same text.
- `survey-data-cleaning`: shared IPs, identical rows and open-text hits are candidates until confirmed;
  Qualtrics synthetic responses are set aside; `--preview` shows who a rule would remove.
- `qsf-convert`: NPS can drive logic, duplicate recode values are refused, the codebook covers every cell.
- `survey-bias-check` and `survey-from-decision` agree on ranges, scale length and the length estimate.
- Every "Field it" section names only tools a hosted MCP connection can call, with no plan or pricing claims.

## 0.1.0 (2026-11-18): first public release

Twelve skills:

- **Survey design:** `survey-from-decision`, `survey-bias-check`, `survey-sample-size`, `qsf-convert`
- **Pricing research:** `van-westendorp-analysis`, `maxdiff-design`, `maxdiff-analysis`
- **Feedback analysis:** `nps-analysis`, `pmf-survey`, `open-ended-coding`, `survey-data-cleaning`
- **Interviews:** `ai-interview-guide`

The ten skills that compute something ship a Python script with 528 tests in total.
