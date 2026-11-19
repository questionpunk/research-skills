# Screener writer: method sources

Each rule in `scripts/screener_writer.py` and each piece of advice in `SKILL.md`, with its source. "Not
fetched" means the source is known from citing work but was not read for this skill; "convention of this
skill" means no published source sets the value.

Contents: Rules · Writing advice · Thresholds · Worked example · Sources

## Rules

| Rule | Basis |
|---|---|
| SC01-SC02 coverage | Each target criterion must be measured by a question, or the screener cannot select on it: a definition, not a published rule |
| SC03-SC06 routing | A screener is a branching questionnaire; every answer needs a defined path and at least one path must qualify (Dillman, Smyth and Christian 2014, on skip instructions and routing errors; not fetched) |
| SC07 screens nothing | A question tied to a criterion that cannot terminate or qualify anyone does not screen; a definition |
| SC08 yes/no | "DON'T rely on 'yes or no' questions" (Whitenton 2019) |
| SC09 distractors | Include incorrect answers "as plausible as the target answer", realistic as behaviours and as topics a company would study (Whitenton 2019). The minimum of two is a convention of this skill; quota questions (every option a valid group) and range questions are exempt. On a single-select with no `qualify` option, the answers that continue are treated as the targets, except on an exclusion question |
| SC10 stands out | Distractors must be as plausible as the target (Whitenton 2019); length and position are the visible cues this rule checks. Ratio 2 and "always first" are conventions of this skill |
| SC11, SC21 reveal the study | Screeners should "avoid revealing specific information about the study"; people who guess the topic may exaggerate to qualify (Whitenton 2019) |
| SC12 leading wording | Leading-pattern list copied in part from this pack's `survey-bias-check` (its sources) |
| SC13 none option | Every multi-select needs a way to say none applies, or people pick something to move on (Dillman, Smyth and Christian 2014; not fetched) |
| SC14 ranges | Answer ranges must be mutually exclusive and exhaustive (same rule as `survey-bias-check` SB010). Whole-number answers are assumed, so "under 5" ends at 4 and "over 5" starts at 6 (a convention of this skill) |
| SC15 articulation | Open questions about past experience are hard to game and show who can describe their experience (Whitenton 2019); asking one for moderated studies is standard recruiting practice (Sova and Nielsen 2003; not fetched). The study type is matched by word (interview, usability, focus group, diary, co-design, card sort, moderated, contextual inquiry; not "unmoderated") |
| SC16 select everything | Exclude people who select every option, especially across questions: a sign of eagerness to qualify (Whitenton 2019). Not raised when a non-"none" option already terminates; a plausible but fictitious option marked terminate is this skill's suggested way to do it (convention) |
| SC17-SC18 quotas | A set of cells with bounds [min_i, max_i] can sum to the total exactly when Σ min_i ≤ total ≤ Σ max_i (each cell takes any whole number in its bounds); tested against brute-force enumeration. A cell none of whose options lies on a qualifying route can hold nobody, so its maximum counts as 0. Each group is checked alone; crossed quotas are not. Quotas on a multi-select double count people |
| SC19 knock-out order | Screen out early so people who do not qualify spend little time (User Interviews field guide on screener surveys, from a search summary; not read in full) |
| SC22 criterion on every route | A criterion screens only the people whose route passes its question; a route that qualifies through a distractor or a goto around the question admits people never screened on it. Checked by searching the forward-only route graph for a path to the end that avoids passing the criterion's questions: a definition, like SC01 |
| SC23 exclusion terminates | An exclusion (Whitenton 2019: screen out market researchers and competitors) works only if the excluded answer ends the screener; a definition |
| SC24 two criteria, one answer | One answer can settle two criteria only if every option settles both; a convention of this skill (warning) |
| SC20 Prolific | Prolific's custom screening pays screened-out participants a fixed reward and requires a redirect with the screen-out code; pre-screeners are preferred where they exist (Prolific researcher help, "How to use custom screening" and "Can I screen participants within my study"; read through search snippets, not in full) |

## Writing advice used in SKILL.md

- Ask about past behaviour, not identity or intent: "Which of these have you used at work in the past month?"
  rather than "Are you a project manager?" (Whitenton 2019: open and multiple-choice questions about past
  activities).
- Put the target answer among realistic distractors and shuffle option order (Whitenton 2019).
- Screen out occupations with an open "What is your job title?" or a list where the excluded industries are
  among others (Whitenton 2019).
- Use one open articulation question for moderated studies and read the answers before inviting (Whitenton
  2019; Sova and Nielsen 2003).
- Over-recruit for no-shows and keep backups (Sova and Nielsen 2003; their specific rates were not fetched,
  so the skill states no number).

## Thresholds

| Value | Source |
|---|---|
| At least 2 plausible distractors | Convention of this skill |
| Qualifying option ≥ 2× the median distractor length (and over 20 characters) | Convention of this skill |
| Select-everything suggestion from 4 options | Convention of this skill |

## Worked example

Whitenton (2019) contrasts "Do you play online games?" (a yes/no question that reveals the topic) with
multiple-choice questions whose distractors are plausible ways of getting around (walking, ride sharing,
taxis) for a scooter study. `fixtures/nngroup_examples.md` encodes both; the linter flags the first (SC08,
SC11) and passes the second (only the SC16 suggestion). The scooter question's wording in the fixture is
ours; the article's distractor list is followed.

## Sources

1. Whitenton, K. (2019). How to use screening questions to select the right participants for user research.
   Nielsen Norman Group, 14 July 2019.
   https://www.nngroup.com/articles/screening-questions-select-research-participants/ (read 2026-11-19).
2. Sova, D. H. and Nielsen, J. (2003). *234 Tips and Tricks for Recruiting Users as Participants in Usability
   Studies*. Nielsen Norman Group. Not fetched.
3. Dillman, D. A., Smyth, J. D. and Christian, L. M. (2014). *Internet, Phone, Mail, and Mixed-Mode Surveys:
   The Tailored Design Method*, 4th ed. Wiley. Not fetched.
4. Prolific researcher help: "How to use custom screening to recruit specific participants"
   (researcher-help.prolific.com/en/articles/445155) and "Can I screen participants within my study?"
   (articles/445165). Seen through search results 2026-11-19; **not read in full**, so check the current
   wording before quoting.
5. User Interviews, UX Research Field Guide, "Screener surveys"
   (https://www.userinterviews.com/ux-research-field-guide-chapter/screener-surveys). Seen through a search
   summary; not read in full.
