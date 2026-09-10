# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import yaml

from scripts import contribute
from scripts.new_skill import TEMPLATE_ROOT


class ContributionTests(unittest.TestCase):
    def invoke(self, argv, root=contribute.ROOT):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = contribute.main(argv, root=root)
        return result, output.getvalue()

    def fixture(self, directory):
        root = Path(directory) / "catalog"
        (root / "components.d").mkdir(parents=True)
        (root / "staging").mkdir()
        shutil.copytree(TEMPLATE_ROOT, root / "templates" / "skill")
        (root / "LICENSE").write_text("Apache License\nVersion 2.0\n", encoding="utf-8")
        (root / "NOTICE").write_text("Original attribution\n", encoding="utf-8")
        (root / ".skillhub-lock.json").write_text('{"schema_version": 1, "skills": {}}\n', encoding="utf-8")
        (root / "admission-exceptions.yml").write_text("schema_version: 1\nexceptions: []\n", encoding="utf-8")
        return root

    def source_skill(self, directory, *, with_license=True, source_only=False):
        source = Path(directory) / "source-skill"
        (source / "references").mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\n"
            "name: imported-example\n"
            "description: Analyze example logs when an example workflow needs diagnosis.\n"
            "license: Apache-2.0\n"
            "metadata:\n"
            "  author: External Team\n"
            + ("produces:\n  - profiling report\n" if source_only else "")
            + "---\n\n"
            + "# Imported Example\n\n"
            + "Use the included reference when the logs require detailed interpretation.\n",
            encoding="utf-8",
        )
        (source / "references" / "details.md").write_bytes(b"source resource\n")
        if with_license:
            (source / "LICENSE").write_text("Apache License\nVersion 2.0\n", encoding="utf-8")
        return source

    @staticmethod
    def snapshot(root):
        root = Path(root)
        return {
            path.relative_to(root): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }

    def test_new_prompts_for_metadata_and_registers_a_local_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            answers = [
                "Tool Team",
                "Analyze tool logs when an operator needs a diagnosis.",
                "Developer Tools",
                "Python 3.11; read logs and write reports.",
            ]
            with mock.patch("builtins.input", side_effect=answers):
                code, output = self.invoke(["new", "tool-log-analysis"], root)
            self.assertEqual(code, 0, output)
            card = (root / "skills" / "tool-log-analysis" / "skill-card.md").read_text(encoding="utf-8")
            self.assertIn("lifecycle: published", card)
            self.assertIn("Python 3.11; read logs and write reports.", card)
            self.assertNotIn("## Validation", card)
            self.assertNotIn("TODO", card)
            self.assertIn("Apache-2.0", card)
            self.assertFalse((root / "skills" / "tool-log-analysis" / "LICENSE").exists())
            self.assertTrue((root / "skills" / "tool-log-analysis" / "NOTICE").exists())
            registry = yaml.safe_load((root / "components.d" / "skillhub.yml").read_text(encoding="utf-8"))
            self.assertTrue(registry["local"])
            self.assertIn("contribute.py check tool-log-analysis", output)

    def test_new_noninteractive_requires_all_author_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            before = self.snapshot(root)
            code, output = self.invoke(["new", "tool-log-analysis", "--non-interactive"], root)
            self.assertEqual(code, 1)
            self.assertIn("--owner", output)
            self.assertEqual(before, self.snapshot(root))

    def test_import_copies_resources_without_modifying_the_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            before = self.snapshot(source)
            code, output = self.invoke(
                ["import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive"], root,
            )
            self.assertEqual(code, 0, output)
            self.assertEqual(before, self.snapshot(source))
            destination = root / "skills" / "imported-example"
            self.assertEqual(
                (destination / "references" / "details.md").read_bytes(),
                b"source resource\n",
            )
            card = (destination / "skill-card.md").read_text(encoding="utf-8")
            self.assertIn("lifecycle: published", card)
            self.assertNotIn("## Validation", card)
            self.assertNotIn("TODO", card)
            self.assertIn("Local catalog import", card)
            self.assertIn("owner: Catalog Team", card)
            registry = yaml.safe_load((root / "components.d" / "skillhub.yml").read_text(encoding="utf-8"))
            self.assertEqual(registry["skills"][0]["catalog_dir"], "imported-example")

    def test_import_prompts_for_catalog_maintainer_despite_source_author(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            with mock.patch("builtins.input", side_effect=["Catalog Team", "see SKILL.md"]) as prompted:
                code, output = self.invoke(
                    ["import", str(source), "--category", "Developer Tools"], root,
                )
            self.assertEqual(code, 0, output)
            self.assertEqual(prompted.call_args_list[0].args[0], "Maintaining team: ")
            card = (root / "skills" / "imported-example" / "skill-card.md").read_text(encoding="utf-8")
            self.assertIn("owner: Catalog Team", card)
            skill = (root / "skills" / "imported-example" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("author: External Team", skill)

    def test_import_noninteractive_requires_catalog_maintainer_despite_source_author(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            before = self.snapshot(root)
            code, output = self.invoke(
                ["import", str(source), "--category", "Developer Tools", "--non-interactive"], root,
            )
            self.assertEqual(code, 1)
            self.assertIn("Missing --owner", output)
            self.assertEqual(before, self.snapshot(root))

    def test_import_translates_source_only_frontmatter_without_changing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary, source_only=True)
            before = self.snapshot(source)
            code, output = self.invoke(
                ["import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive"], root,
            )
            self.assertEqual(code, 0, output)
            self.assertEqual(before, self.snapshot(source))
            document = (root / "skills" / "imported-example" / "SKILL.md").read_text(encoding="utf-8")
            header = document.split("---", 2)[1]
            self.assertNotIn("produces", header)
            self.assertIn("## Imported source metadata", document)
            self.assertIn("produces:", document)
            self.assertIn("translated non-portable", output)

    def test_import_records_runtime_option_without_placeholders(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            code, output = self.invoke([
                "import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive",
                "--runtime-permissions", "HCU and hipprof; read traces and write reports.",
            ], root)
            self.assertEqual(code, 0, output)
            card = (root / "skills" / "imported-example" / "skill-card.md").read_text(encoding="utf-8")
            self.assertIn("HCU and hipprof; read traces and write reports.", card)
            self.assertNotIn("TODO", card)
            self.assertNotIn("## Validation", card)
            self.assertIn("lifecycle: published", card)

    def test_import_dry_run_without_license_leaves_catalog_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            before = self.snapshot(root)
            code, output = self.invoke(
                ["import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive", "--dry-run"], root,
            )
            self.assertEqual(code, 0, output)
            self.assertEqual(before, self.snapshot(root))

            without_license = self.source_skill(Path(temporary) / "missing", with_license=False)
            code, output = self.invoke(
                ["import", str(without_license), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive", "--dry-run"], root,
            )
            self.assertEqual(code, 0, output)
            self.assertEqual(before, self.snapshot(root))

    def test_import_preserves_existing_runtime_without_prompting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            runtime = "HCU and hipprof; no network; read-only trace input."
            original_card = (
                f"# Skill Card\n\n## Runtime and permissions\n\n{runtime}\n\n"
                "## Validation\nMeasured a trace conversion; no hardware run.\n\n"
                "## Custom notes\n\nKeep this note.\n"
            )
            (source / "skill-card.md").write_text(
                original_card, encoding="utf-8",
            )
            before = self.snapshot(source)
            with mock.patch("builtins.input", side_effect=AssertionError("unexpected prompt")):
                code, output = self.invoke(["import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools"], root)
            self.assertEqual(code, 0, output)
            card = (root / "skills/imported-example/skill-card.md").read_text(encoding="utf-8")
            self.assertIn(runtime, card)
            self.assertIn("Keep this note.", card)
            self.assertIn(original_card, card)
            self.assertEqual(before, self.snapshot(source))

    def test_import_runtime_override_preserves_unrelated_card_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            (source / "skill-card.md").write_text(
                "# Skill Card\n\n## Runtime and permissions\n\nOld requirements.\n\n## Custom notes\n\nKeep this note.\n",
                encoding="utf-8",
            )
            before = self.snapshot(source)
            code, output = self.invoke([
                "import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive",
                "--runtime-permissions", "Updated requirements; no network.",
            ], root)
            self.assertEqual(code, 0, output)
            card = (root / "skills/imported-example/skill-card.md").read_text(encoding="utf-8")
            self.assertIn("Updated requirements; no network.", card)
            self.assertNotIn("Old requirements.", card)
            self.assertIn("Keep this note.", card)
            self.assertEqual(before, self.snapshot(source))

    def test_import_migrates_only_known_legacy_card_placeholders(self):
        from scripts.import_skill import LEGACY_VALIDATION_PLACEHOLDERS, LEGACY_ORIGIN_PLACEHOLDER
        for actual_validation in ("", "Measured one log conversion; model profiling not exercised.\n"):
            with self.subTest(actual_validation=actual_validation), tempfile.TemporaryDirectory() as temporary:
                root = self.fixture(temporary)
                source = self.source_skill(temporary)
                (source / "skill-card.md").write_text(
                    "# Skill Card\n\n## Runtime and permissions\n\nTODO: Record runtime requirements and permissions.\n\n"
                    "## Validation\n\n" + "\n".join(sorted(LEGACY_VALIDATION_PLACEHOLDERS)) + "\n" + actual_validation
                    + "\n## Local catalog import\n\n" + LEGACY_ORIGIN_PLACEHOLDER + "\nOriginal author: Example Team.\n",
                    encoding="utf-8",
                )
                before = self.snapshot(source)
                code, output = self.invoke([
                    "import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive",
                    "--runtime-permissions", "see SKILL.md",
                ], root)
                self.assertEqual(code, 0, output)
                card = (root / "skills/imported-example/skill-card.md").read_text(encoding="utf-8")
                self.assertNotIn("TODO", card)
                self.assertIn("[SKILL.md](SKILL.md)", card)
                self.assertIn("Original author: Example Team.", card)
                self.assertEqual("## Validation" in card, bool(actual_validation))
                if actual_validation:
                    self.assertIn(actual_validation.strip(), card)
                self.assertEqual(before, self.snapshot(source))

    def test_import_rejects_unknown_placeholders_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            (source / "skill-card.md").write_text(
                "# Skill Card\n\n## Validation\n\nTODO: Review custom behavior.\n", encoding="utf-8",
            )
            before = self.snapshot(root)
            code, output = self.invoke([
                "import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive",
            ], root)
            self.assertEqual(code, 1, output)
            self.assertIn("unresolved template placeholder", output)
            self.assertEqual(before, self.snapshot(root))

    def test_invalid_component_lists_fail_cleanly_without_writes(self):
        for skills_value in (None, [], "not-a-list", [None]):
            for command in ("new", "import"):
                with self.subTest(skills=skills_value, command=command), tempfile.TemporaryDirectory() as temporary:
                    root = self.fixture(temporary)
                    source = self.source_skill(temporary)
                    component = root / "components.d/skillhub.yml"
                    component.write_text(yaml.safe_dump({
                        "name": "SkillHub", "local": True, "description": "Fixture.", "skills": skills_value,
                    }), encoding="utf-8")
                    before = self.snapshot(root)
                    args = ["import", str(source), "--owner", "Catalog Team"] if command == "import" else [
                        "new", "example-tool", "--owner", "Example Team", "--description", "Analyze tool logs.",
                    ]
                    code, output = self.invoke(args + ["--category", "Developer Tools", "--non-interactive"], root)
                    self.assertEqual(code, 1, output)
                    self.assertIn(str(component), output)
                    self.assertNotIn("Traceback", output)
                    self.assertEqual(before, self.snapshot(root))

    def test_eof_help_does_not_request_a_license(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(contribute.ContributionError) as error:
                contribute.prompt_value("Maintaining team")
        self.assertNotIn("--license", str(error.exception))
        self.assertIn("--runtime-permissions", str(error.exception))

    def test_import_without_license_file_preserves_declared_license_and_origin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary, with_license=False)
            entry = source / "SKILL.md"
            entry.write_text(entry.read_text(encoding="utf-8").replace("Apache-2.0", "MIT"), encoding="utf-8")
            before = self.snapshot(source)
            code, output = self.invoke([
                "import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive",
                "--upstream", "https://example.org/project/LICENSE",
            ], root)
            self.assertEqual(code, 0, output)
            self.assertEqual(before, self.snapshot(source))
            destination = root / "skills" / "imported-example"
            self.assertFalse((destination / "LICENSE").exists())
            card = (destination / "skill-card.md").read_text(encoding="utf-8")
            self.assertIn("license: MIT", card)
            self.assertIn("https://example.org/project/LICENSE", card)

    def test_import_original_defaults_to_apache_without_license_or_origin_prompt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary, with_license=False)
            entry = source / "SKILL.md"
            entry.write_text(entry.read_text(encoding="utf-8").replace("license: Apache-2.0\n", ""), encoding="utf-8")
            code, output = self.invoke([
                "import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive",
            ], root)
            self.assertEqual(code, 0, output)
            destination = root / "skills" / "imported-example"
            self.assertIn("license: Apache-2.0", (destination / "skill-card.md").read_text(encoding="utf-8"))
            self.assertFalse((destination / "LICENSE").exists())
            self.assertNotIn("license:", entry.read_text(encoding="utf-8"))

    def test_import_rejects_nested_skills_before_copying(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self.fixture(temporary)
            source = self.source_skill(temporary)
            (source / "references" / "SKILL.md").write_text("nested", encoding="utf-8")
            code, output = self.invoke(
                ["import", str(source), "--owner", "Catalog Team", "--category", "Developer Tools", "--non-interactive"], root,
            )
            self.assertEqual(code, 1)
            self.assertIn("nested SKILL.md", output)
            self.assertFalse((root / "skills" / "imported-example").exists())

    def test_check_runs_existing_gates_without_submitting_git_changes(self):
        completed = subprocess.CompletedProcess([], 0, "CLI output")
        with mock.patch.object(contribute, "check_environment", return_value="npx.cmd"), \
             mock.patch.object(contribute, "run", return_value=completed) as runner:
            code, output = self.invoke(["check"])
        self.assertEqual(code, 0, output)
        commands = [call.args[0] for call in runner.call_args_list]
        self.assertEqual(commands[0], [sys.executable, "scripts/generate_catalog.py"])
        self.assertEqual(commands[5], [sys.executable, "scripts/sync_sources.py", "--check"])
        self.assertEqual(commands[6], ["npx.cmd", "--yes", "skills@1.5.23", "add", ".", "--list"])
        self.assertEqual(commands[-2], ["npx.cmd", "--yes", "skills@1.5.23", "add", ".", "--list", "--full-depth"])
        self.assertIn("No branch, Git index, commit, push or pull request is created", output)

    def test_help_and_unknown_submit_do_not_require_dependencies(self):
        result = subprocess.run(
            [sys.executable, "-S", str(contribute.ROOT / "scripts" / "contribute.py"), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("{import,new,check}", result.stdout)
        with self.assertRaises(SystemExit) as failure:
            self.invoke(["submit"])
        self.assertEqual(failure.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
