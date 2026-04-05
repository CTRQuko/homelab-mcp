"""Windows MCP — operaciones de fichero y PowerShell en sandbox."""
import logging
import subprocess

from homelab_mcp.base import create_server
from homelab_mcp.config import settings
from homelab_mcp.utils.paths import safe_path
from homelab_mcp.utils.responses import error, ok

log = logging.getLogger(__name__)
mcp = create_server("homelab-windows")
BASE = settings.windows.base_path

# Verbos de solo lectura permitidos en PowerShell (case-insensitive matching)
_ALLOWED_PS_VERBS = {
    "get-childitem", "dir",
    "get-content", "type", "cat",
    "get-item",
    "get-itemproperty",
    "get-process",
    "get-service",
    "get-disk",
    "get-volume",
    "test-path",
    "select-string",
    "measure-object",
    "where-object",
    "format-list",
    "format-table",
    "out-string",
}

# Prefijos de verbos PowerShell destructivos (case-insensitive)
_BLOCKED_VERB_PREFIXES = (
    "remove-", "set-", "new-", "invoke-", "start-", "stop-",
    "restart-", "enable-", "disable-", "clear-", "reset-",
    "uninstall-", "add-", "register-", "unregister-",
    "rename-", "move-", "copy-", "update-", "install-",
    "write-", "export-", "import-", "send-", "push-",
    "mount-", "dismount-", "suspend-", "resume-",
)

# Operadores de shell y binarios peligrosos
_BLOCKED_SHELL_TOKENS = {
    "|", ";", "&", "`",
    "$(", "#{",
}

# Aliases y binarios cmd/bash peligrosos (exactos, case-insensitive)
_BLOCKED_BINARIES = {
    "rm", "del", "rmdir", "rd", "move", "ren", "copy", "xcopy", "robocopy",
    "reg", "net", "sc", "schtasks", "wmic", "icacls", "cacls", "takeown",
    "powershell", "pwsh", "cmd", "bash", "wsl", "sh",
    "format", "diskpart", "cipher",
}


def _ps_allowed(cmd: str) -> tuple[bool, str]:
    """Valida un comando PowerShell contra la whitelist.

    Returns:
        (allowed, reason): True si OK, False con razón si bloqueado.
    """
    stripped = cmd.strip()
    if not stripped:
        return False, "Comando vacío"

    # Bloquear operadores de shell primero
    for token in _BLOCKED_SHELL_TOKENS:
        if token in stripped:
            return False, f"Operador de shell bloqueado: '{token}'"

    # Tokenizar por espacios (primer token es el verbo)
    first = stripped.split()[0].lower()

    # Comprobar que el verbo está en whitelist
    if first not in _ALLOWED_PS_VERBS:
        return False, f"Verbo '{first}' no está en la whitelist de lectura"

    # Buscar verbos destructivos en el resto del comando
    cmd_lower = stripped.lower()
    for prefix in _BLOCKED_VERB_PREFIXES:
        if prefix in cmd_lower:
            return False, f"Verbo destructivo detectado: '{prefix}*'"

    # Buscar binarios peligrosos como tokens
    tokens_lower = cmd_lower.split()
    for t in tokens_lower[1:]:
        if t in _BLOCKED_BINARIES:
            return False, f"Binario peligroso detectado: '{t}'"

    return True, ""


# ---------------------------------------------------------------------------
# Tools de ficheros
# ---------------------------------------------------------------------------

@mcp.tool()
def read_file(rel_path: str) -> dict:
    """Lee un fichero dentro del sandbox Windows (WINDOWS_BASE_PATH).

    Args:
        rel_path: Ruta relativa al sandbox configurado.
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
        rel_path: Ruta relativa al sandbox.
        content: Contenido a escribir.
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
        rel_path: Ruta relativa al sandbox (por defecto la raíz).
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
        rel_path: Ruta relativa al sandbox.
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
# Tools de PowerShell
# ---------------------------------------------------------------------------

@mcp.tool()
def run_powershell(cmd: str) -> dict:
    """Ejecuta un comando PowerShell de solo lectura dentro del sandbox.

    Verbos permitidos: Get-ChildItem, Get-Content, Get-Item, Get-Process,
    Get-Service, Get-Disk, Get-Volume, Test-Path, Select-String, etc.

    Args:
        cmd: Comando PowerShell con argumentos.
    """
    allowed, reason = _ps_allowed(cmd)
    if not allowed:
        log.warning("PowerShell bloqueado: %s | Razón: %s", cmd.split()[0] if cmd.strip() else "", reason)
        return error(f"Comando no permitido: {reason}")
    log.info("PowerShell ejecutando: %s", cmd.split()[0])
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Restricted", "-Command", cmd],
            cwd=BASE,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return ok({
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        })
    except FileNotFoundError:
        return error("PowerShell no encontrado en el PATH")
    except Exception as e:
        log.error("run_powershell error: %s", e)
        return error("Error ejecutando PowerShell", str(e))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
