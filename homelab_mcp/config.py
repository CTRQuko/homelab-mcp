"""Configuración centralizada leída desde .env."""
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, field_validator


# ---------------------------------------------------------------------------
# Schema validation para proxmox_nodes.json (v1.3.0)
# ---------------------------------------------------------------------------

_HOST_PATTERN = re.compile(r"^[a-zA-Z0-9.\-]+:\d{1,5}$")
_USER_PATTERN = re.compile(r"^[\w\-]+@[\w\-]+$")
_ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class _ProxmoxNodeRaw(BaseModel):
    """Schema de validación para entradas en proxmox_nodes.json.

    Aplica al cargar el archivo en `ProxmoxSettings._load_nodes`. Cada nodo
    que falle validación se skipea con warning explicativo (el resto carga).
    Si el JSON top-level es inválido, falla loud (raise) — el plugin reporta
    'degraded' a Mimir y el operador ve el error al boot, no en runtime.
    """
    host: str = Field(min_length=1)
    user: str = Field(min_length=1)
    token_name: str = Field(min_length=1)
    token_value: str = Field(min_length=20)
    endpoint_node: str = Field(min_length=1)

    @field_validator("host")
    @classmethod
    def _check_host(cls, v: str) -> str:
        if not _HOST_PATTERN.match(v):
            raise ValueError(
                f"host debe tener formato '<ip-o-hostname>:<port>'. Recibido: {v!r}"
            )
        port = int(v.rsplit(":", 1)[1])
        if not 1 <= port <= 65535:
            raise ValueError(f"port {port} fuera de rango 1-65535")
        return v

    @field_validator("user")
    @classmethod
    def _check_user(cls, v: str) -> str:
        if not _USER_PATTERN.match(v):
            raise ValueError(
                f"user debe tener formato '<user>@<realm>' (e.g. 'claude@pam'). "
                f"Recibido: {v!r}"
            )
        return v

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
        """Carga nodos desde JSON (ruta relativa a _BASE_DIR o absoluta).

        Validación (v1.3.0):
        - JSON malformado o top-level no-dict → ValueError (fail loud al boot).
        - Por nodo: schema Pydantic `_ProxmoxNodeRaw`. Errores → warning + skip
          ese nodo concreto (el resto del JSON sigue cargando).
        - `endpoint_node` ahora es REQUERIDO (antes default a alias, causaba
          fallos sutiles cuando alias != nombre real del nodo en el cluster).
        """
        path = Path(nodes_file)
        if not path.is_absolute():
            path = _BASE_DIR / path
        if not path.exists():
            log.warning("PROXMOX_NODES_FILE=%s no encontrado", path)
            return

        # Top-level — fail loud
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(
                f"PROXMOX_NODES_FILE inválido ({path}): {e}. "
                "Corrige el JSON antes de arrancar el plugin."
            ) from e

        if not isinstance(raw, dict):
            raise ValueError(
                f"PROXMOX_NODES_FILE debe contener un objeto JSON top-level "
                f"(dict de aliases), recibido {type(raw).__name__}."
            )

        # Per-node — validar uno a uno; warning + skip si inválido
        for alias, cfg in raw.items():
            if not isinstance(alias, str) or not _ALIAS_PATTERN.match(alias):
                log.warning(
                    "Alias %r ignorado: solo se permiten chars alphanumeric + -_",
                    alias,
                )
                continue
            if not isinstance(cfg, dict):
                log.warning(
                    "Nodo %r ignorado: el valor debe ser un dict, recibido %s",
                    alias,
                    type(cfg).__name__,
                )
                continue
            try:
                validated = _ProxmoxNodeRaw.model_validate(cfg)
            except ValidationError as e:
                log.warning(
                    "Nodo %r ignorado por config inválida:\n%s\n"
                    "Sugerencia: ejecutar tool check_inventory tras arreglar.",
                    alias,
                    e,
                )
                continue
            self._nodes[alias] = ProxmoxNodeConfig(
                host=validated.host,
                user=validated.user,
                token_name=validated.token_name,
                token_value=validated.token_value,
                endpoint_node=validated.endpoint_node,
            )

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
