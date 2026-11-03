import os
import cv2
import threading
from queue import Queue
from contextlib import contextmanager

from backend.FuncionesVisuales.face.database.config import DataBasePaths
from backend.FuncionesVisuales.face.face_processing.face_signup import FaceSignUp
from backend.FuncionesVisuales.face.face_processing.face_login import FaceLogIn


class CameraManager:
    """Administrador de cámara con optimizaciones de recursos"""
    
    def __init__(self):
        self.cap = None
        self.is_running = False
        self.frame_queue = Queue(maxsize=2)  # Buffer pequeño para evitar acumulación
        self.current_frame = None
        self.capture_thread = None
        self._lock = threading.Lock()
        
    def start_camera(self):
        """Inicia la cámara de forma optimizada"""
        if self.cap is None:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise Exception("No se pudo abrir la cámara")
            
            # Configuración optimizada (compatible con diferentes versiones de OpenCV)
            self.cap.set(3, 1280)  # WIDTH
            self.cap.set(4, 720)   # HEIGHT
            self.cap.set(5, 30)    # FPS
            
            # Intenta configurar buffer size si está disponible
            try:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except AttributeError:
                # Para versiones más antiguas de OpenCV
                pass
            
    def stop_camera(self):
        """Detiene la cámara y libera recursos"""
        self.is_running = False
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
            
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()
        
    def get_frame(self):
        """Obtiene el frame actual de forma thread-safe"""
        with self._lock:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    return frame
        return None
    
    @contextmanager
    def camera_context(self):
        """Context manager para manejo seguro de la cámara"""
        try:
            self.start_camera()
            yield self
        finally:
            self.stop_camera()


class FaceSystemCore:
    """Núcleo del sistema de reconocimiento facial"""
    
    def __init__(self):
        self.database = DataBasePaths()
        self.face_sign_up = FaceSignUp()
        self.face_login = FaceLogIn()
        self.camera_manager = CameraManager()
        self._user_cache = {}
        self._load_user_cache()
        
    def _load_user_cache(self):
        """Carga los usuarios en caché para evitar acceso repetido al disco"""
        try:
            if os.path.exists(self.database.check_users):
                user_files = os.listdir(self.database.check_users)
                for user_file in user_files:
                    if user_file.endswith('.txt'):
                        user_code = user_file.split('.')[0]
                        self._user_cache[user_code] = True
        except Exception as e:
            print(f"Error cargando caché de usuarios: {e}")
    
    def validate_user_data(self, name, user_code):
        """Valida los datos del usuario"""
        if not name or not user_code:
            return False, "Formulario incompleto"
        
        if len(name.strip()) == 0 or len(user_code.strip()) == 0:
            return False, "Formulario incompleto"
        
        if user_code in self._user_cache:
            return False, "Usuario previamente registrado"
        
        return True, "Datos válidos"
    
    def save_user_data(self, name, user_code):
        """Guarda los datos del usuario de forma optimizada"""
        try:
            user_file_path = f"{self.database.users}/{user_code}.txt"
            with open(user_file_path, 'w', encoding='utf-8') as file:
                file.write(f"{name},{user_code},")
            
            # Actualiza el caché
            self._user_cache[user_code] = True
            return True
        except Exception as e:
            print(f"Error guardando usuario: {e}")
            return False
    
    def process_signup_frame(self, frame, user_code):
        """Procesa frame para registro facial"""
        if frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return self.face_sign_up.process(frame_rgb, user_code)
        return None, False, "Sin frame"
    
    def process_login_frame(self, frame):
        """Procesa frame para login facial"""
        if frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return self.face_login.process(frame_rgb)
        return None, None, "Sin frame"
    
    def cleanup_signup(self):
        """Limpia recursos del registro"""
        self.face_sign_up.__init__()
        
    def cleanup_login(self):
        """Limpia recursos del login"""
        self.face_login.__init__()
    
    def get_camera_manager(self):
        """Devuelve el administrador de cámara"""
        return self.camera_manager


class ResourceOptimizer:
    """Optimizador de recursos del sistema"""
    
    @staticmethod
    def optimize_frame_processing():
        """Configuraciones para optimizar el procesamiento de frames"""
        # Configura OpenCV para usar menos threads
        cv2.setNumThreads(2)
        
        # Configura el uso de CPU de forma más eficiente
        cv2.setUseOptimized(True)
    
    @staticmethod
    def cleanup_opencv_resources():
        """Limpia recursos de OpenCV"""
        cv2.destroyAllWindows()
    
    @staticmethod
    def monitor_memory_usage():
        """Monitorea el uso de memoria (opcional)"""
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        print(f"Uso de memoria: {memory_info.rss / 1024 / 1024:.2f} MB")


# Inicialización del optimizador
ResourceOptimizer.optimize_frame_processing()