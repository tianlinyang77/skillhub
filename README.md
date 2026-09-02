# HYGON-AI Agent Skills

<div align="center">

<img src="assets/banner.gif" alt="HYGON SkillHub: agent skills for HCU, grouped by governed catalog category" width="1200"/>

</div>

Portable [Agent Skills](https://agentskills.io/specification) for [HYGON-AI](https://github.com/HYGON-AI) software, infrastructure, training, inference, operator and general engineering workflows.

The default path is simple: **a skill lives in this repository and ships in one pull request.** Mirroring from a product repository stays available as an explicit opt-in, for teams that want a skill to evolve in the same repository as the code it documents.

## Quick start

After the repository is published, browse or install skills with the standard [`skills` CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add HYGON-AI/skillhub --list
npx skills add HYGON-AI/skillhub
```

Install one skill into a specific agent without prompts:

```bash
npx skills add HYGON-AI/skillhub --skill skillhub-contributor --agent claude-code --yes
```

Pass `--agent` more than once to install into several agents, or `--agent '*'`
for every agent the CLI detects:

```bash
npx skills add HYGON-AI/skillhub --skill skillhub-contributor \
  --agent claude-code --agent codex --agent cursor --yes
```

The pinned CLI installs into any agent it recognizes -- `claude-code`, `codex`,
`cursor`, `windsurf`, `gemini-cli`, `github-copilot`, `zed`, `trae` and around
seventy others. Run `npx skills add HYGON-AI/skillhub` without `--agent` to pick
from the agents detected on your machine. Skills in this catalog are portable
and are not written for one agent.

## Add a skill

Scaffold a local skill, fill in the `TODO` markers, and open one pull request:

```bash
python3 scripts/new_skill.py my-skill-name \
  --owner "Owning team" \
  --description "What it does, when it triggers, and the nearest case that must not trigger it." \
  --license Apache-2.0 \
  --category "Developer Tools"
```

Pass `--repo HYGON-AI/<product>` instead to opt into a remote product source.
See the [quick start](docs/publishing/quickstart.md) for the full walkthrough and
[CONTRIBUTING.md](CONTRIBUTING.md) for the normative rules.

## Repository structure

The repository separates candidate content, source registration, published
skills, evaluation evidence, and generated metadata:

| Path | Purpose |
| --- | --- |
| [`skills/`](skills) | Flat catalog of published, independently installable skills |
| [`staging/`](staging) | Catalog-owned `SKILL.md.candidate` files that cannot be discovered |
| [`components.d/`](components.d) | One reviewed registration per component, local or remote |
| [`templates/`](templates) | Non-discoverable contribution scaffolds |
| [`assets/`](assets) | Repository-level README media; never skill content |
| [`docs/`](docs) | Architecture, admission, evaluation and release policy |

Every direct child of `skills/` is one catalog identity. Published skills must
not contain nested `SKILL.md` files or depend on sibling skills. See the
[normative repository layout](docs/architecture/repository-layout.md) and
[admission policy](docs/governance/admission.md).

## Skill catalog

<!-- catalog:start -->

| Product | Description | Skills |
|---|---|---|
| **SkillHub** | Author, validate, onboard, and publish portable Agent Skills across HYGON-AI projects. | [`rewrite-hygon-git-identity`](skills/rewrite-hygon-git-identity), [`skillhub-contributor`](skills/skillhub-contributor), [`torch-trace-operator-profiler`](skills/torch-trace-operator-profiler) |

<!-- catalog:end -->

## Skills by category

<!-- categories:start -->

3 skills across 3 categories.

### CI and Release

| Skill | Product | Description |
|---|---|---|
| [`rewrite-hygon-git-identity`](skills/rewrite-hygon-git-identity) | SkillHub | 审计并安全重写 HYGON 仓库 Git Commit 历史中的禁止或不规范身份字段。适用于 Author Name、Author Email、Committer Name、Committer Email 或 Commit Message 包含大小写不敏感的 sugon/rogon，或者需要把旧邮箱域按相同用户名映射为 @hygon.com 的场景。执行时使用双 mirror、离线 bundle、签名影响审批、严格 Tree 与拓扑验证、临时审核分支以及受保护的 force-with-lease 正式替换。不得用于源码内容清理、许可证头、密钥、CVE、SAST 或普通 git config 修改。 |

### Developer Tools

| Skill | Product | Description |
|---|---|---|
| [`skillhub-contributor`](skills/skillhub-contributor) | SkillHub | Create, review, and onboard portable Agent Skills into Hygon SkillHub. Use when adding a new SKILL.md to the catalog, registering a local or remote component in components.d, preparing a SkillHub contribution, or diagnosing catalog validation and synchronization failures. |

### Performance and Profiling

| Skill | Product | Description |
|---|---|---|
| [`torch-trace-operator-profiler`](skills/torch-trace-operator-profiler) | SkillHub | Analyze a torch.profiler Chrome/Perfetto JSON trace to attribute time across Python scopes, ATen operators, GPU kernels, runtime API overhead and memory copies. Use when diagnosing a slow PyTorch operator, custom extension, Triton kernel or submodule from a captured trace. |

<!-- categories:end -->

## How publication works

A local skill, which is the default:

1. The skill is written under `skills/<skill-name>/` in this repository.
2. A `components.d/<component>.yml` file registers it with `local: true`.
3. Admission review checks ownership, licensing, self-containment, routing data, and behavior evidence.
4. Validation checks naming, frontmatter, resources, evaluation data, secrets, and generated catalog drift.
5. One pull request lands the content, its registration and the regenerated catalog.

A remote component, when a product team opts in:

1. The product team merges the self-contained skill in its own HYGON-AI repository.
2. A `components.d/<component>.yml` file records the repository, ref and source path.
3. Synchronization mirrors the registered content and records the resolved commit and digest.
4. The same admission and validation gates apply before the mirror lands.

Catalog maintainers can run:

```bash
python3 scripts/validate_skills.py
python3 scripts/validate_agent_skills_spec.py
python3 scripts/generate_catalog.py --check
python3 scripts/sync_sources.py --check --component <component>
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for both paths.

Catalog-owned candidates start under `staging/`. Remote product candidates stay
in their product repositories until admission; `staging/` is not a second
product mirror. A candidate entrypoint is named `SKILL.md.candidate` until its
reviewed promotion into `skills/`, preventing deep-discovery clients from
installing staging content.

## Trust model

The catalog publishes reviewed content; it does not make arbitrary third-party skills trusted. Consumers should still review executable scripts and permissions before installation.

A **local skill** is reviewed here: its integrity rests on Git history,
protected branches, required checks, CODEOWNERS review and DCO sign-off. It has
no `.skillhub-lock.json` entry and no remote content digest.

A **remote component** additionally records its repository, ref, and source path
in [`catalog.json`](catalog.json), with synchronized commits and tree digests in
[`.skillhub-lock.json`](.skillhub-lock.json). See
[supply-chain integrity](docs/security/supply-chain.md) for what each mode does
and does not prove.

CLI discovery proves format compatibility only. Published status additionally
requires the owner, license, source and lifecycle recorded in `skill-card.md`,
plus positive, negative and behavioral cases under `evals/evals.json`.
The catalog additionally enforces exact remote commit/digest provenance and a
pinned Agent Skills reference-validation pass; neither check alone proves that
a Skill's operational behavior is correct.

## Source attribution

Product repositories remain the source of truth for mirrored skills. The catalog preserves upstream authorship and license terms, records each source repository, ref, and path in `catalog.json`, and does not treat an unchanged third-party skill as a HYGON-AI adaptation.

## License

Repository code and catalog-owned skill content are licensed under the [Apache License 2.0](LICENSE) unless stated otherwise. Mirrored skill content remains under its source license, and imported skills must carry a license compatible with public redistribution.
