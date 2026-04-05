"""Tests del Windows MCP."""
import pytest
from pathlib import Path

import homelab_mcp.windows_mcp.server as win_server


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Redirige el BASE del servidor al tmp_path."""
    monkeypatch.setattr(win_server, "BASE", tmp_path)
    return tmp_path


def test_read_file_ok(sandbox):
    f = sandbox / "test.txt"
    f.write_text("hola", encoding="utf-8")
    result = win_server.read_file("test.txt")
    assert result["ok"] is True
    assert result["data"] == "hola"


def test_read_file_traversal(sandbox):
    result = win_server.read_file("../../evil.txt")
    assert result["ok"] is False


def test_write_file_creates_dirs(sandbox):
    result = win_server.write_file("a/b/c.txt", "x")
    assert result["ok"] is True
    assert (sandbox / "a" / "b" / "c.txt").exists()


def test_write_file_traversal(sandbox):
    result = win_server.write_file("../../evil.txt", "bad")
    assert result["ok"] is False


def test_list_dir_ok(sandbox):
    (sandbox / "file.txt").write_text("x")
    (sandbox / "sub").mkdir()
    result = win_server.list_dir(".")
    assert result["ok"] is True
    names = [e["name"] for e in result["data"]]
    assert "file.txt" in names
    assert "sub" in names


def test_file_exists_true(sandbox):
    (sandbox / "e.txt").write_text("x")
    result = win_server.file_exists("e.txt")
    assert result["ok"] is True
    assert result["data"]["exists"] is True


def test_file_exists_false(sandbox):
    result = win_server.file_exists("missing.txt")
    assert result["ok"] is True
    assert result["data"]["exists"] is False


def test_ps_blocked_dangerous_verb(sandbox):
    result = win_server.run_powershell("Remove-Item C:\\Windows\\system32")
    assert result["ok"] is False


def test_ps_blocked_pipe(sandbox):
    result = win_server.run_powershell("Get-ChildItem | Remove-Item")
    assert result["ok"] is False


def test_ps_blocked_semicolon(sandbox):
    result = win_server.run_powershell("Get-Content foo.txt; Remove-Item foo.txt")
    assert result["ok"] is False


def test_ps_blocked_ampersand(sandbox):
    result = win_server.run_powershell("Get-ChildItem & Remove-Item foo")
    assert result["ok"] is False


def test_ps_blocked_subexpression(sandbox):
    result = win_server.run_powershell("Get-Content $(rm evil)")
    assert result["ok"] is False


def test_ps_blocked_invoke_expression(sandbox):
    result = win_server.run_powershell("Invoke-Expression 'rm -rf /'")
    assert result["ok"] is False


def test_ps_blocked_backtick(sandbox):
    result = win_server.run_powershell("Get-ChildItem `rm evil`")
    assert result["ok"] is False


def test_ps_blocked_unknown_verb(sandbox):
    result = win_server.run_powershell("Write-Host 'hello'")
    assert result["ok"] is False


def test_ps_allowed_verb_case_insensitive(sandbox):
    """Get-ChildItem funciona aunque se escriba en minúsculas."""
    # El test no ejecuta realmente PS, solo valida la whitelist
    allowed, _ = win_server._ps_allowed("get-childitem .")
    assert allowed is True


def test_ps_empty_command(sandbox):
    result = win_server.run_powershell("")
    assert result["ok"] is False
