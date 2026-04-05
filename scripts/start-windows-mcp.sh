#!/bin/bash
cd "$(dirname "$0")/.."
python -m homelab_mcp.windows_mcp.server
