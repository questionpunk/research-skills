---
name: survey-sample-size
description: "Calculates survey sample size: how many responses are needed for a margin of error and confidence level, a power analysis to compare two groups (minimum detectable difference), NPS margins and comparisons, minimum subgroup sizes, MaxDiff and conjoint rules of thumb, invitations from a response rate, and how many interviews reach saturation. Use for \"how many people do I need\", \"what's the margin of error on 150 responses\", \"is n=80 enough\" or \"is my sample big enough to be statistically significant\"."
license: MIT
metadata:
  version: "0.2.1"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "survey-design"
---

# Survey sample size

Answers "how many responses do I need" and "is the n I have enough", with the assumption behind every
number. All arithmetic is done by [`scripts/survey_sample_size.py`](scripts/survey_sample_size.py)
(Python 3.9+, standard library only). Run it; do not redo the math in the conversation.

## When to use

Use when the user asks:

- "How many people do I need to survey?" / "What sample size for ±5% at 95% confidence?"
- "What's the margin of error on 150 responses?" / "Is n=80 enough?"
- "Is my sample big enough to be statistically significant?" / "How many per group to see a difference?"
- "What difference can I detect with 200 per group?" / "What power do I have with 120 and 300?"
- "I want results by segment, how many in total, and what quotas?"
- "A leads B by 5 points in my survey, is that outside the margin of error?"
- "How many invitations do I have to send to get 400 completes?"
- "How many respondents for a MaxDiff or a conjoint?" / "How many responses for a reliable NPS?"
- "How many interviews are enough?" / "Have we reached saturation?"

Do not use for:

- Testing whether a difference in collected data is significant, or crosstabs: not covered (for NPS data,
  `nps-analysis`); say so and name the test.
- Building the MaxDiff design itself (item lists, sets): use `maxdiff-design`. A conjoint design is not
  covered. This skill only sizes the sample for them.
- Deciding what to ask and of whom: use `survey-from-decision`; for interview guides, `ai-interview-guide`.
- Coding the interviews: use `open-ended-coding`; this skill only checks saturation from its code counts.
- Out of scope, say so and name the right method: paired or before/after comparisons of the same
  respondents (McNemar's test, paired t test), website A/B tests with sequential stopping, clinical trials,
  cluster-randomised or multi-arm designs beyond a Bonferroni split, usability-test problem discovery
  (1 − (1 − p)^n), and shares of two answers to one multi-select question.
- Power computed after the study from the observed difference: do not compute it; it only restates the
  p-value. Report the confidence interval instead.

A skill named here may not be installed. If it is missing, say so, name the method the request needs,
and do not stretch this skill to cover it.

## What to ask for

Pick the mode from the request, fill everything else from the defaults, and state the defaults in the
answer. Ask one question only when the mode's required input is missing and cannot be inferred.

| Mode | Needed | Defaults |
|---|---|---|
| Percentage, margin of error (`proportion`) | target margin, or the n (and count) to check | margin 0.05 (pass it: the script needs `--margin` or `--n`), p 0.5, confidence 0.95, large population, design effect 1 |
| Mean, margin of error (`mean`) | SD and margin in scale units | confidence 0.95. No default SD: take it from a pilot or an earlier wave; without one, size the top-2-box share with `proportion` instead |
| Two groups (`compare`) | the two percentages (or a lift), or the difference in SDs (d) | alpha 0.05 two-sided, power 0.80, equal groups, one comparison, pooled variance, no continuity correction |
| What an n supports (`check`) | n | p 0.5, confidence 0.95, alpha 0.05, power 0.80, large population |
| Net Promoter Score (`nps`) | target margin or difference in NPS points as a proportion (0.05 = ±5 points), or an n | promoter and detractor shares from an earlier wave, else variance 0.67; confidence 0.95; for `--diff`: alpha 0.05 two-sided, power 0.80 |
| Gap between two answers (`gap`) | the two shares of one single-select question, and n | confidence 0.95 |
| Subgroups (`subgroups`) | each reported subgroup's share | minimum base 100 (200 for MaxDiff or conjoint), or a target margin |
| Invitations (`invites`) | completes and response rate | incidence, completion rate, deliverability 1.0; removal rate 0. No default response rate |
| MaxDiff (`maxdiff`) | number of items | 4 per set (3 for 6 or 7 items, as `maxdiff-design`), sets = 3K/k, 1 subgroup. If a design exists, pass its `--per-set` and `--sets` |
| Conjoint (`conjoint`) | tasks, alternatives (not counting None), levels per attribute | main effects, 1 subgroup |
| Interviews (`interviews`) | number of distinct segments | 1 fairly homogeneous group, narrow aim, goal "codes" |
| Saturation (`saturation`) | new codes per interview, in order | base 4, run length 2, threshold 0.05 |

If the user gives no goal at all ("how many do I need?"), do not ask: answer with the `proportion`
defaults (±5 points, 95%) and `--table`, and say what would change the answer (subgroups, a comparison, a
small population). If they give only an n ("is 80 enough?"), run `check`.

Give proportions, not percentages, to the script (0.05, not 5).

When the result will be published as a margin of error, ask how respondents were selected unless it is
clear; meanwhile give the number under the stated assumption. For an opt-in sample (a panel such as
Prolific, an open link sent to the whole customer list, a social post) pass `--opt-in`: the statement then
reads as a simple-random-sample benchmark, not the precision of the actual sample. A random sample drawn
from a complete list is not opt-in (its non-response still is a caveat).

## Steps

1. **Name the claim the survey must support.** One overall percentage or mean, a comparison between two
   groups or waves, results per subgroup, or a choice exercise. The strictest claim sets n. If several
   apply, run each and take the largest.
2. **Run the matching subcommand** with `--json`, by the script's path inside this skill's directory:

   ```bash
   S="<skill-dir>/scripts/survey_sample_size.py"
   python3 "$S" proportion --margin 0.05 --table --json        # n for ±5 points, and n at other margins
   python3 "$S" proportion --margin 0.05 --population 2000 --weight-cv 0.5 --json
   python3 "$S" proportion --n 150 --json                       # margin of error on 150 responses
   python3 "$S" proportion --n 400 --opt-in --json              # opt-in panel: benchmark wording
   python3 "$S" proportion --n 12 --x 3 --json                  # 3 of 12: Wilson interval, not a ± margin
   python3 "$S" check --n 80 --share under35=0.3 over35=0.7 --json   # is n=80 enough? what it supports
   python3 "$S" mean --sd 1.1 --margin 0.2 --json
   python3 "$S" compare --p1 0.50 --p2 0.60 --table --json      # n per group; add --lift 0.2 instead of --p2
   python3 "$S" compare --p1 0.50 --p2 0.60 --n 150 --json      # power with 150 per group
   python3 "$S" compare --p1 0.50 --n 150 --json                # smallest detectable difference
   python3 "$S" compare --p1 0.50 --p2 0.60 --ratio 2 --comparisons 3 --json   # unequal groups, three comparisons
   python3 "$S" compare --d 0.3 --json                          # two means, d = difference / SD
   python3 "$S" compare --diff 0.4 --sd 1.2 --json              # two means in scale units
   python3 "$S" compare --p1 0.50 --p2 0.60 --n 120 --n2 300 --json   # power with groups of 120 and 300
   python3 "$S" gap --p1 0.42 --p2 0.37 --n 600 --json          # A vs B in the same sample
   python3 "$S" nps --promoters 0.4 --detractors 0.2 --margin 0.05 --table --json   # ±5 NPS points; ±3/5/7/10 rows
   python3 "$S" nps --diff 0.10 --table --json                  # n per group for a 10-point change; 5-20 point rows
   python3 "$S" subgroups --share smb=0.5 mid=0.35 ent=0.15 --margin 0.10 --json   # quota table
   python3 "$S" invites --completes 667 --response-rate 0.12 --incidence 0.6 --completion-rate 0.85 --removal-rate 0.1 --json
   python3 "$S" maxdiff --items 20 --per-set 4 --sets 15 --subgroups 2 --json
   python3 "$S" conjoint --tasks 12 --alternatives 3 --levels 3,4,5 --json
   python3 "$S" interviews --segments 3 --json                 # --method focus-groups, --goal meaning
   python3 "$S" saturation --new-codes 14,9,6,5,3,2,1,0 --json   # or --file codes.csv
   ```

   `python3 "$S" SUBCOMMAND --help` lists every option; `--opt-in`, `--population`, `--deff`, `--weight-cv`
   and `--icc` with `--cluster-size` go on any subcommand that takes them. Bad input exits with status 2 and a one-line
   message; fix the input, do not work around it.
3. **Adjust for the sample you will really get.**
   - Population under about 20 times the n: pass `--population` (finite population correction; also on
     `check`). If everyone in it responded, the script reports a census with no sampling error.
   - Weighted data: `--weight-cv` (coefficient of variation of the weights), or `--deff` if known.
     Clustered sampling for a descriptive estimate (classes, stores, teams): `--icc` with
     `--cluster-size`. Assigning whole clusters to the arms of an experiment is out of scope.
   - Results per subgroup: run `subgroups` with every reported subgroup's share and use its quota table.
   - A subgroup comparison that must detect a stated difference: run `compare` (with `--ratio` when the
     groups differ in size); it usually asks for more than the minimum base.
   - Several comparisons (three or more groups, several key questions): pass `--comparisons m`. Say that
     the Bonferroni split is conservative.
4. **For "is n enough"**, run `check`, or the reverse form of the matching command (`--n`). Say what the n
   supports: the margin of error, the smallest detectable difference, or the power for a difference the
   user names. Answer yes or no against a stated need; if none is stated, give the numbers and let the
   user judge. When the script prints a Wilson interval, quote the interval, never a ± figure. For a rare
   outcome (under 10 expected in the smaller category) the planned n keeps the Wilson interval within the
   target; the statement says so.
5. **Turn completes into invitations** with `invites` when the user recruits from a list. Use their own
   past response and removal rates; if they have none, show two scenarios rather than inventing a rate.
6. **MaxDiff and conjoint:** report the result as a rule of thumb and name the source. MaxDiff: at least
   300 respondents in total and 200 per subgroup reported, raised above 30 items (doubled at 60; the same
   rule `maxdiff-design` and `maxdiff-analysis` use); for a sparse design (each item under 2 times per respondent) also 500 item
   exposures per group, preferably 1000. Conjoint: 500 representations per level, 1000 preferred, and at
   least 300 respondents (200 per compared subgroup). Those
   500/1000 figures count exposures or representations, not respondents. For a high-stakes study
   recommend simulating the design.
7. **Interviews and focus groups:** run `interviews` for the planning range and present it as guidance per
   segment, not a requirement. During fieldwork run `saturation` on the count of new codes per interview
   and report its statement (for example "6+2"). Never attach a margin of error or a percentage to
   interview counts. The evidence behind the ranges:

   | Source | Finding | Applies when |
   |---|---|---|
   | Hennink and Kaiser 2022 (review of 23 articles) | 9–17 interviews or 4–8 focus groups reached saturation | Homogeneous group, narrow aim |
   | Guest, Bunce and Johnson 2006 | Saturation within 12 interviews; main themes visible by 6 | Homogeneous group, structured guide |
   | Hennink, Kaiser and Marconi 2017 | 9 interviews to hear the range of issues; 16 to 24 to understand them | Depth of meaning is the goal |
   | Guest, Namey and Chen 2020 | Base of 4, runs of 2, stop when a run adds ≤5% new codes over the base | Checking saturation during fieldwork |

8. **Build the answer from the script's output**: the headline result, its `statement` (paste it
   unchanged as the rationale sentence), the assumptions, and a `--table` run for "what changes the
   number" where the mode has one.

### If the user's number differs from another calculator

Say why rather than changing the answer: two-proportion formulas (pooled, unpooled, arcsine) differ by
about 1–2% near 0.5 and by more far from it, some A/B calculators use the baseline variance only and round to nearest (pass
`--variance baseline` to reproduce them), and some survey calculators use z rounded to two decimals.
The table of worked differences is in [`references/sources.md`](references/sources.md), "Why other
calculators give slightly different numbers".

## Output

Always this shape:

```markdown
**Answer:** <n> <completes | per group | interviews per segment>, to <the claim it supports>.
<Other modes: "**Answer:** n = <n> gives <±margin | interval | power x%>" for a reverse run; "**Answer:**
saturation <reached at 6+2 | not reached after n interviews>" for saturation.>

| Question | Method | Key inputs | Result |
|---|---|---|---|
| <e.g. Overall percentage within ±5 points> | <subcommand and formula name> | <p, confidence, N, deff> | <n, rounded up> |
| <one row per calculation run> | | | |

**Rationale to paste:** <the script's `statement`, unchanged>

**Assumptions**
- <each assumption the script printed, including every default used>

**What changes the number**
<the script's `--table` rows, or two or three extra runs: other margins, differences, a design effect>

**Quotas / field plan** (if subgroups are reported or the user recruits from a list)
- <quota table rows: subgroup, expected n, margin>
- Invitations: <n> at <response rate>, <incidence>, <completion rate>, <removal rate>

**Caveats**
- <sampling caveat: random vs opt-in (with `--opt-in`, the benchmark wording); rule of thumb vs calculation; quota needed for subgroups>

Sources: <the sources the script printed>
```

For an "is n enough" question the Answer line reads: `**Answer:** Yes | No: n = <n> gives <margin, interval
or detectable difference>; <need> takes <n required>.` With no stated need, drop "Yes | No" and give the
numbers.

## Checks before answering

- Did every number come from the script, not from mental arithmetic?
- Is every n rounded up, and is it clear whether it is total, per group or per subgroup?
- Are the defaults stated (p = 0.5, 95% confidence, alpha 0.05, power 80%)?
- If results will be reported by subgroup, was n sized on the smallest subgroup, not the total?
- If the question was about a difference between groups, was `compare` used, not `proportion`?
- If the two numbers compared come from the same respondents answering one question, was `gap` used?
- If the same respondents are measured twice, does the answer say this skill does not size paired tests?
- If the count in the smaller category is under 10, is the answer an interval or a raw count, not a ± margin?
- If the data will be weighted or clustered, is a design effect applied?
- Is the population small enough to need `--population`, and was it passed?
- If the sample is opt-in (a panel, a customer list, a social post), was `--opt-in` passed, and does the
  answer call the margin a simple-random-sample benchmark rather than this sample's precision?
- For a two-group comparison of proportions, does the answer name the formula variant (pooled variance,
  no continuity correction, unless changed)?
- For an NPS, was `nps` used (not `proportion`), with the variance it assumed stated?
- If several comparisons are planned, was `--comparisons` passed, and is the correction called conservative?
- Is power quoted only for a difference assumed in advance, never for the observed one?
- Are MaxDiff and conjoint results labelled as rules of thumb, with 500 called a minimum number of
  exposures (not respondents), and the MaxDiff design's own items per set and sets used?
- For interviews, is the answer a range per segment with its source, labelled guidance, with no
  percentages or margins?
- Were completes converted to invitations when the user has to recruit?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `prolific_count_participants` (pool size for given screener ids, not a promise of completes), `prolific_study_calc_cost` (an estimated quote), `responses_get_counts` (completes so far; filter to completed, real responses and apply the quality exclusions before comparing with the target n). None creates a study. Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
