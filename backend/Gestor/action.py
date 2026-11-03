# 📌 Diccionario de Handlers (Dynamic Dispatch)
from backend.Funciones.open_apps import OpenApps

import importlib
import inspect

# El escaneo de aplicaciones puede ser lento; inicializarlo solo al abrir una app
# evita bloquear el arranque del asistente y los handlers que no lo necesitan.
_opener = None


def _abrir_aplicacion_por_nombre(**kwargs):
    global _opener
    if _opener is None:
        _opener = OpenApps(fuzzy_threshold=75, cache_enabled=True)
    return _opener.abrir_aplicacion_por_nombre(**kwargs)


def _acepta_contexto_de_comando(funcion):
    try:
        return "texto_comando" in inspect.signature(funcion).parameters
    except (TypeError, ValueError):
        return False

action_global = {
    "poner_cronometro": ("backend.Funciones.funcionesSistema", "poner_cronometro"),
    "hora_actual": ("backend.Funciones.funcionesSistema", "handler_obtener_hora"),
    "poner_alarma": ("backend.Funciones.funcionesSistema", "poner_alarma"),
    "abrir_configuracion": ("backend.Funciones.funcionesFrontend", "abrir_configuracion"),
    "enviar_correo": ("backend.Funciones.funcionesSistema", "handler_enviar_correo"),
    "escribir_word": ("backend.Funciones.funcionesSistema", "handler_escribir_word"),
    "abrir_aplicacion": _abrir_aplicacion_por_nombre,
    "gestionar_ventana": ("backend.Funciones.funcionesSistema", "gestionar_ventana"),
    "clic_texto": ("backend.Funciones.lecturaPantalla", "clic_texto"),
    "cerrar_aplicacion": ("backend.Funciones.funcionesSistema", "cerrar_aplicacion"),
    "maximizar_aplicacion": ("backend.Funciones.funcionesSistema", "maximizar_aplicacion"),
    "minimizar_aplicacion": ("backend.Funciones.funcionesSistema", "minimizar_aplicacion"),
    "alternar_aplicacion": ("backend.Funciones.funcionesSistema", "alternar_aplicacion"),
    "hacer_scroll": ("backend.Funciones.lecturaPantalla", "hacer_scroll"),
    "arrastrar_y_soltar": ("backend.Funciones.lecturaPantalla", "arrastrar_y_soltar"),
    "apagar_sistema": ("backend.Funciones.funcionesSistema", "apagar_sistema"),
    "reiniciar_sistema": ("backend.Funciones.funcionesSistema", "reiniciar_sistema"),
    "suspender_sistema": ("backend.Funciones.funcionesSistema", "suspender_sistema"),
    "bloquear_sistema": ("backend.Funciones.funcionesSistema", "bloquear_sistema"),
    "activar_bluetooth": ("backend.Funciones.funcionesSistema", "activar_bluetooth"),
    "activar_wifi": ("backend.Funciones.funcionesSistema", "activar_wifi"),
    "subir_volumen": ("backend.Funciones.funcionesSistema", "subir_volumen"),
    "bajar_volumen": ("backend.Funciones.funcionesSistema", "bajar_volumen"),
    "ajustar_brillo": ("backend.Funciones.funcionesSistema", "ajustar_brillo"),
    "consultar_clima": ("backend.Funciones.funcionesInternet", "consultar_clima"),
    "consultar_noticias": ("backend.Funciones.funcionesInternet", "consultar_noticias"),
    "consultar_wikipedia": ("backend.Funciones.funcionesInternet", "consultar_wikipedia"),
    "buscar_cancion": ("backend.Funciones.funcionesInternet", "buscar_cancion"),
    "enviar_whatsapp": ("backend.Funciones.funcionesInternet", "enviar_whatsapp"),
    "identificar_anime": ("backend.Funciones.funcionesInternet", "identificar_anime"),
    "generar_imagen": ("backend.Funciones.funcionesInternet", "generar_imagen"),
    "ejecutar_comando_secuencia": ("backend.Funciones.funcionesSistema", "ejecutar_comando_secuencia"),
    # Nombre utilizado actualmente por el clasificador de intenciones.
    "ejecutar_comando": ("backend.Funciones.funcionesSistema", "ejecutar_comando_secuencia"),
    "marcar_calendario_evento": ("backend.Funciones.funcionesSistema2", "marcar_calendario_evento"),
    "mover_evento_calendario": ("backend.Funciones.funcionesSistema2", "mover_evento_calendario"),
    "eliminar_evento_calendario": ("backend.Funciones.funcionesSistema2", "eliminar_evento_calendario"),
    "convertir_pdf_para_ollama": ("backend.Funciones.funcionesSistema2", "convertir_pdf_para_ollama"),
    "flujo_analizar_archivo": ("backend.Funciones.funcionesInternet", "flujo_analizar_archivo"),
    "accion_pedir_mas_contexto": ("backend.Gestor.procesador_intencion", "accion_pedir_mas_contexto"),
    "registrar_rostro": ("backend.FuncionesVisuales.funcionID", "sign_up"),
    "verificar_rostro": ("backend.FuncionesVisuales.funcionID", "login"),
    "cifrar_archivo": ("backend.Seguridad.ProteccionArchivos", "cifrar_archivo"),
    "descifrar_archivo": ("backend.Seguridad.ProteccionArchivos", "descifrar_archivo")
}

def ejecutar_handler(nombre_accion, texto_comando=None, **kwargs):
    """Ejecuta una función de acuerdo con la acción detectada (lazy import)."""
    if nombre_accion not in action_global:
        return f"Acción '{nombre_accion}' no encontrada."
    handler = action_global[nombre_accion]
    try:
        # Si el handler es una función/callable directa (por ejemplo opener.abrir_aplicacion_por_nombre)
        if callable(handler):
            print(f"[DEBUG] Handler callable para '{nombre_accion}': {handler}")
            if texto_comando is not None and _acepta_contexto_de_comando(handler):
                kwargs["texto_comando"] = texto_comando
            return handler(**kwargs)

        # Si el handler es una tupla (modulo, funcion), hacemos lazy import
        if isinstance(handler, (list, tuple)) and len(handler) == 2:
            modulo_nombre, funcion_nombre = handler
            modulo = importlib.import_module(modulo_nombre)
            funcion = getattr(modulo, funcion_nombre)
            print(f"[DEBUG] Handler para '{nombre_accion}': {modulo_nombre}.{funcion_nombre}")
            if texto_comando is not None and _acepta_contexto_de_comando(funcion):
                kwargs["texto_comando"] = texto_comando
            return funcion(**kwargs)

        return f"Configuración de handler inválida para '{nombre_accion}': {handler}"
    except Exception as e:
        return f"❌ Error ejecutando '{nombre_accion}': {e}"


if __name__ == "__main__":
    # Prueba rápida del sistema de handlers
    resultado = ejecutar_handler("abrir_aplicacion", nombre_aplicacion="Calculadora")
    print(f"Resultado de 'abrir_aplicacion': {resultado}")
