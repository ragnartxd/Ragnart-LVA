from collections import deque
from datetime import datetime
from pathlib import Path
import json, logging, random, re, gc, threading, time
from typing import Optional, Dict, Any
import requests
from backend.configuracion_general import cargar_configuracion_general
from backend.configuracion_usuario import (
    PROJECT_ROOT,
    cargar_configuracion_personalizacion,
    cargar_configuracion_respuestas,
)

import os

_BASE_DIR = str(PROJECT_ROOT)

# Configuración de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Cargar la configuración directamente
def cargar_configuracion():
    return cargar_configuracion_respuestas()

config = cargar_configuracion()
max_conversaciones = config.get("max_conversaciones", 2)

# Historial de conversación dinámico
historial_conversacion = deque(maxlen=max_conversaciones)


def _sincronizar_limite_historial():
    global historial_conversacion
    configuracion = cargar_configuracion_respuestas()
    limite = max(0, int(configuracion["max_conversaciones"]))
    if historial_conversacion.maxlen != limite:
        historial_conversacion = deque(historial_conversacion, maxlen=limite)
    if not configuracion["recordar_contexto"]:
        historial_conversacion.clear()
        return ()
    return historial_conversacion


def _aplicar_personalidad(prompt):
    personalidad = cargar_configuracion_personalizacion()["personalidad"].strip()
    if personalidad.lower().endswith((".txt", ".md")):
        ruta = Path(os.path.expandvars(os.path.expanduser(personalidad)))
        if not ruta.is_absolute():
            ruta = PROJECT_ROOT / ruta
        if not ruta.is_file():
            raise FileNotFoundError(f"No se encontró el archivo de personalidad: {ruta}")
        personalidad = ruta.read_text(encoding="utf-8").strip()
    if personalidad:
        return f"Personalidad e instrucciones del usuario: {personalidad}\n\n{prompt}"
    return prompt

def guardar_historial(mensaje):
    """Guarda el historial de conversación en un archivo sin sobrescribir los datos anteriores."""
    fecha_hoy = datetime.today().strftime("%Y-%m-%d")
    ruta_guardado = cargar_configuracion_personalizacion()["ruta_guardado"].strip()
    directorio_datos = os.path.expandvars(os.path.expanduser(ruta_guardado))
    if ruta_guardado and not os.path.isabs(directorio_datos):
        directorio_datos = os.path.join(_BASE_DIR, directorio_datos)
    directorio = os.path.join(
        directorio_datos if ruta_guardado else _BASE_DIR,
        "conversacion",
    )
    nombre_archivo = os.path.join(directorio, f"historial_{fecha_hoy}.txt")
    
    # Crear directorio si no existe
    os.makedirs(directorio, exist_ok=True)
    
    with open(nombre_archivo, "a", encoding="utf-8") as file:
        file.write(mensaje + "\n")  # Escribe cada línea en el archivo sin sobrescribir

def obtener_nombre_aleatorio():
    """Devuelve un nombre aleatorio de la lista de usuarios"""
    nombres = cargar_configuracion_general().get("NOMBRE_USUARIO", [])
    if nombres:
        return random.choice(nombres)
    return "Usuario"  # Si no hay nombres, usa un genérico

# =================== CONFIGURACIÓN DE MODELOS ===================

class ModelManager:
    """Gestor de modelos con carga bajo demanda y gestión eficiente de recursos."""
    
    def __init__(self):
        self.models_config = {
            "qwen3": {
                "model_name": "qwen3:4b",
                "url": "http://localhost:11434/api/generate",
                "specialty": "razonamiento_profundo",
                "timeout": 200,
                "last_used": None,
                "active": False
            },
            "gemma3": {
                "model_name": "gemma3:4b",
                "url": "http://localhost:11434/api/generate",
                "specialty": "generacion_rapida",
                "timeout": 200,
                "last_used": None,
                "active": False
            },
            "llama3": {
                "model_name": "llama3:8b",
                "url": "http://localhost:11434/api/generate",
                "specialty": "asistencia_general",
                "timeout": 200,
                "last_used": None,
                "active": False
            },
            "asistente_formal": { # gemma3 con personalidad formal
                "model_name": "asistente_formal",
                "url": "http://localhost:11434/api/generate",
                "specialty": "personalidad_formal",
                "timeout": 200,
                "last_used": None,
                "active": False
            }
        }
        self.cleanup_thread = None
        self.start_cleanup_service()
    
    def start_cleanup_service(self):
        """Inicia el servicio de limpieza automática de modelos inactivos."""
        def cleanup_inactive_models():
            while True:
                time.sleep(300)  # Revisar cada 5 minutos
                current_time = time.time()
                for model_id, config in self.models_config.items():
                    if (config["active"] and 
                        config["last_used"] and 
                        current_time - config["last_used"] > 900):  # 15 minutos sin uso
                        self.unload_model(model_id)
        
        self.cleanup_thread = threading.Thread(target=cleanup_inactive_models, daemon=True)
        self.cleanup_thread.start()
    
    def load_model(self, model_id: str) -> bool:
        """Carga un modelo específico en Ollama."""
        if model_id not in self.models_config:
            logger.error(f"Modelo {model_id} no está configurado")
            return False
        
        try:
            model_name = self.models_config[model_id]["model_name"]
            logger.debug(f"Probando modelo {model_name} en Ollama")
            # Verificar si el modelo está disponible
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model_name, "prompt": "test", "stream": False},
                
                timeout=30
            )
            if response.status_code == 200:
                self.models_config[model_id]["active"] = True
                logger.info(f"✅ Modelo {model_id} cargado correctamente")
                return True
            else:
                logger.error(f"❌ Ollama respondió {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"❌ Error cargando modelo {model_id}: {e}")

        return False
    
    def unload_model(self, model_id: str):
        """Marca un modelo como inactivo para liberar recursos."""
        if model_id in self.models_config:
            self.models_config[model_id]["active"] = False
            logger.info(f"🔄 Modelo {model_id} marcado como inactivo")
    
    def get_model_config(self, model_id: str) -> Optional[Dict]:
        """Obtiene la configuración de un modelo específico."""
        return self.models_config.get(model_id)
    
    def update_usage(self, model_id: str):
        """Actualiza el tiempo de último uso del modelo."""
        if model_id in self.models_config:
            self.models_config[model_id]["last_used"] = time.time()

# Instancia global del gestor de modelos
model_manager = ModelManager()

# MODO_HARDWARE: "bajo" (CPU/integrada) | "alto" (GPU dedicada)
# Sincronizar con procesador_intencion.py
MODO_HARDWARE = "bajo"

# =================== FUNCIONES DE GENERACIÓN ===================

def generator_qwen3(prompt: str, reintentos: int = 3):
    """
    Generador especializado en razonamiento profundo y análisis complejo.
    Ideal para: lógica compleja, análisis de datos, resolución de problemas.
    """
    model_id = "qwen3"
    config = model_manager.get_model_config(model_id)

    if not config["active"]:
        if not model_manager.load_model(model_id):
            yield "Error: No se pudo cargar Qwen3."
            return
        
    contexto_historial = "\n".join(_sincronizar_limite_historial())
    full_prompt = _aplicar_personalidad(
        f"{contexto_historial}\n{obtener_nombre_aleatorio()}: {prompt}\nAsistente:"
    )
    
    data = {
        "model": config["model_name"],
        "language": "es",  # Especificar el idioma español
        "prompt": str(full_prompt),
        "stream": True,  # Usar streaming para razonamiento
        "options": {
            "temperature": 0.3,  # Más determinístico para razonamiento
            "top_p": 0.8,
            "repeat_penalty": 1.1
        }
    }
    logger.debug(f"Enviando a Ollama: {json.dumps(data, ensure_ascii=False)}")
    
    try:
        response = requests.post(config["url"], json=data, timeout=config["timeout"], stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        yield "Lo siento, no pude conectarme a Qwen3 para streaming."
        return

    # Variables para el manejo del streaming y filtrado
    buffer_completo = ""  # Buffer que acumula TODO el contenido
    buffer_salida = ""    # Buffer solo para lo que se debe mostrar al usuario
    dentro_think = False  # Flag para saber si estamos dentro de <think>
    primera_salida = False
    count_frases = 0
    buffer_frases = ""
    
    for chunk in response.iter_lines(decode_unicode=True):
        if not chunk:
            continue

        # 1) Parsear JSON o tomar el chunk crudo
        try:
            data_chunk = json.loads(chunk)
            token = data_chunk.get("response", "")
        except Exception:
            token = chunk

        # 2) Agregar el token al buffer completo
        buffer_completo += token

        # 3) Procesar el contenido carácter por carácter para detectar <think>
        for char in token:
            # Verificar si estamos entrando en un bloque <think>
            if buffer_completo.endswith("<think>"):
                dentro_think = True
                # Remover "<think>" del buffer de salida si ya se había agregado
                if buffer_salida.endswith("<think>"):
                    buffer_salida = buffer_salida[:-7]
                continue
            
            # Verificar si estamos saliendo de un bloque </think>
            if buffer_completo.endswith("</think>"):
                dentro_think = False
                continue
            
            # Solo agregar al buffer de salida si NO estamos dentro de <think>
            if not dentro_think and char not in ['<', 't', 'h', 'i', 'n', 'k', '>', '/', ' '] or (not dentro_think and not buffer_completo.endswith(("<think", "</think"))):
                buffer_salida += char

        # 4) Procesar la salida acumulada para streaming por frases
        if buffer_salida and es_fin_frase(buffer_salida[-1:]):
            # Encontrar la última frase completa
            frases = re.split(r'([.!?…]\s*)', buffer_salida)
            
            if len(frases) >= 2:  # Tenemos al menos una frase completa
                frase_completa = frases[0] + (frases[1] if len(frases) > 1 else "")
                frase_completa = frase_completa.strip()
                
                if frase_completa and not primera_salida:
                    yield frase_completa
                    primera_salida = True
                elif frase_completa:
                    buffer_frases += frase_completa + " "
                    count_frases += 1
                    
                    if count_frases >= 2:
                        yield buffer_frases.strip()
                        buffer_frases = ""
                        count_frases = 0
                
                # Mantener solo la parte incompleta
                buffer_salida = "".join(frases[2:]) if len(frases) > 2 else ""

    # 5) Entregar cualquier contenido restante
    if buffer_salida.strip():
        resto = buffer_salida.strip()
        if not primera_salida:
            yield resto
        else:
            yield resto

    if buffer_frases.strip():
        yield buffer_frases.strip()

    # 6) Limpiar el texto final y actualizar estados
    # Aplicar una limpieza final más robusta
    texto_final = re.sub(r"<think>.*?</think>", "", buffer_completo, flags=re.DOTALL | re.IGNORECASE)
    texto_final = re.sub(r"</?think[^>]*>", "", texto_final)  # Remover etiquetas rotas
    texto_final = texto_final.strip()
    
    # Actualizar historial y logs
    historial_conversacion.append(f"Usuario: {prompt}\nAsistente: {texto_final}")
    guardar_historial(f"Usuario: {prompt}")
    guardar_historial(f"Asistente (Qwen3): {texto_final}")
    model_manager.update_usage(model_id)
    gc.collect()

    return texto_final


def generator_gemma3(prompt: str, reintentos: int = 3):
    """
    Generador especializado en generación rápida y descripción de imágenes.
    Ideal para: texto creativo, descripciones, respuestas rápidas.
    """
    #model_id = "gemma3"
    model_id = "asistente_formal"  # Usar la personalidad formal
    config = model_manager.get_model_config(model_id)
    
    if not config["active"]:
        if not model_manager.load_model(model_id):
            yield "Error: No se pudo cargar Gemma3."
            return
    contexto_historial = "\n".join(_sincronizar_limite_historial())
    full_prompt = _aplicar_personalidad(
        f"\nContexto: {contexto_historial}\n{obtener_nombre_aleatorio()}: {prompt}"
    )
    
    data = {
        "model": config["model_name"],
        "prompt": str(full_prompt),
        "stream": True,  # Usar streaming para respuestas rápidas
        "options": {
            "temperature": 0.7,  # Más creativo
            "top_p": 0.9,
            "repeat_penalty": 1.0
        }
    }
    
    #logger.debug(f"Enviando a Ollama: {json.dumps(data, ensure_ascii=False)}")
    #logger.debug(f"Prompt a enviar: {repr(prompt)}")
    #logger.debug(f"Data a enviar: {data}")
    try:
        response = requests.post(config["url"], json=data, timeout=config["timeout"], stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        yield "Lo siento, no pude conectarme a Gemma3 para streaming."
        return

    buffer_p = ""
    buffer_add = ""
    count_frases = 0
    primera = False
    texto_completo = ""

    for chunk in response.iter_lines(decode_unicode=True):
        if not chunk:
            continue
        try:
            data_chunk = json.loads(chunk)
            token = data_chunk.get("response", "")
        except Exception:
            token = chunk

        buffer_p += token
        texto_completo += token

        if es_fin_frase(token):
            frase = buffer_p.strip()
            buffer_p = ""

            if not primera:
                yield frase
                primera = True
            else:
                buffer_add += frase + " "
                count_frases += 1

            if count_frases >= 2:
                bloque = buffer_add.strip()
                yield bloque
                buffer_add = ""
                count_frases = 0

    if buffer_p.strip():
        resto = buffer_p.strip()
        if not primera:
            yield resto
            primera = True
        else:
            yield resto

    if buffer_add.strip():
        yield buffer_add.strip()

    salida_limpia = texto_completo.strip()
    historial_conversacion.append(f"Usuario: {prompt}\nAsistente: {salida_limpia}")
    guardar_historial(f"Usuario: {prompt}")
    guardar_historial(f"Gemma3 - Respuesta: {salida_limpia}")
    model_manager.update_usage(model_id)
    gc.collect()

    return salida_limpia

def generator_phi4(prompt: str, reintentos: int = 3):
    """
    Generador de asistencia general con mayor contexto.
    Ideal para: conversación general, tareas mixtas, contexto amplio.
    """
    model_id = "phi4-mini:latest"
    config = model_manager.get_model_config(model_id)
    
    if not config["active"]:
        if not model_manager.load_model(model_id):
            yield "Error: No se pudo cargar LLaMA3."
            return
    
    contexto_historial = "\n".join(_sincronizar_limite_historial())
    full_prompt = _aplicar_personalidad(
        f"{contexto_historial}\n{obtener_nombre_aleatorio()}: {prompt}\nAsistente:"
    )
    
    data = {
        "model": config["model_name"],
        "prompt": str(full_prompt),
        "stream": True,
        "options": {
            "temperature": 0.6,  # Balance entre creatividad y precisión
            "top_p": 0.85,
            "repeat_penalty": 1.05
        }
    }
    logger.debug(f"Enviando a Ollama: {json.dumps(data, ensure_ascii=False)}")
    try:
        response = requests.post(config["url"], json=data, timeout=config["timeout"], stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        yield "Lo siento, no pude conectarme a LLaMA3 para streaming."
        return

    buffer_p = ""
    buffer_add = ""
    count_frases = 0
    primera = False
    texto_completo = ""

    for chunk in response.iter_lines(decode_unicode=True):
        if not chunk:
            continue
        try:
            data_chunk = json.loads(chunk)
            token = data_chunk.get("response", "")
        except Exception:
            token = chunk

        buffer_p += token
        texto_completo += token

        if es_fin_frase(token):
            frase = buffer_p.strip()
            buffer_p = ""

            if not primera:
                yield frase
                primera = True
            else:
                buffer_add += frase + " "
                count_frases += 1

            if count_frases >= 2:
                bloque = buffer_add.strip()
                yield bloque
                buffer_add = ""
                count_frases = 0

    if buffer_p.strip():
        resto = buffer_p.strip()
        if not primera:
            yield resto
            primera = True
        else:
            yield resto

    if buffer_add.strip():
        yield buffer_add.strip()

    salida_limpia = texto_completo.strip()
    historial_conversacion.append(f"Usuario: {prompt}\nAsistente: {salida_limpia}")
    guardar_historial(f"Usuario: {prompt}")
    guardar_historial(f"Asistente: {salida_limpia}")
    model_manager.update_usage(model_id)
    gc.collect()

    return salida_limpia

# =================== FUNCIONES AUXILIARES ===================

def es_fin_frase(token: str) -> bool:
    """
    Determina si un token representa el final de una frase.
    Considera signos de puntuación comunes como punto, signo de interrogación o exclamación.
    """
    return bool(re.search(r"[.!?…]\s*$", token.strip()))

def consultar_modelo_experto(prompt: str, modelo_principal: str, modelo_consulta: str) -> str:
    """
    Permite que un modelo consulte a otro para obtener ayuda especializada.
    
    Args:
        prompt: La consulta original
        modelo_principal: El modelo que está procesando la tarea
        modelo_consulta: El modelo especialista al que se consulta
    
    Returns:
        Respuesta del modelo consulta
    """
    modelos_disponibles = {
        "qwen3": generator_qwen3,
        "gemma3": generator_gemma3,
        "llama3": generator_phi4
    }
    
    if modelo_consulta not in modelos_disponibles:
        return f"Error: Modelo {modelo_consulta} no disponible para consulta."
    
    prompt_consulta = f"[CONSULTA ESPECIALIZADA] {modelo_principal} necesita tu ayuda especializada con: {prompt}"
    
    logger.info(f"🤝 {modelo_principal} consultando a {modelo_consulta}")
    return modelos_disponibles[modelo_consulta](prompt_consulta)

def generar_con_modelo(modelo: str, prompt: str, **kwargs) -> str:
    """
    Función genérica para generar texto con el modelo especificado.
    
    Args:
        modelo: "qwen3", "gemma3", o "llama3"
        prompt: El texto de entrada
        **kwargs: Argumentos adicionales
    
    Returns:
        Respuesta generada por el modelo especificado
    """
    modelos = {
        "qwen3": generator_qwen3,
        "gemma3": generator_gemma3,
        "llama3": generator_phi4
    }
    
    if modelo not in modelos:
        logger.error(f"Modelo {modelo} no reconocido. Modelos disponibles: {list(modelos.keys())}")
        return "Error: Modelo no reconocido."
    
    return modelos[modelo](prompt, **kwargs)


# =================== BUCLE AGENTE CON TOOLS ===================
# Las tools estan definidas en el Modelfile de asistente_formal.
# El modelo responde con dos lineas de control + texto de voz con streaming:
#
#   ACCION: nombre_accion           <- accion a ejecutar (o "null")
#   PARAMS: param1=val1,param2=val2 <- parametros (vacio si no hay)
#   Texto de respuesta en voz...    <- streaming normal al TTS
#
# Flujo tipo "llm" (clasificador no supo):
#   1. Llamada rapida sin streaming: modelo genera solo ACCION + PARAMS
#   2. Codigo parsea, ejecuta handler, obtiene resultado real
#   3. Llamada con streaming: modelo genera respuesta conociendo el resultado
#
# Flujo tipo "tarea" bypass pipeline:
#   1. Handler ya ejecutado por clasificador, resultado conocido
#   2. Una sola llamada con streaming: modelo narra lo que paso
#
# _EJECUCION_LOCK evita duplicaciones por eco o doble deteccion.

_EJECUCION_LOCK    = threading.Lock()
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MODEL_AGENTE        = "asistente_formal"  # Modelfile con tools y personalidad


def _parsear_cabecera_accion(texto_decision: str) -> tuple:
    """
    Parsea las dos lineas de control que genera el modelo en la llamada de decision.
    Retorna (accion: str|None, params: dict)
    """
    lineas       = texto_decision.strip().splitlines()
    linea_accion = next((l for l in lineas if l.strip().startswith("ACCION:")), "ACCION: null")
    linea_params = next((l for l in lineas if l.strip().startswith("PARAMS:")), "PARAMS:")

    accion = linea_accion.replace("ACCION:", "").strip()
    accion = None if accion.lower() == "null" else accion

    params = {}
    valor_params = linea_params.replace("PARAMS:", "").strip()
    if valor_params:
        for par in valor_params.split(","):
            if "=" in par:
                k, v = par.split("=", 1)
                params[k.strip()] = v.strip()

    return accion, params


def _stream_respuesta_voz(prompt: str, timeout: int = 200) -> str:
    """
    Llama a /api/generate con streaming y manda cada frase al TTS en tiempo real.
    Usa el mismo mecanismo de es_fin_frase que los generadores existentes.
    Retorna el texto completo acumulado.
    """
    from backend.Generacion.from_TTS import hablar_async

    payload = {
        "model":   MODEL_AGENTE,
        "prompt":  _aplicar_personalidad(prompt),
        "stream":  True,
        "options": {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.0},
    }

    try:
        response = requests.post(OLLAMA_GENERATE_URL, json=payload,
                                 timeout=timeout, stream=True)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Error conectando a Ollama para streaming: {e}")
        hablar_async("Tuve un problema al procesar eso.")
        return "Tuve un problema al procesar eso."

    buffer_p       = ""
    buffer_add     = ""
    count_frases   = 0
    primera        = False
    texto_completo = ""

    for chunk in response.iter_lines(decode_unicode=True):
        if not chunk:
            continue
        try:
            data_chunk = json.loads(chunk)
            token = data_chunk.get("response", "")
        except Exception:
            token = chunk

        buffer_p       += token
        texto_completo += token

        if es_fin_frase(token):
            frase    = buffer_p.strip()
            buffer_p = ""
            if not frase:
                continue
            if not primera:
                hablar_async(frase)
                primera = True
            else:
                buffer_add   += frase + " "
                count_frases += 1
                if count_frases >= 2:
                    hablar_async(buffer_add.strip())
                    buffer_add   = ""
                    count_frases = 0

    if buffer_p.strip():
        hablar_async(buffer_p.strip())
    if buffer_add.strip():
        hablar_async(buffer_add.strip())

    return texto_completo.strip()


def llamar_modelo_agente(texto: str, contexto: str = "",
                         accion_pipeline: str = None,
                         params_pipeline: dict = None) -> str:
    """
    Motor del agente. Dos modos segun lo que venga del clasificador:

    Modo A — accion_pipeline tiene valor (tipo "tarea", bypass pipeline):
        El handler ya fue ejecutado por el clasificador con resultado conocido.
        Una sola llamada con streaming: modelo narra lo que paso.

    Modo B — accion_pipeline es None (tipo "llm"):
        Llamada 1 sin streaming: modelo decide ACCION y PARAMS (2 lineas, rapido).
        Codigo ejecuta el handler y obtiene el resultado real.
        Llamada 2 con streaming: modelo genera la respuesta de voz con el resultado.

    _EJECUCION_LOCK evita que dos comandos simultaneos dupliquen acciones.
    """
    if not _EJECUCION_LOCK.acquire(blocking=False):
        logger.warning("Ejecucion en curso, comando ignorado para evitar duplicacion")
        return ""

    try:
        from backend.Gestor.action import action_global, ejecutar_handler
        from backend.Gestor.GestorParametros import Gestor_Parametros

        ctx = f"Contexto: {contexto}\n" if contexto else ""

        # ── MODO A: accion ya ejecutada por el pipeline ───────────────────────
        if accion_pipeline:
            resultado = (params_pipeline or {}).get("_resultado", "Ejecutado.")
            prompt = (
                f"{ctx}"
                f"Accion ejecutada: {accion_pipeline}\n"
                f"Resultado: {resultado}\n"
                f"Usuario dijo: {texto}\n"
                f"Responde de forma breve y natural confirmando lo que paso."
            )
            respuesta = _stream_respuesta_voz(prompt)
            model_manager.update_usage("asistente_formal")
            guardar_historial(f"Usuario: {texto}")
            guardar_historial(f"Asistente: {respuesta}")
            return respuesta

        # ── MODO B: el modelo decide la accion ───────────────────────────────

        # Llamada 1 — sin streaming, temperatura baja, solo 2 lineas de control
        prompt_decision = (
            f"{_aplicar_personalidad('')}"
            f"{ctx}"
            f"Usuario: {texto}\n"
            f"Responde SOLO con las dos lineas ACCION y PARAMS. Sin texto adicional."
        )
        payload_decision = {
            "model":   MODEL_AGENTE,
            "prompt":  prompt_decision,
            "stream":  False,
            "options": {"temperature": 0.1, "num_predict": 30},
        }
        try:
            resp = requests.post(OLLAMA_GENERATE_URL, json=payload_decision, timeout=60)
            resp.raise_for_status()
            decision_raw = resp.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"Error en llamada de decision: {e}")
            decision_raw = "ACCION: null\nPARAMS:"

        accion, params = _parsear_cabecera_accion(decision_raw)
        logger.info(f"Decision LLM → accion={accion} params={params}")

        # Ejecutar el handler con el resultado real
        resultado_str = ""
        if accion and accion in action_global:
            try:
                params_proc  = Gestor_Parametros.procesar({"accion": accion, "params": params})
                resultado    = ejecutar_handler(accion, **params_proc["params"])
                resultado_str = str(resultado) if resultado is not None else "Ejecutado correctamente."
                logger.info(f"Handler {accion} → {resultado_str[:60]}")
            except Exception as e:
                resultado_str = f"Error: {e}"
                logger.error(f"Error ejecutando {accion}: {e}")
        elif accion:
            logger.warning(f"Accion no reconocida por el sistema: {accion}")
            resultado_str = "Esa accion no esta disponible."

        # Llamada 2 — con streaming, modelo conoce el resultado real
        if accion and accion in action_global:
            prompt_respuesta = (
                f"{_aplicar_personalidad('')}"
                f"{ctx}"
                f"Accion ejecutada: {accion}\n"
                f"Resultado: {resultado_str}\n"
                f"Usuario dijo: {texto}\n"
                f"Responde de forma breve y natural."
            )
        else:
            prompt_respuesta = (
                f"{_aplicar_personalidad('')}"
                f"{ctx}"
                f"Usuario: {texto}\n"
                f"Responde de forma breve y natural."
            )

        respuesta = _stream_respuesta_voz(prompt_respuesta)
        model_manager.update_usage("asistente_formal")
        guardar_historial(f"Usuario: {texto}")
        guardar_historial(f"Asistente: {respuesta}")
        gc.collect()
        return respuesta

    finally:
        _EJECUCION_LOCK.release()


# =================== FUNCIONES HEREDADAS ===================

def generator_text(prompt, reintentos=3):
    """Función legacy que usa LLaMA3 por defecto para mantener compatibilidad."""
    return generator_phi4(prompt, reintentos)

def generar_ayudas(prompt, reintentos=3):
    """Función legacy que usa Gemma3 para reformulación rápida."""
    full_prompt = f"tienes que reformular el siguiente texto para que sea entendible por un procesador de intenciones, dame solo el mensaje reformulado. (ejemplo: abrio una netflix -- abre netflix).texto: '{prompt}'"
    return generator_gemma3(full_prompt, reintentos)

def generator_raw(prompt, reintentos=3):
    """Función legacy que usa Gemma3 para contenido sin personalidad."""
    return generator_gemma3(prompt, reintentos)

# =================== INFORMACIÓN DE MODELOS ===================

def obtener_estado_modelos() -> Dict[str, Any]:
    """Devuelve el estado actual de todos los modelos."""
    estado = {}
    for model_id, config in model_manager.models_config.items():
        estado[model_id] = {
            "activo": config["active"],
            "especialidad": config["specialty"],
            "ultimo_uso": config["last_used"],
            "tiempo_inactivo": time.time() - config["last_used"] if config["last_used"] else None
        }
    return estado

def recomendar_modelo(tipo_tarea: str) -> str:
    """
    Recomienda el mejor modelo según el tipo de tarea.
    
    Args:
        tipo_tarea: "razonamiento", "creativo", "general", "rapido"
    
    Returns:
        ID del modelo recomendado
    """
    recomendaciones = {
        "razonamiento": "qwen3",
        "logica": "qwen3",
        "analisis": "qwen3",
        "creativo": "gemma3",
        "rapido": "gemma3",
        "descripcion": "gemma3",
        "imagen": "gemma3",
        "general": "llama3",
        "conversacion": "llama3",
        "mixto": "llama3"
    }
    
    return recomendaciones.get(tipo_tarea.lower(), "llama3")

def run_test(nombre, gen_func, prompt):
    """
    Ejecuta un test de generación:
      - gen_func: función generadora (p. ej. generator_gemma3)
      - prompt: texto de entrada
    Mide el tiempo, acumula la respuesta y muestra el historial.
    """
    print(f"\n=== {nombre} ===")
    start = time.time()
    respuesta = ""
    # Iteramos el generador para que realmente se haga la petición
    for chunk in gen_func(prompt):
        respuesta += chunk
    elapsed = time.time() - start

    print(f"Prompt: {prompt}")
    print(f"Respuesta completa:\n{respuesta}")
    print(f"Tiempo de respuesta: {elapsed:.2f} segundos")
    print(f"Historial de conversación: {historial_conversacion}")

if __name__ == "__main__":
    print("=== Pruebas de Modelos ===")

    # 1. Qwen3 - Razonamiento profundo
    run_test(
        "1. Qwen3 - Razonamiento profundo",
        generator_qwen3,
        "Explica la paradoja de «Esta oración es falsa.»"
    )

    # 2. Gemma3 - Generación rápida
    run_test(
        "2. Gemma3 - Generación rápida",
        generator_gemma3,
        "Describe brevemente un atardecer en la playa"
    )

    # 3. Gemma3 - Asistencia general
    run_test(
        "3. Gemma3 - Asistencia general",
        generator_gemma3,
        "Hola, ¿cómo estás hoy?"
    )

    # 4. Llama3 - Consulta especializada
    run_test(
        "4. Llama3 - Consulta especializada",
        generator_phi4,
        "¿Cómo optimizar algoritmos de machine learning?"
    )

    # 5. Gemma3 - Otro ejemplo de generación
    run_test(
        "5. Gemma3 - Poema primaveral",
        generator_gemma3,
        "Genera un poema sobre la primavera"
    )

    # Estado final de los modelos
    print("\n=== Estado de modelos ===")
    estado = obtener_estado_modelos()
    for modelo, info in estado.items():
        status = "Activo" if info["activo"] else "Inactivo"
        print(f"- {modelo}: {status} — {info['especialidad']}")