"""One-time local skill import. Source files are data, never executable hooks."""

# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

import yaml

if __package__:
    from . import new_skill as generator
    from . import skillhub as catalog
else:
    import new_skill as generator
    import skillhub as catalog


class ImportSkillError(ValueError):
    """Import cannot proceed safely without correcting or confirming the input."""


PORTABLE_FRONTMATTER_FIELDS = frozenset((
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
))
LEGACY_RUNTIME_PLACEHOLDERS = frozenset((
    "TODO: Record runtime requirements and permissions.",
    "TODO: List required operating systems, hardware, network access, tools, and write surfaces.",
))
LEGACY_VALIDATION_PLACEHOLDERS = frozenset((
    "TODO: Record representative validation and known limitations; importing files is not a behavior test.",
    "TODO: Describe representative validation evidence and its limitations.",
))
LEGACY_ORIGIN_PLACEHOLDER = "TODO: Record the original repository URL or another publishable origin or attribution."


def plain_path(path):
    """Reject links, including Windows junctions, before walking or copying them."""
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ImportSkillError(
            f"{path}: symbolic links and junctions cannot be imported; use a regular directory or file"
        )
    if not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode):
        raise ImportSkillError(f"{path}: special files cannot be imported")
    return info


def inspect_source(path):
    source = Path(path).absolute()
    if not source.exists():
        raise ImportSkillError(f"Source does not exist: {source}")
    plain_path(source)
    if source.is_file() and source.name == "SKILL.md":
        source = source.parent
    if not source.is_dir() or not (source / "SKILL.md").is_file():
        raise ImportSkillError(
            "Select one skill directory containing SKILL.md, not a repository or collection of skills"
        )
    plain_path(source)
    source = source.resolve()
    count = size = 0
    for directory, directories, filenames in os.walk(source, followlinks=False):
        for name in directories + filenames:
            child = Path(directory) / name
            info = plain_path(child)
            relative = child.relative_to(source)
            if not child.resolve().is_relative_to(source):
                raise ImportSkillError(f"{relative}: path escapes the selected skill directory")
            if any(part in catalog.FORBIDDEN_PACKAGE_PARTS for part in relative.parts):
                raise ImportSkillError(
                    f"{relative}: generated, VCS or dependency directories cannot be imported"
                )
            if stat.S_ISREG(info.st_mode):
                count += 1
                size += info.st_size
                if info.st_size > catalog.MAX_SKILL_FILE_BYTES:
                    raise ImportSkillError(f"{relative}: file exceeds the package size limit")
                if child.name.lower() == "skill.md" and child != source / "SKILL.md":
                    raise ImportSkillError(
                        f"{relative}: nested SKILL.md is not allowed; import one flat skill at a time"
                    )
            if count > catalog.MAX_SKILL_FILES or size > catalog.MAX_SKILL_PACKAGE_BYTES:
                raise ImportSkillError("Source exceeds the package file-count or total-size limit")
    errors = catalog.validate_skill_tree(source, source.parent)
    if errors:
        raise ImportSkillError("\n".join(errors))
    return source


def read_document(path, *, optional_header=False):
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ImportSkillError(f"{path.name}: Markdown must be UTF-8") from exc
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        if optional_header:
            return {}, text
        raise ImportSkillError(f"{path.name}: expected YAML frontmatter with name and description")
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"), None)
    if end is None:
        raise ImportSkillError(f"{path.name}: YAML frontmatter is not closed")
    try:
        header = "".join(lines[1:end])
        data = yaml.safe_load(header)
        node = yaml.compose(header)
        if not isinstance(data, dict) or any(not isinstance(key, str) for key in data):
            raise ImportSkillError(f"{path.name}: frontmatter must be a string-keyed mapping")
        keys = [key.value for key, _ in node.value]
        if len(keys) != len(set(keys)):
            raise ImportSkillError(f"{path.name}: duplicate frontmatter keys are ambiguous")
    except yaml.YAMLError as exc:
        raise ImportSkillError(f"{path.name}: invalid YAML: {exc}") from exc
    return data, "".join(lines[end + 1:])


def normalize_skill_document(frontmatter, body, source_name):
    """Translate source-only frontmatter into visible body context in the copy."""
    portable = {
        key: value for key, value in frontmatter.items()
        if key in PORTABLE_FRONTMATTER_FIELDS
    }
    name = portable.get("name")
    errors = catalog.validate_skill_frontmatter(portable, name, source_name)
    if errors:
        raise ImportSkillError("\n".join(errors))
    source_only = {
        key: value for key, value in frontmatter.items()
        if key not in PORTABLE_FRONTMATTER_FIELDS
    }
    if source_only:
        body = body.rstrip() + (
            "\n\n## Imported source metadata\n\n"
            "The following source-specific frontmatter was preserved during import "
            "but is not part of the portable Agent Skills frontmatter contract.\n\n"
            "```yaml\n"
            + yaml.safe_dump(source_only, allow_unicode=True, sort_keys=False)
            + "```\n"
        )
    document = (
        "---\n"
        + yaml.safe_dump(portable, allow_unicode=True, sort_keys=False)
        + "---\n"
        + body
    )
    return portable, document, tuple(source_only)


def value_or_prompt(value, flag, label, args, prompt, categories=None):
    if value is not None:
        if not isinstance(value, str) or not value.strip():
            raise ImportSkillError(f"{flag} must be a non-empty string")
        return value
    if args.non_interactive:
        raise ImportSkillError(f"Missing {flag}; supply it or rerun without --non-interactive")
    return prompt(label, categories)


def select_material(source, explicit, stem):
    bundled = next(
        (source / name for name in (stem, f"{stem}.txt", f"{stem}.md") if (source / name).exists()),
        None,
    )
    selected = Path(explicit).absolute() if explicit else bundled
    if selected is None:
        return None
    info = plain_path(selected)
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= catalog.MAX_SKILL_FILE_BYTES:
        raise ImportSkillError(
            f"{selected}: expected a non-empty license or notice file within the package size limit"
        )
    if bundled is not None:
        plain_path(bundled)
        if selected.read_bytes() != bundled.read_bytes():
            raise ImportSkillError(
                f"--{stem.lower()}-file conflicts with bundled {bundled.name}; original material cannot be replaced"
            )
    return selected.resolve()


def clean_legacy_card(body):
    """Remove only exact retired generator placeholders, not author-written notes."""
    validation = catalog.skill_card_section(body, "Validation")
    if validation:
        original_content = validation.group("content")
        content = "".join(
            line for line in original_content.splitlines(keepends=True)
            if line.strip() not in LEGACY_VALIDATION_PLACEHOLDERS
        )
        if content != original_content:
            heading = body[validation.start():validation.start("content")]
            replacement = heading + content if content.strip() else ""
            body = body[:validation.start()] + replacement + body[validation.end():]
    return "".join(
        line for line in body.splitlines(keepends=True)
        if line.strip() != LEGACY_ORIGIN_PLACEHOLDER
    )


def render_card(source, frontmatter, config, upstream):
    path = source / "skill-card.md"
    original, body = (
        read_document(path, optional_header=True) if path.exists() else ({}, "# Skill Card\n")
    )
    body = clean_legacy_card(body)
    data = dict(original)
    data.setdefault("schema_version", 1)
    data.update(owner=config.owner, license=config.license_id, lifecycle="published")
    data["source"] = {"repo": config.repo, "path": config.source_path}
    sections = {
        "Summary": config.description,
        "Owner": config.owner,
        "Source": f"Locally maintained at `{config.repo}`, path `{config.source_path}`.",
        "License": f"Declared as `{config.license_id}`; see original source licensing and any preserved LICENSE/NOTICE material. Import does not relicense this content.",
        "Runtime and permissions": config.runtime_permissions,
    }
    for title, content in sections.items():
        if title == "Runtime and permissions":
            section = catalog.skill_card_section(body, title)
            if section:
                if section.group("content").strip() != content.strip():
                    body = body[:section.start()] + f"## {title}\n\n{content}\n\n" + body[section.end():]
                continue
        if not re.search(rf"^## {re.escape(title)}\s*$", body, re.MULTILINE):
            body += f"\n\n## {title}\n\n{content}\n"
    body += (
        "\n\n## Local catalog import\n\n"
        f"This copy is maintained in `{config.repo}` at `{config.source_path}`, not synchronized upstream. "
        "Existing instructions, attribution and validation statements describe the imported source; "
        "review their applicability before publishing this copy. No skill code was executed by the importer.\n"
    )
    if original.get("source"):
        body += "\nOriginal Skill Card source metadata:\n\n```json\n" + json.dumps(
            original["source"], ensure_ascii=False, indent=2
        ) + "\n```\n"
    if original.get("owner") and original["owner"] != config.owner:
        body += f"\nOriginal Skill Card owner: {original['owner']}\n"
    if upstream:
        body += f"\nAdditional origin or attribution: {upstream}\n"
    return "---\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False) + "---\n" + body


def validate_prepared(stage_root, config):
    """Run the existing policy gate on the complete isolated import."""
    (stage_root / "components.d").mkdir()
    (stage_root / "staging").mkdir()
    generator.write_text(
        stage_root / "components.d" / "skillhub.yml",
        yaml.safe_dump(
            {
                "name": "SkillHub",
                "local": True,
                "description": "Local import validation fixture.",
                "skills": [{
                    "path": config.source_path,
                    "catalog_dir": config.name,
                    "category": config.category,
                }],
            },
            sort_keys=False,
        ),
    )
    generator.write_text(stage_root / ".skillhub-lock.json", '{"schema_version": 1, "skills": {}}\n')
    generator.write_text(stage_root / "admission-exceptions.yml", "schema_version: 1\nexceptions: []\n")
    errors, warnings, _, _ = catalog.validate_catalog(stage_root)
    if errors:
        raise ImportSkillError(
            "Imported package needs correction before copying:\n" + "\n".join(errors)
        )
    for warning in warnings:
        print(f"WARNING: {warning}")


def registry_snapshot(root):
    snapshot = {}
    for path in generator.component_files(root):
        plain_path(path)
        snapshot[path] = path.read_bytes()
    return snapshot


def import_local_skill(args, root, prompt):
    source = inspect_source(args.source)
    root = root.resolve()
    source_frontmatter, body = read_document(source / "SKILL.md")
    frontmatter, imported_skill, source_only = normalize_skill_document(
        source_frontmatter, body, source.name
    )
    name = frontmatter.get("name")
    if not catalog.SKILL_NAME_RE.fullmatch(name) or name in catalog.FORBIDDEN_GENERIC_CATALOG_DIRS:
        raise ImportSkillError(
            "Source name must be globally descriptive lowercase hyphen-case; the importer does not rename skills"
        )
    destination = root / "skills" / name
    if source.is_relative_to(destination.resolve()) or destination.resolve().is_relative_to(source):
        raise ImportSkillError("Source and catalog destination must not overlap")
    if destination.exists():
        raise ImportSkillError(
            f"Refusing to overwrite existing destination: {destination}. "
            "Edit the existing local copy and run contribute.py check; import is not an update command."
        )
    for path in (root / "skills", root / "components.d", destination):
        if path.exists() or path.is_symlink():
            plain_path(path)
        if not path.resolve().is_relative_to(root):
            raise ImportSkillError(f"{path}: destination escapes the catalog")
    existing, existing_body = (
        read_document(source / "skill-card.md", optional_header=True)
        if (source / "skill-card.md").exists() else ({}, "")
    )
    metadata = frontmatter.get("metadata", {})
    owner = value_or_prompt(
        args.owner,
        "--owner", "Maintaining team", args, prompt,
    )
    declarations = [
        value for value in (frontmatter.get("license"), existing.get("license"), args.license)
        if value is not None
    ]
    if any(value != declarations[0] for value in declarations):
        raise ImportSkillError(
            "Conflicting license declarations in SKILL.md, Skill Card or --license; resolve them without changing upstream authorship"
        )
    license_id = declarations[0] if declarations else "Apache-2.0"
    category = value_or_prompt(
        args.category or (
            metadata.get("category") if metadata.get("category") in catalog.ALLOWED_CATEGORIES else None
        ),
        "--category", "Catalog category number or name", args, prompt,
        sorted(catalog.ALLOWED_CATEGORIES),
    )
    license_file = select_material(source, args.license_file, "LICENSE")
    upstream = args.upstream
    notice_file = select_material(source, args.notice_file, "NOTICE")
    runtime_section = catalog.skill_card_section(existing_body, "Runtime and permissions")
    existing_runtime = runtime_section.group("content").strip() if runtime_section else None
    if existing_runtime in LEGACY_RUNTIME_PLACEHOLDERS:
        existing_runtime = None
    runtime_permissions = value_or_prompt(
        args.runtime_permissions if args.runtime_permissions is not None else existing_runtime or (
            "See [SKILL.md](SKILL.md) for runtime requirements and permissions."
            if args.non_interactive else None
        ),
        "--runtime-permissions", "Runtime requirements and permissions (or enter: see SKILL.md)", args, prompt,
    )
    if runtime_permissions.casefold() in ("see skill.md", "见 skill.md", "见skill.md"):
        runtime_permissions = "See [SKILL.md](SKILL.md) for runtime requirements and permissions."
    config = generator.ScaffoldConfig(
        name=name,
        repo=catalog.CATALOG_REPO,
        ref=catalog.CATALOG_REF,
        owner=owner,
        description=frontmatter["description"],
        license_id=license_id,
        category=category,
        local=True,
        component="skillhub",
        product_name="SkillHub",
        product_description="Directly maintained HYGON-AI SkillHub skills.",
        source_root=root,
        catalog_root=root,
        license_file=license_file,
        notice_file=notice_file,
        runtime_permissions=runtime_permissions,
    )
    generator.validate_config(config)
    before = registry_snapshot(root)
    component_path, component_text = generator.render_component(config)
    mismatch = generator.license_mismatch_warning(license_id, license_file)
    if mismatch:
        print(mismatch)
    print(f"Import {name}: {source} -> {destination}")
    if not declarations:
        print("Original contribution defaults to repository Apache-2.0; contributor must have the right to publish under these terms.")
    if source_only:
        print(
            "WARNING: translated non-portable source frontmatter into "
            "'Imported source metadata': " + ", ".join(source_only)
        )
    print("Preserve SKILL.md and resources. Generate the Skill Card as published; retain existing attribution.")
    print("Review redistribution rights and any repository-level LICENSE or NOTICE before publishing.")
    with tempfile.TemporaryDirectory(prefix=".import-skill-", dir=root) as temporary:
        stage_root = Path(temporary)
        candidate = stage_root / config.source_path
        shutil.copytree(source, candidate, symlinks=True)
        if source_only:
            generator.write_text(candidate / "SKILL.md", imported_skill)
        inspect_source(candidate)
        generator.write_text(candidate / "skill-card.md", render_card(candidate, frontmatter, config, upstream))
        for source_file, filename in ((license_file, "LICENSE"), (notice_file, "NOTICE")):
            if source_file:
                plain_path(source_file)
                shutil.copy2(source_file, candidate / filename)
        validate_prepared(stage_root, config)
        if args.dry_run:
            print(f"Would register {name} in {component_path}; no catalog files were changed.")
            return 0
        created = False
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.mkdir()
            created = True
            shutil.copytree(candidate, destination, dirs_exist_ok=True, symlinks=True)
            if registry_snapshot(root) != before:
                raise ImportSkillError("Component registration changed during import; retry after reviewing it")
            generator.write_text_atomic(component_path, component_text)
        except BaseException:
            if created and destination.resolve() == root / "skills" / name:
                plain_path(destination)
                shutil.rmtree(destination)
            raise
    print(f"Imported {name} and updated {component_path}. Source directory was not changed.")
    print(f"NEXT: review skills/{name}/skill-card.md; lifecycle is already published. Run checks before submitting.")
    print("NEXT: run python scripts/contribute.py check; commit and open a PR yourself. No submission was performed.")
    return 0
