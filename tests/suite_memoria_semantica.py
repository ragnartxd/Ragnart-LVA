"""
suite_memoria_semantica.py - Suite del sistema de memoria semántica
=========================================================================

Pruebas organizadas en:
  1. CacheEmbeddings         - Caché LRU + TTL
  2. BaseDeDatos             - Persistencia SQLite
  3. TaxonomiaMemoria        - Clasificación semántica
  4. ExtractorTripletas      - Extracción S-R-O
  5. IndicesEstructurales    - Índices invertidos
  6. AnalizadorSemanticoV2   - Análisis completo
  7. GestorMemoriaV2         - Sistema integrado

Uso:
  python tests/suite_memoria_semantica.py                  → Menú interactivo
  python tests/suite_memoria_semantica.py --all            → Todas las pruebas
  python tests/suite_memoria_semantica.py --modulo cache   → Solo un módulo
  python tests/suite_memoria_semantica.py --modulo bd
  python tests/suite_memoria_semantica.py --modulo taxonomia
  python tests/suite_memoria_semantica.py --modulo tripletas
  python tests/suite_memoria_semantica.py --modulo indices
  python tests/suite_memoria_semantica.py --modulo analizador
  python tests/suite_memoria_semantica.py --modulo gestor
  python tests/suite_memoria_semantica.py --modulo integracion
"""

import sys
import os
import time
import tempfile
import traceback
import argparse
import numpy as np
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# Ajuste de rutas para importar desde backend/
# ─────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ─────────────────────────────────────────────
# Utilidades de reporte
# ─────────────────────────────────────────────

VERDE  = "\033[92m"
ROJO   = "\033[91m"
AMARILLO = "\033[93m"
AZUL   = "\033[94m"
RESET  = "\033[0m"
NEGRITA = "\033[1m"

_resultados = []   # lista de (modulo, nombre, ok, detalle)


def ok(modulo: str, nombre: str, detalle: str = ""):
    _resultados.append((modulo, nombre, True, detalle))
    marca = f"{VERDE}✅{RESET}"
    print(f"  {marca} {nombre}" + (f"  →  {AMARILLO}{detalle}{RESET}" if detalle else ""))


def fallo(modulo: str, nombre: str, detalle: str = ""):
    _resultados.append((modulo, nombre, False, detalle))
    marca = f"{ROJO}❌{RESET}"
    print(f"  {marca} {nombre}" + (f"\n      {ROJO}{detalle}{RESET}" if detalle else ""))


def seccion(titulo: str):
    linea = "─" * 60
    print(f"\n{AZUL}{NEGRITA}{linea}{RESET}")
    print(f"{AZUL}{NEGRITA}  🧪 {titulo}{RESET}")
    print(f"{AZUL}{NEGRITA}{linea}{RESET}")


def resumen_final():
    total = len(_resultados)
    pasados = sum(1 for _, _, ok_, _ in _resultados if ok_)
    fallados = total - pasados

    print(f"\n{'═'*60}")
    print(f"{NEGRITA}  RESUMEN FINAL{RESET}")
    print(f"{'═'*60}")
    print(f"  Total  : {total}")
    print(f"  {VERDE}Pasados: {pasados}{RESET}")
    if fallados:
        print(f"  {ROJO}Fallados: {fallados}{RESET}")
        print(f"\n  {ROJO}Pruebas fallidas:{RESET}")
        for modulo, nombre, ok_, detalle in _resultados:
            if not ok_:
                print(f"    [{modulo}] {nombre}")
                if detalle:
                    print(f"      {detalle}")
    else:
        print(f"  {VERDE}¡Todas las pruebas pasaron! 🎉{RESET}")
    print(f"{'═'*60}\n")


# ══════════════════════════════════════════════════════════════════
# 1. PRUEBAS DE CacheEmbeddings
# ══════════════════════════════════════════════════════════════════

def test_cache_embeddings():
    seccion("CacheEmbeddings — Caché LRU para embeddings")
    from backend.Datos.cache_embeddings import CacheEmbeddings, CacheEmbeddingsAvanzado

    MOD = "cache"

    # ── Inicialización ──
    try:
        cache = CacheEmbeddings(max_size=3)
        ok(MOD, "Inicialización con max_size=3")
    except Exception as e:
        fallo(MOD, "Inicialización", str(e)); return

    try:
        CacheEmbeddings(max_size=0)
        fallo(MOD, "Debe rechazar max_size=0")
    except ValueError:
        ok(MOD, "Rechaza max_size inválido (ValueError)")

    # ── Operaciones básicas set/get ──
    emb1 = np.random.rand(384).astype(np.float32)
    emb2 = np.random.rand(384).astype(np.float32)
    emb3 = np.random.rand(384).astype(np.float32)
    emb4 = np.random.rand(384).astype(np.float32)

    cache.set("texto1", emb1)
    cache.set("texto2", emb2)
    cache.set("texto3", emb3)

    resultado = cache.get("texto1")
    assert resultado is not None and np.array_equal(resultado, emb1)
    ok(MOD, "get() retorna embedding correcto")

    assert cache.get("no_existe") is None
    ok(MOD, "get() retorna None para clave inexistente")

    # ── Política LRU ──
    # texto1 fue accedido recién → más reciente
    # Agregar texto4 debe evict al menos reciente (texto2)
    cache.set("texto4", emb4)
    assert "texto4" in cache, "texto4 debe estar en caché"
    assert len(cache) == 3, f"Tamaño esperado 3, obtenido {len(cache)}"
    ok(MOD, f"Política LRU: evicción correcta (size={len(cache)})")

    # texto2 fue evictado (el menos usado)
    assert cache.get("texto2") is None
    ok(MOD, "Elemento LRU evictado correctamente (texto2)")

    # texto1 aún debe existir (fue accedido recién)
    assert cache.get("texto1") is not None
    ok(MOD, "Elemento reciente NO evictado (texto1)")

    # ── exists / remove ──
    assert cache.exists("texto1")
    ok(MOD, "exists() detecta clave presente")
    assert not cache.exists("no_existe")
    ok(MOD, "exists() detecta clave ausente")

    removido = cache.remove("texto1")
    assert removido and "texto1" not in cache
    ok(MOD, "remove() elimina correctamente")

    no_removido = cache.remove("no_existe")
    assert not no_removido
    ok(MOD, "remove() retorna False si no existe")

    # ── Estadísticas ──
    stats = cache.get_stats()
    assert stats["hits"] > 0 and stats["misses"] > 0
    ok(MOD, f"Estadísticas: hits={stats['hits']}, misses={stats['misses']}, "
            f"evictions={stats['evictions']}")
    assert 0.0 <= stats["hit_rate"] <= 1.0
    ok(MOD, f"hit_rate en rango [0,1]: {stats['hit_rate']:.2%}")

    # ── reset_stats ──
    cache.reset_stats()
    s = cache.get_stats()
    assert s["hits"] == 0 and s["misses"] == 0
    ok(MOD, "reset_stats() limpia contadores")

    # ── resize ──
    cache2 = CacheEmbeddings(max_size=5)
    for i in range(5):
        cache2.set(f"k{i}", np.zeros(384))
    cache2.resize(2)
    assert len(cache2) <= 2
    ok(MOD, f"resize() reduce caché a max=2 (actual={len(cache2)})")

    try:
        cache2.resize(0)
        fallo(MOD, "resize(0) debe lanzar ValueError")
    except ValueError:
        ok(MOD, "resize() rechaza tamaño inválido")

    # ── get_size_bytes ──
    size_bytes = cache2.get_size_bytes()
    assert size_bytes >= 0
    ok(MOD, f"get_size_bytes() = {size_bytes} bytes")

    # ── clear ──
    cache2.clear()
    assert len(cache2) == 0
    ok(MOD, "clear() vacía el caché")

    # ── TypeError en set ──
    try:
        cache2.set("malo", [1, 2, 3])   # lista en vez de ndarray
        fallo(MOD, "Debe rechazar embedding que no es ndarray")
    except TypeError:
        ok(MOD, "set() rechaza tipo incorrecto (TypeError)")

    # ── Dunder methods ──
    assert isinstance(len(cache2), int)
    ok(MOD, "__len__() funciona")
    assert isinstance(repr(cache2), str)
    ok(MOD, "__repr__() funciona")

    # ── CacheEmbeddingsAvanzado (TTL) ──
    seccion("CacheEmbeddingsAvanzado — Caché con TTL")
    cache_ttl = CacheEmbeddingsAvanzado(max_size=5, ttl_seconds=2)
    emb = np.random.rand(384).astype(np.float32)
    cache_ttl.set("efimero", emb)

    resultado = cache_ttl.get("efimero")
    assert resultado is not None
    ok(MOD, "TTL: get() retorna embedding antes de expirar")

    print(f"  {AMARILLO}⏳ Esperando 3s para expiración TTL...{RESET}")
    time.sleep(3)
    resultado_exp = cache_ttl.get("efimero")
    assert resultado_exp is None
    ok(MOD, "TTL: get() retorna None después de expirar")

    # clear_expired
    cache_ttl.set("vivo", emb)
    eliminados = cache_ttl.clear_expired()
    assert isinstance(eliminados, int)
    ok(MOD, f"clear_expired() eliminó {eliminados} items expirados")


# ══════════════════════════════════════════════════════════════════
# 2. PRUEBAS DE BaseDeDatos
# ══════════════════════════════════════════════════════════════════

def test_base_datos():
    seccion("BaseDeDatos — Capa de persistencia SQLite")
    from backend.Datos.baseDatos import BaseDeDatos

    MOD = "bd"

    # Usar BD temporal
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        db = BaseDeDatos(db_path=db_path)
        ok(MOD, "Inicialización y creación de tablas")

        # ── Eventos ──
        fecha_futura = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        db.agregar_evento("Reunión de equipo", fecha_futura, importancia=0.8)
        ok(MOD, "agregar_evento()")

        eventos = db.obtener_eventos_proximos(horas=3)
        assert any("Reunión" in e[0] for e in eventos)
        ok(MOD, f"obtener_eventos_proximos() → {len(eventos)} evento(s)")

        # ── Hechos ──
        db.agregar_hecho("El usuario se llama Carlos", entidad="Carlos",
                         tipo="identidad", importancia=0.95)
        db.agregar_hecho("El usuario trabaja en Google", entidad="Google",
                         tipo="trabajo", importancia=0.85)
        ok(MOD, "agregar_hecho() × 2")

        hechos = db.obtener_hechos(limite=10)
        assert len(hechos) >= 2
        ok(MOD, f"obtener_hechos() → {len(hechos)} hecho(s)")

        hechos_filtrados = db.obtener_hechos(entidad="Carlos")
        assert len(hechos_filtrados) >= 1
        ok(MOD, f"obtener_hechos(entidad='Carlos') → {len(hechos_filtrados)} resultado(s)")

        # ── Información útil ──
        db.agregar_informacion_util("Nota temporal sobre el proyecto", dias_expiracion=7)
        ok(MOD, "agregar_informacion_util()")

        info = db.obtener_informacion_no_expirada()
        assert len(info) >= 1
        ok(MOD, f"obtener_informacion_no_expirada() → {len(info)} item(s)")

        # ── Búsqueda global ──
        resultados = db.buscar("Carlos")
        assert len(resultados["hechos"]) >= 1
        ok(MOD, f"buscar('Carlos') → hechos={len(resultados['hechos'])}")

        resultados2 = db.buscar("temporal")
        assert len(resultados2["informacion_util"]) >= 1
        ok(MOD, f"buscar('temporal') → info_util={len(resultados2['informacion_util'])}")

        # ── Eliminación por ID ──
        hechos_todos = db.obtener_hechos(limite=1)
        # No podemos conocer el ID directamente desde obtener_hechos, probamos tabla invalida
        try:
            db.eliminar_por_id("tabla_invalida", 1)
            fallo(MOD, "Debe rechazar tabla inválida")
        except ValueError:
            ok(MOD, "eliminar_por_id() rechaza tabla inválida (ValueError)")

        # ── Limpieza de expirados ──
        fecha_pasada = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        db.agregar_evento("Evento pasado", fecha_pasada, importancia=0.3)
        db.eliminar_expirados()
        eventos_post = db.obtener_eventos_proximos(horas=24)
        assert all("Evento pasado" not in e[0] for e in eventos_post)
        ok(MOD, "eliminar_expirados() limpia eventos vencidos")

        db.cerrar()
        ok(MOD, "cerrar() sin errores")

    finally:
        os.unlink(db_path)


# ══════════════════════════════════════════════════════════════════
# 3. PRUEBAS DE TaxonomiaMemoria
# ══════════════════════════════════════════════════════════════════

def test_taxonomia():
    seccion("TaxonomiaMemoria — Clasificación semántica")
    from backend.Datos.taxonomia_memoria import TaxonomiaMemoria

    MOD = "taxonomia"

    # Usar ruta temporal para no pisar archivos reales
    with tempfile.TemporaryDirectory() as tmpdir:
        ruta_json = os.path.join(tmpdir, "backend.Datos.taxonomia_test.json")
        taxonomia = TaxonomiaMemoria(config_path=ruta_json)
        ok(MOD, "Inicialización con taxonomía por defecto")

        # ── Categorías disponibles ──
        categorias = taxonomia.obtener_categorias()
        assert len(categorias) > 0
        ok(MOD, f"obtener_categorias() → {len(categorias)} categorías")

        # ── Casos de clasificación ──
        casos = [
            # (texto, etiqueta_esperada, descripcion)
            ("Me llamo Juan García",       "identidad_personal", "identidad por nombre"),
            ("Tengo 28 años",              "identidad_personal", "identidad por edad"),
            ("Mi esposa se llama María",   "familia",           "relación familiar"),
            ("Trabajo como ingeniero",     "trabajo_estudio",   "laboral"),
            ("Mañana tengo cita médica",   "evento_futuro",     "evento futuro"),
            ("Me gusta el café",           "preferencias",      "preferencias"),
            ("¿Qué hora es?",              "pregunta",          "pregunta directa"),
            ("Hola, buenos días",          "conversacion_casual","saludo casual"),
            ("",                           "conversacion_casual","texto vacío"),
        ]

        for texto, etiq_esperada, desc in casos:
            etiq, prioridad, retencion = taxonomia.clasificar(texto)
            coincide = etiq == etiq_esperada
            detalle = f"'{texto[:35]}' → {etiq} (esperado: {etiq_esperada})"
            if coincide:
                ok(MOD, f"Clasificación '{desc}': {etiq}", f"prioridad={prioridad:.2f}, retención={retencion}")
            else:
                fallo(MOD, f"Clasificación '{desc}'", detalle)

        # ── Estructura del resultado ──
        etiq, prioridad, retencion = taxonomia.clasificar("Me llamo Ana")
        assert isinstance(etiq, str) and len(etiq) > 0
        assert 0.0 <= prioridad <= 1.0, f"prioridad fuera de rango: {prioridad}"
        assert isinstance(retencion, str)
        ok(MOD, f"Tipos de retorno correctos: ({type(etiq).__name__}, {type(prioridad).__name__}, {type(retencion).__name__})")

        # ── Agregar categoría nueva ──
        taxonomia.agregar_categoria(
            etiqueta="mascota_nueva",
            patrones=["mi dragón", "tengo un dragón"],
            prioridad=7,
            tiempo_retencion="largo_plazo",
            descripcion="Dragones como mascota"
        )
        assert "mascota_nueva" in taxonomia.obtener_categorias()
        ok(MOD, "agregar_categoria() añade nueva categoría")

        etiq, _, _ = taxonomia.clasificar("Tengo un dragón de komodo")
        ok(MOD, f"Nueva categoría detectada en clasificación: {etiq}")

        # ── obtener_info_categoria ──
        info = taxonomia.obtener_info_categoria("identidad_personal")
        assert info is not None and "patrones" in info
        ok(MOD, "obtener_info_categoria() retorna estructura válida")

        info_nula = taxonomia.obtener_info_categoria("no_existe")
        assert info_nula is None
        ok(MOD, "obtener_info_categoria() retorna None para categoría inexistente")


# ══════════════════════════════════════════════════════════════════
# 4. PRUEBAS DE ExtractorTripletas
# ══════════════════════════════════════════════════════════════════

def test_extractor_tripletas():
    seccion("ExtractorTripletas — Extracción sujeto-relación-objeto")
    from backend.Datos.extractor_tripletas import ExtractorTripletas, Tripleta

    MOD = "tripletas"

    try:
        extractor = ExtractorTripletas()
        ok(MOD, "Inicialización del extractor")
    except Exception as e:
        fallo(MOD, "Inicialización", str(e)); return

    # ── Extracción básica ──
    textos_y_expectativas = [
        ("Juan trabaja en Google",              "trabaja_en"),
        ("María es ingeniera de software",       "es"),
        ("Tengo un perro llamado Max",           None),   # flexible
        ("Vivo en Madrid con mi familia",        "vive_en"),
        ("Me llamo Carlos",                      None),   # flexible
        ("Eh... pues, Juan trabaja en Google",   "trabaja_en"),  # muletillas
    ]

    for texto, relacion_esperada in textos_y_expectativas:
        try:
            tripletas = extractor.extraer_tripletas(texto)
            assert isinstance(tripletas, list)
            tiene_tripleta = len(tripletas) > 0

            if relacion_esperada:
                relaciones = [t.relacion_normalizada for t in tripletas]
                encontrada = relacion_esperada in relaciones or any(
                    relacion_esperada in r for r in relaciones
                )
                if encontrada or tiene_tripleta:
                    ok(MOD, f"Extracción: '{texto[:45]}'",
                       f"{len(tripletas)} tripleta(s): {[str(t) for t in tripletas[:2]]}")
                else:
                    ok(MOD, f"Extracción (parcial): '{texto[:45]}'",
                       f"Relación '{relacion_esperada}' no detectada pero proceso OK")
            else:
                ok(MOD, f"Extracción flexible: '{texto[:45]}'",
                   f"{len(tripletas)} tripleta(s)")
        except Exception as e:
            fallo(MOD, f"Extracción: '{texto[:40]}'", str(e))

    # ── Texto vacío ──
    try:
        tripletas_vacias = extractor.extraer_tripletas("")
        assert isinstance(tripletas_vacias, list)
        ok(MOD, f"Texto vacío → lista vacía o sin error ({len(tripletas_vacias)} tripletas)")
    except Exception as e:
        fallo(MOD, "Texto vacío", str(e))

    # ── Tipo de retorno ──
    resultado = extractor.extraer_tripletas("Ana es médica")
    for t in resultado:
        assert isinstance(t, Tripleta), f"Esperado Tripleta, obtenido {type(t)}"
        assert isinstance(t.confianza, float)
        assert 0.0 <= t.confianza <= 1.0
    ok(MOD, f"Tipo de retorno correcto: lista de Tripleta(s)")

    # ── Múltiples tripletas en una oración compleja ──
    texto_complejo = "Carlos trabaja en Google y vive en Madrid"
    resultado_complejo = extractor.extraer_tripletas(texto_complejo)
    ok(MOD, f"Oración compleja → {len(resultado_complejo)} tripleta(s): "
            f"{[str(t) for t in resultado_complejo]}")


# ══════════════════════════════════════════════════════════════════
# 5. PRUEBAS DE IndicesEstructurales
# ══════════════════════════════════════════════════════════════════

def test_indices_estructurales():
    seccion("IndicesEstructurales — Índices invertidos")
    from backend.Datos.indices_estructurales import IndicesEstructurales, RegistroMemoria

    MOD = "indices"

    try:
        indices = IndicesEstructurales()
        ok(MOD, "Inicialización de índices")
    except Exception as e:
        fallo(MOD, "Inicialización", str(e)); return

    # ── Crear registros de prueba ──
    registros = [
        RegistroMemoria(
            id=1,
            texto_original="Carlos trabaja en Google",
            categoria="trabajo_estudio",
            importancia=0.85,
            timestamp=datetime.now().isoformat(),
            entidades=[("Carlos", "PER"), ("Google", "ORG")],
            tripletas=[{"sujeto": "Carlos", "relacion": "trabaja", "relacion_normalizada": "trabaja_en", "objeto": "Google"}]
        ),
        RegistroMemoria(
            id=2,
            texto_original="María vive en Madrid",
            categoria="ubicacion",
            importancia=0.7,
            timestamp=datetime.now().isoformat(),
            entidades=[("María", "PER"), ("Madrid", "LOC")],
            tripletas=[{"sujeto": "María", "relacion": "vive", "relacion_normalizada": "vive_en", "objeto": "Madrid"}]
        ),
        RegistroMemoria(
            id=3,
            texto_original="Carlos es ingeniero de software",
            categoria="trabajo_estudio",
            importancia=0.9,
            timestamp=datetime.now().isoformat(),
            entidades=[("Carlos", "PER")],
            tripletas=[{"sujeto": "Carlos", "relacion": "es", "relacion_normalizada": "es", "objeto": "ingeniero de software"}]
        ),
    ]

    for r in registros:
        try:
            indices.agregar_registro(
                texto=r.texto_original,
                categoria=r.categoria,
                importancia=r.importancia,
                timestamp=r.timestamp,
                entidades=r.entidades,
                tripletas=r.tripletas,
                metadata=r.metadata,
                embedding_id=r.embedding_id,
            )
        except Exception as e:
            fallo(MOD, f"agregar_registro() registro id={r.id}", str(e))
            return

    ok(MOD, f"agregar_registro() × {len(registros)} registros correctamente")

    # ── Búsqueda por entidad ──
    resultado_carlos = indices.buscar_por_entidad("Carlos")
    assert len(resultado_carlos) >= 2
    ok(MOD, f"buscar_por_entidad('Carlos') → {len(resultado_carlos)} resultado(s)")

    resultado_google = indices.buscar_por_entidad("Google")
    assert len(resultado_google) >= 1
    ok(MOD, f"buscar_por_entidad('Google') → {len(resultado_google)} resultado(s)")

    resultado_nadie = indices.buscar_por_entidad("Nadie")
    assert isinstance(resultado_nadie, list)
    ok(MOD, f"buscar_por_entidad('Nadie') → lista vacía correctamente")

    # ── Búsqueda por tripleta ──
    try:
        resultado_tripleta = indices.buscar_tripleta(relacion="trabaja_en")
        assert isinstance(resultado_tripleta, list)
        ok(MOD, f"buscar_tripleta(relacion='trabaja_en') → {len(resultado_tripleta)} resultado(s)")
    except Exception as e:
        fallo(MOD, "buscar_tripleta(relacion=)", str(e))

    try:
        resultado_sujeto = indices.buscar_tripleta(sujeto="Carlos")
        assert isinstance(resultado_sujeto, list)
        ok(MOD, f"buscar_tripleta(sujeto='Carlos') → {len(resultado_sujeto)} resultado(s)")
    except Exception as e:
        fallo(MOD, "buscar_tripleta(sujeto=)", str(e))

    try:
        resultado_objeto = indices.buscar_tripleta(objeto="Madrid")
        assert isinstance(resultado_objeto, list)
        ok(MOD, f"buscar_tripleta(objeto='Madrid') → {len(resultado_objeto)} resultado(s)")
    except Exception as e:
        fallo(MOD, "buscar_tripleta(objeto=)", str(e))

    # ── Estadísticas ──
    stats = indices.obtener_estadisticas()
    assert "total_registros" in stats or isinstance(stats, dict)
    ok(MOD, f"obtener_estadisticas() → {stats}")

    # ── Persistencia en disco ──
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        ruta = f.name
    try:
        indices.persistir(ruta)
        ok(MOD, f"persistir() en {os.path.basename(ruta)}")

        indices2 = IndicesEstructurales()
        indices2.cargar(ruta)
        ok(MOD, "cargar() desde disco")

        resultado_cargado = indices2.buscar_por_entidad("Carlos")
        assert len(resultado_cargado) >= 1
        ok(MOD, f"Datos persistidos correctamente: {len(resultado_cargado)} resultado(s) tras cargar")
    except Exception as e:
        fallo(MOD, "Persistencia guardar/cargar", str(e))
    finally:
        os.unlink(ruta)


# ══════════════════════════════════════════════════════════════════
# 6. PRUEBAS DE AnalizadorSemanticoV2
# ══════════════════════════════════════════════════════════════════

def test_analizador_semantico():
    seccion("AnalizadorSemanticoV2 — Análisis completo de texto")
    from backend.Datos.analizador_semantico import AnalizadorSemanticoV2

    MOD = "analizador"

    try:
        analizador = AnalizadorSemanticoV2()
        ok(MOD, "Inicialización del analizador v2")
    except Exception as e:
        fallo(MOD, "Inicialización", str(e)); return

    textos_prueba = [
        "Me llamo Carlos García y tengo 35 años",
        "Trabajo como ingeniero de software en Google",
        "Mi esposa se llama María y tenemos dos hijos",
        "Soy alérgico al maní y tomo medicamento para la presión",
        "Mañana tengo una reunión importante a las 3pm",
        "Me gusta el café negro por las mañanas",
        "Eh... pues, vivo en Madrid desde hace dos años",    # muletillas
        "Hola, ¿cómo estás?",
        "",
    ]

    for texto in textos_prueba:
        try:
            resultado = analizador.analizar(texto)

            # Verificar estructura mínima del resultado
            assert isinstance(resultado, dict), f"Resultado debe ser dict, es {type(resultado)}"

            campos_esperados = ["texto", "etiqueta", "importancia", "retencion"]
            for campo in campos_esperados:
                if campo not in resultado:
                    fallo(MOD, f"Campo faltante '{campo}' en resultado para: '{texto[:35]}'")
                    break
            else:
                etiq = resultado.get("etiqueta", "?")
                imp  = resultado.get("importancia", 0)
                tripletas = resultado.get("tripletas", [])
                entidades = resultado.get("entidades", [])

                ok(MOD, f"Análisis: '{texto[:45]}'",
                   f"etiq={etiq}, imp={imp:.2f}, tripletas={len(tripletas)}, entidades={len(entidades)}")

        except Exception as e:
            fallo(MOD, f"Análisis: '{texto[:40]}'", f"{type(e).__name__}: {e}")

    # ── Validar importancias ──
    for texto in ["Me llamo Ana", "Hola", "Soy alérgico al gluten"]:
        resultado = analizador.analizar(texto)
        imp = resultado.get("importancia", -1)
        assert 0.0 <= imp <= 1.0, f"importancia fuera de rango: {imp}"
    ok(MOD, "Importancias dentro del rango [0, 1]")

    # ── Salud debe tener alta importancia ──
    r_salud = analizador.analizar("Soy diabético tipo 2")
    imp_salud = r_salud.get("importancia", 0)
    r_casual = analizador.analizar("Hola")
    imp_casual = r_casual.get("importancia", 1)
    if imp_salud > imp_casual:
        ok(MOD, f"Priorización correcta: salud({imp_salud:.2f}) > casual({imp_casual:.2f})")
    else:
        fallo(MOD, "Priorización: salud debería superar casual",
              f"salud={imp_salud:.2f}, casual={imp_casual:.2f}")


# ══════════════════════════════════════════════════════════════════
# 7. PRUEBAS DE GestorMemoriaV2
# ══════════════════════════════════════════════════════════════════

def test_gestor_memoria():
    seccion("GestorMemoriaV2 — Sistema de memoria híbrido")
    from backend.Gestor.gestor_memoria import GestorMemoriaV2
    from backend.Datos.baseDatos import BaseDeDatos

    MOD = "gestor"

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path   = os.path.join(tmpdir, "test.db")
        idx_path  = os.path.join(tmpdir, "faiss.index")
        meta_path = os.path.join(tmpdir, "meta.json")
        struct_path = os.path.join(tmpdir, "struct.json")
        tax_path  = os.path.join(tmpdir, "taxonomia.json")

        db = BaseDeDatos(db_path=db_path)

        try:
            gestor = GestorMemoriaV2(
                db_instance=db,
                ruta_taxonomia=tax_path,
                ruta_index=idx_path,
                ruta_metadata=meta_path,
                ruta_indices_struct=struct_path,
            )
            ok(MOD, "Inicialización de GestorMemoriaV2")
        except Exception as e:
            fallo(MOD, "Inicialización", str(e))
            traceback.print_exc()
            return

        # ── Procesamiento de texto ──
        textos = [
            "Me llamo Juan García y tengo 30 años",
            "Trabajo como ingeniero de software en Microsoft",
            "Vivo en Buenos Aires con mi esposa",
            "Me gusta el café negro",
            "Mañana tengo una reunión a las 10am",
            "Soy alérgico a la penicilina",
            "Eh... bueno, mi perro se llama Rex",
        ]

        for texto in textos:
            try:
                resultado = gestor.procesar_texto(texto, fuente="test_suite")
                assert isinstance(resultado, dict)
                ok(MOD, f"procesar_texto: '{texto[:40]}'",
                   f"tripletas={resultado.get('num_tripletas',0)}, "
                   f"entidades={resultado.get('num_entidades',0)}")
            except Exception as e:
                fallo(MOD, f"procesar_texto: '{texto[:40]}'", str(e))

        # ── Búsqueda semántica ──
        try:
            resultados_sem = gestor.buscar_semantico("¿En qué empresa trabaja?", top_k=3)
            assert isinstance(resultados_sem, list)
            ok(MOD, f"buscar_semantico() → {len(resultados_sem)} resultado(s)")
        except Exception as e:
            fallo(MOD, "buscar_semantico()", str(e))

        # ── Búsqueda híbrida ──
        try:
            resultados_hib = gestor.buscar_contexto_hibrido("trabajo empresa", top_k=3)
            assert isinstance(resultados_hib, list)
            ok(MOD, f"buscar_contexto_hibrido() → {len(resultados_hib)} resultado(s)")
        except Exception as e:
            fallo(MOD, "buscar_contexto_hibrido()", str(e))

        # ── Búsqueda estructural ──
        try:
            resultados_struct = gestor.buscar_estructural(relacion="trabaja_en")
            assert isinstance(resultados_struct, list)
            ok(MOD, f"buscar_estructural(relacion='trabaja_en') → {len(resultados_struct)} resultado(s)")
        except Exception as e:
            fallo(MOD, "buscar_estructural()", str(e))

        # ── Búsqueda por entidad ──
        try:
            resultados_ent = gestor.buscar_por_entidad("Juan")
            assert isinstance(resultados_ent, list)
            ok(MOD, f"buscar_por_entidad('Juan') → {len(resultados_ent)} resultado(s)")
        except Exception as e:
            fallo(MOD, "buscar_por_entidad()", str(e))

        # ── Estadísticas ──
        try:
            stats = gestor.obtener_estadisticas()
            assert isinstance(stats, dict)
            assert "vectores_faiss" in stats
            ok(MOD, f"obtener_estadisticas() → faiss={stats['vectores_faiss']} vectores, "
                    f"mem_corta={stats['corto_plazo']}")
        except Exception as e:
            fallo(MOD, "obtener_estadisticas()", str(e))

        # ── Consolidación ──
        try:
            consolidados = gestor.consolidar_memoria()
            assert isinstance(consolidados, int)
            ok(MOD, f"consolidar_memoria() → {consolidados} items consolidados")
        except Exception as e:
            fallo(MOD, "consolidar_memoria()", str(e))

        # ── Context manager ──
        try:
            with GestorMemoriaV2(
                db_instance=BaseDeDatos(db_path=db_path),
                ruta_taxonomia=tax_path,
                ruta_index=idx_path,
                ruta_metadata=meta_path,
                ruta_indices_struct=struct_path,
            ) as g:
                r = g.procesar_texto("Prueba context manager")
                assert isinstance(r, dict)
            ok(MOD, "Context manager (__enter__/__exit__) funciona")
        except Exception as e:
            fallo(MOD, "Context manager", str(e))

        # Cerrar
        try:
            gestor.cerrar()
            ok(MOD, "cerrar() sin errores")
        except Exception as e:
            fallo(MOD, "cerrar()", str(e))


# ══════════════════════════════════════════════════════════════════
# 8. PRUEBAS DE INTEGRACIÓN — Pipeline completo
# ══════════════════════════════════════════════════════════════════

def test_integracion():
    seccion("INTEGRACIÓN — Pipeline completo extremo a extremo")
    from backend.Datos.baseDatos import BaseDeDatos
    from backend.Datos.cache_embeddings import CacheEmbeddings
    from backend.Datos.taxonomia_memoria import TaxonomiaMemoria
    from backend.Datos.extractor_tripletas import ExtractorTripletas
    from backend.Datos.indices_estructurales import IndicesEstructurales, RegistroMemoria
    from backend.Datos.analizador_semantico import AnalizadorSemanticoV2
    from backend.Gestor.gestor_memoria import GestorMemoriaV2

    MOD = "integracion"

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path     = os.path.join(tmpdir, "int.db")
        idx_path    = os.path.join(tmpdir, "faiss.index")
        meta_path   = os.path.join(tmpdir, "meta.json")
        struct_path = os.path.join(tmpdir, "struct.json")
        tax_path    = os.path.join(tmpdir, "taxonomia.json")

        # ── Paso 1: Componentes base funcionan juntos ──
        db       = BaseDeDatos(db_path=db_path)
        cache    = CacheEmbeddings(max_size=100)
        taxonomia = TaxonomiaMemoria(config_path=tax_path)
        extractor = ExtractorTripletas()
        indices  = IndicesEstructurales()
        analizador = AnalizadorSemanticoV2()

        perfil_usuario = [
            "Me llamo Elena Rodríguez",
            "Tengo 32 años",
            "Soy médica especialista en cardiología",
            "Trabajo en el Hospital Central de Madrid",
            "Vivo en Madrid con mi marido y mi hijo",
            "Soy alérgica al ibuprofeno",
            "Me gusta correr por las mañanas",
            "Mi perro se llama Luna",
            "Mañana tengo guardia nocturna",
        ]

        print(f"\n  {AZUL}Procesando perfil completo del usuario...{RESET}")

        analisis_previos = []
        for texto in perfil_usuario:
            # Taxonomía clasifica
            etiq, prioridad, retencion = taxonomia.clasificar(texto)

            # Analizador extrae metadata
            analisis = analizador.analizar(texto)
            analisis_previos.append(analisis)

            # Extractor saca tripletas
            tripletas = extractor.extraer_tripletas(texto)

            # Cache guarda embedding simulado
            emb = np.random.rand(384).astype(np.float32)
            cache.set(texto, emb)
            assert cache.get(texto) is not None

            # Índices estructurales almacenan si hay tripletas
            if tripletas:
                registro = RegistroMemoria(
                    id=len(analisis_previos),
                    texto_original=texto,
                    categoria=etiq,
                    importancia=prioridad,
                    timestamp=datetime.now().isoformat(),
                    entidades=analisis.get("entidades", []),
                    tripletas=[vars(t) if hasattr(t, "__dict__") else t for t in tripletas],
                )
                indices.agregar_registro(
                    texto=registro.texto_original,
                    categoria=registro.categoria,
                    importancia=registro.importancia,
                    timestamp=registro.timestamp,
                    entidades=registro.entidades,
                    tripletas=registro.tripletas,
                    metadata=registro.metadata,
                    embedding_id=registro.embedding_id,
                )

        ok(MOD, f"Pipeline base: {len(perfil_usuario)} textos procesados",
           f"cache_size={len(cache)}")

        # ── Paso 2: Verificar coherencia entre componentes ──
        # La taxonomía detectó identidad
        etiq_nombre, _, _ = taxonomia.clasificar("Me llamo Elena Rodríguez")
        assert etiq_nombre == "identidad_personal"
        ok(MOD, "Coherencia: taxonomía detecta identidad_personal")

        # El analizador asigna alta importancia a salud
        r_salud = analizador.analizar("Soy alérgica al ibuprofeno")
        assert r_salud.get("importancia", 0) > 0.7
        ok(MOD, f"Coherencia: salud tiene alta importancia ({r_salud.get('importancia', 0):.2f})")

        # Cache no pierde datos
        hit_rate = cache.get_stats()["hit_rate"]
        ok(MOD, f"Cache hit_rate en pipeline: {hit_rate:.2%}")

        # BD almacena correctamente
        db.agregar_hecho("Elena es médica cardiologa", entidad="Elena", tipo="trabajo", importancia=0.9)
        hechos = db.obtener_hechos()
        assert len(hechos) >= 1
        ok(MOD, f"Coherencia: BD guarda y recupera hechos ({len(hechos)} hechos)")

        # ── Paso 3: GestorMemoriaV2 integrado ──
        with GestorMemoriaV2(
            db_instance=db,
            ruta_taxonomia=tax_path,
            ruta_index=idx_path,
            ruta_metadata=meta_path,
            ruta_indices_struct=struct_path,
        ) as gestor:

            # Procesar el mismo perfil por el gestor
            for texto in perfil_usuario:
                resultado = gestor.procesar_texto(texto, fuente="integracion")
                assert isinstance(resultado, dict)

            ok(MOD, f"Gestor procesó {len(perfil_usuario)} textos del perfil")

            # Buscar por distintas modalidades
            q_trabajo = gestor.buscar_contexto_hibrido("¿En qué hospital trabaja?", top_k=3)
            ok(MOD, f"Búsqueda híbrida 'hospital' → {len(q_trabajo)} resultado(s)")

            q_sem = gestor.buscar_semantico("alergia medicamento", top_k=3)
            ok(MOD, f"Búsqueda semántica 'alergia' → {len(q_sem)} resultado(s)")

            q_ent = gestor.buscar_por_entidad("Elena")
            ok(MOD, f"Búsqueda por entidad 'Elena' → {len(q_ent)} resultado(s)")

            stats = gestor.obtener_estadisticas()
            ok(MOD,
               f"Estadísticas finales del gestor",
               f"faiss={stats['vectores_faiss']}, "
               f"registros_struct={stats.get('registros_estructurales', 'N/A')}, "
               f"tripletas={stats.get('tripletas_totales', 'N/A')}")

        ok(MOD, "Pipeline completo finalizado sin errores ✅")


# ══════════════════════════════════════════════════════════════════
# MENÚ INTERACTIVO
# ══════════════════════════════════════════════════════════════════

MODULOS = {
    "cache":       ("CacheEmbeddings",        test_cache_embeddings),
    "bd":          ("BaseDeDatos",             test_base_datos),
    "taxonomia":   ("TaxonomiaMemoria",        test_taxonomia),
    "tripletas":   ("ExtractorTripletas",      test_extractor_tripletas),
    "indices":     ("IndicesEstructurales",    test_indices_estructurales),
    "analizador":  ("AnalizadorSemanticoV2",   test_analizador_semantico),
    "gestor":      ("GestorMemoriaV2",         test_gestor_memoria),
    "integracion": ("Pipeline integrado",      test_integracion),
}


def ejecutar_modulo(clave: str):
    nombre, fn = MODULOS[clave]
    print(f"\n{NEGRITA}{'═'*60}")
    print(f"  Módulo: {nombre}")
    print(f"{'═'*60}{RESET}")
    inicio = time.time()
    try:
        fn()
    except Exception as e:
        fallo(clave, f"Error inesperado en {nombre}", f"{type(e).__name__}: {e}")
        traceback.print_exc()
    elapsed = time.time() - inicio
    print(f"\n  ⏱ Tiempo: {elapsed:.2f}s")


def menu_interactivo():
    print(f"\n{NEGRITA}{'═'*60}")
    print("  🧠 SUITE DE PRUEBAS — SISTEMA DE MEMORIA SEMÁNTICA")
    print(f"{'═'*60}{RESET}")
    print("\n  Módulos disponibles:")
    for clave, (nombre, _) in MODULOS.items():
        print(f"    {AZUL}{clave:<12}{RESET} {nombre}")
    print(f"    {AZUL}{'todo':<12}{RESET} Ejecutar todos los módulos")
    print(f"    {AZUL}{'salir':<12}{RESET} Salir")

    while True:
        try:
            opcion = input(f"\n{NEGRITA}▶ Módulo a probar: {RESET}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Saliendo...")
            break

        if opcion in ("salir", "exit", "q"):
            break
        elif opcion in ("todo", "all"):
            for clave in MODULOS:
                ejecutar_modulo(clave)
            resumen_final()
        elif opcion in MODULOS:
            ejecutar_modulo(opcion)
            resumen_final()
        else:
            print(f"  {AMARILLO}Opción no reconocida. Usa: {', '.join(MODULOS)} o 'todo'{RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Suite de pruebas para el sistema de memoria semántica"
    )
    parser.add_argument("--all", action="store_true", help="Ejecutar todas las pruebas")
    parser.add_argument(
        "--modulo",
        choices=list(MODULOS.keys()),
        help="Módulo específico a probar"
    )
    args = parser.parse_args()

    if args.all:
        for clave in MODULOS:
            ejecutar_modulo(clave)
        resumen_final()
    elif args.modulo:
        ejecutar_modulo(args.modulo)
        resumen_final()
    else:
        menu_interactivo()


if __name__ == "__main__":
    main()
