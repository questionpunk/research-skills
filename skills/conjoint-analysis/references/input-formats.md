# Input formats

Read this when the script cannot find a column, the choices do not match the design, or the data comes from
Sawtooth, Qualtrics, Conjointly, R or QuestionPunk.

Contents: 1. Design mode · 2. Stacked mode · 3. Exports from other tools · 4. Exclusions

Every file: UTF-8 (with or without a BOM) or UTF-16 with a BOM, comma, semicolon, tab or pipe (sniffed;
`--delimiter`, `--design-delimiter`), CRLF or LF. Qualtrics's question-text and ImportId rows are skipped automatically
(`--skip-rows N` otherwise). Duplicate column names and rows with the wrong number of cells stop the script.

## 1. Design mode: `--design design.csv responses.csv`

The design is the file `conjoint-design` writes:

```text
version,task,concept,Brand,Meals per week,Delivery,Price per week
1,1,1,GreenPlate,2,Weekly,$70
1,1,2,HomeChef,3,Every two weeks,$40
1,1,3,FreshBox,4,Every two weeks,$50
1,1,none,,,,
```

`version` may be missing when there is one version; `set` or `block` are also recognized for task and version.
With `--spec`, the spec's attributes are the attribute columns (each must exist). Otherwise every column other
than version, task and concept is an attribute, except reserved names (`id`, `alt`, `ques`, `weight`,
`segment` and the like; the report names any it skipped): name them with `--attribute-cols` if they are
attributes. The none alternative is a row whose concept is `none`, `none of these`, `no choice`, `neither` or
`opt-out`, or whose attribute cells are all blank. A concept numbered `0` is an ordinary concept, so 0-based
numbering works. Each task may have one none row and needs at least two concepts.

Responses, long (`--task-col`, `--choice-col` if the names differ):

```text
respondent,version,task,choice,segment
r001,1,1,2,single
r001,1,2,none,single
```

Responses, wide (columns `task1`, `t1`, `choice_1`, `cbc1` or `q1` ... are found automatically):

```text
respondent,version,task1,task2,task3
r001,1,2,none,1
```

A choice is the concept label from the design: `2`, `2.0`, `Option 2` and `Concept 2` all mean concept 2;
`none` or `None of these` mean none, and `0` means none only in a task that has no concept 0. A blank cell is a
task not shown or not answered and is skipped, not excluded. Versions are matched as labels (`1` and `1.0` are
the same); with one version and no version column in the responses, that version is used. If the none option
was on screen but the design has no none rows, pass `--none-when-missing-row`: it adds the none option to
every task (it was offered in all of them), chosen only where the response says none.

Wide columns: when several name families match (`Q1`, `Q2` beside `task1`...), the first of `task`, `cbc`,
`choice`, `t`, `q` is used and the others are named in a note. A column flag (`--task-col`, `--version-col`,
`--concept-col`, `--choice-col`, `--respondent-col`, `--chosen-col`) that names a missing column stops the
script.

## 2. Stacked mode: one row per respondent × task × concept

```text
respondent,task,concept,Brand,Meals per week,Delivery,Price per week,chosen
r001,1,1,GreenPlate,2,Weekly,$70,0
r001,1,2,HomeChef,3,Every two weeks,$40,1
r001,1,3,FreshBox,4,Every two weeks,$50,0
r001,1,none,,,,,0
```

This is the design file with the respondent added and a `chosen` column (1 on the picked row; `true`, `yes`
and `x` also count). Recognized names: respondent `respondent`, `id`, `resp.id`, `ResponseId`; task `task`,
`set`, `ques`; concept `concept`, `alt`, `option`; chosen `chosen`, `choice`, `selected`. Columns that are not
attributes (a respondent covariate such as `carpool`) must be left out with `--attribute-cols`, or the script
will treat them as attributes and stop with "singular". A task with no chosen row is excluded, unless
`--none-when-missing-row` says the none option was offered: then a none row is added to every task without
one, chosen where no concept was. Rows with `0` in every attribute (and `0` nowhere else) are read as the none
option, which is how Sawtooth writes it.

## 3. Exports from other tools

| Source | What to do |
|---|---|
| Sawtooth (Lighthouse/Discover) CBC "export design + responses" | Stacked: one row per concept with a 0/1 choice column; drop the fixed holdout tasks before analysis. Attribute cells are often level codes (1, 2, 3): map them to the level text, and to real prices before `--price-attr` (the script notes levels that are exactly 1..k). Rename `sys_RespNum` with `--respondent-col` |
| Qualtrics conjoint project | Use the raw conjoint data export (one row per respondent × task × concept with the levels shown and the pick), stacked, with `--attribute-cols`. The individual-utilities export (one row per respondent, one column per level) is not choice data and cannot be analyzed here |
| Conjointly | Stacked or design + responses; check how "none" is coded |
| R `mlogit` / `cbcTools` data | Stacked: `resp.id`, `ques`, `alt`, attributes, `choice` (the Chapman and Feit example in `fixtures/README.md`) |
| QuestionPunk | Each `conjoint_analysis` answer stores the profiles shown per task (`tasks[i].profiles`, one level per attribute in attribute order) and the pick as `task_<i>` = profile index from 0, or `none`. Write one stacked row per profile with `concept` = that index (0-based is fine) and `chosen` = 1 on the picked index. When the question has `include_none_option`, also write a `none` row with blank attributes on every task, `chosen` = 1 when `task_<i>` is `none`. Answers over 4,000 characters come back cut, ending in `…[truncated N chars]`: they do not parse as JSON, so count and drop them, like older answers without `tasks` |

## 4. Exclusions

Each excluded task is counted by reason: the respondent and task appear twice, the version and task are not in
the design, the choice is not a concept of that task, not exactly one chosen row, a blank attribute level, or
fewer than two alternatives. Above 5% of tasks the script stops (a wrong column, version or coding is the usual
cause); `--allow-exclusions` analyses the rest and the report shows the counts.
