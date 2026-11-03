import os
import sys
from tkinter import *
import logging as log

log.basicConfig(level=log.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import GraphicalUserInterface

def activar():
    app = GraphicalUserInterface(Tk())
    app.frame.mainloop()

if __name__ == "__main__":
    log.info("Starting the example application...")
    activar()
    log.info("Example application has been started.")
