# MaxDiff question wording

Respondent-facing text for a MaxDiff exercise. These templates are this skill's own; the literature fixes
the task (pick the best and the worst item in each set), not the words (see [sources.md](sources.md)). Replace the parts in square brackets.

## Introduction (shown once, before the first set)

> In the next [S] questions you will see short lists of [features / messages / benefits]. In each list,
> choose the one that is **most important** to you and the one that is **least important** to you when
> [context, for example: choosing a project management tool for your team].
>
> You will see the same [features] several times in different combinations. That is intended: there are no
> trick questions, so answer each list on its own.

Tell respondents about the repetition. Without that sentence some conclude the survey is broken, or try to
stay consistent with earlier answers.

## The question (repeated for each set)

> Which of these is **most important** to you, and which is **least important**, when [context]?

Layout: one row per item, in the order given by the design's `position` column, with a "Most important"
choice on one side and a "Least important" choice on the other. Exactly one of each per set, and not the
same item for both. Show progress ("Question 3 of 12").

## Choosing the pair of labels

Use one dimension for the whole exercise, and the same question and the same two labels in every set.
Changing the wording between sets makes the answers incomparable.

| What you are measuring | Best label | Worst label |
|---|---|---|
| Feature or need priority | Most important | Least important |
| Message, claim or name appeal | Most appealing | Least appealing |
| Purchase drivers | Most likely to make me buy | Least likely to make me buy |
| Problems and pain points | Biggest problem | Smallest problem |
| Concerns or barriers | Most concerning | Least concerning |
| Preference between options | Like most | Like least |

Rules:

- The two labels are opposite ends of one scale. "Most important" with "least appealing" asks two
  different questions.
- Name the context in the question ("when choosing ...", "for your team"). Importance without a context
  gets answered in general terms.
- Do not use "best" and "worst" as respondent labels when the items are good things: nobody wants to mark a
  benefit "worst". "Least important" is neutral.
- Negative lists (problems, risks): check that "most" still points at the item you would act on first.
- Keep the labels identical across languages in meaning; translate the pair together, not word by word.

## Item text

- Short and parallel: a noun phrase or one clause each, of similar length.
- No brand names or prices unless every item has one.
- No explanations in brackets for some items only. If items need explaining, give every item a
  one-line description, or show a glossary before the exercise.

## Optional anchor (to learn which items matter at all)

An anchor changes the analysis: the scores are then estimated against a threshold, not only against each
other. Decide before fielding and tell whoever analyses the data. The sibling skill `maxdiff-analysis` does
not use anchor answers, so name the tool that will (for example Sawtooth Lighthouse Studio's anchored
MaxDiff) before the anchor goes into the questionnaire.

MaxDiff scores are relative: the top item of a weak list still comes out on top. Two ways to add an
absolute reference, both described in the Sawtooth technical paper ([S2] in sources.md):

**After each set (indirect, dual response).** Use only with 4 or fewer items per set.

> Thinking about the [4] items above:
>
> - All of them are important to me
> - Some are important to me, some are not
> - None of them is important to me

**Once, after the exercise (direct).** One list with every item:

> Which of these are **must-haves** for you? Select all that apply.

The direct version is shorter for the respondent and easier to programme. The two versions do not give
the same threshold, so use one and keep it for later waves.

## Before and after the exercise

- Before: screen for people who can judge the items (users of the category, decision makers).
- After: one open question helps explain the top item, for example "You chose [item] as most important
  most often. Why does it matter to you?" (possible only where the survey tool can pipe in the answer;
  otherwise ask "Which of these matters most to you, and why?").
- Do not put a rating grid of the same items right before the MaxDiff: respondents anchor on their ratings.

## Worked example

Study: which of 12 features to build next for a time-tracking product; 4 per set, 9 sets.

> **Introduction.** In the next 9 questions you will see short lists of features a time-tracking tool
> could offer. In each list, choose the feature that is most important to you and the one that is least
> important to you when deciding which tool your team should use. You will see the same features several
> times in different combinations. That is intended.
>
> **Question 1 of 9.** Which of these is most important to you, and which is least important, when
> deciding which time-tracking tool your team should use?
>
> | Most important | | Least important |
> |---|---|---|
> | ( ) | Automatic timers | ( ) |
> | ( ) | Invoices from tracked time | ( ) |
> | ( ) | Calendar integration | ( ) |
> | ( ) | Offline mode | ( ) |
