"""Tests del Linux MCP."""
import pytest
from unittest.mock import patch
from pathlib import Path

import homelab_mcp.linux_mcp.server as linux_server


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirige el BASE del servidor al tmp_path."""
    monkeypatch.setattr(linux_server, "BASE", tmp_path)
    return tmp_path


def test_read_file_ok(sandbox):
    f = sandbox / "hello.txt"
    f.write_text("mundo", encoding="utf-8")
    result = linux_server.read_file("hello.txt")
    assert result["ok"] is True
    assert result["data"] == "mundo"


def test_read_file_not_found(sandbox):
    result = linux_server.read_file("nope.txt")
    assert result["ok"] is False


def test_read_file_traversal(sandbox):
    result = linux_server.read_file("../../etc/passwd")
    assert result["ok"] is False
    assert "sandbox" in result["error"].lower() or "fuera" in result["error"].lower()


def test_write_file_ok(sandbox):
    result = linux_server.write_file("subdir/nuevo.txt", "contenido")
    assert result["ok"] is True
    assert (sandbox / "subdir" / "nuevo.txt").read_text() == "contenido"


def test_write_file_traversal(sandbox):
    result = linux_server.write_file("../../tmp/evil.txt", "bad")
    assert result["ok"] is False


def test_list_dir_ok(sandbox):
    (sandbox / "a.txt").write_text("a")
    (sandbox / "subdir").mkdir()
    result = linux_server.list_dir(".")
    assert result["ok"] is True
    names = [e["name"] for e in result["data"]]
    assert "a.txt" in names
    assert "subdir" in names


def test_list_dir_not_a_dir(sandbox):
    (sandbox / "f.txt").write_text("x")
    result = linux_server.list_dir("f.txt")
    assert result["ok"] is False


def test_file_exists_true(sandbox):
    (sandbox / "exists.txt").write_text("x")
    result = linux_server.file_exists("exists.txt")
    assert result["ok"] is True
    assert result["data"]["exists"] is True


def test_file_exists_false(sandbox):
    result = linux_server.file_exists("ghost.txt")
    assert result["ok"] is True
    assert result["data"]["exists"] is False


def test_run_command_blocked(sandbox):
    result = linux_server.run_command("rm -rf /")
    assert result["ok"] is False
    assert "no permitido" in result["error"].lower()
