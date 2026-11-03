import os

# Directorio donde está este archivo
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ruta absoluta a la carpeta de imágenes
faces_path: str = os.path.join(BASE_DIR, 'faces')
