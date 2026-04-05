#!/bin/bash
# Auto-configura .env y proxmox_nodes.json desde CLAUDE.md + apispve.md
# Compatible con Linux, WSL, Git Bash y bash en Windows
set -e
cd "$(dirname "$0")/.."

# --- Detectar CLAUDE.md ---
# Orden de búsqueda:
# 1. Variable de entorno CLAUDE_MD (override manual)
# 2. ~/.claude/CLAUDE.md (Linux nativo / WSL con home Linux)
# 3. /mnt/c/Users/$WIN_USER/.claude/CLAUDE.md (WSL accediendo a Windows)
# 4. Simlink o fichero en el directorio actual

detect_claude_md() {
    # Override manual
    if [ -n "${CLAUDE_MD:-}" ] && [ -f "$CLAUDE_MD" ]; then
        echo "$CLAUDE_MD"; return
    fi

    # Ruta estándar Linux/Mac/WSL-home
    if [ -f "$HOME/.claude/CLAUDE.md" ]; then
        echo "$HOME/.claude/CLAUDE.md"; return
    fi

    # WSL: buscar en el home Windows real
    if grep -qi microsoft /proc/version 2>/dev/null; then
        WIN_USER=$(powershell.exe -NoProfile -Command '$env:USERNAME' 2>/dev/null | tr -d '\r')
        WSL_WIN_HOME="/mnt/c/Users/$WIN_USER"
        if [ -n "$WIN_USER" ] && [ -f "$WSL_WIN_HOME/.claude/CLAUDE.md" ]; then
            echo "$WSL_WIN_HOME/.claude/CLAUDE.md"; return
        fi
        # Puede ser symlink a otro sitio — seguirlo
        LINK_TARGET=$(readlink -f "$WSL_WIN_HOME/.claude/CLAUDE.md" 2>/dev/null || true)
        if [ -n "$LINK_TARGET" ] && [ -f "$LINK_TARGET" ]; then
            echo "$LINK_TARGET"; return
        fi
    fi

    echo ""
}

detect_secrets() {
    # Override manual
    if [ -n "${SECRETS_FILE:-}" ] && [ -f "$SECRETS_FILE" ]; then
        echo "$SECRETS_FILE"; return
    fi

    # Buscar apispve.md relativo al CLAUDE.md encontrado
    local claude_dir
    claude_dir=$(dirname "$(readlink -f "$1" 2>/dev/null || echo "$1")")
    
    # Posibles ubicaciones relativas al directorio del CLAUDE.md
    for candidate in \
        "$claude_dir/.config/secrets/apispve.md" \
        "$claude_dir/../.config/secrets/apispve.md" \
        "$(dirname "$claude_dir")/.config/secrets/apispve.md";
    do
        if [ -f "$candidate" ]; then
            echo "$(realpath "$candidate" 2>/dev/null || echo "$candidate")"; return
        fi
    done

    echo ""
}

CLAUDE_MD=$(detect_claude_md)

if [ -z "$CLAUDE_MD" ]; then
    echo "ERROR: No se encontró CLAUDE.md."
    echo "Pasa la ruta manualmente:"
    echo "  CLAUDE_MD=/ruta/CLAUDE.md bash bin/auto-config-from-claude.sh"
    exit 1
fi

SECRETS=$(detect_secrets "$CLAUDE_MD")

echo "=== Auto-config homelab-mcp desde CLAUDE.md ==="
echo "   CLAUDE.md : $CLAUDE_MD"
echo "   Secrets   : ${SECRETS:-'(no encontrado, tokens vacíos)'}"
echo ""

echo "1. Leyendo nodos Proxmox..."
python -c "
from homelab_mcp.utils.claude_md_parser import build_proxmox_config
from pathlib import Path
import sys

claude_md = Path(sys.argv[1])
secrets = Path(sys.argv[2]) if sys.argv[2] else None

config = build_proxmox_config(claude_md, secrets)

if not config['nodes']:
    print('   WARNING: No se encontraron nodos Proxmox en CLAUDE.md', file=sys.stderr)
else:
    print(f'   {len(config[\"nodes\"])} nodo(s) encontrado(s):')
    for alias, node in config['nodes'].items():
        has_token = 'OK' if node['token_value'] else 'SIN TOKEN'
        print(f'     {alias}: {node[\"host\"]} ({node[\"endpoint_node\"]}) [{has_token}]')

primary = config.get('primary')
if primary:
    print(f'   Primario: {primary[\"alias\"]} ({primary[\"host\"]})')
" "$CLAUDE_MD" "$SECRETS"

echo ""
echo "2. Generando proxmox_nodes.json..."
python -c "
from homelab_mcp.utils.claude_md_parser import generate_nodes_json
from pathlib import Path
import sys

claude_md = Path(sys.argv[1])
secrets = Path(sys.argv[2]) if sys.argv[2] else None
content = generate_nodes_json(claude_md, secrets)
Path('proxmox_nodes.json').write_text(content, encoding='utf-8')
print('   proxmox_nodes.json creado')
" "$CLAUDE_MD" "$SECRETS"

echo ""
echo "3. Generando .env..."
if [ -f .env ]; then
    cp .env .env.bak
    echo "   .env.bak creado (backup)"
fi

python -c "
from homelab_mcp.utils.claude_md_parser import generate_env_content
from pathlib import Path
import sys

claude_md = Path(sys.argv[1])
secrets = Path(sys.argv[2]) if sys.argv[2] else None
content = generate_env_content(claude_md, secrets)
Path('.env').write_text(content, encoding='utf-8')
print('   .env generado')
" "$CLAUDE_MD" "$SECRETS"

echo ""
echo "=== Listo ==="
echo "Verifica con:"
echo "  cat .env"
echo "  cat proxmox_nodes.json"
