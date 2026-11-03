import os
from pathlib import Path
import time
import pygame
import live2d.v3 as live2d
from frontend.Diseno.bonito import resources
import logging
from frontend.Diseno.bonito.control_personaje import CharacterController
from backend.configuracion_usuario import (
    PROJECT_ROOT,
    cargar_configuracion_personalizacion,
)

# Solo para Windows - requiere pywin32
try:
    import win32gui
    import win32con
    import win32api
    WINDOWS_AVAILABLE = True
except ImportError:
    WINDOWS_AVAILABLE = False

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def make_window_transparent(hwnd):
    """Hace la ventana transparente en Windows"""
    if WINDOWS_AVAILABLE:
        # Obtener el estilo extendido actual
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        # Agregar el flag de ventana en capas
        ex_style |= win32con.WS_EX_LAYERED | win32con.WS_EX_TOOLWINDOW
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, ex_style)
        # Establecer transparencia (0 = completamente transparente, 255 = opaco)
        # Para transparencia de color específico:
        win32gui.SetLayeredWindowAttributes(hwnd, 0x000000, 0, win32con.LWA_COLORKEY)

def make_window_always_on_top(hwnd):
    """Hace que la ventana permanezca siempre visible encima de otras"""
    if WINDOWS_AVAILABLE:
        win32gui.SetWindowPos(
            hwnd, 
            win32con.HWND_TOPMOST,  # Siempre encima
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )

def get_global_mouse_state():
    """Obtiene el estado global del mouse (funciona fuera de la ventana)"""
    if WINDOWS_AVAILABLE:
        try:
            # Verificar si el botón izquierdo está presionado globalmente
            left_button_state = win32api.GetKeyState(win32con.VK_LBUTTON)
            # Si el bit más significativo es 1, el botón está presionado
            # Usamos 0x8000 para verificar el bit más significativo
            is_pressed = (left_button_state < 0)  # Más confiable que checking bit
            return is_pressed
        except Exception as e:
            logging.warning(f"Error obteniendo estado global del mouse: {e}")
            return False
    else:
        # Fallback para sistemas no Windows
        return pygame.mouse.get_pressed()[0]

def main():
    character_controller = None
    try:
        pygame.init()
        live2d.init()
        display = (300, 400)

        flags = pygame.DOUBLEBUF | pygame.OPENGL | pygame.NOFRAME
        screen = pygame.display.set_mode(display, flags)
        pygame.display.set_caption("Live2D Transparent Assistant")

        # Obtener handle de la ventana para Windows
        hwnd = None
        if WINDOWS_AVAILABLE:
            hwnd = pygame.display.get_wm_info()["window"]
            make_window_transparent(hwnd)
            make_window_always_on_top(hwnd)

        live2d.glewInit()

        # Crear el modelo Live2D
        model = live2d.LAppModel()

        modelo_personaje = cargar_configuracion_personalizacion()["modelo_personaje"].strip()
        if modelo_personaje:
            model_path = Path(os.path.expandvars(os.path.expanduser(modelo_personaje)))
            if not model_path.is_absolute():
                model_path = PROJECT_ROOT / model_path
            if not model_path.is_file():
                raise FileNotFoundError(f"No se encontró el modelo Live2D: {model_path}")
            model.LoadModelJson(str(model_path))
        elif live2d.LIVE2D_VERSION == 3:
            model.LoadModelJson(
                os.path.join(resources.RESOURCES_DIRECTORY, "holograma_men/holograma_men.model3.json")
            )
        else:
            model.LoadModelJson(
                os.path.join(resources.RESOURCES_DIRECTORY, 
                            "holograma_women/holograma_women.model3.json")
            )

        model.Resize(*display)
        
        # Crear el controlador del personaje (ahora carga automáticamente la posición guardada)
        character_controller = CharacterController(model, display, hwnd)

        clock = pygame.time.Clock()
        running = True

        try:
            from backend.Generacion import from_TTS
            from_TTS.conectar_controlador_personaje(character_controller)
            logging.info("✅ Sistema TTS conectado con el controlador del personaje")
        except Exception as e:
            logging.warning(f"⚠️ No se pudo conectar TTS con el personaje: {e}")

        from backend import voz_estado
        ultima_senal_frontend = 0.0
        ultimo_ack_animacion = None
        
        # Variables para controlar el arrastre
        dragging = False
        drag_start_time = 0
        
        # Variable para rastrear si el mouse estaba sobre la ventana en el frame anterior
        mouse_was_over_window = character_controller.is_mouse_over_window()
        
        logging.info("Aplicación iniciada. El asistente seguirá tu mouse automáticamente.")
        
        while running:
            ahora = time.monotonic()
            if ahora - ultima_senal_frontend >= 1.0:
                try:
                    voz_estado.registrar_frontend_activo()
                except OSError:
                    logging.exception("No se pudo publicar el estado del frontend.")
                ultima_senal_frontend = ahora
            estado_voz = voz_estado.leer_estado_reproduccion()
            if estado_voz:
                playback_id = estado_voz["playback_id"]
                if estado_voz["phase"] == "playing":
                    ultimo_ack_animacion = None
                    configuracion_voz = cargar_configuracion_personalizacion()
                    animar_boca = (
                        estado_voz["animaciones"]
                        and configuracion_voz["habilitar_animaciones"]
                    )
                    character_controller.actualizar_animacion_voz(
                        animar_boca,
                        configuracion_voz["nivel_animacion"],
                    )
                elif ultimo_ack_animacion != playback_id:
                    character_controller.actualizar_animacion_voz(False)
                    try:
                        voz_estado.confirmar_animacion_finalizada(playback_id)
                        ultimo_ack_animacion = playback_id
                    except OSError:
                        logging.exception("No se pudo confirmar el cierre de la animación.")

            # Obtener el estado global del mouse (funciona fuera de la ventana)
            global_left_button_pressed = get_global_mouse_state()
            
            # Verificar si el mouse está sobre la ventana
            mouse_over_window = character_controller.is_mouse_over_window()
            
            # Procesar eventos de pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1 and mouse_over_window:  # Botón izquierdo y mouse sobre ventana
                        dragging = True
                        drag_start_time = pygame.time.get_ticks()
                        mouse_pos = pygame.mouse.get_pos()
                        character_controller.start_dragging(mouse_pos)
                        logging.info(f"Iniciando arrastre desde ventana en pos: {mouse_pos}")
                        
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:  # Botón izquierdo
                        if dragging:
                            dragging = False
                            character_controller.stop_dragging()
                            logging.info("Arrastre detenido por mouse up")
                    else:
                        if (
                            mouse_over_window
                            and cargar_configuracion_personalizacion()["habilitar_animaciones"]
                        ):
                            model.SetRandomExpression()
                            model.StartRandomMotion()
                            logging.info("Expresión y movimiento aleatorio activados")
                        
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                
                # Permitir que el controlador maneje eventos específicos
                character_controller.handle_pygame_event(event)

            # Detectar inicio de arrastre desde fuera de la ventana
            current_time = pygame.time.get_ticks()
            if not dragging and global_left_button_pressed and mouse_over_window:
                # El mouse está en la ventana y el botón está presionado
                dragging = True
                drag_start_time = current_time
                mouse_pos = pygame.mouse.get_pos()
                character_controller.start_dragging(mouse_pos)
                logging.info(f"Iniciando arrastre global en pos: {mouse_pos}")

            # Verificar consistencia del estado de arrastre con un pequeño delay
            if dragging and not global_left_button_pressed and (current_time - drag_start_time) > 100:
                # El botón se soltó globalmente (con delay de 100ms para evitar falsos positivos)
                dragging = False
                character_controller.stop_dragging()
                logging.info("Arrastre detenido por verificación global de estado")

            # Actualizar el controlador del personaje
            # Ahora usa el estado global del mouse y detecta automáticamente la posición
            character_controller.update(dragging)

            # Actualizar estado del mouse para el próximo frame
            mouse_was_over_window = mouse_over_window

            # Limpiar con color negro (se volverá transparente)
            live2d.clearBuffer()
            
            model.Update()
            model.Draw()

            pygame.display.flip()
            clock.tick(60)
            
    except Exception as e:
        logging.error(f"Error en el bucle principal: {e}")
    finally:
        try:
            # Asegurar que se guarde la posición antes de cerrar
            if character_controller:
                character_controller.cleanup()
            live2d.dispose()
        except Exception as e:
            logging.warning(f"Error en cleanup: {e}")
        pygame.quit()
        logging.info("Aplicación finalizada correctamente.")


if __name__ == "__main__":
    main()