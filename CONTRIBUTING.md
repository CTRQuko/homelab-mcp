# Contribuyendo

## Workflow

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/mi-cambio`
3. Haz tus cambios
4. Ejecuta tests: `pytest` (deben pasar todos)
5. Abre un PR con tests y documentacion

## Reglas

- `pytest` debe pasar al 100% antes de abrir PR
- No incluyas secrets, tokens ni autodeteccion agresiva de credenciales
- Documenta cambios en `CHANGELOG.md`
- Mantene el sandbox y las whitelists: no desactives validaciones de seguridad

## Setup de desarrollo

```bash
git clone https://github.com/TU-USUARIO/homelab-mcp.git
cd homelab-mcp
pip install -e ".[dev,test]"
pytest
```
