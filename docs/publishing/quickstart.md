# Add a skill: quick start

The end-to-end path for adding a skill. Steps 1-5 cover a local skill, which is
the default; the last section covers the opt-in remote path for a skill owned
by a product repository. For the normative rules see
[CONTRIBUTING.md](../../CONTRIBUTING.md); for the release flow see
[publishing](README.md).

```
new_skill.py
  -> fill TODOs, set lifecycle: published
  -> generate_catalog.py
  -> validate
  -> commit --signoff, open one pull request
```

## 1. Branch

```bash
git checkout -b feat/add-<skill-name>
```

## 2. Scaffold

```bash
python3 scripts/new_skill.py <skill-name> \
  --owner "Owning team" \
  --description "What it does, when it triggers, and the nearest case that must not trigger it." \
  --license Apache-2.0 \
  --category "Performance and Profiling" \
  --with-openai
```

Omitting `--repo` creates a local skill; `--component` is not needed, since
local skills share the `skillhub` component. Add `--dry-run` first to review
destinations, and `--with-references` if the skill needs a `references/`
scaffold linked from `SKILL.md`.

The category must match [the taxonomy](../governance/taxonomy.md) exactly; a
wrong value prints the allowed set. Bare generic names such as `profile`,
`benchmark`, `test`, `build` and `deploy` are rejected.

## 3. Fill in the content

This is the only step a generator cannot do.

- **`SKILL.md`** -- replace the body, keeping the generated frontmatter. Stay at
  or below 500 lines and move detail into `references/`.
- **Bundled files** -- copy any `scripts/`, `references/` or `assets/` the skill
  needs into the skill directory. Everything it needs must be inside it.
- **`skill-card.md`** -- replace each `TODO`, then **change `lifecycle: staging`
  to `published`**. State the validation boundary honestly: what was actually
  exercised, and what a passing check does not prove.
- **`evals/evals.json`** -- at least 3 positive cases, 2 negative cases and 1
  behavioural assertion. Write negatives as near misses from the same
  vocabulary, not unrelated topics: a negative that could never trigger the
  skill tests nothing.

## 4. Generate and validate

```bash
python3 scripts/generate_catalog.py
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py --check
npx --yes skills@1.5.23 add . --list
```

Run the generator before `--check`, or the check reports drift it just created.

## 5. Submit

```bash
git add -A
git commit --signoff -m "feat(skills): add <skill-name>"
git push -u origin feat/add-<skill-name>
gh pr create --fill
```

One pull request carries the content, its registration and the regenerated
catalog files. `--signoff` is required; the DCO check fails without it.

## Common failures

| Message | Cause |
| --- | --- |
| `lifecycle must equal 'published'` | The Skill Card is still `staging` |
| `unresolved scaffold placeholder` | A `TODO` or `Replace with` marker remains |
| `Catalog files are out of date` | `generate_catalog.py` was not run before `--check` |
| `category must be one of: ...` | The category is not in the taxonomy allowlist |
| `template scaffold file is not publishable` | A `.template` file was copied in unrenamed |
| DCO check fails | The commit is missing `--signoff` |

## Remote components (opt-in)

Use this only when a product team owns the skill in its own HYGON-AI
repository and wants it to evolve alongside the code it documents. Everything
above still applies; the differences are that the skill is authored elsewhere,
the change lands in two repositories, and the mirror carries provenance.

```
new_skill.py --repo ...
  -> fill TODOs in the PRODUCT repository
  -> merge the product pull request FIRST
  -> sync_sources.py --check   (preview)
  -> sync_sources.py           (apply)
  -> generate_catalog.py, validate
  -> commit --signoff, open the SkillHub pull request
```

### Scaffold into the product repository

```bash
python3 scripts/new_skill.py <skill-name>   --source-root ../<product-checkout>   --repo HYGON-AI/<product>   --ref main   --owner "Owning team"   --description "What it does, when it triggers, and the nearest case that must not trigger it."   --license Apache-2.0   --category "Operator Development"   --product-name "Display name"   --product-description "One sentence about the product and its skills."
```

The skill files are written under `<product-checkout>/skills/<skill-name>/`,
and the registration is written to `components.d/<component>.yml` here.

### Merge the product change first

Fill in the `TODO` markers in the product repository, then merge that pull
request. Synchronization resolves the registered `ref` to a concrete commit, so
the content must already be on that ref before the mirror can be applied.

### Preview, then apply the mirror

```bash
python3 scripts/sync_sources.py --check --component <component>
```

The check reports the resolved repository, ref, commit and destination without
writing anything. Review those before applying:

```bash
python3 scripts/sync_sources.py --component <component>
python3 scripts/generate_catalog.py
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py --check
```

Applying the mirror also writes a `.skillhub-lock.json` entry recording the
resolved commit and the source-tree SHA-256 digest. Open the SkillHub pull
request with the owning team as reviewers.

### Rules that differ from the local path

- The mirrored files under `skills/` are generated. Never edit them here: fix
  the product repository and synchronize again, or the digest check fails.
- One repository is registered by exactly one component, and every skill in
  that component shares one `ref`. Skill-level ref overrides are not supported.
- Synchronization currently runs on manual dispatch only. Admitting the first
  remote component requires an explicit decision on whether to restore
  scheduled synchronization and at what frequency.

### Additional failures

| Message | Cause |
| --- | --- |
| `does not contain SKILL.md` | The product change is not merged on the registered `ref` yet |
| `drift <name>: published tree does not match resolved source` | A mirrored file was hand-edited here |
| `remote component requires repo` | `local` is false but no `repo` was given |
| `source package is not publishable` | The source directory fails the same portability gates |

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the normative rules and
[supply-chain integrity](../security/supply-chain.md) for what the recorded
commit and digest do and do not prove.
