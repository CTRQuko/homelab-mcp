"""Linux MCP — operaciones de fichero y comandos en sandbox."""
import logging
import os

from homelab_mcp.base import create_server
from homelab_mcp.config import settings
from homelab_mcp.utils.paths import safe_path
from homelab_mcp.utils.responses import error, ok
from homelab_mcp.utils.subprocess_safe import run_safe

log = logging.getLogger(__name__)
mcp = create_server("homelab-linux")
BASE = settings.linux.base_path

# Comandos de solo-lectura permitidos en el sandbox
_ALLOWED_COMMANDS = {
    "ls", "cat", "df", "du", "grep", "find",
    "head", "tail", "wc", "stat", "file",
    "free", "uptime", "hostname",
}


# ---------------------------------------------------------------------------
# Tools de ficheros
# ---------------------------------------------------------------------------

@mcp.tool()
def read_file(rel_path: str) -> dict:
    """Lee un fichero dentro del sandbox linux.

    Args:
        rel_path: Ruta relativa al LINUX_BASE_PATH configurado.
    """
    try:
        path = safe_path(BASE, rel_path)
        if not path.is_file():
            return error(f"No es un fichero: {rel_path}")
        return ok(path.read_text(encoding="utf-8"))
    except ValueError as e:
        return error(str(e))
    except OSError as e:
        return error("Error leyendo fichero", str(e))


@mcp.tool()
def write_file(rel_path: str, content: str) -> dict:
    """Escribe contenido en un fichero dentro del sandbox.

    Args:
        rel_path: Ruta relativa al LINUX_BASE_PATH.
        content: Contenido a escribir (sobrescribe si existe).
    """
    try:
        path = safe_path(BASE, rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ok({"written": str(path), "bytes": len(content.encode())})
    except ValueError as e:
        return error(str(e))
    except OSError as e:
        return error("Error escribiendo fichero", str(e))


@mcp.tool()
def list_dir(rel_path: str = ".") -> dict:
    """Lista el contenido de un directorio dentro del sandbox.

    Args:
        rel_path: Ruta relativa al LINUX_BASE_PATH (por defecto la raíz del sandbox).
    """
    try:
        path = safe_path(BASE, rel_path)
        if not path.is_dir():
            return error(f"No es un directorio: {rel_path}")
        entries = []
        for entry in sorted(path.iterdir()):
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        return ok(entries)
    except ValueError as e:
        return error(str(e))
    except OSError as e:
        return error("Error listando directorio", str(e))


@mcp.tool()
def file_exists(rel_path: str) -> dict:
    """Comprueba si un fichero o directorio existe dentro del sandbox.

    Args:
        rel_path: Ruta relativa al LINUX_BASE_PATH.
    """
    try:
        path = safe_path(BASE, rel_path)
        exists = path.exists()
        return ok({
            "exists": exists,
            "is_file": path.is_file() if exists else None,
            "is_dir": path.is_dir() if exists else None,
        })
    except ValueError as e:
        return error(str(e))


# ---------------------------------------------------------------------------
# Tools de comando
# ---------------------------------------------------------------------------

@mcp.tool()
def run_command(cmd: str) -> dict:
    """Ejecuta un comando whitelisted dentro del sandbox linux.

    Comandos permitidos: ls, cat, df, du, grep, find, head, tail, wc,
    stat, file, free, uptime, hostname.

    Args:
        cmd: Comando con argumentos (se parsea sin shell).
    """
    try:
        result = run_safe(cmd, allowed=_ALLOWED_COMMANDS, cwd=BASE, timeout=30)
        return ok(result)
    except ValueError as e:
        return error(str(e))
    except Exception as e:
        log.error("run_command error: %s", e)
        return error("Error ejecutando comando", str(e))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
