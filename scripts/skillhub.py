#!/usr/bin/env python3
"""Shared catalog parsing and validation helpers."""

from __future__ import print_function

import hashlib
import json
import re
import unicodedata
from pathlib import Path, PurePosixPath

import yaml


ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_GITHUB_OWNER = "HYGON-AI"
CATALOG_REPO = OFFICIAL_GITHUB_OWNER + "/skillhub"
CATALOG_REF = "main"
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EVAL_ID_RE = SKILL_NAME_RE
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
INLINE_SKILL_PATH_RE = re.compile(r"`([^`\s]*SKILL\.md)`")
ALLOWED_SKILL_FRONTMATTER_FIELDS = frozenset((
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
))
ALLOWED_COMPONENT_FIELDS = frozenset((
    "name", "repo", "ref", "local", "description", "skills",
))
ALLOWED_COMPONENT_SKILL_FIELDS = frozenset((
    "path", "catalog_dir", "category",
))
ALLOWED_CATEGORIES = frozenset((
    "Governance and Compliance",
    "Developer Tools",
    "HCU Platform",
    "Operator Development",
    "Performance and Profiling",
    "Accuracy and Debugging",
    "Training",
    "Inference",
    "Distributed Systems",
    "CI and Release",
    "Documentation",
))
FORBIDDEN_GENERIC_CATALOG_DIRS = frozenset((
    "add-model",
    "benchmark",
    "build",
    "deploy",
    "profile",
    "test",
))
ALLOWED_EVAL_FIELDS = frozenset((
    "id",
    "prompt",
    "skill_should_trigger",
    "expected_behavior",
    "unexpected_behavior",
    "logs_contain",
    "files_exist",
))
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500
MAX_SKILL_LINES = 500
MAX_SKILL_FILES = 256
MAX_SKILL_FILE_BYTES = 5 * 1024 * 1024
MAX_SKILL_PACKAGE_BYTES = 20 * 1024 * 1024
FORBIDDEN_PACKAGE_PARTS = frozenset((
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "venv",
))
FORBIDDEN_PACKAGE_FILES = frozenset((
    ".DS_Store",
    ".env",
    "Thumbs.db",
))
REQUIRED_SKILL_CARD_HEADINGS = (
    "Summary",
    "Owner",
    "Source",
    "License",
    "Runtime and permissions",
    "Validation",
)
ALLOWED_SKILL_CARD_FIELDS = frozenset((
    "schema_version", "owner", "source", "license", "lifecycle",
))
ALLOWED_SKILL_CARD_SOURCE_FIELDS = frozenset(("repo", "path"))
ALLOWED_EXCEPTION_FIELDS = frozenset(("repo", "path", "reasons"))
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
SKILL_TEMPLATE_PLACEHOLDERS = (
    "replace-with-lowercase-hyphen-name",
    "hygon-ai/replace-me",
    "replace-with-skill-name",
)


class CatalogError(Exception):
    pass


def display_path(path, root=ROOT):
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def load_yaml(path, root=ROOT):
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CatalogError("{}: invalid YAML: {}".format(display_path(path, root), exc))
    if not isinstance(value, dict):
        raise CatalogError("{}: expected a YAML mapping".format(display_path(path, root)))
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
    if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in value
            or value.startswith(("-", ":"))
            or any(ord(character) < 32 for character in value)
    ):
        raise CatalogError("{} must be a safe repository-relative POSIX path".format(label))
    return value


def load_components(root=ROOT):
    """Load local-first component registrations.

    Local components may omit ``repo``; it is normalized to the catalog
    repository and then validated. Remote components remain available as an
    explicit opt-in for product teams that own their source skills.
    """
    component_dir = root / "components.d"
    paths = sorted(list(component_dir.glob("*.yml")) + list(component_dir.glob("*.yaml")))
    if not paths:
        raise CatalogError("components.d contains no component definitions")

    components = []
    seen_catalog_dirs = {}
    seen_component_names = set()
    seen_remote_repositories = set()
    for path in paths:
        if not SKILL_NAME_RE.fullmatch(path.stem):
            raise CatalogError("{}: component filename must use lowercase hyphen-case".format(
                path.relative_to(root)))
        data = load_yaml(path, root)
        extra_fields = sorted(set(data) - ALLOWED_COMPONENT_FIELDS)
        if extra_fields:
            raise CatalogError("{}: unsupported fields: {}".format(
                path.relative_to(root), ", ".join(extra_fields)))
        for field in ("name", "description", "skills"):
            if field not in data:
                raise CatalogError("{}: missing required field '{}'".format(
                    path.relative_to(root), field))
        if not isinstance(data["name"], str) or not data["name"].strip():
            raise CatalogError("{}: name must be a non-empty string".format(path.relative_to(root)))
        if data["name"] in seen_component_names:
            raise CatalogError("{}: duplicate component name '{}'".format(
                path.relative_to(root), data["name"]))
        seen_component_names.add(data["name"])
        if "local" in data and not isinstance(data["local"], bool):
            raise CatalogError("{}: local must be true or false".format(path.relative_to(root)))
        local = data.get("local", False)
        repo = data.get("repo")
        if local:
            repo = repo or CATALOG_REPO
            if repo != CATALOG_REPO:
                raise CatalogError("{}: local repo must equal '{}'".format(
                    path.relative_to(root), CATALOG_REPO))
        else:
            if repo is None:
                raise CatalogError("{}: remote component requires repo".format(path.relative_to(root)))
            if not isinstance(repo, str) or not REPO_RE.fullmatch(repo):
                raise CatalogError("{}: repo must use owner/name form".format(path.relative_to(root)))
            owner, _ = repo.split("/", 1)
            if owner != OFFICIAL_GITHUB_OWNER:
                raise CatalogError("{}: repo must be owned by {}".format(
                    path.relative_to(root), OFFICIAL_GITHUB_OWNER))
            if repo in seen_remote_repositories:
                raise CatalogError("{}: remote repository '{}' is registered more than once".format(
                    path.relative_to(root), repo))
            seen_remote_repositories.add(repo)
        ref = data.get("ref", CATALOG_REF)
        if (
                not isinstance(ref, str)
                or not REF_RE.fullmatch(ref)
                or ".." in ref
                or ref.startswith("-")
        ):
            raise CatalogError("{}: ref contains unsafe characters".format(path.relative_to(root)))
        if not isinstance(data["description"], str) or not data["description"].strip():
            raise CatalogError("{}: description must be a non-empty string".format(path.relative_to(root)))
        if not isinstance(data["skills"], list) or not data["skills"]:
            raise CatalogError("{}: skills must be a non-empty list".format(path.relative_to(root)))

        normalized_skills = []
        for index, skill in enumerate(data["skills"]):
            label = "{}: skills[{}]".format(path.relative_to(root), index)
            if not isinstance(skill, dict):
                raise CatalogError("{} must be a mapping".format(label))
            extra_skill_fields = sorted(set(skill) - ALLOWED_COMPONENT_SKILL_FIELDS)
            if extra_skill_fields:
                raise CatalogError("{}: unsupported fields: {}".format(
                    label, ", ".join(extra_skill_fields)))
            for field in ("path", "catalog_dir", "category"):
                if field not in skill:
                    raise CatalogError("{}: missing '{}'".format(label, field))
            source_path = safe_relative_path(skill["path"], "{}.path".format(label))
            catalog_dir = skill["catalog_dir"]
            if not isinstance(catalog_dir, str) or len(catalog_dir) > 64 or not SKILL_NAME_RE.fullmatch(catalog_dir):
                raise CatalogError("{}.catalog_dir must be lowercase hyphen-case and at most 64 characters".format(label))
            if catalog_dir in FORBIDDEN_GENERIC_CATALOG_DIRS:
                raise CatalogError(
                    "{}.catalog_dir '{}' is too generic; use a globally descriptive name".format(
                        label, catalog_dir))
            if local:
                expected_path = "skills/{}".format(catalog_dir)
                if source_path != expected_path:
                    raise CatalogError("{}.path must equal '{}' for a local skill".format(
                        label, expected_path))
            category = skill["category"]
            if not isinstance(category, str) or category not in ALLOWED_CATEGORIES:
                raise CatalogError("{}.category must be one of: {}".format(
                    label, ", ".join(sorted(ALLOWED_CATEGORIES))))
            if catalog_dir in seen_catalog_dirs:
                raise CatalogError("duplicate catalog_dir '{}': {} and {}".format(
                    catalog_dir, seen_catalog_dirs[catalog_dir], path.relative_to(root)))
            seen_catalog_dirs[catalog_dir] = path.relative_to(root)
            normalized_skills.append({
                "path": source_path,
                "catalog_dir": catalog_dir,
                "category": category,
            })

        normalized = dict(data)
        normalized.update({
            "repo": repo,
            "ref": ref,
            "local": local,
            "file": path,
            "skills": normalized_skills,
        })
        components.append(normalized)
    return components


def parse_frontmatter_document(path, root=ROOT):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise CatalogError("{}: document must start with an exact YAML frontmatter delimiter (---)".format(
            display_path(path, root)))
    try:
        end = next(i for i in range(1, len(lines)) if lines[i] == "---")
    except StopIteration:
        raise CatalogError("{}: YAML frontmatter is not closed".format(
            display_path(path, root)))
    try:
        frontmatter = yaml.safe_load("\n".join(lines[1:end]))
    except Exception as exc:
        raise CatalogError("{}: invalid frontmatter: {}".format(
            display_path(path, root), exc))
    if not isinstance(frontmatter, dict):
        raise CatalogError("{}: frontmatter must be a mapping".format(
            display_path(path, root)))
    body = "\n".join(lines[end + 1:]).strip()
    return frontmatter, body, text, len(lines)


def parse_skill_frontmatter(path, root=ROOT):
    frontmatter, _, text, line_count = parse_frontmatter_document(path, root)
    return frontmatter, text, line_count


def validate_skill_frontmatter(frontmatter, expected_name, rel, source_name="SKILL.md"):
    """Validate the complete Agent Skills frontmatter contract.

    This intentionally supplements the public ``skills-ref`` implementation:
    the specification requires ``metadata`` to be a string-to-string mapping,
    while the current reference parser coerces nested values to strings before
    validation and therefore cannot reject authored lists or objects.
    """
    errors = []
    location = "{}/{}".format(rel, source_name)
    extra = sorted(set(frontmatter) - ALLOWED_SKILL_FRONTMATTER_FIELDS)
    if extra:
        errors.append("{}: unsupported frontmatter fields: {}".format(
            location, ", ".join(extra)))

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name:
        errors.append("{}: name must be a non-empty string".format(location))
    else:
        if len(name) > 64 or not SKILL_NAME_RE.match(name):
            errors.append(
                "{}: name must be at most 64 characters of lowercase letters, digits, and single hyphens".format(
                    location))
        if name != expected_name:
            errors.append("{}: name must equal catalog_dir '{}'".format(
                location, expected_name))

    description = frontmatter.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("{}: description must be a non-empty string".format(location))
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        errors.append("{}: description exceeds {} characters".format(
            location, MAX_DESCRIPTION_LENGTH))
    elif "<" in description or ">" in description:
        errors.append("{}: description cannot contain angle brackets".format(location))

    if "license" in frontmatter:
        license_value = frontmatter["license"]
        if not isinstance(license_value, str) or not license_value.strip():
            errors.append("{}: license must be a non-empty string".format(location))

    if "compatibility" in frontmatter:
        compatibility = frontmatter["compatibility"]
        if not isinstance(compatibility, str) or not compatibility.strip():
            errors.append("{}: compatibility must be a non-empty string".format(location))
        elif len(compatibility) > MAX_COMPATIBILITY_LENGTH:
            errors.append("{}: compatibility exceeds {} characters".format(
                location, MAX_COMPATIBILITY_LENGTH))

    if "allowed-tools" in frontmatter:
        allowed_tools = frontmatter["allowed-tools"]
        if not isinstance(allowed_tools, str) or not allowed_tools.strip():
            errors.append("{}: allowed-tools must be a non-empty space-separated string".format(location))
        elif any(character in allowed_tools for character in "\r\n\t"):
            errors.append("{}: allowed-tools must be one space-separated line".format(location))

    if "metadata" in frontmatter:
        metadata = frontmatter["metadata"]
        if not isinstance(metadata, dict):
            errors.append("{}: metadata must be a string-to-string mapping".format(location))
        else:
            for key, value in metadata.items():
                if not isinstance(key, str) or not key.strip() or not isinstance(value, str):
                    errors.append(
                        "{}: metadata keys and values must be strings; invalid key {!r}".format(
                            location, key))
    return errors


def validate_skill_placeholders(text, rel, source_name="SKILL.md"):
    """Reject scaffold-only placeholders without policing ordinary prose."""
    lowered = text.lower()
    if "replace with" in lowered or any(
            placeholder in lowered for placeholder in SKILL_TEMPLATE_PLACEHOLDERS):
        return ["{}/{}: unresolved scaffold placeholder".format(rel, source_name)]
    return []


def validate_skill_tree(skill_dir, root=ROOT):
    """Reject non-portable or unexpectedly large published packages."""
    errors = []
    files = []
    casefolded_paths = {}
    for path in sorted(skill_dir.rglob("*")):
        rel = path.relative_to(skill_dir)
        rel_text = str(rel).replace("\\", "/")
        normalized = unicodedata.normalize("NFC", rel_text).casefold()
        previous = casefolded_paths.get(normalized)
        if previous is not None and previous != rel_text:
            errors.append("{}: path collides case-insensitively with {}".format(
                path.relative_to(root), previous))
        else:
            casefolded_paths[normalized] = rel_text

        if path.is_symlink():
            errors.append("{}: symbolic links are not allowed in published skills".format(
                path.relative_to(root)))
            continue
        if not path.is_file() and not path.is_dir():
            errors.append("{}: special files are not allowed in published skills".format(
                path.relative_to(root)))
            continue
        if any(part in FORBIDDEN_PACKAGE_PARTS for part in rel.parts):
            errors.append("{}: generated, VCS, dependency, or environment directories are not publishable".format(
                path.relative_to(root)))
        if path.is_file():
            files.append(path)
            if path.suffix == ".template":
                errors.append("{}: template scaffold file is not publishable".format(
                    path.relative_to(root)))
            if path.name in FORBIDDEN_PACKAGE_FILES or path.suffix == ".pyc":
                errors.append("{}: generated or environment file is not publishable".format(
                    path.relative_to(root)))
            size = path.stat().st_size
            if size > MAX_SKILL_FILE_BYTES:
                errors.append("{}: file exceeds the {} MiB package limit".format(
                    path.relative_to(root), MAX_SKILL_FILE_BYTES // (1024 * 1024)))

    if len(files) > MAX_SKILL_FILES:
        errors.append("{}: package contains {} files; maximum is {}".format(
            skill_dir.relative_to(root), len(files), MAX_SKILL_FILES))
    total_size = sum(path.stat().st_size for path in files)
    if total_size > MAX_SKILL_PACKAGE_BYTES:
        errors.append("{}: package is {:.2f} MiB; maximum is {} MiB".format(
            skill_dir.relative_to(root),
            total_size / float(1024 * 1024),
            MAX_SKILL_PACKAGE_BYTES // (1024 * 1024),
        ))
    return errors


def validate_skill_card(path, record, root=ROOT):
    errors = []
    rel = record["dir"].relative_to(root)
    try:
        card, body, _, _ = parse_frontmatter_document(path, root)
    except CatalogError as exc:
        return [str(exc)]

    extra = sorted(set(card) - ALLOWED_SKILL_CARD_FIELDS)
    if extra:
        errors.append("{}: unsupported frontmatter fields: {}".format(
            path.relative_to(root), ", ".join(extra)))
    if card.get("schema_version") != 1:
        errors.append("{}: schema_version must equal 1".format(path.relative_to(root)))
    if not isinstance(card.get("owner"), str) or not card["owner"].strip():
        errors.append("{}: owner must be a non-empty string".format(path.relative_to(root)))
    if not isinstance(card.get("license"), str) or not card["license"].strip():
        errors.append("{}: license must be a non-empty string".format(path.relative_to(root)))
    else:
        skill_license = record["metadata"].get("license")
        if isinstance(skill_license, str) and card["license"] != skill_license:
            errors.append("{}: license must match SKILL.md frontmatter license '{}'".format(
                path.relative_to(root), skill_license))
    if card.get("lifecycle") != "published":
        errors.append("{}: lifecycle must equal 'published'".format(path.relative_to(root)))

    source = card.get("source")
    if not isinstance(source, dict):
        errors.append("{}: source must be a mapping".format(path.relative_to(root)))
    else:
        source_extra = sorted(set(source) - ALLOWED_SKILL_CARD_SOURCE_FIELDS)
        if source_extra:
            errors.append("{}: unsupported source fields: {}".format(
                path.relative_to(root), ", ".join(source_extra)))
        expected = {
            "repo": record["component"]["repo"],
            "path": record["spec"]["path"],
        }
        for field, expected_value in expected.items():
            if source.get(field) != expected_value:
                errors.append("{}: source.{} must equal '{}'".format(
                    path.relative_to(root), field, expected_value))

    for heading in REQUIRED_SKILL_CARD_HEADINGS:
        if not re.search(r"^## {}\s*$".format(re.escape(heading)), body, re.MULTILINE):
            errors.append("{}: missing required heading '## {}'".format(
                path.relative_to(root), heading))
    if re.search(r"\b(?:TODO|TBD)\b|Replace with", body, re.IGNORECASE):
        errors.append("{}: unresolved template placeholder".format(path.relative_to(root)))
    return errors


def validate_staging(root=ROOT):
    """Keep catalog-owned candidates valid but undiscoverable by deep scans."""
    errors = []
    staging_dir = root / "staging"
    if not staging_dir.is_dir():
        return ["staging directory is required"]

    for discoverable in sorted(staging_dir.rglob("SKILL.md")):
        errors.append("{}: discoverable SKILL.md is not allowed in staging".format(
            discoverable.relative_to(root)))

    candidate_dirs = []
    for entry in sorted(staging_dir.iterdir()):
        if entry.is_symlink():
            errors.append("{}: symbolic links are not allowed in staging".format(
                entry.relative_to(root)))
        elif entry.is_dir():
            candidate_dirs.append(entry)
        elif entry.is_file() and entry.name != "README.md":
            errors.append("{}: staging root accepts only README.md and candidate directories".format(
                entry.relative_to(root)))
        elif not entry.is_file():
            errors.append("{}: special files are not allowed in staging".format(
                entry.relative_to(root)))

    for candidate_dir in candidate_dirs:
        rel = candidate_dir.relative_to(root)
        if not SKILL_NAME_RE.match(candidate_dir.name):
            errors.append("{}: candidate directory must use lowercase hyphen-case".format(rel))
        candidate_file = candidate_dir / "SKILL.md.candidate"
        if not candidate_file.is_file():
            errors.append("{}: SKILL.md.candidate is required".format(rel))
            continue
        try:
            frontmatter, _, text, line_count = parse_frontmatter_document(
                candidate_file, root)
        except CatalogError as exc:
            errors.append(str(exc))
            continue
        errors.extend(validate_skill_frontmatter(
            frontmatter, candidate_dir.name, rel, "SKILL.md.candidate"))
        errors.extend(validate_skill_placeholders(
            text, rel, "SKILL.md.candidate"))
        if line_count > MAX_SKILL_LINES:
            errors.append("{}/SKILL.md.candidate: {} lines; keep it at or below {}".format(
                rel, line_count, MAX_SKILL_LINES))
        errors.extend(validate_skill_tree(candidate_dir, root))
    return errors


def registered_skills(components, root=ROOT):
    records = []
    for component in components:
        for spec in component["skills"]:
            skill_dir = root / "skills" / spec["catalog_dir"]
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                raise CatalogError("{}: registered skill is missing SKILL.md".format(
                    skill_dir.relative_to(root)))
            metadata, text, line_count = parse_skill_frontmatter(skill_file, root)
            records.append({
                "component": component,
                "spec": spec,
                "dir": skill_dir,
                "metadata": metadata,
                "text": text,
                "line_count": line_count,
            })
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
    lock_extra = sorted(set(lock) - {"schema_version", "skills"})
    if lock_extra:
        errors.append(".skillhub-lock.json: unsupported fields: {}".format(
            ", ".join(lock_extra)))
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
        entry_extra = sorted(set(entry) - {
            "repo", "ref", "commit", "path", "content_digest",
        })
        if entry_extra:
            errors.append(".skillhub-lock.json: skill '{}': unsupported fields: {}".format(
                name, ", ".join(entry_extra)))
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
        if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
            errors.append(".skillhub-lock.json: skill '{}'.commit must be a 40-character lowercase Git commit".format(name))
        content_digest = entry.get("content_digest")
        if not isinstance(content_digest, str) or not DIGEST_RE.fullmatch(content_digest):
            errors.append(".skillhub-lock.json: skill '{}'.content_digest must be a lowercase SHA-256 digest".format(name))
        else:
            record = record_by_name.get(name)
            if record and file_tree_digest(record["dir"]) != content_digest:
                errors.append(".skillhub-lock.json: skill '{}'.content_digest does not match the published tree".format(name))
    return errors


def validate_admission_exceptions(components, root=ROOT):
    errors = []
    path = root / "admission-exceptions.yml"
    if not path.is_file():
        return ["admission-exceptions.yml is required"]
    try:
        data = load_yaml(path, root)
    except CatalogError as exc:
        return [str(exc)]
    extra = sorted(set(data) - {"schema_version", "exceptions"})
    if extra:
        errors.append("admission-exceptions.yml: unsupported fields: {}".format(
            ", ".join(extra)))
    if data.get("schema_version") != 1:
        errors.append("admission-exceptions.yml: schema_version must equal 1")
    exceptions = data.get("exceptions")
    if not isinstance(exceptions, list):
        return errors + ["admission-exceptions.yml: exceptions must be a list"]

    registered_sources = {
        (component["repo"], spec["path"])
        for component in components
        for spec in component["skills"]
    }
    seen = set()
    for index, exception in enumerate(exceptions):
        label = "admission-exceptions.yml: exceptions[{}]".format(index)
        if not isinstance(exception, dict):
            errors.append("{} must be a mapping".format(label))
            continue
        extra_fields = sorted(set(exception) - ALLOWED_EXCEPTION_FIELDS)
        if extra_fields:
            errors.append("{}: unsupported fields: {}".format(
                label, ", ".join(extra_fields)))
        repo = exception.get("repo")
        if not isinstance(repo, str) or not REPO_RE.fullmatch(repo) or not repo.startswith(OFFICIAL_GITHUB_OWNER + "/"):
            errors.append("{}: repo must use HYGON-AI/name form".format(label))
        try:
            source_path = safe_relative_path(
                exception.get("path"), "{}.path".format(label))
        except CatalogError as exc:
            errors.append(str(exc))
            source_path = None
        reasons = exception.get("reasons")
        if not isinstance(reasons, list) or not reasons or not all(
                isinstance(reason, str) and reason.strip() for reason in reasons):
            errors.append("{}: reasons must be a non-empty list of non-empty strings".format(label))
        identity = (repo, source_path)
        if source_path is not None:
            if identity in seen:
                errors.append("{}: duplicate exception for {}:{}".format(
                    label, repo, source_path))
            seen.add(identity)
            if identity in registered_sources:
                errors.append("{}: an excepted candidate cannot also be registered for publication".format(label))
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


def validate_eval_dataset(path, root=ROOT, expected_skill=None):
    errors = []
    try:
        value = load_json(path, root)
    except CatalogError as exc:
        return [str(exc)]
    allowed_top_level = {"schema_version", "skill", "evaluations"}
    extra_top_level = sorted(set(value) - allowed_top_level)
    if extra_top_level:
        errors.append("{}: unsupported top-level fields: {}".format(
            path.relative_to(root), ", ".join(extra_top_level)))
    if value.get("schema_version") != 1:
        errors.append("{}: schema_version must equal 1".format(path.relative_to(root)))
    if expected_skill is not None and value.get("skill") != expected_skill:
        errors.append("{}: skill must equal '{}'".format(
            path.relative_to(root), expected_skill))
    elif expected_skill is None and (
            not isinstance(value.get("skill"), str) or not value["skill"].strip()):
        errors.append("{}: skill must be a non-empty string".format(path.relative_to(root)))
    evaluations = value.get("evaluations")
    if not isinstance(evaluations, list) or not evaluations:
        return errors + ["{}: evaluations must be a non-empty list".format(path.relative_to(root))]

    seen_ids = set()
    seen_prompts = set()
    positives = 0
    negatives = 0
    behavior_cases = 0
    for index, case in enumerate(evaluations):
        label = "{}: evaluations[{}]".format(path.relative_to(root), index)
        if not isinstance(case, dict):
            errors.append("{} must be an object".format(label))
            continue
        extra_case_fields = sorted(set(case) - ALLOWED_EVAL_FIELDS)
        if extra_case_fields:
            errors.append("{}: unsupported fields: {}".format(
                label, ", ".join(extra_case_fields)))
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append("{}: id must be a non-empty string".format(label))
        elif not EVAL_ID_RE.match(case_id):
            errors.append("{}: id must use lowercase hyphen-case".format(label))
        elif case_id in seen_ids:
            errors.append("{}: duplicate id '{}'".format(label, case_id))
        else:
            seen_ids.add(case_id)
        prompt = case.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            errors.append("{}: prompt must be a non-empty string".format(label))
        elif prompt.strip() in seen_prompts:
            errors.append("{}: duplicate prompt".format(label))
        else:
            seen_prompts.add(prompt.strip())
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
    errors.extend(validate_admission_exceptions(components, root))
    errors.extend(validate_staging(root))

    for record in records:
        rel = record["dir"].relative_to(root)
        frontmatter = record["metadata"]
        errors.extend(validate_skill_frontmatter(
            frontmatter, record["spec"]["catalog_dir"], rel))
        errors.extend(validate_skill_placeholders(record["text"], rel))
        if record["line_count"] > MAX_SKILL_LINES:
            errors.append("{}/SKILL.md: {} lines; keep it at or below {}".format(
                rel, record["line_count"], MAX_SKILL_LINES))

        errors.extend(validate_skill_tree(record["dir"], root))

        nested_skill_files = [
            path for path in record["dir"].rglob("SKILL.md")
            if path != record["dir"] / "SKILL.md"
        ]
        for path in nested_skill_files:
            errors.append("{}: nested SKILL.md is not allowed in the flat published catalog".format(
                path.relative_to(root)))

        for path in record["dir"].rglob("*"):
            if path.is_file() and path.stat().st_size <= MAX_SKILL_FILE_BYTES:
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
        else:
            errors.extend(validate_skill_card(skill_card, record, root))

        license_file = record["dir"] / "LICENSE"
        if not license_file.is_file() or license_file.stat().st_size == 0:
            errors.append("{}: a non-empty LICENSE file is required in every published package".format(rel))

        eval_file = record["dir"] / "evals" / "evals.json"
        if not eval_file.is_file():
            errors.append("{}: evals/evals.json is required for published skills".format(rel))
        else:
            errors.extend(validate_eval_dataset(
                eval_file, root, record["spec"]["catalog_dir"]))

        openai_yaml = record["dir"] / "agents" / "openai.yaml"
        if openai_yaml.exists():
            try:
                interface = load_yaml(openai_yaml, root).get("interface", {})
                if not isinstance(interface, dict):
                    errors.append("{}: interface must be a mapping".format(
                        openai_yaml.relative_to(root)))
                    interface = {}
                for field in ("display_name", "short_description", "default_prompt"):
                    if not isinstance(interface.get(field), str) or not interface[field].strip():
                        errors.append("{}: interface.{} must be a non-empty string".format(openai_yaml.relative_to(root), field))
                lengths = {
                    "display_name": 64,
                    "short_description": 100,
                    "default_prompt": 1024,
                }
                for field, limit in lengths.items():
                    if isinstance(interface.get(field), str) and len(interface[field]) > limit:
                        errors.append("{}: interface.{} exceeds {} characters".format(
                            openai_yaml.relative_to(root), field, limit))
                expected_invocation = "$" + record["spec"]["catalog_dir"]
                if isinstance(interface.get("default_prompt"), str) and expected_invocation not in interface["default_prompt"]:
                    errors.append("{}: interface.default_prompt must mention '{}'".format(
                        openai_yaml.relative_to(root), expected_invocation))
            except CatalogError as exc:
                errors.append(str(exc))
        else:
            warnings.append("{}: agents/openai.yaml is recommended".format(rel))

    return errors, warnings, components, records


def dump_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
