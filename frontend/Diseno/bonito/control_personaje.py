import threading
import pygame
import logging
import json
import os
from live2d.v3 import StandardParams
import random


# Solo para Windows - requiere pywin32
try:
    import win32gui
    import win32con
    import win32api
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False

class WindowPositionManager:
    """Maneja el guardado y carga de la posición de la ventana"""

    def __init__(self, config_file="frontend/Diseno/bonito/window_position.json"):
        self.config_file = config_file
        self.default_position = (100, 100)  # Posición por defecto
    
    def save_position(self, x, y):
        """Guarda la posición actual de la ventana"""
        try:
            config = {"x": x, "y": y}
            with open(self.config_file, 'w') as f:
                json.dump(config, f)
            logging.info(f"Posición guardada: ({x}, {y})")
        except Exception as e:
            logging.warning(f"Error guardando posición: {e}")
    
    def load_position(self):
        """Carga la posición guardada de la ventana"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    x, y = config.get("x", self.default_position[0]), config.get("y", self.default_position[1])
                    logging.info(f"Posición cargada: ({x}, {y})")
                    return (x, y)
        except Exception as e:
            logging.warning(f"Error cargando posición: {e}")
        
        logging.info(f"Usando posición por defecto: {self.default_position}")
        return self.default_position

class CharacterController:
    def __init__(self, model, display_size, window_handle=None):
        """
        Inicializa el controlador del personaje.
        
        Args:
            model: El modelo Live2D
            display_size: Tupla con el tamaño de la ventana (ancho, alto)
            window_handle: Handle de la ventana (para Windows)
        """
        self.model = model
        self.display_size = display_size
        self.window_handle = window_handle
        
        # Variables para el seguimiento de ojos
        self.eye_follow_enabled = True
        self.eye_smoothing = 0.1  # Factor de suavizado para el movimiento de ojos
        self.current_eye_x = 0.0
        self.current_eye_y = 0.0
        self._voice_animation_time = 0.0
        
        # Variables para el arrastre de ventana
        self.is_dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Gestor de posición de ventana
        self.position_manager = WindowPositionManager()
        
        # Variables para el seguimiento global del mouse
        self.last_global_mouse_pos = (0, 0)
        
        # Configuración inicial del modelo
        self.setup_model()
        
        # Cargar y aplicar la posición guardada
        self.load_and_apply_saved_position()
        
        logging.info("CharacterController inicializado")
    
    def setup_model(self):
        """Configuración inicial del modelo"""
        # Desactivar parpadeo automático para control manual
        self.model.SetAutoBlinkEnable(False)
        
        # Abrir los ojos inicialmente
        self.model.SetParameterValue(StandardParams.ParamEyeLOpen, 1.0)
        self.model.SetParameterValue(StandardParams.ParamEyeROpen, 1.0)
        
        logging.info("Modelo configurado")
    
    def load_and_apply_saved_position(self):
        """Carga y aplica la posición guardada de la ventana"""
        if WINDOWS_AVAILABLE and self.window_handle:
            try:
                saved_x, saved_y = self.position_manager.load_position()
                
                # Verificar que la posición esté dentro de los límites de la pantalla
                screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                
                # Asegurar que la ventana esté visible
                if saved_x < -self.display_size[0] + 50:  # Al menos 50px visibles
                    saved_x = 0
                if saved_y < 0:
                    saved_y = 0
                if saved_x > screen_width - 50:
                    saved_x = screen_width - self.display_size[0]
                if saved_y > screen_height - 50:
                    saved_y = screen_height - self.display_size[1]
                
                # Aplicar la posición
                win32gui.SetWindowPos(
                    self.window_handle, 
                    None, 
                    saved_x, 
                    saved_y, 
                    0, 
                    0,
                    win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                )
                
                logging.info(f"Posición aplicada: ({saved_x}, {saved_y})")
            except Exception as e:
                logging.warning(f"Error aplicando posición guardada: {e}")
    
    def save_current_position(self):
        """Guarda la posición actual de la ventana"""
        if WINDOWS_AVAILABLE and self.window_handle:
            try:
                rect = win32gui.GetWindowRect(self.window_handle)
                window_x, window_y = rect[0], rect[1]
                self.position_manager.save_position(window_x, window_y)
            except Exception as e:
                logging.warning(f"Error guardando posición actual: {e}")
    
    def get_global_mouse_position(self):
        """Obtiene la posición global del mouse (en toda la pantalla)"""
        if WINDOWS_AVAILABLE:
            try:
                return win32gui.GetCursorPos()
            except Exception as e:
                logging.warning(f"Error obteniendo posición global del mouse: {e}")
                return self.last_global_mouse_pos
        else:
            # Fallback para sistemas no Windows
            return pygame.mouse.get_pos()
    
    def global_to_window_coordinates(self, global_pos):
        """Convierte coordenadas globales a coordenadas de ventana"""
        if WINDOWS_AVAILABLE and self.window_handle:
            try:
                rect = win32gui.GetWindowRect(self.window_handle)
                window_x, window_y = rect[0], rect[1]
                
                # Convertir coordenadas globales a coordenadas de ventana
                local_x = global_pos[0] - window_x
                local_y = global_pos[1] - window_y
                
                return (local_x, local_y)
            except Exception as e:
                logging.warning(f"Error convirtiendo coordenadas: {e}")
                return global_pos
        else:
            return global_pos
    
    def start_dragging(self, mouse_pos):
        """Inicia el arrastre de la ventana"""
        if WINDOWS_AVAILABLE and self.window_handle:
            self.is_dragging = True
            try:
                rect = win32gui.GetWindowRect(self.window_handle)
                window_x, window_y = rect[0], rect[1]
                
                # Obtener posición global del mouse
                global_mouse_pos = self.get_global_mouse_position()
                
                # Calcular el offset del mouse respecto a la esquina de la ventana
                self.drag_offset_x = global_mouse_pos[0] - window_x
                self.drag_offset_y = global_mouse_pos[1] - window_y
                
                logging.info(f"Iniciando arrastre - Offset: ({self.drag_offset_x}, {self.drag_offset_y})")
            except Exception as e:
                logging.warning(f"Error al iniciar arrastre: {e}")
                self.is_dragging = False
    
    def stop_dragging(self):
        """Detiene el arrastre de la ventana"""
        if self.is_dragging:
            self.is_dragging = False
            # Guardar la posición actual cuando se deja de arrastrar
            self.save_current_position()
            logging.info("Arrastre detenido y posición guardada")
    
    def update_window_position(self):
        """Actualiza la posición de la ventana basada en el mouse global"""
        if not (WINDOWS_AVAILABLE and self.window_handle and self.is_dragging):
            return
        
        try:
            # Obtener la posición actual del cursor en coordenadas globales
            global_mouse_pos = self.get_global_mouse_position()
            
            # Calcular la nueva posición de la ventana
            new_x = global_mouse_pos[0] - self.drag_offset_x
            new_y = global_mouse_pos[1] - self.drag_offset_y
            
            # Mover la ventana
            win32gui.SetWindowPos(
                self.window_handle, 
                None, 
                new_x, 
                new_y, 
                0, 
                0,
                win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
            )
        except Exception as e:
            logging.warning(f"Error moviendo ventana: {e}")
    
    def update_eye_tracking(self):
        """Actualiza el seguimiento de ojos basado en la posición global del mouse"""
        if not self.eye_follow_enabled:
            return
        
        # Obtener posición global del mouse
        global_mouse_pos = self.get_global_mouse_position()
        self.last_global_mouse_pos = global_mouse_pos
        
        # Convertir a coordenadas de ventana
        window_mouse_pos = self.global_to_window_coordinates(global_mouse_pos)
        
        # Obtener el centro de la ventana
        center_x = self.display_size[0] / 2
        center_y = self.display_size[1] / 2
        
        # Calcular la diferencia desde el centro
        diff_x = window_mouse_pos[0] - center_x
        diff_y = window_mouse_pos[1] - center_y
        
        # Normalizar las coordenadas (-1.0 a 1.0)
        # Ajustar la sensibilidad dividiendo por una fracción del tamaño de pantalla
        max_distance_x = self.display_size[0] * 0.8  # 80% del ancho para mayor rango
        max_distance_y = self.display_size[1] * 0.8  # 80% del alto para mayor rango
        
        target_eye_x = max(-1.0, min(1.0, diff_x / max_distance_x))
        target_eye_y = max(-1.0, min(1.0, -diff_y / max_distance_y))  # Invertir Y
        
        # Aplicar suavizado para movimientos más naturales
        self.current_eye_x += (target_eye_x - self.current_eye_x) * self.eye_smoothing
        self.current_eye_y += (target_eye_y - self.current_eye_y) * self.eye_smoothing
        
        # Aplicar los valores al modelo
        try:
            # Movimiento horizontal de los ojos
            self.model.SetParameterValue(StandardParams.ParamEyeBallX, self.current_eye_x)
            
            # Movimiento vertical de los ojos
            self.model.SetParameterValue(StandardParams.ParamEyeBallY, self.current_eye_y)
            
            # También aplicar un ligero movimiento de cabeza para mayor realismo
            head_x = self.current_eye_x * 0.3  # Movimiento más sutil para la cabeza
            head_y = self.current_eye_y * 0.2
            
            self.model.SetParameterValue(StandardParams.ParamAngleX, head_x * 10)  # Ajustar escala
            self.model.SetParameterValue(StandardParams.ParamAngleY, head_y * 5)
            
        except Exception as e:
            logging.warning(f"Error actualizando seguimiento de ojos: {e}")
    
    def update_blinking(self):
        """Actualiza el parpadeo natural del personaje"""
        # Implementar parpadeo ocasional
        if random.random() < 0.003:  # 0.2% de probabilidad por frame (a 60fps = ~8 segundos promedio)
            self.blink()
    
    def blink(self):
        """Ejecuta un parpadeo"""
        try:
            # Cerrar ojos brevemente
            self.model.SetParameterValue(StandardParams.ParamEyeLOpen, 0.0)
            self.model.SetParameterValue(StandardParams.ParamEyeROpen, 0.0)
            
            # En el próximo frame se abrirán automáticamente
            pygame.time.set_timer(pygame.USEREVENT + 1, 100)  # 100ms después
        except Exception as e:
            logging.warning(f"Error en parpadeo: {e}")
    
    def open_eyes(self):
        """Abre los ojos del personaje"""
        try:
            self.model.SetParameterValue(StandardParams.ParamEyeLOpen, 1.0)
            self.model.SetParameterValue(StandardParams.ParamEyeROpen, 1.0)
        except Exception as e:
            logging.warning(f"Error abriendo ojos: {e}")
    
    def set_eye_follow_enabled(self, enabled):
        """Habilita o deshabilita el seguimiento de ojos"""
        self.eye_follow_enabled = enabled
        logging.info(f"Seguimiento de ojos: {'habilitado' if enabled else 'deshabilitado'}")
    
    def set_eye_smoothing(self, smoothing):
        """Ajusta el factor de suavizado del movimiento de ojos"""
        self.eye_smoothing = max(0.01, min(1.0, smoothing))  # Limitar entre 0.01 y 1.0
        logging.info(f"Suavizado de ojos ajustado a: {self.eye_smoothing}")
    
    def is_mouse_over_window(self):
        """Verifica si el mouse está sobre la ventana"""
        if WINDOWS_AVAILABLE and self.window_handle:
            try:
                global_mouse_pos = self.get_global_mouse_position()
                window_mouse_pos = self.global_to_window_coordinates(global_mouse_pos)
                
                # Verificar si está dentro de los límites de la ventana
                return (0 <= window_mouse_pos[0] <= self.display_size[0] and 
                        0 <= window_mouse_pos[1] <= self.display_size[1])
            except:
                return False
        else:
            # Fallback para sistemas no Windows
            mouse_pos = pygame.mouse.get_pos()
            return (0 <= mouse_pos[0] <= self.display_size[0] and 
                    0 <= mouse_pos[1] <= self.display_size[1])
    
    def update(self, mouse_pressed):
        """
        Actualización principal del controlador.
        
        Args:
            mouse_pressed: Si el botón izquierdo del mouse está presionado
        """
        # Actualizar seguimiento de ojos (ahora usa posición global)
        self.update_eye_tracking()
        
        # Actualizar parpadeo natural
        self.update_blinking()
        
        # Actualizar posición de ventana si se está arrastrando
        if mouse_pressed and self.is_dragging:
            self.update_window_position()
        elif not mouse_pressed and self.is_dragging:
            # Si se soltó el mouse, detener el arrastre
            self.stop_dragging()
    
    def handle_pygame_event(self, event):
        """Maneja eventos específicos de pygame"""
        if event.type == pygame.USEREVENT + 1:
            # Evento para abrir ojos después del parpadeo
            self.open_eyes()
            pygame.time.set_timer(pygame.USEREVENT + 1, 0)  # Cancelar el timer
    
    def cleanup(self):
        """Limpieza al cerrar la aplicación"""
        # Guardar la posición actual antes de cerrar
        self.save_current_position()
        logging.info("Limpieza del controlador completada")

    def mov_mouth(self, detener_evento=None):
        """Mueve la boca mientras el TTS esté reproduciendo audio."""
        import time
        from backend.configuracion_usuario import cargar_configuracion_personalizacion

        from backend.Generacion import from_TTS

        movement_count = 0
        try:
            logging.info("👄 Iniciando animación de boca")
            while (
                from_TTS.async_tts_manager.is_playing.is_set()
                and not (detener_evento and detener_evento.is_set())
            ):
                nivel = max(
                    0,
                    min(100, cargar_configuracion_personalizacion()["nivel_animacion"]),
                ) / 50
                self.model.SetParameterValue(
                    StandardParams.ParamMouthOpenY,
                    min(1.0, random.uniform(0.3, 0.8) * nivel),
                )
                time.sleep(random.uniform(0.10, 0.20))
                self.model.SetParameterValue(
                    StandardParams.ParamMouthOpenY,
                    min(1.0, random.uniform(0.0, 0.2) * nivel),
                )
                time.sleep(random.uniform(0.10, 0.20))
                movement_count += 1
        except Exception as e:
            logging.error(f"❌ Error moviendo la boca: {e}")
        finally:
            self.model.SetParameterValue(StandardParams.ParamMouthOpenY, 0.0)
            logging.info(f"👄 Animación de boca finalizada ({movement_count} movimientos)")

    def actualizar_animacion_voz(self, activa, nivel=50):
        """Actualiza la boca desde el hilo principal del renderizado."""
        import math
        import time

        if not activa:
            self.model.SetParameterValue(StandardParams.ParamMouthOpenY, 0.0)
            self._voice_animation_time = 0.0
            return

        if not self._voice_animation_time:
            self._voice_animation_time = time.monotonic()
        intensidad = max(0, min(100, nivel)) / 100
        fase = (time.monotonic() - self._voice_animation_time) * 11
        apertura = (0.12 + 0.78 * abs(math.sin(fase))) * intensidad
        self.model.SetParameterValue(StandardParams.ParamMouthOpenY, apertura)