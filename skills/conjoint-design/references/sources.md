# Conjoint design: method sources

Every formula, threshold and default in `SKILL.md` and `scripts/conjoint_design.py`, with its source. "Not
fetched" means the citation is known from indexes or citing work but the text was not read for this skill;
"convention of this skill" means no published source sets the value.

Contents: Formulas · Thresholds and defaults · Design advice · Worked examples reproduced · Sources

## Formulas

| Quantity | Formula | Source |
|---|---|---|
| MNL information at β = 0 | (1/m) Σ_j (x_j − x̄)(x_j − x̄)ᵀ per task, averaged over tasks | Huber and Zwerina (1996); Kuhfeld (2010) |
| D-error | det(M)^(−1/p) | Huber and Zwerina (1996); Kuhfeld (2010) |
| Relative D-efficiency | 100 × (det M / Π_q (2S_q/(m²(ℓ_q − 1)))^(ℓ_q − 1))^(1/p) | Bound derived in `design-method.md` section 4; S_q as in Burgess and Street (2005) (not fetched) |
| Orthonormal coding | Normalized Helmert contrasts | Standard; any orthonormal contrast gives the same determinant |
| Cramér's V | √(χ² / (N (min(r, c) − 1))) | Cramér (1946) |
| Sample size | n ≥ 500·c / (t·a); c = most levels of any attribute, t = tasks, a = concepts per task (none not counted) | Johnson and Orme (1996) via Sawtooth Software's "Sample size rules of thumb" page (read 2026-11-19): "at least 500 appearances per level"; also stated in Orme (2010), chapter on sample size (not fetched). Some secondary sources credit Orme (1998) instead; not confirmed either way |
| Sample size from the actual design | n ≥ 500 / e, e = appearances per respondent of the least shown level = its count over all versions / number of versions | The same 500-appearances rule applied to the level that is actually shown least (this skill's application; it equals the formula above for a perfectly balanced design) |
| Per reported subgroup | max(200, the exposure minimum), times the number of subgroups for equal shares | 200 from the Sawtooth page; requiring the exposure minimum within each subgroup is this skill's application of the same rule to an estimate made on that subgroup alone |
| Planning sample | n ≥ 1,000·c / (t·a) | Same Sawtooth page: plan for about 1,000 exposures per level |
| Floors | 300 respondents per study, 200 per reported subgroup | Same Sawtooth page ("300 respondents per study, 200 per subgroup") |
| Interactions | c = product of the two attributes' level counts | Orme (2010), *Getting Started with Conjoint Analysis* (**not confirmed**: the Sawtooth page read defines c only for main effects) |

## Thresholds and defaults

| Value | Source |
|---|---|
| 100 versions | Convention of this skill |
| Warn under 80% relative D-efficiency | Convention of this skill |
| Warn when Cramér's V between attributes is above 0.10 | Convention of this skill (Cohen's (1988) "small" effect for w is 0.10) |
| Warn when level counts differ by more than 1.5× | Convention of this skill |
| 2,000 attempts per task, balance loosened after 50, an identical task redrawn up to 20 times | Implementation constants |
| Seed 20261119 | Arbitrary fixed value so runs repeat |

## Design advice used in SKILL.md

- **Attributes and levels.** Levels of one attribute must be mutually exclusive and cover the realistic
  range; attributes must not overlap in meaning (Orme 2010, chapter on attributes and levels; not fetched).
- **Number of attributes.** Full-profile tasks become hard beyond about six attributes (Green and Srinivasan
  1990; not fetched).
- **Number-of-levels effect.** An attribute split into more levels tends to get more importance (Wittink,
  Krishnamurthi and Reibstein 1990; not fetched). Keep level counts similar where you can.
- **Tasks per respondent.** Respondents can answer many more choice tasks than older guidance assumed;
  Johnson and Orme (1996) reported reliable answers up to about 20 tasks (from secondary summaries; **not
  confirmed** from the paper). This skill suggests 8 to 15.
- **None option.** A none alternative makes shares more realistic but gives less information about the
  attributes; a dual-response none (choose, then "would you really buy it?") keeps both (Brazell et al. 2006;
  not fetched). The efficiency here is for the forced choice among the concepts (Street and Burgess 2007),
  so it overstates the attribute information of a design with a none option.
- **Fully randomized designs and AMCEs.** Independent uniform randomization identifies average marginal
  component effects without a model (Hainmueller, Hopkins and Yamamoto 2014). Prohibitions (restricted
  randomization) break the unconditional independence the simple difference in means relies on; the paper
  covers conditional estimators for that case, which this pack does not provide. Rejecting duplicate
  concepts within a task would couple the concepts of a task, so `--method random` keeps duplicates.
- **Shortcut versus complete enumeration.** Sawtooth's shortcut method balances one-way level frequencies
  and minimizes overlap; complete enumeration also balances two-way level co-occurrence (Chrzan and Orme
  2000; not fetched). The balanced generator here is shortcut-like.
- **Choice designs.** Orthogonality, level balance, minimal overlap and utility balance are the four
  principles of efficient choice designs; at β = 0 the first three are what matter (Huber and Zwerina 1996).

## Worked examples reproduced

- **Sawtooth sample-size example** (Sawtooth page above): attributes with 3, 6 and 4 levels, 3 concepts, 8
  tasks, so c = 6, t = 8, a = 3. The page shows the result only as an image; the formula gives
  n = 500 × 6 / 24 = **125**, and 250 for 1,000 exposures. Reproduced in `tests/`.
- **Optimal designs score 100%.** The foldover pair design (each 2^k profile against its complement) is
  optimal for two-level attributes in pairs (Street and Burgess 2007, chapter on 2^k designs; not fetched),
  and a Latin-square triple design for two 3-level attributes has every level once per task and every
  cross-pair once. Both score 100.000% in `tests/`.
- **Independent check.** `tests/` rebuilds the information matrix with effects coding and computes
  determinants by Gaussian elimination; the ratio of two designs' efficiencies matches the script's.

## Sources

1. Huber, J. and Zwerina, K. (1996). The importance of utility balance in efficient choice designs.
   *Journal of Marketing Research* 33(3):307-317.
2. Kuhfeld, W. F. (2010). *Marketing Research Methods in SAS* (MR-2010). SAS Institute. Free technical report;
   "Efficient Experimental Design with Marketing Research Applications" and "Discrete Choice" chapters. Latest
   edition not confirmed.
3. Burgess, L. and Street, D. J. (2005). Optimal designs for choice experiments with asymmetric attributes.
   *Journal of Statistical Planning and Inference* 134(1):288-301. Pages confirmed via an index; text not
   fetched.
4. Street, D. J. and Burgess, L. (2007). *The Construction of Optimal Stated Choice Experiments: Theory and
   Methods*. Wiley. Not fetched.
5. Louviere, J. J. and Woodworth, G. (1983). Design and analysis of simulated consumer choice or allocation
   experiments: an approach based on aggregate data. *Journal of Marketing Research* 20(4):350-367.
6. Johnson, R. M. and Orme, B. K. (1996). How many questions should you ask in choice-based conjoint studies?
   Sawtooth Software Research Paper Series. Not fetched; the rule is quoted from the Sawtooth page below.
7. Sawtooth Software (Halversen, C., updated 2020). Sample size rules of thumb for choice-based conjoint
   (CBC). https://www.sawtoothsoftware.com/resources/blog/posts/sample-size-rules-of-thumb (read 2026-11-19).
8. Orme, B. K. (2010; 4th ed. 2020). *Getting Started with Conjoint Analysis*. Research Publishers. Edition
   not confirmed; not fetched.
9. Hainmueller, J., Hopkins, D. J. and Yamamoto, T. (2014). Causal inference in conjoint analysis:
   understanding multidimensional choices via stated preference experiments. *Political Analysis* 22(1):1-30.
10. Green, P. E. and Srinivasan, V. (1990). Conjoint analysis in marketing: new developments with
    implications for research and practice. *Journal of Marketing* 54(4):3-19. Not fetched.
11. Wittink, D. R., Krishnamurthi, L. and Reibstein, D. J. (1990). The effect of differences in the number of
    attribute levels on conjoint results. *Marketing Letters* 1(2):113-123. Not fetched.
12. Brazell, J. D., Diener, C. G., Karniouchina, E., Moore, W. L., Séverin, V. and Uldry, P.-F. (2006). The
    no-choice option and dual response choice designs. *Marketing Letters* 17(4):255-268. Not fetched.
13. Cramér, H. (1946). *Mathematical Methods of Statistics*. Princeton University Press.
14. Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences*, 2nd ed. Erlbaum.
15. Chrzan, K. and Orme, B. (2000). An overview and comparison of design strategies for choice-based conjoint
    analysis. Sawtooth Software Research Paper Series. Not fetched.
