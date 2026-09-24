"""
MkDocs hook: generates the MCP servers catalog data from README files.

At build time, scans mcp/*/README.md, extracts metadata, and writes
docs/javascripts/mcp-data.json. The JS on the catalog page reads this
JSON to render cards dynamically.

This also generates individual MCP server doc stubs if a docs/mcp-servers/<name>.md
doesn't already exist, so new servers appear on the site automatically.
"""

import json
import re
from pathlib import Path


def on_pre_build(config, **kwargs):
    """Generate mcp-data.json and MCP server doc stubs before the build."""
    config_dir = config["docs_dir"].replace("/docs", "")
    catalog = _build_mcp_catalog(config_dir)

    # Write JSON for the JS to consume (only if changed, to avoid dev-server loop)
    js_dir = Path(config["docs_dir"]) / "javascripts"
    js_dir.mkdir(parents=True, exist_ok=True)
    data_path = js_dir / "mcp-data.json"
    new_content = json.dumps(catalog, indent=2)
    if data_path.is_file() and data_path.read_text(encoding="utf-8") == new_content:
        pass  # No change, skip write to avoid triggering file watcher
    else:
        data_path.write_text(new_content, encoding="utf-8")

    # Generate stub pages for MCP servers that don't have a docs page yet
    mcp_docs_dir = Path(config["docs_dir"]) / "mcp-servers"
    mcp_docs_dir.mkdir(parents=True, exist_ok=True)

    for server in catalog:
        doc_path = mcp_docs_dir / f"{server['id']}.md"
        _generate_mcp_stub(doc_path, server, config_dir)

    # Inject MCP server pages into nav in memory
    _update_nav(config, catalog)


def _build_mcp_catalog(config_dir: str) -> list:
    """Scan all MCP servers and build catalog entries."""
    mcp_dir = Path(config_dir) / "mcp"
    catalog = []

    if not mcp_dir.is_dir():
        return catalog

    for server_path in sorted(mcp_dir.iterdir()):
        if not server_path.is_dir():
            continue

        readme = server_path / "README.md"
        if not readme.is_file():
            continue

        readme_text = readme.read_text(encoding="utf-8")
        lines = readme_text.split("\n")

        # Extract title from first heading
        name = _format_name(server_path.name)
        for line in lines:
            if line.startswith("# "):
                raw_title = line[2:].strip()
                # Strip common suffixes like " — MCP", " - MCP Server", etc.
                raw_title = re.sub(
                    r'\s*[—–-]\s*MCP\s*(Server)?\s*$', '', raw_title, flags=re.IGNORECASE
                )
                name = raw_title
                break

        # Extract description: first non-blockquote paragraph after the title
        description = _extract_first_paragraph(lines)

        # Convert markdown links/bold to HTML for card rendering
        description = re.sub(
            r'\[([^\]]+)\]\(([^)]+)\)',
            r'<a href="\2" target="_blank" rel="noopener">\1</a>',
            description
        )
        description = re.sub(
            r'\*\*([^*]+)\*\*',
            r'<strong>\1</strong>',
            description
        )

        catalog.append({
            "id": server_path.name,
            "name": name,
            "description": description,
        })

    return catalog


def _extract_first_paragraph(lines: list) -> str:
    """Extract the first non-blockquote paragraph after the title heading."""
    past_title = False
    paragraph_lines = []

    for line in lines:
        if line.startswith("# "):
            past_title = True
            continue

        if not past_title:
            continue

        # Skip blockquote lines
        if line.startswith(">"):
            # If we were accumulating a paragraph, stop (shouldn't happen
            # since blockquotes come before the description)
            if paragraph_lines:
                break
            continue

        # Skip blank lines (before we start accumulating)
        if not line.strip():
            if paragraph_lines:
                break  # End of the paragraph
            continue

        # Skip sub-headings
        if line.startswith("#"):
            if paragraph_lines:
                break
            continue

        paragraph_lines.append(line.strip())

    return " ".join(paragraph_lines)


def _format_name(server_id: str) -> str:
    """Convert server-id to display name: aws-eks-node-diagnostics-mcp -> AWS EKS Node Diagnostics MCP."""
    words = server_id.split("-")
    acronyms = {"aws", "eks", "rds", "rca", "mcp", "crm", "vpc", "dns"}
    return " ".join(
        w.upper() if w.lower() in acronyms else w.capitalize()
        for w in words
    )


def _generate_mcp_stub(doc_path: Path, server: dict, config_dir: str):
    """Generate an MCP server doc page from its README (only if changed)."""
    repo_url = "https://github.com/aws/tools-for-devops-agent"
    github_link = (
        f'<a href="{repo_url}/tree/main/mcp/{server["id"]}" '
        f'target="_blank" rel="noopener" class="md-button">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" width="16" height="16" '
        f'style="vertical-align: text-bottom; margin-right: 0.3rem;">'
        f'<path fill="currentColor" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59'
        f'.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48'
        f'-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33'
        f'.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2'
        f'-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 '
        f'1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07'
        f'-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55'
        f'.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'
        f'View on GitHub</a>\n\n'
    )

    readme = Path(config_dir) / "mcp" / server["id"] / "README.md"
    if readme.is_file():
        readme_content = readme.read_text(encoding="utf-8")
        # Insert the GitHub link after the first heading
        lines = readme_content.split("\n", 1)
        if len(lines) == 2 and lines[0].startswith("# "):
            content = lines[0] + "\n\n" + github_link + lines[1]
        else:
            content = github_link + readme_content
    else:
        content = f"# {server['name']}\n\n{github_link}{server['description']}\n"

    # Rewrite relative markdown links to absolute GitHub URLs so that
    # mkdocs --strict does not fail on unresolvable paths like
    # docs/ARCHITECTURE.md or LICENSE.
    base = f"{repo_url}/blob/main/mcp/{server['id']}/"
    content = re.sub(
        r'\[([^\]]+)\]\((?!https?://|#|\.\./)([^)]+)\)',
        lambda m: f'[{m.group(1)}]({base}{m.group(2).lstrip("./")})' ,
        content,
    )

    if doc_path.is_file() and doc_path.read_text(encoding="utf-8") == content:
        return  # No change, skip write
    doc_path.write_text(content, encoding="utf-8")


def _update_nav(config, catalog):
    """Inject MCP server pages into the nav in memory.

    Looks for MCP Servers > Catalog section and appends server pages there.
    """
    nav = config.get("nav")
    if not nav:
        return

    for item in nav:
        if isinstance(item, dict) and "MCP Servers" in item:
            mcp_nav = item["MCP Servers"]

            for entry in mcp_nav:
                if isinstance(entry, dict) and "Catalog" in entry:
                    catalog_nav = entry["Catalog"]

                    # Collect existing paths
                    existing_paths = set()
                    for sub in catalog_nav:
                        if isinstance(sub, dict):
                            for path in sub.values():
                                existing_paths.add(path)
                        elif isinstance(sub, str):
                            existing_paths.add(sub)

                    # Add MCP server pages
                    for server in catalog:
                        page_path = f"mcp-servers/{server['id']}.md"
                        if page_path not in existing_paths:
                            catalog_nav.append({server["name"]: page_path})
                    break
            break
