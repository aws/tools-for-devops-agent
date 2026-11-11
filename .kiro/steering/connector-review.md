---
inclusion: auto
name: connector-review
description: Review pull requests that add or change a partner connector under connectors/ in this repository, together with the skills the connector recommends. Use when asked to review, re-review, or compare connector PRs, or to check a connector's endpoints, authentication, setup guide, triggers, logo, or partner skills.
---

# Reviewing connector pull requests

A connector is `connectors/<name>/`: a `connector.yaml` describing a partner-hosted MCP server, a `logo.svg` (optional `logo-dark.svg`), and a `README.md` setup guide, plus the skills listed under `skills:`. It holds no server code. Several connector PRs are usually open at once and reviewed by different maintainers, so review every one the same way and report in the same shape.

Repository facts to re-check if anything looks different: `/connectors/` is owned by the admin team in `.github/CODEOWNERS`; `connectors/README.md` says submissions are not open yet; the PR checklist check holds a connector change to the Connectors section (the partner terms box and `contact_email`) and any `skills/` in the PR to the skill checklist; `validate_skills` checks each connector's YAML and version rules (3c and 3d) but not its schema or the published-file allowlist, which step 3a covers.

Partners build to the Connector Guide for Partners until it moves into `CONTRIBUTING.md`. Once `CONTRIBUTING.md` has a connector guide, it takes precedence over this file wherever the two disagree.

## Ground rules

- Do not post, approve, request changes, approve fork CI runs, add or remove labels, resolve threads, or merge without the reviewer's explicit go for that action. Adding a label re-triggers CI, so it counts.
- Do not run code from the PR in the reviewer's normal environment or with their credentials (step 3).
- Probe partner endpoints only without credentials. `connector.yaml` comes from an untrusted PR, so send its hosts nothing beyond the 4.3 script, which talks only to hosts `connector.yaml` names, over `https`, never to a private address, and without following redirects. The sign-in hostnames 4.2 checks come from the partner's own docs, not from `connector.yaml`.
- Report only what you checked, and say what each check proves (table below). Name anything you did not check.
- Do not repeat sensitive strings from the PR in chat or review text, such as internal hostnames, real emails, account or tenant IDs, customer names, or secrets. Describe them instead.
- Each command block may run in a fresh shell, so don't rely on the working directory or a variable carrying over between them. Step 2 saves the review's state to `~/.cache/connector-review/<N>.env`, and every later block restores it on its first line. Set `N` to the PR number at the start of each block, and `NAME` too when the PR has more than one connector. Exported variables can survive from an earlier review, so the restore ignores a `NAME` that isn't a connector in this PR and prints the one it uses.

## What each check proves

| Evidence | Proves | Does not prove |
|---|---|---|
| `connector.yaml` passes the JSON Schema | Descriptor shape | That it works |
| Unauthenticated MCP `initialize` returns 401 or 403 | Host is reachable and rejects anonymous calls | That authentication works |
| Discovery metadata matches the descriptor | The server supports the declared flow. Every auth type in the connector format is one AWS DevOps Agent supports for a custom MCP server | That a sign-in completes for a real account |
| The partner's docs (`docs_url`) match the descriptor and README | The partner documents this setup | That anyone ran it end to end |
| Authenticated run in a non-production Agent Space | It works for that region and auth type | Other regions or auth types |

**Merge** needs the repository contract verified (step 3), evidence the server supports each declared auth type (4.3, 4.4), and no unresolved contradiction that changes what the customer enters or which endpoint is used.

**Production promotion** is separate. It is a maintainer change to `connectors/releases.yaml`, and it needs a live install, sign-in, `tools/list`, and skill load for each advertised endpoint and auth pair.

So a connector can reach `main` without anyone having signed in to it. That is acceptable only because `connectors/releases.yaml` gates production and only maintainers change it.

Anything you could only check statically goes in the review's scope line as a promotion precondition, not a merge blocker. The maintainer change that adds the connector to `connectors/releases.yaml` must link the connector PR and confirm each precondition from its review.

## Step 1: Pre-flight

Run this before reading the diff, and again right before posting anything.

```bash
(
export GH_NO_UPDATE_NOTIFIER=1   # keeps gh's upgrade notice off stderr, so no output filtering is needed
REPO=aws/tools-for-devops-agent; N=${N:?set N to the PR number}
DIRS=$(gh pr view $N -R $REPO --json files --jq '[.files[].path | split("/") | select(.[0] == "connectors" and length >= 3) | .[1]] | unique | join(" ")')
echo "directories under connectors/ this PR touches: ${DIRS:-none}"
gh pr view $N -R $REPO --json state,isDraft,headRefOid,author,assignees,reviewRequests,reviews,comments,labels
gh api repos/$REPO/issues/$N/comments --paginate --jq '.[] | "### \(.user.login) at \(.created_at)\n\(.body)\n"'
gh api repos/$REPO/pulls/$N/reviews --paginate --jq '.[] | "### \(.user.login): \(.state) on \(.commit_id[0:7])\n\(.body)\n"'
gh api graphql -f query="query{repository(owner:\"aws\",name:\"tools-for-devops-agent\"){pullRequest(number:$N){reviewThreads(first:100){nodes{isResolved path comments(first:20){nodes{author{login} body}}}}}}}"
gh api orgs/aws/teams/tools-for-devops-agent-admins/members --jq '[.[].login]'
echo "$DIRS" | tr ' ' '\n' | while read -r d; do [ -n "$d" ] && gh pr list -R $REPO --state all --limit 100 --search "$d" --json number,title,state; done
)
```

Step 2 narrows these to connector directories, the ones with a `connector.yaml`. If it finds none, the PR changes only shared connector files such as `connectors/README.md` or the schema, and this file doesn't apply. Review it as an infrastructure change.

Read full bodies, not summaries. Stop and tell the reviewer if any of these is true:

- Another maintainer or admin has commented, is assigned, or has a pending individual review request. A request to the admin team alone is the CODEOWNERS default.
- Any reviewer's ask is unresolved, such as "before this lands" or a question to the author.
- Another PR touches the same connector or skills, or this PR says it supersedes one.

Record which commit the SME approved and what they said they verified. Commits after that approval are not covered by it.

## Step 2: Trial merge

Never review in the reviewer's own working tree; it may hold uncommitted work. This block merges the PR into a temporary worktree and stops on a conflict. It lists the connectors the PR adds or changes, prints the PR's changed files, and saves the state that later blocks restore.

```bash
(
N=${N:?set N to the PR number}; REPO=aws/tools-for-devops-agent
SRC=$(git rev-parse --show-toplevel) || exit 1
STATE="$HOME/.cache/connector-review/$N.env"
[ -f "$STATE" ] && { echo "STOP: a review of #$N is already in progress ($STATE). Finish it, or run the cleanup block first." >&2; exit 1; }
git -C "$SRC" fetch -q origin main "+pull/$N/head:refs/remotes/origin/pr/$N" || exit 1
WORK=$(mktemp -d)
git -C "$SRC" worktree add -q --detach "$WORK/tree" origin/main || exit 1
cd "$WORK/tree" || exit 1
if ! git -c user.name=review -c user.email=review@localhost merge -q --no-ff --no-edit "origin/pr/$N" >/dev/null 2>&1; then
  git diff --name-only --diff-filter=U | sed 's/^/conflict: /'
  git merge --abort; cd "$SRC" && git worktree remove --force "$WORK/tree"; rm -rf "$WORK"
  echo "STOP: #$N does not merge cleanly into main. Report the conflict to the author; do not run step 3." >&2; exit 1
fi
[ -z "$(git status --porcelain)" ] || { echo "STOP: the trial merge left uncommitted changes" >&2; exit 1; }
git diff --name-only "origin/main...origin/pr/$N" > "$WORK/changed-files.txt"
CONNECTORS=$(git diff --name-only "origin/main...origin/pr/$N" -- connectors/ | awk -F/ 'NF >= 3 {print $2}' | sort -u |
  while read -r c; do git cat-file -e "origin/pr/${N}:connectors/${c}/connector.yaml" 2>/dev/null && printf '%s ' "$c"; done)
CONNECTORS=${CONNECTORS% }
ALLOWED="^(llms\.txt\$|skills/[^/]+/$(echo "$CONNECTORS" | tr ' ' '\n' | sed '/^$/d; s#.*#|connectors/&/#' | tr -d '\n'))"
mkdir -p "$(dirname "$STATE")"
{ printf "export GH_NO_UPDATE_NOTIFIER=1\nREPO='%s' N='%s' SRC='%s' WORK='%s' CONNECTORS='%s'\n" "$REPO" "$N" "$SRC" "$WORK" "$CONNECTORS"
  cat <<'RESTORE'
[ -n "${REVIEW_STATE_ONLY:-}" ] && return 0
case "$CONNECTORS" in
  "") echo "no connector directory with a connector.yaml in #$N" >&2; return 1 ;;
  *" "*) case " $CONNECTORS " in
           *" ${NAME:-} "*) [ -n "${NAME:-}" ] || { echo "#$N has several connectors; set NAME to one of: $CONNECTORS" >&2; return 1; } ;;
           *) echo "#$N has several connectors; set NAME to one of: $CONNECTORS" >&2; return 1 ;;
         esac ;;
  *) NAME=$CONNECTORS ;;
esac
echo "reviewing connector $NAME in #$N" >&2
[ -f "$WORK/venv/bin/activate" ] && . "$WORK/venv/bin/activate"
cd "$WORK/tree" || return 1
RESTORE
} > "$STATE"
git merge-base --is-ancestor origin/main "origin/pr/$N" && echo "head contains main" || echo "head is behind main"
echo "connectors: ${CONNECTORS:-none}"
echo "--- changed files"; cat "$WORK/changed-files.txt"
OUTSIDE=$(grep -v -E "$ALLOWED" "$WORK/changed-files.txt")
if [ -n "$OUTSIDE" ]; then echo "--- STOP before step 3: these files are outside the connector, its skills, and llms.txt:"; echo "$OUTSIDE"; fi
)
```

- **A conflict** is a finding for the author. The block aborts the merge and removes the worktree, so there is nothing to clean up.
- **A clean merge from a stale head** is not a finding, but say so.
- **Several connectors:** review each one through steps 3 and 4 separately, setting `NAME` for each.
- **No connectors listed:** the PR changes only shared files under `connectors/`, so this file doesn't apply.
- **Files outside those paths:** if the block prints a STOP for them, tell the reviewer before going further, especially for `.github/`, `tests/`, `docs/hooks/`, `mkdocs.yml`, or dependency files. The validators in step 3 would run that code.

## Step 3: Deterministic checks

First, create a throwaway environment. It installs `pyyaml` from the hash-pinned requirements on `main`, not from the PR, and a pinned `jsonschema`. Later blocks activate it on their own.

```bash
(
. "$HOME/.cache/connector-review/${N:?set N to the PR number}.env" || exit 1
python3 -m venv "$WORK/venv" && . "$WORK/venv/bin/activate" &&
git show origin/main:.github/scripts/skill-rules/requirements.txt > "$WORK/requirements.txt" &&
pip install -q --require-hashes -r "$WORK/requirements.txt" && pip install -q "jsonschema==4.26.0" && echo "environment ready"
)
```

**3a. Connector contract.** This checks the schema, the published-file allowlist (from git, so untracked files don't count), and some of the rules the schema leaves to a catalog check: unique labels and auth types, regional map parity, and declared placeholders. The rules after the block are not scripted, so read `connector.yaml` for them.

```bash
(
. "$HOME/.cache/connector-review/${N:?set N to the PR number}.env" || exit 1
python3 - "$NAME" <<'EOF'
import json, re, subprocess, sys
from pathlib import Path
import jsonschema, yaml

name = sys.argv[1]
root = f"connectors/{name}"
def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout
text = git("show", f"HEAD:{root}/connector.yaml")
try:
    doc = yaml.safe_load(text)
except yaml.YAMLError as e:
    sys.exit(f"connector.yaml does not parse: {e}")
if not isinstance(doc, dict):
    sys.exit("connector.yaml is missing or is not a mapping")
version = doc.get("schema_version")
schema_dir = Path("connectors/schema") / f"v{version}"
if not isinstance(version, int) or not (schema_dir / "connector.schema.json").is_file():
    sys.exit(f"schema errors: 1\n   ['schema_version'] {version!r} has no schema under connectors/schema/")
schema = json.loads((schema_dir / "connector.schema.json").read_text())
errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
print("schema errors:", len(errors))
for e in errors:
    print("  ", list(e.path), e.message[:200])
print("name matches directory:", doc.get("name") == name)
allowed = {f["path"] for f in json.loads((schema_dir / "published-files.json").read_text())["files"]}
present = {p[len(root) + 1:] for p in git("ls-tree", "-r", "--name-only", "HEAD", "--", f"{root}/").splitlines()}
print("files outside allowlist:", sorted(present - allowed) or "none")
mcp = doc.get("mcp") or {}
labels = [e.get("label") for e in mcp.get("endpoints") or []]
print("endpoint labels:", labels or "single endpoint")
print("duplicate labels:", sorted({x for x in labels if labels.count(x) > 1}) or "none")
types = [a.get("type") for a in mcp.get("auth") or []]
print("auth types in order:", types, "| duplicates:", sorted({t for t in types if types.count(t) > 1}) or "none")
for a in mcp.get("auth") or []:
    for key, value in a.items():
        if isinstance(value, dict):
            missing, extra = sorted(set(labels) - set(value)), sorted(set(value) - set(labels))
            print(f"{a.get('type')}.{key} label parity:", "ok" if not (missing or extra) else f"missing {missing} extra {extra}")
declared = {c.get("name") for c in mcp.get("config") or []}
used = set(re.findall(r"\{\{\s*config\.([a-z0-9_]+)\s*\}\}", text))
print("undeclared placeholders:", sorted(used - declared) or "none", "| unused config:", sorted(declared - used) or "none")
print("triggers:", "present, auth " + str(doc["triggers"].get("auth", "api_key (default)")) if "triggers" in doc else "absent")
llms = Path("llms.txt").read_text()
for s in doc.get("skills") or []:
    skill = Path("skills") / s / "SKILL.md"
    if not skill.is_file():
        print(f"skill {s}: MISSING")
        continue
    tier = re.search(r'^\s*tier:\s*"?([a-z-]+)', skill.read_text(), re.M)
    print(f"skill {s}: tier {tier.group(1) if tier else 'unset'} | in llms.txt: {f'skills/{s}/SKILL.md' in llms}")
EOF
)
```

Any schema error, extra file, name mismatch, duplicate label or auth type, label-parity mismatch, undeclared placeholder, or missing skill is a blocker. An unused config field is a nit. For a partner connector, every skill should be `partner-managed`.

The script doesn't cover these catalog-check rules, so read `connector.yaml` for them. Each is a blocker:

- A `{{config.<name>}}` placeholder fills a whole host label, path segment or `exchange_parameters` value, never part of one or the query. A server the customer runs uses two fields: `https://{{config.<host>}}:{{config.<port>}}/...`.
- A placeholder with an open pattern fills only the leftmost host label; anywhere else, its pattern lists the values, such as `^(eu1|us1)$`. No placeholder fills the registrable domain.
- A pattern is `^...$` with only lowercase letters, digits, `-`, `(a|b)` groups, and `[a-z0-9-]` or `[0-9]` with `{n}` or `{m,n}`, and doesn't match an empty value. A customer-run host may also use `[a-z0-9.-]`, up to 253 characters; its port uses only digits, up to 5.
- No reserved header, such as `Host`, `Accept`, `Content-Type`, `Cookie`, `User-Agent`, `Origin`, `WWW-Authenticate`, `Mcp-Session-Id`, or a name starting with `x-amz-`, `x-amzn-`, `x-forwarded-`, `proxy-` or `sec-`.

**3b. Files, logo, and release manifest.** The SVG search joins each file onto one line first, so whitespace or a line break before an `=` doesn't hide an attribute.

```bash
(
. "$HOME/.cache/connector-review/${N:?set N to the PR number}.env" || exit 1
git ls-files -s "connectors/$NAME" | awk '$1 != "100644"'      # expect no output: no executable bits or symlinks
for f in $(git ls-files "connectors/$NAME" | grep '\.svg$'); do
  tr '\n\r\t' '   ' < "$f" | grep -o -i -E "<script|javascript:|[[:space:]]on[a-z]+[[:space:]]*=|<foreignobject|<!doctype|<!entity|<image|@import|data:[a-z]+/|url\([[:space:]]*[\"']?[^#\"'[:space:])]|href[[:space:]]*=[[:space:]]*[\"'][^#\"']" | sed "s#^#$f: #"
done | grep . || echo "svg: none"
git diff --name-only "origin/main...origin/pr/$N" -- connectors/releases.yaml   # expect no output
)
```

- Any SVG hit is a blocker unless there is a clear, harmless reason.
- The grep finds only the dangerous constructs, and the catalog check is an allowlist, so also read each logo for these. Each is a blocker:
  - Only `svg`, `g`, `defs`, `title`, `desc`, `path`, `rect`, `circle`, `ellipse`, `line`, `polyline`, `polygon`, `use`, `linearGradient`, `radialGradient`, `stop`, `clipPath` and `style` elements, with geometry and presentation attributes, `id`, `class` and `data-name`.
  - A `viewBox` of four numbers with a positive width and height.
  - At most one `<style>`, holding only class rules of fill, stroke, opacity, stop and `clip-rule` properties.
  - A `style` attribute only on the root `<svg>` (`enable-background`) or on a `<use>` (`overflow`).
  - At most 16 KiB per logo. Every file is at most 1 MiB, and `connector.yaml` at most 32 KiB.
- Also render the logo at small size on light and dark backgrounds.
- A partner PR that changes `releases.yaml` is a blocker. Production promotion is a separate maintainer change.

**3c. Repository validators.** These run on the committed trial merge. `validate_skills` skips uncommitted changes and says so in a `note:` line, so treat that note as a failed run, not a pass. The labels are passed the way CI passes them, because `enforce-evals` changes the result.

```bash
(
. "$HOME/.cache/connector-review/${N:?set N to the PR number}.env" || exit 1
[ -z "$(git status --porcelain)" ] || { echo "STOP: the trial merge has uncommitted changes" >&2; exit 1; }
python3 .github/scripts/validate_skills.py --base-ref origin/main
python3 .github/scripts/validate_skill_evals.py --base-ref origin/main --head-ref HEAD --pr-number $N --labels "$(gh pr view $N -R $REPO --json labels --jq '[.labels[].name]')"
python3 .github/scripts/scan_aws_identifiers.py --base-ref origin/main
python3 -m unittest discover -s tests
pip install -q "mkdocs-material==$(git show origin/main:.github/workflows/build-docs.yml | grep -o 'mkdocs-material==[0-9.]*' | head -1 | cut -d= -f3)" && mkdocs build --strict -d "$WORK/site"
)
```

Record the command, exit status, test count, and warning count for each. The unit-test output includes an `::error::The PR checklist check could not run` line; a checklist test prints it on purpose. Judge the tests by the `Ran N tests` and `OK` lines. `scan_aws_identifiers` covers only account and EC2 instance IDs, so sweep the connector and skill files yourself for the strings listed under Ground rules.

**3d. Versions.**

- A new connector or skill normally starts at `1.0.0`.
- For an existing connector, any change to its files needs a higher `version`. Changing or removing an auth option (a header label included), removing an endpoint or changing its URL, or adding an `mcp.config` field needs a new major version.
- For an existing skill, any change to published content needs a higher `metadata.version`.
- `validate_skills` in 3c checks both against the merge base, so treat any version error it reports as a blocker. It compares with `main`, not with the catalog: while publishing is stalled and `main` holds a version the catalog hasn't published, also compare the pull request with the version the catalog serves.

**3e. Find the write-capable skills.** Use both searches; the second catches skills that describe writes in prose without naming a tool.

```bash
(
. "$HOME/.cache/connector-review/${N:?set N to the PR number}.env" || exit 1
T='(^|[^A-Za-z])(create|update|delete|remove|manage|assign|acknowledge|resolve|close|mute|set|add|link|post|send)(_[a-z]|[A-Z])'
W='\b(creat(e|es|ing)|updat(e|es|ing)|delet(e|es|ing)|modif(y|ies)|assign(s|ing)?|acknowledg(e|es|ing)|mute|enable|disable|overwrite)\b'
SKILLS=$(python3 -c 'import sys, yaml; print("\n".join(yaml.safe_load(open(f"connectors/{sys.argv[1]}/connector.yaml")).get("skills") or []))' "$NAME")
[ -n "$SKILLS" ] || { echo "no recommended skills"; exit 0; }
echo "$SKILLS" | while read -r s; do
  printf '%-40s tool-names=%s write-verbs=%s\n' "$s" "$(grep -c -E "$T" skills/$s/SKILL.md)" "$(grep -c -i -E "$W" skills/$s/SKILL.md)"
done
)
```

The counts are a triage aid. They are not a classification.

## Step 4: Manual checks, highest yield first

### 4.1 The partner's documentation

- Open `docs_url` and read the whole page, plus the pages it links for authentication and permissions. An HTTP 200 proves nothing about content.
- Note what kind of page it is: an AWS DevOps Agent setup page, or a general MCP server page written for other clients. If it's a general page, search the partner's docs for a DevOps Agent page. If there is none, say so in the scope line; that is not a finding by itself.
- Compare the docs with `connector.yaml` and the connector README on these points:
  - The endpoint for each region, including any canonical host that breaks the regional pattern.
  - What the customer enters: header names, key format, client IDs and secrets.
  - Permissions, including OAuth client scopes and any scope granted regardless of the user's role.
  - Tools to allowlist, and which tools write.
- A contradiction that changes what the customer enters or which endpoint is used is a blocker. Ask the partner to align the connector or the docs.
- When the connector offers more than the docs describe, ask the partner to update their docs. Don't block, and don't ask them to remove it. That covers an auth type the server's discovery supports (4.3) and a write-capable skill with a guard (4.5). It holds even for an AWS DevOps Agent setup page: every auth type in the connector format is a flow AWS DevOps Agent already supports for a custom MCP server, and the live run before production promotion runs it end to end.
- Partner docs can also be wrong about how AWS DevOps Agent behaves. One partner's guide said its DCR sign-in would fail because its refresh tokens are single-use. AWS DevOps Agent saves the new refresh token from each refresh, so the connector kept DCR and the partner was asked to fix the guide. When partner docs say a flow can't work with AWS DevOps Agent, ask the SME before treating it as a finding.

### 4.2 Region table

- Check every row of the README's region table against the partner's own region or domain documentation.
- Sign-in hostnames, MCP hosts, OAuth issuers, and token endpoints can each use different domains. Never infer one from another; regional naming patterns are often inconsistent.
- To probe a customer-style hostname, use a dummy team name. A name that does not resolve, or that fails TLS hostname validation, supports a documentation finding. The partner's documentation is the authority, though.

### 4.3 Unauthenticated probes and OAuth discovery (non-mutating)

For each endpoint, this does three things without credentials:

1. Sends an MCP `initialize`.
2. Finds the protected-resource metadata. It tries the `WWW-Authenticate` hint first, then the RFC 9728 well-known paths.
3. Checks each declared auth option against its authorization server's metadata, trying every server the protected resource lists.

It sends requests only over `https`, only to hosts named under `mcp:` in `connector.yaml`, and never to a host that resolves to a private, loopback, or link-local address. It reports a redirect instead of following it.

```bash
(
. "$HOME/.cache/connector-review/${N:?set N to the PR number}.env" || exit 1
python3 - "$NAME" <<'EOF'
import ipaddress, json, re, socket, sys, urllib.error, urllib.parse, urllib.request
import yaml

doc = yaml.safe_load(open(f"connectors/{sys.argv[1]}/connector.yaml"))
mcp = doc["mcp"]
INIT = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
    "protocolVersion": "2025-06-18", "capabilities": {},
    "clientInfo": {"name": "connector-review", "version": "0"}}}).encode()

def urls(value):
    if isinstance(value, str) and value.startswith("https://"):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from urls(v)
    elif isinstance(value, list):
        for v in value:
            yield from urls(v)

NAMED = {urllib.parse.urlsplit(u).hostname for u in urls(mcp)}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # report the 3xx rather than follow it

OPENER = urllib.request.build_opener(NoRedirect)

def refusal(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https":
        return "not https"
    if p.hostname not in NAMED:
        return f"host {p.hostname} is not named in connector.yaml"
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(p.hostname, p.port or 443, proto=socket.IPPROTO_TCP)}
    except OSError as e:
        return f"does not resolve ({type(e).__name__})"
    private = sorted(a for a in addrs if not ipaddress.ip_address(a.split("%")[0]).is_global)
    return f"resolves to non-public address {private}" if private else None

def fetch(url, data=None):
    why = refusal(url)
    if why:
        return f"not probed: {why}", {}, b""
    # Some partner edges reject Python's default User-Agent with 403.
    headers = {"Accept": "application/json, text/event-stream", "User-Agent": "connector-review/1.0"}
    if data:
        headers["Content-Type"] = "application/json"
    try:
        with OPENER.open(urllib.request.Request(url, data=data, headers=headers), timeout=15) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:
            body = b""
        return e.code, e.headers, body
    except Exception as e:
        return f"{type(e).__name__}: {str(e)[:80]}", {}, b""

def first_json(candidates):
    for u in dict.fromkeys(candidates):
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

def same(found, declared):
    if not found or not declared:
        return None  # the metadata doesn't publish it: nothing to compare
    return found.rstrip("/") == declared.rstrip("/")

def show(v):
    return "ok" if v is True else "MISMATCH" if v is False else "not advertised" if v is None else v

def check(kind, auth, label, issuer, servers, prm):
    why = refusal(issuer)
    if why:
        return None, f"not probed: {why}"
    _, meta = first_json(well_known(issuer, "/.well-known/oauth-authorization-server")
                         + well_known(issuer, "/.well-known/openid-configuration"))
    if not meta:
        return None, "no metadata found"
    grants = meta.get("grant_types_supported")
    checks = {"issuer": same(meta.get("issuer"), issuer)}
    if prm:
        checks["listed by resource"] = any(same(s, issuer) for s in servers)
    if kind == "dynamic_client_registration":
        checks["registration_endpoint"] = True if meta.get("registration_endpoint") else "missing"
    if kind == "oauth_3lo":
        checks["authorization_url"] = same(meta.get("authorization_endpoint"), for_label(auth["authorization_url"], label))
        checks["exchange_url"] = same(meta.get("token_endpoint"), for_label(auth["exchange_url"], label))
        methods = meta.get("code_challenge_methods_supported")
        checks["pkce S256"] = ("not declared" if not auth.get("pkce") else None if methods is None else "S256" in methods)
        checks["refresh_token grant"] = "advertised" if "refresh_token" in (grants or []) else "not advertised"
    if kind == "oauth_client_credentials":
        checks["exchange_url"] = same(meta.get("token_endpoint"), for_label(auth["exchange_url"], label))
        checks["client_credentials grant"] = None if grants is None else "client_credentials" in grants
    return checks, None

for e in mcp.get("endpoints") or [{"label": "-", "endpoint": mcp["endpoint"]}]:
    label, url = e["label"], e["endpoint"]
    if "{{" in url:
        print(f"{label}: {url} uses config placeholders; probe by hand with a dummy value")
        continue
    status, headers, _ = fetch(url, INIT)
    note = ""
    if status == 200:
        note = "   BLOCKER: answers without credentials"
    elif isinstance(status, int) and 300 <= status < 400:
        note = f"   redirects to {headers.get('Location')} (not followed)"
    print(f"{label}: {url} initialize -> {status}{note}")
    hint = re.search(r'resource_metadata="([^"]+)"', (headers.get("WWW-Authenticate") or "") if headers else "")
    if hint and refusal(hint.group(1)):
        print(f"   resource_metadata hint {hint.group(1)} not followed: {refusal(hint.group(1))}")
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
            issuers, source = [for_label(auth["authorization_server"], label)], "declared"
        elif servers:
            issuers, source = servers, "from protected resource"
        else:
            p = urllib.parse.urlsplit(for_label(auth["exchange_url"], label) or "")
            issuers, source = [f"{p.scheme}://{p.netloc}"], "guessed from exchange_url"
        issuers = [i for i in issuers if i and "{{" not in i]
        if not issuers:
            print(f"   {kind}: no issuer to check; compare URLs with partner docs")
            continue
        results = [(i, *check(kind, auth, label, i, servers, prm)) for i in issuers]
        best = (next((r for r in results if r[1] and False not in r[1].values()), None)
                or next((r for r in results if r[1]), None) or results[0])
        issuer, checks, problem = best
        which = f", {issuers.index(issuer) + 1} of {len(issuers)}" if len(issuers) > 1 else ""
        detail = problem or " ".join(f"{k}={show(v)}" for k, v in checks.items())
        print(f"   {kind}: issuer {issuer} ({source}{which}) {detail}")
EOF
)
```

How to read the output:

- **`initialize`**: expect 401 or 403. A 200 is a blocker. A 3xx means the endpoint redirects anonymous calls instead of rejecting them; ask the partner, but it is not a blocker by itself.
- **`MISMATCH`**: the metadata and `connector.yaml` both give a value, and the values differ. On `issuer`, `listed by resource`, `authorization_url`, `exchange_url`, or `pkce S256` it is a blocker, unless the partner's docs explain it. Quote both values in the finding.
- **`not advertised`**: the metadata doesn't publish that field. Many fields are optional in RFC 8414, so this is not a finding. Compare with the partner's docs instead.
- **DCR `registration_endpoint=missing`**: a blocker.
- **`none found` or `no metadata found`**: not a finding by itself, because not every server publishes discovery metadata. The evidence for the auth type then has to come from the partner's docs (4.4).
- **`refresh_token grant=not advertised`** on `oauth_3lo`: ask the partner how the connection survives token expiry.
- **`not probed`**: the script refused the request. If a hint, redirect, or listed authorization server points to a host `connector.yaml` doesn't name, ask the partner why. A host in `connector.yaml` that resolves to a private address is a blocker.
- **Errors**: an endpoint that returns an error rather than a status may be a network or edge block. Retry it once with `curl --max-redirs 0` before calling it a finding.

The script never sends credentials. Do not add them.

### 4.4 Authentication, by type

- **`api_key`**: The README must state the exact key type and where to create it. Check the header name and prefix, and that an ingestion key or admin key is not the normal path. Check minimum permissions, expiry, and revocation.
- **`oauth_3lo`**: 4.3 checks the per-region authorization and token URLs, PKCE, and the refresh grant. If the server publishes no metadata, the partner's docs must give the same URLs. Confirm who creates the client and whether a secret is needed. Check callback registration, PKCE (`client_id` requires `pkce: true`), and scopes. AWS DevOps Agent saves the new refresh token from each refresh, so single-use refresh tokens work.
- **`dynamic_client_registration`**: 4.3 must show the declared `authorization_server` in the protected resource metadata (`listed by resource`), with a `registration_endpoint`. That is the evidence the flow works: AWS DevOps Agent supports DCR for any custom MCP server, so the partner's docs don't need to name it.
- **`oauth_client_credentials`**: 4.3 checks the per-region token URL and the grant. Check scopes and `exchange_parameters`. Secrets must never appear in `mcp.config`.

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
- **Queries.** The skill should define scope, time bounds, row and aggregate limits, and stop conditions once, and every example query must follow them. Agents copy examples, so an example with no time bound or no row or aggregate limit is a blocker, the same as an unbounded instruction. A result limit does not bound bytes scanned or cost, so ask for a source for any cost or performance claim.
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
- Fork PR runs of the check may be waiting for approval, so run it locally from the trial merge. Exit 0 is pass, 1 is fail, and 2 means it could not run.

  ```bash
  (
  . "$HOME/.cache/connector-review/${N:?set N to the PR number}.env" || exit 1
  gh api repos/$REPO/pulls/$N > "$WORK/pr.json" && python3 -c 'import json, sys; pr = json.load(open(sys.argv[1])); json.dump({"action": "synchronize", "number": pr["number"], "pull_request": pr}, open(sys.argv[2], "w"))' "$WORK/pr.json" "$WORK/event.json"
  python3 .github/scripts/check_pr_checklist.py --event "$WORK/event.json" --base-ref origin/main --head-ref HEAD --out "$WORK/checklist"; echo "exit=$? outcome=$(cat "$WORK/checklist/outcome")"
  )
  ```

## Step 5: Classify

**Blockers:**

- A contract failure from step 3, including a catalog-check rule in 3a or 3b.
- A contradiction from 4.1 or 4.2 that changes what the customer enters or which endpoint is used.
- An auth option with no evidence the server supports it. For DCR, 4.3 must show `listed by resource=ok` and a `registration_endpoint`. For OAuth 3LO and client credentials, discovery or the partner's docs must give the same URLs as `connector.yaml`. `no metadata found` alone is not a finding; it only means the evidence must come from the docs.
- An unauthenticated endpoint, or one in `connector.yaml` that resolves to a private address.
- An unguarded write.
- Invented tool names or query syntax.
- An unbounded query path, including an example query with no time bound or no row or aggregate limit.
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
- `not advertised` or `no metadata found` from 4.3.
- A connector that offers more than the partner's docs describe, such as an auth type discovery supports or a guarded write skill. Ask the partner to update their docs.
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
Merge (2): clean | conflict in <files>
SME: <login> approved <sha>; said they verified <what>
Contract (3a-3d): schema <n errors>; files <ok|...>; labels <ok|...>; catalog rules <ok|...>; skills <n ok|missing ...>; svg <none|...>; validators <results>
Partner docs (4.1): <url> read in full; DevOps Agent page | general MCP page; agrees | contradicts: <what> | offers more: <what>
Regions (4.2): checked against <source>; <ok | rows wrong>
Probes (4.3): initialize <labels -> codes>; discovery <ok | MISMATCH: ... | none found>
Checklist (4.8): <pass | fail: ...>
Auth (4.4): <type>: <evidence> ...
Skills (4.5): <n>; write-capable <...>; read in full <...>; skimmed <...>
Triggers (4.6): absent | <checks>
Ownership (4.7): <evidence>
Blockers: ...
Nits: ...
Not verified: ...
Promotion preconditions: ...
```

Then draft the review comment in a file under the review's `WORK` directory. If the reviewer has their own review format, use it. Otherwise use three sections:

1. **What needs to change.** Blockers, each with file and line, why it matters, and the fix.
2. **Nits.** One line each.
3. **Thanks.** Specific credit, what you verified, and the scope line, including what was not authenticated or run end to end. List the promotion preconditions in the scope line.

Scan the draft for sensitive strings. Show the reviewer the draft and wait for an explicit go. Post with `gh pr review $N -R $REPO --body-file <file>` and the flag they chose. Then check that the posted body, state, and commit match the draft.

- Do not pipe `gh pr review` (or any `gh` write) through `grep` or another filter. The shell reports the filter's exit status instead of `gh`'s. `GH_NO_UPDATE_NOTIFIER=1` keeps the output clean without one.
- If a post's result is unclear, list the PR's reviews before trying again, so you don't post twice.

## Reviewing several connector PRs

- List the queue:

  ```bash
  GH_NO_UPDATE_NOTIFIER=1 gh pr list -R aws/tools-for-devops-agent --state open --limit 100 --json number,title,author,isDraft,files --jq '.[] | select([.files[].path] | any(startswith("connectors/"))) | {number, title, author: .author.login, draft: .isDraft}'
  ```

  Review one PR to completion before starting the next, and keep each PR's step 6 summary.
- Compare each connector with those already on `main` (command below). A difference the partner contract does not explain is worth a question, not a blocker.
- After any connector merges, run the cleanup block for the PRs still open and redo steps 2 and 3. Many connector PRs edit `llms.txt`, so they go stale or conflict.
- Before merging, check `main`'s branch protection, which says which checks are required, whether a new push dismisses earlier approvals (including the SME's), and whether conversations must be resolved. Run `gh api repos/aws/tools-for-devops-agent/branches/main/protection` if you have access.
- Fork PR workflow runs wait in `action_required` until a maintainer approves them. Approving them is an action that needs the reviewer's go.

To compare connectors, run this against the trial merge:

```bash
(
. "$HOME/.cache/connector-review/${N:?set N to the PR number}.env" || exit 1
python3 - <<'EOF'
import pathlib, yaml
for p in sorted(pathlib.Path("connectors").glob("*/connector.yaml")):
    d = yaml.safe_load(p.read_text()); m = d.get("mcp") or {}
    auth = ",".join(a.get("type", "?") for a in m.get("auth") or [])
    print(f'{d.get("name", p.parent.name):<18} v{d.get("version", "?"):<7} {d.get("tier", "?"):<16} {auth:<42} endpoints={len(m.get("endpoints") or [m.get("endpoint")])} triggers={"yes" if "triggers" in d else "no"} skills={len(d.get("skills") or [])}')
EOF
)
```

## When you finish

Run this when the review is done, before redoing step 2 for the same PR, or to clear an abandoned review. It is safe to run more than once.

```bash
(
N=${N:?set N to the PR number}; STATE="$HOME/.cache/connector-review/$N.env"
[ -f "$STATE" ] || { echo "no review of #$N in progress"; exit 0; }
REVIEW_STATE_ONLY=1 . "$STATE" || exit 1
git -C "$SRC" worktree remove --force "$WORK/tree" 2>/dev/null; git -C "$SRC" worktree prune
git -C "$SRC" update-ref -d "refs/remotes/origin/pr/$N" 2>/dev/null
rm -rf "$WORK" "$STATE" && echo "cleaned up the review of #$N"
)
```

Leave the reviewer's own branch, working tree, and git config untouched.
