import os
from pathlib import Path
from frontend.config import Ui_MainWindow
from backend.configuracion_usuario import (
    PROJECT_ROOT,
    RESPUESTAS_FILE,
    cargar_configuracion_personalizacion,
    cargar_configuracion_respuestas,
    guardar_configuracion_respuestas,
)

CONFIG_FILE = RESPUESTAS_FILE

class RespuestasConfig:
    def __init__(self, ui: Ui_MainWindow):
        super().__init__()
        self.ui = ui  
        
        """Carga o inicializa la configuración del historial y actualización de IA."""
        self.config = self.cargar_configuracion()  

        # Conectar botones con funciones
        self.ui.btnGuardar.clicked.connect(self.guardar_configuracion)
        self.ui.checkBoxContexto.clicked.connect(self.cambiar_contexto)
        self.ui.checkBoxHistorial.clicked.connect(self.eliminar_historial)
        self.ui.spinBoxCantidadConversacion.valueChanged.connect(self.establecer_max_conversaciones)

        # Actualizar UI con los valores cargados
        self.actualizar_ui()

    def actualizar_ui(self):
        """Actualiza la interfaz gráfica con los valores de configuración cargados."""
        self.ui.checkBoxContexto.setChecked(self.config.get("recordar_contexto", False))
        self.ui.checkBoxHistorial.setChecked(False)  # No almacena estado, solo elimina historial
        self.ui.spinBoxCantidadConversacion.setValue(self.config.get("max_conversaciones", 0))
        self.config["actualizar_ia_mes"] = False
        self.ui.checkBoxActualizarMes.setChecked(False)
        self.ui.checkBoxActualizarMes.setEnabled(False)
        self.ui.checkBoxActualizarMes.setToolTip(
            "No disponible: el proyecto no tiene una rutina de actualización mensual definida."
        )

    def cargar_configuracion(self):
        """Carga la configuración desde el archivo JSON o inicializa si no existe."""
        return cargar_configuracion_respuestas(CONFIG_FILE)

    def guardar_configuracion(self, nueva_config=None):
        """Guarda la configuración en el archivo JSON y actualiza la UI."""
        if nueva_config is not None:
            if not isinstance(nueva_config, dict):
                print("⚠ Error: Intento de guardar algo que no es un diccionario.", nueva_config)
                return  
            self.config = nueva_config  

        self.config["actualizar_ia_mes"] = False
        guardar_configuracion_respuestas(self.config, CONFIG_FILE)

        print("✅ Configuración guardada correctamente:", self.config)  
        self.actualizar_ui()  

    def cambiar_contexto(self):
        """Activa o desactiva el recordatorio del contexto."""
        self.config["recordar_contexto"] = self.ui.checkBoxContexto.isChecked()
        self.guardar_configuracion(self.config)

    def establecer_max_conversaciones(self):
        """Define cuántas conversaciones se guardarán."""
        self.config["max_conversaciones"] = self.ui.spinBoxCantidadConversacion.value()
        self.guardar_configuracion(self.config)

    def eliminar_historial(self):
        """Elimina el historial de conversaciones."""
        ruta_guardado = cargar_configuracion_personalizacion()["ruta_guardado"].strip()
        ruta_guardado = os.path.expandvars(os.path.expanduser(ruta_guardado))
        if ruta_guardado and not os.path.isabs(ruta_guardado):
            ruta_guardado = str(PROJECT_ROOT / ruta_guardado)
        directorio = (
            Path(ruta_guardado) / "conversacion"
            if ruta_guardado
            else PROJECT_ROOT / "conversacion"
        )
        archivos = list(directorio.glob("historial_*.txt")) if directorio.exists() else []
        for archivo in archivos:
            archivo.unlink()
        print("🗑 Historial eliminado correctamente." if archivos else "⚠ No hay historial para eliminar.")
