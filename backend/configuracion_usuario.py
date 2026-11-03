"""Carga compartida de preferencias editables desde el panel de configuración."""

import json
import multiprocessing
from pathlib import Path

from backend.utils.json_storage import guardar_json_atomico


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSONALIZACION_FILE = (
    PROJECT_ROOT
    / "importaciones"
    / "arc_personalizacion"
    / "config_personalizacion.json"
)
RESPUESTAS_FILE = PROJECT_ROOT / "importaciones" / "respuestas_config.json"

CONFIG_PERSONALIZACION_DEFAULT = {
    "habilitar_animaciones": False,
    "modelo_personaje": "",
    "voz_ia": "",
    "personalidad": "",
    "nivel_audio": 50,
    "nivel_animacion": 50,
    "velocidad_voz": 50,
    "siempre_activo": False,
    "habilitar_aprendizaje": False,
    "priorizar_urgentes": False,
    "iniciar_al_ejecutar": False,
    "ruta_guardado": "",
    "limite_cpu": min(4, multiprocessing.cpu_count()),
}
CONFIG_RESPUESTAS_DEFAULT = {
    "recordar_contexto": False,
    "max_conversaciones": 2,
    "actualizar_ia_mes": False,
    "ultimo_entrenamiento": None,
}


def _cargar(ruta, valores_predeterminados):
    ruta = Path(ruta)
    if not ruta.exists():
        return valores_predeterminados.copy()

    with ruta.open("r", encoding="utf-8") as archivo:
        datos = json.load(archivo)
    if not isinstance(datos, dict):
        raise ValueError(f"La configuración debe ser un objeto JSON: {ruta}")
    return {**valores_predeterminados, **datos}


def cargar_configuracion_personalizacion(ruta=PERSONALIZACION_FILE):
    configuracion = _cargar(ruta, CONFIG_PERSONALIZACION_DEFAULT)
    for clave in (
        "habilitar_animaciones",
        "siempre_activo",
        "habilitar_aprendizaje",
        "priorizar_urgentes",
        "iniciar_al_ejecutar",
    ):
        if not isinstance(configuracion[clave], bool):
            raise ValueError(f"{clave} debe ser un valor booleano.")
    for clave in ("nivel_audio", "nivel_animacion", "velocidad_voz"):
        if isinstance(configuracion[clave], bool) or not isinstance(configuracion[clave], int):
            raise ValueError(f"{clave} debe ser un número entero.")
        configuracion[clave] = max(0, min(100, configuracion[clave]))
    for clave in ("modelo_personaje", "voz_ia", "personalidad", "ruta_guardado"):
        if not isinstance(configuracion[clave], str):
            raise ValueError(f"{clave} debe ser texto.")
    limite_cpu = configuracion["limite_cpu"]
    if isinstance(limite_cpu, bool) or not isinstance(limite_cpu, int):
        raise ValueError("limite_cpu debe ser un número entero.")
    configuracion["limite_cpu"] = max(1, min(multiprocessing.cpu_count(), limite_cpu))
    return configuracion


def guardar_configuracion_personalizacion(configuracion, ruta=PERSONALIZACION_FILE):
    guardar_json_atomico(ruta, configuracion, indent=2, ensure_ascii=False)


def cargar_configuracion_respuestas(ruta=RESPUESTAS_FILE):
    configuracion = _cargar(ruta, CONFIG_RESPUESTAS_DEFAULT)
    if not isinstance(configuracion["recordar_contexto"], bool):
        raise ValueError("recordar_contexto debe ser un valor booleano.")
    if (
        isinstance(configuracion["max_conversaciones"], bool)
        or not isinstance(configuracion["max_conversaciones"], int)
        or configuracion["max_conversaciones"] < 0
    ):
        raise ValueError("max_conversaciones debe ser un entero no negativo.")
    return configuracion


def guardar_configuracion_respuestas(configuracion, ruta=RESPUESTAS_FILE):
    guardar_json_atomico(ruta, configuracion, indent=2, ensure_ascii=False)


def aplicar_limite_cpu():
    import torch

    limite = cargar_configuracion_personalizacion()["limite_cpu"]
    torch.set_num_threads(limite)
    return limite
