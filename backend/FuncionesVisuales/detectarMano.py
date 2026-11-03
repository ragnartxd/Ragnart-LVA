# no esta implementado
import cv2
import mediapipe as mp
import math

class detectormanos():
    def __init__(self, mode=False, maxHands=2, modelComplexity=1, detectionCon=0.5, trackCon=0.5):
        self.mode = mode
        self.maxHands = maxHands
        self.modelComplexity = modelComplexity
        self.detectionCon = detectionCon
        self.trackCon = trackCon

        self.mpHands = mp.solutions.hands
        self.hands = self.mpHands.Hands(self.mode, self.maxHands, self.modelComplexity, self.detectionCon, self.trackCon)
        self.mpDraw = mp.solutions.drawing_utils
        self.tip = [4, 8, 12, 16, 20]  # Índices de las puntas de los dedos

    def encontrarManos(self, img, draw=True):
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.resultados = self.hands.process(imgRGB)

        if self.resultados.multi_hand_landmarks:
            for manoLms in self.resultados.multi_hand_landmarks:
                if draw:
                    self.mpDraw.draw_landmarks(img, manoLms, self.mpHands.HAND_CONNECTIONS)
        return img

    def encontrarPosicion(self, img, manoN=0, draw=True):
        xList = []
        yList = []
        bbox = []
        self.lmList = []

        if self.resultados.multi_hand_landmarks:
            mano = self.resultados.multi_hand_landmarks[manoN]
            for id, lm in enumerate(mano.landmark):
                h, w, c = img.shape
                cx, cy = int(lm.x * w), int(lm.y * h)
                xList.append(cx)
                yList.append(cy)
                self.lmList.append([id, cx, cy])
                if draw:
                    cv2.circle(img, (cx, cy), 5, (255, 0, 255), cv2.FILLED)

            xMin, xMax = min(xList), max(xList)
            yMin, yMax = min(yList), max(yList)
            bbox = xMin, yMin, xMax - xMin, yMax - yMin

            if draw:
                cv2.rectangle(img, (xMin - 20, yMin - 20), (xMax + 20, yMax + 20), (0, 255, 0), 2)

        return self.lmList, bbox
    
    def dedosArriba(self, img, manoN=0):
        dedos = []
        if self.lmList and self.resultados.multi_handedness:
            # Determinar si es mano derecha o izquierda
            handedness = self.resultados.multi_handedness[manoN].classification[0].label
            
            # PULGAR - Lógica mejorada
            # Usamos la distancia entre el pulgar y el centro de la mano para determinar si está extendido
            centro_mano_x = self.lmList[9][1]  # Punto 9 es el centro de la mano
            pulgar_tip_x = self.lmList[4][1]   # Punta del pulgar
            pulgar_mcp_x = self.lmList[2][1]   # Base del pulgar
            
            # Calculamos si el pulgar está extendido basado en la distancia al centro
            if handedness == 'Right':
                # Para mano derecha: pulgar extendido está más a la izquierda del centro
                pulgar_extendido = pulgar_tip_x < centro_mano_x - 30
            else:
                # Para mano izquierda: pulgar extendido está más a la derecha del centro
                pulgar_extendido = pulgar_tip_x > centro_mano_x + 30
            
            # Verificación adicional: el pulgar debe estar más lejos de la base que el punto medio
            distancia_tip = math.hypot(pulgar_tip_x - centro_mano_x, self.lmList[4][2] - self.lmList[9][2])
            distancia_mcp = math.hypot(pulgar_mcp_x - centro_mano_x, self.lmList[2][2] - self.lmList[9][2])
            
            if pulgar_extendido and distancia_tip > distancia_mcp * 1.2:
                dedos.append(1)
            else:
                dedos.append(0)

            # ÍNDICE - Comparar punta con articulación
            if self.lmList[8][2] < self.lmList[6][2]:
                dedos.append(1)
            else:
                dedos.append(0)

            # MEDIO - Comparar punta con articulación
            if self.lmList[12][2] < self.lmList[10][2]:
                dedos.append(1)
            else:
                dedos.append(0)

            # ANULAR - Comparar punta con articulación
            if self.lmList[16][2] < self.lmList[14][2]:
                dedos.append(1)
            else:
                dedos.append(0)

            # MEÑIQUE - Comparar punta con articulación
            if self.lmList[20][2] < self.lmList[18][2]:
                dedos.append(1)
            else:
                dedos.append(0)

        return dedos
    
    def distancia(self, p1, p2, img, draw=True):
        x1, y1 = self.lmList[p1][1], self.lmList[p1][2]
        x2, y2 = self.lmList[p2][1], self.lmList[p2][2]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

        if draw:
            cv2.line(img, (x1, y1), (x2, y2), (255, 0, 255), 3)
            cv2.circle(img, (x1, y1), 5, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (x2, y2), 5, (255, 0, 255), cv2.FILLED)
            cv2.circle(img, (cx, cy), 5, (0, 255, 0), cv2.FILLED)

        distancia = math.hypot(x2 - x1, y2 - y1)
        # Retornar la distancia, el punto medio y la imagen modificada
        return distancia, (cx, cy), img
    
def main():
    cap = cv2.VideoCapture(0)
    detector = detectormanos()

    while True:
        success, img = cap.read()
        img = cv2.flip(img, 1)  # Voltear imagen horizontalmente
        img = detector.encontrarManos(img)
        lmList, bbox = detector.encontrarPosicion(img)

        if lmList:
            dedos = detector.dedosArriba(img)
            cv2.putText(img, f"Dedos: {dedos}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        cv2.imshow("Image", img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()