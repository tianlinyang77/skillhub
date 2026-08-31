# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

import sys
import tempfile
import unittest
from pathlib import Path

from scripts.skillhub import (
    CatalogError,
    load_components,
    validate_eval_dataset,
    validate_inline_skill_dependencies,
    validate_lock,
    validate_markdown_links,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_catalog import build_category_index, replace_section  # noqa: E402


COMPONENT = """\
name: Example
repo: {repo}
description: Example component.
skills:
  - path: skills/example
    catalog_dir: example
    category: Testing
"""


class ComponentOwnerTests(unittest.TestCase):
    def load_repo(self, repo):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component_dir = root / "components.d"
            component_dir.mkdir()
            (component_dir / "example.yml").write_text(
                COMPONENT.format(repo=repo), encoding="utf-8"
            )
            return load_components(root)

    def test_accepts_hygon_ai_repository(self):
        components = self.load_repo("HYGON-AI/example")
        self.assertEqual(components[0]["repo"], "HYGON-AI/example")

    def test_rejects_third_party_repository(self):
        with self.assertRaisesRegex(CatalogError, "repo must be owned by HYGON-AI"):
            self.load_repo("third-party/example")


class StandaloneSkillTests(unittest.TestCase):
    def test_rejects_dependency_on_sibling_skill(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill_dir = root / "skills" / "bulk-example"
            skill_dir.mkdir(parents=True)
            errors = validate_inline_skill_dependencies(
                skill_dir,
                "Load `../required-skill/SKILL.md` before continuing.",
                root,
            )
            self.assertEqual(len(errors), 1)
            self.assertIn("inline dependency escapes skill directory", errors[0])

    def test_rejects_bundled_nested_skill_reference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill_dir = root / "skills" / "self-contained"
            bundled = skill_dir / "references" / "rules" / "SKILL.md"
            bundled.parent.mkdir(parents=True)
            bundled.write_text("# Rules\n", encoding="utf-8")
            errors = validate_inline_skill_dependencies(
                skill_dir,
                "Load `references/rules/SKILL.md` before continuing.",
                root,
            )
            self.assertEqual(len(errors), 1)
            self.assertIn("nested SKILL.md dependencies are not allowed", errors[0])

    def test_checks_links_in_reference_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill_dir = root / "skills" / "example"
            reference = skill_dir / "references" / "guide.md"
            reference.parent.mkdir(parents=True)
            reference.write_text("Read [missing](missing.md).\n", encoding="utf-8")
            errors = validate_markdown_links(skill_dir, root)
            self.assertEqual(len(errors), 1)
            self.assertIn("broken relative link", errors[0])


class EvaluationDatasetTests(unittest.TestCase):
    def test_accepts_minimum_routing_and_behavior_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "evals.json"
            path.write_text(
                """{
  "evaluations": [
    {"id": "p1", "skill_should_trigger": true, "prompt": "positive one", "expected_behavior": ["do the work"]},
    {"id": "p2", "skill_should_trigger": true, "prompt": "positive two"},
    {"id": "p3", "skill_should_trigger": true, "prompt": "positive three"},
    {"id": "n1", "skill_should_trigger": false, "prompt": "negative one"},
    {"id": "n2", "skill_should_trigger": false, "prompt": "negative two"}
  ]
}
""",
                encoding="utf-8",
            )
            self.assertEqual(validate_eval_dataset(path, root), [])

    def test_rejects_thin_routing_only_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "evals.json"
            path.write_text(
                '{"evaluations": [{"id": "p1", "skill_should_trigger": true, "prompt": "positive"}]}',
                encoding="utf-8",
            )
            errors = validate_eval_dataset(path, root)
            self.assertTrue(any("at least 3 positive" in error for error in errors))
            self.assertTrue(any("at least 2 negative" in error for error in errors))
            self.assertTrue(any("behavioral assertion" in error for error in errors))


class LockFileTests(unittest.TestCase):
    def test_rejects_invalid_lock_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".skillhub-lock.json").write_text("not-json\n", encoding="utf-8")
            errors = validate_lock([], [], root)
            self.assertEqual(len(errors), 1)
            self.assertIn("invalid JSON", errors[0])

    def test_accepts_empty_lock_without_remote_components(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".skillhub-lock.json").write_text(
                '{"schema_version": 1, "skills": {}}\n', encoding="utf-8"
            )
            self.assertEqual(validate_lock([], [], root), [])


def make_record(catalog_dir, category, product, description):
    return {
        "component": {"name": product},
        "spec": {"catalog_dir": catalog_dir, "category": category},
        "metadata": {"description": description},
    }


class CategoryIndexTests(unittest.TestCase):
    def test_groups_skills_and_sorts_deterministically(self):
        index = build_category_index([
            make_record("vllm-deploy", "Inference", "vLLM Plugin DAS", "Serve models."),
            make_record("env-check", "Diagnostics", "Cookbook DAS", "Check the host."),
            make_record("megatron-train", "Training", "Megatron DAS", "Train models."),
            make_record("sglang-deploy", "Inference", "SGLang DAS", "Serve models."),
        ])
        self.assertTrue(index.startswith("4 skills across 3 categories."))
        self.assertLess(index.index("### Diagnostics"), index.index("### Inference"))
        self.assertLess(index.index("### Inference"), index.index("### Training"))
        self.assertLess(index.index("sglang-deploy"), index.index("vllm-deploy"))

    def test_uses_singular_labels_for_one_skill(self):
        index = build_category_index([
            make_record("env-check", "Diagnostics", "Cookbook DAS", "Check the host."),
        ])
        self.assertTrue(index.startswith("1 skill across 1 category."))

    def test_escapes_table_breaking_characters(self):
        index = build_category_index([
            make_record("env-check", "Diagnostics", "Cookbook DAS", "Run a | b\nacross lines."),
        ])
        self.assertIn("Run a \\| b across lines.", index)

    def test_requires_readme_markers(self):
        with self.assertRaisesRegex(ValueError, "categories:start"):
            replace_section("# Title\n", "<!-- categories:start -->", "<!-- categories:end -->", "body")


if __name__ == "__main__":
    unittest.main()
