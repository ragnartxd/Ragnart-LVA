"""
funciones para interactuar con APIs y servicios web
"""
import subprocess, time, requests

from backend.Generacion.from_TTS import hablar
from backend.Funciones.funcionesSistema import decir_y_escuchar
from backend.contactos import cargar_contactos_guardados
from backend.configuracion_entorno import obtener_variable_entorno

def consultar_clima(**kwargs): #toca probarlo nose si funcione
    """
    Handler para la intención 'consultar_clima'. Espera el parámetro 'ciudad'.
    """
    from backend.Funciones.apiIntegracion import obtener_clima
    ciudad = kwargs.get("ciudad", "").strip()
    if not ciudad:
        return "No se especificó una ciudad para consultar el clima."
    
    return obtener_clima(ciudad)

def consultar_noticias():
    """
    Handler para la intención 'consultar_noticias'. No espera parámetros.
    """
    from backend.Funciones.apiIntegracion import obtener_noticias
    return obtener_noticias()

def consultar_wikipedia(**kwargs):
    """
    Handler para la intención 'consultar_wikipedia'. Espera el parámetro 'query' (o 'tema').
    """
    from backend.Funciones.apiIntegracion import obtener_wikipedia
    query = kwargs.get("query", "").strip()
    if not query:
        return "No se especificó un tema para consultar en Wikipedia."
    return obtener_wikipedia(query)

def buscar_cancion(**kwargs):
    """
    Handler para la intención 'reproducir_cancion'. Espera el parámetro 'cancion'.
    Utiliza Spotipy y el Authorization Code Flow para buscar y reproducir una canción
    en el dispositivo activo del usuario.
    """
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    cancion = kwargs.get("cancion", "").strip()
    if not cancion:
        return "No se especificó la canción a reproducir."

    # Define los scopes necesarios para controlar la reproducción
    scope = "user-modify-playback-state,user-read-playback-state"
    

    
    client_id = obtener_variable_entorno("SPOTIFY_CLIENT_ID")
    client_secret = obtener_variable_entorno("SPOTIFY_CLIENT_SECRET")
    redirect_uri = obtener_variable_entorno("SPOTIFY_REDIRECT_URI")
    if not client_id or not client_secret or not redirect_uri:
        return "Spotify no está configurado. Completa sus credenciales y URI en .env."

    try:
        # Inicializa el cliente de Spotify con OAuth
        sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope
        ))
        
        # Realiza la búsqueda de la canción
        results = sp.search(q=cancion, type="track", limit=1)
        tracks = results.get("tracks", {}).get("items", [])
        
        if not tracks:
            return "No se encontró la canción."
        
        track = tracks[0]
        track_uri = track["uri"]
        nombre = track.get("name")
        artistas = ", ".join([artist["name"] for artist in track.get("artists", [])])
        
        # Inicia la reproducción en el dispositivo activo del usuario
        sp.start_playback(uris=[track_uri])
        return f"Reproduciendo: {nombre} de {artistas}."
    
    except Exception as e:
        return f"Error al reproducir la canción: {e}"

def verificar_servidor():
    """
    Verifica si el servidor de WhatsApp está activo.
    """
    try:
        response = requests.get("http://localhost:3001/status", timeout=2)
        if response.status_code == 200:
            return True
    except requests.exceptions.RequestException:
        return False
    
def esperar_cliente_listo(timeout=120):
    """Espera hasta que el cliente de WhatsApp esté listo o agota el tiempo."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            response = requests.get("http://localhost:3001/status", timeout=2)
            if response.status_code == 200 and response.json().get("whatsappReady"):
                #print("Cliente de WhatsApp listo para enviar mensajes.")
                return True
            else:
                print("Esperando autenticación de WhatsApp (escanea el QR)...")
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    print("Tiempo de espera agotado para autenticación de WhatsApp.")
    return False

def iniciar_servidor():
    """Inicia el servidor de WhatsApp si no está activo."""
    if not verificar_servidor():
        print("Iniciando el servidor de WhatsApp...")
        subprocess.Popen(["node", ".\\importaciones\\whatsappBot.js"])
        # Espera unos segundos para que el servidor se inicie correctamente.
        time.sleep(30)
    else:
        print("El servidor de WhatsApp ya está activo.")

def enviar_whatsapp(**kwargs):
    """
    Envía un mensaje de WhatsApp a un número específico usando el servidor del bot de WhatsApp.
    
    Parámetros:
      - usuario: Nombre del contacto (clave en la agenda) o número en formato internacional (+57...).
      - mensaje: Texto del mensaje a enviar.
    """
    datos = {"accion": "enviar_whatsapp", "params": kwargs}
    usuario = datos["params"].get("usuario")
    mensaje = datos["params"].get("mensaje")

    if not usuario:
        usuario = decir_y_escuchar("¿A quién quieres enviar el mensaje? ")
        datos["params"]["usuario"] = usuario

    # Convertir el nombre a número si existe en la agenda
    # 1. Cargar contactos guardados
    contactos_guardados = cargar_contactos_guardados()
    # 2. Buscar primero en los contactos guardados, luego en CONTACTOS_WHATSAPP, luego usar el valor directo
    numero = contactos_guardados.get(usuario) or usuario

    if not mensaje:
        mensaje = decir_y_escuchar("¿Qué mensaje quieres enviar? ")
        datos["params"]["mensaje"] = mensaje

    if not numero or not mensaje:
        return "No se especificó un número de contacto o mensaje."

    # Verificar e iniciar el servidor automáticamente si es necesario
    iniciar_servidor()
    
    if not esperar_cliente_listo():
        return "No se pudo autenticar el cliente de WhatsApp. Por favor, escanea el QR en el navegador."

    url = "http://localhost:3001/send"
    data = {"number": numero, "message": mensaje}

    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            return response.json().get("status", "Mensaje enviado.")
        else:
            if "serialize" in response.text:
                # Si el error es de serialización, pero el mensaje se envió se notifica
                return "Mensaje enviado, pero no te puedo confirmar el estado"
            else:
                return f"Error al enviar mensaje: {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error de conexión con el servidor: {e}"
    
def fetch_anilist_info(anilist_id):
    """
    Consulta la API de Anilist usando GraphQL para obtener información del anime.
    
    Parámetros:
      - anilist_id: ID del anime (entero)
    
    Retorna:
      El título en romaji si está disponible, o "Desconocido" en caso contrario.
    """
    query = '''
    query ($id: Int) {
      Media(id: $id, type: ANIME) {
        title {
          romaji
          english
          native
        }
      }
    }
    '''
    variables = {"id": anilist_id}
    url = "https://graphql.anilist.co"
    response = requests.post(url, json={"query": query, "variables": variables}, headers={"Content-Type": "application/json"})
    if response.status_code == 200:
        data = response.json()
        media = data.get("data", {}).get("Media")
        if media:
            # elegir entre "romaji", "english" o "native"
            return media.get("title", {}).get("romaji", "Desconocido")
    return "Desconocido"

def identificar_anime():
    try:
        from backend.Funciones.apiIntegracion import search_anime_with_file
        # Obtener la imagen (o video) del usuario
        resultado = search_anime_with_file()
        if resultado and "result" in resultado and len(resultado["result"]) > 0:
            info = resultado["result"][0]  # Tomamos el primer resultado, el de mayor coincidencia

            # Obtener el título correctamente:
            anilist_value = info.get("anilist")
            if isinstance(anilist_value, dict):
                titulo = anilist_value.get("title", {}).get("romaji", "Desconocido")
            elif isinstance(anilist_value, int):
                titulo = fetch_anilist_info(anilist_value)
            else:
                titulo = "Desconocido"

            episodio = info.get("episode", "No especificado")
            similarity = info.get("similarity", 0)

            # Extraer tiempos (en segundos) y formatearlos a minutos:segundos
            timestamp_from = info.get("from", 0)
            timestamp_to = info.get("to", 0)
            def format_time(seconds):
                minutes = int(seconds // 60)
                secs = int(seconds % 60)
                return f"{minutes}:{secs:02d}"
            tiempo_inicial = format_time(timestamp_from)
            tiempo_final = format_time(timestamp_to)

            # extraer URLs del video e imagen
            video_url = info.get("video", "No disponible")
            image_url = info.get("image", "No disponible")

            return (f"Se detectó: {titulo}, episodio {episodio}.\n"
                    f"Escena aproximada entre {tiempo_inicial} y {tiempo_final}.\n"
                    f"Similaridad: {similarity:.2f}\n"
                    f"Video: {video_url}\n"
                    f"Imagen: {image_url}")
        else:
            return "No se pudo identificar el anime en la imagen."
    except Exception as e:
        return f"Error al identificar anime: {e}"


def generar_imagen(texto, timeout=60):
    from backend.Funciones.apiIntegracion import generar_imagen_funcion
    """Genera una imagen con Stable Horde y la abre en el navegador si está lista."""
    job_id = generar_imagen_funcion(texto)
    if not job_id:
        return "No se pudo generar el trabajo."
    
    print(f"Job ID: {job_id}")

    return "Tiempo de espera excedido."

def flujo_analizar_archivo(texto):
    """
    Orquesta la selección de imagen o captura de pantalla
    y luego llama a Gemini Flash, retornando el texto de la respuesta.
    """
    try:
        from backend.Funciones.funcionesSistema import obtener_imagen_por_voz_o_arrastre
        from backend.Funciones.apiIntegracion import analizar_video_gemini_flash
        from backend.Generacion.AIGeneration import generator_gemma3
        datos, mime = obtener_imagen_por_voz_o_arrastre()
    except Exception as e:
        return f"{e}"

    # Capturamos lo que retorna la llamada a la API
    # Si es un vídeo (p.ej. video/mp4) lo envía a la función de vídeo
    if mime.startswith("video/"):
        texto_default = "Resume este video y genera un quiz con claves de respuesta."
        resultado = analizar_video_gemini_flash(
            video_binario=datos,
            prompt=texto or texto_default
        )
        '''elif mime.startswith("application/pdf"):
        texto_default = "Resume este PDF y genera un quiz con claves de respuesta."
        resultado = analizar_pdf_gemini_flash(
            pdf_binario=datos,
            prompt=texto or texto_default
            )'''
    # En cualquier otro caso, asumimos imagen
    else:
        # aqui estoy usando el modelo de local del sistema...
        texto_default = "Describe detalladamente qué contiene esta imagen."
        
        resultado = generator_gemma3(prompt=texto or texto_default, imagen_binaria=datos)
        #resultado = analizar_imagen_gemini_flash(
        #    imagen_binaria=datos,
        #    prompt=texto or texto_default
        #)

    # Devolvemos ese resultado (ya es un string con response.text)
    hablar(resultado) 
    return resultado

if __name__ == "__main__":
    enviar_whatsapp()