"""
Drag and Drop - Múltiples Archivos
"""
import tkinter as tk
from tkinter import messagebox, scrolledtext
import os
from pathlib import Path

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKINTERDND_AVAILABLE = True
except ImportError:
    TKINTERDND_AVAILABLE = False

class DragDropApp:
    def __init__(self):
        # Verificar si tkinterdnd2 está disponible
        if not TKINTERDND_AVAILABLE:
            self.show_installation_message()
            return
            
        # Crear ventana principal con soporte para drag and drop
        self.root = TkinterDnD.Tk()
        self.root.title("Drag & Drop - Múltiples Archivos")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')
        self.result = None
        
        self.setup_ui()
        self.setup_drag_drop()
        
        # Lista para almacenar archivos procesados
        self.processed_files = []
        
    def setup_ui(self):
        """Configura la interfaz de usuario"""
        title_label = tk.Label(
            self.root,
            text="Arrastra y Suelta Archivos Aquí",
            font=('Arial', 16, 'bold'),
            bg='#f0f0f0',
            fg='#333333'
        )
        title_label.pack(pady=20)
        
        # Área de drop principal
        self.drop_frame = tk.Frame(
            self.root,
            width=600,
            height=200,
            bg='#e8e8e8',
            relief='groove',
            bd=2
        )
        self.drop_frame.pack(pady=20, padx=20, fill='both', expand=False)
        self.drop_frame.pack_propagate(False)
        
        # Etiqueta dentro del área de drop
        self.drop_label = tk.Label(
            self.drop_frame,
            text="📁 Arrastra archivos aquí\n(Acepta cualquier tipo de archivo)",
            font=('Arial', 12),
            bg='#e8e8e8',
            fg='#666666'
        )
        self.drop_label.pack(expand=True)
        
        # Frame para botones
        button_frame = tk.Frame(self.root, bg='#f0f0f0')
        button_frame.pack(pady=10)
        
        # Botón para limpiar lista
        self.clear_button = tk.Button(
            button_frame,
            text="🗑️ Limpiar Lista",
            command=self.clear_files,
            font=('Arial', 10),
            bg='#ff6b6b',
            fg='white',
            relief='flat',
            padx=20
        )
        self.clear_button.pack(side='left', padx=5)
        
        # Botón para mostrar información de archivos
        self.info_button = tk.Button(
            button_frame,
            text="ℹ️ Información de Archivos",
            command=self.show_file_info,
            font=('Arial', 10),
            bg='#4ecdc4',
            fg='white',
            relief='flat',
            padx=20
        )
        self.info_button.pack(side='left', padx=5)

        # Botón "Listo"
        self.done_button = tk.Button(
            self.root,
            text="✅ Listo",
            command=self.finish_and_close,
            font=('Arial', 10),
            bg='#6c63ff',
            fg='white',
            relief='flat',
            padx=20
        )
        self.done_button.pack(pady=10)
        
        # Área de texto para mostrar archivos
        self.text_area = scrolledtext.ScrolledText(
            self.root,
            width=80,
            height=15,
            font=('Consolas', 9),
            bg='white',
            fg='#333333'
        )
        self.text_area.pack(pady=20, padx=20, fill='both', expand=True)
        
        # Barra de estado
        self.status_label = tk.Label(
            self.root,
            text="Listo para recibir archivos...",
            font=('Arial', 9),
            bg='#f0f0f0',
            fg='#666666',
            anchor='w'
        )
        self.status_label.pack(side='bottom', fill='x', padx=10, pady=5)
        
    def setup_drag_drop(self):
        """Configura la funcionalidad de drag and drop"""
        # Registrar el área de drop
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)
        
        # permitir drop en toda la ventana
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.on_drop)
        
        # Eventos de hover para feedback visual
        self.drop_frame.dnd_bind('<<DragEnter>>', self.on_drag_enter)
        self.drop_frame.dnd_bind('<<DragLeave>>', self.on_drag_leave)

    def finish_and_close(self):
        """Compila los datos y cierra la ventana"""
        self.result = []
        for file_path in self.processed_files:
            path_obj = Path(file_path)
            self.result.append({
                "ruta": str(path_obj),
                "nombre": path_obj.name,
                "tamaño": self.format_file_size(path_obj.stat().st_size),
                "extensión": path_obj.suffix or "Sin extensión"
            })
        self.root.destroy() 
        
    def on_drag_enter(self, event):
        """Callback cuando se arrastra algo sobre el área"""
        self.drop_frame.configure(bg='#d4edda', relief='raised')
        self.drop_label.configure(bg='#d4edda', text="📂 Suelta los archivos aquí")
        
    def on_drag_leave(self, event):
        """Callback cuando se sale del área de drop"""
        self.drop_frame.configure(bg='#e8e8e8', relief='groove')
        self.drop_label.configure(bg='#e8e8e8', text="📁 Arrastra archivos aquí\n(Acepta cualquier tipo de archivo)")
        
    def on_drop(self, event):
        """Callback principal cuando se sueltan archivos"""
        # Restaurar apariencia normal
        self.drop_frame.configure(bg='#e8e8e8', relief='groove')
        self.drop_label.configure(bg='#e8e8e8', text="📁 Arrastra archivos aquí\n(Acepta cualquier tipo de archivo)")
        
        # Obtener lista de archivos
        files = self.parse_drop_files(event.data)
        
        if files:
            self.process_files(files)
        else:
            self.update_status("No se detectaron archivos válidos")
            
    def parse_drop_files(self, data):
        """Parsea los datos del drop para extraer rutas de archivos"""
        files = []
        
        # Los datos pueden venir en diferentes formatos
        if isinstance(data, str):
            
            parts = []
            current = ""
            in_braces = False
            
            for char in data:
                if char == '{':
                    in_braces = True
                    current += char
                elif char == '}':
                    in_braces = False
                    current += char
                    parts.append(current.strip('{}'))
                    current = ""
                elif char == ' ' and not in_braces:
                    if current.strip():
                        parts.append(current)
                    current = ""
                else:
                    current += char
            
            if current.strip():
                parts.append(current)
                
            files = parts
        elif isinstance(data, (list, tuple)):
            files = list(data)
            
        # Limpiar y validar rutas
        valid_files = []
        for file_path in files:
            file_path = file_path.strip().strip('{}').strip('"').strip("'")
            if file_path and os.path.exists(file_path):
                valid_files.append(file_path)
                
        return valid_files
        
    def process_files(self, files):
        """Procesa la lista de archivos recibidos"""
        new_files = 0
        
        for file_path in files:
            if file_path not in self.processed_files:
                self.processed_files.append(file_path)
                new_files += 1
                
                # Obtener información del archivo
                path_obj = Path(file_path)
                file_size = self.format_file_size(path_obj.stat().st_size)
                
                # Agregar a la lista visual
                file_info = f"{path_obj.name}\n"
                file_info += f"    Ruta: {file_path}\n"
                file_info += f"    Tamaño: {file_size}\n"
                file_info += f"    Extensión: {path_obj.suffix or 'Sin extensión'}\n"
                file_info += "-" * 80 + "\n"
                
                self.text_area.insert(tk.END, file_info)
                
        # Scroll al final
        self.text_area.see(tk.END)
        
        # Actualizar estado
        total_files = len(self.processed_files)
        if new_files > 0:
            self.update_status(f"{new_files} archivo(s) nuevo(s) agregado(s). Total: {total_files}")
        else:
            self.update_status(f"Archivo(s) ya procesado(s). Total: {total_files}")
            
    def format_file_size(self, size_bytes):
        """Formatea el tamaño del archivo en unidades legibles"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = float(size_bytes)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
            
        return f"{size:.1f} {size_names[i]}"
        
    def clear_files(self):
        """Limpia la lista de archivos"""
        self.processed_files.clear()
        self.text_area.delete(1.0, tk.END)
        self.update_status("Lista de archivos limpiada")
        
    def show_file_info(self):
        """Muestra información resumida de los archivos"""
        if not self.processed_files:
            messagebox.showinfo("Información", "No hay archivos cargados")
            return
            
        # Calcular estadísticas
        total_files = len(self.processed_files)
        total_size = sum(Path(f).stat().st_size for f in self.processed_files if os.path.exists(f))
        
        # Contar extensiones
        extensions = {}
        for file_path in self.processed_files:
            ext = Path(file_path).suffix.lower() or 'sin extensión'
            extensions[ext] = extensions.get(ext, 0) + 1
            
        # Crear mensaje
        info_msg = f"RESUMEN DE ARCHIVOS\n\n"
        info_msg += f"Total de archivos: {total_files}\n"
        info_msg += f"Tamaño total: {self.format_file_size(total_size)}\n\n"
        info_msg += "Tipos de archivo:\n"
        
        for ext, count in sorted(extensions.items()):
            info_msg += f"  • {ext}: {count} archivo(s)\n"
            
        messagebox.showinfo("Información de Archivos", info_msg)
        
    def update_status(self, message):
        """Actualiza el mensaje de estado"""
        self.status_label.configure(text=message)
        self.root.update()
        
    def show_installation_message(self):
        """Muestra mensaje de instalación si falta tkinterdnd2"""
        root = tk.Tk()
        root.title("Dependencia Requerida")
        root.geometry("500x200")
        
        message = """Para usar esta aplicación, necesitas instalar tkinterdnd2:

                    pip install tkinterdnd2

                    Después de la instalación, ejecuta el programa nuevamente."""
        
        tk.Label(root, text=message, font=('Arial', 10), justify='left').pack(pady=20, padx=20)
        
        def close_app():
            root.destroy()
            
        tk.Button(root, text="Cerrar", command=close_app).pack(pady=10)
        root.mainloop()
        
    def run(self):
        """Ejecuta la aplicación"""
        if TKINTERDND_AVAILABLE:
            self.root.mainloop()
        return self.result

if __name__ == "__main__":
    app = DragDropApp()
    archivos = app.run()
    print("archivos seleccionados: ", archivos)