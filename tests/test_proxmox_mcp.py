"""Tests del Proxmox MCP — confirmación y validación."""
import pytest
from unittest.mock import patch, MagicMock

import homelab_mcp.proxmox_mcp.server as pve_server


# ---------------------------------------------------------------------------
# Tests patrón de confirmación
# ---------------------------------------------------------------------------

def test_start_vm_needs_confirm():
    """start_vm sin confirm=True devuelve needs_confirmation."""
    result = pve_server.start_vm("pve", 100, "lxc")
    assert result.get("needs_confirmation") is True
    assert "start" in result["action"]


def test_stop_vm_needs_confirm():
    """stop_vm sin confirm=True devuelve needs_confirmation."""
    result = pve_server.stop_vm("pve", 100, "lxc")
    assert result.get("needs_confirmation") is True
    assert "stop" in result["action"]


def test_restart_vm_needs_confirm():
    """restart_vm sin confirm=True devuelve needs_confirmation."""
    result = pve_server.restart_vm("pve", 100, "qemu")
    assert result.get("needs_confirmation") is True
    assert "reboot" in result["action"]


def test_start_vm_confirm_false_explicit():
    """confirm=False explícito también pide confirmación."""
    result = pve_server.start_vm("pve", 200, "lxc", confirm=False)
    assert result.get("needs_confirmation") is True


def test_start_vm_invalid_vm_type_with_confirm():
    """vm_type inválido con confirm=True devuelve error, no needs_confirmation."""
    result = pve_server.start_vm("pve", 100, "invalid", confirm=True)
    assert result["ok"] is False
    assert "inválido" in result["error"]


# ---------------------------------------------------------------------------
# Tests de lectura (mockeando proxmoxer)
# ---------------------------------------------------------------------------

def test_list_nodes_connection_error():
    """list_nodes devuelve error si Proxmox no está configurado."""
    with patch.object(pve_server.settings.proxmox, "is_configured", return_value=False), \
         patch.object(pve_server.settings.proxmox, "get_node_or_default",
                      return_value=pve_server.settings.proxmox.get_node_or_default("")):
        result = pve_server.list_nodes()
    assert result["ok"] is False
    assert "configurado" in result["error"].lower() or "conexión" in result["error"].lower()


def test_get_vm_status_invalid_type():
    """get_vm_status con vm_type inválido devuelve error."""
    result = pve_server.get_vm_status("pve", 100, "docker")
    assert result["ok"] is False
    assert "inválido" in result["error"]
