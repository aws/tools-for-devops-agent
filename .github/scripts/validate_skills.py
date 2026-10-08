#!/usr/bin/env python3
"""Check that every skill in skills/ can be published.

Skills on `main` are published as one set, so one skill that breaks a rule
stops every skill from being published. This check therefore applies the
rules in skill_checks.py to every skill folder on every pull request, not only
to the skills the pull request changes. See the "Skill Publishing Rules"
section of CONTRIBUTING.md.

Skills are read from Git objects, never from the working tree, so a run sees
exactly what a commit contains (file modes included) and nothing a checkout
or an editor added. Commit a change before checking it locally.

Errors from any skill fail the check. Warnings are printed only for the skills
the pull request touches, so an old warning on an untouched skill doesn't
appear on every pull request.

Before checking any skill, the script runs the cases in
skill-rules/conformance-cases.json through the same rules and stops with exit
code 2 if any case gives the wrong result.

Usage:
    python3 .github/scripts/validate_skills.py --base-ref origin/main
    python3 .github/scripts/validate_skills.py              # whole tree, no base
    python3 .github/scripts/validate_skills.py --self-check-only

Exit codes: 0 every skill passes (warnings allowed), 1 a skill breaks a rule,
2 the check could not run (a Git failure, malformed rule data, or a failed
self-check), which says nothing about the pull request's content.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import skill_checks as sc

SKILLS_DIR = "skills"
RULES_DIR = Path(__file__).resolve().parent / "skill-rules"
CONFORMANCE_FILE = "conformance-cases.json"
DOCS_HINT = 'See the "Skill Publishing Rules" section of CONTRIBUTING.md.'

# Files that may sit directly in skills/ without being a skill.
SKILLS_DIR_HOUSEKEEPING = frozenset({".gitignore"})


class GitError(Exception):
    pass


@dataclass
class SkillResult:
    path: str  # repository-relative, such as skills/my-skill
    findings: list[sc.Finding]
    is_skill: bool = True


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git(repo_root: Path, *args: str, stdin: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        input=stdin,
        capture_output=True,
        env={**os.environ, "GIT_LITERAL_PATHSPECS": "1"},
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout


def _decode_path(raw: bytes) -> str:
    return raw.decode("utf-8", "surrogateescape")


def read_skills(repo_root: Path, rev: str) -> tuple[dict[str, sc.SkillTree], list[SkillResult]]:
    """Every skill folder at `rev`, plus results for entries in skills/ that aren't skill folders."""
    listing = _git(repo_root, "ls-tree", "-r", "-z", "--full-tree", rev, "--", f"{SKILLS_DIR}/")
    trees: dict[str, sc.SkillTree] = {}
    loose: list[SkillResult] = []
    blobs: list[tuple[str, str, str, str]] = []  # (skill, relative path, mode, oid)
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, _, raw_path = record.partition(b"\t")
        mode, kind, oid = meta.decode("ascii").split(" ")
        path = _decode_path(raw_path)
        _, _, rest = path.partition("/")
        skill, _, inner = rest.partition("/")
        if not inner:
            if skill in SKILLS_DIR_HOUSEKEEPING:
                continue
            message = (
                f"{path} is a Git submodule; a skill must be a regular folder"
                if kind == "commit"
                else f"{path} is a file directly under {SKILLS_DIR}/; every file must be inside a skill folder"
            )
            loose.append(SkillResult(path, [sc.Finding("error", message)], is_skill=False))
            continue
        trees.setdefault(skill, sc.SkillTree(skill))
        if kind == "blob":
            blobs.append((skill, inner, mode, oid))
        else:
            trees[skill].entries[inner] = sc.Entry(inner, mode, b"")
    for (skill, inner, mode, _), data in zip(blobs, _read_blobs(repo_root, [b[3] for b in blobs])):
        trees[skill].entries[inner] = sc.Entry(inner, mode, data)
    return trees, loose


def _read_blobs(repo_root: Path, oids: list[str]) -> list[bytes]:
    if not oids:
        return []
    out = _git(repo_root, "cat-file", "--batch", stdin="".join(f"{oid}\n" for oid in oids).encode("ascii"))
    blobs: list[bytes] = []
    pos = 0
    for oid in oids:
        header_end = out.find(b"\n", pos)
        header = out[pos:header_end].decode("ascii", "replace").split(" ") if header_end != -1 else []
        if len(header) != 3 or header[0] != oid or header[1] != "blob" or not header[2].isdigit():
            raise GitError(f"git cat-file could not read object {oid}: {' '.join(header) or 'no output'}")
        start, size = header_end + 1, int(header[2])
        if len(out) < start + size:
            raise GitError(f"git cat-file returned a truncated object {oid}")
        blobs.append(out[start:start + size])
        pos = start + size + 1
    return blobs


def merge_base(repo_root: Path, base_ref: str, head_ref: str) -> str:
    try:
        return _git(repo_root, "merge-base", base_ref, head_ref).decode("ascii").strip()
    except GitError:
        # No common history (for example a grafted clone): compare with the base itself.
        return _git(repo_root, "rev-parse", "--verify", f"{base_ref}^{{commit}}").decode("ascii").strip()


def touched_skills(repo_root: Path, base: str, head: str) -> set[str]:
    out = _git(repo_root, "diff", "--name-only", "--no-renames", "-z", base, head, "--", f"{SKILLS_DIR}/")
    names = set()
    for raw in out.split(b"\0"):
        parts = _decode_path(raw).split("/")
        if len(parts) >= 3:
            names.add(parts[1])
    return names


def uncommitted_skill_changes(repo_root: Path) -> bool:
    try:
        return bool(_git(repo_root, "status", "--porcelain", "--", f"{SKILLS_DIR}/").strip())
    except GitError:
        return False


def read_gitignore(repo_root: Path, rev: str) -> str:
    return _git(repo_root, "show", f"{rev}:{SKILLS_DIR}/.gitignore").decode("utf-8")


def check_repository(
    repo_root: Path, rules: sc.Rules, base: str | None, head_ref: str
) -> tuple[list[SkillResult], set[str] | None]:
    """Results for every skill at `head_ref`, and the skills touched since `base` (None without a base)."""
    head_trees, results = read_skills(repo_root, head_ref)
    touched = touched_skills(repo_root, base, head_ref) if base is not None else None
    for name in sorted(head_trees):
        findings, _ = sc.check_skill(head_trees[name], rules)
        results.append(SkillResult(f"{SKILLS_DIR}/{name}", findings))
    return results, touched


# --- Reporting ------------------------------------------------------------------


def _escape_data(text: str) -> str:
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(text: str) -> str:
    return _escape_data(text).replace(":", "%3A").replace(",", "%2C")


def _plain(text: str) -> str:
    """One log line, whatever the text holds: a newline in a path or value can't start a workflow command."""
    return text.replace("\r", "\\r").replace("\n", "\\n")


def _markdown(text: str) -> str:
    return _plain(text).replace("|", "\\|").replace("`", "'")


def _location(result: SkillResult, finding: sc.Finding) -> str:
    return f"{result.path}/{finding.path}" if finding.path else result.path


def _visible(result: SkillResult, touched: set[str] | None) -> list[sc.Finding]:
    """Errors always; warnings only for touched skills (or every skill when there is no base)."""
    name = result.path.split("/", 1)[-1]
    show_warnings = touched is None or name in touched
    return [f for f in result.findings if f.severity == "error" or show_warnings]


def report(results: list[SkillResult], touched: set[str] | None) -> int:
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    failed = [r for r in results if any(f.severity == "error" for f in r.findings)]
    hidden = 0
    for result in results:
        visible = _visible(result, touched)
        hidden += len(result.findings) - len(visible)
        for finding in visible:
            location = _location(result, finding)
            where = f"{location}:{finding.line}" if finding.line else location
            label = "FAIL" if finding.severity == "error" else "WARN"
            print(f"{label}  {_plain(where)}: {_plain(finding.message)}")
            if in_actions:
                command = "error" if finding.severity == "error" else "warning"
                props = f"file={_escape_property(location)}"
                if finding.line:
                    props += f",line={finding.line}"
                props += f",title={_escape_property('Skill publishing rules')}"
                print(f"::{command} {props}::{_escape_data(f'{finding.message}. {DOCS_HINT}')}")
    skill_count = sum(1 for r in results if r.is_skill)
    print(
        f"\n{skill_count} skill(s) checked: {len(failed)} with errors."
        + (f" {hidden} warning(s) on skills this pull request doesn't touch are not shown." if hidden else "")
    )
    _write_summary(results, touched, failed)
    return 1 if failed else 0


def _write_summary(results: list[SkillResult], touched: set[str] | None, failed: list[SkillResult]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    lines = ["## Skill publishing rules", ""]
    if not failed:
        lines.append("Every skill passes the publishing rules.")
    else:
        lines += ["| Skill | Problem |", "|---|---|"]
        for result in failed:
            for finding in result.findings:
                if finding.severity == "error":
                    where = _location(result, finding) + (f":{finding.line}" if finding.line else "")
                    lines.append(f"| `{_markdown(where)}` | {_markdown(finding.message)} |")
    warnings = [(r, f) for r in results for f in _visible(r, touched) if f.severity == "warning"]
    if warnings:
        lines += ["", "**Warnings** (these don't fail the check):", ""]
        lines += [f"- `{_markdown(_location(r, f))}`: {_markdown(f.message)}" for r, f in warnings]
    lines += ["", DOCS_HINT, ""]
    with open(summary_path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


# --- Entry point ------------------------------------------------------------------


def self_check(rules_dir: Path, rules: sc.Rules) -> list[str]:
    try:
        cases = sc.load_cases(rules_dir / CONFORMANCE_FILE)
    except ValueError as exc:
        return [str(exc)]
    return sc.run_conformance(cases, rules)


def _could_not_run(exc: GitError) -> int:
    print(f"::error title=Skill publishing rules could not run::{_escape_data(str(exc))}")
    print("The check could not read the repository. This is not a finding about the pull request.")
    return 2


def main(argv: list[str] | None = None, repo_root: Path | None = None, rules_dir: Path = RULES_DIR) -> int:
    try:
        return _run(argv, repo_root, rules_dir)
    except Exception as exc:  # noqa: BLE001 - any crash means the check didn't run, never a finding.
        print(f"::error title=Skill publishing rules could not run::{_escape_data(f'{type(exc).__name__}: {exc}')}")
        print("The check stopped unexpectedly. This is not a finding about the pull request.")
        return 2


def _run(argv: list[str] | None, repo_root: Path | None, rules_dir: Path) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-ref", help="the branch the pull request merges into, such as origin/main")
    parser.add_argument("--head-ref", default="HEAD", help="the commit to check (default: HEAD)")
    parser.add_argument("--self-check-only", action="store_true", help="run only the conformance cases")
    args = parser.parse_args(argv)
    repo_root = repo_root or _repo_root()

    base = None
    try:
        if args.self_check_only:
            # The cases test the rules, not the repository, so no Git is needed.
            gitignore = (repo_root / SKILLS_DIR / ".gitignore").read_text(encoding="utf-8")
        else:
            # The extension allowlist is read from the merge base when there is
            # one, so a pull request can't widen it for its own files.
            base = merge_base(repo_root, args.base_ref, args.head_ref) if args.base_ref else None
            gitignore = read_gitignore(repo_root, base or args.head_ref)
    except OSError as exc:
        print(f"::error title=Skill publishing rules::cannot read {SKILLS_DIR}/.gitignore: {_escape_data(str(exc))}")
        return 2
    except GitError as exc:
        return _could_not_run(exc)
    try:
        rules = sc.load_rules(rules_dir, gitignore)
    except ValueError as exc:
        print(f"::error title=Skill publishing rules::{_escape_data(str(exc))}")
        return 2
    problems = self_check(rules_dir, rules)
    if problems:
        for problem in problems:
            print(f"::error title=Self-check failed::{_escape_data(problem)}")
        print("The rules gave the wrong result on their own conformance cases, so no skill was checked.")
        return 2
    if args.self_check_only:
        print("Self-check passed.")
        return 0

    try:
        if args.head_ref == "HEAD" and uncommitted_skill_changes(repo_root):
            print(f"note: uncommitted changes under {SKILLS_DIR}/ are not checked; commit them first.\n")
        results, touched = check_repository(repo_root, rules, base, args.head_ref)
    except GitError as exc:
        return _could_not_run(exc)
    return report(results, touched)


if __name__ == "__main__":
    sys.exit(main())
