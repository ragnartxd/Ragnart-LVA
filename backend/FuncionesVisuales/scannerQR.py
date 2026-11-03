# No esta implementado
import os
import cv2
import numpy as np
import time
import logging
from typing import Optional, Tuple
import sys
import webbrowser

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QRScanner:
    def __init__(self, camera_index: int = 0, resolution: Tuple[int, int] = (640, 480)):
        """
        Inicializa el escáner de códigos QR.
        
        Args:
            camera_index: Índice de la cámara (0 para cámara predeterminada)
            resolution: Resolución de captura (ancho, alto)
        """
        self.camera_index = camera_index
        self.resolution = resolution
        self.cap = None
        self.detector = cv2.QRCodeDetector()
        self.last_qr_code = ""
        self.last_detection_time = 0
        self.debounce_time = 2.0  # Segundos antes de detectar el mismo código QR
        
    def initialize_camera(self) -> bool:
        """
        Inicializa la cámara con configuraciones optimizadas.
        
        Returns:
            bool: True si la cámara se inicializó correctamente
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap.isOpened():
                logger.error(f"No se pudo abrir la cámara {self.camera_index}")
                return False
                
            # Configurar resolución
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            
            # Configuraciones optimizadas
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reducir buffer para menor latencia
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Exposición automática

            # Verificar que la cámara funciona
            ret, frame = self.cap.read()
            if not ret:
                logger.error("No se pudo capturar frame de la cámara")
                return False
                
            logger.info(f"Cámara inicializada - Resolución: {self.resolution}")
            return True
            
        except Exception as e:
            logger.error(f"Error al inicializar la cámara: {e}")
            return False
    
    def preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocesa el frame para mejorar la detección de códigos QR.
        
        Args:
            frame: Frame de entrada
            
        Returns:
            np.ndarray: Frame procesado
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Aplicar ecualización de histograma adaptativa para mejorar contraste
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Aplicar filtro gaussiano para reducir ruido
        blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
        
        return blurred
    
    def detect_qr_code(self, frame: np.ndarray) -> Tuple[Optional[str], Optional[np.ndarray]]:
        """
        Detecta y decodifica códigos QR en el frame.
        
        Args:
            frame: Frame de entrada
            
        Returns:
            Tuple[str, np.ndarray]: Datos del QR y puntos de detección
        """
        try:
            # Procesar frame original
            data, points, _ = self.detector.detectAndDecode(frame)
            
            # Si no se detecta nada, probar con frame preprocesado
            if not data:
                processed_frame = self.preprocess_frame(frame)
                data, points, _ = self.detector.detectAndDecode(processed_frame)
            
            return data if data else None, points
            
        except Exception as e:
            logger.error(f"Error en detección de QR: {e}")
            return None, None
    
    def should_process_qr(self, qr_data: str) -> bool:
        """
        Determina si se debe procesar el código QR basado en debounce.
        
        Args:
            qr_data: Datos del código QR
            
        Returns:
            bool: True si se debe procesar
        """
        current_time = time.time()
        
        if (qr_data != self.last_qr_code or 
            current_time - self.last_detection_time > self.debounce_time):
            self.last_qr_code = qr_data
            self.last_detection_time = current_time
            return True
        
        return False
    
    def draw_qr_detection(self, frame: np.ndarray, points: np.ndarray, qr_data: str) -> np.ndarray:
        """
        Dibuja la detección del código QR en el frame.
        
        Args:
            frame: Frame de entrada
            points: Puntos de detección del QR
            qr_data: Datos del código QR
            
        Returns:
            np.ndarray: Frame con la detección dibujada
        """
        if points is not None:
            # Dibujar contorno del QR
            points = points.astype(int)
            cv2.polylines(frame, [points], True, (0, 255, 0), 3)
            
            # Calcular centro para el texto
            center = tuple(np.mean(points, axis=0).astype(int))
            
            # Dibujar texto con fondo
            text = f"QR: {qr_data[:30]}..." if len(qr_data) > 30 else f"QR: {qr_data}"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            
            # Obtener tamaño del texto
            (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
            
            # Dibujar rectángulo de fondo
            cv2.rectangle(frame, 
                         (center[0] - text_width // 2 - 5, center[1] - text_height - 10),
                         (center[0] + text_width // 2 + 5, center[1] + 5),
                         (0, 0, 0), -1)
            
            # Dibujar texto
            cv2.putText(frame, text, 
                       (center[0] - text_width // 2, center[1] - 5),
                       font, font_scale, (255, 255, 255), thickness)
        
        return frame
    
    def add_ui_elements(self, frame: np.ndarray) -> np.ndarray:
        """
        Añade elementos de interfaz al frame.
        
        Args:
            frame: Frame de entrada
            
        Returns:
            np.ndarray: Frame con elementos UI
        """
        # Información en la esquina superior
        info_text = "Presiona 'q' para salir, 'r' para reiniciar"
        cv2.putText(frame, info_text, (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Líneas de ayuda para centrar QR
        height, width = frame.shape[:2]
        center_x, center_y = width // 2, height // 2
        
        # Cruz central
        cv2.line(frame, (center_x - 20, center_y), (center_x + 20, center_y), (0, 255, 255), 1)
        cv2.line(frame, (center_x, center_y - 20), (center_x, center_y + 20), (0, 255, 255), 1)
        
        # Rectángulo de guía
        rect_size = 150
        cv2.rectangle(frame, 
                     (center_x - rect_size, center_y - rect_size),
                     (center_x + rect_size, center_y + rect_size),
                     (0, 255, 255), 1)
        
        return frame
    
    def run(self):
        """
        Ejecuta el bucle principal del escáner.
        """
        if not self.initialize_camera():
            logger.error("No se pudo inicializar la cámara")
            return

        logger.info("Escáner de códigos QR iniciado. Presiona 'q' para salir.")
        
        try:
            while True:
                ret, frame = self.cap.read()
                
                if not ret:
                    logger.error("No se pudo capturar frame")
                    break
                
                frame = cv2.flip(frame, 1)  # Eliminar modo espejo si es necesario
                # Detectar códigos QR
                qr_data, points = self.detect_qr_code(frame)
                
                if qr_data and self.should_process_qr(qr_data):
                    logger.info(f"Código QR detectado: {qr_data}")
                    print(f"\n🎯 QR DETECTADO: {qr_data}\n")
                    # Si es una URL, abrir en el navegador
                    if qr_data.startswith("http://") or qr_data.startswith("https://"):
                        webbrowser.open(qr_data)
                    # Si quieres abrir archivos locales, puedes usar:
                    elif os.path.exists(qr_data):
                        os.startfile(qr_data)
                
                # Dibujar detección si existe
                if qr_data and points is not None:
                    frame = self.draw_qr_detection(frame, points, qr_data)
                
                # Añadir elementos UI
                frame = self.add_ui_elements(frame)
                
                # Mostrar frame
                cv2.imshow('Escáner de Códigos QR', frame)
                
                # Manejar teclas
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    logger.info("Reiniciando escáner...")
                    self.last_qr_code = ""
                    self.last_detection_time = 0
                    
        except KeyboardInterrupt:
            logger.info("Interrupción del usuario")
        except Exception as e:
            logger.error(f"Error en el bucle principal: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """
        Limpia recursos.
        """
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()
        logger.info("Recursos liberados")

def main():
    """
    Función principal.
    """
    try:
        # Crear y ejecutar el escáner
        scanner = QRScanner(camera_index=0, resolution=(640, 480))
        scanner.run()
        
    except Exception as e:
        logger.error(f"Error en main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()