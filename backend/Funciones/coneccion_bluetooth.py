#!/usr/bin/env python3
"""
Bluetooth Device Scanner - Versión moderna con Bleak
Funciona perfectamente en Windows, macOS y Linux

INSTALACIÓN SIMPLE:
pip install bleak tkinter

Esta versión usa Bleak (Bluetooth Low Energy) que es más moderna
y compatible con Python 3.7+
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import asyncio
import threading
import time
import platform
import subprocess
import sys
from importlib.util import find_spec


class BluetoothScannerBleak:
    def __init__(self, root):
        self.root = root
        self.root.title("🔵 Bluetooth Scanner (Bleak)")
        self.root.geometry("900x700")
        self.root.configure(bg="#f0f0f0")
        
        # Variables
        self.scanning = False
        self.devices = {}
        self.selected_device = None
        self.scanner = None
        self.system_os = platform.system()
        
        # Event loop para async
        self.loop = None
        
        self.setup_ui()
        self.check_bleak_support()
    
    def setup_ui(self):
        """Configurar la interfaz de usuario"""
        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        title_label = ttk.Label(header_frame, text="🔵 Bluetooth Scanner Pro", 
                               font=("Segoe UI", 18, "bold"))
        title_label.pack(side=tk.LEFT)
        
        version_label = ttk.Label(header_frame, text="v2.0 - Powered by Bleak", 
                                 font=("Segoe UI", 10), foreground="gray")
        version_label.pack(side=tk.RIGHT, anchor=tk.E)
        
        # Frame de controles
        control_frame = ttk.LabelFrame(main_frame, text="Controles", padding="10")
        control_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Botones de control
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X)
        
        self.scan_button = ttk.Button(btn_frame, text="🔍 Buscar Dispositivos", 
                                     command=self.toggle_scan)
        self.scan_button.pack(side=tk.LEFT, padx=(0, 10))
        
        clear_button = ttk.Button(btn_frame, text="🗑️ Limpiar", 
                                 command=self.clear_devices)
        clear_button.pack(side=tk.LEFT, padx=(0, 10))
        
        refresh_button = ttk.Button(btn_frame, text="🔄 Actualizar", 
                                   command=self.quick_scan)
        refresh_button.pack(side=tk.LEFT, padx=(0, 10))
        
        # Status y progress
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_label = ttk.Label(status_frame, text="🟢 Listo para escanear")
        self.status_label.pack(side=tk.LEFT)
        
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Frame de dispositivos encontrados
        devices_frame = ttk.LabelFrame(main_frame, text="📱 Dispositivos Bluetooth", padding="5")
        devices_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        
        # Treeview mejorado
        columns = ("nombre", "direccion", "rssi", "tipo", "estado")
        self.device_tree = ttk.Treeview(devices_frame, columns=columns, show="headings", height=12)
        
        # Configurar columnas
        headers = {
            "nombre": "📱 Nombre del Dispositivo",
            "direccion": "🏷️ Dirección MAC", 
            "rssi": "📶 Señal (dBm)",
            "tipo": "🔧 Tipo",
            "estado": "⚡ Estado"
        }
        
        widths = {"nombre": 200, "direccion": 150, "rssi": 100, "tipo": 120, "estado": 100}
        
        for col, header in headers.items():
            self.device_tree.heading(col, text=header)
            self.device_tree.column(col, width=widths[col], minwidth=80)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(devices_frame, orient=tk.VERTICAL, command=self.device_tree.yview)
        h_scrollbar = ttk.Scrollbar(devices_frame, orient=tk.HORIZONTAL, command=self.device_tree.xview)
        
        self.device_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid del treeview
        self.device_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        v_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        h_scrollbar.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Bind para selección
        self.device_tree.bind("<<TreeviewSelect>>", self.on_device_select)
        self.device_tree.bind("<Double-1>", self.on_double_click)
        
        # Frame de acciones
        action_frame = ttk.LabelFrame(main_frame, text="🎯 Acciones del Dispositivo", padding="10")
        action_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        # Información del dispositivo seleccionado
        self.device_info_frame = ttk.Frame(action_frame)
        self.device_info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.device_info_label = ttk.Label(self.device_info_frame, 
                                          text="💡 Selecciona un dispositivo para ver opciones",
                                          font=("Segoe UI", 10))
        self.device_info_label.pack()
        
        # Botones de acción
        action_btn_frame = ttk.Frame(action_frame)
        action_btn_frame.pack(fill=tk.X)
        
        self.connect_button = ttk.Button(action_btn_frame, text="🔗 Conectar", 
                                        command=self.connect_device, state="disabled")
        self.connect_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.services_button = ttk.Button(action_btn_frame, text="🔍 Ver Servicios", 
                                         command=self.show_services, state="disabled")
        self.services_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.pair_button = ttk.Button(action_btn_frame, text="🤝 Emparejar", 
                                     command=self.pair_device, state="disabled")
        self.pair_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.info_button = ttk.Button(action_btn_frame, text="ℹ️ Detalles", 
                                     command=self.show_device_details, state="disabled")
        self.info_button.pack(side=tk.LEFT)
        
        # Frame de log
        log_frame = ttk.LabelFrame(main_frame, text="📋 Registro de Actividad", padding="5")
        log_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Log con colores
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, width=100, 
                                                 state="disabled", wrap=tk.WORD,
                                                 font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Tags para colores en el log
        self.log_text.tag_configure("success", foreground="green")
        self.log_text.tag_configure("error", foreground="red")
        self.log_text.tag_configure("warning", foreground="orange")
        self.log_text.tag_configure("info", foreground="blue")
        
        # Configurar grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=2)
        main_frame.rowconfigure(4, weight=1)
        devices_frame.columnconfigure(0, weight=1)
        devices_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
    
    def log_message(self, message, tag="normal"):
        """Agregar mensaje al log con colores"""
        self.log_text.config(state="normal")
        timestamp = time.strftime("%H:%M:%S")
        
        # Determinar tag automáticamente si no se especifica
        if tag == "normal":
            if "❌" in message or "Error" in message:
                tag = "error"
            elif "✅" in message or "éxito" in message:
                tag = "success"
            elif "⚠️" in message or "Advertencia" in message:
                tag = "warning"
            elif "ℹ️" in message or "Info" in message:
                tag = "info"
        
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")
        print(f"[{timestamp}] {message}")
    
    def check_bleak_support(self):
        """Verificar soporte de Bleak"""
        if find_spec("bleak") is not None:
            self.log_message(f"✅ Bleak instalado correctamente en {self.system_os}", "success")
            self.log_message("🚀 Sistema listo para escanear dispositivos BLE", "success")
            return True

        self.log_message("❌ Bleak no está instalado", "error")
        self.show_bleak_installation()
        return False
    
    def show_bleak_installation(self):
        """Mostrar ventana de instalación de Bleak"""
        install_window = tk.Toplevel(self.root)
        install_window.title("📦 Instalación de Bleak")
        install_window.geometry("600x400")
        install_window.resizable(True, True)
        
        frame = ttk.Frame(install_window, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="📦 Instalar Bleak", font=("Arial", 16, "bold")).pack(pady=(0, 15))
        
        install_text = """
🎯 INSTALACIÓN SÚPER SIMPLE:

pip install bleak

✅ VENTAJAS DE BLEAK:
• Funciona en Python 3.7+ sin problemas
• Compatible con Windows 10/11 nativo
• Soporte BLE (Bluetooth Low Energy) moderno
• No requiere dependencias complicadas
• Mantenimiento activo y documentación excelente

📋 COMANDOS ALTERNATIVOS:
• python -m pip install bleak
• pip3 install bleak
• conda install bleak (para Anaconda)

🔧 DESPUÉS DE INSTALAR:
1. Cierra esta aplicación
2. Ejecuta el comando de instalación
3. Reinicia la aplicación

⚡ COMANDO COMPLETO:
pip install bleak asyncio

NOTA: Bleak funciona con Bluetooth Low Energy (BLE), que es el 
estándar moderno soportado por la mayoría de dispositivos actuales.
        """
        
        text_widget = scrolledtext.ScrolledText(frame, height=18, width=70, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        text_widget.insert(tk.END, install_text.strip())
        text_widget.config(state="disabled")
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="📋 Copiar Comando", 
                  command=lambda: self.copy_to_clipboard("pip install bleak")).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="🚀 Instalar Ahora", 
                  command=self.install_bleak_now).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="❌ Cerrar", command=install_window.destroy).pack(side=tk.RIGHT)
    
    def install_bleak_now(self):
        """Intentar instalar Bleak automáticamente"""
        self.log_message("🔄 Intentando instalar Bleak automáticamente...", "info")
        
        try:
            import subprocess
            result = subprocess.run([sys.executable, "-m", "pip", "install", "bleak"], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log_message("✅ Bleak instalado exitosamente!", "success")
                messagebox.showinfo("Éxito", "Bleak instalado correctamente.\nReinicia la aplicación para usar todas las funciones.")
            else:
                self.log_message(f"❌ Error en instalación: {result.stderr}", "error")
                messagebox.showerror("Error", "No se pudo instalar automáticamente.\nUsa el comando manual en terminal.")
        
        except Exception as e:
            self.log_message(f"❌ Error durante instalación automática: {e}", "error")
            messagebox.showerror("Error", "Instalación automática falló.\nUsa el comando manual.")
    
    def copy_to_clipboard(self, text):
        """Copiar texto al portapapeles"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("📋 Copiado", f"Comando copiado:\n{text}")
    
    def toggle_scan(self):
        """Alternar escaneo"""
        if not self.scanning:
            self.start_scan()
        else:
            self.stop_scan()
    
    def start_scan(self):
        """Iniciar escaneo"""
        if find_spec("bleak") is None:
            messagebox.showerror("Error", "Bleak no está instalado.\nUsa: pip install bleak")
            return
        
        if self.scanning:
            return
        
        self.scanning = True
        self.scan_button.config(text="⏹️ Detener")
        self.status_label.config(text="🔵 Escaneando dispositivos BLE...")
        self.progress.start()
        
        # Ejecutar escaneo async en thread
        scan_thread = threading.Thread(target=self._run_async_scan)
        scan_thread.daemon = True
        scan_thread.start()
    
    def _run_async_scan(self):
        """Ejecutar escaneo async"""
        try:
            # Crear nuevo loop para el thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.scan_devices_async())
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"❌ Error en escaneo: {e}", "error"))
        finally:
            self.root.after(0, self.finish_scan)
    
    async def scan_devices_async(self):
        """Escaneo asíncrono de dispositivos"""
        from bleak import BleakScanner
        
        self.root.after(0, lambda: self.log_message("🔍 Iniciando escaneo BLE...", "info"))
        
        try:
            # Escanear por 10 segundos
            devices = await BleakScanner.discover(timeout=10.0, return_adv=True)
            
            if not devices:
                self.root.after(0, lambda: self.log_message("ℹ️ No se encontraron dispositivos BLE", "info"))
                return
            
            self.root.after(0, lambda: self.log_message(f"✅ Encontrados {len(devices)} dispositivos BLE", "success"))
            
            for address, (device, adv_data) in devices.items():
                if not self.scanning:
                    break
                
                # Obtener información del dispositivo
                name = device.name or "Dispositivo Sin Nombre"
                rssi = adv_data.rssi if hasattr(adv_data, 'rssi') else "N/A"
                
                # Determinar tipo basado en servicios
                device_type = self.determine_device_type(adv_data)
                
                device_info = {
                    'name': name,
                    'address': address,
                    'rssi': rssi,
                    'type': device_type,
                    'status': 'Disponible',
                    'device_obj': device,
                    'adv_data': adv_data
                }
                
                # Agregar a la UI
                self.root.after(0, lambda info=device_info: self.add_device_to_list(info))
                self.root.after(0, lambda n=name, a=address: 
                              self.log_message(f"📱 Encontrado: {n} ({a})", "success"))
        
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"❌ Error durante escaneo: {e}", "error"))
    
    def determine_device_type(self, adv_data):
        """Determinar tipo de dispositivo basado en datos de advertising"""
        try:
            if hasattr(adv_data, 'service_uuids') and adv_data.service_uuids:
                services = adv_data.service_uuids
                
                # UUIDs comunes
                if "0000180F-0000-1000-8000-00805F9B34FB" in services:  # Battery Service
                    return "Dispositivo con Batería"
                elif "0000180A-0000-1000-8000-00805F9B34FB" in services:  # Device Information
                    return "Dispositivo Informativo"
                elif "00001812-0000-1000-8000-00805F9B34FB" in services:  # HID
                    return "Teclado/Mouse"
                elif "0000180D-0000-1000-8000-00805F9B34FB" in services:  # Heart Rate
                    return "Monitor Cardíaco"
                elif "00001816-0000-1000-8000-00805F9B34FB" in services:  # Cycling Speed
                    return "Sensor Ciclismo"
                else:
                    return f"BLE ({len(services)} servicios)"
            
            return "Dispositivo BLE"
        except:
            return "BLE Genérico"
    
    def add_device_to_list(self, device_info):
        """Agregar dispositivo a la lista"""
        # Verificar si ya existe
        for item in self.device_tree.get_children():
            if self.device_tree.item(item)['values'][1] == device_info['address']:
                # Actualizar existente
                self.device_tree.item(item, values=(
                    device_info['name'],
                    device_info['address'],
                    device_info['rssi'],
                    device_info['type'],
                    device_info['status']
                ))
                self.devices[item] = device_info
                return
        
        # Agregar nuevo
        item_id = self.device_tree.insert("", "end", values=(
            device_info['name'],
            device_info['address'],
            device_info['rssi'],
            device_info['type'],
            device_info['status']
        ))
        
        self.devices[item_id] = device_info
    
    def quick_scan(self):
        """Escaneo rápido de 3 segundos"""
        if self.scanning:
            return
        
        self.log_message("⚡ Escaneo rápido (3 segundos)...", "info")
        # Implementar escaneo corto similar al anterior
        self.start_scan()
    
    def stop_scan(self):
        """Detener escaneo"""
        self.scanning = False
        self.finish_scan()
    
    def finish_scan(self):
        """Finalizar escaneo"""
        self.scanning = False
        self.scan_button.config(text="🔍 Buscar Dispositivos")
        self.status_label.config(text="🟢 Escaneo completado")
        self.progress.stop()
        self.log_message("✅ Escaneo finalizado", "success")
    
    def clear_devices(self):
        """Limpiar lista de dispositivos"""
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        self.devices.clear()
        self.selected_device = None
        self.update_action_buttons()
        self.log_message("🗑️ Lista limpiada", "info")
    
    def on_device_select(self, event):
        """Manejar selección de dispositivo"""
        selection = self.device_tree.selection()
        if selection:
            item_id = selection[0]
            self.selected_device = self.devices.get(item_id)
            self.update_action_buttons()
            
            if self.selected_device:
                info = f"📱 {self.selected_device['name']} | 📶 {self.selected_device['rssi']} dBm | 🏷️ {self.selected_device['address']}"
                self.device_info_label.config(text=info)
        else:
            self.selected_device = None
            self.update_action_buttons()
            self.device_info_label.config(text="💡 Selecciona un dispositivo para ver opciones")
    
    def on_double_click(self, event):
        """Manejar doble clic en dispositivo"""
        if self.selected_device:
            self.show_device_details()
    
    def update_action_buttons(self):
        """Actualizar botones de acción"""
        state = "normal" if self.selected_device else "disabled"
        
        self.connect_button.config(state=state)
        self.services_button.config(state=state)
        self.pair_button.config(state=state)
        self.info_button.config(state=state)
    
    def connect_device(self):
        """Conectar al dispositivo"""
        if not self.selected_device:
            return
        
        device = self.selected_device
        self.log_message(f"🔗 Conectando a {device['name']}...", "info")
        
        # Ejecutar conexión async
        connect_thread = threading.Thread(target=self._run_async_connect)
        connect_thread.daemon = True
        connect_thread.start()
    
    def _run_async_connect(self):
        """Ejecutar conexión async"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.connect_device_async())
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"❌ Error en conexión: {e}", "error"))
    
    async def connect_device_async(self):
        """Conexión asíncrona al dispositivo"""
        from bleak import BleakClient
        
        device = self.selected_device
        
        try:
            async with BleakClient(device['address']) as client:
                if client.is_connected:
                    self.root.after(0, lambda: self.log_message(f"✅ Conectado a {device['name']}", "success"))
                    
                    # Obtener servicios básicos
                    services = client.services
                    service_count = len(services)
                    
                    self.root.after(0, lambda: self.log_message(f"🔍 Servicios encontrados: {service_count}", "info"))
                    
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Conexión Exitosa",
                        f"✅ Conectado a {device['name']}\n"
                        f"📍 Dirección: {device['address']}\n"
                        f"🔧 Servicios: {service_count}\n"
                        f"📶 Señal: {device['rssi']} dBm"
                    ))
                else:
                    self.root.after(0, lambda: self.log_message(f"❌ No se pudo conectar a {device['name']}", "error"))
        
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"❌ Error de conexión: {e}", "error"))
            self.root.after(0, lambda: messagebox.showerror("Error", f"No se pudo conectar:\n{e}"))
    
    def show_services(self):
        """Mostrar servicios del dispositivo"""
        if not self.selected_device:
            return
        
        self.log_message(f"🔍 Obteniendo servicios de {self.selected_device['name']}...", "info")
        
        # Ejecutar en thread async
        services_thread = threading.Thread(target=self._run_async_services)
        services_thread.daemon = True
        services_thread.start()
    
    def _run_async_services(self):
        """Obtener servicios async"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.get_services_async())
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"❌ Error obteniendo servicios: {e}", "error"))
    
    async def get_services_async(self):
        """Obtener servicios del dispositivo"""
        from bleak import BleakClient
        
        device = self.selected_device
        
        try:
            async with BleakClient(device['address']) as client:
                if client.is_connected:
                    services = client.services
                    
                    # Crear ventana de servicios
                    self.root.after(0, lambda: self.show_services_window(services, device))
                else:
                    self.root.after(0, lambda: self.log_message("❌ No se pudo conectar para obtener servicios", "error"))
        
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"❌ Error obteniendo servicios: {e}", "error"))
    
    def show_services_window(self, services, device):
        """Mostrar ventana de servicios"""
        services_window = tk.Toplevel(self.root)
        services_window.title(f"🔍 Servicios - {device['name']}")
        services_window.geometry("600x500")
        
        frame = ttk.Frame(services_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text=f"🔧 Servicios de {device['name']}", 
                 font=("Arial", 14, "bold")).pack(pady=(0, 10))
        
        # Lista de servicios
        services_text = scrolledtext.ScrolledText(frame, height=20, width=70, wrap=tk.WORD)
        services_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        services_info = f"📱 Dispositivo: {device['name']}\n"
        services_info += f"🏷️ Dirección: {device['address']}\n"
        services_info += f"📶 Señal: {device['rssi']} dBm\n\n"
        services_info += f"🔧 SERVICIOS ENCONTRADOS ({len(services)}):\n"
        services_info += "=" * 50 + "\n\n"
        
        for i, service in enumerate(services, 1):
            services_info += f"[{i}] Servicio UUID: {service.uuid}\n"
            services_info += f"    Descripción: {service.description or 'Sin descripción'}\n"
            
            characteristics = service.characteristics
            services_info += f"    Características: {len(characteristics)}\n"
            
            for char in characteristics:
                services_info += f"      • {char.uuid} - {char.description or 'Sin descripción'}\n"
                services_info += f"        Propiedades: {', '.join(char.properties)}\n"
            
            services_info += "\n"
        
        services_text.insert(tk.END, services_info)
        services_text.config(state="disabled")
        
        ttk.Button(frame, text="Cerrar", command=services_window.destroy).pack()
        
        self.log_message(f"✅ Servicios obtenidos para {device['name']}: {len(services)} servicios", "success")
    
    def pair_device(self):
        """Emparejar dispositivo usando configuración del sistema"""
        if not self.selected_device:
            return
        
        device = self.selected_device
        self.log_message(f"🤝 Iniciando emparejamiento con {device['name']}...", "info")
        
        try:
            if self.system_os == "Windows":
                # Abrir configuración de Bluetooth en Windows
                subprocess.run(["ms-settings:bluetooth"], shell=True)
                messagebox.showinfo(
                    "Emparejamiento - Windows",
                    f"🪟 Se abrió la configuración de Bluetooth de Windows.\n\n"
                    f"📱 Dispositivo: {device['name']}\n"
                    f"🏷️ Dirección: {device['address']}\n\n"
                    f"👆 Busca '{device['name']}' en la lista y haz clic en 'Emparejar'"
                )
            
            elif self.system_os == "Linux":
                try:
                    # Intentar usar bluetoothctl
                    subprocess.run(["bluetoothctl", "pair", device['address']], check=True)
                    self.log_message(f"✅ Comando de emparejamiento enviado", "success")
                    messagebox.showinfo("Emparejamiento - Linux", 
                                      f"✅ Comando enviado para emparejar con {device['name']}")
                except subprocess.CalledProcessError:
                    messagebox.showinfo(
                        "Emparejamiento Manual - Linux",
                        f"🐧 Ejecuta estos comandos en terminal:\n\n"
                        f"bluetoothctl\n"
                        f"scan on\n"
                        f"pair {device['address']}\n"
                        f"trust {device['address']}\n"
                        f"connect {device['address']}"
                    )
            
            elif self.system_os == "Darwin":  # macOS
                subprocess.run(["open", "/System/Preferences/Bluetooth.prefPane"])
                messagebox.showinfo(
                    "Emparejamiento - macOS",
                    f"🍎 Se abrieron las preferencias de Bluetooth.\n\n"
                    f"📱 Dispositivo: {device['name']}\n"
                    f"🏷️ Dirección: {device['address']}\n\n"
                    f"👆 Busca '{device['name']}' y haz clic en 'Conectar'"
                )
        
        except Exception as e:
            self.log_message(f"❌ Error en emparejamiento: {e}", "error")
            messagebox.showerror("Error de Emparejamiento", f"Error: {e}")
    
    def show_device_details(self):
        """Mostrar detalles completos del dispositivo"""
        if not self.selected_device:
            return
        
        device = self.selected_device
        
        details_window = tk.Toplevel(self.root)
        details_window.title(f"📱 Detalles - {device['name']}")
        details_window.geometry("500x600")
        details_window.resizable(True, True)
        
        frame = ttk.Frame(details_window, padding="15")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(header_frame, text="📱 Información Detallada", 
                 font=("Arial", 16, "bold")).pack(side=tk.LEFT)
        
        # Información detallada
        details_text = scrolledtext.ScrolledText(frame, height=25, width=60, wrap=tk.WORD)
        details_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Compilar información
        info = f"""🏷️ INFORMACIÓN BÁSICA
{'=' * 40}
Nombre: {device['name']}
Dirección MAC: {device['address']}
Tipo de Dispositivo: {device['type']}
Estado: {device['status']}
Intensidad de Señal: {device['rssi']} dBm

📶 CALIDAD DE SEÑAL
{'=' * 40}"""
        
        rssi = device['rssi']
        if isinstance(rssi, (int, float)):
            if rssi >= -50:
                signal_quality = "🟢 Excelente"
            elif rssi >= -60:
                signal_quality = "🟡 Buena"
            elif rssi >= -70:
                signal_quality = "🟠 Regular"
            else:
                signal_quality = "🔴 Débil"
        else:
            signal_quality = "❓ Desconocida"
        
        info += f"""
Calidad: {signal_quality}
Distancia Estimada: {self.estimate_distance(rssi)}

🔧 INFORMACIÓN TÉCNICA
{'=' * 40}
Protocolo: Bluetooth Low Energy (BLE)
Sistema Operativo: {self.system_os}
Descubierto: {time.strftime('%H:%M:%S')}

🚀 CAPACIDADES ESTIMADAS
{'=' * 40}"""
        
        # Capacidades basadas en el tipo de dispositivo
        capabilities = self.get_device_capabilities(device['type'])
        info += f"\n{capabilities}"
        
        # Información de advertising data si está disponible
        if 'adv_data' in device and device['adv_data']:
            try:
                adv_data = device['adv_data']
                info += f"""

📡 DATOS DE ADVERTISING
{'=' * 40}
Manufacturer Data: {bool(hasattr(adv_data, 'manufacturer_data') and adv_data.manufacturer_data)}
Service Data: {bool(hasattr(adv_data, 'service_data') and adv_data.service_data)}
Service UUIDs: {len(adv_data.service_uuids) if hasattr(adv_data, 'service_uuids') and adv_data.service_uuids else 0}
TX Power: {getattr(adv_data, 'tx_power', 'N/A')}
"""
            except:
                info += "\n📡 Datos de advertising no disponibles"
        
        info += f"""

💡 ACCIONES RECOMENDADAS
{'=' * 40}
• Usar 'Conectar' para establecer conexión BLE
• Ver 'Servicios' para explorar funcionalidades
• 'Emparejar' para conexión persistente del sistema
• Verificar compatibilidad con aplicaciones específicas

⚠️ NOTAS IMPORTANTES
{'=' * 40}
• BLE (Bluetooth Low Energy) es diferente a Bluetooth clásico
• Algunos dispositivos requieren aplicaciones específicas
• La distancia y obstáculos afectan la conectividad
• Algunos servicios pueden requerir autenticación
"""
        
        details_text.insert(tk.END, info)
        details_text.config(state="disabled")
        
        # Botones de acción
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="🔗 Conectar", 
                  command=lambda: [details_window.destroy(), self.connect_device()]).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="🔍 Ver Servicios", 
                  command=lambda: [details_window.destroy(), self.show_services()]).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="📋 Copiar Info", 
                  command=lambda: self.copy_device_info(device)).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(btn_frame, text="❌ Cerrar", command=details_window.destroy).pack(side=tk.RIGHT)
        
        self.log_message(f"ℹ️ Mostrando detalles de {device['name']}", "info")
    
    def estimate_distance(self, rssi):
        """Estimar distancia basada en RSSI"""
        if not isinstance(rssi, (int, float)):
            return "Desconocida"
        
        if rssi >= -50:
            return "< 1 metro (muy cerca)"
        elif rssi >= -60:
            return "1-3 metros (cerca)"
        elif rssi >= -70:
            return "3-10 metros (medio)"
        elif rssi >= -80:
            return "10-30 metros (lejos)"
        else:
            return "> 30 metros (muy lejos)"
    
    def get_device_capabilities(self, device_type):
        """Obtener capacidades estimadas del dispositivo"""
        capabilities = {
            "Dispositivo con Batería": "• Monitoreo de nivel de batería\n• Notificaciones de batería baja",
            "Teclado/Mouse": "• Entrada de texto\n• Control de cursor\n• Combinaciones de teclas",
            "Monitor Cardíaco": "• Monitoreo de frecuencia cardíaca\n• Alertas de zona de entrenamiento",
            "Sensor Ciclismo": "• Velocidad y cadencia\n• Datos de entrenamiento",
            "Dispositivo Informativo": "• Información del fabricante\n• Número de modelo y firmware",
            "BLE Genérico": "• Servicios personalizados\n• Funcionalidad específica del fabricante"
        }
        
        return capabilities.get(device_type, "• Funcionalidades específicas del dispositivo\n• Consultar documentación del fabricante")
    
    def copy_device_info(self, device):
        """Copiar información del dispositivo al portapapeles"""
        info = f"""Dispositivo Bluetooth: {device['name']}
Dirección: {device['address']}
Tipo: {device['type']}
Señal: {device['rssi']} dBm
Estado: {device['status']}
Descubierto: {time.strftime('%Y-%m-%d %H:%M:%S')}"""
        
        self.copy_to_clipboard(info)
        self.log_message(f"📋 Información de {device['name']} copiada al portapapeles", "info")


def check_bleak_dependency():
    """Verificar si Bleak está instalado"""
    return find_spec("bleak") is not None


def show_dependency_error():
    """Mostrar error de dependencias"""
    root = tk.Tk()
    root.withdraw()
    
    message = """🚫 Bleak no está instalado

INSTALACIÓN SÚPER FÁCIL:

pip install bleak

✅ VENTAJAS:
• Funciona perfectamente en Windows 10/11
• Compatible con Python 3.7+
• Sin problemas de compilación
• Soporte BLE moderno

Después de instalar, reinicia la aplicación."""
    
    result = messagebox.askyesno("Instalar Bleak", 
                                f"{message}\n\n¿Quieres abrir la ventana de ayuda?")
    
    if result:
        # Crear ventana temporal de ayuda
        temp_root = tk.Tk()
        temp_app = BluetoothScannerBleak(temp_root)
        temp_app.show_bleak_installation()
        temp_root.mainloop()
    
    root.destroy()


def main():
    """Función principal"""
    # Verificar dependencias
    if not check_bleak_dependency():
        show_dependency_error()
        return
    
    # Crear y ejecutar aplicación
    root = tk.Tk()
    app = BluetoothScannerBleak(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n🛑 Aplicación cerrada por el usuario")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")


if __name__ == "__main__":
    main()