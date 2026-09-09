# Supply-chain integrity

The two contribution modes carry different integrity evidence. Never describe
one with the other's guarantees.

## Local skills (default)

Original contributions default to the repository Apache-2.0 license. A separate
LICENSE in every skill is not required. Every Skill Card still declares a license;
this declaration is checked, while redistribution rights and the sufficiency of
license/NOTICE material require review. A local import retains the source license
and attribution, and does not acquire a new license by being copied here.

A local skill's only source of truth is this repository:

- the component sets `local: true`;
- an omitted `repo` normalizes to `HYGON-AI/skillhub`, and any other value is rejected;
- the source path must equal `skills/<catalog_dir>` exactly;
- content, registration, runtime requirements, licensing and generated catalog files
  are reviewed in a single pull request.

A local skill has **no `.skillhub-lock.json` entry and no remote content
digest**. Its safeguards are Git history, review and DCO sign-off, with protected
branches, required checks and CODEOWNERS review effective only when configured
on GitHub. Committing workflow and CODEOWNERS files does not enable enforcement;
verify the [repository settings](../governance/repository-settings.md) separately.
Do not present local review as remote provenance. The remote commit and digest
mechanism below verifies byte consistency, not authorship or safety.

## Remote components (explicit opt-in)

When a maintained skill is imported from any GitHub repository, this
additional evidence applies:

- Component definitions record repository, ref and source path.
- Synchronization resolves a concrete commit and source-tree SHA-256 digest into `.skillhub-lock.json`.
- Catalog mirrors and metadata are produced through pull requests.
- Synchronization rejects symlinks, special files and paths outside the source package before copying.
- Catalog validation verifies each remote lock entry against its component registration and published tree digest.
- Pull-request validation resolves every remote ref independently and requires
  the resolved commit, source digest, lock entry and published tree to agree.
- GitHub Actions dependencies and compatibility CLIs are pinned to reviewed
  commits or versions rather than floating major tags.

## Enforced remote integrity gate

`scripts/sync_sources.py --check` clones each registered remote ref without
modifying the catalog and fails unless its resolved commit and tree digest
match `.skillhub-lock.json` and the published directory. Apply mode performs
the same pre-copy path, symlink, special-file and package-boundary checks before
updating a mirror.

## Signing profile

Signing must not become a release claim until the repository has a complete
and verifiable trust model. It becomes a release gate only after the repository
defines:

1. the canonical byte representation and digest algorithm;
2. signer identity and offline or protected key custody;
3. certificate or public-key distribution;
4. verification in pull requests and release builds;
5. key rotation, revocation, incident response, and historical verification.

Until that profile exists, remote source commit and content digest checks prove
byte consistency, not author identity or content safety. Documentation must not describe unsigned content
as signed or verified.

## External import trust boundary

Treat fetched files as untrusted data. Never execute imported helpers or install
their dependencies during synchronization. Preserve original attribution and
redistribution rights. Run the pinned Quality Gate on the SkillHub PR, together
with catalog validation and DCO, before reviewed merge. The quality runner must
be isolated and disposable, with no production credentials or workloads; prepare
the scanner images before accepting PR jobs. PR jobs receive no sync secrets.

Use a catalog-scoped GitHub App token to push synchronization branches and open
PRs so `pull_request` checks actually start. A missing App configuration fails
the sync workflow rather than creating an unchecked bot PR. Configure required
checks in branch protection; workflow files alone do not enforce merge policy.
