"""Configuración centralizada leída desde .env."""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv
import os

# Carga .env desde la raíz del proyecto (un nivel arriba de homelab_mcp/)
_BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BASE_DIR / ".env", override=False)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Proxmox (single-node + multi-node)
# ---------------------------------------------------------------------------

@dataclass
class ProxmoxNodeConfig:
    """Configuración de un nodo Proxmox individual."""
    host: str = ""
    user: str = ""
    token_name: str = ""
    token_value: str = ""
    endpoint_node: str = ""

    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.token_name and self.token_value)


@dataclass
class ProxmoxSettings:
    """Configuración Proxmox con soporte single-node y multi-nodo.

    Single-node: usa PROXMOX_HOST, PROXMOX_USER, etc.
    Multi-nodo: usa PROXMOX_NODES_FILE apuntando a un JSON.
    """
    host: str = field(default_factory=lambda: os.getenv("PROXMOX_HOST", ""))
    user: str = field(default_factory=lambda: os.getenv("PROXMOX_USER", ""))
    token_name: str = field(default_factory=lambda: os.getenv("PROXMOX_TOKEN_NAME", ""))
    token_value: str = field(default_factory=lambda: os.getenv("PROXMOX_TOKEN_VALUE", ""))
    _nodes: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        nodes_file = os.getenv("PROXMOX_NODES_FILE", "")
        if nodes_file:
            self._load_nodes(nodes_file)

    def _load_nodes(self, nodes_file: str) -> None:
        """Carga nodos desde JSON (ruta relativa a _BASE_DIR o absoluta)."""
        path = Path(nodes_file)
        if not path.is_absolute():
            path = _BASE_DIR / path
        if not path.exists():
            log.warning("PROXMOX_NODES_FILE=%s no encontrado", path)
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            for alias, cfg in raw.items():
                self._nodes[alias] = ProxmoxNodeConfig(
                    host=cfg.get("host", ""),
                    user=cfg.get("user", self.user),
                    token_name=cfg.get("token_name", ""),
                    token_value=cfg.get("token_value", ""),
                    endpoint_node=cfg.get("endpoint_node", alias),
                )
        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            log.warning("Error parseando PROXMOX_NODES_FILE: %s", e)

    def is_configured(self) -> bool:
        return bool(self.host and self.user and self.token_name and self.token_value)

    @property
    def nodes(self) -> dict[str, ProxmoxNodeConfig]:
        return dict(self._nodes)

    @property
    def available_nodes(self) -> list[str]:
        """Aliases de nodos disponibles (con token configurado)."""
        return [a for a, n in self._nodes.items() if n.is_configured()]

    def get_node(self, alias: str) -> ProxmoxNodeConfig | None:
        """Devuelve config de un nodo por alias.

        Busca en _nodes primero, luego cae al single-node config si coincide
        el endpoint_node o el host.
        """
        if alias in self._nodes:
            return self._nodes[alias]
        # Buscar por endpoint_node (e.g. "logrono", "munilla")
        for node_cfg in self._nodes.values():
            if node_cfg.endpoint_node == alias:
                return node_cfg
        # Fallback: single-node config
        return None

    def get_node_or_default(self, node_hint: str) -> ProxmoxNodeConfig:
        """Devuelve config de nodo, o el default single-host."""
        found = self.get_node(node_hint)
        if found and found.is_configured():
            return found
        return ProxmoxNodeConfig(
            host=self.host,
            user=self.user,
            token_name=self.token_name,
            token_value=self.token_value,
            endpoint_node=node_hint,
        )


# ---------------------------------------------------------------------------
# Otros MCPs
# ---------------------------------------------------------------------------

@dataclass
class LinuxSettings:
    base_path: Path = field(
        default_factory=lambda: Path(os.getenv("LINUX_BASE_PATH", "/srv/homelab")).resolve()
    )


@dataclass
class WindowsSettings:
    base_path: Path = field(
        default_factory=lambda: Path(os.getenv("WINDOWS_BASE_PATH", "C:/homelab")).resolve()
    )


@dataclass
class NpmSettings:
    base_path: Path = field(
        default_factory=lambda: Path(os.getenv("NPM_BASE_PATH", ".")).resolve()
    )


@dataclass
class PythonProjectsSettings:
    base_path: Path = field(
        default_factory=lambda: Path(os.getenv("PYTHON_BASE_PATH", ".")).resolve()
    )


@dataclass
class DockerSettings:
    host: str = field(default_factory=lambda: os.getenv("DOCKER_HOST", ""))


@dataclass
class Settings:
    proxmox: ProxmoxSettings = field(default_factory=ProxmoxSettings)
    linux: LinuxSettings = field(default_factory=LinuxSettings)
    windows: WindowsSettings = field(default_factory=WindowsSettings)
    npm: NpmSettings = field(default_factory=NpmSettings)
    python_projects: PythonProjectsSettings = field(default_factory=PythonProjectsSettings)
    docker: DockerSettings = field(default_factory=DockerSettings)
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


settings = Settings()
