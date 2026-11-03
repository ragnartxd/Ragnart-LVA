import cv2
import detectarMano as dm

detector = dm.detectormanos()
cap = cv2.VideoCapture(0)

# Configurar la cámara para mejor rendimiento
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)

# Variables para suavizar la detección
contador_frames = 0
dedos_previos = []
FRAMES_PARA_CAMBIO = 3  # Número de frames consecutivos necesarios para cambiar el conteo

while True:
    success, img = cap.read()
    if not success:
        continue
        
    img = cv2.flip(img, 1)  # Voltear imagen horizontalmente
    img = detector.encontrarManos(img)
    lmList, bbox = detector.encontrarPosicion(img)

    if lmList:
        dedos = detector.dedosArriba(img)
        contar = sum(dedos)
        
        # Sistema de suavizado para evitar cambios bruscos
        if len(dedos_previos) >= FRAMES_PARA_CAMBIO:
            dedos_previos.pop(0)
        dedos_previos.append(contar)
        
        # Usar el conteo más frecuente de los últimos frames
        if len(dedos_previos) == FRAMES_PARA_CAMBIO:
            contar_final = max(set(dedos_previos), key=dedos_previos.count)
        else:
            contar_final = contar
        
        # Generar el texto según el número de dedos
        textos = {
            0: "Ningún dedo arriba",
            1: "Un dedo arriba", 
            2: "Dos dedos arriba",
            3: "Tres dedos arriba",
            4: "Cuatro dedos arriba",
            5: "Cinco dedos arriba"
        }
        
        texto = textos.get(contar_final, f"{contar_final} dedos arriba")
        
        # Mostrar información en pantalla
        cv2.putText(img, texto, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
        cv2.putText(img, f"Dedos detectados: {dedos}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # Mostrar el recuadro de la mano si está disponible
        if bbox:
            x, y, w, h = bbox
            cv2.rectangle(img, (x-20, y-20), (x+w+20, y+h+20), (0, 255, 0), 2)
    else:
        # Limpiar el historial si no se detecta mano
        dedos_previos = []
        cv2.putText(img, "No se detecta mano", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # Agregar instrucciones en pantalla
    cv2.putText(img, "Presiona 'q' para salir", (10, img.shape[0] - 20), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    cv2.imshow("Contar Dedos - Mejorado", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()