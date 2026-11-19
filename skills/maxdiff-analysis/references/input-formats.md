# MaxDiff analysis: input formats, options and JSON output

## Accepted shapes

| Shape | One row per | Shown items come from | Flag |
|---|---|---|---|
| 1. Long | respondent, set and shown item | the rows themselves | detected |
| 2. Wide, items in columns | respondent and set | `item1`, `item2`, ... or `--shown-cols` | detected |
| 2b. Wide, items in one cell | respondent and set | `--shown-col set_items` (split on `;`, or `--shown-sep`) | `--shown-col` |
| 3. Wide with a design file | respondent and set | `--design` | `--design` |
| 4. One row per respondent | respondent | `--design` | detected (no `set` column, `b1,w1,...` columns) |

In shapes 2 to 4 the best and worst cells hold the item label, or, with `--choice-coding position`,
the position of the chosen item in the set (1 = first). Position coding is common in Sawtooth-style
exports. It is never guessed: say so with the flag.

Where the shown sets come from depends on the survey tool. Tools that field a fixed design (you
uploaded or generated versions) need the design file. Tools that draw the sets per respondent at run
time, QuestionPunk's MaxDiff question among them, have no design file to join: the shown items must
come from the response export itself (shapes 1, 2 or 2b).

### 1. Long (one row per respondent, set and shown item)

```csv
respondent,segment,set,item,best,worst
r1,smb,1,Unlimited projects,1,0
r1,smb,1,Custom branding,0,0
r1,smb,1,Priority support,0,1
```

- `best` and `worst` must be `0` or `1`; `0.0`/`1.0` and `FALSE`/`TRUE` (any case) are read as 0 and 1
  with a note. Anything else (blank, `yes`) makes that set invalid; recode the file rather than letting
  the script guess.
- `set` only has to be unique within a respondent.

### 2. Wide with the shown items in columns (one row per respondent and set)

```csv
respondent,segment,set,item1,item2,item3,best,worst
r1,smb,1,Unlimited projects,Custom branding,Priority support,Unlimited projects,Priority support
```

- `best` and `worst` hold the item label exactly as written in the shown-item columns.
- The shown-item columns are those named `item1`, `item2`, ... (also `shown1`, `option_1`, ...): the
  number in the name is the position, whatever order the columns are in, and two columns with the same
  number stop the run. Or list them with `--shown-cols colA,colB,colC`, in position order. An empty cell
  means that position was not used.

### 3. Wide with a design file

Responses, one row per respondent and set:

```csv
respondent,segment,version,set,best,worst
r1,smb,1,1,Unlimited projects,Priority support
```

Design, as written by the `maxdiff-design` skill:

```csv
version,set,position,item
1,1,1,Unlimited projects
1,1,2,Custom branding
1,1,3,Priority support
```

Run with `--design design.csv`. The design must be in this long form (the `--wide` layout of
`maxdiff-design` is not read here). Its columns are `version,set,position,item` whatever the responses'
columns are called (if the design itself uses the names given with `--set-col` and so on, those are
used); its delimiter is read from its own header. Sets are matched on `(version, set)`. If the design has a single
version, the responses do not need a `version` column. Item labels in `best`/`worst` must match the
design's `item` values exactly; if your export has item numbers, the design must use the same numbers.

### 2b. Wide with the shown items in one cell

```csv
respondent,set,set_items,best,worst
r1,1,Unlimited projects;Custom branding;Priority support,Unlimited projects,Priority support
```

Run with `--shown-col set_items` (and `--shown-sep "|"` if the separator is not `;`).

### 4. One row per respondent, with a design file

```csv
respondent,segment,version,b1,w1,b2,w2,b3,w3
r1,smb,1,2,3,1,4,4,1
```

Each set has a best and a worst column named prefix + set number (`b1`/`w1` by default; change with
`--best-prefix` and `--worst-prefix`, for example `best_1`/`worst_1`). The number is matched to the
design's `set` value, so the design must number its sets 1, 2, 3, ... . Every set needs both columns:
a `b4` with no `w4`, or two columns for one set (`b1` and `b01`), stops the run. A design file is
required. A
set left blank counts as an excluded set (`best_not_exactly_one`), so skipped questions are visible
in the validation block. The example is position-coded: add `--choice-coding position`.

The format is detected from the header (an `item` column means long; no `set`, `best` or `worst`
column plus best/worst column pairs means one row per respondent). Force it with
`--format long|wide|respondent`. Conflicting options stop the run: `--design` with `--shown-col` or
`--shown-cols`, both of those together, or either with `--format long`.

### Exports that need reshaping first

- **Qualtrics** CSV exports have two extra rows under the header (question text and an `ImportId` row).
  Drop them before running, or every set on them is excluded.
- **Sawtooth** respondent-level exports may name the choice columns with a suffix (`MXD_1_b`,
  `Task 1 - Best`). Rename them to `b1`/`w1` or pass `--best-prefix`/`--worst-prefix` when the set number
  comes last; otherwise reshape to the long form.

### QuestionPunk

A QuestionPunk MaxDiff question draws the sets for each respondent, so there is no design file.
`response_get_details` returns, for the MaxDiff question, `rawAnswer` and `answerDetails`:

```json
{"rawAnswer": {"sets": [[19, 6, 15, 0], [13, 15, 4, 12]], "set0_best": "19", "set0_worst": "0",
               "set1_best": "4", "set1_worst": "13"},
 "answerDetails": {"answer_options": ["Item A", "Item B", "..."], "best_label": "Most important"}}
```

`sets` lists the 0-based indices into `answer_options` of the items shown in each set; `set<i>_best` and
`set<i>_worst` are the chosen indices (strings). Write one long-format row per respondent, set and shown
item (`best`/`worst` 1 on the chosen rows). A response without `sets` (older answers) cannot be scored: leave
it out and say how many. The `responses_read` cell for this question lists only the picks.

## Validation

Structural problems stop the run with exit code 2: unreadable or empty file (or a UTF-16 file with NUL
bytes), missing or duplicate column, blank respondent/set/item id, a respondent with two segment values,
a design that reuses a position, has a position that is not a finite number or lists an item twice in a
set, a multi-version design with no version column in the responses, best/worst columns without a
partner. So does an exclusion rate above 50% (see below).

A set that breaks a rule is **excluded and counted**, one reason per set, checked in this order:

| Reason | Meaning |
|---|---|
| `duplicate_set` | wide format: the same respondent and set on more than one row (all copies dropped) |
| `set_not_in_design` | the (version, set) is not in the design file |
| `invalid_value` | long format: a best/worst cell is not a 0/1 flag; position coding: a cell is not a finite number |
| `duplicate_item` | the same item is listed twice in the set |
| `fewer_than_two_items` | the set shows fewer than two items |
| `best_not_exactly_one` | no best, or more than one |
| `worst_not_exactly_one` | no worst, or more than one |
| `choice_not_shown` | the best or worst label, or position, is not among the shown items |
| `best_equals_worst` | the same item is marked best and worst |

The report always shows sets read, valid and excluded, the count per reason with the first offending
respondent and set, respondents left with no valid set, and items not shown in any valid set.

When more than half of the sets are excluded the script stops (exit 2) instead of scoring the rest: that
many exclusions nearly always mean a wrong column mapping or choice coding. When most of them are
`choice_not_shown` with whole numbers in best/worst, the message suggests `--choice-coding position`.
`--allow-exclusions` scores the remaining sets anyway.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--respondent-col`, `--set-col`, `--item-col`, `--best-col`, `--worst-col` | `respondent`, `set`, `item`, `best`, `worst` | column names |
| `--version-col`, `--position-col` | `version`, `position` | column names for the design join |
| `--shown-cols a,b,c` | auto | wide format: columns with the shown items |
| `--shown-col NAME`, `--shown-sep` | none, `;` | wide format: one cell with all shown items |
| `--choice-coding label\|position` | `label` | how best/worst cells are coded in the wide and respondent shapes |
| `--best-prefix`, `--worst-prefix` | `b`, `w` | column prefixes of the one-row-per-respondent shape |
| `--format auto\|long\|wide\|respondent` | `auto` | force the shape |
| `--design FILE` | none | design CSV (`version,set,position,item`) |
| `--segment-col NAME` | none | cut results by this column |
| `--delimiter ";"` | read from the header | delimiter of the responses CSV: comma, semicolon or tab is detected; the design file's is detected separately |
| `--allow-exclusions` | off | score even when more than 50% of sets are excluded |
| `--model sequential\|marginal\|best-only` | `sequential` | which logit ([method.md](method.md), section 2); the pair (maxdiff) model of R `support.BWS` is not implemented |
| `--no-logit` | off | counting analysis only |
| `--share-scale preference\|probability` | `preference` | which share formula ([method.md](method.md), section 6) |
| `--items-per-set N` | from data | `a` for the probability scale when set sizes vary |
| `--bootstrap N` | 1000 | replicates; 0 turns intervals off |
| `--seed N` | 12345 | bootstrap seed |
| `--ci P` | 95 | interval level in percent |
| `--min-base N` | 200 | warn when a reported group has fewer respondents |
| `--respondent-scores` | off | add each respondent's counting scores to the JSON |
| `--json` | off | JSON instead of the text table |

Exit codes: 0 success; 2 bad input or arguments; 3 the overall logit has no finite estimate or did not
converge (the message names the items; rerun with `--no-logit` for counts). A segment whose logit
cannot be estimated does not stop the run: its `logit.status` is `not_estimated` with the reason.

Run time: the bootstrap refits the logit once per replicate and per group. A study with 300 respondents,
12 sets of 5 and 20 items takes about 40 seconds for 1000 replicates on a laptop; 1000 respondents with
15 sets of 5 from 30 items take about 2.5 minutes, plus as long again per segment. When a group's
bootstrap will take more than 20 seconds the script says so on stderr after five replicates. Run
`--bootstrap 0` first to check the validation block, then the default in the background for the numbers
you report (`--bootstrap 200` for a first look). A group with fewer than 2 respondents gets no intervals.

## JSON shape (`--json`)

```json
{
  "skill": "maxdiff-analysis",
  "version": "0.2.0",
  "input": {
    "path": "...", "design": null, "format": "long", "n_items": 9, "items_per_set": 4,
    "sets_read": 1080, "sets_valid": 1080, "sets_excluded": 0,
    "excluded_by_reason": {}, "excluded_examples": {},
    "respondents_read": 120, "respondents_without_valid_sets": [], "items_without_valid_sets": [],
    "numeric_choice_not_shown": 0, "notes": []
  },
  "method": {"counting": "...", "logit": "...", "shares": "...", "intervals": "...", "hierarchical_bayes": "...",
             "anchoring": "..."},
  "overall": {
    "n_respondents": 120,
    "n_sets": 1080,
    "below_min_base": true,
    "bootstrap": {"replicates": 1000, "level": 95.0, "unit": "respondent", "logit_replicates_failed": 0,
                  "logit_replicates_failed_share": 0.0, "logit_intervals": "ok"},
    "ranked_by": "share",
    "average_share": 11.1,
    "items": [
      {
        "item": "item1", "shown": 480, "best": 299, "worst": 8,
        "best_rate": 0.623, "worst_rate": 0.017,
        "bw_score": 0.606, "bw_score_ci": [0.556, 0.656],
        "utility": 1.741, "utility_se": 0.085, "utility_ci": [1.579, 1.919],
        "share": 37.1, "share_ci": [32.6, 41.7],
        "rank": 1
      }
    ],
    "logit": {
      "status": "ok", "model": "sequential", "identification": "zero-centred (sum of utilities = 0)",
      "likelihood": "full",
      "reference_item": "item9", "iterations": 6,
      "log_likelihood": -2014.1, "log_likelihood_null": -2683.7, "choice_tasks": 2160,
      "rlh": 0.394, "rlh_chance": 0.289, "mcfadden_r2": 0.249,
      "lr_chi_square": 1339.1, "lr_degrees_of_freedom": 8,
      "share_scale": "preference",
      "reference_coded": {"item1": {"utility": 3.37, "se": 0.13}}
    },
    "adjacent_pairs": [
      {"higher": "item1", "lower": "item2", "metric": "share", "difference": 14.5,
       "difference_ci": [7.9, 22.2], "verdict": "separated", "prob_higher_above": 1.0}
    ]
  },
  "segment_column": "segment",
  "segments": {"new": {"...": "same shape as overall"}},
  "segment_differences": [
    {"segments": ["new", "returning"], "metric": "share",
     "items": [{"item": "item1", "difference": 1.7, "difference_ci": [-7.5, 9.8], "excludes_zero": false}]}
  ],
  "respondents": [{"respondent": "s001", "segment": "new", "sets": 9, "bw_score": {"item1": 0.75}}],
  "warnings": ["..."]
}
```

- `items` is sorted by `rank`. Ranks follow `share` when the logit ran and `bw_score` otherwise
  (`ranked_by` says which); equal values share a rank.
- `logit_intervals` is `ok` or `unreliable`. When more than 5% of replicates had no finite logit
  estimate it is `unreliable`, and `utility_ci`, `share_ci` are `null`.
- `adjacent_pairs` compares each item with the next one in the ranking; `metric` is `share`, or
  `bw_score` when the logit did not run or its intervals are unreliable. `segment_differences` needs
  `--segment-col`, at least two segments and `--bootstrap` above 0.
- `verdict` is `separated` (interval above 0), `not separated` (it includes 0) or `reversed` (below 0:
  possible when the ranking is by share but the tested metric is the counting score), `null` without
  intervals.
- With `--model marginal`, `likelihood` is `composite (...)`, and `lr_chi_square`,
  `lr_degrees_of_freedom`, `utility_se` and the reference-coded `se` are `null` (method.md, section 8).
- `item_groups` appears when the items split into groups never shown together; ranks then hold only
  within a group.
- `items_per_set` in `input` is the data's set size (or a range such as `3-5`); the `a` used by the
  probability scale is in `method.shares`.
- `below_min_base` is present only when true. `segment_column`/`segments` appear only with
  `--segment-col`, `respondents` only with `--respondent-scores`.
- A value that cannot be computed is `null` (for example `utility` when the logit did not run, or the
  score of an item never shown in a segment).
- The numbers in the example are illustrative; values are not rounded in the real output.
