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


def body(*sections: str) -> str:
    return "\n\n".join(sections) + "\n"


REQUIRED_ALL_TICKED = "## Required before review\n- [x] **No internal-only or proprietary content**"
LICENSE_TICKED = "## License confirmation\n- [x] I confirm the terms of the Apache License 2.0."
SECURITY_TICKED = "## Security and safety\n- [x] Read-only by default."
SKILLS_TICKED = "## Skills — complete if this PR adds or changes a skill\n- [x] frontmatter is valid"


class TemplateTest(unittest.TestCase):
    """The check and the template must agree; a reworded template fails here first."""

    def test_every_section_is_a_template_heading(self):
        headings = [m.group(1) for m in map(cpc.HEADING.match, TEMPLATE.splitlines()) if m]
        names = [*cpc.ALWAYS_SECTIONS, cpc.TOOL_SECTION, *cpc.TOOL_DIRS.values()]
        for name in names:
            with self.subTest(name):
                matches = [h for h in headings if h.lower().startswith(name.lower())]
                self.assertEqual(len(matches), 1, f"{name!r} should prefix exactly one heading, got {matches}")

    def test_every_universal_item_is_a_template_checkbox(self):
        boxes = [line for line in TEMPLATE.splitlines() if cpc.UNCHECKED.match(line)]
        for pattern in cpc.UNIVERSAL_ITEMS:
            with self.subTest(pattern.pattern):
                self.assertEqual(sum(bool(pattern.search(b)) for b in boxes), 1)

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
        paths = ["skills/a/SKILL.md", "mcp/b/README.md", "custom-agents/c/SYSTEM_PROMPT.md"]
        self.assertEqual(cpc.evaluate(TICKED, paths)[0], [])


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
        for paths in (DOCS_PR, ["connectors/acme/connector.yaml"]):
            with self.subTest(paths):
                self.assertEqual(cpc.evaluate(text, paths)[0], [])


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


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "out"
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.tmp / "repo"), *args], check=True, capture_output=True)

    def event(self, pr_body):
        path = self.tmp / "event.json"
        path.write_text(json.dumps({"pull_request": {
            "body": pr_body, "number": 1, "created_at": "2026-10-20T00:00:00Z",
            "draft": False, "user": {"type": "User"}, "labels": [],
        }}), encoding="utf-8")
        return str(path)

    def test_an_unreadable_event_is_an_error_not_a_finding(self):
        code = cpc.main(["--event", str(self.tmp / "missing.json"), "--base-ref", "main", "--out", str(self.out)])
        self.assertEqual(code, 2)
        self.assertEqual((self.out / "outcome").read_text().strip(), "error")
        self.assertFalse((self.out / "reason").exists())

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
