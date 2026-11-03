import os, re, json, logging
import numpy as np
from spacy.matcher import PhraseMatcher
from backend.utils.numero_texto import reemplazar_numeros_en_texto
from backend.utils.utils_embedding import cargar_modelo_embeddings_general

logger = logging.getLogger(__name__)

# ----------- CONFIGURACIÓN -----------
UMBRAL_TAREA = 0.75          # Umbral de confianza para bypass directo (modo bajo)
UMBRAL_EMBEDDING_ALTO = 0.70  # Si embedding supera esto → actúa con confianza
UMBRAL_EMBEDDING_BAJO = 0.45  # Si embedding está entre bajo y alto → pasa al LLM

# MODO_HARDWARE:
#   "bajo" → CPU / gráficos integrados. Alta confianza hace bypass directo al handler.
#   "alto" → GPU dedicada. Todo pasa por el LLM para respuestas siempre generativas.
MODO_HARDWARE = "bajo"

# ----------- MODELO SPACY -----------
from backend.utils.utils_nlp import get_nlp, get_imperativos, es_frase_descriptiva
nlp = get_nlp()
matcher = PhraseMatcher(nlp.vocab, attr="LOWER")

# ----------- CARGA DE INTENTS -----------
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INTENTS_JSON_PATH = os.path.join(_BASE_DIR, "importaciones", "intenciones", "intents.json")
print(f"Cargando intents desde: {INTENTS_JSON_PATH}")
if not os.path.exists(INTENTS_JSON_PATH):
    raise FileNotFoundError(f"No se encuentra: {INTENTS_JSON_PATH}")

with open(INTENTS_JSON_PATH, "r", encoding="utf-8") as f:
    intents_config = json.load(f)


# =============================================================================
# CAPA 0: ANÁLISIS ESTRUCTURAL CON spaCy (~3ms, corre antes que todo)
# =============================================================================

# Mapeo imperativo/clítico → intent directo
# Cuando spaCy detecta estos verbos en imperativo, va directo sin pasar por embeddings
_VERBO_A_INTENT = {
    "subir":     "subir_volumen",
    "súbelo":    "subir_volumen",
    "súbela":    "subir_volumen",
    "bajar":     "bajar_volumen",
    "bájalo":    "bajar_volumen",
    "bájala":    "bajar_volumen",
    "silenciar": "bajar_volumen",
    "apagar":    "apagar_sistema",
    "cerrar":    "cerrar_aplicacion",
    "abrir":     "abrir_aplicacion",
    "maximizar": "maximizar_aplicacion",
    "minimizar": "minimizar_aplicacion",
    "capturar":  "tomar_captura",
    "bloquear":  "bloquear_sistema",
    "reiniciar": "reiniciar_sistema",
    "suspender": "suspender_sistema",
    "cifrar":    "cifrar_archivo",
    "descifrar": "descifrar_archivo",
}

def analizar_estructura(texto: str) -> dict:
    """
    Capa 0: extrae señales gramaticales con spaCy.

    Retorna:
    {
        "es_imperativa":  bool   - hay verbo imperativo → señal de tarea
        "es_descriptiva": bool   - gerundio/estado sin acción → señal de conversación
        "intent_directo": str|None - imperativo mapea directo a intent conocido
        "texto_nuclear":  str    - frase simplificada para embeddings (verbo+objeto)
        "doc":            Doc
    }
    """
    doc         = nlp(texto)
    imperativos = get_imperativos(doc)
    descriptiva = es_frase_descriptiva(doc)

    intent_directo = None
    texto_nuclear  = texto

    if imperativos:
        # Buscar mapeo directo imperativo → intent
        for token in imperativos:
            for clave in (token.text.lower(), token.lemma_.lower()):
                if clave in _VERBO_A_INTENT:
                    intent_directo = _VERBO_A_INTENT[clave]
                    break
            if intent_directo:
                break

        # Construir texto nuclear: lemas de imperativos + sustantivos objeto
        # Ej: "está muy bajo el audio súbelo" → "subir audio"
        partes = [t.lemma_ for t in imperativos]
        for token in doc:
            if token.pos_ in ("NOUN", "PROPN") and token.dep_ in ("obj", "dobj", "nsubj"):
                partes.append(token.text)
        if partes:
            texto_nuclear = " ".join(partes)

    return {
        "es_imperativa":  len(imperativos) > 0,
        "es_descriptiva": descriptiva,
        "intent_directo": intent_directo,
        "texto_nuclear":  texto_nuclear,
        "doc":            doc,
    }
# =============================================================================
# CAPA 2: EMBEDDINGS LIVIANOS (sentence-transformers)
# Se inicializa una sola vez al arrancar. ~90MB de RAM.
# =============================================================================
_intent_embeddings = {}  # {intent_name: np.array shape (N, 384)}

# Ruta donde se persisten los embeddings precalculados (junto a intents.json)
_CACHE_EMBEDDINGS_PATH = os.path.join(
    os.path.dirname(INTENTS_JSON_PATH), "intents_embeddings_cache.npz"
)

def _cargar_modelo_embeddings_intencion():
    """Carga el modelo de embeddings la primera vez que se necesita."""
    try:
        modelo = cargar_modelo_embeddings_general()
        logger.info("✅ Modelo de embeddings cargado correctamente.")
        return modelo
    except Exception as e:
        logger.error(f"❌ No se pudo cargar el modelo de embeddings: {e}")
        return None

def _cache_valida() -> bool:
    """True si el cache existe y es mas nuevo que intents.json."""
    if not os.path.exists(_CACHE_EMBEDDINGS_PATH):
        return False
    return os.path.getmtime(_CACHE_EMBEDDINGS_PATH) >= os.path.getmtime(INTENTS_JSON_PATH)

def _precalcular_embeddings_intents():
    """
    Primera vez: genera los embeddings y los guarda en disco (.npz).
    Arranques siguientes: los carga directamente sin tocar el modelo,
    ahorrando varios segundos de startup.
    El cache se invalida automaticamente si editas intents.json.
    """
    global _intent_embeddings

    # Intentar cargar desde disco
    if _cache_valida():
        try:
            data = np.load(_CACHE_EMBEDDINGS_PATH, allow_pickle=False)
            _intent_embeddings = {k: data[k] for k in data.files}
            logger.info(f"⚡ Embeddings cargados desde cache ({len(_intent_embeddings)} intents).")
            return
        except Exception as e:
            logger.warning(f"⚠️ No se pudo leer cache, regenerando: {e}")

    # Calcular desde cero
    model = _cargar_modelo_embeddings_intencion()
    if not model:
        return

    for intent_name, datos in intents_config.items():
        ejemplos = datos.get("ejemplos", [])
        if ejemplos:
            vectors = model.encode(ejemplos, convert_to_numpy=True, normalize_embeddings=True)
            _intent_embeddings[intent_name] = vectors

    # Guardar en disco para el proximo arranque
    try:
        np.savez(_CACHE_EMBEDDINGS_PATH, **_intent_embeddings)
        logger.info(f"💾 Cache de embeddings guardado en: {_CACHE_EMBEDDINGS_PATH}")
    except Exception as e:
        logger.warning(f"⚠️ No se pudo guardar cache: {e}")

    logger.info(f"✅ Embeddings precalculados para {len(_intent_embeddings)} intents.")

# Precalcular (o cargar desde cache) al importar el modulo
_precalcular_embeddings_intents()


def _similitud_coseno(vec_a: np.ndarray, matriz_b: np.ndarray) -> np.ndarray:
    """
    Calcula similitud coseno entre un vector y una matriz de vectores.
    Asume vectores ya normalizados → producto punto directo.
    """
    return np.dot(matriz_b, vec_a)


def clasificar_con_embeddings(texto: str):
    """
    Capa 2: Clasificación por similitud semántica.

    Retorna:
        (intent_name, score, "seguro")    si score >= UMBRAL_EMBEDDING_ALTO
        (intent_name, score, "dudoso")    si UMBRAL_EMBEDDING_BAJO <= score < UMBRAL_EMBEDDING_ALTO
        (None, score, "no_sabe")          si score < UMBRAL_EMBEDDING_BAJO
    """
    model = _cargar_modelo_embeddings_intencion()
    if not model or not _intent_embeddings:
        return None, 0.0, "no_sabe"

    vec_texto = model.encode([texto], convert_to_numpy=True, normalize_embeddings=True)[0]

    mejor_intent = None
    mejor_score = -1.0

    for intent_name, matriz in _intent_embeddings.items():
        similitudes = _similitud_coseno(vec_texto, matriz)
        score_max = float(np.max(similitudes))
        if score_max > mejor_score:
            mejor_score = score_max
            mejor_intent = intent_name

    if mejor_score >= UMBRAL_EMBEDDING_ALTO:
        estado = "seguro"
    elif mejor_score >= UMBRAL_EMBEDDING_BAJO:
        estado = "dudoso"
    else:
        estado = "no_sabe"

    logger.debug(f"📐 Embedding: '{texto}' → {mejor_intent} ({mejor_score:.3f}) [{estado}]")
    return mejor_intent, mejor_score, estado




# =============================================================================
# UTILIDADES DE TEXTO
# =============================================================================
def limpiar_texto(texto):
    frases_inutiles = [
        "por favor", "podrías", "puedes", "porfa", "me puedes", "me podrías",
        "dime", "decime", "quiero que", "quisiera", "serías tan amable de", "bro", "oye",
        "hermano", "hermana", "amigo", "amiga", "asistente", "asistenta",
        "harias el favor de", "podrías hacerme el favor de", "señor", "quiero"
    ]
    texto = texto.lower()
    for frase in frases_inutiles:
        texto = texto.replace(frase, "")
    texto = texto.strip()

    return reemplazar_numeros_en_texto(texto)


def detectar_emocion(texto):
    if not isinstance(texto, str):
        try:
            texto = str(texto)
        except Exception:
            return None
    texto = texto.lower()
    emociones = {
        "triste": ["estoy triste", "me siento mal", "ando bajoneado", "no estoy bien"],
        "feliz": ["estoy feliz", "me siento bien", "estoy contento", "todo bien"],
        "enojado": ["estoy enojado", "me molesta", "ando furioso", "estoy harto"],
        "ansioso": ["estoy nervioso", "tengo ansiedad", "me preocupa", "estoy estresado"],
    }
    for emocion, frases in emociones.items():
        for frase in frases:
            if frase in texto:
                return emocion
    return None


def reformular_texto(texto):
    try:
        from backend.Generacion.AIGeneration import generar_ayudas
    except ImportError:
        logger.error("No se pudo importar generar_ayudas.")
        return texto

    prompt = f"Reformula esta oración para que sea más clara para una IA clasificadora: '{texto}'"
    texto_reformulado = generar_ayudas(prompt)

    if hasattr(texto_reformulado, "__iter__") and not isinstance(texto_reformulado, (str, bytes)):
        acumulado = ""
        try:
            for fragmento in texto_reformulado:
                if fragmento is None:
                    continue
                if not isinstance(fragmento, str):
                    fragmento = str(fragmento)
                if fragmento.strip():
                    acumulado += fragmento.strip() + " "
        except TypeError:
            acumulado = str(texto_reformulado)
        texto_reformulado = acumulado.strip()

    if texto_reformulado is None:
        texto_reformulado = ""
    if not isinstance(texto_reformulado, str):
        texto_reformulado = str(texto_reformulado)

    return texto_reformulado


def extraer_parametros(resto_texto, params_def):
    palabras = resto_texto.split()
    params = {}
    for param, param_info in params_def.items():
        keyword = param_info.get("keyword")
        if keyword is None:
            params[param] = " ".join(palabras)
        else:
            try:
                idx = palabras.index(keyword)
                next_keywords = [p.get("keyword") for p in params_def.values() if p.get("keyword")]
                next_idx = len(palabras)
                for nk in next_keywords:
                    try:
                        nk_idx = palabras.index(nk, idx + 1)
                        next_idx = min(next_idx, nk_idx)
                    except ValueError:
                        pass
                params[param] = " ".join(palabras[idx + 1:next_idx])
            except ValueError:
                params[param] = ""
    return params

_PALABRAS_CONECTORAS = {
    "luego", "entonces", "después", "despues", "si", "cuando",
    "ahora", "mismo", "ya", "porfavor", "gracias", "ok",
    "por", "favor", "también", "tambien",
}

def _limpiar_nombre_app(nombre: str) -> str:
    """
    Elimina del nombre de una app las palabras que no pueden ser parte
    de un nombre de aplicación: conectores, adverbios de tiempo, cortesías.

    Ejemplos:
        "chrome luego"     → "chrome"
        "spotify entonces" → "spotify"
        "discord si"       → "discord"
    """
    if not nombre:
        return nombre
    palabras = nombre.strip().split()
    # Recortar desde el final mientras la última palabra sea conectora
    while palabras and palabras[-1].lower() in _PALABRAS_CONECTORAS:
        palabras.pop()
    # Recortar desde el inicio también por si acaso
    while palabras and palabras[0].lower() in _PALABRAS_CONECTORAS:
        palabras.pop(0)
    return " ".join(palabras)


def detectar_intencion_con_contexto(texto, intents):
    """Capa 1: Coincidencia exacta de sinónimos."""
    palabras = texto.lower().split()
    candidatos = []
    for intent, datos in intents.items():
        for sinonimo in datos.get("synonyms", []):
            sp = sinonimo.lower().split()
            l = len(sp)
            for i in range(len(palabras) - l + 1):
                if palabras[i:i + l] == sp:
                    candidatos.append({
                        "intent": intent,
                        "sinonimo": sinonimo,
                        "start": i,
                        "length": l
                    })

    if not candidatos:
        return None, None

    min_start = min(c["start"] for c in candidatos)
    grupo = [c for c in candidatos if c["start"] == min_start]

    if len(grupo) == 1:
        return grupo[0]["intent"], grupo[0]["sinonimo"]
    for corto in sorted(grupo, key=lambda x: x["length"]):
        resto_start = corto["start"] + corto["length"]
        if resto_start < len(palabras):
            segunda = palabras[resto_start]
            for otro in grupo:
                sp_otro = otro["sinonimo"].lower().split()
                if (
                    otro["intent"] != corto["intent"]
                    and len(sp_otro) > corto["length"]
                    and len(sp_otro) > 1
                    and sp_otro[1] == segunda
                ):
                    return otro["intent"], otro["sinonimo"]

    mejor = max(grupo, key=lambda x: x["length"])
    return mejor["intent"], mejor["sinonimo"]


def es_fragmento_valido(fragmento):
    fragmento = fragmento.strip()
    if not fragmento:
        return False
    if len(fragmento.split()) <= 2:
        palabras_validas_solas = ["sí", "no", "hola", "adiós", "gracias", "ok", "bien", "mal"]
        if fragmento.lower() not in palabras_validas_solas:
            return False
    patrones_incompletos = [
        r'^(el|la|los|las|un|una|unos|unas)\s+\w+$',
        r'^(de|del|con|sin|para|por|entre)\s+',
        r'^\w+$',
    ]
    for patron in patrones_incompletos:
        if re.match(patron, fragmento.lower()):
            return False
    return True


def unir_fragmentos_conversacion(acciones_detectadas):
    if len(acciones_detectadas) <= 1:
        return acciones_detectadas

    resultado = []
    i = 0
    while i < len(acciones_detectadas):
        accion_actual = acciones_detectadas[i]
        fragmentos_a_unir = [accion_actual]
        j = i + 1

        while j < len(acciones_detectadas):
            accion_siguiente = acciones_detectadas[j]
            actual_es_conversacion = accion_actual["tipo"] == "conversacion"
            siguiente_es_conversacion = accion_siguiente["tipo"] == "conversacion"
            actual_es_preguntar = accion_actual["accion"] == "preguntar"
            siguiente_es_preguntar = accion_siguiente["accion"] == "preguntar"
            actual_fusionable = actual_es_conversacion or actual_es_preguntar
            siguiente_fusionable = siguiente_es_conversacion or siguiente_es_preguntar

            deberia_unir = actual_fusionable and siguiente_fusionable

            if deberia_unir:
                fragmentos_a_unir.append(accion_siguiente)
                j += 1
                accion_actual = accion_siguiente
            else:
                break

        if len(fragmentos_a_unir) > 1:
            textos_unidos = []
            for frag in fragmentos_a_unir:
                if frag["texto"].strip():
                    textos_unidos.append(frag["texto"])
                elif frag["accion"] == "conversacion" and "mensaje" in frag["params"]:
                    textos_unidos.append(frag["params"]["mensaje"])
            texto_completo = " y ".join(textos_unidos)
            resultado.append({
                "tipo": "conversacion",
                "score": max(frag["score"] for frag in fragmentos_a_unir),
                "texto": texto_completo,
                "accion": "conversacion",
                "params": {"mensaje": texto_completo}
            })
        else:
            resultado.append(accion_actual)

        i = j
    return resultado


# =============================================================================
# CLASIFICADOR EN CASCADA — 4 CAPAS
# Capa 0 (spaCy) → Capa 1 (sinónimos) → Capa 2 (embeddings) → LLM con tools
# =============================================================================

# Pares de intents opuestos. Si la polaridad contradice el intent clasificado,
# se invierte al opuesto. Solo aplica cuando hay señal de queja clara.
_PARES_OPUESTOS = {
    "subir_volumen": "bajar_volumen",
    "bajar_volumen": "subir_volumen",
}

def _tiene_senal_queja(doc) -> bool:
    """
    Detecta si una frase descriptiva contiene señal de problema implícito.
    Solo decide si merece pasar a embeddings en vez de cortarse como conversación.
    No resuelve el intent — eso lo hace embeddings + corrección de polaridad.
    """
    from utils.utils_nlp import _VERBOS_PERCEPCION, _PALABRAS_EXCESO, _VERBOS_MOLESTIA
    tokens = [t for t in doc]
    for i, token in enumerate(tokens):
        # Negación sobre verbo de percepción: "no escucho", "no se escucha"
        if token.lemma_.lower() in _VERBOS_PERCEPCION:
            tiene_neg = any(c.text.lower() == "no" for c in token.children)
            if not tiene_neg:
                tiene_neg = any(
                    tokens[j].text.lower() == "no"
                    for j in range(max(0, i - 3), i)
                )
            if tiene_neg:
                return True
        # Adjetivo/adverbio de exceso
        if token.text.lower() in _PALABRAS_EXCESO or token.lemma_.lower() in _PALABRAS_EXCESO:
            return True
        # Verbo de molestia: "me está quemando", "me molesta"
        if token.lemma_.lower() in _VERBOS_MOLESTIA:
            return True
        # "casi no/nada/nunca" → defecto
        if token.text.lower() == "casi" and i + 1 < len(tokens):
            if tokens[i + 1].text.lower() in ("no", "nada", "nunca"):
                return True
        # "demasiado/demasiada" → exceso
        if token.text.lower() in ("demasiado", "demasiada"):
            return True
    return False


def clasificar_subcomando(sub: str, señales: dict = None):
    """
    Retorna: (intent_name, matched_sinonimo, score, tipo)
    señales: resultado de analizar_estructura(), None para calcularlo aquí.
    """
    if señales is None:
        señales = analizar_estructura(sub)

    # ── CAPA 0: spaCy ─────────────────────────────────────────────────────────

    # A) Frase descriptiva sin imperativo → conversación directa
    #    EXCEPTO si contiene señal de queja implícita → dejar caer a embeddings
    if señales["es_descriptiva"] and not señales["es_imperativa"]:
        if not _tiene_senal_queja(señales["doc"]):
            logger.debug("🧠 Capa 0: descriptiva → conversacion")
            return None, None, 0.9, "conversacion"
        # Tiene señal de queja: continuar al pipeline normal

    # B) Imperativo con mapeo directo → intent sin pasar por embeddings
    #    Resuelve: "súbelo" → subir_volumen directamente
    if señales["intent_directo"]:
        logger.debug(f"🧠 Capa 0: imperativo directo → {señales['intent_directo']}")
        return señales["intent_directo"], None, 0.95, "tarea"

    # Si hay imperativo usar texto_nuclear (verbo+objeto sin ruido adjetival)
    texto_para_clasificar = señales["texto_nuclear"] if señales["es_imperativa"] else sub

    # ── PRE-CAPA 1: Detección de negación explícita ───────────────────────────
    from backend.utils.utils_nlp import analizar_polaridad
    polaridad = analizar_polaridad(señales["doc"])
    if polaridad["es_negada"]:
        logger.debug("🚫 Capa 0: acción negada → en_mantenimiento")
        return "en_mantenimiento", None, 1.0, "tarea"

    # ── CAPA 1: Sinónimos exactos ──────────────────────────────────────────────
    intent_name, matched = detectar_intencion_con_contexto(sub, intents_config)
    if intent_name:
        logger.debug(f"✅ Capa 1: '{matched}' → {intent_name}")
        return intent_name, matched, 1.0, "tarea"

    # ── CAPA 2: Embeddings semánticos ─────────────────────────────────────────
    intent_emb, score_emb, estado_emb = clasificar_con_embeddings(texto_para_clasificar)

    es_queja = polaridad["queja_exceso"] or polaridad["queja_defecto"]

    if intent_emb in _PARES_OPUESTOS and estado_emb in ("seguro", "dudoso"):
        opuesto = _PARES_OPUESTOS[intent_emb]
        if intent_emb == "bajar_volumen" and polaridad["queja_defecto"]:
            logger.debug(f"↔ Polaridad corrige: {intent_emb} → {opuesto}")
            intent_emb = opuesto
        elif intent_emb == "subir_volumen" and polaridad["queja_exceso"]:
            logger.debug(f"↔ Polaridad corrige: {intent_emb} → {opuesto}")
            intent_emb = opuesto

    elif es_queja and (intent_emb == "conversacion" or estado_emb == "no_sabe"):
        # Embeddings no encontró tarea concreta pero hay queja confirmada.
        # Construir texto reducido con sustantivos + adjetivos de la frase
        # para que embeddings tenga mejor señal.
        tokens_clave = [
            t.lemma_ for t in señales["doc"]
            if t.pos_ in ("NOUN", "PROPN", "ADJ") and len(t.text) > 2
        ]
        if tokens_clave:
            texto_reducido = " ".join(tokens_clave)
            logger.debug(f"🔁 Queja sin intent: reintentando embeddings con '{texto_reducido}'")
            intent_emb2, score_emb2, estado_emb2 = clasificar_con_embeddings(texto_reducido)
            if intent_emb2 and intent_emb2 != "conversacion" and estado_emb2 in ("seguro", "dudoso"):
                # Aplicar corrección de polaridad también al resultado del reintento
                if intent_emb2 in _PARES_OPUESTOS:
                    opuesto2 = _PARES_OPUESTOS[intent_emb2]
                    if intent_emb2 == "bajar_volumen" and polaridad["queja_defecto"]:
                        intent_emb2 = opuesto2
                    elif intent_emb2 == "subir_volumen" and polaridad["queja_exceso"]:
                        intent_emb2 = opuesto2
                logger.debug(f"✅ Reintento queja: '{texto_reducido}' → {intent_emb2}")
                return intent_emb2, None, score_emb2, "tarea"

    if estado_emb == "seguro":
        if intent_emb == "conversacion":
            return None, None, score_emb, "conversacion"
        return intent_emb, None, score_emb, "tarea"

    if estado_emb == "dudoso":
        # Antes iba a RoBERTa — ahora delegamos al LLM con tools
        # En modo alto siempre delega; en modo bajo también (no hay suficiente confianza)
        logger.debug(f"⚠️  Capa 2 dudoso ({score_emb:.3f}) → delegando al LLM")
        return None, None, score_emb, "llm"

    # Capa 2 no sabe → delegar al LLM con tools
    logger.debug("❓ Capa 2 no sabe → delegando al LLM")
    return None, None, score_emb, "llm"


# =============================================================================
# ANÁLISIS PRINCIPAL
# =============================================================================
def analizar_intencion(texto):
    texto = limpiar_texto(texto)
    señales_completas = analizar_estructura(texto) #spacy
    subcomandos = [s.strip() for s in re.split(r' y | luego |,', texto) if s.strip()]
    acciones_detectadas = []
    apps_to_open = []
    collecting_apps = False

    for sub in subcomandos:
        señales_sub = señales_completas if sub == texto else analizar_estructura(sub)
        intent_name, matched, score, tipo = clasificar_subcomando(sub, señales_sub)

        if intent_name == "abrir_aplicacion":
            resto = sub.lower().replace((matched or "").lower(), "", 1).strip() if matched else sub
            datos = intents_config[intent_name]
            params = extraer_parametros(resto, datos.get("params", {}))
            app_name = _limpiar_nombre_app(params.get("nombre_app", ""))
            if app_name:
                apps_to_open.append(app_name)
                collecting_apps = True

        elif collecting_apps and intent_name:
            # El fragmento siguiente al bloque de apps es una acción distinta:
            # cerrar el colector y registrar las apps acumuladas primero.
            if apps_to_open:
                acciones_detectadas.append({
                    "tipo": "tarea", "score": 1.0, "texto": " y ".join(apps_to_open),
                    "accion": "abrir_aplicacion",
                    "params": {"nombre_app": " y ".join(apps_to_open)}
                })
                apps_to_open = []
                collecting_apps = False
            resto = sub.lower().replace((matched or "").lower(), "", 1).strip() if matched else sub
            datos = intents_config[intent_name]
            params = extraer_parametros(resto, datos.get("params", {}))
            acciones_detectadas.append({
                "tipo": "tarea", "score": score, "texto": sub,
                "accion": intent_name, "params": params
            })

        elif collecting_apps:
            # Fragmento sin intent propio después de abrir_aplicacion.
            # Distinguir con spaCy:
            #   - Sin verbo → es otro nombre de app ("spotify", "discord")
            #   - Con verbo → es un comando que el clasificador no reconoció
            #                 ("busca gatos", "reproduce música") → cerrar colector
            doc_sub = nlp(sub)
            tiene_verbo = any(t.pos_ == "VERB" for t in doc_sub)

            if tiene_verbo:
                # Cerrar el colector de apps primero
                if apps_to_open:
                    acciones_detectadas.append({
                        "tipo": "tarea", "score": 1.0,
                        "texto": " y ".join(apps_to_open),
                        "accion": "abrir_aplicacion",
                        "params": {"nombre_app": " y ".join(apps_to_open)}
                    })
                    apps_to_open = []
                    collecting_apps = False
                # Registrar el fragmento como conversacion (no se reconoció su intent)
                acciones_detectadas.append({
                    "tipo": "conversacion", "score": 0.5, "texto": sub,
                    "accion": "conversacion", "params": {"mensaje": sub}
                })
            else:
                # Sin verbo → es otro nombre de app
                app_name = _limpiar_nombre_app(sub.strip())
                if app_name:
                    apps_to_open.append(app_name)

        else:
            if intent_name:
                if intent_name == "en_mantenimiento":
                    acciones_detectadas.append({
                        "tipo": "tarea", "score": score, "texto": sub,
                        "accion": "en_mantenimiento", "params": {}
                    })
                else:
                    resto = sub.lower().replace((matched or "").lower(), "", 1).strip() if matched else sub
                    datos = intents_config[intent_name]
                    params = extraer_parametros(resto, datos.get("params", {}))
                    acciones_detectadas.append({
                        "tipo": "tarea", "score": score, "texto": sub,
                        "accion": intent_name, "params": params
                    })
            elif tipo == "llm":
                # Embedding no supo → el LLM decide con tools
                acciones_detectadas.append({
                    "tipo": "llm", "score": score, "texto": sub,
                    "accion": "llm", "params": {"mensaje": sub}
                })
            elif tipo == "tarea":
                acciones_detectadas.append({
                    "tipo": "tarea", "score": score, "texto": sub,
                    "accion": "preguntar",
                    "params": {"mensaje": f"No entendí '{sub}'. ¿Puedes reformular?"}
                })
            else:
                acciones_detectadas.append({
                    "tipo": "conversacion", "score": score, "texto": sub,
                    "accion": "conversacion", "params": {"mensaje": sub}
                })

    if apps_to_open:
        acciones_detectadas.append({
            "tipo": "tarea", "score": 1.0, "texto": " y ".join(apps_to_open),
            "accion": "abrir_aplicacion",
            "params": {"nombre_app": " y ".join(apps_to_open)}
        })

    acciones_detectadas = unir_fragmentos_conversacion(acciones_detectadas)

    # Deduplicar
    final = []
    seen = set()
    for a in acciones_detectadas:
        key = (a["accion"], tuple(sorted(a["params"].items())))
        if key not in seen:
            seen.add(key)
            final.append(a)

    # Unificar apps
    apps = [a["params"]["nombre_app"] for a in final if a["accion"] == "abrir_aplicacion"]
    final = [a for a in final if a["accion"] != "abrir_aplicacion"]
    if apps:
        final.append({
            "tipo": "tarea", "score": 1.0, "texto": "",
            "accion": "abrir_aplicacion",
            "params": {"nombre_app": " y ".join(apps)}
        })

    print(final)
    return final


def procesar_intencion(texto):
    emocion = detectar_emocion(texto)
    if emocion:
        return [{"accion": "emocion_detectada", "params": {"emocion": emocion}}]

    analisis = analizar_intencion(texto)

    if not analisis or all(a["accion"] == "preguntar" for a in analisis):
        # No se entendió por ninguna capa — delegar al LLM con tools directamente
        logger.debug("❓ Ninguna capa resolvió la intención → delegando al LLM")
        return [{"tipo": "llm", "accion": "llm", "params": {"mensaje": texto}, "score": 0.0}]

    return analisis


def accion_pedir_mas_contexto(prompt_base):
    try:
        from backend.Funciones.funcionesSistema import decir_y_escuchar
    except ImportError:
        logger.error("No se pudo importar decir_y_escuchar.")
        return ""

    pregunta = f"{prompt_base} ¿Puedes ampliar un poco más sobre eso?"
    respuesta_usuario = decir_y_escuchar(pregunta)
    if respuesta_usuario:
        return respuesta_usuario
    return "Lo siento, no entendí tu respuesta. ¿Puedes repetirlo?"


# =============================================================================
# PRUEBAS
# =============================================================================
if __name__ == "__main__":
    ejemplos = [
        # Capa 1 debería resolver estos
        "dime las diferencias entre el agua y el fuego",
        "poner el brillo a treinta y subir el volumen",
        "abre chrome y firefox",
        "cuéntame sobre la historia y la geografía de colombia",
        # Capa 2 debería resolver estos
        "necesito que abras el navegador",
        "está muy bajo el audio, súbelo",
        "quiero ver las noticias de hoy",
        "pon un temporizador de 5 minutos",
        # Casos ambiguos para Capa 3
        "se me está pasando la hora muy rápido",
        "muévelo hacia arriba",
    ]
    for e in ejemplos:
        print(f"\n🔍 '{e}'")
        procesar_intencion(e)