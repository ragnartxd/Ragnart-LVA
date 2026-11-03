"""
gestor_memoria_v2.py
--------------------
Gestor principal del sistema de memoria híbrido cognitivo.

MEJORAS sobre v1:
✅ Integración con ExtractorTripletas
✅ Integración con IndicesEstructurales
✅ Búsqueda híbrida: filtro estructural + re-ranking semántico
✅ Almacenamiento triple: FAISS + Índices + SQLite
✅ Manejo robusto de entrada por voz

MANTIENE:
- Thread safety completo
- Caché de embeddings (LRU)
- Persistencia de índice FAISS
- Consolidación automática
- Logging estructurado
"""

import time
import threading
import logging
from datetime import datetime
import numpy as np
import faiss
import json
import os
from collections import defaultdict
from typing import Dict, List, Tuple

# Imports del sistema v1 (mantener compatibilidad)
from backend.Datos.taxonomia_memoria import TaxonomiaMemoria
from backend.Datos.cache_embeddings import CacheEmbeddings
from backend.utils.json_storage import guardar_json_atomico

# Imports de componentes nuevos
from backend.Datos.analizador_semantico import AnalizadorSemanticoV2
from backend.Datos.indices_estructurales import IndicesEstructurales, RegistroMemoria
from backend.utils.utils_embedding import cargar_modelo_embeddings_general

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('memoria_v2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BD_DIR = os.path.join(BASE_DIR, "..", "Datos", "BD")


class GestorMemoriaV2:
    """
    Gestor principal del sistema de memoria híbrido cognitivo.
    
    Combina:
    1. Búsqueda semántica por embeddings (FAISS)
    2. Búsqueda estructural por tripletas y entidades
    3. Re-ranking híbrido para resultados óptimos
    
    Thread-safe y optimizado para asistente virtual local.
    """
    
    def __init__(self, db_instance=None,
                 dim_embeddings: int = 384,
                 ruta_taxonomia: str = None,
                 ruta_index: str = None,
                 ruta_metadata: str = None,
                 ruta_indices_struct: str = None):
        
        # Rutas absolutas por defecto
        if ruta_taxonomia is None:
            ruta_taxonomia = os.path.join(BD_DIR, "taxonomia_memoria.json")
        if ruta_index is None:
            ruta_index = os.path.join(BD_DIR, "memoria_faiss_v2.index")
        if ruta_metadata is None:
            ruta_metadata = os.path.join(BD_DIR, "metadata_faiss_v2.json")
        if ruta_indices_struct is None:
            ruta_indices_struct = os.path.join(BD_DIR, "indices_estructurales.json")
        """
        Inicializa el gestor de memoria v2.
        
        Args:
            db_instance: Instancia de BaseDeDatos
            modelo_embeddings: Nombre del modelo de SentenceTransformer
            dim_embeddings: Dimensión de los embeddings
            ruta_taxonomia: Ruta al archivo JSON de taxonomía
            ruta_index: Ruta para persistir el índice FAISS
            ruta_metadata: Ruta para persistir metadata
            ruta_indices_struct: Ruta para persistir índices estructurales
        """
        logger.info("🧠 Inicializando GestorMemoriaV2 (Sistema Híbrido)...")
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Base de datos — crear instancia por defecto si no se provee una
        if db_instance is None:
            from backend.Datos.baseDatos import BaseDeDatos
            db_instance = BaseDeDatos()
            logger.info("ℹ️ db_instance no provisto, se creó BaseDeDatos por defecto")
        self.db = db_instance
        self._configurar_wal_mode()
        
        # Rutas de persistencia
        self.ruta_index = ruta_index
        self.ruta_metadata = ruta_metadata
        self.ruta_indices_struct = ruta_indices_struct
        
        # Modelo de embeddings
        self.dim_embeddings = dim_embeddings
        self.modelo = self._cargar_modelo_embeddings_memoria()
        
        # Componentes del sistema
        self.taxonomia = TaxonomiaMemoria(ruta_taxonomia)
        self.cache_embeddings = CacheEmbeddings(max_size=2000)
        self.analizador = AnalizadorSemanticoV2()  # NUEVO: v2 con tripletas
        self.indices_estructurales = IndicesEstructurales()  # NUEVO
        
        # Índice vectorial FAISS
        self.index = self._inicializar_index()
        self.id_to_metadata = {}
        self.next_id = 0
        
        # Cargar datos persistidos
        self._cargar_index_persistido()
        self._cargar_indices_estructurales()
        
        # Memoria de corto plazo (volátil)
        self.memoria_corta = []
        self.max_memoria_corta = 50
        
        # Estadísticas
        self.stats = defaultdict(int)
        self.stats["inicio"] = datetime.now().isoformat()
        
        # Timer de consolidación automática
        self._iniciar_consolidacion_automatica()
        
        logger.info("✅ GestorMemoriaV2 inicializado correctamente")
    
    def _configurar_wal_mode(self):
        """Configura SQLite en modo WAL para mejor concurrencia"""
        try:
            conn = self.db.conn
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.commit()
            logger.info("✅ SQLite configurado en modo WAL")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo configurar WAL mode: {e}")
    
    def _cargar_modelo_embeddings_memoria(self):
        """Carga el modelo de embeddings con manejo robusto de errores"""
        try:
            modelo = cargar_modelo_embeddings_general()
            return modelo
        except Exception as e:
            logger.error(f"❌ Error cargando modelo de embeddings: {e}")
            raise RuntimeError(
                f"No se pudo cargar el modelo 'embedding'. "
                "Verifica tu conexión a internet y que el modelo exista."
            ) from e
    
    def _inicializar_index(self) -> faiss.Index:
        """Inicializa el índice FAISS con métricas coseno"""
        try:
            index = faiss.IndexFlatIP(self.dim_embeddings)
            logger.info(f"✅ Índice FAISS inicializado (dim={self.dim_embeddings})")
            return index
        except Exception as e:
            logger.error(f"❌ Error inicializando índice FAISS: {e}")
            raise
    
    def _cargar_index_persistido(self):
        """Carga el índice FAISS y metadata desde disco si existen"""
        try:
            if os.path.exists(self.ruta_index) and os.path.exists(self.ruta_metadata):
                logger.info("📂 Cargando índice FAISS persistido...")
                
                self.index = faiss.read_index(self.ruta_index)
                
                with open(self.ruta_metadata, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.id_to_metadata = data.get("metadata", {})
                    self.next_id = data.get("next_id", 0)
                
                # FIX 1: Validar sincronización entre FAISS y next_id
                if self.index.ntotal != self.next_id:
                    logger.warning(
                        f"⚠️ Desincronización detectada: FAISS tiene {self.index.ntotal} vectores "
                        f"pero next_id={self.next_id}. Corrigiendo next_id."
                    )
                    self.next_id = self.index.ntotal
                
                logger.info(f"✅ Índice FAISS cargado: {self.index.ntotal} vectores")
            else:
                logger.info("ℹ️ No hay índice FAISS persistido, iniciando desde cero")
        except Exception as e:
            logger.error(f"⚠️ Error cargando índice FAISS: {e}")
            self.index = self._inicializar_index()
            self.id_to_metadata = {}
            self.next_id = 0
    
    def _cargar_indices_estructurales(self):
        """NUEVO: Carga índices estructurales desde disco"""
        try:
            if os.path.exists(self.ruta_indices_struct):
                self.indices_estructurales.cargar(self.ruta_indices_struct)
                logger.info("✅ Índices estructurales cargados")
            else:
                logger.info("ℹ️ No hay índices estructurales, iniciando desde cero")
        except Exception as e:
            logger.error(f"⚠️ Error cargando índices estructurales: {e}")
    
    def _persist_all(self):
        """Persiste todos los índices: FAISS + Estructurales"""
        with self._lock:
            # Persistir FAISS
            try:
                os.makedirs(os.path.dirname(self.ruta_index), exist_ok=True)
                faiss.write_index(self.index, self.ruta_index)
                
                data = {
                    "metadata": self.id_to_metadata,
                    "next_id": self.next_id,
                    "timestamp": datetime.now().isoformat()
                }
                guardar_json_atomico(
                    self.ruta_metadata,
                    data,
                    indent=2,
                    ensure_ascii=False,
                    trailing_newline=False,
                )
                
                logger.info(f"💾 Índice FAISS persistido: {self.index.ntotal} vectores")
            except Exception as e:
                logger.error(f"❌ Error persistiendo FAISS: {e}")
            
            # Persistir índices estructurales
            try:
                self.indices_estructurales.persistir(self.ruta_indices_struct)
            except Exception as e:
                logger.error(f"❌ Error persistiendo índices estructurales: {e}")
    
    def _iniciar_consolidacion_automatica(self):
        """Inicia timer para consolidación automática cada 5 minutos"""
        def consolidar_periodicamente():
            while True:
                time.sleep(300)  # 5 minutos
                try:
                    self.consolidar_memoria()
                except Exception as e:
                    logger.error(f"⚠️ Error en consolidación automática: {e}")
        
        timer_thread = threading.Thread(
            target=consolidar_periodicamente,
            daemon=True,
            name="ConsolidacionTimer"
        )
        timer_thread.start()
        logger.info("⏰ Timer de consolidación automática iniciado")
    
    def _embed(self, texto: str) -> np.ndarray:
        """Genera embedding para el texto usando caché"""
        with self._lock:
            # Intentar obtener del caché
            cached = self.cache_embeddings.get(texto)
            if cached is not None:
                self.stats["cache_hits"] += 1
                return cached
            
            # Generar nuevo embedding
            self.stats["cache_misses"] += 1
            embedding = self.modelo.encode(texto, convert_to_numpy=True)
            
            # Normalizar para similitud coseno
            embedding = embedding / np.linalg.norm(embedding)
            
            # Guardar en caché
            self.cache_embeddings.set(texto, embedding)
            
            return embedding
    
    def procesar_texto(self, texto: str, fuente: str = "user",
                      forzar_guardado: bool = False) -> Dict:
        """
        Procesa texto y lo guarda en el sistema de memoria híbrido.
        
        MEJORA: Ahora extrae y almacena tripletas + entidades.
        
        Args:
            texto: Texto a procesar
            fuente: Origen del texto
            forzar_guardado: Si True, guarda incluso textos de baja importancia
            
        Returns:
            Dict con resultado del procesamiento
        """
        if not texto or not texto.strip():
            return {"error": "Texto vacío"}
        
        # ✅ NUEVO: descartar preguntas, no son hechos
        CATEGORIAS_NO_GUARDAR = {"pregunta", "conversacion_casual", "instruccion"}
        categoria_rapida, _, _ = self.taxonomia.clasificar(texto)
        if categoria_rapida in CATEGORIAS_NO_GUARDAR and not forzar_guardado:
            logger.debug(f"⏭️ Texto descartado (cat={categoria_rapida}): '{texto[:40]}'")
            return {
                "procesado": False,
                "importancia": 0.0,
                "tipo_memoria": "efimero",
                "categoria": categoria_rapida,
                "num_tripletas": 0,
                "num_entidades": 0,
                "guardado_largo_plazo": False
            }
        
        with self._lock:
            self.stats["textos_procesados"] += 1
            
            # Analizar con el analizador v2 (incluye tripletas)
            analisis = self.analizador.analizar(texto)
            
            importancia = analisis["importancia"]
            tipo_memoria = analisis["tipo_memoria"]
            categoria = self._inferir_categoria(analisis)
            
            # Obtener datos estructurados
            tripletas = analisis.get("tripletas", [])
            entidades = analisis.get("entidades", [])
            
            logger.info(
                f"📊 Texto procesado: imp={importancia:.2f}, "
                f"tipo={tipo_memoria}, cat={categoria}, "
                f"tripletas={len(tripletas)}, entidades={len(entidades)}"
            )
            
            # Agregar a memoria corta
            self.memoria_corta.append({
                "texto": texto,
                "fuente": fuente,
                "importancia": importancia,
                "etiqueta": categoria,
                "timestamp": datetime.now().isoformat(),
                "tripletas": tripletas,
                "entidades": entidades
            })
            
            # Limitar tamaño de memoria corta
            if len(self.memoria_corta) > self.max_memoria_corta:
                self.memoria_corta.pop(0)
            
            # Decidir si guardar en largo plazo
            umbral = 0.7 if not forzar_guardado else 0.0
            
            if importancia >= umbral or forzar_guardado:
                self._guardar_largo_plazo(
                    texto=texto,
                    fuente=fuente,
                    importancia=importancia,
                    categoria=categoria,
                    tipo_memoria=tipo_memoria,
                    tripletas=tripletas,
                    entidades=entidades,
                    metadata=analisis.get("metadata", {})
                )
            
            return {
                "procesado": True,
                "importancia": importancia,
                "tipo_memoria": tipo_memoria,
                "categoria": categoria,
                "num_tripletas": len(tripletas),
                "num_entidades": len(entidades),
                "guardado_largo_plazo": importancia >= umbral
            }
    
    def _inferir_categoria(self, analisis: Dict) -> str:
        """Infiere la categoría principal del análisis"""
        hechos = analisis.get("hechos_extraidos", [])
        if hechos:
            # FIX 3: evento_futuro tiene prioridad explícita para que llegue a la tabla eventos
            for hecho in hechos:
                if hecho.get("etiqueta") == "evento_futuro":
                    return "evento_futuro"
            # Para el resto, tomar la categoría del hecho de mayor importancia
            hecho_max = max(hechos, key=lambda h: h.get("importancia", 0))
            return hecho_max.get("etiqueta", "general")
        return "general"
    
    def _guardar_largo_plazo(self, texto: str, fuente: str, importancia: float,
                            categoria: str, tipo_memoria: str,
                            tripletas: List[Dict], entidades: List[Tuple[str, str]],
                            metadata: Dict):
        """
        Guarda en los tres sistemas de almacenamiento:
        1. FAISS (embeddings semánticos)
        2. IndicesEstructurales (tripletas + entidades)
        3. SQLite (persistencia tradicional)
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            # 1. Generar y guardar embedding en FAISS
            embedding = self._embed(texto)
            embedding_id = self.next_id
            
            self.index.add(np.array([embedding], dtype=np.float32))
            self.id_to_metadata[str(embedding_id)] = {
                "texto": texto,
                "fuente": fuente,
                "importancia": importancia,
                "categoria": categoria,
                "timestamp": timestamp
            }
            
            # 2. Guardar en índices estructurales
            self.indices_estructurales.agregar_registro(
                texto=texto,
                categoria=categoria,
                importancia=importancia,
                timestamp=timestamp,
                entidades=entidades,
                tripletas=tripletas,
                metadata=metadata,
                embedding_id=embedding_id
            )
            
            self.next_id += 1
            
            # 3. Guardar en SQLite (mantener compatibilidad)
            try:
                if categoria == "evento_futuro":
                    # FIX 3: buscar fecha en metadata o en los hechos extraídos
                    fecha_evento = metadata.get("fecha")
                    if not fecha_evento:
                        for hecho in metadata.get("hechos_extraidos", []):
                            if hecho.get("etiqueta") == "evento_futuro":
                                fecha_evento = hecho.get("metadata", {}).get("fecha")
                                if fecha_evento:
                                    break
                    if fecha_evento:
                        self.db.agregar_evento(
                            descripcion=texto,
                            fecha=fecha_evento,
                            importancia=importancia
                        )
                    else:
                        # Guardar como hecho si no hay fecha parseable
                        self.db.agregar_hecho(
                            texto=texto,
                            entidad=entidades[0][0] if entidades else None,
                            tipo=categoria,
                            importancia=importancia,
                            contexto=json.dumps(metadata)
                        )
                else:
                    self.db.agregar_hecho(
                        texto=texto,
                        entidad=entidades[0][0] if entidades else None,
                        tipo=categoria,
                        importancia=importancia,
                        contexto=json.dumps(metadata)
                    )
            except Exception as e:
                logger.error(f"⚠️ Error guardando en SQLite: {e}")
            
            # Actualizar estadísticas
            self.stats[f"etiqueta_{categoria}"] += 1
            
            logger.debug(
                f"💾 Guardado en largo plazo: '{texto[:50]}...' "
                f"(ID={embedding_id}, cat={categoria})"
            )
            try:
                self._persist_all()
            except Exception as e:
                logger.warning(f"⚠️ Error persistiendo después de guardar: {e}")
    
    def buscar_contexto_hibrido(self, query: str, top_k: int = 5,
                               filtros: Dict = None,
                               peso_estructural: float = 0.3,
                               peso_semantico: float = 0.7) -> List[Tuple[RegistroMemoria, float]]:
        """
        NUEVO: Búsqueda híbrida combinando filtros estructurales y semántica.
        
        Proceso:
        1. Analizar query (extraer tripletas/entidades)
        2. Aplicar filtros estructurales
        3. Búsqueda semántica en FAISS
        4. Re-ranking híbrido
        
        Args:
            query: Pregunta del usuario
            top_k: Número de resultados
            filtros: Filtros estructurales adicionales
            peso_estructural: Peso del score estructural [0-1]
            peso_semantico: Peso del score semántico [0-1]
            
        Returns:
            Lista de (RegistroMemoria, score_final) ordenada
        """
        with self._lock:
            self.stats["busquedas"] += 1

            if self.index.ntotal == 0:
                logger.debug("⚠️ Índice FAISS vacío, no hay contexto disponible")
                return []
            
            # Analizar query
            analisis_query = self.analizador.analizar(query)
            tripletas_query = analisis_query.get("tripletas", [])
            entidades_query = analisis_query.get("entidades", [])
            
            # Preparar filtros estructurales
            filtros_struct = filtros or {}
            
            # Agregar filtros inferidos de la query
            if tripletas_query and not filtros_struct.get("relacion"):
                # Usar relación de la primera tripleta
                filtros_struct["relacion"] = tripletas_query[0]["relacion_normalizada"]
            
            if entidades_query and not filtros_struct.get("entidad"):
                # Usar primera entidad
                filtros_struct["entidad"] = entidades_query[0][0]
            
            logger.debug(f"🔍 Búsqueda híbrida: filtros={filtros_struct}")
            
            # Búsqueda semántica en FAISS
            embedding_query = self._embed(query)
            D, I = self.index.search(
                np.array([embedding_query], dtype=np.float32),
                min(top_k * 3, self.index.ntotal)  # Buscar más candidatos
            )
            
            # Preparar scores semánticos
            ids_semanticos = I[0].tolist()
            scores_semanticos = {
                idx: float(score) 
                for idx, score in zip(ids_semanticos, D[0])
                if idx >= 0
            }
            
            # Búsqueda híbrida
            resultados = self.indices_estructurales.buscar_hibrida(
                filtros_estructurales=filtros_struct,
                ids_semanticos=ids_semanticos,
                scores_semanticos=scores_semanticos,
                limit=top_k,
                peso_estructural=peso_estructural,
                peso_semantico=peso_semantico
            )
            
            logger.info(
                f"✅ Búsqueda híbrida completada: {len(resultados)} resultados"
            )
            
            return resultados
    
    def buscar_estructural(self, sujeto: str = None, relacion: str = None,
                          objeto: str = None, limit: int = 10) -> List[RegistroMemoria]:
        """
        NUEVO: Búsqueda puramente estructural por tripletas.
        
        Args:
            sujeto: Filtro por sujeto
            relacion: Filtro por relación
            objeto: Filtro por objeto
            limit: Número máximo de resultados
            
        Returns:
            Lista de registros que cumplen los filtros
        """
        with self._lock:
            return self.indices_estructurales.buscar_tripleta(
                sujeto=sujeto,
                relacion=relacion,
                objeto=objeto,
                limit=limit
            )
    
    def buscar_por_entidad(self, entidad: str, limit: int = 10) -> List[RegistroMemoria]:
        """NUEVO: Busca todos los registros que mencionan una entidad"""
        with self._lock:
            return self.indices_estructurales.buscar_por_entidad(entidad, limit)
    
    def buscar_semantico(self, query: str, top_k: int = 10) -> List[Dict]:
        """Búsqueda puramente semántica (mantener compatibilidad v1)"""
        with self._lock:
            if self.index.ntotal == 0:
                return []
            
            embedding_query = self._embed(query)
            
            D, I = self.index.search(
                np.array([embedding_query], dtype=np.float32),
                min(top_k, self.index.ntotal)
            )
            
            resultados = []
            for idx, similitud in zip(I[0], D[0]):
                if idx < 0:
                    continue
                
                metadata = self.id_to_metadata.get(str(idx), {})
                resultados.append({
                    "texto": metadata.get("texto", ""),
                    "similitud": float(similitud),
                    "importancia": metadata.get("importancia", 0.5),
                    "categoria": metadata.get("categoria", "general")
                })
            
            return resultados

    # ── Adaptadores de compatibilidad con yatusabe.py ─────────────────────────

    def procesar_entrada(self, texto: str, resultado_procesador=None, **kwargs) -> str:
        """
        Adaptador: yatusabe.py llama gm.procesar_entrada(texto, resultado_procesador=...).
        Delega en procesar_texto() e ignora resultado_procesador (no relevante para memoria).
        Devuelve una cadena descriptiva del resultado para el log de yatusabe.
        """
        resultado = self.procesar_texto(texto, fuente="user")
        if resultado.get("error"):
            return "vacio"
        if resultado.get("guardado_largo_plazo"):
            return f"largo_plazo_{resultado.get('categoria', 'general')}"
        return "memoria_corta"

    def buscar_contexto(self, query: str, top_k: int = 5) -> Dict:
        """
        Adaptador: yatusabe.py llama gm.buscar_contexto(texto, top_k=5) y espera
        un dict con claves "hechos", "informacion_util", "eventos", "faiss", "memoria_corta".
        Reúne resultados de todas las fuentes disponibles.
        """
        self.stats["busquedas"] += 1
    
        # ✅ NUEVO: categorías que nunca deben llegar al LLM
        CATEGORIAS_EXCLUIR = {"pregunta", "conversacion_casual", "instruccion", "general"}
        
        resultado = {
            "hechos": [],
            "informacion_util": [],
            "eventos": [],
            "faiss": [],
            "memoria_corta": []
        }

        try:
            resultado["hechos"] = self.db.obtener_hechos(limite=top_k)
            resultado["informacion_util"] = self.db.obtener_informacion_no_expirada()
            resultado["eventos"] = self.db.obtener_eventos_proximos(horas=168)
        except Exception as e:
            logger.warning(f"⚠️ buscar_contexto: error consultando BD: {e}")

        try:
            if self.index.ntotal > 0:
                embedding_query = self._embed(query)
                D, I = self.index.search(
                    np.array([embedding_query], dtype=np.float32),
                    min(top_k, self.index.ntotal)
                )
                for idx, score in zip(I[0], D[0]):
                    if idx < 0:
                        continue
                    meta = self.id_to_metadata.get(str(idx), {})
                    categoria = meta.get("categoria", "general")
                    
                    # ✅ NUEVO: filtrar categorías basura
                    if categoria in CATEGORIAS_EXCLUIR:
                        continue
                    
                    resultado["faiss"].append({
                        "id": int(idx),
                        "texto": meta.get("texto", ""),
                        "score_relevancia": float(score),
                        "categoria": categoria
                    })
        except Exception as e:
            logger.warning(f"⚠️ buscar_contexto: error en FAISS: {e}")

        # ✅ NUEVO: memoria corta también filtrada
        resultado["memoria_corta"] = [
            m["texto"] for m in self.memoria_corta[-top_k:]
            if m.get("etiqueta") not in CATEGORIAS_EXCLUIR
        ]

        return resultado

    # ── Fin adaptadores ───────────────────────────────────────────────────────

    def consolidar_memoria(self, max_batch: int = 100) -> int:
        """Consolidación inteligente: memoria corta → largo plazo"""
        with self._lock:
            logger.info("🧠 Iniciando consolidación de memoria...")
            start_time = time.time()
            
            candidatos = sorted(
                self.memoria_corta,
                key=lambda x: x["importancia"],
                reverse=True
            )[:max_batch]
            
            consolidados = 0
            for entrada in candidatos:
                if entrada["importancia"] >= 0.75:
                    try:
                        self._guardar_largo_plazo(
                            texto=entrada["texto"],
                            fuente="consolidacion_automatica",
                            importancia=entrada["importancia"],
                            categoria=entrada.get("etiqueta", "general"),
                            tipo_memoria="medio_plazo",
                            tripletas=entrada.get("tripletas", []),
                            entidades=entrada.get("entidades", []),
                            metadata={"origen": "memoria_corta"}
                        )
                        self.memoria_corta.remove(entrada)
                        consolidados += 1
                    except Exception as e:
                        logger.error(f"⚠️ Error consolidando: {e}")
            
            # Limpiar BD de expirados
            try:
                self.db.eliminar_expirados()
            except Exception as e:
                logger.error(f"⚠️ Error limpiando BD: {e}")
            
            # Persistir todos los índices
            if consolidados > 0:
                self._persist_all()
            
            elapsed = time.time() - start_time
            logger.info(
                f"✅ Consolidación completada: {consolidados} items en {elapsed:.2f}s"
            )
            
            return consolidados
    
    def obtener_estadisticas(self) -> Dict:
        """Obtiene estadísticas detalladas del sistema"""
        with self._lock:
            stats = {
                "corto_plazo": len(self.memoria_corta),
                "vectores_faiss": self.index.ntotal,
                "registros_estructurales": self.indices_estructurales.stats["total_registros"],
                "tripletas_totales": self.indices_estructurales.stats["total_tripletas"],
                "entidades_unicas": self.indices_estructurales.stats["total_entidades_unicas"],
                "cache_hits": self.stats["cache_hits"],
                "cache_misses": self.stats["cache_misses"],
                "busquedas": self.stats["busquedas"],
                "textos_procesados": self.stats["textos_procesados"],
                "inicio_sistema": self.stats.get("inicio", "N/A")
            }
            
            # Estadísticas de índices estructurales
            stats_struct = self.indices_estructurales.obtener_estadisticas()
            stats["top_relaciones"] = stats_struct.get("top_relaciones", {})
            stats["top_entidades"] = stats_struct.get("top_entidades", {})
            
            return stats
    
    def cerrar(self):
        """Cierra el sistema ordenadamente"""
        logger.info("💾 Cerrando GestorMemoriaV2...")
        
        try:
            self.consolidar_memoria()
            self._persist_all()
        except Exception:
            logger.exception("Error cerrando GestorMemoriaV2.")
            raise
        finally:
            self.cache_embeddings.clear()
            self.db.cerrar()

        logger.info("✅ GestorMemoriaV2 cerrado correctamente")
    
    def __enter__(self):
        """Soporte para context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierre automático al salir del context manager"""
        self.cerrar()
        return False


if __name__ == "__main__":
    # Ejemplo de uso
    print("\n🧪 Pruebas del GestorMemoriaV2 (Sistema Híbrido)\n")
    print("=" * 80)
    
    from backend.Datos.baseDatos import BaseDeDatos
    
    db = BaseDeDatos()
    
    with GestorMemoriaV2(db) as gestor:
        # Procesar textos de prueba
        textos = [
            "Me llamo Juan García y tengo 30 años",
            "Trabajo como ingeniero de software en Google",
            "Vivo en Madrid con mi esposa",
            "Me gusta el café por las mañanas",
            "Eh... pues, tengo diabetes tipo 2"  # Con muletilla
        ]
        
        print("\n1️⃣ Procesando textos...")
        print("-" * 80)
        for texto in textos:
            resultado = gestor.procesar_texto(texto, fuente="test")
            print(f"✅ '{texto[:40]}...'")
            print(f"   → Tripletas: {resultado['num_tripletas']}, "
                  f"Entidades: {resultado['num_entidades']}")
        
        # Búsqueda híbrida
        print("\n2️⃣ Búsqueda híbrida: '¿Dónde trabaja el usuario?'")
        print("-" * 80)
        resultados = gestor.buscar_contexto_hibrido(
            query="¿Dónde trabaja el usuario?",
            top_k=3
        )
        
        for i, (registro, score) in enumerate(resultados, 1):
            print(f"\n  Resultado {i} (score={score:.3f}):")
            print(f"    Texto: {registro.texto_original}")
            print(f"    Tripletas: {len(registro.tripletas)}")
            if registro.tripletas:
                t = registro.tripletas[0]
                print(f"      → ({t['sujeto']}) --[{t['relacion_normalizada']}]--> ({t['objeto']})")
        
        # Búsqueda estructural
        print("\n3️⃣ Búsqueda estructural: relación='trabaja_en'")
        print("-" * 80)
        resultados_struct = gestor.buscar_estructural(relacion="trabaja_en")
        
        for registro in resultados_struct:
            print(f"  - {registro.texto_original}")
        
        # Estadísticas
        print("\n4️⃣ Estadísticas del sistema")
        print("-" * 80)
        stats = gestor.obtener_estadisticas()
        for k, v in stats.items():
            if not isinstance(v, dict):
                print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("✅ Pruebas completadas\n")
