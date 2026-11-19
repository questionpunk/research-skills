# How the design is built and checked

Read this when a user asks how the design was generated, why the efficiency is what it is, or how to compare
it with Sawtooth, Conjointly, Qualtrics or a SAS/R design.

Contents: 1. Spec format · 2. Generator · 3. Diagnostics · 4. The efficiency bound · 5. File format · 6. Limits

## 1. Spec format

Text (one attribute per line; `#` starts a comment):

```text
Brand: FreshBox | GreenPlate | HomeChef
Meals per week: 2 | 3 | 4
Price per week: $40 | $50 | $60 | $70
prohibit: Meals per week=4 & Price per week=$40
```

Levels may also be separated by `;` or `,` when no `|` is present. With commas, a digit, a comma and
exactly three digits (`$1,299`) is a thousands separator inside one level, so `$1,200, $2,500` is two levels;
`100,200,300` is one number, so write `100 | 200 | 300`. Prohibition conditions are joined by `&` only
(`Salt and Pepper` stays one level); a line is a prohibition only when it starts with `prohibit:`. JSON is
the same content, and is the way to write a name or level that contains `&`:
`{"attributes": [{"name": "Brand", "levels": ["FreshBox", "GreenPlate"]}], "prohibitions": [{"Brand":
"FreshBox", "Price per week": "$40"}]}`. A prohibition removes every concept that matches all of its
conditions; it must name two or more different attributes (to drop a level, delete it from the attribute).
Attribute names `version`, `block`, `task`, `set`, `ques`, `concept`, `alt`, `alternative`, `respondent`,
`respondent_id`, `resp.id`, `id`, `responseid`, `response_id`, `rid`, `chosen`, `choice`, `segment` and
`weight` (any case) are reserved for file columns, the same list `conjoint-analysis` uses.

## 2. Generator

`--method balanced` (default). For each version, task and concept, each attribute takes the level that has
appeared least (1) within the task, then (2) within the version, then (3) in the whole design, with random tie
breaks. Rule 1 gives minimal overlap: no level repeats within a task while the attribute has at least as many
levels as there are concepts. Rules 2 and 3 give level balance. Levels that would complete a prohibited
concept are skipped while it is built; a duplicate concept within a task is perturbed or redrawn. After 50
failed attempts at a task the balance rule is loosened at random so tight prohibitions can still be met; after
2,000 the script stops and says the prohibitions are too tight. An identical task within a version is
redrawn up to 20 times, then allowed (small designs have few distinct tasks). Concepts are built in
sequence, so the order they are shown in is shuffled afterwards: otherwise the last concept would be the one
that repeats a level. This is a greedy heuristic close to Sawtooth's "shortcut" method: it balances one-way
level counts and minimizes overlap, but does not balance two-way co-occurrence of levels across attributes as
"complete enumeration" does (Chrzan and Orme 2000). More versions make up for that in practice; check
Cramér's V.

`--method random`. Each concept is drawn uniformly from the allowed profiles, independently of every other
concept and task (with prohibitions this is a uniform draw over the profiles that remain, not attribute by
attribute). Two concepts in a task can therefore be identical, and some tasks repeat: that is what
independent assignment means, and the script reports it as expected rather than removing it. Use it when the
analysis will report AMCEs (Hainmueller, Hopkins and Yamamoto 2014), which assume levels are assigned
independently. Prohibitions break that independence across attributes: the simple difference in means is
then no longer the AMCE, so use no prohibitions with `random`. It is less efficient for the logit (section 4),
and the low-efficiency warning says so instead of asking for `balanced`.

Respondents are assigned to versions in rotation (respondent 1 to version 1, ...). More versions balance
levels and pairs across respondents and protect against order and context effects; 100 is this skill's
default, a convention, not a published number.

## 3. Diagnostics

| Check | How | Warn when |
|---|---|---|
| Level frequency | Count of each level over all concepts, its deviation from perfect balance, max/min ratio | A level never shown; max/min above 1.5 (convention) |
| Overlap | Share of tasks in which an attribute repeats a level among the concepts | Reported; "unavoidable" when the attribute has fewer levels than concepts (in the largest task) |
| Attribute association | Cramér's V between every pair of attributes over all concepts; the strongest pair is named | V above 0.10 (convention); said to be expected only when a prohibition names both attributes |
| D-error | det(M)^(−1/p), M = MNL information per task at β = 0, orthonormal coding, none excluded | Singular M: `design` stops (exit 2, nothing written); `check` warns not to field it |
| Relative D-efficiency | 100 × (det M / bound)^(1/p) (section 4) | Under 80% (convention) |
| Duplicates, prohibitions (`check`) | Same profile twice in a task; concepts that break the spec's prohibitions | Any (expected for duplicates under `random`) |
| Exposure | Least shown level's appearances per respondent: its count over all versions / number of versions (respondents take versions in rotation) | Feeds the sample size: n ≥ 500 / that number, beside the nominal rule |

At β = 0 every alternative is equally likely, so for a task with m concepts with coded rows x₁ ... x_m the
information is (1/m) Σ (x_j − x̄)(x_j − x̄)ᵀ (Huber and Zwerina 1996; Kuhfeld 2010). M averages it over all
tasks; p is the number of main-effect parameters, Σ(ℓ_q − 1). The none alternative is left out of the
efficiency (as in Street and Burgess's forced-choice results): the number describes the forced choice among
the concepts. A none option takes choice probability away from the concepts and spends some information on
its own constant, so the information about the attributes is lower than this number suggests, and more so
the more often none is expected to be chosen; plan the sample with that in mind.

D-error depends on the coding and on whether information is averaged per task. Here it is per task with
orthonormal coding (an optimal pair of two-level profiles gives 2.0); SAS, Ngene and Huber and Zwerina often
use effects coding or total information, which give different raw numbers for the same design. Compare tools
by relative D-efficiency or by the ratio of two designs' D-errors from the same tool, not by raw D-error.

## 4. The efficiency bound

Orthonormal (normalized Helmert) contrasts B_q for attribute q with ℓ levels satisfy B_qB_qᵀ = I − J/ℓ. For
one task in which level a appears n_a times among m concepts, the trace of that attribute's block of the
information is

  (1/m)[Σ n_a(1 − 1/ℓ) − (Σ n_a² − m²/ℓ)/m] = 1 − Σ n_a² / m².

This is largest when the levels are spread as evenly as possible: with m = ℓx + y (0 ≤ y < ℓ), the smallest
Σ n_a² is (ℓ − y)x² + y(x + 1)², so the trace is at most 2S_q/m² with 2S_q = m² − (ℓx² + 2xy + y). The S_q is
the quantity Burgess and Street (2005) use for optimal main-effects choice designs. For a fixed trace the
determinant of the ℓ − 1 by ℓ − 1 block is largest when its eigenvalues are equal, and for a positive
semidefinite block matrix det M ≤ Π det(M_qq) (Fischer's inequality). So

  det M ≤ Π_q (2S_q / (m²(ℓ_q − 1)))^(ℓ_q − 1),

reached by a design with minimal overlap, equal pairwise level co-occurrence within each attribute and no
association between attributes. The tests confirm it: the foldover pair design for two-level attributes and a
Latin-square triple design score 100%, and no random design exceeds 100%. The algebra above is this skill's
derivation; it agrees with the published optimal designs it was tested on, but the bound was not checked
line by line against Burgess and Street's theorem.

The bound ignores prohibitions and the finite layout (tasks × versions), so it may be out of reach for a
given design; a design with prohibitions usually scores under 100% but can occasionally reach it. Read the
number as "how close to the best forced-choice, main-effects design without prohibitions", and the 90% aim
and 80% warning as this skill's conventions.

## 5. File format (shared with conjoint-analysis)

```text
version,task,concept,Brand,Meals per week,Delivery,Price per week
1,1,1,GreenPlate,2,Weekly,$70
1,1,2,HomeChef,3,Every two weeks,$40
1,1,3,FreshBox,4,Every two weeks,$50
1,1,none,,,,
```

One row per version × task × concept, numbered from 1 in the order shown on screen; with `--none` a row with
concept `none` and blank attributes follows each task. Both skills read a file by the same rules:

- Column names: `task` (or `set`, `ques`, `question`), `concept` (or `alt`, `alternative`, `option`,
  `profile`), `version` (or `block`) when there are several versions; every other non-reserved column is an
  attribute. Names are compared ignoring case; a blank trailing column and Excel's `sep=;` first line are
  ignored.
- Labels: `2`, `2.0`, `Option 2`, `Concept 2`, `Alt 2`, `Profile 2` and `Card 2` are the same concept.
  Numbering from 0 is fine: concept `0` is an ordinary concept.
- The none option: a row whose concept label is `none`, `none of these`, `no choice`, `neither`, `opt-out`
  or `opt out` (any case), or whose attribute cells are all blank. A none label with attribute levels is an
  error.
- Each (version, task, concept) appears once, a task has at most one none row and at least two concepts;
  `check` stops with exit code 2 otherwise, because a recorded choice could not be matched to a profile.

`conjoint-analysis` reads this file with `--design design.csv` plus the respondents' choices:
`respondent,version,task,choice` (choice = the concept number or `none`), or one row per respondent with
`version,task1,...,taskT`.

## 6. Limits

- Main effects only. Interactions need a larger design (Johnson-Orme with c = the product of the two
  attributes' level counts) and a model this pack does not estimate.
- No alternative-specific designs (attributes that apply to one brand only), partial profiles, adaptive CBC
  or holdout tasks. Add holdout tasks by hand as extra fixed tasks if needed.
- The efficiency is for the aggregate logit at β = 0. Bayesian-efficient designs with priors (Kessels et al.)
  can do better when good priors exist.
