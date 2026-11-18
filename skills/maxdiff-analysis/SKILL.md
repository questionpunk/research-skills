---
name: maxdiff-analysis
description: "Score MaxDiff (best-worst scaling) results from a CSV: counting scores and an aggregate multinomial logit, giving utilities and preference shares with bootstrap intervals, model fit and segment comparisons. Use for \"analyze MaxDiff\", \"best-worst scores\", \"share of preference\", \"which features matter most\" or \"feature priority results\" from a Sawtooth, Qualtrics or other survey export. Not for building the design (maxdiff-design) or individual-level HB utilities."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "pricing-research"
---

# MaxDiff analysis

Turns raw MaxDiff (best-worst scaling) answers into a ranked table: counting scores, pooled logit
utilities, shares that sum to 100, bootstrap intervals, model fit, and tested differences between
neighbouring items and between segments. The calculation lives in
[`scripts/maxdiff_analysis.py`](scripts/maxdiff_analysis.py) (Python 3.9+, standard library only).
Run it; do not redo the math in the conversation.

**What it does not do.** Say these limits in the answer when they matter.

- **No hierarchical Bayes (HB).** It fits one set of utilities for the whole group (aggregate logit), so
  there are no individual-level utilities. The user needs HB for a utility per respondent, clustering
  respondents on utilities, TURF or reach analysis, or a design too sparse for each person to see each
  item several times. Tools: Sawtooth Lighthouse Studio (CBC/HB), Latent Gold (latent class), R `bayesm`
  (`rhierMnlRwMixture`) or Stan. Per-respondent counting scores (`--respondent-scores`) are a rough
  stand-in, not a substitute.
- **No anchored MaxDiff.** Scores are relative to the items tested. There is no "important in absolute
  terms" threshold, and an anchor question in the export is not used.
- **No respondent weights, no latent classes, no TURF.**

## When to use

Use when the user has MaxDiff or best-worst answers (from Sawtooth, Qualtrics or any survey export) and
asks to "analyze MaxDiff", "score the best-worst results", "share of preference", "which features
matter most", "feature priority results" or "compare MaxDiff by segment".

Do not use, and hand over instead:

| Request | Use |
|---|---|
| No data yet: build the sets, items per set, versions | `maxdiff-design` |
| "How many respondents do I need for MaxDiff?" | `survey-sample-size` |
| Conjoint or choice-based conjoint data (profiles with attributes and levels) | `conjoint-analysis` |
| Price questions (too cheap / too expensive, price ladders) | `van-westendorp-analysis`, `gabor-granger-analysis` |
| Removing speeders, straight-liners or duplicates before scoring | `survey-data-cleaning`, then come back |
| Rating-scale or ranking questions that are not best-worst sets | `survey-crosstabs` |
| Individual-level HB utilities, latent-class segments, TURF, anchored MaxDiff | not covered; see above |

A skill named in this section may not be installed (some are still planned). If it is missing, say so, name
the method the request needs, and do not stretch this skill to cover it.

## What to ask for

Only the data file is required. Ask one question at most: "Which file has the answers, and is there a
column to cut by?" Everything else has a default or can be read from the file.

| Input | Default | Notes |
|---|---|---|
| Responses CSV | required | five accepted shapes; see [input formats](references/input-formats.md) |
| Design CSV | none | `version,set,position,item` (as `maxdiff-design` writes it); needed only when the responses do not say which items were shown |
| Column names | `respondent`, `set`, `item`, `best`, `worst` | read the header and map with `--respondent-col` etc.; never rename the user's file |
| Choice coding | `label` | `--choice-coding position` when best/worst hold the position in the set (common in Sawtooth-style exports). Never guess: if the cells are small integers and the items are not, check with the user or the codebook |
| Segment column | none | `--segment-col`; one value per respondent |
| Logit model | `sequential` | `marginal` to line up with Sawtooth's coding, `best-only` as a check; see [method](references/method.md) |
| Share formula | `preference` | `probability` for Sawtooth-style rescaled scores |
| Intervals | 95%, 1000 bootstrap replicates, seed 12345 | resampling respondents |
| Minimum base | 200 respondents per reported group | below it the group is flagged, not hidden |

If the export is in another shape, reshape it to the long format with a short script first and tell the
user what you mapped to what.

## Steps

1. **Look at the file.** Read the header and first rows. Identify the shape, the column names, and
   whether best/worst are 0/1 flags, item labels or positions. Check where the shown items are: in the
   rows, in columns, in one delimited cell, or only in a design file.
2. **Run the script** from the skill folder with the options the file needs:

   ```bash
   python3 scripts/maxdiff_analysis.py responses.csv --segment-col plan
   python3 scripts/maxdiff_analysis.py export.csv --design design.csv --choice-coding position
   python3 scripts/maxdiff_analysis.py responses.csv --shown-col set_items --json > result.json
   ```

   Use `--bootstrap 200` for a first look at a large file and the default for reported numbers.
3. **Read the validation block before the scores.** Report sets read, valid and excluded with the count
   per reason. Many exclusions for one reason usually mean a wrong column mapping or coding: fix and
   rerun before interpreting anything.
4. **If the script exits with code 3** (no finite logit estimate), an item was always worst or always
   best, or two groups of items never met. Report the items the message names, rerun with `--no-logit`
   and present counting scores only. Do not substitute numbers of your own.
5. **Check counts against the logit.** They should give nearly the same order. If the script warns that
   items were not shown equally often, lead with the logit columns.
6. **Read the fit line.** Compare RLH with the chance level printed next to it. There is no cut-off for
   "good" fit; a pooled model of people who disagree has a modest RLH. A value at chance means the
   answers carry no shared order (or the coding is wrong).
7. **Use the tested differences, not overlapping intervals.** The "Adjacent items" lines give the
   bootstrap interval of the difference between neighbours. If it includes 0, the two items are not
   separated by this data: report them as a group. The "Difference" tables do the same between
   segments.
8. **Write the answer** in the shape below.

## Output

Always this shape, in this order:

1. **Summary** (two or three sentences): the leading items, the trailing items, and which neighbours
   are not separated.
2. **Data used**: respondents, valid sets, excluded sets by reason, items, items per set; respondents
   dropped for having no valid set.
3. **Results table**, one row per item, sorted by rank:

   | Rank | Item | Shown | Best | Worst | B-W score [95% CI] | Utility [95% CI] | Share % [95% CI] |
   |---|---|---|---|---|---|---|---|

   Under it: the average share (100 / number of items) and which items are above and below it; the
   pairs of neighbours that are not separated.
4. **Model fit**: RLH with its chance level, McFadden pseudo-R2, likelihood-ratio chi-square with
   degrees of freedom.
5. **Segments** (if cut): each segment's table with its base and a flag when below the minimum, then
   the difference table per pair of segments, marking intervals that exclude 0.
6. **Method line**, copied from the script's `method` block: counting formula, logit model, share
   formula, interval method with replicates and seed, "aggregate estimates; hierarchical Bayes not
   run; not anchored".
7. **Warnings**, copied from the script, in plain words.

How to explain the columns:

- **B-W score** = (times best - times worst) / times shown, from -1 to +1. Transparent, no model.
- **Utility** = zero-centred logit utility. Interval scale: differences mean something, ratios do not.
  The reference-coded line (last item = 0) is the same estimate in the form other tools print.
- **Share** = `100 * exp(u) / sum exp(u)`: the modelled chance the item is picked best out of all the
  items. Within this study a share of 20 is twice a share of 10. Shares are relative to this item
  list: add or remove an item and every share changes, so do not compare shares across studies.
  With `--share-scale probability` the column is Sawtooth's probability scale applied to pooled
  utilities; name it so, and note it will not equal a Sawtooth HB report.

With `--json` the same content is machine-readable; keys are listed in
[input formats](references/input-formats.md). Formulas and derivations are in
[method](references/method.md), citations in [sources](references/sources.md), how to line the numbers
up with Sawtooth or R output in [compare with other tools](references/compare-with-other-tools.md), and
the hand-worked test cases in [fixtures](fixtures/README.md).

## Checks before answering

Each must be "yes" before the answer goes out.

- Did the numbers come from the script's output, not from arithmetic in the conversation?
- Was the choice coding (label or position) confirmed from the file or codebook, not assumed?
- Are excluded sets reported with counts and reasons, and is the exclusion rate plausible?
- Does the answer name the logit model and the share formula, and say the estimates are pooled, not
  HB and not anchored?
- Are the intervals the bootstrap intervals over respondents (not the model SE)? If the script
  withheld logit intervals as unreliable, is that stated and are counting-score intervals used?
- Are neighbours whose difference interval includes 0 described as not separated by this data, rather
  than ranked with confidence or called equal?
- Are segments compared with the difference tables (not by overlapping per-segment intervals, not by
  t-tests on shares, not on raw utilities), with the caveat that among many items some intervals
  exclude 0 by chance and that a noisier segment has flatter shares?
- Is every group under 200 respondents flagged as directional?
- If items were not shown equally often, does the answer lead with the logit rather than counts?
- Is RLH reported next to its chance level, with no "good/bad" label?
- Is the claim limited to relative preference among the tested items? The top item of a weak list is
  still weak; nothing here measures absolute appeal, willingness to pay or items not in the study.

## Field it with QuestionPunk (optional)

The result above is complete on its own. MaxDiff, conjoint and Van Westendorp are built-in QuestionPunk question types; check which your plan includes in the app.

QuestionPunk draws the sets for each respondent itself, so take the shown items from the response export, not from a design file. Hosted MCP tools this step may use: `responses_export` and `report_get`. Ask before creating, changing or publishing anything. If a response or report tool answers that you must reconnect and approve, reconnect the QuestionPunk connector once: connections made before 3 Oct 2026 lack the `responses:read` permission.
