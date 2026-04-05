"""Wrapper seguro para subprocesos con whitelist y timeout."""
import shlex
import subprocess
import sys
from pathlib import Path

_IS_WINDOWS = sys.platform == "win32"


def _tokenize(cmd: str) -> list[str]:
    """Tokeniza una cadena de comando de forma segura.

    En POSIX usa shlex.split con interpretación de escape completa.
    En Windows usa shlex.split(posix=False) y elimina comillas externas
    de cada token para normalizar el resultado.
    """
    if not cmd or not cmd.strip():
        raise ValueError("Comando vacío")

    if _IS_WINDOWS:
        try:
            tokens = shlex.split(cmd, posix=False)
        except ValueError as e:
            raise ValueError(f"Comando mal formado: {e}") from e
        # posix=False preserva comillas externas: '"foo"' -> 'foo'
        cleaned = []
        for t in tokens:
            if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
                t = t[1:-1]
            cleaned.append(t)
        return cleaned
    else:
        try:
            return shlex.split(cmd)
        except ValueError as e:
            raise ValueError(f"Comando mal formado: {e}") from e


def run_safe(
    cmd: str,
    allowed: set[str] | list[str],
    cwd: Path,
    timeout: int = 30,
    env: dict | None = None,
) -> dict:
    """Ejecuta un comando si el primer token está en la whitelist.

    El binario se busca por nombre simple (e.g. 'python', 'ls'), no por ruta
    absoluta. Esto es intencional: rutas absolutas con espacios (como
    C:\\Program Files\\...) no son soportadas por diseño de seguridad.

    Args:
        cmd: Cadena de comando (se parsea con shlex, sin shell).
        allowed: Conjunto de binarios permitidos (primer token del comando).
        cwd: Directorio de trabajo (debe ser el sandbox).
        timeout: Tiempo máximo en segundos.
        env: Variables de entorno opcionales.

    Returns:
        dict con keys 'stdout', 'stderr', 'returncode'.

    Raises:
        ValueError: Si el primer token no está en la whitelist.
        ValueError: Si cmd está vacío o mal formado.
    """
    tokens = _tokenize(cmd)

    if not tokens:
        raise ValueError("Comando vacío")

    binary = tokens[0]
    allowed_set = set(allowed)
    if binary not in allowed_set:
        raise ValueError(
            f"Comando '{binary}' no permitido. Permitidos: {', '.join(sorted(allowed_set))}"
        )

    result = subprocess.run(
        tokens,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }
