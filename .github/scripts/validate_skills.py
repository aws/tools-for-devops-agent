#!/usr/bin/env python3
"""Check that every skill in skills/, and every connector in connectors/, can be published.

Skills on `main` are published automatically, so this check applies the
rules in skill_checks.py to every skill folder on every pull request, not only
to the skills the pull request changes. See the "Skill
Publishing Rules" section of CONTRIBUTING.md.

Connectors on `main` are published the same way, so every connectors/<name>/
folder is checked by the rules in connector_checks.py too.

Skills are read from Git objects, never from the working tree, so a run sees
exactly what a commit contains (file modes included) and nothing a checkout
or an editor added. Commit a change before checking it locally.

Errors from any skill fail the check. Warnings are printed only for the skills
the pull request touches, so an old warning on an untouched skill doesn't
appear on every pull request.

Before checking any skill, the script runs the cases in
skill-rules/conformance-cases.json through the same rules and stops with exit
code 2 if any case gives the wrong result.

With --check-github-logins, the metadata.author names that a pull request adds
are also looked up on GitHub (github_logins.py).

Usage:
    python3 .github/scripts/validate_skills.py --base-ref origin/main
    python3 .github/scripts/validate_skills.py              # whole tree, no base
    python3 .github/scripts/validate_skills.py --self-check-only
    GH_TOKEN=... python3 .github/scripts/validate_skills.py --base-ref origin/main --check-github-logins

Exit codes: 0 every skill passes (warnings allowed), 1 a skill breaks a rule,
2 the check could not run (a Git failure, malformed rule data, or a failed
self-check), which says nothing about the pull request's content.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import yaml

import connector_checks as cc
import github_logins
import skill_checks as sc

SKILLS_DIR = "skills"
CONNECTORS_DIR, CONNECTOR_FILE = cc.CONNECTORS_DIR, cc.CONNECTOR_FILE
MAX_CONNECTOR_FILE_BYTES = 32_768
RELEASES_PATH = f"{CONNECTORS_DIR}/releases.yaml"
RULES_DIR = Path(__file__).resolve().parent / "skill-rules"
# Read from the merge base, like skills/.gitignore.
PUBLISHED_FILES_PATH = f"{sc.RULES_DIR_DISPLAY}/{sc.PUBLISHED_FILES_FILE}"
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


def _ls_tree(repo_root: Path, rev: str, *paths: str) -> Iterator[tuple[str, str, str, str]]:
    """(mode, kind, oid, path) for each entry of `git ls-tree -r` at `rev`, under `paths` when there are any."""
    for record in _git(repo_root, "ls-tree", "-r", "-z", "--full-tree", rev, "--", *paths).split(b"\0"):
        if record:
            meta, _, raw_path = record.partition(b"\t")
            mode, kind, oid = meta.decode("ascii").split(" ")
            yield mode, kind, oid, _decode_path(raw_path)


def _read_file(repo_root: Path, rev: str, path: str) -> bytes | None:
    """The bytes of the file at `path` in `rev`, or None when `rev` has no file there."""
    oids = [oid for _, kind, oid, found in _ls_tree(repo_root, rev, path) if kind == "blob" and found == path]
    return _read_blobs(repo_root, oids)[0] if oids else None


def read_skills(repo_root: Path, rev: str) -> tuple[dict[str, sc.SkillTree], list[SkillResult]]:
    """Every skill folder at `rev`, plus results for entries in skills/ that aren't skill folders."""
    trees: dict[str, sc.SkillTree] = {}
    loose: list[SkillResult] = []
    blobs: list[tuple[str, str, str, str]] = []  # (skill, relative path, mode, oid)
    for mode, kind, oid, path in _ls_tree(repo_root, rev, f"{SKILLS_DIR}/"):
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
    data = _read_file(repo_root, rev, f"{SKILLS_DIR}/.gitignore")
    if data is None:
        raise GitError(f"{rev} has no {SKILLS_DIR}/.gitignore")
    return data.decode("utf-8")


def repository_results(repo_root: Path, rev: str) -> list[SkillResult]:
    """Rules outside skill folders that still decide what is published.

    Skills are published from GitHub's archive of the whole repository, which
    must contain no symbolic link, and a root .gitattributes setting can change
    the bytes that archive holds for a skill's files.
    """
    results: list[SkillResult] = []
    for mode, kind, oid, path in _ls_tree(repo_root, rev):
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


def read_connectors(repo_root: Path, rev: str) -> dict[str, sc.SkillTree]:
    """Every connectors/<name>/ folder at `rev`.

    Files directly in connectors/, such as releases.yaml, belong to no folder,
    and connectors/schema/ holds the schemas, not a connector.
    """
    blobs: list[tuple[str, str, str, str]] = []  # (connector, path in its folder, mode, oid)
    for mode, kind, oid, path in _ls_tree(repo_root, rev, f"{CONNECTORS_DIR}/"):
        parts = path.split("/", 2)
        if kind == "blob" and len(parts) == 3 and parts[1] != cc.SCHEMA_FOLDER:
            blobs.append((parts[1], parts[2], mode, oid))
    folders: dict[str, sc.SkillTree] = {}
    for (name, inner, mode, _), data in zip(blobs, _read_blobs(repo_root, [blob[3] for blob in blobs])):
        folders.setdefault(name, sc.SkillTree(name)).entries[inner] = sc.Entry(inner, mode, data)
    return folders


def connector_results(repo_root: Path, base: str | None, head_ref: str) -> list[SkillResult]:
    """The connector_checks.py rules for every connector folder, compared with the merge base when there is one.

    Every finding shows, as for the connector YAML: a warning can only come from
    a folder that differs from its merge-base copy.
    """
    head_folders = read_connectors(repo_root, head_ref)
    base_folders = read_connectors(repo_root, base) if base is not None else {}
    results: list[SkillResult] = []
    for name in sorted(set(head_folders) | set(base_folders)):
        head = head_folders.get(name)
        findings = cc.check_connector(name, head) if head is not None else []
        if base is not None:
            findings += cc.check_history(name, base_folders.get(name), head)
        if findings:
            results.append(SkillResult(f"{CONNECTORS_DIR}/{name}", findings, is_skill=False, always_visible=True))
    return results


def base_published_excludes(data: bytes) -> tuple[str, ...]:
    """The exclude list in the merge base's skill-rules/published-files.json. Raises ValueError when malformed.

    The base branch's list applies, so a change to it takes effect only once it
    has merged, as a new extension in skills/.gitignore does.
    """
    try:
        return sc.published_excludes(json.loads(data.decode("utf-8")))
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"{PUBLISHED_FILES_PATH} on the base branch is malformed: {exc}") from exc


def connector_skill_references(repo_root: Path, rev: str) -> tuple[dict[str, list[str]], list[SkillResult]]:
    """Skill name -> the connectors whose connector.yaml lists it under skills: (recommended skills).

    Also returns an error for each connector.yaml, and for connectors/releases.yaml,
    that isn't UTF-8 or that breaks the YAML rules of sc.read_yaml, since the
    connectors are published from the same files. A connector.yaml whose skills:
    value isn't a list of skill names gets a warning, so a broken file doesn't
    silently skip the check; the connector version rules report one that isn't a
    mapping.
    """
    files: list[tuple[str, str]] = []
    for _, kind, oid, path in _ls_tree(repo_root, rev, f"{CONNECTORS_DIR}/"):
        parts = path.split("/")
        is_connector_file = len(parts) == 3 and parts[2] == CONNECTOR_FILE
        if kind == "blob" and (is_connector_file or path == RELEASES_PATH):
            files.append((path, oid))
    references: dict[str, list[str]] = {}
    results: list[SkillResult] = []
    for (path, _), data in zip(files, _read_blobs(repo_root, [oid for _, oid in files])):
        root, findings = _read_connector_yaml(path, data)
        if path != RELEASES_PATH and not findings:
            problem, skills = _recommended_skills(root)
            if problem:
                findings.append(sc.Finding("warning", f"{problem} against deprecated skills"))
            for skill in skills:
                references.setdefault(skill, []).append(path.split("/")[1])
        if findings:
            results.append(SkillResult(path, findings, is_skill=False, always_visible=True))
    return references, results


def _read_connector_yaml(path: str, data: bytes) -> tuple[yaml.Node | None, list[sc.Finding]]:
    """The YAML node tree of a file under connectors/, or None with an error for each problem."""
    file_name = path.rsplit("/", 1)[-1]
    if file_name == CONNECTOR_FILE and len(data) > MAX_CONNECTOR_FILE_BYTES:
        message = f"{file_name} is {len(data):,} bytes; the limit is {MAX_CONNECTOR_FILE_BYTES:,}"
        return None, [sc.Finding("error", message)]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [sc.Finding("error", f"{file_name} is not valid UTF-8", line=data.count(b"\n", 0, exc.start) + 1)]
    root, problems = sc.read_yaml(text, file_name, first_line=1)
    return root, [sc.Finding("error", message, line=line) for line, message in problems]


def _recommended_skills(root: yaml.Node | None) -> tuple[str | None, list[str]]:
    """The skill names under a connector.yaml's skills: key, and what kept any of it from being checked.

    A root that isn't a mapping has no skills: key, and the connector version
    rules already report it as an error.
    """
    if not isinstance(root, yaml.MappingNode):
        return None, []
    skills_node = next((value for key, value in root.value if key.value == "skills"), None)
    if skills_node is None:
        return None, []
    if not isinstance(skills_node, yaml.SequenceNode):
        return "has a skills: value that isn't a list, so it wasn't checked", []
    items = skills_node.value
    names = [item.value for item in items if isinstance(item, yaml.ScalarNode) and item.tag == sc.STR_TAG]
    if len(names) < len(items):
        return "has a skills: entry that isn't a skill name, so that entry wasn't checked", names
    return None, names


def author_login_findings(
    info: sc.SkillInfo, base: sc.SkillTree | None, resolver: github_logins.Resolver
) -> list[sc.Finding]:
    """Findings for the metadata.author names that are new since `base`, each looked up on GitHub.

    A name is new when the skill has no merge-base copy (it is new, or there is
    no base) or when the merge-base copy's author line doesn't list it, ignoring
    case as GitHub does. Names already on the base branch aren't looked up, so
    an account deleted later can't fail a pull request that leaves the author
    line alone. A team, org/team, is looked up by its organization.
    """
    author = info.metadata.get("author")
    if author is None:
        return []
    old_author = sc.lenient_metadata_text(base, "author") if base is not None else None
    old_names = {name.lower() for name in sc.author_names(old_author)} if old_author is not None else set()
    findings: list[sc.Finding] = []
    for name in dict.fromkeys(sc.author_names(author)):
        if name.lower() in old_names:
            continue
        account, is_team, _ = name.partition("/")
        lookup = resolver.lookup(account)
        severity = "error"
        if lookup.status == github_logins.MISSING:
            what = f'is a team of "{account}", which isn\'t' if is_team else "isn't"
            message = (
                f'"{name}" in metadata.author {what} a GitHub account. Use the GitHub username of whoever maintains '
                "the skill, or their organization or org/team"
            )
        elif lookup.status == github_logins.FOUND and is_team and lookup.account_type == "User":
            message = (
                f'"{name}" in metadata.author is a team of "{account}", but "{account}" is a GitHub user, not an '
                "organization, so it has no teams"
            )
        elif lookup.status == github_logins.UNKNOWN:
            severity = "warning"
            message = (
                f'"{name}" in metadata.author wasn\'t looked up on GitHub, because {lookup.reason}; '
                "make sure it is a GitHub account"
            )
        else:
            continue
        findings.append(sc.Finding(severity, message, "SKILL.md", info.author_line))
    return findings


def check_repository(
    repo_root: Path,
    rules: sc.Rules,
    base: str | None,
    head_ref: str,
    resolver: github_logins.Resolver | None = None,
) -> tuple[list[SkillResult], set[str] | None]:
    """Results for every skill at `head_ref`, and the skills touched since `base` (None without a base).

    With a base, each skill is also compared with its merge-base copy: a folder
    can't be removed or reuse a retired path, the version must go up when the
    published files change, and the lines the pull request adds are checked
    for internal host and tool names. With a resolver, the metadata.author
    names that are new since the base are looked up on GitHub.
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
    recommended, connector_yaml_results = connector_skill_references(repo_root, head_ref)
    results += connector_yaml_results
    results += connector_results(repo_root, base, head_ref)
    for name in sorted(head_trees):
        findings, info = sc.check_skill(head_trees[name], rules)
        if base is not None:
            findings += sc.check_added_content(base_trees.get(name), head_trees[name], rules)
        if resolver is not None and info is not None:
            findings += author_login_findings(info, base_trees.get(name), resolver)
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
        connector_cases = sc.load_cases(rules_dir / cc.CONFORMANCE_FILE)
    except ValueError as exc:
        return [str(exc)]
    problems = sc.run_conformance(cases, rules) + cc.run_conformance(connector_cases)
    actual = sc.content_hash(golden_files)
    if actual != golden_hash:
        problems.append(f"the content hash of the golden fixture is {actual}, not {golden_hash}")
    return problems


def _could_not_run(exc: GitError) -> int:
    print(f"::error title=Skill publishing rules could not run::{_escape_data(str(exc))}")
    print("The check could not read the repository. This is not a finding about the pull request.")
    return 2


def main(
    argv: list[str] | None = None,
    repo_root: Path | None = None,
    rules_dir: Path = RULES_DIR,
    login_resolver: github_logins.Resolver | None = None,
) -> int:
    """Runs the check. `login_resolver` replaces the GitHub lookup, so tests never reach the network."""
    try:
        return _run(argv, repo_root, rules_dir, login_resolver)
    except Exception as exc:  # noqa: BLE001 - any crash means the check didn't run, never a finding.
        print(f"::error title=Skill publishing rules could not run::{_escape_data(f'{type(exc).__name__}: {exc}')}")
        print("The check stopped unexpectedly. This is not a finding about the pull request.")
        return 2


def _run(
    argv: list[str] | None, repo_root: Path | None, rules_dir: Path, login_resolver: github_logins.Resolver | None
) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-ref", help="the branch the pull request merges into, such as origin/main")
    parser.add_argument("--head-ref", default="HEAD", help="the commit to check (default: HEAD)")
    parser.add_argument("--self-check-only", action="store_true", help="run only the conformance cases")
    parser.add_argument(
        "--check-github-logins",
        action="store_true",
        help="look up on GitHub each metadata.author name that a new skill lists or a changed author line adds, "
        f"with the token in {' or '.join(github_logins.TOKEN_VARIABLES)}",
    )
    args = parser.parse_args(argv)
    repo_root = repo_root or _repo_root()

    base = None
    published = None
    try:
        if args.self_check_only:
            # The cases test the rules, not the repository, so no Git is needed.
            gitignore = (repo_root / SKILLS_DIR / ".gitignore").read_text(encoding="utf-8")
        else:
            # The extension allowlist and the published set are read from the
            # merge base when there is one, so a new extension, or a change to
            # what is published, takes effect only after its change has merged.
            base = merge_base(repo_root, args.base_ref, args.head_ref) if args.base_ref else None
            gitignore = read_gitignore(repo_root, base or args.head_ref)
            published = _read_file(repo_root, base, PUBLISHED_FILES_PATH) if base is not None else None
    except OSError as exc:
        print(f"::error title=Skill publishing rules::cannot read {SKILLS_DIR}/.gitignore: {_escape_data(str(exc))}")
        return 2
    except GitError as exc:
        return _could_not_run(exc)
    try:
        rules = sc.load_rules(rules_dir, gitignore)
        excludes = base_published_excludes(published) if published is not None else None
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

    resolver = None
    if args.check_github_logins:
        resolver = login_resolver or github_logins.GitHubResolver.from_environment()
    if excludes is not None:
        # The cases above test this pull request's rules; its skills are held to the base branch's published set.
        rules = dataclasses.replace(rules, published_excludes=excludes)
    try:
        if args.head_ref == "HEAD" and uncommitted_skill_changes(repo_root):
            print(f"note: uncommitted changes under {SKILLS_DIR}/ are not checked; commit them first.\n")
        results, touched = check_repository(repo_root, rules, base, args.head_ref, resolver)
    except GitError as exc:
        return _could_not_run(exc)
    return report(results, touched)


if __name__ == "__main__":
    sys.exit(main())
