"""
baseDatos.py
-------------
Capa de persistencia pura del asistente.
Su única responsabilidad es crear tablas, guardar, actualizar, eliminar y leer datos.
No analiza intenciones ni estructura semántica.
"""
import sqlite3
import threading
from datetime import datetime, timedelta

class BaseDeDatos:
    def __init__(self, db_path: str = "backend/Datos/BD/asistente.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.crear_tablas()

    # ------------------------------------------------------
    # 🔧 CREACIÓN DE TABLAS
    # ------------------------------------------------------
    def crear_tablas(self):
        """Crea todas las tablas necesarias para la memoria del asistente."""
        with self._lock:
            # Tabla para eventos (fechas, recordatorios, citas)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    descripcion TEXT NOT NULL,
                    fecha TEXT NOT NULL,
                    importancia REAL DEFAULT 0.5,
                    creado_en TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Tabla para hechos o recuerdos (datos del usuario, afirmaciones, etc.)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS hechos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    texto TEXT NOT NULL,
                    tipo TEXT DEFAULT 'fact',
                    entidad TEXT,
                    importancia REAL DEFAULT 0.5,
                    contexto TEXT,
                    creado_en TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Tabla para información útil (temporal o contextual)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS informacion_util (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contenido TEXT NOT NULL,
                    fecha_creacion TEXT DEFAULT CURRENT_TIMESTAMP,
                    fecha_expiracion TEXT,
                    importancia REAL DEFAULT 0.3
                )
            ''')

            self.conn.commit()

    # ------------------------------------------------------
    # 💾 INSERCIÓN DE DATOS
    # ------------------------------------------------------
    def agregar_evento(self, descripcion: str, fecha: str, importancia: float = 0.6):
        with self._lock:
            self.cursor.execute(
                'INSERT INTO eventos (descripcion, fecha, importancia) VALUES (?, ?, ?)',
                (descripcion, fecha, importancia)
            )
            self.conn.commit()

    def agregar_hecho(self, texto: str, entidad: str = None, tipo: str = "fact",
                      importancia: float = 0.5, contexto: str = None):
        with self._lock:
            self.cursor.execute(
                'INSERT INTO hechos (texto, tipo, entidad, importancia, contexto) VALUES (?, ?, ?, ?, ?)',
                (texto, tipo, entidad, importancia, contexto)
            )
            self.conn.commit()

    def agregar_informacion_util(self, contenido: str, dias_expiracion: int = 7, importancia: float = 0.4):
        fecha_expiracion = (datetime.now() + timedelta(days=dias_expiracion)).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self.cursor.execute(
                'INSERT INTO informacion_util (contenido, fecha_expiracion, importancia) VALUES (?, ?, ?)',
                (contenido, fecha_expiracion, importancia)
            )
            self.conn.commit()

    # ------------------------------------------------------
    # 🔍 CONSULTAS DE LECTURA
    # ------------------------------------------------------
    def obtener_eventos_proximos(self, horas: int = 24):
        """Devuelve eventos próximos dentro de las próximas X horas."""
        ahora = datetime.now()
        limite = (ahora + timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self.cursor.execute(
                'SELECT descripcion, fecha FROM eventos WHERE fecha BETWEEN ? AND ? ORDER BY fecha ASC',
                (ahora.strftime("%Y-%m-%d %H:%M:%S"), limite)
            )
            return self.cursor.fetchall()

    def obtener_hechos(self, entidad: str = None, limite: int = 10):
        """Obtiene hechos generales o filtrados por entidad."""
        with self._lock:
            if entidad:
                self.cursor.execute(
                    'SELECT texto, tipo, importancia FROM hechos WHERE entidad = ? ORDER BY importancia DESC LIMIT ?',
                    (entidad, limite)
                )
            else:
                self.cursor.execute(
                    'SELECT texto, tipo, importancia FROM hechos ORDER BY importancia DESC LIMIT ?',
                    (limite,)
                )
            return self.cursor.fetchall()

    def obtener_informacion_no_expirada(self):
        """Devuelve la información útil que todavía no caduca."""
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self.cursor.execute(
                'SELECT contenido FROM informacion_util WHERE fecha_expiracion > ? ORDER BY fecha_expiracion ASC',
                (ahora,)
            )
            return self.cursor.fetchall()

    # ------------------------------------------------------
    # 🧹 ELIMINACIÓN Y MANTENIMIENTO
    # ------------------------------------------------------
    def eliminar_expirados(self):
        """Elimina información útil o eventos pasados ya no relevantes."""
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._lock:
            self.cursor.execute('DELETE FROM informacion_util WHERE fecha_expiracion <= ?', (ahora,))
            self.cursor.execute('DELETE FROM eventos WHERE fecha <= ?', (ahora,))
            self.conn.commit()

    def eliminar_por_id(self, tabla: str, id_: int):
        """Elimina un registro específico por ID en la tabla dada."""
        if tabla not in ["eventos", "hechos", "informacion_util", "emociones"]:
            raise ValueError(f"Tabla no válida: {tabla}")
        with self._lock:
            self.cursor.execute(f'DELETE FROM {tabla} WHERE id = ?', (id_,))
            self.conn.commit()

    # ------------------------------------------------------
    # 🧾 UTILIDADES
    # ------------------------------------------------------
    def buscar(self, palabra: str):
        """Busca coincidencias en todas las tablas."""
        like_query = f"%{palabra.lower()}%"
        resultados = {}
        with self._lock:
            self.cursor.execute('SELECT descripcion FROM eventos WHERE LOWER(descripcion) LIKE ?', (like_query,))
            resultados["eventos"] = [r[0] for r in self.cursor.fetchall()]

            self.cursor.execute('SELECT texto FROM hechos WHERE LOWER(texto) LIKE ?', (like_query,))
            resultados["hechos"] = [r[0] for r in self.cursor.fetchall()]

            self.cursor.execute('SELECT contenido FROM informacion_util WHERE LOWER(contenido) LIKE ?', (like_query,))
            resultados["informacion_util"] = [r[0] for r in self.cursor.fetchall()]
        return resultados

    def cerrar(self):
        """Cierra la conexión de forma segura."""
        with self._lock:
            self.conn.close()
