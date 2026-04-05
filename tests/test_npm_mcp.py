"""Tests del npm MCP — validación de sandbox."""
import pytest

import homelab_mcp.npm_mcp.server as npm_server


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(npm_server, "BASE", tmp_path)
    return tmp_path


def test_npm_outdated_traversal(sandbox):
    result = npm_server.npm_outdated("../../etc")
    assert result["ok"] is False
    assert "sandbox" in result["error"].lower() or "fuera" in result["error"].lower()


def test_npm_audit_traversal(sandbox):
    result = npm_server.npm_audit("../../../tmp")
    assert result["ok"] is False


def test_npm_list_traversal(sandbox):
    result = npm_server.npm_list("../../..")
    assert result["ok"] is False


def test_npm_outdated_missing_dir(sandbox):
    result = npm_server.npm_outdated("nonexistent-project")
    assert result["ok"] is False
    assert "sandbox" in result["error"].lower() or "no encontrad" in result["error"].lower()


def test_npm_outdated_valid_dir(sandbox):
    """Directorio dentro del sandbox válido (npm fallará porque no hay package.json, pero la ruta es aceptada)."""
    proj = sandbox / "myproject"
    proj.mkdir()
    result = npm_server.npm_outdated("myproject")
    # Si npm no está instalado, devuelve error de npm, no de sandbox
    if not result["ok"]:
        assert "sandbox" not in result.get("error", "").lower()
