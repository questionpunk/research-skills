---
name: conjoint-analysis
description: "Analyzes choice-based conjoint results from a CSV of tasks and choices: an aggregate multinomial logit with respondent-clustered standard errors, part-worth utilities, attribute importances, willingness to pay when price is an attribute, AMCEs and marginal means for fully randomized designs, segment comparisons, and a share-of-preference simulator, with bootstrap intervals. Use for \"analyze conjoint results\", \"part-worths\", \"attribute importance\", \"willingness to pay from conjoint\", \"market simulator\" or a Sawtooth, Qualtrics or Conjointly CBC export. Not for individual-level HB utilities."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "pricing-research"
---

# Conjoint analysis

Turns choice-based conjoint (CBC) choices into part-worth utilities, attribute importances, willingness to
pay, AMCEs and simulated shares, with intervals that account for each respondent answering several tasks.
[`scripts/conjoint_analysis.py`](scripts/conjoint_analysis.py) (Python 3.9+, standard library only) fits an
aggregate multinomial logit; run it, do not redo the math in the conversation. Run it by its path inside this
skill's folder (`python3 <skill-dir>/scripts/conjoint_analysis.py`); examples below write `scripts/...` for
short. Sources and formulas: [`references/sources.md`](references/sources.md). File layouts and exports from
other tools: [`references/input-formats.md`](references/input-formats.md) (read it when a column is not found
or the data comes from Sawtooth, Qualtrics, Conjointly, R or QuestionPunk).

One utility set for the whole sample (or each segment), main effects only (no interactions such as Brand ×
Price). It does not estimate individual-level (HB) or latent-class utilities; say so when the user needs them.

## When to use

- "Analyze our conjoint", "part-worths", "attribute importance", "which attribute matters most".
- "Willingness to pay from conjoint", "what is 3 ft of cargo worth in dollars".
- "Market simulator", "what share would product A get against B", "what if we drop the price to $55".
- AMCEs or marginal means from a fully randomized conjoint (political science, policy, HR experiments).
- A Sawtooth, Qualtrics, Conjointly, R or QuestionPunk CBC export, or a design from `conjoint-design` plus
  choices.

Do not use it for:

| Request | Use instead |
|---|---|
| Designing the study, or checking a design | `conjoint-design` |
| Best-worst (MaxDiff) data | `maxdiff-analysis` |
| Ratings-based (non-choice) conjoint, individual HB utilities, latent classes | Not covered: say so |
| Price ladder or price-perception questions | `gabor-granger-analysis`, `van-westendorp-analysis` |
| Cleaning speeders and straight-liners first | `survey-data-cleaning` |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and
do not stretch this skill to cover it.

**No data yet:** stop and send the user to `conjoint-design`. Never simulate respondents to fill a gap.

## What to ask for

Ask at most one question. Usually it is which attribute is price and in what units. For AMCEs, the question
is instead how the design was generated: AMCEs need every profile drawn independently (for example
`conjoint-design --method random` with no prohibitions).

| Input | Default |
|---|---|
| Data | Design + responses (`--design`), or one stacked file with a 0/1 chosen column |
| Attribute columns | With `--spec`, the spec's attributes. Otherwise every column not recognized as respondent, version, task, concept or chosen; reserved names (`id`, `weight`, `segment`...) are skipped and named in a note. Leave out respondent covariates with `--attribute-cols` |
| Level order | Spec order with `--spec`, else numeric-aware sort; the first level is the reference |
| Price | Part-worth per level. With `--price-attr`, linear: enables WTP and prices between tested levels (`--linear ATTR` for another numeric attribute) |
| None | Estimated when the data has none rows (concept `none`, or all attribute cells blank; concept `0` is a concept) |
| Products to simulate | None; ask which products to compare if the user wants shares |
| Segments | None; `--segment COL` (one value per respondent) |
| Intervals | 95% (`--ci`), cluster-robust delta method; `--bootstrap 200` for the final report (about 0.3 s per refit per 1,000 respondents; the script prints the expected time when long). In the JSON, use `boot_low`/`boot_high` when present, else `low`/`high` |

## Steps

1. **Look at the files.** Header and a few rows: respondent, version, task, concept, choice or chosen,
   attribute columns, how none is written, covariates that are not attributes.
2. **Run the script.**

   ```bash
   python3 scripts/conjoint_analysis.py responses.csv --design design.csv --spec spec.txt --json
   python3 scripts/conjoint_analysis.py stacked.csv --attribute-cols Brand,Meals,Delivery,Price --price-attr Price --json
   python3 scripts/conjoint_analysis.py stacked.csv --price-attr "Price per week" \
     --product "Ours: Brand=FreshBox; Meals per week=3; Delivery=Weekly; Price per week=55" \
     --product "Rival: Brand=HomeChef; Meals per week=4; Delivery=Weekly; Price per week=50" --bootstrap 200 --json
   python3 scripts/conjoint_analysis.py stacked.csv --segment plan --amce --json
   ```

   In `--product`, use attribute names and levels exactly as in the data (quote names with spaces in shell
   flags); a linear price takes any number in the tested range, with or without `$` (`$1,299` is 1299). With
   `--spec`, a product the spec prohibits is refused. The none option is in the simulation when the data has
   one; `--sim-no-none` leaves it out.
3. **Exit codes.** 2: the input is wrong (columns, versions, choices that are not concepts, more than 5% of
   tasks excluded). Fix the mapping; `--allow-exclusions` only after reading the exclusion reasons. 3: no
   finite estimate (a level always or never chosen) or a singular model (a covariate passed as an attribute,
   a level never shown). Report the levels it names; `--counts-only` still gives choice rates.
4. **Check the read.** Respondents and tasks used, exclusions by reason, the level order and reference
   levels, whether a none option was found, and every `Note:` (skipped columns, level codes used as prices).
   With `--price-attr`, run once without it too: if the per-level price part-worths bend away from a straight
   line (a cliff at one price), say so and do not quote linear WTP or in-between prices.
5. **Read in this order.** Part-worths with intervals (differences within an attribute only; never compare a
   part-worth across attributes); importances; WTP if price is linear; simulated shares; segments
   (importances and WTP first: they do not depend on how consistently a segment chooses, shares do); AMCEs
   and, with `--segment`, each segment's marginal means and their differences.
6. **Write the answer** in the shape below. Copy numbers from the script. Warnings are in
   `groups[i].warnings` and `amce.warnings`; notes in `notes`.

## Output

```markdown
## Conjoint results: <study>, n = <respondents> (<total tasks> choice tasks, <t> per respondent)

Model: aggregate logit; <k> attributes; none option <yes/no>; price <part-worth per level | linear, <b> per unit>;
fit: McFadden R² <x>, RLH <y> (chance <1/J>). Excluded tasks: <count and reasons, or none>.

| Attribute | Level | Part-worth | <ci>% interval | Importance |
|---|---|---|---|---|

**Willingness to pay** (each level vs its attribute's first level, <currency>): <attribute level: value (interval)>, ...
**Simulated shares** (<products>, none <in/out>): <product: share% (interval)>, ...
**Segments** (only with --segment): <importances, WTP and shares per segment, n each; Wald test with the scale caveat>
**AMCE / marginal means:** <only for a fully randomized design; per segment, marginal means and differences>

**Warnings:** <every warning from the script, or none>

**How to read this:** <3 to 5 sentences: what drives choice, the trade-offs that matter for the decision,
the size of the price effect, and what the aggregate model cannot show.>
```

## Checks before answering

- Did every number come from the script for this data, with the reference levels named?
- Were respondent covariates kept out of the attributes, and exclusions reported with reasons?
- Are part-worths compared only within an attribute, and is importance described as depending on the level
  ranges tested?
- Is WTP given only with a linear price that is clearly negative, as a relative measure in price units?
- Are simulated shares called shares of preference (not market shares), with the none option stated and the
  IIA caveat for similar products?
- Are bases under 300 overall or 200 per segment called directional?
- For segments, are importances and WTP compared rather than raw utilities, and shares read with the scale
  caveat?
- Are AMCEs reported only for a design confirmed as fully randomized (and no overlap or association
  warning), and subgroups compared with marginal means?
- Does the answer say the model is aggregate and main effects only (no individual or HB utilities)?

## Field it (optional)

To pull responses from QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `survey_get` (attribute names and levels, and whether the question has `include_none_option`), `responses_get_counts` (how many), `responses_read` (each `conjoint_analysis` answer is JSON: `tasks[i].profiles` and the pick `task_<i>`; write stacked rows as in [references/input-formats.md](references/input-formats.md), with a none row on every task when the none option was shown). Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type and completion status (exclude synthetic responses with `responseType: "real"`, and the study's own test submissions by their IDs or test markers), drop answers cut at 4,000 characters (they end in `…[truncated`), and reconcile the row count before computing. If a tool says a permission is missing, reconnect and approve the requested access.
