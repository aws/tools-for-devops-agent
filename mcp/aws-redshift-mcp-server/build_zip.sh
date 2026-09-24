#!/bin/bash
# Builds the .zip deployment package for the Lambda "proxy" variant.
#
# Installs uv and mcp-proxy targeting manylinux2014_aarch64 / Python 3.13
# wheels directly via `pip install --platform`, with no container runtime
# required. Every dependency in this tree (uv, mcp-proxy, and transitive
# deps like cryptography and pydantic-core) publishes prebuilt manylinux
# wheels for arm64, so this produces the exact same result as building
# inside a Lambda-compatible container -- just without needing Docker or
# Finch installed.
#
# Installs from the SAME requirements.txt as the SAM build path
# (sam-app/src/requirements.txt) so both deployment options resolve
# identical, pinned dependency versions. Do not install uv/mcp-proxy
# unpinned here -- mcp-proxy 0.12.0 imports request_ctx from
# mcp.server.lowlevel.server, which the breaking mcp v2.0.0 release
# removed; an unpinned install would silently resolve mcp==2.0.0 and
# break with an ImportError on Lambda cold start. See requirements.txt
# for the full explanation.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
ZIP_PATH="${SCRIPT_DIR}/redshift-mcp-proxy-lambda.zip"
REQUIREMENTS_FILE="${SCRIPT_DIR}/sam-app/src/requirements.txt"

PYTHON_BIN="$(command -v python3.13 || command -v python3 || command -v python)"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "ERROR: no python3 interpreter found on PATH." >&2
  exit 1
fi

if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
  echo "ERROR: requirements file not found at ${REQUIREMENTS_FILE}" >&2
  exit 1
fi

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

"${PYTHON_BIN}" -m pip install --no-cache-dir \
  --platform manylinux2014_aarch64 \
  --python-version 3.13 \
  --implementation cp \
  --abi cp313 \
  --only-binary=:all: \
  --target "${BUILD_DIR}" \
  -r "${REQUIREMENTS_FILE}"

cat > "${BUILD_DIR}/run.sh" <<'EOF'
#!/bin/sh
# Lambda Web Adapter startup script (set as the function Handler). The
# adapter layer's own /opt/bootstrap invokes this via AWS_LAMBDA_EXEC_WRAPPER.
# Starts mcp-proxy, which spawns the standard, unmodified
# `uvx awslabs.redshift-mcp-server` as its stdio backend -- the same command
# as the standard stdio MCP config. Pinned to 0.0.29 (not @latest) to match
# sam-app/src/run.sh -- see that file's comment for why: 0.0.30+ adds a 7th
# tool (review_cluster) not documented or exercised by this skill.
export PYTHONPATH="/var/task"
# pip installs console-script binaries (uv, uvx, mcp-proxy) under a
# "<package>-<version>.data/scripts" directory when using `pip install
# --target`, not always a top-level bin/ -- the exact folder name varies by
# pip version and build environment, so locate it dynamically instead of
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
EOF
chmod 755 "${BUILD_DIR}/run.sh"

rm -f "${ZIP_PATH}"
(cd "${BUILD_DIR}" && zip -q -r "${ZIP_PATH}" . -x '__pycache__/*' -x '*/__pycache__/*')
echo "Package built:"
ls -la "${ZIP_PATH}"
unzip -l "${ZIP_PATH}" | tail -5
