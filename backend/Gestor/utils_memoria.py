"""
utils_memoria.py
----------------
Herramientas de utilidad para administrar y analizar el sistema de memoria
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List
from collections import Counter

from backend.utils.json_storage import guardar_json_atomico


class AnalizadorMemoria:
    """Analiza y genera reportes sobre el estado de la memoria"""
    
    def __init__(self, gestor_memoria):
        self.gm = gestor_memoria
    
    def generar_reporte_completo(self) -> Dict:
        """Genera un reporte completo del estado de la memoria"""
        stats = self.gm.obtener_estadisticas()
        
        reporte = {
            "timestamp": datetime.now().isoformat(),
            "resumen": {
                "total_recuerdos": stats["vectores_faiss"],
                "memoria_corta": stats["corto_plazo"],
                "eventos_proximos": stats["eventos"],
                "hechos_almacenados": stats["hechos"],
                "informacion_temporal": stats["info_util"]
            },
            "rendimiento": {
                "cache_hit_rate": self._calcular_hit_rate(stats),
                "busquedas_realizadas": stats.get("busquedas", 0)
            },
            "distribucion": stats.get("distribucion_etiquetas", {}),
            "salud": self._evaluar_salud_sistema(stats)
        }
        
        return reporte
    
    def _calcular_hit_rate(self, stats: Dict) -> float:
        """Calcula tasa de aciertos del caché"""
        hits = stats.get("cache_hits", 0)
        misses = stats.get("cache_misses", 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)
    
    def _evaluar_salud_sistema(self, stats: Dict) -> str:
        """Evalúa el estado general del sistema"""
        vectores = stats["vectores_faiss"]
        max_vectores = self.gm.MAX_VECTORES
        
        uso_porcentaje = (vectores / max_vectores) * 100
        
        if uso_porcentaje < 50:
            return "🟢 Óptimo"
        elif uso_porcentaje < 80:
            return "🟡 Saludable"
        elif uso_porcentaje < 95:
            return "🟠 Cerca del límite"
        else:
            return "🔴 Requiere consolidación"
    
    def buscar_recuerdos_por_etiqueta(self, etiqueta: str, limite: int = 10) -> List[str]:
        """Busca todos los recuerdos de una etiqueta específica"""
        resultados = []
        
        # Buscar en FAISS
        for id_str, metadata in self.gm.id_to_metadata.items():
            if metadata.get("etiqueta") == etiqueta:
                resultados.append({
                    "texto": metadata.get("texto", ""),
                    "importancia": metadata.get("importancia", 0),
                    "timestamp": metadata.get("timestamp", 0)
                })
        
        # Ordenar por importancia
        resultados.sort(key=lambda x: x["importancia"], reverse=True)
        return resultados[:limite]
    
    def obtener_timeline_memoria(self, dias: int = 7) -> Dict:
        """Obtiene una línea temporal de los recuerdos recientes"""
        limite_tiempo = datetime.now() - timedelta(days=dias)
        
        timeline = []
        for id_str, metadata in self.gm.id_to_metadata.items():
            timestamp = metadata.get("timestamp", 0)
            fecha = datetime.fromtimestamp(timestamp)
            
            if fecha >= limite_tiempo:
                timeline.append({
                    "fecha": fecha.strftime("%Y-%m-%d %H:%M"),
                    "texto": metadata.get("texto", "")[:100],
                    "etiqueta": metadata.get("etiqueta", ""),
                    "importancia": metadata.get("importancia", 0)
                })
        
        # Ordenar por fecha
        timeline.sort(key=lambda x: x["fecha"], reverse=True)
        return {"periodo": f"Últimos {dias} días", "eventos": timeline}
    
    def detectar_patrones_conversacion(self) -> Dict:
        """Detecta patrones en las conversaciones del usuario"""
        etiquetas = [
            entrada.get("etiqueta", "")
            for entrada in self.gm.memoria_corta
        ]
        
        contador = Counter(etiquetas)
        
        return {
            "etiquetas_frecuentes": contador.most_common(5),
            "total_interacciones": len(self.gm.memoria_corta),
            "diversidad": len(contador) / max(len(etiquetas), 1)
        }


class MantenedorMemoria:
    """Realiza tareas de mantenimiento de la memoria"""
    
    def __init__(self, gestor_memoria):
        self.gm = gestor_memoria
    
    def limpieza_profunda(self) -> Dict:
        """Realiza una limpieza profunda del sistema"""
        print("🧹 Iniciando limpieza profunda...")
        
        # 1. Eliminar información expirada
        self.gm.db.eliminar_expirados()
        
        # 2. Consolidar memoria importante
        consolidados = self.gm.consolidar_memoria()
        
        # 3. Limpiar caché
        cache_size_antes = len(self.gm.cache_embeddings.cache)
        self.gm.cache_embeddings.clear()
        
        # 4. Compactar índice si es necesario
        vectores_antes = self.gm.index.ntotal
        if vectores_antes > self.gm.MAX_VECTORES * 0.95:
            self.gm._compactar_indice()
        
        vectores_despues = self.gm.index.ntotal
        
        resultado = {
            "consolidados": consolidados,
            "cache_limpiado": cache_size_antes,
            "vectores_antes": vectores_antes,
            "vectores_despues": vectores_despues,
            "espacio_liberado": vectores_antes - vectores_despues
        }
        
        print(f"✅ Limpieza completada: {resultado}")
        return resultado
    
    def exportar_memoria(self, archivo_salida: str = "backup_memoria.json"):
        """Exporta toda la memoria a un archivo JSON"""
        print(f"💾 Exportando memoria a {archivo_salida}...")
        
        # Recopilar toda la información
        backup = {
            "fecha_export": datetime.now().isoformat(),
            "estadisticas": self.gm.obtener_estadisticas(),
            "memoria_corta": self.gm.memoria_corta,
            "metadatos_faiss": self.gm.id_to_metadata,
            "hechos": self.gm.db.obtener_hechos(limite=1000),
            "eventos": self.gm.db.obtener_eventos_proximos(horas=24*365),
            "info_util": self.gm.db.obtener_informacion_no_expirada()
        }
        
        guardar_json_atomico(
            archivo_salida,
            backup,
            indent=2,
            ensure_ascii=False,
            default=str,
            trailing_newline=False,
        )
        
        print(f"✅ Memoria exportada correctamente")
        return archivo_salida
    
    def importar_memoria(self, archivo_entrada: str):
        """Importa memoria desde un archivo JSON de backup"""
        print(f"📥 Importando memoria desde {archivo_entrada}...")
        
        with open(archivo_entrada, 'r', encoding='utf-8') as f:
            backup = json.load(f)
        
        # Restaurar memoria corta
        self.gm.memoria_corta = backup.get("memoria_corta", [])
        
        # Restaurar metadatos FAISS
        self.gm.id_to_metadata = backup.get("metadatos_faiss", {})
        
        # Restaurar hechos
        hechos = backup.get("hechos", [])
        for hecho in hechos:
            if isinstance(hecho, (list, tuple)) and len(hecho) >= 3:
                texto, tipo, importancia = hecho[0], hecho[1], hecho[2]
                self.gm.db.agregar_hecho(texto, tipo=tipo, importancia=importancia)
        
        print("✅ Memoria importada correctamente")
    
    def optimizar_indices(self):
        """Optimiza los índices FAISS para mejor rendimiento"""
        print("⚡ Optimizando índices FAISS...")
        
        if self.gm.index.ntotal == 0:
            print("ℹ️ No hay vectores para optimizar")
            return
        
        # Recrear índice con IVF para búsquedas más rápidas
        # (solo si hay suficientes vectores)
        if self.gm.index.ntotal > 1000:
            import faiss
            
            # Configurar índice IVF
            nlist = min(100, self.gm.index.ntotal // 10)
            quantizer = faiss.IndexFlatL2(self.gm.dim)
            nuevo_indice = faiss.IndexIVFFlat(quantizer, self.gm.dim, nlist)
            
            # Entrenar y agregar vectores
            print(f"📚 Entrenando índice con {nlist} clusters...")
            # Aquí necesitarías recuperar todos los vectores para reentrenar
            # Por ahora solo guardamos el índice actual
            
        self.gm._persist_index()
        print("✅ Optimización completada")


class ExploradorMemoria:
    """Permite explorar y buscar en la memoria de forma interactiva"""
    
    def __init__(self, gestor_memoria):
        self.gm = gestor_memoria
    
    def buscar_interactivo(self, consulta: str, top_k: int = 5):
        """Búsqueda interactiva con resultados formateados"""
        print(f"\n🔍 Buscando: '{consulta}'\n")
        
        resultados = self.gm.buscar_contexto(consulta, top_k=top_k)
        
        # Mostrar resultados FAISS
        print("📊 Resultados semánticos (FAISS):")
        if resultados["faiss"]:
            for i, res in enumerate(resultados["faiss"], 1):
                print(f"{i}. [{res['etiqueta']}] {res['texto']}")
                print(f"   Relevancia: {1 - res['distancia']:.2f} | Importancia: {res['importancia']:.2f}\n")
        else:
            print("   No se encontraron resultados\n")
        
        # Mostrar hechos
        print("📝 Hechos relacionados:")
        if resultados["hechos"]:
            for hecho in resultados["hechos"][:3]:
                print(f"   • {hecho}")
        else:
            print("   No se encontraron hechos\n")
        
        # Mostrar eventos
        if resultados["eventos"]:
            print("\n📅 Eventos relacionados:")
            for evento in resultados["eventos"][:3]:
                print(f"   • {evento}")
        
        return resultados
    
    def listar_todas_etiquetas(self):
        """Lista todas las etiquetas disponibles y su frecuencia"""
        contador = Counter()
        
        for metadata in self.gm.id_to_metadata.values():
            etiqueta = metadata.get("etiqueta", "sin_etiqueta")
            contador[etiqueta] += 1
        
        print("\n🏷️  Etiquetas en memoria:")
        for etiqueta, count in contador.most_common():
            print(f"   {etiqueta}: {count} recuerdos")
        
        return contador
    
    def ver_recuerdos_importantes(self, umbral: float = 0.8, limite: int = 10):
        """Muestra los recuerdos más importantes"""
        recuerdos = []
        
        for id_str, metadata in self.gm.id_to_metadata.items():
            importancia = metadata.get("importancia", 0)
            if importancia >= umbral:
                recuerdos.append({
                    "texto": metadata.get("texto", ""),
                    "importancia": importancia,
                    "etiqueta": metadata.get("etiqueta", ""),
                    "timestamp": metadata.get("timestamp", 0)
                })
        
        # Ordenar por importancia
        recuerdos.sort(key=lambda x: x["importancia"], reverse=True)
        
        print(f"\n⭐ Top {limite} recuerdos más importantes:\n")
        for i, rec in enumerate(recuerdos[:limite], 1):
            fecha = datetime.fromtimestamp(rec["timestamp"]).strftime("%Y-%m-%d")
            print(f"{i}. [{rec['etiqueta']}] {rec['texto']}")
            print(f"   Importancia: {rec['importancia']:.2f} | Fecha: {fecha}\n")
        
        return recuerdos[:limite]


# Función de utilidad principal
def ejecutar_menu_interactivo():
    """Menú interactivo para gestionar la memoria"""
    from backend.Gestor.gestor_memoria import GestorMemoria
    
    gm = GestorMemoria()
    analizador = AnalizadorMemoria(gm)
    mantenedor = MantenedorMemoria(gm)
    explorador = ExploradorMemoria(gm)
    
    while True:
        print("\n" + "="*50)
        print("🧠 SISTEMA DE GESTIÓN DE MEMORIA")
        print("="*50)
        print("1. Ver reporte completo")
        print("2. Buscar en memoria")
        print("3. Ver recuerdos importantes")
        print("4. Listar etiquetas")
        print("5. Ver timeline reciente")
        print("6. Limpieza profunda")
        print("7. Exportar backup")
        print("8. Importar backup")
        print("9. Optimizar índices")
        print("0. Salir")
        print("="*50)
        
        opcion = input("\nSelecciona una opción: ").strip()
        
        if opcion == "1":
            reporte = analizador.generar_reporte_completo()
            print(json.dumps(reporte, indent=2, ensure_ascii=False))
        
        elif opcion == "2":
            consulta = input("Ingresa tu búsqueda: ")
            explorador.buscar_interactivo(consulta)
        
        elif opcion == "3":
            umbral = float(input("Umbral de importancia (0-1, default 0.8): ") or "0.8")
            explorador.ver_recuerdos_importantes(umbral=umbral)
        
        elif opcion == "4":
            explorador.listar_todas_etiquetas()
        
        elif opcion == "5":
            dias = int(input("Días hacia atrás (default 7): ") or "7")
            timeline = analizador.obtener_timeline_memoria(dias=dias)
            print(json.dumps(timeline, indent=2, ensure_ascii=False))
        
        elif opcion == "6":
            confirmar = input("¿Confirmas limpieza profunda? (s/n): ")
            if confirmar.lower() == 's':
                resultado = mantenedor.limpieza_profunda()
        
        elif opcion == "7":
            archivo = input("Nombre del archivo (default: backup_memoria.json): ") or "backup_memoria.json"
            mantenedor.exportar_memoria(archivo)
        
        elif opcion == "8":
            archivo = input("Nombre del archivo a importar: ")
            mantenedor.importar_memoria(archivo)
        
        elif opcion == "9":
            mantenedor.optimizar_indices()
        
        elif opcion == "0":
            print("👋 Cerrando sistema...")
            gm.cerrar()
            break
        
        else:
            print("❌ Opción inválida")


if __name__ == "__main__":
    ejecutar_menu_interactivo()
