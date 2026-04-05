"""Proxmox MCP — tools de lectura y control básico."""
import logging
from typing import Literal

from proxmoxer import ProxmoxAPI
from proxmoxer.core import ResourceException

from homelab_mcp.base import create_server
from homelab_mcp.config import settings
from homelab_mcp.utils.responses import error, needs_confirmation, ok

log = logging.getLogger(__name__)
mcp = create_server("homelab-proxmox")

_VM_TYPES = ("qemu", "lxc")


def _get_client(node_hint: str = "") -> tuple[ProxmoxAPI, str]:
    """Crea cliente Proxmox para un nodo específico.

    Args:
        node_hint: Alias del nodo (pve, pve2, pve3) o nombre de endpoint
                   (logrono, munilla). Si vacío, usa el default.

    Returns:
        Tupla (cliente_api, endpoint_node_name).
    """
    cfg = settings.proxmox
    node_cfg = cfg.get_node_or_default(node_hint) if node_hint else None

    if node_cfg and node_cfg.is_configured():
        client = ProxmoxAPI(
            host=node_cfg.host,
            user=node_cfg.user,
            token_name=node_cfg.token_name,
            token_value=node_cfg.token_value,
            verify_ssl=False,
        )
        return client, node_cfg.endpoint_node

    # Fallback single-host
    if not cfg.is_configured():
        raise RuntimeError(
            "Proxmox no configurado. Revisa PROXMOX_HOST/USER/TOKEN en .env "
            "o genera con: python -m homelab_mcp.utils.claude_md_parser"
        )
    client = ProxmoxAPI(
        host=cfg.host,
        user=cfg.user,
        token_name=cfg.token_name,
        token_value=cfg.token_value,
        verify_ssl=False,
    )
    return client, node_hint


def _call(fn):
    """Ejecuta fn y devuelve ok/error según resultado."""
    try:
        return ok(fn())
    except ResourceException as e:
        log.warning("Proxmox API error: %s", e)
        return error("Proxmox API error", str(e))
    except Exception as e:
        log.error("Error inesperado: %s", e)
        return error("Error de conexión", str(e))


# ---------------------------------------------------------------------------
# Tools de lectura
# ---------------------------------------------------------------------------

@mcp.tool()
def list_nodes(node: str = "") -> dict:
    """Lista todos los nodos visibles desde un host Proxmox.

    En modo multi-nodo, especifica el alias (pve, pve2, pve3) para
    conectar a ese host. Si vacío, usa el nodo por defecto.

    Args:
        node: Alias del nodo al que conectar (opcional).
    """
    def _fetch():
        p, _ = _get_client(node)
        return p.nodes.get()
    return _call(_fetch)


@mcp.tool()
def get_node_status(node: str) -> dict:
    """Estado del nodo: CPU, memoria, uptime, versión.

    Args:
        node: Alias del nodo (pve, pve2, pve3) o nombre endpoint (logrono, munilla).
    """
    def _fetch():
        p, endpoint = _get_client(node)
        return p.nodes(endpoint).status.get()
    return _call(_fetch)


@mcp.tool()
def list_qemu(node: str) -> dict:
    """Lista máquinas virtuales QEMU/KVM de un nodo.

    Args:
        node: Alias del nodo (pve, pve2, pve3).
    """
    def _fetch():
        p, endpoint = _get_client(node)
        return p.nodes(endpoint).qemu.get()
    return _call(_fetch)


@mcp.tool()
def list_lxc(node: str) -> dict:
    """Lista contenedores LXC de un nodo.

    Args:
        node: Alias del nodo (pve, pve2, pve3).
    """
    def _fetch():
        p, endpoint = _get_client(node)
        return p.nodes(endpoint).lxc.get()
    return _call(_fetch)


@mcp.tool()
def get_vm_status(node: str, vmid: int, vm_type: str = "lxc") -> dict:
    """Estado de una VM o LXC (cpu, mem, status, uptime).

    Args:
        node: Alias del nodo (pve, pve2, pve3).
        vmid: ID numérico de la VM/LXC.
        vm_type: "lxc" o "qemu".
    """
    if vm_type not in _VM_TYPES:
        return error(f"vm_type inválido: '{vm_type}'. Usa 'lxc' o 'qemu'.")

    def _fetch():
        p, endpoint = _get_client(node)
        if vm_type == "lxc":
            return p.nodes(endpoint).lxc(vmid).status.current.get()
        return p.nodes(endpoint).qemu(vmid).status.current.get()

    return _call(_fetch)


# ---------------------------------------------------------------------------
# Tools de acción (con validación explícita)
# ---------------------------------------------------------------------------

def _vm_action(
    node: str,
    vmid: int,
    vm_type: str,
    action: Literal["start", "stop", "reboot"],
    confirm: bool = False,
) -> dict:
    if not confirm:
        return needs_confirmation(f"{action}_vm", f"{vm_type}/{vmid}@{node}")

    if vm_type not in _VM_TYPES:
        return error(f"vm_type inválido: '{vm_type}'. Usa 'lxc' o 'qemu'.")

    def _exec():
        p, endpoint = _get_client(node)
        target = p.nodes(endpoint).lxc(vmid) if vm_type == "lxc" else p.nodes(endpoint).qemu(vmid)
        if action == "start":
            return target.status.start.post()
        elif action == "stop":
            return target.status.stop.post()
        else:
            return target.status.reboot.post()

    result = _call(_exec)
    if result["ok"]:
        result["data"] = {"action": action, "node": node, "vmid": vmid, "vm_type": vm_type}
    return result


@mcp.tool()
def start_vm(node: str, vmid: int, vm_type: str = "lxc", confirm: bool = False) -> dict:
    """Arranca una VM o LXC. REQUIERE confirm=True para ejecutar.

    Args:
        node: Nombre del nodo.
        vmid: ID de la VM/LXC.
        vm_type: "lxc" o "qemu".
        confirm: Debe ser True para ejecutar. Por defecto False (dry run).
    """
    return _vm_action(node, vmid, vm_type, "start", confirm=confirm)


@mcp.tool()
def stop_vm(node: str, vmid: int, vm_type: str = "lxc", confirm: bool = False) -> dict:
    """Para una VM o LXC (stop forzado). REQUIERE confirm=True para ejecutar.

    Args:
        node: Nombre del nodo.
        vmid: ID de la VM/LXC.
        vm_type: "lxc" o "qemu".
        confirm: Debe ser True para ejecutar. Por defecto False (dry run).
    """
    return _vm_action(node, vmid, vm_type, "stop", confirm=confirm)


@mcp.tool()
def restart_vm(node: str, vmid: int, vm_type: str = "lxc", confirm: bool = False) -> dict:
    """Reinicia una VM o LXC. REQUIERE confirm=True para ejecutar.

    Args:
        node: Nombre del nodo.
        vmid: ID de la VM/LXC.
        vm_type: "lxc" o "qemu".
        confirm: Debe ser True para ejecutar. Por defecto False (dry run).
    """
    return _vm_action(node, vmid, vm_type, "reboot", confirm=confirm)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
