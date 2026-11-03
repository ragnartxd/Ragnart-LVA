import tkinter as tk
from tkinter import *
import imutils
from PIL import Image, ImageTk
import threading
import time

from backend.FuncionesVisuales.face.gui.image_paths import ImagePaths
from backend.FuncionesVisuales.face.core_functionality import FaceSystemCore, ResourceOptimizer


class OptimizedVideoLabel(Label):
    """Label optimizado para mostrar video"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.current_image = None
        self.update_id = None
        
    def update_frame(self, frame):
        """Actualiza el frame de forma optimizada"""
        if frame is not None:
            try:
                # Redimensiona de forma eficiente
                frame_resized = imutils.resize(frame, width=1280)
                im = Image.fromarray(frame_resized)
                
                # Libera la imagen anterior
                if self.current_image:
                    del self.current_image
                
                self.current_image = ImageTk.PhotoImage(image=im)
                self.configure(image=self.current_image)
                self.image = self.current_image
            except Exception as e:
                print(f"Error actualizando frame: {e}")
    
    def cleanup(self):
        """Limpia recursos del video label"""
        if self.update_id:
            self.after_cancel(self.update_id)
            self.update_id = None
        if self.current_image:
            del self.current_image
            self.current_image = None


class CustomFrame(tk.Frame):
    """Frame personalizado optimizado"""
    
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.pack(fill=tk.BOTH, expand=True)


class FaceSignUpWindow:
    """Ventana de registro facial optimizada"""
    
    def __init__(self, parent, core_system, user_code, on_complete):
        self.parent = parent
        self.core_system = core_system
        self.user_code = user_code
        self.on_complete = on_complete
        self.is_running = False
        self.window = None
        self.video_label = None
        
    def create_window(self):
        """Crea la ventana de registro"""
        self.window = Toplevel(self.parent)
        self.window.title('Face Capture')
        self.window.geometry('1280x720')
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        
        self.video_label = OptimizedVideoLabel(self.window)
        self.video_label.place(x=0, y=0)
        
        self.is_running = True
        self.start_capture()
        
    def start_capture(self):
        """Inicia la captura de video"""
        def capture_loop():
            with self.core_system.get_camera_manager().camera_context():
                while self.is_running and self.window and self.window.winfo_exists():
                    try:
                        frame = self.core_system.get_camera_manager().get_frame()
                        if frame is not None:
                            processed_frame, save_image, info = self.core_system.process_signup_frame(frame, self.user_code)
                            
                            if processed_frame is not None:
                                self.video_label.update_frame(processed_frame)
                            
                            if save_image:
                                self.window.after(3000, self.close_window)
                                break
                        
                        time.sleep(0.033)  # ~30 FPS
                        
                    except Exception as e:
                        print(f"Error en captura: {e}")
                        break
        
        # Ejecuta en thread separado para no bloquear la GUI
        capture_thread = threading.Thread(target=capture_loop, daemon=True)
        capture_thread.start()
        
    def close_window(self):
        """Cierra la ventana y libera recursos"""
        self.is_running = False
        
        if self.video_label:
            self.video_label.cleanup()
        
        self.core_system.cleanup_signup()
        
        if self.window:
            self.window.destroy()
        
        if self.on_complete:
            self.on_complete()


class FaceLoginWindow:
    """Ventana de login facial optimizada"""
    
    def __init__(self, parent, core_system, on_complete):
        self.parent = parent
        self.core_system = core_system
        self.on_complete = on_complete
        self.is_running = False
        self.window = None
        self.video_label = None
        
    def create_window(self):
        """Crea la ventana de login"""
        self.window = Toplevel(self.parent)
        self.window.title('Face Login')
        self.window.geometry('1280x720')
        self.window.protocol("WM_DELETE_WINDOW", self.close_window)
        
        self.video_label = OptimizedVideoLabel(self.window)
        self.video_label.place(x=0, y=0)
        
        self.is_running = True
        self.start_login()
        
    def start_login(self):
        """Inicia el proceso de login"""
        def login_loop():
            with self.core_system.get_camera_manager().camera_context():
                while self.is_running and self.window and self.window.winfo_exists():
                    try:
                        frame = self.core_system.get_camera_manager().get_frame()
                        processed_frame, recognized, message = self.core_system.process_login_frame(frame)

                        if processed_frame is not None:
                            self.video_label.update_frame(processed_frame)

                            if recognized is not None:  # entra cuando ya hay un resultado
                                # 1) Mostrar en consola si reconoció o no, y qué usuario
                                print(f"[Login] reconocido={recognized}, mensaje='{message}'")
                                # 2) Cerrar ventana tras 2 s
                                self.window.after(2000, self.close_window)
                                break
                        
                        time.sleep(0.033)  # ~30 FPS
                        
                    except Exception as e:
                        print(f"Error en login: {e}")
                        break
        
        # Ejecuta en thread separado
        login_thread = threading.Thread(target=login_loop, daemon=True)
        login_thread.start()
        
    def close_window(self):
        """Cierra la ventana y libera recursos"""
        self.is_running = False
        
        if self.video_label:
            self.video_label.cleanup()
        
        self.core_system.cleanup_login()
        
        if self.window:
            self.window.destroy()
        
        if self.on_complete:
            self.on_complete()


class GraphicalUserInterface:
    """Interfaz gráfica principal optimizada"""
    
    def __init__(self, root):
        self.main_window = root
        self.main_window.title('Faces Access Control')
        self.main_window.geometry('1280x720')
        self.main_window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.frame = CustomFrame(self.main_window)
        
        # Componentes del sistema
        self.core_system = FaceSystemCore()
        self.images = ImagePaths()
        
        # Ventanas secundarias
        self.signup_window = None
        self.current_face_window = None
        
        # Cache de imágenes para evitar recargas
        self.image_cache = {}
        
        # Configuración inicial
        self.setup_main_interface()
        
    def load_image(self, image_path):
        """Carga imágenes con cache para optimizar memoria"""
        if image_path not in self.image_cache:
            try:
                self.image_cache[image_path] = PhotoImage(file=image_path)
            except Exception as e:
                print(f"Error cargando imagen {image_path}: {e}")
                return None
        return self.image_cache[image_path]
    
    def setup_main_interface(self):
        """Configura la interfaz principal"""
        # Fondo
        background_img = self.load_image(self.images.init_img)
        if background_img:
            background = Label(self.frame, image=background_img)
            background.image = background_img
            background.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Botón Login
        login_img = self.load_image(self.images.login_img)
        if login_img:
            login_button = Button(self.frame, image=login_img, height=40, width=200,
                                command=self.open_login, relief=FLAT, borderwidth=0)
            login_button.image = login_img
            login_button.place(x=980, y=325)
        
        # Botón Signup
        signup_img = self.load_image(self.images.signup_img)
        if signup_img:
            signup_button = Button(self.frame, image=signup_img, height=40, width=200,
                                 command=self.open_signup, relief=FLAT, borderwidth=0)
            signup_button.image = signup_img
            signup_button.place(x=980, y=578)
    
    def open_signup(self):
        """Abre la ventana de registro"""
        if self.signup_window:
            return
            
        self.signup_window = Toplevel(self.frame)
        self.signup_window.title('Facial Sign Up')
        self.signup_window.geometry('1280x720')
        self.signup_window.protocol("WM_DELETE_WINDOW", self.close_signup)
        
        # Fondo
        background_img = self.load_image(self.images.gui_signup_img)
        if background_img:
            background = Label(self.signup_window, image=background_img)
            background.image = background_img
            background.place(x=0, y=0)
        
        # Campos de entrada
        self.input_name = Entry(self.signup_window, font=('Arial', 12))
        self.input_name.place(x=585, y=320)
        
        self.input_user_code = Entry(self.signup_window, font=('Arial', 12))
        self.input_user_code.place(x=585, y=475)
        
        # Botón registro
        register_img = self.load_image(self.images.register_img)
        if register_img:
            register_button = Button(self.signup_window, image=register_img, height=40, width=200,
                                   command=self.process_signup_data, relief=FLAT, borderwidth=0)
            register_button.image = register_img
            register_button.place(x=1005, y=565)
    
    def process_signup_data(self):
        """Procesa los datos de registro"""
        name = self.input_name.get().strip()
        user_code = self.input_user_code.get().strip()
        
        # Valida datos
        is_valid, message = self.core_system.validate_user_data(name, user_code)
        if not is_valid:
            print(f"Error: {message}")
            return
        
        # Guarda datos
        if self.core_system.save_user_data(name, user_code):
            # Limpia campos
            self.input_name.delete(0, END)
            self.input_user_code.delete(0, END)
            
            # Cierra ventana de registro
            self.close_signup()
            
            # Abre ventana de captura facial
            self.current_face_window = FaceSignUpWindow(
                self.main_window, 
                self.core_system, 
                user_code, 
                self.on_face_signup_complete
            )
            self.current_face_window.create_window()
        else:
            print("Error guardando datos del usuario")
    
    def on_face_signup_complete(self):
        """Callback cuando completa el registro facial"""
        self.current_face_window = None
        print("Registro completado exitosamente")
    
    def close_signup(self):
        """Cierra la ventana de registro"""
        if self.signup_window:
            self.signup_window.destroy()
            self.signup_window = None
    
    def open_login(self):
        """Abre la ventana de login"""
        if self.current_face_window:
            return
            
        self.current_face_window = FaceLoginWindow(
            self.main_window,
            self.core_system,
            self.on_face_login_complete
        )
        self.current_face_window.create_window()
    
    def on_face_login_complete(self):
        """Callback cuando completa el login facial"""
        self.current_face_window = None
        print("Login completado")
    
    def on_closing(self):
        """Maneja el cierre de la aplicación"""
        try:
            # Cierra ventanas secundarias
            if self.current_face_window:
                self.current_face_window.close_window()
            
            if self.signup_window:
                self.signup_window.destroy()
            
            # Limpia recursos
            ResourceOptimizer.cleanup_opencv_resources()
            
            # Cierra ventana principal
            self.main_window.destroy()
            
        except Exception as e:
            print(f"Error al cerrar: {e}")
        finally:
            self.main_window.quit()


def main():
    """Función principal"""
    root = tk.Tk()
    app = GraphicalUserInterface(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("Aplicación interrumpida por el usuario")
    except Exception as e:
        print(f"Error en la aplicación: {e}")
    finally:
        ResourceOptimizer.cleanup_opencv_resources()


if __name__ == "__main__":
    main()