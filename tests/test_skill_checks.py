"""Unit tests for .github/scripts/skill_checks.py.

Each test builds one skill folder in memory and runs the rules on it, so no
Git repository is needed. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import skill_checks as sc  # noqa: E402

RULES = sc.Rules(
    agent_types=frozenset({"GENERIC", "CHAT", "INCIDENT_RCA"}),
    vocabulary={
        "agent-types": frozenset({"Chat tasks", "Evaluation"}),
        "aws-services": frozenset({"Amazon CloudWatch", "Amazon EKS"}),
        "technical-domains": frozenset({"Operations"}),
    },
    aliases={"CloudWatch": "Amazon CloudWatch"},
    allowed_extensions=frozenset({"md", "json", "png", "html"}),
    published_excludes=("evals/", ".skilleval.yaml", ".skilleval.yml", "CHANGELOG.md", "README.md", "images/"),
    display_agent_types={"Chat tasks": ("CHAT",), "Evaluation": None},
)

VALID_FRONTMATTER = """\
name: demo-skill
description: Use this skill when testing the skill publishing check.
metadata:
  author: octocat
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks"
  summary: "Checks a demo skill."
"""


def skill_md(frontmatter: str = VALID_FRONTMATTER, body: str = "\n# Demo\n") -> bytes:
    return f"---\n{frontmatter}---\n{body}".encode("utf-8")


def tree(content: bytes | None = None, name: str = "demo-skill", **files: bytes) -> sc.SkillTree:
    entries = {}
    if content is not None:
        entries["SKILL.md"] = sc.Entry("SKILL.md", "100644", content)
    for path, data in files.items():
        entries[path] = sc.Entry(path, "100644", data)
    return sc.SkillTree(name, entries)


def frontmatter_with(**overrides: str | None) -> str:
    """VALID_FRONTMATTER with metadata keys replaced (value) or removed (None)."""
    metadata = {
        "author": "octocat",
        "version": '"1.0.0"',
        "aws-devops-agent-skills.agent-types": '"Chat tasks"',
        "summary": '"Checks a demo skill."',
    }
    for key, value in overrides.items():
        if value is None:
            metadata.pop(key, None)
        else:
            metadata[key] = value
    lines = "".join(f"  {key}: {value}\n" for key, value in metadata.items())
    return (
        "name: demo-skill\n"
        "description: Use this skill when testing the skill publishing check.\n"
        f"metadata:\n{lines}"
    )


class CheckSkillTestCase(unittest.TestCase):
    def check(self, skill: sc.SkillTree) -> tuple[list[sc.Finding], sc.SkillInfo | None]:
        return sc.check_skill(skill, RULES)

    def errors(self, skill: sc.SkillTree) -> list[sc.Finding]:
        return [f for f in self.check(skill)[0] if f.severity == "error"]

    def warnings(self, skill: sc.SkillTree) -> list[sc.Finding]:
        return [f for f in self.check(skill)[0] if f.severity == "warning"]

    def assertOneError(self, skill: sc.SkillTree, fragment: str, line: int | None = None) -> sc.Finding:
        errors = self.errors(skill)
        matching = [f for f in errors if fragment in f.message]
        self.assertTrue(matching, f"no error containing {fragment!r}; got {[f.message for f in errors]}")
        if line is not None:
            self.assertEqual(matching[0].line, line, matching[0].message)
        return matching[0]


class ValidSkillTests(CheckSkillTestCase):
    def test_valid_skill_has_no_findings(self):
        findings, info = self.check(tree(skill_md()))
        self.assertEqual(findings, [])
        self.assertEqual(info.name, "demo-skill")
        self.assertEqual(info.version, (1, 0, 0))
        self.assertEqual(info.metadata["author"], "octocat")

    def test_block_scalar_description_is_accepted(self):
        fm = VALID_FRONTMATTER.replace(
            "description: Use this skill when testing the skill publishing check.\n",
            "description: >-\n  Use this skill when testing\n  the skill publishing check.\n",
        )
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_optional_fields_are_accepted(self):
        fm = frontmatter_with(
            summary='"Checks a demo skill."',
            deprecated='"false"',
            agent_types='"CHAT, INCIDENT_RCA"',
        ).replace("metadata:\n", "title: Demo Skill\ncompatibility: Requires nothing.\nmetadata:\n")
        self.assertEqual(self.check(tree(skill_md(fm)))[0], [])


class FileAndYamlTests(CheckSkillTestCase):
    def test_missing_skill_md(self):
        self.assertOneError(tree(None, **{"README.md": b"# Demo\n"}), "has no SKILL.md")

    def test_not_utf8(self):
        self.assertOneError(tree(b"---\nname: \xff\n---\n"), "not valid UTF-8")

    def test_no_opening_delimiter(self):
        self.assertOneError(tree(b"name: demo-skill\n"), "must start with a --- line", line=1)

    def test_no_closing_delimiter(self):
        self.assertOneError(tree(b"---\nname: demo-skill\n"), "no closing --- line")

    def test_invalid_yaml_reports_line(self):
        content = skill_md(VALID_FRONTMATTER + 'bad: "unclosed\n')
        self.assertOneError(tree(content), "not valid YAML")

    def test_anchor_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("author: octocat", "author: &who octocat")
        self.assertOneError(tree(skill_md(fm)), "anchors", line=5)

    def test_alias_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("author: octocat", "author: &who octocat") + "license: *who\n"
        self.assertOneError(tree(skill_md(fm)), "aliases")

    def test_tag_is_rejected(self):
        fm = VALID_FRONTMATTER.replace('version: "1.0.0"', "version: !!str 1.0.0")
        self.assertOneError(tree(skill_md(fm)), "tags", line=6)

    def test_flow_collection_is_rejected(self):
        fm = VALID_FRONTMATTER + "allowed-tools: [read, write]\n"
        self.assertOneError(tree(skill_md(fm)), "flow collections", line=9)

    def test_frontmatter_must_be_a_mapping(self):
        self.assertOneError(tree(b"---\n- one\n- two\n---\n"), "must be a mapping")

    def test_duplicate_key_reports_second_line(self):
        fm = VALID_FRONTMATTER + "name: demo-skill\n"
        self.assertOneError(tree(skill_md(fm)), 'duplicate key "name"', line=9)

    def test_duplicate_metadata_key(self):
        fm = VALID_FRONTMATTER + '  version: "1.0.1"\n'
        self.assertOneError(tree(skill_md(fm)), 'duplicate key "metadata.version"', line=9)

    def test_non_string_key_is_rejected(self):
        fm = VALID_FRONTMATTER + "1: one\n"
        self.assertOneError(tree(skill_md(fm)), "keys must be plain text")

    def test_unknown_top_level_key_is_a_warning(self):
        fm = VALID_FRONTMATTER + "owner: someone\n"
        warnings = self.warnings(tree(skill_md(fm)))
        self.assertEqual(len(warnings), 1)
        self.assertIn('unknown top-level key "owner"', warnings[0].message)
        self.assertEqual(self.errors(tree(skill_md(fm))), [])


class NameTests(CheckSkillTestCase):
    def with_name(self, name: str, folder: str = "demo-skill") -> sc.SkillTree:
        return tree(skill_md(VALID_FRONTMATTER.replace("name: demo-skill", f"name: {name}")), name=folder)

    def test_name_is_required(self):
        fm = VALID_FRONTMATTER.replace("name: demo-skill\n", "")
        self.assertOneError(tree(skill_md(fm)), '"name" is required')

    def test_name_must_be_a_string(self):
        self.assertOneError(self.with_name("true"), '"name" must be text, not true or false', line=2)

    def test_name_pattern(self):
        for bad in ("Demo-Skill", "demo--skill", "-demo", "demo-", "demo_skill"):
            with self.subTest(bad=bad):
                self.assertOneError(self.with_name(bad, folder=bad), "lowercase letters, digits and single hyphens")

    def test_name_length(self):
        long_name = "a" * 65
        self.assertOneError(self.with_name(long_name, folder=long_name), "65 characters; the limit is 64")

    def test_name_with_trailing_newline_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("name: demo-skill", "name: |\n  demo-skill")
        self.assertOneError(tree(skill_md(fm)), "lowercase letters, digits and single hyphens")

    def test_deeply_nested_frontmatter_is_a_finding_not_a_crash(self):
        nested = "".join("  " * depth + f"k{depth}:\n" for depth in range(1, 1200)) + "  " * 1200 + "k: v\n"
        self.assertOneError(tree(skill_md(VALID_FRONTMATTER + "deep:\n" + nested)), "nested too deeply")

    def test_name_must_match_folder(self):
        self.assertOneError(self.with_name("other-skill"), 'but the folder is "demo-skill"', line=2)


class DescriptionAndTitleTests(CheckSkillTestCase):
    def test_description_is_required(self):
        fm = VALID_FRONTMATTER.replace("description: Use this skill when testing the skill publishing check.\n", "")
        self.assertOneError(tree(skill_md(fm)), '"description" is required')

    def test_description_must_not_be_empty(self):
        fm = VALID_FRONTMATTER.replace("Use this skill when testing the skill publishing check.", '""')
        self.assertOneError(tree(skill_md(fm)), '"description" must not be empty', line=3)

    def test_description_limit(self):
        fm = VALID_FRONTMATTER.replace("Use this skill when testing the skill publishing check.", "x" * 1025)
        self.assertOneError(tree(skill_md(fm)), "1,025 characters; the limit is 1,024")
        fm = VALID_FRONTMATTER.replace("Use this skill when testing the skill publishing check.", "x" * 1024)
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_title_limit_and_single_line(self):
        fm = VALID_FRONTMATTER + f"title: {'T' * 101}\n"
        self.assertOneError(tree(skill_md(fm)), '"title" is 101 characters; the limit is 100')
        fm = VALID_FRONTMATTER + "title: |\n  Two\n  lines\n"
        self.assertOneError(tree(skill_md(fm)), '"title" must be a single line')


class MetadataTests(CheckSkillTestCase):
    def test_metadata_is_required(self):
        fm = "name: demo-skill\ndescription: Use this skill when testing.\n"
        self.assertOneError(tree(skill_md(fm)), '"metadata" is required')

    def test_metadata_must_be_a_mapping(self):
        fm = "name: demo-skill\ndescription: Use this skill when testing.\nmetadata: none\n"
        self.assertOneError(tree(skill_md(fm)), '"metadata" must be a mapping', line=4)

    def test_metadata_values_must_be_strings(self):
        fm = frontmatter_with(version="1.0")
        error = self.assertOneError(tree(skill_md(fm)), '"metadata.version" must be text, not a number', line=6)
        self.assertIn("quotes", error.message)

    def test_metadata_values_must_not_be_nested(self):
        fm = VALID_FRONTMATTER + "  extra:\n    nested: value\n"
        self.assertOneError(tree(skill_md(fm)), '"metadata.extra" must be text, not a mapping', line=9)

    def test_author_is_required_and_github_shaped(self):
        self.assertOneError(tree(skill_md(frontmatter_with(author=None))), '"metadata.author" is required')
        for bad in ('"-octocat"', '"octo cat"', '"octo--cat"', '"a,,b"', '""'):
            with self.subTest(bad=bad):
                self.assertOneError(tree(skill_md(frontmatter_with(author=bad))), "GitHub usernames")

    def test_author_accepts_a_comma_separated_list(self):
        self.assertEqual(self.errors(tree(skill_md(frontmatter_with(author='"octocat, hubot"')))), [])

    def test_version_is_required(self):
        self.assertOneError(tree(skill_md(frontmatter_with(version=None))), '"metadata.version" is required')

    def test_version_must_be_major_minor_patch(self):
        for bad in ('"2.6"', '"1.0.0-beta"', '"1.0.0+build"', '"01.0.0"', '"v1.0.0"', '"1.0.0.0"'):
            with self.subTest(bad=bad):
                self.assertOneError(tree(skill_md(frontmatter_with(version=bad))), "MAJOR.MINOR.PATCH", line=6)

    def test_block_scalar_version_with_trailing_newline_is_rejected(self):
        fm = frontmatter_with(version="|\n    1.0.0")
        self.assertOneError(tree(skill_md(fm)), "MAJOR.MINOR.PATCH")

    def test_unquoted_three_part_version_is_text(self):
        findings, info = self.check(tree(skill_md(frontmatter_with(version="1.2.3"))))
        self.assertEqual(findings, [])
        self.assertEqual(info.version, (1, 2, 3))

    def test_summary_limit_and_single_line(self):
        fm = frontmatter_with(summary=f'"{"s" * 201}"')
        self.assertOneError(tree(skill_md(fm)), '"metadata.summary" is 201 characters; the limit is 200')
        fm = frontmatter_with(summary='"two\\nlines"')
        self.assertOneError(tree(skill_md(fm)), '"metadata.summary" must be a single line')

    def test_deprecated_must_be_true_or_false_text(self):
        self.assertOneError(tree(skill_md(frontmatter_with(deprecated='"yes"'))), '"true" or "false"')
        self.assertOneError(tree(skill_md(frontmatter_with(deprecated="true"))), "must be text, not true or false")
        self.assertEqual(self.errors(tree(skill_md(frontmatter_with(deprecated='"true"')))), [])

    def test_agent_types_values(self):
        fm = frontmatter_with(agent_types='"CHAT, PAGER"')
        self.assertOneError(tree(skill_md(fm)), 'unknown value "PAGER"')
        fm = frontmatter_with(agent_types='"CHAT,"')
        self.assertOneError(tree(skill_md(fm)), "empty value between commas")


class DimensionTests(CheckSkillTestCase):
    def test_unknown_dimension_is_an_error(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.services": '"Amazon EKS"'})
        self.assertOneError(tree(skill_md(fm)), "not a known dimension")

    def test_empty_dimension_value_is_an_error(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.aws-services": '"Amazon EKS, "'})
        self.assertOneError(tree(skill_md(fm)), "empty value between commas")

    def test_unapproved_value_is_a_warning_with_suggestion(self):
        fm = frontmatter_with(**{"aws-devops-agent-skills.aws-services": '"CloudWatch, Amazon S3"'})
        skill = tree(skill_md(fm))
        self.assertEqual(self.errors(skill), [])
        messages = [w.message for w in self.warnings(skill)]
        self.assertEqual(len(messages), 2)
        self.assertIn('use "Amazon CloudWatch"', messages[0])
        self.assertIn('"Amazon S3" is not an approved aws-services value', messages[1])


class SummaryAndAgentTypeTests(CheckSkillTestCase):
    def test_missing_summary_is_a_warning_for_every_skill(self):
        skill = tree(skill_md(frontmatter_with(summary=None)))
        self.assertEqual(self.errors(skill), [])
        (warning,) = self.warnings(skill)
        self.assertIn('"metadata.summary" is missing', warning.message)
        self.assertEqual(warning.line, 4)

    def test_agent_types_come_from_the_display_tag(self):
        metadata = {"aws-devops-agent-skills.agent-types": "Chat tasks, Evaluation, Chat tasks"}
        self.assertEqual(sc.runtime_agent_types(metadata, RULES), (["CHAT"], False))

    def test_explicit_agent_types_override_the_display_tag(self):
        metadata = {"agent_types": "INCIDENT_RCA, GENERIC", "aws-devops-agent-skills.agent-types": "Chat tasks"}
        self.assertEqual(sc.runtime_agent_types(metadata, RULES), (["INCIDENT_RCA", "GENERIC"], False))

    def test_no_mapped_agent_type_falls_back_to_generic_with_a_warning(self):
        self.assertEqual(sc.runtime_agent_types({}, RULES), (["GENERIC"], True))
        fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": '"Evaluation"'})
        (warning,) = self.warnings(tree(skill_md(fm)))
        self.assertIn('none of "Evaluation" has an agent-type mapping yet', warning.message)
        self.assertIn("GENERIC", warning.message)
        fm = frontmatter_with(**{"aws-devops-agent-skills.agent-types": None})
        (warning,) = self.warnings(tree(skill_md(fm)))
        self.assertIn("it sets no agent types", warning.message)

    def test_explicit_generic_does_not_warn(self):
        fm = frontmatter_with(agent_types='"GENERIC"', **{"aws-devops-agent-skills.agent-types": None})
        self.assertEqual(self.check(tree(skill_md(fm)))[0], [])


def with_files(*paths: str, mode: str = "100644", data: bytes = b"text\n") -> sc.SkillTree:
    skill = tree(skill_md())
    for path in paths:
        skill.entries[path] = sc.Entry(path, mode, data)
    return skill


class PublishedSetTests(unittest.TestCase):
    def test_excludes_evals_eval_config_changelog_readme_and_images(self):
        skill = with_files(
            "README.md", "CHANGELOG.md", ".skilleval.yaml", "evals/evals.json", "images/diagram.png",
            "references/a.md", "docs/CHANGELOG.md", "references/README.md",
        )
        self.assertEqual(
            sorted(sc.published_files(skill, RULES)),
            ["SKILL.md", "docs/CHANGELOG.md", "references/README.md", "references/a.md"],
        )

    def test_repository_published_set_leaves_out_readme_and_images(self):
        gitignore = (ROOT / "skills" / ".gitignore").read_text(encoding="utf-8")
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules", gitignore)
        for name in ("README.md", "images/", "evals/", "CHANGELOG.md"):
            self.assertIn(name, rules.published_excludes)

    def test_zip_is_deterministic(self):
        files = {"b.md": b"b", "a.md": b"a" * 100}
        self.assertEqual(sc.build_zip(files), sc.build_zip(dict(reversed(files.items()))))


class PackageTests(CheckSkillTestCase):
    def test_typical_skill_passes(self):
        skill = with_files("README.md", "references/guide.md", "assets/diagram.png", "evals/evals.json")
        self.assertEqual(self.errors(skill), [])

    def test_file_count_limit(self):
        paths = [f"references/{i:03}.md" for i in range(99)]
        self.assertEqual(self.errors(with_files(*paths)), [])
        self.assertOneError(with_files(*paths, "references/extra.md"), "101 published files; the limit is 100")

    def test_evals_do_not_count_toward_the_file_limit(self):
        paths = [f"evals/run/{i:03}.json" for i in range(200)]
        self.assertEqual(self.errors(with_files(*paths)), [])

    def test_zip_size_limit_and_warning(self):
        import random

        rng = random.Random(7)
        near = bytes(rng.getrandbits(8) for _ in range(900_000))
        self.assertEqual(self.errors(with_files("assets/big.png", data=near)), [])
        self.assertTrue(any("90%" in w.message for w in self.warnings(with_files("assets/big.png", data=near))))
        over = bytes(rng.getrandbits(8) for _ in range(990_000))
        self.assertOneError(with_files("assets/big.png", data=over), "the limit is 983,040")

    def test_executable_symlink_and_submodule_are_rejected_anywhere(self):
        self.assertOneError(with_files("references/a.md", mode="100755"), "executable")
        self.assertOneError(with_files("evals/run.json", mode="100755"), "executable")
        self.assertOneError(with_files("references/link.md", mode="120000", data=b"../../x"), "symbolic link")
        self.assertOneError(with_files("vendor", mode="160000", data=b""), "Git submodule")

    def test_path_rules(self):
        cases = {
            "references/my notes.md": "letters, digits",
            "references/naïve.md": "letters, digits",
            "references/CON.md": "reserved name",
            "references/notes.": "ends with a period",
            "references/" + "a" * 510 + ".md": "the limit is 512",
        }
        for path, fragment in cases.items():
            with self.subTest(path=path):
                self.assertOneError(with_files(path), fragment)

    def test_folder_name_with_trailing_newline_is_rejected(self):
        self.assertOneError(with_files("references\n/a.md"), "letters, digits")

    def test_case_collision(self):
        self.assertOneError(with_files("references/Guide.md", "references/guide.md"), "differ only in case")

    def test_hidden_files_are_rejected_in_the_published_set_only(self):
        self.assertOneError(with_files(".DS_Store"), "hidden")
        self.assertOneError(with_files("references/.notes.md"), "hidden")
        self.assertOneError(with_files(".claude/settings.json"), "hidden")
        self.assertEqual(self.errors(with_files(".skilleval.yaml", "evals/.cache.json")), [])

    def test_extension_allowlist(self):
        self.assertOneError(with_files("references/run.sh"), 'extension ".sh"')
        self.assertOneError(with_files("LICENSE"), "no file extension")
        self.assertEqual(self.errors(with_files("references/page.HTML")), [])
        self.assertEqual(self.errors(with_files("evals/results.log")), [])

    def test_scripts_folder_is_rejected_anywhere(self):
        self.assertOneError(with_files("scripts/run.md"), "scripts/ folders")
        self.assertOneError(with_files("evals/scripts/run.json"), "scripts/ folders")

    def test_shebang_in_published_file(self):
        self.assertOneError(with_files("references/run.md", data=b"#!/bin/sh\necho hi\n"), "starts with #!")


AWS_KEY_ID = "AKIA" + "Q7X2" * 4
PEM_HEADER = "-----BEGIN " + "RSA PRIVATE KEY-----"


class ContentSafetyTests(CheckSkillTestCase):
    def test_access_key_id_anywhere_in_the_folder(self):
        data = f"line one\nkey = {AWS_KEY_ID}\n".encode()
        error = self.assertOneError(with_files("evals/journal.json", data=data), "AWS access key ID")
        self.assertEqual((error.path, error.line), ("evals/journal.json", 2))
        self.assertNotIn(AWS_KEY_ID, error.message)

    def test_documented_example_key_is_allowed(self):
        data = ("AKIA" + "IOSFODNN7EXAMPLE\n").encode()
        self.assertEqual(self.errors(with_files("references/a.md", data=data)), [])

    def test_private_key(self):
        data = f"\n\n{PEM_HEADER}\nMIIB...\n".encode()
        self.assertOneError(with_files("references/a.md", data=data), "private key", line=3)

    def test_invisible_characters(self):
        for char in ("\u200b", "\u202e", "\u2066", "\ufeff", "\U000e0041"):
            with self.subTest(code=hex(ord(char))):
                data = f"fine\nhidden{char}text\n".encode()
                self.assertOneError(with_files("references/a.md", data=data), f"U+{ord(char):04X}", line=2)

    def test_invisible_characters_in_skill_md(self):
        content = skill_md(body="\n# Demo\nignore\u200bprevious\n")
        self.assertOneError(tree(content), "U+200B", line=12)

    def test_active_html_and_insecure_links_warn(self):
        data = b'<script>alert(1)</script>\n<iframe src="x"></iframe>\n[a](javascript:void(0))\n[b](http://example.com)\n'
        skill = with_files("references/a.md", data=data)
        self.assertEqual(self.errors(skill), [])
        messages = " | ".join(w.message for w in self.warnings(skill))
        for fragment in ("<script>", "<iframe>", "javascript:", "http://"):
            self.assertIn(fragment, messages)

    def test_placeholders_and_comments_do_not_warn(self):
        data = b"Returns { data: <object> | null }\n<!-- REPEAT per queue -->\n<details>more</details>\n"
        self.assertEqual(self.warnings(with_files("references/a.md", data=data)), [])



def versioned(version: str = "1.0.0", **files: bytes) -> sc.SkillTree:
    fm = VALID_FRONTMATTER.replace('version: "1.0.0"', f'version: "{version}"')
    return tree(skill_md(fm), **files)


class ContentHashTests(unittest.TestCase):
    def test_hash_is_sha256_over_sorted_path_and_file_digest_records(self):
        import hashlib

        files = {"b.md": b"bee\n", "a/c.md": b"sea\n"}
        expected = hashlib.sha256(
            b"a/c.md\0" + hashlib.sha256(b"sea\n").hexdigest().encode() + b"\n"
            + b"b.md\0" + hashlib.sha256(b"bee\n").hexdigest().encode() + b"\n"
        ).hexdigest()
        self.assertEqual(sc.content_hash(files), expected)

    def test_any_byte_or_path_change_changes_the_hash(self):
        base = sc.content_hash({"a.md": b"x"})
        self.assertNotEqual(base, sc.content_hash({"a.md": b"x "}))
        self.assertNotEqual(base, sc.content_hash({"b.md": b"x"}))


class HistoryTests(unittest.TestCase):
    def history(self, base, head, retired=frozenset()) -> list[sc.Finding]:
        return sc.check_history("demo-skill", base, head, RULES, retired)

    def errors(self, base, head, retired=frozenset()) -> list[str]:
        return [f.message for f in self.history(base, head, retired) if f.severity == "error"]

    def test_unchanged_skill_passes(self):
        self.assertEqual(self.history(versioned(), versioned()), [])

    def test_removed_folder_is_an_error(self):
        (message,) = self.errors(versioned(), None)
        self.assertIn('set metadata.deprecated: "true"', message)

    def test_new_skill_passes_unless_its_path_was_retired(self):
        self.assertEqual(self.history(None, versioned()), [])
        (message,) = self.errors(None, versioned(), retired=frozenset({"demo-skill"}))
        self.assertIn("was used by a skill that was removed", message)

    def test_content_change_needs_a_higher_version(self):
        base = versioned("1.0.0", **{"references/a.md": b"one\n"})
        head = versioned("1.0.0", **{"references/a.md": b"two\n"})
        (message,) = self.errors(base, head)
        self.assertIn("metadata.version must go up from 1.0.0", message)
        finding = next(f for f in self.history(base, head) if f.severity == "error")
        self.assertEqual((finding.path, finding.line), ("SKILL.md", 6))

    def test_readme_is_published_so_it_needs_a_bump(self):
        base = versioned("1.0.0", **{"README.md": b"# Demo\n"})
        head = versioned("1.0.0", **{"README.md": b"# Demo, fixed\n"})
        self.assertEqual(len(self.errors(base, head)), 1)

    def test_unpublished_changes_need_no_bump(self):
        base = versioned("1.0.0", **{"CHANGELOG.md": b"a\n", "evals/evals.json": b"{}\n"})
        head = versioned("1.0.0", **{"CHANGELOG.md": b"b\n", "evals/evals.json": b"[]\n", ".skilleval.yaml": b"x\n"})
        self.assertEqual(self.history(base, head), [])

    def test_version_must_never_go_down(self):
        (message,) = self.errors(versioned("1.2.0"), versioned("1.1.9"))
        self.assertIn("went down from 1.2.0 to 1.1.9", message)

    def test_bump_with_changelog_passes(self):
        base = versioned("1.0.0", **{"CHANGELOG.md": b"## 1.0.0\n"})
        head = versioned("1.1.0", **{"CHANGELOG.md": b"## 1.1.0\n## 1.0.0\n"})
        self.assertEqual(self.history(base, head), [])

    def test_bump_without_changelog_change_warns(self):
        base = versioned("1.0.0", **{"CHANGELOG.md": b"## 1.0.0\n"})
        head = versioned("1.0.1", **{"CHANGELOG.md": b"## 1.0.0\n"})
        (finding,) = self.history(base, head)
        self.assertEqual(finding.severity, "warning")
        self.assertIn("CHANGELOG.md", finding.message)

    def test_two_part_base_version_is_compared_as_patch_zero(self):
        self.assertEqual(self.errors(versioned("2.6"), versioned("2.6.1", **{"CHANGELOG.md": b"x\n"})), [])
        self.assertEqual(len(self.errors(versioned("2.6"), versioned("2.6.0"))), 1)

    def test_unreadable_base_version_skips_the_version_rules_with_a_warning(self):
        (finding,) = self.history(versioned("latest"), versioned("1.0.0"))
        self.assertEqual(finding.severity, "warning")
        self.assertIn("were not checked", finding.message)

    def test_invalid_head_version_is_left_to_check_skill(self):
        self.assertEqual(self.history(versioned("1.0.0"), versioned("1.0")), [])


class ParseVersionTests(unittest.TestCase):
    def test_strict_and_lenient(self):
        self.assertEqual(sc.parse_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(sc.parse_version("2.6"))
        self.assertEqual(sc.parse_version("2.6", allow_two_part=True), (2, 6, 0))
        self.assertIsNone(sc.parse_version("1.2.3-rc.1", allow_two_part=True))


class LoadRulesTests(unittest.TestCase):
    def test_display_mapping_covers_every_display_agent_type(self):
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules", "!*.md\n")
        self.assertEqual(set(rules.display_agent_types), set(rules.vocabulary["agent-types"]))
        self.assertEqual(rules.display_agent_types["Incident RCA"], ("INCIDENT_RCA",))

    def test_repository_rule_files_load(self):
        gitignore = (ROOT / "skills" / ".gitignore").read_text(encoding="utf-8")
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules", gitignore)
        self.assertEqual(
            rules.allowed_extensions,
            frozenset("md txt json yaml yml xml csv tsv html htm png jpg jpeg gif svg webp pdf".split()),
        )
        self.assertIn("evals/", rules.published_excludes)
        self.assertIn("GENERIC", rules.agent_types)
        self.assertIn("Amazon CloudWatch", rules.vocabulary["aws-services"])
        self.assertEqual(rules.aliases["CloudWatch"], "Amazon CloudWatch")
        for value, target in rules.aliases.items():
            self.assertNotIn(value, rules.vocabulary["aws-services"] | rules.vocabulary["technical-domains"])
            self.assertTrue(any(target in values for values in rules.vocabulary.values()), target)


class LoadRulesValidationTests(unittest.TestCase):
    def rules_dir(self, agent_types, vocabulary) -> Path:
        import json
        import tempfile

        target = Path(tempfile.mkdtemp())
        self.addCleanup(__import__("shutil").rmtree, target)
        source = ROOT / ".github" / "scripts" / "skill-rules"
        for name in source.iterdir():
            (target / name.name).write_bytes(name.read_bytes())
        if agent_types is not None:
            (target / "agent-types.json").write_text(json.dumps(agent_types), encoding="utf-8")
        if vocabulary is not None:
            (target / "vocabulary.json").write_text(json.dumps(vocabulary), encoding="utf-8")
        return target

    def test_string_where_a_list_is_expected_fails_closed(self):
        vocabulary = {"values": {"agent-types": "Chat tasks", "aws-services": [], "technical-domains": []}, "aliases": {}}
        with self.assertRaisesRegex(ValueError, "list of non-empty strings"):
            sc.load_rules(self.rules_dir(None, vocabulary), "!*.md\n")
        with self.assertRaisesRegex(ValueError, "list of non-empty strings"):
            sc.load_rules(self.rules_dir({"values": "GENERIC"}, None), "!*.md\n")

    def test_display_mapping_fails_closed(self):
        agent_types = {"values": ["GENERIC", "CHAT"]}
        vocabulary = {"values": {"agent-types": ["Chat tasks"], "aws-services": [], "technical-domains": []}, "aliases": {}}
        cases = {
            "one entry for each agent-types value": {**agent_types, "display_mapping": {}},
            "unknown values": {**agent_types, "display_mapping": {"Chat tasks": ["PAGER"]}},
            "list of non-empty strings": {**agent_types, "display_mapping": {"Chat tasks": "CHAT"}},
        }
        for fragment, data in cases.items():
            with self.subTest(fragment=fragment):
                with self.assertRaisesRegex(ValueError, fragment):
                    sc.load_rules(self.rules_dir(data, vocabulary), "!*.md\n")

    def test_aliases_must_map_strings_to_strings(self):
        vocabulary = {"values": {"agent-types": [], "aws-services": [], "technical-domains": []}, "aliases": {"a": 1}}
        with self.assertRaisesRegex(ValueError, "aliases"):
            sc.load_rules(self.rules_dir(None, vocabulary), "!*.md\n")


class ConformanceTests(unittest.TestCase):
    def write_cases(self, cases) -> Path:
        import tempfile

        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write(__import__("json").dumps({"cases": cases}))
        return Path(handle.name)

    def test_repository_cases_give_their_expected_results(self):
        gitignore = (ROOT / "skills" / ".gitignore").read_text(encoding="utf-8")
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules", gitignore)
        cases = sc.load_cases(ROOT / ".github" / "scripts" / "skill-rules" / "conformance-cases.json")
        self.assertEqual(sc.run_conformance(cases, rules), [])

    def test_malformed_case_files_are_rejected(self):
        files = {"SKILL.md": {"text": "x"}}
        bad = {
            "duplicate id": [{"id": "a", "name": "d", "expect": "pass", "files": files}] * 2,
            'needs an "error"': [{"id": "a", "name": "d", "expect": "fail", "files": files}],
            'exactly one of "text" or "base64"': [{"id": "a", "name": "d", "expect": "pass", "files": {"x": {}}}],
            '"expect" must be': [{"id": "a", "name": "d", "expect": "maybe", "files": files}],
        }
        for fragment, cases in bad.items():
            with self.subTest(fragment=fragment):
                with self.assertRaisesRegex(ValueError, fragment.replace("(", r"\(")):
                    sc.load_cases(self.write_cases(cases))

    def test_wrong_expectation_is_reported(self):
        case = {"id": "a", "name": "demo-skill", "expect": "fail", "error": "nope", "files": {"SKILL.md": {"text": skill_md().decode()}}}
        problems = sc.run_conformance([case], RULES)
        self.assertEqual(len(problems), 1)
        self.assertIn("expected an error containing 'nope', got: no errors", problems[0])


class GitignoreAllowlistTests(unittest.TestCase):
    def test_reads_extension_lines_only(self):
        text = "*\n!*/\n!.gitignore\n# comment\n!*.md\n!*.PNG\n**/scripts/\n"
        self.assertEqual(sc.allowed_extensions_from_gitignore(text), frozenset({"md", "png"}))

    def test_empty_allowlist_fails_closed(self):
        with self.assertRaises(ValueError):
            sc.allowed_extensions_from_gitignore("*\n")


if __name__ == "__main__":
    unittest.main()
