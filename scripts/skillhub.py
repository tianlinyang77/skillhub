#!/usr/bin/env python3
"""Shared catalog parsing and validation helpers."""

from __future__ import print_function

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

import yaml


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_GITHUB_OWNER = "HYGON-AI"
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
INLINE_SKILL_PATH_RE = re.compile(r"`([^`\s]*SKILL\.md)`")
SECRET_PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
)
BEHAVIOR_ASSERTION_FIELDS = (
    "expected_behavior",
    "unexpected_behavior",
    "logs_contain",
    "files_exist",
)


class CatalogError(Exception):
    pass


def load_yaml(path):
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CatalogError("{}: invalid YAML: {}".format(path.relative_to(ROOT), exc))
    if not isinstance(value, dict):
        raise CatalogError("{}: expected a YAML mapping".format(path.relative_to(ROOT)))
    return value


def load_json(path, root=ROOT):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CatalogError("{}: invalid JSON: {}".format(path.relative_to(root), exc))
    if not isinstance(value, dict):
        raise CatalogError("{}: expected a JSON object".format(path.relative_to(root)))
    return value


def safe_relative_path(value, label):
    if not isinstance(value, str) or not value.strip():
        raise CatalogError("{} must be a non-empty string".format(label))
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise CatalogError("{} must be a safe repository-relative POSIX path".format(label))
    return value


def load_components(root=ROOT):
    component_dir = root / "components.d"
    paths = sorted(list(component_dir.glob("*.yml")) + list(component_dir.glob("*.yaml")))
    if not paths:
        raise CatalogError("components.d contains no component definitions")

    components = []
    seen_catalog_dirs = {}
    for path in paths:
        data = load_yaml(path)
        for field in ("name", "repo", "description", "skills"):
            if field not in data:
                raise CatalogError("{}: missing required field '{}'".format(path.relative_to(root), field))
        if not isinstance(data["name"], str) or not data["name"].strip():
            raise CatalogError("{}: name must be a non-empty string".format(path.relative_to(root)))
        repo = str(data["repo"])
        if not REPO_RE.match(repo):
            raise CatalogError("{}: repo must use owner/name form".format(path.relative_to(root)))
        owner, _ = repo.split("/", 1)
        if owner != OFFICIAL_GITHUB_OWNER:
            raise CatalogError("{}: repo must be owned by {}".format(
                path.relative_to(root), OFFICIAL_GITHUB_OWNER))
        ref = data.get("ref", "main")
        if not isinstance(ref, str) or not REF_RE.match(ref) or ".." in ref:
            raise CatalogError("{}: ref contains unsafe characters".format(path.relative_to(root)))
        if not isinstance(data["description"], str) or not data["description"].strip():
            raise CatalogError("{}: description must be a non-empty string".format(path.relative_to(root)))
        if not isinstance(data["skills"], list) or not data["skills"]:
            raise CatalogError("{}: skills must be a non-empty list".format(path.relative_to(root)))
        if "local" in data and not isinstance(data["local"], bool):
            raise CatalogError("{}: local must be true or false".format(path.relative_to(root)))

        normalized = dict(data)
        normalized["ref"] = ref
        normalized["local"] = data.get("local", False)
        normalized["file"] = path
        normalized_skills = []
        for index, skill in enumerate(data["skills"]):
            label = "{}: skills[{}]".format(path.relative_to(root), index)
            if not isinstance(skill, dict):
                raise CatalogError("{} must be a mapping".format(label))
            for field in ("path", "catalog_dir", "category"):
                if field not in skill:
                    raise CatalogError("{}: missing '{}'".format(label, field))
            source_path = safe_relative_path(skill["path"], "{}.path".format(label))
            catalog_dir = skill["catalog_dir"]
            if not isinstance(catalog_dir, str) or len(catalog_dir) > 64 or not SKILL_NAME_RE.match(catalog_dir):
                raise CatalogError("{}.catalog_dir must be lowercase hyphen-case and at most 64 characters".format(label))
            category = skill["category"]
            if not isinstance(category, str) or not category.strip():
                raise CatalogError("{}.category must be a non-empty string".format(label))
            if catalog_dir in seen_catalog_dirs:
                raise CatalogError("duplicate catalog_dir '{}': {} and {}".format(
                    catalog_dir, seen_catalog_dirs[catalog_dir], path.relative_to(root)))
            seen_catalog_dirs[catalog_dir] = path.relative_to(root)
            item = dict(skill)
            item["path"] = source_path
            normalized_skills.append(item)
        normalized["skills"] = normalized_skills
        components.append(normalized)
    return components


def parse_skill_frontmatter(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise CatalogError("{}: SKILL.md must start with YAML frontmatter".format(path.relative_to(ROOT)))
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise CatalogError("{}: SKILL.md frontmatter is not closed".format(path.relative_to(ROOT)))
    try:
        metadata = yaml.safe_load("\n".join(lines[1:end]))
    except Exception as exc:
        raise CatalogError("{}: invalid frontmatter: {}".format(path.relative_to(ROOT), exc))
    if not isinstance(metadata, dict):
        raise CatalogError("{}: frontmatter must be a mapping".format(path.relative_to(ROOT)))
    return metadata, text, len(lines)


def registered_skills(components, root=ROOT):
    records = []
    for component in components:
        for spec in component["skills"]:
            skill_dir = root / "skills" / spec["catalog_dir"]
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                raise CatalogError("{}: registered skill is missing SKILL.md".format(skill_dir.relative_to(root)))
            metadata, text, line_count = parse_skill_frontmatter(skill_file)
            record = {
                "component": component,
                "spec": spec,
                "dir": skill_dir,
                "metadata": metadata,
                "text": text,
                "line_count": line_count,
            }
            records.append(record)
    return records


def file_tree_digest(path):
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file_path.relative_to(path)).replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def validate_lock(components, records, root=ROOT):
    errors = []
    lock_path = root / ".skillhub-lock.json"
    if not lock_path.is_file():
        return [".skillhub-lock.json is required"]
    try:
        lock = load_json(lock_path, root)
    except CatalogError as exc:
        return [str(exc)]
    if lock.get("schema_version") != 1:
        errors.append(".skillhub-lock.json: schema_version must equal 1")
    entries = lock.get("skills")
    if not isinstance(entries, dict):
        return errors + [".skillhub-lock.json: skills must be an object"]

    expected = {}
    for component in components:
        if component["local"]:
            continue
        for spec in component["skills"]:
            expected[spec["catalog_dir"]] = (component, spec)
    missing = sorted(set(expected) - set(entries))
    extra = sorted(set(entries) - set(expected))
    for name in missing:
        errors.append(".skillhub-lock.json: missing remote skill '{}'".format(name))
    for name in extra:
        errors.append(".skillhub-lock.json: unregistered skill '{}'".format(name))

    record_by_name = {
        record["spec"]["catalog_dir"]: record for record in records
    }
    for name in sorted(set(expected) & set(entries)):
        component, spec = expected[name]
        entry = entries[name]
        if not isinstance(entry, dict):
            errors.append(".skillhub-lock.json: skill '{}' must be an object".format(name))
            continue
        exact_fields = {
            "repo": component["repo"],
            "ref": component["ref"],
            "path": spec["path"],
        }
        for field, expected_value in exact_fields.items():
            if entry.get(field) != expected_value:
                errors.append(".skillhub-lock.json: skill '{}'.{} must equal '{}'".format(
                    name, field, expected_value))
        commit = entry.get("commit")
        if not isinstance(commit, str) or not COMMIT_RE.match(commit):
            errors.append(".skillhub-lock.json: skill '{}'.commit must be a 40-character lowercase Git commit".format(name))
        digest = entry.get("content_digest")
        if not isinstance(digest, str) or not DIGEST_RE.match(digest):
            errors.append(".skillhub-lock.json: skill '{}'.content_digest must be a lowercase SHA-256 digest".format(name))
        else:
            record = record_by_name.get(name)
            if record and file_tree_digest(record["dir"]) != digest:
                errors.append(".skillhub-lock.json: skill '{}'.content_digest does not match the published tree".format(name))
    return errors


def validate_inline_skill_dependencies(skill_dir, text, root=ROOT):
    """Reject references to sibling skills that are absent after installation."""
    errors = []
    for target in INLINE_SKILL_PATH_RE.findall(text):
        candidate = (skill_dir / target).resolve()
        try:
            candidate.relative_to(skill_dir.resolve())
        except ValueError:
            errors.append("{}/SKILL.md: inline dependency escapes skill directory: {}".format(
                skill_dir.relative_to(root), target))
            continue
        if not candidate.is_file():
            errors.append("{}/SKILL.md: missing inline skill dependency: {}".format(
                skill_dir.relative_to(root), target))
        elif candidate != (skill_dir / "SKILL.md").resolve():
            errors.append("{}/SKILL.md: nested SKILL.md dependencies are not allowed; move supporting instructions to references/*.md: {}".format(
                skill_dir.relative_to(root), target))
    return errors


def validate_markdown_links(skill_dir, root=ROOT):
    errors = []
    for markdown in sorted(skill_dir.rglob("*.md")):
        try:
            text = markdown.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append("{}: Markdown must be UTF-8".format(markdown.relative_to(root)))
            continue
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "#")):
                continue
            candidate = (markdown.parent / target).resolve()
            try:
                candidate.relative_to(skill_dir.resolve())
            except ValueError:
                errors.append("{}: link escapes skill directory: {}".format(
                    markdown.relative_to(root), target))
                continue
            if not candidate.exists():
                errors.append("{}: broken relative link: {}".format(
                    markdown.relative_to(root), target))
    return errors


def validate_eval_dataset(path, root=ROOT):
    errors = []
    try:
        value = load_json(path, root)
    except CatalogError as exc:
        return [str(exc)]
    evaluations = value.get("evaluations")
    if not isinstance(evaluations, list) or not evaluations:
        return ["{}: evaluations must be a non-empty list".format(path.relative_to(root))]

    seen_ids = set()
    positives = 0
    negatives = 0
    behavior_cases = 0
    for index, case in enumerate(evaluations):
        label = "{}: evaluations[{}]".format(path.relative_to(root), index)
        if not isinstance(case, dict):
            errors.append("{} must be an object".format(label))
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append("{}: id must be a non-empty string".format(label))
        elif case_id in seen_ids:
            errors.append("{}: duplicate id '{}'".format(label, case_id))
        else:
            seen_ids.add(case_id)
        prompt = case.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append("{}: prompt must be a non-empty string".format(label))
        should_trigger = case.get("skill_should_trigger")
        if not isinstance(should_trigger, bool):
            errors.append("{}: skill_should_trigger must be true or false".format(label))
        elif should_trigger:
            positives += 1
        else:
            negatives += 1

        has_behavior = False
        for field in BEHAVIOR_ASSERTION_FIELDS:
            if field not in case:
                continue
            assertions = case[field]
            if not isinstance(assertions, list) or not assertions or not all(
                    isinstance(item, str) and item.strip() for item in assertions):
                errors.append("{}: {} must be a non-empty list of non-empty strings".format(
                    label, field))
            else:
                has_behavior = True
        if should_trigger is True and has_behavior:
            behavior_cases += 1

    if positives < 3:
        errors.append("{}: requires at least 3 positive trigger cases; found {}".format(
            path.relative_to(root), positives))
    if negatives < 2:
        errors.append("{}: requires at least 2 negative trigger cases; found {}".format(
            path.relative_to(root), negatives))
    if behavior_cases < 1:
        errors.append("{}: requires at least 1 positive case with a behavioral assertion".format(
            path.relative_to(root)))
    return errors


def validate_catalog(root=ROOT):
    errors = []
    warnings = []
    try:
        components = load_components(root)
        records = registered_skills(components, root)
    except CatalogError as exc:
        return [str(exc)], warnings, [], []

    registered = set(record["spec"]["catalog_dir"] for record in records)
    skills_dir = root / "skills"
    actual = set(p.name for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else set()
    for orphan in sorted(actual - registered):
        errors.append("skills/{} is not registered in components.d".format(orphan))

    errors.extend(validate_lock(components, records, root))

    for record in records:
        rel = record["dir"].relative_to(root)
        metadata = record["metadata"]
        extra = sorted(set(metadata) - {"name", "description"})
        if extra:
            errors.append("{}/SKILL.md: unsupported frontmatter fields: {}".format(rel, ", ".join(extra)))
        if metadata.get("name") != record["spec"]["catalog_dir"]:
            errors.append("{}/SKILL.md: name must equal catalog_dir '{}'".format(rel, record["spec"]["catalog_dir"]))
        description = metadata.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append("{}/SKILL.md: description must be a non-empty string".format(rel))
        elif len(description) > 1024:
            errors.append("{}/SKILL.md: description exceeds 1024 characters".format(rel))
        elif "<" in description or ">" in description:
            errors.append("{}/SKILL.md: description cannot contain angle brackets".format(rel))
        if record["line_count"] > 500:
            errors.append("{}/SKILL.md: {} lines; keep it at or below 500".format(rel, record["line_count"]))

        nested_skill_files = [
            path for path in record["dir"].rglob("SKILL.md")
            if path != record["dir"] / "SKILL.md"
        ]
        for path in nested_skill_files:
            errors.append("{}: nested SKILL.md is not allowed in the flat published catalog".format(
                path.relative_to(root)))

        for path in record["dir"].rglob("*"):
            if path.is_symlink():
                errors.append("{}: symbolic links are not allowed in published skills".format(path.relative_to(root)))
            if path.is_file() and path.stat().st_size <= 2 * 1024 * 1024:
                try:
                    content = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                for label, pattern in SECRET_PATTERNS:
                    if pattern.search(content):
                        errors.append("{}: possible hard-coded {}".format(path.relative_to(root), label))

        errors.extend(validate_markdown_links(record["dir"], root))

        errors.extend(validate_inline_skill_dependencies(
            record["dir"], record["text"], root))

        skill_card = record["dir"] / "skill-card.md"
        if not skill_card.is_file():
            errors.append("{}: skill-card.md is required for published skills".format(rel))

        eval_file = record["dir"] / "evals" / "evals.json"
        if not eval_file.is_file():
            errors.append("{}: evals/evals.json is required for published skills".format(rel))
        else:
            errors.extend(validate_eval_dataset(eval_file, root))

        openai_yaml = record["dir"] / "agents" / "openai.yaml"
        if openai_yaml.exists():
            try:
                interface = load_yaml(openai_yaml).get("interface", {})
                for field in ("display_name", "short_description", "default_prompt"):
                    if not isinstance(interface.get(field), str) or not interface[field].strip():
                        errors.append("{}: interface.{} must be a non-empty string".format(openai_yaml.relative_to(root), field))
            except CatalogError as exc:
                errors.append(str(exc))
        else:
            warnings.append("{}: agents/openai.yaml is recommended".format(rel))

    return errors, warnings, components, records


def dump_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
