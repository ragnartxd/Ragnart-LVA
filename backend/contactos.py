import json
from pathlib import Path

from backend.utils.json_storage import guardar_json_atomico


CONTACTOS_FILE = (
    Path(__file__).resolve().parent.parent
    / "importaciones"
    / "arc_personalizacion"
    / "contactos.json"
)


def cargar_contactos_guardados(path=CONTACTOS_FILE):
    path = Path(path)
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as archivo:
        data = json.load(archivo)
    return data if isinstance(data, dict) else {}


def guardar_contactos_guardados(contactos, path=CONTACTOS_FILE):
    if not isinstance(contactos, dict):
        raise TypeError("Los contactos deben estar en un diccionario.")

    path = Path(path)
    guardar_json_atomico(
        path,
        contactos,
        indent=2,
        ensure_ascii=False,
        trailing_newline=False,
    )
