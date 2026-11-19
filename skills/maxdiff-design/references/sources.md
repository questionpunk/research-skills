# MaxDiff design: method sources

Checked against the sources below on 2026-11-12. Each rule names the source it was read in ([S1] to [S10]).
Rules the script adds by itself are listed under "Script conventions" and are not from the literature.

Notation: K = number of items in the study, k = items shown per set, S = sets per respondent,
V = questionnaire versions. In block-design notation v = K, b = S, r = times an item appears in one version,
lambda = times a pair of items appears together in one version.

## Formulas and thresholds

### Sets per respondent

- **Times an item is shown to one respondent = S x k / K** (exact when the design is balanced). Worked example
  in [S1]: 20 items, 4 per set, 20 sets, so each item is displayed 4 times.
- **Aim for 3 to 5 exposures per item per respondent.** [S1]: enough sets that "each item has the opportunity
  to appear from three to five times per respondent".
- **Minimum for individual-level (HB) scores: S = 3K/k**, rounded up. [S1] gives the formula with K and k
  defined as above. It rests on Orme's 2005 simulation, quoted in [S2] p. 11: "displaying each item three or
  more times per respondent works well for obtaining reasonably precise individual-level estimates with HB".
  [S4] states the same rule as "Ask enough questions to show each item 3 times to a respondent".
- **Below 2 exposures the software warns.** [S1] (Lighthouse) and [S3] (Discover) both warn when each item is
  displayed fewer than 2 times per respondent.
- **Sample size changes the rule.** [S3]: for samples of 50 to 400, show each item 3 or more times per
  respondent; for samples of 600 or more, 1 to 2 times "is typically sufficient". [S3] says nothing about
  samples between 400 and 600.

### Items per set

- **4 or 5 per set.** [S1]: "we recommend displaying either four or five items at a time". [S3] (Discover)
  says three to five, recommends five or fewer, and warns above 7 items per task. [S7] (Displayr): usually 5,
  4 for wordy items, 6 for easy ones.
- **More than about 5 adds little.** [S2] p. 10, summarising Orme 2005: precision gains are minimal above five
  items per set for studies up to about 30 items; Chrzan and Patterson 2006 confirmed with real respondents
  that about 4 or 5 per set works best.
- **No more than half the items in one set (k <= K/2).** [S1], and [S2] p. 11: with more, precision for
  middle-ranked items falls.
- **At least 3 per set** for a best and a worst choice. [S2] p. 6 (a subset "with a minimum of three items");
  [S3]: "Number of items per task must be 3 or more". Two per set is a paired comparison.

### Number of items

- **At least six items** for a MaxDiff exercise in [S3]. With fewer, a ranking question covers the same
  ground.
- **Around 30 or fewer** is the limit [S3] suggests against fatigue. Above about 30, [S5] says to raise the
  sample size, and [S1] describes sparse designs.

### Versions

- [S1]: default 300 versions, at most 999, and "at least four different versions" for paper questionnaires.
- [S7]: "10 is sufficient to minimize order and context effects" (attributed there to Sawtooth), and nothing
  speaks against a separate design per respondent.
- [S7], caveat: different versions are a source of variation between respondents and may influence a
  segmentation, so one version is often better when the aim is to compare respondents with each other.
- [S2] p. 10: versions need not be completed by equal numbers of respondents, and no version needs a minimum
  sample.

### Design criteria

[S2] p. 8 lists what the Sawtooth designer optimises, in this order of priority:

1. **Frequency (one-way) balance:** each item appears an equal number of times.
2. **Orthogonality (two-way balance):** each item appears with each other item an equal number of times.
3. **Connectivity:** the items cannot be split into two groups with no item of one group ever shown with an
   item of the other. Needed to put all items on one scale. [S1]: by default a version without connectivity
   is rejected, because individual-level estimation becomes very difficult.
4. **Within-set positional balance:** each item appears equally often in each position.
5. **Across-set positional balance:** avoid the same item in successive sets.

[S2] p. 8: the designer repeats its algorithm 1000 times and keeps the replication with the best one-way
balance, then two-way, then positional balance. [S2] p. 10: exact balance in all tables is usually impossible
and is not required for unbiased estimates.

### Item correlations

[S7] judges a design by the correlations between its item columns (1 when the item is in a set, 0 when
not). They are slightly negative in any MaxDiff design; values between -0.5 and 0.5 "should ... cause no
concern", and -1 means two items never appear together and one is always there when the other is not.
For two items shown n_a and n_b times in N sets and together n_ab times:
correlation = (N n_ab - n_a n_b) / sqrt(n_a (N - n_a) n_b (N - n_b)).
In a BIBD every pair has the same value, (b lambda - r^2) / (r (b - r)); for (7, 3, 1) that is
(7 - 9) / (3 x 4) = -0.1667.

### Balanced incomplete block designs (BIBD)

From [S6]:

- Necessary conditions: **b k = v r** and **lambda (v - 1) = r (k - 1)**; Fisher's inequality **b >= v**.
- The conditions are not sufficient: a design with those parameters may not exist (the article's example is
  (43, 7, 1)).
- A design with b = v is symmetric. The (7, 3, 1) design (Fano plane) is the smallest: 7 sets of 3, each item
  3 times, each pair once.
- The complement of a design (replace each set by the items it leaves out) is again a BIBD with
  k' = v - k, r' = b - r, **lambda' = lambda + b - 2r**. The complement of (7, 3, 1) is (7, 4, 2).

- **Affine planes** [S10]: a finite affine plane of order n has n^2 points, n^2 + n lines, n points on each
  line and n + 1 lines through each point, and any two points lie on exactly one line. Read as a design:
  v = n^2, b = n^2 + n, k = n, r = n + 1, lambda = 1. Examples: (9, 3) with 12 sets, (25, 5) with 30 sets.
  All known affine planes have prime or prime-power order. The script builds prime orders only, from the
  lines y = m x + c and x = c over the integers mod q (the standard coordinate construction; the tests count
  every pair).
- A published example used as a fixture: the 7-item, 7-set, 4-per-set design printed in the support.BWS
  manual [S9] (from `find.BIB(trt = 7, k = 4, b = 7)`).

A BIBD in a MaxDiff version means one-way and two-way balance are both exact. Most (K, k, S) combinations
have none, which is why the criteria above ask for "equal or as near as possible".

### Sample size

- [S5]: "at least 300 respondents in total" and "at least 200 for every separately reportable subgroup";
  with more than about 30 items raise both (the post's example: double them at 60 items).
- [S4] gives the lower figure: most MaxDiff surveys have at least 200 respondents, or 200 per subgroup.
- For a margin of error or a comparison between groups, use the sibling skill `survey-sample-size`.
- Sparse designs (each respondent sees an item once or less), analysed with pooled models only: [S1] says
  each item "should be seen by the segment or population of interest at least 500 times and preferably 1000
  times". Item exposures in a group = respondents x S x k / K.

### More than about 30 items

[S8] describes three approaches, all analysed with information pooled across respondents:

- **Sparse MaxDiff:** every item stays in the design and a respondent typically sees each one once.
  Sawtooth "generally prefer[s]" it to Express for long lists. Its example of a 160-item study had a sample
  in the thousands.
- **Express MaxDiff:** each respondent gets a random subset of the list (for example 30 items) and a full
  design on that subset; scores for items a respondent never saw sit near the population average.
- **Bandit MaxDiff:** an adaptive version that shows the leading items more often; [S8] cites a study with
  337 items.

### Anchoring

[S2] pp. 15-17: MaxDiff scores are relative. Two add-ons give an absolute threshold: Louviere's indirect
dual-response question after each set, and Lattery's direct method (a separate question on each item).
The indirect method "should probably not be used with more than 4 items shown per set".

## Script conventions (ours, not from the literature)

- **Default items per set:** 4, or 3 when 4 would exceed half the items (6 or 7 items). Under 6 items the
  script asks for `--per-set`.
- **Default sets:** 3K/k rounded up (`--exposures` changes the 3; values above 5 get a note).
- **Default versions:** 10, the figure [S7] gives as enough to average out order and context effects. It
  sits between the paper minimum of 4 and Sawtooth's 300 [S1], and 10 versions can still be set up by hand
  in tools that cannot import a design. Use up to 300 when the tool assigns versions itself. When respondents
  are to be compared with each other the script states both views rather than picking one: [S7] prefers 1
  version, Sawtooth fields many and scores individuals with HB [S1] [S2].
- **Length estimate:** sets x 20 seconds. The 20 seconds is an assumption, not a sourced figure; pass
  `--seconds-per-set` with a pilot timing.
- **`--respondents N`:** compared with [S5]'s 300 in total and 200 per reported subgroup, both raised in
  proportion to K / 30 above 30 items (300 x K / 30; [S5]'s own example doubles them at 60 items). Total
  exposures per item = N x (times the least-shown item appears per version), compared with the 500 and 1000
  of [S1] only for a sparse design (under 2 exposures per respondent, the line where [S1] and [S3] warn);
  above that the report says the rule does not apply. The per-respondent line follows [S3]: under 50
  respondents is outside its guidance, 3 or more exposures fit it, under 1 exposure is below its 1 to 2 at any
  sample, and the exposure warning is lifted at 600 or more respondents when each item is shown at least
  once per respondent.
- **Default seed:** 1. **Default restarts:** 10 per version ([S2]'s designer uses 1000 replications; raise
  `--restarts` for a slower, slightly better search).
- **Exact constructions tried:** a cyclic difference set when S = K (search stops after 200000 nodes), the
  affine plane when K = q^2, k = q, S = q^2 + q for a prime q up to 7, and all k-subsets when S = C(K, k)
  and S is at most 50. Otherwise a seeded randomized search. Its Method line reports what the diagnostics
  show: an exact BIBD when every pair count came out equal; "no BIBD has these parameters" only when the
  counting conditions b k = v r, lambda (v - 1) = r (k - 1) or Fisher's b >= v fail [S6]; otherwise that the
  conditions hold and the search found none, which proves nothing about existence (for example a Steiner
  triple system, a (v, 3, 1) design, exists exactly when v = 1 or 3 mod 6 [S11], and the search can miss it).
- **Pass, warn and fail thresholds:**
  - fail: a set with fewer than 2 different items, or one that shows every item (a BIBD needs 2 <= k < v,
    and a complete set is not a MaxDiff task); fewer than 3 items per set ([S3]: "must be 3 or more";
    generation refuses `--per-set 2`); an item repeated inside a set; sets or versions of different shape; item frequencies more than 1
    apart inside a version; items that split into groups never compared (no connectivity overall);
  - warn: item frequencies more than 1 apart over all versions (fail with a single version); pair counts
    more than 1 apart inside a version; a pair that never appears together; an item missing from a version
    (a respondent then says nothing about it, so only pooled scores cover it); an item's position counts more
    than 1 apart; a version that is not connected on its own; fewer than 3 exposures per respondent (unless
    `--respondents` is 600 or more); more than half the items or more than 5 items in a set; an item
    correlation outside -0.5 to 0.5; the same set twice in one version when enough different sets exist
    (the generator trades items between sets to avoid it).
  - reported, not judged: the largest position gap inside one version (the positional criterion judges the
    whole design), and the number of item pairs with no correlation (an item in every set or in none).
- **Prohibited pairs** are not supported and no threshold for them is stated.
  "Within 1" is the tightest bound that always exists for item and position frequencies. For pair counts it
  does not always exist, so a larger gap is a warning.

## Where practitioners disagree

- **Items per set:** [S1] says 4 or 5, [S3] says 3 to 5 and only warns above 7.
- **Exposures:** [S1] and [S4] ask for 3 or more. [S3] says that for samples of 600 or more, 1 to 2 exposures
  per item "is typically sufficient", because pooled information carries the estimate.
- **Versions:** Sawtooth defaults to 300 ([S1]); Displayr calls 10 sufficient and prefers one version for
  segmentation ([S7]); many survey tools field one fixed design or draw random sets. One version leaves order
  and context effects in the data; random sets without checks are the first pitfall below.
- **Long lists:** Sawtooth prefers sparse to Express designs ([S8]); both need pooled analysis.
- **Sample size:** 300 in total ([S5]) against 200 ([S4]). Both are rules of thumb, not power calculations.
- **How much balance matters:** [S2] treats small imbalance as harmless for logit and HB estimation, while
  counting analysis (best minus worst counts) is valid only when items are shown equally often.

## Sources

- [S1] Sawtooth Software, Lighthouse Studio manual, "Designing the Study" (MaxDiff):
  https://sawtoothsoftware.com/help/lighthouse-studio/manual/maxdiff-designing-study.html
- [S2] Sawtooth Software (2020), *The MaxDiff System Technical Paper*, version 9, October 2020:
  https://content.sawtoothsoftware.com/assets/cb58ce5e-9d49-4d3c-b066-24bb735ad26d
- [S3] Sawtooth Software, Discover help, "MaxDiff design settings":
  https://sawtoothsoftware.com/help/discover/survey-elements/maxdiff/design-settings
- [S4] Sawtooth Software, "MaxDiff Calculator & Design Guidelines":
  https://sawtoothsoftware.com/resources/maxdiff-calculator
- [S5] Sawtooth Software, "MaxDiff Sample Size Calculation Best Practices" (updated 30 September 2024):
  https://sawtoothsoftware.com/resources/blog/posts/maxdiff-sample-size
- [S6] Wikipedia, "Block design" (conditions, Fisher's inequality, complements, Fano plane):
  https://en.wikipedia.org/wiki/Block_design
- [S7] Tim Bock, "How to Create a MaxDiff Experimental Design in Displayr", Displayr blog:
  https://www.displayr.com/how-to-create-a-maxdiff-experimental-design-in-displayr/
- [S8] Sawtooth Software, Lighthouse Studio manual, "Developing a List of Items":
  https://sawtoothsoftware.com/help/lighthouse-studio/manual/maxdiff-list-of-items.html
- [S9] Hideo Aizaki, R package support.BWS, reference manual (version 0.4-6):
  https://cran.r-project.org/web/packages/support.BWS/support.BWS.pdf
- [S10] Wikipedia, "Affine plane (incidence geometry)":
  https://en.wikipedia.org/wiki/Affine_plane_(incidence_geometry)
- [S11] SageMath reference manual, "Balanced Incomplete Block Designs (BIBD)": "A Steiner Triple System of an
  n-set exists if and only if n = 1 (mod 6) or n = 3 (mod 6)", built by Bose's and Skolem's constructions:
  https://doc.sagemath.org/html/en/reference/combinat/sage/combinat/designs/bibd.html

Background, cited through [S2]'s reference list:

- Finn, A. and Louviere, J. J. (1992), "Determining the Appropriate Response to Evidence of Public Concern:
  The Case of Food Safety", *Journal of Public Policy and Marketing* 11(1), 12-25. The first published
  best-worst study.
- Orme, B. (2005), "Accuracy of HB Estimation in MaxDiff Experiments", Sawtooth Software technical paper.
- Chrzan, K. and Patterson, M. (2006), "Testing for the Optimal Number of Attributes in MaxDiff Questions",
  Sawtooth Software Conference Proceedings.
- Lattery, K. (2010), "Anchoring Maximum Difference Scaling against a Threshold: Dual Response and Direct
  Binary Responses", Sawtooth Software Conference Proceedings.
- Louviere, J. J., Flynn, T. N. and Marley, A. A. J. (2015), *Best-Worst Scaling: Theory, Methods and
  Applications*, Cambridge University Press.

## Pitfalls

- Random sets with no balance check: items end up shown unequally, and counting scores are biased.
- More than half the items in a set (k > K/2).
- Fewer than 2 exposures per item while promising individual-level scores or segmentation.
- The same item order inside every set (position bias), or a single version for everyone.
- A design that is not connected, so items cannot be placed on one scale.
- A design that cannot be reproduced: seed the generator and keep the design file with the data.
- Items that are not comparable (features mixed with prices, or two wordings of the same idea).
- Reading scores as absolute: without an anchor, the top item is only better than the others on the list.
