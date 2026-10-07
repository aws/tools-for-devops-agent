"""Publishing rules for one skill folder, skills/<name>/.

Every function here works on an in-memory copy of a skill folder, so the same
rules run on Git objects in CI (validate_skills.py), on the cases in
skill-rules/conformance-cases.json, and in the unit tests under tests/.

The rules exist because skills on `main` are published as one set: the
catalog publisher validates every skill before it writes anything, and one
skill that breaks a rule stops every skill from publishing.
See the "Skill Publishing Rules" section of CONTRIBUTING.md.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

RULES_DIR_DISPLAY = ".github/scripts/skill-rules"
AGENT_TYPES_FILE = "agent-types.json"
VOCABULARY_FILE = "vocabulary.json"

NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_TITLE_LENGTH = 100
MAX_SUMMARY_LENGTH = 200

VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
# Only ever accepted for the merge-base copy of a skill, so that a skill still
# on a two-part version can be compared while it is being fixed.
TWO_PART_VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")

# GitHub's own rule for usernames: alphanumerics and single hyphens, no leading
# or trailing hyphen, at most 39 characters.
GITHUB_LOGIN_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")

DIMENSION_PREFIX = "aws-devops-agent-skills."
DIMENSIONS = ("agent-types", "aws-services", "technical-domains")

# The Agent Skills specification's frontmatter fields, plus the optional
# display `title`. Anything else is reported as a warning.
TOP_LEVEL_KEYS = ("name", "description", "license", "compatibility", "metadata", "allowed-tools", "title")

FRONTMATTER_PATTERN = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)

STR_TAG = "tag:yaml.org,2002:str"
_SCALAR_KINDS = {
    "tag:yaml.org,2002:int": "a number",
    "tag:yaml.org,2002:float": "a number",
    "tag:yaml.org,2002:bool": "true or false",
    "tag:yaml.org,2002:null": "empty",
    "tag:yaml.org,2002:timestamp": "a date",
}

# YAML features that different parsers read differently, or that let one part
# of the frontmatter silently change another. Other tools parse the same text,
# in other languages, so the frontmatter is limited to plain block mappings and
# scalars that every parser reads the same way.
_FORBIDDEN_TOKENS = (
    (yaml.AnchorToken, "anchors (&)"),
    (yaml.AliasToken, "aliases (*)"),
    (yaml.TagToken, "tags (! or !!)"),
    (yaml.DirectiveToken, "directives (%)"),
    (yaml.DocumentStartToken, "document markers (--- or ...)"),
    (yaml.DocumentEndToken, "document markers (--- or ...)"),
    (yaml.FlowMappingStartToken, "flow collections ({...} or [...])"),
    (yaml.FlowSequenceStartToken, "flow collections ({...} or [...])"),
)


@dataclass(frozen=True)
class Entry:
    """One file in a skill folder. `path` is relative to the folder; `mode` is the Git file mode."""

    path: str
    mode: str
    data: bytes


@dataclass
class SkillTree:
    name: str
    entries: dict[str, Entry] = field(default_factory=dict)


@dataclass(frozen=True)
class Finding:
    """A rule result. `severity` is "error" (blocks the pull request) or "warning"."""

    severity: str
    message: str
    path: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class Rules:
    """The data the rules read from skill-rules/."""

    agent_types: frozenset[str]
    vocabulary: dict[str, frozenset[str]]
    aliases: dict[str, str]


@dataclass
class SkillInfo:
    """What later rules need from a parsed SKILL.md."""

    name: str
    version: tuple[int, int, int] | None
    metadata: dict[str, str]


def load_rules(rules_dir: Path) -> Rules:
    """Read the rule data files. Raises ValueError when one is malformed, so the check fails closed."""
    agent_types = _read_json(rules_dir / AGENT_TYPES_FILE)
    vocabulary = _read_json(rules_dir / VOCABULARY_FILE)
    try:
        values = agent_types["values"]
        dimensions = vocabulary["values"]
        aliases = vocabulary["aliases"]
        if not all(isinstance(v, str) for v in values):
            raise TypeError(f"{AGENT_TYPES_FILE}: every value must be a string")
        if set(dimensions) != set(DIMENSIONS):
            raise ValueError(f"{VOCABULARY_FILE}: values must have exactly the keys {', '.join(DIMENSIONS)}")
        return Rules(
            agent_types=frozenset(values),
            vocabulary={dim: frozenset(dimensions[dim]) for dim in DIMENSIONS},
            aliases=dict(aliases),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError(f"malformed rule data in {rules_dir}: {exc}") from exc


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def parse_version(text: str, *, allow_two_part: bool = False) -> tuple[int, int, int] | None:
    """`MAJOR.MINOR.PATCH` as a tuple, or None. `allow_two_part` reads `2.6` as 2.6.0."""
    match = VERSION_PATTERN.match(text)
    if match:
        return (int(match[1]), int(match[2]), int(match[3]))
    match = TWO_PART_VERSION_PATTERN.match(text) if allow_two_part else None
    if match:
        return (int(match[1]), int(match[2]), 0)
    return None


def check_skill(tree: SkillTree, rules: Rules) -> tuple[list[Finding], SkillInfo | None]:
    """Every rule that needs only this copy of the skill. Returns the findings and, when SKILL.md parses, its info."""
    findings: list[Finding] = []
    skill_md = tree.entries.get("SKILL.md")
    if skill_md is None:
        findings.append(Finding("error", "the skill folder has no SKILL.md"))
        return findings, None
    info = _check_skill_md(tree.name, skill_md.data, rules, findings)
    return findings, info


# --- SKILL.md -----------------------------------------------------------------


class _Report:
    """Collects findings for SKILL.md. Frontmatter starts on line 2, so YAML line N is file line N + 2."""

    def __init__(self, findings: list[Finding]):
        self.findings = findings

    def error(self, message: str, line: int | None = None) -> None:
        self.findings.append(Finding("error", message, "SKILL.md", line))

    def warning(self, message: str, line: int | None = None) -> None:
        self.findings.append(Finding("warning", message, "SKILL.md", line))


def _line(node: Node) -> int:
    return node.start_mark.line + 2


def _kind(node: Node) -> str:
    if isinstance(node, MappingNode):
        return "a mapping"
    if isinstance(node, SequenceNode):
        return "a list"
    return _SCALAR_KINDS.get(node.tag, "not text")


def _check_skill_md(folder: str, data: bytes, rules: Rules, findings: list[Finding]) -> SkillInfo | None:
    report = _Report(findings)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.error("SKILL.md is not valid UTF-8", line=data.count(b"\n", 0, exc.start) + 1)
        return None

    if not (text.startswith("---\n") or text.startswith("---\r\n")):
        report.error(
            "SKILL.md must start with a --- line, then the YAML frontmatter, then a closing --- line", line=1
        )
        return None
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        report.error("the frontmatter has no closing --- line", line=1)
        return None
    frontmatter = match.group(1)

    root = _parse_frontmatter(frontmatter, report)
    if root is None:
        return None
    if not isinstance(root, MappingNode):
        report.error("the frontmatter must be a mapping of keys to values, such as name: my-skill", line=2)
        return None

    top = _mapping_items(root, "", report)
    for key, (key_node, _) in top.items():
        if key not in TOP_LEVEL_KEYS:
            report.warning(
                f'unknown top-level key "{key}"; the Agent Skills specification defines '
                "name, description, license, compatibility, metadata and allowed-tools",
                line=_line(key_node),
            )

    name = _check_name(folder, top, report)
    _check_description(top, report)
    _check_title(top, report)
    for key in ("license", "compatibility", "allowed-tools"):
        if key in top:
            _text(top, key, key, report)

    metadata, version = _check_metadata(top, rules, report)
    return SkillInfo(name=name or folder, version=version, metadata=metadata)


def _parse_frontmatter(frontmatter: str, report: _Report) -> Node | None:
    """The composed YAML node tree, or None after reporting why the frontmatter can't be read safely."""
    try:
        forbidden = [
            (token, what)
            for token in yaml.scan(frontmatter, Loader=yaml.SafeLoader)
            for kind, what in _FORBIDDEN_TOKENS
            if isinstance(token, kind)
        ]
    except yaml.YAMLError as exc:
        _report_yaml_error(exc, report)
        return None
    for token, what in forbidden:
        report.error(f"the frontmatter uses {what}, which is not allowed", line=token.start_mark.line + 2)
    if forbidden:
        return None
    try:
        root = yaml.compose(frontmatter, Loader=yaml.SafeLoader)
    except yaml.YAMLError as exc:
        _report_yaml_error(exc, report)
        return None
    if root is None:
        report.error("the frontmatter is empty", line=2)
    return root


def _report_yaml_error(exc: yaml.YAMLError, report: _Report) -> None:
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None) or str(exc)
    report.error(f"the frontmatter is not valid YAML: {problem}", line=mark.line + 2 if mark else None)


def _mapping_items(node: MappingNode, prefix: str, report: _Report) -> dict[str, tuple[ScalarNode, Node]]:
    items: dict[str, tuple[ScalarNode, Node]] = {}
    for key_node, value_node in node.value:
        if not (isinstance(key_node, ScalarNode) and key_node.tag == STR_TAG):
            report.error("frontmatter keys must be plain text", line=_line(key_node))
            continue
        if key_node.value in items:
            report.error(f'duplicate key "{prefix}{key_node.value}"', line=_line(key_node))
            continue
        items[key_node.value] = (key_node, value_node)
    return items


def _text(items: dict, key: str, label: str, report: _Report) -> str | None:
    """The string value of `key`, or None after reporting that it isn't text. A missing key returns None silently."""
    if key not in items:
        return None
    key_node, value_node = items[key]
    if isinstance(value_node, ScalarNode) and value_node.tag == STR_TAG:
        return value_node.value
    message = f'"{label}" must be text, not {_kind(value_node)}'
    if isinstance(value_node, ScalarNode):
        message += f'. Put the value in quotes, for example {key}: "{value_node.value}"'
    report.error(message, line=_line(key_node))
    return None


def _single_line(value: str) -> bool:
    return "\n" not in value.strip("\n")


def _check_name(folder: str, top: dict, report: _Report) -> str | None:
    if "name" not in top:
        report.error('"name" is required')
        return None
    name = _text(top, "name", "name", report)
    if name is None:
        return None
    line = _line(top["name"][0])
    if len(name) > MAX_NAME_LENGTH:
        report.error(f'"name" is {len(name):,} characters; the limit is {MAX_NAME_LENGTH}', line=line)
    if not NAME_PATTERN.match(name):
        report.error('"name" must be lowercase letters, digits and single hyphens, such as my-skill', line=line)
    if name != folder:
        report.error(
            f'"name" is "{name}" but the folder is "{folder}"; they must match. '
            "A skill's folder path is its permanent identity",
            line=line,
        )
    return name


def _check_description(top: dict, report: _Report) -> None:
    if "description" not in top:
        report.error('"description" is required')
        return
    description = _text(top, "description", "description", report)
    if description is None:
        return
    line = _line(top["description"][0])
    if not description.strip():
        report.error('"description" must not be empty', line=line)
    elif len(description) > MAX_DESCRIPTION_LENGTH:
        report.error(
            f'"description" is {len(description):,} characters; the limit is {MAX_DESCRIPTION_LENGTH:,}', line=line
        )


def _check_title(top: dict, report: _Report) -> None:
    title = _text(top, "title", "title", report)
    if title is None:
        return
    line = _line(top["title"][0])
    if not _single_line(title):
        report.error('"title" must be a single line', line=line)
    if len(title.strip()) > MAX_TITLE_LENGTH:
        report.error(f'"title" is {len(title.strip()):,} characters; the limit is {MAX_TITLE_LENGTH}', line=line)


def _check_metadata(top: dict, rules: Rules, report: _Report) -> tuple[dict[str, str], tuple[int, int, int] | None]:
    if "metadata" not in top:
        report.error('"metadata" is required, with at least author and version')
        return {}, None
    key_node, node = top["metadata"]
    metadata_line = _line(key_node)
    if not isinstance(node, MappingNode):
        report.error('"metadata" must be a mapping, with one key: value pair per line', line=metadata_line)
        return {}, None

    items = _mapping_items(node, "metadata.", report)
    metadata: dict[str, str] = {}
    lines: dict[str, int] = {}
    for key in items:
        value = _text(items, key, f"metadata.{key}", report)
        if value is not None:
            metadata[key] = value
            lines[key] = _line(items[key][0])

    _check_author(metadata, items, lines, metadata_line, report)
    version = _check_version(metadata, items, lines, metadata_line, report)
    _check_summary(metadata, lines, report)
    _check_deprecated(metadata, lines, report)
    _check_agent_types(metadata, lines, rules, report)
    _check_dimensions(metadata, items, rules, report)
    return metadata, version


def _split(value: str) -> list[str]:
    return [part.strip() for part in value.split(",")]


def _check_author(metadata: dict, items: dict, lines: dict, metadata_line: int, report: _Report) -> None:
    if "author" not in items:
        report.error('"metadata.author" is required', line=metadata_line)
        return
    if "author" not in metadata:
        return
    if not all(GITHUB_LOGIN_PATTERN.match(part) for part in _split(metadata["author"])):
        report.error(
            '"metadata.author" must be one or more GitHub usernames separated by commas, '
            'for example "octocat" or "octocat, hubot"',
            line=lines["author"],
        )


def _check_version(
    metadata: dict, items: dict, lines: dict, metadata_line: int, report: _Report
) -> tuple[int, int, int] | None:
    if "version" not in items:
        report.error('"metadata.version" is required, for example version: "1.0.0"', line=metadata_line)
        return None
    if "version" not in metadata:
        return None
    version = parse_version(metadata["version"])
    if version is None:
        report.error(
            f'"metadata.version" is "{metadata["version"]}"; it must be MAJOR.MINOR.PATCH, for example "1.2.0", '
            "with no prefix or suffix",
            line=lines["version"],
        )
    return version


def _check_summary(metadata: dict, lines: dict, report: _Report) -> None:
    summary = metadata.get("summary")
    if summary is None:
        return
    if not _single_line(summary):
        report.error('"metadata.summary" must be a single line', line=lines["summary"])
    if len(summary.strip()) > MAX_SUMMARY_LENGTH:
        report.error(
            f'"metadata.summary" is {len(summary.strip()):,} characters; the limit is {MAX_SUMMARY_LENGTH}',
            line=lines["summary"],
        )


def _check_deprecated(metadata: dict, lines: dict, report: _Report) -> None:
    deprecated = metadata.get("deprecated")
    if deprecated is not None and deprecated not in ("true", "false"):
        report.error(
            '"metadata.deprecated" must be "true" or "false", in quotes, because metadata values are text',
            line=lines["deprecated"],
        )


def _check_agent_types(metadata: dict, lines: dict, rules: Rules, report: _Report) -> None:
    value = metadata.get("agent_types")
    if value is None:
        return
    for part in _split(value):
        if not part:
            report.error('"metadata.agent_types" has an empty value between commas', line=lines["agent_types"])
        elif part not in rules.agent_types:
            report.error(
                f'"metadata.agent_types" has unknown value "{part}"; '
                f"allowed values are listed in {RULES_DIR_DISPLAY}/{AGENT_TYPES_FILE}",
                line=lines["agent_types"],
            )


def _check_dimensions(metadata: dict, items: dict, rules: Rules, report: _Report) -> None:
    for key in items:
        if not key.startswith(DIMENSION_PREFIX):
            continue
        dimension = key[len(DIMENSION_PREFIX):]
        line = _line(items[key][0])
        if dimension not in DIMENSIONS:
            report.error(
                f'"metadata.{key}" is not a known dimension; use one of: '
                + ", ".join(DIMENSION_PREFIX + d for d in DIMENSIONS),
                line=line,
            )
            continue
        if key not in metadata:
            continue
        approved = rules.vocabulary.get(dimension, frozenset())
        for part in _split(metadata[key]):
            if not part:
                report.error(f'"metadata.{key}" has an empty value between commas', line=line)
            elif part not in approved:
                hint = (
                    f'use "{rules.aliases[part]}"'
                    if part in rules.aliases
                    else f"approved values are listed in {RULES_DIR_DISPLAY}/{VOCABULARY_FILE}"
                )
                report.warning(f'"{part}" is not an approved {dimension} value; {hint}', line=line)


# --- Conformance cases ------------------------------------------------------------


def load_cases(path: Path) -> list[dict]:
    """The cases in conformance-cases.json. Raises ValueError when the file is malformed."""
    document = _read_json(path)
    cases = document.get("cases") if isinstance(document, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{path.name}: expected an object with a non-empty cases list")
    seen: set[str] = set()
    for case in cases:
        problem = _case_problem(case)
        if problem is None and case["id"] in seen:
            problem = "duplicate id"
        if problem:
            raise ValueError(f"{path.name}: case {case.get('id', '?') if isinstance(case, dict) else '?'}: {problem}")
        seen.add(case["id"])
    return cases


def _case_problem(case) -> str | None:
    if not isinstance(case, dict):
        return "a case must be an object"
    for key in ("id", "name", "expect"):
        if not isinstance(case.get(key), str):
            return f'"{key}" must be a string'
    if case["expect"] not in ("pass", "fail"):
        return '"expect" must be "pass" or "fail"'
    if case["expect"] == "fail" and not isinstance(case.get("error"), str):
        return 'a "fail" case needs an "error" string'
    if not isinstance(case.get("files"), dict):
        return '"files" must be an object'
    for path, spec in case["files"].items():
        if not isinstance(spec, dict) or len({"text", "base64"} & set(spec)) != 1:
            return f'file "{path}" needs exactly one of "text" or "base64"'
    return None


def tree_from_files(name: str, files: dict) -> SkillTree:
    """A SkillTree from a case's "files" object: {path: {"text"|"base64": ..., "mode"?: ...}}."""
    entries = {}
    for path, spec in files.items():
        data = spec["text"].encode("utf-8") if "text" in spec else base64.b64decode(spec["base64"])
        entries[path] = Entry(path, spec.get("mode", "100644"), data)
    return SkillTree(name, entries)


def run_conformance(cases: list[dict], rules: Rules) -> list[str]:
    """Problems with the rules' results on the cases; an empty list means every case gives its expected result."""
    problems = []
    for case in cases:
        findings, _ = check_skill(tree_from_files(case["name"], case["files"]), rules)
        errors = [f.message for f in findings if f.severity == "error"]
        if case["expect"] == "pass" and errors:
            problems.append(f"case {case['id']}: expected pass, got: {'; '.join(errors)}")
        elif case["expect"] == "fail" and not any(case["error"] in message for message in errors):
            got = "; ".join(errors) if errors else "no errors"
            problems.append(f"case {case['id']}: expected an error containing {case['error']!r}, got: {got}")
    return problems
