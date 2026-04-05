[![CI](https://github.com/CTRQuko/homelab-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/CTRQuko/homelab-mcp/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

# homelab-mcp

Coleccion de servidores MCP (Model Context Protocol) para gestionar un homelab con Proxmox, Linux, Windows, Docker, npm y Python.

Cada dominio corre como proceso independiente via `stdio`, se integra con Claude Code y cualquier cliente MCP compatible.

## Estructura

```
homelab-mcp/
├── homelab_mcp/
│   ├── config.py               # Configuracion centralizada (.env + multi-nodo)
│   ├── base.py                 # Factory del servidor MCP + logging
│   ├── logging_conf.py         # Setup de logging
│   ├── utils/
│   │   ├── paths.py            # safe_path — sandbox de rutas
│   │   ├── subprocess_safe.py  # run_safe — ejecucion con whitelist
│   │   ├── responses.py        # ok() / error() / needs_confirmation()
│   │   └── claude_md_parser.py # Extrae config Proxmox de CLAUDE.md
│   ├── proxmox_mcp/server.py   # Multi-nodo (pve, pve2, pve3...)
│   ├── linux_mcp/server.py
│   ├── windows_mcp/server.py
│   ├── docker_mcp/server.py
│   ├── npm_mcp/server.py
│   └── python_mcp/server.py
├── bin/
│   └── auto-config-from-claude.sh  # Genera .env + proxmox_nodes.json
├── scripts/                    # Lanzadores individuales y paralelo
├── tests/
├── .env.example
└── pyproject.toml
```

## Instalacion

```bash
git clone https://github.com/CTRQuko/homelab-mcp.git
cd homelab-mcp
cp .env.example .env   # edita los valores reales
pip install -e .
# Con herramientas de desarrollo:
pip install -e ".[dev]"
# Solo tests:
pip install -e ".[test]"
```

## Auto-config desde CLAUDE.md

Si ya tienes configuracion Proxmox en `~/.claude/CLAUDE.md` y tokens en un fichero de secrets:

```bash
bash bin/auto-config-from-claude.sh
```

Esto genera automaticamente:
- `.env` con el nodo primario y todas las variables
- `proxmox_nodes.json` con todos los nodos detectados

Solo necesitas verificar que los valores son correctos.

## Variables de entorno (.env)

```env
# Proxmox API token (nodo primario)
PROXMOX_HOST=192.168.1.X
PROXMOX_USER=user@pam
PROXMOX_TOKEN_NAME=my-token
PROXMOX_TOKEN_VALUE=REEMPLAZAR

# Multi-nodo (opcional): fichero JSON con todos los nodos
# Generado por: bash bin/auto-config-from-claude.sh
# PROXMOX_NODES_FILE=proxmox_nodes.json

# Sandbox Linux (read/write dentro de esta ruta)
LINUX_BASE_PATH=/srv/homelab

# Sandbox Windows
WINDOWS_BASE_PATH=C:/homelab

# npm / Python sandboxes
NPM_BASE_PATH=.
PYTHON_BASE_PATH=.

# Docker socket (opcional)
DOCKER_HOST=unix:///var/run/docker.sock

# Nivel de log: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

### Multi-nodo Proxmox

Con `PROXMOX_NODES_FILE=proxmox_nodes.json`, los tools de Proxmox aceptan alias de nodo:
- `list_lxc("node1")` → conecta al primer nodo
- `list_lxc("node2")` → conecta al segundo nodo
- `list_lxc("node3")` → conecta al tercer nodo

Sin el fichero JSON, todo usa el nodo unico de `PROXMOX_HOST`.

## Ejecucion manual

```bash
homelab-proxmox-mcp
homelab-linux-mcp
homelab-windows-mcp
homelab-docker-mcp
homelab-npm-mcp
homelab-python-mcp
```

## Integracion en mcp.json

```json
{
  "mcpServers": {
    "homelab-proxmox": {
      "command": "homelab-proxmox-mcp",
      "args": []
    },
    "homelab-linux": {
      "command": "homelab-linux-mcp",
      "args": []
    },
    "homelab-windows": {
      "command": "homelab-windows-mcp",
      "args": []
    },
    "homelab-docker": {
      "command": "homelab-docker-mcp",
      "args": []
    },
    "homelab-npm": {
      "command": "homelab-npm-mcp",
      "args": []
    },
    "homelab-python": {
      "command": "homelab-python-mcp",
      "args": []
    }
  }
}
```

## Tools disponibles

### Proxmox MCP
| Tool | Descripcion |
|------|-------------|
| `list_nodes()` | Lista nodos del cluster |
| `get_node_status(node)` | CPU, memoria, uptime del nodo |
| `list_qemu(node)` | VMs QEMU/KVM del nodo |
| `list_lxc(node)` | Contenedores LXC del nodo |
| `get_vm_status(node, vmid, vm_type)` | Estado de VM o LXC |
| `start_vm(node, vmid, vm_type, confirm)` | Arrancar VM/LXC (requiere `confirm=True`) |
| `stop_vm(node, vmid, vm_type, confirm)` | Parar VM/LXC (requiere `confirm=True`) |
| `restart_vm(node, vmid, vm_type, confirm)` | Reiniciar VM/LXC (requiere `confirm=True`) |

### Linux MCP
| Tool | Descripcion |
|------|-------------|
| `read_file(rel_path)` | Leer fichero dentro del sandbox |
| `write_file(rel_path, content)` | Escribir fichero dentro del sandbox |
| `list_dir(rel_path)` | Listar directorio |
| `file_exists(rel_path)` | Comprobar existencia |
| `run_command(cmd)` | Comando whitelisted (ls, cat, df, du, grep, find, head, tail...) |

### Windows MCP
| Tool | Descripcion |
|------|-------------|
| `read_file(rel_path)` | Leer fichero dentro del sandbox |
| `write_file(rel_path, content)` | Escribir fichero dentro del sandbox |
| `list_dir(rel_path)` | Listar directorio |
| `file_exists(rel_path)` | Comprobar existencia |
| `run_powershell(cmd)` | PS de solo lectura (Get-*, Test-Path...) |

### Docker MCP
| Tool | Descripcion |
|------|-------------|
| `list_containers(all)` | Listar contenedores |
| `inspect_container(name)` | Inspeccionar configuracion |
| `get_container_logs(name, tail)` | Ultimas N lineas de logs |
| `restart_container(name, confirm)` | Reiniciar contenedor (requiere `confirm=True`) |

### npm MCP
| Tool | Descripcion |
|------|-------------|
| `npm_outdated(path)` | Dependencias desactualizadas |
| `npm_audit(path)` | Vulnerabilidades |
| `npm_list(path)` | Arbol de dependencias |

### Python MCP
| Tool | Descripcion |
|------|-------------|
| `python_version()` | Version Python del servidor |
| `pytest_run(path)` | Ejecutar tests |
| `ruff_check(path)` | Linting con ruff |
| `pip_list()` | Paquetes instalados |

## Tests

```bash
pytest
```

83 tests cubriendo todos los MCPs, utilidades y configuracion.

## Seguridad

### Sandboxes por MCP

| MCP | Variable .env | Default | Aplicado en |
|-----|---------------|---------|-------------|
| Linux | `LINUX_BASE_PATH` | `/srv/homelab` | `read_file`, `write_file`, `list_dir`, `file_exists`, `run_command` |
| Windows | `WINDOWS_BASE_PATH` | `C:/homelab` | `read_file`, `write_file`, `list_dir`, `file_exists`, `run_powershell` |
| npm | `NPM_BASE_PATH` | `.` | `npm_outdated`, `npm_audit`, `npm_list` |
| Python | `PYTHON_BASE_PATH` | `.` | `pytest_run`, `ruff_check` |
| Docker | — | — | No aplica (trabaja con nombres de contenedores) |
| Proxmox | — | — | No aplica (trabaja con la API autenticada) |

### Medidas de seguridad

- **Sandbox de rutas**: Linux, Windows, npm y Python MCP validan que todas las rutas se resuelvan dentro del directorio base configurado. Path traversal (`../..`) es rechazado usando `Path.relative_to()`.
- **Whitelist de comandos**: `run_command` (Linux) solo permite binarios explicitamente listados. Los comandos se parsean con `shlex` y se ejecutan sin `shell=True`.
- **PowerShell restringido**: Solo verbos de lectura (`Get-*`, `Test-Path`). Se bloquean pipes (`|`), punto y coma (`;`), ampersand (`&`), backticks, subexpresiones (`$()`), verbos destructivos (`Remove-*`, `Set-*`, `Invoke-*`, etc.) y binarios peligrosos (`rm`, `del`, `cmd`, etc.). Se ejecuta con `-ExecutionPolicy Restricted -NonInteractive`.
- **Docker con confirmacion**: `restart_container` requiere `confirm=True` explicito. Sin el devuelve un aviso de confirmacion.
- **Proxmox con confirmacion**: `start_vm`, `stop_vm` y `restart_vm` requieren `confirm=True` explicito. Se valida configuracion antes de conectar.
- **Sin secretos hardcodeados**: Todo por `.env`, nunca en el codigo.

### Limitaciones conocidas

- `run_safe` no soporta rutas absolutas con espacios como nombre de binario (e.g. `C:\Program Files\...`). Esto es intencional: usa nombres simples (`python`, `ls`).
- `run_powershell` pasa el comando como string a `-Command`; la validacion cubre la mayoria de vectores pero un escape creativo de PowerShell podria evadirla en teoria.
- No hay autenticacion entre el cliente MCP y el servidor; la seguridad recae en el control de acceso al proceso.

## Ejemplo mcp.json alternativo (con python -m)

Si prefieres invocar los servidores con `python -m` en lugar del entrypoint:

```json
{
  "mcpServers": {
    "proxmox": {
      "command": "python",
      "args": ["-m", "homelab_mcp.proxmox_mcp.server"],
      "env": { "PYTHONPATH": "/path/to/homelab-mcp" },
      "type": "stdio"
    },
    "linux": {
      "command": "python",
      "args": ["-m", "homelab_mcp.linux_mcp.server"],
      "env": { "PYTHONPATH": "/path/to/homelab-mcp" },
      "type": "stdio"
    },
    "docker": {
      "command": "python",
      "args": ["-m", "homelab_mcp.docker_mcp.server"],
      "env": { "PYTHONPATH": "/path/to/homelab-mcp" },
      "type": "stdio"
    },
    "windows": {
      "command": "python",
      "args": ["-m", "homelab_mcp.windows_mcp.server"],
      "env": { "PYTHONPATH": "/path/to/homelab-mcp" },
      "type": "stdio"
    },
    "npm": {
      "command": "python",
      "args": ["-m", "homelab_mcp.npm_mcp.server"],
      "env": { "PYTHONPATH": "/path/to/homelab-mcp" },
      "type": "stdio"
    },
    "python": {
      "command": "python",
      "args": ["-m", "homelab_mcp.python_mcp.server"],
      "env": { "PYTHONPATH": "/path/to/homelab-mcp" },
      "type": "stdio"
    }
  }
}
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
