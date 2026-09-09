# Repository settings baseline

Workflow files define checks, but they do not make those checks mandatory.
Before SkillHub is treated as a production catalog, an administrator must
apply and verify the following GitHub settings on the publishing repository.

## Main branch ruleset

Protect `main` with a branch ruleset or branch protection rule that:

- requires pull requests and at least one approval;
- requires CODEOWNERS review for owned paths and dismisses stale approvals;
- requires `validate (3.11)`, `validate (3.12)`, and `dco` to pass on the
  latest commit;
- requires the pinned Quality Gate's `All required checks` result on that
  same PR revision (select its actual emitted check name after the first run);
- requires conversation resolution and a current branch before merge;
- blocks force pushes and branch deletion; and
- applies to administrators and automation unless a narrowly scoped, audited
  bypass is documented.

Do not select a required status-check name until that check has run once on the
publishing repository. Reverify the selected names after renaming a workflow or
job.

Check completion matters: a queued or running job is not a pass, and successful
local `contribute.py check` results do not satisfy GitHub required checks.

## Repository security and contribution settings

- Enable web-based commit sign-off so browser-created commits follow the DCO
  policy. Automated synchronization commits already use `git commit --signoff`.
- Enable Private Vulnerability Reporting before directing external reporters
  to **Security → Report a vulnerability**.
- Keep secret scanning and push protection enabled.
- Enable dependency alerts and security updates, then review automation changes
  through the same validation path as other contributions.
- Disable unused publishing surfaces and grant workflow tokens only the
  permissions declared by each workflow.
- Store `SKILLHUB_SYNC_TOKEN` only when cross-repository access requires it;
  scope it to read source repositories and never expose it to fork workflows.

## Release verification

### External import automation setup

The quality runner and required checks below are needed for ordinary human-authored
PRs too. A GitHub App is needed only for synchronization automation to push a branch
and open a PR; contributors using ordinary Git do not need App credentials.

1. Install a GitHub App on this catalog only, with Contents and Pull requests
   read/write permissions. Set repository variable `SKILLHUB_APP_ID` and secret
   `SKILLHUB_APP_PRIVATE_KEY`. The sync workflow creates a short-lived token;
   it deliberately does not fall back to `GITHUB_TOKEN` for pushing/opening PRs,
   because those events would not normally trigger PR checks.
2. Keep optional `SKILLHUB_SYNC_TOKEN` limited to reading private sources.
   Public sources do not need it. PR quality jobs must not receive these secrets.
3. Provide a disposable, isolated Linux x64 runner labeled `quality`, with
   Python/PyYAML, Docker and the scanner images required by the pinned
   [Quality Gate](https://github.com/HYGON-AI/quality-gate/tree/2ba24f43aa792b744cf6d9c5b8839fb8856e278c).
   The engine refuses to pull missing images during PR scanning. Never share
   this runner with production jobs or leave credentials on it between runs.
4. Run a representative import PR and inspect all three quality groups. Verify
   imported copyright and license notices are preserved; findings require review
   or a reviewed gate policy change, not removal of upstream attribution.
5. Make the quality result, catalog checks and DCO required in branch protection,
   and verify a failed check blocks merge and an App-authored PR triggers checks.

These are deployment prerequisites, not settings enabled by committing YAML.

### Acceptance evidence

Before announcing the catalog endpoint, an administrator records evidence that:

1. direct pushes to `main` cannot bypass review;
2. a pull request cannot merge while either Python validation job, `dco`, or the
   Quality Gate summary is missing, queued, running or failing;
3. CODEOWNERS review is requested for workflows, validators, templates, source
   registrations, and published skills;
4. a private vulnerability report can be submitted without opening a public
   issue; and
5. the synchronization workflow can open a signed-off pull request but cannot
   merge it by itself. Synchronization currently runs on manual dispatch only;
   when the first remote component is admitted, an administrator must record
   explicitly whether to restore scheduled synchronization and at what
   frequency.

Repository settings are external state. Review them periodically and after a
repository transfer, fork promotion, workflow rename, or default-branch change.
