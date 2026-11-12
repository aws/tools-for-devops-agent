"""Tests for .github/scripts/check_pr_checklist.py."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import check_pr_checklist as cpc  # noqa: E402

TEMPLATE = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
TICKED = re.sub(r"^(\s*-\s*)\[\s*\]", r"\1[x]", TEMPLATE, flags=re.M)

SKILL_PR = ["skills/demo/SKILL.md"]
DOCS_PR = ["CONTRIBUTING.md"]
CONNECTOR_PR = ["connectors/acme/connector.yaml", "connectors/acme/logo.svg"]


def body(*sections: str) -> str:
    return "\n\n".join(sections) + "\n"


REQUIRED_ALL_TICKED = "## Required before review\n- [x] **No internal-only or proprietary content**"
LICENSE_TICKED = "## License confirmation\n- [x] I confirm the terms of the Apache License 2.0."
SECURITY_TICKED = "## Security and safety\n- [x] Read-only by default."
SKILLS_TICKED = "## Skills — complete if this PR adds or changes a skill\n- [x] frontmatter is valid"
CONNECTORS_TICKED = "## Connectors — complete if this PR adds or changes a connector\n- [x] I accept the terms."
PARTNER_YAML = "name: acme\ntier: partner-managed\ncontact_email: devops@acme.example\n"
AWS_YAML = "name: acme\ntier: aws-managed\ncontact_email: devops@acme.example\n"
ACME_ENTRY = {"vendor": "Acme, Inc.", "domains": ["acme.example"], "github": ["Acme-Dev", "acme/devops"],
              "confirmed": "2026-11-12"}
ACME_RECORD = json.dumps({"connectors": {"acme": ACME_ENTRY}})
PARTNER_AUTHOR = {"user": {"type": "User", "login": "acme-dev"}, "author_association": "CONTRIBUTOR"}


class TemplateTest(unittest.TestCase):
    """The check and the template must agree; a reworded template fails here first."""

    def test_every_section_is_a_template_heading(self):
        headings = [m.group(1) for m in map(cpc.HEADING.match, TEMPLATE.splitlines()) if m]
        names = [*cpc.ALWAYS_SECTIONS, cpc.TOOL_SECTION, *cpc.TOOL_DIRS.values(), cpc.CONNECTOR_SECTION]
        for name in names:
            with self.subTest(name):
                matches = [h for h in headings if h.lower().startswith(name.lower())]
                self.assertEqual(len(matches), 1, f"{name!r} should prefix exactly one heading, got {matches}")

    def test_every_universal_item_is_a_template_checkbox(self):
        boxes = [line for line in TEMPLATE.splitlines() if cpc.UNCHECKED.match(line)]
        for pattern in cpc.UNIVERSAL_ITEMS:
            with self.subTest(pattern.pattern):
                self.assertEqual(sum(bool(pattern.search(b)) for b in boxes), 1)

    def test_the_terms_box_names_the_version_in_terms_md(self):
        # A terms revision changes TERMS.md's date and the box together, so each
        # connector PR records the version its partner accepted.
        terms = (ROOT / "connectors" / "TERMS.md").read_text(encoding="utf-8")
        dated = re.search(r"^Date last updated: (\d{4}-\d{2}-\d{2})$", terms, re.M)
        self.assertIsNotNone(dated, "TERMS.md must end with 'Date last updated: YYYY-MM-DD'")
        boxes = [line for line in TEMPLATE.splitlines() if "Partner Connector Terms and Conditions" in line]
        self.assertEqual(len(boxes), 1)
        self.assertIn(f"version {dated.group(1)},", boxes[0])

    def test_untouched_template_waives_nothing(self):
        # Prose in the template that happens to read as `n/a: <reason>` would let
        # every author skip that item without writing anything.
        unmet, waived, _ = cpc.evaluate(TEMPLATE, SKILL_PR)
        self.assertEqual(waived, [])
        self.assertTrue(any("domain SME" in u for u in unmet))

    def test_untouched_template_on_a_docs_pr_holds_only_the_universal_items(self):
        unmet, _, is_tool = cpc.evaluate(TEMPLATE, DOCS_PR)
        self.assertFalse(is_tool)
        self.assertEqual(len(unmet), 2)
        self.assertIn("internal-only", unmet[0])
        self.assertIn("Apache License", unmet[1])

    def test_fully_ticked_template_passes_on_every_tool_type(self):
        paths = ["skills/a/SKILL.md", "mcp/b/README.md", "custom-agents/c/SYSTEM_PROMPT.md", *CONNECTOR_PR]
        self.assertEqual(cpc.evaluate(TICKED, paths)[0], [])

    def test_untouched_template_on_a_connector_pr_holds_the_universal_items_and_the_terms(self):
        unmet, _, is_tool = cpc.evaluate(TEMPLATE, CONNECTOR_PR)
        self.assertFalse(is_tool)
        self.assertEqual(len(unmet), 3)
        self.assertTrue(unmet[2].startswith("Connectors → I accept the"))


class EvaluateTest(unittest.TestCase):
    def test_sme_item_can_be_marked_na_with_a_reason(self):
        text = body(
            "## Required before review\n"
            "- [x] **No internal-only or proprietary content**\n"
            "- [ ] **A domain SME has reviewed and signed off.** n/a: renames a label, changes no technical claim",
            LICENSE_TICKED, SECURITY_TICKED, SKILLS_TICKED,
        )
        unmet, waived, _ = cpc.evaluate(text, SKILL_PR)
        self.assertEqual(unmet, [])
        self.assertEqual(len(waived), 1)
        self.assertIn("domain SME", waived[0])

    def test_universal_items_cannot_be_marked_na(self):
        text = body(REQUIRED_ALL_TICKED, "## License confirmation\n- [ ] Apache License 2.0 n/a: not mine to give")
        unmet, waived, _ = cpc.evaluate(text, DOCS_PR)
        self.assertEqual(waived, [])
        self.assertEqual(len(unmet), 1)
        self.assertIn("cannot be marked n/a", unmet[0])

    def test_bare_na_waives_nothing(self):
        text = body(
            "## Required before review\n- [x] No internal-only or proprietary content\n- [ ] **CHANGELOG updated** n/a",
            LICENSE_TICKED, SECURITY_TICKED, SKILLS_TICKED,
        )
        unmet, waived, _ = cpc.evaluate(text, SKILL_PR)
        self.assertEqual(waived, [])
        self.assertEqual(len(unmet), 1)

    def test_a_deleted_section_is_unmet(self):
        unmet, _, _ = cpc.evaluate(body(REQUIRED_ALL_TICKED, LICENSE_TICKED, SECURITY_TICKED), SKILL_PR)
        self.assertEqual(len(unmet), 1)
        self.assertTrue(unmet[0].startswith("Skills → section missing"))

    def test_a_shortened_heading_still_finds_its_section(self):
        text = body(REQUIRED_ALL_TICKED, LICENSE_TICKED, SECURITY_TICKED, "## Skills\n- [x] frontmatter is valid")
        self.assertEqual(cpc.evaluate(text, SKILL_PR)[0], [])

    def test_tool_items_do_not_apply_to_a_pr_touching_no_tool(self):
        text = body("## Required before review\n- [x] No internal-only or proprietary content\n- [ ] README is complete",
                    LICENSE_TICKED)
        for paths in (DOCS_PR, ["connectors/releases.yaml"], ["connectors/schema/v1/connector.schema.json"],
                      ["connectors/README.md", "connectors/TERMS.md"]):
            with self.subTest(paths):
                self.assertEqual(cpc.evaluate(text, paths)[0], [])


class ConnectorTest(unittest.TestCase):
    def test_a_connector_pr_with_the_terms_accepted_passes(self):
        text = body(REQUIRED_ALL_TICKED, CONNECTORS_TICKED, LICENSE_TICKED)
        self.assertEqual(cpc.evaluate(text, CONNECTOR_PR)[0], [])

    def test_a_connector_pr_without_the_terms_accepted_fails(self):
        text = body(REQUIRED_ALL_TICKED, CONNECTORS_TICKED.replace("[x]", "[ ]"), LICENSE_TICKED)
        unmet, _, _ = cpc.evaluate(text, CONNECTOR_PR)
        self.assertEqual(len(unmet), 1)
        self.assertTrue(unmet[0].startswith("Connectors → "))

    def test_the_terms_cannot_be_marked_na(self):
        text = body(
            REQUIRED_ALL_TICKED,
            "## Connectors — complete if this PR adds or changes a connector\n- [ ] I accept the terms. n/a: filed by an SA",
            LICENSE_TICKED,
        )
        unmet, waived, _ = cpc.evaluate(text, CONNECTOR_PR)
        self.assertEqual(waived, [])
        self.assertEqual(len(unmet), 1)
        self.assertIn("cannot be marked n/a", unmet[0])

    def test_a_deleted_connectors_section_is_unmet(self):
        unmet, _, _ = cpc.evaluate(body(REQUIRED_ALL_TICKED, LICENSE_TICKED), CONNECTOR_PR)
        self.assertEqual(unmet, ["Connectors → section missing from the description; restore it from the template"])

    def test_a_connector_with_its_skills_is_held_to_both_sections(self):
        text = body(REQUIRED_ALL_TICKED, LICENSE_TICKED, SECURITY_TICKED, SKILLS_TICKED)
        unmet, _, is_tool = cpc.evaluate(text, [*CONNECTOR_PR, "skills/acme-investigation/SKILL.md"])
        self.assertTrue(is_tool)
        self.assertEqual(len(unmet), 1)
        self.assertTrue(unmet[0].startswith("Connectors → section missing"))

    def test_a_changed_connector_must_set_contact_email(self):
        files = {
            "connectors/acme/connector.yaml": "name: acme\ncontact_email: devops@acme.example\n",
            "connectors/beta/connector.yaml": "name: beta\nsupport_url: https://beta.example\n",
            "connectors/gamma/connector.yaml": "name: gamma\ncontact_email:\n  # not set\n",
            "connectors/delta/connector.yaml": "mcp:\n  contact_email: nested@delta.example\n",
        }
        paths = ["connectors/acme/logo.svg", "connectors/beta/connector.yaml", "connectors/gamma/README.md",
                 "connectors/delta/connector.yaml", "connectors/omega/README.md", "connectors/README.md",
                 "connectors/schema/v1/connector.schema.json"]
        unmet = cpc.missing_contact(paths, files.get)
        self.assertEqual([u.split(" sets ")[0] for u in unmet], [
            "Connectors → connectors/beta/connector.yaml",
            "Connectors → connectors/delta/connector.yaml",
            "Connectors → connectors/gamma/connector.yaml",
        ])

    def test_a_removed_connector_needs_no_contact(self):
        # connector.yaml is required, so a connector directory without one at the
        # head is a connector the PR deletes.
        paths = ["connectors/acme/connector.yaml", "connectors/acme/logo.svg", "connectors/acme/README.md"]
        self.assertEqual(cpc.missing_contact(paths, lambda path: None), [])

    def test_a_block_scalar_or_empty_contact_email_is_not_set(self):
        for value in (">\n  devops@acme.example", "|\n  devops@acme.example", '""', "''", "", "# none"):
            with self.subTest(value):
                text = f"name: acme\ncontact_email: {value}\n"
                self.assertEqual(len(cpc.missing_contact(["connectors/acme/connector.yaml"], {
                    "connectors/acme/connector.yaml": text}.get)), 1)

    def test_no_connector_change_reads_nothing(self):
        def read(path):
            raise AssertionError(path)
        self.assertEqual(cpc.missing_contact([*DOCS_PR, "connectors/releases.yaml", "connectors/TERMS.md"], read), [])

    def test_the_summary_names_the_terms_only_for_a_connector_pr(self):
        self.assertIn("partner terms", cpc.summary([], [], False, "complete", True))
        self.assertNotIn("partner terms", cpc.summary([], [], False, "complete", False))


class TierTest(unittest.TestCase):
    def test_only_a_single_plain_or_quoted_partner_managed_tier_counts_as_partner(self):
        cases = {
            "tier: partner-managed": True,
            'tier: "partner-managed"': True,
            "tier: 'partner-managed'  # shown as a badge": True,
            "tier:   partner-managed": True,
            "tier: aws-managed": False,
            "tier: Partner-Managed": False,
            'tier: "partner-managed\'': False,
            "tier: !!str partner-managed": False,
            "tier: *anchor": False,
            "tier: >\n  partner-managed": False,
            "tier:": False,
            "": False,
            "mcp:\n  tier: partner-managed": False,
            # A second spelling of the key, which a YAML parser would keep instead.
            "tier: partner-managed\ntier: aws-managed": False,
            'tier: partner-managed\n"tier": aws-managed': False,
            "tier: partner-managed\n'tier' : aws-managed": False,
            "tier: partner-managed\ntier : aws-managed": False,
            "tier: partner-managed\n? tier\n: aws-managed": False,
            "\ufefftier: partner-managed": False,
        }
        for text, expected in cases.items():
            with self.subTest(text):
                self.assertIs(cpc.declares_partner_tier(f"name: acme\n{text}\nversion: 1.0.0\n"), expected)

    def test_nested_and_block_text_lines_are_not_the_tier(self):
        text = "name: acme\ntier: partner-managed\ndescription: |\n  tier: aws-managed\nmcp:\n  tier: x\n"
        self.assertTrue(cpc.declares_partner_tier(text))

    def test_a_partner_managed_connector_never_reads_the_record(self):
        def read_base(path):
            raise AssertionError(path)
        files = {"connectors/acme/connector.yaml": PARTNER_YAML}
        self.assertEqual(cpc.unowned_tier(CONNECTOR_PR, files.get, read_base), [])

    def test_any_other_tier_needs_an_entry_in_the_record(self):
        files = {
            "connectors/acme/connector.yaml": AWS_YAML,
            "connectors/beta/connector.yaml": "name: beta\ntier: aws-managed\n",
            "connectors/gamma/connector.yaml": "name: gamma\n",
        }
        paths = ["connectors/acme/connector.yaml", "connectors/beta/logo.svg", "connectors/gamma/README.md"]
        record = json.dumps({"connectors": {"beta": "aws/devops-agent-team"}})
        unmet = cpc.unowned_tier(paths, files.get, {cpc.OWNERSHIP_RECORD: record}.get)
        self.assertEqual([u.split(" must ")[0] for u in unmet], [
            "Connectors → connectors/acme/connector.yaml",
            "Connectors → connectors/gamma/connector.yaml",
        ])
        self.assertIn(cpc.OWNERSHIP_RECORD, unmet[0])

    def test_a_record_the_base_branch_lacks_lists_no_connector(self):
        files = {"connectors/acme/connector.yaml": AWS_YAML}
        self.assertEqual(len(cpc.unowned_tier(CONNECTOR_PR, files.get, lambda path: None)), 1)

    def test_the_committed_record_is_well_formed_and_lists_no_connector_yet(self):
        text = (ROOT / cpc.OWNERSHIP_RECORD).read_text(encoding="utf-8")
        self.assertEqual(cpc.ownership_record(text), set())

    def test_a_malformed_record_is_an_error_not_a_grant(self):
        for text in ("not json", "[]", '{"connectors": []}', '{"connectors": {"acme": ""}}',
                     '{"connectors": {"acme": 1}}', "{}"):
            with self.subTest(text):
                with self.assertRaises(ValueError):
                    cpc.ownership_record(text)

    def test_a_removed_connector_has_no_tier_to_check(self):
        self.assertEqual(cpc.unowned_tier(CONNECTOR_PR, lambda path: None, lambda path: None), [])

    def test_the_summary_names_the_record_for_a_connector_pr(self):
        self.assertIn(cpc.OWNERSHIP_RECORD, cpc.summary([], [], False, "complete", True))


class PartnerRecordTest(unittest.TestCase):
    def test_the_committed_record_is_well_formed(self):
        text = (ROOT / cpc.PARTNER_RECORD).read_text(encoding="utf-8")
        self.assertIsInstance(cpc.partner_record(text), dict)

    def test_a_well_formed_entry_parses(self):
        self.assertEqual(cpc.partner_record(ACME_RECORD), {"acme": ACME_ENTRY})

    def test_a_record_the_base_branch_lacks_lists_no_connector(self):
        self.assertEqual(cpc.partner_record(None), {})

    def test_a_malformed_record_is_an_error_not_a_grant(self):
        def entry(**fields):
            return json.dumps({"connectors": {"acme": {**ACME_ENTRY, **fields}}})
        cases = {
            "not json": "not json",
            "a list": "[]",
            "no connectors": "{}",
            "another top-level key": json.dumps({"connectors": {}, "extra": 1}),
            "connectors as a list": '{"connectors": []}',
            "a repeated connector": '{"connectors": {"acme": {}, "acme": {}}}',
            "a missing key": json.dumps({"connectors": {"acme": {k: v for k, v in ACME_ENTRY.items()
                                                                 if k != "confirmed"}}}),
            "an extra key": entry(notes="x"),
            "an empty vendor": entry(vendor=" "),
            "a long vendor": entry(vendor="x" * 129),
            "no domains": entry(domains=[]),
            "an uppercase domain": entry(domains=["Acme.example"]),
            "a scheme": entry(domains=["https://acme.example"]),
            "a wildcard": entry(domains=["*.acme.example"]),
            "a trailing dot": entry(domains=["acme.example."]),
            "a single label": entry(domains=["example"]),
            "a repeated domain": entry(domains=["acme.example", "acme.example"]),
            "eleven domains": entry(domains=[f"d{i}.example" for i in range(11)]),
            "no github": entry(github=[]),
            "a leading @": entry(github=["@acme-dev"]),
            "a repeated user in another case": entry(github=["acme-dev", "Acme-Dev"]),
            "a user with a space": entry(github=["acme dev"]),
            "a user over 39 characters": entry(github=["a" * 40]),
            "an organization over 39 characters": entry(github=[f"{'o' * 40}/team"]),
            "a team with a dot": entry(github=["acme/dev.ops"]),
            "a bare organization with a slash": entry(github=["acme/"]),
            "an entry not named like a connector": json.dumps({"connectors": {"Acme_Co": ACME_ENTRY}}),
            "a date with a time": entry(confirmed="2026-11-12T00:00:00Z"),
            "an impossible date": entry(confirmed="2026-02-30"),
        }
        for name, text in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    cpc.partner_record(text)

    def test_a_partner_connector_needs_an_entry(self):
        files = {"connectors/acme/connector.yaml": PARTNER_YAML}
        unmet = cpc.unconfirmed_partner(CONNECTOR_PR, files.get, {}.get, PARTNER_AUTHOR)
        self.assertEqual(len(unmet), 1)
        self.assertIn(f"acme has no entry in {cpc.PARTNER_RECORD}", unmet[0])

    def test_a_listed_author_passes_in_any_case(self):
        files = {"connectors/acme/connector.yaml": PARTNER_YAML}
        for login in ("acme-dev", "ACME-DEV"):
            with self.subTest(login):
                pr = {"user": {"login": login}, "author_association": "NONE"}
                self.assertEqual(cpc.unconfirmed_partner(
                    CONNECTOR_PR, files.get, {cpc.PARTNER_RECORD: ACME_RECORD}.get, pr), [])

    def test_an_unlisted_author_fails_and_a_team_authorizes_no_one(self):
        files = {"connectors/acme/connector.yaml": PARTNER_YAML}
        for login in ("someone-else", "acme/devops", "acme", ""):
            with self.subTest(login):
                pr = {"user": {"login": login}, "author_association": "CONTRIBUTOR"}
                unmet = cpc.unconfirmed_partner(CONNECTOR_PR, files.get, {cpc.PARTNER_RECORD: ACME_RECORD}.get, pr)
                self.assertEqual(len(unmet), 1)
                self.assertIn("is not a GitHub user that", unmet[0])

    def test_a_member_of_the_owning_organization_needs_no_listing(self):
        files = {"connectors/acme/connector.yaml": PARTNER_YAML}
        read_base = {cpc.PARTNER_RECORD: ACME_RECORD}.get
        for association, expected in (("MEMBER", 0), ("OWNER", 0), ("COLLABORATOR", 1), ("CONTRIBUTOR", 1),
                                      ("FIRST_TIME_CONTRIBUTOR", 1), (None, 1)):
            with self.subTest(association):
                pr = {"user": {"login": "aws-dev"}, "author_association": association}
                self.assertEqual(len(cpc.unconfirmed_partner(CONNECTOR_PR, files.get, read_base, pr)), expected)

    def test_a_member_still_needs_the_connector_to_have_an_entry(self):
        files = {"connectors/acme/connector.yaml": PARTNER_YAML}
        pr = {"user": {"login": "aws-dev"}, "author_association": "MEMBER"}
        self.assertEqual(len(cpc.unconfirmed_partner(CONNECTOR_PR, files.get, {}.get, pr)), 1)

    def test_other_tiers_and_removed_connectors_never_read_the_record(self):
        def read_base(path):
            raise AssertionError(path)
        files = {"connectors/acme/connector.yaml": AWS_YAML}
        paths = [*CONNECTOR_PR, "connectors/gone/connector.yaml", "connectors/README.md", "connectors/releases.yaml"]
        self.assertEqual(cpc.unconfirmed_partner(paths, files.get, read_base, PARTNER_AUTHOR), [])

    def test_a_malformed_record_raises_when_a_connector_needs_it(self):
        files = {"connectors/acme/connector.yaml": PARTNER_YAML}
        with self.assertRaises(ValueError):
            cpc.unconfirmed_partner(CONNECTOR_PR, files.get, {cpc.PARTNER_RECORD: "{}"}.get, PARTNER_AUTHOR)

    def test_the_record_never_arrives_with_a_connector(self):
        cases = [
            ([cpc.PARTNER_RECORD, "connectors/acme/connector.yaml"], 1),
            ([cpc.PARTNER_RECORD, "connectors/acme/README.md"], 1),
            ([cpc.PARTNER_RECORD], 0),
            ([cpc.PARTNER_RECORD, "CONTRIBUTING.md", "connectors/README.md", "tests/test_x.py"], 0),
            (["connectors/acme/connector.yaml"], 0),
        ]
        for paths, expected in cases:
            with self.subTest(paths):
                self.assertEqual(len(cpc.record_with_connector(paths)), expected)

    def test_the_summary_names_the_partner_record_for_a_connector_pr(self):
        self.assertIn(cpc.PARTNER_RECORD, cpc.summary([], [], False, "complete", True))


class DecideTest(unittest.TestCase):
    AFTER = "2026-10-20T00:00:00Z"
    BEFORE = "2026-10-01T00:00:00Z"

    def pr(self, **fields):
        base = {"created_at": self.AFTER, "draft": False, "user": {"type": "User"}, "labels": []}
        return {**base, **fields}

    def test_outcomes(self):
        cases = [
            ("nothing unmet", self.pr(), [], ("pass", "complete")),
            ("unmet", self.pr(), ["x"], ("fail", "incomplete")),
            ("bot", self.pr(user={"type": "Bot"}), ["x"], ("pass", "bot")),
            ("draft", self.pr(draft=True), ["x"], ("pass", "draft")),
            ("draft with the label", self.pr(draft=True, labels=[{"name": cpc.ENFORCE_LABEL}]), ["x"], ("pass", "draft")),
            ("predating", self.pr(created_at=self.BEFORE), ["x"], ("pass", "predating")),
            ("predating with the label", self.pr(created_at=self.BEFORE, labels=[{"name": cpc.ENFORCE_LABEL}]), ["x"],
             ("fail", "incomplete")),
            ("no creation time", self.pr(created_at=""), ["x"], ("fail", "incomplete")),
        ]
        for name, pr, unmet, expected in cases:
            with self.subTest(name):
                self.assertEqual(cpc.decide(pr, unmet), expected)

    def test_a_tier_finding_fails_every_pr_but_a_draft(self):
        cases = [
            ("bot", self.pr(user={"type": "Bot"}), ("fail", "incomplete")),
            ("predating", self.pr(created_at=self.BEFORE), ("fail", "incomplete")),
            ("draft", self.pr(draft=True), ("pass", "draft")),
        ]
        for name, pr, expected in cases:
            with self.subTest(name):
                self.assertEqual(cpc.decide(pr, ["tier"], ["tier"]), expected)


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "out"
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.tmp / "repo"), *args], check=True, capture_output=True)

    def event(self, pr_body, **fields):
        path = self.tmp / "event.json"
        path.write_text(json.dumps({"pull_request": {
            "body": pr_body, "number": 1, "created_at": "2026-10-20T00:00:00Z",
            "draft": False, "labels": [], **PARTNER_AUTHOR, **fields,
        }}), encoding="utf-8")
        return str(path)

    def test_an_unreadable_event_is_an_error_not_a_finding(self):
        code = cpc.main(["--event", str(self.tmp / "missing.json"), "--base-ref", "main", "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertEqual((self.out / "outcome").read_text().strip(), "error")
        self.assertFalse((self.out / "reason").exists())

    def connector_pr(self, connector_yaml, base_record=None, pr_record=None, base_partner_record=ACME_RECORD,
                     pr_partner_record=None, **event_fields):
        repo = self.tmp / "repo"
        repo.mkdir()
        self.git("init", "-q", "-b", "main")
        for path, text in ((cpc.OWNERSHIP_RECORD, base_record), (cpc.PARTNER_RECORD, base_partner_record)):
            if text is not None:
                (repo / ".github").mkdir(exist_ok=True)
                (repo / path).write_text(text, encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "base")
        self.git("checkout", "-q", "-b", "pr")
        (repo / "connectors" / "acme").mkdir(parents=True)
        (repo / "connectors" / "acme" / "connector.yaml").write_text(connector_yaml, encoding="utf-8")
        for path, text in ((cpc.OWNERSHIP_RECORD, pr_record), (cpc.PARTNER_RECORD, pr_partner_record)):
            if text is not None:
                (repo / ".github").mkdir(exist_ok=True)
                (repo / path).write_text(text, encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "connector")
        cwd = os.getcwd()
        os.chdir(repo)
        self.addCleanup(os.chdir, cwd)
        text = body(REQUIRED_ALL_TICKED, CONNECTORS_TICKED, LICENSE_TICKED)
        return cpc.main(["--event", self.event(text, **event_fields), "--base-ref", "main", "--out", str(self.out)])

    def test_a_connector_pr_with_contact_email_passes(self):
        self.assertEqual(self.connector_pr(PARTNER_YAML), 0)
        self.assertEqual((self.out / "outcome").read_text().strip(), "pass")

    def test_a_connector_pr_without_contact_email_fails(self):
        self.assertEqual(self.connector_pr("name: acme\ntier: partner-managed\n"), 1)
        self.assertEqual((self.out / "reason").read_text().strip(), "incomplete")

    def test_an_aws_managed_connector_without_an_entry_fails(self):
        self.assertEqual(self.connector_pr(AWS_YAML), 1)
        self.assertEqual((self.out / "reason").read_text().strip(), "incomplete")

    def test_an_aws_managed_connector_with_an_entry_on_the_base_branch_passes(self):
        record = json.dumps({"connectors": {"acme": "aws/devops-agent-team"}})
        self.assertEqual(self.connector_pr(AWS_YAML, base_record=record), 0)

    def test_an_entry_the_pr_adds_itself_grants_nothing(self):
        record = json.dumps({"connectors": {"acme": "aws/devops-agent-team"}})
        self.assertEqual(self.connector_pr(AWS_YAML, pr_record=record), 1)

    def test_a_partner_connector_without_an_entry_fails(self):
        self.assertEqual(self.connector_pr(PARTNER_YAML, base_partner_record=None), 1)
        self.assertEqual((self.out / "reason").read_text().strip(), "incomplete")

    def test_a_partner_entry_the_pr_adds_itself_grants_nothing(self):
        self.assertEqual(self.connector_pr(PARTNER_YAML, base_partner_record=None, pr_partner_record=ACME_RECORD), 1)

    def test_a_partner_connector_from_an_unlisted_author_fails(self):
        self.assertEqual(self.connector_pr(PARTNER_YAML, user={"type": "User", "login": "stranger"}), 1)

    def test_a_partner_connector_from_an_unlisted_bot_fails(self):
        self.assertEqual(self.connector_pr(PARTNER_YAML, user={"type": "Bot", "login": "some-bot[bot]"}), 1)

    def test_a_partner_connector_from_an_organization_member_passes(self):
        self.assertEqual(self.connector_pr(PARTNER_YAML, user={"type": "User", "login": "aws-dev"},
                                           author_association="MEMBER"), 0)

    def test_a_malformed_partner_record_is_an_error_not_a_finding(self):
        self.assertEqual(self.connector_pr(PARTNER_YAML, base_partner_record='{"connectors": []}'), 2)
        self.assertEqual((self.out / "outcome").read_text().strip(), "error")

    def test_a_head_ref_git_cannot_read_is_an_error_not_a_finding(self):
        self.connector_pr(PARTNER_YAML)
        code = cpc.main(["--event", self.event(body(REQUIRED_ALL_TICKED, CONNECTORS_TICKED, LICENSE_TICKED)),
                         "--base-ref", "main", "--head-ref", "pr", "--out", str(self.out)])
        self.assertEqual(code, 0)
        read = cpc.read_at("no-such-ref")
        with self.assertRaises(RuntimeError):
            read("connectors/acme/connector.yaml")

    def test_a_skill_pr_with_the_untouched_template_fails(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "base")
        self.git("checkout", "-q", "-b", "pr")
        (repo / "skills" / "demo").mkdir(parents=True)
        (repo / "skills" / "demo" / "SKILL.md").write_text("x\n", encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "skill")
        cwd = os.getcwd()
        os.chdir(repo)
        self.addCleanup(os.chdir, cwd)
        code = cpc.main(["--event", self.event(TEMPLATE), "--base-ref", "main", "--out", str(self.out)])
        self.assertEqual(code, 1)
        self.assertEqual((self.out / "outcome").read_text().strip(), "fail")
        self.assertEqual((self.out / "reason").read_text().strip(), "incomplete")
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["outcome", "reason"])


if __name__ == "__main__":
    unittest.main()
