#!/usr/bin/env python3
# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: LicenseRef-HYGON-Internal
"""Thin Skill adapter for the shared governance engine."""

import os
import sys
from pathlib import Path


def _engine_root() -> Path:
    configured = os.environ.get("HYGON_GOVERNANCE_ROOT")
    legacy_configured = os.environ.get("HYGON_OPEN_SOURCE_GOVERNANCE_ROOT")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    if legacy_configured:
        candidates.append(Path(legacy_configured))
    candidates.append(Path(__file__).resolve().parents[3])
    for root in candidates:
        if (root / "src/hygon_compliance/cli.py").is_file():
            return root
    raise RuntimeError(
        "shared governance engine not found; install the Skill from the governance "
        "checkout or set HYGON_GOVERNANCE_ROOT"
    )


def _activate_project_venv(root: Path) -> None:
    venv = root / ".venv"
    python = venv / "bin" / "python"
    if not python.is_file() or os.environ.get("HYGON_GOVERNANCE_VENV_ACTIVE") == "1":
        return
    if Path(sys.prefix).resolve() == venv.resolve():
        return
    environment = os.environ.copy()
    environment["HYGON_GOVERNANCE_VENV_ACTIVE"] = "1"
    os.execve(
        str(python),
        [str(python), str(Path(__file__).resolve())] + sys.argv[1:],
        environment,
    )


def _configure_runtime(root: Path) -> None:
    os.environ.setdefault("HYGON_GOVERNANCE_ROOT", str(root))
    runtime = root / "runtime"
    if "HYGON_GOVERNANCE_HOME" not in os.environ and runtime.is_symlink():
        os.environ["HYGON_GOVERNANCE_HOME"] = str(runtime.resolve())


def main() -> int:
    root = _engine_root()
    _configure_runtime(root)
    _activate_project_venv(root)
    sys.path.insert(0, str(root / "src"))
    from hygon_compliance.cli import main as governance_main

    return governance_main(["full-audit"] + sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
