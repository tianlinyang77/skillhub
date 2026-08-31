# Evaluation contract

Every published skill carries `evals/evals.json`. Structural validation is a
required catalog gate; model-executed routing and behavior evaluation can be
added to CI without changing the per-skill dataset shape.

## Minimum dataset

- At least three cases with `skill_should_trigger: true`.
- At least two cases with `skill_should_trigger: false`.
- At least one positive case with a behavioral assertion.
- Unique, stable case identifiers.
- Prompts that resemble real user requests rather than keyword-only probes.

Supported behavioral assertions are:

- `expected_behavior`
- `unexpected_behavior`
- `logs_contain`
- `files_exist`

Each assertion field is a non-empty list of non-empty strings. Positive cases
from other published skills should eventually be treated as implicit negative
competition cases during full-catalog routing evaluation.

Evaluation results must distinguish routing evidence from behavior evidence.
A routing pass does not prove that a script ran correctly, and a behavior pass
with a forced skill does not prove that automatic routing selected it.

See [`templates/skill/evals/evals.json.template`](../../templates/skill/evals/evals.json.template)
for the contribution scaffold.
