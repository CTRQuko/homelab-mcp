#!/bin/bash
cd "$(dirname "$0")/.."
python -m homelab_mcp.proxmox_mcp.server
