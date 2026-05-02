# Changelog

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
