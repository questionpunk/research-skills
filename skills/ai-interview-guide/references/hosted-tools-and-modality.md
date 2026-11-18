# Where the brief goes in a hosted tool, and choosing the modality

## Placing the brief in a hosted AI-interview tool

Tools split the brief differently. Some take instructions for the whole study, some per question, some
both; some keep research goals apart from the question guide. Use this table to find the nearest field,
and read the tool's own documentation before pasting.

| Part of the brief | Kind of field to look for | If the tool has none |
|---|---|---|
| Goal (section 1), context (section 3) | A goal, background or "context for the AI" field that participants do not see | Put it at the top of the study-level instructions |
| Must-ask questions (section 4) | The question list or discussion guide, one entry per question, in order | Not usable as a guided interview; use the custom-LLM prompt |
| Probes, "done when" (section 4) | A per-question instruction or follow-up guidance field | Put the two or three most important ones in the study-level instructions, naming the question |
| Probe depth (section 4) | A per-question follow-up setting (off, some, more; or a maximum number) | State the limit in the instruction for that question |
| Skip / branch (section 4) | Conditional logic or a per-question instruction | Write it as an instruction addressed to the moderator |
| Avoid (section 6) | A guardrail, boundaries or "topics to avoid" field | Study-level instructions |
| Consent screen (section 7) | A welcome, intro or consent screen before the session; or a screener | A separate consent step before the interview link |
| Opener (section 7), closing (section 8) | Intro and end messages | First and last entry in the question list, with depth "none" |
| Length (section 9) | A time or question limit | State it in the study-level instructions |

Rules for what to paste:

- **Only study-specific instructions.** Hosted moderators are built to ask one question at a time, stay
  neutral and follow up. Do not paste the general behaviour rules from the custom-LLM prompt. Vendor
  documentation advises a few specific instructions over long general guidance.
- **Address the moderator, not the participant.** "If the participant mentions another service, ask how
  they came to choose it", not "If you use another service, tell us how you chose it".
- **Do not repeat a question inside an instruction.** It may be asked twice.
- **Make the depth setting agree with the brief.** A question with detailed probing instructions and
  follow-ups switched off will not be probed. Vendors define their levels differently (in one vendor's
  documentation the middle level means at least two follow-ups), so compare numbers, not level names.
- **Instructions may not carry across questions.** Where they are per question, repeat a rule that
  matters for several questions under each of them.

## Text or voice

| | Text | Voice |
|---|---|---|
| Answers | Shorter, more edited | Longer and less edited in the studies cited in `sources.md` |
| Participant effort | Anywhere, at their own pace | Needs a quiet place, a microphone and a stable connection |
| Failure modes | Terse replies; pasted or LLM-written answers | Speech-recognition errors, latency, interruptions |
| Sensitive topics | No finding either way in the sources; check in the pilot | Same |
| Data | Transcript only | Audio is more identifying; the consent text must say whether it is stored |

Default to text. Recommend voice when the story matters more than precision and participants can speak
freely; recommend text when participants answer at work or in public. These recommendations are practical
judgement, not findings.

## Voice sub-mode

| | Real-time conversation | Turn-based (the participant records each answer, then sends it) |
|---|---|---|
| Feels like | A call | Voice messages |
| Shows | Hesitation and thinking aloud | A considered answer |
| Needs | A quiet place for the whole session; low latency | Only a moment of quiet per answer |
| Risks | Interruptions, talking over each other, latency | Less spontaneous; participants may re-record |

Choose turn-based when participants may not have a quiet place or need thinking time, and real-time when
how they reason matters as much as what they conclude. This trade-off is described in one vendor's
documentation (Marvin, see `sources.md`); no study in the sources compares the two.
