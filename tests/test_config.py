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

_VALID_TOKEN = "12345678-1234-1234-1234-123456789012"  # 36 chars, formato UUID


def test_proxmox_nodes_from_json(tmp_path):
    """ProxmoxSettings carga nodos desde JSON."""
    nodes = {
        "pve": {"host": "10.0.0.1:8006", "user": "testuser@pam", "token_name": "api", "token_value": _VALID_TOKEN, "endpoint_node": "node1"},
        "pve2": {"host": "10.0.0.2:8006", "user": "testuser@pam", "token_name": "api", "token_value": _VALID_TOKEN + "x", "endpoint_node": "pve2"},
    }
    nodes_file = tmp_path / "nodes.json"
    nodes_file.write_text(json.dumps(nodes))

    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(nodes_file)}):
        ps = ProxmoxSettings()

    assert "pve" in ps.available_nodes
    assert "pve2" in ps.available_nodes
    assert ps.get_node("pve").host == "10.0.0.1:8006"
    assert ps.get_node("pve").endpoint_node == "node1"


def test_proxmox_get_node_by_endpoint(tmp_path):
    """get_node busca por endpoint_node si el alias no coincide."""
    nodes = {"pve": {"host": "1.2.3.4:8006", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "node1"}}
    f = tmp_path / "n.json"
    f.write_text(json.dumps(nodes))
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(f)}):
        ps = ProxmoxSettings()
    assert ps.get_node("node1") is not None
    assert ps.get_node("node1").host == "1.2.3.4:8006"


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


# ---------------------------------------------------------------------------
# Schema validation v1.3.0 — proxmox_nodes.json
# ---------------------------------------------------------------------------

def test_proxmox_nodes_malformed_json_raises(tmp_path):
    """JSON malformado → ValueError loud al boot (fail-loud)."""
    bad = tmp_path / "bad.json"
    bad.write_text("{ this is not json }", encoding="utf-8")
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(bad)}):
        with pytest.raises(ValueError, match="PROXMOX_NODES_FILE inválido"):
            ProxmoxSettings()


def test_proxmox_nodes_top_level_not_dict_raises(tmp_path):
    """JSON top-level es lista → ValueError (debe ser dict de aliases)."""
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(bad)}):
        with pytest.raises(ValueError, match="objeto JSON top-level"):
            ProxmoxSettings()


def test_proxmox_nodes_invalid_host_format(tmp_path):
    """host sin puerto → nodo skipped con warning, otros nodos cargan."""
    nodes = {
        "pve_bad": {"host": "10.0.0.1", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "n"},
        "pve_good": {"host": "10.0.0.2:8006", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "n2"},
    }
    f = tmp_path / "n.json"
    f.write_text(json.dumps(nodes))
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(f)}):
        ps = ProxmoxSettings()
    assert "pve_bad" not in ps.available_nodes
    assert "pve_good" in ps.available_nodes


def test_proxmox_nodes_invalid_user_format(tmp_path):
    """user sin @ → nodo skipped con warning."""
    nodes = {
        "pve": {"host": "10.0.0.1:8006", "user": "claude", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "n"},
    }
    f = tmp_path / "n.json"
    f.write_text(json.dumps(nodes))
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(f)}):
        ps = ProxmoxSettings()
    assert "pve" not in ps.available_nodes


def test_proxmox_nodes_missing_endpoint_node(tmp_path):
    """endpoint_node faltante → skipped (ya no más default-a-alias silente)."""
    nodes = {
        "pve": {"host": "10.0.0.1:8006", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN},
    }
    f = tmp_path / "n.json"
    f.write_text(json.dumps(nodes))
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(f)}):
        ps = ProxmoxSettings()
    assert "pve" not in ps.available_nodes


def test_proxmox_nodes_short_token_skipped(tmp_path):
    """token_value de menos de 20 chars → skipped."""
    nodes = {
        "pve": {"host": "10.0.0.1:8006", "user": "u@pam", "token_name": "t", "token_value": "short", "endpoint_node": "n"},
    }
    f = tmp_path / "n.json"
    f.write_text(json.dumps(nodes))
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(f)}):
        ps = ProxmoxSettings()
    assert "pve" not in ps.available_nodes


def test_proxmox_nodes_partial_load(tmp_path):
    """Mezcla válidos + inválidos: solo los válidos se cargan."""
    nodes = {
        "pve_ok1":  {"host": "10.0.0.1:8006", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "n1"},
        "pve_bad":  {"host": "10.0.0.2", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "n2"},
        "pve_ok2":  {"host": "10.0.0.3:8006", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN + "X", "endpoint_node": "n3"},
    }
    f = tmp_path / "n.json"
    f.write_text(json.dumps(nodes))
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(f)}):
        ps = ProxmoxSettings()
    assert set(ps.available_nodes) == {"pve_ok1", "pve_ok2"}


def test_proxmox_nodes_invalid_alias_skipped(tmp_path):
    """Alias con caracteres prohibidos (espacios, $) → skipped."""
    nodes = {
        "valid_alias": {"host": "10.0.0.1:8006", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "n1"},
        "alias con espacio": {"host": "10.0.0.2:8006", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "n2"},
        "alias$with$dollar": {"host": "10.0.0.3:8006", "user": "u@pam", "token_name": "t", "token_value": _VALID_TOKEN, "endpoint_node": "n3"},
    }
    f = tmp_path / "n.json"
    f.write_text(json.dumps(nodes))
    with patch.dict(os.environ, {"PROXMOX_NODES_FILE": str(f)}):
        ps = ProxmoxSettings()
    assert ps.available_nodes == ["valid_alias"]
