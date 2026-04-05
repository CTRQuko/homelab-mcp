#!/bin/bash
# Auto-configura .env y proxmox_nodes.json desde CLAUDE.md + apispve.md
set -e
cd "$(dirname "$0")/.."

CLAUDE_MD="$HOME/.claude/CLAUDE.md"
SECRETS="C:/homelab/.config/secrets/apispve.md"

echo "=== Auto-config homelab-mcp desde CLAUDE.md ==="

if [ ! -f "$CLAUDE_MD" ]; then
    echo "ERROR: No se encontró $CLAUDE_MD"
    exit 1
fi

echo "1. Leyendo CLAUDE.md..."
python -c "
from homelab_mcp.utils.claude_md_parser import build_proxmox_config
from pathlib import Path

claude_md = Path.home() / '.claude' / 'CLAUDE.md'
secrets = Path('C:/homelab/.config/secrets/apispve.md')
config = build_proxmox_config(claude_md, secrets if secrets.exists() else None)

print('   Nodos encontrados:')
for alias, node in config['nodes'].items():
    has_token = 'OK' if node['token_value'] else 'SIN TOKEN'
    print(f'     {alias}: {node[\"host\"]} ({node[\"endpoint_node\"]}) [{has_token}]')

primary = config.get('primary')
if primary:
    print(f'   Primario: {primary[\"alias\"]} ({primary[\"host\"]})')
"

echo ""
echo "2. Generando proxmox_nodes.json..."
python -c "
from homelab_mcp.utils.claude_md_parser import generate_nodes_json
from pathlib import Path

claude_md = Path.home() / '.claude' / 'CLAUDE.md'
secrets = Path('C:/homelab/.config/secrets/apispve.md')
content = generate_nodes_json(claude_md, secrets if secrets.exists() else None)
Path('proxmox_nodes.json').write_text(content, encoding='utf-8')
print('   proxmox_nodes.json creado')
"

echo ""
echo "3. Generando .env..."
if [ -f .env ]; then
    cp .env .env.bak
    echo "   .env.bak creado (backup del anterior)"
fi

python -c "
from homelab_mcp.utils.claude_md_parser import generate_env_content
from pathlib import Path

claude_md = Path.home() / '.claude' / 'CLAUDE.md'
secrets = Path('C:/homelab/.config/secrets/apispve.md')
content = generate_env_content(claude_md, secrets if secrets.exists() else None)
Path('.env').write_text(content, encoding='utf-8')
print('   .env generado')
"

echo ""
echo "=== Listo ==="
echo "Verifica .env y proxmox_nodes.json antes de usar."
echo "Test rápido: python -m homelab_mcp.utils.claude_md_parser"
