"""Tests for .github/scripts/check_partner_maintainers.py."""

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

import check_partner_maintainers as cpm  # noqa: E402

HEAD_SHA = "a" * 40
OWNERS = ["yeremyjt", "aadimch"]
CODEOWNERS = "/.github/ @aws/admins\n/connectors/ @yeremyjt @aadimch\n"
PARTNER_SKILL = '---\nname: acme-logs\nmetadata:\n  tier: "partner-managed"\n---\n# Acme logs\n'
AWS_SKILL = '---\nname: acme-logs\nmetadata:\n  tier: "aws-managed"\n---\n# Acme logs\n'
PUSHED = "2026-11-20T10:00:00Z"
BEFORE_PUSH = "2026-11-20T09:00:00Z"
AFTER_PUSH = "2026-11-20T11:00:00Z"


def connector(maintainers=("acme-dev",), tier="partner-managed", skills=(), version="1.0.0"):
    lines = ["name: acme", f"version: {version}", f"tier: {tier}", f"maintainers: [{', '.join(maintainers)}]"]
    if skills:
        lines.append(f"skills: [{', '.join(skills)}]")
    return "\n".join(lines) + "\n"


def labeled(login, created_at=AFTER_PUSH, name=cpm.LABEL):
    return {"event": "labeled", "actor": {"login": login}, "label": {"name": name}, "created_at": created_at}


def at(text):
    return cpm.parse_time(text)


class MaintainersTest(unittest.TestCase):
    def test_users_leave_out_teams_and_ignore_case_and_a_leading_at(self):
        doc = {"maintainers": ["Acme-Dev", "@second", "acme/engineering", 7, None]}
        self.assertEqual(cpm.maintainer_users(doc), {"acme-dev", "second"})
        self.assertEqual(cpm.maintainer_entries(doc), {"acme-dev", "second", "acme/engineering"})

    def test_a_missing_or_malformed_list_has_no_entry(self):
        for doc in ({}, None, {"maintainers": "acme-dev"}, {"maintainers": {"a": 1}}):
            with self.subTest(doc):
                self.assertEqual(cpm.maintainer_entries(doc), frozenset())

    def test_load_connector(self):
        self.assertEqual(cpm.load_connector(None), {})
        self.assertIsNone(cpm.load_connector("maintainers: [unclosed\n"))
        self.assertIsNone(cpm.load_connector("- a list\n"))
        self.assertEqual(cpm.load_connector("tier: partner-managed\n"), {"tier": "partner-managed"})


class ChangedConnectorNamesTest(unittest.TestCase):
    def test_a_connector_is_the_folder_of_a_path_under_connectors(self):
        paths = ["connectors/beta/logo.svg", "connectors/acme/connector.yaml", "connectors/acme/README.md",
                 "connectors/releases.yaml", "connectors/schema/v1/connector.schema.json", "docs/connectors/x.md"]
        self.assertEqual(cpm.changed_connector_names(paths), ["acme", "beta"])

    def test_connector_names_need_a_connector_yaml(self):
        paths = ["connectors/acme/connector.yaml", "connectors/beta/README.md", "connectors/acme/sub/connector.yaml"]
        self.assertEqual(cpm.connector_names(paths), ["acme"])


class LabelVerdictTest(unittest.TestCase):
    def verdict(self, events, labels=(cpm.LABEL,), push_times=(at(PUSHED),)):
        return cpm.label_verdict(list(labels), events, OWNERS, list(push_times))[0]

    def test_label_table(self):
        cases = [
            ("an owner added it after the last push", [labeled("aadimch")], True),
            ("an owner in another case", [labeled("AadimCh")], True),
            ("an owner added it before the last push", [labeled("aadimch", BEFORE_PUSH)], False),
            ("an owner added it in the second of the push", [labeled("aadimch", PUSHED)], False),
            ("a non-owner added it", [labeled("mallory")], False),
            ("a non-owner added it again after an owner", [labeled("aadimch"), labeled("mallory")], False),
            ("an owner added it again after a non-owner", [labeled("mallory"), labeled("yeremyjt")], True),
            ("another label was added", [labeled("aadimch", name="needs-checklist")], False),
            ("a deleted account added it", [{"event": "labeled", "actor": None, "label": {"name": cpm.LABEL},
                                              "created_at": AFTER_PUSH}], False),
            ("no record of it", [], False),
        ]
        for name, events, expected in cases:
            with self.subTest(name):
                self.assertEqual(self.verdict(events), expected)

    def test_without_the_label_nothing_counts(self):
        self.assertFalse(self.verdict([labeled("aadimch")], labels=()))

    def test_with_no_recorded_push_an_owner_label_counts(self):
        self.assertTrue(self.verdict([labeled("aadimch", BEFORE_PUSH)], push_times=()))

    def test_the_latest_push_is_the_one_that_counts(self):
        pushes = (at("2026-11-20T08:00:00Z"), at("2026-11-20T12:00:00Z"))
        self.assertFalse(self.verdict([labeled("aadimch")], push_times=pushes))


class FetchTest(unittest.TestCase):
    environment = {"GITHUB_API_URL": "https://api.example", "GITHUB_REPOSITORY": "aws/tools", "GITHUB_TOKEN": "t0ken"}

    def fetch(self, function, pages, *args):
        requests = []

        def urlopen(request, timeout):
            requests.append(request)
            return io.StringIO(json.dumps(pages[len(requests) - 1]))

        with mock.patch.dict(os.environ, self.environment), mock.patch("urllib.request.urlopen", urlopen):
            return function(*args), requests

    def test_every_page_of_events_is_fetched_with_the_token(self):
        pages = [[labeled("x")] * cpm.PER_PAGE, [labeled("aadimch")]]
        events, requests = self.fetch(cpm.fetch_label_events, pages, 7)
        self.assertEqual(len(events), cpm.PER_PAGE + 1)
        self.assertEqual([request.full_url for request in requests], [
            "https://api.example/repos/aws/tools/issues/7/events?per_page=100&page=1",
            "https://api.example/repos/aws/tools/issues/7/events?per_page=100&page=2",
        ])
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer t0ken")

    def test_push_times_come_from_this_branchs_push_runs(self):
        def run(title, created_at=PUSHED, branch="acme-update", repository="acme/tools", sha=HEAD_SHA):
            return {"display_title": title, "created_at": created_at, "head_sha": sha, "head_branch": branch,
                    "head_repository": {"full_name": repository}}

        runs = [
            run("check-partner-maintainers: opened", "2026-11-20T08:00:00Z"),
            run("check-partner-maintainers: synchronize"),
            run("check-partner-maintainers: labeled", AFTER_PUSH),
            run("check-partner-maintainers: edited", AFTER_PUSH),
            run("Add the Acme connector", AFTER_PUSH),
            run("check-partner-maintainers: synchronize", AFTER_PUSH, branch="other"),
            run("check-partner-maintainers: synchronize", AFTER_PUSH, repository="mallory/tools"),
            run("check-partner-maintainers: synchronize", AFTER_PUSH, sha="b" * 40),
        ]
        times, requests = self.fetch(cpm.fetch_push_times, [{"workflow_runs": runs}], HEAD_SHA, "acme/tools",
                                     "acme-update")
        self.assertEqual(sorted(times), [at("2026-11-20T08:00:00Z"), at(PUSHED)])
        self.assertEqual(requests[0].full_url,
                         "https://api.example/repos/aws/tools/actions/workflows/check-partner-maintainers.yml/runs"
                         f"?event=pull_request&head_sha={HEAD_SHA}&per_page=100&page=1")

    def test_the_run_name_prefix_matches_the_workflow(self):
        workflow = (ROOT / ".github" / "workflows" / cpm.WORKFLOW_FILE).read_text(encoding="utf-8")
        self.assertIn(f'run-name: "{cpm.RUN_NAME_PREFIX}${{{{ github.event.action }}}}"', workflow)


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

    def check(self, base_files, pull_request_files, author="acme-dev", labels=(), events=(),
              push_times=(PUSHED,), draft=False, fetch_error=None):
        """The exit code of main() for a pull request by ``author`` that makes
        ``pull_request_files`` on top of ``base_files``."""
        self.commit({cpm.CODEOWNERS_PATH: CODEOWNERS, **base_files})
        self.git("checkout", "-q", "-b", "pr")
        self.commit(pull_request_files)
        event = self.tmp / "event.json"
        event.write_text(json.dumps({"pull_request": {
            "number": 7, "draft": draft, "user": {"login": author},
            "labels": [{"name": name} for name in labels],
            "head": {"sha": HEAD_SHA, "ref": "acme-update", "repo": {"full_name": "acme/tools"}},
        }}), encoding="utf-8")
        self.fetched = []

        def fetch_label_events(number):
            self.fetched.append(("events", number))
            if fetch_error:
                raise fetch_error
            return list(events)

        def fetch_push_times(sha, repository, branch):
            self.fetched.append(("runs", sha, repository, branch))
            return [at(time) for time in push_times]

        self.summary = self.tmp / "summary.md"
        with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(self.summary)}), \
                contextlib.redirect_stdout(io.StringIO()) as self.output:
            return cpm.main(["--event", str(event), "--base-ref", "main"],
                            fetch_label_events=fetch_label_events, fetch_push_times=fetch_push_times)

    def report(self):
        return self.summary.read_text(encoding="utf-8")

    def test_a_pull_request_without_a_partner_connector_passes_without_a_fetch(self):
        code = self.check({"connectors/acme/connector.yaml": connector(tier="aws-managed")},
                          {"connectors/acme/README.md": "x\n", "README.md": "x\n", "connectors/releases.yaml": "x\n"},
                          author="mallory")
        self.assertEqual(code, 0)
        self.assertEqual(self.fetched, [])
        self.assertIn("changes no partner-managed connector", self.report())

    def test_a_listed_author_passes_without_a_fetch(self):
        code = self.check({"connectors/acme/connector.yaml": connector()},
                          {"connectors/acme/connector.yaml": connector(version="1.0.1"),
                           "connectors/acme/README.md": "x\n"}, author="Acme-Dev")
        self.assertEqual(code, 0)
        self.assertEqual(self.fetched, [])
        self.assertIn("`@Acme-Dev` is a user in `maintainers`", self.report())

    def test_an_unlisted_author_needs_the_label(self):
        code = self.check({"connectors/acme/connector.yaml": connector()}, {"connectors/acme/README.md": "x\n"},
                          author="mallory")
        self.assertEqual(code, 1)
        self.assertEqual(self.fetched, [("events", 7), ("runs", HEAD_SHA, "acme/tools", "acme-update")])
        report = self.report()
        self.assertEqual(report, self.output.getvalue()[:-1])
        for expected in ("`@mallory` is not a user in `maintainers` of `acme`", cpm.INBOX, "`@yeremyjt`, `@aadimch`",
                         f"doesn't have the `{cpm.LABEL}` label"):
            self.assertIn(expected, report)

    def test_an_unlisted_author_with_an_owner_label_after_the_push_passes(self):
        code = self.check({"connectors/acme/connector.yaml": connector()}, {"connectors/acme/README.md": "x\n"},
                          author="mallory", labels=[cpm.LABEL], events=[labeled("yeremyjt")])
        self.assertEqual(code, 0)
        self.assertIn("after the last push", self.report())

    def test_a_label_from_before_the_last_push_does_not_count(self):
        code = self.check({"connectors/acme/connector.yaml": connector()}, {"connectors/acme/README.md": "x\n"},
                          author="mallory", labels=[cpm.LABEL], events=[labeled("yeremyjt", BEFORE_PUSH)])
        self.assertEqual(code, 1)
        self.assertIn("before the last push", self.report())

    def test_a_team_never_matches_the_author(self):
        code = self.check({"connectors/acme/connector.yaml": connector(maintainers=["acme/engineering"])},
                          {"connectors/acme/README.md": "x\n"}, author="engineer-at-acme")
        self.assertEqual(code, 1)

    def test_a_new_connector_needs_the_label(self):
        code = self.check({}, {"connectors/acme/connector.yaml": connector()})
        self.assertEqual(code, 1)
        self.assertIn("`acme` is a new connector", self.report())

    def test_a_listed_author_who_changes_maintainers_needs_the_label(self):
        code = self.check({"connectors/acme/connector.yaml": connector()},
                          {"connectors/acme/connector.yaml": connector(maintainers=["acme-dev", "friend"])})
        self.assertEqual(code, 1)
        self.assertIn("it changes `maintainers` of `acme`", self.report())

    def test_reordering_or_recasing_maintainers_is_no_change(self):
        code = self.check({"connectors/acme/connector.yaml": connector(maintainers=["acme-dev", "second"])},
                          {"connectors/acme/connector.yaml": connector(maintainers=["Second", "acme-dev"])})
        self.assertEqual(code, 0)

    def test_an_author_the_pull_request_adds_to_maintainers_still_needs_the_label(self):
        code = self.check({"connectors/acme/connector.yaml": connector()},
                          {"connectors/acme/connector.yaml": connector(maintainers=["acme-dev", "mallory"])},
                          author="mallory")
        self.assertEqual(code, 1)
        self.assertIn("`@mallory` is not a user", self.report())

    def test_a_pull_request_that_moves_the_connector_off_the_partner_tier_is_still_checked(self):
        code = self.check({"connectors/acme/connector.yaml": connector()},
                          {"connectors/acme/connector.yaml": connector(tier="aws-managed")}, author="mallory")
        self.assertEqual(code, 1)

    def test_a_connector_yaml_broken_on_the_base_branch_needs_the_label(self):
        code = self.check({"connectors/acme/connector.yaml": "maintainers: [unclosed\n"},
                          {"connectors/acme/README.md": "x\n"})
        self.assertEqual(code, 1)
        self.assertIn("can't be read on the base branch", self.report())

    def test_a_skill_is_checked_against_the_connector_that_lists_it(self):
        base = {"connectors/acme/connector.yaml": connector(skills=["acme-logs"]),
                "skills/acme-logs/SKILL.md": PARTNER_SKILL}
        self.assertEqual(self.check(base, {"skills/acme-logs/README.md": "x\n"}), 0)

    def test_a_skill_change_by_an_unlisted_author_needs_the_label(self):
        base = {"connectors/acme/connector.yaml": connector(skills=["acme-logs"]),
                "skills/acme-logs/SKILL.md": AWS_SKILL}
        code = self.check(base, {"skills/acme-logs/README.md": "x\n"}, author="mallory")
        self.assertEqual(code, 1)
        self.assertIn("partner-managed connectors `acme`", self.report())

    def test_a_new_skill_listed_by_an_existing_connector_passes_for_a_listed_author(self):
        code = self.check({"connectors/acme/connector.yaml": connector()},
                          {"connectors/acme/connector.yaml": connector(skills=["acme-logs"], version="1.1.0"),
                           "skills/acme-logs/SKILL.md": PARTNER_SKILL})
        self.assertEqual(code, 0)

    def test_a_partner_skill_no_connector_lists_needs_the_label(self):
        code = self.check({}, {"skills/acme-logs/SKILL.md": PARTNER_SKILL})
        self.assertEqual(code, 1)
        self.assertIn("no partner-managed connector lists the partner-managed skill `acme-logs`", self.report())

    def test_an_aws_skill_no_connector_lists_passes(self):
        self.assertEqual(self.check({}, {"skills/acme-logs/SKILL.md": AWS_SKILL}, author="mallory"), 0)

    def test_a_draft_passes_until_it_is_ready(self):
        code = self.check({}, {"connectors/acme/connector.yaml": connector()}, draft=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.fetched, [])
        self.assertIn("is a draft", self.report())

    def test_an_owner_the_pull_request_adds_itself_labels_nothing(self):
        code = self.check({"connectors/acme/connector.yaml": connector()},
                          {"connectors/acme/README.md": "x\n", cpm.CODEOWNERS_PATH: "/connectors/ @mallory\n"},
                          author="mallory", labels=[cpm.LABEL], events=[labeled("mallory")])
        self.assertEqual(code, 1)

    def test_a_base_without_a_connectors_owner_is_an_error_not_a_finding(self):
        code = self.check({cpm.CODEOWNERS_PATH: "/.github/ @aws/admins\n"}, {"connectors/acme/connector.yaml": connector()})
        self.assertEqual(code, 2)
        self.assertEqual(self.fetched, [])
        self.assertIn("could not run", self.output.getvalue())

    def test_a_failed_fetch_is_an_error_not_a_finding(self):
        code = self.check({}, {"connectors/acme/connector.yaml": connector()}, fetch_error=OSError("refused"))
        self.assertEqual(code, 2)
        self.assertFalse(self.summary.exists())


if __name__ == "__main__":
    unittest.main()
