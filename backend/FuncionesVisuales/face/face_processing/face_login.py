import numpy as np
from typing import Tuple

from backend.FuncionesVisuales.face.face_processing.face_utils import FaceUtils
from backend.FuncionesVisuales.face.database.config import DataBasePaths


class FaceLogIn:
    def __init__(self):
        self.face_utilities = FaceUtils()
        self.database = DataBasePaths()

        self.matcher = None
        self.comparison = False
        self.cont_frame = 0
        
        # Constantes para optimización
        self.REQUIRED_FRAMES = 48
        self.PROCESSING_MESSAGE = 'procesando rostro, por favor espera...'

    def process(self, face_image: np.ndarray) -> Tuple[np.ndarray, bool, str]:
        """
        Procesa el frame para login facial optimizado
        
        Args:
            face_image: Frame de la cámara
            
        Returns:
            Tupla con (imagen_procesada, estado_matcher, mensaje)
        """
        # Step 1: Detección de rostro (early return si falla)
        check_face_detect, face_info, face_save = self.face_utilities.check_face(face_image)
        if not check_face_detect:
            return face_image, self.matcher, '¡No se detectó rostro!'

        # Step 2: Face mesh (early return si falla)
        check_face_mesh, face_mesh_info = self.face_utilities.face_mesh(face_image)
        if not check_face_mesh:
            return face_image, self.matcher, '¡No se detectó face mesh!'

        # Step 3: Extraer puntos del mesh
        face_mesh_points_list = self.face_utilities.extract_face_mesh(face_image, face_mesh_info)

        # Step 4: Verificar centrado del rostro
        check_face_center = self.face_utilities.check_face_center(face_mesh_points_list)

        # Step 5: Mostrar estado actual
        self.face_utilities.show_state_login(face_image, state=self.matcher)

        # Early return si el rostro no está centrado
        if not check_face_center:
            self.cont_frame = 0  # Reset contador si no está centrado
            return face_image, self.matcher, 'Centre el rostro en la cámara'

        # Step 6: Contar frames solo si está centrado
        self.cont_frame += 1
        
        # Procesar solo cuando se alcance el número requerido de frames
        if self.cont_frame < self.REQUIRED_FRAMES:
            frames_left = self.REQUIRED_FRAMES - self.cont_frame
            return face_image, self.matcher, f'por favor espere {frames_left} frames más'

        # Step 7: Procesar face matching (solo una vez)
        if self.comparison or self.matcher is not None:
            return face_image, self.matcher, self.PROCESSING_MESSAGE

        # Extraer información del rostro
        face_bbox = self.face_utilities.extract_face_bbox(face_image, face_info)
        face_points = self.face_utilities.extract_face_points(face_image, face_info)

        # Recortar rostro
        face_crop = self.face_utilities.face_crop(face_save, face_bbox)

        # Validar que el crop sea válido
        if face_crop.size == 0:
            self.cont_frame = 0  # Reset para reintentar
            return face_image, self.matcher, 'Recorte de rostro inválido, intente de nuevo'

        # Leer base de datos
        faces_database, names_database, info = self.face_utilities.read_face_database(self.database.faces)

        # Verificar si hay caras en la base de datos
        if not faces_database:
            return face_image, self.matcher, 'Base de datos vacía - registre primero'

        # Marcar que se está comparando
        self.comparison = True

        # Step 8: Comparar rostros
        try:
            self.matcher, user_name = self.face_utilities.face_matching(face_crop, faces_database, names_database)

            if self.matcher:
                # Step 9: Guardar registro de acceso
                
                self.face_utilities.user_check_in(user_name, self.database.users)
                return face_image, self.matcher, f'Bienvenido {user_name}!', user_name
            else:
                return face_image, self.matcher, 'Acceso denegado - rostro no reconocido'

        except Exception as e:
            print(f"Error durante el emparejamiento de rostros: {e}")
            # Reset para permitir reintentar
            self.comparison = False
            self.cont_frame = 0
            return face_image, self.matcher, 'proceso fallido, intente de nuevo'

    def reset(self):
        """Resetea el estado del login para nueva sesión"""
        self.matcher = None
        self.comparison = False
        self.cont_frame = 0
        self.face_utilities.user_registered = False