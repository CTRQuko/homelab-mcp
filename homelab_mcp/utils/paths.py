"""Utilidades de sandbox para rutas de ficheros."""
from pathlib import Path


def safe_path(base: Path, relative: str) -> Path:
    """Resuelve una ruta relativa dentro del sandbox.

    Lanza ValueError si la ruta resuelta escapa del directorio base.
    """
    base = base.resolve()
    full = (base / relative).resolve()
    # Comparación case-insensitive en Windows, case-sensitive en Linux
    try:
        full.relative_to(base)
    except ValueError:
        raise ValueError(f"Ruta '{relative}' fuera del sandbox ({base})")
    return full
