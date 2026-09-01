# Supply-chain integrity

## Current foundation

- Product repositories remain the source of truth.
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

Until that profile exists, source commit and content digest checks are the
enforced integrity mechanism. Documentation must not describe unsigned content
as signed or verified.
