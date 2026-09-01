# Copyright (c) 2026 Hygon Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

import sys
import tempfile
import unittest
from pathlib import Path

from scripts.skillhub import (
    ALLOWED_CATEGORIES,
    CatalogError,
    load_components,
    validate_admission_exceptions,
    validate_eval_dataset,
    validate_inline_skill_dependencies,
    validate_lock,
    validate_markdown_links,
    validate_skill_card,
    validate_skill_frontmatter,
    validate_skill_placeholders,
    validate_skill_tree,
    validate_staging,
)
from scripts.check_dco import has_valid_signoff

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_catalog import build_category_index, replace_section  # noqa: E402
from validate_cli_discovery import discovery_errors  # noqa: E402


COMPONENT = """\
name: Example
repo: {repo}
description: Example component.
skills:
  - path: skills/example
    catalog_dir: example
    category: Developer Tools
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

    def test_category_allowlist_is_stable(self):
        self.assertEqual(ALLOWED_CATEGORIES, frozenset({
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
        }))

    def test_accepts_accuracy_and_debugging_category(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component_dir = root / "components.d"
            component_dir.mkdir()
            (component_dir / "example.yml").write_text(
                COMPONENT.format(repo="HYGON-AI/example").replace(
                    "category: Developer Tools", "category: Accuracy and Debugging"
                ),
                encoding="utf-8",
            )
            components = load_components(root)
            self.assertEqual(
                components[0]["skills"][0]["category"],
                "Accuracy and Debugging",
            )

    def test_rejects_third_party_repository(self):
        with self.assertRaisesRegex(CatalogError, "repo must be owned by HYGON-AI"):
            self.load_repo("third-party/example")

    def test_rejects_source_path_that_can_be_parsed_as_a_git_option(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component_dir = root / "components.d"
            component_dir.mkdir()
            (component_dir / "example.yml").write_text(
                COMPONENT.format(repo="HYGON-AI/example").replace(
                    "path: skills/example", "path: --help"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CatalogError, "safe repository-relative"):
                load_components(root)

    def test_rejects_unknown_category(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component_dir = root / "components.d"
            component_dir.mkdir()
            (component_dir / "example.yml").write_text(
                COMPONENT.format(repo="HYGON-AI/example").replace(
                    "category: Developer Tools", "category: Made Up Category"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CatalogError, "category must be one of"):
                load_components(root)

    def test_rejects_bare_generic_catalog_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            component_dir = root / "components.d"
            component_dir.mkdir()
            (component_dir / "example.yml").write_text(
                COMPONENT.format(repo="HYGON-AI/example").replace(
                    "catalog_dir: example", "catalog_dir: profile"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CatalogError, "is too generic"):
                load_components(root)


class StandaloneSkillTests(unittest.TestCase):
    def test_accepts_all_agent_skills_frontmatter_fields(self):
        frontmatter = {
            "name": "example",
            "description": "Do example work when the user requests an example.",
            "license": "Apache-2.0",
            "compatibility": "Requires Python 3.11+.",
            "metadata": {"author": "HYGON-AI", "version": "1.0.0"},
            "allowed-tools": "Read Bash(git:*)",
        }
        self.assertEqual(
            validate_skill_frontmatter(frontmatter, "example", Path("skills/example")),
            [],
        )

    def test_rejects_vendor_field_and_non_string_metadata(self):
        frontmatter = {
            "name": "example",
            "description": "Do example work when requested.",
            "version": "1.0.0",
            "metadata": {"tags": ["one", "two"]},
        }
        errors = validate_skill_frontmatter(
            frontmatter, "example", Path("skills/example")
        )
        self.assertTrue(any("unsupported frontmatter fields: version" in error for error in errors))
        self.assertTrue(any("metadata keys and values must be strings" in error for error in errors))

    def test_rejects_overlong_compatibility(self):
        errors = validate_skill_frontmatter(
            {
                "name": "example",
                "description": "Do example work when requested.",
                "compatibility": "x" * 501,
            },
            "example",
            Path("skills/example"),
        )
        self.assertTrue(any("compatibility exceeds 500" in error for error in errors))

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

    def test_rejects_generated_cache_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill_dir = root / "skills" / "example"
            cache_file = skill_dir / "__pycache__" / "helper.pyc"
            cache_file.parent.mkdir(parents=True)
            cache_file.write_bytes(b"cache")
            errors = validate_skill_tree(skill_dir, root)
            self.assertTrue(any("not publishable" in error for error in errors))

    def test_rejects_template_scaffold_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill_dir = root / "skills" / "example"
            template_file = skill_dir / "agents" / "openai.yaml.template"
            template_file.parent.mkdir(parents=True)
            template_file.write_text("interface: {}\n", encoding="utf-8")
            errors = validate_skill_tree(skill_dir, root)
            self.assertTrue(any(
                "template scaffold file is not publishable" in error
                for error in errors
            ))

    def test_rejects_scaffold_placeholder_but_allows_todo_and_tbd_prose(self):
        rel = Path("skills/example")
        self.assertEqual(
            validate_skill_placeholders(
                "# Review\nCheck whether source files contain TODO or TBD markers.",
                rel,
            ),
            [],
        )
        errors = validate_skill_placeholders("# Replace with skill title", rel)
        self.assertTrue(any("unresolved scaffold placeholder" in error for error in errors))
        errors = validate_skill_placeholders(
            "name: replace-with-lowercase-hyphen-name", rel
        )
        self.assertTrue(any("unresolved scaffold placeholder" in error for error in errors))


class StagingSkillTests(unittest.TestCase):
    def write_candidate(self, root, directory="example", name="example"):
        candidate_dir = root / "staging" / directory
        candidate_dir.mkdir(parents=True)
        (candidate_dir / "SKILL.md.candidate").write_text(
            "---\n"
            "name: {}\n"
            "description: Do example work when the user requests an example.\n"
            "---\n\n"
            "# Example\n".format(name),
            encoding="utf-8",
        )
        return candidate_dir

    def test_accepts_undiscoverable_candidate_entrypoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_candidate(root)
            self.assertEqual(validate_staging(root), [])

    def test_rejects_nested_discoverable_skill_md_in_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate_dir = self.write_candidate(root)
            nested = candidate_dir / "references" / "nested" / "SKILL.md"
            nested.parent.mkdir(parents=True)
            nested.write_text("# Discoverable\n", encoding="utf-8")
            errors = validate_staging(root)
            self.assertTrue(any(
                "discoverable SKILL.md is not allowed in staging" in error
                for error in errors
            ))

    def test_rejects_discoverable_skill_md_at_staging_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging_dir = root / "staging"
            staging_dir.mkdir()
            (staging_dir / "SKILL.md").write_text(
                "# Discoverable\n", encoding="utf-8"
            )
            errors = validate_staging(root)
            self.assertTrue(any(
                "discoverable SKILL.md is not allowed in staging" in error
                for error in errors
            ))

    def test_rejects_candidate_name_directory_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_candidate(root, directory="example", name="other")
            errors = validate_staging(root)
            self.assertTrue(any(
                "name must equal catalog_dir 'example'" in error
                for error in errors
            ))

    def test_rejects_candidate_scaffold_placeholder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate_dir = self.write_candidate(root)
            candidate_file = candidate_dir / "SKILL.md.candidate"
            candidate_file.write_text(
                candidate_file.read_text(encoding="utf-8").replace(
                    "# Example", "# Replace with skill title"
                ),
                encoding="utf-8",
            )
            errors = validate_staging(root)
            self.assertTrue(any(
                "unresolved scaffold placeholder" in error
                for error in errors
            ))


class SkillCardTests(unittest.TestCase):
    def test_accepts_structured_skill_card(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill_dir = root / "skills" / "example"
            skill_dir.mkdir(parents=True)
            path = skill_dir / "skill-card.md"
            path.write_text(
                """---
schema_version: 1
owner: HYGON-AI Example Team
source:
  repo: HYGON-AI/example
  path: skills/example
license: Apache-2.0
lifecycle: published
---
# Skill Card

## Summary
Summary.

## Owner
Owner.

## Source
Source.

## License
License.

## Runtime and permissions
None.

## Validation
Validated.
""",
                encoding="utf-8",
            )
            record = {
                "dir": skill_dir,
                "component": {"repo": "HYGON-AI/example"},
                "spec": {"path": "skills/example"},
                "metadata": {"license": "Apache-2.0"},
            }
            self.assertEqual(validate_skill_card(path, record, root), [])


class EvaluationDatasetTests(unittest.TestCase):
    def test_accepts_minimum_routing_and_behavior_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "evals.json"
            path.write_text(
                """{
  "schema_version": 1,
  "skill": "example",
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
            self.assertEqual(validate_eval_dataset(path, root, "example"), [])

    def test_rejects_thin_routing_only_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "evals.json"
            path.write_text(
                '{"schema_version": 1, "skill": "example", "evaluations": [{"id": "p1", "skill_should_trigger": true, "prompt": "positive"}]}',
                encoding="utf-8",
            )
            errors = validate_eval_dataset(path, root, "example")
            self.assertTrue(any("at least 3 positive" in error for error in errors))
            self.assertTrue(any("at least 2 negative" in error for error in errors))
            self.assertTrue(any("behavioral assertion" in error for error in errors))

    def test_rejects_eval_identity_mismatch_and_unknown_case_field(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "evals.json"
            path.write_text(
                """{
  "schema_version": 1,
  "skill": "other",
  "evaluations": [
    {"id": "p1", "skill_should_trigger": true, "prompt": "one", "expected_behavior": ["ok"], "tags": []},
    {"id": "p2", "skill_should_trigger": true, "prompt": "two"},
    {"id": "p3", "skill_should_trigger": true, "prompt": "three"},
    {"id": "n1", "skill_should_trigger": false, "prompt": "four"},
    {"id": "n2", "skill_should_trigger": false, "prompt": "five"}
  ]
}
""",
                encoding="utf-8",
            )
            errors = validate_eval_dataset(path, root, "example")
            self.assertTrue(any("skill must equal 'example'" in error for error in errors))
            self.assertTrue(any("unsupported fields: tags" in error for error in errors))


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


class AdmissionExceptionTests(unittest.TestCase):
    def test_rejects_exception_that_is_also_registered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "admission-exceptions.yml").write_text(
                """schema_version: 1
exceptions:
  - repo: HYGON-AI/example
    path: skills/example
    reasons:
      - Not ready.
""",
                encoding="utf-8",
            )
            components = [{
                "repo": "HYGON-AI/example",
                "skills": [{"path": "skills/example"}],
            }]
            errors = validate_admission_exceptions(components, root)
            self.assertTrue(any("cannot also be registered" in error for error in errors))


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


class DcoTests(unittest.TestCase):
    def test_accepts_valid_signoff(self):
        self.assertTrue(has_valid_signoff(
            "feat(catalog): add example\n\nSigned-off-by: Example User <example@example.com>\n"
        ))

    def test_rejects_missing_or_malformed_signoff(self):
        self.assertFalse(has_valid_signoff("feat(catalog): add example\n"))
        self.assertFalse(has_valid_signoff("Signed-off-by: Example User\n"))


class CliDiscoveryTests(unittest.TestCase):
    def test_accepts_cli_border_and_ansi_output(self):
        output = "\x1b[?25h|\no  Found 1 skill\n|    example\n"
        self.assertEqual(discovery_errors(output, ["example"]), [])

    def test_rejects_count_or_name_drift(self):
        errors = discovery_errors("Found 2 skills\n| other\n", ["example"])
        self.assertTrue(any("catalog registers 1" in error for error in errors))
        self.assertTrue(any("omitted registered skill" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
