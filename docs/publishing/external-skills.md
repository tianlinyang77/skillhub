# Skills from another repository

SkillHub accepts skills from GitHub organizations and personal repositories.
The default is a one-time local import: it preserves the source package but
makes the reviewed copy a SkillHub-maintained skill. Ongoing synchronization is
an explicit advanced option.

## Default: one-time local import

Clone or otherwise obtain the source directory, then run this from a SkillHub
contribution branch:

```bash
python3 scripts/contribute.py import ../upstream-skill
```

The source must be one flat directory containing `SKILL.md`. The importer copies
its `SKILL.md`, references, scripts, assets and bundled LICENSE/NOTICE material;
it does not execute or modify source files. It rejects nested skills, symlinks,
caches, oversized packages and invalid required portable fields. Source-only
frontmatter such as `produces` is retained in an **Imported source metadata**
section of the copied `SKILL.md`, rather than left as an invalid top-level Agent
Skills field. An existing Skill Card is retained as context but adapted to local
identity with lifecycle `published`; upstream attribution remains in the card.
Existing runtime/permission text is reused unless explicitly overridden with
`--runtime-permissions`; otherwise the command prompts, or records a SKILL.md
reference in non-interactive mode. Only known retired generator Validation/origin
placeholders are removed from the copied card. Actual notes are preserved.
Other unfinished placeholders fail before any registration is written.

If the package does not include license text, no duplicate file is required.
Local directory imports are intended for your own original contributions. When
no license is declared, they default to the repository Apache-2.0 license without
asking for license or source URLs; you must have the right to publish under these
terms. Existing license declarations and source metadata are preserved, not
overwritten. `--upstream <url>` is optional. This default is not permission to
relicense third-party content. Use `--license-file <path>`
or `--notice-file <path>` when redistribution requires additional license or
notice material. Existing bundled files are always preserved.
Review redistribution rights and the generated Skill Card, then run:

```bash
python3 scripts/contribute.py check
```

Then review the diff and submit one ordinary signed-off pull request. This is a
local copy, so later upstream changes are not pulled automatically.
An existing destination is never overwritten; edit that local copy and run
`contribute.py check` to update it. No Validation form or manual lifecycle
change is required, and the metadata value does not bypass PR checks or review.

## Opt in to remote synchronization

Use this only when the product team wants the skill to remain maintained in its
own repository and evolve alongside its code. The rest of this page describes
that remote mirror path.

### First synchronized import

1. Confirm the license permits redistribution, preserve upstream attribution
   and required LICENSE/NOTICE files, and identify a catalog maintainer in the
   PR. The upstream package must already include a matching Skill Card.
   If it lacks them, ask upstream to add them or maintain a licensed local copy
   with original attribution. Do not patch a remote mirror by hand.
2. Create a contribution branch and add `components.d/tool-skills.yml`:

   ```yaml
   name: Tool Skills
   repo: someone/tool-skills
   ref: main
   description: Maintained application log analysis skills.
   skills:
     - path: skills/log-analyzer
       catalog_dir: log-analyzer
       category: Developer Tools
   ```

   Replace the example repository and path with the actual source. `ref` is an
   existing branch or release tag. `catalog_dir` must be globally unique and
   match the Skill's frontmatter `name`. Skill Card source
   metadata must match the registered repository and source path. One component
   registers one repository and one ref.
3. Import and validate from the SkillHub root:

   ```bash
   python scripts/sync_sources.py --component tool-skills
   python scripts/generate_catalog.py
   python -m unittest discover -s tests
   python scripts/validate_skills.py
   python scripts/validate_agent_skills_spec.py
   python scripts/generate_catalog.py --check
   python scripts/sync_sources.py --check --component tool-skills
   ```

   Apply mode creates the mirror and lock entry. `--check` reports drift and
   exits nonzero for a first import without a mirror/lock; that is expected.
   Follow CONTRIBUTING's normal and full-depth CLI discovery checks as well.
4. Commit with sign-off and open a SkillHub PR containing the registration,
   mirror, `.skillhub-lock.json` and generated catalog files. Quality Gate,
   catalog validation and DCO must pass, followed by maintainer review.
   Do not merge a source-only registration before its mirror and lock.

### Subsequent updates

After the first import is merged, run **Sync Opt-in Product Skills** manually
from Actions. It fetches registered sources, validates packages, updates mirrors
and locks, then uses the configured GitHub App to create/update a PR. All PR
checks run again. No automatic merge is performed. If the source ref moves
during review, re-sync; the provenance check compares against the current ref.

For automated PRs, administrators must first configure the App and isolated
quality runner described in [repository settings](../governance/repository-settings.md).
Until then, maintainers can prepare the import locally and open a PR, but must
wait for the quality runner and required checks before publishing it.

## Failures

- Missing ref, deleted Skill, invalid package or failed quality check: fix the
  source/registration and retry; do not merge a partial import.
- Sync operates in an expendable checkout and may have updated earlier packages
  before a later source fails. The workflow stops before pushing a PR. For a
  local multi-component failure, inspect/discard only generated changes on your
  contribution branch and rerun; do not assume repository-wide rollback.
- Private sources require narrowly scoped read credentials and explicit public
  redistribution approval; access to a repository alone is not permission.
- A name collision requires an upstream rename or a separately maintained local
  adaptation. Changing only `catalog_dir` does not rename the remote package.
