import subprocess
import sys
from pathlib import Path


def abrir_configuracion():
    project_root = Path(__file__).resolve().parents[2]
    subprocess.Popen(
        [sys.executable, "-m", "frontend.interfaz_logica"],
        cwd=project_root,
    )
    return "Abriendo el panel de configuración."
