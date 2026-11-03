"""
main.py - lanzador unificado para backend (yatusabe) + frontend (Live2D o Pygame).
"""

import os
import sys
import logging
import argparse
import time

import os, sys

if '__file__' in globals():
    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
else:
    PROJECT_ROOT = os.path.abspath(os.getcwd())


# Asegurar imports relativos al proyecto
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.terminales import cerrar_terminal, iniciar_en_terminal

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

def run_frontend(gui_module_path: str):
    """
    Ejecuta el frontend en hilo principal.
    Se espera que el módulo tenga una función main().
    """
    logger = logging.getLogger("frontend_runner")
    logger.info("Importando frontend: %s", gui_module_path)
    mod = __import__(gui_module_path, fromlist=["*"])
    if hasattr(mod, "main"):
        logger.info("Llamando %s.main()", gui_module_path)
        mod.main()   
    else:
        logger.error("El módulo %s no tiene función main().", gui_module_path)
        raise RuntimeError("Frontend no tiene main()")

def main():
    parser = argparse.ArgumentParser(description="Lanzador para yatusabe + frontend")
    parser.add_argument("--nogui", action="store_true", help="No arrancar interfaz gráfica (solo backend).")
    parser.add_argument("--backend-only", action="store_true", help="Solo backend.")
    parser.add_argument("--frontend-only", action="store_true", help="Solo frontend.")
    parser.add_argument("--debug", action="store_true", help="Modo debug (logging DEBUG).")
    args = parser.parse_args()

    setup_logging(debug=args.debug)
    logger = logging.getLogger("run_all")
    logger.info("Iniciando run_all.py")
    preflight_checks()

    check_imports(["vosk", "pyaudio", "pygame", "live2d", "pyautogui"])

    if args.backend_only:
        try:
            import backend.yatusabe as yatusabe
            yatusabe.escuchar()
        except KeyboardInterrupt:
            logger.info("Cerrando backend...")
        finally:
            if "yatusabe" in locals():
                yatusabe.cleanup()
        return

    backend_process = None
    if not args.frontend_only:
        logger.info("Arrancando backend en una terminal separada...")
        backend_process = iniciar_en_terminal(
            [sys.executable, "-m", "backend.yatusabe"],
            PROJECT_ROOT,
        )

    if not args.nogui:
        try:
            gui_module = "frontend.Diseno.bonito.main"
            logger.info("Iniciando frontend (GUI) en esta terminal.")
            run_frontend(gui_module)
        finally:
            logger.info("Frontend finalizó. Cerrando el backend...")
            cerrar_terminal(backend_process)
            logger.info("run_all.py finalizado.")
    elif backend_process:
        try:
            while backend_process.poll() is None:
                time.sleep(0.5)
        except KeyboardInterrupt:
            cerrar_terminal(backend_process)

if __name__ == "__main__":
    main()
