#!/bin/sh
# Lambda Web Adapter startup script (function Handler). The adapter
# layer's own /opt/bootstrap invokes this via AWS_LAMBDA_EXEC_WRAPPER.
#
# Starts mcp-proxy, a generic stdio<->streamable-HTTP bridge, which spawns
# the standard, unmodified `uvx awslabs.redshift-mcp-server` as its stdio
# backend -- the exact same command as the standard stdio MCP config:
#
#   { "mcpServers": { "awslabs.redshift-mcp-server":
#       { "command": "uvx", "args": ["awslabs.redshift-mcp-server==0.0.29"] } } }
#
# No forked/custom MCP server code ships in this deployment -- the server
# is always pulled from PyPI on cold start.
#
# Pinned to 0.0.29 (not @latest): 0.0.30 added a 7th tool, review_cluster,
# which requires superuser/CREATEUSER privileges and is not documented or
# exercised anywhere in this skill. Pinning keeps the deployed tool surface
# matching what SKILL.md/README.md document (six tools) and avoids an
# unreviewed new tool silently appearing on the next cold start. Bump this
# pin deliberately (and update the docs) if review_cluster is adopted.
set -e

export PYTHONPATH="/var/task"

# pip installs console-script binaries (uv, uvx, mcp-proxy) under a
# "<package>-<version>.data/scripts" directory when using `pip install
# --target`, not a top-level bin/ -- the exact folder name varies by pip
# version and build environment, so locate it dynamically instead of
# hardcoding a path.
for d in /var/task/*.data/scripts; do
  [ -d "$d" ] && export PATH="${d}:${PATH}"
done
export PATH="/var/task/bin:${PATH}"

# uv/uvx cache and home dirs must be writable; /tmp is the only writable
# path in the Lambda execution environment.
export HOME=/tmp
export UV_CACHE_DIR=/tmp/uv-cache
export UV_TOOL_DIR=/tmp/uv-tools
export UV_PYTHON_INSTALL_DIR=/tmp/uv-python

exec python3 -m mcp_proxy --port=8000 --host=0.0.0.0 --stateless --pass-environment -- \
  uvx awslabs.redshift-mcp-server==0.0.29
