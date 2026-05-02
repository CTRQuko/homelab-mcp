# Changelog

## 1.2.0 (2026-05-02) — VM security audit tool

### Added

- **`check_vm_security(node, vmid)`** — audita postura de seguridad de una
  VM Proxmox vía `qm config` (sin tocar la VM). Detecta:
  - `ciuser` con sudo NOPASSWD por defecto en imágenes cloud (debian, ubuntu,
    core, ec2-user, etc.)
  - `claude_key` inyectada en un user privilegiado (privilege escalation
    por reuso de credencial)
  - `cipassword` set tras bootstrap (riesgo de leak por snapshot)

  Cada issue lleva categoría + sugerencia de fix accionable (bootstrap
  canónico, eliminar cipassword tras setup, etc.).

  Read-only — usa solo el token Proxmox existente.

### Diseño

Complemento natural de `check_node` y `check_inventory` (v1.1.0). Cubre
la pregunta operativa: "¿esta VM nueva está bootstrappeada según el modelo
homelab o es un cloud-init shortcut con sudo libre?"

Caso de uso: detectado el 2026-05-02 — VM 106 AdGuard se desplegó con
`ciuser=debian` + claude_key en `/home/debian/.ssh/authorized_keys` + sudo
NOPASSWD. Resultado: claude_key efectivamente concedía root al saltar el
bootstrap canónico. Ahora detectable proactivamente con este tool.

## 1.1.0 (2026-05-02) — diagnostic tools

### Added

- **`check_node(node)`** — diagnóstico end-to-end de un nodo Proxmox.
  Verifica conectividad, autenticación, alineamiento `endpoint_node` ↔ nombre
  real del cluster, y permisos sobre `/nodes/<x>/status`. Cada issue detectado
  lleva categoría (`auth_failed`, `permission_denied`, `dns_failed`,
  `tls_failed`, `endpoint_node_mismatch`, etc.) + sugerencia de fix concreta.
  Diagnóstico canónico para errores 401/403/500 cuyo origen no es obvio.

- **`check_inventory()`** — valida `proxmox_nodes.json` contra la realidad
  de cada API. Itera todos los nodos configurados, ejecuta `check_node` en
  cada uno y devuelve summary global + detalle por nodo. Detecta divergencia
  alias ↔ endpoint_node real, causa típica de errores tras migración de red
  o renombrado de nodos.

- **`list_acls(node)`** — lista entradas ACL del usuario del token en un
  nodo. Detecta gaps comunes (falta ACL en `/`, `/nodes`, `/vms`, `/storage`)
  y devuelve hint con corrección manual exacta vía Proxmox UI. Útil para
  diagnosticar 403 Forbidden por privilegios faltantes.

### Diseño

Los 3 tools son **read-only** y se apoyan en los privilegios que ya tiene
el token; no escalan permisos. Patrón: el plugin diagnostica y sugiere fix,
el operador (o un agente con privilegios suficientes) ejecuta la corrección.
Mimir como capa de tools — no rules baked en CLAUDE.md ni scripts ad-hoc.

### Tests

- 83 passing — baseline sin cambios.

## 1.0.0 (2026-04-05)

Primera release publica.

- **6 MCPs**: Proxmox (multi-nodo), Linux, Windows, Docker, npm, Python
- **Auto-config** desde `CLAUDE.md` + fichero de secrets
- **Seguridad**: sandbox de rutas, whitelist de comandos, PowerShell restringido, patron de confirmacion
- **83 tests** cubriendo todos los MCPs, utilidades y configuracion
- **CI** con GitHub Actions (pytest en Python 3.11)
