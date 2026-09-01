# Repository guidance

- Treat `docs/architecture/repository-layout.md` as the normative directory contract.
- Treat `components.d/*.yml` as the source registry and `skills/` as the published catalog.
- Treat `staging/` as non-published catalog-owned candidate space. Candidate
  entrypoints use `SKILL.md.candidate`; reject every real `SKILL.md` below it.
  Product-owned candidates stay in their product repositories.
- Do not hand-edit a remotely mirrored skill. Change its product repository and synchronize it.
- Keep the published catalog flat: one direct child of `skills/` is one skill, with no nested `SKILL.md`.
- Use `templates/skill/` for new contributions; template suffixes prevent accidental discovery.
- Require `skill-card.md` and `evals/evals.json` before publication.
- Run `python3 scripts/validate_skills.py` after skill or registry changes.
- Run `python3 scripts/generate_catalog.py` after changes, then verify with `--check`.
- Run pinned normal and `--full-depth` CLI discovery after structural changes
  and confirm staging and templates are not discovered.
- Keep `SKILL.md` concise and move detailed material to one-level references.
- Never add credentials, private product data, or tokens to examples, remotes, or workflow logs.
