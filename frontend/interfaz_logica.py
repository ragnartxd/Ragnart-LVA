import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from frontend.config import Ui_MainWindow
from frontend.respuestasconfig import RespuestasConfig
from frontend.integracionconfig import IntegracionConfig
from frontend.generalconfig import GeneralConfig  # Importa la interfaz convertida
from frontend.personalizacionconfig import PersonalizacionConfig  # Importa la interfaz convertida

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # Carga la interfaz
        self.general_config = GeneralConfig(self)
        self.integracion_config = IntegracionConfig(self)
        self.respuestas_config = RespuestasConfig(self)
        self.personalizacion_config = PersonalizacionConfig(self)
        

# Aquí cargas tu interfaz
if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyle("Fusion")  # Establece el estilo Fusion

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
