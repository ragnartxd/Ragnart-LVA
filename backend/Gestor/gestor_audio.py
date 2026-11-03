import threading, queue, time, logging, pyaudio
import numpy as np
from collections import deque
from backend.Generacion.from_TTS import estado_audio

logger = logging.getLogger(__name__)

# ── Parámetros ajustables ─────────────────────────────────────────────────────
SAMPLE_RATE    = 16000
FRAME_MS       = 32
FRAME_SAMPLES  = int(SAMPLE_RATE * FRAME_MS / 1000)
VAD_THRESHOLD  = 0.5      # 0.5 evita capturar eco del TTS y ruido ambiente
SILENCE_TIMEOUT_S = 1   # silencio para cerrar una frase
MIN_SPEECH_MS  = 200      # descartar alucinaciones cortas de Whisper (<300ms)
VENTANA_ACTIVO_S = 10.0   # ventana de conversación sin wake word


class _SileroVAD:
    """
    Wrapper sobre Silero VAD. Corre 100% local en CPU (~2 MB).
    """
    def __init__(self):
        import torch
        self._torch = torch
        logger.info("Cargando Silero VAD...")
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        self.model = model
        self.model.eval()
        logger.info("Silero VAD listo")

    def probabilidad(self, pcm_bytes: bytes) -> float:
        """
        Recibe FRAME_SAMPLES muestras int16 @ 16 kHz.
        Devuelve probabilidad de voz humana entre 0.0 y 1.0.
        """
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = self._torch.from_numpy(audio).unsqueeze(0)
        with self._torch.no_grad():
            return self.model(tensor, SAMPLE_RATE).item()


class GestorAudio:
    """
    Tres modos de operación con responsabilidades claramente separadas:

    ESPERA   → Audio continuo frame a frame → Vosk (wake word).
               Sin VAD: Vosk necesita cada frame sin interrupciones.

    ACTIVO   → VAD acumula frames de voz en un buffer interno.
               Al detectar silencio, emite la frase COMPLETA como
               un único bloque de bytes (numpy-ready) → Faster-Whisper.
               Nunca emite frames sueltos al transcriptor.

    VENTANA  → Igual que ACTIVO pero la ventana de 10 s controla
               si el usuario sigue hablando sin necesitar wake word.
               Si tiempo_sin_voz() > VENTANA_ACTIVO_S → volver a ESPERA.
    """

    def __init__(self):
        self.p              = None
        self.stream         = None
        self.audio_queue    = queue.Queue()
        self.is_listening   = False   # ESPERA
        self.is_processing  = False   # ACTIVO / VENTANA
        self.running        = False
        self.thread         = None
        self._vad           = None

        # Segmentación interna (ACTIVO / VENTANA)
        
        self._buf            = []
        self._silence_frames = 0
        self._in_speech      = False
        self._pre_buf = deque(maxlen=5)  # ~150 ms de historial
        self._silence_limit  = int(SILENCE_TIMEOUT_S * 1000 / FRAME_MS)
        self._ultima_voz     = 0.0    # timestamp última voz real
        self._mode_lock      = threading.Lock()
        self._mode_epoch     = 0

    # ── Ciclo de vida ─────────────────────────────────────────────────────────

    def inicializar(self) -> bool:
        """Carga VAD e inicia PyAudio. Devuelve True si todo está correcto."""
        try:
            self._vad = _SileroVAD()
        except Exception as e:
            logger.error(f"No se pudo cargar Silero VAD: {e}")
            logger.error("Ejecuta: pip install torch torchaudio")
            return False

        try:
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=SAMPLE_RATE,
                input=True,
                frames_per_buffer=FRAME_SAMPLES,
            )
            self.running = True
            self.thread  = threading.Thread(target=self._audio_loop, daemon=True)
            self.thread.start()
            print("✅ Gestor de audio con VAD inicializado")
            return True
        except Exception as e:
            logger.exception(f"Error inicializando PyAudio: {e}")
            return False

    def cerrar(self):
        self.running = self.is_listening = self.is_processing = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        print("Gestor de audio cerrado")

    # ── Cambios de modo ───────────────────────────────────────────────────────

    def activar_wake_word(self):
        """Modo ESPERA: frames continuos a la queue → Vosk."""
        with self._mode_lock:
            self._mode_epoch += 1
            self._reset_seg()
            self.is_listening  = True
            self.is_processing = False
            self._vaciar_queue()
        print("🔇 Modo ESPERA (esperando wake word)")

    def activar_procesamiento(self):
        """Modo ACTIVO/VENTANA: VAD acumula y emite frases completas."""
        with self._mode_lock:
            self._mode_epoch += 1
            self._reset_seg()
            self.is_processing = True
            self.is_listening  = False
            self._vaciar_queue()
            self._ultima_voz   = time.time()
        print("🎙️ Modo ACTIVO (escuchando comando)")

    def desactivar(self):
        with self._mode_lock:
            self._mode_epoch += 1
            self.is_listening  = False
            self.is_processing = False
            self._reset_seg()
            self._vaciar_queue()

    # ── Interfaz pública ──────────────────────────────────────────────────────

    def obtener_audio_data(self, timeout=0.1):
        """
        Devuelve datos de audio de la queue o None si está vacía.

        En modo ESPERA: bytes de un frame (32 ms) → Vosk.
        En modo ACTIVO: bytes de una frase completa → Faster-Whisper.
        """
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def tiempo_sin_voz(self) -> float:
        """
        Segundos desde la última voz humana detectada en modo ACTIVO/VENTANA.
        El ruido ambiente NO actualiza este valor → ventana expira correctamente.
        """
        if self._ultima_voz == 0.0:
            return 0.0
        return time.time() - self._ultima_voz

    # ── Loop de captura (hilo interno) ────────────────────────────────────────

    def _audio_loop(self):
        while self.running and self.stream:
            try:
                # Si asistente esta reproduciendo no procesar datos de entrada.
                if estado_audio().get("reproduciendo", False):
                    time.sleep(0.01)
                    continue

                with self._mode_lock:
                    if not (self.is_listening or self.is_processing):
                        modo_captura = None
                        epoca_captura = self._mode_epoch
                    else:
                        modo_captura = "espera" if self.is_listening else "activo"
                        epoca_captura = self._mode_epoch
                if modo_captura is None:
                    time.sleep(0.01)
                    continue

                data = self.stream.read(FRAME_SAMPLES, exception_on_overflow=False)

                with self._mode_lock:
                    if (
                        epoca_captura != self._mode_epoch
                        or not (self.is_listening or self.is_processing)
                    ):
                        continue
                    if modo_captura == "espera" and self.is_listening:
                        self.audio_queue.put(data)
                    elif modo_captura == "activo" and self.is_processing:
                        prob = self._vad.probabilidad(data)
                        self._frame_activo(data, prob)

            except Exception as e:
                if self.running:
                    logger.exception(f"Error en loop de audio: {e}")
                break

    # ── Segmentación VAD (modo ACTIVO/VENTANA) ────────────────────────────────

    def _frame_activo(self, frame: bytes, prob: float):
        """
        Acumula frames de voz en buffer interno.
        Al detectar silencio suficiente, emite la frase completa a la queue.

        Nota: el resultado emitido es un único bloque de bytes que representa
        la frase entera. Faster-Whisper lo convierte a numpy directamente,
        sin escribir nada a disco.
        """
        self._pre_buf.append(frame)
        hay_voz = prob >= VAD_THRESHOLD

        if hay_voz:
            self._ultima_voz = time.time()

            if not self._in_speech:
                self._in_speech = True
                self._silence_frames = 0
                self._buf.extend(self._pre_buf)
                logger.debug(f"Inicio de frase (prob={prob:.2f})")
            self._buf.append(frame)
            self._silence_frames = 0

        else:
            if self._in_speech:
                self._silence_frames += 1
                self._buf.append(frame)   # padding de silencio al final
                if self._silence_frames >= self._silence_limit:
                    self._emitir_frase()

    def _emitir_frase(self):
        """
        Concatena el buffer y lo pone en la queue como un único bloque.
        Faster-Whisper recibirá esto directamente como numpy array.
        """
        duracion_ms = len(self._buf) * FRAME_MS
        if duracion_ms >= MIN_SPEECH_MS:
            frase_completa = b"".join(self._buf)
            self.audio_queue.put(frase_completa)
            logger.debug(f"Frase emitida ({duracion_ms} ms, {len(frase_completa)} bytes)")
        else:
            logger.debug(f"Frase descartada, muy corta ({duracion_ms} ms)")
        self._reset_seg()

    def _reset_seg(self):
        self._buf            = []
        self._silence_frames = 0
        self._in_speech      = False

    def _vaciar_queue(self):
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break


# Instancia global
gestor_audio = GestorAudio()