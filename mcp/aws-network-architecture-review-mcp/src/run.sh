#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# Lambda Web Adapter entry point.
# Starts the FastMCP server on the port expected by LWA (AWS_LWA_PORT).
export PYTHONPATH="/opt/python:${PYTHONPATH}"
export MCP_HOST="127.0.0.1"
cd /var/task
exec python3 server.py
