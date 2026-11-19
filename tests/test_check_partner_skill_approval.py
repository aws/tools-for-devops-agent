"""Tests for .github/scripts/check_partner_skill_approval.py."""

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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import check_partner_skill_approval as cpsa  # noqa: E402

HEAD_SHA = "a" * 40
EARLIER_SHA = "b" * 40
OWNERS = ["yeremyjt", "aadimch"]
CODEOWNERS = "/.github/ @aws/admins\n/connectors/ @yeremyjt @aadimch\n"
PARTNER_SKILL = '---\nname: acme\nmetadata:\n  tier: "partner-managed"\n---\n# Acme\n'
AWS_SKILL = '---\nname: acme\nmetadata:\n  tier: "aws-managed"\n---\n# Acme\n'


def review(login, state, commit_id=HEAD_SHA):
    return {"user": {"login": login}, "state": state, "commit_id": commit_id}


class ConnectorOwnerLoginsTest(unittest.TestCase):
    def test_the_last_connectors_line_wins_and_teams_are_ignored(self):
        text = (
            "# /connectors/ @commented-out\n"
            "/connectors/ @first\n"
            "/connectors/acme/ @acme-owner\n"
            "/connectors/ @YeremyJT @aws/connector-team docs@example.com @aadimch # @inline-comment\n"
            "/skills/ @someone\n"
        )
        self.assertEqual(cpsa.connector_owner_logins(text), OWNERS)

    def test_no_connectors_line_or_no_user_on_it_gives_no_owner(self):
        for text in ("", "/.github/ @aws/admins\n", "/connectors/ @aws/connector-team\n", "connectors/ @someone\n"):
            with self.subTest(text):
                self.assertEqual(cpsa.connector_owner_logins(text), [])

    def test_the_committed_codeowners_names_a_user(self):
        text = (ROOT / cpsa.CODEOWNERS_PATH).read_text(encoding="utf-8")
        self.assertTrue(cpsa.connector_owner_logins(text))


class ChangedSkillNamesTest(unittest.TestCase):
    def test_a_skill_is_the_folder_of_a_path_under_skills(self):
        paths = ["skills/beta/evals/evals.json", "skills/acme/SKILL.md", "skills/acme/README.md",
                 "skills/.gitignore", "connectors/acme/connector.yaml", "docs/skills/gamma/index.md"]
        self.assertEqual(cpsa.changed_skill_names(paths), ["acme", "beta"])


class OwnersApprovingHeadCommitTest(unittest.TestCase):
    def test_review_table(self):
        cases = [
            ("an approval of the head commit", [review("aadimch", "APPROVED")], ["aadimch"]),
            ("an approval of an earlier commit", [review("aadimch", "APPROVED", EARLIER_SHA)], []),
            ("a later change request", [review("aadimch", "APPROVED"), review("aadimch", "CHANGES_REQUESTED")], []),
            ("a later dismissal", [review("aadimch", "APPROVED"), review("aadimch", "DISMISSED")], []),
            ("a later comment", [review("aadimch", "APPROVED"), review("aadimch", "COMMENTED")], ["aadimch"]),
            ("a later pending review", [review("aadimch", "APPROVED"), review("aadimch", "PENDING")], ["aadimch"]),
            ("an approval after a change request",
             [review("aadimch", "CHANGES_REQUESTED"), review("aadimch", "APPROVED")], ["aadimch"]),
            ("an approval from a non-owner", [review("mallory", "APPROVED")], []),
            ("a login in another case", [review("AadimCh", "APPROVED")], ["aadimch"]),
            ("a change request from another owner",
             [review("aadimch", "APPROVED"), review("yeremyjt", "CHANGES_REQUESTED")], ["aadimch"]),
            ("a review from a deleted account", [{"user": None, "state": "APPROVED", "commit_id": HEAD_SHA}], []),
            ("no review", [], []),
        ]
        for name, reviews, expected in cases:
            with self.subTest(name):
                self.assertEqual(cpsa.owners_approving_head_commit(reviews, OWNERS, HEAD_SHA), expected)


class FetchReviewsTest(unittest.TestCase):
    def test_every_page_is_fetched_with_the_token(self):
        pages = [[review("aadimch", "COMMENTED")] * cpsa.REVIEWS_PER_PAGE, [review("aadimch", "APPROVED")]]
        requests = []

        def urlopen(request, timeout):
            requests.append(request)
            return io.StringIO(json.dumps(pages[len(requests) - 1]))

        environment = {"GITHUB_API_URL": "https://api.example", "GITHUB_REPOSITORY": "aws/tools", "GITHUB_TOKEN": "t0ken"}
        with mock.patch.dict(os.environ, environment), mock.patch("urllib.request.urlopen", urlopen):
            reviews = cpsa.fetch_reviews(7)
        self.assertEqual(len(reviews), cpsa.REVIEWS_PER_PAGE + 1)
        self.assertEqual([request.full_url for request in requests], [
            "https://api.example/repos/aws/tools/pulls/7/reviews?per_page=100&page=1",
            "https://api.example/repos/aws/tools/pulls/7/reviews?per_page=100&page=2",
        ])
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer t0ken")


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)

    def git(self, *args):
        identity = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(["git", "-C", str(self.repo), *identity, *args], check=True, capture_output=True)

    def commit(self, files):
        """Writes each path's text, or deletes the path when its text is None, and commits."""
        for path, text in files.items():
            target = self.repo / path
            if text is None:
                target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "change")

    def check(self, base_files, pull_request_files, reviews=(), fetch_error=None):
        """The exit code of main() for a pull request that makes ``pull_request_files`` on top of ``base_files``."""
        self.commit({cpsa.CODEOWNERS_PATH: CODEOWNERS, **base_files})
        self.git("checkout", "-q", "-b", "pr")
        self.commit(pull_request_files)
        event = self.tmp / "event.json"
        event.write_text(json.dumps({"pull_request": {"number": 7, "head": {"sha": HEAD_SHA}}}), encoding="utf-8")
        self.fetched = []

        def fetch_reviews(pull_request_number):
            self.fetched.append(pull_request_number)
            if fetch_error:
                raise fetch_error
            return list(reviews)

        self.summary = self.tmp / "summary.md"
        with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(self.summary)}), \
                contextlib.redirect_stdout(io.StringIO()) as self.output:
            return cpsa.main(["--event", str(event), "--base-ref", "main"], fetch_reviews=fetch_reviews)

    def test_no_partner_managed_skill_passes_without_a_fetch(self):
        code = self.check({"skills/acme/SKILL.md": AWS_SKILL}, {"skills/acme/README.md": "x\n", "README.md": "x\n"})
        self.assertEqual(code, 0)
        self.assertEqual(self.fetched, [])
        self.assertIn("no partner-managed skill", self.summary.read_text(encoding="utf-8"))

    def test_a_partner_managed_skill_without_an_approval_fails(self):
        code = self.check({"skills/acme/SKILL.md": PARTNER_SKILL}, {"skills/acme/README.md": "x\n"},
                          [review("aadimch", "APPROVED", EARLIER_SHA), review("mallory", "APPROVED")])
        self.assertEqual(code, 1)
        self.assertEqual(self.fetched, [7])
        report = self.summary.read_text(encoding="utf-8")
        self.assertEqual(report, self.output.getvalue()[:-1])
        for expected in ("`acme`", "`@yeremyjt`, `@aadimch`", f"`{HEAD_SHA}`", "a maintainer re-runs this job"):
            self.assertIn(expected, report)

    def test_a_partner_managed_skill_with_an_approval_of_the_head_commit_passes(self):
        code = self.check({}, {"skills/acme/SKILL.md": PARTNER_SKILL}, [review("YeremyJT", "APPROVED")])
        self.assertEqual(code, 0)
        self.assertIn("`@yeremyjt`", self.summary.read_text(encoding="utf-8"))

    def test_a_pull_request_that_removes_the_tier_still_needs_the_approval(self):
        self.assertEqual(self.check({"skills/acme/SKILL.md": PARTNER_SKILL}, {"skills/acme/SKILL.md": AWS_SKILL}), 1)

    def test_a_pull_request_that_deletes_the_skill_still_needs_the_approval(self):
        self.assertEqual(self.check({"skills/acme/SKILL.md": PARTNER_SKILL}, {"skills/acme/SKILL.md": None}), 1)

    def test_a_pull_request_that_renames_the_skill_still_needs_the_approval(self):
        body = "Enough shared text for git to read the move as a rename.\n" * 20
        code = self.check({"skills/acme/SKILL.md": PARTNER_SKILL + body},
                          {"skills/acme/SKILL.md": None, "skills/other/SKILL.md": AWS_SKILL + body})
        self.assertEqual(code, 1)
        self.assertIn("`acme`", self.summary.read_text(encoding="utf-8"))

    def test_a_skill_md_with_unreadable_frontmatter_counts_as_partner_managed(self):
        self.assertEqual(self.check({}, {"skills/acme/SKILL.md": "# No frontmatter\n"}), 1)

    def test_an_owner_the_pull_request_adds_itself_approves_nothing(self):
        pull_request_files = {"skills/acme/SKILL.md": PARTNER_SKILL, cpsa.CODEOWNERS_PATH: "/connectors/ @mallory\n"}
        self.assertEqual(self.check({}, pull_request_files, [review("mallory", "APPROVED")]), 1)

    def test_a_base_without_a_connectors_owner_is_an_error_not_a_finding(self):
        code = self.check({cpsa.CODEOWNERS_PATH: "/.github/ @aws/admins\n"}, {"skills/acme/SKILL.md": PARTNER_SKILL})
        self.assertEqual(code, 2)
        self.assertEqual(self.fetched, [])
        self.assertIn("could not run", self.output.getvalue())

    def test_a_failed_fetch_is_an_error_not_a_finding(self):
        code = self.check({}, {"skills/acme/SKILL.md": PARTNER_SKILL}, fetch_error=OSError("connection refused"))
        self.assertEqual(code, 2)
        self.assertFalse(self.summary.exists())


if __name__ == "__main__":
    unittest.main()
