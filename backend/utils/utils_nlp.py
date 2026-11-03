"""
utils/utils_nlp.py
------------------
Instancia única compartida de spaCy para todo el proyecto.

USO en cualquier módulo:
    from backend.utils.utils_nlp import get_nlp

    nlp = get_nlp()
    doc = nlp("tu texto aquí")
"""

import logging
import threading
import spacy

logger = logging.getLogger(__name__)

_nlp   = None
_lock  = threading.Lock()
_MODELO = "es_core_news_md"

# Verbos que por sí solos indican estado, NO acción ejecutable
# IMPORTANTE: "ver" fue removido — "quiero ver las noticias" ES una tarea
_VERBOS_ESTADO_PURO = {
    "estar", "ser", "parecer", "sentir", "notar",
    "creer", "opinar", "resultar", "volverse"
}

# Verbos de deseo/modalidad que ANTECEDEN a una acción real
# "quiero VER", "necesito ABRIR" → la acción real es el segundo verbo
_VERBOS_MODALIDAD = {
    "querer", "necesitar", "poder", "deber", "desear",
    "pensar", "intentar", "tratar", "esperar"
}

# Clíticos que se adhieren a verbos imperativos en español
_CLITICOS = ("lo", "la", "los", "las", "le", "les", "me", "te", "se", "nos")


# =============================================================================
# SINGLETON
# =============================================================================
def get_nlp():
    """Retorna la instancia única de spaCy (thread-safe)."""
    global _nlp
    if _nlp is not None:
        return _nlp
    with _lock:
        if _nlp is not None:
            return _nlp
        try:
            logger.info(f"⏳ Cargando spaCy ({_MODELO})...")
            _nlp = spacy.load(_MODELO)
            logger.info("✅ spaCy cargado.")
        except OSError:
            logger.warning(f"⚠ Modelo '{_MODELO}' no encontrado. Descargando...")
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "spacy", "download", _MODELO], check=True)
            _nlp = spacy.load(_MODELO)
            logger.info("✅ spaCy descargado y cargado.")
    return _nlp


# =============================================================================
# HELPERS PÚBLICOS
# =============================================================================
def analizar(texto: str):
    """Shortcut: analiza texto y retorna doc."""
    return get_nlp()(texto)


def get_verbos(doc) -> list:
    return [t for t in doc if t.pos_ == "VERB"]


def get_imperativos(doc) -> list:
    """
    Retorna verbos en modo imperativo.
    Incluye fallback para clíticos adheridos como 'súbelo', 'muévelo'.
    """
    imperativos = []
    for token in doc:
        if token.pos_ == "VERB":
            morph = token.morph.to_dict()
            if morph.get("Mood") == "Imp":
                imperativos.append(token)
            elif _tiene_clitico(token.text):
                imperativos.append(token)
    return imperativos


def get_sustantivos(doc) -> list:
    return [t for t in doc if t.pos_ in ("NOUN", "PROPN")]


def get_adjetivos(doc) -> list:
    return [t for t in doc if t.pos_ == "ADJ"]


def get_sujeto(doc):
    for token in doc:
        if token.dep_ in ("nsubj", "nsubjpass"):
            return token
    return None


def get_objeto(doc):
    for token in doc:
        if token.dep_ in ("obj", "dobj"):
            return token
    return None


def es_frase_imperativa(doc) -> bool:
    return len(get_imperativos(doc)) > 0


def es_frase_descriptiva(doc) -> bool:
    """
    True SOLO si la frase es genuinamente descriptiva/conversacional.
    
    Reglas (todas deben cumplirse):
      1. No hay ningún imperativo
      2. No hay verbo de modalidad seguido de acción (quiero ver, necesito abrir)
      3. El verbo principal es de estado puro O es gerundio
         sin objeto accionable concreto

    Casos que NO son descriptivos (aunque tengan verbo de estado):
      - "quiero ver las noticias"   → modalidad + acción + objeto
      - "la pantalla está muy oscura" → implica acción (ajustar brillo)
      - "muévelo hacia arriba"      → imperativo con clítico

    Casos que SÍ son descriptivos:
      - "se me está pasando la hora rápido" → gerundio, sin objeto, sin acción
      - "hola cómo estás"                  → verbo estado, saludo
      - "qué piensas sobre esto"           → verbo estado, opinión
    """
    imperativos = get_imperativos(doc)
    if imperativos:
        return False  # Imperativo → siempre es tarea

    verbos = [t for t in doc if t.pos_ == "VERB"]
    if not verbos:
        return False  # Sin verbos → dejar que embeddings decida

    # Verificar si hay patrón modalidad + acción
    # Ej: "quiero ver", "necesito abrir", "quiero encriptar"
    for i, token in enumerate(verbos):
        if token.lemma_ in _VERBOS_MODALIDAD:
            # Buscar si hay otro verbo después (la acción real)
            for otro in verbos[i+1:]:
                if otro.lemma_ not in _VERBOS_MODALIDAD and otro.lemma_ not in _VERBOS_ESTADO_PURO:
                    # Hay un verbo de acción real después del modal → NO es descriptiva
                    return False

    # Verificar si el verbo principal es de estado puro o gerundio
    for token in verbos:
        morph = token.morph.to_dict()
        es_gerundio    = morph.get("VerbForm") == "Ger"
        es_estado_puro = token.lemma_ in _VERBOS_ESTADO_PURO

        if es_gerundio or es_estado_puro:
            # Verificar que no haya objeto accionable
            # Si hay objeto concreto, probablemente es tarea
            objeto = get_objeto(doc)
            if objeto is None:
                return True  # Gerundio/estado sin objeto → descriptiva

            # Hay objeto: verificar si es accionable (sustantivo concreto)
            # Palabras que en contexto de "estar" sugieren acción pendiente
            objetos_accionables = {
                "pantalla", "volumen", "brillo", "audio", "sonido",
                "archivo", "ventana", "aplicacion", "app", "sistema"
            }
            if objeto.lemma_.lower() not in objetos_accionables:
                return True  # Objeto no accionable → descriptiva

    return False


# =============================================================================
# ANÁLISIS DE POLARIDAD E INTENCIÓN IMPLÍCITA
# =============================================================================

# Verbos de percepción del usuario (primera persona)
# Cuando están negados o modificados negativamente → implican un problema
_VERBOS_PERCEPCION = {
    "escuchar", "oír", "ver", "notar", "sentir", "distinguir", "entender"
}

# Adjetivos/participios que expresan exceso (implican "bajar/reducir")
_PALABRAS_EXCESO = {
    "fuerte", "alto", "ruidoso", "ensordecedor", "molesto",
    "brillante", "cegador", "encandilador", "intenso", "quemando",
    "quema", "demasiado", "exagerado", "insoportable"
}

# Adjetivos/adverbios que expresan defecto (implican "subir/aumentar")
# NOTA: "casi" NO va aquí — solo es defecto si va seguido de "no/nada/nunca",
# ese caso lo maneja el bloque especial en analizar_polaridad.
# Ponerlo aquí causaría falsos positivos en "casi termino", "casi listo", etc.
_PALABRAS_DEFECTO = {
    "bajo", "silencioso", "inaudible", "oscuro", "apagado",
    "tenue", "opaco", "nada", "apenas", "poco"
}

# Verbos que al estar en forma continua/gerundio con sujeto del sistema
# expresan problema: "la pantalla me está quemando"
_VERBOS_MOLESTIA = {
    "quemar", "molestar", "lastimar", "doler", "dañar",
    "cansar", "fatigar", "encandil", "cegar","reventar", "ensordecer", "picar"  
}


def analizar_polaridad(doc) -> dict:
    """
    Analiza si la frase expresa un estado problemático que implica acción correctiva.

    Detecta tres cosas independientemente con sintaxis spaCy:
      1. Negación explícita sobre verbo de acción del asistente
         → "no abras chrome", "no subas el volumen"
      2. Queja de exceso → implica bajar/reducir
         → "esto suena muy fuerte", "la pantalla me está quemando"
      3. Queja de defecto → implica subir/aumentar
         → "no escucho nada", "el audio casi no se escucha"

    Retorna:
    {
        "es_negada":      bool  - negación sobre verbo de acción del asistente
        "queja_exceso":   bool  - el usuario se queja de algo demasiado alto/brillante
        "queja_defecto":  bool  - el usuario se queja de algo demasiado bajo/oscuro/inaudible
    }
    """
    es_negada     = False
    queja_exceso  = False
    queja_defecto = False

    tokens_texto = [t.text.lower() for t in doc]

    for token in doc:
        # ── Detectar negación explícita sobre verbo de acción ──────────────
        # spaCy marca el "no" con dep_="advmod" o dep_="neg" dependiendo del modelo.
        # Buscamos el token "no" y verificamos si su head es un verbo de acción.
        if token.text.lower() == "no" and token.dep_ in ("advmod", "neg", "cc"):
            head = token.head
            # spaCy a veces etiqueta imperativos/subjuntivos como ADJ (ej: "abras", "cierres")
            # por eso aceptamos tanto VERB como ADJ como head válido
            if head.pos_ in ("VERB", "ADJ") and head.lemma_ not in _VERBOS_ESTADO_PURO and head.lemma_ not in _VERBOS_PERCEPCION:
                es_negada = True

        # ── Detectar queja de exceso ────────────────────────────────────────
        # Caso 1: adjetivo/adverbio de exceso en la frase
        if token.text.lower() in _PALABRAS_EXCESO or token.lemma_.lower() in _PALABRAS_EXCESO:
            queja_exceso = True

        # Caso 2: verbo de molestia ("la pantalla me está quemando los ojos")
        if token.lemma_.lower() in _VERBOS_MOLESTIA:
            queja_exceso = True

        # ── Detectar queja de defecto ───────────────────────────────────────
        # Caso 1: adjetivo/adverbio de defecto en la frase
        if token.text.lower() in _PALABRAS_DEFECTO or token.lemma_.lower() in _PALABRAS_DEFECTO:
            # Excepción: "baja el volumen" tiene "baja" como imperativo, no como queja
            # Solo cuenta si NO es imperativo
            morph = token.morph.to_dict()
            es_imperativo_token = morph.get("Mood") == "Imp"
            if not es_imperativo_token and token.pos_ != "VERB":
                queja_defecto = True

        # Caso 2: verbo de percepción negado
        # "no escucho nada", "no se escucha", "no oigo bien"
        if token.lemma_.lower() in _VERBOS_PERCEPCION:
            # Buscar si tiene un "no" en sus dependientes o en la frase antes del verbo
            tiene_negacion = any(
                c.text.lower() == "no" and c.dep_ in ("advmod", "neg", "cc")
                for c in token.children
            )
            # También verificar "no" suelto antes del verbo en el texto
            if not tiene_negacion:
                idx = token.i
                tiene_negacion = any(
                    doc[i].text.lower() == "no"
                    for i in range(max(0, idx - 3), idx)
                )
            if tiene_negacion:
                queja_defecto = True

    # ── Caso especial: "demasiado" modifica hacia exceso siempre ───────────
    if "demasiado" in tokens_texto or "demasiada" in tokens_texto:
        queja_exceso = True
        queja_defecto = False  # demasiado siempre es exceso

    # ── Caso especial: "casi no" o "apenas" → defecto ──────────────────────
    for i, tok in enumerate(doc):
        if tok.text.lower() == "casi" and i + 1 < len(doc):
            siguiente = doc[i + 1].text.lower()
            if siguiente in ("no", "nada", "nunca"):
                queja_defecto = True
                queja_exceso  = False

    return {
        "es_negada":    es_negada,
        "queja_exceso": queja_exceso,
        "queja_defecto": queja_defecto,
    }


# =============================================================================
# HELPERS INTERNOS
# =============================================================================
def _tiene_clitico(texto: str) -> bool:
    """
    Detecta verbos con clítico adherido: 'súbelo', 'bájala', 'muévelo', 'ábrelo'.
    Mínimo 3 caracteres antes del clítico para evitar falsos positivos.
    """
    texto = texto.lower()
    for clitico in _CLITICOS:
        if texto.endswith(clitico) and len(texto) > len(clitico) + 2:
            return True
    return False