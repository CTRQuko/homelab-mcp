#!/bin/bash
cd "$(dirname "$0")/.."
python -m homelab_mcp.docker_mcp.server
