#!/bin/bash
cd "$(dirname "$0")/.."
python -m homelab_mcp.npm_mcp.server
