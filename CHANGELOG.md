# Changelog

The pack and each skill use [semver](https://semver.org). A skill's version is in `catalog.json` and in its
`SKILL.md` `metadata.version`.

## 0.2.0 (2026-11-19): ten new skills, every skill reviewed

Ten new skills:

- **Survey design:** `screener-writer`
- **Pricing research:** `gabor-granger-analysis`, `conjoint-design`, `conjoint-analysis`
- **Feedback analysis:** `csat-ces-analysis`, `likert-analysis`, `survey-crosstabs`, `survey-weighting`,
  `kano-analysis`, `ux-scale-scoring`

All 22 skills were reviewed independently by three models, each finding was reproduced against the code, and
every confirmed fix has a regression test. 1,183 script tests pass on Python 3.9 and 3.12. Changes to the
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
