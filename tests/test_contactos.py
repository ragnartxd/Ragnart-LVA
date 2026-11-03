import tempfile
import unittest
from pathlib import Path

from backend.contactos import cargar_contactos_guardados, guardar_contactos_guardados


class ContactosTests(unittest.TestCase):
    def test_archivo_ausente_inicia_con_agenda_vacia(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            ruta = Path(directorio) / "contactos.json"
            self.assertEqual(cargar_contactos_guardados(ruta), {})

    def test_guarda_y_carga_contactos_en_la_ruta_indicada(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as directorio:
            ruta = Path(directorio) / "contactos.json"
            contactos = {"contacto de prueba": "+000000000"}

            guardar_contactos_guardados(contactos, ruta)

            self.assertEqual(cargar_contactos_guardados(ruta), contactos)


if __name__ == "__main__":
    unittest.main()

