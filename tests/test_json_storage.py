import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.utils.json_storage import guardar_json_atomico


class GuardadoJsonAtomicoTests(unittest.TestCase):
    def _tempdir(self):
        return tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)

    def test_crea_directorio_y_preserva_unicode_formato_y_salto_final(self):
        with self._tempdir() as directorio:
            ruta = Path(directorio) / "nueva" / "datos.json"
            datos = {"título": "reunión", "activa": True}

            guardar_json_atomico(ruta, datos, indent=2, ensure_ascii=False)

            contenido = ruta.read_text(encoding="utf-8")
            self.assertEqual(json.loads(contenido), datos)
            self.assertIn("reunión", contenido)
            self.assertTrue(contenido.endswith("\n"))
            self.assertEqual(list(ruta.parent.glob("*.tmp")), [])

    def test_fallo_de_serializacion_conserva_destino_y_limpia_temporal(self):
        with self._tempdir() as directorio:
            ruta = Path(directorio) / "datos.json"
            original = '{"anterior": true}\n'
            ruta.write_text(original, encoding="utf-8")

            with self.assertRaises(TypeError):
                guardar_json_atomico(ruta, {"invalido": object()}, indent=2)

            self.assertEqual(ruta.read_text(encoding="utf-8"), original)
            self.assertEqual(list(Path(directorio).glob("*.tmp")), [])

    def test_admite_serializador_personalizado_y_sin_salto_final(self):
        with self._tempdir() as directorio:
            ruta = Path(directorio) / "cache.json"
            guardar_json_atomico(
                ruta,
                {"ruta": Path("local")},
                indent=2,
                ensure_ascii=False,
                default=str,
                trailing_newline=False,
            )

            contenido = ruta.read_text(encoding="utf-8")
            self.assertEqual(json.loads(contenido), {"ruta": "local"})
            self.assertFalse(contenido.endswith("\n"))

    def test_estado_de_voz_persiste_con_el_mismo_formato_de_datos(self):
        from backend import voz_estado

        with self._tempdir() as directorio:
            ruta = Path(directorio) / "playback.json"
            with patch.object(voz_estado, "_PLAYBACK_STATE", ruta):
                voz_estado.publicar_reproduccion("turno-1", True, True)
                estado = voz_estado.leer_estado_reproduccion()

        self.assertEqual(estado["playback_id"], "turno-1")
        self.assertEqual(estado["phase"], "playing")
        self.assertTrue(estado["animaciones"])


if __name__ == "__main__":
    unittest.main()
