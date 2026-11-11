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

import github_logins  # noqa: E402
import validate_skills  # noqa: E402

GIT_ENV = {
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def skill_md(name: str, version: str = "1.0.0", extra: str = "", author: str = "octocat") -> str:
    return (
        f"---\nname: {name}\ndescription: Use this skill when testing {name}.\n"
        f'metadata:\n  author: {author}\n  version: "{version}"\n'
        f'  summary: "Tests {name}."\n  aws-devops-agent-skills.agent-types: "CHAT"\n'
        f"{extra}---\n\n# {name}\n"
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

    def rules_copy(self) -> Path:
        target = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, target)
        shutil.copytree(validate_skills.RULES_DIR, target, dirs_exist_ok=True)
        return target

    def run_check(
        self,
        *argv: str,
        env: dict | None = None,
        rules_dir: Path | None = None,
        repo_root: Path | None = None,
        login_resolver=None,
    ) -> tuple[int, str]:
        # Strict UTF-8, as on a real stdout, so text that can't be printed fails the test.
        raw = io.BytesIO()
        out = io.TextIOWrapper(raw, encoding="utf-8", errors="strict", newline="\n")
        # As outside GitHub Actions, with no token even if the shell exports one: github_logins reads GH_TOKEN too.
        environ = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_") and k != "GH_TOKEN"}
        environ.update(env or {})
        with mock.patch.dict(os.environ, environ, clear=True), contextlib.redirect_stdout(out):
            code = validate_skills.main(
                list(argv),
                repo_root=repo_root or self.repo,
                rules_dir=rules_dir or validate_skills.RULES_DIR,
                login_resolver=login_resolver,
            )
        out.flush()
        return code, raw.getvalue().decode("utf-8")


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
        self.write("skills/beta/CHANGELOG.md", "# Changelog\n")
        self.commit("touch beta without changing its published files")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  skills/beta/SKILL.md", out)
        self.assertNotIn("skills/alpha", out)
        self.assertIn("1 warning(s) on skills this change doesn't touch are not shown", out)

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
        self.assertIn("1 skill(s) checked: 0 with errors. 1 other problem(s) in the repository.", out)

    def test_a_path_that_is_not_utf8_is_reported_not_a_crash(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        blob = self.git("hash-object", "-w", "skills/alpha/SKILL.md")
        subprocess.run(
            ["git", "update-index", "--add", "--index-info"],
            cwd=self.repo,
            input=b"100644 " + blob.encode() + b"\tskills/caf\xe9/SKILL.md\n",
            check=True,
            capture_output=True,
            env={**os.environ, **GIT_ENV},
        )
        self.git("commit", "-q", "-m", "a folder name that isn't UTF-8")
        summary = self.repo / "summary.md"
        code, out = self.run_check("--base-ref", base, env={"GITHUB_ACTIONS": "true", "GITHUB_STEP_SUMMARY": str(summary)})
        self.assertEqual(code, 1, out)
        self.assertNotIn("could not run", out)
        self.assertIn("caf\\xe9", out)

    def test_a_file_name_that_is_not_utf8_is_reported_not_a_crash(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        blob = self.git("hash-object", "-w", "skills/alpha/SKILL.md")
        subprocess.run(
            ["git", "update-index", "--add", "--index-info"],
            cwd=self.repo,
            input=b"100644 " + blob.encode() + b"\tskills/alpha/references/caf\xe9.md\n",
            check=True,
            capture_output=True,
            env={**os.environ, **GIT_ENV},
        )
        self.git("commit", "-q", "-m", "a file name that isn't UTF-8")
        for env in ({}, {"GITHUB_ACTIONS": "true", "GITHUB_STEP_SUMMARY": str(self.repo / "summary.md")}):
            with self.subTest(env=env):
                code, out = self.run_check("--base-ref", base, env=env)
                self.assertEqual(code, 1, out)
                self.assertNotIn("could not run", out)
                self.assertIn("references/caf\\xe9.md", out)

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


class PackageIntegrationTests(RepoTestCase):
    def test_executable_bit_from_git_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/alpha/references/run.md", "steps\n")
        base = self.commit("base")
        (self.repo / "skills/alpha/references/run.md").chmod(0o755)
        self.git("update-index", "--chmod=+x", "skills/alpha/references/run.md")
        self.git("commit", "-q", "-m", "make it executable")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn('"references/run.md" is executable', out)

    def test_symlink_from_git_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        (self.repo / "skills/alpha/link.md").symlink_to("SKILL.md")
        self.commit("add a link")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn('"link.md" is a symbolic link', out)

    def test_a_new_extension_applies_only_after_it_merges(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        self.write("skills/.gitignore", "*\n!*/\n!*.md\n!*.sh\n")
        self.write("skills/alpha/references/run.sh", "echo hi\n")
        self.commit("allow and add a shell file")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn('extension ".sh"', out)

    def test_symlink_outside_skills_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("docs/index.md", "# Docs\n")
        base = self.commit("base")
        (self.repo / "docs/latest.md").symlink_to("index.md")
        self.commit("add a link outside skills/")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("docs/latest.md is a symbolic link", out)

    def test_root_gitattributes_that_change_skill_bytes_fail(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write(".gitattributes", "mcp/** text eol=lf\n*.png binary\n")
        base = self.commit("scoped attributes are fine")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 0, out)
        self.write(".gitattributes", "mcp/** text eol=lf\n*.md export-ignore\n")
        self.commit("an attribute that applies under skills/")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  .gitattributes:2: this line can change how Git archives files under skills/", out)
        self.write(".gitattributes", "[attr]gone export-ignore\nskills/** gone\n")
        self.commit("a macro that drops skills/ from the archive")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  .gitattributes:1: this line can change how Git archives files under skills/", out)
        # Git stops reading the file at its first NUL byte.
        self.write(".gitattributes", "skills/** export-ignore\x00\n")
        self.commit("a NUL byte after the attribute")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  .gitattributes:1: this line can change how Git archives files under skills/", out)
        # Git splits the file at newlines only: these are one line each for Git.
        self.write(".gitattributes", "# a\x0cb\n[\x0bs]kills/** export-ignore\n")
        self.commit("characters Python would split a line at")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  .gitattributes:2: this line can change how Git archives files under skills/", out)

    def test_internal_names_on_added_lines_warn_for_the_touched_skill(self):
        rules_dir = self.rules_copy()
        names = {"description": "Made-up names for this test.", "hosts": ["corp.example"], "terms": ["Rivendell"]}
        (rules_dir / "internal-names.json").write_text(json.dumps(names), encoding="utf-8")
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/alpha/evals/journal.md", "role: ops-Rivendell\n")
        base = self.commit("base already names an internal tool")
        self.write("skills/alpha/references/notes.md", "See https://wiki.corp.example/x\n")
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.0.1"))
        self.commit("add an internal link")
        code, out = self.run_check("--base-ref", base, rules_dir=rules_dir)
        self.assertEqual(code, 0, out)
        self.assertIn('WARN  skills/alpha/references/notes.md:1: adds "wiki.corp.example"', out)
        self.assertNotIn("journal.md", out)

    def test_extension_allowlist_comes_from_head_without_a_base(self):
        self.write("skills/.gitignore", "*\n!*/\n!*.md\n!*.txt\n")
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/alpha/notes.txt", "notes\n")
        self.commit("base")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)


class HistoryIntegrationTests(RepoTestCase):
    def test_removed_skill_folder_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/beta/SKILL.md", skill_md("beta"))
        base = self.commit("base")
        self.git("rm", "-q", "-r", "skills/beta")
        self.commit("remove beta")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  skills/beta: the skill folder skills/beta was removed", out)
        self.assertIn("1 skill(s) checked", out)

    def test_a_deprecated_skill_cannot_stay_recommended_by_a_connector(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("connectors/acme/connector.yaml", "name: acme\nversion: 1.0.0\nskills: [alpha, beta]\n")
        base = self.commit("base")
        deprecated = skill_md("alpha", version="1.0.1", extra='  deprecated: "true"\n')
        self.write("skills/alpha/SKILL.md", deprecated)
        self.commit("deprecate alpha")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        line = deprecated.splitlines().index('  deprecated: "true"') + 1
        self.assertIn(f"FAIL  skills/alpha/SKILL.md:{line}: the skill is deprecated, but connectors/acme/connector.yaml still recommends it", out)
        # Like any change to a connector's files, dropping a skill from its list needs a higher version.
        self.write("connectors/acme/connector.yaml", "name: acme\nversion: 1.0.1\nskills: [beta]\n")
        self.commit("drop alpha from the connector")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 0, out)

    def test_a_connector_yaml_that_breaks_the_yaml_rules_fails_and_an_odd_shape_warns(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        cases = {
            "skills: [alpha\n": "FAIL  connectors/acme/connector.yaml:2: connector.yaml is not valid YAML",
            "skills: " + "[" * 2000 + "]" * 2000 + "\n": "FAIL  connectors/acme/connector.yaml:1: connector.yaml is nested too deeply",
            "name: acme\nreleased: 2024-13-45\nskills: [alpha]\n": "FAIL  connectors/acme/connector.yaml:2: connector.yaml has the unquoted value 2024-13-45",
            "port: !!int abc\nskills: [alpha]\n": "FAIL  connectors/acme/connector.yaml:1: connector.yaml uses tags",
            "name: acme\nversion: 1.0.0\nskills: alpha\n": "WARN  connectors/acme/connector.yaml: has a skills: value that isn't a list",
            # Not a mapping, so it has no version either, which the connector version rules need.
            "- alpha\n": "FAIL  connectors/acme/connector.yaml:1: connector.yaml must be a mapping of keys to values",
            # An empty file, or one of only comments, holds no document, which isn't a mapping either.
            "": "FAIL  connectors/acme/connector.yaml:1: connector.yaml must be a mapping of keys to values",
            "# comment\n": "FAIL  connectors/acme/connector.yaml:1: connector.yaml must be a mapping of keys to values",
        }
        for text, expected in cases.items():
            with self.subTest(text=text[:24]):
                self.write("connectors/acme/connector.yaml", text)
                self.commit("an odd connector")
                code, out = self.run_check("--base-ref", base)
                self.assertEqual(code, 1 if expected.startswith("FAIL") else 0, out)
                self.assertIn(expected, out)
                self.assertNotIn("isn't a YAML mapping", out)

    def test_a_connector_yaml_over_32_kib_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        text = "name: acme\n# " + "x" * 32_768 + "\n"
        self.write("connectors/acme/connector.yaml", text)
        self.commit("a large connector")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn(f"FAIL  connectors/acme/connector.yaml: connector.yaml is {len(text):,} bytes; the limit is 32,768", out)

    def test_a_connector_yaml_that_is_not_utf8_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        (self.repo / "connectors" / "acme").mkdir(parents=True)
        (self.repo / "connectors" / "acme" / "connector.yaml").write_bytes(b"name: acme\ntitle: \xff\n")
        self.commit("a connector that isn't UTF-8")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  connectors/acme/connector.yaml:2: connector.yaml is not valid UTF-8", out)

    def test_a_releases_file_that_breaks_the_yaml_rules_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("connectors/releases.yaml", "schema_version: 1\nconnectors: []\n")
        self.commit("base")
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.write("connectors/releases.yaml", "schema_version: 1\nconnectors: [acme,\n  bronto]\n")
        self.commit("a flow list over two lines")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  connectors/releases.yaml:2: releases.yaml has a flow collection", out)

    def test_odd_connector_lists_still_find_the_skill(self):
        cases = {
            "name: acme\nversion: 1.0.0\nskills: [alpha, null]\n": "has a skills: entry that isn't a skill name",
            "name: acme\nversion: 1.0.0\nskills:\n  - 'alpha'\n": None,
        }
        for text, warning in cases.items():
            with self.subTest(text=text[:24]):
                self.write("skills/alpha/SKILL.md", skill_md("alpha"))
                self.write("connectors/acme/connector.yaml", text)
                base = self.commit("base")
                self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.0.1", extra='  deprecated: "true"\n'))
                self.commit("deprecate alpha")
                code, out = self.run_check("--base-ref", base)
                self.assertEqual(code, 1, out)
                self.assertIn("connectors/acme/connector.yaml still recommends it", out)
                if warning:
                    self.assertIn(f"WARN  connectors/acme/connector.yaml: {warning}", out)
                else:
                    self.assertNotIn("WARN  connectors/", out)

    def test_a_skill_removed_through_a_merge_commit_is_retired(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/old/SKILL.md", skill_md("old"))
        self.commit("first")
        self.git("checkout", "-q", "-b", "remove-old")
        self.git("rm", "-q", "-r", "skills/old")
        self.commit("remove old on a branch")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "merge the removal", "remove-old")
        base = self.git("rev-parse", "HEAD")
        self.write("skills/old/SKILL.md", skill_md("old"))
        self.commit("bring old back")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  skills/old/SKILL.md:2: skills/old was used by a skill that was removed earlier", out)

    def test_a_shallow_clone_skips_retired_paths_with_a_warning(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.commit("first")
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.0.1"))
        self.commit("second")
        clone = Path(tempfile.mkdtemp()) / "clone"
        self.addCleanup(shutil.rmtree, clone.parent)
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", self.repo.as_uri(), str(clone)],
            check=True,
            capture_output=True,
            env={**os.environ, **GIT_ENV},
        )
        code, out = self.run_check("--base-ref", "HEAD", repo_root=clone)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  skills: the clone is shallow", out)

    def test_rename_fails_as_a_removal(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        self.git("mv", "skills/alpha", "skills/alpha-two")
        self.write("skills/alpha-two/SKILL.md", skill_md("alpha-two"))
        self.commit("rename")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("skills/alpha was removed", out)

    def test_reusing_a_retired_path_fails(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/old/SKILL.md", skill_md("old"))
        self.commit("first")
        self.git("rm", "-q", "-r", "skills/old")
        base = self.commit("retire old")
        self.write("skills/old/SKILL.md", skill_md("old"))
        self.commit("bring old back")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("skills/old was used by a skill that was removed earlier", out)

    def test_a_path_renamed_away_on_main_is_retired(self):
        # A long body keeps every file similar enough that Git reports the
        # move as a rename (R), not a delete (D) plus an add.
        body = "".join(f"Step {i}: check the thing.\n" for i in range(200))
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/old/SKILL.md", skill_md("old") + body)
        self.write("skills/old/references/guide.md", body)
        self.commit("first")
        self.git("mv", "skills/old", "skills/new")
        self.write("skills/new/SKILL.md", skill_md("new") + body)
        base = self.commit("rename old to new on main")
        self.assertRegex(self.git("log", "-1", "--name-status", "--format="), r"(?m)^R\d+\tskills/old/")
        self.write("skills/old/SKILL.md", skill_md("old"))
        self.commit("bring old back")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("skills/old was used by a skill that was removed earlier", out)

    def test_a_path_that_only_existed_on_a_merged_branch_is_not_retired(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.commit("base")
        self.git("checkout", "-q", "-b", "feature")
        self.write("skills/draft/SKILL.md", skill_md("draft"))
        self.commit("add draft")
        self.git("mv", "skills/draft", "skills/final")
        self.write("skills/final/SKILL.md", skill_md("final"))
        self.commit("rename before merge")
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "merge feature", "feature")
        base = self.git("rev-parse", "HEAD")
        self.write("skills/draft/SKILL.md", skill_md("draft"))
        self.commit("add a skill named draft")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 0, out)

    def test_content_change_without_bump_fails_and_with_bump_passes(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/alpha/references/a.md", "one\n")
        base = self.commit("base")
        self.write("skills/alpha/references/a.md", "two\n")
        self.commit("change without bump")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 1, out)
        self.assertIn("metadata.version must go up from 1.0.0", out)
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.0.1"))
        self.write("skills/alpha/CHANGELOG.md", "## 1.0.1\n")
        self.commit("bump")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 0, out)

    def test_merge_base_not_base_tip_is_the_comparison(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        fork_point = self.commit("base")
        self.git("checkout", "-q", "-b", "feature")
        self.write("skills/beta/SKILL.md", skill_md("beta"))
        self.commit("add beta")
        self.git("checkout", "-q", "main")
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="2.0.0"))
        self.commit("main moves on")
        self.git("checkout", "-q", "feature")
        code, out = self.run_check("--base-ref", "main")
        self.assertEqual(code, 0, out)
        self.assertNotIn("went down", out)
        self.assertEqual(self.git("merge-base", "main", "feature"), fork_point)


def connector_yaml(version: str = "1.0.0", name: str = "acme") -> str:
    return (
        f"schema_version: 1\nname: {name}\nversion: {version}\ntype: mcp\nmcp:\n"
        '  endpoint: "https://mcp.acme.example/mcp"\n'
        "  auth:\n    - type: api_key\n      headers:\n"
        '        - { header: Authorization, label: API key, prefix: "Bearer " }\n'
    )


class ConnectorVersionTests(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("connectors/acme/connector.yaml", connector_yaml())
        self.write("connectors/acme/logo.svg", "<svg/>\n")
        self.write("connectors/releases.yaml", "schema_version: 1\nconnectors: []\n")
        self.write("connectors/schema/v1/published-files.json", '{"files": []}\n')
        self.base = self.commit("base")

    def test_a_changed_file_at_the_same_version_fails_until_the_version_goes_up(self):
        self.write("connectors/acme/logo.svg", "<svg></svg>\n")
        self.commit("a new logo")
        code, out = self.run_check("--base-ref", self.base, env={"GITHUB_ACTIONS": "true"})
        self.assertEqual(code, 1, out)
        self.assertIn(
            "FAIL  connectors/acme/connector.yaml:3: files in connectors/acme/ changed, so version must go up from 1.0.0",
            out,
        )
        self.assertIn("::error file=connectors/acme/connector.yaml,line=3,title=Skill publishing rules::", out)
        self.assertIn("1 skill(s) checked: 0 with errors. 1 other problem(s) in the repository.", out)
        self.write("connectors/acme/connector.yaml", connector_yaml("1.0.1"))
        self.commit("bump the version")
        code, out = self.run_check("--base-ref", self.base)
        self.assertEqual(code, 0, out)

    def test_a_removed_connector_folder_fails(self):
        self.git("rm", "-q", "-r", "connectors/acme")
        self.commit("remove acme")
        code, out = self.run_check("--base-ref", self.base)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  connectors/acme: the connector folder connectors/acme was removed", out)

    def test_the_schema_folder_and_shared_files_are_not_connectors(self):
        self.write("connectors/schema/v1/published-files.json", '{"files": [], "note": "changed"}\n')
        self.write("connectors/README.md", "# Connectors\n")
        self.commit("change shared files")
        code, out = self.run_check("--base-ref", self.base)
        self.assertEqual(code, 0, out)
        self.assertNotIn("connectors/schema", out)

    def test_a_new_connector_not_at_1_0_0_warns(self):
        self.write("connectors/bravo/connector.yaml", connector_yaml("2.0.0", name="bravo"))
        self.commit("add bravo")
        code, out = self.run_check("--base-ref", self.base)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  connectors/bravo/connector.yaml:3: a new connector starts at version 1.0.0, not 2.0.0", out)
        code, out = self.run_check()
        self.assertEqual(code, 0, out)
        self.assertNotIn("connectors/bravo", out)

    def test_without_a_base_only_the_version_itself_is_checked(self):
        self.write("connectors/acme/connector.yaml", connector_yaml('"1.1"'))
        self.commit("a two-part version")
        code, out = self.run_check()
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL  connectors/acme/connector.yaml:3: "version" is "1.1"; it must be MAJOR.MINOR.PATCH', out)


class PublishedFilesFromTheBaseTests(RepoTestCase):
    """skill-rules/published-files.json is read from the merge base, so a change to it applies once it has merged."""

    PATH = validate_skills.PUBLISHED_FILES_PATH

    def published_files(self, *exclude: str) -> str:
        return json.dumps({"description": "Test copy.", "exclude": list(exclude)})

    def test_a_name_the_pull_request_leaves_out_of_the_published_set_still_needs_a_bump(self):
        self.write(self.PATH, self.published_files("evals/", ".skilleval.yaml", "CHANGELOG.md"))
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.write("skills/alpha/NOTES.md", "one\n")
        base = self.commit("base")
        rules_dir = self.rules_copy()
        widened = self.published_files("evals/", ".skilleval.yaml", "CHANGELOG.md", "NOTES.md")
        (rules_dir / "published-files.json").write_text(widened, encoding="utf-8")
        self.write(self.PATH, widened)
        self.write("skills/alpha/NOTES.md", "two\n")
        merged = self.commit("leave NOTES.md out of the published set, and change it")
        code, out = self.run_check("--base-ref", base, rules_dir=rules_dir)
        self.assertEqual(code, 1, out)
        self.assertIn("metadata.version must go up from 1.0.0", out)
        # Once the list has merged, it applies.
        self.write("skills/alpha/NOTES.md", "three\n")
        self.commit("change NOTES.md again")
        code, out = self.run_check("--base-ref", merged, rules_dir=rules_dir)
        self.assertEqual(code, 0, out)

    def test_a_malformed_list_on_the_base_branch_cannot_run(self):
        self.write(self.PATH, '{"exclude": "evals/"}')
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        base = self.commit("base")
        code, out = self.run_check("--base-ref", base)
        self.assertEqual(code, 2, out)
        self.assertIn("published-files.json on the base branch is malformed", out)
        self.assertNotIn("skill(s) checked", out)


class StubResolver:
    """Answers GitHub lookups from a table: a login it doesn't list is a user that exists."""

    def __init__(self, answers: dict[str, github_logins.Lookup] | None = None):
        self.answers = {login.lower(): lookup for login, lookup in (answers or {}).items()}
        self.calls: list[str] = []

    def lookup(self, login: str) -> github_logins.Lookup:
        self.calls.append(login)
        return self.answers.get(login.lower(), github_logins.Lookup(github_logins.FOUND, account_type="User"))


class RefusingResolver:
    def lookup(self, login: str) -> github_logins.Lookup:
        raise AssertionError(f"looked up {login} with the flag off")


MISSING = github_logins.Lookup(github_logins.MISSING)
ORGANIZATION = github_logins.Lookup(github_logins.FOUND, account_type="Organization")
# The author line of skill_md().
AUTHOR_LINE = 5


class GitHubLoginTests(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.base = self.commit("base")

    def test_a_new_skill_whose_author_is_not_an_account_fails(self):
        self.write("skills/beta/SKILL.md", skill_md("beta", author="octocat, no-such-login"))
        self.commit("add beta")
        resolver = StubResolver({"no-such-login": MISSING})
        code, out = self.run_check("--base-ref", self.base, "--check-github-logins", login_resolver=resolver)
        self.assertEqual(code, 1, out)
        self.assertIn(
            f'FAIL  skills/beta/SKILL.md:{AUTHOR_LINE}: "no-such-login" in metadata.author isn\'t a GitHub account', out
        )
        self.assertEqual(resolver.calls, ["octocat", "no-such-login"])

    def test_an_unchanged_author_line_is_not_looked_up(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.0.1", extra='  tier: "aws-managed"\n'))
        self.commit("touch alpha but not its author")
        resolver = StubResolver({"octocat": MISSING})
        code, out = self.run_check("--base-ref", self.base, "--check-github-logins", login_resolver=resolver)
        self.assertEqual(code, 0, out)
        self.assertEqual(resolver.calls, [])

    def test_a_changed_author_line_looks_up_only_the_names_it_adds(self):
        self.write("skills/alpha/SKILL.md", skill_md("alpha", version="1.0.1", author="OctoCat, hubot"))
        self.commit("add a co-author")
        resolver = StubResolver()
        code, out = self.run_check("--base-ref", self.base, "--check-github-logins", login_resolver=resolver)
        self.assertEqual(code, 0, out)
        self.assertEqual(resolver.calls, ["hubot"])

    def test_a_team_is_looked_up_by_its_organization(self):
        self.write("skills/beta/SKILL.md", skill_md("beta", author="octo-org/octo-team"))
        self.write("skills/gamma/SKILL.md", skill_md("gamma", author="gone-org/octo-team"))
        self.write("skills/delta/SKILL.md", skill_md("delta", author="octocat/octo-team"))
        self.commit("add three team-owned skills")
        resolver = StubResolver({"octo-org": ORGANIZATION, "gone-org": MISSING})
        code, out = self.run_check("--base-ref", self.base, "--check-github-logins", login_resolver=resolver)
        self.assertEqual(code, 1, out)
        self.assertEqual(sorted(resolver.calls), ["gone-org", "octo-org", "octocat"])
        self.assertNotIn("skills/beta", out)
        self.assertIn('"gone-org/octo-team" in metadata.author is a team of "gone-org", which isn\'t a GitHub account', out)
        self.assertIn('"octocat" is a GitHub user, not an organization, so it has no teams', out)

    def test_a_lookup_github_cannot_answer_is_a_warning(self):
        reason = "GitHub's API rate limit was reached"
        self.write("skills/beta/SKILL.md", skill_md("beta", author="hubot"))
        self.commit("add beta")
        resolver = StubResolver({"hubot": github_logins.Lookup(github_logins.UNKNOWN, reason=reason)})
        code, out = self.run_check("--base-ref", self.base, "--check-github-logins", login_resolver=resolver)
        self.assertEqual(code, 0, out)
        self.assertIn(
            f'WARN  skills/beta/SKILL.md:{AUTHOR_LINE}: "hubot" in metadata.author wasn\'t looked up on GitHub, '
            f"because {reason}",
            out,
        )

    def test_without_a_token_every_new_name_is_a_warning_and_nothing_is_requested(self):
        self.write("skills/beta/SKILL.md", skill_md("beta", author="hubot"))
        self.commit("add beta")
        with mock.patch.object(github_logins.urllib.request.OpenerDirector, "open", side_effect=AssertionError):
            code, out = self.run_check("--base-ref", self.base, "--check-github-logins")
        self.assertEqual(code, 0, out)
        self.assertIn("because no GitHub token is set in GH_TOKEN or GITHUB_TOKEN", out)

    def test_without_the_flag_nothing_is_looked_up(self):
        self.write("skills/beta/SKILL.md", skill_md("beta", author="no-such-login"))
        self.commit("add beta")
        code, out = self.run_check("--base-ref", self.base, login_resolver=RefusingResolver())
        self.assertEqual(code, 0, out)

    def test_without_a_base_every_author_is_looked_up(self):
        self.write("skills/beta/SKILL.md", skill_md("beta", author="hubot"))
        self.commit("add beta")
        resolver = StubResolver()
        code, out = self.run_check("--check-github-logins", login_resolver=resolver)
        self.assertEqual(code, 0, out)
        self.assertEqual(resolver.calls, ["octocat", "hubot"])

    def test_a_malformed_author_is_reported_once_and_not_looked_up(self):
        self.write("skills/beta/SKILL.md", skill_md("beta", author='"octo cat"'))
        self.commit("add beta")
        resolver = StubResolver()
        code, out = self.run_check("--base-ref", self.base, "--check-github-logins", login_resolver=resolver)
        self.assertEqual(code, 1, out)
        self.assertIn("must be one or more GitHub usernames or teams", out)
        self.assertEqual(resolver.calls, [])


class SelfCheckTests(RepoTestCase):
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

    def test_a_wrong_connector_case_stops_the_check(self):
        rules_dir = self.rules_copy()
        path = rules_dir / "connector-conformance-cases.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        unchanged = next(case for case in document["cases"] if case["id"] == "unchanged")
        unchanged["expect"], unchanged["error"] = "fail", "anything"
        path.write_text(json.dumps(document), encoding="utf-8")
        code, out = self.run_check("--self-check-only", rules_dir=rules_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("connector case unchanged: expected an error containing 'anything'", out)

    def test_changed_hash_function_stops_the_check(self):
        rules_dir = self.rules_copy()
        path = rules_dir / validate_skills.CONFORMANCE_FILE
        document = json.loads(path.read_text(encoding="utf-8"))
        document["content_hash"]["sha256"] = "0" * 64
        path.write_text(json.dumps(document), encoding="utf-8")
        self.write("skills/alpha/SKILL.md", skill_md("alpha"))
        self.commit("base")
        code, out = self.run_check("--self-check-only", rules_dir=rules_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("content hash of the golden fixture", out)

    def test_malformed_rule_data_cannot_run(self):
        rules_dir = self.rules_copy()
        (rules_dir / "vocabulary.json").write_text("{not json", encoding="utf-8")
        code, out = self.run_check("--self-check-only", rules_dir=rules_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("cannot read", out)


if __name__ == "__main__":
    unittest.main()
