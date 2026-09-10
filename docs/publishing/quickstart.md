# Add a skill: quick start

The normal path is a local skill: import an existing skill directory, or create
one here when no package exists. Then review
the content, run one local check command, and open one pull request. For the
normative rules see
[CONTRIBUTING.md](../../CONTRIBUTING.md); for the release flow see
[publishing](README.md).

```
contribute.py import <existing-skill> | new <name> when starting from scratch
  -> review SKILL.md and generated skill-card.md (lifecycle defaults to published)
  -> contribute.py check
  -> commit --signoff, open one pull request
```

## Preparation (once per checkout)

Run commands from a SkillHub checkout, not from the original skill directory.
Use Python 3.11+, Git, and Node.js/npm (CI uses Node.js 22). In PowerShell,
`python` may be used in place of `python3`.

```bash
python3 -m pip install -r requirements-dev.txt
git config --local user.name "Your Git author name"
git config --local user.email "Your verified GitHub email or GitHub noreply address"
```

Use your actual Git identity, not the example text. Check `git status` before
updating; preserve existing work. Start a contribution branch from current main:

```bash
git switch main
git pull --ff-only origin main
git switch -c feat/add-<skill-name>
```

## 1. Add the skill

If you already have a skill directory, import its complete package first:

```bash
python3 scripts/contribute.py import ../existing-skill
```

`import` copies one flat skill directory, including `SKILL.md`, `references/`,
`scripts/`, `assets/` and bundled LICENSE/NOTICE material. It does not execute
source files or modify the source directory. It reuses source metadata where it
is trustworthy and always changes the imported Skill Card lifecycle to
`published`. It is a one-time local copy, not upstream synchronization.

Import always asks for the **SkillHub maintaining team** unless `--owner` is
supplied. This records who is responsible for the catalog copy; it does not
replace the original author or an existing Skill Card owner, which remain in
the imported package as attribution. Category and runtime information are only
prompted when they cannot be reused or were not supplied explicitly.

Imports prioritize an explicit `--runtime-permissions` value, then an existing
non-empty Skill Card runtime section, then a prompt. Enter `see SKILL.md` if
that document already explains the requirements; the importer records a link.
In non-interactive mode with no existing value, the default is that same link.
Selecting a category number records it automatically; no second manual category
edit or automatic guessing is needed.

If no skill directory exists yet, create one with the interactive local scaffold:

```bash
python3 scripts/contribute.py new <skill-name>
```

The command asks for owner, description, category, and runtime requirements and
permissions, then creates the skill directory and local registration. Original
contributions default to the root Apache-2.0 license; no duplicate LICENSE file
is generated. Use `--dry-run` to preview destinations, `--with-references` to
create a linked reference scaffold, or `--help` to see flags for non-interactive
automation.

The category must match [the taxonomy](../governance/taxonomy.md) exactly; a
wrong value prints the allowed set. Bare generic names such as `profile`,
`benchmark`, `test`, `build` and `deploy` are rejected.

### Review the content

This is the only step no helper can do for the author.

- **`SKILL.md`** -- review the imported body, or complete a new scaffold. Stay at
  or below 500 lines and move detail into `references/`.
- **Bundled files** -- copy any `scripts/`, `references/` or `assets/` the skill
  needs into the skill directory. Everything it needs must be inside it.
- **`skill-card.md`** -- review the generated metadata; lifecycle already defaults
  to `published`. Runtime requirements and permissions are collected by the command
  or supplied with `--runtime-permissions`. You may refer to SKILL.md instead of
  repeating documented requirements. Non-interactive use defaults to that reference.

No separate eval file or Skill Card Validation section is required.
Known retired generator placeholders are cleaned during import; real authored
notes are retained. Other unfinished placeholders must be resolved before import.
The `published` field does not mean the contribution has been reviewed or released.

## 2. Check

```bash
python3 scripts/contribute.py check
```

This runs catalog generation, unit tests, policy validation, Agent Skills
validation, generated-file checks, remote-provenance checks (when present), and
normal/full-depth CLI discovery. It regenerates catalog files but never updates
a remote mirror or submits Git changes.

These are catalog/tool checks, not a real run of the contributed skill. PR
Quality Gate scanners and DCO run separately after submission. A local pass
does not prove source-code quality, security, hardware behavior, or merge approval.

## 3. Submit

Review the changes and stage only this contribution:

```bash
git status
git diff
git add -- skills/<skill-name> components.d/skillhub.yml README.md catalog.json skills.sh.json
git diff --cached --stat
git commit --signoff -m "feat(skills): add <skill-name>"
git push -u origin feat/add-<skill-name>
```

One pull request carries the content, its registration and the regenerated
catalog files. `--signoff` is required; the DCO check fails without it. Open
the pull request in the GitHub browser; `gh` is not required.

If you use GitHub CLI, after a successful commit and push:

```bash
gh auth login
gh pr create --base main --head feat/add-<skill-name> --fill
gh pr checks
```

Do not merge while required checks are queued or failing. Maintainer review
and the [repository settings baseline](../governance/repository-settings.md)
are still required.

## Common failures

| Message | Cause |
| --- | --- |
| `lifecycle must equal 'published'` | An old or manually authored card is still `staging`; new cards already default to `published` |
| `unresolved scaffold placeholder` / `unresolved template placeholder` | A recognized scaffold token remains; Skill Cards also reject TODO/TBD markers. SKILL.md body does not reject every ordinary TODO/TBD mention. |
| `Runtime and permissions must contain text` | Fill the runtime section, or link to the requirements already documented in SKILL.md |
| `Refusing to overwrite existing destination` | The skill is already imported; edit the existing local copy and run check, rather than importing again |
| `skills must be a non-empty list` | A component list is empty or malformed; inspect its diff and restore accidentally removed registrations, not just an empty list |
| `unable to auto-detect email address` | Configure the current repository's Git name/email, then retry commit and push; staged files remain |
| `Head sha can't be blank` / `No commits between` | Verify the commit and branch push succeeded before creating the PR |
| `Catalog files are out of date` | Run `python3 scripts/contribute.py check` |
| `category must be one of: ...` | The category is not in the taxonomy allowlist |
| `template scaffold file is not publishable` | A `.template` file was copied in unrenamed |
| `Conflicting license declarations` during import | Existing declarations and an explicit `--license` disagree; resolve the conflict without overwriting source rights. Undeclared original imports default to Apache-2.0; no license or source URL prompt is required. |
| DCO check fails | The commit is missing `--signoff` |

### Retrying an existing import

Updating SkillHub's scripts does not rewrite a previously generated Skill Card.
Prefer editing that local card: remove retired template-only Validation/origin
lines, retain real authored notes, and complete its runtime information.
If deliberately starting again, back up the imported directory outside `skills/`
and remove only its own component list item. Never clear the shared registry or
delete the original source directory.

## Remote components (opt-in)

Remote sources use GitHub `<owner>/<repository>` form; they are not restricted
to the HYGON-AI organization. This is different from `contribute.py import`,
which makes a one-time locally maintained copy. Choose the path that matches
your source:

- **Keep an existing skill synchronized:** register and mirror the existing
  package; follow [Import external skills](external-skills.md).
- **Create a new skill in a source repository:** use the authoring steps below,
  merge the source change first, then submit the SkillHub import PR.

An existing upstream package must already meet the publication contract;
do not scaffold over an existing skill.

Use the following authoring flow when a team maintains the skill in a separate GitHub
repository and wants it to evolve alongside the code it documents. Everything
above still applies; the differences are that the skill is authored elsewhere,
the change lands in two repositories, and the mirror carries provenance.

```
new_skill.py --repo ...
  -> fill TODOs in the SOURCE repository
  -> merge the source pull request FIRST
  -> sync_sources.py --check   (preview)
  -> sync_sources.py           (apply)
  -> generate_catalog.py, validate
  -> commit --signoff, open the SkillHub pull request
```

### Scaffold a new skill into the source repository

Replace the angle-bracket placeholders before running the command. `--repo`
identifies the source repository; `--owner` records the skill's author or
maintaining team and need not match the GitHub account name.

```bash
python3 scripts/new_skill.py <skill-name> \
  --source-root ../<source-checkout> \
  --repo <owner>/<repository> \
  --ref main \
  --owner "Author or maintaining team" \
  --description "What it does, when it triggers, and the nearest case that must not trigger it." \
  --license Apache-2.0 \
  --category "Operator Development" \
  --product-name "Display name" \
  --product-description "One sentence about the source project and its skills."
```

The skill files are written under `<source-checkout>/skills/<skill-name>/`,
and the registration is written to `components.d/<component>.yml` here.

### Merge the source change first

Fill in the `TODO` markers in the source repository, then merge that pull
request. Synchronization resolves the registered `ref` to a concrete commit, so
the content must already be on that ref before the mirror can be applied.

### Preview, then apply the mirror

```bash
python3 scripts/sync_sources.py --check --component <component>
```

The check fetches the source and compares its resolved commit and content with
the lock and published mirror without writing catalog files. A first import
with no mirror or lock returns nonzero for expected drift. Review the source
and registered destination before applying:

```bash
python3 scripts/sync_sources.py --component <component>
python3 scripts/generate_catalog.py
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py --check
python3 scripts/sync_sources.py --check --component <component>
```

Applying the mirror also writes a `.skillhub-lock.json` entry recording the
resolved commit and the source-tree SHA-256 digest. Open the SkillHub pull
request with the catalog maintainer as reviewer. Quality Gate, catalog validation
and DCO must pass before merge. Manually opening a PR does not require GitHub App
credentials; automated sync PRs require the App configuration described in
[repository settings](../governance/repository-settings.md). Both paths need the
quality runner and required branch checks configured for enforced quality review.

### Rules that differ from the local path

- The mirrored files under `skills/` are generated. Never edit them here: fix
  the source repository and synchronize again, or the digest check fails.
- One repository is registered by exactly one component, and every skill in
  that component shares one `ref`. Skill-level ref overrides are not supported.
- Synchronization currently runs on manual dispatch only. Admitting the first
  remote component requires an explicit decision on whether to restore
  scheduled synchronization and at what frequency.

### Additional failures

| Message | Cause |
| --- | --- |
| `does not contain SKILL.md` | The source path is wrong, the skill was deleted, or its change is not on the registered `ref` yet |
| `drift <name>: published tree does not match resolved source` | A mirrored file was hand-edited here |
| `remote component requires repo` | `local` is false but no `repo` was given |
| `source package is not publishable` | The source directory fails the same portability gates |

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the normative rules and
[supply-chain integrity](../security/supply-chain.md) for what the recorded
commit and digest do and do not prove.
