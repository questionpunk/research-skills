# Fixtures for ux-scale-scoring

Synthetic inputs (no participant data) and one published worked example. Expected values were worked out
independently of the script: SUS by Sauro's equivalent form ((Σ odd answers − 5) + (25 − Σ even answers)) ×
2.5 rather than item by item, t critical values from a t table, and p-values by numerical integration of the
t density rather than the incomplete beta function the script uses.

## 1. `brooke_1996.input.csv`: Brooke's scored example

Brooke (1996) prints a filled-in SUS with these item contributions: 4, 1, 1, 4, 1, 2, 1, 1, 4, 3, total 22,
"SUS Score = 22 × 2.5 = 55". The ticked boxes are images, so the answer positions are inferred from the
contributions with Brooke's own rule (odd items: position − 1; even items: 5 − position):
**5, 4, 2, 1, 2, 3, 2, 4, 5, 2**. Check: odd sum 5+2+2+2+5 = 16 → 16 − 5 = 11; even sum 4+1+3+4+2 = 14 →
25 − 14 = 11; (11 + 11) × 2.5 = **55**. Curved grade: 55 lies in D (51.7-62.6); percentile by interpolation
15 + (55 − 51.7)/(62.7 − 51.7) × 20 = 21. Closest Bangor adjective mean: OK (50.9).

## 2. `two_designs.input.csv`: the same 12 participants rate designs A and B

| P | A | B | A − B |
|---|---|---|---|
| 01 | 75.0 | 52.5 | 22.5 |
| 02 | 100.0 | 75.0 | 25.0 |
| 03 | 80.0 | 60.0 | 20.0 |
| 04 | 50.0 | 45.0 | 5.0 |
| 05 | 82.5 | 67.5 | 15.0 |
| 06 | 90.0 | 75.0 | 15.0 |
| 07 | 67.5 | 47.5 | 20.0 |
| 08 | 70.0 | 52.5 | 17.5 |
| 09 | 95.0 | 75.0 | 20.0 |
| 10 | 40.0 | 25.0 | 15.0 |
| 11 | 80.0 | 70.0 | 10.0 |
| 12 | 85.0 | 67.5 | 17.5 |

Participant 04 answered 3 to every A item (straight-lined; scores 50).

- A: mean 915/12 = **76.25**, SD **17.50**, t₀.₉₇₅,₁₁ = 2.200985, margin 2.200985 × 17.5/√12 = 11.119 →
  **65.13 to 87.37**. Grade B (74.1-77.1); percentile 70 + (76.25 − 74.1)/3.1 × 10 = **76.9**.
- B: mean 712.5/12 = **59.375**, SD 15.3787 → 49.60 to 69.15. Grade D.
- Overall (24 scores, both designs pooled): mean 67.8125, SD 18.2720, t₀.₉₇₅,₂₃ = 2.068658 → 60.10 to 75.53.
  This interval treats the 24 rows as 24 people. Here they are 12 people rating both designs, so it is
  wrong for this study: with `--paired` the script prints the pooled mean with no interval and no target
  test (the participant-level average of the two designs has the same mean, 67.8125, but interval 57.49 to
  78.14 and p = 0.124 against 60, against 0.047 for the pooled rows).
- Independent groups (Welch): SE = √(17.5²/12 + 15.3787²/12) = 6.7253, t = 16.875/6.7253 = **2.5092**,
  df = **21.64**, two-sided p = **0.0201**.
- Paired (the right test for this design): differences mean 16.875, SD 5.4486, SE 1.5729, t = **10.73**,
  df 11, p = **3.6 × 10⁻⁷**, interval **13.41 to 20.34**. The paired test is far more sensitive here because
  each participant's general leniency cancels out.
- Overall vs 68, one-tailed "above", as the script computes it without `--paired` (rows treated as
  independent; it warns that the same participants appear in both designs): t = (67.8125 − 68)/(18.272/√24)
  = −0.0503, p = **0.520**.

## 3. `umux_lite.input.csv`: UMUX-Lite on 7 points

Pairs (capabilities, ease): (7,7), (6,6), (5,6), (6,7), (4,5), (7,6), (5,5), (6,6). Score =
((a − 1) + (b − 1)) × 100/12: 100, 83.33, 75, 91.67, 58.33, 91.67, 66.67, 83.33. Mean **81.25**, SD
13.9087, t₀.₉₇₅,₇ = 2.364624 → 69.62 to 92.88. SUS-equivalent 0.65 × 81.25 + 22.9 = **75.71**.

## 4. `tlx.input.csv`: raw NASA-TLX, two tasks

Raw TLX per participant = mean of the six 0-100 ratings, for example (55 + 10 + 40 + 30 + 60 + 35)/6 =
38.33. Task t1: 38.33, 54.17, 27.50, 42.50 → mean **40.625** (SD 11.021). Task t2: 19.17, 29.17, 16.67,
25.83 → mean **22.708** (SD 5.789). Lower is better.

## 5. Generated in the tests

- All-positive SUS answers scored as the standard version: odd and even item means correlate positively, so
  the script warns; scored with `--instrument sus-positive` they do not.
- Skipped items: excluded and counted by default; `--impute-midpoint` scores up to `--max-imputed` (default
  1) skipped items as 3 and prints the complete-case mean beside the result.
- A 7-point "SUS" is refused; encodings, delimiters and the Qualtrics header are read the same way as in the
  sibling skills.
