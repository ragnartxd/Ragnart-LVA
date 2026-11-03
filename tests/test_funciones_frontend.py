import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.Gestor.GestorParametros import Gestor_Parametros
from backend.Gestor.action import ejecutar_handler


class AbrirConfiguracionTests(unittest.TestCase):
    def test_accion_abre_el_panel_en_un_proceso_separado(self):
        project_root = Path(__file__).resolve().parent.parent
        with patch("backend.Funciones.funcionesFrontend.subprocess.Popen") as lanzar:
            resultado = ejecutar_handler("abrir_configuracion")

        self.assertEqual(resultado, "Abriendo el panel de configuración.")
        lanzar.assert_called_once_with(
            [sys.executable, "-m", "frontend.interfaz_logica"],
            cwd=project_root,
        )

    def test_intencion_se_configura_sin_parametros(self):
        parametros = Gestor_Parametros.procesar({
            "accion": "abrir_configuracion",
            "params": {},
        })
        self.assertEqual(parametros, {"accion": "abrir_configuracion", "params": {}})

        ruta_intenciones = (
            Path(__file__).resolve().parent.parent
            / "importaciones"
            / "intenciones"
            / "intents.json"
        )
        with ruta_intenciones.open(encoding="utf-8") as archivo:
            intenciones = json.load(archivo)
        self.assertIn("abrir_configuracion", intenciones)
        self.assertIn(
            "abre el panel de configuración",
            intenciones["abrir_configuracion"]["ejemplos"],
        )


if __name__ == "__main__":
    unittest.main()
