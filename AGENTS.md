# Repository guidance

- Treat `docs/architecture/repository-layout.md` as the normative directory contract.
- Use `local: true` as the default contribution model. Maintain those skills
  directly under `skills/` and let `scripts/new_skill.py` update the shared
  SkillHub component registration.
- Use a remote component only when a product team explicitly commits to
  maintaining the source skill in its own HYGON-AI repository. Never hand-edit
  the synchronized mirror for such an opt-in component.
- Keep the published catalog flat: one direct child of `skills/` is one skill,
  with no nested `SKILL.md`.
- Keep candidates under `staging/` undiscoverable with `SKILL.md.candidate`.
- Require `skill-card.md`, `evals/evals.json`, and a bundled `LICENSE` before publication.
- Run catalog generation, validation, Agent Skills reference validation, and
  pinned normal/full-depth CLI discovery after structural changes.
- Keep `SKILL.md` concise and move detailed material to one-level references.
- Never add credentials, private product data, or tokens to examples, remotes, or workflow logs.
