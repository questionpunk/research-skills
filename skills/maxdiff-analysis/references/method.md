# MaxDiff analysis: the math the script implements

Every formula here is implemented in `scripts/maxdiff_analysis.py`. Citations are in
[sources.md](sources.md). Worked numbers are in [`../fixtures/README.md`](../fixtures/README.md).

Notation: items `1..K`; a set `S` shows some of them; in each set the respondent marks one item best
(`b`) and a different one worst (`w`). `u_i` is the utility of item `i`.

## 1. Counting scores

For each item, over all valid sets of the respondents in the group:

- `shown_i` = number of sets that showed item `i`
- `B_i` = number of sets where `i` was best, `W_i` = number where it was worst
- best rate `B_i / shown_i`, worst rate `W_i / shown_i`
- **best-minus-worst score** `BW_i = (B_i - W_i) / shown_i`

`BW_i` runs from -1 (worst every time it was shown) to +1 (best every time). Because every set gives
one best and one worst, `sum_i (B_i - W_i) = 0`. The per-respondent score is the same formula on one
respondent's sets (`--respondent-scores`).

Counting ignores which items an item competed against. It is a fair summary when every item is shown
equally often and against a similar mix of other items. When it is not, the script warns and the logit
is the better summary.

## 2. Three logit models for a best-worst answer

All of these use the multinomial logit (Luce) form. They differ in how the worst answer is modelled.

| Name | Probability of the answer (best `b`, worst `w`) in set `S` | In the script |
|---|---|---|
| Marginal sequential | `exp(u_b) / sum_{j in S} exp(u_j)` times `exp(-u_w) / sum_{k in S, k != b} exp(-u_k)` | `--model sequential` (default) |
| Marginal | `exp(u_b) / sum_{j in S} exp(u_j)` times `exp(-u_w) / sum_{k in S} exp(-u_k)` | `--model marginal` |
| Maxdiff (pair) | `exp(u_b - u_w) / sum_{r != s in S} exp(u_r - u_s)` | not implemented |
| Best only | `exp(u_b) / sum_{j in S} exp(u_j)`; the worst answer is not modelled | `--model best-only` |

- **Sequential** is the default because it is a proper probability model of the answer: the respondent
  picks the best of the shown items, then the worst of the items that are left, and the probabilities
  of the `m (m - 1)` possible answers sum to 1.
- **Marginal** lets the worst choice range over all shown items, including the one already marked best.
  This is the coding Sawtooth describes: each set becomes two separate, independent choice sets, with the
  design multiplied by -1 for the worst one. Use it when you want numbers on that footing. Its two
  factors do not sum to 1 over valid answers.
- **Maxdiff** assumes the respondent compares all `m (m - 1)` ordered pairs and picks the pair with the
  largest difference. It is the model the method is named after.

The first three assume that the worst choice uses the same utilities as the best choice with the sign
flipped. If people are more consistent when choosing best than when choosing worst, that assumption is
wrong; `--model best-only` shows how much the worst answers move the result.

## 3. Likelihood, gradient and information (sequential model)

Pooled over all valid sets `t` (all respondents in the group, treated as one long interview):

```
LL(u) = sum_t [ u_{b_t} - log sum_{j in S_t} exp(u_j) ]
      + sum_t [ -u_{w_t} - log sum_{k in R_t} exp(-u_k) ]          R_t = S_t without b_t
```

Collecting terms:

```
LL(u) = sum_i u_i (B_i - W_i)
      - sum_S n_S log sum_{j in S} exp(u_j)
      - sum_R m_R log sum_{k in R} exp(-u_k)
```

where `n_S` counts how often the shown set `S` occurred and `m_R` how often the remaining set `R`
occurred. So the data enter only through `B_i - W_i` (the numerator of the counting score) and the set
counts. The script pools exactly these.

With `p_i(S) = exp(u_i) / sum_{j in S} exp(u_j)` and `q_i(R) = exp(-u_i) / sum_{k in R} exp(-u_k)`:

```
gradient     g_i  = (B_i - W_i) - sum_{S contains i} n_S p_i(S) + sum_{R contains i} m_R q_i(R)

information  I_ii = sum_S n_S p_i(S) (1 - p_i(S)) + sum_R m_R q_i(R) (1 - q_i(R))
(= -Hessian) I_ij = - sum_S n_S p_i(S) p_j(S)     - sum_R m_R q_i(R) q_j(R)          (i != j)
```

Derivation of the worst-choice term: `d/du_i [ -u_w - log sum_k exp(-u_k) ] = -[i = w] + q_i`, and
`d q_i / d u_i = -q_i (1 - q_i)`, `d q_i / d u_j = q_i q_j`. The best-choice term is the standard
multinomial logit. `I` is a sum of covariance matrices, so `LL` is concave.

For `--model marginal`, replace `R` by `S` in the worst term. For `--model best-only`, drop the worst
term and replace `B_i - W_i` by `B_i`.

## 4. Identification, estimation, standard errors

- **Identification.** Adding a constant to every `u_i` changes nothing, so one constraint is needed. The
  script estimates with the last item fixed at `u_K = 0` (last in the design file's order, or in natural
  label order when there is no design), and **reports zero-centred utilities** `c_i = u_i - mean(u)`,
  which do not depend on which item was the reference. The reference-coded values, the form Sawtooth
  calls raw scores, are printed under each table and are in the JSON under `logit.reference_coded`.
- **Newton-Raphson.** Start at `u = 0`. Each step solves `I step = g` for the `K - 1` free utilities with
  a hand-written Cholesky factorisation (`I = L L^T`, forward then back substitution) and sets
  `u <- u + step`. If the log-likelihood would fall, the step is halved (at most 30 times).
- **Convergence.** Stop when the largest step is below `1e-8` and the largest gradient element is below
  `1e-6` per choice task. More than 50 iterations, a non-positive-definite `I`, or a step that cannot
  increase the likelihood is a failure (exit code 3), never a silent result.
- **Standard errors.** `V = I^{-1}` at the estimate (inverse of the observed information, which for this
  model equals the expected information). For the zero-centred utilities, `c = C u` with
  `C = Id - (1/K) 1 1^T`, so `Var(c) = C V C^T` exactly (the map is linear), where `V` is padded with a
  zero row and column for the reference item:
  `Var(c_i) = V_ii - (2/K) sum_j V_ij + (1/K^2) sum_jk V_jk`.
- **What the SE ignores.** `V` treats every set as an independent observation. Sets from one respondent
  are not independent, so these SEs are usually too small. The bootstrap intervals resample respondents
  and do not have this problem; quote those.

## 5. When no estimate exists (separation)

Build a directed graph on the items with an edge `a -> c` whenever an answer ranks `a` above `c`:

- best task: `b -> j` for every other shown item `j`;
- worst task: `k -> w` for every other item `k` in the worst task's set.

**A finite, unique maximum-likelihood estimate exists if and only if this graph is strongly connected.**

Why: `LL` is concave, so the maximum fails to be attained exactly when there is a direction `d` (not
constant across items) along which `LL` never decreases. Along `u + t d`, a best-task term
`u_b - log sum_S exp(u_j)` stays bounded as `t` grows only if `d_b >= d_j` for all `j` in `S`, and a
worst-task term only if `d_k >= d_w` for all `k`. So a bad direction is a non-constant `d` with
`d_a >= d_c` on every edge `a -> c`. If the graph is strongly connected, following a cycle through any
two items forces all `d` equal, so no bad direction exists. If it is not, take a group of items that no
outside item is ever ranked above (a source component of the graph), set `d = 1` on it and `0`
elsewhere: every edge constraint holds, so the utilities of that group run to infinity. The same
argument gives uniqueness, because a strongly connected graph is connected and `I` is then positive
definite. This is the condition known for the Bradley-Terry and Plackett-Luce models (Ford 1957;
Hunter 2004), applied to best and worst choices.

Typical causes: an item that is worst every time it is shown, an item that is best every time, a very
small group, or two blocks of items that were never shown together. The script checks the graph before
fitting and names the offending groups. Counting scores remain valid.

## 6. Shares

Two transformations of the zero-centred utilities, both reported so that they sum to 100:

- **Share of preference** (default, `--share-scale preference`):
  `share_i = 100 exp(u_i) / sum_j exp(u_j)`. This is the logit probability that item `i` is picked best
  if all `K` items were shown together. Ratios mean something: a share of 20 is twice a share of 10.
- **Probability scale** (`--share-scale probability`):
  `p_i = exp(c_i) / (exp(c_i) + a - 1)` with `c` zero-centred and `a` the number of items per set, then
  `100 p_i / sum_j p_j`. `p_i` is the probability that item `i` is picked best against `a - 1` items of
  average utility (`exp(0) = 1` each). This is Sawtooth's "probability scale"/"rescaled scores". It is
  flatter than the share of preference: top items get smaller numbers and bottom items larger ones.

The two scales give the same order and different numbers. Always say which one a table shows.
Sawtooth applies the probability scale per respondent to hierarchical Bayes utilities and averages;
here it is applied once to the pooled utilities, so the numbers are not the same as an HB report.

## 7. Intervals

Percentile bootstrap over **respondents**, not sets:

1. Draw `n` respondents with replacement from the `n` in the group (seeded; `random.Random(seed)`, and
   for a segment `random.Random("<seed>:<segment>")`).
2. Recompute the counting scores, refit the logit (started from the full-sample estimate) and recompute
   the shares.
3. After `B` replicates (default 1000), the interval for each quantity is the 2.5th to 97.5th percentile
   of its replicate values (linear interpolation between order statistics; `--ci` changes the level).

A replicate in which the logit has no finite estimate (section 5) is left out of the utility and share
intervals and counted in `logit_replicates_failed` (and as a share in
`logit_replicates_failed_share`). Leaving replicates out drops exactly the resamples in which an item
looked most extreme, so the remaining interval is too narrow. The script warns whenever any replicate
fails. When more than 5% fail it marks `logit_intervals` as `unreliable` and does not print utility or
share intervals at all; counting-score intervals are unaffected. The 5% limit is a convention of this
script, not a published threshold. Point estimates always come from the full sample.

### Differences between two items

Two intervals that overlap do not prove a tie, and two that do not overlap are a stricter test than
needed, because the two estimates come from the same respondents and move together. The script
therefore works on the difference itself. For each pair of neighbours in the ranking, with `s_A` and
`s_B` the two shares:

- `difference = s_A - s_B` from the full sample;
- `difference_ci` = the percentile interval of `s_A* - s_B*` over the bootstrap replicates, both shares
  taken from the same replicate;
- `prob_higher_above` = the share of replicates in which `s_A* > s_B*` (a replicate with an exact tie
  counts one half).

If the interval of the difference includes 0, the two items are **not separated by this data**.
`prob_higher_above` is a description of how stable the order is under resampling. It is not a p-value
and not a posterior probability. When the logit did not run, or its intervals are unreliable, the same
quantities are computed on the counting score (`metric` says which).

### Differences between two segments

For each pair of segments and each item, `difference = share in the first - share in the second`.
Segments are resampled independently of each other (each with its own seeded stream), so replicate `b`
of one segment is paired with replicate `b` of the other, and the interval is the percentile interval of
the paired differences. `excludes_zero` marks intervals that do not contain 0. With `K` items and
several segment pairs there are many intervals; at a 95% level about one in twenty will exclude 0 by
chance alone, so a single flagged item is weak evidence. If either segment has no usable logit
replicates, the comparison is made on counting scores.

Do not compare segments by checking whether their per-segment intervals overlap, and do not run
t-tests on shares: shares within a segment sum to 100 and are not independent of each other.

## 8. Model fit

Let `T` be the number of choice tasks the likelihood is a product of: two per set for the sequential
and marginal models (one best choice, one worst choice), one per set for best-only. `LL` is the
log-likelihood at the estimate and `LL0` the log-likelihood with all utilities equal (random choice).

- **Root likelihood** `RLH = exp(LL / T)`: the geometric mean of the probabilities the model gave to
  the choices that were made. 1 is a perfect fit.
- **Chance level** `RLH0 = exp(LL0 / T)`: the same quantity under random choice. It depends on the
  model. With `a` items in every set:
  - best-only: every task has `a` alternatives, `RLH0 = 1/a`;
  - marginal: both tasks have `a` alternatives, `RLH0 = 1/a`;
  - sequential: the best task has `a` alternatives and the worst task `a - 1`, so
    `LL0 = -N (log a + log(a - 1))` over `N` sets and `T = 2N` tasks, giving
    `RLH0 = (1/a * 1/(a - 1))^(1/2) = 1 / sqrt(a (a - 1))`. For `a = 4` that is `0.289`, not `0.25`;
    for `a = 2` the worst task has one alternative (probability 1) and `RLH0 = sqrt(1/2) = 0.707`.
  With mixed set sizes the script uses the actual `LL0`, which is the geometric mean over all tasks.
- **McFadden pseudo-R2** `= 1 - LL / LL0`: 0 when the model does no better than random choice, 1 for a
  perfect fit.
- **Likelihood-ratio chi-square** `= 2 (LL - LL0)` with `K - 1` degrees of freedom (the number of
  estimated utilities). Like the model SE, it treats sets as independent, so it overstates the
  evidence; the script prints the statistic and no p-value.

Always compare RLH with its chance level, never with a fixed cut-off: no published threshold separates
good from bad fit, and RLH from different models or set sizes are not comparable. A pooled model fitted
to people who disagree with each other has a modest RLH even when every person answers carefully.

## 9. Position-coded answers

Some exports store the best and worst answer as the position of the chosen item in the set (1 = first
shown) rather than its label. With `--choice-coding position` the script looks the position up in the
set: the `position` column of the design file, the order of the shown-item columns, or the order inside
the delimited cell. A position that does not exist in the set makes the set invalid
(`choice_not_shown`); a cell that is not a number makes it invalid (`invalid_value`). The script cannot
tell a position from a numeric item label, so the coding is never guessed: it is `label` unless stated.

## 10. Closed forms used to check the implementation

- **Two items per set, sequential model.** Once best is chosen from `{A, B}`, worst is the only item
  left (probability 1). The likelihood is binomial: `u_A - u_B = log(n_A / n_B)` and
  `Var = 1/n_A + 1/n_B`.
- **Same set every time, best-only model.** The likelihood is multinomial with
  `P(i) = exp(u_i) / sum_j exp(u_j)`, a saturated model, so the fitted probabilities equal the observed
  shares: `u_i - u_K = log(n_i / n_K)`, `Var = 1/n_i + 1/n_K`.
- **Data in exactly the model's proportions.** For counts `n_o` over outcomes `o`,
  `sum_o n_o log P_o(u)` is at most `sum_o n_o log (n_o / N)`, with equality only when
  `P_o(u) = n_o / N` for every outcome (Gibbs' inequality). If the data are built to match the model at
  some `u*`, then `u*` is the maximum-likelihood estimate.
- **Fit on the two-item fixture.** 20 sets give 40 tasks: 20 best choices and 20 worst choices with
  one item left (probability 1). `RLH = (0.75^15 * 0.25^5)^(1/40)` and `RLH0 = (0.5^20)^(1/40) =
  sqrt(0.5)`.
- **Maxdiff model with two items** (for comparison only): `P(A best, B worst) = exp(2(u_A - u_B)) /
  (exp(2(u_A - u_B)) + 1)`, so its estimate is half the sequential one. Utilities from different models
  are on different scales; shares and ranks are what to compare.
