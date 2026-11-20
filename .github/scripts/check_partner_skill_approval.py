#!/usr/bin/env python3
"""Check that a code owner of /connectors/ approved a change to a partner-managed skill.

Run by ``.github/workflows/check-partner-skill-approval.yml``.

A changed skill is the ``<name>`` of a changed path ``skills/<name>/...``. It is
partner-managed when ``metadata.tier`` in its ``SKILL.md`` is ``partner-managed`` at
the merge base or at the head, so a pull request that changes the tier, or deletes
the skill, still needs the approval.

The owners are the user logins on the last ``/connectors/`` line of
``.github/CODEOWNERS``, read at the merge base so a pull request cannot name its own
approver. For each owner, only the latest review that approves, requests changes or
was dismissed counts. The pull request passes when, for at least one owner, that
review approves the head commit. A review does not start a new run, so after the
approval a maintainer re-runs the job.

Exit status: 0 pass, 1 the approval is missing, 2 the check could not run. An error
says nothing about the pull request.
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
from pathlib import Path

import skill_checks as sc
import validate_skills
from check_pr_checklist import read_at

PARTNER_TIER = "partner-managed"
SKILL_PATH = re.compile(r"skills/([^/]+)/")
CODEOWNERS_PATH = ".github/CODEOWNERS"
CONNECTORS_PATTERN = "/connectors/"
# A COMMENTED or PENDING review is not here: neither one changes an approval.
DECIDING_REVIEW_STATES = frozenset({"APPROVED", "CHANGES_REQUESTED", "DISMISSED"})
REVIEWS_PER_PAGE = 100
REQUEST_TIMEOUT_SECONDS = 30


def changed_paths(merge_base: str, head_ref: str) -> list[str]:
    # --no-renames: a rename lists only the new path, which hides the skill that the
    # pull request moves away. -z: git prints an unusual path as it is, not quoted.
    output = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z", merge_base, head_ref],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [path for path in output.split("\0") if path]


def changed_skill_names(paths: list[str]) -> list[str]:
    return sorted({match.group(1) for match in map(SKILL_PATH.match, paths) if match})


def is_partner_managed(skill_md: str | None) -> bool:
    """Whether a SKILL.md, or None for one that is not there, sets the partner-managed
    tier. A tier that can't be read counts, so a broken file can't skip the approval."""
    if skill_md is None:
        return False
    try:
        return sc.read_skill_tier(skill_md.encode("utf-8")) == PARTNER_TIER
    except ValueError:
        return True


def partner_managed_skills(paths: list[str], read_base, read_head) -> list[str]:
    """The changed skills that are partner-managed at the merge base or at the head.
    ``read_base`` and ``read_head`` return a file's text there, or None without one."""
    return [
        name
        for name in changed_skill_names(paths)
        if is_partner_managed(read_base(f"skills/{name}/SKILL.md"))
        or is_partner_managed(read_head(f"skills/{name}/SKILL.md"))
    ]


def connector_owner_logins(codeowners: str) -> list[str]:
    """The user logins, in lower case, on the last /connectors/ line of a CODEOWNERS file."""
    logins: list[str] = []
    for line in codeowners.splitlines():
        fields = line.split("#", 1)[0].split()
        if fields and fields[0] == CONNECTORS_PATTERN:
            # A review names a user, and the job's token can't list the members of a
            # team, so a team owner (@org/team) can't be matched and is left out.
            logins = [field[1:].lower() for field in fields[1:] if field.startswith("@") and "/" not in field]
    return logins


def owners_approving_head_commit(reviews: list[dict], owner_logins: list[str], head_sha: str) -> list[str]:
    """The owners whose latest deciding review approves ``head_sha``. ``reviews`` is
    oldest first, the order the GitHub API lists them in."""
    latest_decision: dict[str, tuple[str, str | None]] = {}
    for review in reviews:
        login = ((review.get("user") or {}).get("login") or "").lower()
        if login in owner_logins and review.get("state") in DECIDING_REVIEW_STATES:
            latest_decision[login] = (review["state"], review.get("commit_id"))
    return [login for login in owner_logins if latest_decision.get(login) == ("APPROVED", head_sha)]


def fetch_reviews(pull_request_number: int) -> list[dict]:
    """Every review of the pull request, from the GitHub API, oldest first."""
    api_url = os.environ.get("GITHUB_API_URL") or "https://api.github.com"
    reviews_url = f"{api_url}/repos/{os.environ['GITHUB_REPOSITORY']}/pulls/{pull_request_number}/reviews"
    headers = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}
    reviews: list[dict] = []
    for page in itertools.count(1):
        request = urllib.request.Request(f"{reviews_url}?per_page={REVIEWS_PER_PAGE}&page={page}", headers=headers)
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            page_of_reviews = json.load(response)
        reviews += page_of_reviews
        if len(page_of_reviews) < REVIEWS_PER_PAGE:
            break
    return reviews


def code_spans(items) -> str:
    return ", ".join(f"`{item}`" for item in items)


def summary(skills: list[str], owner_logins: list[str], approving_logins: list[str], head_sha: str) -> str:
    lines = ["## Partner skill approval", ""]
    if not skills:
        lines.append("This pull request changes no partner-managed skill, so it needs no approval from a "
                     f"code owner of `{CONNECTORS_PATTERN}`.")
        return "\n".join(lines) + "\n"
    lines += [f"This pull request changes partner-managed skills: {code_spans(skills)}.", ""]
    # A login is in code font, so that this text notifies nobody when it is copied into a comment.
    if approving_logins:
        lines.append(f"A code owner of `{CONNECTORS_PATTERN}` approved the head commit `{head_sha}`: "
                     f"{code_spans('@' + login for login in approving_logins)}.")
    else:
        lines += [
            f"It needs an approving review of the head commit `{head_sha}` from a code owner of "
            f"`{CONNECTORS_PATTERN}`: {code_spans('@' + login for login in owner_logins)}. "
            "An approval of an earlier commit does not count.",
            "",
            "A review does not start this check again. After the approval, a maintainer re-runs this job.",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, fetch_reviews=fetch_reviews) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--event", required=True, help="the pull_request event payload ($GITHUB_EVENT_PATH)")
    parser.add_argument("--base-ref", required=True, help="the base branch, e.g. origin/main")
    parser.add_argument("--head-ref", default="HEAD")
    args = parser.parse_args(argv)

    try:
        pull_request = json.loads(Path(args.event).read_text(encoding="utf-8"))["pull_request"]
        head_sha = pull_request["head"]["sha"]
        merge_base = validate_skills.merge_base(Path.cwd(), args.base_ref, args.head_ref)
        read_base = read_at(merge_base)
        skills = partner_managed_skills(changed_paths(merge_base, args.head_ref), read_base, read_at(args.head_ref))
        owner_logins: list[str] = []
        approving_logins: list[str] = []
        if skills:
            owner_logins = connector_owner_logins(read_base(CODEOWNERS_PATH) or "")
            if not owner_logins:
                raise ValueError(f"{CODEOWNERS_PATH} at the merge base names no user on a {CONNECTORS_PATTERN} line")
            reviews = fetch_reviews(pull_request["number"])
            approving_logins = owners_approving_head_commit(reviews, owner_logins, head_sha)
    except Exception as error:  # noqa: BLE001 - failing to reach a verdict is an error, never a finding
        print(f"::error::The partner skill approval check could not run ({type(error).__name__}: {error}). "
              "Nothing was concluded about this pull request.")
        return 2

    report = summary(skills, owner_logins, approving_logins, head_sha)
    print(report)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as file:
            file.write(report)
    return 1 if skills and not approving_logins else 0


if __name__ == "__main__":
    sys.exit(main())
