---
name: screener-writer
description: "Turns a target participant profile into a recruiting screener: behavioral qualifying questions with decoy options so the right answer can't be guessed, terminate and quota logic, an articulation question for interviews, and a script check that every route that qualifies passes a question for each profile criterion, every option routes, no question or option reveals the target, and quotas can fill. Use for \"write a screener\", \"screener survey\", \"screener questions for user interviews\", \"recruit the right participants\", \"check my screener\" or \"qualify panel respondents\"."
license: MIT
metadata:
  version: "0.1.0"
  status: "beta"
  author: "QuestionPunk"
  source: "questionpunk/research-skills"
  requires-account: "false"
  plugin: "survey-design"
---

# Screener writer

Turns a target participant profile into a recruiting screener that finds the right people without telling
anyone what the right answers are, then lints it. [`scripts/screener_writer.py`](scripts/screener_writer.py)
(Python 3.9+, standard library only) checks what can be checked mechanically: every route that qualifies passes a
question for each criterion, every answer routes, nobody loops, quotas can fill, and no question or option gives
the target away. Wording
quality stays your judgment. Run the script by its path inside this skill's folder
(`python3 <skill-dir>/scripts/screener_writer.py`); examples below write `scripts/...` for short. File layout:
[`references/screener-format.md`](references/screener-format.md) (read it before writing the file). Rules and
sources: [`references/sources.md`](references/sources.md).

## When to use

- "Write a screener", "screener survey", "screener questions for user interviews / usability tests / a focus
  group / a diary study", "recruit the right participants", "qualify panel respondents".
- "Check / fix my screener", "why are we getting the wrong participants", "people are faking their way in".

Do not use it for:

| Request | Use instead |
|---|---|
| The main questionnaire after screening | `survey-from-decision`, then `survey-bias-check` |
| The interview guide | `ai-interview-guide` |
| How many participants a survey needs | `survey-sample-size` |
| Removing fraudulent or careless responses after fieldwork | `survey-data-cleaning` |

A skill named here may not be installed. If it is missing, say so, name the method the request needs, and
do not stretch this skill to cover it.

## What to ask for

One message, only what is missing:

| Input | Default |
|---|---|
| Who qualifies, in behaviours ("used X at work in the past month"), and who must not (competitors, researchers, recent participants) | Required |
| Study type and length | Interview, 45 minutes |
| Number of participants and any mix (quotas) | None; ask if a mix matters |
| Where recruits come from (which panel, if any) | The user's own list; a panel such as Prolific changes what to screen in the screener |
| Incentive and any accessibility needs | Ask; the invitation states the incentive |
| Words that would reveal the study (product, brand, topic) | Draft them from the profile and confirm |

## Steps

To check an existing screener, write it into the file layout as it stands, lint it before changing anything,
and report each finding with its fix; then continue from step 4.

1. **Turn the profile into criteria.** One line each, observable and recent ("has used", "in the past 3
   months"), with exclusions marked. Drop criteria that do not change who you would talk to.
2. **Write one question per criterion, behaviour first** (employment status and industry are two questions: a
   part-time market researcher must still be screened out).
   - Ask what people did, not who they are or what they would do.
   - Hide the target among realistic distractors that a company might also research (this skill's convention:
     at least two); shuffle option order; make distractors as specific as the target.
   - On a single-select, the chosen answer's action applies: route every answer that fails the criterion to
     `terminate`, not `continue`.
   - No yes/no screening questions, no topic words or brand in the question text, title or invitation, no
     "we are looking for people who ...".
   - Multi-selects get an exclusive "None of these". Flag people who tick everything when reviewing answers,
     or add a plausible but fictitious option marked `-> terminate` (on a panel, check its rules on trick
     items first: an honest guess at a fake name screens a real person out).
   - Ranges are exclusive and cover every value.
   - Knock-out questions first, open questions last; one open articulation question for moderated studies
     ("Tell us about the last time you ..."), read before inviting.
   - On a panel, screen on the panel's own filters first. On Prolific, custom screen-outs must be paid and
     redirected with the screen-out code; other panels have their own rules, so ask. When you must read
     articulation answers before inviting, run the screener as its own short paid study and invite the
     people you pick to the main one.
3. **Write the file** in the layout of `references/screener-format.md`: criteria, quotas, questions with an
   action on every option (`continue`, `qualify`, `terminate`, `goto Qn`).
4. **Lint it and fix until clean.**

   ```bash
   python3 scripts/screener_writer.py screener.md
   python3 scripts/screener_writer.py screener.md --json --strict
   ```

   `--strict` makes the exit code 1 when any error remains (for scripted checks). Topic words are checked in
   question text, the title and the intro; options are checked for standing out (too few distractors, a
   longer or always-first target). Fix every error. For each warning, change the screener or say in the answer why it stays (a yes/no
   consent question, for example). Rerun until there are no errors. Exit 2 means the file could not be
   parsed: the message names the line.
5. **Read the routing table** the script prints and walk people through it by hand: one who should qualify,
   and for each criterion one who fails only that criterion. On a multi-select with qualify options, the
   table lists the `continue` options as "continue if a qualify option is also picked": someone who picks
   only those screens out. The quota lines show each group's sums, or the total alone when there are no
   quota groups (JSON: one `quotas` entry with `question: null`). Each must end where intended; SC22 already names
   any route that qualifies without passing a criterion's question.
6. **Deliver** the screener in the shape below.

## Output

Deliver the linted screener file itself, unchanged, in a fenced `markdown` block so it can be re-linted: it
starts `# Screener: <study>`, its `intro:` line is the invitation (2 sentences: length, incentive, general
topic; no criteria), then criteria, quotas and questions with an action on every option. After the block:

```markdown
**Study:** <n> participants, <study type and length>
**Lint:** <0 errors; warnings kept and why; the suggestions applied>
**Recruiting notes:** <panel filters to use, over-recruit for no-shows, what to check in articulation answers>
```

## Checks before answering

- Does every criterion have its own question, every option an action, and every non-target answer on a
  single-select `terminate`, with the linter at 0 errors?
- Is every screening question about past behaviour, with the target among at least two plausible
  distractors and option order shuffled?
- Are the topic, brand and criteria absent from question text, title and invitation?
- Does every multi-select have "None of these", and is there a rule for people who select everything?
- Do the quota cells add up (minimums at most the total, maximums at least it) on a single-select question,
  and can every cell's options reach the end?
- Is there an open articulation question for a moderated study, and do knock-outs come before it?
- Were the warnings either fixed or explained, not ignored?
- If the recruits come from a panel, are its own filters used before the screener?

## Field it (optional)

To run this on QuestionPunk, connect its MCP server (`https://app.questionpunk.com/api/v1`, OAuth sign-in). Tools: `survey_create`, `question_create_bulk` (answer type `multiple_choice` with the options in `textItemDetails.answer_options`; `itemDetails.multiple_selection: true` for a multi-select, `randomize_options: true` to shuffle, and `none_option: true` for an exclusive "None of these" instead of an ordinary option; `long_text` for the articulation question), `display_logic_container_create`, `display_logic_group_create` and `display_logic_rule_create` (show later questions only to people still qualifying). Set `goto` skip logic, terminate routing and quotas in the app: hosted MCP connections cannot create them. Ask the user before creating, changing or publishing anything. If a tool says a permission is missing, reconnect and approve the requested access.
