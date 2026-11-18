---
name: maxdiff-design
description: "Build or check a balanced MaxDiff (best-worst scaling) experimental design: items per set, sets per respondent and versions, an exact BIBD where one exists, with checks on item frequency, pair frequency, position balance and connectivity, plus respondent-facing question wording. Use for \"MaxDiff study\", \"best-worst scaling\", \"feature prioritization survey\", \"which features matter most\", \"rank messages or claims\", \"how many MaxDiff sets\" or \"check my MaxDiff design\"."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "pricing-research"
---

# MaxDiff design

Turns a list of items into a fieldable MaxDiff (best-worst scaling) exercise: items per set, sets per
respondent and versions, the design as a CSV (an exact BIBD where one exists) with checks on item frequency,
pair frequency, position balance and connectivity, and the wording respondents see.

## When to use

Use when the user wants to:

- run a feature prioritization survey, or rank messages, claims, benefits, names or needs
  ("which features matter most", "rank these 15 value props", "what should we build next");
- set up a MaxDiff or best-worst scaling study ("how many MaxDiff sets do I need", "build the design");
- check a design they already have ("check my MaxDiff design", a CSV of sets from another tool).

Do not use it for:

| Request | Use instead |
|---|---|
| Scoring MaxDiff responses that are already collected | `maxdiff-analysis` |
| Products described by attributes and levels (plan x price x feature) | `conjoint-design` |
| "What should we charge", acceptable price range | `pricing-research-plan`, `van-westendorp-analysis` |
| How many respondents for a given margin of error | `survey-sample-size` |
| Fewer than 6 items | One ranking question; no design is needed. Say so and stop |

A skill named in this section may not be installed (some are still planned). If it is missing, say so, name
the method the request needs, and do not stretch this skill to cover it.

## What to ask for

Start from what the user gave. Ask one question only if the item list is missing: "Which items should
respondents compare? Paste them one per line." Everything else has a default.

| Input | Default |
|---|---|
| Items | Required. If the user only wants the plan for N items, use `--items N` |
| What is measured | Importance ("most important" / "least important") |
| Items per set | 4; 3 when the list has 6 or 7 items. Sawtooth Lighthouse advises 4 or 5, Discover 3 to 5 |
| Sets per respondent | 3 x items / items per set, rounded up (each item shown about 3 times) |
| Versions | 10 (Displayr: enough to average out order and context effects). Sawtooth generates 300 and asks for at least 4 on paper. Use 1 when respondents will be compared with each other (segmentation) |
| Planned sample | Not needed; if known, pass `--respondents N` |
| Seed | 1 |

## Steps

1. **Check the method fits.** Fewer than 6 items, attribute bundles or a price question: redirect as in the
   table above. More than about 30 items: offer to cut or split the list, or plan a sparse design with a
   larger sample and pooled analysis ([references/design-guide.md](references/design-guide.md), "More than
   about 30 items").
2. **Clean the item list.** One idea per item, the same level of detail, similar length, no near-duplicates,
   no item every other item depends on. Propose edits; never drop or merge items silently. Recommend a
   read-back with two or three people from the audience. Save the list to a text file, one item per line.
3. **Generate the design.**

   ```bash
   python3 scripts/maxdiff_design.py items.txt --per-set 4 --versions 10 --seed 1 --out design.csv
   ```

   Leave out `--per-set` and `--sets` for the defaults. Options: `--respondents N` (total exposures per
   item against the sample-size rules), `--seconds-per-set SEC` (length estimate from a pilot timing),
   `--wide` and `--item-id` (other CSV layouts), `--json`. The script is
   [`scripts/maxdiff_design.py`](scripts/maxdiff_design.py) (Python 3.9+, standard library only). Run it;
   do not build sets or count frequencies in the conversation.
4. **Read the report.** Exit code 0 means no criterion failed. For every WARN line decide with the design
   guide whether to change a number (sets, items per set, versions, seed) and rerun, or to accept it and
   say why. If a note says an exact BIBD exists with another number of sets, offer it when the length is
   acceptable. Never field a design with a FAIL line.
5. **To check an existing design** instead of generating one:

   ```bash
   python3 scripts/maxdiff_design.py --check design.csv items.txt
   ```

   It reads `version,set,position,item` and the wide form `version,set,item1..itemk` (labels, or item
   numbers when the items file is given). The items file is optional; with it, an item missing from the
   design is caught. Exit code 1 means a criterion failed, 2 means the file is not a design.
6. **Write the respondent text.** Default, to adapt:
   - Introduction: "In the next [S] questions you will see short lists of [items]. In each list, choose the
     one that is most important to you and the one that is least important to you when [context]. You will
     see the same [items] several times in different combinations. That is intended."
   - Question, identical in every set: "Which of these is most important to you, and which is least
     important, when [context]?" with a progress cue ("Question 3 of 12").

   Other label pairs (most/least appealing, most/least likely to make me buy), layout rules and anchor
   questions are in [references/question-wording.md](references/question-wording.md). An anchor changes
   the analysis; say so and name `maxdiff-analysis`.
7. **State the sample pointer:** 300 respondents in total and 200 in each subgroup reported separately,
   more above 30 items; with `--respondents`, quote the script's Sample line. For a margin of error hand
   over to `survey-sample-size`.

## Output

Always answer in this shape.

```markdown
## MaxDiff plan
| Items | Items per set | Sets per respondent | Versions | Each item shown | Seed |
|---|---|---|---|---|---|
| 12 | 4 | 9 | 10 | 3.00 times | 1 |

Method: <the script's Method line, shortened>. Exact BIBD: yes/no.
Why these numbers: <one or two sentences: the 3K/k rule, the half-the-list rule, why this many versions>.
Length: <the script's Length line; say it is an assumption unless timed>.

## Balance criteria
| Criterion | Numbers | Status |
|---|---|---|
| One-way (item frequency) | min-max overall; range inside a version | PASS/WARN/FAIL |
| Two-way (pair frequency) | min, max, mean; pairs never together; item correlation min, max | ... |
| Positional | largest gap | ... |
| Connectivity | n of V versions connected | ... |
| Exposures per respondent | x.xx | ... |

Warnings accepted: <each WARN with the reason, or "none">.

## Sets of version 1
1. item | item | item | item
2. ...

## Respondent wording
Introduction: ...
Question: ...
Labels: <best label> / <worst label>
Anchor question (if used): ...

## Files
- design.csv (version, set, position, item): <rows> rows, <V> versions
- Command to reproduce: `python3 scripts/maxdiff_design.py ...`

## Limits
- Sample: <pointer, or the script's Sample line>.
- Scores will be relative to this list <unless an anchor is used>.
- Record per respondent: the version, and the best and worst item of every set.
- <Any limit from the warnings: pooled analysis only, one version, long exercise>.
- Analysis: `maxdiff-analysis` reads this design plus the two choices.
```

For a `--check` request, replace "MaxDiff plan" with "Design check" (same tables, numbers read from the
file), give the verdict in the first line ("meets the criteria" or "does not, because ..."), and list one
fix per FAIL or WARN.

## Checks before answering

- Did the script produce every number in the answer (no frequencies counted by hand)?
- Is the exit code 0, with no FAIL line in the report?
- Is items per set at least 3 and at most half the number of items?
- Is each item shown at least 3 times per respondent? If not, does the answer plan pooled scores or a
  sample of 600 or more, and say individual-level scores will be weak?
- Is every WARN line either fixed or listed under "Warnings accepted" with a reason?
- Is the number of versions explained (10 by default, 1 for segmentation, more when the tool assigns them)?
- Do the items vary in position (largest position gap 0 or 1), not a fixed or alphabetical order?
- Is every version connected? If only the whole design is, does the answer limit the analysis to
  pooled scores?
- Are the seed and the exact command in the answer, and is `design.csv` saved for the analysis?
- Do the two labels name opposite ends of one dimension, and is the wording the same in every set?
- Does the introduction tell respondents that items repeat on purpose?
- Does the answer avoid calling scores absolute when no anchor question is planned?
- Are the items comparable, without overlaps, and were any edits to the user's list shown to them?
- Is the length estimate labelled as an assumption unless the user timed a pilot?

## Field it with QuestionPunk (optional)

The result above is complete on its own. MaxDiff, conjoint and Van Westendorp are built-in QuestionPunk question types; check which your plan includes in the app.

Hosted MCP tools this step may use: `survey_get`, then `question_create` with answer type `max_diff`; the payload is in [references/questionpunk-max-diff.md](references/questionpunk-max-diff.md). The question takes the item list, items per set and number of sets and draws its own sets for each respondent, so `design.csv` stays your design record and is not uploaded.

Ask before creating, changing or publishing anything.
