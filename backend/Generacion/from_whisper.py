import os
import numpy as np
import whisper
import sounddevice as sd
import logging, json, soundfile as sf

# === CONFIGURACIÓN ===
# Carpeta donde se guardarán los modelos Whisper
RUTA_MODELOS = os.path.join(".", "importaciones", "whisper-models")
os.makedirs(RUTA_MODELOS, exist_ok=True)

# Tamaño del modelo (puedes cambiarlo a tiny, base, small, medium, large)
MODELO_NOMBRE = "small"

# === LOGGING ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"🧠 Inicializando Whisper en: {RUTA_MODELOS}")

# === CARGA DEL MODELO ===
# Se descargará automáticamente si no existe
modelo = whisper.load_model(MODELO_NOMBRE, download_root=RUTA_MODELOS)
logger.info(f"✅ Modelo Whisper '{MODELO_NOMBRE}' cargado desde {RUTA_MODELOS}")

# === CLASE COMPATIBLE CON VOSK ===
class WhisperRecognizer:
    def __init__(self, model):
        self.model = model
        self.audio_buffer = []
        self.sample_rate = 16000

    def AcceptWaveform(self, data):
        """Simula el mismo comportamiento que Vosk.AcceptWaveform"""
        self.audio_buffer.append(data)
        audio_len = len(b"".join(self.audio_buffer))
        # 3 segundos aprox de audio
        if audio_len >= 96000 * 3:
            return True
        return False

    def Result(self):
        """Procesa el audio acumulado y devuelve JSON compatible con Vosk."""
        audio_bytes = b"".join(self.audio_buffer)
        self.audio_buffer.clear()

        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        import uuid

        # Crear carpeta temporal local (dentro del proyecto)
        tmp_dir = os.path.join(".", "importaciones", "temp_audio")
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f"whisper_{uuid.uuid4().hex}.wav")

        sf.write(tmp_path, audio_np, self.sample_rate)
        result = self.model.transcribe(tmp_path, language="es")

        # Eliminar el archivo temporal manualmente después de procesar
        try:
            os.remove(tmp_path)
        except Exception:
            pass


        texto = result["text"].strip()
        return json.dumps({"text": texto})

    def FinalResult(self):
        """Alias de Result."""
        return self.Result()

    def Reset(self):
        """Limpia el buffer de audio."""
        self.audio_buffer.clear()


# Instancia global, igual que en from_TTS.py
rec = WhisperRecognizer(modelo)

def obtener_reconocedor():
    return rec

def obtener_modelo():
    return modelo

# === PRUEBA MANUAL ===
if __name__ == "__main__":
    print("🎙️ Prueba de WhisperRecognizer (5s de grabación)")
    import sounddevice as sd

    rec = obtener_reconocedor()
    print("Habla algo...")

    duration = 5
    recording = sd.rec(int(duration * 16000), samplerate=16000, channels=1, dtype='int16')
    sd.wait()

    rec.audio_buffer.append(recording.tobytes())
    result = json.loads(rec.Result())
    print("Texto reconocido:", result["text"])
