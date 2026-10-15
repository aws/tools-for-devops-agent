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
)

VALID_FRONTMATTER = """\
name: demo-skill
description: Use this skill when testing the skill publishing check.
metadata:
  author: octocat
  version: "1.0.0"
  aws-devops-agent-skills.agent-types: "Chat tasks"
  summary: "Checks a demo skill."
  agent_types: "CHAT"
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
        "agent_types": '"CHAT"',
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

    def assertOneError(
        self, skill: sc.SkillTree, fragment: str, line: int | None = None, *, also: tuple[str, ...] = ()
    ) -> sc.Finding:
        """Exactly one error contains `fragment`, and the only other errors are the ones `also` names."""
        errors = self.errors(skill)
        messages = [f.message for f in errors]
        matching = [f for f in errors if fragment in f.message]
        self.assertEqual(len(matching), 1, f"want one error containing {fragment!r}; got {messages}")
        others = [m for m in messages if fragment not in m]
        self.assertEqual(len(others), len(also), f"unexpected extra errors: {others}")
        for extra in also:
            self.assertTrue(any(extra in m for m in others), f"no extra error containing {extra!r}; got {others}")
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
        self.assertOneError(tree(content), "not valid YAML", line=10)

    def test_anchor_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("author: octocat", "author: &who octocat")
        self.assertOneError(tree(skill_md(fm)), "anchors", line=5)

    def test_alias_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("author: octocat", "author: &who octocat") + "license: *who\n"
        self.assertOneError(tree(skill_md(fm)), "aliases", also=("anchors",))

    def test_tag_is_rejected(self):
        fm = VALID_FRONTMATTER.replace('version: "1.0.0"', "version: !!str 1.0.0")
        self.assertOneError(tree(skill_md(fm)), "tags", line=6)

    def test_flow_collection_is_rejected(self):
        fm = VALID_FRONTMATTER + "allowed-tools: [read, write]\n"
        self.assertOneError(tree(skill_md(fm)), "flow collections", line=10)

    def test_frontmatter_must_be_a_mapping(self):
        self.assertOneError(tree(b"---\n- one\n- two\n---\n"), "must be a mapping")

    def test_duplicate_key_reports_second_line(self):
        fm = VALID_FRONTMATTER + "name: demo-skill\n"
        self.assertOneError(tree(skill_md(fm)), 'duplicate key "name"', line=10)

    def test_duplicate_metadata_key(self):
        fm = VALID_FRONTMATTER + '  version: "1.0.1"\n'
        self.assertOneError(tree(skill_md(fm)), 'duplicate key "metadata.version"', line=10)

    def test_non_string_key_is_rejected(self):
        fm = VALID_FRONTMATTER + "1: one\n"
        self.assertOneError(tree(skill_md(fm)), "keys must be plain text")

    def test_unknown_top_level_key_is_a_warning(self):
        fm = VALID_FRONTMATTER + "owner: someone\n"
        warnings = self.warnings(tree(skill_md(fm)))
        self.assertEqual(len(warnings), 1)
        self.assertIn('unknown top-level key "owner"', warnings[0].message)
        self.assertEqual(self.errors(tree(skill_md(fm))), [])
        (warning,) = self.warnings(tree(skill_md(VALID_FRONTMATTER + "licence: MIT\n")))
        self.assertIn('unknown top-level key "licence" (did you mean "license"?)', warning.message)

    def test_keys_must_be_plain_text_at_any_depth(self):
        for key in ("1e3", "true", "~", "1"):
            with self.subTest(key=key):
                fm = VALID_FRONTMATTER + f"extra:\n  {key}: one\n"
                self.assertOneError(tree(skill_md(fm)), "keys must be plain text", line=11)
        self.assertEqual(self.errors(tree(skill_md(VALID_FRONTMATTER + 'extra:\n  "1e3": one\n'))), [])

    def test_duplicate_keys_are_rejected_at_any_depth(self):
        for extra, line in (("extra:\n  a: one\n  a: two\n", 12), ("extra:\n  - a: one\n    a: two\n", 12)):
            with self.subTest(extra=extra):
                self.assertOneError(tree(skill_md(VALID_FRONTMATTER + extra)), 'duplicate key "extra.a"', line=line)

    def test_line_breaks_other_parsers_dont_see_are_rejected(self):
        for char in ("\u2028", "\u2029", "\x85"):
            with self.subTest(code=hex(ord(char))):
                fm = VALID_FRONTMATTER.replace('  agent_types: "CHAT"\n', f'  agent_types: "CHAT"{char}  deprecated: "true"\n')
                self.assertOneError(tree(skill_md(fm)), f"U+{ord(char):04X}, which YAML parsers disagree on", line=9)

    def test_triple_dash_inside_the_frontmatter_is_rejected(self):
        fm = VALID_FRONTMATTER.replace("testing the skill publishing check.", "testing --- the publishing check.")
        self.assertOneError(tree(skill_md(fm)), 'contains "---"', line=3)

    def test_directives_and_document_markers_are_rejected(self):
        self.assertOneError(tree(b"---\n%YAML 1.1\n--- # start\n" + skill_md()[4:]), "directives (%)", also=("document markers",))
        self.assertOneError(tree(skill_md(VALID_FRONTMATTER + "...\n")), "document markers", line=10)

    def test_empty_frontmatter_is_named(self):
        for content in (b"---\n\n---\n# Demo\n", b"---\n---\n# Demo\n"):
            with self.subTest(content=content):
                self.assertOneError(tree(content), "the frontmatter is empty")


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
        self.assertOneError(tree(skill_md(fm)), "lowercase letters, digits and single hyphens", also=("they must match",))

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
        self.assertOneError(tree(skill_md(fm)), '"metadata.extra" must be text, not a mapping', line=10)

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

    def test_misspelled_prefix_is_an_error(self):
        for key in (
            "aws-devops-agent-skill.aws-services",
            "AWS-DevOps-Agent-Skills.aws-services",
            "aws_devops_agent_skills.aws-services",
            "aws-devops-agent-skils.aws-services",
            "aws-devops-agnet-skills.aws-services",
            "devops-agent-skills.aws-services",
            "aws-devops-agent-skills:aws-services",
        ):
            with self.subTest(key=key):
                skill = tree(skill_md(frontmatter_with(**{key: '"Amazon EKS"'})))
                self.assertOneError(skill, "misspells the aws-devops-agent-skills. prefix")
                self.assertEqual(self.warnings(skill), [])

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

    def test_missing_agent_types_warns_that_the_skill_loads_for_every_agent(self):
        skill = tree(skill_md(frontmatter_with(agent_types=None)))
        self.assertEqual(self.errors(skill), [])
        (warning,) = self.warnings(skill)
        self.assertIn("installs as GENERIC and loads for every agent", warning.message)
        self.assertEqual(warning.line, 4)

    def test_the_display_tag_does_not_set_agent_types(self):
        fm = frontmatter_with(agent_types=None, **{"aws-devops-agent-skills.agent-types": '"Chat tasks"'})
        (warning,) = self.warnings(tree(skill_md(fm)))
        self.assertIn('"metadata.agent_types" is not set', warning.message)

    def test_explicit_generic_does_not_warn(self):
        fm = frontmatter_with(agent_types='"GENERIC"', **{"aws-devops-agent-skills.agent-types": None})
        self.assertEqual(self.check(tree(skill_md(fm)))[0], [])


class LimitsAndTierTests(CheckSkillTestCase):
    def test_index_is_a_reserved_name(self):
        fm = frontmatter_with().replace("name: demo-skill", "name: index")
        self.assertOneError(tree(skill_md(fm), name="index"), "reserved for the skill catalog's index", line=2)

    def test_a_very_long_version_part_is_an_error_not_a_crash(self):
        fm = frontmatter_with(version='"1.' + "9" * 4301 + '.0"')
        self.assertOneError(tree(skill_md(fm)), "each part can have at most 10 digits")

    def test_version_length_limits(self):
        for bad in ('"1.0.12345678901"', '"12345678901.0.0"'):
            with self.subTest(bad=bad):
                self.assertOneError(tree(skill_md(frontmatter_with(version=bad))), "at most 10 digits", line=6)
        long_version = '"' + ".".join(["1234567890"] * 3) + '"'  # 32 characters, 10 digits each: allowed
        self.assertEqual(self.errors(tree(skill_md(frontmatter_with(version=long_version)))), [])

    def test_tier_values(self):
        for good in ('"aws-managed"', '"partner-managed"'):
            with self.subTest(good=good):
                self.assertEqual(self.errors(tree(skill_md(frontmatter_with(tier=good)))), [])
        self.assertOneError(tree(skill_md(frontmatter_with(tier='"community"'))), '"metadata.tier" must be')
        self.assertOneError(tree(skill_md(frontmatter_with(tier='"AWS-managed"'))), '"metadata.tier" must be')

    def test_spec_text_fields_must_not_be_empty(self):
        for key in ("license", "compatibility", "allowed-tools"):
            with self.subTest(key=key):
                fm = frontmatter_with().replace("metadata:\n", f'{key}: ""\nmetadata:\n')
                self.assertOneError(tree(skill_md(fm)), f'"{key}" must not be empty', line=4)

    def test_compatibility_limit(self):
        fm = frontmatter_with().replace("metadata:\n", f"compatibility: {'c' * 501}\nmetadata:\n")
        self.assertOneError(tree(skill_md(fm)), '"compatibility" is 501 characters; the limit is 500')
        fm = frontmatter_with().replace("metadata:\n", f"compatibility: {'c' * 500}\nmetadata:\n")
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_byte_order_mark_is_named(self):
        content = "\ufeff".encode() + skill_md()
        self.assertOneError(tree(content), "byte order mark", line=1)

    def test_tab_anywhere_in_the_frontmatter_is_rejected(self):
        for value, line in (('"Checks\ta demo skill."', 8), (">-\n    Checks\ta demo skill.", 9)):
            with self.subTest(value=value):
                self.assertOneError(tree(skill_md(frontmatter_with(summary=value))), "tab character", line=line)

    def test_a_key_with_no_value_says_so(self):
        fm = frontmatter_with().replace("metadata:\n", "license:\nmetadata:\n")
        error = self.assertOneError(tree(skill_md(fm)), '"license" has no value; give it a value or remove the key')
        self.assertNotIn("Put the value in quotes", error.message)
        error = self.assertOneError(tree(skill_md(frontmatter_with(author=""))), '"metadata.author" has no value')
        self.assertNotIn("remove the key", error.message)

    def test_special_yaml_values_are_named(self):
        fm = frontmatter_with().replace("metadata:\n", "license: =\nmetadata:\n")
        self.assertOneError(tree(skill_md(fm)), '"license" must be text, not a special YAML value')

    def test_values_other_parsers_read_as_numbers_must_be_quoted(self):
        for value in ("1e3", "-1.0e3", "+.5", "0o17", "+0o17", "1_0e3", "._5", "1_0.5e3"):
            with self.subTest(value=value):
                fm = frontmatter_with().replace("metadata:\n", f"title: {value}\nmetadata:\n")
                self.assertOneError(tree(skill_md(fm)), "other YAML parsers read")
        fm = frontmatter_with().replace("metadata:\n", 'title: "1e3"\nmetadata:\n')
        self.assertEqual(self.errors(tree(skill_md(fm))), [])

    def test_empty_title_is_rejected(self):
        fm = frontmatter_with().replace("metadata:\n", 'title: "  "\nmetadata:\n')
        self.assertOneError(tree(skill_md(fm)), '"title" must not be empty')

    def test_empty_summary_counts_as_missing(self):
        for value in ('""', '"   "'):
            with self.subTest(value=value):
                skill = tree(skill_md(frontmatter_with(summary=value)))
                self.assertEqual(self.errors(skill), [])
                (warning,) = self.warnings(skill)
                self.assertIn('"metadata.summary" is empty', warning.message)
                self.assertEqual(warning.line, 8)

    def test_non_text_values_do_not_also_warn_as_missing(self):
        fm = frontmatter_with(agent_types="\n    - CHAT", summary="\n    - one")
        skill = tree(skill_md(fm))
        self.assertEqual(sorted(f.message.split('"')[1] for f in self.errors(skill)), ["metadata.agent_types", "metadata.summary"])
        self.assertEqual(self.warnings(skill), [])

    def test_unknown_metadata_key_warns_with_a_suggestion(self):
        skill = tree(skill_md(frontmatter_with(deprecate='"true"')))
        self.assertEqual(self.errors(skill), [])
        (warning,) = self.warnings(skill)
        self.assertIn('unknown metadata key "deprecate"; did you mean "deprecated"?', warning.message)

    def test_long_body_is_a_warning(self):
        # A blank line and 499 lines, each ending in a newline. The skill evaluation
        # tool also counts the empty piece after the last newline, so 501.
        body = "\n" + "".join(f"Line {i}.\n" for i in range(499))
        skill = tree(skill_md(body=body))
        self.assertEqual(self.errors(skill), [])
        (warning,) = self.warnings(skill)
        self.assertIn("the SKILL.md body is 501 lines", warning.message)
        self.assertEqual(self.warnings(tree(skill_md(body="\n" + "x\n" * 498))), [])


class ParseVersionTests(unittest.TestCase):
    def test_a_very_long_part_is_rejected_not_a_crash(self):
        self.assertIsNone(sc.parse_version("1." + "9" * 4301 + ".0"))

    def test_only_major_minor_patch_parses(self):
        self.assertEqual(sc.parse_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(sc.parse_version("2.6"))
        self.assertIsNone(sc.parse_version("1.2.3-rc.1"))


class LoadRulesTests(unittest.TestCase):
    def test_repository_rule_files_load(self):
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules")
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
            sc.load_rules(self.rules_dir(None, vocabulary))
        with self.assertRaisesRegex(ValueError, "list of non-empty strings"):
            sc.load_rules(self.rules_dir({"values": "GENERIC"}, None))

    def test_aliases_must_map_strings_to_strings(self):
        vocabulary = {"values": {"agent-types": [], "aws-services": [], "technical-domains": []}, "aliases": {"a": 1}}
        with self.assertRaisesRegex(ValueError, "aliases"):
            sc.load_rules(self.rules_dir(None, vocabulary))


class ConformanceTests(unittest.TestCase):
    def write_cases(self, cases) -> Path:
        import tempfile

        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        self.addCleanup(Path(handle.name).unlink)
        with handle:
            handle.write(__import__("json").dumps({"cases": cases}))
        return Path(handle.name)

    def test_repository_cases_give_their_expected_results(self):
        rules = sc.load_rules(ROOT / ".github" / "scripts" / "skill-rules")
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


if __name__ == "__main__":
    unittest.main()
