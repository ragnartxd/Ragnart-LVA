"""Acceso a preferencias locales editables desde la interfaz."""

import json
from pathlib import Path

from backend.utils.json_storage import guardar_json_atomico


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "importaciones" / "config_general.json"


def cargar_configuracion_general():
    if not CONFIG_FILE.exists():
        return {
            "NOMBRE_ASISTENTE": "",
            "NOMBRE_USUARIO": [],
            "IDIOMA": "Español",
        }

    with CONFIG_FILE.open("r", encoding="utf-8") as archivo:
        configuracion = json.load(archivo)
    if not isinstance(configuracion, dict):
        raise ValueError(f"La configuración general debe ser un objeto JSON: {CONFIG_FILE}")

    nombres = configuracion.get("NOMBRE_USUARIO", [])
    if isinstance(nombres, str):
        nombres = [nombres] if nombres else []
    if not isinstance(nombres, list) or not all(isinstance(nombre, str) for nombre in nombres):
        raise ValueError("NOMBRE_USUARIO debe ser una lista de nombres.")

    return {
        "NOMBRE_ASISTENTE": str(configuracion.get("NOMBRE_ASISTENTE", "")),
        "NOMBRE_USUARIO": nombres,
        "IDIOMA": str(configuracion.get("IDIOMA", "Español")),
    }


def guardar_configuracion_general(configuracion):
    guardar_json_atomico(CONFIG_FILE, configuracion, indent=4, ensure_ascii=False)
