"""Carga y persistencia local de valores privados del proyecto."""

import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

from backend.utils.json_storage import guardar_json_atomico


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
API_KEY_PREFIX = "RAGNART_API_"


def _leer_archivo_env():
    if not ENV_FILE.exists():
        return {}

    variables = {}
    with ENV_FILE.open("r", encoding="utf-8") as archivo:
        for numero_linea, linea in enumerate(archivo, start=1):
            linea = linea.strip()
            if not linea or linea.startswith("#"):
                continue
            if linea.startswith("export "):
                linea = linea[7:].lstrip()
            if "=" not in linea:
                raise ValueError(f"Línea {numero_linea} inválida en .env.")

            nombre, valor = linea.split("=", 1)
            nombre = nombre.strip()
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nombre):
                raise ValueError(f"Nombre de variable inválido en .env, línea {numero_linea}.")

            valor = valor.strip()
            if valor.startswith('"') and valor.endswith('"'):
                try:
                    valor = json.loads(valor)
                except json.JSONDecodeError as error:
                    raise ValueError(f"Valor entre comillas inválido en .env, línea {numero_linea}.") from error
            elif valor.startswith("'") and valor.endswith("'"):
                valor = valor[1:-1]
            variables[nombre] = valor
    return variables


def obtener_variable_entorno(nombre, predeterminado=""):
    """Prioriza las variables definidas por el sistema sobre las de .env."""
    if nombre in os.environ:
        return os.environ[nombre]
    return _leer_archivo_env().get(nombre, predeterminado)


def _nombre_variable_api(servicio):
    nombre = unicodedata.normalize("NFKD", str(servicio))
    nombre = nombre.encode("ascii", "ignore").decode("ascii").upper()
    nombre = re.sub(r"[^A-Z0-9]+", "_", nombre).strip("_")
    if not nombre:
        raise ValueError("El nombre del servicio no permite crear una variable de entorno.")
    return f"{API_KEY_PREFIX}{nombre}"


def obtener_clave_api(servicio):
    return obtener_variable_entorno(_nombre_variable_api(servicio))


def _guardar_variables_env(variables):
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    contenido = "".join(
        f"{nombre}={json.dumps(str(valor), ensure_ascii=False)}\n"
        for nombre, valor in sorted(variables.items())
    )
    descriptor, ruta_temporal = tempfile.mkstemp(
        prefix=".env.", suffix=".tmp", dir=ENV_FILE.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as archivo:
            archivo.write(contenido)
        os.replace(ruta_temporal, ENV_FILE)
    except Exception:
        if os.path.exists(ruta_temporal):
            os.unlink(ruta_temporal)
        raise


def guardar_configuracion_api(configuracion, ruta_config):
    """Guarda claves en .env y deja solo los nombres de servicios en JSON."""
    nombres_variables = {}
    for servicio in configuracion:
        nombre_variable = _nombre_variable_api(servicio)
        if nombre_variable in nombres_variables:
            raise ValueError(
                f"Los servicios '{nombres_variables[nombre_variable]}' y '{servicio}' "
                "producen el mismo nombre de variable."
            )
        nombres_variables[nombre_variable] = servicio

    variables = _leer_archivo_env()
    variables.update({
        nombre_variable: str(configuracion[servicio] or "")
        for nombre_variable, servicio in nombres_variables.items()
    })
    _guardar_variables_env(variables)

    ruta_config = Path(ruta_config)
    configuracion_publica = {servicio: "" for servicio in configuracion}
    guardar_json_atomico(ruta_config, configuracion_publica, indent=4, ensure_ascii=False)

    for nombre_variable, servicio in nombres_variables.items():
        os.environ[nombre_variable] = str(configuracion[servicio] or "")


def cargar_configuracion_api(ruta_config, servicios_base=()):
    """Migra valores legados de JSON a .env y devuelve las claves disponibles."""
    ruta_config = Path(ruta_config)
    if ruta_config.exists():
        with ruta_config.open("r", encoding="utf-8") as archivo:
            configuracion = json.load(archivo)
        if not isinstance(configuracion, dict) or not all(
            isinstance(servicio, str) for servicio in configuracion
        ):
            raise ValueError(f"La configuración de APIs debe ser un objeto JSON: {ruta_config}")
    else:
        configuracion = {}

    servicios = list(dict.fromkeys([*servicios_base, *configuracion.keys()]))
    variables_env = _leer_archivo_env()
    valores = {}
    for servicio in servicios:
        nombre_variable = _nombre_variable_api(servicio)
        valor_legado = configuracion.get(servicio, "")
        valor_entorno = os.environ.get(nombre_variable, variables_env.get(nombre_variable, ""))
        valores[servicio] = valor_entorno or str(valor_legado or "")

    if not ruta_config.exists() or any(
        configuracion.get(servicio) for servicio in configuracion
    ) or any(servicio not in configuracion for servicio in servicios_base):
        guardar_configuracion_api(valores, ruta_config)

    return valores
