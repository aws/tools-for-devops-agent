#!/bin/sh
set -e
export PYTHONPATH="/opt/python:/var/task"
exec python3 -m mcp_proxy --port=8000 --host=0.0.0.0 --stateless --pass-environment -- python3 server.py
