#!/usr/bin/env python3
"""Check that a partner connector pull request comes from one of the connector's maintainers.

Run by ``.github/workflows/check-partner-maintainers.yml``.

A pull request is in scope when it changes ``connectors/<name>/`` of a partner-managed
connector, or a skill that a partner-managed connector lists in ``skills:`` or whose
``metadata.tier`` is ``partner-managed``. A connector is partner-managed when its
``tier`` is ``partner-managed`` at the merge base or at the head, or when its
``connector.yaml`` can't be read there, so a pull request that changes the tier or
breaks the file is still checked. A changed skill is checked against every
partner-managed connector that lists it at the merge base or at the head.

The pull request passes when, for every connector in scope, the connector exists at
the merge base, the pull request leaves its ``maintainers`` unchanged, and its author
is a user in that connector's ``maintainers`` at the merge base. ``maintainers`` is
read at the merge base, so a pull request can't add its own author. An ``org/team``
entry never matches, because the job's token can't read another organization's
teams.

Any other pull request in scope needs the ``partner-managed-verified`` label, added by
a code owner of /connectors/ after the pull request's last push:

- The owners are the user logins on the last /connectors/ line of .github/CODEOWNERS
  at the merge base, so a pull request can't name its own owner.
- The label's time and author are those of the latest time it was added.
- The last push is the latest run of this workflow on the head commit for an
  ``opened``, ``synchronize`` or ``reopened`` event, read from the run's name, which
  the workflow sets to the event's action. With no such run, the head commit was
  pushed before this check ran on the pull request, and the label counts.

A draft passes until it is marked ready for review.

Exit status: 0 pass, 1 the pull request needs the label, 2 the check could not run. An
error says nothing about the pull request.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import yaml

import validate_skills
from check_partner_skill_approval import (
    CODEOWNERS_PATH,
    CONNECTORS_PATTERN,
    changed_paths,
    changed_skill_names,
    code_spans,
    connector_owner_logins,
    is_partner_managed,
)
from check_pr_checklist import read_at

LABEL = "partner-managed-verified"
PARTNER_TIER = "partner-managed"
INBOX = "devops-agent-partner-connectors@amazon.com"
WORKFLOW_FILE = "check-partner-maintainers.yml"
# The workflow's run-name is this prefix and the event's action.
RUN_NAME_PREFIX = "check-partner-maintainers: "
PUSH_ACTIONS = frozenset({"opened", "synchronize", "reopened"})
CHANGED_CONNECTOR = re.compile(r"connectors/([^/]+)/")
CONNECTOR_FILE = re.compile(r"connectors/([^/]+)/connector\.yaml")
# connectors/schema/ holds the schemas, not a connector.
NOT_A_CONNECTOR = frozenset({"schema"})
PER_PAGE = 100
REQUEST_TIMEOUT_SECONDS = 30


def load_connector(text: str | None) -> dict | None:
    """A connector.yaml as a mapping: {} when the file is not there, None when it
    can't be read as a mapping."""
    if text is None:
        return {}
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def is_partner_connector(base_doc: dict | None, head_doc: dict | None) -> bool:
    return any(doc is None or doc.get("tier") == PARTNER_TIER for doc in (base_doc, head_doc))


def maintainer_entries(doc: dict | None) -> frozenset[str]:
    """Every ``maintainers`` entry, users and teams, in lower case."""
    entries = (doc or {}).get("maintainers")
    if not isinstance(entries, list):
        return frozenset()
    return frozenset(entry.strip().lstrip("@").lower() for entry in entries if isinstance(entry, str))


def maintainer_users(doc: dict | None) -> frozenset[str]:
    """The ``maintainers`` entries that are users. An org/team entry is left out."""
    return frozenset(entry for entry in maintainer_entries(doc) if "/" not in entry)


def listed_skills(doc: dict | None) -> frozenset[str]:
    skills = (doc or {}).get("skills")
    return frozenset(skill for skill in skills if isinstance(skill, str)) if isinstance(skills, list) else frozenset()


def changed_connector_names(paths: list[str]) -> list[str]:
    return sorted({match.group(1) for match in map(CHANGED_CONNECTOR.match, paths)
                   if match and match.group(1) not in NOT_A_CONNECTOR})


def tree_paths(ref: str) -> list[str]:
    """Every file path under connectors/ in ``ref``'s tree."""
    output = subprocess.run(["git", "ls-tree", "-r", "--name-only", "-z", ref, "--", "connectors/"],
                            check=True, capture_output=True, text=True).stdout
    return [path for path in output.split("\0") if path]


def connector_names(paths: list[str]) -> list[str]:
    """The connectors with a connector.yaml among a tree's file paths."""
    return sorted({match.group(1) for match in map(CONNECTOR_FILE.fullmatch, paths)
                   if match and match.group(1) not in NOT_A_CONNECTOR})


def connector_reasons(name: str, base_doc: dict | None, head_doc: dict | None, author: str) -> list[str]:
    """Why a change to one connector needs the label: [] when it doesn't."""
    if base_doc is None:
        return [f"`connectors/{name}/connector.yaml` can't be read on the base branch"]
    if not base_doc:
        return [f"`{name}` is a new connector"]
    reasons = []
    if head_doc is None or maintainer_entries(head_doc) != maintainer_entries(base_doc):
        reasons.append(f"it changes `maintainers` of `{name}`")
    if author.lower() not in maintainer_users(base_doc):
        reasons.append(f"its author `@{author}` is not a user in `maintainers` of `{name}` on the base branch")
    return reasons


def review_scope(paths: list[str], author: str, read_base, read_head, base_names, head_names):
    """The partner connectors the pull request changes, directly or through a skill,
    and the reasons it needs the label. ``read_base`` and ``read_head`` return a file's
    text there, or None without one."""
    docs: dict[tuple[str, str], dict | None] = {}

    def doc(side: str, name: str) -> dict | None:
        if (side, name) not in docs:
            read = read_base if side == "base" else read_head
            docs[side, name] = load_connector(read(f"connectors/{name}/connector.yaml"))
        return docs[side, name]

    def partner(name: str) -> bool:
        return is_partner_connector(doc("base", name), doc("head", name))

    connectors = {name for name in changed_connector_names(paths) if partner(name)}
    reasons: list[str] = []
    for skill in changed_skill_names(paths):
        listers = {name for name in set(base_names) | set(head_names)
                   if partner(name) and skill in listed_skills(doc("base", name)) | listed_skills(doc("head", name))}
        if listers:
            connectors |= listers
        elif is_partner_managed(read_base(f"skills/{skill}/SKILL.md")) or \
                is_partner_managed(read_head(f"skills/{skill}/SKILL.md")):
            reasons.append(f"no partner-managed connector lists the partner-managed skill `{skill}`")
    for name in sorted(connectors):
        reasons += connector_reasons(name, doc("base", name), doc("head", name), author)
    return sorted(connectors), reasons


def parse_time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def run_action(display_title: str | None) -> str | None:
    """The event action in a run's name, or None for a run named some other way."""
    if not display_title or not display_title.startswith(RUN_NAME_PREFIX):
        return None
    return display_title[len(RUN_NAME_PREFIX):].strip()


def label_verdict(labels: list[str], events: list[dict], owner_logins: list[str],
                  push_times: list[datetime]) -> tuple[bool, str]:
    """Whether the label counts, and why. ``events`` is the pull request's issue events,
    oldest first, the order the GitHub API lists them in."""
    if LABEL not in labels:
        return False, f"The pull request doesn't have the `{LABEL}` label."
    added = [event for event in events
             if event.get("event") == "labeled" and (event.get("label") or {}).get("name") == LABEL]
    if not added:
        return False, f"The pull request has the `{LABEL}` label, but no record of it being added was found."
    latest = added[-1]
    actor = ((latest.get("actor") or {}).get("login") or "").lower()
    added_at = parse_time(latest["created_at"])
    # A login is in code font, so that this text notifies nobody when it is copied into a comment.
    if actor not in owner_logins:
        return False, (f"`@{actor}` added the label at {latest['created_at']}, and only a code owner of "
                       f"`{CONNECTORS_PATTERN}` can: {code_spans('@' + login for login in owner_logins)}.")
    if push_times and added_at <= max(push_times):
        return False, (f"`@{actor}` added the label at {latest['created_at']}, before the last push at "
                       f"{max(push_times).strftime('%Y-%m-%dT%H:%M:%SZ')}. A code owner checks the new commits, "
                       "then removes the label and adds it again.")
    return True, f"`@{actor}` added the label at {latest['created_at']}, after the last push."


def api_get(path_and_query: str):
    api_url = os.environ.get("GITHUB_API_URL") or "https://api.github.com"
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
    request = urllib.request.Request(f"{api_url}{path_and_query}", headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.load(response)


def fetch_label_events(pull_request_number: int) -> list[dict]:
    """Every issue event of the pull request, from the GitHub API, oldest first."""
    repository = os.environ["GITHUB_REPOSITORY"]
    events: list[dict] = []
    for page in itertools.count(1):
        page_of_events = api_get(f"/repos/{repository}/issues/{pull_request_number}/events"
                                 f"?per_page={PER_PAGE}&page={page}")
        events += page_of_events
        if len(page_of_events) < PER_PAGE:
            break
    return events


def fetch_push_times(head_sha: str, head_repository: str, head_branch: str) -> list[datetime]:
    """When this workflow ran on the head commit of this pull request's branch for an
    event that pushed it: opened, synchronize or reopened."""
    repository = os.environ["GITHUB_REPOSITORY"]
    times: list[datetime] = []
    for page in itertools.count(1):
        runs = api_get(f"/repos/{repository}/actions/workflows/{WORKFLOW_FILE}/runs"
                       f"?event=pull_request&head_sha={head_sha}&per_page={PER_PAGE}&page={page}"
                       ).get("workflow_runs") or []
        for run in runs:
            if (run.get("head_sha") == head_sha and run.get("head_branch") == head_branch
                    and (run.get("head_repository") or {}).get("full_name") == head_repository
                    and run_action(run.get("display_title")) in PUSH_ACTIONS):
                times.append(parse_time(run["created_at"]))
        if len(runs) < PER_PAGE:
            break
    return times


def summary(draft: bool, author: str, connectors: list[str], reasons: list[str], owner_logins: list[str],
            label: tuple[bool, str] | None) -> str:
    lines = ["## Partner maintainers", ""]
    if draft:
        lines.append("This pull request is a draft, so it isn't checked until it is marked ready for review.")
        return "\n".join(lines) + "\n"
    if not connectors and not reasons:
        lines.append("This pull request changes no partner-managed connector or skill, so its author needs no check.")
        return "\n".join(lines) + "\n"
    if connectors:
        lines += [f"This pull request changes the partner-managed connectors {code_spans(connectors)}.", ""]
    if not reasons:
        lines.append(f"Its author `@{author}` is a user in `maintainers` of each on the base branch, "
                     "and it leaves `maintainers` unchanged.")
        return "\n".join(lines) + "\n"
    lines += [f"It needs the `{LABEL}` label, because:", ""]
    lines += [f"- {reason}" for reason in reasons]
    lines += [
        "",
        f"The partner confirms the pull request by email to {INBOX}, from the domain of `contact_email` in "
        "`connector.yaml` on `main`, and names the GitHub users in `maintainers`. A code owner of "
        f"`{CONNECTORS_PATTERN}` ({code_spans('@' + login for login in owner_logins)}) then adds the label. "
        "For a pull request the AWS team opened, the code owner adds the label after reviewing it. "
        "See `connectors/README.md`.",
    ]
    if label:
        lines += ["", label[1]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, fetch_label_events=fetch_label_events,
         fetch_push_times=fetch_push_times) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", required=True, help="the pull_request event payload ($GITHUB_EVENT_PATH)")
    parser.add_argument("--base-ref", required=True, help="the base branch, e.g. origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    args = parser.parse_args(argv)

    owner_logins: list[str] = []
    label: tuple[bool, str] | None = None
    try:
        pull_request = json.loads(Path(args.event).read_text(encoding="utf-8"))["pull_request"]
        draft = bool(pull_request.get("draft"))
        author = pull_request["user"]["login"]
        merge_base = validate_skills.merge_base(Path.cwd(), args.base_ref, args.head_ref)
        read_base, read_head = read_at(merge_base), read_at(args.head_ref)
        connectors, reasons = review_scope(
            changed_paths(merge_base, args.head_ref), author, read_base, read_head,
            connector_names(tree_paths(merge_base)), connector_names(tree_paths(args.head_ref)))
        if reasons and not draft:
            owner_logins = connector_owner_logins(read_base(CODEOWNERS_PATH) or "")
            if not owner_logins:
                raise ValueError(f"{CODEOWNERS_PATH} at the merge base names no user on a {CONNECTORS_PATTERN} line")
            head = pull_request["head"]
            label = label_verdict(
                [item.get("name") for item in pull_request.get("labels") or []],
                fetch_label_events(pull_request["number"]),
                owner_logins,
                fetch_push_times(head["sha"], (head.get("repo") or {}).get("full_name"), head["ref"]),
            )
    except Exception as error:  # noqa: BLE001 - failing to reach a verdict is an error, never a finding
        print(f"::error::The partner maintainers check could not run ({type(error).__name__}: {error}). "
              "Nothing was concluded about this pull request.")
        return 2

    report = summary(draft, author, connectors, reasons, owner_logins, label)
    print(report)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as file:
            file.write(report)
    return 1 if reasons and not draft and not (label and label[0]) else 0


if __name__ == "__main__":
    sys.exit(main())
