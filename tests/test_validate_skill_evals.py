"""Tests for the evals.json rule in .github/scripts/validate_skill_evals.py.

``evals.json`` is the functional tests' input, so an honored ``functional``
exemption waives it. These cover what reaches that waiver and what doesn't,
including that a skill's ``metadata.tier`` plays no part in it, and that the rest
of the check is unmoved.

Each test builds a throwaway Git repository with a skill in it, the way the
workflow sees a pull request.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import validate_skill_evals  # noqa: E402

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}

REASON = "No access to the skill evaluation tool."
ALL_TYPES = ("structure", "best-practices", "functional")


def skill_md(name: str, metadata_extra: str = "") -> str:
    return (
        f"---\nname: {name}\ndescription: Use this skill when testing {name}.\n"
        f'metadata:\n  author: octocat\n  version: "1.0.0"\n{metadata_extra}'
        f"---\n\n# {name}\n"
    )


def exemptions(*test_types: str, reason: str = REASON) -> str:
    return json.dumps({t: {"reason": reason} for t in test_types}, indent=2) + "\n"


EXEMPT_ALL = exemptions(*ALL_TYPES)


class EvalsJsonTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "base\n")
        self.base = self.commit()

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env={**os.environ, **GIT_ENV},
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def write(self, path: str, text: str) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit(self) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")
        return self.git("rev-parse", "HEAD")

    def add_skill(
        self,
        name: str,
        exemptions_file: str | None = EXEMPT_ALL,
        *,
        tier: str | None = None,
        evals_json: bool = False,
        results: tuple[str, ...] = (),
    ) -> None:
        """A skill the pull request adds, with only what each test needs in evals/."""
        self.write(
            f"skills/{name}/SKILL.md",
            skill_md(name, f'  tier: "{tier}"\n' if tier else ""),
        )
        if exemptions_file is not None:
            self.write(f"skills/{name}/evals/exemptions.json", exemptions_file)
        if evals_json:
            self.write(f"skills/{name}/evals/evals.json", "[]\n")
        self.results(name, *results)
        # Keeps evals/ in the tree when nothing else put a file in it.
        self.write(f"skills/{name}/evals/.keep", "")
        self.commit()

    def results(self, name: str, *test_types: str) -> None:
        """Complete results for the named test types, as the tool writes them."""
        evals = f"skills/{name}/evals"
        if "structure" in test_types:
            self.write(f"{evals}/structure/structure-tests-results-v1.json", "{}\n")
        if "best-practices" in test_types:
            self.write(f"{evals}/best-practices/v1/benchmark.json", "{}\n")
            self.write(
                f"{evals}/best-practices/v1/iteration-1/"
                "best-practices-tests-results.json",
                "{}\n",
            )
        if "functional" in test_types:
            self.write(f"{evals}/functional/v1/benchmark.json", "{}\n")
            self.write(f"{evals}/functional/v1/evals.json", "{}\n")
            for side in ("with_skill", "without_skill"):
                self.write(
                    f"{evals}/functional/v1/iteration-1/scenario-a/{side}/"
                    "functional-tests-results.json",
                    "{}\n",
                )

    def report(self, name: str, base: str | None = None, **kwargs):
        (report,) = validate_skill_evals.build_reports(
            self.repo, [name], base or self.base, **kwargs
        )
        return report

    def label(self) -> dict:
        return {
            "force_reason": "enforce-evals label",
            "withdraw_exemptions": "the `enforce-evals` label",
        }

    def assertEvalsJson(self, report, *, required: bool):
        violation = f"missing file `skills/{report.id}/evals/evals.json`"
        if required:
            self.assertIn(violation, report.violations)
        else:
            self.assertNotIn(violation, report.violations)

    # -- the waiver ---------------------------------------------------------

    def test_an_exempted_functional_run_waives_evals_json(self):
        self.add_skill("all-three")
        report = self.report("all-three")
        self.assertTrue(report.enforced)
        self.assertTrue(report.ok, report.violations)
        self.assertEvalsJson(report, required=False)
        # Reported, so a green check still shows the file is absent and why.
        self.assertTrue(
            any("`evals.json` not required" in e for e in report.exemptions),
            report.exemptions,
        )

    def test_functional_alone_waives_it_with_the_other_results_committed(self):
        self.add_skill(
            "partly",
            exemptions("functional"),
            results=("structure", "best-practices"),
        )
        report = self.report("partly")
        self.assertEvalsJson(report, required=False)
        self.assertTrue(report.ok, report.violations)

    def test_the_tier_plays_no_part(self):
        """The waiver follows the claim, not who maintains the skill."""
        for tier in ("partner-managed", "aws-managed", None):
            with self.subTest(tier=tier, claims="all three"):
                name = f"claimed-{tier}"
                self.add_skill(name, tier=tier)
                self.assertEvalsJson(self.report(name), required=False)
            with self.subTest(tier=tier, claims="none"):
                name = f"unclaimed-{tier}"
                self.add_skill(name, None, tier=tier)
                self.assertEvalsJson(self.report(name), required=True)

    # -- what the waiver does not reach ------------------------------------

    def test_the_other_two_exemptions_do_not_waive_it(self):
        for test_type in ("structure", "best-practices"):
            with self.subTest(test_type):
                name = f"only-{test_type}"
                self.add_skill(name, exemptions(test_type), results=("functional",))
                report = self.report(name)
                self.assertEvalsJson(report, required=True)
                self.assertFalse(report.ok)

    def test_no_exemptions_file_at_all_requires_it(self):
        self.add_skill("plain", None)
        self.assertEvalsJson(self.report("plain"), required=True)

    def test_a_malformed_functional_claim_grants_nothing(self):
        cases = {
            "empty reason": '{"functional": {"reason": "  "}}\n',
            "reason missing": '{"functional": {}}\n',
            "not an object": '{"functional": "no tool access"}\n',
            "invalid JSON": '{"functional": {"reason": "x",}\n',
        }
        for index, (name, text) in enumerate(cases.items()):
            with self.subTest(name):
                skill = f"malformed-{index}"
                self.add_skill(skill, text)
                report = self.report(skill)
                self.assertEvalsJson(report, required=True)
                self.assertFalse(report.ok)

    def test_the_label_requires_evals_json_and_the_results_again(self):
        self.add_skill("withdrawn")
        report = self.report("withdrawn", **self.label())
        self.assertEvalsJson(report, required=True)
        self.assertTrue(any("structure/" in v for v in report.violations))
        self.assertTrue(report.exemptions_withdrawn)

    def test_naming_evals_json_as_a_test_type_waives_nothing(self):
        # It is not an exemptable key, and naming it is an error of its own.
        self.add_skill("named", exemptions("evals.json"))
        report = self.report("named")
        self.assertEvalsJson(report, required=True)
        self.assertTrue(
            any("unknown test type `evals.json`" in v for v in report.violations),
            report.violations,
        )

    # -- the rest of the check is unchanged --------------------------------

    def test_the_waiver_does_not_waive_the_results(self):
        self.add_skill("results-still", exemptions("functional"))
        report = self.report("results-still")
        self.assertEvalsJson(report, required=False)
        self.assertFalse(report.ok)
        for expected in ("structure/", "best-practices"):
            self.assertTrue(
                any(expected in v for v in report.violations), report.violations
            )

    def test_an_evals_dir_is_still_required(self):
        self.write("skills/no-dir/SKILL.md", skill_md("no-dir"))
        self.commit()
        report = self.report("no-dir")
        self.assertEqual(
            report.violations, ["missing directory `skills/no-dir/evals/`"]
        )

    def test_committed_results_cannot_be_deleted(self):
        self.add_skill("ratchet", EXEMPT_ALL, evals_json=True, results=("structure",))
        base = self.git("rev-parse", "HEAD")
        shutil.rmtree(self.repo / "skills/ratchet/evals")
        self.write("skills/ratchet/SKILL.md", skill_md("ratchet") + "more\n")
        self.commit()
        report = self.report("ratchet", base=base)
        self.assertTrue(report.enforced)
        self.assertFalse(report.ok)

    def test_a_committed_evals_json_is_neither_missing_nor_reported_as_waived(self):
        self.add_skill("kept", exemptions("functional"), evals_json=True)
        report = self.report("kept")
        self.assertEvalsJson(report, required=False)
        self.assertFalse(
            any("`evals.json` not required" in e for e in report.exemptions),
            report.exemptions,
        )

    # -- end to end --------------------------------------------------------

    def run_main(self, *argv: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
        with mock.patch.object(
            validate_skill_evals, "_repo_root", return_value=self.repo
        ), mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(
            out
        ), contextlib.redirect_stderr(err):
            code = validate_skill_evals.main(list(argv))
        return code, out.getvalue() + err.getvalue()

    def test_main_passes_the_waiver_and_fails_it_under_the_label(self):
        self.add_skill("e2e")
        code, output = self.run_main("--base-ref", self.base, "--head-ref", "HEAD")
        self.assertEqual(code, 0, output)
        self.assertIn("`evals.json` not required", output)

        code, output = self.run_main(
            "--base-ref",
            self.base,
            "--head-ref",
            "HEAD",
            "--labels",
            f'["{validate_skill_evals.ENFORCE_LABEL}"]',
        )
        self.assertEqual(code, 1)
        self.assertIn("missing file `skills/e2e/evals/evals.json`", output)

    def test_main_skill_option_applies_the_same_rule(self):
        self.add_skill("claimed")
        self.add_skill("unclaimed", None)
        self.assertEqual(self.run_main("--skill", "claimed")[0], 0)
        self.assertEqual(self.run_main("--skill", "unclaimed")[0], 1)
        self.assertEqual(
            self.run_main(
                "--skill", "claimed", "--labels",
                f'["{validate_skill_evals.ENFORCE_LABEL}"]',
            )[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
