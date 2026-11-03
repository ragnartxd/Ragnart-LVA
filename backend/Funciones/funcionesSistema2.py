"""Funciones auxiliares de calendario y análisis de PDF."""

import datetime
import json
import os
from pathlib import Path

from backend.configuracion_usuario import PROJECT_ROOT
from backend.utils.utils_instruccion_adicional import decir_y_escuchar
from backend.utils.json_storage import guardar_json_atomico


_EVENTOS_PATH = PROJECT_ROOT / "importaciones" / "calendario" / "eventos_calendario.json"


def _cargar_eventos():
    if not _EVENTOS_PATH.exists():
        return []
    with _EVENTOS_PATH.open("r", encoding="utf-8") as archivo:
        eventos = json.load(archivo)
    if not isinstance(eventos, list) or any(
        not isinstance(evento, dict) or not isinstance(evento.get("titulo"), str)
        for evento in eventos
    ):
        raise ValueError(
            "El archivo de calendario debe contener una lista de eventos con título."
        )
    return eventos


def _validar_fecha_hora(fecha, hora):
    try:
        datetime.datetime.strptime(fecha, "%Y-%m-%d")
        datetime.datetime.strptime(hora, "%H:%M")
    except (TypeError, ValueError):
        return False
    return True


def _pedir_titulo(pregunta, titulo):
    titulo = titulo or decir_y_escuchar(pregunta)
    return titulo.strip() if isinstance(titulo, str) else ""


def marcar_calendario_evento(titulo: str = None, fecha: str = None, hora: str = None):
    """Crea un evento en el calendario local."""
    titulo = _pedir_titulo("¿Cuál es el título del evento?", titulo)
    if not titulo:
        return "No se guardó el evento porque falta el título."
    if not fecha:
        fecha = decir_y_escuchar("¿Qué fecha? (formato año-mes-día)")
    if not hora:
        hora = decir_y_escuchar("¿A qué hora? (formato hora:minutos)")
    if not _validar_fecha_hora(fecha, hora):
        return "❌ Fecha u hora en formato incorrecto. Usa YYYY-MM-DD y HH:MM."

    try:
        eventos = _cargar_eventos()
        eventos.append({"titulo": titulo, "fecha": fecha, "hora": hora})
        guardar_json_atomico(_EVENTOS_PATH, eventos, indent=2, ensure_ascii=False)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return f"❌ Error al guardar el evento: {error}"
    return f"✅ Evento '{titulo}' marcado para el {fecha} a las {hora}."


def mover_evento_calendario(
    titulo: str = None,
    nueva_fecha: str = None,
    nueva_hora: str = None,
):
    """Actualiza la fecha y hora de un evento existente."""
    titulo = _pedir_titulo("¿Cuál es el título del evento que quieres mover?", titulo)
    if not titulo:
        return "No se movió el evento porque falta el título."
    if not nueva_fecha:
        nueva_fecha = decir_y_escuchar("¿A qué nueva fecha? (formato año-mes-día)")
    if not nueva_hora:
        nueva_hora = decir_y_escuchar("¿A qué nueva hora? (formato hora:minutos)")
    if not _validar_fecha_hora(nueva_fecha, nueva_hora):
        return "❌ Fecha u hora en formato incorrecto. Usa YYYY-MM-DD y HH:MM."

    try:
        eventos = _cargar_eventos()
        evento = next(
            (
                item
                for item in eventos
                if item["titulo"].casefold() == titulo.casefold()
            ),
            None,
        )
        if evento is None:
            return f"❌ No se encontró un evento con el título '{titulo}'."
        evento["fecha"] = nueva_fecha
        evento["hora"] = nueva_hora
        guardar_json_atomico(_EVENTOS_PATH, eventos, indent=2, ensure_ascii=False)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return f"❌ Error al mover el evento: {error}"
    return f"✅ Evento '{titulo}' movido a {nueva_fecha} a las {nueva_hora}."


def eliminar_evento_calendario(titulo: str = None):
    """Elimina del calendario el evento indicado por título."""
    titulo = _pedir_titulo("¿Cuál es el título del evento que quieres eliminar?", titulo)
    if not titulo:
        return "No se eliminó el evento porque falta el título."

    try:
        eventos = _cargar_eventos()
        evento = next(
            (
                item
                for item in eventos
                if item["titulo"].casefold() == titulo.casefold()
            ),
            None,
        )
        if evento is None:
            return f"❌ No se encontró un evento con el título '{titulo}'."
        eventos.remove(evento)
        guardar_json_atomico(_EVENTOS_PATH, eventos, indent=2, ensure_ascii=False)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return f"❌ Error al eliminar el evento: {error}"
    return f"✅ Evento '{titulo}' eliminado del calendario."


def convertir_pdf_para_ollama(
    pdf_path: str = None,
    output_dir: str = "importaciones/imagenes/pdf_ollama",
):
    """Extrae texto e imágenes de un PDF y genera un resumen con el modelo local."""
    import fitz

    from backend.Generacion.AIGeneration import generar_con_modelo
    from backend.utils.utils_obtenerArchivo import seleccionar_archivo_con_arrastre

    if not pdf_path:
        pdf_path = seleccionar_archivo_con_arrastre()
    if not pdf_path:
        return "No se seleccionó ningún PDF."

    ruta_pdf = Path(os.path.expandvars(os.path.expanduser(pdf_path)))
    if not ruta_pdf.is_absolute():
        ruta_pdf = PROJECT_ROOT / ruta_pdf
    if not ruta_pdf.is_file():
        raise FileNotFoundError(f"No existe el PDF: {ruta_pdf}")

    directorio_salida = Path(os.path.expandvars(os.path.expanduser(output_dir)))
    if not directorio_salida.is_absolute():
        directorio_salida = PROJECT_ROOT / directorio_salida
    directorio_salida.mkdir(parents=True, exist_ok=True)

    texto_paginas = []
    imagenes_extraidas = []
    with fitz.open(ruta_pdf) as documento:
        for numero_pagina, pagina in enumerate(documento, start=1):
            texto_paginas.append(pagina.get_text("text"))
            for indice_imagen, info_imagen in enumerate(
                pagina.get_images(full=True),
                start=1,
            ):
                imagen = documento.extract_image(info_imagen[0])
                ruta_imagen = directorio_salida / (
                    f"pagina{numero_pagina}_img{indice_imagen}.{imagen['ext']}"
                )
                ruta_imagen.write_bytes(imagen["image"])
                imagenes_extraidas.append(str(ruta_imagen))

    texto = "\n".join(texto_paginas)
    prompt = (
        "Resume detalladamente el texto extraído de este PDF. "
        "Las imágenes se extrajeron por separado y sus rutas se incluyen al final; "
        "no se enviaron como entrada visual al modelo.\n\n"
        f"Texto del PDF:\n{texto}\n\n"
        f"Rutas de imágenes extraídas:\n{os.linesep.join(imagenes_extraidas)}"
    )
    respuesta = generar_con_modelo(modelo="gemma3", prompt=prompt)
    resumen = respuesta if isinstance(respuesta, str) else "".join(map(str, respuesta))
    return {
        "texto": texto,
        "resumen": resumen,
        "imagenes": imagenes_extraidas,
    }
