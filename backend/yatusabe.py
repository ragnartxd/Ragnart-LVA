import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import contextlib, json, time, logging, threading
from vosk import KaldiRecognizer
from backend.Gestor.GestorParametros import Gestor_Parametros
from backend.Gestor.procesador_intencion import procesar_intencion
from backend.Generacion.AIGeneration import generator_gemma3, generator_qwen3, llamar_modelo_agente
from backend.Gestor.action import action_global, ejecutar_handler

import json
import logging
from vosk import KaldiRecognizer

# Importar TTS (siempre el mismo)
from backend.Generacion.from_TTS import (
    hablar, hablar_async, estado_audio,
    obtener_modelo as obtener_modelo_vosk,
    obtener_reconocedor as obtener_reconocedor_vosk,
    async_tts_manager
)

# Cambiá esta bandera según qué quieras usar 
USAR_WHISPER = False # CAMBIALO A True SI QUIERES USAR WHISPER
USAR_FASTER_WHISPER = True # CAMBIALO A True SI QUIERES USAR FASTER-WHISPER

#El Usuario puede interrumpir al asistente mientras habla
BARGE_IN_HABILITADO = False #False si quieres que el asistente termine antes de escuchar/True si quieres interrumpir.

esperando_respuesta_directa = False

WHISPER_DISPONIBLE = False
# Importar Whisper opcional
if USAR_WHISPER == True:
    try:
        from backend.Generacion.from_whisper import (
            obtener_reconocedor as obtener_reconocedor_whisper
        )
        WHISPER_DISPONIBLE = True
    except Exception as e:
        logging.warning(f"⚠️ Whisper no disponible: {e}")
        WHISPER_DISPONIBLE = False

if USAR_FASTER_WHISPER:
    try:
        from backend.Generacion.from_faster_whisper import (
            obtener_reconocedor as obtener_reconocedor_whisper
        )
        WHISPER_DISPONIBLE = True
    except Exception as e:
        logging.warning(f"⚠️ Faster-Whisper no disponible: {e}")
        WHISPER_DISPONIBLE = False


from backend.Gestor.gestor_memoria import GestorMemoriaV2 as GestorMemoria
from backend.Gestor.gestor_audio import gestor_audio
from backend.configuracion_general import cargar_configuracion_general
from backend.configuracion_usuario import (
    PROJECT_ROOT,
    aplicar_limite_cpu,
    cargar_configuracion_personalizacion,
    cargar_configuracion_respuestas,
)

logging.getLogger("comtypes").setLevel(logging.ERROR)
logging.getLogger(__name__).info(
    "Límite de hilos CPU configurado: %s", aplicar_limite_cpu()
)

def _crear_gestor_memoria():
    ruta_guardado = cargar_configuracion_personalizacion()["ruta_guardado"].strip()
    if not ruta_guardado:
        return GestorMemoria()

    directorio = os.path.expandvars(os.path.expanduser(ruta_guardado))
    if not os.path.isabs(directorio):
        directorio = os.path.join(str(PROJECT_ROOT), directorio)
    directorio = os.path.abspath(directorio)
    os.makedirs(directorio, exist_ok=True)
    from backend.Datos.baseDatos import BaseDeDatos

    return GestorMemoria(
        db_instance=BaseDeDatos(os.path.join(directorio, "asistente.db")),
        ruta_taxonomia=os.path.join(directorio, "taxonomia_memoria.json"),
        ruta_index=os.path.join(directorio, "memoria_faiss_v2.index"),
        ruta_metadata=os.path.join(directorio, "metadata_faiss_v2.json"),
        ruta_indices_struct=os.path.join(directorio, "indices_estructurales.json"),
    )


gm = _crear_gestor_memoria()
palabras_clave = cargar_configuracion_general()

NOMBRE_ASISTENTE = palabras_clave.get("NOMBRE_ASISTENTE", "asistente")
NOMBRE_USUARIOS = palabras_clave.get("NOMBRE_USUARIO", [])
IDIOMA = palabras_clave.get("IDIOMA", "Español")

IDIOMA_CODIGOS = {
    "Español": "es",
    "Inglés": "en",
    "Francés": "fr",
}

# Inicialización del reconocedor principal y wake word 

modelo_vosk = obtener_modelo_vosk()
rec_wake    = KaldiRecognizer(modelo_vosk, 16000, json.dumps(palabras_clave))
USAR_FASTER_WHISPER_ACTIVO = False
 
if (USAR_WHISPER or USAR_FASTER_WHISPER) and WHISPER_DISPONIBLE:
    rec_main = obtener_reconocedor_whisper()
    USAR_FASTER_WHISPER_ACTIVO = USAR_FASTER_WHISPER
    print("🎙️ Usando Faster-Whisper para comandos y Vosk para wake word")
else:
    rec_main = obtener_reconocedor_vosk()
    print("🎙️ Usando Vosk para todo")


modo_conversacion_activa = False
ultima_interaccion_usuario = 0
detener_evento = threading.Event()


# INICIALIZAR GESTOR DE AUDIO AL INICIO
if not gestor_audio.inicializar():
    print("❌ Error inicializando gestor de audio")
    sys.exit(1)

@contextlib.contextmanager
def audio_stream(p, **kwargs):
    stream = p.open(**kwargs)
    try:
        yield stream
    finally:
        stream.stop_stream()
        stream.close()
        
def obtener_contexto_conversacion(texto):
    """Obtiene el contexto más relevante usando búsqueda híbrida real"""
    try:
        if not cargar_configuracion_respuestas()["recordar_contexto"]:
            return ""

        CATEGORIAS_EXCLUIR = {"pregunta", "conversacion_casual", "instruccion", "general"}
        
        # Búsqueda híbrida (tripletas + semántica + re-ranking)
        resultados_hibridos = gm.buscar_contexto_hibrido(texto, top_k=3)
        contexto_partes = []

        # RESULTADOS HÍBRIDOS (ya rankeados por relevancia)
        for registro, score in resultados_hibridos:
            categoria = getattr(registro, "categoria", "general")
            if score > 0.3 and categoria not in CATEGORIAS_EXCLUIR:
                contexto_partes.append(registro.texto_original)

        # EVENTOS PRÓXIMOS (solo estos vienen de SQLite aparte)
        try:
            eventos = gm.db.obtener_eventos_proximos(horas=168)
            for e in eventos[:2]:
                if isinstance(e, (list, tuple)) and len(e) >= 2:
                    contexto_partes.append(f"Evento: {e[0]} el {e[1]}")
        except Exception as e:
            logging.warning(f"⚠️ Error obteniendo eventos: {e}")

        # Deduplicar y limpiar 
        vistos = set()
        contexto_limpio = []
        for c in contexto_partes:
            if isinstance(c, str) and len(c.strip()) > 0 and c not in vistos:
                vistos.add(c)
                contexto_limpio.append(c)

        if contexto_limpio:
            contexto = " | ".join(contexto_limpio)
            print(f"📚 Contexto recuperado ({len(contexto_limpio)} items): {contexto[:200]}...")
            return contexto
        else:
            print("📚 No se encontró contexto relevante (vacío)")
            return ""

    except Exception as e:
        logging.exception("Error al obtener contexto: %s", e)
        print(f"❌ Error obteniendo contexto: {e}")
        return ""


    
def procesar_comando(texto, intentos):
    respuestas = []
    acciones_ejecutadas = []
    if cargar_configuracion_personalizacion()["priorizar_urgentes"]:
        acciones_urgentes = {
            "apagar_sistema",
            "reiniciar_sistema",
            "suspender_sistema",
            "bloquear_sistema",
        }
        intentos = sorted(
            intentos,
            key=lambda intento: intento.get("accion") not in acciones_urgentes,
        )
 
    for intento in intentos:
        accion = intento.get("accion")
        params = intento.get("params", {})
        if intento.get("accion") == "conversacion" or intento.get("tipo") == "conversacion":
            # Usar el nuevo sistema de contexto mejorado
            contexto = obtener_contexto_conversacion(texto)
            prompt = f"Usuario: {texto}"
 
            if "explicame" in texto.lower() or "explica" in texto.lower() or "explicación" in texto.lower() or "detalle" in texto.lower():
                generador = generator_qwen3(prompt)
            else:
                prompt = f"Informacion para usar: {str(contexto)}\nUsuario: {texto}"
                generador = generator_gemma3(prompt)
 
            # Si el resultado es un iterador (un generador), lo procesamos así:
            if hasattr(generador, "__iter__") and not isinstance(generador, str):
                acumulado = ""
                fragmento_count = 0
 
                for fragmento in generador:
                    if fragmento and fragmento.strip():
                        fragmento_count += 1
                        print(f"📝 Fragmento {fragmento_count}: {fragmento[:50]}...")
                        
                        # Enviar inmediatamente a audio asíncrono
                        hablar_async(fragmento)
                        
                        # Acumular para respuesta final
                        acumulado += fragmento + " "
                respuesta = acumulado.strip()
            else:
                # En caso de que generator_... no sea un generador (ej. error temprano), lo tratamos como string
                # Fallback para respuestas no-streaming
                respuesta = str(generador)
                hablar_async(respuesta)
                print("📤 Respuesta enviada a audio (no-streaming)")
 
            respuestas.append(respuesta)
 
        elif intento.get("tipo") == "llm":
            # Embedding no resolvió la intención — el LLM decide con tools
            # si ejecutar una acción del sistema o solo conversar
            contexto = obtener_contexto_conversacion(texto)
            respuesta = llamar_modelo_agente(
                texto=texto,
                contexto=contexto,
            )
            respuestas.append(respuesta)
 
        elif accion in action_global:
            try:
                datos = Gestor_Parametros.procesar({"accion": accion, "params": params})
                respuesta_real = ejecutar_handler(
                    accion,
                    texto_comando=intento.get("texto", texto),
                    **datos["params"],
                )
                acciones_ejecutadas.append(respuesta_real)
            except (TypeError, ValueError) as e:
                error_msg = str(e)
                if "nombre_app" in error_msg:
                    respuestas.append("¿Qué aplicación deseas abrir?")
                else:
                    respuestas.append(f"Error ejecutando '{accion}': {e}")
        else:
            respuestas.append("No entendí la instrucción.")
 
    if acciones_ejecutadas:
        acciones_str = [str(a) for a in acciones_ejecutadas if a is not None]
        prompt= f"{texto}\nAsistente: {' '.join(acciones_str)}"
        respuesta_modelo = generator_gemma3(prompt)
        if hasattr(respuesta_modelo, "__iter__") and not isinstance(respuesta_modelo, str):
            acumulado2 = ""
            for frag in respuesta_modelo:
                 if frag and frag.strip():
                    hablar_async(frag)
                    acumulado2 += frag + " "
            respuestas.append(acumulado2.strip())
        else:
            respuesta2 = str(respuesta_modelo)
            hablar_async(respuesta2)
            respuestas.append(respuesta2)
 
    # Ahora concatenamos todas las respuestas en un solo texto (para logging, etc.)
    if respuestas:
        respuesta_final = " y ".join(respuestas)
    else:
        respuesta_final = "No entendí la instrucción."
 
    # **¡Ojo! Ya hablamos cada fragmento dentro del bucle**,
    # aquí NO volvemos a llamar a hablar(respuesta_final).
 
    return respuesta_final
 
modo_conversacion_activa   = False
ultima_interaccion_usuario = 0.0
 
def escuchar():
    global modo_conversacion_activa, ultima_interaccion_usuario
 
    detener_evento.clear()
    gestor_audio.activar_wake_word()
    configuracion = cargar_configuracion_personalizacion()
    if configuracion["iniciar_al_ejecutar"]:
        hablar("Asistente iniciado. Te escucho.")
        _pasar_a_activo()
    else:
        hablar(f"Escuchando, Di {NOMBRE_ASISTENTE} para activar.")
 
    while not detener_evento.is_set():
        _actualizar_configuracion_general()
        data = gestor_audio.obtener_audio_data(timeout=0.1)
 
        # ── Sin datos: solo chequear timeouts ─────────────────────────────────
        if data is None:
            if modo_conversacion_activa:
                asistente_hablando = estado_audio().get("reproduciendo", False)
                # Mientras el asistente habla, resetear el temporizador para
                # que la ventana no expire antes de que el usuario pueda responder.
                if asistente_hablando:
                    gestor_audio._ultima_voz = time.time()
                elif _ventana_respuesta_expirada():
                    _pasar_a_espera("Ventana 10 s expirada → ESPERA")
            continue
 
        # ── MODO ACTIVO / VENTANA ──────────────────────────────────────────────
        if modo_conversacion_activa:
            asistente_hablando = estado_audio().get("reproduciendo", False)
 
            # Barge-in (opcional)
            if asistente_hablando and BARGE_IN_HABILITADO:
                print("Barge-in: interrumpiendo TTS")
                async_tts_manager.parar_audio()
                rec_main.Reset()
                ultima_interaccion_usuario = time.time()
                asistente_hablando = False
 
            # Timeout de inactividad: resetear mientras el asistente habla
            if asistente_hablando:
                gestor_audio._ultima_voz = time.time()
            elif _ventana_respuesta_expirada():
                _pasar_a_espera("Ventana 10 s expirada → ESPERA")
                continue
 
            # ── PUNTO CLAVE ────────────────────────────────────────────────────
            # GestorAudio (modo ACTIVO) ya acumuló la frase completa con VAD
            # y la emitió como un único bloque de bytes.
            # rec_main.transcribir() convierte bytes → numpy → Faster-Whisper
            # todo en memoria, sin pasar por disco ni por streaming de frames.
            # ──────────────────────────────────────────────────────────────────
            # Usar transcribir() si es Faster-Whisper, AcceptWaveform si es Vosk
            gestor_audio.desactivar()
            if USAR_FASTER_WHISPER_ACTIVO:
                texto = rec_main.transcribir(data)
            else:
                texto = ""
                if rec_main.AcceptWaveform(data):
                    result = json.loads(rec_main.Result())
                    texto  = result.get("text", "").strip()
                    rec_main.Reset()
 
            if texto:
                if esperando_respuesta_directa:
                    continue  # 🔥 ignorar mientras otra función escucha
                ultima_interaccion_usuario = time.time()
                print(f"✅ Detectado: {texto}")
                _procesar_peticion_y_esperar(texto)
            else:
                gestor_audio.activar_procesamiento()
            continue
 
        # ── MODO ESPERA (wake word con Vosk) ──────────────────────────────────
        # En este modo data es un frame de 32 ms → Vosk lo consume directamente.
        if rec_wake.AcceptWaveform(data):
            wake_result       = json.loads(rec_wake.Result())
            palabra_detectada = wake_result.get("text", "").lower()
 
            if NOMBRE_ASISTENTE.lower() in palabra_detectada or "hola" in palabra_detectada:
                print(f"Wake word: '{palabra_detectada}'")
                hablar_async("Hola, encantado de poder asistirte.")
                _pasar_a_activo()
 
 
def _esperar_fin_tts():
    """
    Bloquea hasta que el TTS termine de reproducir o se agote max_espera.
    Evita que el microfono capture la voz del propio asistente.
    """
    async_tts_manager.esperar_cola_vacia()
    time.sleep(0.2)


def _procesar_peticion_y_esperar(texto):
    """Suspende la captura hasta procesar la petición y cerrar la respuesta hablada."""
    global modo_conversacion_activa, ultima_interaccion_usuario

    gestor_audio.desactivar()
    gestor_audio._vaciar_queue()
    rec_main.Reset()
    try:
        procesar_texto_reconocido(texto)
    except Exception:
        logging.exception("Error procesando la petición reconocida.")
        hablar_async("Ocurrió un error al procesar tu petición.")
    finally:
        async_tts_manager.esperar_cola_vacia()
        gestor_audio.desactivar()
        gestor_audio._vaciar_queue()
        rec_main.Reset()
        if not detener_evento.is_set():
            gestor_audio.activar_procesamiento()
            modo_conversacion_activa = True
            ultima_interaccion_usuario = time.time()
            print("🎙️ Respuesta terminada; micrófono activo para continuar.")
        else:
            modo_conversacion_activa = False


def _ventana_respuesta_expirada():
    configuracion = cargar_configuracion_personalizacion()
    return (
        not configuracion["siempre_activo"]
        and gestor_audio.tiempo_sin_voz() > 10.0
    )


def _actualizar_configuracion_general():
    global palabras_clave, NOMBRE_ASISTENTE, NOMBRE_USUARIOS, rec_wake

    configuracion = cargar_configuracion_general()
    nombre = configuracion.get("NOMBRE_ASISTENTE", "").strip() or "asistente"
    usuarios = configuracion.get("NOMBRE_USUARIO", [])
    if nombre != NOMBRE_ASISTENTE:
        NOMBRE_ASISTENTE = nombre
        palabras_clave = configuracion
        rec_wake = KaldiRecognizer(modelo_vosk, 16000, json.dumps(palabras_clave))
    NOMBRE_USUARIOS = usuarios
    palabras_clave = configuracion
 
 
def _pasar_a_activo():
    """Transicion limpia ESPERA → ACTIVO.
    Espera a que el TTS termine antes de abrir el microfono para evitar
    que el asistente escuche su propia voz como un comando.
    """
    global modo_conversacion_activa, ultima_interaccion_usuario
    rec_main.Reset()
    # Esperar a que termine el saludo del TTS antes de escuchar.
    # Sin esto, 'Hola en que te ayudo' activa el wake word de nuevo.
    _esperar_fin_tts()
    gestor_audio.activar_procesamiento()
    modo_conversacion_activa   = True
    ultima_interaccion_usuario = time.time()
    print("\u25b6 Modo ACTIVO")
 
 
def _pasar_a_espera(motivo: str = ""):
    """Transición limpia ACTIVO/VENTANA → ESPERA."""
    global modo_conversacion_activa
    if motivo:
        print(motivo)
    modo_conversacion_activa = False
    rec_main.Reset()
    rec_wake.Reset()
    gestor_audio.activar_wake_word()       # Vosk vuelve a recibir frames
    print("⏸ Modo ESPERA")


def detener():
    """Solicita al bucle de escucha salir y permite ejecutar el cierre ordenado."""
    detener_evento.set()
 
def procesar_texto_reconocido(texto):
    """Procesa texto ya reconocido sin capturar nuevo audio"""
    if not texto:
        respuesta = "No pude entender lo que dijiste."
        hablar_async(respuesta)
        return respuesta
 
    try:
        # 1. Analizar intención
        intentos = procesar_intencion(texto)

        # 2. Guardar en memoria usando el método real (no el adaptador)
        configuracion = cargar_configuracion_personalizacion()
        if configuracion["habilitar_aprendizaje"]:
            resultado = gm.procesar_texto(texto, fuente="user")

            if resultado.get("procesado"):
                tipo_guardado = f"{resultado.get('tipo_memoria', 'desconocido')}_{resultado.get('categoria', 'general')}"
            else:
                tipo_guardado = f"descartado_{resultado.get('categoria', 'general')}"
            print(f"💾 Guardado como: {tipo_guardado}")
        else:
            print("🧠 Aprendizaje desactivado; no se guarda esta interacción en memoria.")
 
    except Exception as e:
        logging.exception("Error guardando en memoria: %s", e)
        print(f"⚠️ No se pudo guardar en memoria: {e}")
        intentos = []
 
    print(f"Texto reconocido: {texto}")
 
    respuesta = procesar_comando(texto, intentos)
    print(f"🤖 Respuesta: {respuesta}")
 
    return respuesta
 
 
# MODIFICAR LA FUNCIÓN cleanup:
def cleanup():
    print("\n Consolidando memoria antes de cerrar...")
    gm.consolidar_memoria()  # Mover memoria importante a largo plazo
    gm.cerrar()  # Cerrar BD y guardar índice FAISS
    gestor_audio.cerrar()

    
if __name__ == "__main__":
    try:
        escuchar()
    except KeyboardInterrupt:
        print("\n Cerrando aplicación...")
    finally:
        cleanup()
