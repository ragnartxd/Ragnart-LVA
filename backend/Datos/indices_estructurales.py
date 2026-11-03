"""
indices_estructurales.py
------------------------
Sistema de índices secundarios para búsqueda estructural eficiente.

Implementa:
- Índice invertido por entidad
- Índice invertido por tipo de relación
- Índice por categoría semántica
- Búsqueda híbrida estructural + semántica

Optimizado para recuperación rápida con filtrado multi-criterio.
"""

import logging
import threading
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import json

from backend.utils.json_storage import guardar_json_atomico

logger = logging.getLogger(__name__)


@dataclass
class RegistroMemoria:
    """Registro completo de memoria con información estructurada"""
    id: int
    texto_original: str
    categoria: str
    importancia: float
    timestamp: str
    
    # Datos estructurados
    entidades: List[Tuple[str, str]]  # [(texto, tipo), ...]
    tripletas: List[Dict]  # [{"sujeto": ..., "relacion": ..., "objeto": ...}, ...]
    
    # Embedding (referencia)
    embedding_id: Optional[int] = None
    
    # Metadata adicional
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class IndicesEstructurales:
    """
    Sistema de índices invertidos para búsqueda estructural eficiente.
    
    Mantiene índices por:
    1. Entidad → IDs de registros
    2. Tipo de relación → IDs de registros
    3. Categoría → IDs de registros
    4. Sujeto de tripleta → IDs de registros
    5. Objeto de tripleta → IDs de registros
    
    Thread-safe y optimizado para consultas rápidas.
    """
    
    def __init__(self):
        """Inicializa los índices estructurales"""
        self._lock = threading.RLock()
        
        # Índice principal: ID → RegistroMemoria
        self.registros: Dict[int, RegistroMemoria] = {}
        
        # Índices invertidos
        self.indice_entidades: Dict[str, Set[int]] = defaultdict(set)  # entidad → {ids}
        self.indice_relaciones: Dict[str, Set[int]] = defaultdict(set)  # relacion → {ids}
        self.indice_categorias: Dict[str, Set[int]] = defaultdict(set)  # categoria → {ids}
        self.indice_sujetos: Dict[str, Set[int]] = defaultdict(set)  # sujeto → {ids}
        self.indice_objetos: Dict[str, Set[int]] = defaultdict(set)  # objeto → {ids}
        
        # Contador de IDs
        self.next_id = 0
        
        # Estadísticas
        self.stats = {
            "total_registros": 0,
            "total_entidades_unicas": 0,
            "total_relaciones_unicas": 0,
            "total_tripletas": 0
        }
        
        logger.info("📇 IndicesEstructurales inicializado")
    
    def agregar_registro(self, texto: str, categoria: str, importancia: float,
                        timestamp: str, entidades: List[Tuple[str, str]],
                        tripletas: List[Dict], metadata: Dict = None,
                        embedding_id: int = None) -> int:
        """
        Agrega un nuevo registro y actualiza todos los índices.
        
        Args:
            texto: Texto original
            categoria: Categoría semántica
            importancia: Score de importancia [0-1]
            timestamp: Timestamp ISO
            entidades: Lista de (texto_entidad, tipo_entidad)
            tripletas: Lista de diccionarios con tripletas
            metadata: Metadata adicional
            embedding_id: ID en el índice FAISS (opcional)
            
        Returns:
            ID del registro creado
        """
        with self._lock:
            # Crear registro
            registro_id = self.next_id
            self.next_id += 1
            
            registro = RegistroMemoria(
                id=registro_id,
                texto_original=texto,
                categoria=categoria,
                importancia=importancia,
                timestamp=timestamp,
                entidades=entidades,
                tripletas=tripletas,
                embedding_id=embedding_id,
                metadata=metadata or {}
            )
            
            # Guardar en índice principal
            self.registros[registro_id] = registro
            
            # Actualizar índices invertidos
            self._actualizar_indices(registro_id, registro)
            
            # Actualizar estadísticas
            self._actualizar_stats()
            
            logger.debug(f"➕ Registro {registro_id} agregado: '{texto[:30]}...'")
            
            return registro_id
    
    def _actualizar_indices(self, registro_id: int, registro: RegistroMemoria):
        """Actualiza todos los índices invertidos para un registro"""
        
        # Índice de categorías
        self.indice_categorias[registro.categoria].add(registro_id)
        
        # Índice de entidades
        for texto_entidad, tipo_entidad in registro.entidades:
            # Normalizar entidad (minúsculas, sin espacios extra)
            entidad_norm = self._normalizar_texto(texto_entidad)
            self.indice_entidades[entidad_norm].add(registro_id)
            
            # También indexar por tipo de entidad
            clave_tipo = f"TIPO:{tipo_entidad}"
            self.indice_entidades[clave_tipo].add(registro_id)
        
        # Índice de tripletas
        for tripleta in registro.tripletas:
            # Indexar por relación normalizada
            relacion = tripleta.get("relacion_normalizada", "")
            if relacion:
                self.indice_relaciones[relacion].add(registro_id)
            
            # Indexar por sujeto
            sujeto = tripleta.get("sujeto", "")
            if sujeto:
                sujeto_norm = self._normalizar_texto(sujeto)
                self.indice_sujetos[sujeto_norm].add(registro_id)
            
            # Indexar por objeto
            objeto = tripleta.get("objeto", "")
            if objeto:
                objeto_norm = self._normalizar_texto(objeto)
                self.indice_objetos[objeto_norm].add(registro_id)
    
    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para indexación: lowercase, sin espacios extra"""
        return " ".join(texto.lower().split())
    
    def buscar_por_entidad(self, entidad: str, limit: int = 10) -> List[RegistroMemoria]:
        """
        Busca registros que contengan una entidad específica.
        
        Args:
            entidad: Nombre de la entidad
            limit: Número máximo de resultados
            
        Returns:
            Lista de registros ordenados por importancia
        """
        with self._lock:
            entidad_norm = self._normalizar_texto(entidad)
            ids = self.indice_entidades.get(entidad_norm, set())
            
            registros = [self.registros[i] for i in ids if i in self.registros]
            registros.sort(key=lambda r: r.importancia, reverse=True)
            
            return registros[:limit]
    
    def buscar_por_relacion(self, relacion: str, limit: int = 10) -> List[RegistroMemoria]:
        """
        Busca registros que contengan una relación específica.
        
        Args:
            relacion: Tipo de relación (ej: "trabaja_en", "vive_en")
            limit: Número máximo de resultados
            
        Returns:
            Lista de registros ordenados por importancia
        """
        with self._lock:
            ids = self.indice_relaciones.get(relacion, set())
            
            registros = [self.registros[i] for i in ids if i in self.registros]
            registros.sort(key=lambda r: r.importancia, reverse=True)
            
            return registros[:limit]
    
    def buscar_por_categoria(self, categoria: str, limit: int = 10) -> List[RegistroMemoria]:
        """Busca registros de una categoría específica"""
        with self._lock:
            ids = self.indice_categorias.get(categoria, set())
            
            registros = [self.registros[i] for i in ids if i in self.registros]
            registros.sort(key=lambda r: r.importancia, reverse=True)
            
            return registros[:limit]
    
    def buscar_tripleta(self, sujeto: str = None, relacion: str = None,
                       objeto: str = None, limit: int = 10) -> List[RegistroMemoria]:
        """
        Búsqueda estructural por componentes de tripleta.
        
        Permite filtrar por uno, dos o tres componentes:
        - buscar_tripleta(sujeto="usuario") → todas las tripletas con "usuario" como sujeto
        - buscar_tripleta(relacion="trabaja_en") → todas las relaciones de trabajo
        - buscar_tripleta(sujeto="usuario", relacion="trabaja_en") → trabajos del usuario
        
        Args:
            sujeto: Filtro por sujeto (opcional)
            relacion: Filtro por relación (opcional)
            objeto: Filtro por objeto (opcional)
            limit: Número máximo de resultados
            
        Returns:
            Lista de registros que cumplen los filtros
        """
        with self._lock:
            # Obtener conjuntos de IDs por cada filtro
            conjuntos = []
            
            if sujeto:
                sujeto_norm = self._normalizar_texto(sujeto)
                conjuntos.append(self.indice_sujetos.get(sujeto_norm, set()))
            
            if relacion:
                conjuntos.append(self.indice_relaciones.get(relacion, set()))
            
            if objeto:
                objeto_norm = self._normalizar_texto(objeto)
                conjuntos.append(self.indice_objetos.get(objeto_norm, set()))
            
            # Si no hay filtros, retornar vacío
            if not conjuntos:
                return []
            
            # Intersección de todos los conjuntos (AND lógico)
            ids_resultado = set.intersection(*conjuntos) if len(conjuntos) > 1 else conjuntos[0]
            
            # Obtener registros
            registros = [self.registros[i] for i in ids_resultado if i in self.registros]
            registros.sort(key=lambda r: r.importancia, reverse=True)
            
            logger.debug(
                f"🔍 Búsqueda tripleta: sujeto={sujeto}, rel={relacion}, obj={objeto} "
                f"→ {len(registros)} resultados"
            )
            
            return registros[:limit]
    
    def buscar_hibrida(self, filtros_estructurales: Dict,
                      ids_semanticos: List[int],
                      scores_semanticos: Dict[int, float],
                      limit: int = 10,
                      peso_estructural: float = 0.3,
                      peso_semantico: float = 0.7) -> List[Tuple[RegistroMemoria, float]]:
        """
        Búsqueda híbrida: filtro estructural + re-ranking semántico.
        
        Proceso:
        1. Aplicar filtros estructurales para reducir espacio de búsqueda
        2. Intersectar con resultados semánticos
        3. Re-rankear combinando scores estructurales y semánticos
        
        Args:
            filtros_estructurales: Dict con filtros {"categoria": ..., "relacion": ..., etc}
            ids_semanticos: IDs de resultados semánticos (de FAISS)
            scores_semanticos: Mapping ID → score semántico
            limit: Número máximo de resultados
            peso_estructural: Peso del score estructural [0-1]
            peso_semantico: Peso del score semántico [0-1]
            
        Returns:
            Lista de (RegistroMemoria, score_final) ordenada por score
        """
        with self._lock:
            # Paso 1: Aplicar filtros estructurales
            ids_estructurales = self._aplicar_filtros_estructurales(filtros_estructurales)
            
            # Paso 2: Intersectar con resultados semánticos
            ids_comunes = set(ids_estructurales) & set(ids_semanticos)
            
            # Paso 3: Re-rankear
            resultados = []
            for registro_id in ids_comunes:
                if registro_id not in self.registros:
                    continue
                
                registro = self.registros[registro_id]
                
                # Score estructural: importancia del registro
                score_estructural = registro.importancia
                
                # Score semántico: similitud coseno
                score_semantico = scores_semanticos.get(registro_id, 0.0)
                
                # Score final: combinación ponderada
                score_final = (
                    peso_estructural * score_estructural +
                    peso_semantico * score_semantico
                )
                
                resultados.append((registro, score_final))
            
            # Ordenar por score final
            resultados.sort(key=lambda x: x[1], reverse=True)
            
            logger.debug(
                f"🔀 Búsqueda híbrida: {len(ids_estructurales)} estructurales, "
                f"{len(ids_semanticos)} semánticos → {len(resultados)} comunes"
            )
            
            return resultados[:limit]
    
    def _aplicar_filtros_estructurales(self, filtros: Dict) -> Set[int]:
        """
        Aplica múltiples filtros estructurales y retorna IDs que cumplen todos.
        
        Filtros soportados:
        - categoria: str
        - entidad: str
        - relacion: str
        - sujeto: str
        - objeto: str
        - importancia_min: float
        """
        conjuntos = []
        
        # Filtro por categoría
        if "categoria" in filtros:
            ids = self.indice_categorias.get(filtros["categoria"], set())
            conjuntos.append(ids)
        
        # Filtro por entidad
        if "entidad" in filtros:
            entidad_norm = self._normalizar_texto(filtros["entidad"])
            ids = self.indice_entidades.get(entidad_norm, set())
            conjuntos.append(ids)
        
        # Filtro por relación
        if "relacion" in filtros:
            ids = self.indice_relaciones.get(filtros["relacion"], set())
            conjuntos.append(ids)
        
        # Filtro por sujeto
        if "sujeto" in filtros:
            sujeto_norm = self._normalizar_texto(filtros["sujeto"])
            ids = self.indice_sujetos.get(sujeto_norm, set())
            conjuntos.append(ids)
        
        # Filtro por objeto
        if "objeto" in filtros:
            objeto_norm = self._normalizar_texto(filtros["objeto"])
            ids = self.indice_objetos.get(objeto_norm, set())
            conjuntos.append(ids)
        
        # Si no hay filtros, retornar todos los IDs
        if not conjuntos:
            return set(self.registros.keys())
        
        # Intersección de todos los conjuntos
        ids_resultado = set.intersection(*conjuntos)
        
        # Filtro por importancia mínima (post-filtrado)
        if "importancia_min" in filtros:
            importancia_min = filtros["importancia_min"]
            ids_resultado = {
                i for i in ids_resultado
                if i in self.registros and self.registros[i].importancia >= importancia_min
            }
        
        return ids_resultado
    
    def obtener_registro(self, registro_id: int) -> Optional[RegistroMemoria]:
        """Obtiene un registro por su ID"""
        with self._lock:
            return self.registros.get(registro_id)
    
    def eliminar_registro(self, registro_id: int) -> bool:
        """
        Elimina un registro y actualiza todos los índices.
        
        Args:
            registro_id: ID del registro a eliminar
            
        Returns:
            True si se eliminó, False si no existía
        """
        with self._lock:
            if registro_id not in self.registros:
                return False
            
            registro = self.registros[registro_id]
            
            # Remover de índices
            self.indice_categorias[registro.categoria].discard(registro_id)
            
            for texto_ent, tipo_ent in registro.entidades:
                entidad_norm = self._normalizar_texto(texto_ent)
                self.indice_entidades[entidad_norm].discard(registro_id)
                self.indice_entidades[f"TIPO:{tipo_ent}"].discard(registro_id)
            
            for tripleta in registro.tripletas:
                relacion = tripleta.get("relacion_normalizada", "")
                if relacion:
                    self.indice_relaciones[relacion].discard(registro_id)
                
                sujeto = tripleta.get("sujeto", "")
                if sujeto:
                    self.indice_sujetos[self._normalizar_texto(sujeto)].discard(registro_id)
                
                objeto = tripleta.get("objeto", "")
                if objeto:
                    self.indice_objetos[self._normalizar_texto(objeto)].discard(registro_id)
            
            # Eliminar del índice principal
            del self.registros[registro_id]
            
            # Actualizar estadísticas
            self._actualizar_stats()
            
            logger.debug(f"🗑️ Registro {registro_id} eliminado")
            
            return True
    
    def _actualizar_stats(self):
        """Actualiza las estadísticas del sistema"""
        self.stats["total_registros"] = len(self.registros)
        self.stats["total_entidades_unicas"] = len(self.indice_entidades)
        self.stats["total_relaciones_unicas"] = len(self.indice_relaciones)
        
        total_tripletas = sum(
            len(r.tripletas) for r in self.registros.values()
        )
        self.stats["total_tripletas"] = total_tripletas
    
    def obtener_estadisticas(self) -> Dict:
        """Retorna estadísticas del sistema de índices"""
        with self._lock:
            return {
                **self.stats,
                "categorias": {
                    cat: len(ids) for cat, ids in self.indice_categorias.items()
                },
                "top_relaciones": self._top_n_dict(self.indice_relaciones, 10),
                "top_entidades": self._top_n_dict(self.indice_entidades, 10)
            }
    
    def _top_n_dict(self, indice: Dict[str, Set[int]], n: int) -> Dict[str, int]:
        """Retorna las top N claves de un índice por número de referencias"""
        items = [(k, len(v)) for k, v in indice.items() if not k.startswith("TIPO:")]
        items.sort(key=lambda x: x[1], reverse=True)
        return dict(items[:n])
    
    def persistir(self, filepath: str):
        """Persiste los índices en disco (JSON)"""
        with self._lock:
            data = {
                "next_id": self.next_id,
                "registros": [
                    {
                        "id": r.id,
                        "texto_original": r.texto_original,
                        "categoria": r.categoria,
                        "importancia": r.importancia,
                        "timestamp": r.timestamp,
                        "entidades": r.entidades,
                        "tripletas": r.tripletas,
                        "embedding_id": r.embedding_id,
                        "metadata": r.metadata
                    }
                    for r in self.registros.values()
                ]
            }
            
            guardar_json_atomico(
                filepath,
                data,
                indent=2,
                ensure_ascii=False,
                trailing_newline=False,
            )
            
            logger.info(f"💾 Índices persistidos en {filepath}")
    
    def cargar(self, filepath: str):
        """Carga índices desde disco"""
        with self._lock:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.next_id = data.get("next_id", 0)
            
            # Reconstruir registros e índices
            for r_data in data.get("registros", []):
                registro = RegistroMemoria(
                    id=r_data["id"],
                    texto_original=r_data["texto_original"],
                    categoria=r_data["categoria"],
                    importancia=r_data["importancia"],
                    timestamp=r_data["timestamp"],
                    entidades=r_data["entidades"],
                    tripletas=r_data["tripletas"],
                    embedding_id=r_data.get("embedding_id"),
                    metadata=r_data.get("metadata", {})
                )
                
                self.registros[registro.id] = registro
                self._actualizar_indices(registro.id, registro)
            
            self._actualizar_stats()
            
            logger.info(f"📂 Índices cargados desde {filepath}: {len(self.registros)} registros")


if __name__ == "__main__":
    # Pruebas
    indices = IndicesEstructurales()
    
    # Agregar registros de prueba
    print("\n📇 Pruebas de IndicesEstructurales\n")
    print("=" * 80)
    
    # Registro 1
    id1 = indices.agregar_registro(
        texto="Me llamo Juan García y trabajo en Google",
        categoria="identidad_personal",
        importancia=0.9,
        timestamp="2024-01-15 10:30:00",
        entidades=[("Juan García", "PERSON"), ("Google", "ORG")],
        tripletas=[
            {"sujeto": "usuario", "relacion": "llamarse", "relacion_normalizada": "tiene_nombre", "objeto": "Juan García"},
            {"sujeto": "usuario", "relacion": "trabajar", "relacion_normalizada": "trabaja_en", "objeto": "Google"}
        ]
    )
    print(f"✅ Registro 1 agregado (ID: {id1})")
    
    # Registro 2
    id2 = indices.agregar_registro(
        texto="Vivo en Madrid y me gusta el café",
        categoria="ubicacion",
        importancia=0.7,
        timestamp="2024-01-15 10:31:00",
        entidades=[("Madrid", "GPE")],
        tripletas=[
            {"sujeto": "usuario", "relacion": "vivir", "relacion_normalizada": "vive_en", "objeto": "Madrid"},
            {"sujeto": "usuario", "relacion": "gustar", "relacion_normalizada": "le_gusta", "objeto": "el café"}
        ]
    )
    print(f"✅ Registro 2 agregado (ID: {id2})")
    
    # Registro 3
    id3 = indices.agregar_registro(
        texto="Juan trabaja en Microsoft desde 2020",
        categoria="trabajo_estudio",
        importancia=0.85,
        timestamp="2024-01-15 10:32:00",
        entidades=[("Juan", "PERSON"), ("Microsoft", "ORG")],
        tripletas=[
            {"sujeto": "Juan", "relacion": "trabajar", "relacion_normalizada": "trabaja_en", "objeto": "Microsoft"}
        ]
    )
    print(f"✅ Registro 3 agregado (ID: {id3})\n")
    
    # Prueba 1: Buscar por entidad
    print("\n1️⃣ Búsqueda por entidad 'Juan García':")
    print("-" * 80)
    resultados = indices.buscar_por_entidad("Juan García")
    for r in resultados:
        print(f"  - [{r.id}] {r.texto_original}")
    
    # Prueba 2: Buscar por relación
    print("\n2️⃣ Búsqueda por relación 'trabaja_en':")
    print("-" * 80)
    resultados = indices.buscar_por_relacion("trabaja_en")
    for r in resultados:
        print(f"  - [{r.id}] {r.texto_original}")
    
    # Prueba 3: Buscar tripleta específica
    print("\n3️⃣ Búsqueda por tripleta (sujeto='usuario', relacion='trabaja_en'):")
    print("-" * 80)
    resultados = indices.buscar_tripleta(sujeto="usuario", relacion="trabaja_en")
    for r in resultados:
        print(f"  - [{r.id}] {r.texto_original}")
    
    # Estadísticas
    print("\n📊 Estadísticas:")
    print("-" * 80)
    stats = indices.obtener_estadisticas()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    print("\n" + "=" * 80)
    print("✅ Pruebas completadas\n")
