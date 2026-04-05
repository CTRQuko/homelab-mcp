"""Tests del helper safe_path."""
import pytest
from pathlib import Path

from homelab_mcp.utils.paths import safe_path


def test_safe_path_valid(tmp_path):
    """Ruta válida dentro del sandbox se resuelve correctamente."""
    result = safe_path(tmp_path, "subdir/file.txt")
    assert result == (tmp_path / "subdir" / "file.txt").resolve()


def test_safe_path_root(tmp_path):
    """Ruta vacía/punto devuelve la raíz del sandbox."""
    result = safe_path(tmp_path, ".")
    assert result == tmp_path.resolve()


def test_safe_path_traversal_raises(tmp_path):
    """Path traversal con .. lanza ValueError."""
    with pytest.raises(ValueError, match="fuera del sandbox"):
        safe_path(tmp_path, "../../etc/passwd")


def test_safe_path_absolute_sibling_raises(tmp_path):
    """Nombre de directorio que empieza igual pero es diferente lanza ValueError."""
    # e.g. sandbox=/tmp/abc, intento /tmp/abc-evil
    parent = tmp_path.parent
    sibling = parent / (tmp_path.name + "-evil")
    with pytest.raises(ValueError, match="fuera del sandbox"):
        safe_path(tmp_path, "../" + sibling.name)


def test_safe_path_nested_valid(tmp_path):
    """Ruta anidada válida no lanza."""
    result = safe_path(tmp_path, "a/b/c/d.txt")
    assert str(result).startswith(str(tmp_path))
