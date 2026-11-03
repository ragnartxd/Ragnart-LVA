import tempfile
import threading
import os
import sys
import types
import unittest
from datetime import datetime as DateTime
from pathlib import Path
from unittest.mock import Mock, patch

# sentence-transformers funciona con PyTorch; impedir que Transformers intente
# importar el runtime TensorFlow opcional del entorno de escritorio.
os.environ.setdefault("USE_TF", "0")

# Las acciones de escritorio son dependencias opcionales para estas pruebas:
# ninguna prueba debe necesitar pulsar teclas o emitir sonidos reales.
try:
    import pyautogui  # noqa: F401
except ImportError:
    escritorio_falso = types.ModuleType("pyautogui")
    escritorio_falso.press = Mock()
    escritorio_falso.click = Mock()
    escritorio_falso.position = Mock(return_value=types.SimpleNamespace(x=0, y=0))
    sys.modules["pyautogui"] = escritorio_falso
try:
    import winsound  # noqa: F401
except ImportError:
    sonido_falso = types.ModuleType("winsound")
    sonido_falso.PlaySound = Mock()
    sonido_falso.SND_ALIAS = 0
    sys.modules["winsound"] = sonido_falso

# TTS y reconocimiento de voz tienen modelos/librerías locales que no hacen
# falta al probar la lógica de sistema; su interfaz se reemplaza por una voz nula.
voz_falsa = types.ModuleType("backend.Generacion.from_TTS")
voz_falsa.hablar = Mock()
sys.modules.setdefault("backend.Generacion.from_TTS", voz_falsa)

from backend.Funciones import funcionesSistema as sistema
from backend.Funciones import funcionesSistema2 as sistema2


class FuncionesSistemaTests(unittest.TestCase):
    def _tempdir(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)

    def _despachar_desde_voz(self, texto):
        from backend.Gestor.GestorParametros import Gestor_Parametros
        from backend.Gestor.action import ejecutar_handler
        from backend.Gestor.procesador_intencion import procesar_intencion

        intento = procesar_intencion(texto)[0]
        datos = Gestor_Parametros.procesar(
            {"accion": intento["accion"], "params": intento.get("params", {})}
        )
        return intento, ejecutar_handler(
            intento["accion"],
            texto_comando=intento.get("texto", texto),
            **datos["params"],
        )

    def test_cronometro_espera_en_un_hilo_y_rechaza_duracion_no_positiva(self):
        with patch.object(
            sistema.Gestor_Parametros,
            "procesar",
            return_value={"params": {"segundos": 2}},
        ), patch.object(sistema.threading, "Thread") as hilo:
            resultado = sistema.poner_cronometro(segundos=2)

        self.assertIn("2 segundos", resultado)
        objetivo = hilo.call_args.kwargs["target"]
        with patch.object(sistema.time, "sleep") as dormir, patch("builtins.print"):
            objetivo()
        dormir.assert_called_once_with(2)

        with patch.object(
            sistema.Gestor_Parametros,
            "procesar",
            return_value={"params": {"segundos": 0}},
        ):
            self.assertIn("mayor que cero", sistema.poner_cronometro(segundos=0))

    def test_gestionar_ventana_pasa_la_accion_validada(self):
        ventana = Mock()
        ventana.title = "Bloc de notas"
        ventana.isMinimized = False
        with patch.object(sistema, "obtener_ventana", return_value=ventana):
            resultado = sistema.minimizar_aplicacion(nombre_app="Bloc de notas")

        ventana.minimize.assert_called_once_with()
        self.assertIn("Minimizar", resultado)

    def test_acciones_de_ventana_cubren_cerrar_maximizar_minimizar_y_alternar(self):
        for accion, metodo in (
            (sistema.cerrar_aplicacion, "close"),
            (sistema.minimizar_aplicacion, "minimize"),
            (sistema.maximizar_aplicacion, "maximize"),
            (sistema.alternar_aplicacion, "minimize"),
        ):
            with self.subTest(accion=accion.__name__):
                ventana = Mock()
                ventana.title = "Ventana simulada"
                ventana.isMinimized = False
                with patch.object(sistema, "obtener_ventana", return_value=ventana):
                    resultado = accion(nombre_app="Ventana simulada")
                getattr(ventana, metodo).assert_called_once_with()
                self.assertIn("Ventana simulada", resultado)

    def test_referencia_a_ventana_actual_resuelve_la_ventana_activa(self):
        ventana = Mock()
        ventana.title = "Editor de texto"
        pygetwindow_falso = types.ModuleType("pygetwindow")
        pygetwindow_falso.getActiveWindow = Mock(return_value=ventana)
        pygetwindow_falso.getAllWindows = Mock()

        with patch.dict(sys.modules, {"pygetwindow": pygetwindow_falso}):
            encontrada = sistema.obtener_ventana("la ventana actual")

        self.assertIs(encontrada, ventana)
        pygetwindow_falso.getActiveWindow.assert_called_once_with()
        pygetwindow_falso.getAllWindows.assert_not_called()

    def test_nombre_de_ventana_vacio_no_se_convierte_en_primera_ventana(self):
        pygetwindow_falso = types.ModuleType("pygetwindow")
        pygetwindow_falso.getActiveWindow = Mock()
        pygetwindow_falso.getAllWindows = Mock(return_value=[Mock(title="Cualquier ventana")])

        with patch.dict(sys.modules, {"pygetwindow": pygetwindow_falso}):
            encontrada = sistema.obtener_ventana("   ")

        self.assertIsNone(encontrada)
        pygetwindow_falso.getAllWindows.assert_not_called()

    def test_ruta_de_voz_cierra_ventana_actual_hasta_el_handler(self):
        from backend.Gestor.procesador_intencion import procesar_intencion
        from backend.Gestor.GestorParametros import Gestor_Parametros
        from backend.Gestor.action import ejecutar_handler

        intentos = procesar_intencion("cierra la ventana actual")
        self.assertEqual(intentos[0]["accion"], "cerrar_aplicacion")
        self.assertEqual(intentos[0]["params"]["nombre_app"], "ventana actual")

        datos = Gestor_Parametros.procesar(
            {"accion": intentos[0]["accion"], "params": intentos[0]["params"]}
        )
        ventana = Mock()
        ventana.title = "Ventana simulada"
        pygetwindow_falso = types.ModuleType("pygetwindow")
        pygetwindow_falso.getActiveWindow = Mock(return_value=ventana)
        pygetwindow_falso.getAllWindows = Mock()

        with patch.dict(sys.modules, {"pygetwindow": pygetwindow_falso}):
            resultado = ejecutar_handler(intentos[0]["accion"], **datos["params"])

        ventana.close.assert_called_once_with()
        self.assertIn("Ventana simulada", resultado)

    def test_ruta_de_voz_calendario_pregunta_datos_y_guarda_evento_local(self):
        with self._tempdir() as directorio:
            ruta = Path(directorio) / "calendario" / "eventos.json"
            with patch.object(sistema2, "_EVENTOS_PATH", ruta), patch.object(
                sistema2,
                "decir_y_escuchar",
                side_effect=["Cita médica", "2030-06-15", "08:30"],
            ):
                intento, resultado = self._despachar_desde_voz("agendar evento")
                eventos = sistema2._cargar_eventos()

        self.assertEqual(intento["accion"], "marcar_calendario_evento")
        self.assertIn("Cita médica", resultado)
        self.assertEqual(eventos[0]["fecha"], "2030-06-15")

    def test_ruta_de_voz_pdf_selecciona_archivo_y_usa_resumen_local_simulado(self):
        with self._tempdir() as directorio:
            pdf = Path(directorio) / "entrada.pdf"
            pdf.write_bytes(b"pdf simulado")
            pagina = Mock()
            pagina.get_text.return_value = "Contenido local"
            pagina.get_images.return_value = []
            documento = Mock()
            documento.__enter__ = Mock(return_value=[pagina])
            documento.__exit__ = Mock(return_value=False)
            fitz_falso = types.ModuleType("fitz")
            fitz_falso.open = Mock(return_value=documento)
            selector_falso = types.ModuleType("backend.utils.utils_obtenerArchivo")
            selector_falso.seleccionar_archivo_con_arrastre = Mock(return_value=str(pdf))
            generacion_falsa = types.ModuleType("backend.Generacion.AIGeneration")
            generacion_falsa.generar_con_modelo = Mock(return_value="Resumen local")

            with patch.dict(
                sys.modules,
                {
                    "fitz": fitz_falso,
                    "backend.utils.utils_obtenerArchivo": selector_falso,
                    "backend.Generacion.AIGeneration": generacion_falsa,
                },
            ):
                intento, resultado = self._despachar_desde_voz("resumir un pdf")

        self.assertEqual(intento["accion"], "convertir_pdf_para_ollama")
        self.assertEqual(resultado["resumen"], "Resumen local")
        self.assertIn("Contenido local", resultado["texto"])

    def test_intencion_de_secuencia_llega_al_handler_con_nombre_de_parametro_de_voz(self):
        from backend.Gestor.action import action_global, ejecutar_handler

        self.assertIn("ejecutar_comando", action_global)
        with patch.object(
            sistema,
            "ejecutar_comando_secuencia",
            return_value="secuencia recibida",
        ) as handler:
            resultado = ejecutar_handler(
                "ejecutar_comando", comando_voz="reproduce la secuencia diaria"
            )

        self.assertEqual(resultado, "secuencia recibida")
        handler.assert_called_once_with(comando_voz="reproduce la secuencia diaria")

    def test_secuencia_de_voz_acepta_el_parametro_del_intent_actual(self):
        with patch.object(
            sistema, "grabar_secuencia", return_value=[("tecla", "enter")]
        ), patch.object(sistema, "guardar_secuencia") as guardar:
            resultado = sistema.ejecutar_comando_secuencia(
                comando_voz="graba la secuencia y guárdala como prueba"
            )

        guardar.assert_called_once_with("prueba", [("tecla", "enter")])
        self.assertIn("guardada correctamente", resultado)

    def test_ruta_de_voz_graba_comando_y_pide_nombre_antes_de_capturar(self):
        with patch.object(sistema, "decir_y_escuchar", return_value="macro_test"), patch.object(
            sistema, "grabar_secuencia", return_value=[("tecla", "enter")]
        ), patch.object(sistema, "guardar_secuencia") as guardar:
            intento, resultado = self._despachar_desde_voz("graba el comando")

        self.assertEqual(intento["accion"], "ejecutar_comando")
        guardar.assert_called_once_with("macro_test", [("tecla", "enter")])
        self.assertIn("guardada correctamente", resultado)

    def test_repetir_comando_reproduce_la_ultima_secuencia_guardada(self):
        sistema.sequences["ultima_prueba"] = [("tecla", "enter")]
        try:
            with patch.object(sistema, "reproducir_secuencia") as reproducir:
                resultado = sistema.ejecutar_comando_secuencia(
                    texto_comando="repite la accion anterior"
                )
            reproducir.assert_called_once_with("ultima_prueba")
            self.assertIn("ultima_prueba", resultado)
        finally:
            sistema.sequences.pop("ultima_prueba", None)

    def test_reproduccion_de_secuencia_ejecuta_accion_y_respeta_salida(self):
        class HiloControlado:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                pass

            def join(self):
                pass

        escritorio = sys.modules["pyautogui"]
        sistema.sequences["prueba_unitaria"] = [("tecla", "enter")]
        sistema.stop_replay = False

        def pulsar(tecla):
            sistema.stop_replay = True

        with patch.object(sistema.threading, "Thread", HiloControlado), patch.object(
            escritorio, "press", side_effect=pulsar
        ) as presionar, patch.object(sistema.time, "sleep"):
            sistema.reproducir_secuencia("prueba_unitaria")

        presionar.assert_called_once_with("enter")
        sistema.sequences.pop("prueba_unitaria", None)

    def test_grabacion_de_secuencia_cierra_hook_tras_inactividad(self):
        teclado_falso = types.ModuleType("keyboard")
        teclado_falso.hook = Mock(return_value="hook")
        teclado_falso.unhook = Mock()

        with patch.dict(sys.modules, {"keyboard": teclado_falso}), patch.object(
            sistema.ctypes.windll.user32, "GetAsyncKeyState", return_value=0
        ), patch.object(sistema.time, "monotonic", side_effect=[0.0, 3.1]), patch.object(
            sistema.time, "sleep"
        ), patch.object(sistema, "hablar"):
            acciones = sistema.grabar_secuencia()

        self.assertEqual(acciones, [])
        teclado_falso.hook.assert_called_once()
        teclado_falso.unhook.assert_called_once_with("hook")

    def test_guardado_de_secuencia_persiste_json_y_actualiza_memoria(self):
        with self._tempdir() as directorio:
            ruta = Path(directorio) / "sequences.json"
            with patch.object(sistema, "sequences_path", str(ruta)), patch.object(
                sistema, "hablar"
            ):
                sistema.guardar_secuencia("secuencia_test", [("tecla", "enter")])
                contenido = __import__("json").loads(ruta.read_text(encoding="utf-8"))

        self.assertEqual(contenido["secuencia_test"], [["tecla", "enter"]])
        sistema.sequences.pop("secuencia_test", None)

    def test_correo_sin_credenciales_no_intenta_conectar(self):
        entorno_falso = types.ModuleType("backend.configuracion_entorno")
        entorno_falso.obtener_variable_entorno = Mock(return_value=None)

        with patch.dict(sys.modules, {"backend.configuracion_entorno": entorno_falso}), patch.object(
            sistema.smtplib, "SMTP_SSL"
        ) as smtp:
            resultado = sistema.handler_enviar_correo(
                destinatario="destino@example.test", asunto="prueba", cuerpo="texto"
            )

        self.assertIn("Correo no configurado", resultado)
        smtp.assert_not_called()

    def test_correo_configurado_envia_conexion_simulada(self):
        entorno_falso = types.ModuleType("backend.configuracion_entorno")
        entorno_falso.obtener_variable_entorno = Mock(
            side_effect=["asistente@example.test", "clave-local"]
        )
        servidor = Mock()
        contexto_smtp = Mock()
        contexto_smtp.__enter__ = Mock(return_value=servidor)
        contexto_smtp.__exit__ = Mock(return_value=False)

        with patch.dict(sys.modules, {"backend.configuracion_entorno": entorno_falso}), patch.object(
            sistema, "cargar_contactos_guardados", return_value={}
        ), patch.object(sistema.smtplib, "SMTP_SSL", return_value=contexto_smtp):
            resultado = sistema.handler_enviar_correo(
                destinatario="destino@example.test", asunto="Prueba", cuerpo="Mensaje local"
            )

        self.assertIn("Correo enviado a destino@example.test", resultado)
        servidor.login.assert_called_once_with("asistente@example.test", "clave-local")
        servidor.sendmail.assert_called_once()

    def test_escritura_word_genera_y_guarda_con_dependencias_locales_simuladas(self):
        with self._tempdir() as directorio:
            (Path(directorio) / "Desktop").mkdir()
            documento_falso = Mock()
            documento_falso.save.side_effect = lambda ruta: Path(ruta).write_bytes(b"docx")
            docx_falso = types.ModuleType("docx")
            docx_falso.Document = Mock(return_value=documento_falso)
            generacion_falsa = types.ModuleType("backend.Generacion.AIGeneration")
            generacion_falsa.generator_gemma3 = Mock(return_value="Contenido generado")

            with patch.dict(
                sys.modules,
                {"docx": docx_falso, "backend.Generacion.AIGeneration": generacion_falsa},
            ), patch.object(sistema.os.path, "expanduser", return_value=directorio), patch.object(
                sistema, "decir_y_escuchar", return_value="no"
            ):
                resultado = sistema.handler_escribir_word(texto_completo="tema general")
                self.assertIn("Documento creado en:", resultado)
                documento_falso.add_paragraph.assert_called_once_with("Contenido generado")
                ruta_creada = Path(resultado.split(": ", 1)[1].rstrip("."))
                self.assertTrue(ruta_creada.is_file())


    def test_handler_de_hora_usa_formato_validado(self):
        with patch.object(
            sistema.Gestor_Parametros,
            "procesar",
            return_value={"params": {"formato_24h": True}},
        ), patch.object(sistema.datetime, "datetime", wraps=DateTime) as reloj:
            reloj.now.return_value = DateTime(2030, 1, 1, 14, 5, 9)
            resultado = sistema.handler_obtener_hora(formato_24h=True)
        self.assertIn("14:05:09", resultado)

    def test_alarma_rechaza_horas_fuera_de_rango(self):
        with patch.object(
            sistema.Gestor_Parametros,
            "procesar",
            return_value={"params": {"hora_texto": "25:80"}},
        ), patch.object(sistema.threading, "Timer") as temporizador:
            resultado = sistema.poner_alarma(hora_texto="25:80")

        self.assertIn("entre 00:00 y 23:59", resultado)
        temporizador.assert_not_called()

    def test_alarma_valida_programa_temporizador_sin_esperar(self):
        with patch.object(
            sistema.Gestor_Parametros,
            "procesar",
            return_value={"params": {"hora_texto": "23:59"}},
        ), patch.object(sistema.datetime, "datetime", wraps=DateTime) as reloj, patch.object(
            sistema.threading, "Timer"
        ) as temporizador:
            reloj.now.return_value = DateTime(2030, 1, 1, 12, 0)
            resultado = sistema.poner_alarma(hora_texto="23:59")

        self.assertIn("23:59", resultado)
        temporizador.assert_called_once()
        temporizador.return_value.start.assert_called_once_with()

    def test_ruta_de_voz_alarma_interpreta_hora_hablada_con_articulos(self):
        with patch.object(sistema.threading, "Timer") as temporizador:
            intento, resultado = self._despachar_desde_voz("ponme una alarma a las 7")

        self.assertEqual(intento["accion"], "poner_alarma")
        self.assertIn("07:00", resultado)
        temporizador.assert_called_once()

    def test_ruta_de_voz_cronometro_convierte_minutos_a_segundos(self):
        with patch.object(sistema.threading, "Thread") as hilo:
            intento, resultado = self._despachar_desde_voz(
                "pon un temporizador por cinco minutos"
            )

        self.assertEqual(intento["accion"], "poner_cronometro")
        self.assertIn("300 segundos", resultado)
        hilo.assert_called_once()

    def test_comandos_de_energia_se_despachan_sin_ejecutar_acciones_reales(self):
        comandos = {
            "apagar_sistema": "shutdown /s /t 0",
            "reiniciar_sistema": "shutdown /r /t 0",
            "suspender_sistema": "rundll32.exe powrprof.dll,SetSuspendState 0,1,0",
            "bloquear_sistema": "rundll32.exe user32.dll,LockWorkStation",
        }
        for accion, comando in comandos.items():
            with self.subTest(accion=accion), patch.object(
                sistema.os, "system", return_value=0
            ) as ejecutar:
                resultado = getattr(sistema, accion)()
                ejecutar.assert_called_once_with(comando)
                self.assertNotIn("Error", resultado)

    def test_wifi_y_volumen_usen_sus_adaptadores_del_sistema(self):
        with patch.object(sistema.os, "system", return_value=0) as ejecutar_comando:
            self.assertIn("activado", sistema.activar_wifi())
        self.assertIn("netsh interface set interface", ejecutar_comando.call_args.args[0])

        escritorio = sys.modules["pyautogui"]
        with patch.object(escritorio, "press") as pulsar, patch.object(
            sistema.time, "sleep"
        ):
            self.assertIn("aumentado", sistema.subir_volumen())
            self.assertIn("reducido", sistema.bajar_volumen())
        self.assertEqual(
            [llamada.args[0] for llamada in pulsar.call_args_list],
            ["volumeup"] * 5 + ["volumedown"] * 5,
        )

    def test_bluetooth_invoca_el_script_local_con_estado_validado(self):
        proceso = Mock(returncode=0, stderr="")
        with patch.object(sistema.subprocess, "run", return_value=proceso) as ejecutar:
            resultado = sistema.activar_bluetooth("activar bluetooth")

        self.assertIn("correctamente", resultado)
        self.assertEqual(ejecutar.call_args.args[0][-1], "on")
        self.assertTrue(Path(ejecutar.call_args.args[0][-2]).is_file())

    def test_bluetooth_admite_orden_de_desactivacion(self):
        proceso = Mock(returncode=0, stderr="")
        with patch.object(sistema.subprocess, "run", return_value=proceso) as ejecutar:
            resultado = sistema.activar_bluetooth("  DESACTIVAR BLUETOOTH  ")
        self.assertIn("correctamente", resultado)
        self.assertEqual(ejecutar.call_args.args[0][-1], "off")

    def test_ruta_de_voz_bluetooth_usa_comando_contexto_si_el_slot_llega_vacio(self):
        proceso = Mock(returncode=0, stderr="")
        with patch.object(sistema.subprocess, "run", return_value=proceso) as ejecutar:
            intento, resultado = self._despachar_desde_voz("enciende bluetooth")

        self.assertEqual(intento["accion"], "activar_bluetooth")
        self.assertIn("correctamente", resultado)
        self.assertEqual(ejecutar.call_args.args[0][-1], "on")

    def test_ruta_de_voz_bluetooth_resuelve_desactivacion_con_articulo(self):
        proceso = Mock(returncode=0, stderr="")
        with patch.object(sistema.subprocess, "run", return_value=proceso) as ejecutar:
            intento, resultado = self._despachar_desde_voz("desactiva el bluetooth")

        self.assertEqual(intento["accion"], "activar_bluetooth")
        self.assertIn("correctamente", resultado)
        self.assertEqual(ejecutar.call_args.args[0][-1], "off")

    def test_brillo_rechaza_valores_invalidos_antes_de_invocar_powershell(self):
        with patch.object(sistema.subprocess, "run") as ejecutar:
            resultado = sistema.ajustar_brillo(101)

        self.assertIn("entre 0 y 100", resultado)
        ejecutar.assert_not_called()

    def test_brillo_valido_invoca_powershell_y_devuelve_confirmacion(self):
        with patch.object(
            sistema.subprocess, "run", return_value=Mock(returncode=0, stderr="")
        ) as ejecutar:
            resultado = sistema.ajustar_brillo(50)
        self.assertEqual(resultado, "Brillo ajustado a 50.")
        self.assertEqual(ejecutar.call_args.kwargs["timeout"], 15)

    def test_bluetooth_rechaza_entrada_no_textual_sin_excepcion(self):
        resultado = sistema.activar_bluetooth(None)
        self.assertIn("inválido", resultado.lower())

    def test_brillo_convierte_timeout_de_powershell_en_respuesta_controlada(self):
        with patch.object(
            sistema.subprocess,
            "run",
            side_effect=sistema.subprocess.TimeoutExpired("powershell", 15),
        ):
            resultado = sistema.ajustar_brillo(50)
        self.assertIn("No se pudo ajustar el brillo", resultado)

    def test_cronometro_rechaza_booleano_como_duracion(self):
        with patch.object(sistema.threading, "Thread") as hilo:
            resultado = sistema.poner_cronometro(segundos=True)
        self.assertIn("duración", resultado.lower())
        hilo.assert_not_called()

    def test_calendario_crea_mueve_y_elimina_eventos_en_ruta_configurada(self):
        with self._tempdir() as directorio:
            ruta = Path(directorio) / "calendario" / "eventos.json"
            with patch.object(sistema2, "_EVENTOS_PATH", ruta):
                creado = sistema2.marcar_calendario_evento(
                    "Reunión", "2030-05-12", "09:30"
                )
                movido = sistema2.mover_evento_calendario(
                    "reunión", "2030-05-13", "10:30"
                )
                guardados = sistema2._cargar_eventos()
                eliminado = sistema2.eliminar_evento_calendario("REUNIÓN")

        self.assertIn("marcado", creado)
        self.assertIn("movido", movido)
        self.assertEqual(guardados[0]["fecha"], "2030-05-13")
        self.assertIn("eliminado", eliminado)
        self.assertEqual(guardados[0]["titulo"], "Reunión")

    def test_calendario_rechaza_fecha_invalida_sin_escribir(self):
        with self._tempdir() as directorio:
            ruta = Path(directorio) / "eventos.json"
            with patch.object(sistema2, "_EVENTOS_PATH", ruta):
                resultado = sistema2.marcar_calendario_evento(
                    "Reunión", "fecha", "25:80"
                )

        self.assertIn("formato incorrecto", resultado)
        self.assertFalse(ruta.exists())

    def test_conversion_pdf_resume_texto_y_retorna_imagenes_extraidas(self):
        with self._tempdir() as directorio:
            ruta_pdf = Path(directorio) / "entrada.pdf"
            ruta_pdf.write_bytes(b"pdf simulado")
            pagina = Mock()
            pagina.get_text.return_value = "Texto de prueba del documento"
            pagina.get_images.return_value = []
            documento = Mock()
            documento.__enter__ = Mock(return_value=[pagina])
            documento.__exit__ = Mock(return_value=False)
            fitz_falso = types.ModuleType("fitz")
            fitz_falso.open = Mock(return_value=documento)

            with patch.dict(sys.modules, {"fitz": fitz_falso}), patch(
                "backend.Generacion.AIGeneration.generar_con_modelo",
                return_value=iter(["Resumen ", "generado"]),
            ) as generar:
                resultado = sistema2.convertir_pdf_para_ollama(
                    str(ruta_pdf),
                    str(Path(directorio) / "imagenes"),
                )

        self.assertEqual(resultado["resumen"], "Resumen generado")
        self.assertIn("Texto de prueba", resultado["texto"])
        self.assertEqual(resultado["imagenes"], [])
        self.assertIn("Texto de prueba", generar.call_args.kwargs["prompt"])

if __name__ == "__main__":
    unittest.main()
