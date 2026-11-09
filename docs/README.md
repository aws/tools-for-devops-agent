# How the documentation site works

The site at [aws.github.io/tools-for-devops-agent](https://aws.github.io/tools-for-devops-agent/) is built with [MkDocs](https://www.mkdocs.org/) and the [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme. GitHub Actions builds it from `main` and publishes it to GitHub Pages. There is no `gh-pages` branch.

This file is not published. `exclude_docs` in `mkdocs.yml` keeps it out of the site. Without that setting, the strict build fails because `README.md` and `index.md` both claim the home page.

## Build and deploy

| Workflow | When it runs | What it does |
|---|---|---|
| [`build-docs.yml`](../.github/workflows/build-docs.yml) | Every pull request, and every push to `main` | Runs `mkdocs build --strict`. It deploys nothing. |
| [`deploy-docs.yml`](../.github/workflows/deploy-docs.yml) | A push to `main` that changes the site sources (see below), or a manual run | Builds the site, uploads the `site/` folder as a Pages artifact and deploys it. |

`deploy-docs.yml` runs only when a push changes one of these paths:

- `docs/**`
- `mkdocs.yml`
- `skills/*/SKILL.md` and `skills/*/README.md`
- `mcp/*/README.md`
- `custom-agents/*/README.md`
- `.github/workflows/deploy-docs.yml`

A change to any other file does not update the site until the next push that matches. To publish without such a change, run the workflow from the Actions tab (`workflow_dispatch`).

Both workflows install `mkdocs-material==9.6.14`. The dependencies of that package are not pinned.

## What is in `docs/`

| Path | Purpose |
|---|---|
| `index.md` | Home page. It uses HTML blocks styled by `stylesheets/extra.css`. |
| `getting-started.md` | Hand-written page. |
| `skills/index.md`, `custom-agents/index.md`, `mcp-servers/index.md` | Catalog pages. Each holds an empty `<div>` that `javascripts/catalog.js` fills with cards. |
| `hooks/*.py` | MkDocs hooks that generate the catalog data and pages at build time. |
| `javascripts/catalog.js` | Reads the generated JSON and renders the catalog cards and group-by buttons. Output is sanitised with DOMPurify, which loads from jsDelivr. |
| `stylesheets/extra.css` | Theme overrides, the home page hero and the catalog card styles. |
| `assets/` | Logo and favicon. |

## Generated content

Most of the site is generated from the tool folders, so a new skill, custom agent or MCP server appears on the site with no change to `docs/`.

`mkdocs.yml` registers three hooks. Each runs in `on_pre_build`:

| Hook | Reads | Writes |
|---|---|---|
| `hooks/skills_catalog.py` | `skills/*/SKILL.md` front matter and `skills/*/README.md` | `javascripts/skills-data.json` and one page per skill at `skills/<name>.md` |
| `hooks/agents_catalog.py` | `custom-agents/*/README.md` | `javascripts/agents-data.json` and `custom-agents/<name>.md` |
| `hooks/mcp_catalog.py` | `mcp/*/README.md` | `javascripts/mcp-data.json` and `mcp-servers/<name>.md` |

Each hook also adds its generated pages under the matching `Catalog` entry in `nav`. It changes the navigation in memory only, so `mkdocs.yml` stays the same.

A generated page is the tool's `README.md` with a "View on GitHub" button and an author and tags block added after the first heading. If there is no `README.md`, the page is built from the skill description.

The generated files are listed in `.gitignore`. Do not commit them. Do not edit them either: the next build overwrites them.

The hooks write a file only when its content changes, so `mkdocs serve` does not rebuild in a loop.

For the rules that control how a tool shows on the site (display names, acronyms, skill tags on agent cards, link formats), see "Common Review Findings" in [CONTRIBUTING.md](../CONTRIBUTING.md) and [`.kiro/steering/project-conventions.md`](../.kiro/steering/project-conventions.md).

## Add a hand-written page

1. Add the Markdown file under `docs/`, for example `docs/my-page.md`.
2. Add it to `nav` in `mkdocs.yml`. With `navigation.tabs` on, a top-level `nav` entry shows as a tab.
3. Link to other pages in `docs/` with relative paths. Link to files outside `docs/` with a full `https://github.com/aws/tools-for-devops-agent/blob/main/...` URL. A relative link to a file outside `docs/` fails the strict build.
4. Build the site locally (see below).

## Build the site locally

```bash
python3 -m venv venv && . venv/bin/activate
python3 -m pip install mkdocs-material==9.6.14
mkdocs build --strict   # same check as CI; output goes to site/
mkdocs serve            # preview at http://127.0.0.1:8000/tools-for-devops-agent/
```

`mkdocs serve` rebuilds when a file under `docs/` changes, but it does not reload a changed hook. After you edit a file in `hooks/`, stop the server and start it again.

`--strict` makes every warning an error. A common cause is a relative link to a file that does not exist or is outside `docs/`.
