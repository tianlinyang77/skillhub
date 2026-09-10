#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
"""Shared primitives for safe Git commit identity history rewrites."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


MIN_GIT_VERSION = (2, 36, 0)
FILTER_REPO_VERSION = "v2.47.0"
FILTER_REPO_SHA256 = (
    "67447413e273fc76809289111748870b6f6072f08b17efe94863a92d810b7d94"
)
ZERO_SHA = "0" * 40
FORBIDDEN_DOMAINS = {b"sugon.com", b"rogon.com", b"rogon.cn"}
TRIM_EMAIL_BYTES = b" \t\r\n\xe2\x80\x9c\xe2\x80\x9d\"'"
FORBIDDEN_TOKEN = re.compile(rb"(?:sugon|rogon)", re.IGNORECASE)
IDENTITY = re.compile(rb"^(.*) <([^<>]*)> ([0-9]+ [+-][0-9]{4})$")
ALLOWED_EXACT_FIELDS = {
    "author_name",
    "author_email",
    "committer_name",
    "committer_email",
    "message",
}


class SafetyError(RuntimeError):
    """Raised when a safety invariant is not satisfied."""


@dataclass(frozen=True)
class IdentityValue:
    name: bytes
    email: bytes
    timestamp: bytes


@dataclass(frozen=True)
class ExactChange:
    commit: str
    field: str
    old: bytes
    new: bytes


def run(
    command: Sequence[str],
    *,
    input_bytes: Optional[bytes] = None,
    cwd: Optional[Path] = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    process = subprocess.run(
        list(command),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )
    if check and process.returncode != 0:
        stderr = process.stderr.decode("utf-8", "replace").strip()
        raise SafetyError(
            "command failed with exit code "
            f"{process.returncode}: {' '.join(command)}"
            + (f"\n{stderr}" if stderr else "")
        )
    return process


def git(
    git_bin: str,
    repo: Path,
    *args: str,
    input_bytes: Optional[bytes] = None,
    check: bool = True,
) -> bytes:
    return run(
        [git_bin, "-C", str(repo), *args],
        input_bytes=input_bytes,
        check=check,
    ).stdout


def git_version(git_bin: str) -> Tuple[int, int, int]:
    output = run([git_bin, "--version"]).stdout.decode("ascii", "replace").strip()
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", output)
    if not match:
        raise SafetyError(f"cannot parse Git version: {output}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def require_git_version(git_bin: str) -> str:
    version = git_version(git_bin)
    if version < MIN_GIT_VERSION:
        minimum = ".".join(str(part) for part in MIN_GIT_VERSION)
        actual = ".".join(str(part) for part in version)
        raise SafetyError(
            f"Git {minimum} or newer is required; selected Git is {actual}"
        )
    return ".".join(str(part) for part in version)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> str:
    data = canonical_json_bytes(value)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SafetyError(f"cannot read valid JSON from {path}: {exc}") from exc


def b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def unb64(value: str, *, label: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise SafetyError(f"{label} is not valid base64") from exc


def display_bytes(value: bytes, limit: int = 240) -> str:
    text = value.decode("utf-8", "backslashreplace")
    text = text.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def parse_commit(raw: bytes) -> Tuple[List[Tuple[bytes, bytes]], bytes]:
    header_bytes, separator, message = raw.partition(b"\n\n")
    if not separator:
        raise SafetyError("commit object does not contain a header separator")
    headers: List[Tuple[bytes, bytes]] = []
    for line in header_bytes.splitlines():
        if line.startswith(b" "):
            if not headers:
                raise SafetyError("orphan commit-header continuation")
            key, value = headers[-1]
            headers[-1] = (key, value + b"\n" + line)
            continue
        key, space, value = line.partition(b" ")
        if not space:
            raise SafetyError(f"malformed commit header: {line!r}")
        headers.append((key, value))
    return headers, message


def header_values(
    headers: Sequence[Tuple[bytes, bytes]], key: bytes
) -> List[bytes]:
    return [value for candidate, value in headers if candidate == key]


def parse_identity(value: bytes) -> IdentityValue:
    match = IDENTITY.match(value)
    if not match:
        raise SafetyError(f"cannot parse commit identity header: {value!r}")
    name, email, timestamp = match.groups()
    return IdentityValue(name=name, email=email, timestamp=timestamp)


def render_identity(identity: IdentityValue) -> bytes:
    return (
        identity.name
        + b" <"
        + identity.email
        + b"> "
        + identity.timestamp
    )


def batch_commits(
    git_bin: str, repo: Path, commits: Iterable[str]
) -> Dict[str, bytes]:
    ordered = sorted(set(commits))
    if not ordered:
        return {}
    process = subprocess.Popen(
        [git_bin, "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output, stderr = process.communicate(
        input="".join(f"{commit}\n" for commit in ordered).encode("ascii")
    )
    if process.returncode != 0:
        raise SafetyError(
            "git cat-file --batch failed: "
            + stderr.decode("utf-8", "replace").strip()
        )
    stream = io.BytesIO(output)
    bodies: Dict[str, bytes] = {}
    for commit in ordered:
        header = stream.readline().decode("ascii").rstrip("\n")
        parts = header.split()
        if len(parts) != 3:
            raise SafetyError(f"unexpected cat-file response: {header}")
        object_id, object_type, size_text = parts
        if object_id != commit or object_type != "commit":
            raise SafetyError(f"unexpected cat-file response: {header}")
        body = stream.read(int(size_text))
        if stream.read(1) != b"\n":
            raise SafetyError(f"missing cat-file record separator for {commit}")
        bodies[commit] = body
    if stream.read():
        raise SafetyError("unexpected trailing git cat-file output")
    return bodies


def commits_for_ref(git_bin: str, repo: Path, ref: str) -> List[str]:
    output = git(git_bin, repo, "rev-list", "--reverse", "--topo-order", ref)
    return output.decode("ascii").splitlines()


def signed_commits(
    bodies: Mapping[str, bytes],
) -> Set[str]:
    signed: Set[str] = set()
    for commit, body in bodies.items():
        headers, _ = parse_commit(body)
        if any(key.startswith(b"gpgsig") for key, _ in headers):
            signed.add(commit)
    return signed


def supported_email_mapping(email: bytes) -> Optional[bytes]:
    clean = email.strip(TRIM_EMAIL_BYTES)
    local, separator, domain = clean.rpartition(b"@")
    if not separator or not local or domain.lower() not in FORBIDDEN_DOMAINS:
        return None
    return local + b"@hygon.com"


def contains_forbidden(value: bytes) -> bool:
    return FORBIDDEN_TOKEN.search(value) is not None


def validate_ref(git_bin: str, ref: str, *, heads_only: bool = False) -> None:
    if heads_only and not ref.startswith("refs/heads/"):
        raise SafetyError(f"expected a refs/heads/* ref, got {ref}")
    process = run(
        [git_bin, "check-ref-format", ref],
        check=False,
    )
    if process.returncode != 0:
        raise SafetyError(f"invalid Git ref: {ref}")


def ensure_bare_mirror(git_bin: str, repo: Path) -> None:
    if not repo.is_dir():
        raise SafetyError(f"repository does not exist: {repo}")
    bare = git(git_bin, repo, "rev-parse", "--is-bare-repository").strip()
    if bare != b"true":
        raise SafetyError(f"history rewrite repository must be bare: {repo}")
    mirror = git(
        git_bin,
        repo,
        "config",
        "--bool",
        "--get",
        "remote.origin.mirror",
        check=False,
    ).strip()
    if mirror != b"true":
        raise SafetyError(f"repository is not a mirror clone: {repo}")


def load_email_map(path: Path) -> Dict[bytes, bytes]:
    document = read_json(path)
    if not isinstance(document, dict) or document.get("version") != 1:
        raise SafetyError(f"unsupported email mapping format: {path}")
    raw_changes = document.get("changes")
    if not isinstance(raw_changes, list):
        raise SafetyError(f"email mapping changes must be a list: {path}")
    result: Dict[bytes, bytes] = {}
    for index, entry in enumerate(raw_changes):
        label = f"{path}: changes[{index}]"
        if not isinstance(entry, dict):
            raise SafetyError(f"{label} must be an object")
        old = unb64(str(entry.get("old_b64", "")), label=f"{label}.old_b64")
        new = unb64(str(entry.get("new_b64", "")), label=f"{label}.new_b64")
        if old in result:
            raise SafetyError(f"{label} duplicates an old email value")
        if supported_email_mapping(old) != new:
            raise SafetyError(
                f"{label} is not the exact approved-domain mapping "
                "<same local part>@hygon.com"
            )
        if contains_forbidden(new):
            raise SafetyError(f"{label} leaves a forbidden token in the new email")
        result[old] = new
    return result


def load_exact_changes(path: Optional[Path]) -> List[ExactChange]:
    if path is None:
        return []
    document = read_json(path)
    if not isinstance(document, dict) or document.get("version") != 1:
        raise SafetyError(f"unsupported exact-change format: {path}")
    raw_changes = document.get("changes")
    if not isinstance(raw_changes, list):
        raise SafetyError(f"exact changes must be a list: {path}")
    result: List[ExactChange] = []
    seen: Set[Tuple[str, str]] = set()
    for index, entry in enumerate(raw_changes):
        label = f"{path}: changes[{index}]"
        if not isinstance(entry, dict):
            raise SafetyError(f"{label} must be an object")
        commit = str(entry.get("commit", ""))
        field = str(entry.get("field", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise SafetyError(f"{label}.commit must be a full lowercase SHA-1")
        if field not in ALLOWED_EXACT_FIELDS:
            raise SafetyError(f"{label}.field is unsupported: {field}")
        old = unb64(str(entry.get("old_b64", "")), label=f"{label}.old_b64")
        new_raw = entry.get("new_b64")
        if new_raw is None:
            raise SafetyError(f"{label}.new_b64 is unresolved")
        new = unb64(str(new_raw), label=f"{label}.new_b64")
        key = (commit, field)
        if key in seen:
            raise SafetyError(f"{label} duplicates {commit}:{field}")
        if old == new:
            raise SafetyError(f"{label} does not change the field")
        if contains_forbidden(new):
            raise SafetyError(f"{label} leaves a forbidden token in the new value")
        seen.add(key)
        result.append(ExactChange(commit=commit, field=field, old=old, new=new))
    return result


def exact_change_map(
    changes: Iterable[ExactChange],
) -> Dict[Tuple[str, str], ExactChange]:
    return {(change.commit, change.field): change for change in changes}


def commit_fields(raw: bytes) -> Dict[str, bytes]:
    headers, message = parse_commit(raw)
    authors = header_values(headers, b"author")
    committers = header_values(headers, b"committer")
    if len(authors) != 1 or len(committers) != 1:
        raise SafetyError("commit must contain exactly one author and committer")
    author = parse_identity(authors[0])
    committer = parse_identity(committers[0])
    return {
        "author_name": author.name,
        "author_email": author.email,
        "committer_name": committer.name,
        "committer_email": committer.email,
        "message": message,
    }


def parent_map(
    bodies: Mapping[str, bytes],
) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for commit, body in bodies.items():
        headers, _ = parse_commit(body)
        result[commit] = [
            value.decode("ascii") for value in header_values(headers, b"parent")
        ]
    return result


def affected_descendants(
    ordered_commits: Sequence[str],
    parents: Mapping[str, Sequence[str]],
    directly_changed: Set[str],
) -> Set[str]:
    affected: Set[str] = set()
    for commit in ordered_commits:
        if commit in directly_changed or any(
            parent in affected for parent in parents.get(commit, [])
        ):
            affected.add(commit)
    return affected


def load_commit_map(path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        if not line.strip():
            continue
        if number == 1 and line.startswith("old"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise SafetyError(f"malformed commit-map line {number}: {line}")
        old, new = parts
        if new == ZERO_SHA:
            raise SafetyError(f"commit unexpectedly removed: {old}")
        if old != new:
            mapping[old] = new
    return mapping


def require_hash(path: Path, approved_sha256: str, *, label: str) -> str:
    actual = sha256_file(path)
    if not re.fullmatch(r"[0-9a-f]{64}", approved_sha256):
        raise SafetyError(f"{label} approval must be a lowercase SHA-256")
    if actual != approved_sha256:
        raise SafetyError(
            f"{label} hash does not match approval: actual={actual}, "
            f"approved={approved_sha256}"
        )
    return actual


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(data)
    temporary.replace(path)
