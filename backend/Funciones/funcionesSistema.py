"""
Funciones del sistema, util para la automatizacion de tareas. 
"""
import ctypes, json, pyautogui, os, re, threading, time, datetime, winsound, smtplib
import subprocess
import unicodedata
from backend.Generacion.from_TTS import hablar
from backend.Gestor.GestorParametros import Gestor_Parametros
from backend.contactos import cargar_contactos_guardados
from backend.configuracion_usuario import PROJECT_ROOT
from backend.utils.utils_instruccion_adicional import decir_y_escuchar
from backend.utils.json_storage import guardar_json_atomico

_BASE_DIR = str(PROJECT_ROOT)

# Cargar secuencias desde archivo JSON (si existe)
sequences_path = os.path.join(_BASE_DIR, "importaciones", "sequences.json")
try:
    with open(sequences_path, "r", encoding="utf-8") as f:
        sequences = json.load(f)
except FileNotFoundError:
    sequences = {}

stop_replay = False  # Bandera global para detener la reproducción

def grabar_secuencia():
    """Graba una secuencia de teclas y clics hasta detectar 3 segundos de inactividad."""
    import keyboard
    acciones = []
    hablar("Grabando... Finaliza automáticamente después de 3 segundos sin acción.")
    estado = {"ultima_actividad": time.monotonic()}
    bloqueo = threading.Lock()

    def registrar_tecla(evento):
        if evento.event_type == keyboard.KEY_DOWN:
            with bloqueo:
                acciones.append(("tecla", evento.name))
                estado["ultima_actividad"] = time.monotonic()

    hook = keyboard.hook(registrar_tecla, suppress=False)
    mouse_presionado = False
    try:
        while True:
            estado_mouse = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
            if estado_mouse and not mouse_presionado:
                posicion = pyautogui.position()
                with bloqueo:
                    acciones.append(("clic", [int(posicion.x), int(posicion.y)]))
                    estado["ultima_actividad"] = time.monotonic()
            mouse_presionado = estado_mouse
            with bloqueo:
                sin_actividad = time.monotonic() - estado["ultima_actividad"] >= 3
            if sin_actividad:
                break
            time.sleep(0.02)
    finally:
        keyboard.unhook(hook)

    hablar("Grabación finalizada.")
    return acciones

def guardar_secuencia(nombre, acciones):
    """Guarda la secuencia con el nombre proporcionado."""
    sequences[nombre] = acciones
    guardar_json_atomico(sequences_path, sequences, indent=2, ensure_ascii=False)
    hablar(f"Secuencia guardada como '{nombre}'.")

def reproducir_secuencia(nombre):
    """Reproduce una secuencia guardada hasta que se presione ESC."""
    global stop_replay
    if nombre not in sequences:
        return f"No se encontró la secuencia '{nombre}'."

    stop_replay = False
    acciones = sequences[nombre]

    def monitorear_parada():
        """Detiene la reproducción si se presiona ESC."""
        import keyboard
        global stop_replay
        while not stop_replay:
            if keyboard.is_pressed('esc'):
                stop_replay = True
            time.sleep(0.1)

    hilo_monitoreo = threading.Thread(target=monitorear_parada, daemon=True)
    hilo_monitoreo.start()

    hablar(f"▶Reproduciendo secuencia '{nombre}' (presiona ESC para detener)...")
    while not stop_replay:
        for accion in acciones:
            if stop_replay:
                break
            if accion[0] == 'tecla':
                pyautogui.press(accion[1])
            elif accion[0] == 'clic':
                pyautogui.click(*accion[1])
            time.sleep(0.1)
    hablar("Reproducción detenida.")
    hilo_monitoreo.join()

def ejecutar_comando_secuencia(
    comando_usuario: str = None,
    comando_voz: str = None,
    texto_comando: str = None,
):
    """
    Procesa comandos como:
    - "graba la secuencia y guárdala como abrir_calculadora"
    - "reproduce la secuencia abrir_calculadora"
    """
    comando_usuario = comando_usuario or comando_voz or texto_comando
    if not isinstance(comando_usuario, str):
        return "Comando de secuencia no reconocido."
    comando = comando_usuario.lower().strip()
    comando_simple = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", comando)
        if unicodedata.category(caracter) != "Mn"
    )

    if "graba la secuencia y guárdala como" in comando:
        nombre = comando.split("graba la secuencia y guárdala como")[-1].strip()
        acciones = grabar_secuencia()
        guardar_secuencia(nombre, acciones)
        return f"Secuencia '{nombre}' grabada y guardada correctamente."

    elif comando.startswith("reproduce la secuencia"):
        nombre = comando.split("reproduce la secuencia")[-1].strip()
        reproducir_secuencia(nombre)
        return f"Secuencia '{nombre}' reproducida."

    elif any(
        frase in comando_simple
        for frase in ("repite la accion anterior", "repite lo anterior", "ejecuta de nuevo", "vuelve a hacer")
    ):
        if not sequences:
            return "No hay una secuencia guardada para repetir."
        nombre = next(reversed(sequences))
        reproducir_secuencia(nombre)
        return f"Última secuencia '{nombre}' reproducida."

    elif "graba el comando" in comando or "graba ese comando" in comando:
        nombre = decir_y_escuchar("¿Qué nombre le pongo a la secuencia?")
        if not isinstance(nombre, str) or not nombre.strip():
            return "No se grabó la secuencia porque falta el nombre."
        nombre = nombre.strip()
        acciones = grabar_secuencia()
        guardar_secuencia(nombre, acciones)
        return f"Secuencia '{nombre}' grabada y guardada correctamente."

    else:
        return "Comando de secuencia no reconocido."

def obtener_ventana(nombre_app):
    """Obtiene la ventana que coincida con el nombre de la aplicación usando búsqueda parcial."""
    import pygetwindow as gw

    if not isinstance(nombre_app, str):
        return None
    if not nombre_app.strip():
        return None

    nombre_normalizado = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", nombre_app.casefold().strip())
        if unicodedata.category(caracter) != "Mn"
    )
    palabras = nombre_normalizado.split()
    referencia_actual = (
        ("ventana" in palabras or "aplicacion" in palabras)
        and any(
            palabra in palabras
            for palabra in ("actual", "activa", "esta", "esa", "abierta")
        )
    )
    if referencia_actual:
        return gw.getActiveWindow()

    ventanas = gw.getAllWindows()
    for ventana in ventanas:
        if nombre_app.lower() in ventana.title.lower():
            return ventana
    return None

def gestionar_ventana(**kwargs):
    """Gestiona la ventana de una aplicación según la acción especificada."""
    parametros = dict(kwargs)
    accion = parametros.pop("accion", "cerrar_aplicacion")
    parametros["accion"] = accion
    datos = Gestor_Parametros.procesar(
        {"accion": "gestionar_ventana", "params": parametros}
    )
    nombre_app = datos["params"]["nombre_app"]
    accion = datos["params"]["accion"]

    ventana = obtener_ventana(nombre_app)
    if not ventana:
        return f"No se encontró una ventana con el nombre '{nombre_app}'."

    acciones = {
        "minimizar_aplicacion": ventana.minimize,
        "maximizar_aplicacion": ventana.maximize,
        "cerrar_aplicacion": ventana.close,
        "alternar_aplicacion": lambda: ventana.restore() if ventana.isMinimized else ventana.minimize()
    }

    if accion in acciones:
        try:
            acciones[accion]()
            return f"{accion.replace('_aplicacion', '').capitalize()} '{ventana.title}'."
        except Exception as e:
            return f"Error ejecutando '{accion}': {str(e)}"

    return "Acción no reconocida."


def cerrar_aplicacion(**kwargs):
    return gestionar_ventana(**{**kwargs, "accion": "cerrar_aplicacion"})


def minimizar_aplicacion(**kwargs):
    return gestionar_ventana(**{**kwargs, "accion": "minimizar_aplicacion"})


def maximizar_aplicacion(**kwargs):
    return gestionar_ventana(**{**kwargs, "accion": "maximizar_aplicacion"})


def alternar_aplicacion(**kwargs):
    return gestionar_ventana(**{**kwargs, "accion": "alternar_aplicacion"})


def handler_escribir_word(**kwargs):
    """
    Maneja la escritura en un documento de Word.
    """
    from docx import Document
    from backend.Generacion.AIGeneration import generator_gemma3
    datos = Gestor_Parametros.procesar({"accion": "escribir_word", "params": kwargs})
    texto_a_escribir = datos["params"].get("texto_completo", "").strip()

    prompt = f"Escribe un párrafo sobre '{texto_a_escribir}'."

    resultado = generator_gemma3(prompt)
    texto_generado = (
        resultado if isinstance(resultado, str) else "".join(map(str, resultado))
    )

    base_path = os.path.join(os.path.expanduser("~"), "Desktop", "documento_generado")
    file_path = f"{base_path}.docx"
    count = 1

    while os.path.exists(file_path):
        file_path = f"{base_path}_{count}.docx"
        count += 1

    try:
        doc = Document()
        doc.add_paragraph(texto_generado)
        doc.save(file_path)
        abrir = decir_y_escuchar("¿Quieres abrir el documento generado? Di ‘sí’ o ‘no’.")
        if abrir and "sí" in abrir.lower():
            os.startfile(file_path)
            return f"Documento abierto: {file_path}."
        else:
            return f"Documento creado en: {file_path}."
    except Exception as e:
        return f"Error al escribir en Word: {e}"

def handler_enviar_correo(**kwargs):
    """
    Maneja el envío de correos electrónicos.
    """
    from email.mime.text import MIMEText
    from backend.configuracion_entorno import obtener_variable_entorno

    email = obtener_variable_entorno("SMTP_EMAIL")
    password = obtener_variable_entorno("SMTP_PASSWORD")
    if not email or not password:
        return "Correo no configurado. Define SMTP_EMAIL y SMTP_PASSWORD en .env."

    datos = Gestor_Parametros.procesar({"accion": "enviar_correo", "params": kwargs})
    destinatario = datos["params"]["destinatario"]

    if not  destinatario:
        destinatario = decir_y_escuchar("dime el destinatario del correo electrónico.")
        datos["params"]["destinatario"] = destinatario
    
    contactos_guardados = cargar_contactos_guardados()
    destinatario = contactos_guardados.get(destinatario, destinatario) or destinatario
    
    asunto = datos["params"]["asunto"]

    if not asunto:
        hablar("Asunto del correo no especificado. Por favor, dime el asunto.")
        asunto = decir_y_escuchar("dime el asunto del correo electrónico.")
        datos["params"]["asunto"] = asunto
        
    cuerpo = datos["params"]["cuerpo"]

    if not cuerpo:
        hablar("Cuerpo del correo no especificado. Por favor, dime el cuerpo del correo.")
        cuerpo = decir_y_escuchar("dime el cuerpo del correo electrónico.")
        datos["params"]["cuerpo"] = cuerpo

    try:
        msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = asunto
        msg["From"] = email
        msg["To"] = destinatario

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(email, password)
            servidor.sendmail(email, destinatario, msg.as_string().encode("utf-8"))
        return f"Correo enviado a {destinatario} con asunto '{asunto}'."
    except Exception as e:
        return f"Error al enviar el correo: {e}"

def handler_obtener_hora(**kwargs):
    """Devuelve la hora actual en formato de 12h o 24h según el parámetro recibido."""
    datos = Gestor_Parametros.procesar({"accion": "obtener_hora", "params": kwargs})
    formato_24h = datos["params"].get("formato_24h", True)

    hora_actual = datetime.datetime.now().strftime("%H:%M:%S") if formato_24h else datetime.datetime.now().strftime("%I:%M:%S %p")
    print(f"Hora actual: {hora_actual}")
    return f"Di que la hora actual es {hora_actual}."

def poner_alarma(**kwargs):
    """
    Programa una alarma para una hora específica.
    """
    datos = Gestor_Parametros.procesar({"accion": "poner_alarma", "params": kwargs})
    hora_texto = datos["params"]["hora_texto"].strip()
    hora_normalizada = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", hora_texto.casefold())
        if unicodedata.category(caracter) != "Mn"
    )
    hora_normalizada = re.sub(r"^(?:(?:a|para)\s+)?(?:las?\s+)?", "", hora_normalizada).strip()
    periodo = None
    for sufijo in (" de la manana", " de la tarde", " de la noche", " am", " pm"):
        if hora_normalizada.endswith(sufijo):
            hora_normalizada = hora_normalizada[: -len(sufijo)].strip()
            periodo = sufijo.strip()
            break

    coincidencia = re.fullmatch(r"(\d{1,2})(?::(\d{2})|(\d{2}))?", hora_normalizada)
    if not coincidencia:
        return "Hora inválida. Usa HH:MM o HHMM."
    hora = int(coincidencia.group(1))
    minuto = int(coincidencia.group(2) or coincidencia.group(3) or 0)

    if periodo in ("pm", "de la tarde", "de la noche"):
        if not 1 <= hora <= 12:
            return "Hora inválida. La hora debe estar entre 00:00 y 23:59."
        if hora < 12:
            hora += 12
    elif periodo in ("am", "de la manana"):
        if not 1 <= hora <= 12:
            return "Hora inválida. La hora debe estar entre 00:00 y 23:59."
        if hora == 12:
            hora = 0
    if not 0 <= hora <= 23 or not 0 <= minuto <= 59:
        return "Hora inválida. La hora debe estar entre 00:00 y 23:59."

    ahora = datetime.datetime.now()
    hoy_objetivo = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if hoy_objetivo <= ahora:
        # Si ya pasó esa hora hoy, lo programamos para mañana:
        hoy_objetivo += datetime.timedelta(days=1)

    segundos_espera = (hoy_objetivo - ahora).total_seconds()

    def alarma():
        """Función que se ejecuta cuando suena la alarma."""
        for _ in range(5):
            winsound.PlaySound("SystemExit", winsound.SND_ALIAS)
            time.sleep(1)
        print(f"¡Alarma activada! Son las {datetime.datetime.now().strftime('%H:%M:%S')}")

    # Usamos el número de segundos exacto, no 10 fijos:
    temporizador = threading.Timer(segundos_espera, alarma)
    temporizador.daemon = True
    temporizador.start()
    return f"Alarma programada para las {hoy_objetivo.strftime('%H:%M')}."

def poner_cronometro(**kwargs):
    """
    Programa un cronómetro para un tiempo específico.
    """
    duracion = kwargs.get("segundos")
    if isinstance(duracion, bool):
        return "La duración del cronómetro debe ser un número entero mayor que cero."
    datos = Gestor_Parametros.procesar({"accion": "poner_cronometro", "params": kwargs})
    segundos = datos["params"]["segundos"]
    if segundos <= 0:
        return "La duración del cronómetro debe ser mayor que cero."

    def iniciar_cronometro():
        print(f"Cronómetro iniciado: {segundos} segundos.")
        time.sleep(segundos)
        print("¡Tiempo terminado!")

    hilo = threading.Thread(target=iniciar_cronometro, daemon=True)
    hilo.start()
    return f"Cronómetro iniciado por {segundos} segundos."

def apagar_sistema():
    """
    Apaga el sistema inmediatamente.
    """
    try:
        if os.system("shutdown /s /t 0") != 0:
            return "Error al apagar el sistema."
        return "Sistema apagándose."
    except Exception as e:
        return f"Error al apagar el sistema: {e}"

def reiniciar_sistema():
    """Reinicia el sistema inmediatamente."""
    try:
        if os.system("shutdown /r /t 0") != 0:
            return "Error al reiniciar el sistema."
        return "Sistema reiniciándose."
    except Exception as e:
        return f"Error al reiniciar el sistema: {e}"

def suspender_sistema():
    """Suspende el sistema (modo de suspensión)."""
    try:
        if os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0") != 0:
            return "Error al suspender el sistema."
        return "Sistema suspendido."
    except Exception as e:  
        return f"Error al suspender el sistema: {e}"

def bloquear_sistema():
    """Bloquea el sistema (muestra la pantalla de bloqueo)."""
    try:
        if os.system("rundll32.exe user32.dll,LockWorkStation") != 0:
            return "Error al bloquear el sistema."
        return "Sistema bloqueado."
    except Exception as e:
        return f"Error al bloquear el sistema: {e}"


def activar_bluetooth(estado=None, texto_comando=None):
    """ Activa o desactiva el Bluetooth llamando a un script PowerShell """
    try:
        if (estado is None or estado == "") and isinstance(texto_comando, str):
            estado = texto_comando
        if not isinstance(estado, str):
            return "Estado inválido. Usa 'on' para activar o 'off' para desactivar."
        estado = estado.strip().lower()
        estado_simple = "".join(
            caracter
            for caracter in unicodedata.normalize("NFD", estado)
            if unicodedata.category(caracter) != "Mn"
        )
        if estado in ("apagar bluetooth", "desactivar bluetooth", "apaga bluetooth", "desactiva bluetooth"):
            estado = "off"
        elif estado in ("encender bluetooth", "activar bluetooth", "enciende bluetooth", "activa bluetooth"):
            estado = "on"
        elif "bluetooth" in estado_simple:
            verbo = estado_simple.split()[0]
            if verbo.startswith(("apaga", "apagar", "desactiva", "desactivar", "deshabilita", "deshabilitar")):
                estado = "off"
            elif verbo.startswith(("enciende", "encender", "activa", "activar", "habilita", "prende", "conecta")):
                estado = "on"
        if estado not in ["on", "off"]:
            return "Estado inválido. Usa 'on' para activar o 'off' para desactivar."
        
        script_path = PROJECT_ROOT / "importaciones" / "activar_bluetooth.ps1"
        resultado = subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                estado,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if resultado.returncode != 0:
            detalle = resultado.stderr.strip()
            if detalle:
                return f"Error al cambiar Bluetooth a {estado}: {detalle}"
            return f"Error al cambiar Bluetooth a {estado}. Intenta ejecutarlo como administrador."
        
        return f"Bluetooth cambiado a {estado} correctamente."
    except Exception as e:
        return f"Error al cambiar el estado de Bluetooth: {e}"

def activar_wifi(): # toca adaptarlo para obtener el nombre del adaptador
    """Activa el adaptador WiFi en el sistema."""
    nombre_wifi = "Wi-Fi"  # Cambia esto si el nombre de tu WiFi es diferente
    cmd = f'netsh interface set interface name="{nombre_wifi}" admin=enabled'
    ret = os.system(cmd)
    
    if ret != 0:
        return "Error: No se pudo activar el WiFi. Verifica que el nombre del adaptador es correcto."
    return "WiFi activado correctamente."
    
def subir_volumen():
    """Sube el volumen del sistema en incrementos de 10."""
    for _ in range(5):  # Simula 5 pulsaciones rápidas
        pyautogui.press("volumeup")
        time.sleep(0.05)  # Pequeña pausa para evitar errores en algunos sistemas
    return "Volumen aumentado en 5 pasos."

def bajar_volumen():
    """Baja el volumen del sistema en decrementos de 10."""
    for _ in range(5):
        pyautogui.press("volumedown")
        time.sleep(0.05)
    return "Volumen reducido en 5 pasos."

def ajustar_brillo(nuevo_valor):
    """
    Ajusta el brillo de la pantalla al valor especificado (0-100).
    Requiere PowerShell y soporte WMI.
    """
    if isinstance(nuevo_valor, bool) or not isinstance(nuevo_valor, int):
        return "El brillo debe ser un número entero entre 0 y 100."
    if not 0 <= nuevo_valor <= 100:
        return "El brillo debe estar entre 0 y 100."
    comando = (
        "$monitores = Get-WmiObject -Namespace root/WMI "
        "-Class WmiMonitorBrightnessMethods; "
        "if (-not $monitores) { exit 2 }; "
        f"$monitores | ForEach-Object {{ $_.WmiSetBrightness(1, {nuevo_valor}) }}"
    )
    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-Command", comando],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return "No se pudo ajustar el brillo: PowerShell excedió el tiempo de espera."
    except OSError as error:
        return f"No se pudo ajustar el brillo: {error}"
    if resultado.returncode != 0:
        detalle = resultado.stderr.strip()
        return f"No se pudo ajustar el brillo: {detalle or 'no hay monitor compatible.'}"
    return f"Brillo ajustado a {nuevo_valor}."


if __name__ == "__main__":
    handler_escribir_word(texto_completo="un articulo universitario completo, detallado y extenso, con una estructura clara sobre las celulas")
