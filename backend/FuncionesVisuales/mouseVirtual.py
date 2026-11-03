# No esta implementado
import cv2
import numpy as np
import detectarMano as sm
import autopy
import time

# Configuración de parámetros
anchocam, altocam = 640, 480
cuadro = 100  # Tamaño del cuadro de la mano
anchopanta, altopanta = autopy.screen.size()  # Tamaño de la pantalla
sua = 7  # Factor de suavizado
pubix, pubiy = 0, 0
cubix, cubiy = 0, 0

# Variables para controlar clics duraderos
click_izquierdo_activo = False
tiempo_ultimo_click = 0
tiempo_espera_click = 0.3  # Tiempo mínimo entre clics (segundos)

# Configurar captura de video
cap = cv2.VideoCapture(0)
cap.set(3, anchocam)
cap.set(4, altocam)

detector = sm.detectormanos(maxHands=1)  # Solo usaremos una mano

def mostrar_instrucciones(frame):
    """Mostrar las instrucciones de uso en el frame"""
    instrucciones = [
        "CONTROLES:",
        "1 dedo (indice) = Mover cursor",
        "2 dedos juntos (indice+medio) = Clic izquierdo",
        "3 dedos (indice+medio+anular) = Clic derecho",
        "Pulgar+indice juntos = Clic izq. duradero",
        "ESC = Salir"
    ]
    
    y_offset = 50
    for i, texto in enumerate(instrucciones):
        color = (0, 255, 255) if i == 0 else (255, 255, 255)
        grosor = 2 if i == 0 else 1
        cv2.putText(frame, texto, (10, y_offset + i * 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, grosor)

def detectar_gesto_duradero(detector, frame):
    """Detectar si el pulgar e índice están juntos para clic duradero"""
    try:
        # Calcular distancia entre pulgar (4) e índice (8)
        longitud_pulgar_indice, _, _ = detector.distancia(4, 8, frame, draw=False)
        return longitud_pulgar_indice < 40  # Umbral para considerar "juntos"
    except:
        return False

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: No se pudo leer el frame de la cámara")
        break
    
    frame = cv2.flip(frame, 1)  # Voltear horizontalmente para efecto espejo
    frame = detector.encontrarManos(frame)
    lista, bbox = detector.encontrarPosicion(frame)

    if len(lista) != 0:
        x1, y1 = lista[8][1:]  # Punta del dedo índice
        x2, y2 = lista[12][1:]  # Punta del dedo medio
        
        dedos = detector.dedosArriba(frame)  # Contar dedos arriba
        tiempo_actual = time.time()
        
        # Dibujar cuadro de trabajo
        cv2.rectangle(frame, (cuadro, cuadro), (anchocam - cuadro, altocam - cuadro), (255, 0, 255), 2)

        # Detectar gesto de clic duradero (pulgar + índice juntos)
        gesto_duradero = detectar_gesto_duradero(detector, frame)
        
        # MODO 1: Movimiento - solo dedo índice arriba
        if dedos[1] == 1 and dedos[2] == 0 and dedos[3] == 0 and not gesto_duradero:
            # Mapear coordenadas de la cámara a la pantalla
            x3 = np.interp(x1, (cuadro, anchocam - cuadro), (0, anchopanta))
            y3 = np.interp(y1, (cuadro, altocam - cuadro), (0, altopanta))

            # Aplicar suavizado
            cubix = pubix + (x3 - pubix) / sua
            cubiy = pubiy + (y3 - pubiy) / sua

            # Mover el mouse
            autopy.mouse.move(cubix, cubiy)
            cv2.circle(frame, (x1, y1), 15, (0, 255, 0), cv2.FILLED)
            cv2.putText(frame, "MOVER", (x1 + 20, y1), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            pubix, pubiy = cubix, cubiy
            
            # Si había un clic duradero activo, liberarlo
            if click_izquierdo_activo:
                autopy.mouse.toggle(autopy.mouse.Button.LEFT, False)
                click_izquierdo_activo = False
        
        # MODO 2: Clic izquierdo - índice y medio arriba, anular abajo
        elif dedos[1] == 1 and dedos[2] == 1 and dedos[3] == 0 and not gesto_duradero:
            try:
                longitud, punto_medio, frame = detector.distancia(8, 12, frame)
                
                # Si los dedos están muy cerca, hacer clic izquierdo
                if longitud < 30 and tiempo_actual - tiempo_ultimo_click > tiempo_espera_click:
                    cv2.circle(frame, punto_medio, 15, (0, 0, 255), cv2.FILLED)
                    cv2.putText(frame, "CLIC IZQ", (punto_medio[0] + 20, punto_medio[1]), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    autopy.mouse.click()
                    tiempo_ultimo_click = tiempo_actual
                    
                    # Liberar clic duradero si estaba activo
                    if click_izquierdo_activo:
                        autopy.mouse.toggle(autopy.mouse.Button.LEFT, False)
                        click_izquierdo_activo = False
                        
            except Exception as e:
                print(f"Error en detección de distancia para clic izquierdo: {e}")
        
        # MODO 3: Clic derecho - índice, medio y anular arriba
        elif dedos[1] == 1 and dedos[2] == 1 and dedos[3] == 1 and dedos[4] == 0:
            try:
                # Calcular distancia entre índice y anular para activar clic derecho
                longitud_der, punto_medio_der, frame = detector.distancia(8, 16, frame)
                
                if longitud_der < 50 and tiempo_actual - tiempo_ultimo_click > tiempo_espera_click:
                    cv2.circle(frame, punto_medio_der, 15, (255, 0, 0), cv2.FILLED)
                    cv2.putText(frame, "CLIC DER", (punto_medio_der[0] + 20, punto_medio_der[1]), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    autopy.mouse.click(autopy.mouse.Button.RIGHT)
                    tiempo_ultimo_click = tiempo_actual
                    
                    # Liberar clic duradero si estaba activo
                    if click_izquierdo_activo:
                        autopy.mouse.toggle(autopy.mouse.Button.LEFT, False)
                        click_izquierdo_activo = False
                        
            except Exception as e:
                print(f"Error en detección de clic derecho: {e}")
        
        # MODO 4: Clic izquierdo duradero - pulgar e índice juntos
        elif gesto_duradero and dedos[1] == 1:
            try:
                # Activar/desactivar clic duradero
                if not click_izquierdo_activo and tiempo_actual - tiempo_ultimo_click > tiempo_espera_click:
                    autopy.mouse.toggle(autopy.mouse.Button.LEFT, True)
                    click_izquierdo_activo = True
                    tiempo_ultimo_click = tiempo_actual
                    
                # Mostrar indicador visual
                cv2.circle(frame, (x1, y1), 20, (0, 255, 255), 3)
                cv2.putText(frame, "CLIC DURADERO", (x1 + 25, y1), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                # Continuar moviendo el mouse mientras se mantiene presionado
                x3 = np.interp(x1, (cuadro, anchocam - cuadro), (0, anchopanta))
                y3 = np.interp(y1, (cuadro, altocam - cuadro), (0, altopanta))
                cubix = pubix + (x3 - pubix) / sua
                cubiy = pubiy + (y3 - pubiy) / sua
                autopy.mouse.move(cubix, cubiy)
                pubix, pubiy = cubix, cubiy
                
            except Exception as e:
                print(f"Error en clic duradero: {e}")
        
        # Si no hay ningún gesto reconocido, liberar clic duradero
        else:
            if click_izquierdo_activo:
                autopy.mouse.toggle(autopy.mouse.Button.LEFT, False)
                click_izquierdo_activo = False
    
    else:
        # Si no se detecta mano, liberar clic duradero
        if click_izquierdo_activo:
            autopy.mouse.toggle(autopy.mouse.Button.LEFT, False)
            click_izquierdo_activo = False
    
    # Mostrar información en pantalla
    cv2.putText(frame, f'Pantalla: {anchopanta}x{altopanta}', (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Mostrar estado del clic duradero
    if click_izquierdo_activo:
        cv2.putText(frame, 'CLIC DURADERO ACTIVO', (10, altocam - 80), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    # Mostrar instrucciones
    mostrar_instrucciones(frame)
    
    cv2.imshow("Mouse Virtual Mejorado", frame)
    
    # Presionar Esc para salir
    if cv2.waitKey(1) & 0xFF == 27:
        # Asegurarse de liberar el clic duradero al salir
        if click_izquierdo_activo:
            autopy.mouse.toggle(autopy.mouse.Button.LEFT, False)
        break

cap.release()
cv2.destroyAllWindows()