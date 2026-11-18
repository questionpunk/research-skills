# Fixtures for maxdiff-design

Synthetic designs only (items are the letters A to G); no respondent data. Every expected value below was
worked out by hand from the design tables, not by running the script. The `*.expected.json` files hold the
same numbers for the tests.

| File | What it is |
|---|---|
| `items7.input.txt` | Seven items, A to G, one per line |
| `bibd_7_3_1.input.csv` | The (7, 3, 1) balanced incomplete block design (Fano plane), one version |
| `bibd_7_4_2.input.csv` | Its complement, the (7, 4, 2) design, one version |
| `unbalanced.input.csv` | A deliberately bad design that `--check` must fail |
| `affine_9_3.input.csv` | The affine plane of order 3: 9 items, 12 sets of 3, written from a 3 x 3 grid |
| `published_bws_7_4.input.csv`, `fruit7.input.txt` | A published 7-item BIBD, in the wide layout with item numbers |

Layout of the design files: `version,set,position,item`, except the published one, which is wide
(`version,set,item1..item4`) with 1-based item numbers into `fruit7.input.txt`.

**Item correlation** (in every `expected.json`): for two items shown n_a and n_b times in N sets and
together n_ab times, (N n_ab - n_a n_b) / sqrt(n_a (N - n_a) n_b (N - n_b)).

- Both 7-item BIBDs: N = 7. (7, 3, 1): (7 x 1 - 3 x 3) / sqrt(3 x 4 x 3 x 4) = -2 / 12 = -0.1667.
  (7, 4, 2): (7 x 2 - 4 x 4) / sqrt(4 x 3 x 4 x 3) = -2 / 12 = -0.1667. Same for every pair.
- Unbalanced design: N = 4. A (sets 1-3) and E (set 4): (4 x 0 - 3 x 1) / sqrt(3 x 1 x 1 x 3) = -1, the
  minimum. E and F (both only in set 4): (4 x 1 - 1 x 1) / sqrt(1 x 3 x 1 x 3) = 1, the maximum. Outside
  -0.5 to 0.5, so a **warning**.

## bibd_7_3_1: seven items, seven sets of three

Built by hand from the cyclic difference set {0, 1, 3} mod 7 (the Fano plane; see
`../references/sources.md`, "Balanced incomplete block designs"): with A = 0 ... G = 6, set *i* holds the
items *i*, *i*+1 and *i*+3 (mod 7), in that order.

| Set | Position 1 | Position 2 | Position 3 |
|---|---|---|---|
| 1 | A | B | D |
| 2 | B | C | E |
| 3 | C | D | F |
| 4 | D | E | G |
| 5 | E | F | A |
| 6 | F | G | B |
| 7 | G | A | C |

Hand checks:

- **Item frequency.** Each column of the table is a rotation of A..G, so every item appears once per
  column: 3 times in all. Check with the identity bk = vr: 7 sets x 3 = 21 = 7 items x 3.
- **Times shown per respondent.** 7 sets x 3 / 7 items = 3.00.
- **Pair frequency.** Within a set the three differences are 1 (positions 1-2), 2 (positions 2-3) and 3
  (positions 1-3). Each of the 7 rotations gives one pair at each difference, and the differences 1, 2, 3
  (with their negatives 6, 5, 4) cover all 21 pairs of 7 items exactly once. So min = max = mean = 1,
  sd = 0, no pair is missing. Check with lambda (v - 1) = r (k - 1): 1 x 6 = 3 x 2.
- **Position frequency.** Each item appears once in each column: A [1, 1, 1], and the same for B to G.
  Largest gap 0.
- **Connectivity.** Every pair shares a set, so there is one component.
- **Criteria.** All pass: 3 per set is at most half of 7 (3.5), and 3.00 exposures meets the 3K/k rule
  (3 x 7 / 3 = 7 sets).

## bibd_7_4_2: seven items, seven sets of four

Set *i* is the complement of set *i* above, written as the items *i*+2, *i*+4, *i*+5, *i*+6 (mod 7).

| Set | Position 1 | Position 2 | Position 3 | Position 4 |
|---|---|---|---|---|
| 1 | C | E | F | G |
| 2 | D | F | G | A |
| 3 | E | G | A | B |
| 4 | F | A | B | C |
| 5 | G | B | C | D |
| 6 | A | C | D | E |
| 7 | B | D | E | F |

Hand checks:

- **Item frequency.** Again each column is a rotation: 4 appearances per item (7 x 4 = 28 = 7 x 4).
- **Pair frequency.** A complement of a (v, b, r, k, lambda) design has lambda' = lambda + b - 2r =
  1 + 7 - 6 = 2 (formula in `../references/sources.md`). Direct count for the pair A-B: sets 3 and 4, so 2.
  Total check: 7 sets x 6 pairs per set = 42 = 21 pairs x 2. min = max = mean = 2, sd = 0.
- **Times shown per respondent.** 7 x 4 / 7 = 4.00.
- **Position frequency.** [1, 1, 1, 1] for every item.
- **Criteria.** No failure. One warning: 4 per set is more than half of 7 items (4 x 2 = 8 > 7).

## unbalanced: a design `--check` must flag

| Set | Position 1 | Position 2 | Position 3 |
|---|---|---|---|
| 1 | A | B | C |
| 2 | A | B | D |
| 3 | A | C | D |
| 4 | E | F | G |

Hand checks:

- **Item frequency.** A 3; B 2 (sets 1, 2); C 2 (sets 1, 3); D 2 (sets 2, 3); E, F, G 1 each. Sum 12 =
  4 sets x 3. Range 3 - 1 = 2, more than 1: one-way balance **fails** (within the version and overall,
  which are the same thing with one version).
- **Times shown per respondent.** 12 / 7 = 1.7143, under 2: **warning**.
- **Pair frequency.** A-B 2 (sets 1, 2), A-C 2 (sets 1, 3), A-D 2 (sets 2, 3), B-C 1, B-D 1, C-D 1, E-F 1,
  E-G 1, F-G 1. Sum 12 = 4 sets x 3 pairs. Nine pairs occur, so 21 - 9 = 12 never occur. min 0, max 2,
  mean 12 / 21 = 0.5714. Variance = (3 x 2^2 + 6 x 1^2) / 21 - 0.5714^2 = 0.8571 - 0.3265 = 0.5306, so
  sd = 0.7284. Range 2: two-way **warning**; missing pairs: **warning**.
- **Position frequency.** A [3, 0, 0], B [0, 2, 0], C [0, 1, 1], D [0, 0, 2], E [1, 0, 0], F [0, 1, 0],
  G [0, 0, 1]. Largest gap 3 (item A): **warning**.
- **Connectivity.** A, B, C, D never share a set with E, F, G: 2 components, **fails**.
- **Result.** Does not meet the criteria; exit code 1.

## affine_9_3: nine items, twelve sets of three

Write the items P1 to P9 in a grid and take every row, column, diagonal and broken diagonal:

```
P1 P2 P3
P4 P5 P6
P7 P8 P9
```

| Sets | Lines | Items (in file order) |
|---|---|---|
| 1-3 | rows | 1 2 3, 4 5 6, 7 8 9 |
| 4-6 | columns | 1 4 7, 2 5 8, 3 6 9 |
| 7-9 | diagonals | 1 5 9, 2 6 7, 3 4 8 |
| 10-12 | other diagonals | 3 5 7, 1 6 8, 2 4 9 |

Hand checks:

- **Parameters.** v = 9, b = 12, k = 3. b k = v r gives r = 12 x 3 / 9 = 4. lambda (v - 1) = r (k - 1)
  gives lambda = 4 x 2 / 8 = 1. Fisher: 12 >= 9.
- **Item frequency.** Each item is in one row, one column and one line of each diagonal family: 4.
- **Pair frequency.** 12 sets x 3 pairs = 36 = C(9, 2), and no pair repeats (two cells of the grid lie in
  the same row, the same column, or on exactly one diagonal of one family), so every pair appears once.
- **Position frequency** (read off the table, items written in the order above): P1 [4, 0, 0],
  P2 [3, 1, 0], P3 [3, 0, 1], P4 [1, 3, 0], P5 [0, 4, 0], P6 [0, 3, 1], P7 [1, 0, 3], P8 [0, 1, 3],
  P9 [0, 0, 4]. Largest gap 4: positional **warning**, the only one.
- **Item correlation.** N = 12: (12 x 1 - 4 x 4) / sqrt(4 x 8 x 4 x 8) = -4 / 32 = -0.125.
- **Times shown.** 12 x 3 / 9 = 4.00.

## published_bws_7_4: a published BIBD in the wide layout

The design printed in the reference manual of the R package support.BWS (the example for
`find.BIB(trt = 7, k = 4, b = 7)`; source [S9] in `../references/sources.md`), with its item names
Apple, Orange, Grapes, Banana, Peach, Melon, Pear numbered 1 to 7.

| Set | item1 | item2 | item3 | item4 |
|---|---|---|---|---|
| 1 | 1 | 4 | 6 | 7 |
| 2 | 2 | 3 | 4 | 6 |
| 3 | 2 | 4 | 5 | 7 |
| 4 | 1 | 2 | 5 | 6 |
| 5 | 1 | 3 | 4 | 5 |
| 6 | 3 | 5 | 6 | 7 |
| 7 | 1 | 2 | 3 | 7 |

Hand checks:

- **Item frequency.** 1: sets 1, 4, 5, 7. 2: sets 2, 3, 4, 7. 3: sets 2, 5, 6, 7. 4: sets 1, 2, 3, 5.
  5: sets 3, 4, 5, 6. 6: sets 1, 2, 4, 6. 7: sets 1, 3, 6, 7. Four each (7 x 4 = 28).
- **Pair frequency.** lambda = r (k - 1) / (v - 1) = 4 x 3 / 6 = 2. Spot checks: 1-2 in sets 4 and 7;
  4-6 in sets 1 and 2; 5-7 in sets 3 and 6. Total 7 x 6 = 42 = 21 x 2.
- **Position frequency** (column counts): Apple [4, 0, 0, 0], Orange [2, 2, 0, 0], Grapes [1, 2, 1, 0],
  Banana [0, 2, 2, 0], Peach [0, 1, 2, 1], Melon [0, 0, 2, 2], Pear [0, 0, 0, 4]. The published design
  lists items in ascending order, so positional balance gets a **warning** (gap 4).
- **Other warning.** 4 per set is more than half of 7.
- **Result.** An exact BIBD; no failure.

## Generated designs (tests, no files)

The tests also generate designs and check properties that follow from the arithmetic, whatever the seed:

- `--items 7 --per-set 3`: 3K/k = 3 x 7 / 3 = 7 sets. A cyclic BIBD exists, so each version must have
  item frequency 3 and every pair exactly once; with the default 10 versions, 30 and 10.
- `--items 7 --per-set 4 --sets 7`: every pair twice per version (the (7, 4, 2) design).
- `--items 6 --per-set 3 --sets 20`: all C(6, 3) = 20 subsets; r = 20 x 3 / 6 = 10 and
  lambda = r (k - 1) / (v - 1) = 10 x 2 / 5 = 4.
- `--items 25 --per-set 5 --sets 30`: the affine plane of order 5. r = b k / v = 30 x 5 / 25 = 6;
  lambda = r (k - 1) / (v - 1) = 6 x 4 / 24 = 1; C(25, 2) = 300 pairs = 30 sets x 10 pairs. The test counts
  every pair in every version and requires exactly 1. With 2 versions: item frequency 12, pair count 2.
- `--items 9 --per-set 3 --sets 12`: the affine plane of order 3, same check (36 pairs, each once).
- `--items 16 --per-set 4 --sets 20`: 4 is not prime, so no affine construction; the search is used.
- `--items 60 --per-set 5 --sets 12 --respondents N`: 12 x 5 / 60 = 1 exposure per respondent, so N in
  total per item: 700 is above the minimum of 500, 300 is under it.
- `--items 12 --per-set 4 --respondents 300`: 9 sets; 300 x 9 x 4 / 12 = 900 exposures per item;
  length 9 x 20 s = 3.0 minutes, or 4.5 minutes at 30 s per set.
- `--items 20 --per-set 5`: 3 x 20 / 5 = 12 sets; 12 x 5 / 20 = 3 appearances per item per version exactly.
- `--items 10 --per-set 4`: 3 x 10 / 4 = 7.5, rounded up to 8 sets; 32 slots over 10 items means two items
  appear 4 times and eight appear 3 times in a version (range 1), and 3.2 exposures on average.
