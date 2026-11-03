import os
from pathlib import Path
import numpy as np
import json
from faster_whisper import WhisperModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUTA_MODELOS = str(PROJECT_ROOT / "importaciones" / "faster-whisper-models")
os.makedirs(RUTA_MODELOS, exist_ok=True)

# Modelos disponibles: tiny, base, small, medium
# tiny   = 39 MB  (más rápido, menos preciso)
# base   = 74 MB  (equilibrado — recomendado con VAD externo)
# small  = 244 MB (buena precisión)
MODELO_NOMBRE = "small"

SAMPLE_RATE = 16000
# Duración mínima de audio para intentar transcripción (200 ms)
MIN_BYTES = int(SAMPLE_RATE * 0.2) * 2  # 200 ms @ 16 kHz int16 → 6400 bytes

print(f"🧠 Cargando Faster-Whisper ({MODELO_NOMBRE})...")
modelo = WhisperModel(
    MODELO_NOMBRE,
    device="cpu",
    compute_type="int8",   # cuantización para latencia mínima en CPU
    download_root=RUTA_MODELOS,
    num_workers=1,         # evitar overhead de múltiples workers en CPU
)
print("✅ Faster-Whisper cargado")


class FasterWhisperRecognizer:
    """
    Transcriptor batch. Contrato de uso:

    1. GestorAudio (modo ACTIVO) acumula voz con VAD y emite la frase
       COMPLETA como un único bloque de bytes (int16, 16 kHz).
    2. Este reconocedor convierte esos bytes a numpy float32 en memoria
       y los pasa directamente a Faster-Whisper. Sin archivos temporales.
    3. La API imita la de Vosk (AcceptWaveform / Result / Reset) para
       mantener compatibilidad con yatusabe.py.

    IMPORTANTE: NO usar AcceptWaveform en bucle frame a frame.
    GestorAudio entrega la frase ya completa; llamar AcceptWaveform
    una sola vez con el bloque entero.
    """

    def __init__(self, model: WhisperModel):
        self.model        = model
        self.audio_buffer = []    # acumula bloques de bytes
        self.sample_rate  = SAMPLE_RATE

    # ── API compatible con Vosk ───────────────────────────────────────────────

    def AcceptWaveform(self, data: bytes) -> bool:
        """
        Recibe el bloque completo de bytes de la frase (ya segmentada por VAD).
        Siempre devuelve True: el audio está listo para transcribir.
        """
        self.audio_buffer.append(data)
        return True

    def Result(self) -> str:
        """
        Transcribe el audio acumulado en memoria y devuelve JSON Vosk-compatible.
        No escribe nada a disco.
        """
        if not self.audio_buffer:
            return json.dumps({"text": ""})

        audio_bytes = b"".join(self.audio_buffer)
        self.audio_buffer.clear()

        if len(audio_bytes) < MIN_BYTES:
            logger_msg = f"⚠️ Audio muy corto ({len(audio_bytes)} bytes), descartado"
            print(logger_msg)
            return json.dumps({"text": ""})

        # ── Conversión int16 → float32 normalizado, TODO en memoria ──────────
        audio_np = (
            np.frombuffer(audio_bytes, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )
        # Faster-Whisper acepta numpy array directamente (sin ruta de archivo)

        try:
            segments, _info = self.model.transcribe(
                audio_np,
                language="es",
                beam_size=1,          # greedy search: mínima latencia
                best_of=1,            # sin sampling extra
                vad_filter=False,     # ya filtramos con Silero en GestorAudio
                temperature=0.0,      # determinístico
                condition_on_previous_text=False,  # sin contexto previo: más rápido
            )
            texto = " ".join(seg.text for seg in segments).strip()
            if texto:
                print(f"🎙️ Faster-Whisper: '{texto}'")
            else:
                print("🎙️ Faster-Whisper: sin texto detectado")
        except Exception as e:
            print(f"⚠️ Error en transcripción: {e}")
            texto = ""

        return json.dumps({"text": texto})

    def FinalResult(self) -> str:
        """Alias de Result() para compatibilidad con la API de Vosk."""
        return self.Result()

    def Reset(self):
        """Limpia el buffer entre frases."""
        self.audio_buffer.clear()

    # ── Método directo (sin pasar por JSON) ───────────────────────────────────

    def transcribir(self, audio_bytes: bytes) -> str:
        """
        Método optimizado: recibe bytes, devuelve texto directamente.
        Úsalo desde yatusabe.py en modo ACTIVO para evitar el round-trip JSON.

        Retorna cadena vacía si el audio es muy corto o no hay voz.
        """
        if not audio_bytes or len(audio_bytes) < MIN_BYTES:
            return ""

        audio_np = (
            np.frombuffer(audio_bytes, dtype=np.int16)
            .astype(np.float32) / 32768.0
        )

        try:
            segments, _info = self.model.transcribe(
                audio_np,
                language="es",
                beam_size=1,
                best_of=1,
                vad_filter=False,
                temperature=0.0,
                condition_on_previous_text=False,
                repetition_penalty=1.2,
                no_speech_threshold=0.3,
            )
            texto = " ".join(seg.text for seg in segments).strip()
        except Exception as e:
            print(f"⚠️ Error en transcripción directa: {e}")
            texto = ""

        return texto


# ── Instancias globales ────────────────────────────────────────────────────────
rec = FasterWhisperRecognizer(modelo)


def obtener_reconocedor() -> FasterWhisperRecognizer:
    return rec


def obtener_modelo() -> WhisperModel:
    return modelo


# ── Prueba standalone ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sounddevice as sd
    print("Grabando 3 segundos de prueba...")
    recording = sd.rec(int(3 * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    texto = rec.transcribir(recording.tobytes())
    print(f"Resultado: '{texto}'")
