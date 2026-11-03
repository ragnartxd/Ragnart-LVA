import datetime, os, time

import pyautogui
import pytesseract
from PIL import Image
from backend.Gestor.GestorParametros import Gestor_Parametros

# 📌 Configurar la ruta de Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 📌 Función para tomar una captura de pantalla
def tomar_captura(**kwargs):
    """Toma una captura de pantalla y devuelve la ruta del archivo."""
    datos = Gestor_Parametros.procesar({"accion": "tomar_captura", "params": kwargs})

    carpeta = "Capturas"
    if not os.path.exists(carpeta):
        os.makedirs(carpeta)

    nombre_archivo = f"{carpeta}/captura_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png"
    screenshot = pyautogui.screenshot()
    screenshot.save(nombre_archivo)

    return nombre_archivo  # 🔹 Devuelve solo la ruta del archivo


def buscar_texto_en_pantalla(**kwargs):
    """Busca un texto en pantalla y devuelve sus coordenadas si se encuentra, usando OCR para obtener la posición."""
    datos = Gestor_Parametros.procesar({"accion": "buscar_texto_en_pantalla", "params": kwargs})
    texto_usuario = datos["params"]["texto"]

    # Tomamos la captura una sola vez
    ruta_captura = tomar_captura()
    
    # Abrimos la imagen
    imagen = Image.open(ruta_captura)
    
    # Extraemos los datos con OCR en formato de diccionario (TSV convertido)
    ocr_data = pytesseract.image_to_data(imagen, lang="eng+spa", config="--psm 6", output_type=pytesseract.Output.DICT)
    imagen.close()
    os.remove(ruta_captura)
    
    # Buscamos en los datos la palabra que contenga el texto_usuario
    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        palabra = ocr_data['text'][i]
        if palabra and texto_usuario.lower() in palabra.lower():
            left = ocr_data['left'][i]
            top = ocr_data['top'][i]
            width = ocr_data['width'][i]
            height = ocr_data['height'][i]
            # Calculamos el centro del cuadro
            x = left + width // 2
            y = top + height // 2
            return (x, y)
    return None


# 📌 Función para hacer clic en un texto en pantalla
def clic_texto(**kwargs):
    """Busca un texto en pantalla y hace clic en su ubicación si se encuentra."""
    datos = Gestor_Parametros.procesar({"accion": "clic_texto", "params": kwargs})
    texto_usuario = datos["params"]["texto"]

    coordenadas = buscar_texto_en_pantalla(texto=texto_usuario)

    if coordenadas:
        pyautogui.moveTo(coordenadas, duration=0.2)
        pyautogui.click(coordenadas)
        return f"🖱️ Clic en '{texto_usuario}' en {coordenadas}"
    
    return f"❌ No se encontró '{texto_usuario}' en la pantalla."


# 📌 Función para hacer doble clic en un texto en pantalla
def hacer_doble_clic_en_texto(**kwargs):
    """Busca un texto en pantalla y hace doble clic en su posición."""
    datos = Gestor_Parametros.procesar({"accion": "hacer_doble_clic_en_texto", "params": kwargs})
    texto = datos["params"]["texto"]

    coordenadas = buscar_texto_en_pantalla(texto=texto)
    if coordenadas:
        pyautogui.doubleClick(coordenadas)
        return f"👆👆 Doble clic en '{texto}' en {coordenadas}"
    
    return f"❌ No se encontró '{texto}' en la pantalla."


# 📌 Función para hacer scroll
def hacer_scroll(**kwargs):
    """Realiza un desplazamiento (scroll) hacia arriba o abajo."""
    datos = Gestor_Parametros.procesar({"accion": "hacer_scroll", "params": kwargs})

    direccion = datos["params"].get("texto", "abajo").lower()
    cantidad = datos["params"].get("cantidad", 1)  

    if "baja" in direccion or "abajo" in direccion:
        pyautogui.scroll(-cantidad * 100)
        return f"📜 Scroll hacia abajo ({cantidad} veces)"
    elif "sube" in direccion or "arriba" in direccion:
        pyautogui.scroll(cantidad * 100)
        return f"📜 Scroll hacia arriba ({cantidad} veces)"
    
    return "❌ Dirección no válida. Usa 'arriba' o 'abajo'."


# 📌 Función para arrastrar y soltar un texto
def arrastrar_y_soltar(**kwargs):
    """Busca dos textos en la pantalla y arrastra el primero hacia el segundo."""
    datos = Gestor_Parametros.procesar({"accion": "arrastrar_y_soltar", "params": kwargs})
    texto_origen = datos["params"]["texto_origen"]
    texto_destino = datos["params"]["texto_destino"]

    origen = buscar_texto_en_pantalla(texto=texto_origen)
    destino = buscar_texto_en_pantalla(texto=texto_destino)

    if origen and destino:
        pyautogui.moveTo(origen)
        pyautogui.mouseDown()
        time.sleep(0.2)  # Pequeña pausa para simular arrastre
        pyautogui.moveTo(destino)
        pyautogui.mouseUp()
        return f"🎯 Arrastrado '{texto_origen}' hacia '{texto_destino}'"
    
    return "❌ No se pudo encontrar ambos elementos en la pantalla."


# 📌 Función para leer el texto de una captura de pantalla
def leer_texto_captura():  
    """Captura la pantalla, extrae el texto con OCR (usando psm=6) y elimina la imagen."""
    ruta_captura = tomar_captura()
    imagen = Image.open(ruta_captura)
    
    # Se añade el parámetro config para usar psm=6
    texto_extraido = pytesseract.image_to_string(imagen, lang="eng+spa", config="--psm 6")
    imagen.close()

    if os.path.exists(ruta_captura):
        os.remove(ruta_captura)

    return f"📜 Texto detectado: {texto_extraido.strip()}" if texto_extraido.strip() else "❌ No se detectó texto en la pantalla."


if __name__ == "__main__":
    # Pruebas de las funciones
    print(leer_texto_captura())
    print(buscar_texto_en_pantalla(texto="comments"))
    print(clic_texto(texto="comments"))
    print(hacer_doble_clic_en_texto(texto="apps.json"))
    print(hacer_scroll(texto="abajo", cantidad=3))
    print(arrastrar_y_soltar(texto_origen="guardar.txt", texto_destino="importaciones"))
