"""Integration tests for .github/scripts/validate_skills.py.

Each test builds a throwaway Git repository with skills/ in it and runs the
command's main() against it, the way the workflow does.
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

import validate_skills  # noqa: E402

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def skill_md(name: str, version: str = "1.0.0", extra: str = "") -> str:
    return (
        f"---\nname: {name}\ndescription: Use this skill when testing {name}.\n"
        f'metadata:\n  author: octocat\n  version: "{version}"\n'
        f'  summary: "Tests {name}."\n  aws-devops-agent-skills.agent-types: "Chat tasks"\n{extra}---\n\n# {name}\n'
    )


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        self.git("init", "-q", "-b", "main")
        self.write("skills/.gitignore", "*\n!*/\n!*.md\n")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, env={**os.environ, **GIT_ENV}
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    def write(self, path: str, text: str) -> None:
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit(self, message: str = "change") -> str:
        self.git("add", "-A", "-f")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_check(self, *argv: str, env: dict | None = None, rules_dir: Path | None = None) -> tuple[int, str]:
        out = io.StringIO()
        environ = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
        environ.update(env or {})
        with mock.patch.dict(os.environ, environ, clear=True), contextlib.redirect_stdout(out):
            code = validate_skills.main(
                list(argv), repo_root=self.repo, rules_dir=rules_dir or validate_skills.RULES_DIR
            )
        return code, out.getvalue()


class ValidateSkillsTests(RepoTestCase):
    def test_clean_repository_passes(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        self.write("skills/beta/SKILL.md", skill_md("beta"))
        self.commit("add beta")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 0, out)
        self.assertIn("2 skill(s) checked: 0 with errors.", out)

    def test_broken_skill_fails_with_annotation(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.1"))
        self.commit("bad version")
        code, out = self.run_check("--base-ref", base, env={"GITHUB_ACTIONS": "true"})
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  skills/alpha/SKILL.md:6:", out)
        self.assertIn("::error file=skills/alpha/SKILL.md,line=6,title=Skill publishing rules::", out)

    def test_untouched_skill_errors_still_fail(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.1"))
        base = self.commit("base with a broken skill")
        self.write("skills/beta/SKILL.md", skill_md("beta"))
        self.commit("add beta")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("skills/alpha/SKILL.md:6", out)

    def test_warnings_are_shown_only_for_touched_skills(self):
        off_vocabulary = '  aws-devops-agent-skills.aws-services: "Made Up Service"\n'
        self.write("skills/alpha/SKILL.md", skill_md("alpha", extra=off_vocabulary))
        self.write("skills/beta/SKILL.md", skill_md("beta", extra=off_vocabulary))
        base = self.commit("base")
        self.write("skills/beta/README.md", "# Beta\n")
        self.commit("touch beta")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  skills/beta/SKILL.md", out)
        self.assertNotIn("skills/alpha", out)
        self.assertIn("1 warning(s) on skills this pull request doesn't touch are not shown", out)

    def test_without_a_base_every_warning_is_shown(self):
        off_vocabulary = '  aws-devops-agent-skills.aws-services: "Made Up Service"\n'
        self.write("skills/alpha/SKILL.md", skill_md("alpha", extra=off_vocabulary))
        self.commit("base")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  skills/alpha/SKILL.md", out)

    def test_file_directly_under_skills_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/notes.md", "loose\n")
        self.commit("base")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("skills/notes.md is a file directly under skills/", out)

    def test_submodule_skill_folder_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        head = self.commit("base")
        self.git("update-index", "--add", "--cacheinfo", f"160000,{head},skills/vendored")
        self.git("commit", "-q", "-m", "add a submodule")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("skills/vendored is a Git submodule", out)

    def test_unknown_base_ref_cannot_run(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.commit("base")
        code, out = self.run_check("--base-ref", "no-such-branch")
        self.assertEqual(code, 2, out)
        self.assertIn("This is not a finding about the pull request.", out)

    def test_uncommitted_changes_are_noted(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.commit("base")
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="9"))
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertIn("uncommitted changes under skills/ are not checked", out)

    def test_missing_git_object_cannot_run(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.commit("base")
        blob = self.git("rev-parse", "HEAD:skills/alpha/SKILL.md")
        (self.repo / ".git" / "objects" / blob[:2] / blob[2:]).unlink()
        code, out = self.run_check()
        self.assertEqual(code, 2, out)
        self.assertIn("This is not a finding about the pull request.", out)

    def test_unexpected_exception_cannot_run(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.commit("base")
        with mock.patch.object(validate_skills.sc, "check_skill", side_effect=RuntimeError("boom")):
            code, out = self.run_check()
        self.assertEqual(code, 2, out)
        self.assertIn("boom", out)

    def test_untrusted_text_cannot_start_a_workflow_command(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.0") .replace(
            'version: "1.0"', 'version: "1.0\\n::warning title=spoofed::x"'))
        self.commit("base")
        code, out = self.run_check(env={"GITHUB_ACTIONS": "true"})
        self.assertEqual(code, 1, out)
        self.assertFalse(any(line.startswith("::warning title=spoofed") for line in out.splitlines()), out)

    def test_step_summary_lists_errors(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.1"))
        self.commit("base")
        summary = self.repo / "summary.md"
        code, _ = self.run_check(env={"GITHUB_STEP_SUMMARY": str(summary)})
        self.assertEqual(code, 1)
        self.assertIn("| `skills/alpha/SKILL.md:6` |", summary.read_text(encoding="utf-8"))


class SelfCheckTests(RepoTestCase):
    def rules_copy(self) -> Path:
        target = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, target)
        shutil.copytree(validate_skills.RULES_DIR, target, dirs_exist_ok=True)
        return target

    def test_repository_cases_pass(self):
        code, out = self.run_check("--self-check-only")
        self.assertEqual(code, 0, out)

    def test_wrong_case_stops_the_check(self):
        rules_dir = self.rules_copy()
        path = rules_dir / validate_skills.CONFORMANCE_FILE
        document = json.loads(path.read_text(encoding="utf-8"))
        valid = next(case for case in document["cases"] if case["id"] == "valid-minimal")
        valid["expect"], valid["error"] = "fail", "anything"
        path.write_text(json.dumps(document), encoding="utf-8")
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.commit("base")
        code, out = self.run_check(rules_dir=rules_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("case valid-minimal: expected an error", out)
        self.assertNotIn("skill(s) checked", out)

    def test_malformed_rule_data_cannot_run(self):
        rules_dir = self.rules_copy()
        (rules_dir / "vocabulary.json").write_text("{not json", encoding="utf-8")
        code, out = self.run_check("--self-check-only", rules_dir=rules_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("cannot read", out)


if __name__ == "__main__":
    unittest.main()
