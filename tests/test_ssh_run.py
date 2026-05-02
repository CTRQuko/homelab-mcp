"""Tests para homelab_ssh_run — wrapper canonical SSH+sudo (v1.4.0).

Mockea subprocess.run y filesystem para testear sin tocar SSH real.
"""
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_sudo_key(tmp_path, monkeypatch):
    """Crea un sudo key file fake y lo expone via env var."""
    key_file = tmp_path / "claude-sudo.key"
    key_file.write_text("test_password_123", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_SUDO_KEY_FILE", str(key_file))
    return str(key_file)


def _fake_ssh_proc(stdout="", stderr="", returncode=0):
    """Crea un mock de subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["ssh", "fake", "fake"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Validation: input args
# ---------------------------------------------------------------------------

def test_ssh_run_empty_node_returns_error(fake_sudo_key):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    result = ssh_run("", "ls")
    assert result["ok"] is False
    assert "node" in result["error"].lower()


def test_ssh_run_empty_command_returns_error(fake_sudo_key):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    result = ssh_run("pve", "")
    assert result["ok"] is False
    assert "command" in result["error"].lower()


def test_ssh_run_destructive_pattern_blocked(fake_sudo_key):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    cases = [
        "rm -rf /",
        "mkfs.ext4 /dev/sda",
        "dd if=/dev/zero of=/dev/sda",
        "shutdown -h now",
        "reboot",
    ]
    for cmd in cases:
        result = ssh_run("pve", cmd)
        assert result["ok"] is False, f"Should reject: {cmd!r}"
        assert "destructiv" in result["error"].lower()


def test_ssh_run_privileged_user_blocked(fake_sudo_key):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    cases = ["root@pve", "debian@10.0.1.14", "ubuntu@host", "admin@x"]
    for node in cases:
        result = ssh_run(node, "ls")
        assert result["ok"] is False, f"Should reject: {node!r}"
        assert "bloqueado" in result["error"].lower() or "user" in result["error"].lower()


# ---------------------------------------------------------------------------
# Sudo key file handling
# ---------------------------------------------------------------------------

def test_ssh_run_missing_sudo_key_file(monkeypatch, tmp_path):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    monkeypatch.setenv("CLAUDE_SUDO_KEY_FILE", str(tmp_path / "missing.key"))
    result = ssh_run("pve", "/usr/sbin/pct list", sudo=True)
    assert result["ok"] is False
    assert "no encontrado" in result["error"].lower() or "missing" in result["error"].lower()


def test_ssh_run_empty_sudo_key_file(monkeypatch, tmp_path):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    key_file = tmp_path / "empty.key"
    key_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_SUDO_KEY_FILE", str(key_file))
    result = ssh_run("pve", "/usr/sbin/pct list", sudo=True)
    assert result["ok"] is False
    assert "vacío" in result["error"].lower() or "empty" in result["error"].lower()


# ---------------------------------------------------------------------------
# Successful execution paths (mocked subprocess)
# ---------------------------------------------------------------------------

def test_ssh_run_success_with_sudo(fake_sudo_key):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _fake_ssh_proc(stdout="VMID NAME\n100 vm1\n", returncode=0)
        result = ssh_run("pve", "/usr/sbin/pct list", sudo=True)
    assert result["ok"] is True
    assert result["data"]["exit_code"] == 0
    assert "VMID NAME" in result["data"]["stdout"]
    assert result["data"]["sudo_used"] is True
    assert result["data"]["command_run"] == "/usr/sbin/pct list"
    # Verifica que NO se filtró el password en command_run
    assert "test_password_123" not in result["data"]["command_run"]


def test_ssh_run_success_without_sudo(fake_sudo_key):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _fake_ssh_proc(stdout="hostname\n", returncode=0)
        result = ssh_run("pve", "hostname", sudo=False)
    assert result["ok"] is True
    assert result["data"]["sudo_used"] is False
    # Verifica que el comando enviado no lleva sudo
    args, _ = mock_run.call_args
    ssh_args = args[0]
    assert "sudo" not in ssh_args[2]


def test_ssh_run_nonzero_exit_returned_in_data(fake_sudo_key):
    """Comando que falla en remote → ok=True pero exit_code refleja el error."""
    from homelab_mcp.proxmox_mcp.server import ssh_run
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _fake_ssh_proc(
            stdout="", stderr="not allowed", returncode=1
        )
        result = ssh_run("pve", "/usr/sbin/pct list", sudo=True)
    assert result["ok"] is True  # tool ran successfully
    assert result["data"]["exit_code"] == 1
    assert "not allowed" in result["data"]["stderr"]


def test_ssh_run_timeout(fake_sudo_key):
    from homelab_mcp.proxmox_mcp.server import ssh_run
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=5)
        result = ssh_run("pve", "/usr/sbin/pct list", timeout=5)
    assert result["ok"] is False
    assert "timeout" in result["error"].lower()


def test_ssh_run_password_passed_via_stdin_not_args(fake_sudo_key):
    """Password va en remote_cmd (echo), NO en args de subprocess."""
    from homelab_mcp.proxmox_mcp.server import ssh_run
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _fake_ssh_proc(returncode=0)
        ssh_run("pve", "/usr/sbin/pct list", sudo=True)

    args, _ = mock_run.call_args
    ssh_args = args[0]
    # ssh_args = ["ssh", "pve", "<remote_cmd>"]
    # El password va dentro del remote_cmd como `echo 'pass' | sudo -S ...`
    assert ssh_args[0] == "ssh"
    assert ssh_args[1] == "pve"
    # Password DEBE estar en el remote command (es como sudo lo recibe)
    assert "test_password_123" in ssh_args[2]
    # Pero NO en command_run que sí se loguea
    # (eso lo testea test_ssh_run_success_with_sudo)


def test_ssh_run_strips_sudo_prompt_from_stderr(fake_sudo_key):
    """[sudo] password for... líneas se quitan del stderr final."""
    from homelab_mcp.proxmox_mcp.server import ssh_run
    fake_stderr = "[sudo] password for claude: real_error_here"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _fake_ssh_proc(
            stdout="", stderr=fake_stderr, returncode=1
        )
        result = ssh_run("pve", "/usr/sbin/pct list", sudo=True)
    assert "[sudo] password" not in result["data"]["stderr"]
    assert "real_error_here" in result["data"]["stderr"]
