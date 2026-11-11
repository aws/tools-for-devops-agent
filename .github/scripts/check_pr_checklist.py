#!/usr/bin/env python3
"""Check that a pull request's description has its required checklist items done.

Run by ``.github/workflows/validate-pr-checklist.yml``. Reads the ``pull_request``
event payload and the files the pull request changes, lists the unmet items in the
job's step summary, and writes the verdict for ``label-pr-checklist-result.yml``::

    <out>/outcome   pass | fail | error
    <out>/reason    complete | incomplete | draft | bot | predating

The unmet items are never written to ``<out>``. The labeling workflow runs with
write access and posts a comment, so it is handed only values it checks against a
fixed list; text from a PR description never reaches it.

Which items apply comes from the files the PR changes, not from the "Type of
change" boxes, one of which names three tool types at once. A PR that touches no
tool directory is held only to the items that apply to every contribution. Inside
a tool PR an item that genuinely does not apply can be marked ``n/a:`` with a
reason on its own line, and the reviewer judges the reason; the universal items
cannot be waived that way.

A PR that changes a connector directory, ``connectors/<name>/``, is also held to
the Connectors section, whose partner terms acceptance can never be marked
``n/a``, and each such connector's ``connector.yaml`` must set ``contact_email``.
A connector is a definition, not a tool, so it adds no other tool items; the
shared files directly in ``connectors/`` and ``connectors/schema/`` call for nothing.

Each changed connector must also declare ``tier: partner-managed``, unless it has an
entry in the AWS ownership record, ``.github/aws-managed-connectors.json``, read from
the base branch so a PR cannot add its own entry. ``tier`` is the badge customers
see, so this finding fails even a PR that is otherwise only reported on, except a
draft, which is checked again when it is marked ready for review.

Exit status: 0 pass, 1 fail, 2 the check could not run. An error says nothing
about the PR, and the labeler leaves the PR's label and comment alone on it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# When the gated PR template reached main (commit 49f31c1, merged with PR #135),
# not when this check merged: a PR opened after it had the checklist in front of
# its author. A PR opened earlier passes with warnings unless ENFORCE_LABEL is on it.
CHECK_INTRODUCED = "2026-10-13T07:33:08Z"
ENFORCE_LABEL = "enforce-checklist"

# Matched against the description's "## " headings by prefix, case-insensitively,
# so rewording the rest of a heading keeps its section. The tests pin each one
# against .github/PULL_REQUEST_TEMPLATE.md.
ALWAYS_SECTIONS = ("Required before review", "License confirmation")
TOOL_SECTION = "Security and safety"
TOOL_DIRS = {"skills/": "Skills", "mcp/": "MCP servers", "custom-agents/": "Custom agents"}
# Every item in this section is enforced and none can be marked n/a: accepting the
# partner terms is a statement only the partner can make.
CONNECTOR_SECTION = "Connectors"
CONNECTOR_DIR = re.compile(r"^connectors/(?!schema/)([^/]+)/")
# contact_email is optional in schema v1 only because connectors merged before it
# have none; every connector a PR changes must set it. Its format is the schema's
# job, so this looks only for the top-level key with a plain or quoted value, not a
# block scalar (> or |), whose trailing newline the schema's pattern would refuse.
CONTACT_EMAIL = re.compile(r"""^contact_email:[ \t]*(?![>|]|""|'')[^\s#]""", re.M)
# `tier` is the badge customers see. A PR can set partner-managed on its own; any
# other value needs the connector's entry in the AWS ownership record. This reads
# connector.yaml as text, so it fails closed: the file must have exactly one
# top-level line that could set `tier`, and it must be a plain or quoted
# partner-managed. TIER_KEY counts every spelling of the key a YAML parser accepts
# at the top level (quoted, explicit `? `, a space before the colon), so a second
# spelling cannot hide the value the parser keeps.
TIER_KEY = re.compile(r"""^(?:\?[ \t]*)?(["']?)tier\1[ \t]*(?::|$)""")
PARTNER_TIER = re.compile(r"""^tier:[ \t]*(["']?)partner-managed\1[ \t]*(?:#.*)?$""")
OWNERSHIP_RECORD = ".github/aws-managed-connectors.json"

# Items every PR is held to, tool or not, and that can never be marked n/a: the
# repository is public, and the licence is a statement only the author can make.
UNIVERSAL_ITEMS = (
    re.compile(r"internal[-\s]only or proprietary", re.I),
    re.compile(r"Apache License 2\.0", re.I),
)

HEADING = re.compile(r"^##\s+(.*?)\s*$")
UNCHECKED = re.compile(r"^\s*-\s*\[\s*\]\s*")
# `n/a:` and a reason. A bare "n/a" waives nothing: the reason is what gets judged.
NA_WITH_REASON = re.compile(r"\bn/a\s*:\s*\S", re.I)


def sections(body: str) -> dict[str, list[str]]:
    """The description's lines, grouped under their "## " heading."""
    found: dict[str, list[str]] = {}
    current = None
    for line in body.splitlines():
        heading = HEADING.match(line)
        if heading:
            current = heading.group(1)
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return found


def find_section(found: dict[str, list[str]], prefix: str) -> list[str] | None:
    for heading, lines in found.items():
        if heading.lower().startswith(prefix.lower()):
            return lines
    return None


def changes_connector(paths: list[str]) -> bool:
    return any(CONNECTOR_DIR.match(p) for p in paths)


def missing_contact(paths: list[str], read) -> list[str]:
    """Unmet entries for each changed connector whose connector.yaml sets no
    contact_email. ``read`` returns a file's text at the PR head, or None when the
    file is not there. A connector directory without connector.yaml, which every
    connector must have, is a connector the PR removes, so it needs no contact."""
    names = sorted({m.group(1) for m in map(CONNECTOR_DIR.match, paths) if m})
    unmet = []
    for name in names:
        path = f"connectors/{name}/connector.yaml"
        text = read(path)
        if text is None:
            continue
        if not CONTACT_EMAIL.search(text):
            unmet.append(f"{CONNECTOR_SECTION} → {path} sets no contact_email, the corporate work email "
                         "address where AWS can reach the company about this connector")
    return unmet


def declares_partner_tier(text: str) -> bool:
    """Whether connector.yaml's only top-level ``tier`` is partner-managed."""
    lines = [line for line in text.splitlines() if TIER_KEY.match(line)]
    return len(lines) == 1 and bool(PARTNER_TIER.match(lines[0]))


def ownership_record(text: str | None) -> set[str]:
    """The connector names the AWS ownership record lists. A record the base branch
    does not have lists none. A malformed one raises, so main() reports an error
    rather than granting or refusing anything on a record it cannot read."""
    if text is None:
        return set()
    record = json.loads(text)
    connectors = record.get("connectors") if isinstance(record, dict) else None
    if not isinstance(connectors, dict) or not all(
        isinstance(owner, str) and owner.strip() for owner in connectors.values()
    ):
        raise ValueError(f"{OWNERSHIP_RECORD} must be {{\"connectors\": {{\"<name>\": \"<owning AWS team>\"}}}}")
    return set(connectors)


def unowned_tier(paths: list[str], read, read_base) -> list[str]:
    """Unmet entries for each changed connector that declares a tier other than
    partner-managed without an entry in the ownership record. ``read`` returns a
    file's text at the PR head and ``read_base`` at the base branch, or None when the
    file is not there. The record is read only when a connector needs it."""
    names = sorted({m.group(1) for m in map(CONNECTOR_DIR.match, paths) if m})
    unmet = []
    owned = None
    for name in names:
        path = f"connectors/{name}/connector.yaml"
        text = read(path)
        if text is None or declares_partner_tier(text):
            continue
        if owned is None:
            owned = ownership_record(read_base(OWNERSHIP_RECORD))
        if name in owned:
            continue
        unmet.append(f"{CONNECTOR_SECTION} → {path} must declare tier: partner-managed. Any other tier, "
                     f"or one this check cannot read as a single top-level line, needs an entry for {name} "
                     f"in {OWNERSHIP_RECORD} on the base branch, added by a maintainer in its own pull request")
    return unmet


def required_sections(paths: list[str]) -> tuple[list[str], bool]:
    """The sections the changed files call for, and whether this is a tool PR."""
    tool_dirs = [d for d in TOOL_DIRS if any(p.startswith(d) for p in paths)]
    names = list(ALWAYS_SECTIONS)
    if tool_dirs:
        names.append(TOOL_SECTION)
        names += [TOOL_DIRS[d] for d in tool_dirs]
    if changes_connector(paths):
        names.append(CONNECTOR_SECTION)
    return names, bool(tool_dirs)


def evaluate(body: str, paths: list[str]) -> tuple[list[str], list[str], bool]:
    """(unmet, waived, is_tool_pr). Each entry reads "<section> → <item>"."""
    names, is_tool = required_sections(paths)
    found = sections(body)
    unmet: list[str] = []
    waived: list[str] = []
    for name in names:
        lines = find_section(found, name)
        if lines is None:
            # Deleting a required section must not be a way past it.
            unmet.append(f"{name} → section missing from the description; restore it from the template")
            continue
        for line in lines:
            if not UNCHECKED.match(line):
                continue
            item = UNCHECKED.sub("", line).replace("**", "").strip()
            if not item:
                continue
            universal = name == CONNECTOR_SECTION or any(p.search(item) for p in UNIVERSAL_ITEMS)
            if not is_tool and not universal:
                continue
            if NA_WITH_REASON.search(item):
                if not universal:
                    waived.append(f"{name} → {item}")
                    continue
                item += "  (this item cannot be marked n/a)"
            unmet.append(f"{name} → {item}")
    return unmet, waived, is_tool


def decide(pr: dict, unmet: list[str], binding: list[str] | None = None) -> tuple[str, str]:
    """(outcome, reason). The reason lets the labeler say why a PR passed, so it
    never tells the author of a draft or a grandfathered PR they are done.
    ``binding`` holds the unmet entries that fail any PR that is not a draft,
    whoever opened it and whenever."""
    if not unmet:
        return "pass", "complete"
    if binding and not pr.get("draft"):
        return "fail", "incomplete"
    # A bot cannot fill in a template, and a draft is not submitted for review. The
    # label does not override either: labeling a draft would nag an author who has
    # said they are not finished.
    if (pr.get("user") or {}).get("type") == "Bot":
        return "pass", "bot"
    if pr.get("draft"):
        return "pass", "draft"
    created = pr.get("created_at") or ""
    labels = {label.get("name") for label in pr.get("labels") or []}
    if created and created < CHECK_INTRODUCED and ENFORCE_LABEL not in labels:
        return "pass", "predating"
    return "fail", "incomplete"


def summary(unmet: list[str], waived: list[str], is_tool: bool, reason: str, is_connector: bool) -> str:
    lines = ["## PR checklist", ""]
    lines.append(
        "This PR touches a tool directory, so every required item applies."
        if is_tool
        else "This PR touches no tool directory, so only the items that apply to every contribution are enforced."
    )
    if is_connector:
        lines.append("It changes a connector, so the partner terms in the Connectors section must be accepted, "
                     "and each changed connector's connector.yaml must set contact_email and declare "
                     f"tier: partner-managed, unless the connector is listed in {OWNERSHIP_RECORD}.")
    if waived:
        lines += ["", "Marked n/a, with a reason:", ""] + [f"- {w}" for w in waived]
    heading = {
        "complete": "All applicable required items are met.",
        "incomplete": "Unmet required items:",
        "bot": "Opened by a bot, so the checklist is not enforced. Reported only:",
        "draft": "A draft, so the checklist is not enforced until it is marked ready for review. Reported only:",
        "predating": f"Opened before this check existed, so these are warnings. Apply `{ENFORCE_LABEL}` to require them:",
    }[reason]
    lines += ["", heading]
    if unmet:
        lines += [""] + [f"- {u}" for u in unmet]
    return "\n".join(lines) + "\n"


def read_at(head_ref: str):
    """Reads a file at ``head_ref``: its text, or None when the path is not in that
    tree. A ref git cannot read raises, so main() reports an error rather than
    blaming the PR for a missing file."""
    def read(path: str) -> str | None:
        listed = subprocess.run(["git", "ls-tree", head_ref, "--", path], capture_output=True, text=True)
        if listed.returncode != 0:
            raise RuntimeError(f"git ls-tree {head_ref} failed: {listed.stderr.strip()}")
        if not listed.stdout.strip():
            return None
        shown = subprocess.run(["git", "show", f"{head_ref}:{path}"], check=True, capture_output=True)
        return shown.stdout.decode("utf-8", "replace")
    return read


def changed_paths(base_ref: str, head_ref: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [p for p in out.splitlines() if p]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", required=True, help="the pull_request event payload ($GITHUB_EVENT_PATH)")
    parser.add_argument("--base-ref", required=True, help="the base branch, e.g. origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--out", type=Path, required=True, help="directory for outcome and reason")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    try:
        pr = json.loads(Path(args.event).read_text(encoding="utf-8"))["pull_request"]
        paths = changed_paths(args.base_ref, args.head_ref)
        unmet, waived, is_tool = evaluate(pr.get("body") or "", paths)
        unmet += missing_contact(paths, read_at(args.head_ref))
        binding = unowned_tier(paths, read_at(args.head_ref), read_at(args.base_ref))
        unmet += binding
        outcome, reason = decide(pr, unmet, binding)
        report = summary(unmet, waived, is_tool, reason, changes_connector(paths))
        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            with open(step_summary, "a", encoding="utf-8") as f:
                f.write(report)
    except Exception as e:  # noqa: BLE001 - failing to reach a verdict is an error, never a finding
        (args.out / "outcome").write_text("error\n", encoding="utf-8")
        print(f"::error::The PR checklist check could not run ({type(e).__name__}: {e}). "
              "Nothing was concluded about this pull request.")
        return 2

    (args.out / "outcome").write_text(outcome + "\n", encoding="utf-8")
    (args.out / "reason").write_text(reason + "\n", encoding="utf-8")
    print(report)
    if reason == "predating":
        for item in unmet:
            print(f"::warning::{item}")
    return 0 if outcome == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
