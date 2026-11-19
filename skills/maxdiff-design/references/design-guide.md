# MaxDiff design guide

How to choose the numbers the script needs, and how to read its report. Sources for every rule are in
[sources.md](sources.md) ([S1] to [S10] below refer to its list).

## Contents

- Is MaxDiff the right method
- Writing the item list
- Items per set
- Sets per respondent
- Versions
- Sample size
- More than about 30 items
- Survey length
- Reading the diagnostics
- Exact designs worth knowing
- Fielding the design

## Is MaxDiff the right method

MaxDiff ranks a list of comparable items by forcing trade-offs: in each set the respondent picks the best
and the worst. Use it when you have about 6 to 30 items of the same kind (features, messages, benefits,
names) and rating scales would come back with everything "important".

Use something else when:

- there are fewer than 6 items: ask one ranking question;
- the items are bundles of attributes with levels (plan A at price X with feature Y): that is conjoint;
- the question is a price: use a pricing method;
- you need to know whether an item is good enough, not only better than the others: add an anchor question
  (see [question-wording.md](question-wording.md)) or use a rating.

## Writing the item list

- One idea per item, all at the same level of detail and of similar length.
- Items must be comparable on the one dimension the question names (importance, appeal, concern).
- No overlapping items: two wordings of the same idea split its score.
- No item that is a precondition for everything else ("the product works"), which wins every set.
- Pilot read-back: ask two or three people from the audience to say each item back in their own words.
  Rewrite any item they explain differently from what you meant.
- Keep the list to around 30 or fewer [S3]. Each extra item adds sets for every respondent.

## Items per set

| Items in the study (K) | Items per set (k) | Why |
|---|---|---|
| 6 or 7 | 3 | 4 would be more than half the list |
| 8 or 9 | 4 | at most half the list |
| 10 or more | 4, or 5 for short items | Sawtooth's 4 or 5 [S1] |

Rules: at least 3, at most half the items, and more than about 5 adds fatigue for little precision
[S1] [S2]. On phones and for long items (full sentences) prefer the smaller number.

## Sets per respondent

Sets = 3 x K / k, rounded up, shows each item about 3 times, the minimum for individual-level scores
[S1]. Up to 5 exposures improves precision if respondents can take the length.

| K | k | Sets for 3 exposures | Sets for 5 exposures |
|---|---|---|---|
| 8 | 4 | 6 | 10 |
| 10 | 4 | 8 | 13 |
| 12 | 4 | 9 | 15 |
| 15 | 5 | 9 | 15 |
| 20 | 4 | 15 | 25 |
| 20 | 5 | 12 | 20 |
| 30 | 5 | 18 | 30 |

If the sets needed are more than respondents will finish, cut items first. If that is not possible, accept
fewer exposures and plan a pooled analysis with a larger sample (see "Sample size"). Below 2 exposures
individual-level scores are not supported [S1] [S3].

## Versions

A version is one respondent's full questionnaire: its own sets, in its own order.

- **Default, 10 versions:** enough to average out order and context effects [S7], and still few enough to
  set up by hand.
- **Online, tool can assign versions:** generate more, up to Sawtooth's default of 300 [S1], and assign
  them at random or in rotation. Pair counts and positions even out across versions.
- **Paper:** at least 4 [S1].
- **Comparing or clustering respondents (segmentation):** practitioners disagree. Displayr prefers one
  version, because different versions add differences between respondents that are not preference [S7];
  Sawtooth fields many versions and scores each respondent with HB [S1]. Ask which analysis is planned and
  record the choice. With one version every respondent sees the same context for each item; say so in the
  write-up. One version is also the answer when the tool allows nothing else.

Versions do not need equal numbers of respondents, and none needs a minimum sample [S2].

Generating hundreds of versions takes a while. Measured on a laptop for 300 versions: about 35 seconds for
20 items (4 per set) and about 2 minutes for 30 items (5 per set); `--restarts 3` cut the 30-item run to
under 40 seconds at a small cost in pair balance. Above about 20 items with hundreds of versions, use
`--restarts 3` or run the command in the background so a tool time-out does not stop it.

## Sample size

- 300 respondents in total and 200 in every subgroup you will report separately [S5]; [S4] gives 200 as
  the floor.
- Above about 30 items, raise these in proportion (double at 60 items) [S5].
- Sparse design (each item under 2 times per respondent, where Sawtooth's tools warn; [S1] writes the rule
  for designs that show an item once or less), pooled analysis only: each item should be seen 500 to 1000
  times in every group you report [S1]. These are item exposures, not respondents. The sibling skills
  `survey-sample-size` and `maxdiff-analysis` use this same rule and the 300/200 floors above. Exposures of one item in a group
  = respondents x sets x k / K. Example: 40 items, 5 per set, 8 sets gives 1 exposure per respondent, so
  500 to 1000 respondents per group.

- Exposures and sample size trade off: with 50 to 400 respondents show each item 3 or more times; with 600
  or more, 1 to 2 times is typically enough [S3].

Run the script with `--respondents N` to get the total exposures per item for your sample next to these
rules. They are rules of thumb: for a margin of error on a share or a comparison between groups, use the
skill `survey-sample-size`.

## More than about 30 items

The script warns and still builds what you ask for. The options, all of which pool information across respondents
and need a larger sample [S8]:

| Approach | What a respondent sees | Build it here |
|---|---|---|
| Sparse | Every item about once | Yes: give `--sets` so that sets x k is about K, and many versions |
| Express | A random subset (for example 30 items), each item several times | No: draw the subsets in the survey tool, design each subset here |
| Bandit | Leading items more often as data comes in | No: needs a tool that adapts during fieldwork |

Sawtooth prefers sparse to Express for long lists [S8]. First ask whether the list can be cut or split
into two studies.

## Survey length

The report prints sets x seconds per set. The default of 20 seconds per set is an assumption, not a
sourced figure: time two or three pilot respondents and rerun with `--seconds-per-set`. Longer items and
more items per set take longer.

## Reading the diagnostics

| Line | Good | What to do when it is not |
|---|---|---|
| Item frequency | min and max equal, or 1 apart | Change the number of sets so sets x k is a multiple of K |
| Pair frequency | small sd; range inside a version 0 or 1 | Try another seed, more restarts, or one more set; a gap of 2 is sometimes the best possible |
| Pairs never together | 0 over the whole design | More versions or more sets; with one version and many items it cannot be 0 |
| Position frequency | largest gap 0 or 1 | Regenerate; a fixed order (alphabetical, sorted) causes this |
| Item correlation | between -0.5 and 0.5 [S7] | Same fixes as pair frequency; -1 means two items never meet and split the sets between them |
| Connectivity | every version connected | More sets per respondent; if only "connected overall", use pooled scores |
| Exposures | 3.00 or more | More sets or fewer items |
| Exact BIBD | "yes" is a bonus, not a requirement | Nothing: near-balance is enough for logit and HB [S2] |

A FAIL means the design should not be fielded as it is. A WARN is a trade-off to state in the plan.

## Exact designs worth knowing

When the number of sets equals one of these, the script builds an exact BIBD (every item equally often,
every pair equally often) instead of searching. The patterns are K items in K sets, and q x q items in
q x q + q sets of q (affine plane, q prime) [S6] [S10].

| Items (K) | Per set (k) | Sets | Each item shown | Each pair together |
|---|---|---|---|---|
| 7 | 3 | 7 | 3 | 1 |
| 7 | 4 | 7 | 4 | 2 |
| 11 | 5 | 11 | 5 | 2 |
| 13 | 4 | 13 | 4 | 1 |
| 21 | 5 | 21 | 5 | 1 |
| 9 | 3 | 12 (affine plane) | 4 | 1 |
| 25 | 5 | 30 (affine plane) | 6 | 1 |
| 6 | 3 | 20 (all subsets) | 10 | 4 |

Each row satisfies b k = v r and lambda (v - 1) = r (k - 1) [S6]; for example 13 x 4 = 13 x 4 and
1 x 12 = 4 x 3. Not every row suits MaxDiff as it is: (7, 4, 7) shows more than half the items in a set
(prefer (7, 3, 7)), and (25, 5, 30) and (6, 3, 20) show each item 6 and 10 times, above the usual 3 to 5. When the default number of sets is not the exact one, the script prints a note such as
"an exact BIBD exists with --sets 13".

## Fielding the design

- Keep `design.csv` and the seed with the data. Analysis needs to know which items each respondent saw.
- Programme each set as one question that shows the items in the CSV's `position` order, with one "best"
  and one "worst" pick that cannot be the same item.
- Record for every respondent: the version, and for every set the best and the worst item. The analysis
  input is the design rows plus those two choices (long format: respondent or version, set, item, best,
  worst).
- If the survey tool draws its own sets and cannot import a design, pass it the three numbers (items,
  items per set, sets) and export the sets each respondent saw. Then run `--check` on that export.
- Other layouts: `--wide` writes `version,set,item1..itemk` (the form Sawtooth and Displayr use), and
  `--item-id` adds 1-based item numbers. `--check` reads the long and the wide form, with labels or numbers,
  comma, semicolon or tab separated. The sibling skill `maxdiff-analysis` reads only the long form, so keep
  that file for the analysis.
- Test one version yourself on a phone before launch, and time it.
