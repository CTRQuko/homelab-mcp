"""Tests del wrapper subprocess_safe."""
import sys
import pytest
from pathlib import Path

from homelab_mcp.utils.subprocess_safe import run_safe, _tokenize


def test_allowed_command(tmp_path):
    """Comando en whitelist se ejecuta correctamente."""
    script = tmp_path / "hello.py"
    script.write_text("print('hello')")
    result = run_safe(
        f"python {script}",
        allowed={"python", "python3"},
        cwd=tmp_path,
        timeout=10,
    )
    assert result["returncode"] == 0
    assert "hello" in result["stdout"]


def test_blocked_command_raises(tmp_path):
    """Comando fuera de whitelist lanza ValueError."""
    with pytest.raises(ValueError, match="no permitido"):
        run_safe("rm -rf /", allowed={"ls"}, cwd=tmp_path)


def test_empty_command_raises(tmp_path):
    """Comando vacío lanza ValueError."""
    with pytest.raises(ValueError, match="vacío"):
        run_safe("", allowed={"ls"}, cwd=tmp_path)


def test_malformed_command_raises(tmp_path):
    """Comillas sin cerrar lanza ValueError."""
    with pytest.raises(ValueError, match="mal formado"):
        run_safe("ls 'unclosed", allowed={"ls"}, cwd=tmp_path)


def test_returncode_on_failure(tmp_path):
    """Comando que falla devuelve returncode != 0."""
    script = tmp_path / "fail.py"
    script.write_text("import sys; sys.exit(1)")
    result = run_safe(
        f"python {script}",
        allowed={"python", "python3"},
        cwd=tmp_path,
        timeout=10,
    )
    assert result["returncode"] != 0


# ---------------------------------------------------------------------------
# Tests _tokenize (Windows path handling)
# ---------------------------------------------------------------------------

def test_tokenize_simple():
    """Tokeniza comando simple correctamente."""
    tokens = _tokenize("ls -la /tmp")
    assert tokens[0] == "ls"
    assert "-la" in tokens


def test_tokenize_quoted_arg():
    """Tokeniza argumentos entre comillas."""
    tokens = _tokenize('python script.py "arg with spaces"')
    assert tokens[0] == "python"
    assert "arg with spaces" in tokens


def test_tokenize_empty_raises():
    """Cadena vacía lanza ValueError."""
    with pytest.raises(ValueError, match="vacío"):
        _tokenize("")


def test_tokenize_whitespace_only_raises():
    """Solo espacios lanza ValueError."""
    with pytest.raises(ValueError, match="vacío"):
        _tokenize("   ")


def test_run_safe_accepts_set_and_list(tmp_path):
    """run_safe acepta tanto set como list para allowed."""
    script = tmp_path / "ok.py"
    script.write_text("print('ok')")
    # Con list
    r1 = run_safe(f"python {script}", allowed=["python"], cwd=tmp_path, timeout=10)
    assert r1["returncode"] == 0
    # Con set
    r2 = run_safe(f"python {script}", allowed={"python"}, cwd=tmp_path, timeout=10)
    assert r2["returncode"] == 0
