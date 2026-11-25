#!/bin/bash
# Lambda Web Adapter entrypoint: serve the FastMCP app over streamable HTTP.
# A directly-exec'd python does not inherit the Lambda runtime's sys.path,
# so the dependency layer (/opt/python) and the function code (/var/task)
# must be added explicitly.
export PYTHONPATH="/opt/python:/var/task:${PYTHONPATH:-}"
exec python -m uvicorn --host 0.0.0.0 --port "${PORT:-8000}" server:handler
