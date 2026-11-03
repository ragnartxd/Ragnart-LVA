
from PyQt5 import QtWidgets, QtCore, QtGui

class DropWindow(QtWidgets.QWidget):
    """
    Ventana fullscreen transparente que acepta un único drag‑and‑drop.
    """
    
    def __init__(self):
        super().__init__()
        # Sin bordes, siempre encima, fondo transparente
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)

        # Texto central, opacidad baja
        label = QtWidgets.QLabel("Arrastra archivo", self)
        label.setAlignment(QtCore.Qt.AlignCenter)
        font = QtGui.QFont("Sans", 32)
        label.setFont(font)
        label.setStyleSheet("color: rgba(255,255,255,0.2);")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(label)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        # Tomamos la primera URL y cerramos la app Qt
        self.file_path = event.mimeData().urls()[0].toLocalFile()
        QtWidgets.QApplication.quit()

def seleccionar_archivo_con_arrastre():
    """
    Lanza la GUI de arrastre. Devuelve la ruta del archivo.
    """
    app = QtWidgets.QApplication([])
    win = DropWindow()
    win.showFullScreen()
    app.exec_()
    return getattr(win, 'file_path', None)

def obtener_imagen_por_voz_o_arrastre():
    """
    Flujo completo:
      1. Por voz decide “pantallazo” o “archivo”.
      2. Si pantallazo, usa pyautogui para screenshot.
      3. Si archivo, abre DropWindow y lee bytes+MIME.
    """
    import imghdr
    from io import BytesIO
    import pyautogui
    from pathlib import Path
    
    opcion = escuchar_opcion_imagen()
    if opcion == "pantallazo":
        # Captura la pantalla como JPEG
        img = pyautogui.screenshot()
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue(), "image/jpeg"
    
    # Si llegamos aquí, la opción es 'archivo'
    elif opcion == "archivo" or opcion == "archivos":
        # Usamos drag & drop (o input de ruta) tal como ya tenías:
        path = seleccionar_archivo_con_arrastre()  # tu ventana transparente
        if not path:
            raise FileNotFoundError("No se recibió ningún archivo.")

        # Leemos los bytes
        datos = Path(path).read_bytes()

        # Detectamos tipo por extensión primero
        ext = Path(path).suffix.lower()
        if ext in {".mp4", ".mov", ".mkv", ".avi"}:
            mime = f"video/{ext[1:]}"   # ext=".mp4" -> "video/mp4"
            return datos, mime
        
        elif ext == "pdf":
            mime = "application/pdf"
            return datos, mime
        else:
            # Si no es vídeo, detectamos imagen
            img_type = imghdr.what(None, h=datos) or "jpeg"
            mime = f"image/{img_type}"
            return datos, mime


    raise ValueError("Opción no reconocida. Di ‘pantallazo’ o ‘archivo’.")


def escuchar_opcion_imagen():
    """
    Escucha por micrófono y devuelve el texto reconocido en minúsculas.
    """
    from backend.utils.utils_instruccion_adicional import decir_y_escuchar
    return decir_y_escuchar("¿Quieres hacer un pantallazo o arrastrar un archivo? Di ‘pantallazo’ o ‘archivo’.")