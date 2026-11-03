"""
Integración de APIs externas para obtener información variada.
"""
import base64
import os
import tempfile
import time
import types
import requests

from youtubesearchpython import VideosSearch
import webbrowser
os.environ["PAFY_BACKEND"] = "internal"
from backend.configuracion_entorno import (
    PROJECT_ROOT,
    cargar_configuracion_api,
    guardar_configuracion_api,
    obtener_clave_api,
)


# Agrega la ruta donde se encuentra libvlc.dll a PATH para yutu pero esto debo cambiarlo
os.environ["PATH"] += os.pathsep + r"C:\Program Files\VideoLAN\VLC"
# Establece también la ruta de plugins, si es necesario
os.environ["VLC_PLUGIN_PATH"] = r"C:\Program Files\VideoLAN\VLC\plugins"

CONFIG_FILE = os.path.join(PROJECT_ROOT, "importaciones", "config_integracion.json")
SERVICIOS_BASE = ("Clima", "Noticias", "Imagen", "Gemini")

def cargar_configuracion():
    """Carga nombres de servicios y migra claves antiguas a .env."""
    return cargar_configuracion_api(CONFIG_FILE, SERVICIOS_BASE)

def guardar_configuracion(config):
    """Guarda las claves privadas en .env y solo los servicios en JSON."""
    guardar_configuracion_api(config, CONFIG_FILE)

def obtener_api_key(servicio):
    """Obtiene la clave API de un servicio específico."""
    return obtener_clave_api(servicio)

def modificar_api_key(servicio, nueva_clave):
    """
    Modifica la clave de una API. No permite eliminar APIs base.
    """
    if servicio in configuracion:
        configuracion[servicio] = nueva_clave
        guardar_configuracion(configuracion)
    else:
        raise ValueError(f"No existe una configuración para el servicio '{servicio}'.")

        
def obtener_clima(ciudad): #esta sirve bien
    """
    Obtiene el clima actual para una ciudad usando el endpoint gratuito de OpenWeatherMap.
    Parámetros:
      - ciudad: nombre de la ciudad (ej. "Madrid")
      - api_key: tu clave API asignada por OpenWeatherMap.
    Retorna:
      Un string con la temperatura y la descripción del clima.
    """
    api_key = obtener_api_key("Clima")
    if not api_key:
        return "⚠ No se ha configurado una clave API para Clima."
    
    url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={api_key}&units=metric&lang=es"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Lanza una excepción para códigos de error HTTP
        data = response.json()
        temperatura = data["main"]["temp"]
        descripcion = data["weather"][0]["description"]
        print(f"El clima en {ciudad} es de {temperatura}°C con {descripcion}.")
        return f"El clima en {ciudad} es de {temperatura}°C con {descripcion}."
    except requests.exceptions.HTTPError as http_err:
        return f"Error HTTP: {http_err}"
    except Exception as e:
        return f"Error al obtener el clima: {e}"

def obtener_noticias(): #esta no tiene para colombia
    """
    Obtiene titulares de noticias recientes usando NewsAPI.
    
    Parámetros:
      - api_key: Tu clave API de NewsAPI.
      - pais: Código del país (ejemplo: "us" para Estados Unidos, "es" para España).
      
    Retorna:
      Un string con los primeros 5 titulares o un mensaje de error.
    """

    api_key = obtener_api_key("Noticias")
    if not api_key:
        return "⚠ No se ha configurado una clave API para Noticias."
    
    url = f"https://newsapi.org/v2/top-headlines?country=co&apiKey={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Lanza un error para códigos de estado HTTP no exitosos
        data = response.json()
        articulos = data.get("articles", [])
        if not articulos:
            return "No se encontraron noticias para el país especificado."
        # Extraer los títulos de los primeros 5 artículos
        titulares = [articulo.get("title") for articulo in articulos if articulo.get("title")]
        return "Titulares: " + " | ".join(titulares[:5])
    except requests.exceptions.HTTPError as http_err:
        return f"Error HTTP: {http_err}"
    except Exception as e:
        return f"Error al obtener noticias: {e}"
    
def obtener_wikipedia(query): # Esta sirve bien
    """
    Obtiene un extracto del artículo de Wikipedia en español para la consulta dada.
    
    Parámetros:
      - query: El término de búsqueda (por ejemplo, "Ibague")
      
    Retorna:
      El extracto del artículo o un mensaje si no se encontró información.
    """
    base_url = "https://es.wikipedia.org/w/api.php"
    parametros = {
        "action": "query",
        "prop": "extracts",
        "exintro": True,          # Solo la introducción
        "explaintext": True,      # Texto sin formato HTML
        "format": "json",
        "titles": query,
        "redirects": 1,           # Para seguir redirecciones
        "formatversion": 2        # Para obtener un formato más limpio
    }
    
    try:
        respuesta = requests.get(base_url, params=parametros)
        respuesta.raise_for_status()  # Lanza excepción para códigos HTTP de error
        datos = respuesta.json()
        paginas = datos.get("query", {}).get("pages", [])
        if paginas and "extract" in paginas[0]:
            extracto = paginas[0]["extract"]
            return extracto if extracto.strip() else "No se encontró información relevante en Wikipedia."
        else:
            return "No se encontró información en Wikipedia para esa consulta."
    except Exception as e:
        return f"Error al consultar Wikipedia: {e}"
    
def obtener_token_spotify(CLIENT_ID, CLIENT_SECRET):
    """
    Obtiene un token de acceso de Spotify usando Client Credentials Flow.
    """
    token_url = "https://accounts.spotify.com/api/token"
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {b64_auth_str}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials"
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    response.raise_for_status()
    token_data = response.json()
    return token_data["access_token"]

def obtener_cancion(nombre_cancion, token):
    """
    Busca una canción en Spotify y devuelve información básica.
    
    Parámetros:
      - nombre_cancion: El nombre de la canción a buscar (ej. "Shape of You")
      - token: Token de acceso obtenido previamente.
    
    Retorna:
      El primer track encontrado o None si no hay resultados.
    """
    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "q": nombre_cancion,
        "type": "track",
        "limit": 1
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    tracks = data.get("tracks", {}).get("items", [])
    if tracks:
        return tracks[0]
    return None
    
def buscar_video(query):
    """
    Busca un video en YouTube y devuelve su ID.
    """
    videosSearch = VideosSearch(query, limit=1)
    result = videosSearch.result()
    if result.get("result") and len(result["result"]) > 0:
        video_id = result["result"][0]["id"]
        return video_id
    return None

def reproducir_video(video_id): #tiene un error / toca cambiarlo hay mejores formas
    """
    Reproduce un video de YouTube usando VLC y pafy.
    """
    import vlc
    import pafy
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        video = pafy.new(url)  # Ya no necesitas set_api_backend
        best = video.getbest()
        playurl = best.url

        # Crear instancia de VLC
        instance = vlc.Instance()
        player = instance.media_player_new()
        media = instance.media_new(playurl)
        player.set_media(media)
        player.play()

        return player  # Devuelve el reproductor por si quieres controlarlo después

    except Exception as e:
        print(f"⚠️ Error al reproducir el video: {str(e)}")
        return None
    
def capture_image_data():
    """
    Captura la pantalla, la redimensiona y la comprime,
    y retorna los datos binarios de la imagen (JPEG).
    """
    import pyautogui
    from io import BytesIO
    # Capturar pantalla completa
    screenshot = pyautogui.screenshot()
    # Redimensionar
    new_width = screenshot.width // 2
    new_height = screenshot.height // 2
    screenshot = screenshot.resize((new_width, new_height))
    
    # Guardar en buffer con compresión
    buffer = BytesIO()
    screenshot.save(buffer, format="JPEG", quality=80)
    return buffer.getvalue()

def search_anime_with_file():
    """
    Envía la imagen capturada a trace.moe usando una petición POST
    con multipart/form-data, lo que suele funcionar mejor que enviar
    una cadena base64 en el cuerpo.
    """
    url = "https://api.trace.moe/search"
    image_data = capture_image_data()
    files = {
        "image": ("screenshot.jpg", image_data, "image/jpeg")
    }
    data = {"anilistInfo": "true"}
    response = requests.post(url, files=files, data=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error en la API: {response.status_code} - {response.text}")
    
def convertir_doc_a_pdf(doc_path, output_name="output.pdf", landscape=False):
    """
    Convierte un archivo DOC, DOCX u ODF a PDF usando la API de ApyHub.
    
    Parámetros:
      - doc_path: Ruta del archivo de Word.
      - output_name: Nombre del archivo PDF resultante (opcional).
      - landscape: Si es True, genera el PDF en modo horizontal.
    
    Retorna:
      - El contenido del PDF si la conversión es exitosa.
      - Mensaje de error en caso de fallo.
    """
    url = f"https://api.apyhub.com/convert/word-file/pdf-file?output={output_name}&landscape={str(landscape).lower()}"
    from backend.configuracion_entorno import obtener_variable_entorno

    api_token = obtener_variable_entorno("APYHUB_API_TOKEN")
    if not api_token:
        raise ValueError("Define APYHUB_API_TOKEN en .env para usar ApyHub.")
    headers = {"apy-token": api_token}

    with open(doc_path, "rb") as file:
        files = {"file": (doc_path, file, "application/msword")}
        response = requests.post(url, headers=headers, files=files)
    
    if response.status_code == 200:
        # Guardar el PDF convertido
        with open(output_name, "wb") as pdf_file:
            pdf_file.write(response.content)
        return f"Conversión exitosa. Archivo guardado como {output_name}"
    else:
        return f"Error en la conversión: {response.text}"
    

def generar_imagen_funcion(prompt):
    """
    Genera una imagen a partir de un prompt utilizando la API de generación de imágenes.
    """
    from openai import OpenAI
    api_key = obtener_api_key("Imagen")
    if not api_key:
        return "⚠ No se ha configurado una clave API para generacion de imagenes."
    
    client = OpenAI(
        base_url="https://api.electronhub.top/v1/",
        api_key= api_key
    )

    try:
        response = client.images.generate(
            model="flux-schnell",  
            prompt=prompt,
            n=1  
        )

        #print("Respuesta de la API:", response)

        if response.data and len(response.data) > 0 and response.data[0].url:
            url_imagen = response.data[0].url
            #print("Imagen generada:", url_imagen)

            webbrowser.open(url_imagen)
            return url_imagen
        else:
            return "No se pudo generar la imagen. Respuesta de la API incorrecta."

    except Exception as e:
        return f"Error: {str(e)}"
    

def analizar_imagen_gemini_flash(imagen_binaria, prompt):
    """
    Envía una imagen (como bytes) al modelo Gemini y retorna la respuesta.

    Args:
        imagen_binaria (bytes): Imagen capturada o cargada.
        texto_opcional (str): Prompt opcional que acompaña a la imagen.

    Returns:
        str: Respuesta del modelo Gemini.
    """
    from google import genai
    api_key = obtener_api_key("Gemini")
    if not api_key:
        return "No se ha configurado una clave API para Gemini."

    client = genai.Client(api_key=api_key)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(imagen_binaria)
        tmp_path = tmp.name

    uploaded = client.files.upload(file=tmp_path)  # devuelve un objeto FileRef

    response = client.models.generate_content(
        model="gemini-2.0-flash",       # el identificador correcto
        contents=[uploaded, prompt]
    )

    return response.text
    
def analizar_video_gemini_flash(video_binario: bytes, prompt: str) -> str:
    """
    Envía un vídeo al modelo Gemini 2.0 Flash, esperando a que el upload
    termine de procesarse (estado ACTIVE), y retorna la respuesta.
    """
    from google import genai
    api_key = obtener_api_key("Gemini")
    if not api_key:
        return "No se ha configurado la clave API para Gemini."
    client = genai.Client(api_key=api_key)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_binario)
        tmp_path = tmp.name

    uploaded = client.files.upload(file=tmp_path)
    file_name = uploaded.name  # Resource name, p.ej: "projects/.../files/709uaqgnzy"

    timeout = 900    # segundos max
    interval = 30    # segundos entre checks
    waited = 0
    while waited < timeout:
        info = client.files.get(name=file_name)
        if info.state == "ACTIVE":
            break
        time.sleep(interval)
        waited += interval
    else:
        return "Timeout: el vídeo no se procesó a ACTIVE en el tiempo permitido."

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[uploaded, prompt]
    )

    return response.text

def analizar_pdf_gemini_flash(pdf_binario: bytes, prompt: str) -> str:
    """
    Envía un PDF como bytes directamente al modelo Gemini 2.0 Flash y retorna la respuesta.
    """
    from google import genai
    api_key = obtener_api_key("Gemini")
    if not api_key:
        return "No se ha configurado la clave API para Gemini."
    client = genai.Client(api_key=api_key)

    part = types.Part.from_bytes(data=pdf_binario, mime_type="application/pdf")
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[part, prompt]
    )

    return response.text

# Cargar configuración inicial
configuracion = cargar_configuracion()

