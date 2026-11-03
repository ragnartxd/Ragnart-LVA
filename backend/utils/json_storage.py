"""Persistencia atómica de documentos JSON locales."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


def guardar_json_atomico(
    ruta: str | Path,
    datos: Any,
    *,
    indent: int | None = None,
    ensure_ascii: bool = True,
    default: Callable[[Any], Any] | None = None,
    trailing_newline: bool = True,
) -> None:
    """Escribe JSON en el mismo directorio y reemplaza el destino al terminar."""
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)

    temporal = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{destino.name}.",
            suffix=".tmp",
            dir=destino.parent,
            delete=False,
        ) as archivo:
            temporal = Path(archivo.name)
            json.dump(
                datos,
                archivo,
                ensure_ascii=ensure_ascii,
                indent=indent,
                default=default,
            )
            if trailing_newline:
                archivo.write("\n")
        os.replace(temporal, destino)
    finally:
        if temporal is not None and temporal.exists():
            try:
                temporal.unlink()
            except FileNotFoundError:
                pass
