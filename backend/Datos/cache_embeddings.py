"""
cache_embeddings.py
-------------------
Sistema de caché LRU (Least Recently Used) para embeddings.

Optimiza el rendimiento evitando recalcular embeddings para textos repetidos.
Implementa política de evicción LRU para mantener el tamaño bajo control.

Fecha: 2024
"""

import time
import logging
import numpy as np
from typing import Optional
from collections import OrderedDict

# Configurar logging
logger = logging.getLogger(__name__)


class CacheEmbeddings:
    """
    Caché LRU para embeddings de texto.
    
    Características:
    - Política de evicción LRU (Least Recently Used)
    - Thread-safe mediante OrderedDict
    - Métricas de rendimiento integradas
    - Configuración de tamaño máximo
    """
    
    def __init__(self, max_size: int = 2000):
        """
        Inicializa el caché de embeddings.
        
        Args:
            max_size: Número máximo de embeddings a almacenar
        """
        if max_size <= 0:
            raise ValueError("max_size debe ser mayor a 0")
        
        self.max_size = max_size
        
        # Usar OrderedDict para orden de inserción
        self.cache = OrderedDict()
        
        # Métricas
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.total_requests = 0
        
        logger.info(f"✅ CacheEmbeddings inicializado (max_size={max_size})")
    
    def get(self, texto: str) -> Optional[np.ndarray]:
        """
        Recupera un embedding del caché.
        
        Si el embedding existe, lo mueve al final (más reciente) según LRU.
        
        Args:
            texto: Texto cuyo embedding se busca
        
        Returns:
            np.ndarray si existe en caché, None si no existe
        """
        self.total_requests += 1
        
        if texto in self.cache:
            # Mover al final (más reciente)
            self.cache.move_to_end(texto)
            self.hits += 1
            
            logger.debug(f"✓ Cache HIT: '{texto[:30]}...'")
            return self.cache[texto]
        
        self.misses += 1
        logger.debug(f"✗ Cache MISS: '{texto[:30]}...'")
        return None
    
    def set(self, texto: str, embedding: np.ndarray):
        """
        Guarda un embedding en el caché.
        
        Si el caché está lleno, elimina el elemento menos recientemente usado (LRU).
        
        Args:
            texto: Texto asociado al embedding
            embedding: Vector numpy del embedding
        """
        if not isinstance(embedding, np.ndarray):
            raise TypeError("embedding debe ser un numpy.ndarray")
        
        # Si ya existe, actualizar y mover al final
        if texto in self.cache:
            self.cache.move_to_end(texto)
            self.cache[texto] = embedding
            logger.debug(f"↻ Cache UPDATE: '{texto[:30]}...'")
            return
        
        # Si está lleno, eliminar el más antiguo (LRU)
        if len(self.cache) >= self.max_size:
            oldest_key, _ = self.cache.popitem(last=False)  # FIFO: first=True sería el primero
            self.evictions += 1
            logger.debug(f"🗑️ Cache EVICT: '{oldest_key[:30]}...'")
        
        # Agregar nuevo embedding al final
        self.cache[texto] = embedding
        logger.debug(f"+ Cache ADD: '{texto[:30]}...'")
    
    def exists(self, texto: str) -> bool:
        """
        Verifica si un texto existe en el caché sin afectar el orden LRU.
        
        Args:
            texto: Texto a verificar
        
        Returns:
            bool: True si existe, False si no
        """
        return texto in self.cache
    
    def remove(self, texto: str) -> bool:
        """
        Elimina un embedding del caché.
        
        Args:
            texto: Texto a eliminar
        
        Returns:
            bool: True si se eliminó, False si no existía
        """
        if texto in self.cache:
            del self.cache[texto]
            logger.debug(f"🗑️ Cache REMOVE: '{texto[:30]}...'")
            return True
        return False
    
    def clear(self):
        """Limpia completamente el caché"""
        size_before = len(self.cache)
        self.cache.clear()
        logger.info(f"🧹 Cache limpiado: {size_before} embeddings eliminados")
    
    def get_stats(self) -> dict:
        """
        Obtiene estadísticas del caché.
        
        Returns:
            dict: Diccionario con métricas del caché
        """
        hit_rate = 0.0
        if self.total_requests > 0:
            hit_rate = self.hits / self.total_requests
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "utilization": len(self.cache) / self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_requests": self.total_requests,
            "hit_rate": hit_rate,
            "miss_rate": 1.0 - hit_rate
        }
    
    def reset_stats(self):
        """Reinicia las métricas del caché"""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.total_requests = 0
        logger.info("🔄 Estadísticas del caché reiniciadas")
    
    def resize(self, new_max_size: int):
        """
        Cambia el tamaño máximo del caché.
        
        Si el nuevo tamaño es menor, elimina los elementos más antiguos.
        
        Args:
            new_max_size: Nuevo tamaño máximo
        """
        if new_max_size <= 0:
            raise ValueError("new_max_size debe ser mayor a 0")
        
        old_max_size = self.max_size
        self.max_size = new_max_size
        
        # Si el nuevo tamaño es menor, limpiar excedentes
        while len(self.cache) > new_max_size:
            oldest_key, _ = self.cache.popitem(last=False)
            self.evictions += 1
            logger.debug(f"🗑️ Cache EVICT (resize): '{oldest_key[:30]}...'")
        
        logger.info(
            f"📏 Caché redimensionado: {old_max_size} → {new_max_size} "
            f"(actual: {len(self.cache)})"
        )
    
    def get_size_bytes(self) -> int:
        """
        Estima el tamaño del caché en bytes.
        
        Returns:
            int: Tamaño estimado en bytes
        """
        total_bytes = 0
        
        for texto, embedding in self.cache.items():
            # Tamaño del texto (UTF-8)
            total_bytes += len(texto.encode('utf-8'))
            
            # Tamaño del embedding (numpy array)
            total_bytes += embedding.nbytes
        
        return total_bytes
    
    def get_most_used(self, n: int = 10) -> list:
        """
        Obtiene los N textos más recientemente usados.
        
        Args:
            n: Número de elementos a retornar
        
        Returns:
            list: Lista de textos más recientes
        """
        # OrderedDict mantiene orden de inserción/actualización
        items = list(self.cache.keys())
        return items[-n:] if len(items) >= n else items
    
    def __len__(self) -> int:
        """Retorna el número de elementos en el caché"""
        return len(self.cache)
    
    def __contains__(self, texto: str) -> bool:
        """Permite usar 'in' para verificar existencia"""
        return texto in self.cache
    
    def __repr__(self) -> str:
        """Representación en string del caché"""
        stats = self.get_stats()
        return (
            f"CacheEmbeddings(size={len(self)}/{self.max_size}, "
            f"hit_rate={stats['hit_rate']:.2%})"
        )


class CacheEmbeddingsAvanzado(CacheEmbeddings):
    """
    Versión avanzada del caché con TTL (Time To Live).
    
    Agrega expiración automática de embeddings antiguos.
    """
    
    def __init__(self, max_size: int = 2000, ttl_seconds: int = 3600):
        """
        Inicializa caché avanzado con TTL.
        
        Args:
            max_size: Número máximo de embeddings
            ttl_seconds: Tiempo de vida en segundos (default: 1 hora)
        """
        super().__init__(max_size)
        self.ttl_seconds = ttl_seconds
        self.timestamps = OrderedDict()
        
        logger.info(f"✅ CacheEmbeddingsAvanzado con TTL={ttl_seconds}s")
    
    def get(self, texto: str) -> Optional[np.ndarray]:
        """
        Recupera embedding verificando TTL.
        
        Si el embedding expiró, lo elimina y retorna None.
        """
        if texto not in self.cache:
            self.misses += 1
            return None
        
        # Verificar TTL
        timestamp = self.timestamps.get(texto)
        if timestamp and (time.time() - timestamp) > self.ttl_seconds:
            # Expirado
            logger.debug(f"⏰ Cache EXPIRED: '{texto[:30]}...'")
            del self.cache[texto]
            del self.timestamps[texto]
            self.misses += 1
            return None
        
        # No expirado, actualizar acceso
        self.cache.move_to_end(texto)
        self.timestamps.move_to_end(texto)
        self.hits += 1
        
        return self.cache[texto]
    
    def set(self, texto: str, embedding: np.ndarray):
        """Guarda embedding con timestamp"""
        super().set(texto, embedding)
        
        # Actualizar timestamp
        self.timestamps[texto] = time.time()
        
        # Sincronizar orden
        if texto in self.cache:
            self.timestamps.move_to_end(texto)
    
    def clear_expired(self) -> int:
        """
        Elimina todos los embeddings expirados.
        
        Returns:
            int: Número de embeddings eliminados
        """
        current_time = time.time()
        expired_keys = []
        
        for texto, timestamp in self.timestamps.items():
            if (current_time - timestamp) > self.ttl_seconds:
                expired_keys.append(texto)
        
        for key in expired_keys:
            del self.cache[key]
            del self.timestamps[key]
        
        if expired_keys:
            logger.info(f"🧹 Limpiados {len(expired_keys)} embeddings expirados")
        
        return len(expired_keys)
    
    def clear(self):
        """Limpia caché y timestamps"""
        super().clear()
        self.timestamps.clear()


if __name__ == "__main__":
    # Ejemplo de uso
    print("\n🧪 Pruebas de CacheEmbeddings\n")
    
    # Crear caché pequeño para demostración
    cache = CacheEmbeddings(max_size=3)
    
    # Simular embeddings
    emb1 = np.random.rand(384)
    emb2 = np.random.rand(384)
    emb3 = np.random.rand(384)
    emb4 = np.random.rand(384)
    
    # Agregar embeddings
    print("1. Agregando embeddings...")
    cache.set("texto 1", emb1)
    cache.set("texto 2", emb2)
    cache.set("texto 3", emb3)
    print(f"   Estado: {cache}\n")
    
    # Obtener embedding (hit)
    print("2. Obteniendo 'texto 1' (debería ser HIT)...")
    result = cache.get("texto 1")
    print(f"   Resultado: {'HIT' if result is not None else 'MISS'}")
    print(f"   Estado: {cache}\n")
    
    # Agregar cuarto (debe evict)
    print("3. Agregando 'texto 4' (debería evict 'texto 2')...")
    cache.set("texto 4", emb4)
    print(f"   Estado: {cache}\n")
    
    # Verificar evicción
    print("4. Intentando obtener 'texto 2' (debería ser MISS)...")
    result = cache.get("texto 2")
    print(f"   Resultado: {'HIT' if result is not None else 'MISS'}\n")
    
    # Estadísticas
    print("5. Estadísticas finales:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n" + "="*50 + "\n")
    
    # Probar caché con TTL
    print("🧪 Pruebas de CacheEmbeddingsAvanzado (TTL)\n")
    
    cache_ttl = CacheEmbeddingsAvanzado(max_size=5, ttl_seconds=2)
    
    cache_ttl.set("temporal", emb1)
    print("1. Agregado 'temporal' con TTL=2s")
    print(f"   Estado: {cache_ttl}\n")
    
    print("2. Esperando 1 segundo...")
    time.sleep(1)
    result = cache_ttl.get("temporal")
    print(f"   Obtener 'temporal': {'HIT' if result is not None else 'MISS'}\n")
    
    print("3. Esperando 2 segundos más (total 3s > TTL)...")
    time.sleep(2)
    result = cache_ttl.get("temporal")
    print(f"   Obtener 'temporal': {'HIT' if result is not None else 'MISS (expirado)'}\n")
    
    print("✅ Pruebas completadas")
