# Coding with a language model: what the evidence says

Context for [`../SKILL.md`](../SKILL.md) when the coder is an LLM. Only the arXiv abstracts of the two
papers below were read (2026-11-12); numbers are quoted from the abstracts and nothing else is claimed.

## What two studies found

**Dunivin (2024), arXiv:2401.15170.** A codebook of 9 codes from a socio-historical study was applied by
GPT-4 and GPT-3.5 to dense, paragraph-length passages and compared with human coding, per code, with
Cohen's kappa.

- GPT-4 reached kappa of 0.79 or more on 3 of the 9 codes and 0.6 or more on 8 of the 9.
- GPT-3.5 performed much worse: mean kappa 0.34, maximum 0.55.
- Coding fidelity "improves considerably" when the model is asked to give a rationale for each decision.
- The paper ends with advice on adapting a codebook for a model.

**Xiao, Yuan, Liao, Abdelghani and Oudeyer (2023), arXiv:2304.10548 (IUI '23 Companion).** GPT-3 was
given expert-written codebooks through prompting, with no task-specific training, on one deductive coding
task (classifying children's curiosity-driven questions). Agreement with expert coding was "fair to
substantial". The abstract gives no kappa values.

## What follows for this skill

- **Results are per code and per model.** In Dunivin's study one code out of nine stayed under 0.6 with
  the stronger model, and the weaker model failed overall. A single overall figure, or a result from a
  different model, tells you little about your codebook. Hence: report agreement per code, and name the
  model.
- **The comparison that matters is with a person.** Both studies measure the model against human coding.
  A second run of the same model is a consistency check, not that comparison.
- **Ask for the reason.** Have the model write a one-line rationale per row citing the words that
  triggered the code (Dunivin's finding), in a `rationale` column of the batch file next to `id,codes`;
  `merge` ignores it. Keep the rationale column out of the file given to a second coder (`sample` writes
  only id and answer).
- **The codebook does the work.** Both studies used expert-written codebooks. Vague definitions cost
  agreement with any coder; `include` and `exclude` with borderline cases are where a model gains most.
- **Limits of this evidence.** Two studies, two tasks, models from 2023; neither is about short survey
  answers. Treat them as a reason to test, not as proof that a model can code your data.

## Reporting an LLM coder

State, next to the agreement table: the model name and version, the date, the prompt (or where it is
kept), whether a rationale was requested, the codebook version, how many rows a person coded, and
agreement per code against that person with its interval. `agreement --gold human.csv llm.csv
--coder-info "name,human" --coder-info "run,llm,MODEL" --codebook-version v2` prints the header and the
precision, recall and F1 of the model against the person.
