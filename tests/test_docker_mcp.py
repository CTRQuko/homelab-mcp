"""Tests del Docker MCP — confirmación de restart."""
import pytest

import homelab_mcp.docker_mcp.server as docker_server


def test_restart_without_confirm():
    """restart_container sin confirm=True devuelve needs_confirmation."""
    result = docker_server.restart_container("mycontainer")
    assert result.get("needs_confirmation") is True
    assert result["action"] == "restart_container"
    assert result["target"] == "mycontainer"


def test_restart_without_confirm_explicit_false():
    """restart_container con confirm=False devuelve needs_confirmation."""
    result = docker_server.restart_container("mycontainer", confirm=False)
    assert result.get("needs_confirmation") is True
