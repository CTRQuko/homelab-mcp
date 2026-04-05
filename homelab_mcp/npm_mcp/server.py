"""npm MCP — auditoría y análisis de proyectos Node.js."""
import logging
import subprocess
from pathlib import Path

from homelab_mcp.base import create_server
from homelab_mcp.config import settings
from homelab_mcp.utils.paths import safe_path
from homelab_mcp.utils.responses import error, ok

log = logging.getLogger(__name__)
mcp = create_server("homelab-npm")
BASE = settings.npm.base_path


def _resolve_project_path(rel_path: str) -> Path:
    """Valida ruta relativa dentro del sandbox npm.

    Raises:
        ValueError: Si la ruta escapa del sandbox o no es un directorio.
    """
    p = safe_path(BASE, rel_path)
    if not p.is_dir():
        raise ValueError(f"Directorio no encontrado dentro del sandbox: {rel_path}")
    return p


def _npm_run(args: list[str], cwd: Path, timeout: int) -> dict:
    try:
        result = subprocess.run(
            ["npm", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return ok({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        })
    except FileNotFoundError:
        return error("npm no encontrado en el PATH")
    except subprocess.TimeoutExpired:
        return error(f"Timeout tras {timeout}s")
    except Exception as e:
        log.error("npm error: %s", e)
        return error("Error ejecutando npm", str(e))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def npm_outdated(path: str = ".") -> dict:
    """Muestra dependencias desactualizadas (npm outdated --json).

    Args:
        path: Ruta relativa al NPM_BASE_PATH configurado.
    """
    try:
        cwd = _resolve_project_path(path)
    except ValueError as e:
        return error(str(e))
    return _npm_run(["outdated", "--json"], cwd=cwd, timeout=120)


@mcp.tool()
def npm_audit(path: str = ".") -> dict:
    """Audita vulnerabilidades de dependencias (npm audit --json).

    Args:
        path: Ruta relativa al NPM_BASE_PATH configurado.
    """
    try:
        cwd = _resolve_project_path(path)
    except ValueError as e:
        return error(str(e))
    return _npm_run(["audit", "--json"], cwd=cwd, timeout=300)


@mcp.tool()
def npm_list(path: str = ".") -> dict:
    """Lista el árbol de dependencias instaladas (npm list --json).

    Args:
        path: Ruta relativa al NPM_BASE_PATH configurado.
    """
    try:
        cwd = _resolve_project_path(path)
    except ValueError as e:
        return error(str(e))
    return _npm_run(["list", "--json", "--depth=1"], cwd=cwd, timeout=60)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
