"""Tests de configuración básica."""
import json
import os
from unittest.mock import patch

import pytest

from homelab_mcp.config import Settings, ProxmoxSettings


def test_settings_defaults():
    """Settings crea instancia con defaults sin .env."""
    with patch.dict(os.environ, {}, clear=True):
        s = Settings()
    assert s.log_level in ("INFO", "")  # acepta valor ya cargado por load_dotenv


def test_proxmox_is_configured_false():
    """ProxmoxSettings.is_configured() devuelve False cuando faltan valores."""
    with patch.dict(os.environ, {
        "PROXMOX_HOST": "",
        "PROXMOX_USER": "",
        "PROXMOX_TOKEN_NAME": "",
        "PROXMOX_TOKEN_VALUE": "",
    }):
        s = Settings()
    assert not s.proxmox.is_configured()


def test_proxmox_is_configured_true():
    """ProxmoxSettings.is_configured() devuelve True con todos los valores."""
    with patch.dict(os.environ, {
        "PROXMOX_HOST": "10.0.0.1",
        "PROXMOX_USER": "testuser@pam",
        "PROXMOX_TOKEN_NAME": "test-token",
        "PROXMOX_TOKEN_VALUE": "secret",
    }):
        s = Settings()
    assert s.proxmox.is_configured()


def test_linux_base_path_is_resolved():
    """LinuxSettings.base_path es un Path absoluto."""
    with patch.dict(os.environ, {"LINUX_BASE_PATH": "/tmp/test"}):
        s = Settings()
    assert s.linux.base_path.is_absolute()


def test_windows_base_path_is_resolved():
    """WindowsSettings.base_path es un Path absoluto."""
    s = Settings()
    assert s.windows.base_path.is_absolute()


# ---------------------------------------------------------------------------
# Multi-nodo Proxmox
# ---------------------------------------------------------------------------

def test_proxmox_nodes_from_json(tmp_path):
    """ProxmoxSettings carga nodos desde JSON."""
    nodes = {
        "pve": {"host": "10.0.0.1", "user": "testuser@pam", "token_name": "api", "token_value": "secret", "endpoint_node": "node1"},
        "pve2": {"host": "10.0.0.2", "user": "testuser@pam", "token_name": "api", "token_value": "secret2", "endpoint_node": "pve2"},
    }
    nodes_file = tmp_path / "nodes.json"
    nodes_file.write_text(json.dumps(nodes))

    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(nodes_file)}):
        ps = ProxmoxSettings()

    assert "pve" in ps.available_nodes
    assert "pve2" in ps.available_nodes
    assert ps.get_node("pve").host == "10.0.0.1"
    assert ps.get_node("pve").endpoint_node == "node1"


def test_proxmox_get_node_by_endpoint(tmp_path):
    """get_node busca por endpoint_node si el alias no coincide."""
    nodes = {"pve": {"host": "1.2.3.4", "user": "u", "token_name": "t", "token_value": "v", "endpoint_node": "node1"}}
    f = tmp_path / "n.json"
    f.write_text(json.dumps(nodes))
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(f)}):
        ps = ProxmoxSettings()
    assert ps.get_node("node1") is not None
    assert ps.get_node("node1").host == "1.2.3.4"


def test_proxmox_get_node_or_default_fallback():
    """get_node_or_default cae al single-host si no hay nodo."""
    with patch.dict(os.environ, {"PROXMOX_HOST": "10.0.0.99", "PROXMOX_USER": "u", "PROXMOX_TOKEN_NAME": "t", "PROXMOX_TOKEN_VALUE": "v"}):
        ps = ProxmoxSettings()
    default = ps.get_node_or_default("unknown")
    assert default.host == "10.0.0.99"
    assert default.endpoint_node == "unknown"


def test_proxmox_missing_nodes_file_is_ok():
    """PROXMOX_NODES_FILE apuntando a fichero inexistente no crashea."""
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": "/tmp/nonexistent.json"}):
        ps = ProxmoxSettings()
    assert ps.available_nodes == []
