"""
main.py - lanzador unificado con HOT-RELOADING para desarrollo rápido
"""

import os
import sys
import signal
import logging
import argparse
import threading
import time
import importlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from backend.terminales import cerrar_terminal, iniciar_en_terminal

if '__file__' in globals():
    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
else:
    PROJECT_ROOT = os.path.abspath(os.getcwd())

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

LOG_FILE = os.path.join(PROJECT_ROOT, "logs", "run_all.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def setup_logging(debug: bool = False):
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    handlers = [logging.StreamHandler(), logging.FileHandler(LOG_FILE, encoding="utf-8")]
    logging.basicConfig(level=level, format=fmt, handlers=handlers)

def preflight_checks():
    """Chequeos rápidos: versión de Python y existencia de carpetas críticas."""
    logger = logging.getLogger("preflight")
    pyver = sys.version_info
    if pyver < (3, 10):
        logger.warning("Se recomienda Python >= 3.10 (actual: %s). Algunos paquetes pueden fallar.", sys.version)
    for p in ("backend", "frontend"):
        if not os.path.isdir(os.path.join(PROJECT_ROOT, p)):
            logger.error("No se encontró la carpeta '%s' en %s. Asegúrate de ejecutar desde la raíz del proyecto.", p, PROJECT_ROOT)
            raise SystemExit(1)
    logger.info("Checks básicos OK.")

def check_imports(modules):
    logger = logging.getLogger("preflight.imports")
    missing = []
    for m in modules:
        try:
            __import__(m)
        except Exception as e:
            logger.warning("No se pudo importar '%s' (%s).", m, e)
            missing.append(m)
    if missing:
        logger.warning("Módulos posiblemente faltantes: %s", missing)
    return missing


class CodeReloadHandler(FileSystemEventHandler):
    """Observa cambios en archivos .py y recarga módulos automáticamente"""
    
    def __init__(self, reload_callback, watch_paths=None):
        super().__init__()
        self.reload_callback = reload_callback
        self.watch_paths = watch_paths or []
        self.last_reload = {}
        self.cooldown = 1.0  # Esperar 1 seg antes de recargar el mismo archivo
        
    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith('.py'):
            return
            
        # Evitar recargas múltiples del mismo archivo
        now = time.time()
        if event.src_path in self.last_reload:
            if now - self.last_reload[event.src_path] < self.cooldown:
                return
        
        self.last_reload[event.src_path] = now
        
        logger = logging.getLogger("hotreload")
        logger.info(f"📝 Detectado cambio en: {event.src_path}")
        
        # Convertir path a nombre de módulo
        rel_path = os.path.relpath(event.src_path, PROJECT_ROOT)
        module_name = rel_path.replace(os.sep, '.').replace('.py', '')
        
        self.reload_callback(module_name, event.src_path)


class ReloadableBackend:
    """Wrapper para backend que permite recarga sin reiniciar todo"""
    
    def __init__(self):
        self.yatusabe = None
        self.logger = logging.getLogger("backend_reloadable")
        self.lock = threading.Lock()
        self.load_backend()
        
    def load_backend(self):
        """Carga o recarga el módulo backend"""
        with self.lock:
            try:
                if self.yatusabe:
                    self.logger.info("🔄 Recargando backend.yatusabe...")
                    importlib.reload(self.yatusabe)
                else:
                    self.logger.info("📦 Cargando backend.yatusabe...")
                    import backend.yatusabe as yatusabe
                    self.yatusabe = yatusabe
                    
                self.logger.info("✅ Backend cargado correctamente")
                return True
            except Exception as e:
                self.logger.exception(f"❌ Error cargando backend: {e}")
                return False
    
    def reload(self):
        """Recarga el backend"""
        return self.load_backend()
    
    def run(self, stop_event):
        """Ejecuta el backend"""
        if not self.yatusabe:
            self.logger.error("Backend no está cargado")
            return
            
        stop_thread = threading.Thread(
            target=lambda: (
                stop_event.wait(),
                self.yatusabe.detener() if hasattr(self.yatusabe, "detener") else None,
            ),
            name="backend-stop-watcher",
            daemon=True,
        )
        stop_thread.start()
        try:
            if hasattr(self.yatusabe, "escuchar"):
                self.logger.info("🚀 Iniciando yatusabe.escuchar()...")
                self.yatusabe.escuchar()
            else:
                self.logger.error("backend.yatusabe no tiene 'escuchar'")
        except Exception as e:
            self.logger.exception(f"Error en yatusabe: {e}")
        finally:
            if hasattr(self.yatusabe, "cleanup"):
                self.yatusabe.cleanup()


def run_backend_with_reload(stop_event: threading.Event, backend_ready_event: threading.Event, 
                            hotreload: bool = False):
    """Ejecuta backend con opción de hot-reloading"""
    logger = logging.getLogger("backend_runner")
    backend = ReloadableBackend()
    
    if not backend.yatusabe:
        backend_ready_event.set()
        return
    
    # Si hotreload está activo, configurar watchdog
    observer = None
    if hotreload:
        def reload_backend_module(module_name, file_path):
            if 'backend' in module_name:
                logger.info(f"🔄 Recargando backend debido a cambio en {module_name}")
                backend.reload()
        
        handler = CodeReloadHandler(reload_backend_module)
        observer = Observer()
        backend_path = os.path.join(PROJECT_ROOT, "backend")
        observer.schedule(handler, backend_path, recursive=True)
        observer.start()
        logger.info(f"👁️  Observando cambios en: {backend_path}")
    
    # Ejecutar backend en thread separado
    def _run():
        backend.run(stop_event)
        backend_ready_event.set()
    
    th = threading.Thread(target=_run, name="yatusabe-thread", daemon=True)
    th.start()
    
    # Esperar hasta stop o finalización
    while not stop_event.is_set():
        if backend_ready_event.is_set():
            break
        time.sleep(0.5)
    
    if observer:
        observer.stop()
        observer.join()


def run_frontend(gui_module_path: str, hotreload: bool = False):
    """
    Ejecuta el frontend con opción de hot-reloading
    """
    logger = logging.getLogger("frontend_runner")
    logger.info(f"Importando frontend: {gui_module_path}")
    
    if hotreload:
        logger.warning("⚠️  Hot-reload en frontend puede causar problemas con GUI. "
                      "Se recomienda solo para backend.")
    
    mod = __import__(gui_module_path, fromlist=["*"])
    if hasattr(mod, "main"):
        logger.info(f"Llamando {gui_module_path}.main()")
        mod.main()   
    else:
        logger.error(f"El módulo {gui_module_path} no tiene función main().")
        raise RuntimeError("Frontend no tiene main()")


def main():
    parser = argparse.ArgumentParser(description="Lanzador para yatusabe + frontend con hot-reloading")
    parser.add_argument("--nogui", action="store_true", help="No arrancar interfaz gráfica (solo backend).")
    parser.add_argument("--backend-only", action="store_true", help="Solo backend.")
    parser.add_argument("--frontend-only", action="store_true", help="Solo frontend.")
    parser.add_argument("--debug", action="store_true", help="Modo debug (logging DEBUG).")
    parser.add_argument("--hotreload", action="store_true", 
                       help="🔥 Activar hot-reloading: recarga automática al modificar código")
    parser.add_argument("--watch-frontend", action="store_true",
                       help="Observar también cambios en frontend (experimental)")
    args = parser.parse_args()

    setup_logging(debug=args.debug)
    logger = logging.getLogger("run_all")
    
    if args.hotreload:
        logger.info("🔥 HOT-RELOAD ACTIVADO - Los cambios se recargarán automáticamente")
    
    logger.info("Iniciando run_all.py")
    preflight_checks()
    check_imports(["vosk", "pyaudio", "pygame", "live2d", "pyautogui"])

    stop_event = threading.Event()
    backend_ready_event = threading.Event()

    # Señales para shutdown ordenado
    def _signal_handler(signum, frame):
        logger.info(f"Señal recibida ({signum}). Iniciando cierre ordenado...")
        stop_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _signal_handler)
    try:
        signal.signal(signal.SIGTERM, _signal_handler)
    except Exception:
        pass

    # Lanzar backend si procede
    backend_thread = None
    backend_process = None
    if not args.frontend_only and not args.backend_only:
        logger.info("Arrancando backend (yatusabe) en background...")
        backend_command = [
            sys.executable,
            os.path.abspath(__file__),
            "--backend-only",
        ]
        if args.hotreload:
            backend_command.append("--hotreload")
        if args.debug:
            backend_command.append("--debug")
        backend_process = iniciar_en_terminal(
            backend_command,
            PROJECT_ROOT,
        )

    # Si solo backend, esperar hasta que stop_event sea activado
    if args.backend_only:
        logger.info("Modo backend-only: esperando señal para detener...")
        logger.info("💡 Presiona Ctrl+C para detener")
        backend_thread = threading.Thread(
            target=run_backend_with_reload,
            args=(stop_event, backend_ready_event, args.hotreload),
            name="backend-starter",
            daemon=True,
        )
        backend_thread.start()
        try:
            while not stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            stop_event.set()
        finally:
            if backend_thread:
                backend_thread.join(timeout=8)
        logger.info("Terminando backend-only.")
        return

    if args.nogui:
        logger.info("--nogui especificado: no se arranca frontend. Esperando shutdown...")
        try:
            while backend_process and backend_process.poll() is None:
                time.sleep(0.5)
        except KeyboardInterrupt:
            cerrar_terminal(backend_process)
        return

    # Lanzar frontend (GUI) en hilo principal
    if not args.backend_only:
        try:
            gui_module = "frontend.Diseno.bonito.main"
            logger.info("Iniciando frontend (GUI). Esto bloqueará el hilo principal hasta que se cierre la ventana.")
            run_frontend(gui_module, args.hotreload and args.watch_frontend)
        except Exception as e:
            logger.exception(f"Error al iniciar frontend: {e}")
            stop_event.set()
        finally:
            logger.info("Frontend finalizó. Solicitando parada del backend...")
            cerrar_terminal(backend_process)
            logger.info("run_all.py finalizado.")


if __name__ == "__main__":
    main()