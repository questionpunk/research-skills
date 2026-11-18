# Comparing these numbers with other tools

Numbers from two tools match only when the model, the identification and the scale all match. Use this
table to line them up before concluding that one of them is wrong. Sources are in
[sources.md](sources.md).

| Tool and analysis | Worst answer modelled as | Utilities reported | Shares reported | To approximate here |
|---|---|---|---|---|
| Sawtooth aggregate logit | separate choice over all shown items with negated utilities (marginal) | raw (last item = 0), zero-centred with a range of 100, and rescaled 0-100 | probability scale `exp(U)/(exp(U)+a-1)` rescaled to 100 | `--model marginal --share-scale probability`; compare its raw scores with the "Reference-coded utilities" line (same reference item only if it is the last item here too) |
| Sawtooth HB | as above, per respondent | individual utilities, averaged | probability scale per respondent, then averaged | cannot be matched: this script pools respondents. Expect a similar order and different numbers |
| R `support.BWS` | pair (maxdiff) model by default; marginal and marginal sequential available | reference-coded conditional logit coefficients | `exp(v)/sum exp(v)` | `--model sequential` or `marginal` when the R data set was built with that model; the pair model is not implemented here |
| R `support.BWS` counts | n/a | `B`, `W`, `B - W`, `(B - W)/(N r)` | n/a | the Best, Worst and B-W score columns; `(B - W)/(N r)` equals the B-W score when every respondent saw every item `r` times |
| Displayr `flipMaxDiff` | rank-ordered logit with ties by default, tricked logit optional; latent class or HB | class or individual parameters | probabilities | cannot be matched: different likelihood and respondent-level heterogeneity |

What to expect when the model differs:

- **Order of items:** the same on balanced data unless two items are close (see the adjacent-item lines).
- **Utility scale:** differs. The pair model is on a different scale from the sequential one (exactly
  half, with two items per set); marginal and sequential are close but not equal. Never compare raw
  utilities across models.
- **Shares:** share of preference and probability scale differ by construction; the probability scale is
  flatter. Compare like with like.
- **Reference-coded versus zero-centred:** subtract the mean of the reference-coded utilities (including
  the 0 of the reference item) to get the zero-centred ones.
- **Intervals:** Sawtooth's aggregate logit reports model standard errors that treat sets as independent
  (the SE column here). The bootstrap intervals here resample respondents and are wider.
