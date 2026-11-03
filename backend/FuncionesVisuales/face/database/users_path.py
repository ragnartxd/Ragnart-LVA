import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

users_path: str = os.path.join(BASE_DIR, 'users')
users_check_path: str = users_path  # si quieres lo mismo, o apunta a 'users'/
