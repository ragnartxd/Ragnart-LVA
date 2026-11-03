"""Inicio y cierre de procesos con consolas separadas en Windows."""

import os
import signal
import subprocess


def iniciar_en_terminal(comando, cwd):
    opciones = {}
    if os.name == "nt":
        opciones["creationflags"] = (
            subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    return subprocess.Popen(comando, cwd=cwd, **opciones)


def cerrar_terminal(proceso, timeout=8):
    if proceso is None or proceso.poll() is not None:
        return

    if os.name == "nt":
        try:
            proceso.send_signal(signal.CTRL_BREAK_EVENT)
            proceso.wait(timeout=timeout)
            return
        except (OSError, subprocess.TimeoutExpired):
            pass

    proceso.terminate()
    proceso.wait(timeout=timeout)
