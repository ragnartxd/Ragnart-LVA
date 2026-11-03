import logging

# Configuración de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Gestor_Parametros:
    """
    Clase que gestiona y valida los parámetros globales para todas las funciones.
    Ahora permite parámetros dinámicos con conversión automática de tipos.
    """

    # Parámetros por defecto con tipos esperados
    PARAMS_REQUERIDOS = {
        "gestionar_ventana": {"nombre_app": str, "accion": str},
        "abrir_aplicacion": {"nombre_app": str},
        "abrir_configuracion": {},
        "escribir_word": {"texto_completo": str},
        "enviar_correo": {"destinatario": str, "asunto": str, "cuerpo": str},
        "obtener_hora": {"formato_24h": bool},
        "poner_alarma": {"hora_texto": str},
        "poner_cronometro": {"segundos": int},
        "clic_texto": {"texto": str},
        "hacer_doble_clic_en_texto": {"texto": str},
        "hacer_scroll": {"texto": str, "cantidad": int},
        "arrastrar_y_soltar": {"texto_origen": str, "texto_destino": str},
        "leer_texto_captura": {},
        "tomar_captura": {},
        "buscar_texto_en_pantalla": {"texto": str},
        "alternar_aplicacion": {"nombre_app": str},
        "apagar_sistema": {},
        "reiniciar_sistema": {},
        "suspender_sistema": {},
        "bloquear_sistema": {},
        "activar_bluetooth": {"estado": str},
        "activar_wifi": {},
        "subir_volumen": {},
        "bajar_volumen": {},
        "ajustar_brillo": {"nuevo_valor": int},
        "consultar_clima": {"ciudad": str},
        "consultar_noticias": {},  # Sin parámetros
        "consultar_wikipedia": {"query": str},
        "buscar_cancion": {"cancion": str},
        "enviar_whatsapp": {"usuario": str, "mensaje": str},
        "identificar_anime": {},
        "generar_imagen": {"texto": str},
        "ejecutar_comando_secuencia": {"comando_voz": str},
        "flujo_analizar_archivo": {"texto": str},
        "accion_pedir_mas_contexto": {"texto": str},
        "te_quiero_modificar":{},
        "registrar_rostro":{},
        "verificar_rostro": {},
        "cifrar_archivo": {},
        "descifrar_archivo": {}
    }

    @staticmethod
    def procesar(params: dict) -> dict:
        logger.debug(f"📊 Debug - params recibido en procesar(): {params}")
        accion = params.get("accion")
        if not accion:
            raise ValueError("❌ Falta el parámetro 'accion'.")

        original_accion = accion
        alias = {
            "cerrar_aplicacion": "gestionar_ventana",
            "maximizar_aplicacion": "gestionar_ventana",
            "minimizar_aplicacion": "gestionar_ventana",
            "alternar_aplicacion": "gestionar_ventana",
            "hora_actual": "obtener_hora"
        }
        if accion in alias:
            accion = alias[accion]
            if "params" not in params:
                params["params"] = {}
            # Solo añadir 'accion' si es un parámetro esperado
            if "accion" in Gestor_Parametros.PARAMS_REQUERIDOS.get(accion, {}):
                params["params"]["accion"] = original_accion

        parametros_esperados = Gestor_Parametros.PARAMS_REQUERIDOS.get(accion, {})  
        parametros_finales = {}

        logger.debug(f"🔍 Debug - Params dentro de params: {params.get('params')}")

        for param, tipo in parametros_esperados.items():
            valor = params.get("params", {}).get(param)
            if valor is None:
                raise ValueError(f"❌ Falta el parámetro obligatorio: '{param}' en la función '{accion}'.")
            # Conversión segura para booleanos
            elif tipo == bool:
                if isinstance(valor, str):
                    valor_str = valor.strip().lower()
                    if valor_str in ["true", "1", "si", "sí"]:
                        valor = True
                    elif valor_str in ["false", "0", "no", ""]:
                        valor = False
                    else:
                        raise TypeError(f"🚨 El parámetro '{param}' debe ser booleano, pero recibió '{valor}' inválido.")
                elif isinstance(valor, (int, float)):
                    valor = bool(valor)
                elif not isinstance(valor, bool):
                    raise TypeError(f"🚨 El parámetro '{param}' debe ser de tipo bool, pero recibió {type(valor).__name__}.")
            else:
                if not isinstance(valor, tipo):
                    # → Si el tipo esperado es int y valor es str de dígitos, conviértelo:
                    if tipo is int and isinstance(valor, str) and valor.isdigit():
                        valor = int(valor)
                    elif tipo is int and param == "segundos" and isinstance(valor, str):
                        import re
                        from backend.utils.numero_texto import texto_a_numero

                        coincidencia = re.fullmatch(
                            r"\s*(\d+|[\wáéíóúñ]+)\s*(segundos?|minutos?|horas?)?\s*",
                            valor.strip().lower(),
                        )
                        cantidad = (
                            texto_a_numero(coincidencia.group(1))
                            if coincidencia
                            else None
                        )
                        if cantidad is None or not float(cantidad).is_integer():
                            raise TypeError(
                                f"🚨 El parámetro '{param}' debe ser de tipo int, "
                                f"pero recibió {type(valor).__name__}."
                            )
                        unidad = (coincidencia.group(2) or "segundos").rstrip("s")
                        factor = {"segundo": 1, "minuto": 60, "hora": 3600}[unidad]
                        valor = int(cantidad) * factor
                    else:
                        raise TypeError(
                            f"🚨 El parámetro '{param}' debe ser de tipo {tipo.__name__}, "
                            f"pero recibió {type(valor).__name__}."
                        )
            parametros_finales[param] = valor


        # Conversión automática de tipos para parámetros inesperados
        for key, value in params.get("params", {}).items():
            if key not in parametros_esperados:
                logger.warning(f"⚠️ Parámetro inesperado '{key}' en '{accion}', intentaremos convertirlo.")
                if key == "nombre_app" and isinstance(value, list):
                    parametros_finales[key] = value[0] if value else ""
                elif isinstance(value, str) and value.isdigit():
                    parametros_finales[key] = int(value)
                elif isinstance(value, str):
                    try:
                        parametros_finales[key] = float(value)
                    except ValueError:
                        parametros_finales[key] = value  
                else:
                    parametros_finales[key] = value  

        return {"accion": accion, "params": parametros_finales}
