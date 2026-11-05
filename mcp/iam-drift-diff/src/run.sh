#!/bin/bash
# Lambda Web Adapter entry point.
# Starts the FastMCP server on the port the Lambda Web Adapter expects.
# Dependencies (fastmcp, boto3) are provided by the dependencies layer at
# /opt/python; the app code (iam_drift package) is in /var/task.
export PYTHONPATH="/opt/python:/var/task:${PYTHONPATH}"
cd /var/task
exec python3 server.py
