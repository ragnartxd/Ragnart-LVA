import queue
import threading
import tempfile
import unittest
from pathlib import Path
import sys
import types
from unittest.mock import patch

import numpy as np

from backend.Gestor.gestor_audio import GestorAudio
from backend.Generacion import from_TTS

_memoria_falsa = types.ModuleType("backend.Gestor.gestor_memoria")
_memoria_falsa.GestorMemoriaV2 = lambda **_kwargs: object()
with (
    patch.object(GestorAudio, "inicializar", return_value=True),
    patch.dict(sys.modules, {"backend.Gestor.gestor_memoria": _memoria_falsa}),
):
    from backend import voz_estado, yatusabe


class _AudioStream:
    def __init__(self):
        self.read_started = threading.Event()
        self.release_read = threading.Event()

    def read(self, _frame_samples, exception_on_overflow=False):
        self.read_started.set()
        self.release_read.wait(timeout=2)
        return b"frame"


class TurnoDeAudioTests(unittest.TestCase):
    def test_deshabilitar_captura_descarta_el_frame_que_estaba_en_lectura(self):
        gestor = GestorAudio()
        gestor.stream = _AudioStream()
        gestor.running = True
        gestor.activar_procesamiento()

        with patch(
            "backend.Gestor.gestor_audio.estado_audio",
            return_value={"reproduciendo": False},
        ):
            hilo = threading.Thread(target=gestor._audio_loop)
            hilo.start()
            self.assertTrue(gestor.stream.read_started.wait(timeout=1))
            gestor.desactivar()
            gestor.running = False
            gestor.stream.release_read.set()
            hilo.join(timeout=1)

        self.assertFalse(hilo.is_alive())
        with self.assertRaises(queue.Empty):
            gestor.audio_queue.get_nowait()
        self.assertFalse(gestor.is_processing)
        self.assertFalse(gestor.is_listening)

    def test_peticion_no_reactiva_microfono_hasta_drenar_audio_tts(self):
        eventos = []

        class FakeAudio:
            def desactivar(self):
                eventos.append("microfono_desactivado")

            def _vaciar_queue(self):
                eventos.append("cola_vaciada")

            def activar_procesamiento(self):
                eventos.append("microfono_activado")

        class FakeRecognizer:
            def Reset(self):
                eventos.append("reconocedor_reiniciado")

        class FakeTTS:
            def esperar_cola_vacia(self):
                eventos.append("tts_finalizado")

        with (
            patch.object(yatusabe, "gestor_audio", FakeAudio()),
            patch.object(yatusabe, "rec_main", FakeRecognizer()),
            patch.object(yatusabe, "async_tts_manager", FakeTTS()),
            patch.object(yatusabe, "procesar_texto_reconocido", side_effect=lambda _: eventos.append("peticion_procesada")),
            patch.object(yatusabe, "detener_evento", threading.Event()),
        ):
            yatusabe._procesar_peticion_y_esperar("hola")

        self.assertLess(
            eventos.index("microfono_desactivado"),
            eventos.index("peticion_procesada"),
        )
        self.assertLess(
            eventos.index("peticion_procesada"),
            eventos.index("tts_finalizado"),
        )
        self.assertLess(
            eventos.index("tts_finalizado"),
            eventos.index("microfono_activado"),
        )

    def test_estado_de_voz_y_confirmacion_se_comparten_en_archivos_atomicos(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            with (
                patch.object(
                    voz_estado,
                    "_PLAYBACK_STATE",
                    Path(directorio) / "playback.json",
                ),
                patch.object(
                    voz_estado,
                    "_ANIMATION_ACK",
                    Path(directorio) / "ack.json",
                ),
            ):
                voz_estado.publicar_reproduccion("playback-1", True, True)
                estado = voz_estado.leer_estado_reproduccion()
                self.assertEqual(estado["playback_id"], "playback-1")
                self.assertEqual(estado["phase"], "playing")

                voz_estado.publicar_reproduccion("playback-1", False, True)
                self.assertEqual(
                    voz_estado.leer_estado_reproduccion()["phase"],
                    "audio_finished",
                )
                self.assertFalse(voz_estado.animacion_finalizada("playback-1"))
                voz_estado.confirmar_animacion_finalizada("playback-1")
                self.assertTrue(voz_estado.animacion_finalizada("playback-1"))

    def test_tts_no_reproduce_con_microfono_activo_hasta_ack_frontend(self):
        manager = from_TTS.AsyncTTSManager.__new__(from_TTS.AsyncTTSManager)
        manager.is_playing = threading.Event()
        manager.character_controller = None
        manager.is_playing.clear()

        ack_checks = []

        def frontend_confirmo(_playback_id):
            ack_checks.append(manager.is_playing.is_set())
            return len(ack_checks) >= 2

        with (
            patch.object(
                from_TTS,
                "cargar_configuracion_personalizacion",
                return_value={"nivel_audio": 50, "habilitar_animaciones": True},
            ),
            patch.object(from_TTS.sd, "play"),
            patch.object(from_TTS.sd, "wait"),
            patch.object(voz_estado, "publicar_reproduccion") as publicar,
            patch.object(voz_estado, "frontend_activo", side_effect=[True, True, True]),
            patch.object(voz_estado, "animacion_finalizada", side_effect=frontend_confirmo),
            patch.object(from_TTS.time, "sleep"),
        ):
            manager._reproducir(np.ones(4, dtype=np.float32), 24000)

        self.assertEqual(publicar.call_count, 2)
        self.assertTrue(publicar.call_args_list[0].kwargs["reproduciendo"])
        self.assertFalse(publicar.call_args_list[1].kwargs["reproduciendo"])
        self.assertEqual(ack_checks, [True, True, True])
        self.assertFalse(manager.is_playing.is_set())


if __name__ == "__main__":
    unittest.main()

