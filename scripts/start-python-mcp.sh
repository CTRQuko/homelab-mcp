#!/bin/bash
cd "$(dirname "$0")/.."
python -m homelab_mcp.python_mcp.server
