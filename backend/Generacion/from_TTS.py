import numpy as np
import sounddevice as sd
import threading, queue, time, logging, glob, os
import uuid
from pathlib import Path
from vosk import Model, KaldiRecognizer
from backend.configuracion_usuario import (
    PROJECT_ROOT,
    cargar_configuracion_personalizacion,
)
from backend import voz_estado

"""
Motores disponibles:  "coqui" | "kokoro"

Pipeline de dos etapas (elimina el gap entre fragmentos):
  Cola de texto → [Hilo generador] → Cola de audio → [Hilo reproductor]
  Mientras se reproduce el fragmento N, ya se está generando el N+1.

Para elegir voz en Kokoro:
  - Voz simple   → KOKORO_VOZ = "em_santa"
  - Voz mezclada → KOKORO_VOZ = cargar_voz("bm_george") * 0.43 + cargar_voz("bm_lewis") * 0.17 + cargar_voz("em_santa") * 0.40
"""

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# UTILIDAD: cargar_voz
# ─────────────────────────────────────────────
def cargar_voz(nombre: str):
    import torch
    from kokoro import KPipeline as _KP
    hf = os.path.expanduser("~/.cache/huggingface/hub")
    matches = glob.glob(f"{hf}/**/voices/{nombre}.pt", recursive=True)
    if matches:
        return torch.load(matches[0], weights_only=True)
    logger.info(f"⬇️  Descargando voz {nombre} (solo esta vez)...")
    for _ in _KP(lang_code="e")(".", voice=nombre, speed=1.0):
        pass
    matches = glob.glob(f"{hf}/**/voices/{nombre}.pt", recursive=True)
    if matches:
        return torch.load(matches[0], weights_only=True)
    raise FileNotFoundError(f"No se encontró {nombre}.pt en caché")


# ═════════════════════════════════════════════
#  CONFIGURACIÓN — edita solo aquí
# ═════════════════════════════════════════════

MOTOR = "kokoro"   # "coqui" | "kokoro"

# ── Coqui ────────────────────────────────────
COQUI_MODEL      = "tts_models/es/css10/vits"
COQUI_SAMPLERATE = 22050

# ── Kokoro ───────────────────────────────────
KOKORO_LANG       = "e"
KOKORO_SAMPLERATE = 24000

#KOKORO_VOZ = "em_santa"
KOKORO_VOZ = cargar_voz("bm_george") * 0.43 + cargar_voz("bm_lewis") * 0.17 + cargar_voz("em_santa") * 0.40

# ── Pipeline ──────────────────────────────────
# Cuántos audios pre-generar por adelantado.
# 1 = genera el siguiente mientras reproduce el actual (recomendado)
# 2 = genera dos por adelantado (más RAM, menos gap en textos cortos)
AUDIO_QUEUE_MAXSIZE = 2

# ═════════════════════════════════════════════


# ── Vosk ─────────────────────────────────────
_vosk_model_path = Path(
    os.environ.get(
        "ASISTENTE_VOSK_MODEL_PATH",
        str(PROJECT_ROOT / "importaciones" / "vosk-model-es-0.42" / "vosk-model-es-0.42"),
    )
)
if not _vosk_model_path.is_absolute():
    _vosk_model_path = PROJECT_ROOT / _vosk_model_path
VOSK_MODEL_PATH = str(_vosk_model_path.resolve())
VOSK_SAMPLERATE = 16000

# ─────────────────────────────────────────────
# CARGA DE VOSK (una sola vez al arrancar)
# ─────────────────────────────────────────────
if not os.path.isdir(VOSK_MODEL_PATH):
    raise FileNotFoundError(
        "No se encontró el modelo local de Vosk en "
        f"'{VOSK_MODEL_PATH}'. Comprueba que esté descomprimido y que contenga "
        "las carpetas am, conf y graph."
    )

try:
    _vosk_model = Model(VOSK_MODEL_PATH)
except Exception as exc:
    raise RuntimeError(
        f"Vosk no pudo cargar el modelo local en '{VOSK_MODEL_PATH}'. "
        "Comprueba que el modelo esté completo y que haya memoria disponible. "
        "Si tienes otro modelo Vosk local más ligero, indica su ruta en "
        "ASISTENTE_VOSK_MODEL_PATH."
    ) from exc
_vosk_rec   = KaldiRecognizer(_vosk_model, VOSK_SAMPLERATE)
logger.info("✅ Vosk cargado")

# ─────────────────────────────────────────────
# CARGA DEL MOTOR TTS (una sola vez al arrancar)
# ─────────────────────────────────────────────
if MOTOR == "coqui":
    from TTS.api import TTS as _CoquiTTS
    _engine = _CoquiTTS(model_name=COQUI_MODEL, progress_bar=True).to("cpu")
    logger.info(f"✅ Coqui cargado: {COQUI_MODEL}")

elif MOTOR == "kokoro":
    from kokoro import KPipeline
    _engine = KPipeline(lang_code=KOKORO_LANG)
    logger.info("✅ Kokoro cargado")

else:
    raise ValueError(f"MOTOR desconocido: '{MOTOR}'. Usa 'coqui' o 'kokoro'.")


# ─────────────────────────────────────────────
# GESTOR ASÍNCRONO DE TTS — pipeline 2 etapas
# ─────────────────────────────────────────────

class AsyncTTSManager:
    """
    Gestor de TTS con pipeline de dos etapas:

      text_queue  → hilo _generador  → audio_queue  → hilo _reproductor

    El reproductor nunca espera generación: cuando termina un audio,
    el siguiente ya está listo (o casi) en audio_queue.
    """

    def __init__(self):
        # Cola de entrada: textos a procesar
        self.text_queue  = queue.Queue()

        # Cola intermedia: audios ya generados, listos para reproducir
        # Tamaño limitado para no pre-generar infinito y desperdiciar RAM
        self.audio_queue = queue.Queue(maxsize=AUDIO_QUEUE_MAXSIZE)

        # Eventos de estado
        self.is_playing  = threading.Event()
        self.stop_event  = threading.Event()

        # Para esperar_cola_vacia: contamos ítems pendientes de principio a fin
        self._pendientes = 0
        self._pendientes_lock = threading.Lock()
        self._todo_listo = threading.Condition(self._pendientes_lock)

        self.character_controller = None

        # Arrancar ambos hilos
        self._hilo_gen  = threading.Thread(target=self._generador,  daemon=True, name="tts-gen")
        self._hilo_play = threading.Thread(target=self._reproductor, daemon=True, name="tts-play")
        self._hilo_gen.start()
        self._hilo_play.start()
        logger.info("🎵 Pipeline TTS iniciado (generador + reproductor)")

    # ── Utilidades ───────────────────────────

    def change_number_to_words(self, texto: str) -> str:
        from backend.utils.numero_texto import digitos_a_palabras
        return digitos_a_palabras(texto)

    def set_character_controller(self, controller):
        self.character_controller = controller
        logger.info("🎭 Controlador de personaje conectado al TTS")

    # ── Etapa 1: generador ───────────────────

    def _generador(self):
        """Toma textos de text_queue, genera audio, lo pone en audio_queue."""
        while not self.stop_event.is_set():
            try:
                item = self.text_queue.get(timeout=1.0)
                if item is None:
                    self.audio_queue.put(None)  # propagar señal de parada
                    break

                texto = item
                try:
                    audio, samplerate = self._generar(texto)
                    # put() bloquea si audio_queue está llena — eso es intencional:
                    # no genera más de AUDIO_QUEUE_MAXSIZE por adelantado
                    self.audio_queue.put((audio, samplerate))
                except Exception as e:
                    logger.error(f"❌ Error generando audio: {e}")
                    with self._todo_listo:
                        self._pendientes -= 1
                        self._todo_listo.notify_all()

                self.text_queue.task_done()

            except queue.Empty:
                continue

    def _generar(self, texto: str) -> tuple[np.ndarray, int]:
        """Genera y devuelve (audio_array, samplerate) sin reproducir."""
        configuracion = cargar_configuracion_personalizacion()
        velocidad = 0.5 + max(0, min(100, configuracion["velocidad_voz"])) / 100
        if MOTOR == "coqui":
            audio = np.array(_engine.tts(text=texto), dtype=np.float32)
            if velocidad != 1.0:
                import librosa
                audio = librosa.effects.time_stretch(audio, rate=velocidad)
            return audio, COQUI_SAMPLERATE

        elif MOTOR == "kokoro":
            voz = configuracion["voz_ia"].strip() or KOKORO_VOZ
            if isinstance(voz, str) and os.path.isfile(os.path.expanduser(voz)):
                import torch
                voz = torch.load(os.path.expanduser(voz), map_location="cpu", weights_only=True)
            chunks = [
                np.array(a, dtype=np.float32)
                for _, _, a in _engine(texto, voice=voz, speed=velocidad)
            ]
            audio = np.concatenate(chunks) if chunks else np.array([], dtype=np.float32)
            return audio, KOKORO_SAMPLERATE

    # ── Etapa 2: reproductor ─────────────────

    def _reproductor(self):
        """Toma audios de audio_queue y los reproduce secuencialmente."""
        while not self.stop_event.is_set():
            try:
                item = self.audio_queue.get(timeout=1.0)
                if item is None:
                    break

                audio, samplerate = item
                try:
                    self._reproducir(audio, samplerate)
                except Exception as e:
                    logger.exception(f"❌ Error reproduciendo audio: {e}")
                finally:
                    self.audio_queue.task_done()
                    with self._todo_listo:
                        self._pendientes -= 1
                        self._todo_listo.notify_all()

            except queue.Empty:
                continue

    def _reproducir(self, audio: np.ndarray, samplerate: int):
        configuracion = cargar_configuracion_personalizacion()
        playback_id = uuid.uuid4().hex
        self.is_playing.set()
        try:
            try:
                voz_estado.publicar_reproduccion(
                    playback_id,
                    reproduciendo=True,
                    animaciones=configuracion["habilitar_animaciones"],
                )
            except OSError:
                logger.exception("No se pudo notificar al frontend el inicio del audio.")
            nivel_audio = max(0, min(100, configuracion["nivel_audio"])) / 100
            sd.play(audio * nivel_audio, samplerate=samplerate)
            sd.wait()
        finally:
            try:
                try:
                    voz_estado.publicar_reproduccion(
                        playback_id,
                        reproduciendo=False,
                        animaciones=configuracion["habilitar_animaciones"],
                    )
                except OSError:
                    logger.exception("No se pudo notificar al frontend el fin del audio.")
                if voz_estado.frontend_activo():
                    limite = time.monotonic() + 10
                    while (
                        not voz_estado.animacion_finalizada(playback_id)
                        and voz_estado.frontend_activo()
                        and time.monotonic() < limite
                    ):
                        time.sleep(0.03)
                    if not voz_estado.animacion_finalizada(playback_id):
                        logger.warning(
                            "El frontend no confirmó el cierre de boca para la reproducción %s.",
                            playback_id,
                        )
            finally:
                self.is_playing.clear()

    # ── API pública ──────────────────────────

    def hablar_async(self, texto: str):
        """Añade texto a la cola para reproducción asíncrona."""
        if not texto or not texto.strip():
            return
        texto = texto.strip()

        # Opcional: convertir números a palabras para mejor pronunciación solo coqui el kokoro ya lo hace.
        if MOTOR == "coqui":
            texto = self.change_number_to_words(texto)

        with self._todo_listo:
            self._pendientes += 1

        self.text_queue.put(texto)
        logger.debug(f"📝 Cola: '{texto[:50]}'")

    # No usamos esta función, pero la dejamos para compatibilidad con código legacy
    def hablar_sync(self, texto: str):
        """Reproduce texto de forma síncrona (bloquea hasta terminar)."""
        texto = texto.strip()
        if MOTOR == "coqui":
            texto = self.change_number_to_words(texto)
        audio, samplerate = self._generar(texto)
        self._reproducir(audio, samplerate)

    def esperar_cola_vacia(self):
        """Bloquea hasta que todos los textos encolados hayan sido reproducidos."""
        with self._todo_listo:
            self._todo_listo.wait_for(lambda: self._pendientes == 0)

    def limpiar_cola(self):
        """Descarta todos los textos pendientes (no interrumpe el audio actual)."""
        vaciados = 0
        while not self.text_queue.empty():
            try:
                self.text_queue.get_nowait()
                self.text_queue.task_done()
                vaciados += 1
            except queue.Empty:
                break
        # También descartar audios ya generados pero no reproducidos
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.task_done()
                vaciados += 1
            except queue.Empty:
                break
        with self._todo_listo:
            self._pendientes = max(0, self._pendientes - vaciados)
            self._todo_listo.notify_all()
        logger.info("🧹 Cola limpiada")

    def parar_audio(self):
        """Detiene la reproducción actual y limpia todo."""
        self.limpiar_cola()
        sd.stop()
        self.is_playing.clear()

    def obtener_estado(self) -> dict:
        return {
            "motor":             MOTOR,
            "cola_texto":        self.text_queue.qsize(),
            "cola_audio":        self.audio_queue.qsize(),
            "pendientes_total":  self._pendientes,
            "reproduciendo":     self.is_playing.is_set(),
            "gen_activo":        self._hilo_gen.is_alive(),
            "play_activo":       self._hilo_play.is_alive(),
        }

    def shutdown(self):
        """Cierra el gestor de forma segura."""
        self.stop_event.set()
        self.text_queue.put(None)
        self._hilo_gen.join(timeout=3.0)
        self._hilo_play.join(timeout=3.0)
        logger.info("🔇 Gestor de audio cerrado")


# ─────────────────────────────────────────────
# INSTANCIA GLOBAL
# ─────────────────────────────────────────────
async_tts_manager = AsyncTTSManager()


# ─────────────────────────────────────────────
# FUNCIONES PÚBLICAS
# ─────────────────────────────────────────────

def hablar(texto: str):
    """Función legacy síncrona para compatibilidad."""
    async_tts_manager.hablar_sync(texto)

def hablar_async(texto: str):
    """Nueva función asíncrona para reproducción no bloqueante."""
    async_tts_manager.hablar_async(texto)

def esperar_audio():
    """Espera a que termine todo el audio pendiente."""
    async_tts_manager.esperar_cola_vacia()

def limpiar_audio():
    """Limpia todo el audio pendiente."""
    async_tts_manager.limpiar_cola()

def parar_audio():
    """Detiene inmediatamente la reproducción."""
    async_tts_manager.parar_audio()

def estado_audio() -> dict:
    """Devuelve el estado del sistema de audio."""
    return async_tts_manager.obtener_estado()

def cola_audio_vacia() -> bool:
    """Verifica si no hay nada pendiente."""
    return async_tts_manager._pendientes == 0

def tamaño_cola_audio() -> int:
    """Devuelve el número total de fragmentos pendientes."""
    return async_tts_manager._pendientes

def conectar_controlador_personaje(controller):
    """Conecta el controlador del personaje al sistema TTS."""
    async_tts_manager.set_character_controller(controller)


# ─────────────────────────────────────────────
# FUNCIONES PÚBLICAS — VOSK
# ─────────────────────────────────────────────

def obtener_modelo() -> Model:
    """Devuelve el modelo Vosk ya inicializado."""
    return _vosk_model

def obtener_reconocedor() -> KaldiRecognizer:
    """Devuelve el reconocedor Vosk ya inicializado."""
    return _vosk_rec


# ─────────────────────────────────────────────
# PRUEBAS
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print(f"=== Pruebas de TTS Asíncrono [{MOTOR.upper()}] ===")

    print("\n1. Prueba de audio asíncrono:")
    hablar_async("Este es el primer fragmento.")
    hablar_async("Este es el segundo fragmento.")
    hablar_async("Y este es el tercer fragmento.")

    print("✅ Tres fragmentos añadidos a la cola")
    print(f"📊 Estado: {estado_audio()}")

    for i in range(5):
        print(f"⚙️ Haciendo otras tareas... {i+1}/5")
        time.sleep(1)

    print("⏳ Esperando a que termine el audio...")
    esperar_audio()
    print("✅ Todo el audio ha terminado")

    print("\n2. Prueba de audio síncrono:")
    hablar("Este es un mensaje síncrono que bloquea.")
    print("✅ Audio síncrono completado")

    async_tts_manager.shutdown()
