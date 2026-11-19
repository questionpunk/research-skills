---
name: maxdiff-design
description: "Builds or checks a balanced MaxDiff (best-worst scaling) experimental design: items per set, sets per respondent and versions, exact BIBDs from cyclic, affine-plane and complete constructions or a balanced search otherwise, with checks on item frequency, pair frequency, position balance and connectivity, plus respondent-facing question wording. Use for \"MaxDiff study\", \"best-worst scaling\", \"feature prioritization survey\", \"which features matter most\", \"rank messages or claims\", \"how many MaxDiff sets\" or \"check my MaxDiff design\"."
license: MIT
metadata:
  version: "0.2.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "pricing-research"
---

# MaxDiff design

Turns a list of items into a fieldable MaxDiff (best-worst scaling) exercise: items per set, sets per
respondent and versions, the design as a CSV with checks on item frequency, pair frequency, position balance
and connectivity, and the wording respondents see. Exact BIBDs come from three constructions (cyclic
difference sets, affine planes, all subsets); other sizes get a seeded balanced search, which may or may not
reach an exact design.

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
| Products described by attributes and levels (plan x price x feature) | Not covered: say it needs a choice-based conjoint design |
| "What should we charge", acceptable price range | `van-westendorp-analysis` |
| How many respondents for a given margin of error | `survey-sample-size` |
| Fewer than 6 items | One ranking question; no design is needed. Say so and stop |

A skill named here may not be installed. If it is missing, say so, name the method the request needs,
and do not stretch this skill to cover it.

## What to ask for

Start from what the user gave. Ask one question only if there is no item list, no item count and no
design to check: "Which items should respondents compare? Paste them one per line." Everything else has a
default.

| Input | Default |
|---|---|
| Items | Required. If the user only wants the plan for N items, use `--items N` |
| What is measured | Importance ("most important" / "least important") |
| Items per set | 4; 3 when the list has 6 or 7 items (`survey-sample-size` uses the same default). Sawtooth Lighthouse advises 4 or 5, Discover 3 to 5 |
| Sets per respondent | 3 x items / items per set, rounded up (each item shown about 3 times) |
| Versions | 10 (Displayr: enough to average out order and context effects). Sawtooth generates 300 and asks for at least 4 on paper. If respondents will be clustered or compared with each other, ask how they will be scored: Displayr prefers 1 version (versions add differences that are not preference), Sawtooth fields many versions and scores individuals with HB. Record the choice |
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
3. **Generate the design.** Run the script by its path inside this skill's directory, from the user's
   working directory, so the items file and `design.csv` stay with the user's files:

   ```bash
   python3 <skill-dir>/scripts/maxdiff_design.py items.txt --out design.csv
   ```

   The defaults are 4 per set (3 for 6 or 7 items), 3 x items / per set sets, 10 versions and seed 1; pass
   `--per-set`, `--sets`, `--versions` or `--seed` only to change one. For a plan without item text, use
   `--items N` in place of the items file. Options: `--respondents N` (total exposures per
   item against the sample-size rules), `--seconds-per-set SEC` (length estimate from a pilot timing),
   `--wide` and `--item-id` (other CSV layouts), `--json`. The script is
   [`scripts/maxdiff_design.py`](scripts/maxdiff_design.py) (Python 3.9+, standard library only). Run it;
   do not build sets or count frequencies in the conversation.
4. **Read the report.** Exit code 0 means no criterion failed. For every WARN line decide with the design
   guide whether to change a number (sets, items per set, versions, seed) and rerun, or to accept it and
   say why. If a note says an exact BIBD exists with another number of sets, offer it when the length is
   acceptable. When the Method line says the counting conditions hold but the search found no exact BIBD,
   do not call the design impossible: near-balance is enough. Never field a design with a FAIL line.
5. **To check an existing design** instead of generating one:

   ```bash
   python3 <skill-dir>/scripts/maxdiff_design.py --check design.csv items.txt
   ```

   It reads `version,set,position,item` and the wide form `version,set,item1..itemk` (labels, or item
   numbers when the items file is given; the number in `item3` is the position). A respondent column
   (`respondent`, `respondent_id`) is read as the version, one per respondent. Comma, semicolon or tab
   separators and an Excel `sep=` first line are detected; `--delimiter` sets another. The items file is optional; with it, an item
   missing from the design is caught. Exit code 1 means a criterion failed, 2 means the file is not a
   design.
6. **Write the respondent text.** Default, to adapt:
   - Introduction: "In the next [S] questions you will see short lists of [items]. In each list, choose the
     one that is most important to you and the one that is least important to you when [context]. You will
     see the same [items] several times in different combinations. That is intended."
   - Question, identical in every set: "Which of these is most important to you, and which is least
     important, when [context]?" with a progress cue ("Question 3 of 12").

   Other label pairs (most/least appealing, most/least likely to make me buy), layout rules and anchor
   questions are in [references/question-wording.md](references/question-wording.md). An anchor changes
   the analysis, and `maxdiff-analysis` does not score anchors: before fieldwork, name the tool that will
   (for example Sawtooth Lighthouse Studio's anchored MaxDiff), or leave the anchor out.
7. **State the sample pointer:** at least 300 respondents in total and 200 in each subgroup reported
   separately, raised in proportion above 30 items; with a sparse design (each item under 2 times per
   respondent), also 500 to 1000 exposures per item in each group. `survey-sample-size` and
   `maxdiff-analysis` use the same rule. With `--respondents`, quote the script's Sample line. For a
   margin of error hand over to `survey-sample-size`, passing this design's items per set and sets.

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
| <one row per Criteria line of the report, in its order and with its wording> | <the numbers on that line> | PASS/WARN/FAIL |

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
- design.csv (version, set, position, item): <rows> rows, <V> versions. This long form is what
  `maxdiff-analysis --design` reads; `--wide` is only for tools that import that layout
- Command to reproduce: `python3 <skill-dir>/scripts/maxdiff_design.py ...`

## Limits
- Sample: <pointer, or the script's Sample line>.
- Scores will be relative to this list <unless an anchor is used>.
- Record per respondent: the version, and the best and worst item of every set.
- <Any limit from the warnings: pooled analysis only, one version, long exercise>.
- Analysis: `maxdiff-analysis` reads the long design.csv plus the two choices (not anchor answers).
```

For a `--check` request, replace "MaxDiff plan" with "Design check" (same tables, numbers read from the
file, no seed), give the verdict in the first line ("meets the criteria" or "does not, because ..."), list
one fix per FAIL or WARN, and leave out "Respondent wording" and the reproduce command unless the user
asked for them. For an `--items N` plan, leave out "Sets of version 1" item text and the wording until the
items are known. Thresholds and their sources: [references/sources.md](references/sources.md).

## Checks before answering

- Did the script produce every number in the answer (no frequencies counted by hand)?
- Is the exit code 0, with no FAIL line in the report?
- Is items per set at least 3 and at most half the number of items?
- Is each item shown at least 3 times per respondent? If not, does the answer plan pooled scores or a
  sample of 600 or more, and say individual-level scores will be weak?
- Is every WARN line either fixed or listed under "Warnings accepted" with a reason (the Result line counts
  them)?
- Is the number of versions explained (10 by default, more when the tool assigns them, and for
  segmentation the choice between 1 version and many versions with HB, with the reason)?
- Do the items vary in position (largest position gap 0 or 1), not a fixed or alphabetical order?
- Is every version connected? If only the whole design is, does the answer limit the analysis to
  pooled scores?
- When generating: are the seed and the exact command in the answer, and is `design.csv` saved for the analysis?
- Do the two labels name opposite ends of one dimension, and is the wording the same in every set?
- Does the introduction tell respondents that items repeat on purpose?
- Does the answer avoid calling scores absolute when no anchor question is planned?
- Are the items comparable, without overlaps, and were any edits to the user's list shown to them?
- Is the length estimate labelled as an assumption unless the user timed a pilot?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `survey_get` (current version and questions), `question_create` (adds the `max_diff` question; payload in [references/questionpunk-max-diff.md](references/questionpunk-max-diff.md)). It draws its own sets per respondent (3 to 6 items per set, at most 50 sets), so `design.csv` is not uploaded and its diagnostics describe the local design only. Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
