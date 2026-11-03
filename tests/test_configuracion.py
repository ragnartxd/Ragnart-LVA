import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import configuracion_entorno
from backend import configuracion_general
from backend import configuracion_usuario


class ConfiguracionEntornoTests(unittest.TestCase):
    def test_migra_claves_heredadas_de_json_a_env(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            ruta_config = Path(directorio) / "apis.json"
            ruta_config.write_text(
                json.dumps({"Clima": "clave-local", "Noticias": ""}),
                encoding="utf-8",
            )
            with patch.object(configuracion_entorno, "ENV_FILE", Path(directorio) / ".env"):
                with patch.dict(os.environ):
                    os.environ.pop("RAGNART_API_CLIMA", None)
                    os.environ.pop("RAGNART_API_NOTICIAS", None)
                    resultado = configuracion_entorno.cargar_configuracion_api(
                        ruta_config, ("Clima", "Noticias")
                    )
                    json_guardado = ruta_config.read_text(encoding="utf-8")
                    env_guardado = configuracion_entorno._leer_archivo_env()

            self.assertEqual(resultado["Clima"], "clave-local")
            self.assertEqual(env_guardado["RAGNART_API_CLIMA"], "clave-local")
            self.assertNotIn("clave-local", json_guardado)
            self.assertEqual(json.loads(json_guardado), {"Clima": "", "Noticias": ""})

    def test_guardar_claves_preserva_otras_variables_env(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            env_file = Path(directorio) / ".env"
            ruta_config = Path(directorio) / "apis.json"
            env_file.write_text('SPOTIFY_CLIENT_ID="cliente"\n', encoding="utf-8")
            with patch.object(configuracion_entorno, "ENV_FILE", env_file):
                with patch.dict(os.environ):
                    configuracion_entorno.guardar_configuracion_api(
                        {"Clima": "nueva-clave", "Mi servicio": "otra-clave"},
                        ruta_config,
                    )
                    variables = configuracion_entorno._leer_archivo_env()
                    json_guardado = json.loads(ruta_config.read_text(encoding="utf-8"))

            self.assertEqual(variables["SPOTIFY_CLIENT_ID"], "cliente")
            self.assertEqual(variables["RAGNART_API_CLIMA"], "nueva-clave")
            self.assertEqual(variables["RAGNART_API_MI_SERVICIO"], "otra-clave")
            self.assertEqual(json_guardado, {"Clima": "", "Mi servicio": ""})

    def test_rechaza_nombres_de_servicio_que_colisionan(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            with patch.object(
                configuracion_entorno,
                "ENV_FILE",
                Path(directorio) / ".env",
            ):
                with self.assertRaises(ValueError):
                    configuracion_entorno.guardar_configuracion_api(
                        {"mi-servicio": "una", "mi servicio": "dos"},
                        Path(directorio) / "apis.json",
                    )


class ConfiguracionGeneralTests(unittest.TestCase):
    def test_round_trip_de_preferencias_json(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            ruta_config = Path(directorio) / "config_general.json"
            with patch.object(configuracion_general, "CONFIG_FILE", ruta_config):
                configuracion_general.guardar_configuracion_general({
                    "NOMBRE_ASISTENTE": "asistente",
                    "NOMBRE_USUARIO": ["Ana", "Luis"],
                    "IDIOMA": "Español",
                })
                resultado = configuracion_general.cargar_configuracion_general()

            self.assertEqual(resultado["NOMBRE_ASISTENTE"], "asistente")
            self.assertEqual(resultado["NOMBRE_USUARIO"], ["Ana", "Luis"])
            self.assertEqual(resultado["IDIOMA"], "Español")


class ConfiguracionUsuarioTests(unittest.TestCase):
    def test_preferencias_de_personalizacion_se_comparten_con_el_backend(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            ruta = Path(directorio) / "config_personalizacion.json"
            configuracion = configuracion_usuario.CONFIG_PERSONALIZACION_DEFAULT.copy()
            configuracion.update({
                "nivel_audio": 25,
                "velocidad_voz": 75,
                "personalidad": "Responde de forma breve.",
                "habilitar_aprendizaje": True,
            })
            configuracion_usuario.guardar_configuracion_personalizacion(configuracion, ruta)

            resultado = configuracion_usuario.cargar_configuracion_personalizacion(ruta)

            self.assertEqual(resultado["nivel_audio"], 25)
            self.assertEqual(resultado["velocidad_voz"], 75)
            self.assertEqual(resultado["personalidad"], "Responde de forma breve.")
            self.assertTrue(resultado["habilitar_aprendizaje"])

    def test_preferencias_de_respuestas_se_comparten_con_el_backend(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            ruta = Path(directorio) / "respuestas_config.json"
            configuracion_usuario.guardar_configuracion_respuestas(
                {"recordar_contexto": False, "max_conversaciones": 4},
                ruta,
            )

            resultado = configuracion_usuario.cargar_configuracion_respuestas(ruta)

            self.assertFalse(resultado["recordar_contexto"])
            self.assertEqual(resultado["max_conversaciones"], 4)

    def test_rechaza_valores_de_slider_no_enteros(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            ruta = Path(directorio) / "config_personalizacion.json"
            ruta.write_text(json.dumps({"nivel_audio": "alto"}), encoding="utf-8")

            with self.assertRaises(ValueError):
                configuracion_usuario.cargar_configuracion_personalizacion(ruta)


if __name__ == "__main__":
    unittest.main()

