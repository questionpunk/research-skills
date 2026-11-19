# Kano analysis: method sources

Checked 2026-11-19. "Read" means the page was read in the source on that date: Berger et al. (1993) and
Matzler and Hinterhuber (1998, pp. 32-34). "Via the spec" means the claim comes from QuestionPunk's internal Kano
method spec (2026-10-08), whose author read the source; those were not re-read and are marked so on purpose. Page numbers are the printed journal pages.

## Contents

- The questionnaire
- The evaluation table
- Category per feature
- Fong's test
- Better and Worse
- Self-stated importance
- Warnings and their thresholds
- Caveats from the literature
- Sources

## The questionnaire

- One pair per requirement: a functional form ("If the gas mileage is good, how do you feel?") and a
  dysfunctional form ("If the gas mileage is poor, how do you feel?"), each answered with the same five options:
  "I like it that way", "It must be that way", "I am neutral", "I can live with it that way", "I dislike it that
  way" (Berger et al. 1993, p. 6, Fig. 3 and 5; read). These English answers are the CQM translation as
  taught by Shoji Shiba (Berger p. 5, footnote; via QuestionPunk's method spec, not re-checked).
- Ask about the benefit in the customer's terms, one thought per question; test internally first; casual changes
  to the answer wording are risky (Berger pp. 7, 9, 25-26; via the spec).
- Kano (1995, p. 66) recommends a sixth answer, "others", with space for comments, and a pilot: 20-30% "others"
  signals poorly worded questions (via the spec, which read the chapter). The script reads the five answers
  only; collect "others" as a separate comment if you offer it.
- Oral, explained interviews worked best because the format is unfamiliar (Matzler and Hinterhuber 1998, p. 32;
  read). In a self-completed survey, show an example first.
- The `design` command fills the template "If <product> had <feature>, how would you feel?" / "...did not
  have...". It is a starting draft (convention of this skill); Berger's examples use "good" / "poor" for
  performance features.
- The wording checks (no negation word in the dysfunctional question, a negation in the functional one, a double
  negative, two features joined by "and"/"or", identical questions, over 140 characters, over 20 features) are
  conventions of this skill and advisory: a performance contrast such as "arrives today" / "arrives next week"
  has no negation word and is still a valid pair (Berger's "good" / "poor" is another).

## The evaluation table

Berger et al. (1993), p. 6, Fig. 4 (read). Rows are the functional answer, columns the dysfunctional:

| Functional / Dysfunctional | like | must-be | neutral | live with | dislike |
|---|---|---|---|---|---|
| like | Q | A | A | A | O |
| must-be | R | I | I | I | M |
| neutral | R | I | I | I | M |
| live with | R | I | I | I | M |
| dislike | R | R | R | R | Q |

A attractive, O one-dimensional, M must-be, I indifferent, R reverse, Q questionable. The tests re-derive the
table from the category definitions (satisfied by presence and dissatisfied by absence is O, and so on).

Coding: QuestionPunk stores and exports answers as 1-5 in this order (checked in the app source,
`KANO_ANSWERS`). Some tools number the other way; `--code-order dislike-first` handles it, and only bare
numbers depend on it (text answers and `--counts` do not). Only whole codes are read ("2", or "2.0" from a
spreadsheet); "2.5" is unreadable, not 2. A number followed by a label the script does not know ("1 - Strongly
disagree", another language) is unreadable too, because the label may run the other way. Importance likewise
takes whole 1-9. These reading rules are conventions of this skill.

Column detection (convention of this skill): `_f`/`_d`, `functional`/`dysfunctional` and similar suffixes pair
by stem. A `functional`, `func`, `dysfunctional`, `dysfunc` or `dys` column with no partner stops the run; a
generic one (`_has`, `_pos`, ` D`) with no partner is ignored and listed in the notes, since ordinary columns
end that way too. Feature names that differ only in case are one feature.

Reversed codes map (f, d) to (6 − f, 6 − d): every true A, O and M answer becomes R, true R becomes A, O or M,
and I and Q stay where they are (derivable from the table above). Swapping the functional and dysfunctional
columns does the same to A, O and M, so the warning asks about both. So the script warns when, over all features,
R is the mode for most features, R is more than 20% of answers, or R outnumbers A + O + M. The 20% and the
comparison are conventions of this skill; the warning asks for the codebook and does not rescore. Because Q sits
only at (like, like) and (dislike, dislike), neither swapping the questions nor reversing the codes changes Q: a
high Q share points at unclear wording or inattentive respondents.

## Category per feature

- The mode: "use whatever code appears most often in the responses for that requirement" (Berger p. 10).
- Ties: take the category with "the greatest impact on the product (use the following ordering: M > O > A > I)"
  (Berger p. 11; read). R and Q come last (R before Q): convention of this skill, as no source orders them.
  Any tie, including three-way ties, is reported as a tie, not as a clear category.
- A few R answers are not an error: they may be a distinct group of customers, "a good market segmentation
  opportunity" (Berger p. 10; read).
- If most respondents score R, the requirement was probably worded the other way: rescore everyone with the
  answers swapped (Berger p. 10; read). The script flags it and does not rescore automatically. Check the
  codebook and the question direction first; if both are right, an R mode is a real finding (respondents do not
  want the feature), not an error to be wished away.
- Features are listed M, O, A, I, R, Q, then by Worse (most negative first), following Berger's grouping order.

## Fong's test

- With a and b the counts of the two most frequent categories and n all answers to the feature (R and Q
  included), the top category is **not** a clear winner when |a − b| < 1.65·√((a + b)(2n − a − b)/(2n)).
- Fong, D. (1996), *CQM Journal* 5(3). **Not read** (volume and issue confirmed by QuestionPunk's method spec
  from the editor's contents list). The formula is taken from Raverta and Loera (2026), *Food Frontiers* 7(3),
  e70272, Methods section 3.3, which applies it; **read by the QuestionPunk spec author on 2026-10-08; the
  publisher page refused automated reads on 2026-11-19.** The tests call the test with three of their Table 2 count
  pairs (n = 107: 42 vs 41 → threshold 11.761, not clear; 63 vs 24 → 11.86, clear; 52 vs 42 → 11.98, not
  clear). The other counts in those rows were not re-checked, so no fixture reproduces the rows.
- A tie (a = b) is never a clear winner.
- 1.65 is the two-sided 90% (one-sided 95%) normal critical value, so "clear" is a 90% statement, not the 95% of
  the Better/Worse intervals. The test is a large-sample approximation: on a small base a "clear" verdict is
  weak (the script also flags bases under 30). When several classes tie for second place the script names them
  all ("A vs M/O"); the threshold is the same because only the counts enter it.

## Better and Worse

- Better = (A + O)/(A + O + M + I); Worse = −(O + M)/(A + O + M + I); R and Q are left out (Timko, in Berger et
  al. 1993, p. 18; read). Fig. 16 (p. 18) gives seven worked rows, all reproduced in the tests.
- Plot Better (0 to 1, up) against |Worse| (0 to 1, across); corners Attractive (top left), One-dimensional (top
  right), Must-be (bottom right), Indifferent (bottom left) (Berger p. 19, Fig. 17; read).
- Uncertainty: "the statistical uncertainty of the averages is quite large (tens of percent). Don't count on
  these numbers to differentiate between close results" (Berger p. 20; read).
- The script adds Wilson (1927) intervals (95% unless `--confidence` says otherwise) for Better and |Worse|,
  treating each as a share of the A + O + M + I answers (conditional on that base, which the table prints next to
  n). Convention of this skill: no source gives an interval; this one makes Berger's "tens of percent" visible
  per feature. The intervals describe one feature at a time; they are not a test of the difference between two
  features, whose answers come from the same respondents.
- Matzler and Hinterhuber (1998, p. 33) call them the extent of satisfaction and dissatisfaction (citing Berger).
  Their edge-grip example is in percentages, not counts: Table 1 (p. 33) A 7.0, O 32.3, M 49.3, I 9.5, R 0.3,
  Q 1.5; Table 2 (p. 34) rounds to A 7, O 33, M 50, I 10 and prints 0.40 and −0.83 (read). The fixture
  checks only those coefficients.

## Self-stated importance

- "How important is it or would it be if: [requirement]?", 1 "Not at all important" to 9 "Extremely important"
  (Berger p. 11-12; via the spec). The `design` command asks "How important is this to you: <feature>?" on
  the same 1-9 scale, because feature names are noun phrases, not clauses (the same adaptation QuestionPunk's
  question type makes).
- Timko multiplied Better and Worse by the importance, scaled to 0-1 as (r − 1)/8 on the 1-9 scale (Berger p. 19,
  footnote 33; read). The script reports the mean importance and these weighted coefficients
  (`better_weighted`, `worse_weighted`, using the mean importance) in `--json`. The mean includes everyone who
  answered the pair, R and Q included, while Better and Worse leave R and Q out (convention of this skill).
- When 10 or more importance answers never exceed 7, the script notes that the scale may be 1-5 or 1-7, for
  which the (r − 1)/8 scaling is wrong (convention of this skill). 10 and 0 are not read on the 1-9 scale.
- Reading: self-stated importance helps "establish your priorities for product development" (Matzler and
  Hinterhuber 1998, p. 32; read), so use it to order features within a category, not to change the category.

## Warnings and their thresholds

- Questionable answers above 10% of a feature (or overall): convention of this skill, shared with QuestionPunk's
  report. Sauerwein et al. (1996) saw no attribute above 2%; Berger p. 10 says drop a requirement for now if it
  gets "a substantial number" of Q.
- Small base under 30 answers per feature: convention of this skill, shared with QuestionPunk's report.
- More than 5% unreadable answers stops the run (pack rule).
- Reverse warning: R the mode of most features, R over 20% of all answers, or R more than A + O + M (convention
  of this skill; reasoning under "The evaluation table").

## Why tools disagree

When another tool gives a feature a different category, check these in order:

- The evaluation table. Compare the tool's cells with Fig. 4 (Berger p. 6; read); for example (must-be,
  must-be) is I in Berger's table. Some tools score some cells differently (not checked here); the table
  decides every count.
- The code order (1 = like or 1 = dislike) and which column is functional.
- The category rule. Berger uses the mode and reads the second and third most frequent answers alongside it
  (pp. 10-11; read). Tools that use a different rule, such as one comparing A + O + M with I + R + Q, can
  disagree on spread answers (that rule was not found in Berger pp. 10-11; source not checked).
- Ties: Berger breaks them M > O > A > I (p. 11; read).
- Continuous analysis. DuMouchel's method (Berger pp. 20-21; read) scores the functional answer like 4,
  must-be 2, neutral 0, live with −1, dislike −2, and the dysfunctional answer like −2, must-be −1, neutral 0,
  live with 2, dislike 4, then places each feature at its average scores; a feature can sit in a different
  quadrant from its mode. This skill does not compute it.
- Better/Worse quadrants are not categories: the chart places a feature by its coefficients, the table by its
  mode.

## Caveats from the literature

- Mikulić and Prebežac (2011), *Managing Service Quality* 21(1):46-66 (via the spec, which read it): wording
  moves the category (asking about presence gave A, about performance gave M, for the same feature); the method
  says nothing about an attribute's weight in overall satisfaction; respondents need no experience of the
  feature.
- Answers spread over several categories often mean segments (Matzler and Hinterhuber 1998, p. 33, read:
  expert skiers saw edge grip as must-be, novices as one-dimensional). Use `--segment-col`.

## Sources

- Berger, C., Blauth, R., Boger, D., Bolster, C., Burchill, G., DuMouchel, W., Pouliot, F., Richter, R.,
  Rubinoff, A., Shen, D., Timko, M. & Walden, D. (1993). Kano's methods for understanding customer-defined
  quality. *Center for Quality of Management Journal* 2(4):3-35. Read 2026-11-19 at
  walden-family.com/public/cqm-journal/2-4-Whole-Issue.pdf.
- Fong, D. (1996). Using the self-stated importance questionnaire to interpret Kano questionnaire results.
  *CQM Journal* 5(3). Not read.
- Kano, N., Seraku, N., Takahashi, F. & Tsuji, S. (1984). Attractive quality and must-be quality. *Hinshitsu*
  14(2):147-156 (J-STAGE pagination; often cited as 39-48). doi:10.20684/quality.14.2_147. In Japanese; not
  read.
- Kano, N. (1995). Upsizing the organization by attractive quality creation. In G. K. Kanji (ed.), *Total
  Quality Management*, pp. 60-72. Springer. Via the spec.
- Matzler, K. & Hinterhuber, H. H. (1998). How to make product development projects more successful by
  integrating Kano's model of customer satisfaction into quality function deployment. *Technovation*
  18(1):25-38. Pages 32-34 read 2026-11-19 at hinterhuber.com (author-posted PDF).
- Mikulić, J. & Prebežac, D. (2011). A critical review of techniques for classifying quality attributes in the
  Kano model. *Managing Service Quality* 21(1):46-66. Via the spec.
- Raverta, P. & Loera, B. (2026). Indifferent or attractive? An exploratory Kano model application to
  cultivated meat products. *Food Frontiers* 7(3), e70272. doi:10.1002/fft2.70272. Authors and title from the
  Crossref record (read); the article via the spec, as the publisher page refused automated reads.
- Sauerwein, E., Bailom, F., Matzler, K. & Hinterhuber, H. H. (1996). The Kano model: how to delight your
  customers. IX International Working Seminar on Production Economics, Innsbruck, preprints vol. I, 313-327.
  Via the spec.
- Wilson, E. B. (1927). Probable inference. *JASA* 22:209-212.
- "The spec" is QuestionPunk's internal Kano method spec (2026-10-08), whose author read the PDFs named above and
  recorded page numbers; items marked "via the spec" were not re-read for this skill.
