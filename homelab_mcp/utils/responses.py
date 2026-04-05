"""Helpers para respuestas estructuradas uniformes entre MCPs."""
from typing import Any


def ok(data: Any) -> dict:
    """Respuesta exitosa."""
    return {"ok": True, "data": data}


def error(message: str, details: str = "") -> dict:
    """Respuesta de error."""
    result: dict = {"ok": False, "error": message}
    if details:
        result["details"] = details
    return result


def needs_confirmation(action: str, target: str) -> dict:
    """Respuesta que exige confirmación explícita antes de actuar."""
    return {
        "ok": False,
        "needs_confirmation": True,
        "action": action,
        "target": target,
        "message": f"Acción '{action}' sobre '{target}' requiere confirmación. Invoca de nuevo con confirm=True.",
    }
