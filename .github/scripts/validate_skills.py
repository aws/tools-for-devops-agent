#!/usr/bin/env python3
"""Check that every skill in skills/ can be published.

Skills on `main` are published automatically, so this check applies the
rules in skill_checks.py to every skill folder on every pull request, not only
to the skills the pull request changes. See the "Skill
Publishing Rules" section of CONTRIBUTING.md.

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

import yaml

import skill_checks as sc

SKILLS_DIR = "skills"
CONNECTORS_DIR = "connectors"
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
    always_visible: bool = False


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


def repository_results(repo_root: Path, rev: str) -> list[SkillResult]:
    """Rules outside skill folders that still decide what is published.

    Skills are published from GitHub's archive of the whole repository, which
    must contain no symbolic link, and a root .gitattributes setting can change
    the bytes that archive holds for a skill's files.
    """
    listing = _git(repo_root, "ls-tree", "-r", "-z", "--full-tree", rev)
    results: list[SkillResult] = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, _, raw_path = record.partition(b"\t")
        mode, kind, oid = meta.decode("ascii").split(" ")
        path = _decode_path(raw_path)
        if path.startswith(f"{SKILLS_DIR}/"):
            continue  # Checked per skill.
        if mode == "120000":
            message = (
                f"{path} is a symbolic link; skills are published from an archive of the whole repository, "
                "which must not contain any"
            )
            results.append(SkillResult(path, [sc.Finding("error", message)], is_skill=False))
        elif path == ".gitattributes" and kind == "blob":
            # Git stops reading the file at its first NUL byte, so this does too.
            text = _read_blobs(repo_root, [oid])[0].split(b"\0", 1)[0].decode("utf-8", "replace")
            findings = [
                sc.Finding(
                    "error",
                    "this line can change how Git archives files under skills/, so the published files could "
                    "differ from what the check reads; scope it to another folder, or remove the setting",
                    line=number,
                )
                # Git splits the file at newlines only, so line numbers match GitHub's.
                for number, line in enumerate(text.split("\n"), 1)
                if sc.gitattributes_line_applies_to_skills(line)
            ]
            if findings:
                results.append(SkillResult(path, findings, is_skill=False))
    return results


def is_shallow(repo_root: Path) -> bool:
    return _git(repo_root, "rev-parse", "--is-shallow-repository").decode("ascii").strip() == "true"


def retired_skills(repo_root: Path, base: str, present: set[str]) -> frozenset[str]:
    """Skill folder names that `base`'s first-parent history deleted and that `base` doesn't have.

    First-parent only, so a path that existed only inside a pull request's
    branch, renamed before it merged, never counts as retired. A merge commit
    is compared with its first parent, which is how a pull request's removal
    reaches `main`. Renames are turned off, so a folder renamed away on `main`
    shows as deleted.
    """
    out = _git(
        repo_root,
        "log",
        "--first-parent",
        "--diff-merges=first-parent",
        "--no-renames",
        "--format=",
        "--name-only",
        "--diff-filter=D",
        "-z",
        base,
        "--",
        f"{SKILLS_DIR}/",
    )
    names = set()
    for raw in out.split(b"\0"):
        parts = _decode_path(raw).strip().split("/")
        if len(parts) >= 3 and parts[0] == SKILLS_DIR:
            names.add(parts[1])
    return frozenset(names - present)


def connector_skill_references(repo_root: Path, rev: str) -> tuple[dict[str, list[str]], list[SkillResult]]:
    """Skill name -> the connectors whose connector.yaml lists it under skills: (recommended skills).

    Also returns a warning for each connector.yaml that can't be read, isn't a
    mapping, has a skills: value that isn't a list of skill names, or writes
    skills: more than once, so a broken file doesn't silently skip the check. The YAML is composed, not
    constructed, so a value PyYAML can't build (a bad date, say) can't stop
    the check.
    """
    listing = _git(repo_root, "ls-tree", "-r", "-z", "--full-tree", rev, "--", f"{CONNECTORS_DIR}/")
    files: list[tuple[str, str]] = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, _, raw_path = record.partition(b"\t")
        _, kind, oid = meta.decode("ascii").split(" ")
        parts = _decode_path(raw_path).split("/")
        if kind == "blob" and len(parts) == 3 and parts[2] == "connector.yaml":
            files.append((parts[1], oid))
    references: dict[str, list[str]] = {}
    unreadable: list[SkillResult] = []
    for (connector, _), data in zip(files, _read_blobs(repo_root, [oid for _, oid in files])):
        try:
            problem, skills = _recommended_skills(*_compose_connector(data.decode("utf-8")))
        except (UnicodeDecodeError, yaml.YAMLError, RecursionError):
            problem, skills = "can't be read as YAML, so its skills: list wasn't checked", []
        if problem:
            message = f"{problem} against deprecated skills"
            path = f"{CONNECTORS_DIR}/{connector}/connector.yaml"
            unreadable.append(SkillResult(path, [sc.Finding("warning", message)], is_skill=False, always_visible=True))
        for skill in skills:
            references.setdefault(skill, []).append(connector)
    return references, unreadable


def _compose_connector(text: str) -> tuple[yaml.Node | None, int]:
    """The YAML node tree of a connector.yaml, with merge keys (<<) resolved, and how many skills: keys it writes.

    No values are built. The count is taken before merging, since a merge can
    supply skills: as well without the file being ambiguous.
    """
    loader = yaml.SafeLoader(text)
    try:
        root = loader.get_single_node()
        written = 0
        if isinstance(root, yaml.MappingNode):
            written = sum(1 for key, _ in root.value if isinstance(key, yaml.ScalarNode) and key.value == "skills")
            loader.flatten_mapping(root)
        return root, written
    finally:
        loader.dispose()


def _recommended_skills(root: yaml.Node | None, written: int) -> tuple[str | None, list[str]]:
    """The skill names under a connector.yaml's skills: key, and what kept any of it from being checked."""
    if not isinstance(root, yaml.MappingNode):
        return "isn't a YAML mapping, so its skills: list wasn't checked", []
    values = [value for key, value in root.value if isinstance(key, yaml.ScalarNode) and key.value == "skills"]
    if not values:
        return None, []
    if not isinstance(values[-1], yaml.SequenceNode):
        return "has a skills: value that isn't a list, so it wasn't checked", []
    items = values[-1].value  # As in PyYAML, the last skills: key wins.
    names = [item.value for item in items if isinstance(item, yaml.ScalarNode) and item.tag == sc.STR_TAG]
    if len(names) < len(items):
        return "has a skills: entry that isn't a skill name, so that entry wasn't checked", names
    if written > 1:
        return "has more than one skills: key, so only the last one was checked", names
    return None, names


def check_repository(
    repo_root: Path, rules: sc.Rules, base: str | None, head_ref: str
) -> tuple[list[SkillResult], set[str] | None]:
    """Results for every skill at `head_ref`, and the skills touched since `base` (None without a base).

    With a base, each skill is also compared with its merge-base copy: a folder
    can't be removed or reuse a retired path, the version must go up when the
    published files change, and the lines the pull request adds are checked
    for internal host and tool names.
    """
    head_trees, results = read_skills(repo_root, head_ref)
    results += repository_results(repo_root, head_ref)
    touched = None
    base_trees: dict[str, sc.SkillTree] = {}
    history: dict[str, list[sc.Finding]] = {}
    if base is not None:
        touched = touched_skills(repo_root, base, head_ref)
        base_trees, _ = read_skills(repo_root, base)
        retired: frozenset[str] = frozenset()
        if is_shallow(repo_root):
            message = "the clone is shallow, so skill paths retired earlier in history were not checked; use fetch-depth: 0"
            results.append(SkillResult(SKILLS_DIR, [sc.Finding("warning", message)], is_skill=False, always_visible=True))
        else:
            retired = retired_skills(repo_root, base, set(base_trees))
        for name in sorted(set(base_trees) | set(head_trees)):
            history[name] = sc.check_history(name, base_trees.get(name), head_trees.get(name), rules, retired)
        for name in sorted(set(base_trees) - set(head_trees)):
            results.append(SkillResult(f"{SKILLS_DIR}/{name}", history[name], is_skill=False))
    recommended, unreadable = connector_skill_references(repo_root, head_ref)
    results += unreadable
    for name in sorted(head_trees):
        findings, info = sc.check_skill(head_trees[name], rules)
        if base is not None:
            findings += sc.check_added_content(base_trees.get(name), head_trees[name], rules)
        if info is not None and info.metadata.get("deprecated") == "true":
            for connector in recommended.get(name, []):
                findings.append(
                    sc.Finding(
                        "error",
                        f"the skill is deprecated, but {CONNECTORS_DIR}/{connector}/connector.yaml still recommends it "
                        "under skills:. Remove it from that list in the same pull request, or the connector fails "
                        "validation",
                        "SKILL.md",
                        info.deprecated_line,
                    )
                )
        results.append(SkillResult(f"{SKILLS_DIR}/{name}", findings + history.get(name, [])))
    return results, touched


# --- Reporting ------------------------------------------------------------------


def _printable(text: str) -> str:
    """Text any output can encode: a path that isn't UTF-8 shows its bytes as \\x escapes."""
    try:
        raw = text.encode("utf-8", "surrogateescape")
    except UnicodeEncodeError:
        raw = text.encode("utf-8", "backslashreplace")
    return raw.decode("utf-8", "backslashreplace")


def _escape_data(text: str) -> str:
    return _printable(text).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(text: str) -> str:
    return _escape_data(text).replace(":", "%3A").replace(",", "%2C")


def _plain(text: str) -> str:
    """One log line, whatever the text holds: a newline in a path or value can't start a workflow command."""
    return _printable(text).replace("\r", "\\r").replace("\n", "\\n")


def _markdown(text: str) -> str:
    return _plain(text).replace("|", "\\|").replace("`", "'")


def _location(result: SkillResult, finding: sc.Finding) -> str:
    return f"{result.path}/{finding.path}" if finding.path else result.path


def _visible(result: SkillResult, touched: set[str] | None) -> list[sc.Finding]:
    """Errors always; warnings only for touched skills (or every skill when there is no base)."""
    name = result.path.split("/", 1)[-1]
    show_warnings = result.always_visible or touched is None or name in touched
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
    failed_skills = sum(1 for r in failed if r.is_skill)
    other = len(failed) - failed_skills
    print(
        f"\n{skill_count} skill(s) checked: {failed_skills} with errors."
        + (f" {other} other problem(s) in the repository." if other else "")
        + (f" {hidden} warning(s) on skills this change doesn't touch are not shown." if hidden else "")
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
        golden_files, golden_hash = sc.load_golden_hash(rules_dir / CONFORMANCE_FILE)
    except ValueError as exc:
        return [str(exc)]
    problems = sc.run_conformance(cases, rules)
    actual = sc.content_hash(golden_files)
    if actual != golden_hash:
        problems.append(f"the content hash of the golden fixture is {actual}, not {golden_hash}")
    return problems


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
            # one, so a new extension takes effect only after the
            # skills/.gitignore change that adds it has merged.
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
