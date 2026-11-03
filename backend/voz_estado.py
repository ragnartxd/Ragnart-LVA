"""Coordinación local del estado de voz entre backend y frontend."""

import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time

from backend.configuracion_usuario import PROJECT_ROOT
from backend.utils.json_storage import guardar_json_atomico


logger = logging.getLogger(__name__)
_project_key = hashlib.sha256(
    os.path.normcase(str(PROJECT_ROOT)).encode("utf-8")
).hexdigest()[:16]
_STATE_DIR = Path(tempfile.gettempdir()) / f"ragnart-voice-{_project_key}"
_PLAYBACK_STATE = _STATE_DIR / "playback.json"
_FRONTEND_HEARTBEAT = _STATE_DIR / "frontend.json"
_ANIMATION_ACK = _STATE_DIR / "animation-ack.json"


def publicar_reproduccion(playback_id, reproduciendo, animaciones):
    """Publica el inicio o fin de un fragmento de voz para el frontend."""
    guardar_json_atomico(
        _PLAYBACK_STATE,
        {
            "playback_id": playback_id,
            "phase": "playing" if reproduciendo else "audio_finished",
            "animaciones": bool(animaciones),
            "updated_at": time.time(),
        },
    )


def leer_estado_reproduccion():
    try:
        with _PLAYBACK_STATE.open("r", encoding="utf-8") as archivo:
            estado = json.load(archivo)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("No se pudo leer el estado de voz compartido: %s", error)
        return None

    if (
        not isinstance(estado, dict)
        or not isinstance(estado.get("playback_id"), str)
        or estado.get("phase") not in {"playing", "audio_finished"}
    ):
        logger.warning("Estado de voz compartido inválido: %s", _PLAYBACK_STATE)
        return None
    return estado


def registrar_frontend_activo():
    guardar_json_atomico(_FRONTEND_HEARTBEAT, {"updated_at": time.time()})


def frontend_activo(max_antiguedad=3.0):
    try:
        with _FRONTEND_HEARTBEAT.open("r", encoding="utf-8") as archivo:
            estado = json.load(archivo)
        return time.time() - float(estado["updated_at"]) <= max_antiguedad
    except FileNotFoundError:
        return False
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        logger.warning("No se pudo comprobar el frontend activo: %s", error)
        return False


def confirmar_animacion_finalizada(playback_id):
    guardar_json_atomico(_ANIMATION_ACK, {"playback_id": playback_id})


def animacion_finalizada(playback_id):
    try:
        with _ANIMATION_ACK.open("r", encoding="utf-8") as archivo:
            estado = json.load(archivo)
        return estado.get("playback_id") == playback_id
    except FileNotFoundError:
        return False
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("No se pudo leer la confirmación de animación: %s", error)
        return False
