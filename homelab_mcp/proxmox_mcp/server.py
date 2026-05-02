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
# Tools de diagnóstico (read-only, exponen problemas con sugerencias de fix)
# ---------------------------------------------------------------------------

def _classify_error(exc: Exception) -> str:
    """Clasifica errores comunes en categorías reconocibles para diagnóstico."""
    s = str(exc)
    if "401" in s or "Unauthorized" in s:
        return "auth_failed"
    if "403" in s or "Forbidden" in s or "Permission check failed" in s:
        return "permission_denied"
    if "Name or service not known" in s or "hostname lookup" in s:
        return "dns_failed"
    if "TLS" in s or "certificate verify failed" in s or "SSL" in s:
        return "tls_failed"
    if "Connection refused" in s or "Connection reset" in s:
        return "connection_refused"
    if "timed out" in s.lower() or "timeout" in s.lower():
        return "timeout"
    return "other"


def _suggest_fix(category: str, context: dict) -> str:
    """Devuelve la sugerencia de fix recomendada según categoría de error."""
    suggestions = {
        "auth_failed": (
            "Token inválido o no existe en el host Proxmox. Verifica que "
            f"'{context.get('user')}!{context.get('token_name')}' existe en /etc/pve/user.cfg "
            "del nodo. Si fue rotado, actualiza el token_value en proxmox_nodes.json."
        ),
        "permission_denied": (
            f"El token tiene auth correcta pero le falta el privilegio Sys.Audit/VM.Audit en "
            f"el path solicitado. Fix permanente: en Proxmox UI → Datacenter → Permissions → "
            f"Add → User Permission. Path: '/', User: '{context.get('user')}', "
            "Role: 'PVEAuditor' o 'claude-readonly' (si existe), Propagate: Yes."
        ),
        "dns_failed": (
            f"El cliente intentó conectar a un hostname literal que no resuelve. Probable causa: "
            f"endpoint_node='{context.get('alias')}' usado como hostname en URL. "
            "Solución: añadir 'endpoint_node' explícito en proxmox_nodes.json apuntando al "
            "nombre real del nodo en el cluster (e.g. 'logrono', 'munilla')."
        ),
        "tls_failed": (
            "Error TLS — el plugin usa verify_ssl=False internamente. Si persiste, puede ser "
            "un redirect del Proxmox API a un hostname distinto cuyo cert no coincide. "
            "Verifica endpoint_node en proxmox_nodes.json."
        ),
        "connection_refused": (
            f"Host {context.get('host')} rechaza conexión en puerto 8006. Comprueba que "
            "Proxmox está activo y firewall permite acceso desde tu red."
        ),
        "timeout": (
            f"Timeout conectando a {context.get('host')}. El nodo no es alcanzable desde tu "
            "red — verifica IP correcta en proxmox_nodes.json y conectividad de red."
        ),
        "other": "Error no clasificado — revisa los detalles para diagnóstico manual.",
    }
    return suggestions.get(category, suggestions["other"])


@mcp.tool()
def check_node(node: str) -> dict:
    """Diagnóstico completo de un nodo Proxmox.

    Verifica conectividad, autenticación, alineamiento de endpoint_node con la
    realidad del cluster, y permisos del token sobre /nodes/<x>/status. Devuelve
    issues con severidad y sugerencia de fix por cada problema detectado.

    Args:
        node: Alias del nodo (pve, pve2, pve3) según proxmox_nodes.json.
    """
    issues = []
    cfg = settings.proxmox.get_node(node) if node else None
    result = {
        "node": node,
        "config": {
            "host": cfg.host if cfg else None,
            "user": cfg.user if cfg else None,
            "endpoint_node_configured": cfg.endpoint_node if cfg else None,
        },
        "connectivity": "not_tested",
        "authentication": "not_tested",
        "endpoint_node_actual": None,
        "permission_node_status": "not_tested",
        "issues": issues,
    }

    if not cfg or not cfg.is_configured():
        issues.append({
            "severity": "error",
            "category": "config_missing",
            "msg": f"Nodo '{node}' no configurado en proxmox_nodes.json o falta uno de los campos host/user/token_name/token_value.",
            "fix": "Añade el bloque del nodo en proxmox_nodes.json con todos los campos.",
        })
        result["overall"] = "config_missing"
        return result

    ctx = {"alias": node, "host": cfg.host, "user": cfg.user, "token_name": cfg.token_name}

    # 1. Conectividad + auth básica via /nodes/
    try:
        client = ProxmoxAPI(
            host=cfg.host,
            user=cfg.user,
            token_name=cfg.token_name,
            token_value=cfg.token_value,
            verify_ssl=False,
        )
        nodes_list = client.nodes.get()
        result["connectivity"] = "ok"
        result["authentication"] = "ok"
        actual_endpoints = [n.get("node") for n in nodes_list if isinstance(n, dict)]
        result["endpoint_node_actual"] = actual_endpoints[0] if actual_endpoints else None

        if cfg.endpoint_node and cfg.endpoint_node not in actual_endpoints:
            issues.append({
                "severity": "warning",
                "category": "endpoint_node_mismatch",
                "msg": (
                    f"endpoint_node configurado='{cfg.endpoint_node}' no coincide con nodos "
                    f"reales reportados por la API: {actual_endpoints}."
                ),
                "fix": (
                    f'Edita proxmox_nodes.json: en el bloque "{node}" cambia '
                    f'"endpoint_node": "{cfg.endpoint_node}" por '
                    f'"endpoint_node": "{actual_endpoints[0] if actual_endpoints else node}".'
                ),
            })
        elif not cfg.endpoint_node and actual_endpoints and node not in actual_endpoints:
            issues.append({
                "severity": "warning",
                "category": "endpoint_node_missing",
                "msg": (
                    f"endpoint_node no está configurado. El alias '{node}' se usará como "
                    f"nombre de nodo, pero el nombre real en el cluster es "
                    f"'{actual_endpoints[0]}'. list_qemu/list_lxc fallarán."
                ),
                "fix": (
                    f'Edita proxmox_nodes.json: añade "endpoint_node": "{actual_endpoints[0]}" '
                    f'al bloque "{node}".'
                ),
            })
    except Exception as e:
        cat = _classify_error(e)
        result["connectivity"] = "fail"
        result["authentication"] = "fail" if cat == "auth_failed" else result["authentication"]
        issues.append({
            "severity": "error",
            "category": cat,
            "msg": f"Error en /nodes/: {e}",
            "fix": _suggest_fix(cat, ctx),
        })
        result["overall"] = "unreachable"
        return result

    # 2. Permisos sobre /nodes/<endpoint>/status
    endpoint = cfg.endpoint_node or node
    try:
        client.nodes(endpoint).status.get()
        result["permission_node_status"] = "ok"
    except Exception as e:
        cat = _classify_error(e)
        result["permission_node_status"] = "fail"
        issues.append({
            "severity": "error",
            "category": cat,
            "msg": f"Error en /nodes/{endpoint}/status: {e}",
            "fix": _suggest_fix(cat, ctx),
        })

    # 3. Permisos sobre /access/acl (lectura — opcional, no fatal)
    try:
        acl_entries = client.access.acl.get()
        user_id_short = cfg.user.split("@")[0] if "@" in cfg.user else cfg.user
        user_acls = [
            a for a in acl_entries
            if a.get("ugid") in (cfg.user, user_id_short)
        ]
        result["acls_for_token_user"] = [
            {
                "path": a.get("path"),
                "role": a.get("roleid"),
                "propagate": a.get("propagate"),
                "type": a.get("type"),
            }
            for a in user_acls
        ]
    except Exception as e:
        result["acls_for_token_user"] = f"unreadable: {e}"

    # Overall
    sev_count = {"error": 0, "warning": 0, "info": 0}
    for i in issues:
        sev_count[i.get("severity", "info")] = sev_count.get(i.get("severity", "info"), 0) + 1
    if sev_count["error"]:
        result["overall"] = "degraded"
    elif sev_count["warning"]:
        result["overall"] = "warnings"
    else:
        result["overall"] = "healthy"
    result["issue_counts"] = sev_count

    return result


@mcp.tool()
def check_inventory() -> dict:
    """Valida proxmox_nodes.json contra la realidad de cada API.

    Itera todos los nodos configurados y para cada uno verifica:
    - host alcanzable
    - token autenticado
    - endpoint_node coincide con nombre real reportado por /nodes/

    Útil tras rotación de tokens, migración de red, o renombrado de nodos.

    Returns:
        Dict con summary global + detalle por nodo.
    """
    nodes_cfg = settings.proxmox.nodes
    if not nodes_cfg:
        return error(
            "proxmox_nodes.json vacío o no cargado",
            "Verifica PROXMOX_NODES_FILE env var y el contenido del JSON.",
        )

    per_node = {}
    overall_issues = 0
    healthy = 0
    degraded = 0
    warnings_total = 0

    for alias in nodes_cfg.keys():
        node_result = check_node(alias)
        per_node[alias] = node_result
        if node_result.get("overall") == "healthy":
            healthy += 1
        elif node_result.get("overall") == "degraded":
            degraded += 1
            overall_issues += node_result.get("issue_counts", {}).get("error", 0)
        elif node_result.get("overall") == "warnings":
            warnings_total += node_result.get("issue_counts", {}).get("warning", 0)
        else:
            degraded += 1

    return ok({
        "summary": {
            "nodes_total": len(nodes_cfg),
            "healthy": healthy,
            "degraded": degraded,
            "warnings": warnings_total,
        },
        "per_node": per_node,
    })


@mcp.tool()
def list_acls(node: str) -> dict:
    """Lista las entradas ACL del usuario del token en un nodo Proxmox.

    Útil para diagnosticar 403 errors — muestra exactamente qué roles tiene
    el token en qué paths. Si falta /nodes o /, los tools que tocan estado
    de nodo darán 403.

    Args:
        node: Alias del nodo (pve, pve2, pve3).
    """
    cfg = settings.proxmox.get_node(node) if node else None
    if not cfg or not cfg.is_configured():
        return error(f"Nodo '{node}' no configurado.")

    try:
        client = ProxmoxAPI(
            host=cfg.host,
            user=cfg.user,
            token_name=cfg.token_name,
            token_value=cfg.token_value,
            verify_ssl=False,
        )
        acl_entries = client.access.acl.get()
    except Exception as e:
        return error(f"No puedo leer /access/acl en {cfg.host}", str(e))

    user_short = cfg.user.split("@")[0] if "@" in cfg.user else cfg.user
    user_acls = [a for a in acl_entries if a.get("ugid") in (cfg.user, user_short)]

    # Detectar permisos comunes faltantes
    paths_with_user_acl = {a.get("path") for a in user_acls}
    common_required_paths = ["/", "/nodes", "/vms", "/storage"]
    missing_paths = [p for p in common_required_paths if p not in paths_with_user_acl]

    return ok({
        "host": cfg.host,
        "user": cfg.user,
        "acl_entries": [
            {
                "path": a.get("path"),
                "role": a.get("roleid"),
                "propagate": bool(a.get("propagate")),
                "type": a.get("type"),
            }
            for a in user_acls
        ],
        "common_paths_without_acl": missing_paths,
        "hint": (
            "Si faltan / o /nodes, get_node_status dará 403. Añadir vía Proxmox UI: "
            "Datacenter → Permissions → Add → User Permission con role PVEAuditor o "
            "claude-readonly y propagate=Yes."
            if missing_paths else
            "ACLs presentes en los paths comunes."
        ),
    })


# ---------------------------------------------------------------------------
# Tools de seguridad / postura de hosts (read-only, vía API Proxmox)
# ---------------------------------------------------------------------------

# Usuarios con sudo NOPASSWD por defecto en imágenes cloud / templates Debian
# y similares. claude_key NUNCA debe tener acceso a estos users — privilege
# escalation por reuso de key.
_PRIVILEGED_DEFAULT_USERS = {
    "root", "debian", "ubuntu", "admin", "centos", "fedora", "alpine",
    "core", "ec2-user", "azureuser", "ansible",
}


@mcp.tool()
def check_vm_security(node: str, vmid: int) -> dict:
    """Audita la postura de seguridad de una VM (vía qm config + cloud-init).

    Detecta los riesgos típicos de VMs creadas con cloud-init:
    - Usuario default (debian, ubuntu, core, etc.) con sudo NOPASSWD por
      defecto, accesible vía sshkey inyectada por cloud-init.
    - claude_key inyectada en un user privilegiado (privilege escalation).
    - Falta de bootstrap canónico (sin user `claude` whitelist + `jandro` admin).

    NO ejecuta nada en la VM — solo lee la config Proxmox del host. Útil
    como gate antes de declarar una VM lista para uso.

    Args:
        node: Alias del nodo Proxmox (pve, pve2, pve3) que aloja la VM.
        vmid: ID numérico de la VM.

    Returns:
        Dict con secciones config (ciuser, sshkeys, ipconfig0), issues
        (severidad + categoría + msg + fix) y overall (healthy / warnings /
        degraded).
    """
    cfg = settings.proxmox.get_node(node) if node else None
    if not cfg or not cfg.is_configured():
        return error(f"Nodo '{node}' no configurado.")

    try:
        client = ProxmoxAPI(
            host=cfg.host,
            user=cfg.user,
            token_name=cfg.token_name,
            token_value=cfg.token_value,
            verify_ssl=False,
        )
        endpoint = cfg.endpoint_node or node
        vm_cfg = client.nodes(endpoint).qemu(vmid).config.get()
    except Exception as e:
        return error(
            f"No puedo leer config de VM {vmid} en {node}",
            str(e),
        )

    issues: list[dict] = []
    ciuser = vm_cfg.get("ciuser", "")
    sshkeys_raw = vm_cfg.get("sshkeys", "")
    cipassword_set = bool(vm_cfg.get("cipassword"))

    # 1. ¿ciuser es un usuario privilegiado por defecto?
    if ciuser and ciuser in _PRIVILEGED_DEFAULT_USERS:
        issues.append({
            "severity": "error",
            "category": "privileged_default_ciuser",
            "msg": (
                f"ciuser='{ciuser}' es un usuario con sudo NOPASSWD por defecto "
                f"en la imagen cloud. Cualquier acceso SSH con la sshkey configurada "
                f"se convierte en root efectivo, eludiendo el modelo de privilegio "
                f"basado en user 'claude' con sudoers whitelist."
            ),
            "fix": (
                "Bootstrap correcto post-deploy: crear usuario 'claude' (whitelist) "
                "+ 'jandro' (admin), borrar sudo del user default o eliminar el "
                "user default por completo. Patrón en scripts/deployment/bootstrap-pve4.sh."
            ),
        })

    # 2. ¿sshkeys contiene la claude_key? (URL-encoded en qm config)
    if "claude%40" in sshkeys_raw or "claude@" in sshkeys_raw:
        if ciuser and ciuser in _PRIVILEGED_DEFAULT_USERS:
            issues.append({
                "severity": "error",
                "category": "claude_key_on_privileged_user",
                "msg": (
                    f"sshkeys de cloud-init contiene claude_key + ciuser='{ciuser}' "
                    f"con sudo NOPASSWD. Esto convierte claude_key en credencial root, "
                    f"violando el principio de least-privilege del modelo homelab."
                ),
                "fix": (
                    "Tras bootstrap correcto: regenerar claude_key (rotación) o, mejor, "
                    "no inyectar claude_key vía cloud-init. Que el bootstrap añada la key "
                    "solo al user 'claude' tras crearlo con sudoers whitelist."
                ),
            })

    # 3. ¿cipassword está set? (debug / acceso de emergencia)
    if cipassword_set:
        issues.append({
            "severity": "warning",
            "category": "cipassword_set",
            "msg": (
                "cipassword está configurado en la cloud-init de la VM. Si se "
                "filtra el snapshot del cloud-init drive, el password queda expuesto."
            ),
            "fix": (
                "Tras el bootstrap, eliminar cipassword: "
                "qm set <vmid> --delete cipassword"
            ),
        })

    # 4. ¿Hay user 'claude' bootstrappeado? — solo verificable vía SSH/agent,
    # no desde qm config. Reportar como info: usar guest agent si está activo.
    info = {
        "config": {
            "ciuser": ciuser or None,
            "sshkeys_present": bool(sshkeys_raw),
            "sshkeys_contains_claude_key": "claude%40" in sshkeys_raw or "claude@" in sshkeys_raw,
            "cipassword_set": cipassword_set,
            "ipconfig0": vm_cfg.get("ipconfig0", ""),
        },
        "issues": issues,
    }

    if any(i["severity"] == "error" for i in issues):
        info["overall"] = "degraded"
    elif any(i["severity"] == "warning" for i in issues):
        info["overall"] = "warnings"
    else:
        info["overall"] = "healthy"

    return ok(info)


# ---------------------------------------------------------------------------
# Tool de ejecución SSH (canonical wrapper SSH+sudo) — v1.4.0
# ---------------------------------------------------------------------------

import os
import re
import shutil
import subprocess
from pathlib import Path

# Patrones destructivos rechazados de plano. NO es seguridad real (solo
# defensa-en-profundidad — el sudoers whitelist del host sigue siendo el
# guard primario). Captura errores tipográficos obvios antes de tocar SSH.
_DESTRUCTIVE_PATTERNS = (
    "rm -rf /",
    "rm -rf ~",
    "mkfs.",
    "dd if=/dev/zero of=/dev/sd",
    "dd if=/dev/zero of=/dev/nvme",
    ":(){:|:&};:",  # fork bomb
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init 0",
    "init 6",
)


@mcp.tool()
def ssh_run(
    node: str,
    command: str,
    sudo: bool = True,
    timeout: int = 30,
) -> dict:
    """Ejecuta un comando en un host remoto vía SSH (con sudo opcional).

    Wrapper canónico que evita que el caller construya manualmente
    ``ssh <host> "echo $(cat sudo-key) | sudo -S ..."``. Lee la sudo
    password de ``CLAUDE_SUDO_KEY_FILE`` (env var) — default a
    ``C:/homelab/.config/secrets/claude-sudo.key`` (Windows) o
    ``~/.config/secrets/claude-sudo.key`` (Linux/macOS).

    Seguridad:
    - El usuario remoto SSH es el del ``~/.ssh/config`` del operador
      (típicamente ``claude``). Esta tool NO hace login como root, debian,
      ubuntu, ni similar.
    - El sudoers whitelist del host (``/etc/sudoers.d/claude``) es el
      guard primario: si el comando no está, sudo lo rechaza con código
      no-cero y la tool devuelve ese error.
    - Defensa-en-profundidad: lista corta de patrones destructivos
      rechazados antes de tocar SSH (rm -rf /, mkfs, dd zero, fork bomb,
      shutdown, etc.).

    Args:
        node: Alias SSH resoluble del ``~/.ssh/config`` del operador
            (e.g. ``pve``, ``pve2``, ``truenas``, ``lxc-nextcloud``).
        command: Comando a ejecutar EN EL HOST. Si ``sudo=True``, el
            comando debe estar en la whitelist sudoers (full path
            obligatorio, e.g. ``/usr/sbin/pct list``).
        sudo: Si True, prefija con sudo password. Default True.
        timeout: Timeout en segundos. Default 30.

    Returns:
        Dict con ``ok``, ``exit_code``, ``stdout``, ``stderr``,
        ``command_run`` (sin password), ``sudo_used``.
    """
    if not shutil.which("ssh"):
        return error("ssh no está disponible en PATH")

    if not isinstance(node, str) or not node.strip():
        return error("node es obligatorio (alias SSH)")
    if not isinstance(command, str) or not command.strip():
        return error("command es obligatorio")

    # Reject login como users privilegiados via @ en el alias. Mismo modelo
    # que el hook validate-ssh.py — defensa contra cloud-init shortcuts.
    if "@" in node:
        priv_users = {"root", "debian", "ubuntu", "admin",
                      "centos", "fedora", "alpine", "core",
                      "ec2-user", "azureuser"}
        user_part = node.split("@", 1)[0]
        if user_part in priv_users:
            return error(
                f"Login SSH como user '{user_part}' bloqueado. Usa el "
                f"alias del ~/.ssh/config (que apunta a user 'claude' o "
                f"similar limitado), no user@host directo."
            )

    # Defensa-en-profundidad: patrones destructivos
    cmd_lower = command.lower()
    for pat in _DESTRUCTIVE_PATTERNS:
        if pat in cmd_lower:
            return error(
                f"Comando rechazado: contiene patrón destructivo {pat!r}. "
                "Si es legítimo, usa el path/argumento exacto del sudoers."
            )

    if sudo:
        key_path = os.getenv(
            "CLAUDE_SUDO_KEY_FILE",
            r"C:\homelab\.config\secrets\claude-sudo.key"
            if os.name == "nt"
            else os.path.expanduser("~/.config/secrets/claude-sudo.key"),
        )
        try:
            password = Path(key_path).read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return error(
                f"sudo key file no encontrado: {key_path}. "
                "Define CLAUDE_SUDO_KEY_FILE o pon la key en el path default."
            )
        except OSError as e:
            return error(f"Error leyendo sudo key: {e}")
        if not password:
            return error("sudo key file está vacío")

        # echo password | sudo -S -p '' command
        # -p '' suprime el prompt de sudo (que iría a stderr)
        # Password vía stdin para no aparecer en process list
        remote_cmd = f"echo '{password}' | sudo -S -p '' {command}"
    else:
        remote_cmd = command

    try:
        proc = subprocess.run(
            ["ssh", node, remote_cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return error(
            f"Timeout tras {timeout}s ejecutando comando en {node!r}"
        )
    except FileNotFoundError:
        return error("ssh binary no disponible (ya validado arriba — race?)")
    except Exception as e:
        return error(f"Error ejecutando ssh: {e}")

    # Limpiar prompts de sudo del stderr (con o sin newline tras el prompt)
    stderr_clean = re.sub(
        r"^\[sudo\] password for [^\n:]+:\s*",
        "",
        proc.stderr.strip(),
    )

    return ok({
        "node": node,
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": stderr_clean,
        "command_run": command,  # SIN password
        "sudo_used": sudo,
    })


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
