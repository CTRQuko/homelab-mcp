"""Tests del parser de CLAUDE.md."""
import json
import pytest
from pathlib import Path

from homelab_mcp.utils.claude_md_parser import (
    extract_proxmox_nodes,
    extract_token_values,
    build_proxmox_config,
    generate_env_content,
    generate_nodes_json,
)


SAMPLE_CLAUDE_MD = """\
## 3. Acceso Proxmox -- 3 capas

### Capa 1: API Proxmox (PRIMERA OPCION)

| Nodo | IP:Puerto | Token ID | Endpoint node | Estado |
|------|-----------|----------|---------------|--------|
| pve | `10.0.0.1:8006` | `testuser@pam!test-token` | `node1` | OK |
| pve2 | `10.0.0.2:8006` | `testuser@pam!test-token` | `pve2` | OK |
| pve3 | `10.0.0.3:8006` | `testuser@pam!other-token` | `node3` | OK |
| pve4 | `10.0.0.4:8006` | -- | -- | offline |
"""

SAMPLE_SECRETS = """\
pve-node1

testuser@pam!test-token
aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee01

pve2
testuser@pam!test-token
aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee02

pve 3
testuser@pam!other-token
aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee03
"""


# ---------------------------------------------------------------------------
# extract_proxmox_nodes
# ---------------------------------------------------------------------------

def test_extracts_three_active_nodes():
    nodes = extract_proxmox_nodes(SAMPLE_CLAUDE_MD)
    assert len(nodes) == 3


def test_skips_offline_node():
    nodes = extract_proxmox_nodes(SAMPLE_CLAUDE_MD)
    aliases = [n["alias"] for n in nodes]
    assert "pve4" not in aliases


def test_extracts_correct_ips():
    nodes = extract_proxmox_nodes(SAMPLE_CLAUDE_MD)
    by_alias = {n["alias"]: n for n in nodes}
    assert by_alias["pve"]["host"] == "10.0.0.1"
    assert by_alias["pve2"]["host"] == "10.0.0.2"
    assert by_alias["pve3"]["host"] == "10.0.0.3"


def test_extracts_token_id_parts():
    nodes = extract_proxmox_nodes(SAMPLE_CLAUDE_MD)
    by_alias = {n["alias"]: n for n in nodes}
    assert by_alias["pve"]["user"] == "testuser@pam"
    assert by_alias["pve"]["token_name"] == "test-token"
    assert by_alias["pve3"]["token_name"] == "other-token"


def test_extracts_endpoint_nodes():
    nodes = extract_proxmox_nodes(SAMPLE_CLAUDE_MD)
    by_alias = {n["alias"]: n for n in nodes}
    assert by_alias["pve"]["endpoint_node"] == "node1"
    assert by_alias["pve3"]["endpoint_node"] == "node3"


def test_empty_md_returns_empty():
    nodes = extract_proxmox_nodes("# Nothing here")
    assert nodes == []


# ---------------------------------------------------------------------------
# extract_token_values
# ---------------------------------------------------------------------------

def test_extracts_tokens_from_secrets(tmp_path):
    secrets = tmp_path / "apispve.md"
    secrets.write_text(SAMPLE_SECRETS)
    entries = extract_token_values(secrets)
    assert len(entries) == 3
    # Los entries tienen label, token_id, token_value
    assert entries[0]["label"] == "pve-node1"
    assert entries[0]["token_value"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee01"
    assert entries[1]["label"] == "pve2"
    assert entries[2]["token_value"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee03"


def test_missing_secrets_returns_empty(tmp_path):
    tokens = extract_token_values(tmp_path / "nonexistent.md")
    assert tokens == []


# ---------------------------------------------------------------------------
# build_proxmox_config
# ---------------------------------------------------------------------------

def test_build_config_combines_nodes_and_tokens(tmp_path):
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(SAMPLE_CLAUDE_MD)
    secrets = tmp_path / "apispve.md"
    secrets.write_text(SAMPLE_SECRETS)

    config = build_proxmox_config(claude, secrets)
    assert "pve" in config["nodes"]
    assert "pve2" in config["nodes"]
    assert "pve3" in config["nodes"]
    assert config["primary"]["alias"] == "pve"
    # Token values filled from secrets (each node has its own)
    assert config["nodes"]["pve"]["token_value"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee01"
    assert config["nodes"]["pve2"]["token_value"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee02"
    assert config["nodes"]["pve3"]["token_value"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeee03"
    # pve y pve2 tienen token_id idéntico pero valores distintos
    assert config["nodes"]["pve"]["token_value"] != config["nodes"]["pve2"]["token_value"]


def test_build_config_without_secrets(tmp_path):
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(SAMPLE_CLAUDE_MD)

    config = build_proxmox_config(claude, None)
    assert len(config["nodes"]) == 3
    # Sin secrets, token_value vacío
    assert config["nodes"]["pve"]["token_value"] == ""


# ---------------------------------------------------------------------------
# generate_env_content
# ---------------------------------------------------------------------------

def test_generate_env_content_has_primary(tmp_path):
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(SAMPLE_CLAUDE_MD)
    secrets = tmp_path / "apispve.md"
    secrets.write_text(SAMPLE_SECRETS)

    env = generate_env_content(claude, secrets)
    assert "PROXMOX_HOST=10.0.0.1" in env
    assert "PROXMOX_USER=testuser@pam" in env
    assert "PROXMOX_TOKEN_NAME=test-token" in env
    assert "PROXMOX_NODES_FILE=" in env


# ---------------------------------------------------------------------------
# generate_nodes_json
# ---------------------------------------------------------------------------

def test_generate_nodes_json_is_valid(tmp_path):
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(SAMPLE_CLAUDE_MD)
    secrets = tmp_path / "apispve.md"
    secrets.write_text(SAMPLE_SECRETS)

    raw = generate_nodes_json(claude, secrets)
    parsed = json.loads(raw)
    assert "pve" in parsed
    assert parsed["pve"]["endpoint_node"] == "node1"
    assert parsed["pve2"]["host"] == "10.0.0.2"
