# No esta implementado
# Detector de gestos: Corazón y Paz
import cv2
import mediapipe as mp
import math
import numpy as np

class DetectorGestos():
    def __init__(self, mode=False, maxHands=2, modelComplexity=1, detectionCon=0.7, trackCon=0.5):
        self.mode = mode
        self.maxHands = maxHands
        self.modelComplexity = modelComplexity
        self.detectionCon = detectionCon
        self.trackCon = trackCon

        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(self.mode, self.maxHands, self.modelComplexity, self.detectionCon, self.trackCon)
        self.mpDraw = mp.solutions.drawing_utils
        
        # Historia de gestos para suavizado
        self.historial_gestos = []
        self.FRAMES_PARA_CONFIRMAR = 5

    def encontrarManos(self, img, draw=True):
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.resultados = self.hands.process(imgRGB)

        if self.resultados.multi_hand_landmarks:
            for manoLms in self.resultados.multi_hand_landmarks:
                if draw:
                    self.mpDraw.draw_landmarks(img, manoLms, self.mpHands.HAND_CONNECTIONS)
        return img

    def encontrarPosicion(self, img, manoN=0, draw=True):
        self.lmList = []
        if self.resultados.multi_hand_landmarks:
            mano = self.resultados.multi_hand_landmarks[manoN]
            for id, lm in enumerate(mano.landmark):
                h, w, c = img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                self.lmList.append([id, cx, cy])
                if draw:
                    cv2.circle(img, (cx, cy), 3, (255, 0, 255), cv2.FILLED)
        return self.lmList

    def calcularDistancia(self, p1, p2):
        """Calcula la distancia entre dos puntos"""
        if len(self.lmList) > max(p1, p2):
            x1, y1 = self.lmList[p1][1], self.lmList[p1][2]
            x2, y2 = self.lmList[p2][1], self.lmList[p2][2]
            return math.hypot(x2 - x1, y2 - y1)
        return 0

    def calcularAngulo(self, p1, p2, p3):
        """Calcula el ángulo entre tres puntos"""
        if len(self.lmList) > max(p1, p2, p3):
            x1, y1 = self.lmList[p1][1], self.lmList[p1][2]
            x2, y2 = self.lmList[p2][1], self.lmList[p2][2]
            x3, y3 = self.lmList[p3][1], self.lmList[p3][2]
            
            # Vectores
            v1 = np.array([x1 - x2, y1 - y2])
            v2 = np.array([x3 - x2, x3 - y2])
            
            # Ángulo en radianes
            cosine_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
            return np.degrees(angle)
        return 0

    def detectarPaz(self):
        """Detecta el signo de paz (dedos índice y medio extendidos)"""
        if not self.lmList:
            return False
            
        # Verificar que índice y medio están extendidos
        indice_extendido = self.lmList[8][2] < self.lmList[6][2]
        medio_extendido = self.lmList[12][2] < self.lmList[10][2]
        
        # Verificar que anular y meñique están doblados
        anular_doblado = self.lmList[16][2] > self.lmList[14][2]
        menique_doblado = self.lmList[20][2] > self.lmList[18][2]
        
        # Verificar que el pulgar está doblado (cerca de la palma)
        pulgar_doblado = self.calcularDistancia(4, 9) < self.calcularDistancia(3, 9)
        
        # Verificar separación entre índice y medio
        separacion_dedos = abs(self.lmList[8][1] - self.lmList[12][1])
        separacion_minima = 30  # Píxeles mínimos de separación
        
        return (indice_extendido and medio_extendido and 
                anular_doblado and menique_doblado and 
                pulgar_doblado and separacion_dedos > separacion_minima)

    def detectarCorazon(self):
        """Detecta si se están haciendo dos manos en forma de corazón"""
        if not self.resultados.multi_hand_landmarks or len(self.resultados.multi_hand_landmarks) < 2:
            return False
            
        # Necesitamos dos manos para hacer un corazón
        manos = []
        for i in range(min(2, len(self.resultados.multi_hand_landmarks))):
            mano_landmarks = []
            mano = self.resultados.multi_hand_landmarks[i]
            for id, lm in enumerate(mano.landmark):
                h, w, c = 480, 640, 3  # Dimensiones típicas
                cx, cy = int(lm.x * w), int(lm.y * h)
                mano_landmarks.append([id, cx, cy])
            manos.append(mano_landmarks)
        
        if len(manos) < 2:
            return False
            
        # Verificar posición de pulgares e índices para formar corazón
        mano1, mano2 = manos[0], manos[1]
        
        # Pulgares (punto 4) e índices (punto 8)
        pulgar1 = mano1[4]
        indice1 = mano1[8]
        pulgar2 = mano2[4]
        indice2 = mano2[8]
        
        # Calcular distancias para verificar si forman un corazón
        dist_pulgares = math.hypot(pulgar1[1] - pulgar2[1], pulgar1[2] - pulgar2[2])
        dist_indices = math.hypot(indice1[1] - indice2[1], indice1[2] - indice2[2])
        
        # Los pulgares deben estar cerca (forman la punta inferior del corazón)
        # Los índices deben estar separados (forman la parte superior del corazón)
        pulgares_juntos = dist_pulgares < 50
        indices_separados = dist_indices > 80 and dist_indices < 200
        
        # Verificar que los pulgares están por debajo de los índices (forma de corazón)
        pulgares_abajo = (pulgar1[2] > indice1[2]) and (pulgar2[2] > indice2[2])
        
        # Verificar que otros dedos están relativamente doblados
        dedos_doblados = True
        for mano in manos:
            # Medio, anular y meñique doblados
            if (mano[12][2] < mano[10][2] or 
                mano[16][2] < mano[14][2] or 
                mano[20][2] < mano[18][2]):
                dedos_doblados = False
                break
        
        return (pulgares_juntos and indices_separados and 
                pulgares_abajo and dedos_doblados)

    def detectarCorazonUnaMano(self):
        """Detecta corazón con una sola mano (pulgar e índice formando corazón)"""
        if not self.lmList:
            return False
            
        # Verificar que pulgar e índice forman una forma circular/corazón
        pulgar_tip = self.lmList[4]
        indice_tip = self.lmList[8]
        
        # Distancia entre pulgar e índice
        dist_pulgar_indice = self.calcularDistancia(4, 8)
        
        # Debe estar en un rango específico (ni muy cerca ni muy lejos)
        distancia_correcta = 20 < dist_pulgar_indice < 80
        
        # Verificar que otros dedos están extendidos o en posición específica
        medio_pos = self.lmList[12][2] < self.lmList[10][2]  # Medio extendido
        anular_pos = self.lmList[16][2] < self.lmList[14][2]  # Anular extendido
        menique_pos = self.lmList[20][2] < self.lmList[18][2]  # Meñique extendido
        
        # Verificar posición relativa (pulgar e índice deben estar en la parte superior)
        altura_correcta = (pulgar_tip[2] < self.lmList[9][2] and 
                          indice_tip[2] < self.lmList[9][2])
        
        return (distancia_correcta and medio_pos and 
                anular_pos and menique_pos and altura_correcta)

    def procesarGesto(self, img):
        """Procesa y determina el gesto actual"""
        gesto_actual = "Ninguno"
        
        if self.lmList:
            # Detectar gestos
            es_paz = self.detectarPaz()
            es_corazon_dos_manos = self.detectarCorazon()
            es_corazon_una_mano = self.detectarCorazonUnaMano()
            
            if es_corazon_dos_manos:
                gesto_actual = "Corazón (dos manos)"
            elif es_corazon_una_mano:
                gesto_actual = "Corazón (una mano)"
            elif es_paz:
                gesto_actual = "Paz"
        
        # Sistema de suavizado
        self.historial_gestos.append(gesto_actual)
        if len(self.historial_gestos) > self.FRAMES_PARA_CONFIRMAR:
            self.historial_gestos.pop(0)
        
        # Determinar gesto más frecuente
        if len(self.historial_gestos) >= 3:
            gesto_final = max(set(self.historial_gestos), key=self.historial_gestos.count)
        else:
            gesto_final = gesto_actual
            
        return gesto_final

def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    detector = DetectorGestos()
    
    while True:
        success, img = cap.read()
        if not success:
            continue
            
        img = cv2.flip(img, 1)
        img = detector.encontrarManos(img)
        
        # Procesar primera mano
        lmList = detector.encontrarPosicion(img, draw=False)
        gesto = detector.procesarGesto(img)
        
        # Mostrar resultado
        color = (0, 255, 0) if gesto != "Ninguno" else (0, 0, 255)
        cv2.putText(img, f"Gesto: {gesto}", (10, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        
        # Instrucciones
        cv2.putText(img, "Gestos: Paz (2 dedos) | Corazon (pulgares juntos)", 
                   (10, img.shape[0] - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(img, "Presiona 'q' para salir", 
                   (10, img.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Mostrar número de manos detectadas
        num_manos = len(detector.resultados.multi_hand_landmarks) if detector.resultados.multi_hand_landmarks else 0
        cv2.putText(img, f"Manos detectadas: {num_manos}", (10, 90), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        
        cv2.imshow("Detector de Gestos - Corazón y Paz", img)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()