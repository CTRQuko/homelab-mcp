#!/bin/bash
cd "$(dirname "$0")/.."
echo "Iniciando todos los MCPs en paralelo..."
python -m homelab_mcp.proxmox_mcp.server &
python -m homelab_mcp.docker_mcp.server &
python -m homelab_mcp.linux_mcp.server &
python -m homelab_mcp.windows_mcp.server &
python -m homelab_mcp.npm_mcp.server &
python -m homelab_mcp.python_mcp.server &
echo "PIDs lanzados. Usa 'kill %1 %2 ...' o Ctrl+C para parar."
wait
