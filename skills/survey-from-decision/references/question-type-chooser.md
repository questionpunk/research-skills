# Question-type chooser

Pick the type from what the table shell needs in its cells, not from what is easy to build. Read the first
table top to bottom and stop at the first row that matches. Sources for each rule are in
[sources.md](sources.md).

## 1. From the cell to the type

| The shell's cell needs | Type (use this name in the question table) | Options | Analysis line |
|---|---|---|---|
| Who qualifies, or who gets a block | `single choice` (screener or filter) | Concrete behaviours; the qualifying answer not obvious | Base definition; report how many were screened out |
| % who did a thing in a period | `open number` | "open number (times)" over a named recent period | % with 1 or more; median; distribution in bands set after seeing the data |
| How much or how often | `open number` | "open number (unit)"; one unit, one period | Median and quartiles; mean only without extreme values |
| % holding one of several exclusive positions | `single choice` | Complete, mutually exclusive list; "None of these" when possible | % per option with interval; largest gap against the threshold |
| % choosing between the options of the decision, described as outcomes | `forced choice` | Two (or three) statements of equal length and tone, plus "No preference" | % per statement; difference between the two |
| Which of several things apply | `multiple select` | Complete list, "None of these" exclusive and last | % selecting each (they do not add to 100) |
| Strength of a one-directional feeling (importance, difficulty, interest, frequency in words) | `rating, 5-point unipolar` | Not at all / Slightly / Moderately / Very / Extremely + construct | % top two; full distribution |
| Position between two opposites (satisfied–dissatisfied, easier–harder, better–worse) | `rating, 7-point bipolar` | Three labelled points each side and a labelled midpoint | % top two, % bottom two; full distribution |
| The same rating for several items | `grid` of unipolar or bipolar ratings | Same scale on every row; 5 rows at most | One row per item; rank items by % top two |
| The top item out of a short list (6 or fewer) | `single choice` ("which one matters most") | The list, order randomised | % first choice |
| Priority across more than 6 items | Not in this survey | Use `maxdiff-design` | — |
| The reason behind a closed answer | `open text` | "open text", optional, right after the closed question | Coded into themes with `open-ended-coding`; % per theme among those asked |
| A category you cannot list yet | `open text` | "open text" | Code first; closed list in the next wave |
| A segment column | `single choice` | Bands that match how the business already segments | Column of the shells; check each column's n |
| A tracked measure (recommendation 0–10, an existing satisfaction item) | Keep the existing type | Unchanged wording and scale | As tracked before, so waves compare (`nps-analysis` for 0–10 recommendation) |
| A price or willingness to pay | Not a single question | Use `pricing-research-plan` | — |

## 2. Types to avoid, and what to use instead

| Tempting | Problem | Use |
|---|---|---|
| Agree / disagree statements | People lean towards agreeing whatever the content; the respondent must first form the real rating and then translate it | A rating whose options name the construct ("How easy or difficult…") |
| Yes / no on an opinion | Same leaning, and no strength | Forced choice between two statements, or a rating |
| Yes / no on loosely defined behaviour ("Do you use X?") | "Use" is undefined, no period | Open number over a named period. Yes / no is fine for a filter on one concrete event in a named period |
| Vague frequency words (often, regularly, sometimes) | Each respondent defines them differently | Open number over a named period |
| Pre-set number ranges | The ranges tell people what is normal and shift answers | Open number; band it in analysis |
| Full ranking of a long list | Slow, error-prone on phones, hard to analyze | "Which one matters most", or `maxdiff-design` |
| "Would you use / buy / pay for…" | People overstate what they will do | What they did last time, what they use now, what they paid |
| "Should we build X?" | Hands the decision to the respondent | Measure the behaviour the decision rule depends on |
| A short closed list plus "Other" | Respondents stay inside the offered options | A complete list from earlier open answers, or the open question |
| Double-barrelled ("fast and reliable") | Two answers, one field | Two questions |
| "Don't know" on an attitude item | An easy exit for people who have a view | A filter question before the block; "Not sure" only for facts |
| Numbered scale with labelled ends only | Middle points mean different things to different people | Every point labelled with words |

## 3. Options checklist for any closed question

- Exhaustive: every respondent in the base can pick something true for them.
- Mutually exclusive, unless the type is multiple select.
- Same grammatical form and similar length for every option.
- Scales run in one direction throughout the survey (low to high or the reverse, never mixed).
- Unordered lists are randomised; "None of these" and "Other" stay last. Ordered lists (scales, time, size)
  are never randomised.
- No option the analysis will merge with another anyway. Merge it now.

## 4. One question, one cell

Before keeping a question, complete this sentence: "The answer fills row __ / column __ of table T__, and
the number is compared with the threshold in rule __ (or defines the base / the column)." If the sentence
cannot be completed, the question goes to "Questions deliberately left out" with the reason `no shell`.
