#!/usr/bin/env python3
"""Create a product-owned Skill scaffold and its catalog registration."""

# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

import argparse
import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

try:
    from scripts.skillhub import (
        ALLOWED_CATEGORIES,
        FORBIDDEN_GENERIC_CATALOG_DIRS,
        MAX_DESCRIPTION_LENGTH,
        OFFICIAL_GITHUB_OWNER,
        REF_RE,
        REPO_RE,
        SKILL_NAME_RE,
    )
except ModuleNotFoundError:  # Direct execution adds scripts/, not the repository root.
    from skillhub import (
        ALLOWED_CATEGORIES,
        FORBIDDEN_GENERIC_CATALOG_DIRS,
        MAX_DESCRIPTION_LENGTH,
        OFFICIAL_GITHUB_OWNER,
        REF_RE,
        REPO_RE,
        SKILL_NAME_RE,
    )


CATALOG_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = CATALOG_ROOT / "templates" / "skill"


class ScaffoldError(ValueError):
    """Raised when creating a scaffold would be unsafe or ambiguous."""


@dataclass(frozen=True)
class ScaffoldConfig:
    name: str
    repo: str
    ref: str
    owner: str
    description: str
    license_id: str
    category: str
    component: str
    product_name: str
    product_description: str
    source_root: Path
    catalog_root: Path
    license_file: Path
    notice_file: Path | None = None
    with_openai: bool = False
    with_references: bool = False
    dry_run: bool = False

    @property
    def source_path(self):
        return f"skills/{self.name}"

    @property
    def destination(self):
        return self.source_root / "skills" / self.name


def display_name(slug):
    return " ".join(
        part.capitalize() for part in slug.replace("_", "-").split("-") if part
    )


def normalized_component(repo):
    slug = repo.split("/", 1)[-1].lower().replace("_", "-").replace(".", "-")
    return "-".join(part for part in slug.split("-") if part)


def require_text(value, label):
    normalized = value.strip()
    if not normalized:
        raise ScaffoldError(f"{label} must be a non-empty string")
    return normalized


def resolve_optional_file(value, source_root, candidates):
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = source_root / path
        path = path.resolve()
        if not path.is_file() or path.stat().st_size == 0:
            raise ScaffoldError(f"{path} is not a non-empty file")
        return path
    for candidate in candidates:
        path = source_root / candidate
        if path.is_file() and path.stat().st_size > 0:
            return path.resolve()
    return None


def validate_config(config):
    for label, value in (
        ("owner", config.owner),
        ("description", config.description),
        ("license", config.license_id),
        ("product name", config.product_name),
        ("product description", config.product_description),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ScaffoldError(f"{label} must be a non-empty string")
    if len(config.name) > 64 or not SKILL_NAME_RE.fullmatch(config.name):
        raise ScaffoldError(
            "name must be lowercase hyphen-case and at most 64 characters"
        )
    if config.name in FORBIDDEN_GENERIC_CATALOG_DIRS:
        raise ScaffoldError(
            f"name '{config.name}' is too generic; use a globally descriptive name"
        )
    if len(config.component) > 64 or not SKILL_NAME_RE.fullmatch(config.component):
        raise ScaffoldError(
            "component must be lowercase hyphen-case and at most 64 characters"
        )
    if (
        not REPO_RE.fullmatch(config.repo)
        or config.repo.split("/", 1)[0] != OFFICIAL_GITHUB_OWNER
    ):
        raise ScaffoldError(
            f"repo must be owned by {OFFICIAL_GITHUB_OWNER} and use owner/name form"
        )
    if not REF_RE.fullmatch(config.ref) or config.ref.startswith("-"):
        raise ScaffoldError("ref must be a safe branch or release-tag name")
    if config.category not in ALLOWED_CATEGORIES:
        raise ScaffoldError(
            "category must be one of: {}".format(", ".join(sorted(ALLOWED_CATEGORIES)))
        )
    if len(config.description) > MAX_DESCRIPTION_LENGTH:
        raise ScaffoldError(f"description exceeds {MAX_DESCRIPTION_LENGTH} characters")
    if "<" in config.description or ">" in config.description:
        raise ScaffoldError("description cannot contain angle brackets")
    if not config.source_root.is_dir():
        raise ScaffoldError(f"source root does not exist: {config.source_root}")
    if not (config.catalog_root / "components.d").is_dir():
        raise ScaffoldError(
            f"catalog root does not contain components.d: {config.catalog_root}"
        )
    if config.source_root.resolve() == config.catalog_root.resolve():
        raise ScaffoldError(
            "new_skill.py creates product-owned skills; catalog-owned skills must use staging/"
        )
    if not config.license_file.is_file() or config.license_file.stat().st_size == 0:
        raise ScaffoldError("license file must be a non-empty file")
    if config.notice_file is not None and (
        not config.notice_file.is_file() or config.notice_file.stat().st_size == 0
    ):
        raise ScaffoldError("notice file must be a non-empty file")
    if config.destination.exists():
        raise ScaffoldError(
            f"refusing to overwrite existing path: {config.destination}"
        )


def read_template(template_root, relative_path):
    path = template_root / relative_path
    if not path.is_file():
        raise ScaffoldError(f"required template is missing: {path}")
    return path.read_text(encoding="utf-8")


def render_skill(config, template_root):
    text = read_template(template_root, "SKILL.md.template")
    replacements = {
        "replace-with-lowercase-hyphen-name": config.name,
        "State what the skill does, when it should trigger, and the nearest important case where it should not trigger.": json.dumps(
            config.description, ensure_ascii=False
        ),
        "Replace with an SPDX identifier or a reference to the bundled LICENSE file.": json.dumps(
            config.license_id, ensure_ascii=False
        ),
        "Replace with the owning HYGON-AI team.": json.dumps(
            config.owner, ensure_ascii=False
        ),
        "# Replace with skill title": f"# {display_name(config.name)}",
        "List the information, files, repository state, tools and approvals required.": "TODO: Document the required inputs, repository state, tools, and approvals.",
        "State the concrete files, decisions, reports or external changes produced.": "TODO: Document the concrete outputs and externally visible changes.",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = (
        "\n".join(
            line
            for line in text.splitlines()
            if not line.startswith("compatibility: Remove this field")
        )
        + "\n"
    )
    return text


def render_skill_card(config, template_root):
    text = read_template(template_root, "skill-card.md.template")
    replacements = {
        "Replace with the owning HYGON-AI team.": json.dumps(
            config.owner, ensure_ascii=False
        ),
        "HYGON-AI/replace-me": config.repo,
        "skills/replace-me": config.source_path,
        "Replace with the SPDX identifier.": json.dumps(
            config.license_id, ensure_ascii=False
        ),
        "lifecycle: published": "lifecycle: staging",
        "Replace with one sentence describing the skill's outcome.": config.description,
        "Replace with the owning HYGON-AI team and maintainer contact mechanism.": f"TODO: Add the maintained contact mechanism for {config.owner}.",
        "- Lifecycle: `staging` or `published`": "- Lifecycle: `staging`",
        "Replace with the SPDX identifier and required attribution files.": f"Declared as `{config.license_id}`; see the bundled `LICENSE` and any bundled `NOTICE`.",
        "List required operating systems, hardware, network access, tools and write\nsurfaces. State `none` explicitly where appropriate.": "TODO: List required operating systems, hardware, network access, tools, and write surfaces.",
        "Describe the last representative validation environment without turning a\npartial or synthetic result into a production claim.": "TODO: Describe representative validation evidence and its limitations.",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def render_evals(config, template_root):
    text = read_template(template_root, "evals/evals.json.template")
    replacements = {
        "replace-with-lowercase-hyphen-name": config.name,
        "replace-positive-one": "positive-one",
        "replace-positive-two": "positive-two",
        "replace-positive-three": "positive-three",
        "replace-negative-one": "negative-one",
        "replace-negative-two": "negative-two",
        "Replace with a realistic positive user request.": "TODO: Add a realistic positive request.",
        "Replace with one observable behavior assertion.": "TODO: Add one observable behavior assertion.",
        "Replace with a second positive request using different wording.": "TODO: Add a second positive request using different wording.",
        "Replace with a boundary-positive request.": "TODO: Add a boundary-positive request.",
        "Replace with a nearby task owned by another skill.": "TODO: Add a nearby request that must not trigger this skill.",
        "Replace with a vocabulary match that should not trigger this skill.": "TODO: Add a vocabulary match that must not trigger this skill.",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def render_openai(config, template_root):
    text = read_template(template_root, "agents/openai.yaml.template")
    short_description = " ".join(config.description.split())[:160]
    replacements = {
        '"Replace with user-facing name"': json.dumps(
            display_name(config.name), ensure_ascii=False
        ),
        '"Replace with a short capability description"': json.dumps(
            short_description, ensure_ascii=False
        ),
        "replace-with-skill-name": config.name,
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def render_files(config, template_root=TEMPLATE_ROOT):
    files = {
        Path("SKILL.md"): render_skill(config, template_root),
        Path("skill-card.md"): render_skill_card(config, template_root),
        Path("evals/evals.json"): render_evals(config, template_root),
    }
    if config.with_openai:
        files[Path("agents/openai.yaml")] = render_openai(config, template_root)
    if config.with_references:
        files[Path("references/details.md")] = (
            "# Detailed workflow\n\n"
            "TODO: Move detailed domain knowledge and long procedures here before publication.\n"
        )
    return files


def yaml_string(value):
    return json.dumps(value, ensure_ascii=False)


def component_skill_block(config):
    return f"  - path: {yaml_string(config.source_path)}\n    catalog_dir: {yaml_string(config.name)}\n    category: {yaml_string(config.category)}\n"


def component_files(catalog_root):
    component_dir = catalog_root / "components.d"
    return sorted(component_dir.glob("*.yml")) + sorted(component_dir.glob("*.yaml"))


def append_component_skill(original, skill_block):
    """Insert a list item into a block-style skills sequence without reformatting."""
    lines = original.splitlines(keepends=True)
    skills_index = None
    for index, line in enumerate(lines):
        if re.fullmatch(r"skills:\s*(?:#.*)?\n?", line):
            skills_index = index
            break
    if skills_index is None:
        raise ScaffoldError("existing component must use a block-style skills: list")

    insertion = len(lines)
    for index in range(skills_index + 1, len(lines)):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not lines[index][0].isspace():
            insertion = index
            break

    if (
        insertion > 0
        and lines[insertion - 1]
        and not lines[insertion - 1].endswith("\n")
    ):
        lines[insertion - 1] += "\n"
    lines.insert(insertion, skill_block)
    return "".join(lines)


def render_component(config):
    component_dir = config.catalog_root / "components.d"
    yml_path = component_dir / f"{config.component}.yml"
    yaml_path = component_dir / f"{config.component}.yaml"
    if yml_path.exists() and yaml_path.exists():
        raise ScaffoldError(
            f"component has both .yml and .yaml definitions: {config.component}"
        )
    target = yaml_path if yaml_path.exists() else yml_path

    for path in component_files(config.catalog_root):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ScaffoldError(f"{path} is invalid YAML: {exc}") from exc
        if not isinstance(data, dict):
            raise ScaffoldError(f"{path} must contain a mapping")
        for skill in data.get("skills", []):
            if not isinstance(skill, dict):
                continue
            if skill.get("catalog_dir") == config.name:
                raise ScaffoldError(
                    f"catalog_dir '{config.name}' is already registered in {path}"
                )
            if (
                data.get("repo") == config.repo
                and skill.get("path") == config.source_path
            ):
                raise ScaffoldError(
                    f"source path '{config.source_path}' is already registered in {path}"
                )
        if data.get("repo") == config.repo and path != target:
            raise ScaffoldError(f"repo '{config.repo}' is already owned by {path}")

    if target.exists():
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
        if data.get("repo") != config.repo:
            raise ScaffoldError(f"{target} repo does not match '{config.repo}'")
        if data.get("ref", "main") != config.ref:
            raise ScaffoldError(f"{target} ref does not match '{config.ref}'")
        if data.get("local") is True:
            raise ScaffoldError(
                f"cannot append a product-owned skill to local component {target}"
            )
        original = target.read_text(encoding="utf-8")
        return target, append_component_skill(original, component_skill_block(config))

    text = (
        f"name: {yaml_string(config.product_name)}\n"
        f"repo: {yaml_string(config.repo)}\n"
        f"ref: {yaml_string(config.ref)}\n"
        f"description: {yaml_string(config.product_description)}\n"
        "skills:\n"
        f"{component_skill_block(config)}"
    )
    return target, text


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(content)


def write_text_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            delete=False,
            dir=str(path.parent),
            prefix=f".{path.name}-",
        ) as stream:
            stream.write(content)
            temporary = Path(stream.name)
        if path.exists():
            shutil.copymode(path, temporary)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_scaffold(config, template_root=TEMPLATE_ROOT):
    validate_config(config)
    files = render_files(config, template_root)
    component_path, component_text = render_component(config)

    if config.dry_run:
        print(f"Would create {config.destination}")
        print(f"Would update {component_path}")
        print(f"Would copy license from {config.license_file}")
        if config.notice_file:
            print(f"Would copy NOTICE from {config.notice_file}")
        return

    config.destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".new-skill-", dir=str(config.destination.parent))
    )
    try:
        for relative, content in files.items():
            write_text(temporary / relative, content)
        shutil.copyfile(config.license_file, temporary / "LICENSE")
        if config.notice_file:
            shutil.copyfile(config.notice_file, temporary / "NOTICE")

        temporary.replace(config.destination)
        write_text_atomic(component_path, component_text)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        if config.destination.exists():
            shutil.rmtree(config.destination)
        raise

    print(f"Created {config.destination}")
    print(f"Updated {component_path}")
    print(f"Copied license from {config.license_file}")
    if config.notice_file:
        print(f"Copied NOTICE from {config.notice_file}")
    print(
        "NEXT: verify --license matches the copied license text and NOTICE obligations."
    )
    print(
        "NEXT: replace every TODO and set skill-card lifecycle to published after review."
    )
    print(
        "NEXT: merge the source-repository change before synchronizing this component."
    )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Create a product-owned Skill scaffold and component registration."
    )
    parser.add_argument("name", help="globally descriptive lowercase-hyphen skill name")
    parser.add_argument(
        "--repo", required=True, help="HYGON-AI source repository in owner/name form"
    )
    parser.add_argument(
        "--owner", required=True, help="owning team recorded in Skill metadata"
    )
    parser.add_argument(
        "--description",
        required=True,
        help="capability and trigger-boundary description",
    )
    parser.add_argument(
        "--license",
        dest="license_id",
        required=True,
        help="SPDX expression recorded in SKILL.md and skill-card.md",
    )
    parser.add_argument(
        "--license-file",
        help="license text to copy; defaults to LICENSE, LICENSE.txt, or LICENSE.md in source root",
    )
    parser.add_argument(
        "--notice-file",
        help="NOTICE text to copy; defaults to an existing NOTICE file in source root",
    )
    parser.add_argument("--category", required=True, choices=sorted(ALLOWED_CATEGORIES))
    parser.add_argument(
        "--ref", default="main", help="reviewed source branch or release tag"
    )
    parser.add_argument(
        "--component", help="components.d file stem; defaults to normalized repo name"
    )
    parser.add_argument(
        "--product-name",
        help="component display name; defaults to title-cased component",
    )
    parser.add_argument(
        "--product-description",
        help="component description; defaults to the Skill description",
    )
    parser.add_argument(
        "--source-root", default=".", help="product repository root; defaults to cwd"
    )
    parser.add_argument(
        "--catalog-root",
        default=str(CATALOG_ROOT),
        help="SkillHub checkout containing components.d and templates",
    )
    parser.add_argument(
        "--with-openai", action="store_true", help="create agents/openai.yaml"
    )
    parser.add_argument(
        "--with-references", action="store_true", help="create references/details.md"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show planned paths without writing"
    )
    return parser.parse_args(argv)


def config_from_args(args):
    source_root = Path(args.source_root).resolve()
    catalog_root = Path(args.catalog_root).resolve()
    name = require_text(args.name, "name")
    repo = require_text(args.repo, "repo")
    component = require_text(args.component or normalized_component(repo), "component")
    license_file = resolve_optional_file(
        args.license_file, source_root, ("LICENSE", "LICENSE.txt", "LICENSE.md")
    )
    if license_file is None:
        raise ScaffoldError(
            "no source LICENSE found; add one or pass --license-file explicitly"
        )
    notice_file = resolve_optional_file(
        args.notice_file, source_root, ("NOTICE", "NOTICE.txt", "NOTICE.md")
    )
    return ScaffoldConfig(
        name=name,
        repo=repo,
        ref=require_text(args.ref, "ref"),
        owner=require_text(args.owner, "owner"),
        description=require_text(args.description, "description"),
        license_id=require_text(args.license_id, "license"),
        category=require_text(args.category, "category"),
        component=component,
        product_name=require_text(
            args.product_name or display_name(component), "product name"
        ),
        product_description=require_text(
            args.product_description or args.description, "product description"
        ),
        source_root=source_root,
        catalog_root=catalog_root,
        license_file=license_file,
        notice_file=notice_file,
        with_openai=args.with_openai,
        with_references=args.with_references,
        dry_run=args.dry_run,
    )


def main(argv=None):
    try:
        config = config_from_args(parse_args(argv))
        create_scaffold(config)
    except ScaffoldError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
