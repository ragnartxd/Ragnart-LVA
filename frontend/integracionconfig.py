from pathlib import Path
from PyQt5.QtWidgets import QWidget, QInputDialog
from frontend.config import Ui_MainWindow  # Importa tu diseño
from backend.configuracion_entorno import cargar_configuracion_api, guardar_configuracion_api

class IntegracionConfig(QWidget):

    """Gestiona las APIs sin guardar credenciales en archivos versionados."""

    BASE_APIS = {
        "Clima": "",
        "Noticias": "",
        "Imagen": "",
        "Gemini": "",
    }

    def __init__(self, ui: Ui_MainWindow):
        super().__init__()
        self.ui = ui  
        self.config = {}  
        self.config_file = (
            Path(__file__).resolve().parent.parent
            / "importaciones"
            / "config_integracion.json"
        )

        # Cargar datos iniciales
        self.config = self.cargar_configuracion()

        # Conectar botones con funciones
        self.ui.btnGuardar.clicked.connect(self.guardar_configuracion)
        self.ui.btnRestablecer.clicked.connect(self.restablecer_configuracion)
        self.ui.btnAgregarApi.clicked.connect(self.agregar_api)
        self.ui.btnEliminarApi.clicked.connect(self.eliminar_api)
        self.ui.btnCambiarClave.clicked.connect(self.cambiar_clave)
        self.ui.BoxApi.currentIndexChanged.connect(self.cambiar_api)

        # Mostrar clave de la API seleccionada
        self.cambiar_api()

    def cargar_configuracion(self):
        """Carga claves desde .env y migra cualquier valor legado del JSON."""
        self.config = cargar_configuracion_api(
            self.config_file, self.BASE_APIS.keys()
        )

        self.ui.BoxApi.clear()
        self.ui.BoxApi.addItems(self.config.keys())

        return self.config


    def guardar_configuracion(self):
        """Guarda claves en .env y nombres de servicios en JSON."""
        guardar_configuracion_api(self.config, self.config_file)

    def cambiar_api(self):
        """Actualiza el campo de clave según la API seleccionada"""
        api_actual = self.ui.BoxApi.currentText()
        self.ui.textClave.setText(self.config.get(api_actual, ""))

    def cambiar_clave(self):
        """Cambia la clave de la API seleccionada"""
        api_actual = self.ui.BoxApi.currentText()
        nueva_clave = self.ui.textClave.text()

        if api_actual:
            self.config[api_actual] = nueva_clave
            print(f"Clave de {api_actual} actualizada.")

    def agregar_api(self):
        """Agrega una nueva API"""
        nueva_api, ok = QInputDialog.getText(self, "Agregar API", "Nombre de la nueva API:")
        if ok and nueva_api:
            if nueva_api in self.config:
                print("⚠ La API ya existe.")
                return
            
            self.config[nueva_api] = ""
            self.ui.BoxApi.addItem(nueva_api)
            self.ui.BoxApi.setCurrentText(nueva_api)
            print(f"✅ API {nueva_api} agregada.")

    def eliminar_api(self):
        """Elimina APIs personalizadas (pero no las APIs base)"""
        api_actual = self.ui.BoxApi.currentText()
        
        if api_actual in self.BASE_APIS:
            print("⚠ No puedes eliminar una API base.")
            return

        if api_actual:
            self.config.pop(api_actual, None)
            self.ui.BoxApi.removeItem(self.ui.BoxApi.currentIndex())
            print(f"🗑 API {api_actual} eliminada.")

    def restablecer_configuracion(self):
        """Restaura las APIs base y elimina las personalizadas"""
        self.config = self.BASE_APIS.copy()
        self.ui.BoxApi.clear()
        self.ui.BoxApi.addItems(self.config.keys())
        self.ui.textClave.clear()
        print("🔄 Configuración restablecida.")
