---
inclusion: auto
name: connector-review
description: Review pull requests that add or change a partner connector under connectors/ in this repository, together with the skills the connector recommends. Use when asked to review, re-review, or compare connector PRs, or to check a connector's endpoints, authentication, setup guide, triggers, logo, or partner skills.
---

# Reviewing connector pull requests

A connector is `connectors/<name>/`: a `connector.yaml` describing a partner-hosted MCP server, a `logo.svg` (optional `logo-dark.svg`), and a `README.md` setup guide, plus the skills listed under `skills:`. It holds no server code. Several connector PRs are usually open at once and reviewed by different maintainers, so review every one the same way and report in the same shape.

Repository facts to re-check if anything looks different: `/connectors/` is owned by the admin team in `.github/CODEOWNERS`; `connectors/README.md` says submissions are not open yet; the PR checklist check deliberately skips `connectors/` but still holds any `skills/` in the PR to the skill checklist; there is no repository validator for connector files, so step 3 does that work.

`CONTRIBUTING.md` does not yet have a connector contribution guide. When it does, it takes precedence over this file wherever the two disagree.

## Ground rules

- Do not post, approve, request changes, approve fork CI runs, add or remove labels, resolve threads, or merge without the reviewer's explicit go for that action. Adding a label re-triggers CI, so it counts.
- Do not run code from the PR in the reviewer's normal environment or with their credentials (step 3).
- Report only what you checked, and say what each check proves (table below). Name anything you did not check.
- Do not repeat sensitive strings from the PR in chat or review text, such as internal hostnames, real emails, account or tenant IDs, customer names, or secrets. Describe them instead.
- Probe partner endpoints only without credentials (step 4.3).

## What each check proves

| Evidence | Proves | Does not prove |
|---|---|---|
| `connector.yaml` passes the JSON Schema | Descriptor shape | That it works |
| Unauthenticated MCP `initialize` returns 401 or 403 | Host is reachable and rejects anonymous calls | That authentication works |
| OAuth or DCR metadata resolves and matches the descriptor | The partner advertises that flow | That AWS DevOps Agent can complete it |
| The partner's docs (`docs_url`, ideally an AWS DevOps Agent setup page) match the descriptor and README | The partner documents this setup as supported | That anyone ran it end to end |
| Authenticated run in a non-production Agent Space | It works for that region and auth type | Other regions or auth types |

**Merge** needs: the repository contract verified (step 3); the partner's docs agreeing with the descriptor and README, or a named partner or SME confirmation; and no unresolved contradiction.

**Production promotion** is separate. It is a maintainer change to `connectors/releases.yaml`, and it needs a live install, sign-in, `tools/list`, and skill load for each advertised endpoint and auth pair.

Anything you could only check statically goes in the review's scope line as a promotion precondition, not a merge blocker.

## Step 1: Pre-flight

Run this before reading the diff, and again right before posting anything.

```bash
export GH_NO_UPDATE_NOTIFIER=1   # keeps gh's upgrade notice off stderr, so no output filtering is needed
REPO=aws/tools-for-devops-agent; N=${N:?set N to the PR number}
NAME=$(gh pr view $N -R $REPO --json files --jq '[.files[].path | select(startswith("connectors/")) | split("/")[1]] | unique | join(" ")'); echo "connector(s): $NAME"
gh pr view $N -R $REPO --json state,isDraft,headRefOid,author,assignees,reviewRequests,reviews,comments
gh api repos/$REPO/issues/$N/comments --paginate --jq '.[] | "### \(.user.login) at \(.created_at)\n\(.body)\n"'
gh api repos/$REPO/pulls/$N/reviews --paginate --jq '.[] | "### \(.user.login): \(.state) on \(.commit_id[0:7])\n\(.body)\n"'
gh api graphql -f query="query{repository(owner:\"aws\",name:\"tools-for-devops-agent\"){pullRequest(number:$N){reviewThreads(first:100){nodes{isResolved path comments(first:20){nodes{author{login} body}}}}}}}"
gh api orgs/aws/teams/tools-for-devops-agent-admins/members --jq '[.[].login]'
gh pr list -R $REPO --state all --limit 100 --search "$NAME" --json number,title,state
```

If `NAME` lists more than one connector, review each one separately through steps 3 and 4. Read full bodies, not summaries. Stop and tell the reviewer if any of these is true:

- Another maintainer or admin has commented, is assigned, or has a pending individual review request. A request to the admin team alone is the CODEOWNERS default.
- Any reviewer's ask is unresolved, such as "before this lands" or a question to the author.
- Another PR touches the same connector or skills, or this PR says it supersedes one.

Record which commit the SME approved and what they said they verified. Commits after that approval are not covered by it.

## Step 2: Trial merge

Never review in the reviewer's own working tree; it may hold uncommitted work.

```bash
SRC=$(git rev-parse --show-toplevel); WORK=$(mktemp -d)
git fetch -q origin main "+pull/$N/head:refs/remotes/origin/pr/$N"
git worktree add -q --detach "$WORK/tree" origin/main && cd "$WORK/tree"
git -c user.name=review -c user.email=review@localhost merge -q --no-ff --no-edit "origin/pr/$N"
git merge-base --is-ancestor origin/main "origin/pr/$N" && echo "head contains main" || echo "head is behind main"
git diff --name-only origin/main...HEAD
```

A merge conflict is a finding for the author. A clean merge from a stale head is not, but say so.

## Step 3: Deterministic checks

**Before running anything:**

- Read the changed-file list.
- If the PR touches anything other than `connectors/$NAME/`, the partner's `skills/<skill>/` directories, and `llms.txt`, stop and tell the reviewer. Watch especially for `.github/`, `tests/`, `docs/hooks/`, `mkdocs.yml`, and dependency files: the validators below would run that code.

Use a throwaway environment:

```bash
python3 -m venv "$WORK/venv" && . "$WORK/venv/bin/activate" && pip install -q pyyaml jsonschema
```

**3a. Connector contract.** This covers the schema, the file allowlist, and the cross-field rules that the schema description assigns to a "catalog check", which does not exist yet. Run it from the trial merge:

```bash
python3 - "$NAME" <<'EOF'
import json, re, sys
from pathlib import Path
import jsonschema, yaml
name = sys.argv[1]
root = Path("connectors") / name
text = (root / "connector.yaml").read_text()
doc = yaml.safe_load(text)
schema_dir = Path("connectors/schema") / f"v{doc.get('schema_version')}"
schema = json.loads((schema_dir / "connector.schema.json").read_text())
errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
print("schema errors:", len(errors))
for e in errors:
    print("  ", list(e.path), e.message[:200])
print("name matches directory:", doc.get("name") == name)
allowed = {f["path"] for f in json.loads((schema_dir / "published-files.json").read_text())["files"]}
present = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() or p.is_symlink()}
print("files outside allowlist:", sorted(present - allowed) or "none")
mcp = doc.get("mcp", {})
labels = [e["label"] for e in mcp.get("endpoints", [])]
print("endpoint labels:", labels or "single endpoint")
print("duplicate labels:", sorted({x for x in labels if labels.count(x) > 1}) or "none")
types = [a.get("type") for a in mcp.get("auth", [])]
print("auth types in order:", types, "| duplicates:", sorted({t for t in types if types.count(t) > 1}) or "none")
for a in mcp.get("auth", []):
    for key, value in a.items():
        if isinstance(value, dict):
            missing, extra = sorted(set(labels) - set(value)), sorted(set(value) - set(labels))
            print(f"{a['type']}.{key} label parity:", "ok" if not (missing or extra) else f"missing {missing} extra {extra}")
declared = {c["name"] for c in mcp.get("config", [])}
used = set(re.findall(r"\{\{\s*config\.([a-z0-9_]+)\s*\}\}", text))
print("undeclared placeholders:", sorted(used - declared) or "none", "| unused config:", sorted(declared - used) or "none")
print("triggers:", "present, auth " + str(doc["triggers"].get("auth", "api_key (default)")) if "triggers" in doc else "absent")
llms = Path("llms.txt").read_text()
for s in doc.get("skills", []):
    skill = Path("skills") / s / "SKILL.md"
    if not skill.is_file():
        print(f"skill {s}: MISSING")
        continue
    tier = re.search(r'^\s*tier:\s*"?([a-z-]+)', skill.read_text(), re.M)
    print(f"skill {s}: tier {tier.group(1) if tier else 'unset'} | in llms.txt: {f'skills/{s}/SKILL.md' in llms}")
EOF
```

Any schema error, extra file, name mismatch, duplicate label or auth type, label-parity mismatch, undeclared placeholder, or missing skill is a blocker. An unused config field is a nit. For a partner connector, every skill should be `partner-managed`.

**3b. Files, logo, and release manifest.**

```bash
git ls-files -s "connectors/$NAME" | awk '$1 != "100644"'      # expect no output: no executable bits or symlinks
grep -n -i -o -E '<script|[[:space:]]on[a-z]+=|<foreignobject|<!doctype|<!entity|<image|@import|data:[a-z]+/|url\([^#)]|href="[^#"]' connectors/$NAME/*.svg || echo "svg: none"
git diff --name-only origin/main...HEAD -- connectors/releases.yaml   # expect no output
```

- Any SVG hit is a blocker unless there is a clear, harmless reason.
- Also render the logo at small size on light and dark backgrounds.
- A partner PR that changes `releases.yaml` is a blocker. Production promotion is a separate maintainer change.

**3c. Repository validators.**

```bash
python3 .github/scripts/validate_skills.py --base-ref origin/main
python3 .github/scripts/validate_skill_evals.py --base-ref origin/main --pr-number $N
python3 .github/scripts/scan_aws_identifiers.py --base-ref origin/main
python3 -m unittest discover -s tests
pip install -q "mkdocs-material==$(grep -o 'mkdocs-material==[0-9.]*' .github/workflows/build-docs.yml | head -1 | cut -d= -f3)" && mkdocs build --strict
```

Record the command, exit status, test count, and warning count for each. The unit-test output includes an `::error::The PR checklist check could not run` line; a checklist test prints it on purpose. Judge the tests by the `Ran N tests` and `OK` lines. `scan_aws_identifiers` covers only account and EC2 instance IDs, so sweep the connector and skill files yourself for the strings listed under Ground rules.

**3d. Versions.**

- A new connector or skill normally starts at `1.0.0`.
- For an existing connector, any change to its files needs a higher `version`.
- For an existing skill, any change to published content needs a higher `metadata.version`. `validate_skills` checks skills, not connectors.

**3e. Find the write-capable skills.** Use both searches; the second catches skills that describe writes in prose without naming a tool.

```bash
T='(^|[^A-Za-z])(create|update|delete|remove|manage|assign|acknowledge|resolve|close|mute|set|add|link|post|send)(_[a-z]|[A-Z])'
W='\b(creat(e|es|ing)|updat(e|es|ing)|delet(e|es|ing)|modif(y|ies)|assign(s|ing)?|acknowledg(e|es|ing)|mute|enable|disable|overwrite)\b'
python3 -c 'import sys,yaml; print("\n".join(yaml.safe_load(open(f"connectors/{sys.argv[1]}/connector.yaml"))["skills"]))' "$NAME" |
  while read -r s; do printf '%-40s tool-names=%s write-verbs=%s\n' "$s" "$(grep -c -E "$T" skills/$s/SKILL.md)" "$(grep -c -i -E "$W" skills/$s/SKILL.md)"; done
```

The counts are a triage aid. They are not a classification.

## Step 4: Manual checks, highest yield first

### 4.1 The partner's documentation

- Open `docs_url` and read the whole page, plus the pages it links for authentication and permissions. An HTTP 200 proves nothing about content.
- Decide what kind of page it is, because that decides what it can settle:
  - **An AWS DevOps Agent setup page.** This is the authority for how the connector should be set up.
  - **A general MCP server page,** with setup written for other clients. Search the partner's docs for an AWS DevOps Agent page first. If there is none, the general page still settles endpoints, tools, and permissions. For authentication, check that the connector's auth type is one the docs offer to a client like DevOps Agent. For example, a pre-registered Authorization Code client is fine when the docs' default mechanism is one DevOps Agent doesn't use. Say in the scope line that there is no DevOps Agent-specific partner guide. That is not a finding by itself.
- Compare the docs with `connector.yaml` and the connector README on these points:
  - Supported auth methods, and any it says not to use.
  - The endpoint for each region, including any canonical host that breaks the regional pattern.
  - Required headers and key format.
  - Permissions, including OAuth client scopes and any scope granted regardless of the user's role.
  - Tools to allowlist, and which tools write.
- A contradiction that changes what the customer enters, which endpoint or auth flow is used, or what the agent does is a blocker. Ask the partner to align the connector or the docs.

In past reviews here, the most consequential finding came from this check. A connector advertised a flow, DCR, that the partner's own guide said AWS DevOps Agent cannot complete. Valid discovery metadata does not outweigh that guide.

### 4.2 Region table

- Check every row of the README's region table against the partner's own region or domain documentation.
- Sign-in hostnames, MCP hosts, OAuth issuers, and token endpoints can each use different domains. Never infer one from another; regional naming patterns are often inconsistent.
- To probe a customer-style hostname, use a dummy team name. A name that does not resolve, or that fails TLS hostname validation, supports a documentation finding. The partner's documentation is the authority, though.

### 4.3 Unauthenticated probes and OAuth discovery (non-mutating)

For each endpoint, this does three things without credentials:

1. Sends an MCP `initialize`.
2. Finds the protected-resource metadata. It tries the `WWW-Authenticate` hint first, then the RFC 9728 well-known paths.
3. Checks each declared auth option against its authorization server's metadata.

```bash
python3 - "$NAME" <<'EOF'
import json, re, sys, urllib.error, urllib.parse, urllib.request
import yaml

doc = yaml.safe_load(open(f"connectors/{sys.argv[1]}/connector.yaml"))
mcp = doc["mcp"]
INIT = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {},
    "clientInfo": {"name": "connector-review", "version": "0"}}}).encode()

def fetch(url, data=None):
    # Some partner edges reject Python's default User-Agent with 403.
    headers = {"Accept": "application/json, text/event-stream", "User-Agent": "connector-review/1.0"}
    if data:
        headers["Content-Type"] = "application/json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=15) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()
    except Exception as e:
        return f"{type(e).__name__}: {str(e)[:80]}", {}, b""

def first_json(urls):
    for u in dict.fromkeys(urls):
        status, _, body = fetch(u)
        if status == 200:
            try:
                return u, json.loads(body)
            except ValueError:
                pass
    return None, None

def well_known(url, suffix):
    p = urllib.parse.urlsplit(url)
    origin, path = f"{p.scheme}://{p.netloc}", p.path.rstrip("/")
    return [origin + suffix + path, url.rstrip("/") + suffix, origin + suffix]

def for_label(value, label):
    return value.get(label) if isinstance(value, dict) else value

def same(a, b):
    return bool(a) and bool(b) and a.rstrip("/") == b.rstrip("/")

def show(v):
    return "ok" if v is True else ("MISMATCH" if v is False else v)

for e in mcp.get("endpoints") or [{"label": "-", "endpoint": mcp["endpoint"]}]:
    label, url = e["label"], e["endpoint"]
    if "{{" in url:
        print(f"{label}: {url} uses config placeholders; probe by hand with a dummy value")
        continue
    status, headers, _ = fetch(url, INIT)
    print(f"{label}: {url} initialize -> {status}" + ("   BLOCKER: answers without credentials" if status == 200 else ""))
    hint = re.search(r'resource_metadata="([^"]+)"', headers.get("WWW-Authenticate", "") if headers else "")
    prm_url, prm = first_json(([hint.group(1)] if hint else []) + well_known(url, "/.well-known/oauth-protected-resource"))
    servers = (prm or {}).get("authorization_servers") or []
    print(f"   protected resource: {prm_url or 'none found (not a finding; compare with partner docs)'}"
          + (f" -> resource {prm.get('resource')}, authorization_servers {servers}" if prm else ""))
    for auth in mcp["auth"]:
        kind = auth["type"]
        if kind == "api_key":
            print("   api_key: nothing to discover")
            continue
        if kind == "dynamic_client_registration":
            issuer, source = for_label(auth["authorization_server"], label), "declared"
        elif servers:
            issuer, source = servers[0], "from protected resource"
        else:
            p = urllib.parse.urlsplit(for_label(auth["exchange_url"], label))
            issuer, source = f"{p.scheme}://{p.netloc}", "guessed from exchange_url"
        if not issuer or "{{" in issuer:
            print(f"   {kind}: no issuer to check; compare URLs with partner docs")
            continue
        meta_url, meta = first_json(well_known(issuer, "/.well-known/oauth-authorization-server")
                                    + well_known(issuer, "/.well-known/openid-configuration"))
        if not meta:
            print(f"   {kind}: issuer {issuer} ({source}): no metadata found")
            continue
        grants = meta.get("grant_types_supported") or []
        checks = {"issuer": same(meta.get("issuer"), issuer)}
        if prm:
            checks["listed by resource"] = any(same(s, issuer) for s in servers)
        if kind == "dynamic_client_registration":
            checks["registration_endpoint"] = bool(meta.get("registration_endpoint"))
        if kind == "oauth_3lo":
            checks["authorization_url"] = same(meta.get("authorization_endpoint"), for_label(auth["authorization_url"], label))
            checks["exchange_url"] = same(meta.get("token_endpoint"), for_label(auth["exchange_url"], label))
            checks["pkce S256"] = ("S256" in (meta.get("code_challenge_methods_supported") or [])) if auth.get("pkce") else "not declared"
            checks["refresh_token grant"] = "advertised" if "refresh_token" in grants else "not advertised"
        if kind == "oauth_client_credentials":
            checks["exchange_url"] = same(meta.get("token_endpoint"), for_label(auth["exchange_url"], label))
            checks["client_credentials grant"] = "client_credentials" in grants
        print(f"   {kind}: issuer {issuer} ({source}) " + " ".join(f"{k}={show(v)}" for k, v in checks.items()))
EOF
```

How to read the output:

- **`initialize`**: expect 401 or 403. A 200 is a blocker.
- **`MISMATCH`**: a `MISMATCH` on `issuer`, `listed by resource`, `authorization_url`, `exchange_url`, or `pkce S256` is a blocker, unless the partner's docs explain it. Quote both values in the finding.
- **DCR without `registration_endpoint`**: a blocker.
- **`none found` or `no metadata found`**: not a finding by itself, because not every server publishes discovery metadata. Compare the URLs with the partner's docs instead.
- **`refresh_token grant=not advertised`** on `oauth_3lo`: ask the partner how the connection survives token expiry.
- **Errors**: an endpoint that returns an error rather than a status may be a network or edge block. Retry it with `curl` before calling it a finding.

The script never sends credentials. Do not add them.

### 4.4 Authentication, by type

- **`api_key`**: The README must state the exact key type and where to create it. Check the header name and prefix, and that an ingestion key or admin key is not the normal path. Check minimum permissions, expiry, and revocation.
- **`oauth_3lo`**: 4.3 checks the per-region authorization and token URLs, PKCE, and the refresh grant. Confirm who creates the client and whether a secret is needed. Check callback registration, PKCE (`client_id` requires `pkce: true`), and scopes. Ask whether refresh tokens rotate; single-use refresh tokens that the client does not store break the connection at expiry.
- **`dynamic_client_registration`**: The issuer must resolve and support registration (4.3). Then confirm from the partner's docs (4.1) that AWS DevOps Agent can use it.
- **`oauth_client_credentials`**: Check per-region token URLs, scopes, and `exchange_parameters`. Secrets must never appear in `mcp.config`.

### 4.5 Recommended skills

- **Coverage.** Read in full every skill that 3e flags with a non-zero tool-name count, and every skill whose description mentions changing state. Skim the rest for tool names and query bounds. State in the review which skills were read in full and which were skimmed.
- **Writes.** Read-only is the default, and a generic investigation skill must not write just because a write tool is enabled. Every write needs all of the following:
  - The user explicitly asks for it.
  - A fresh read of the target.
  - An exact preview of the change.
  - Explicit confirmation after the preview, immediately before the call.
  - A bounded target.
  - No retry with a broader permission or a guessed identifier after a denial.

  Creating a disabled rule or a draft is still a write. A dedicated write skill is the cleaner pattern, but a guarded inline write is acceptable.
- **Tool names and parameters.** They must match the partner's tool documentation or an authenticated `tools/list`. Never accept guessed names or casing.
- **Queries.** The skill should define scope, time bounds, row and aggregate limits, and stop conditions once. Each example should follow them. A result limit does not bound bytes scanned or cost, so ask for a source for any cost or performance claim.
- **Hand-offs.** A reference to another skill that is not in the repository or in the connector's `skills:` list is a nit. Drop it or say "if installed".
- **Permissions.** If any recommended skill writes, the connector README must say which skills write and what extra roles they need, not only the read-only role.
- **Partner-managed exemptions.** Each skill should carry the exact standard `evals/exemptions.json` from `CONTRIBUTING.md`. An exempt skill has not been evaluated, so do not call it evaluated.
- **Size and summary.** `validate_skills` warnings on body length and a missing `metadata.summary` are nits.

### 4.6 Triggers

If `triggers` is absent, that is not a finding.

If present, check:

- The webhook auth matches what the partner can send.
- `incidentId`, `title`, and `priority` render to valid JSON.
- Each firing gets its own ID, because a reused ID is deduplicated and dropped.
- Priorities map onto the platform's set.
- Free text is JSON-escaped.
- No secrets are copied into `data`.
- If resolved notifications would open a second investigation, the README says to turn them off.
- The README setup steps match the partner's own setup page.

### 4.7 Ownership and logo

- **Partner-managed claim.** It needs evidence: the author or maintainer belongs to the partner organization, the partner confirms in the thread, or the SME attests. Commit email domains and org membership are good signals.
- **Logo.** The partner's own logo is covered by that evidence. Third-party branding needs explicit authorization.

### 4.8 PR description

- A PR description that does not follow the template is not a connector defect.
- If the checklist check fails or adds `needs-checklist`, tell the reviewer, because the repository treats that label as a hold. Do not make it a blocker in the review.
- Fork PR runs of the check may be waiting for approval, so run it locally from the trial merge. Exit 0 is pass, 1 is fail, and 2 means it could not run. The verdict is in `$WORK/checklist/outcome`.

  ```bash
  gh api repos/$REPO/pulls/$N > "$WORK/pr.json" && python3 -c 'import json, sys; pr = json.load(open(sys.argv[1])); json.dump({"action": "synchronize", "number": pr["number"], "pull_request": pr}, open(sys.argv[2], "w"))' "$WORK/pr.json" "$WORK/event.json"
  python3 .github/scripts/check_pr_checklist.py --event "$WORK/event.json" --base-ref origin/main --head-ref HEAD --out "$WORK/checklist"; echo "exit=$? outcome=$(cat "$WORK/checklist/outcome")"
  ```

## Step 5: Classify

**Blockers:**

- A contract failure from step 3.
- A contradiction from 4.1 or 4.2 that changes setup or behavior.
- An auth flow with no evidence that AWS DevOps Agent supports it.
- An unauthenticated endpoint.
- An unguarded write.
- Invented tool names or query syntax.
- An unbounded query path.
- An invalid trigger template.
- Sensitive or proprietary content.
- Missing ownership evidence.
- A missing version bump.
- A partner change to `releases.yaml`.
- Permission guidance that leaves writes uncontrolled. A skill can write, and nothing documented stops it: neither the README's roles or scopes, nor a DevOps Agent control the README tells customers to use, such as disabling write tools or requiring approval.

**Nits:**

- A permission gap that a documented control already covers. For example, the README omits an OAuth scope that grants writes, but tells customers to disable write tools or require approval.
- An unused config field.
- A hand-off to a missing skill.
- Body length or a missing summary.
- Wording that does not change behavior.
- Cosmetic logo issues.

**Not findings by themselves:**

- A 401 response.
- Absent triggers.
- The standard partner exemption.
- A PR body that is not on the template.
- A connector that differs from one already on `main`, when the partner contract explains the difference.

Before asserting a defect, quote the line, name the authoritative source, state the consequence, and say what resolves it. If sources conflict, ask the partner and SME rather than choosing silently.

## Step 6: Report, draft, post

Give the reviewer this summary first. Use the same shape for every connector so reviews can be compared.

```
Connector: <name>  PR #<N>  head <sha>  trial merge on main <sha>
Pre-flight: clean | stopped: <why>
SME: <login> approved <sha>; said they verified <what>
Contract (3a-3d): schema <n errors>; files <ok|...>; labels <ok|...>; skills <n ok|missing ...>; svg <none|...>; validators <results>
Partner docs (4.1): <url> read in full; DevOps Agent page | general MCP page; agrees | contradicts: <what>
Regions (4.2): checked against <source>; <ok | rows wrong>
Probes (4.3): initialize <labels -> codes>; discovery <ok | MISMATCH: ... | none found>
Checklist (4.8): <pass | fail: ...>
Auth (4.4): <type>: <evidence level> ...
Skills (4.5): <n>; write-capable <...>; read in full <...>; skimmed <...>
Triggers (4.6): absent | <checks>
Ownership (4.7): <evidence>
Blockers: ...
Nits: ...
Not verified: ...
Promotion preconditions: ...
```

Then draft the review comment in a file under `$WORK`. If the reviewer has their own review format, use it. Otherwise use three sections:

1. **What needs to change.** Blockers, each with file and line, why it matters, and the fix.
2. **Nits.** One line each.
3. **Thanks.** Specific credit, what you verified, and the scope line, including what was not authenticated or run end to end.

Scan the draft for sensitive strings. Show the reviewer the draft and wait for an explicit go. Post with `gh pr review $N -R $REPO --body-file <file>` and the flag they chose. Then check that the posted body, state, and commit match the draft.

- Do not pipe `gh pr review` (or any `gh` write) through `grep` or another filter. The shell reports the filter's exit status instead of `gh`'s. `GH_NO_UPDATE_NOTIFIER=1` from Step 1 already keeps the output clean.
- If a post's result is unclear, list the PR's reviews before trying again, so you don't post twice.

## Reviewing several connector PRs

- List the queue:

  ```bash
  gh pr list -R $REPO --state open --limit 100 --json number,title,author,isDraft,files --jq '.[] | select([.files[].path] | any(startswith("connectors/"))) | {number, title, author: .author.login, draft: .isDraft}'
  ```

  Review one PR to completion before starting the next, and keep each PR's step 6 summary.
- Compare each connector with those already on `main` (command below). A difference the partner contract does not explain is worth a question, not a blocker.
- After any connector merges, redo steps 2 and 3 for the PRs still open. Many connector PRs edit `llms.txt`, so they go stale or conflict.
- Before merging, check `main`'s branch protection, which says which checks are required, whether a new push dismisses earlier approvals (including the SME's), and whether conversations must be resolved. Run `gh api repos/$REPO/branches/main/protection` if you have access.
- Fork PR workflow runs wait in `action_required` until a maintainer approves them. Approving them is an action that needs the reviewer's go.

To compare connectors, run this from the trial merge:

```bash
python3 - <<'EOF'
import pathlib, yaml
for p in sorted(pathlib.Path("connectors").glob("*/connector.yaml")):
    d = yaml.safe_load(p.read_text()); m = d["mcp"]
    auth = ",".join(a["type"] for a in m["auth"])
    print(f'{d["name"]:<18} v{d["version"]:<7} {d["tier"]:<16} {auth:<42} endpoints={len(m.get("endpoints") or [m.get("endpoint")])} triggers={"yes" if "triggers" in d else "no"} skills={len(d.get("skills", []))}')
EOF
```

## When you finish

```bash
deactivate 2>/dev/null; cd "$SRC" && git worktree remove --force "$WORK/tree" && rm -rf "$WORK"
```

Leave the reviewer's own branch, working tree, and git config untouched.
