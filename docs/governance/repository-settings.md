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
- requires conversation resolution and a current branch before merge;
- blocks force pushes and branch deletion; and
- applies to administrators and automation unless a narrowly scoped, audited
  bypass is documented.

Do not select a required status-check name until that check has run once on the
publishing repository. Reverify the selected names after renaming a workflow or
job.

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

Before announcing the catalog endpoint, an administrator records evidence that:

1. direct pushes to `main` cannot bypass review;
2. a pull request cannot merge while either Python validation job or `dco` is
   failing;
3. CODEOWNERS review is requested for workflows, validators, templates, source
   registrations, and published skills;
4. a private vulnerability report can be submitted without opening a public
   issue; and
5. the scheduled synchronization workflow can open a signed-off pull request
   but cannot merge it by itself.

Repository settings are external state. Review them periodically and after a
repository transfer, fork promotion, workflow rename, or default-branch change.
