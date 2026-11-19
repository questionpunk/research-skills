---
name: maxdiff-analysis
description: "Scores MaxDiff (best-worst scaling, BWS) results from a CSV: counting scores and an aggregate multinomial logit, giving utilities and preference shares with bootstrap intervals, model fit and segment comparisons. Use for \"analyze MaxDiff\", \"best-worst scores\", \"share of preference\", \"which features matter most\" or \"feature priority results\" from a Sawtooth, Qualtrics or other survey export. Not for building the design (maxdiff-design) or individual-level HB utilities."
license: MIT
metadata:
  version: "0.2.0"
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
  terms" threshold, and an anchor question in the export is not used (the `maxdiff-design` skill says the
  same before fieldwork).
- **No pair (maxdiff) model**, the default of R `support.BWS`: its utilities cannot be reproduced here.
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
| Too cheap / too expensive price questions | `van-westendorp-analysis` |
| Removing speeders, straight-liners or duplicates before scoring | `survey-data-cleaning`, then come back |
| Conjoint data, rating-scale or ranking questions that are not best-worst sets | not covered: say so and name the method |
| Individual-level HB utilities, latent-class segments, TURF, anchored MaxDiff | not covered; see above |

A skill named here may not be installed. If it is missing, say so, name the method the request needs,
and do not stretch this skill to cover it.

## What to ask for

Only the data file is required. Ask "Which file has the answers, and is there a column to cut by?" if
that is not clear. Everything else has a default or can be read from the file, except an ambiguous
choice coding: then also ask for the codebook (see the table).

| Input | Default | Notes |
|---|---|---|
| Responses CSV | required | five accepted shapes; see [input formats](references/input-formats.md) |
| Design CSV | none | the long `version,set,position,item` file `maxdiff-design` writes (not its `--wide` form); needed only when the responses do not say which items were shown |
| Column names | `respondent`, `set`, `item`, `best`, `worst` | read the header and map with `--respondent-col` etc.; never rename the user's file. Comma, semicolon and tab files are detected |
| Choice coding | `label` | `--choice-coding position` when best/worst hold the position in the set (common in Sawtooth-style exports). Never guess: whenever best/worst are small whole numbers, whether the items are text or numeric ids, confirm from the codebook. With numeric item ids a position can match an id and be scored as the wrong item without any exclusion |
| Segment column | none | `--segment-col`; one value per respondent |
| Logit model | `sequential` | `--model marginal` to line up with Sawtooth's coding (a composite likelihood: no chi-square test or model SE), `--model best-only` as a check; the `support.BWS` pair model is not available; see [method](references/method.md) |
| Share formula | `preference` | `--share-scale probability` for Sawtooth-style rescaled scores |
| Intervals | 95%, 1000 bootstrap replicates, seed 12345 | resampling respondents |
| Minimum base | 200 respondents per reported group | below it the group is flagged, not hidden. Planning rule, shared with `maxdiff-design` and `survey-sample-size`: 300 in total and 200 per subgroup reported |

If the export is in another shape, reshape it to the long format with a short script first and tell the
user what you mapped to what.

## Steps

1. **Look at the file.** Read the header and first rows. Identify the shape, the column names, and
   whether best/worst are 0/1 flags, item labels or positions. Check where the shown items are: in the
   rows, in columns, in one delimited cell, or only in a design file. A Qualtrics export has two extra
   header rows to drop; Sawtooth suffix-named columns may need reshaping
   ([input formats](references/input-formats.md), "Exports that need reshaping first").
2. **Run the script** by its path inside this skill's directory, from the user's working directory (so
   their files and `result.json` stay there), with the options the file needs. Check the validation block
   first with `--bootstrap 0`, then run the default for the reported numbers:

   ```bash
   python3 <skill-dir>/scripts/maxdiff_analysis.py responses.csv --bootstrap 0
   python3 <skill-dir>/scripts/maxdiff_analysis.py responses.csv --segment-col plan
   python3 <skill-dir>/scripts/maxdiff_analysis.py export.csv --design design.csv --choice-coding position
   python3 <skill-dir>/scripts/maxdiff_analysis.py responses.csv --shown-col set_items --json > result.json
   ```

   The bootstrap refits the logit per replicate and per segment; when it will take more than 20 seconds
   the script says so on stderr. Run long jobs in the background rather than against a tool time-out.
3. **Read the validation block before the scores.** Report sets read, valid and excluded with the count
   per reason. Many exclusions for one reason usually mean a wrong column mapping or coding: fix and
   rerun before interpreting anything. Above 50% excluded the script stops (exit 2) and says why; use
   `--allow-exclusions` only after confirming the exclusions are real.
4. **If the script exits with code 3** (no finite logit estimate), either some items were never shown
   in a set with the others (the message lists the groups: there is no overall ranking, report each
   group's counting scores separately), or an item was always worst or always best (separation). Rerun
   with `--no-logit` and present counting scores only. Do not substitute numbers of your own.
5. **Check counts against the logit.** They usually agree, but close items can swap between counts and
   logit, or between models, even on a balanced design; when they disagree, lead with the logit and say
   which model. If the script warns that items were not shown equally often, lead with the logit columns.
   In the JSON, an item with a high `best_rate` and a high `worst_rate` divides the sample: say so and cut
   by segment rather than reading its middling score as indifference.
6. **Read the fit line.** Compare RLH with the chance level printed next to it. There is no cut-off for
   "good" fit; a pooled model of people who disagree has a modest RLH. A value at chance means the
   answers carry no shared order (or the coding is wrong).
7. **Use the tested differences, not overlapping intervals.** The "Adjacent items" lines give the
   bootstrap interval of the difference between neighbours. If it includes 0, the two items are not
   separated by this data: report them as neighbours not separated. "Reversed" means the tested metric
   (counting score) orders them the other way from the ranking (share): say so. Only neighbours are
   tested; two items that are each close to a third may still differ from each other, so do not call a
   run of items tied. The "Difference" tables do the same between segments.
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
   degrees of freedom (for `--model marginal`: no chi-square; say the likelihood is composite).
5. **Segments** (if cut): each segment's table with its base and a flag when below the minimum, then
   the difference table per pair of segments, marking intervals that exclude 0. Say that among many
   items some intervals exclude 0 by chance, and that a noisier segment has flatter shares.
6. **Method line**, copied from the script's `method` block: counting formula, logit model, share
   formula, interval method with replicates and seed, "aggregate estimates; hierarchical Bayes not
   run; not anchored".
7. **Warnings**, copied from the script, in plain words.

With `--no-logit` (or after exit 3), drop the Utility and Share columns, the average share and the model
fit, rank by B-W score, and say why there is no logit.

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

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `responses_read` (ids, status, type), `response_get_details` (each response's `rawAnswer`: the sets shown and the picks; reshape as in [input formats](references/input-formats.md), "QuestionPunk"). Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type and completion status (exclude synthetic and test responses), and reconcile the row count before computing. Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
