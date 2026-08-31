# Supply-chain integrity

## Current foundation

- Product repositories remain the source of truth.
- Component definitions record repository, ref and source path.
- Synchronization resolves a concrete commit and source-tree SHA-256 digest into `.skillhub-lock.json`.
- Catalog mirrors and metadata are produced through pull requests.
- Synchronization rejects symlinks, special files and paths outside the source package before copying.
- Catalog validation verifies each remote lock entry against its component registration and published tree digest.

## Required next integrity gate

Before the first remote product skill is published, PR CI must additionally
resolve the registered remote ref independently and prove that it still maps to
the recorded commit. Local validation already checks the source registration,
lock structure, mirrored tree digest, and pre-copy file safety.

## Signing profile

NVIDIA demonstrates the value of signed content, but HYGON should not copy a
signature filename without copying its trust model. Signing becomes a release
gate only after the repository defines:

1. the canonical byte representation and digest algorithm;
2. signer identity and offline or protected key custody;
3. certificate or public-key distribution;
4. verification in pull requests and release builds;
5. key rotation, revocation, incident response, and historical verification.

Until that profile exists, source commit and content digest checks are the
enforced integrity mechanism. Documentation must not describe unsigned content
as signed or verified.
