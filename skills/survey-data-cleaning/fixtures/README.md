# Fixtures for survey-data-cleaning

All three files are synthetic: invented respondents, `example.com` addresses and documentation-range IPs
(`192.0.2.x`). The expected values below were worked out by hand from the CSV, before the script was run,
and the tests compare the script against this file.

## Configuration used

```
--grid sat=g1..g6 --grid brand=b1..b4
--attention "ac1=Strongly disagree" --attention ac2=4
--open-cols open_feedback
--rule "exp_gt_age: years_experience > age"
--rule 'never_but_sessions: uses_product == "Never" and sessions_per_week > 0'
```

Defaults: speeder below 1/3 of the median, straight-lining when every item in a grid of at least 4 items is
identical, two failed attention checks, more than 0.5 of answers blank.

## `planted.input.csv` (20 respondents, R01–R20)

### Speeders

19 durations (R15 is blank and is not checked). Sorted:

120, 150, 200, 480, 540, 570, 580, 590, 595, **600**, 605, 610, 620, 630, 640, 660, 700, 700, 900

- Median = the 10th of 19 values = **600**.
- Cut-off = 600 × 1/3 = **200**. Flag when duration < 200 (strictly).
- Flagged: R20 (120), R04 (150). R11 (200) sits exactly on the cut-off and is not flagged.
- With `--speed-fraction 0.5`: cut-off 300, flagged R04, R11, R20.

### Straight-lining (longest run of identical consecutive answers)

| Id | sat (g1–g6) | Longest | brand (b1–b4) | Longest |
|---|---|---|---|---|
| R01 | 4 5 3 4 2 4 | 1 | 3 4 2 5 | 1 |
| R02 | 2 2 3 4 4 5 | 2 | 1 2 2 3 | 2 |
| R03 | 5 4 4 4 3 2 | 3 | 1 1 1 (blank) | 3 |
| R04 | 1 3 2 5 4 1 | 1 | 2 5 1 3 | 1 |
| R05 | 3 3 4 2 5 4 | 2 | 4 3 3 2 | 2 |
| R06 | 5 5 5 5 5 5 | **6** | 4 5 3 4 | 1 |
| R07 | 4 3 4 2 3 5 | 1 | 2 3 4 4 | 2 |
| R08 | 4 3 4 2 3 5 | 1 | 2 3 4 4 | 2 |
| R09 | 2 4 3 3 5 1 | 2 | 2 2 2 2 | **4** |
| R10 | 3 4 2 2 2 5 | 3 | 5 4 3 1 | 1 |
| R11 | 4 2 5 3 3 4 | 2 | 3 1 4 2 | 1 |
| R12 | 4 4 4 4 4 2 | 5 | 3 2 5 4 | 1 |
| R13 | 1 2 4 3 5 5 | 2 | 2 4 4 1 | 2 |
| R14 | 3 5 4 4 2 1 | 2 | 5 5 2 3 | 2 |
| R15 | 2 3 5 4 1 3 | 1 | 4 2 3 5 | 1 |
| R16 | 5 3 3 2 4 4 | 2 | 1 3 2 2 | 2 |
| R17 | 4 1 3 5 2 4 | 1 | 3 5 1 2 | 1 |
| R18 | 3 2 4 4 5 3 | 2 | all blank | 0 |
| R19 | 2 5 4 3 3 1 | 2 | 4 1 3 5 | 1 |
| R20 | 3 3 3 3 3 3 | **6** | 3 3 1 2 | 2 |

- Default (run = all items: 6 of 6 for sat, 4 of 4 for brand): R06, R09, R20.
- `--longstring-fraction 0.5` on sat alone: threshold = more than half of 6 = 4, so R06, R12 (5), R20.
- `--longstring-min 3` on brand alone: R03 (3) and R09 (4).
- `--min-grid-items 5`: the 4-item brand grid is reported but not flagged, so R06 and R20 only.
- A 2-item grid with equal answers is never flagged at the default minimum of 4.

Variability (sample standard deviation of the answers in a grid):

- R06 sat (5 5 5 5 5 5): 0.
- R12 sat (4 4 4 4 4 2): mean 22/6 = 3.6667; squared deviations 5 × 0.1111 + 2.7778 = 3.3333; divided by
  5 = 0.6667; square root = **0.8165**.
- R03 brand (1 1 1, one blank): variability 0 over 3 answered items. That is below the minimum of 4
  answered items, so R03 is not flagged.
- R18 brand (all blank): not computed.

No grid row in this file repeats a block or steps by one throughout, so there are no pattern candidates.

### Duplicates (the first row of a group is kept unflagged)

- R08: every column except `id` equals R07, so the same email and IP. Counted `duplicate` (same email as
  R07); also the candidates `identical_answers` and `shared_ip`. R07 gets a note.
- R13: same IP as R02 (`192.0.2.2`), different answers. Only the candidate `shared_ip`: a shared IP is
  not proof, so R13's flag count is 0.
- R16: email `Dana@Example.com ` equals R05's `dana@example.com` after trimming and lower-casing: counted
  `duplicate`.
- Counted duplicates: R08, R16, with the default key columns or with `--dup-cols email`.

### Attention checks (ac1 = "Strongly disagree", ac2 = "4"; flag at 2 failures)

- R04: "Agree", "1": 2 failures, flagged.
- R20: "Agree", "2": 2 failures, flagged.
- R14: "Disagree" on ac1 only: 1 failure, not flagged.
- R17: ac1 "strongly disagree " passes (case and spaces ignored); ac2 blank counts as a failure: 1, not flagged.
- With `--attention-min-fails 1`: R04, R14, R17, R20.

### Open answers (candidates to read; they count only when confirmed with `--confirm`)

| Id | Answer | Reason |
|---|---|---|
| R01, R19 | "The onboarding was confusing but support helped me quickly." (59 characters, at least 20) | same text from two respondents |
| R04 | "kkkkkk" | a character repeated 4+ times; no vowels |
| R10 | "x" | fewer than 3 characters |
| R11 | "No" | fewer than 3 characters (possibly a fair answer: this is why they are candidates) |
| R15 | "bcdfg" | no vowels |
| R20 | "asdfgh" | 6 neighbouring keys on the home row |

R07 and R08 share "Works well for us." but it is 18 characters, under 20, so it is not a same-text
candidate. R18's blank answer is non-response, not a candidate.

### Inconsistent answers

- `exp_gt_age` (years_experience > age): R05 (30 > 24), R14 (40 > 31). Not evaluable: R09 (age is
  "Prefer not to say"), R18 (blank).
- `never_but_sessions`: R20 ("Never" and 5 sessions). R02 is "Never" with 0 sessions: consistent. Not
  evaluable: R18 (blank).
- R18 has no evaluable rule, so its `inconsistent` cell is blank, not 0.

### Item non-response

Question columns = 21 columns minus `id`, `duration_sec`, `email`, `ip` = **17**.

- R18: b1–b4, age, years_experience, uses_product, sessions_per_week, open_feedback blank = 9/17 = 0.5294,
  above 0.5: flagged.
- R03 (b4 blank) and R17 (ac2 blank): 1/17 = 0.0588. Everyone else 0.

### Expected flags

| Id | Counted flags | Count | Candidates (not counted unless confirmed) |
|---|---|---|---|
| R01 | | 0 | open_text_candidate |
| R04 | speeder, attention_fail | 2 | open_text_candidate |
| R05 | inconsistent | 1 | |
| R06 | straightliner | 1 | |
| R08 | duplicate | 1 | identical_answers, shared_ip |
| R09 | straightliner | 1 | |
| R10 | | 0 | open_text_candidate |
| R11 | | 0 | open_text_candidate |
| R13 | | 0 | shared_ip |
| R14 | inconsistent | 1 | |
| R15 | | 0 | open_text_candidate |
| R16 | duplicate | 1 | |
| R18 | high_missing | 1 | |
| R19 | | 0 | open_text_candidate |
| R20 | speeder, straightliner, attention_fail, inconsistent | 4 | open_text_candidate |

No flags and no candidates: R02, R03, R07, R12, R17. Distribution of counted flags: 0 flags: 11 (the five
above plus R01, R10, R11, R13, R15, R19), 1 flag: 7, 2 flags: 1 (R04), 4 flags: 1 (R20).

No open answers in this file are near-duplicates (the only repeated long answer is identical, R01 and R19).
The platform fraud columns are absent, so those three checks report "not present" and their cells are blank.

### Drop rules

- `--drop-if "count>=2"` removes R04 and R20: 2 of 20 = 10.0%; 18 kept.
- `--drop-if "duplicate,speeder+attention_fail"` removes R04, R08, R16, R20.
- `--drop-if "count>=2,duplicate" --preview` reports R04, R08, R16, R20 and writes no clean or removed file.

## `clean.input.csv` (6 respondents, C01–C06)

No planted problems. Durations sorted: 480, 540, 600, 620, 660, 700; median = (600 + 620) / 2 = 610;
cut-off 203.33; nobody is below it. Expected: zero flags on every check, and a `--drop-if "count>=1"`
clean file identical to the input.

## `qualtrics.input.csv` (Qualtrics layout, 12 rows, Q01–Q12)

Three header rows as in a Qualtrics CSV export: internal names, question text, and a row of
`{"ImportId": ...}` cells. Data starts on the fourth row. Layout and `Status` / `Finished` codes follow
Qualtrics' "Understanding your dataset" page (see `references/sources.md`).

Configuration used:

```
--grid q1=Q1_1..Q1_6 --open-cols Q2 --item-cols Q1_1..Q1_6,Q2
```

### Rows set aside (counted, not screened)

- Q09: `Status` 1 (survey preview). Q10: `Status` "Survey Test". Q11: `Finished` 0 (unfinished).
- 12 rows, 9 screened. Q09 and Q10 straight-line the grid but get no flags, because they are not screened.

### Speed

Durations of the 9 screened rows, by `path`:

- long: 580 (Q03), 600 (Q01), 610 (Q12), 620 (Q02), 640 (Q04): median 610, cut-off 203.33.
- short: 60 (Q08), 190 (Q07), 200 (Q05), 210 (Q06): median (190 + 200) / 2 = 195, cut-off 65.
- All nine together: 60, 190, 200, 210, **580**, 600, 610, 620, 640: median 580, cut-off 193.33.

Expected:

- Without `--speed-by`: Q08 (60) and Q07 (190) are below 193.33. Q07 is an honest short-path respondent.
- With `--speed-by path`: only Q08 (60 < 65).
- Duration per answered item (7 question columns): Q08 60/7 = 8.57; Q07 answered 6, 190/6 = 31.67;
  Q05 200/7 = 28.57; Q06 210/7 = 30.00. With `--speed-by path --min-per-item 30`: Q05 and Q08 (Q06 is not
  below 30).

Page speed index (`--page-time-cols t_p1,t_p2`): median page time divided by own page time, capped at 3,
averaged over pages; flag above 2.0.

- All nine together: page 1 times sorted 20, 95, 100, 105, **290**, 300, 305, 310, 320, median 290; page 2
  the same with 40 for 20, median 290. Q05: 290/100 = 2.9 on both pages, index 2.9. Q06: 290/105 = 2.76.
  Q07: 290/95 = 3.05, capped at 3. Q08: capped at 3 on both. All four short-path respondents are above 2.0.
- With `--speed-by path`: short-path medians are (95 + 100) / 2 = 97.5 on both pages. Q08: 97.5/20 = 4.875,
  capped at 3; 97.5/40 = 2.4375; index (3 + 2.4375) / 2 = **2.72**, flagged. Q07: 97.5/95 = 1.03. Only Q08.

### Grid q1 (Q1_1–Q1_6)

| Id | Answers | Longest run | Variability | Expected |
|---|---|---|---|---|
| Q02 | 1 2 1 2 1 2 | 1 | 0.5477 (mean 1.5; 6 × 0.25 = 1.5; / 5 = 0.3; root) | pattern candidate: repeating block of 2 |
| Q03 | 1 2 3 4 5 4 | 1 | | pattern candidate: staircase (four steps of +1 in a row) |
| Q07 | 3 3 3 (blank) 3 3 | 3 | 0 over 5 answered | straightliner: zero variance over 5 answered items |
| others | mixed | 1 | above 0 | none |

Pattern candidates are report-only: Q02 and Q03 keep a flag count of 0.

### Platform fraud fields (report only)

- `Q_RecaptchaScore` below 0.5: Q03 (0.3). Q04 has 0.2 but `Q_RecaptchaStatus` is "error", so it is not
  evaluated; Q12 has no score. Expected: flagged Q03; 1 error; 1 blank.
- `Q_BallotBoxStuffing` true: Q05. `Q_DuplicateRespondent` true: Q06.
- None of these changes a flag count: Q03 and Q06 stay at 0.

### Open answers

- Q01: "Delivery was quick and the driver was polite." Distinct words: delivery, was, quick, and, the,
  driver, polite = 7.
- Q05: "The delivery was quick and the driver was very polite." Distinct words: the same 7 plus "very" = 8.
- Shared 7, union 8: overlap 7/8 = **0.875**, at or above 0.8, so both are near-duplicate candidates.
- With `--similar-text 0.9` or `off`: no candidates.

### Summary (with `--speed-by path`)

| Id | Counted flags | Candidates and platform fields (not counted) |
|---|---|---|
| Q01 | | open_text_candidate |
| Q02 | | pattern_candidate |
| Q03 | | pattern_candidate, platform_bot |
| Q05 | | open_text_candidate, platform_ballot_stuffing |
| Q06 | | platform_duplicate |
| Q07 | straightliner | |
| Q08 | speeder | |

- Distribution: 0 flags: 7 (Q01, Q02, Q03, Q04, Q05, Q06, Q12); 1 flag: 2. Share with 1 or more: 2/9 =
  0.2222.
- Flags that occur together: pattern_candidate + platform_bot 1 (Q03); open_text_candidate +
  platform_ballot_stuffing 1 (Q05). Without `--speed-by`, speeder + straightliner 1 (Q07).
- Warnings at the 0.12 comparison point: open_text_candidate and pattern_candidate, each 2/9 = 22.2%.
  Speeder, straightliner and each platform field are 1/9 = 11.1%, below it.
- `--drop-if "count>=1,not_screened" --compare-cols region` removes Q07, Q08, Q09, Q10, Q11.
  Region of the removed: north 3 (Q07, Q09, Q11), south 2 (Q08, Q10). Kept: north 3 (Q01, Q02, Q05),
  south 4 (Q03, Q04, Q06, Q12). The clean file keeps the three header rows.

## Files written by the tests

The tests also write small temporary files: a semicolon-delimited Windows-1252 file, a tab-delimited
UTF-8 file with a byte-order mark, a two-row-header file with blank column names, and a 2-item grid.
`ReviewFindingsTest` writes its own synthetic inputs (a Qualtrics `Status` 256 row, a shared IP with a
"No" answer, a one-question yes/no survey, a blank duration column with page times, a `NaN` grid cell,
blank attention checks, a semicolon file with decimal commas, a UTF-16 file and a Google Forms
`Timestamp` column); each test states its expected values inline.
