"""Extrae configuración Proxmox de CLAUDE.md y apispve.md."""
import json
import re
from pathlib import Path


def extract_proxmox_nodes(claude_md: str | Path) -> list[dict]:
    """Extrae nodos Proxmox de la tabla en CLAUDE.md.

    Busca la tabla de Capa 1 API Proxmox con formato:
    | Nodo | IP:Puerto | Token ID | Endpoint node | Estado |

    Returns:
        Lista de dicts con keys: alias, host, port, token_id, endpoint_node, estado.
    """
    if isinstance(claude_md, (str, Path)) and Path(claude_md).exists():
        content = Path(claude_md).read_text(encoding="utf-8", errors="replace")
    elif isinstance(claude_md, str):
        content = claude_md
    else:
        return []

    nodes = []

    # Patrón para filas de tabla Markdown con IP:Puerto
    # | pve | `10.0.0.1:8006` | `user@pam!my-token` | `node1` | OK |
    row_pattern = re.compile(
        r'\|\s*(\w+)\s*\|'             # alias (pve, pve2, pve3...)
        r'\s*`?(\d+\.\d+\.\d+\.\d+)'  # IP
        r':(\d+)`?\s*\|'               # Puerto
        r'\s*`?([^`|]+?)`?\s*\|'       # Token ID
        r'\s*`?([^`|]+?)`?\s*\|'       # Endpoint node
        r'\s*(\w+)\s*\|'               # Estado
    )

    for m in row_pattern.finditer(content):
        alias, ip, port, token_id, endpoint_node, estado = m.groups()
        token_id = token_id.strip()
        endpoint_node = endpoint_node.strip().rstrip('`')

        # Saltar nodos offline o headers
        if estado.lower() in ("offline", "estado"):
            continue
        if not token_id or token_id == "—":
            continue

        # Separar user y token_name del token_id (e.g. "user@pam!my-token")
        user, token_name = "", ""
        if "!" in token_id:
            user, token_name = token_id.rsplit("!", 1)

        nodes.append({
            "alias": alias,
            "host": ip,
            "port": int(port),
            "user": user,
            "token_name": token_name,
            "token_id": token_id,
            "endpoint_node": endpoint_node,
            "estado": estado,
        })

    return nodes


def extract_token_values(secrets_file: str | Path) -> list[dict]:
    """Extrae valores de token de apispve.md.

    Formato esperado: bloques separados por líneas vacías:
        label
        <vacía>
        token_id
        token_value

    Returns:
        Lista de dicts con keys: label, token_id, token_value.
        Ordenados como aparecen en el fichero.
    """
    path = Path(secrets_file)
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8", errors="replace")
    entries = []

    uuid_pattern = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
    token_id_pattern = re.compile(r'(\S+@\S+!\S+)')

    lines = [l.strip() for l in content.splitlines()]
    i = 0
    current_label = ""
    while i < len(lines):
        line = lines[i]
        tid_match = token_id_pattern.match(line)
        if tid_match:
            tid = tid_match.group(1)
            # Siguiente línea no vacía debería ser el UUID
            j = i + 1
            while j < len(lines) and not lines[j]:
                j += 1
            if j < len(lines) and uuid_pattern.match(lines[j]):
                entries.append({
                    "label": current_label,
                    "token_id": tid,
                    "token_value": lines[j],
                })
        elif line and not uuid_pattern.match(line):
            # Línea no vacía que no es UUID ni token_id = label
            current_label = line
        i += 1

    return entries


def build_proxmox_config(
    claude_md: str | Path,
    secrets_file: str | Path | None = None,
) -> dict:
    """Combina nodos de CLAUDE.md con tokens de apispve.md.

    Returns:
        Dict con estructura:
        {
            "primary": { ... config del primer nodo OK ... },
            "nodes": {
                "pve": { "host", "user", "token_name", "token_value", "endpoint_node" },
                "pve2": { ... },
                ...
            }
        }
    """
    nodes_raw = extract_proxmox_nodes(claude_md)
    token_entries = []
    if secrets_file:
        token_entries = extract_token_values(secrets_file)

    # Match tokens a nodos por label fuzzy (e.g. "pve-logrono" → "pve", "pve 3" → "pve3")
    def _match_label_to_alias(label: str, aliases: list[str]) -> str | None:
        label_clean = label.lower().replace(" ", "").replace("-", "")
        # Ordenar aliases más largos primero para evitar que "pve" matchee antes que "pve2"
        sorted_aliases = sorted(aliases, key=len, reverse=True)
        for alias in sorted_aliases:
            alias_clean = alias.lower().replace(" ", "").replace("-", "")
            if alias_clean in label_clean or label_clean.startswith(alias_clean):
                return alias
        return None

    aliases = [n["alias"] for n in nodes_raw]
    # Build token map: alias → token_value
    token_by_alias: dict[str, str] = {}
    for entry in token_entries:
        matched = _match_label_to_alias(entry["label"], aliases)
        if matched:
            token_by_alias[matched] = entry["token_value"]

    # Fallback: si no hubo match por label, asignar por token_id en orden
    unmatched_nodes = [n for n in nodes_raw if n["alias"] not in token_by_alias]
    unmatched_tokens = [e for e in token_entries
                        if _match_label_to_alias(e["label"], aliases) is None]
    for node, entry in zip(unmatched_nodes, unmatched_tokens):
        if node["token_id"] == entry["token_id"]:
            token_by_alias[node["alias"]] = entry["token_value"]

    nodes = {}
    primary = None

    for n in nodes_raw:
        token_value = token_by_alias.get(n["alias"], "")
        node_config = {
            "host": n["host"],
            "user": n["user"],
            "token_name": n["token_name"],
            "token_value": token_value,
            "endpoint_node": n["endpoint_node"],
        }
        nodes[n["alias"]] = node_config
        if primary is None:
            primary = node_config.copy()
            primary["alias"] = n["alias"]

    return {
        "primary": primary,
        "nodes": nodes,
    }


def generate_env_content(
    claude_md: str | Path,
    secrets_file: str | Path | None = None,
) -> str:
    """Genera contenido .env a partir de CLAUDE.md.

    Returns:
        String con el contenido del .env listo para escribir.
    """
    config = build_proxmox_config(claude_md, secrets_file)
    primary = config.get("primary") or {}
    nodes = config.get("nodes", {})

    lines = [
        "# === PROXMOX MCP (generado desde CLAUDE.md) ===",
        f"PROXMOX_HOST={primary.get('host', '')}",
        f"PROXMOX_USER={primary.get('user', '')}",
        f"PROXMOX_TOKEN_NAME={primary.get('token_name', '')}",
        f"PROXMOX_TOKEN_VALUE={primary.get('token_value', 'REEMPLAZAR')}",
        "",
        "# Multi-nodo: fichero JSON con todos los nodos Proxmox",
        "PROXMOX_NODES_FILE=proxmox_nodes.json",
        "",
        "# LINUX MCP",
        "LINUX_BASE_PATH=/srv/homelab",
        "",
        "# WINDOWS MCP",
        "WINDOWS_BASE_PATH=C:/homelab",
        "",
        "# NPM MCP",
        "NPM_BASE_PATH=.",
        "",
        "# PYTHON MCP",
        "PYTHON_BASE_PATH=.",
        "",
        "# DOCKER MCP",
        "DOCKER_HOST=unix:///var/run/docker.sock",
        "",
        "# LOG LEVEL",
        "LOG_LEVEL=INFO",
    ]
    return "\n".join(lines) + "\n"


def generate_nodes_json(
    claude_md: str | Path,
    secrets_file: str | Path | None = None,
) -> str:
    """Genera proxmox_nodes.json con todos los nodos.

    Returns:
        JSON string formateado.
    """
    config = build_proxmox_config(claude_md, secrets_file)
    return json.dumps(config["nodes"], indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Ejecutable para auto-config desde CLAUDE.md."""
    import sys

    claude_md = Path.home() / ".claude" / "CLAUDE.md"
    secrets = Path("C:/homelab/.config/secrets/apispve.md")

    if not claude_md.exists():
        print(f"ERROR: No se encontró {claude_md}", file=sys.stderr)
        sys.exit(1)

    config = build_proxmox_config(claude_md, secrets if secrets.exists() else None)

    print("=== Nodos Proxmox extraídos de CLAUDE.md ===")
    for alias, node in config["nodes"].items():
        has_token = "OK" if node["token_value"] else "SIN TOKEN"
        print(f"  {alias}: {node['host']} ({node['endpoint_node']}) [{has_token}]")

    primary = config.get("primary")
    if primary:
        print(f"\nPrimario: {primary['alias']} ({primary['host']})")
    else:
        print("\nWARNING: No se encontraron nodos Proxmox en CLAUDE.md")


if __name__ == "__main__":
    main()
