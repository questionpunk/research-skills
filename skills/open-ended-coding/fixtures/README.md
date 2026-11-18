# Fixtures for open-ended-coding

All data here is synthetic or copied from a published worked example. No respondent data. Every expected
value below was worked out by hand or read from the cited publication, not taken from the script; the
tests in `tests/test_open_ended_coding.py` compare the script with these numbers.

Notation for a two-coder table on one code: a = both coders used it, b = only coder A, c = only coder B,
d = neither, N = a + b + c + d.

- p_o = (a + d) / N
- p_e = (a + b)/N · (a + c)/N + (c + d)/N · (b + d)/N
- kappa = (p_o − p_e) / (1 − p_e)
- alpha (binary, two coders) = 1 − (2N − 1) · (b + c) / (n_1 · n_0), with n_1 = 2a + b + c values "present"
  and n_0 = 2d + b + c values "absent" (Krippendorff 2011, section A)
- positive agreement = 2a / (2a + b + c)

## 1. Kappa: published example, grant proposals

`kappa_grants_a.csv`, `kappa_grants_b.csv`. Source: Wikipedia, "Cohen's kappa", section "Simple example"
(https://en.wikipedia.org/wiki/Cohen%27s_kappa). Two readers, 50 proposals: 20 yes/yes, 5 yes/no,
10 no/yes, 15 no/no.

- p_o = (20 + 15) / 50 = 0.70
- reader A says yes 25/50 = 0.5, reader B 30/50 = 0.6; p_e = 0.5·0.6 + 0.5·0.4 = 0.50
- kappa = (0.70 − 0.50) / (1 − 0.50) = **0.40** (published value 0.40)
- alpha, by hand: n_1 = 55, n_0 = 45, b + c = 15: 1 − 99·15 / (55·45) = 1 − 1485/2475 = **0.400**

The same article gives two tables with equal agreement and different kappa, tested without a file:
(a, b, c, d) = (45, 15, 25, 15): p_o = 0.60, p_e = 0.6·0.7 + 0.4·0.3 = 0.54, kappa = 0.06/0.46 =
**0.1304**; (25, 35, 5, 35): p_o = 0.60, p_e = 0.6·0.3 + 0.4·0.7 = 0.46, kappa = 0.14/0.54 = **0.2593**.

## 2. Alpha: Krippendorff's worked examples

Source: Krippendorff, K. (2011), *Computing Krippendorff's Alpha-Reliability*, sections A, B and C
(https://repository.upenn.edu/asc_papers/43).

**A. Binary, two observers** (`krippendorff_a_meg.csv`, `krippendorff_a_owen.csv`; 0 is written `ZERO`,
1 is `ONE`).

| Item | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Meg | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| Owen | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |

- Published: alpha = 1 − (20 − 1) · 4 / (14 · 6) = **0.095**
- Kappa by hand: the observers agree on items 2, 4, 5, 7, 8, 10, so p_o = 6/10 = 0.60. Meg says 1 on
  2/10, Owen on 4/10: p_e = 0.2·0.4 + 0.8·0.6 = 0.56. kappa = 0.04 / 0.44 = **0.0909**
- For the code `ONE`: a = 1 (item 2), b = 1 (item 9), c = 3 (items 1, 3, 6), d = 5

**B. Nominal, two observers** (`krippendorff_b_ben.csv`, `krippendorff_b_gerry.csv`).

| Item | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Ben | a | a | b | b | d | c | c | c | e | d | d | a |
| Gerry | b | a | b | b | b | c | c | c | e | d | d | d |

- Published: alpha = **0.692**
- Kappa by hand: agreement on items 2, 3, 4, 6, 7, 8, 9, 10, 11, so p_o = 9/12 = 0.75. Ben uses
  a, b, c, d, e 3, 2, 3, 3, 1 times; Gerry 1, 4, 3, 3, 1 times.
  p_e = (3·1 + 2·4 + 3·3 + 3·3 + 1·1) / 144 = 30/144 = 0.2083.
  kappa = (0.75 − 0.2083) / (1 − 0.2083) = 0.5417 / 0.7917 = **0.6842**

**C. Nominal, four observers, missing data** (in the test file, no CSV: the command line compares two
coders, the function takes any number).

| Unit | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 1 | 2 | 3 | 3 | 2 | 1 | 4 | 1 | 2 | . | . | . |
| B | 1 | 2 | 3 | 3 | 2 | 2 | 4 | 1 | 2 | 5 | . | 3 |
| C | . | 3 | 3 | 3 | 2 | 3 | 4 | 2 | 2 | 5 | 1 | . |
| D | 1 | 2 | 3 | 3 | 2 | 4 | 4 | 1 | 2 | 5 | 1 | . |

- Published: alpha = **0.743**

## 3. Agreement: multi-code hand case, with the edge cases

`agree_a.csv`, `agree_b.csv`, 10 responses, compared with `codebook.csv` (which also defines `UX` and
`UNCODABLE`, used by neither coder here).

| id | Coder A | Coder B | Same set |
|---|---|---|---|
| 1 | PRICE | PRICE | yes |
| 2 | PRICE;SUPPORT | PRICE | no |
| 3 | SUPPORT | SUPPORT | yes |
| 4 | SPEED | SPEED | yes |
| 5 | PRICE | PRICE;SPEED | no |
| 6 | OTHER | SUPPORT | no |
| 7 | SUPPORT;SPEED | SUPPORT;SPEED | yes |
| 8 | PRICE | PRICE | yes |
| 9 | SPEED | OTHER | no |
| 10 | SUPPORT | SUPPORT | yes |

| Code | a | b | c | d | p_o | p_e | kappa | alpha | positive agreement |
|---|---|---|---|---|---|---|---|---|---|
| PRICE | 4 | 0 | 0 | 6 | 1.00 | 0.4·0.4 + 0.6·0.6 = 0.52 | 0.48/0.48 = **1.0000** | 1 − 19·0/(8·12) = **1.0000** | 8/8 = 1.0000 |
| SUPPORT | 3 | 1 (id 2) | 1 (id 6) | 5 | 0.80 | 0.4·0.4 + 0.6·0.6 = 0.52 | 0.28/0.48 = **0.5833** | 1 − 19·2/(8·12) = 1 − 38/96 = **0.6042** | 6/8 = 0.7500 |
| SPEED | 2 | 1 (id 9) | 1 (id 5) | 6 | 0.80 | 0.3·0.3 + 0.7·0.7 = 0.58 | 0.22/0.42 = **0.5238** | 1 − 19·2/(6·14) = 1 − 38/84 = **0.5476** | 4/6 = 0.6667 |
| OTHER | 0 | 1 (id 6) | 1 (id 9) | 8 | 0.80 | 0.1·0.1 + 0.9·0.9 = 0.82 | −0.02/0.18 = **−0.1111** | 1 − 19·2/(2·18) = 1 − 38/36 = **−0.0556** | 0/2 = 0.0000 |
| UX | 0 | 0 | 0 | 10 | 1.00 | 0·0 + 1·1 = 1.00 | **undefined** (0/0) | **undefined** | undefined (0/0) |

Edge cases this covers:

- `UX`: a code neither coder used. Expected agreement is 1, so kappa divides by zero. The script must say
  "undefined" and give the reason, not print 0, 1 or crash.
- `OTHER`: 80% agreement with a negative kappa (the kappa paradox on a rare code).

Overall:

- identical code set on ids 1, 3, 4, 7, 8, 10: **6 of 10** (60.0%)
- mean of the four defined kappas: (1 + 0.5833 + 0.5238 − 0.1111) / 4 = 1.9960 / 4 = **0.4990**;
  lowest **−0.1111** (`OTHER`)
- pooled over the codes at least one coder used (4 codes × 10 responses = 40 decisions):
  a = 4 + 3 + 2 + 0 = 9, b = 3, c = 3, d = 6 + 5 + 6 + 8 = 25. p_o = 34/40 = 0.85;
  both coders say "present" on 12/40 = 0.3, so p_e = 0.09 + 0.49 = 0.58; kappa = 0.27/0.42 = **0.6429**

Note how the pooled 0.64 looks fine while one code is below zero: the reason to report per code.

## 4. Counts: hand case

`coded.csv` (codes in one column, `;` between codes) and `coded_wide.csv` (the same coding as one 0/1
column per code, prefix `code_`). 20 respondents, `plan` is free for odd ids and paid for even ids.
Row 8 is blank with no code; with `--text-col answer` the script counts it as `NO_ANSWER`.

| Base | Rows | n |
|---|---|---|
| All respondents | 1–20 | 20 |
| No answer (blank) | 3, 8, 13 | 3 |
| Answered | the rest | 17 |
| Uncodable | 5 ("n/a"), 11 ("asdf") | 2 |
| Codable | | 15 |

| Code | Rows | n | % of all (n/20) | % of answered (n/17) |
|---|---|---|---|---|
| PRICE | 1, 4, 7, 12, 17, 19, 20 | 7 | 35.0 | 41.2 |
| SUPPORT | 2, 10, 16, 20 | 4 | 20.0 | 23.5 |
| SPEED | 4, 6, 15, 17 | 4 | 20.0 | 23.5 |
| UX | 9, 10, 18 | 3 | 15.0 | 17.6 |
| OTHER | 14 | 1 | 5.0 | 5.9 |
| UNCODABLE | 5, 11 | 2 | 10.0 | 11.8 |

- Code assignments on codable answers: 7 + 4 + 4 + 3 + 1 = 19 on 15 answers, mean 19/15 = 1.27.
- The five substantive shares of answered add up to 19/17 = 111.8%: over 100% because rows 4, 10, 17 and
  20 carry two codes.
- With the default `--min-base 30` every percentage is withheld (17 answered, 20 rows). The tests pass
  `--min-base 10` to check the percentages and the default to check that they are withheld.

Segment cut (`--segment-col plan`):

| | free (odd ids) | paid (even ids) |
|---|---|---|
| Rows | 10 | 10 |
| No answer | 2 (3, 13) | 1 (8) |
| Answered | 8 | 9 |
| Uncodable | 2 (5, 11) | 0 |
| PRICE | 4 (1, 7, 17, 19) = 50.0% | 3 (4, 12, 20) = 33.3% |
| SUPPORT | 0 | 4 (2, 10, 16, 20) = 44.4% |
| SPEED | 2 (15, 17) = 25.0% | 2 (4, 6) = 22.2% |
| UX | 1 (9) = 12.5% | 2 (10, 18) = 22.2% |
| OTHER | 0 | 1 (14) = 11.1% |

The segment test uses `--min-base 9`: paid (9 answered) keeps its percentages, free (8 answered) is
flagged as a small base and shows counts only.

## 5. Validation

- `codebook.csv`: four codes in the fixed format, plus `OTHER` and `UNCODABLE`.
- `coded_bad.csv`: one problem per row. Expected errors: row 1 unknown code `PRICING`; row 2 no code;
  row 3 blank answer coded `PRICE`; row 4 `NO_ANSWER` on a non-blank answer; row 5 `UNCODABLE` combined
  with `PRICE`; row 7 `price` (wrong case, the script suggests `PRICE`). Expected warnings: row 6 answer
  "none" coded `SPEED`; codes `SUPPORT` and `UX` unused.
- `quotes_ok.csv`: three quotes that are word for word in their rows and whose rows carry the code.
- `quotes_bad.csv`: a reworded quote (row 4), a quote on a row that does not carry the code (row 12), and
  a row id that does not exist (99).

## 6. Sampling

`sample` is checked on properties, since a random draw has no hand value: the same seed gives the same
ids, a different seed a different draw, blank answers (3, 8, 13) are never drawn unless
`--include-blank`, ids listed in `--exclude` are never drawn, the output keeps only the id and the answer,
and asking for more answers than are eligible is an error.

## 7. Reference coder: precision, recall, F1, negative agreement, PABAK

`gold_human.csv` (reference, coder A) and `gold_llm.csv` (compared coder B), 12 responses. Run with
`--gold gold_human.csv`. Extra formulas: precision = a / (a + c), recall = a / (a + b),
F1 = 2a / (2a + b + c), negative agreement = 2d / (2d + b + c), PABAK = 2·p_o − 1.

| id | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Reference | PRICE | PRICE | PRICE;SUPPORT | SUPPORT | SUPPORT | SPEED | SPEED | PRICE | OTHER | SUPPORT | UX | PRICE;SPEED |
| Compared | PRICE | PRICE;SPEED | PRICE | SUPPORT | SUPPORT;PRICE | SPEED | OTHER | PRICE | SPEED | SUPPORT | UX | PRICE |

| Code | a | b (reference only) | c (compared only) | d | precision | recall | F1 | p_o | p_e | kappa | negative agreement | PABAK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRICE | 5 | 0 | 1 (id 5) | 6 | 5/6 = **0.8333** | 5/5 = **1.0000** | 10/11 = **0.9091** | 11/12 | (5·6 + 7·6)/144 = 0.5000 | (0.9167 − 0.5)/0.5 = **0.8333** | 12/13 = **0.9231** | 22/12 − 1 = **0.8333** |
| SUPPORT | 3 | 1 (id 3) | 0 | 8 | 3/3 = **1.0000** | 3/4 = **0.7500** | 6/7 = **0.8571** | 11/12 | (4·3 + 8·9)/144 = 0.5833 | 0.3333/0.4167 = **0.8000** | 16/17 | 0.8333 |
| SPEED | 1 (id 6) | 2 (ids 7, 12) | 2 (ids 2, 9) | 7 | 1/3 = **0.3333** | 1/3 = **0.3333** | 2/6 = **0.3333** | 8/12 | (3·3 + 9·9)/144 = 0.6250 | 0.0417/0.375 = **0.1111** | 14/18 | 16/12 − 1 = **0.3333** |
| OTHER | 0 | 1 (id 9) | 1 (id 7) | 10 | 0/1 = **0.0000** | 0/1 = **0.0000** | 0/2 = **0.0000** | 10/12 | (1·1 + 11·11)/144 = 0.8472 | −2/22 = **−0.0909** | 20/22 = **0.9091** | 20/12 − 1 = **0.6667** |
| UX | 1 | 0 | 0 | 11 | **1.0000** | **1.0000** | **1.0000** | 1 | 122/144 | **1.0000** | 1 | 1 |

"High agreement, low kappa" flag (agreement ≥ 80% and kappa < 0.40): `OTHER` (83.3%, −0.09) is flagged;
`SPEED` (66.7%) is not, its agreement is simply low; `PRICE` is not.

## 8. More than two coders

**Krippendorff's example C as four files** (`krippendorff_c_a.csv` to `krippendorff_c_d.csv`, value v
written `V<v>`, a missing value = the row is absent, so `--allow-unmatched` is needed). Unit 12 has one
value and cannot be paired: 11 units. Published alpha **0.743** (section 2 above).

Pairwise categorical kappa by hand, on the units both observers valued:

- A and B share units 1–9 and differ on unit 6 only: p_o = 8/9. A uses 1, 2, 3, 4 on 3, 3, 2, 1 units;
  B on 2, 4, 2, 1. p_e = (3·2 + 3·4 + 2·2 + 1·1)/81 = 23/81. kappa = (72 − 23)/(81 − 23) = 49/58 =
  **0.8448**
- A and D share units 1–9 and differ on unit 6 only: p_o = 8/9. D uses 1, 2, 3, 4 on 2, 3, 2, 2 units.
  p_e = (3·2 + 3·3 + 2·2 + 1·2)/81 = 21/81. kappa = (72 − 21)/(81 − 21) = 51/60 = **0.8500**

**Three coders, several codes per response**: `agree_a.csv`, `agree_b.csv` (section 3) plus `agree_c.csv`,
which equals coder A except row 2 (`PRICE`) and row 6 (`SUPPORT`). For a binary code with m coders on a
unit, of whom k used it: alpha = 1 − (n − 1) · Σ k(m − k)/(m − 1) / (n_1 · n_0), with n_1 = Σ k,
n_0 = Σ (m − k), n = n_1 + n_0 (Krippendorff's coincidence matrix written out for two values). Here m = 3
on all 10 units, n = 30.

| Code | Units not unanimous (k of 3) | Σ k(m − k)/(m − 1) | n_1 | n_0 | alpha |
|---|---|---|---|---|---|
| PRICE | none | 0 | 12 | 18 | **1.0000** |
| SUPPORT | 2 (k = 1), 6 (k = 2) | 1 + 1 = 2 | 3·3 + 1 + 2 = 12 | 18 | 1 − 29·2/216 = **0.7315** |
| SPEED | 5 (k = 1), 9 (k = 2) | 2 | 3·2 + 1 + 2 = 9 | 21 | 1 − 29·2/189 = **0.6931** |
| OTHER | 6 (k = 1), 9 (k = 1) | 2 | 2 | 28 | 1 − 29·2/56 = **−0.0357** |

Lowest pairwise kappa for `SUPPORT` is the A–B pair, 0.5833 (section 3).

## 9. Bootstrap intervals

A bootstrap interval has no hand value. The tests check what must hold: the same seed gives identical
output; another seed gives different intervals; every point estimate lies inside its interval; a code
with perfect agreement in every resample has the interval 1.000 to 1.000; an interval that spans two
bands is flagged; the intervals around Krippendorff's examples contain the published values; `--bootstrap
0` turns intervals off. The percentile helper is checked by hand: the 2.5th percentile of 1, 2, 3, 4, 5
is at rank 0.1 between 1 and 2, so **1.1**; of the defined replicates 0.2, 0.4, 0.6 the 2.5th and 97.5th
percentiles are 0.2 + 0.05·0.2 = **0.21** and 0.4 + 0.95·0.2 = **0.59**.

## 10. Disagreements and merge

`--disagreements` on `agree_a.csv` and `agree_b.csv` must list ids 2, 5, 6, 9 (section 3) with the codes
in dispute `SUPPORT`, `SPEED`, `SUPPORT;OTHER`, `SPEED;OTHER` (codebook order, reserved codes last) and an
empty `final_codes`.

`adjudicated.csv` decides them: 2 → `PRICE`, 5 → `PRICE;SPEED`, 6 → `SUPPORT`, 9 → `SPEED`. Merged into
`agree_a.csv`: rows 2, 5 and 6 change, row 9 is confirmed as coder A had it. Counts on the merged file:
`PRICE` rows 1, 2, 5, 8 = 4; `SUPPORT` rows 3, 6, 7, 10 = 4; `SPEED` rows 4, 5, 7, 9 = 4; `OTHER` 0.

## 11. Counts extras

All on `coded_sentiment.csv` (= `coded.csv` plus a `sentiment` column) with `codebook_nets.csv`
(= `codebook.csv` plus `parent`: `PRICE` → `COST`; `SUPPORT`, `SPEED`, `UX` → `EXPERIENCE`).

**Nets.** `EXPERIENCE` = rows with `SUPPORT` (2, 10, 16, 20), `SPEED` (4, 6, 15, 17) or `UX` (9, 10, 18):
rows 2, 4, 6, 9, 10, 15, 16, 17, 18, 20 = **10** respondents (row 10 carries two of the codes, so the sum
of code counts is 11). 10/20 = 50.0% of all, 10/17 = 58.8% of answered. `COST` = 7. By plan: `EXPERIENCE`
paid rows 2, 4, 6, 10, 16, 18, 20 = 7, free rows 9, 15, 17 = 3.

**Share of mentions** (`--mentions`), 19 assignments: 7/19 = 36.8, 4/19 = 21.1, 4/19 = 21.1, 3/19 = 15.8,
1/19 = 5.3 (sum 100.1 after rounding).

**Wilson interval.** Published check (NIST/SEMATECH e-Handbook 7.2.4.1): p̂ = 0.13, N = 200, z = 1.645
gives a lower limit of **0.09577**. By hand for `PRICE`, 7 of 17, z = 1.96:

```
p = 0.411765   z² = 3.8416   z²/n = 0.225976   z²/2n = 0.112988
centre   = (0.411765 + 0.112988) / 1.225976 = 0.428029
radicand = 0.411765·0.588235/17 + 3.8416/1156 = 0.014248 + 0.003323 = 0.017571;  sqrt = 0.132556
half     = 1.96 · 0.132556 / 1.225976 = 0.211921
interval = 0.2161 to 0.6400  ->  21.6% to 64.0%
```

`SUPPORT`, 4 of 17, same steps: 9.6% to 47.3%. With no successes the formula reduces to 0 to
z²/(n + z²); for n = 20 that is 3.8416/23.8416 = 0.1611.

**Health check**, defaults (rare under 5, broad over 50%, `OTHER` over 10%): rare = `SUPPORT` (4),
`SPEED` (4), `UX` (3); nothing broad (`PRICE` is 7/17 = 41.2%); `OTHER` 1/17 = 5.9%, not flagged. Pairs:
`PRICE` + `SPEED` on rows 4 and 17 = 2; `PRICE` + `SUPPORT` on row 20 = 1; `SUPPORT` + `UX` on row 10 = 1.
With `--rare-below 4 --broad-above 40 --other-above 5`: rare = `UX` only, broad = `PRICE`, `OTHER` flagged.

**Sentiment.** The column holds a value on the 15 codable rows: negative on rows 1, 2, 4, 7, 9, 10, 12,
15, 17, 18, 20 = 11 (73.3%); mixed on 6, 16 = 2 (13.3%); neutral on 14, 19 = 2 (13.3%); positive 0.

## 12. Saturation log

`saturation.csv`, 9 rows, with `--base 4 --run 2` (the smallest base and run in Guest et al. 2020):

| Batch | Rows | Codes in the rows | New | Codes so far | New ÷ base codes |
|---|---|---|---|---|---|
| base | 1–4 | A;B / B;C / A / D | A, B, C, D | 4 | |
| run 1 | 5–6 | E / A | E | 5 | 1/4 = 25.0% |
| run 2 | 7–8 | A;B / C;OTHER | none (`OTHER` is not a code found in the data) | 5 | 0/4 = 0.0% |

Row 9 does not fill a run and is not evaluated. At the 5% threshold the rule is met in run 2, after 8
answers; at a 25% threshold in run 1.

## 13. Stratified sample and top-up

Proportional allocation by largest remainder, by hand: 17 eligible answers, free 8 and paid 9, n = 6.
6·8/17 = 2.82 and 6·9/17 = 3.18: whole parts 2 and 3, the one remaining place goes to the larger
remainder (free), so **3 and 3**. Second case: strata of 10, 30, 60 and n = 10 give 1, 3, 6 exactly.

The top-up is checked on properties: after `--top-up-min 2` every code is carried by at least 2 sampled
rows, or by all rows that carry it if there are fewer (`OTHER` has one); the output still holds only id
and answer.
