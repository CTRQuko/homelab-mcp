"""Python MCP — testing, linting y diagnóstico de proyectos Python."""
import logging
import subprocess
import sys
from pathlib import Path

from homelab_mcp.base import create_server
from homelab_mcp.config import settings
from homelab_mcp.utils.paths import safe_path
from homelab_mcp.utils.responses import error, ok

log = logging.getLogger(__name__)
mcp = create_server("homelab-python")
BASE = settings.python_projects.base_path


def _resolve_path(rel_path: str) -> Path:
    """Valida ruta relativa dentro del sandbox python.

    Raises:
        ValueError: Si la ruta escapa del sandbox o no existe.
    """
    p = safe_path(BASE, rel_path)
    if not p.exists():
        raise ValueError(f"Ruta no encontrada dentro del sandbox: {rel_path}")
    return p


def _run(args: list[str], cwd: Path | None, timeout: int) -> dict:
    try:
        result = subprocess.run(
            args,
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
        return error(f"Herramienta no encontrada: {args[0]}")
    except subprocess.TimeoutExpired:
        return error(f"Timeout tras {timeout}s")
    except Exception as e:
        log.error("python_mcp error: %s", e)
        return error("Error ejecutando herramienta", str(e))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def python_version() -> dict:
    """Muestra la versión de Python en uso por el servidor MCP."""
    info = {
        "version": sys.version,
        "executable": sys.executable,
        "version_info": {
            "major": sys.version_info.major,
            "minor": sys.version_info.minor,
            "micro": sys.version_info.micro,
        },
    }
    return ok(info)


@mcp.tool()
def pytest_run(path: str = ".") -> dict:
    """Ejecuta pytest en un proyecto Python.

    Args:
        path: Ruta relativa al PYTHON_BASE_PATH configurado.
    """
    try:
        target = _resolve_path(path)
    except ValueError as e:
        return error(str(e))
    cwd = target if target.is_dir() else target.parent
    return _run(
        [sys.executable, "-m", "pytest", "-q", str(target)],
        cwd=cwd,
        timeout=600,
    )


@mcp.tool()
def ruff_check(path: str = ".") -> dict:
    """Ejecuta ruff check sobre un directorio o fichero.

    Args:
        path: Ruta relativa al PYTHON_BASE_PATH configurado.
    """
    try:
        target = _resolve_path(path)
    except ValueError as e:
        return error(str(e))
    return _run(
        [sys.executable, "-m", "ruff", "check", str(target)],
        cwd=None,
        timeout=120,
    )


@mcp.tool()
def pip_list() -> dict:
    """Lista paquetes instalados en el entorno Python actual."""
    return _run(
        [sys.executable, "-m", "pip", "list", "--format=json"],
        cwd=None,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
