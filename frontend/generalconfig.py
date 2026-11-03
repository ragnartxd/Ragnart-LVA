from PyQt5.QtWidgets import QWidget
from frontend.config import Ui_MainWindow
from backend.configuracion_general import (
    cargar_configuracion_general,
    guardar_configuracion_general as guardar_configuracion_json,
)


class GeneralConfig(QWidget):
    def __init__(self, ui: Ui_MainWindow):
        super().__init__()
        self.ui = ui  # Recibe la interfaz y la almacena
        
        # Cargar datos iniciales
        self.cargar_configuracion()
        
        # Conectar botones con funciones
        self.ui.btnGuardar.clicked.connect(self.guardar_configuracion)
        self.ui.btnRestablecer.clicked.connect(self.restablecer_configuracion)

    def cargar_configuracion(self):
        """Carga las preferencias personales desde JSON."""
        try:
            datos = cargar_configuracion_general()
            self.ui.TextnombreAsistente.setText(datos.get("NOMBRE_ASISTENTE", ""))
            usuarios = datos.get("NOMBRE_USUARIO", [])
            self.ui.TextNombreUsuario1.setText(usuarios[0] if len(usuarios) > 0 else "")
            self.ui.TextNombreUsuario2.setText(usuarios[1] if len(usuarios) > 1 else "")
            self.ui.TextNombreUsuario3.setText(usuarios[2] if len(usuarios) > 2 else "")
            self.ui.BoxEleccionIdioma.setCurrentText(datos.get("IDIOMA", "Español"))
        except Exception as e:
            print(f"❌ Error al cargar la configuración: {e}")


    def guardar_configuracion(self):
        """Guarda la configuración en un archivo"""
        nombre_asistente = self.ui.TextnombreAsistente.text()
        nombre_usuario1 = self.ui.TextNombreUsuario1.text()
        nombre_usuario2 = self.ui.TextNombreUsuario2.text()
        nombre_usuario3 = self.ui.TextNombreUsuario3.text()
        idioma = self.ui.BoxEleccionIdioma.currentText()

        actualizar_nombre_asistente(nombre_asistente)  # 🔹 Actualiza el backend


        guardar_configuracion_json({
            "NOMBRE_ASISTENTE": nombre_asistente or "",
            "NOMBRE_USUARIO": [
                nombre for nombre in (
                    nombre_usuario1,
                    nombre_usuario2,
                    nombre_usuario3,
                ) if nombre
            ],
            "IDIOMA": idioma or "",
        })

    def restablecer_configuracion(self):
        """Borra la configuración y deja los campos vacíos"""
        self.ui.TextnombreAsistente.clear()
        self.ui.BoxEleccionIdioma.setCurrentText("Español")  # Restablecer al idioma predeterminado
        self.ui.TextNombreUsuario2.clear()
        self.ui.TextNombreUsuario3.clear()
        self.ui.BoxEleccionIdioma.setCurrentIndex(0)  # Primera opción (Español)

def actualizar_nombre_asistente(nuevo_nombre):
    """Cambia el nombre de activación por voz del asistente"""
    global NOMBRE_ASISTENTE
    NOMBRE_ASISTENTE = nuevo_nombre.lower()
    print(f"Nombre del asistente actualizado a: {nuevo_nombre}")

NOMBRES_USUARIOS=[]
def actualizar_nombre_usuario(nombres):
    """Actualiza el nombre del usuario para personalizar respuestas"""
    global NOMBRES_USUARIOS
    NOMBRES_USUARIOS = [nombre for nombre in nombres if nombre]
    print (f"Nombre de usuarios actualizados {NOMBRES_USUARIOS}")

'''def actualizar_idioma_ia(nuevo_idioma):
    """Modifica el idioma en el que la IA procesa el lenguaje"""
    if nuevo_idioma == "Español":
        procesador_intencion.IDIOMA_MODELO = "es"
    elif nuevo_idioma == "Inglés":
        procesador_intencion.IDIOMA_MODELO = "en"
    elif nuevo_idioma == "Francés":
        procesador_intencion.IDIOMA_MODELO = "fr"
    print(f"Idioma de la IA actualizado a: {nuevo_idioma}")'''