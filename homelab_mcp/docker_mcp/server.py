"""Docker MCP — inspección y control básico de contenedores."""
import logging
from functools import lru_cache

import docker
import docker.errors

from homelab_mcp.base import create_server
from homelab_mcp.utils.responses import error, needs_confirmation, ok

log = logging.getLogger(__name__)
mcp = create_server("homelab-docker")


def _get_client() -> docker.DockerClient:
    """Crea cliente Docker. Lanza RuntimeError si Docker no está disponible."""
    try:
        client = docker.from_env()
        client.ping()
        return client
    except docker.errors.DockerException as e:
        raise RuntimeError(f"Docker no disponible: {e}") from e


def _call(fn):
    try:
        return ok(fn())
    except RuntimeError as e:
        return error(str(e))
    except docker.errors.NotFound as e:
        return error("Contenedor no encontrado", str(e))
    except docker.errors.APIError as e:
        log.warning("Docker API error: %s", e)
        return error("Docker API error", str(e))
    except Exception as e:
        log.error("Error inesperado Docker: %s", e)
        return error("Error inesperado", str(e))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_containers(all: bool = False) -> dict:
    """Lista contenedores Docker.

    Args:
        all: Si True incluye contenedores parados. Por defecto solo running.
    """
    def _fetch():
        client = _get_client()
        return [
            {
                "id": c.id[:12],
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else c.image.id[:12],
            }
            for c in client.containers.list(all=all)
        ]
    return _call(_fetch)


@mcp.tool()
def inspect_container(name: str) -> dict:
    """Inspecciona un contenedor (configuración completa).

    Args:
        name: Nombre o ID del contenedor.
    """
    def _fetch():
        client = _get_client()
        c = client.containers.get(name)
        attrs = c.attrs
        return {
            "id": c.id[:12],
            "name": c.name,
            "status": c.status,
            "image": c.image.tags[0] if c.image.tags else c.image.id[:12],
            "created": attrs.get("Created"),
            "started": attrs.get("State", {}).get("StartedAt"),
            "ports": attrs.get("NetworkSettings", {}).get("Ports", {}),
            "mounts": [
                {"src": m.get("Source"), "dst": m.get("Destination"), "mode": m.get("Mode")}
                for m in attrs.get("Mounts", [])
            ],
            "env": attrs.get("Config", {}).get("Env", []),
            "restart_policy": attrs.get("HostConfig", {}).get("RestartPolicy", {}),
        }
    return _call(_fetch)


@mcp.tool()
def get_container_logs(name: str, tail: int = 200) -> dict:
    """Devuelve las últimas líneas de logs de un contenedor.

    Args:
        name: Nombre o ID del contenedor.
        tail: Número de líneas a devolver (máx 1000).
    """
    tail = min(max(1, tail), 1000)

    def _fetch():
        client = _get_client()
        c = client.containers.get(name)
        raw = c.logs(tail=tail, timestamps=True)
        return raw.decode("utf-8", errors="replace")

    return _call(_fetch)


@mcp.tool()
def restart_container(name: str, confirm: bool = False) -> dict:
    """Reinicia un contenedor por nombre o ID.

    REQUIERE confirm=True para ejecutar. Sin confirmación devuelve un aviso.

    Args:
        name: Nombre o ID del contenedor.
        confirm: Debe ser True para ejecutar el restart. Por defecto False (dry run).
    """
    if not confirm:
        return needs_confirmation("restart_container", name)

    def _exec():
        client = _get_client()
        c = client.containers.get(name)
        c.restart()
        return {"restarted": c.name}

    return _call(_exec)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
