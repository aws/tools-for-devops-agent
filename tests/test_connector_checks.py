"""Unit tests for .github/scripts/connector_checks.py.

Each test builds connector folders in memory and runs the rules on them, so no
Git repository is needed. Run with:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import connector_checks as cc  # noqa: E402
import skill_checks as sc  # noqa: E402

CASES_FILE = ROOT / ".github" / "scripts" / "skill-rules" / cc.CONFORMANCE_FILE

CONNECTOR = """\
schema_version: 1
name: acme
version: 1.0.0
type: mcp
mcp:
  endpoints:
    - { label: EU, endpoint: "https://eu.acme.example/mcp" }
    - { label: US, endpoint: "https://us.acme.example/mcp" }
  auth:
    - type: api_key
      headers:
        - { header: Authorization, label: API key, prefix: "Bearer " }
    - type: oauth_3lo
      authorization_url: "https://login.acme.example/authorize"
      exchange_url: "https://login.acme.example/token"
      pkce: true
"""
VERSION_LINE = 3
API_KEY_OPTION = '    - type: api_key\n      headers:\n        - { header: Authorization, label: API key, prefix: "Bearer " }\n'


def tree(files: dict[str, bytes]) -> sc.SkillTree:
    return sc.SkillTree("acme", {path: sc.Entry(path, "100644", data) for path, data in files.items()})


def folder(version: str = "1.0.0", text: str = CONNECTOR, **files: bytes) -> sc.SkillTree:
    """A connector folder whose connector.yaml is `text` at `version`."""
    assert "version: 1.0.0\n" in text
    connector_yaml = text.replace("version: 1.0.0\n", f"version: {version}\n", 1).encode("utf-8")
    return tree({"connector.yaml": connector_yaml, "logo.svg": b"<svg/>\n", "README.md": b"# Acme\n", **files})


def changed(version: str, old: str, new: str) -> sc.SkillTree:
    assert old in CONNECTOR, old
    return folder(version, CONNECTOR.replace(old, new))


def messages(findings, severity: str = "error") -> list[str]:
    return [f.message for f in findings if f.severity == severity]


class ConformanceTests(unittest.TestCase):
    def test_repository_cases_give_their_expected_results(self):
        self.assertEqual(cc.run_conformance(sc.load_cases(CASES_FILE)), [])


class ReadDocumentTests(unittest.TestCase):
    def test_values_are_typed_as_the_catalog_publisher_types_them(self):
        text = (
            'a: true\nb: false\nc: null\nd: ~\ne:\nf: 3\ng: -0.25\nh: "3"\ni: 1.0.0\nj: [x, 2, {k: true}]\n'
            "l: |\n  yes\n"
        )
        expected = {
            "a": True, "b": False, "c": None, "d": None, "e": None, "f": 3, "g": -0.25, "h": "3",
            "i": "1.0.0", "j": ["x", 2, {"k": True}], "l": "yes\n",
        }
        document = cc.read_document(text.encode("utf-8"))
        self.assertTrue(cc.same(document.value, expected), document.value)
        self.assertEqual(document.lines["a"], 1)
        self.assertEqual(document.lines["l"], 11)

    def test_yaml_that_breaks_a_rule_is_unreadable_unless_lenient(self):
        text = b"name: acme\nversion: 1.0.0\nreleased: 2026-11-10\n"
        self.assertIsNone(cc.read_document(text))
        lenient = cc.read_document(text, strict=False)
        self.assertEqual(lenient.get("version"), "1.0.0")
        for unreadable in (b"name: [acme\n", b"name: \xff\n", None):
            with self.subTest(unreadable=unreadable):
                self.assertIsNone(cc.read_document(unreadable, strict=False))

    def test_values_compare_strictly(self):
        self.assertFalse(cc.same(True, 1))
        self.assertFalse(cc.same(1, "1"))
        self.assertFalse(cc.same(None, cc.ABSENT))
        self.assertFalse(cc.same([1, 2], [2, 1]))
        self.assertTrue(cc.same({"a": 1, "b": [None]}, {"b": [None], "a": 1}))
        self.assertTrue(cc.same(cc.ABSENT, cc.ABSENT))


class CheckConnectorTests(unittest.TestCase):
    def test_a_valid_connector_passes(self):
        self.assertEqual(cc.check_connector("acme", folder()), [])

    def test_connector_yaml_is_required(self):
        findings = cc.check_connector("acme", tree({"README.md": b"# Acme\n"}))
        self.assertEqual(messages(findings), ["connectors/acme/ has no connector.yaml; every connector folder needs one"])

    def test_the_version_must_be_major_minor_patch_text(self):
        for version in ('"1.1"', '"v1.0.0"', '"1.0.0-beta"', '"01.0.0"', '"12345678901.0.0"', "1"):
            with self.subTest(version=version):
                findings = cc.check_connector("acme", folder(version))
                self.assertEqual(len(messages(findings)), 1, findings)
                expected = f'"version" is {version}; it must be MAJOR.MINOR.PATCH'
                self.assertTrue(findings[0].message.startswith(expected), findings[0].message)
                self.assertEqual(findings[0].line, VERSION_LINE)

    def test_a_missing_version_is_required(self):
        findings = cc.check_connector("acme", tree({"connector.yaml": b"name: acme\n"}))
        self.assertEqual(messages(findings), ['"version" is required, such as version: 1.0.0'])
        self.assertIsNone(findings[0].line)

    def test_a_document_that_is_not_a_mapping_is_an_error(self):
        # An empty file, or one of only comments, holds no document, which isn't a mapping either.
        for text in (b"- acme\n", b"", b"# comment\n"):
            with self.subTest(text=text):
                findings = cc.check_connector("acme", tree({"connector.yaml": text}))
                self.assertEqual(messages(findings), ["connector.yaml must be a mapping of keys to values, such as name: acme"])
                self.assertEqual(findings[0].line, 1)

    def test_yaml_problems_are_left_to_the_yaml_check(self):
        self.assertEqual(cc.check_connector("acme", tree({"connector.yaml": b"name: [acme\n"})), [])

    def test_the_name_is_the_folder_name(self):
        findings = cc.check_connector("acme", folder(text=CONNECTOR.replace("name: acme", "name: acme-cloud")))
        self.assertEqual(
            messages(findings),
            ['"name" is "acme-cloud" but the folder is "acme"; they must match, because a connector\'s folder is its identity'],
        )
        self.assertEqual(findings[0].line, 2)
        findings = cc.check_connector("acme", folder(text=CONNECTOR.replace("name: acme\n", "")))
        self.assertEqual(messages(findings), ['"name" is required, and it must be the folder name: name: acme'])
        self.assertEqual(cc.check_connector("acme", folder(text=CONNECTOR.replace("name: acme", 'name: "acme"'))), [])

    def test_the_folder_name_is_a_capability_name(self):
        for name in ("Acme", "acme_cloud", "acme--cloud", "-acme", "a" * 65):
            with self.subTest(name=name):
                findings = cc.check_connector(name, folder(text=CONNECTOR.replace("name: acme", f"name: {name}")))
                self.assertEqual(len(messages(findings)), 1, findings)
                self.assertIn("must be lowercase letters, digits and single hyphens, at most 64", findings[0].message)
                self.assertIsNone(findings[0].path)
        self.assertEqual(cc.check_connector("a" * 64, folder(text=CONNECTOR.replace("name: acme", f"name: {'a' * 64}"))), [])

    def test_deprecated_is_a_boolean_not_text(self):
        """The catalog publisher's schema refuses any other value, as its skill check does for metadata.deprecated."""
        for value in ("true", "false"):
            with self.subTest(value=value):
                self.assertEqual(cc.check_connector("acme", folder(text=CONNECTOR + f"deprecated: {value}\n")), [])
        message = '"deprecated" must be true or false, without quotes, because the catalog reads it as a boolean'
        quoted = (('"true"', "; write deprecated: true"), ('"False"', "; write deprecated: false"))
        for value, hint in quoted + (('"yes"', ""), ("1", ""), ("", "")):
            with self.subTest(value=value):
                findings = cc.check_connector("acme", folder(text=CONNECTOR + f"deprecated: {value}\n"))
                self.assertEqual(messages(findings), [message + hint])
                self.assertEqual((findings[0].path, findings[0].line), ("connector.yaml", CONNECTOR.count("\n") + 1))

    def test_index_is_reserved_for_the_catalog(self):
        findings = cc.check_connector("index", folder(text=CONNECTOR.replace("name: acme", "name: index")))
        self.assertEqual(
            messages(findings), ["the folder name connectors/index is reserved for the connector catalog's index; use another name"]
        )
        self.assertIsNone(findings[0].path)


class ReferencesTests(unittest.TestCase):
    def references(self, extra: str, connectors=("acme", "bravo"), skills=("alpha",)) -> list[sc.Finding]:
        return cc.check_references(folder(text=CONNECTOR + extra), set(connectors), set(skills))

    def test_each_skill_is_a_skill_folder(self):
        findings = self.references("skills: [alpha, ghost, alpha, ghost, 3]\n")
        self.assertEqual(messages(findings), ['"skills" lists "ghost", which isn\'t a skill folder in skills/'])
        self.assertEqual((findings[0].path, findings[0].line), ("connector.yaml", CONNECTOR.count("\n") + 1))
        self.assertEqual(self.references("skills: [alpha]\n"), [])
        self.assertEqual(self.references("skills: alpha\n"), [])  # Not a list: validate_skills.py warns.

    def test_the_replacement_is_a_connector_folder(self):
        findings = self.references("deprecated: true\nreplacement: charlie\n")
        self.assertEqual(messages(findings), ['"replacement" is "charlie", which isn\'t a connector folder in connectors/'])
        self.assertEqual(findings[0].line, CONNECTOR.count("\n") + 2)
        self.assertEqual(self.references("deprecated: true\nreplacement: bravo\n"), [])

    def test_a_connector_yaml_that_cannot_be_read_is_left_to_the_other_rules(self):
        for data in (b"skills: [ghost\n", b"- ghost\n"):
            with self.subTest(data=data):
                self.assertEqual(cc.check_references(tree({"connector.yaml": data}), {"acme"}, set()), [])
        self.assertEqual(cc.check_references(tree({"README.md": b"# Acme\n"}), {"acme"}, set()), [])


class HistoryTests(unittest.TestCase):
    def test_an_unchanged_connector_passes(self):
        self.assertEqual(cc.check_history("acme", folder(), folder()), [])

    def test_a_removed_folder_is_an_error(self):
        self.assertIn("set deprecated: true", messages(cc.check_history("acme", folder(), None))[0])

    def test_a_breaking_change_at_the_same_version_names_the_major_version_it_needs(self):
        findings = cc.check_history("acme", folder(), changed("1.0.0", "label: API key", "label: Team API key"))
        self.assertEqual(
            messages(findings),
            [
                'files in connectors/acme/ changed, so version must go up from 1.0.0, to 2.0.0 because the "api_key" '
                "option in mcp.auth was removed or changed. Every file in a connector folder is published, and a "
                "published version never changes"
            ],
        )
        self.assertEqual(findings[0].line, VERSION_LINE)

    def test_any_changed_file_needs_a_higher_version(self):
        for head in (
            folder(**{"logo.svg": b"<svg></svg>\n"}),
            folder(**{"README.md": b"# Acme Cloud\n"}),
            folder(**{"logo-dark.svg": b"<svg/>\n"}),
            folder(text="# A comment.\n" + CONNECTOR),
        ):
            with self.subTest(files=sorted(head.entries)):
                findings = cc.check_history("acme", folder(), head)
                self.assertEqual(len(messages(findings)), 1, findings)
                self.assertIn("so version must go up from 1.0.0", findings[0].message)
                version_line = head.entries["connector.yaml"].data.decode().splitlines().index("version: 1.0.0") + 1
                self.assertEqual((findings[0].path, findings[0].line), ("connector.yaml", version_line))

    def test_a_removed_file_needs_a_higher_version_too(self):
        head = folder()
        del head.entries["README.md"]
        self.assertIn("so version must go up", messages(cc.check_history("acme", folder(), head))[0])

    def test_the_version_never_goes_down(self):
        findings = cc.check_history("acme", folder("1.10.0"), folder("1.9.0"))
        self.assertEqual(messages(findings), ["version went down from 1.10.0 to 1.9.0; it must never go down"])

    def test_name_and_type_never_change(self):
        head = folder("2.0.0", CONNECTOR.replace("name: acme", "name: acme-cloud").replace("type: mcp", "type: rest"))
        findings = cc.check_history("acme", folder(), head)
        self.assertEqual(
            messages(findings),
            [
                '"name" changed from "acme" to "acme-cloud"; a connector\'s name never changes, so set it back',
                '"type" changed from "mcp" to "rest"; a connector\'s type never changes, so set it back',
            ],
        )
        self.assertEqual([f.line for f in findings], [2, 4])

    def test_breaking_changes_need_a_new_major_version(self):
        api_key_changed = 'the "api_key" option in mcp.auth was removed or changed'
        cases = (
            (api_key_changed, "label: API key", "label: Team API key"),
            (api_key_changed, API_KEY_OPTION, ""),
            ('the "oauth_3lo" option in mcp.auth was removed or changed', "pkce: true", 'pkce: "true"'),
            (
                'the mcp.endpoints entry "US" was removed or its URL changed',
                '    - { label: US, endpoint: "https://us.acme.example/mcp" }\n',
                "",
            ),
            (
                'the mcp.endpoints entry "EU" was removed or its URL changed',
                "https://eu.acme.example/mcp",
                "https://eu.acme.example/v2/mcp",
            ),
            (
                'the mcp.config field "team" was added',
                "  auth:\n",
                '  config:\n    - { name: team, label: Team, pattern: "^[a-z]{1,8}$" }\n  auth:\n',
            ),
        )
        for reason, old, new in cases:
            with self.subTest(reason=reason, old=old):
                for version in ("1.0.1", "1.1.0"):
                    findings = cc.check_history("acme", folder(), changed(version, old, new))
                    self.assertEqual(len(messages(findings)), 1, findings)
                    self.assertTrue(
                        findings[0].message.startswith(f"{reason}, which needs a new major version: 2.0.0, not {version}"),
                        findings[0].message,
                    )
                    self.assertEqual(findings[0].line, VERSION_LINE)
                self.assertEqual(cc.check_history("acme", folder(), changed("2.0.0", old, new)), [])

    def test_an_added_endpoint_changes_an_auth_option_that_gives_its_urls_per_endpoint(self):
        """The catalog needs a key for every endpoint label in such a map, so adding an endpoint needs a major version."""
        per_endpoint = CONNECTOR.replace(
            '      exchange_url: "https://login.acme.example/token"\n',
            '      exchange_url:\n        EU: "https://eu.login.acme.example/token"\n'
            '        US: "https://us.login.acme.example/token"\n',
        )
        added = per_endpoint.replace(
            '    - { label: US, endpoint: "https://us.acme.example/mcp" }\n',
            '    - { label: US, endpoint: "https://us.acme.example/mcp" }\n'
            '    - { label: AP, endpoint: "https://ap.acme.example/mcp" }\n',
        ).replace(
            '        US: "https://us.login.acme.example/token"\n',
            '        US: "https://us.login.acme.example/token"\n        AP: "https://ap.login.acme.example/token"\n',
        )
        findings = cc.check_history("acme", folder("1.0.0", per_endpoint), folder("1.1.0", added))
        self.assertEqual(
            [m.split(",")[0] for m in messages(findings)], ['the "oauth_3lo" option in mcp.auth was removed or changed']
        )
        self.assertEqual(cc.check_history("acme", folder("1.0.0", per_endpoint), folder("2.0.0", added)), [])

    def test_a_single_endpoint_url_change_needs_a_new_major_version(self):
        single = CONNECTOR.replace(
            '  endpoints:\n    - { label: EU, endpoint: "https://eu.acme.example/mcp" }\n'
            '    - { label: US, endpoint: "https://us.acme.example/mcp" }\n',
            '  endpoint: "https://mcp.acme.example/mcp"\n',
        )
        base = folder("1.0.0", single)
        head = folder("1.1.0", single.replace("mcp.acme.example", "api.acme.example"))
        self.assertEqual(
            [m.split(",")[0] for m in messages(cc.check_history("acme", base, head))],
            ["mcp.endpoint was removed or its URL changed"],
        )

    def test_changes_that_keep_connections_working_need_only_a_higher_version(self):
        cases = {
            "an added auth option": (
                "  auth:\n",
                '  auth:\n    - type: oauth_client_credentials\n      exchange_url: "https://login.acme.example/token"\n',
            ),
            "an added endpoint": (
                '  auth:\n',
                '    - { label: AP, endpoint: "https://ap.acme.example/mcp" }\n  auth:\n',
            ),
            "the same value, quoted differently": (
                '"https://login.acme.example/token"',
                "https://login.acme.example/token",
            ),
        }
        for label, (old, new) in cases.items():
            with self.subTest(label):
                self.assertEqual(cc.check_history("acme", folder(), changed("1.0.1", old, new)), [])
        reordered = CONNECTOR.replace(API_KEY_OPTION, "") + API_KEY_OPTION
        self.assertEqual(cc.check_history("acme", folder(), folder("1.0.1", reordered)), [])

    def test_a_config_field_that_is_removed_or_kept_needs_no_major_version(self):
        with_field = CONNECTOR.replace(
            "  auth:\n", '  config:\n    - { name: team, label: Team, pattern: "^[a-z]{1,8}$" }\n  auth:\n'
        )
        self.assertEqual(cc.check_history("acme", folder("1.0.0", with_field), folder("1.0.1", with_field)), [])
        self.assertEqual(cc.check_history("acme", folder("1.0.0", with_field), folder("1.1.0")), [])

    def test_a_new_connector_starts_at_1_0_0_or_warns(self):
        self.assertEqual(cc.check_history("acme", None, folder()), [])
        findings = cc.check_history("acme", None, folder("2.0.0"))
        self.assertEqual(messages(findings, "warning"), ["a new connector starts at version 1.0.0, not 2.0.0"])
        self.assertEqual(messages(findings), [])

    def test_a_version_that_skips_a_step_warns(self):
        findings = cc.check_history("acme", folder("1.0.0"), folder("1.2.0"))
        self.assertEqual(messages(findings), [])
        self.assertEqual(
            messages(findings, "warning"),
            ["version should go up only one step from 1.0.0: to 1.0.1, 1.1.0 or 2.0.0, not 1.2.0"],
        )

    def test_an_unreadable_base_version_skips_the_rules_with_a_warning(self):
        findings = cc.check_history("acme", folder('"1.0"'), folder("1.0.0", **{"logo.svg": b"<svg></svg>\n"}))
        self.assertEqual(messages(findings), [])
        self.assertIn("the version rules were not checked", messages(findings, "warning")[0])

    def test_a_base_copy_that_breaks_a_newer_yaml_rule_is_still_compared(self):
        base = folder("1.0.0", CONNECTOR + "released: 2026-11-10\n")
        head = folder("1.0.0", CONNECTOR + 'released: "2026-11-10"\n')
        self.assertIn("so version must go up", messages(cc.check_history("acme", base, head))[0])

    def test_an_unreadable_head_is_left_to_the_other_rules(self):
        self.assertEqual(cc.check_history("acme", folder(), tree({"connector.yaml": b"name: [acme\n"})), [])
        self.assertEqual(cc.check_history("acme", folder(), folder('"1.1"')), [])


if __name__ == "__main__":
    unittest.main()
