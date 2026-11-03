import os
import re
import json
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtGui import QRegularExpressionValidator
from PyQt5.QtCore import QRegularExpression
from backend.contactos import CONTACTOS_FILE, cargar_contactos_guardados, guardar_contactos_guardados
from backend.configuracion_usuario import (
    PERSONALIZACION_FILE,
    cargar_configuracion_personalizacion,
    guardar_configuracion_personalizacion,
)

class PersonalizacionConfig:
    def __init__(self, main_window):
        self.main_window = main_window
        self.dir_arc = os.path.join(os.path.dirname(__file__), '../importaciones/arc_personalizacion')
        os.makedirs(self.dir_arc, exist_ok=True)
        self.config_path = PERSONALIZACION_FILE
        self.contactos_path = CONTACTOS_FILE
        self.config = self.cargar_configuracion()
        self.contactos = self.cargar_contactos()
        self.cambios_pendientes = False
        for slider in (
            main_window.horizontalSliderAudio,
            main_window.horizontalSliderAnimacion,
            main_window.horizontalSliderVoz,
        ):
            slider.setRange(0, 100)
        main_window.sliderCPU.setRange(1, os.cpu_count() or 1)
        self._conectar_eventos()
        self._cargar_a_interfaz()

    def _conectar_eventos(self):
        """Conecta los eventos de la interfaz, sin auto-guardado excepto para contactos"""
        ui = self.main_window
        
        # Eventos que solo marcan cambios pendientes (no guardan automáticamente)
        ui.checkBoxAnimaciones.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.lineEditFilePersonaje.editingFinished.connect(self._marcar_cambios_pendientes)
        ui.lineEditFileVozIA.editingFinished.connect(self._marcar_cambios_pendientes)
        ui.lineEditPersonalidad.editingFinished.connect(self._marcar_cambios_pendientes)
        ui.horizontalSliderAudio.valueChanged.connect(self._marcar_cambios_pendientes)
        ui.horizontalSliderAudio.valueChanged.connect(self._actualizar_etiquetas_sliders)
        ui.horizontalSliderAnimacion.valueChanged.connect(self._marcar_cambios_pendientes)
        ui.horizontalSliderAnimacion.valueChanged.connect(self._actualizar_etiquetas_sliders)
        ui.horizontalSliderVoz.valueChanged.connect(self._marcar_cambios_pendientes)
        ui.horizontalSliderVoz.valueChanged.connect(self._actualizar_etiquetas_sliders)
        ui.checkBoxAnimacionesSiempreActivo.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.checkBoxAnimacionesAprendizaje.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.checkBoxAnimacionesTareasUrgentes.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.checkBoxAnimacionesInicaralejecutar.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.lineEditSaveFile.editingFinished.connect(self._marcar_cambios_pendientes)
        ui.sliderCPU.valueChanged.connect(self._marcar_cambios_pendientes)
        ui.checkBoxAnimacionesSiempreActivo.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.checkBoxAnimacionesAprendizaje.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.checkBoxAnimacionesTareasUrgentes.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.checkBoxAnimacionesInicaralejecutar.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.lineEditSaveFile.editingFinished.connect(self._marcar_cambios_pendientes)
        ui.sliderCPU.valueChanged.connect(self._marcar_cambios_pendientes)
        
        # Eventos que requieren acción inmediata
        ui.pushButton.clicked.connect(self.agregar_contacto)
        ui.comboBox.currentIndexChanged.connect(self._actualizar_vista_contactos)
        ui.btnBuscarModelo.clicked.connect(self.seleccionar_modelo_personaje)
        ui.btnBuscarVoz.clicked.connect(self.seleccionar_voz)
        ui.btnBuscarPersonalidad.clicked.connect(self.seleccionar_personalidad)
        self._actualizar_vista_contactos()
        ui.btnGuardar.clicked.connect(self.guardar_configuracion)
        ui.btnRestablecer.clicked.connect(self.restablecer_configuracion)
        ui.checkBoxAnimaciones.setToolTip(
            "Activa la animación de boca durante la voz y los movimientos del modelo."
        )
        ui.lineEditFilePersonaje.setToolTip(
            "Selecciona el archivo .model3.json del modelo Live2D; el modelo incluye sus movimientos."
        )
        ui.lineEditFileVozIA.setToolTip(
            "Usa un nombre de voz Kokoro o selecciona un archivo local .pt."
        )
        ui.lineEditPersonalidad.setToolTip(
            "Escribe instrucciones o selecciona un archivo de texto con la personalidad."
        )
        ui.horizontalSliderAudio.setToolTip(
            "Volumen de reproducción del asistente; se aplica al siguiente audio."
        )
        self._actualizar_etiquetas_sliders()

    def _marcar_cambios_pendientes(self):
        """Marca que hay cambios pendientes de guardar"""
        self.cambios_pendientes = True

    def _cargar_a_interfaz(self):
        """Carga la configuración desde el archivo a la interfaz"""
        ui = self.main_window
        c = self.config
        
        # Temporalmente desconectar señales para evitar marcar cambios durante la carga
        self._desconectar_señales_temporalmente()
        
        try:
            ui.checkBoxAnimaciones.setChecked(c.get('habilitar_animaciones', False))
            ui.lineEditFilePersonaje.setText(c.get('modelo_personaje', ''))
            ui.lineEditFileVozIA.setText(c.get('voz_ia', ''))
            ui.lineEditPersonalidad.setText(c.get('personalidad', ''))
            ui.horizontalSliderAudio.setValue(c.get('nivel_audio', 50))
            ui.horizontalSliderAnimacion.setValue(c.get('nivel_animacion', 50))
            ui.horizontalSliderVoz.setValue(c.get('velocidad_voz', 50))
            ui.sliderCPU.setValue(c.get('limite_cpu', min(4, os.cpu_count() or 1)))
            ui.checkBoxAnimacionesSiempreActivo.setChecked(c.get('siempre_activo', False))
            ui.checkBoxAnimacionesAprendizaje.setChecked(c.get('habilitar_aprendizaje', False))
            ui.checkBoxAnimacionesTareasUrgentes.setChecked(c.get('priorizar_urgentes', False))
            ui.checkBoxAnimacionesInicaralejecutar.setChecked(c.get('iniciar_al_ejecutar', False))
            ui.lineEditSaveFile.setText(c.get('ruta_guardado', ''))
            
            # Mostrar contactos en el campo (solo como texto de lectura)
            self._actualizar_vista_contactos()
            
            # Limpiar campo de entrada de contactos
            ui.lineEditSaveFile_3.setText("")  # Asignar un valor por defecto para el campo de teléfono
            self._actualizar_etiquetas_sliders()
            
        finally:
            # Reconectar señales
            self._conectar_señales_temporalmente()
            # Resetear cambios pendientes ya que acabamos de cargar
            self.cambios_pendientes = False

    def _desconectar_señales_temporalmente(self):
        """Desconecta temporalmente las señales para evitar cambios durante la carga"""
        ui = self.main_window
        ui.checkBoxAnimaciones.stateChanged.disconnect()
        ui.lineEditFilePersonaje.editingFinished.disconnect()
        ui.lineEditFileVozIA.editingFinished.disconnect()
        ui.lineEditPersonalidad.editingFinished.disconnect()
        ui.horizontalSliderAudio.valueChanged.disconnect()
        ui.horizontalSliderAnimacion.valueChanged.disconnect()
        ui.horizontalSliderVoz.valueChanged.disconnect()
        ui.checkBoxAnimacionesSiempreActivo.stateChanged.disconnect()
        ui.checkBoxAnimacionesAprendizaje.stateChanged.disconnect()
        ui.checkBoxAnimacionesTareasUrgentes.stateChanged.disconnect()
        ui.checkBoxAnimacionesInicaralejecutar.stateChanged.disconnect()
        ui.lineEditSaveFile.editingFinished.disconnect()
        ui.sliderCPU.valueChanged.disconnect()

    def _conectar_señales_temporalmente(self):
        """Reconecta las señales después de la carga"""
        ui = self.main_window
        ui.checkBoxAnimaciones.stateChanged.connect(self._marcar_cambios_pendientes)
        ui.lineEditFilePersonaje.editingFinished.connect(self._marcar_cambios_pendientes)
        ui.lineEditFileVozIA.editingFinished.connect(self._marcar_cambios_pendientes)
        ui.lineEditPersonalidad.editingFinished.connect(self._marcar_cambios_pendientes)
        ui.horizontalSliderAudio.valueChanged.connect(self._marcar_cambios_pendientes)
        ui.horizontalSliderAudio.valueChanged.connect(self._actualizar_etiquetas_sliders)
        ui.horizontalSliderAnimacion.valueChanged.connect(self._marcar_cambios_pendientes)
        ui.horizontalSliderAnimacion.valueChanged.connect(self._actualizar_etiquetas_sliders)
        ui.horizontalSliderVoz.valueChanged.connect(self._marcar_cambios_pendientes)
        ui.horizontalSliderVoz.valueChanged.connect(self._actualizar_etiquetas_sliders)

    def _actualizar_etiquetas_sliders(self):
        ui = self.main_window
        ui.labelValorAudio.setText(f"{ui.horizontalSliderAudio.value()}%")
        ui.labelValorAnimacion.setText(f"{ui.horizontalSliderAnimacion.value()}%")
        ui.labelValorVoz.setText(f"{ui.horizontalSliderVoz.value()}%")

    def _ruta_inicial_selector(self, campo):
        ruta = campo.text().strip()
        if ruta and os.path.exists(ruta):
            return ruta if os.path.isdir(ruta) else os.path.dirname(ruta)
        return str(PERSONALIZACION_FILE.parent)

    def seleccionar_modelo_personaje(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Seleccionar modelo Live2D",
            self._ruta_inicial_selector(self.main_window.lineEditFilePersonaje),
            "Modelos Live2D (*.model3.json);;Archivos JSON (*.json)",
        )
        if ruta:
            self.main_window.lineEditFilePersonaje.setText(ruta)
            self._marcar_cambios_pendientes()

    def seleccionar_voz(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Seleccionar voz Kokoro",
            self._ruta_inicial_selector(self.main_window.lineEditFileVozIA),
            "Voces Kokoro (*.pt);;Todos los archivos (*)",
        )
        if ruta:
            self.main_window.lineEditFileVozIA.setText(ruta)
            self._marcar_cambios_pendientes()

    def seleccionar_personalidad(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Seleccionar archivo de personalidad",
            self._ruta_inicial_selector(self.main_window.lineEditPersonalidad),
            "Archivos de texto (*.txt *.md);;Todos los archivos (*)",
        )
        if ruta:
            self.main_window.lineEditPersonalidad.setText(ruta)
            self._marcar_cambios_pendientes()

    def _actualizar_vista_contactos(self):
        """Actualiza el formato esperado sin borrar lo escrito por el usuario."""
        ui = self.main_window
        tipo = ui.comboBox.currentText()
        if tipo == "Telefono":
            ui.lineEditSaveFile_2.setPlaceholderText("Ej.: +573001234567")
            ui.lineEditSaveFile_2.setValidator(
                QRegularExpressionValidator(
                    QRegularExpression(r"\+?[0-9\s().-]*"),
                    ui.lineEditSaveFile_2,
                )
            )
        elif tipo == "Gmail":
            ui.lineEditSaveFile_2.setPlaceholderText("Ej.: nombre@gmail.com")
            ui.lineEditSaveFile_2.setValidator(
                QRegularExpressionValidator(
                    QRegularExpression(r"[A-Za-z0-9._%+-]*(@gmail\.com)?"),
                    ui.lineEditSaveFile_2,
                )
            )
        else:
            ui.lineEditSaveFile_2.setPlaceholderText("")
            ui.lineEditSaveFile_2.setValidator(None)

    def cargar_configuracion(self):
        """Carga la configuración desde el archivo JSON"""
        try:
            return cargar_configuracion_personalizacion(self.config_path)
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.warning(None, 'Error', f'Error al cargar la configuración: {str(e)}')
        return {}

    def guardar_configuracion(self):
        """Guarda la configuración actual en el archivo JSON"""
        try:
            ui = self.main_window
            self.config = {
                'habilitar_animaciones': ui.checkBoxAnimaciones.isChecked(),
                'modelo_personaje': ui.lineEditFilePersonaje.text().strip(),
                'voz_ia': ui.lineEditFileVozIA.text().strip(),
                'personalidad': ui.lineEditPersonalidad.text().strip(),
                'nivel_audio': ui.horizontalSliderAudio.value(),
                'nivel_animacion': ui.horizontalSliderAnimacion.value(),
                'velocidad_voz': ui.horizontalSliderVoz.value(),
                'siempre_activo': ui.checkBoxAnimacionesSiempreActivo.isChecked(),
                'habilitar_aprendizaje': ui.checkBoxAnimacionesAprendizaje.isChecked(),
                'priorizar_urgentes': ui.checkBoxAnimacionesTareasUrgentes.isChecked(),
                'iniciar_al_ejecutar': ui.checkBoxAnimacionesInicaralejecutar.isChecked(),
                'ruta_guardado': ui.lineEditSaveFile.text().strip(),
                'limite_cpu': ui.sliderCPU.value(),
            }
            
            guardar_configuracion_personalizacion(self.config, self.config_path)
            
            self.cambios_pendientes = False
            QMessageBox.information(self.main_window, 'Guardado', 'Configuración guardada correctamente.')
            
        except IOError as e:
            QMessageBox.critical(self.main_window, 'Error', f'Error al guardar la configuración: {str(e)}')

    def restablecer_configuracion(self):
        """Restablece la configuración a los valores por defecto"""
        reply = QMessageBox.question(
            self.main_window, 
            'Confirmar restablecimiento', 
            '¿Está seguro de que desea restablecer toda la configuración? Esta acción no se puede deshacer.',
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Eliminar archivos de configuración
                if os.path.exists(self.config_path):
                    os.remove(self.config_path)
                if os.path.exists(self.contactos_path):
                    os.remove(self.contactos_path)
                
                # Resetear variables
                self.config = {}
                self.contactos = {}
                self.cambios_pendientes = False
                
                # Recargar interfaz
                self._cargar_a_interfaz()
                QMessageBox.information(self.main_window, 'Restablecido', 'Configuración restablecida correctamente.')
                
            except IOError as e:
                QMessageBox.critical(self.main_window, 'Error', f'Error al restablecer la configuración: {str(e)}')

    def agregar_contacto(self):
        """Agrega un nuevo contacto a la lista"""
        ui = self.main_window
        nombre = ui.lineEditSaveFile_3.text().strip()
        contacto = ui.lineEditSaveFile_2.text().strip()
        tipo = ui.comboBox.currentText()
        
        
        # Validaciones
        if not nombre:
            QMessageBox.warning(self.main_window, 'Contacto', 'Debes ingresar un nombre para el contacto.')
            return
            
        if not contacto:
            QMessageBox.warning(self.main_window, 'Contacto', 'Debes ingresar la información del contacto.')
            return
            
        if nombre in self.contactos:
            reply = QMessageBox.question(
                self.main_window, 
                'Contacto existente', 
                f'El contacto "{nombre}" ya existe. ¿Desea reemplazarlo?',
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Validaciones específicas por tipo
        if tipo == "Telefono":
            contacto_limpio = re.sub(r"[\s().-]", "", contacto)
            digitos = contacto_limpio.removeprefix("+")
            if not digitos.isdigit():
                QMessageBox.warning(self.main_window, 'Contacto', 'El teléfono debe contener solo números y un + inicial opcional.')
                return
            if len(digitos) < 7:
                QMessageBox.warning(self.main_window, 'Contacto', 'El teléfono debe tener al menos 7 dígitos.')
                return
            contacto = contacto_limpio
        elif tipo == "Gmail":
            contacto = contacto.strip().lower()
            if not re.fullmatch(r"[A-Za-z0-9._%+-]+@gmail\.com", contacto):
                QMessageBox.warning(self.main_window, 'Contacto', 'El correo debe ser un Gmail válido (@gmail.com).')
                return
        
        try:
            # Guardar el contacto
            self.contactos[nombre] = contacto
            self.guardar_contactos()
            
            # Actualizar interfaz
            self._actualizar_vista_contactos()
            ui.lineEditSaveFile_3.setText("")  # Limpiar campo de nombre
            
            QMessageBox.information(self.main_window, 'Contacto', f'Contacto "{nombre}" agregado correctamente.')
            
        except Exception as e:
            QMessageBox.critical(self.main_window, 'Error', f'Error al agregar el contacto: {str(e)}')

    def cargar_contactos(self):
        """Carga los contactos desde el archivo JSON"""
        try:
            return cargar_contactos_guardados(self.contactos_path)
        except (json.JSONDecodeError, IOError) as e:
            QMessageBox.warning(None, 'Error', f'Error al cargar los contactos: {str(e)}')
        return {}

    def guardar_contactos(self):
        """Guarda los contactos en el archivo JSON"""
        try:
            guardar_contactos_guardados(self.contactos, self.contactos_path)
        except IOError as e:
            QMessageBox.critical(self.main_window, 'Error', f'Error al guardar los contactos: {str(e)}')

    def seleccionar_ruta_guardado(self):
        """Abre un diálogo para seleccionar la ruta de guardado"""
        ui = self.main_window
        ruta = QFileDialog.getExistingDirectory(ui, 'Seleccionar carpeta para guardar datos')
        if ruta:
            ui.lineEditSaveFile.setText(ruta)
            self._marcar_cambios_pendientes()

    def tiene_cambios_pendientes(self):
        """Retorna True si hay cambios pendientes de guardar"""
        return self.cambios_pendientes

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication, QMainWindow
    import sys

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    main_window = QMainWindow()
    ui = PersonalizacionConfig(main_window)
    main_window.show()
    sys.exit(app.exec_())
    