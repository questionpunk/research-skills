# Fixtures for pmf-survey

All inputs are synthetic (invented product "Acme", no real respondents). Every expected value below was
worked out by hand from the counts, before and independently of `scripts/pmf_survey.py`. Pairs are named
`<case>.input.csv` and `<case>.expected.json`.

## The formula used by hand

Wilson score interval, no continuity correction (Wilson 1927; formula as printed in the NIST handbook, see
`../references/sources.md`), with p = x/n and z = 1.96 for 95%:

```
centre = (p + z²/2n) / (1 + z²/n)
half   = z · sqrt( p(1−p)/n + z²/4n² ) / (1 + z²/n)
interval = centre − half  to  centre + half
```

z² = 3.8416. The script uses the unrounded z (1.959964), which changes the fourth decimal at most; expected
values are rounded to one decimal of a percentage point and the tests allow ±0.1.

### Check against a published worked example

NIST/SEMATECH e-Handbook, section 7.2.4.1, works a one-sided 95% lower limit for p̂ = 0.13, N = 200,
z = 1.645 and prints **0.09577**. That is the lower limit of the two-sided 90% Wilson interval for 26 of 200:

```
z²      = 2.706025        z²/n = 0.01353013      z²/2n = 0.00676506
centre  = (0.13 + 0.00676506) / 1.01353013 = 0.134939
radicand= 0.13·0.87/200 + 2.706025/160000 = 0.0005655 + 0.0000169127 = 0.0005824127
sqrt    = 0.0241332       half = 1.645 · 0.0241332 / 1.01353013 = 0.039169
lower   = 0.134939 − 0.039169 = 0.09577      (NIST: 0.09577)
```

`tests/test_pmf_survey.py` asserts this value (`test_wilson_matches_nist_worked_example`).

A second check needs no source: with x = 0 the formula reduces to 0 to z²/(n + z²). For n = 20 that is
3.8416 / 23.8416 = 0.1611 (`test_wilson_zero_successes_closed_form`).

## basic

`basic.input.csv`: 50 rows. 16 very, 14 somewhat, 10 not, 8 N/A, 2 blank. The header is the full question
text, so it also tests column auto-detection.

- Base = 16 + 14 + 10 = 40 (N/A and blank outside). Score = 16/40 = **40.0%**.
- z²/n = 3.8416/40 = 0.09604; 1 + z²/n = 1.09604; z²/2n = 0.04802.
- centre = (0.4 + 0.04802)/1.09604 = 0.44802/1.09604 = 0.408762.
- radicand = 0.4·0.6/40 + 3.8416/6400 = 0.006 + 0.00060025 = 0.00660025; sqrt = 0.081242.
- half = 1.96 · 0.081242 / 1.09604 = 0.145281.
- Interval = 0.263481 to 0.554043 → **26.3% to 55.4%**. It contains 40% → **cannot tell**.
- With N/A in the base: 16/48 = **33.3%**.
- Base 40 ≥ 30 → not a small base.

## segments

`segments.input.csv`: 75 rows, columns `persona`, `disappointment`, `main_benefit`.

| Persona | Very | Somewhat | Not | N/A | Base |
|---|---|---|---|---|---|
| Founder | 18 | 8 | 4 | 2 | 30 |
| Manager | 9 | 12 | 9 | 1 | 30 |
| Engineer | 3 | 5 | 4 | 0 | 12 |
| Total | 30 | 25 | 17 | 3 | 72 |

Overall: 30/72 = 41.67% → **41.7%**. z²/n = 0.053356; centre = (0.416667 + 0.026678)/1.053356 = 0.420888;
radicand = 0.416667·0.583333/72 + 3.8416/20736 = 0.00337577 + 0.00018526 = 0.00356103; sqrt = 0.059674;
half = 1.96·0.059674/1.053356 = 0.111037 → 0.309851 to 0.531925 → **31.0% to 53.2%**, cannot tell.
With N/A in the base: 30/75 = **40.0%**.

Founder: 18/30 = **60.0%**. z²/n = 0.128053; centre = (0.6 + 0.064027)/1.128053 = 0.588648;
radicand = 0.6·0.4/30 + 3.8416/3600 = 0.008 + 0.00106711 = 0.00906711; sqrt = 0.095221;
half = 1.96·0.095221/1.128053 = 0.165448 → 0.423200 to 0.754096 → **42.3% to 75.4%**. Lower limit above
40% → **above**.

Manager: 9/30 = **30.0%**. centre = (0.3 + 0.064027)/1.128053 = 0.322703; radicand = 0.3·0.7/30 +
0.00106711 = 0.00806711; sqrt = 0.089817; half = 1.96·0.089817/1.128053 = 0.156058 → 0.166645 to 0.478761 →
**16.7% to 47.9%**. Contains 40% → cannot tell.

Engineer: 3/12 = **25.0%**. z²/n = 0.320133; centre = (0.25 + 0.160067)/1.320133 = 0.310625;
radicand = 0.25·0.75/12 + 3.8416/576 = 0.015625 + 0.00666944 = 0.02229444; sqrt = 0.149313;
half = 1.96·0.149313/1.320133 = 0.221685 → 0.088940 to 0.532310 → **8.9% to 53.2%**, cannot tell,
base 12 < 30 → **small base**.

Share of all very-disappointed respondents: Founder 18/30 = 60.0%, Manager 9/30 = 30.0%, Engineer 3/30 = 10.0%.

Focus on Founder + Manager (`--focus-segments Founder,Manager`): 27/60 = **45.0%**. z²/n = 0.064027;
centre = (0.45 + 0.032013)/1.064027 = 0.453009; radicand = 0.45·0.55/60 + 3.8416/14400 = 0.004125 +
0.00026678 = 0.00439178; sqrt = 0.066270; half = 1.96·0.066270/1.064027 = 0.122074 → 0.330935 to 0.575083 →
**33.1% to 57.5%**, cannot tell.

Main benefit among the 30 very-disappointed respondents: speed 13 + 4 + 1 = 18, focus 3 + 4 + 1 = 8,
design 2 + 1 + 1 = 4. Core benefit = speed.

The 25 somewhat-disappointed respondents: speed 5 + 4 + 1 = **10 match**; focus 2 + 5 + 2 = 9 and
design 0 + 2 + 2 = 4, so **13 differ**; blank 1 + 1 = **2 unknown**.

## small_n

`small_n.input.csv`: 10 rows, 4 very, 4 somewhat, 2 not: the "4 of 10" case Sean Ellis mentions.

4/10 = **40.0%**. z²/n = 0.38416; centre = (0.4 + 0.19208)/1.38416 = 0.427754; radicand = 0.4·0.6/10 +
3.8416/400 = 0.024 + 0.009604 = 0.033604; sqrt = 0.183314; half = 1.96·0.183314/1.38416 = 0.259576 →
0.168178 to 0.687330 → **16.8% to 68.7%**, cannot tell, base 10 < 30 → small-base flag.

## labels

`labels.input.csv`: 13 rows with label variants the script maps without `--map`: mixed case, surrounding and
doubled spaces, the short forms "Very" and "somewhat", Ellis's full "Not disappointed (it isn't really that
useful)" with a curly apostrophe, "N/A – I no longer use Acme" with an en dash and with a hyphen, "n/a", and
"I no longer use it".

Counts: very 4, somewhat 3, not 2, N/A 4. Score 4/9 = 44.44% → **44.4%**. z²/n = 0.426844;
centre = (0.444444 + 0.213422)/1.426844 = 0.461064; radicand = 0.444444·0.555556/9 + 3.8416/324 =
0.02743484 + 0.01185679 = 0.03929163; sqrt = 0.198221; half = 1.96·0.198221/1.426844 = 0.272289 →
0.188775 to 0.733353 → **18.9% to 73.3%**. With N/A in the base: 4/13 = **30.8%**.

## coded

`coded.input.csv`: numeric codes 1 (×5), 2 (×3), 3 (×2), 4 (×1) in a column named `pmf_q1`.

- Without `--map`: exit code 2 and all four codes listed. The script must not guess what a number means.
- With `--map 1=very --map 2=somewhat --map 3=not --map 4=na`: 5/10 = **50.0%**. centre = 0.5 (symmetric);
  radicand = 0.25/10 + 0.009604 = 0.034604; sqrt = 0.186022; half = 1.96·0.186022/1.38416 = 0.263410 →
  **23.7% to 76.3%**.

## bad_labels

`bad_labels.input.csv`: contains "Extremely disappointed" (×2) and "Kind of" (×1), which belong to a
different scale. Expected: exit code 2, both labels named in the message, nothing scored.

## all_na

`all_na.input.csv`: 5 × N/A and 1 blank. Expected: exit code 2 with "No score", "5 N/A" and "1 blank" in the
message. There is no current-user base, so a percentage would be 0/0.

## benefit_match

`benefit_match.input.csv`: a `benefit_match` column of yes/no values (one written "No", one blank).
5 very, 6 somewhat, 2 not. Among the 6 somewhat: 3 yes, 2 no, 1 blank → matches 3, differs 2, unknown 1.

## Fixtures for wave comparison, several segment columns, accounts, wording and counts

### The formula for a change between two waves

Newcombe (1998) hybrid score interval for two independent proportions, in the form printed in the NCSS
"Two Proportions" documentation (see `../references/sources.md`). With (l1, u1) and (l2, u2) the Wilson limits
of the earlier and the later wave, and d = p2 − p1:

```
lower = d − z · sqrt( l2(1−l2)/n2 + u1(1−u1)/n1 )
upper = d + z · sqrt( u2(1−u2)/n2 + l1(1−l1)/n1 )
```

The script computes the same interval in its other published form, d − sqrt((p2−l2)² + (u1−p1)²) and
d + sqrt((u2−p2)² + (p1−l1)²). The two are equal because a Wilson limit l satisfies (p−l)² = z²·l(1−l)/n, so
the hand calculation below is an independent check of the code.

### Check against Newcombe's example

Newcombe's paper uses 56 of 70 against 48 of 80 (the same counts appear in the R DescTools `BinomDiffCI`
help). By hand, with 48/80 as the earlier and 56/70 as the later sample:

```
48/80: p = 0.6   Wilson 0.490453 to 0.700383        56/70: p = 0.8   Wilson 0.691831 to 0.876954
d = 0.2
lower: 0.691831·0.308169/70 + 0.700383·0.299617/80 = 0.00304572 + 0.00262308 = 0.00566880
       sqrt = 0.075291; ×1.96 = 0.147571;  0.2 − 0.147571 = 0.0524
upper: 0.876954·0.123046/70 + 0.490453·0.509547/80 = 0.00154151 + 0.00312386 = 0.00466537
       sqrt = 0.068304; ×1.96 = 0.133875;  0.2 + 0.133875 = 0.3339
```

0.0524 to 0.3339 is the interval remembered from Newcombe's Table II for his method 10; the table itself was
not opened. `test_newcombe_matches_hand_worked_example` asserts it.

## waves

`waves.input.csv`: 111 rows. Wave `2026-Q1`: 12 very, 22 somewhat, 18 not, 2 N/A (base 52). Wave `2026-Q2`:
18 very, 20 somewhat, 15 not, 1 N/A (base 53). Two rows (1 very, 1 somewhat) have no wave. This is the
"23% to 34% on about 52 answers each" case.

- Q1: 12/52 = 23.08% → **23.1%**. z²/n = 0.073877; centre = (0.230769 + 0.036938)/1.073877 = 0.249291;
  radicand = 0.230769·0.769231/52 + 3.8416/10816 = 0.00341375 + 0.00035518 = 0.00376892; sqrt = 0.061392;
  half = 1.96·0.061392/1.073877 = 0.112050 → 0.137241 to 0.361340 → **13.7% to 36.1%**.
- Q2: 18/53 = 33.96% → **34.0%**. z²/n = 0.072483; centre = (0.339623 + 0.036242)/1.072483 = 0.350462;
  radicand = 0.339623·0.660377/53 + 3.8416/11236 = 0.00423168 + 0.00034190 = 0.00457358; sqrt = 0.067628;
  half = 1.96·0.067628/1.072483 = 0.123593 → 0.226869 to 0.474055 → **22.7% to 47.4%**.
- Change d = 0.339623 − 0.230769 = 0.108853 → **+10.9 points**.
- lower: 0.226869·0.773131/53 + 0.361340·0.638660/52 = 0.00330942 + 0.00443795 = 0.00774737; sqrt = 0.088019;
  ×1.96 = 0.172518 → 0.108853 − 0.172518 = −0.063664 → **−6.4 points**.
- upper: 0.474055·0.525945/53 + 0.137241·0.862759/52 = 0.00470428 + 0.00227704 = 0.00698132; sqrt = 0.083554;
  ×1.96 = 0.163766 → 0.108853 + 0.163766 = 0.272620 → **+27.3 points**.
- The interval includes 0 → **cannot tell**. Cross-check with the pooled two-proportion z statistic: pooled
  p = 30/105 = 0.285714; se = sqrt(0.285714·0.714286·(1/52 + 1/53)) = 0.088177; z = 0.108853/0.088177 =
  1.23, under 1.96.
- Whole file: very 12 + 18 + 1 = 31, somewhat 22 + 20 + 1 = 43, not 33, N/A 3.

A change that is detected (used with `--counts` and `--previous-counts` in the tests): 20 of 100, then 45 of
100. Wilson limits 0.133366 to 0.288831 and 0.356144 to 0.547556; d = 0.25.
lower: 0.356144·0.643856/100 + 0.288831·0.711169/100 = 0.00229305 + 0.00205408; sqrt = 0.065933; ×1.96 =
0.129228 → 0.120772. upper: 0.547556·0.452444/100 + 0.133366·0.866634/100 = 0.00247738 + 0.00115579;
sqrt = 0.060276; ×1.96 = 0.118141 → 0.368141. **+12.1 to +36.8 points**, all above 0 → **increased**.

## benefit_case

`benefit_case.input.csv`: benefit codes that differ only in case or spacing ("Speed", "speed", "SPEED",
" speed "). They are one code. Very disappointed (7): Speed 3 + speed 2 = 5, Focus 2 → core benefit shown as
"Speed" (first spelling in the file). Somewhat (6): SPEED 2 + " speed " 1 = **3 match**; focus 2 + Design 1 =
**3 differ**. With `--core-benefit FOCUS`: 2 match, 4 differ.

## multi_segment

`multi_segment.input.csv`: 12 rows, two segment columns.

- persona: Founder 4 very + 1 somewhat → 4/5 = **80.0%**; Manager 1 very, 3 somewhat, 3 not → 1/7 = **14.3%**.
- plan: Paid 4 very + 2 somewhat → 4/6 = **66.7%**; Free 1 very, 2 somewhat, 3 not → 1/6 = **16.7%**.
- 4/5: z²/n = 0.76832; centre = (0.8 + 0.38416)/1.76832 = 0.669653; radicand = 0.8·0.2/5 + 3.8416/100 =
  0.070416; sqrt = 0.265360; half = 1.96·0.265360/1.76832 = 0.294124 → **37.6% to 96.4%**.
- 1/7: z²/n = 0.5488; centre = (0.142857 + 0.2744)/1.5488 = 0.269407; radicand = 0.142857·0.857143/7 +
  3.8416/196 = 0.01749271 + 0.0196 = 0.03709271; sqrt = 0.192595; half = 0.243728 → **2.6% to 51.3%**.
- 4/6: z²/n = 0.640267; centre = (0.666667 + 0.320133)/1.640267 = 0.601609; radicand = 0.666667·0.333333/6 +
  3.8416/144 = 0.03703704 + 0.02667778 = 0.06371481; sqrt = 0.252418; half = 0.301621 → **30.0% to 90.3%**.
- 1/6: centre = (0.166667 + 0.320133)/1.640267 = 0.296781; radicand = 0.166667·0.833333/6 + 0.02667778 =
  0.04982593; sqrt = 0.223217; half = 0.266728 → **3.0% to 56.4%**.
- Four segment intervals are read, so the caution names 4.

## accounts

`accounts.input.csv`: 13 respondents in accounts A–F plus one respondent with no account id.

| Account | Answers | In base | Very | Vote |
|---|---|---|---|---|
| A | very, very, somewhat | 3 | 2 | very (2 > 1.5) |
| B | very, somewhat | 2 | 1 | not very (tie) |
| C | very | 1 | 1 | very |
| D | somewhat, not | 2 | 0 | not very |
| E | N/A, N/A | 0 | 0 | outside the base |
| F | very, N/A | 1 | 1 | very |
| (no id) | somewhat | 1 | 0 | not very, its own account |

- Respondents: very 5, somewhat 4, not 1, N/A 3 → 5/10 = **50.0%**, interval 23.7% to 76.3% (as in `coded`).
- Accounts: 7, of which 1 outside the base → base 6, very 3 → **50.0%**. centre = 0.5; radicand = 0.25/6 +
  3.8416/144 = 0.04166667 + 0.02667778 = 0.06834444; sqrt = 0.261428; half = 1.96·0.261428/1.640267 =
  0.312387 → **18.8% to 81.2%**.

## nonstandard

`nonstandard.input.csv`: 4 "Very disappointed", 3 "Mildly disappointed", 3 "Not disappointed" (a three-option
scale some tools use).

- Without `--map`: exit code 2 and a "Non-standard answer wording" message that names the label and says it
  is not comparable with the 40% benchmark. This is a different message from "Unknown answer labels".
- With `--map "Mildly disappointed=somewhat"`: 4/10 = **40.0%**, 16.8% to 68.7% (as in `small_n`), verdict
  `not_comparable`, no benchmark verdict.

`bad_labels` now exercises both messages: "Extremely disappointed" is reported as non-standard wording and
"Kind of" as an unknown label.

## Counts, response rate

- `--counts very=16,somewhat=14,not=10,na=8,blank=2` must give exactly the `basic` result.
- `--invited 600` with those counts: answered = 16 + 14 + 10 + 8 = 48; 48/600 = **8.0%**, under 10% → flagged.
  `--invited 200`: 48/200 = **24.0%**, not flagged.
