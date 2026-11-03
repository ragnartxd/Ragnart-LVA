import numpy as np
from typing import Tuple

from backend.FuncionesVisuales.face.face_processing.face_utils import FaceUtils
from backend.FuncionesVisuales.face.database.config import DataBasePaths


class FaceSignUp:
    def __init__(self):
        self.database = DataBasePaths()
        self.face_utilities = FaceUtils()
        
        # Variables para optimización
        self.frames_stable = 0
        self.REQUIRED_STABLE_FRAMES = 30  # Frames necesarios para estabilidad
        self.last_face_center = False

    def process(self, face_image: np.ndarray, user_name: str, user_code: str) -> Tuple[np.ndarray, bool, str, str]:
        """
        Procesa el frame para registro facial optimizado
        
        Args:
            face_image: Frame de la cámara
            user_code: Código único del usuario
            
        Returns:
            Tupla con (imagen_procesada, éxito_registro, mensaje)
        """
        # Validación temprana del user_code
        if not user_code or not user_code.strip():
            return face_image, False, 'código de usuario inválido!'

        # Step 1: Detección de rostro (early return si falla)
        check_face_detect, face_info, face_save = self.face_utilities.check_face(face_image)
        if not check_face_detect:
            self._reset_stability()
            return face_image, False, '¡No face detected!'

        # Step 2: Face mesh (early return si falla)
        check_face_mesh, face_mesh_info = self.face_utilities.face_mesh(face_image)
        if not check_face_mesh:
            self._reset_stability()
            return face_image, False, '¡No face mesh detected!'

        # Step 3: Extraer puntos del mesh
        face_mesh_points_list = self.face_utilities.extract_face_mesh(face_image, face_mesh_info)

        # Step 4: Verificar centrado del rostro
        check_face_center = self.face_utilities.check_face_center(face_mesh_points_list)

        # Step 5: Mostrar estado actual
        self.face_utilities.show_state_signup(face_image, state=check_face_center)

        # Early return si el rostro no está centrado
        if not check_face_center:
            self._reset_stability()
            return face_image, False, 'centra el rostro por favor'

        # Step 6: Verificar estabilidad del rostro centrado
        if not self._check_stability(check_face_center):
            frames_left = self.REQUIRED_STABLE_FRAMES - self.frames_stable
            return face_image, False, f'Mantente firme... {frames_left} frames restantes'

        # Step 7: Procesar guardado del rostro
        try:
            # Extraer información del rostro
            face_bbox = self.face_utilities.extract_face_bbox(face_image, face_info)
            face_points = self.face_utilities.extract_face_points(face_image, face_info)

            # Recortar rostro
            face_crop = self.face_utilities.face_crop(face_save, face_bbox)

            # Validar que el crop sea válido
            if face_crop.size == 0:
                self._reset_stability()
                return face_image, False, 'Recorte de rostro inválido, intenta de nuevo'

            # Verificar si el usuario ya existe
            if self._user_exists(user_code) or self._user_exists(user_name):
                return face_image, False, f'El usuario {user_name} ya existe!'

            # Step 8: Guardar rostro
            check_save_image = self.face_utilities.save_face(face_crop, user_name, self.database.faces, user_code)
            
            if check_save_image:
                self._reset_stability()
                return face_image, True, f'El usuario {user_name} se registró con éxito!'
            else:
                return face_image, False, 'Error al guardar el rostro, intenta de nuevo'

        except Exception as e:
            print(f"Error durante el registro facial: {e}")
            self._reset_stability()
            return face_image, False, 'Error de registro, intenta de nuevo'

    def _check_stability(self, current_face_center: bool) -> bool:
        """
        Verifica la estabilidad del rostro centrado
        
        Args:
            current_face_center: Estado actual del centrado
            
        Returns:
            True si el rostro ha estado estable el tiempo suficiente
        """
        if current_face_center and self.last_face_center:
            self.frames_stable += 1
        else:
            self.frames_stable = 0
            
        self.last_face_center = current_face_center
        return self.frames_stable >= self.REQUIRED_STABLE_FRAMES

    def _reset_stability(self):
        """Resetea los contadores de estabilidad"""
        self.frames_stable = 0
        self.last_face_center = False

    def _user_exists(self, user_name: str) -> bool:
        """
        Verifica si el usuario ya existe en la base de datos
        
        Args:
            user_name: Nombre del usuario
            
        Returns:
            True si el usuario ya existe
        """
        try:
            import os
            user_file_path = os.path.join(self.database.faces, f"{user_name}.png")
            return os.path.exists(user_file_path)
        except Exception:
            return False

    def reset(self):
        """Resetea el estado del registro para nueva sesión"""
        self._reset_stability()