# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

from scripts.new_skill import (
    TEMPLATE_ROOT,
    ScaffoldConfig,
    ScaffoldError,
    config_from_args,
    create_scaffold,
    license_mismatch_warning,
    parse_args,
)
from scripts.skillhub import validate_markdown_links


class NewSkillTests(unittest.TestCase):
    def create(self, config):
        with redirect_stdout(io.StringIO()):
            return create_scaffold(config, TEMPLATE_ROOT)

    def make_roots(self, temp):
        root = Path(temp)
        source_root = root / "quality-gate"
        catalog_root = root / "skillhub"
        source_root.mkdir()
        (catalog_root / "components.d").mkdir(parents=True)
        (source_root / "LICENSE").write_text(
            "Apache License\nVersion 2.0\n", encoding="utf-8"
        )
        return source_root, catalog_root

    def make_config(self, source_root, catalog_root, **overrides):
        values = {
            "name": "quality-gate-audit",
            "repo": "HYGON-AI/quality-gate",
            "ref": "main",
            "owner": "Quality Gate Team",
            "description": "Audit a repository when publication readiness must be verified.",
            "license_id": "Apache-2.0",
            "category": "Governance and Compliance",
            "component": "quality-gate",
            "product_name": "Quality Gate",
            "product_description": "Repository publication and compliance gates.",
            "source_root": source_root,
            "catalog_root": catalog_root,
            "license_file": source_root / "LICENSE",
            "with_openai": True,
            "with_references": True,
        }
        values.update(overrides)
        return ScaffoldConfig(**values)

    def test_creates_named_scaffold_license_and_component(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            config = self.make_config(source_root, catalog_root)

            self.create(config)

            skill_dir = source_root / "skills" / "quality-gate-audit"
            expected = {
                "SKILL.md",
                "skill-card.md",
                "evals/evals.json",
                "agents/openai.yaml",
                "references/details.md",
                "LICENSE",
            }
            actual = {
                str(path.relative_to(skill_dir)).replace("\\", "/")
                for path in skill_dir.rglob("*")
                if path.is_file()
            }
            self.assertEqual(actual, expected)
            self.assertEqual(
                (skill_dir / "LICENSE").read_text(encoding="utf-8"),
                "Apache License\nVersion 2.0\n",
            )
            self.assertFalse(
                any(path.suffix == ".template" for path in skill_dir.rglob("*"))
            )
            self.assertFalse((skill_dir / "README.md").exists())
            skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(
                "[Detailed workflow](references/details.md)", skill_text
            )
            self.assertEqual(validate_markdown_links(skill_dir, source_root), [])

            authored = "\n".join(
                path.read_text(encoding="utf-8")
                for path in skill_dir.rglob("*")
                if path.is_file() and path.name != "LICENSE"
            )
            self.assertNotIn("Replace with", authored)
            self.assertNotIn("replace-with", authored)
            self.assertIn("name: quality-gate-audit", authored)
            self.assertIn("lifecycle: staging", authored)
            self.assertIn("$quality-gate-audit", authored)

            component = yaml.safe_load(
                (catalog_root / "components.d" / "quality-gate.yml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(component["repo"], "HYGON-AI/quality-gate")
            self.assertEqual(component["ref"], "main")
            self.assertEqual(
                component["skills"],
                [
                    {
                        "path": "skills/quality-gate-audit",
                        "catalog_dir": "quality-gate-audit",
                        "category": "Governance and Compliance",
                    }
                ],
            )

    def test_omits_reference_link_when_reference_scaffold_is_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            config = self.make_config(
                source_root, catalog_root, with_references=False
            )

            self.create(config)

            skill_dir = source_root / "skills" / config.name
            skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            self.assertFalse((skill_dir / "references").exists())
            self.assertNotIn("references/details.md", skill_text)
            self.assertNotIn("optional References section", skill_text)

    def test_warns_for_obvious_license_mismatch_without_blocking(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            config = self.make_config(
                source_root, catalog_root, license_id="MIT"
            )
            output = io.StringIO()

            with redirect_stdout(output):
                create_scaffold(config, TEMPLATE_ROOT)

            self.assertIn("WARNING:", output.getvalue())
            self.assertIn("looks like Apache-2.0", output.getvalue())
            self.assertTrue(config.destination.is_dir())

    def test_license_warning_accepts_matching_or_composite_declaration(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, _ = self.make_roots(temp)
            license_file = source_root / "LICENSE"

            self.assertIsNone(
                license_mismatch_warning("Apache-2.0", license_file)
            )
            self.assertIsNone(
                license_mismatch_warning("MIT OR Apache-2.0", license_file)
            )
            license_file.write_text("Custom reviewed terms\n", encoding="utf-8")
            self.assertIsNone(license_mismatch_warning("LicenseRef-Custom", license_file))

    def test_copies_existing_notice_automatically(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            notice = source_root / "NOTICE"
            notice.write_text("Required attribution\n", encoding="utf-8")
            config = self.make_config(source_root, catalog_root, notice_file=notice)

            self.create(config)

            copied = source_root / "skills" / config.name / "NOTICE"
            self.assertEqual(
                copied.read_text(encoding="utf-8"), "Required attribution\n"
            )

    def test_appends_without_reformatting_existing_component(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            component_path = catalog_root / "components.d" / "quality-gate.yml"
            component_path.write_text(
                "# Product-owned registry\n"
                "name: Quality Gate\n"
                "repo: HYGON-AI/quality-gate\n"
                "ref: main\n"
                "description: Existing description.\n"
                "skills:\n"
                "  - path: skills/existing-skill\n"
                "    catalog_dir: existing-skill\n"
                "    category: Developer Tools\n"
                "local: false\n",
                encoding="utf-8",
            )
            config = self.make_config(source_root, catalog_root)

            self.create(config)

            text = component_path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("# Product-owned registry\n"))
            self.assertEqual(text.count("catalog_dir:"), 2)
            self.assertIn('catalog_dir: "quality-gate-audit"', text)
            self.assertLess(
                text.index('catalog_dir: "quality-gate-audit"'),
                text.index("local: false"),
            )

    def test_refuses_existing_destination_without_changing_component(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            config = self.make_config(source_root, catalog_root)
            destination = source_root / "skills" / config.name
            destination.mkdir(parents=True)
            marker = destination / "owned.txt"
            marker.write_text("preserve\n", encoding="utf-8")

            with self.assertRaisesRegex(ScaffoldError, "refusing to overwrite"):
                self.create(config)

            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve\n")
            self.assertFalse(
                (catalog_root / "components.d" / "quality-gate.yml").exists()
            )

    def test_rolls_back_source_directory_when_component_write_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            config = self.make_config(source_root, catalog_root)

            with (
                mock.patch(
                    "scripts.new_skill.write_text_atomic",
                    side_effect=OSError("simulated component write failure"),
                ),
                self.assertRaisesRegex(OSError, "simulated component"),
            ):
                self.create(config)

            self.assertFalse(config.destination.exists())
            self.assertFalse(
                (catalog_root / "components.d" / "quality-gate.yml").exists()
            )

    def test_rejects_unknown_category_and_third_party_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            with self.assertRaisesRegex(ScaffoldError, "category must be one of"):
                self.create(
                    self.make_config(source_root, catalog_root, category="Made Up"),
                )
            with self.assertRaisesRegex(ScaffoldError, "repo must be owned"):
                self.create(
                    self.make_config(
                        source_root, catalog_root, repo="third-party/example"
                    ),
                )

    def test_dry_run_does_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            config = self.make_config(source_root, catalog_root, dry_run=True)

            self.create(config)

            self.assertFalse(config.destination.exists())
            self.assertFalse(
                (catalog_root / "components.d" / "quality-gate.yml").exists()
            )

    def test_cli_configuration_detects_root_license_and_notice(self):
        with tempfile.TemporaryDirectory() as temp:
            source_root, catalog_root = self.make_roots(temp)
            notice = source_root / "NOTICE.txt"
            notice.write_text("Attribution\n", encoding="utf-8")
            args = parse_args(
                [
                    "quality-gate-audit",
                    "--source-root",
                    str(source_root),
                    "--catalog-root",
                    str(catalog_root),
                    "--repo",
                    "HYGON-AI/quality-gate",
                    "--owner",
                    "Quality Gate Team",
                    "--description",
                    "Audit repositories when release evidence is required.",
                    "--license",
                    "Apache-2.0",
                    "--category",
                    "Governance and Compliance",
                ]
            )

            config = config_from_args(args)

            self.assertEqual(config.license_file, (source_root / "LICENSE").resolve())
            self.assertEqual(config.notice_file, notice.resolve())
            self.assertEqual(config.component, "quality-gate")


if __name__ == "__main__":
    unittest.main()
