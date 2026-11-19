---
name: gabor-granger-analysis
description: "Estimates a demand curve and the revenue- or profit-maximizing price from Gabor-Granger purchase-likelihood answers: take rate at each tested price with confidence intervals, a monotonicity check per respondent, a monotone demand curve, arc price elasticity, revenue and profit curves with a bootstrap check on the optimal price, and optional user-supplied weights for stated-intent overclaim. Reads full, adaptive or monadic price ladders. Use for \"Gabor-Granger\", \"price ladder results\", \"demand curve from survey\", \"revenue-maximizing price\", \"price test results\" or \"would you buy at $X\" data."
license: MIT
metadata:
  version: "0.1.2"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "pricing-research"
---

# Gabor-Granger analysis

Turns "would you buy it at this price?" answers into a demand curve, a revenue (or profit) curve and the
tested price that maximizes it, with intervals and a bootstrap check on how stable that price is.
[`scripts/gabor_granger_analysis.py`](scripts/gabor_granger_analysis.py) (Python 3.9+, standard library only)
does the arithmetic; run it, do not redo the math in the conversation. Run it by its path inside this skill's
folder (`python3 <skill-dir>/scripts/gabor_granger_analysis.py`); examples below write `scripts/...` for short.
Formulas, thresholds and sources: [`references/sources.md`](references/sources.md).

The result ranks the tested prices by **stated** intent. It is not a sales forecast and cannot pick a price
between two tested prices.

## When to use

- "Analyze our Gabor-Granger / price ladder results", "which price maximizes revenue", "demand curve from
  this survey", "would you buy it at $X" answers at several prices.
- A monadic price test (each respondent saw one price) or an adaptive ladder (start price random, up after
  yes, down after no).
- "What price maximizes profit if each unit costs $X?"

Do not use it for:

| Request | Use instead |
|---|---|
| Four price questions (too cheap, cheap, expensive, too expensive) | `van-westendorp-analysis` |
| Price traded off against features or competitors | `conjoint-design`, then `conjoint-analysis` |
| How many respondents to recruit | `survey-sample-size` |
| Speeders, duplicates, straight-liners | `survey-data-cleaning` first |
| Pricing strategy with no survey data | Not this skill |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and
do not stretch this skill to cover it.

**No data yet:** give the design below and stop. Never invent or simulate responses. Design: one clearly
described product and billing period; 4 to 7 prices spanning the plausible range (include one most people
would accept and one few would); ask "Would you buy [product] at [price]?" as yes/no or as a 5-point scale
from "definitely would buy" to "definitely would not buy"; randomize the start price (adaptive) or the price
order, or assign one price per respondent (monadic) to limit anchoring.

## What to ask for

Ask only what blocks the run: the direction of bare numeric codes, which columns are prices, how the prices
were asked when the script stops on it (`--design`), and for counts whether one group answered every price.
Then, only if unclear and it matters: currency, billing period, unit cost.

| Input | Default |
|---|---|
| File | One row per respondent, a column per price (`$10`, `price_10`, `p10`; Qualtrics question text with one price also works). Otherwise `--price-cols`, `--long`, `--max-price-col` or `--counts` |
| Answers | yes/no or 1/0 read directly; 5-point intent labels read by their words; bare 1-5 codes need `--intent-scale` (highest intent first; most tools: `5,4,3,2,1`); two codes (1 = yes, 2 = no) need `--intent-scale 1,2`; 7-point or unipolar likelihood labels need `--intent-scale 'Extremely likely\|Very likely\|...'` (labels, highest first, separated by `\|`). Never guess the direction |
| "Would buy" | Top-2 box (definitely + probably); `--buy-box 1` for top box only. On a 7-point scale say which box the user wants |
| Design | `--design auto` reads it from the answers and stops when most respondents answered one price but some answered several; then ask and pass `full` (blanks are skips), `adaptive` (prices not asked are filled) or `monadic` |
| Counts | `--counts-sample same` when one group answered every price (most published tables: one base for all prices), `separate` when each price had its own sample. Required |
| Calibration | None: output is labelled stated intent. `--intent-weights` only with weights the user supplies and can source |
| Unit cost | None: revenue index. With a cost, `--unit-cost` maximizes profit. If the user gives a cost but asks for the revenue-maximizing price, run both and report both |
| Inconsistent respondents (buy at a higher price, not a lower) | Excluded and counted; `--inconsistent keep` to keep |
| Prices not asked (adaptive ladder) | Filled from monotonicity and counted (`n_observed` = answers given); never for monadic data or with `--intent-weights`; `--no-impute` to turn off |
| Segments | None; `--segment COL` if the user wants a split |
| Bootstrap | 1,000 replicates, seed fixed; `--bootstrap 0` to skip |

## Steps

1. **Look at the file.** Read the header and a few rows. Identify the shape (wide, long, highest price,
   counts), the price columns, how answers are written, and any segment column.
2. **Run the script.**

   ```bash
   python3 scripts/gabor_granger_analysis.py answers.csv --json
   python3 scripts/gabor_granger_analysis.py answers.csv --intent-scale 5,4,3,2,1 --unit-cost 6 --segment plan --json
   python3 scripts/gabor_granger_analysis.py answers.csv --long --price-col price --answer-col buy --id-col rid --json
   python3 scripts/gabor_granger_analysis.py answers.csv --max-price-col highest_ok --prices 10,15,20,25,30 --json
   python3 scripts/gabor_granger_analysis.py --counts 10:190,15:164,20:118,25:74,30:36 --base 200 --counts-sample same --json
   ```

   Flag syntax: `--price-cols "q1=9.99,q2=14.99"` (COLUMN=PRICE); `--counts PRICE:BUYERS` with `--base N`, or
   `PRICE:BUYERS/N` per price when bases differ; `--intent-weights 0.7,0.5,0.3,0.1,0` (one probability per
   scale point, highest first); `--long` without `--id-col` means each row is its own respondent (monadic).
   Lists with a thousands separator or a decimal comma use `;` between items (`--prices "999;1,299;1,499"`,
   `--counts "999:120;1,299:85"`): `1,299` is one price. Other flags: `--delimiter`, `--skip-rows N`
   (Qualtrics rows are detected), `--decimal comma`, `--curves-csv FILE` (never the input), `--confidence 0.9`.
   Without `--json` it prints a readable report.
3. **If it exits with code 2, fix the cause, not the data.** Unreadable answers above 5%, numeric codes with
   no direction, unknown price columns, duplicate headers and cut rows all stop it. Ask the user rather than
   editing answers; `--allow-unreadable` only after you have looked at what is being dropped.
4. **Check the read.** Price mapping, respondents read / excluded / analysed, imputed cells, and the answer
   rule printed in the first line, and the design line. Over 10% inconsistent is a review flag of this skill,
   not a published rule: check the coding and price order, rerun with `--inconsistent keep` and say whether
   the optimum moves (price read as quality is a real cause).
5. **Read the curve before the optimum.** Report the take rate with its interval at each price, where the
   steepest drop is (most negative arc elasticity), and whether the monotone fit pooled any prices.
6. **Read the optimum with its stability.** The bootstrap line says how often each price wins. Under 50% for
   the named price, report the range of prices that win, not one price. An optimum at the lowest or highest
   tested price means the ladder did not bracket it: say so and suggest testing beyond it. If the script
   says the raw (unpooled) curve peaks elsewhere, report both.
7. **Write the answer** in the shape below. Copy numbers from the script; do not recompute or re-round.

## Output

```markdown
## Gabor-Granger result: <product>, <currency> per <period>

**Respondents:** <read> read, <no answer> without a readable answer, <inconsistent> inconsistent (<excluded|kept>),
<analysed> analysed; <imputed> answers filled from the ladder. Design: <`design`>. Answer rule: <`answers`>.

| Price | n (answers given) | Would buy | <confidence>% interval | Monotone | Revenue index | <Profit index> | Arc elasticity to next |
|---|---|---|---|---|---|---|---|

**<Revenue|Profit>-maximizing tested price: <price>** (monotone take rate <x>%), the optimum in <y>% of
bootstrap samples (<other prices and their shares>).
<If the share is under 50%: "No single price is stable: <prices> each win in <shares>." If tied: "Tied at
<prices>." If no optimum is named: "No optimal price named: <reason>.">

**By segment** (only with --segment): one row per segment with its respondents, the smallest per-price n,
the optimum and its bootstrap share.

**Warnings:** <every entry of the top-level `warnings` and of each group's `warnings`, or "none">

**How to read this:** <2 to 4 sentences: the price range the data supports, where demand drops fastest, what
a unit cost or a wider ladder would change, and that stated intent overstates real purchase.>
```

"Would buy" is the raw take rate; its interval is Wilson for yes/no or top-N box answers and bootstrap with
`--intent-weights` (the level is `confidence` in the JSON); "Monotone" is the pooled take rate the revenue
index uses (`monotone_ci_low/high` is its bootstrap interval). With `--counts-sample separate`, "read" counts
answers, one per person per price. Leave out the profit column when no cost was given. Mark prices with
fewer than 100 answers given (`n_observed`) as directional.

## Checks before answering

- Did every number come from the script output for this file, with nothing recomputed?
- Was the intent scale direction confirmed (labels, codebook or the user), never assumed?
- Is the "would buy" rule stated (yes/no, top box, top-2 box, or user-supplied calibration weights)?
- Are excluded, inconsistent and imputed counts reported?
- Is the optimum called the best **tested** price, with its bootstrap share, and a range given when it is
  unstable?
- If the optimum is the lowest or highest tested price, does the answer say the ladder may not bracket it?
- Is the revenue index described as an index from stated intent, not revenue or sales?
- Are small bases (under 100 at a price, or a small segment) called directional?
- If a unit cost was used, is it stated as the user's figure?
- For a monadic test, is it clear each price was a separate sample?
- Was the data left unedited?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `question_create` (answer type `gabor_granger`, `itemDetails.prices`: 2 to 12 distinct positive prices; optional `price_order` `random` (default) / `ascending` / `descending`, `currency_prefix` (default `$`) and `currency_suffix`; the question text names the product; in the app it is "Price Ladder"), `responses_get_counts` (how many), `responses_read` (with `answerFormat: "numeric"` each answer is one `<price>: 1|0` line per price; write one row per respondent with a `price_<price>` column per price). Page `responses_read` with `nextCursor` until it is exhausted, filter to the intended response type and completion status (`responseType: "real"` drops synthetic responses; drop the study's own test submissions by their IDs or test markers too), and reconcile the row count with `responses_get_counts` before running the script; if they differ, report both. Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
