# Fixtures for survey-sample-size

`cases.json` holds one entry per case: the command-line arguments and the values the script must return.
No respondent data is involved; every input is a planning number.

Each expected value below comes from a published worked example (cited) or from hand arithmetic shown
here. The hand arithmetic uses the rounded textbook quantiles, so it can be redone on a calculator:

| Quantile | Value | Used for |
|---|---|---|
| z(0.975) | 1.96 | 95% confidence; alpha = 0.05 two-sided |
| z(0.95) | 1.645 | alpha = 0.05 one-sided |
| z(0.80) | 0.8416 | power 80% |
| z(0.90) | 1.2816 | power 90% |

The script uses the exact quantiles (1.959964, 1.644854, 0.841621, 1.281552). Only case R2 sits close enough
to a whole number for the two to round differently (it says so); the unrounded values are listed so a
reviewer can see the distance. Full citations and links are in [`../references/sources.md`](../references/sources.md).

## A. Proportion (margin of error)

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| A1 | 1.96² × 0.5 × 0.5 / 0.05² = 3.8416 × 0.25 / 0.0025 = 384.16 | 385 | Published: Israel 1992, "(1.96)²(.5)(.5)/(.05)² = 385" |
| A2 | 385 / (1 + (385 − 1)/2000) = 385 / 1.192 = 322.99. Unrounded n0: 384.16 / (1 + 383.16/2000) = 322.40 | 323 | Published: Israel 1992, finite population example (N = 2,000 farmers, n = 323) |
| A3 | 3.8416 × 0.25 / 0.03² = 0.9604 / 0.0009 = 1067.11 | 1068 | Hand |
| A4 | 1.96 × √(0.25 / 80) = 1.96 × 0.055902 = 0.10957 | 0.1096 | Hand |
| A5 | 1.96 × √(0.25 / 100) = 1.96 × 0.05 = 0.098 | 0.098 | Hand |
| A6 | 1.96 × √(0.25 / 400) = 1.96 × 0.025 = 0.049 | 0.049 | Hand |
| A7 | 384.16 × 1.5 = 576.24 | 577 | Hand (design effect multiplies n) |
| A8 | 1.96 × √(0.25 / 323) × √((2000 − 323)/(2000 − 1)) = 1.96 × 0.027821 × 0.915925 = 0.04994 | 0.0499 | Hand (the reverse of A2: 323 of 2,000 gives back ±5 points) |
| A9 | 1.96 × √(0.2 × 0.8 / 80) = 1.96 × 0.044721 = 0.08765 | 0.0877 | Hand |
| A10 | A1 and A4 together: 80 < 385 | not sufficient | Hand |

## B. Mean (margin of error)

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| B1 | (1.96 × 15 / 2)² = 14.7² = 216.09 | 217 | Published: Illowsky and Dean, *Introductory Statistics* (OpenStax), section 8.1, "Calculating the Sample Size n": SD 15 years, within 2 years, 95% → 217 students |
| B2 | 1.96 × 15 / √217 = 29.4 / 14.7309 = 1.9958 | 1.9958 | Hand (the reverse of B1) |

## C. Two proportions (n per group)

Default formula (Fleiss, Levin and Paik; pooled variance under the null hypothesis, separate variances under
the alternative, no continuity correction):

n = [z_α √(2 p̄ q̄) + z_β √(p1 q1 + p2 q2)]² / (p1 − p2)², with p̄ = (p1 + p2)/2 and q = 1 − p.

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| C1 | p̄ = 0.425. 1.96 × √(2 × 0.425 × 0.575) = 1.96 × 0.699107 = 1.370249. 0.8416 × √(0.35 × 0.65 + 0.5 × 0.5) = 0.8416 × 0.691014 = 0.581557. (1.951806)² / 0.15² = 3.809547 / 0.0225 = 169.31 | 170 | Published: CUHK Centre for Clinical Research and Biostatistics calculator page, example 1, "NFleiss = ... = 170" |
| C2 | p̄ = 0.45. 1.96 × √0.495 = 1.96 × 0.703562 = 1.378982. 0.8416 × √(0.25 + 0.24) = 0.8416 × 0.7 = 0.58912. (1.968102)² / 0.1² = 3.873426 / 0.01 = 387.34 | 388 | Published: same page, example 2 (0.50 vs 0.40 → 388 per group) |
| C3 | p̄ = 0.625. 1.96 × √0.46875 = 1.96 × 0.684653 = 1.341920. 1.2816 × √(0.25 + 0.1875) = 1.2816 × 0.661438 = 0.847699. (2.189619)² / 0.25² = 4.794431 / 0.0625 = 76.71 | 76.71 → 77 | Published: R `stats::power.prop.test(p1 = .50, p2 = .75, power = .90)`, documented result "n = 76.7" |
| C4 | Unpooled: (1.96 + 0.8416)² × (0.25 + 0.24) / 0.1² = 7.848963 × 0.49 / 0.01 = 384.60 | 385 | Hand |
| C5 | Continuity correction on C2's 387.34: 387.34/4 × [1 + √(1 + 4/(387.34 × 0.1))]² = 96.8357 × [1 + √1.103268]² = 96.8357 × 2.050366² = 96.8357 × 4.204002 = 407.10 | 408 | Hand |
| C6 | One-sided. p̄ = 0.6. 1.645 × √0.48 = 1.645 × 0.692820 = 1.139689. 0.8416 × √(0.25 + 0.21) = 0.8416 × 0.678233 = 0.570801. (1.710490)² / 0.2² = 2.925776 / 0.04 = 73.14 | 74 | Hand |
| C7 | The reverse of C2: with 388 per group and p1 = 0.50, the smallest detectable p2 is just under 0.60, because 0.60 needs 387.34. | difference 0.0999 | Hand (follows from C2; the test also checks that the returned p2 needs at most 388) |

## D. Two means (n per group)

n = 2 (z_α + z_β)² / d² + z_α² / 4, where d is the difference in standard deviations. The first term is
the normal approximation; the second is Guenther's correction for using a t test.

(1.96 + 0.8416)² = 2.8016² = 7.848963; 2 × 7.848963 = 15.697926; 1.96² / 4 = 0.9604.

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| D1 | 15.697926 / 0.5² = 62.79; + 0.9604 = 63.75 | 63 (normal), 64 | Hand. Cross-check: Cohen 1992, Table 2 lists 64 per group for d = .50 |
| D2 | 15.697926 / 0.8² = 24.53; + 0.9604 = 25.49 | 25 (normal), 26 | Hand. Cross-check: Cohen 1992, Table 2 lists 26 for d = .80 |
| D3 | 15.697926 / 0.2² = 392.45; + 0.9604 = 393.41 | 393 (normal), 394 | Hand. Cohen 1992 prints 393; exact noncentral-t software gives 394. |
| D4 | d = 5 / 20 = 0.25. 15.697926 / 0.0625 = 251.17; + 0.9604 = 252.13 | 253 | Hand |
| D5 | The reverse of D1: d = 2.8016 × √(2 / (64 − 0.9604)) = 2.8016 × 0.178118 = 0.4990 | 0.499 | Hand |

## E. Subgroups

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| E1 | Smallest share 0.15, minimum base 100: 100 / 0.15 = 666.67 | 667 | Hand |
| E2 | 200 / 0.25 = 800 | 800 | Hand. Same shape as Orme's "4 × 200 = 800" for four equal segments (ch. 7, p. 65) |

## F. Invitations

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| F1 | Yield 0.20 × 0.50 × 0.80 = 0.08. 385 / 0.08 = 4812.5 | 4813 | Hand |
| F2 | 100 / 0.10 = 1000 | 1000 | Hand |

## G. MaxDiff (rules of thumb)

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| G1 | Sets = 3K/k = 3 × 20 / 5 = 12. Each item shown 12 × 5 / 20 = 3 times (not sparse, so the exposure rule is reported, 500 / 3 = 166.67 → 167, but not binding). Floor 300 in total | 12 sets, n 300 | Hand, from Sawtooth's 3K/k rule and its 300-in-total guideline |
| G2 | 60 items, 5 per set, 12 sets: recommended sets 3 × 60 / 5 = 36; shown 12 × 5 / 60 = 1 time, so sparse. 500 / 1 = 500; 1000 / 1 = 1000. Floor 300 × 60/30 = 600 (raised for more than 30 items) | n 600 (exposures: 500 minimum, 1000 preferred) | Hand, from Sawtooth's "at least 500 times and preferably 1000 times" rule and its advice to double the floors at 60 items |
| G3 | G1 with 3 subgroups: floor max(300, 3 × 200) = 600 | 600 | Hand |

## H. Conjoint (rules of thumb)

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| H1 | 100 respondents × 10 tasks × 3 concepts / 3 brands = 1000 | 1000 representations | Published: Orme, ch. 7, p. 64 |
| H2 | c = 5. 500 × 5 / (12 × 3) = 69.44 → 70; 1000 × 5 / 36 = 138.89 → 139. Floor 300 | 70, 139, n 300 | Hand, from n·t·a/c ≥ 500 |
| H3 | Two-way: c = 5 × 4 = 20. 500 × 20 / 36 = 277.78 → 278. Floor 300 | 278, n 300 | Hand |
| H4 | c = 6. 500 × 6 / (8 × 2) = 187.5 → 188 per subgroup; × 4 = 752. Floor 4 × 200 = 800 | 752, n 800 | Hand |

## Second set: intervals for small counts, power, unequal groups, corrections, other calculators

Extra quantiles used below: z(0.99167) = 2.394 (alpha 0.05 two-sided split over 3 comparisons: 1 − 0.05/6);
z(0.95) = 1.645 (90% confidence); z(0.995) = 2.576 (99% confidence). Φ is the standard normal cumulative
probability, read from a table. `saturation_guest2020.csv` is the same data as case W1, as a file.

### I. Wilson interval for small counts

Wilson: centre = (p + z²/2n) / (1 + z²/n); half-width = z / (1 + z²/n) × √(p(1 − p)/n + z²/4n²). z² = 3.8416.

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| I1 | 3 of 20: p = 0.15. 1 + 3.8416/20 = 1.19208. Centre = (0.15 + 0.09604) / 1.19208 = 0.206396. Half = 1.96/1.19208 × √(0.1275/20 + 3.8416/1600) = 1.644185 × √0.008776 = 1.644185 × 0.093680 = 0.154027 | 0.0524 to 0.3604 | Hand |
| I2 | n = 5, p = 0.2 (1 expected response, so Wilson is used without `--x`): 1 + 3.8416/5 = 1.76832. Centre = (0.2 + 0.38416) / 1.76832 = 0.330347. Half = 1.96/1.76832 × √(0.16/5 + 3.8416/100) = 1.108397 × √0.070416 = 1.108397 × 0.265360 = 0.294124 | 0.0362 to 0.6245 | Hand |
| I3 | n = 80, p = 0.2: 16 expected responses, at least 10, so the symmetric margin of A9 stays | wald | Hand |

Test `test_zero_count_interval_starts_at_zero`: 0 of 20 gives 0 to z²/(n + z²) = 3.8416/23.8416 = 0.1611.

### J. Power for a given n

Proportions (pooled): power = Φ[(|p1 − p2| √n − z_α √(2 p̄ q̄)) / √(p1 q1 + p2 q2)]. Means: power = Φ[d √((n − z_α²/4)/2) − z_α].

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| J1 | (0.25 × √50 − 1.341920) / 0.661438 = (1.767767 − 1.341920) / 0.661438 = 0.6438. Φ(0.6438) = 0.740 | 0.740 | Published: R `power.prop.test(n = 50, p1 = .50, p2 = .75)`, documented "power = 0.740" |
| J2 | The reverse, at 90% power | p2 = 0.8026 | Published: R `power.prop.test(n = 50, p1 = .5, power = .90)`, documented "p2 = 0.8026" |
| J3 | (0.1 × √388 − 1.378982) / 0.7 = (1.969772 − 1.378982) / 0.7 = 0.8440. Φ(0.8440) = 0.8007 | 0.801, sufficient | Hand (388 is the n of C2, so power is just over 80%) |
| J4 | 0.5 × √((64 − 0.9604)/2) − 1.96 = 0.5 × 5.614250 − 1.96 = 0.8471. Φ(0.8471) = 0.8015 | 0.80 (2 places) | Hand (64 is the n of D1) |
| J5 | Undo the continuity correction: n = (n′ − 1/δ)² / n′ = (408 − 10)² / 408 = 388.245. Then (0.1 × √388.245 − 1.378982) / 0.7 = 0.8449. Φ(0.8449) = 0.8009 | 0.801 | Hand (408 is the n of C5) |

### K. Unequal groups (r = n2 / n1)

Proportions: n1 = [z_α √((1 + 1/r) p̄ q̄) + z_β √(p1 q1 + p2 q2 / r)]² / (p1 − p2)², p̄ = (p1 + r p2)/(1 + r), n2 = r n1.
Means: n1 = (1 + 1/r)(z_α + z_β)² / d² + z_α² / (2(1 + r)). Power with h or d: Φ[effect × √(n1 n2/(n1 + n2)) − z_α].

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| K1 | r = 2. p̄ = (0.35 + 2 × 0.50)/3 = 0.45. 1.96 × √(1.5 × 0.45 × 0.55) = 1.96 × 0.609303 = 1.194234. 0.8416 × √(0.2275 + 0.25/2) = 0.8416 × 0.593717 = 0.499672. (1.693906)² / 0.0225 = 2.869318 / 0.0225 = 127.53. n2 = 2 × 127.53 = 255.05 | 128 and 256 (384) | Hand. Equal groups need 170 + 170 = 340 (C1) |
| K2 | 0.2 × √(543 × 675 / 1218) − 1.96 = 0.2 × 17.3472 − 1.96 = 1.5094. Φ(1.5094) = 0.934 | 0.934 | Published: pwr vignette, `pwr.2p2n.test(h = 0.2, n1 = 543, n2 = 675)`, power = 0.9344102 |
| K3 | r = 1.25. n1 − z_α²/(2 × 2.25) = 28 − 0.8537 = 27.1463. 0.5 × √(27.1463 / 1.8) − 1.96 = 0.5 × 3.883464 − 1.96 = −0.0183. Φ(−0.0183) = 0.4927 | 0.49 (2 places) | Published cross-check: pwr vignette, `pwr.t2n.test(n1 = 28, n2 = 35, d = 0.5)`, power = 0.4924588 (exact noncentral t; ours is an approximation) |
| K4 | r = 2. 1.5 × 7.848963 / 0.25 = 47.09; + 3.8416/6 = 0.64 → 47.73. n2 = 95.47 | 48 and 96 | Hand |

### L. Relative lift

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| L1 | p2 = 0.20 × 1.25 = 0.25, then as R1 | 1094 | Hand |
| L2 | p2 = 0.50 × 0.8 = 0.40, then as C2 | 388 | Hand |

### M. Several comparisons (Bonferroni)

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| M1 | alpha/3 = 0.016667, z = 2.394. 2.394 × 0.703562 = 1.684327; + 0.58912 = 2.273447. (2.273447)² / 0.01 = 516.86 | 517 | Hand (388 for one comparison, C2) |
| M2 | (2.394 + 0.8416)² = 3.2356² = 10.469107. 2 × 10.469107 / 0.25 = 83.75; + 2.394²/4 = 1.43 → 85.19 | 86 | Hand (64 for one comparison, D1) |

### N. Other formulas: arcsine (Cohen's h) and baseline variance

Arcsine: h = |2 asin √p1 − 2 asin √p2|, n = 2 (z_α + z_β)² / h² = 15.697926 / h².
Baseline: n = [z_α √(2 p1 q1) + z_β √(p1 q1 + p2 q2)]² / (p1 − p2)².

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| N1 | h = 2 × (0.321751 − 0.225513) = 0.192476. 15.697926 / 0.037047 = 423.7 | 423.7 → 424 | Published: pwr vignette, `pwr.2p.test(h = ES.h(p1 = 0.10, p2 = 0.05), sig.level = 0.05, power = .80)`, n = 423.7319 |
| N2 | h = 0.100167. 15.697926 / 0.010033 = 1564.5 | 1564.5 → 1565 | Published: pwr vignette, same call with p1 = 0.55, p2 = 0.50, n = 1564.529 |
| N3 | 1.96 × √(2 × 0.2 × 0.8) = 1.96 × 0.565685 = 1.108743. 0.8416 × √(0.16 + 0.1875) = 0.8416 × 0.589491 = 0.496116. (1.604859)² / 0.0025 = 2.575572 / 0.0025 = 1030.2 | 1030.2 → 1031 | Hand, from the formula in Evan Miller's calculator source; his page rounds to the nearest whole number (1,030) |
| N4 | 1.96 × √0.5 = 1.385929; + 0.58912 = 1.975049. (1.975049)² / 0.01 = 390.1 | 390.1 → 391 | Hand, same formula (his page: 390) |
| N5 | 1.96 × √(2 × 0.7 × 0.3) = 1.96 × 0.648074 = 1.270225. 0.8416 × √(0.21 + 0.2475) = 0.8416 × 0.676387 = 0.569247. (1.839472)² / 0.0225 = 3.383657 / 0.0225 = 150.4 | 150.4 → 151 | Hand, same formula (his page: 150) |
| N6 | 15.697926 / 0.2² = 392.45 | 393 | Hand |

### R. Reconciliation with other calculators (see sources.md)

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| R1 | p̄ = 0.225. 1.96 × √(2 × 0.225 × 0.775) = 1.96 × 0.590551 = 1.157480; + 0.496116 = 1.653596. (1.653596)² / 0.0025 = 1093.75 | 1094 | Hand |
| R2 | (1.96 + 0.8416)² × (0.16 + 0.1875) / 0.0025 = 7.848963 × 0.3475 / 0.0025 = 1091.01 with these rounded quantiles; 1090.99 with exact ones (7.848879 × 139). **The one case where the two differ across a whole number.** | 1091 | Hand; the script's exact quantiles give 1091 |
| R3 | h = 2 × (0.523599 − 0.463648) = 0.119902. 15.697926 / 0.014376 = 1091.9 | 1092 | Hand |
| R4 | h = 2 × (0.886077 − 0.785398) = 0.201358. 15.697926 / 0.040545 = 387.2 | 388 | Hand |
| R5 | p̄ = 0.625. 1.341920 (as C3) + 0.569247 (as N5) = 1.911167. (1.911167)² / 0.0225 = 162.34 | 163 | Hand |
| R6 | 162.34/4 × [1 + √(1 + 4/(162.34 × 0.15))]² = 40.585 × [1 + 1.079011]² = 40.585 × 4.322287 = 175.42 | 176 | Hand |
| R7 | h = 2 × (0.991157 − 0.835482) = 0.311350. 15.697926 / 0.096939 = 161.9 | 162 | Hand |
| R8 | 90%: 1.645² × 0.25 / 0.0025 = 270.6 | 271 | Hand. A calculator using z = 1.65 gets 272.25 → 273 |
| R9 | 99%: 2.576² × 0.25 / 0.0025 = 663.6 | 664 | Hand. A calculator using z = 2.58 gets 665.64 → 666 |

### O. Quota table

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| O1 | Base for ±10 points: 3.8416 × 0.25 / 0.01 = 96.04 → 97. Required totals: 97/0.50 = 194; 97/0.35 = 277.1 → 278; 97/0.15 = 646.7 → 647. Total 647. Expected n: 323.5, 226.45, 97.05. Margins: 0.98/√323.5 = 0.0545; 0.98/√226.45 = 0.0651; 0.98/√97.05 = 0.0995 | total 647; rows checked in `test_quota_table_has_a_row_per_named_subgroup` | Hand |

### Q. What a given n supports

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| Q1 | Overall: A4, 0.1096. Smallest subgroup 0.2 × 80 = 16; 16 × 0.5 = 8 expected, under 10, so Wilson: 1 + 3.8416/16 = 1.2401; centre 0.5; half = 1.96/1.2401 × √(0.25/16 + 3.8416/1024) = 1.580518 × 0.139200 = 0.2200 → 0.28 to 0.72. Two halves of 40: d = 2.8016 × √(2/(40 − 0.9604)) = 2.8016 × 0.226340 = 0.6341. Percentages: 0.50 vs 0.80 needs (1.96 × √0.455 + 0.8416 × √0.41)² / 0.09 = (1.322092 + 0.538887)² / 0.09 = 38.5 ≤ 40; 0.50 vs 0.79 needs (1.96 × √0.45795 + 0.8416 × √0.4159)² / 0.0841 = (1.326371 + 0.542750)² / 0.0841 = 41.5 > 40, so the detectable p2 lies between 0.79 and 0.80 | 0.1096; 0.28–0.72; d 0.634; p2 in (0.79, 0.80) | Hand |

### S. Gap between two answers in one sample

e = 1.96 × √((p1 + p2 − (p1 − p2)²) / (n − 1)).

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| S1 | 1.96 × √((0.56 − 0.0016)/440) = 1.96 × 0.035624 = 0.0698. n for a 4-point gap to exceed its margin: 3.8416 × 0.5584 / 0.0016 + 1 = 1341.7 | 0.0698; 1342 | Published: Franklin 2007, Time poll example (n = 441, 30% vs 26%, MOE .0698); the 1342 by hand |
| S2 | 1.96 × √((0.56 − 0.0036)/734) = 1.96 × 0.027533 = 0.0540 | 0.054, exceeds | Published: Franklin 2007, PPP example (n = 735, 31% vs 25%, MOE .054) |

### T. Design effect helpers

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| T1 | deff = 1 + (20 − 1) × 0.05 = 1.95. 384.16 × 1.95 = 749.1 | 750 | Hand |
| T2 | deff = 1 + 0.5² = 1.25. 384.16 × 1.25 = 480.2 | 481 | Hand |

### U. Invitations with responses removed in cleaning

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| U1 | Completes to collect: 385 / 0.9 = 427.8 → 428. Yield 0.9 × 0.2 = 0.18. 385 / 0.18 = 2138.9 | 428; 2139 | Hand |

### V. Interview planning ranges (guidance)

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| V1 | 3 × 9 = 27, 3 × 17 = 51 | 27 to 51 | Hennink and Kaiser 2022 range (9–17) × segments |
| V2 | 2 × 4 = 8, 2 × 8 = 16 | 8 to 16 | Hennink and Kaiser 2022 range (4–8 focus groups) × segments |
| V3 | 16 to 24, one segment | 16 to 24 | Hennink, Kaiser and Marconi 2017 |

### W. Saturation (Guest, Namey and Chen 2020)

| Case | Arithmetic | Expected | Origin |
|---|---|---|---|
| W1 | Base (interviews 1–4): 20 + 10 + 5 + 2 = 37 codes. Run 5–6: 4 + 3 = 7, 7/37 = 19%. Run 6–7: 3 + 1 = 4, 4/37 = 11%. Run 7–8: 1 + 0 = 1, 1/37 = 2.7% ≤ 5% | saturation at interview 6, reported "6+2" | Published: the paper's worked example (base 37; 7 new = 19%; 4 new = 11%; then one new theme; "saturation was reached at interview 6", "6+2"). The split of the 37 across interviews 1–4 is ours; the paper gives only the sum |
| W2 | Same start, then 1, 1, 1 with a 0% threshold: runs 7–8 and 8–9 each add 2/37 = 5.4% > 0 | not reached | Hand |
| W3 | Run length 3: 5–7: 8/37 = 21.6%; 6–8: 4/37 = 10.8%; 7–9: 1/37 = 2.7% | "6+3" | Hand |
