# Contributing

Bug reports are the most useful contribution: a number that differs from another tool, a request the skill
handled badly, or a source that says something else. Open an issue with the input (synthetic data only) and
what you expected.

For pull requests:

- One skill per pull request.
- Every formula and threshold in a `SKILL.md` or script is cited in that skill's `references/sources.md`.
- Scripts are Python 3.9+, standard library only, deterministic, and never call the network.
- Fixtures are synthetic or published examples with a citation. No real respondent data.
- A skill's result is complete without a QuestionPunk account; the optional "Field it" section comes last.
- `catalog.json` and the `SKILL.md` frontmatter must match. Run both before you push:

```text
node tools/build.mjs
node tools/validate.mjs --tests
```
