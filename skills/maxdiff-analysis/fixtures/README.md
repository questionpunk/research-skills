# Fixtures for maxdiff-analysis

All data here are invented. Expected values were worked out without the analysis script: by hand
(shown below), from a closed-form maximum-likelihood estimate, or, for the synthetic file, from the
utilities the generator was given. The tests in `../tests/` assert exactly these numbers.

| File | Made by | Used for |
|---|---|---|
| `counts.input.csv` | hand | counting scores, segments, per-respondent scores |
| `counts_wide.input.csv` | hand | the same answers in wide format |
| `counts_design.csv` + `counts_responses.input.csv` | hand | the same answers as design file + responses |
| `counts_positions.input.csv` (+ `counts_design.csv`) | hand | the same answers, position-coded |
| `counts_by_respondent.input.csv` (+ `counts_design.csv`) | hand | the same answers, one row per respondent |
| `counts_cell.input.csv` | hand | the same answers, shown items in one `;`-separated cell |
| `logit_pairs.input.csv` | `generate_fixtures.py` | closed-form logit, two items per set |
| `logit_sequential.input.csv` | `generate_fixtures.py` | exact logit for the sequential and best-only models |
| `synthetic.input.csv` | `generate_fixtures.py` (seeded) | recovery of known utilities, bootstrap |
| `bad_sets.input.csv`, `bad_wide.input.csv` | hand | sets that must be excluded and counted |
| `bad_missing_column.input.csv` | hand | exit code 2 |
| `bad_separation.input.csv` | hand | exit code 3 (no finite logit estimate) |

`python3 fixtures/generate_fixtures.py --check` confirms the generated files match the generator. The
generator does not import the analysis script.

## counts: 3 respondents, 4 items, 4 sets of 3

Every respondent sees the four possible triples of A, B, C, D, so each item is shown 3 times per
respondent and 9 times in all. Answers (best / worst):

| Set | Shown | r1 (smb) | r2 (smb) | r3 (ent) |
|---|---|---|---|---|
| 1 | A B C | A / C | B / C | A / B |
| 2 | A B D | A / D | A / D | D / B |
| 3 | A C D | A / D | C / A | A / C |
| 4 | B C D | B / D | B / D | C / B |

Tally, all respondents:

| Item | Shown | Best (where) | Worst (where) | B - W | Score (B - W)/shown |
|---|---|---|---|---|---|
| A | 9 | 6 (r1: 1,2,3; r2: 2; r3: 1,3) | 1 (r2: 3) | 5 | 5/9 = 0.5556 |
| B | 9 | 3 (r1: 4; r2: 1,4) | 3 (r3: 1,2,4) | 0 | 0 |
| C | 9 | 2 (r2: 3; r3: 4) | 3 (r1: 1; r2: 1; r3: 3) | -1 | -1/9 = -0.1111 |
| D | 9 | 1 (r3: 2) | 5 (r1: 2,3,4; r2: 2,4) | -4 | -4/9 = -0.4444 |

Checks: best counts sum to 12 and worst counts to 12 (12 sets); the B - W column sums to 0.

Segment `smb` (r1 + r2, each item shown 6 times): A (4 - 1)/6 = 0.5; B (3 - 0)/6 = 0.5;
C (1 - 2)/6 = -0.1667; D (0 - 5)/6 = -0.8333.

Segment `ent` (r3 only, each item shown 3 times): A 2/3; B -3/3 = -1; C (1 - 1)/3 = 0; D 1/3.
In this segment B is worst in every set that shows it and never best, so no answer ranks B above
anything: the logit has no finite estimate and the test expects `not_estimated` with B named.

Per-respondent scores: r1 = A 3/3, B 1/3, C -1/3, D -3/3; r3 = the `ent` row above.

Position coding (`counts_positions.input.csv`): the design lists each set in alphabetical order, so in
set 1 (A B C) A is position 1 and C position 3; r2's set 3 (A C D), best C / worst A, is `2,1`; r3's
set 2 (A B D), best D / worst B, is `3,2`. Every such file must give the tally above.

### differences (segments and neighbours), counting scores

`ent` minus `smb`: A 2/3 - 1/2 = 1/6; B -1 - 1/2 = -3/2; C 0 - (-1/6) = 1/6; D 1/3 - (-5/6) = 7/6.

Bootstrap range for B: `ent` has one respondent, so every replicate is r3 and its B score is always -1.
A replicate of `smb` is (r1, r1), (r1, r2) or (r2, r2); B's score is then (1 + 1)/6 = 1/3,
(1 + 2)/6 = 1/2 or (2 + 2)/6 = 2/3. The difference can only be -4/3, -3/2 or -5/3, so with 200
replicates the 95% interval is [-5/3, -4/3] and excludes 0. For A the `smb` score is 1, 1/2 or 0, so the
difference 2/3 - that ranges from -1/3 to 2/3 and includes 0.

Neighbours in `ent` (ranked A 2/3, D 1/3, C 0, B -1): differences 1/3, 1/3, 1; no resampling variation,
so each interval is a single point and the order holds in 100% of replicates. Overall, A minus B is
5/9 - 0.

With `--bootstrap 200` and the default seed, 14 of the 200 replicates of the whole file (7%) have no
finite logit estimate (a replicate made of r3 three times, for example, has B always worst). That is
above the 5% limit, so the test expects `logit_intervals` to be `unreliable` and no share intervals.
The count 14 depends on the seed; the test asserts only that the share is above the limit.

The logit for the whole file has no closed form; its values are not asserted, only that the three input
shapes give the same utilities.

## logit_pairs: 20 sets showing A and B; A is best in 15

Ten respondents answer two sets each. With two items, once the best is chosen the worst is the only
item left, so the sequential likelihood is binomial:

```
LL = 15 log p + 5 log (1 - p),   p = exp(u_A) / (exp(u_A) + exp(u_B))
max at p = 15/20                 =>  u_A - u_B = log(15/5) = log 3 = 1.098612
Var(u_A - u_B) = 1/15 + 1/5 = 0.266667   =>  SE = 0.516398
LL at the maximum = 15 log 0.75 + 5 log 0.25 = -11.246703;   LL at u = 0: 20 log 0.5 = -13.862944
```

Fit (`references/method.md`, section 8). The 20 sets are 40 choice tasks: 20 best choices and 20 worst
choices that have one item left, each with probability 1:

```
RLH        = exp(-11.246703 / 40) = exp(-0.281168) = 0.754902      (= (0.75^15 * 0.25^5)^(1/40))
chance RLH = exp(-13.862944 / 40) = exp(-0.346574) = 0.707107      (= sqrt(1/2), not 1/2)
McFadden pseudo-R2 = 1 - 11.246703 / 13.862944 = 0.188722
LR chi-square = 2 * (13.862944 - 11.246703) = 5.232482 on 1 degree of freedom
best-only model: 20 tasks, chance RLH = 1/2, RLH = exp(-11.246703 / 20) = 0.569877
```

Zero-centred: `u_A = +0.549306`, `u_B = -0.549306`, each with SE `0.516398 / 2 = 0.258199`.
Share of preference: `exp(u_A) / (exp(u_A) + exp(u_B)) = 3/4`, so 75.0 and 25.0.
Probability scale with `a = 2`: `exp(0.549306) = sqrt(3) = 1.732051`;
`p_A = 1.732051 / 2.732051 = 0.633975`, `p_B = 0.577350 / 1.577350 = 0.366025`; they already sum to 1,
so 63.40 and 36.60.
Counting: A (15 - 5)/20 = +0.5, B -0.5.

Marginal model (`--model marginal`): "B is worst out of {A, B}" has probability
`exp(-u_B) / (exp(-u_A) + exp(-u_B)) = p`, the same as "A is best". The likelihood is the binomial
one squared: same estimate `log 3`, variance halved, SE `sqrt(0.266667 / 2) = 0.365148`.

## logit_sequential: 105 sets showing A, B, C, in exactly the model's proportions

Choose utilities `u = (2 log 2, log 2, 0)` for (A, B, C), so `exp(u) = (4, 2, 1)` and
`exp(-u) = (1/4, 1/2, 1)`. Under the sequential model:

| Best | P(best) | Left | P(worst \| best) | P(best, worst) | x 105 sets |
|---|---|---|---|---|---|
| A | 4/7 | B, C | B: (1/2)/(3/2) = 1/3; C: 2/3 | AB 4/21; AC 8/21 | 20; 40 |
| B | 2/7 | A, C | A: (1/4)/(5/4) = 1/5; C: 4/5 | BA 2/35; BC 8/35 | 6; 24 |
| C | 1/7 | A, B | A: (1/4)/(3/4) = 1/3; B: 2/3 | CA 1/21; CB 2/21 | 5; 10 |

The file holds exactly these 105 answers (35 respondents x 3 sets). Since the observed proportions
equal the model probabilities at `u`, that `u` is the maximum-likelihood estimate (Gibbs' inequality;
`references/method.md`, section 10):

```
reference-coded (C = 0):  u_A = 2 log 2 = 1.386294,  u_B = log 2 = 0.693147
zero-centred (mean = log 2):  A +0.693147,  B 0,  C -0.693147
share of preference:  4/7, 2/7, 1/7  =  57.142857, 28.571429, 14.285714
```

Standard errors from the information matrix (`method.md`, section 3), parameters (u_A, u_B):

```
best tasks, 105 sets on {A,B,C} with p = (4/7, 2/7, 1/7):
  AA: 105 * (4/7)(3/7) = 180/7      BB: 105 * (2/7)(5/7) = 150/7      AB: -105 * (4/7)(2/7) = -120/7
worst tasks:
  left {B,C}, 60 sets, q_B = 1/3:            BB += 60 * (1/3)(2/3) = 40/3
  left {A,C}, 30 sets, q_A = 1/5:            AA += 30 * (1/5)(4/5) = 24/5
  left {A,B}, 15 sets, q_A = 1/3, q_B = 2/3: AA += 10/3,  BB += 10/3,  AB += -15 * (1/3)(2/3) = -10/3

I_AA = 180/7 + 24/5 + 10/3 = 3554/105 = 33.847619
I_BB = 150/7 + 40/3 + 10/3 = 800/21   = 38.095238
I_AB = -120/7 - 10/3       = -430/21  = -20.476190
det  = I_AA * I_BB - I_AB^2 = 1289.433107 - 419.274376 = 870.158730

V_AA = I_BB / det = 0.043780   =>  SE(u_A) = 0.209236
V_BB = I_AA / det = 0.038898   =>  SE(u_B) = 0.197226
V_AB = -I_AB / det = 0.023532
```

Zero-centred SEs (`c_A = (2 u_A - u_B)/3`, `c_B = (2 u_B - u_A)/3`, `c_C = -(u_A + u_B)/3`):

```
Var(c_A) = (4 V_AA + V_BB - 4 V_AB) / 9 = (0.175120 + 0.038898 - 0.094126) / 9 = 0.013321  => 0.115418
Var(c_B) = (4 V_BB + V_AA - 4 V_AB) / 9 = (0.155593 + 0.043780 - 0.094126) / 9 = 0.011694  => 0.108139
Var(c_C) = (V_AA + V_BB + 2 V_AB) / 9   = (0.043780 + 0.038898 + 0.047063) / 9 = 0.014416  => 0.120065
```

Fit: the fitted probabilities equal the observed proportions, so
`LL = 20 log(20/105) + 40 log(40/105) + 6 log(6/105) + 24 log(24/105) + 5 log(5/105) + 10 log(10/105)
= -163.099124`. Under random choice each answer has probability 1/3 * 1/2, so
`LL0 = 105 log(1/6) = -188.134744` and the chance RLH over 210 tasks is `sqrt(1/6) = 0.408248`
(marginal model: 1/3).

Counting from the same table: A best 60, worst 6 + 5 = 11, score 49/105 = 0.4667; B best 30, worst
20 + 10 = 30, score 0; C best 15, worst 40 + 24 = 64, score -49/105.

Best-only model on the same file: every set shows the same three items, so the model is a saturated
multinomial and the fitted probabilities equal the best shares 60/105, 30/105, 15/105:

```
u_A - u_C = log(60/15) = log 4 = 1.386294,   SE = sqrt(1/60 + 1/15) = 0.288675
u_B - u_C = log(30/15) = log 2 = 0.693147,   SE = sqrt(1/30 + 1/15) = 0.316228
```

(The estimates coincide with the sequential ones because the file was built from one set of utilities;
the SEs are larger because the worst answers are not used.)

## synthetic: 120 simulated respondents, 9 items, 9 sets of 4

`generate_fixtures.py` (seed 20261112, only `random.random()` calls) simulates respondents who answer
by the sequential model from known zero-centred utilities:

| item1 | item2 | item3 | item4 | item5 | item6 | item7 | item8 | item9 |
|---|---|---|---|---|---|---|---|---|
| 1.6 | 1.2 | 0.8 | 0.4 | 0.0 | -0.4 | -0.8 | -1.2 | -1.6 |

Each respondent gets a random relabelling of the cyclic design with base block {0, 1, 3, 7} mod 9: nine
sets of four in which every item appears exactly 4 times, so each item is shown 120 x 4 = 480 times.
The `segment` column alternates `new`/`returning` and carries no information.

What the tests assert, and why:

- **Recovery within 0.25** of the true utility for every item. The model standard error for this
  sample is about 0.08, so 0.25 is about three standard errors. (Observed largest error: 0.21, item8.)
- **Rank order** of the logit shares, and of the counting scores, equals the true order. Neighbouring
  true utilities differ by 0.4, about 3.5 standard errors of a difference, so this holds for this seed;
  it is a property of this file, not a guarantee for other seeds.
- Shares sum to 100, zero-centred utilities and counting scores sum to 0, every item is shown 480 times.
- The bootstrap is repeatable for a seed, changes with the seed, leaves point estimates unchanged, and
  each interval contains its point estimate.

The values are sampling results, not exact, so no exact utilities are asserted for this file.

## Bad input

`bad_sets.input.csv` is `counts.input.csv` plus eight broken sets. Expected: 20 sets read, 12 valid,
8 excluded, and results identical to `counts.input.csv`.

| Respondent, set | What is wrong | Reason counted |
|---|---|---|
| r4, 1 | two items marked best | `best_not_exactly_one` |
| r4, 2 | nothing marked worst | `worst_not_exactly_one` |
| r4, 3 | A marked best and worst | `best_equals_worst` |
| r4, 4 | B listed twice | `duplicate_item` |
| r4, 5 | one item only | `fewer_than_two_items` |
| r4, 6 | `yes` in the best column | `invalid_value` |
| r4, 7 | no best and two worst (first failing rule wins) | `best_not_exactly_one` |
| r3, 5 | nothing marked | `best_not_exactly_one` |

r4 has no valid set and must be reported as dropped; the base stays 3 respondents.

`bad_wide.input.csv`: r1 set 2 has best `C`, which was not shown (`choice_not_shown`); r1 set 3 has A as
best and worst (`best_equals_worst`); r1 set 4 appears on two rows (`duplicate_set`, counted once, both
rows dropped). Five sets remain valid.

`bad_missing_column.input.csv` has no `worst` column: exit code 2, message names the column.

`bad_separation.input.csv`: D is worst in all four sets and never best, so nothing is ever ranked below
D. Expected: exit code 3 naming D; with `--no-logit`, exit 0 and D's counting score is -4/4 = -1.
