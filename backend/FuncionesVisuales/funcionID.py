# standalone_auth.py

import cv2
from backend.Funciones.funcionesSistema import decir_y_escuchar
from backend.Generacion.from_TTS import hablar
from backend.FuncionesVisuales.face.core_functionality import FaceSystemCore

def textInNum(texto):
    """convierte los numeros de texto en digitos"""
    numeros = {
        "cero": 0,
        "uno": 1,
        "dos": 2,
        "tres": 3,
        "cuatro": 4,
        "cinco": 5,
        "seis": 6,
        "siete": 7,
        "ocho": 8,
        "nueve": 9
    }
    for palabra, numero in numeros.items():
        texto = texto.replace(palabra, str(numero))
    return texto

def sign_up():
    """
    Flujo de registro (enrolamiento) “headless” salvo la ventana de cámara:
    1. Pide nombre de usuario y código.
    2. Arranca la cámara y muestra el video con el mapeo de la cara.
    3. Captura múltiples embeddings y guarda en la base de datos.
    4. Cierra la cámara y la ventana.
    """
    core = FaceSystemCore()
    user_name = decir_y_escuchar("Dime el nombre de usuario que deseas registrar").strip()
    user_code_text = decir_y_escuchar("Dime un código único (numérico o alfanumérico): ").strip()
    user_code = textInNum(user_code_text)
    hablar(f"\nRegistrando usuario: {user_name} con código: {user_code_text}\n")
    validacion = decir_y_escuchar("¿Es correcto? Responde 'sí' o 'no', di 'cancelar' para abortar.").strip().lower()

    while validacion not in ['sí', 'si']:
        if validacion not in ['sí', 'si', 'yes']:
            user_name = decir_y_escuchar("Por favor, dime el nombre de usuario nuevamente").strip()
            user_code_text = decir_y_escuchar("Dime un código único nuevamente: ").strip()
            user_code = textInNum(user_code_text)
            hablar(f"\nRegistrando usuario: {user_name} con código: {user_code_text}\n")
            validacion = decir_y_escuchar("¿Es correcto? Responde 'sí' o 'no', di 'cancelar' para abortar.").strip().lower()
        elif validacion == 'cancelar':
            hablar("Registro cancelado por el usuario.")
            return

    # Prepara el enrolamiento
    core.face_sign_up.reset()
    core.camera_manager.start_camera()

    hablar("\nMueve la cara hasta que la malla esté estable y centrada.")

    try:
        while True:
            frame = core.camera_manager.get_frame()
            # process devuelve (processed_frame, done, mensaje)
            processed_frame, done, mensaje = core.face_sign_up.process(frame, user_name, user_code)
            
            # Muestra el frame con overlay
            cv2.imshow("Registro de rostro", processed_frame)

            if done:
                print("✅ Registro completado:", mensaje)
                cv2.waitKey(1500)  # breve pausa para confirmar al usuario
                break

            # Tecla 'q' para forzar captura temprana
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("🔔 Captura forzada por el usuario.")
                # opcionalmente podrías llamar a process() de nuevo para rematar la captura
                break

    finally:
        core.camera_manager.stop_camera()
        cv2.destroyAllWindows()


def login():
    """
    Flujo de login “headless” salvo la ventana de cámara:
    1. Indica al usuario que centre su rostro.
    2. Arranca la cámara y muestra el video con el mapeo de la cara.
    3. Cuando detecta un resultado (True/False), imprime el mensaje y cierra.
    """
    core = FaceSystemCore()
    core.camera_manager.start_camera()

    hablar("\nSitúate centrado frente a la cámara. Trata de ver a la camara y espera a que el sistema te reconozca.")
    hablar("Esperando reconocimiento...")

    try:
        while True:
            frame = core.camera_manager.get_frame()
            processed_frame, recognized, message, user_name = core.face_login.process(frame)

            cv2.imshow("Validación de rostro", processed_frame)

            # recognized es None mientras no hay resultado final
            if recognized is not None:
                # recognized==True/False, message contiene el texto (Bienvenido…/Acceso denegado…)
                hablar(message)
                cv2.waitKey(1500)
                break

            if cv2.waitKey(1) & 0xFF == ord('q'):
                hablar("Login cancelado por el usuario.")
                break

    finally:
        core.camera_manager.stop_camera()
        cv2.destroyAllWindows()

    return user_name
