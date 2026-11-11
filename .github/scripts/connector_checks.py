"""The connector version rules: each connectors/<name>/ folder compared with its merge-base copy.

The rules and their reasons are under "Connector versions" in the "Skill Publishing
Rules" section of CONTRIBUTING.md. Like skill_checks.py, every function works on an
in-memory folder (sc.SkillTree), so the same rules run on Git objects in
validate_skills.py and on the cases in skill-rules/connector-conformance-cases.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

import skill_checks as sc

CONNECTORS_DIR = "connectors"
CONNECTOR_FILE = "connector.yaml"
# connectors/schema/ holds the JSON Schemas, not a connector.
SCHEMA_FOLDER = "schema"
CONFORMANCE_FILE = "connector-conformance-cases.json"


class _Absent:
    """Stands for a key a document doesn't have, which equals only itself."""

    def __repr__(self) -> str:
        return "absent"


ABSENT = _Absent()


@dataclass(frozen=True)
class Document:
    """connector.yaml as JSON, and the line of each top-level key."""

    value: object
    lines: dict[str, int] = field(default_factory=dict)

    def get(self, key: str) -> object:
        return self.value.get(key, ABSENT) if isinstance(self.value, dict) else ABSENT


def read_document(data: bytes | None, *, strict: bool = True) -> Document | None:
    """connector.yaml as the catalog publisher reads it, or None when it can't be read.

    A file with no YAML document, such as an empty one or one of only comments,
    reads as null, which isn't a mapping. strict=False also reads a merge-base
    copy that breaks a YAML rule added since it merged, as PyYAML alone reads it.
    """
    if data is None:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    root, problems = sc.read_yaml(text, CONNECTOR_FILE, first_line=1)
    if problems and not strict and (lenient := sc.compose_lenient(text)) is not None:
        root, problems = lenient, []
    if problems:
        return None
    if root is None:
        return Document(None)
    try:
        value = to_json(root)
    except RecursionError:
        return None
    lines = (
        {key.value: key.start_mark.line + 1 for key, _ in root.value if isinstance(key, ScalarNode)}
        if isinstance(root, MappingNode)
        else {}
    )
    return Document(value, lines)


def to_json(node: Node) -> object:
    """A YAML node as JSON. Only plain scalars are typed; a repeated key keeps its last value, as PyYAML does."""
    if isinstance(node, ScalarNode):
        return sc.plain_scalar_value(node.value) if node.style is None else node.value
    if isinstance(node, SequenceNode):
        return [to_json(item) for item in node.value]
    if isinstance(node, MappingNode):
        return {str(key.value): to_json(value) for key, value in node.value}
    raise TypeError(f"unexpected YAML node {type(node).__name__}")


def same(left: object, right: object) -> bool:
    """Whether two to_json values are equal as JavaScript compares them deeply: true is not 1, and 1 is not "1".

    Comparing their JSON text gives that, because to_json never makes an integral
    float: sc.plain_scalar_value reads 1.0 as text, so equal numbers have equal text.
    """
    return left is right or (
        ABSENT not in (left, right) and json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)
    )


def _version(document: Document | None) -> tuple[int, int, int] | None:
    version = document.get("version") if document is not None else ABSENT
    return sc.parse_version(version) if isinstance(version, str) else None


def _show(value: object) -> str:
    return "nothing" if value is ABSENT else json.dumps(value, ensure_ascii=False)


def _data(folder: sc.SkillTree | None, path: str) -> bytes | None:
    entry = folder.entries.get(path) if folder is not None else None
    return entry.data if entry is not None else None


def _hash(folder: sc.SkillTree) -> str:
    """sc.content_hash of every file in the folder, since every one is published."""
    return sc.content_hash({path: entry.data for path, entry in folder.entries.items()})


def check_connector(name: str, folder: sc.SkillTree) -> list[sc.Finding]:
    """The rules that need only this copy: connector.yaml is there and has a version the other rules can compare.

    YAML problems in connector.yaml are left out: validate_skills.py reports
    them for every file under connectors/.
    """
    data = _data(folder, CONNECTOR_FILE)
    if data is None:
        message = f"{CONNECTORS_DIR}/{name}/ has no {CONNECTOR_FILE}; every connector folder needs one"
        return [sc.Finding("error", message)]
    document = read_document(data)
    if document is None:
        return []
    if not isinstance(document.value, dict):
        message = f"{CONNECTOR_FILE} must be a mapping of keys to values, such as name: {name}"
        return [sc.Finding("error", message, CONNECTOR_FILE, 1)]
    if _version(document) is not None:
        return []
    version = document.get("version")
    if version is ABSENT:
        return [sc.Finding("error", '"version" is required, such as version: 1.0.0', CONNECTOR_FILE)]
    shown = _show(version[:40]) if isinstance(version, str) else _show(version)[:40]
    message = (
        f'"version" is {shown}; it must be MAJOR.MINOR.PATCH, such as version: 1.0.0, with at most '
        f"{sc.MAX_VERSION_PART_DIGITS} digits in each part"
    )
    return [sc.Finding("error", message, CONNECTOR_FILE, document.lines.get("version"))]


def check_history(name: str, base: sc.SkillTree | None, head: sc.SkillTree | None) -> list[sc.Finding]:
    """The rules that compare a connector folder with its merge-base copy. None means the folder isn't there."""
    if base is not None and head is None:
        return [
            sc.Finding(
                "error",
                f"the connector folder {CONNECTORS_DIR}/{name} was removed. A published connector stays in the "
                f"catalog, so its folder must stay too: set deprecated: true in its {CONNECTOR_FILE} instead",
            )
        ]
    if head is None:
        return []
    document = read_document(_data(head, CONNECTOR_FILE))
    version = _version(document)
    if version is None:
        return []  # check_connector reports why there is no version to compare.
    version_line = document.lines.get("version")
    if base is None:
        if version != sc.FIRST_VERSION:
            message = f"a new connector starts at version 1.0.0, not {sc.format_version(version)}"
            return [sc.Finding("warning", message, CONNECTOR_FILE, version_line)]
        return []
    old_document = read_document(_data(base, CONNECTOR_FILE), strict=False)
    old_version = _version(old_document)
    if old_version is None:
        message = (
            f"the version rules were not checked, because {CONNECTOR_FILE} on the base branch has no version that "
            "can be read"
        )
        return [sc.Finding("warning", message, CONNECTOR_FILE, version_line)]

    findings = []
    for key in ("name", "type"):
        old, new = old_document.get(key), document.get(key)
        if not same(old, new):
            message = (
                f'"{key}" changed from {_show(old)} to {_show(new)}; a connector\'s {key} never changes, so set it back'
            )
            findings.append(sc.Finding("error", message, CONNECTOR_FILE, document.lines.get(key, version_line)))

    def error(message: str) -> None:
        findings.append(sc.Finding("error", message, CONNECTOR_FILE, version_line))

    old_text, new_text = sc.format_version(old_version), sc.format_version(version)
    if version < old_version:
        error(f"version went down from {old_text} to {new_text}; it must never go down")
    elif version == old_version:
        if _hash(base) != _hash(head):
            error(
                f"files in {CONNECTORS_DIR}/{name}/ changed, so version must go up from {old_text}. Every file in a "
                "connector folder is published, and a published version never changes"
            )
    else:
        if version[0] == old_version[0]:
            for reason in major_change_reasons(old_document.value, document.value):
                error(
                    f"{reason}, which needs a new major version: {version[0] + 1}.0.0, not {new_text}. Within a "
                    "major version, auth options and endpoint URLs stay as they are and no config field is added, "
                    "so that connections customers already made keep working"
                )
        if version not in sc.next_versions(old_version):
            steps = [sc.format_version(step) for step in sc.next_versions(old_version)]
            message = (
                f"version should go up only one step from {old_text}: to {steps[0]}, {steps[1]} or {steps[2]}, "
                f"not {new_text}"
            )
            findings.append(sc.Finding("warning", message, CONNECTOR_FILE, version_line))
    return findings


def _objects(value: object) -> list[dict]:
    """The items of a JSON list that are objects. Anything else is a schema problem, not a version one."""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _mcp(document: object) -> dict:
    mcp = document.get("mcp") if isinstance(document, dict) else None
    return mcp if isinstance(mcp, dict) else {}


def _auth_options(document: object) -> dict[str, dict]:
    """Each mcp.auth option by its type. The last one wins if a type repeats, which the schema forbids anyway."""
    options = _objects(_mcp(document).get("auth"))
    return {option["type"]: option for option in options if isinstance(option.get("type"), str)}


def _endpoint_urls(document: object) -> dict[str, object]:
    """Each endpoint's URL, named for the message: mcp.endpoint, or an mcp.endpoints entry by its label."""
    mcp = _mcp(document)
    urls: dict[str, object] = {}
    if "endpoint" in mcp:
        urls["mcp.endpoint"] = mcp["endpoint"]
    for entry in _objects(mcp.get("endpoints")):
        if isinstance(entry.get("label"), str):
            urls[f'the mcp.endpoints entry "{entry["label"]}"'] = entry.get("endpoint", ABSENT)
    return urls


def _config_field_names(document: object) -> list[str]:
    return [item["name"] for item in _objects(_mcp(document).get("config")) if isinstance(item.get("name"), str)]


def major_change_reasons(old: object, new: object) -> list[str]:
    """What changed from `old` to `new` that only a major version may change, as the catalog publisher counts it."""
    reasons = []
    new_options = _auth_options(new)
    for kind, option in _auth_options(old).items():
        if not same(option, new_options.get(kind, ABSENT)):
            reasons.append(f'the "{kind}" option in mcp.auth was removed or changed')
    new_urls = _endpoint_urls(new)
    for endpoint, url in _endpoint_urls(old).items():
        if not same(url, new_urls.get(endpoint, ABSENT)):
            reasons.append(f"{endpoint} was removed or its URL changed")
    old_fields = set(_config_field_names(old))
    for name in dict.fromkeys(_config_field_names(new)):
        if name not in old_fields:
            reasons.append(f'the mcp.config field "{name}" was added')
    return reasons


# --- Conformance cases ------------------------------------------------------------


def run_conformance(cases: list[dict]) -> list[str]:
    """Problems with the rules' results on the cases from sc.load_cases; empty when every case gives its result."""
    return sc.run_cases(cases, _case_findings, label="connector case")


def _case_findings(case: dict) -> list[sc.Finding]:
    name = case["name"]
    head = sc.tree_from_files(name, case["files"]) if case.get("files") is not None else None
    findings = check_connector(name, head) if head is not None else []
    if "base" in case:
        base = sc.tree_from_files(name, case["base"]) if case.get("base") is not None else None
        findings += check_history(name, base, head)
    return findings
