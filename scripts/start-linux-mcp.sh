#!/bin/bash
cd "$(dirname "$0")/.."
python -m homelab_mcp.linux_mcp.server
