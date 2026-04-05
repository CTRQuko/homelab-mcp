"""Tests del Python MCP — validación de sandbox."""
import pytest

import homelab_mcp.python_mcp.server as py_server


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(py_server, "BASE", tmp_path)
    return tmp_path


def test_pytest_run_traversal(sandbox):
    result = py_server.pytest_run("../../etc")
    assert result["ok"] is False
    assert "sandbox" in result["error"].lower() or "fuera" in result["error"].lower()


def test_ruff_check_traversal(sandbox):
    result = py_server.ruff_check("../../../tmp")
    assert result["ok"] is False


def test_pytest_run_missing_path(sandbox):
    result = py_server.pytest_run("ghost-project")
    assert result["ok"] is False
    assert "no encontrad" in result["error"].lower() or "sandbox" in result["error"].lower()


def test_ruff_check_valid_dir(sandbox):
    """Directorio dentro del sandbox válido."""
    proj = sandbox / "mylib"
    proj.mkdir()
    (proj / "main.py").write_text("x = 1\n")
    result = py_server.ruff_check("mylib")
    # Si ruff no está instalado devuelve error de herramienta, no de sandbox
    if not result["ok"]:
        assert "sandbox" not in result.get("error", "").lower()


def test_python_version():
    """python_version siempre funciona sin sandbox."""
    result = py_server.python_version()
    assert result["ok"] is True
    assert "version" in result["data"]


def test_pip_list():
    """pip_list funciona sin path."""
    result = py_server.pip_list()
    assert result["ok"] is True
