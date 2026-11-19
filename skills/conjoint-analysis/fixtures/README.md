# Fixtures for conjoint-analysis

Synthetic data and one published example. Regenerate with `python3 fixtures/generate_fixtures.py` (seeded).

## `candy_stacked.csv` + `candy_spec.txt`: published SAS example

"Choice of Chocolate Candies" (Kuhfeld 2010; SAS sample "Discrete Choice 1"): ten subjects each choose one of
the eight candies of the 2³ factorial Chocolate (Milk, Dark) × Center (Chewy, Soft) × Nuts (No Nuts, Nuts).
Profiles numbered in SAS order (Dark, Soft, Nuts counted in binary, 1 = Milk Chewy No Nuts ... 8 = Dark Soft
Nuts); chosen profiles 5 6 7 5 2 6 2 6 6 6.

Hand derivation: with one set holding the full factorial, the logit factorizes by attribute, so each
coefficient is the log odds of choosing that level. Dark chosen 8 of 10 → ln 4 = **1.38629**; Soft 1 of 10 →
ln(1/9) = **−2.19722**; Nuts 7 of 10 (profiles 2, 4, 6, 8) → ln(7/3) = **0.84730**. Model SEs
1/√(10·0.8·0.2) = **0.79057**, 1/√(10·0.1·0.9) = **1.05409**, 1/√(10·0.7·0.3) = **0.69007**. These match
the estimates usually quoted from Kuhfeld's report (the report itself was not re-read; see
`../references/sources.md`). The spec puts Milk, Chewy and No Nuts first so the dummies are Dark, Soft and
Nuts as in the SAS output.

## `plan_design.csv`, `plan_spec.txt`, `plan_responses.csv`: design mode, simulated

The design is the file `conjoint-design` wrote (20 versions × 8 tasks × 3 concepts + none; see that skill's
fixtures). 400 respondents take versions in rotation and choose by a known logit with Gumbel errors:
GreenPlate +0.3 and HomeChef −0.2 vs FreshBox; 3 meals +0.5 and 4 meals +0.6 vs 2; every two weeks −0.4 vs
weekly; −0.05 per dollar; none −3.0. A quarter are segment `family`. Tests check recovery within 3 SE, WTP as
a ratio, shares summing to 100, the segment Wald test and that wide and long responses give the same fit. The design is a byte copy of
`conjoint-design/fixtures/plan_design.csv`; when that file is regenerated, copy it here and rerun this script.

## `one_attribute_stacked.csv`: AMCE identity

60 respondents × 4 pairs of colors drawn independently and uniformly (Blue, Red, Green). With one attribute
the OLS AMCE of each colour vs Blue equals the difference of the marginal means exactly.

## Chapman and Feit minivan check (not shipped)

```text
curl -O http://r-marketing.r-forge.r-project.org/data/rintro-chapter13conjoint.csv
printf 'seat: 6 | 7 | 8\ncargo: 2ft | 3ft\neng: gas | hyb | elec\nprice: 30 | 35 | 40\n' > cf_spec.txt
python3 scripts/conjoint_analysis.py rintro-chapter13conjoint.csv --attribute-cols seat,cargo,eng,price --spec cf_spec.txt --json
python3 scripts/conjoint_analysis.py rintro-chapter13conjoint.csv --attribute-cols seat,cargo,eng,price --spec cf_spec.txt --price-attr price --json
```

Run 2026-11-19: log-likelihood −2581.6024; seat 7 −0.535280 (model SE 0.062360), seat 8 −0.305840
(0.061129), cargo 3ft 0.477449 (0.050888), eng hyb −0.811282 (0.060130), eng elec −1.530762 (0.067456),
price 35 −0.913656 (0.060601), price 40 −1.725851 (0.069631). Linear price: −0.1733053 (0.0069398),
log-likelihood −2582.0551, WTP cargo 3ft 2.750601 thousand dollars. All match the book's printed `mlogit`
output (`references/sources.md`, worked example 2). `carpool` is a respondent covariate, so it is left out of
the attributes; it works as `--segment carpool`.
