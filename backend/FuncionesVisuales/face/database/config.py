from pydantic import BaseModel
from backend.FuncionesVisuales.face.database.users_path import users_path, users_check_path
from backend.FuncionesVisuales.face.database.faces_path import faces_path

class DataBasePaths(BaseModel):
    faces: str = faces_path
    users: str = users_path
    check_users: str = users_check_path
