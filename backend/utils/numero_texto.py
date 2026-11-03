"""
numero_texto.py
---------------
Conversión bidireccional número ↔ texto en español.

Funciones públicas (4):
    texto_a_numero(texto)  → int | float | None
    numero_a_texto(n)      → str
    reemplazar_numeros_en_texto(texto) → str   (palabras numéricas → dígitos)
    digitos_a_palabras(texto)          → str   (dígitos → palabras; soporta HH:MM)

Rango soportado:
    texto_a_numero : hasta 999 999 999 999 (novecientos noventa y nueve mil millones...)
    numero_a_texto : hasta ±999 999 999 999, con decimales
"""

import re


# =============================================================================
# TABLAS BASE
# =============================================================================

_UNIDADES = {
    "cero": 0, "un": 1, "uno": 1, "una": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
}

_DECENAS_ESPECIALES = {
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
    "quince": 15, "dieciséis": 16, "dieciseis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20,
}

# veintiuno..veintinueve (forma compuesta obligatoria en español)
_VEINTI = {f"veinti{u}": 20 + v for u, v in _UNIDADES.items() if 1 <= v <= 9}
_VEINTI["veintiún"] = 21
_VEINTI["veintiuna"] = 21

_DECENAS = {
    "treinta": 30, "cuarenta": 40, "cincuenta": 50,
    "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90,
}

_CENTENAS = {
    "cien": 100, "ciento": 100,
    "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300,
    "cuatrocientos": 400, "cuatrocientas": 400,
    "quinientos": 500, "quinientas": 500,
    "seiscientos": 600, "seiscientas": 600,
    "setecientos": 700, "setecientas": 700,
    "ochocientos": 800, "ochocientas": 800,
    "novecientos": 900, "novecientas": 900,
}

# Escala: palabra → valor
_ESCALAS = {
    "mil":      1_000,
    "millon":   1_000_000,
    "millón":   1_000_000,
    "millones": 1_000_000,
    "billon":   1_000_000_000,
    "billón":   1_000_000_000,
    "billones": 1_000_000_000,
}

# Unión de todo el vocabulario numérico (para regex y lookup)
_TODO_VOCAB: dict[str, int] = {
    **_UNIDADES,
    **_DECENAS_ESPECIALES,
    **_VEINTI,
    **_DECENAS,
    **_CENTENAS,
    **{k: v for k, v in _ESCALAS.items()},
}

# Palabras que solos son demasiado ambiguas para reemplazar en texto libre
# ("un" puede ser artículo, "una" también, "cien" puede ir dentro de "por ciento")
_EXCLUIR_EN_TEXTO_LIBRE = {"un", "una", "cien", "ciento"}

# Regex que captura una secuencia numérica en español dentro de un texto
_PALABRAS_NUM = sorted(
    [p for p in _TODO_VOCAB.keys() if p not in _EXCLUIR_EN_TEXTO_LIBRE],
    key=len, reverse=True
)
_PATRON_NUM = re.compile(
    r'\b(?:' + '|'.join(re.escape(p) for p in _PALABRAS_NUM) + r')'
    r'(?:\s+(?:y\s+)?(?:' + '|'.join(re.escape(p) for p in _PALABRAS_NUM) + r'))*\b',
    flags=re.IGNORECASE,
)


# =============================================================================
# TEXTO → NÚMERO
# =============================================================================

def _normalizar(texto: str) -> str:
    """Quita tildes, pasa a minúsculas y colapsa espacios."""
    tabla = str.maketrans("áéíóúüÁÉÍÓÚÜñÑ", "aeiouuAEIOUUnN")
    return " ".join(texto.lower().translate(tabla).split())


def texto_a_numero(texto: str) -> "int | float | None":
    """
    Convierte una cadena de texto en español al número que representa.

    Acepta:
        - enteros:   "ciento veinte y tres"  → 123
        - negativos: "menos cuarenta"        → -40
        - decimales: "tres punto cinco"      → 3.5
                     "dos coma cuatro"       → 2.4
        - dígitos mezclados: "2 millones"    → 2000000

    Retorna None si no reconoce nada numérico en el texto.

    Ejemplos:
        texto_a_numero("doce")                       → 12
        texto_a_numero("un millón doscientos mil")   → 1_200_000
        texto_a_numero("menos tres punto catorce")   → -3.14  (aprox)
        texto_a_numero("42")                         → 42
    """
    texto = texto.strip()
    if not texto:
        return None

    # ── Negativo ─────────────────────────────────────────────────────────────
    negativo = False
    if re.match(r'^(menos|-)\s*', texto, re.IGNORECASE):
        negativo = True
        texto = re.sub(r'^(menos|-)\s*', '', texto, flags=re.IGNORECASE).strip()

    # ── Separar parte decimal si existe ──────────────────────────────────────
    parte_decimal_str = None
    for sep in (r'\bpunto\b', r'\bcoma\b', r'\.', r','):
        m = re.split(sep, texto, maxsplit=1, flags=re.IGNORECASE)
        if len(m) == 2:
            texto = m[0].strip()
            parte_decimal_str = m[1].strip()
            break

    # ── Convertir parte entera ────────────────────────────────────────────────
    parte_entera = _parsear_entero(texto)
    if parte_entera is None:
        return None

    # ── Convertir parte decimal ───────────────────────────────────────────────
    resultado: float | int = parte_entera
    if parte_decimal_str is not None:
        dec = _parsear_entero(parte_decimal_str)
        if dec is None:
            # intento como dígitos directos ("3.5")
            try:
                dec_float = float("0." + parte_decimal_str.replace(" ", ""))
            except ValueError:
                dec_float = 0.0
        else:
            # "cinco" → 0.5, "cincuenta" → 0.50, "tres" → 0.3
            digitos = len(str(dec))
            dec_float = dec / (10 ** digitos)
        resultado = parte_entera + dec_float

    if negativo:
        resultado = -resultado

    # Devolver int si no hay decimales reales
    if isinstance(resultado, float) and resultado == int(resultado):
        return int(resultado)
    return resultado


def _parsear_entero(texto: str) -> "int | None":
    """
    Núcleo de parseo para la parte entera.
    Maneja: dígitos, palabras en español, y mezclas ("2 millones trescientos mil").
    """
    texto = texto.strip()
    if not texto:
        return None

    # Número ya en dígitos
    if re.fullmatch(r'\d[\d\s]*', texto):
        try:
            return int(texto.replace(" ", ""))
        except ValueError:
            return None

    norm = _normalizar(texto)
    tokens = norm.split()

    total   = 0   # acumulador de escala alta (millones, billones)
    current = 0   # acumulador de escala baja (< 1000)
    hubo_algo = False

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        # Ignorar conectores
        if tok in ("y", "e"):
            i += 1
            continue

        # Dígito suelto (p.ej. "2" en "2 millones")
        if tok.isdigit():
            current += int(tok)
            hubo_algo = True
            i += 1
            continue

        # Escala (mil / millón / billón)
        if tok in _ESCALAS:
            factor = _ESCALAS[tok]
            if factor == 1_000:
                # "mil" sin prefijo → 1000; con prefijo current ya tiene el multiplicador
                multiplicador = current if current > 0 else 1
                current = multiplicador * 1_000
            else:
                # millones / billones: current es el multiplicador; volcamos a total
                multiplicador = current if current > 0 else 1
                total += multiplicador * factor
                current = 0
            hubo_algo = True
            i += 1
            continue

        # Valor del token en las tablas
        valor = (
            _UNIDADES.get(tok) or
            _DECENAS_ESPECIALES.get(tok) or
            _VEINTI.get(tok) or
            _DECENAS.get(tok) or
            _CENTENAS.get(tok)
        )

        # Fallback: con tilde vs sin tilde ya normalizado arriba
        if valor is None and tok in _TODO_VOCAB:
            valor = _TODO_VOCAB[tok]

        if valor is not None:
            current += valor
            hubo_algo = True
        # token no reconocido → lo ignoramos (podría ser ruido)

        i += 1

    if not hubo_algo:
        return None

    return total + current


# =============================================================================
# NÚMERO → TEXTO
# =============================================================================

def numero_a_texto(n: "int | float") -> str:
    """
    Convierte un número al texto en español.

    Soporta:
        - Enteros positivos y negativos hasta ±999 999 999 999
        - Floats con hasta 10 decimales significativos
        - 0 → "cero"

    Ejemplos:
        numero_a_texto(0)           → "cero"
        numero_a_texto(21)          → "veintiuno"
        numero_a_texto(100)         → "cien"
        numero_a_texto(101)         → "ciento uno"
        numero_a_texto(1000)        → "mil"
        numero_a_texto(1_500_000)   → "un millón quinientos mil"
        numero_a_texto(-7)          → "menos siete"
        numero_a_texto(3.14)        → "tres punto catorce"
        numero_a_texto(0.5)         → "cero punto cinco"
    """
    if not isinstance(n, (int, float)):
        raise TypeError(f"Se esperaba int o float, se recibió {type(n).__name__}")

    # Negativo
    if n < 0:
        return "menos " + numero_a_texto(-n)

    # Separar parte entera y decimal
    parte_entera = int(n)
    parte_decimal = round(n - parte_entera, 10)

    texto_entero = _entero_a_texto(parte_entera)

    if parte_decimal == 0:
        return texto_entero

    # Convertir decimales: "0.5" → "cinco", "0.14" → "catorce", "0.123" → "ciento veintitrés"
    # Se elimina el "0." y se parsea como entero
    dec_str = f"{parte_decimal:.10f}".split(".")[1].rstrip("0")
    dec_int = int(dec_str)
    texto_decimal = _entero_a_texto(dec_int)
    return f"{texto_entero} punto {texto_decimal}"


def _entero_a_texto(n: int) -> str:
    """Convierte un entero no negativo a texto en español."""
    if n < 0:
        raise ValueError("Usar numero_a_texto() para negativos")

    if n == 0:
        return "cero"

    # ── Billones ─────────────────────────────────────────────────────────────
    if n >= 1_000_000_000:
        billones = n // 1_000_000_000
        resto    = n  % 1_000_000_000
        prefijo  = _entero_a_texto(billones)
        escala   = "billón" if billones == 1 else "billones"
        partes   = [f"{prefijo} {escala}"]
        if resto:
            partes.append(_entero_a_texto(resto))
        return " ".join(partes)

    # ── Millones ──────────────────────────────────────────────────────────────
    if n >= 1_000_000:
        millones = n // 1_000_000
        resto    = n  % 1_000_000
        prefijo  = "un" if millones == 1 else _entero_a_texto(millones)
        escala   = "millón" if millones == 1 else "millones"
        partes   = [f"{prefijo} {escala}"]
        if resto:
            partes.append(_entero_a_texto(resto))
        return " ".join(partes)

    # ── Miles ─────────────────────────────────────────────────────────────────
    if n >= 1_000:
        miles = n // 1_000
        resto = n  % 1_000
        if miles == 1:
            prefijo = "mil"
        else:
            prefijo = _entero_a_texto(miles) + " mil"
        partes = [prefijo]
        if resto:
            partes.append(_entero_a_texto(resto))
        return " ".join(partes)

    # ── Centenas ──────────────────────────────────────────────────────────────
    if n >= 100:
        centena = (n // 100) * 100
        resto   = n % 100
        # Tabla inversa centenas
        _INV_CENTENAS = {
            100: "cien",    # "cien" solo cuando es exactamente 100
            200: "doscientos", 300: "trescientos", 400: "cuatrocientos",
            500: "quinientos", 600: "seiscientos",  700: "setecientos",
            800: "ochocientos", 900: "novecientos",
        }
        texto_centena = _INV_CENTENAS[centena]
        if centena == 100 and resto > 0:
            texto_centena = "ciento"   # 101-199 → "ciento X"
        if resto:
            return f"{texto_centena} {_entero_a_texto(resto)}"
        return texto_centena

    # ── Decenas ───────────────────────────────────────────────────────────────
    if n >= 30:
        decena = (n // 10) * 10
        unidad = n % 10
        _INV_DECENAS = {
            30: "treinta", 40: "cuarenta", 50: "cincuenta",
            60: "sesenta", 70: "setenta",  80: "ochenta", 90: "noventa",
        }
        if unidad:
            return f"{_INV_DECENAS[decena]} y {_uno_a_texto(unidad)}"
        return _INV_DECENAS[decena]

    # ── 21-29 ──────────────────────────────────────────────────────────────────
    if n >= 21:
        _VEINTI_INV = {
            21: "veintiuno", 22: "veintidós", 23: "veintitrés",
            24: "veinticuatro", 25: "veinticinco", 26: "veintiséis",
            27: "veintisiete", 28: "veintiocho", 29: "veintinueve",
        }
        return _VEINTI_INV[n]

    # ── 10-20 ──────────────────────────────────────────────────────────────────
    if n >= 10:
        _TEENS_INV = {
            10: "diez", 11: "once", 12: "doce", 13: "trece", 14: "catorce",
            15: "quince", 16: "dieciséis", 17: "diecisiete",
            18: "dieciocho", 19: "diecinueve", 20: "veinte",
        }
        return _TEENS_INV[n]

    # ── 1-9 ────────────────────────────────────────────────────────────────────
    return _uno_a_texto(n)


def _uno_a_texto(n: int) -> str:
    _UNIDADES_INV = {
        0: "cero", 1: "uno", 2: "dos", 3: "tres", 4: "cuatro",
        5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve",
    }
    return _UNIDADES_INV[n]


# =============================================================================
# UTILIDAD: reemplazar números escritos dentro de un texto libre
# =============================================================================

def reemplazar_numeros_en_texto(texto: str) -> str:
    """
    Reemplaza expresiones numéricas en español dentro de un texto por su dígito.

    Útil para normalizar frases del usuario antes de clasificar intenciones.

    Ejemplos:
        "pon un temporizador de diez minutos"   → "pon un temporizador de 10 minutos"
        "sube el volumen veinticinco por ciento" → "sube el volumen 25 por ciento"
        "quiero tres alarmas"                    → "quiero 3 alarmas"
    """
    def _reemplazar(match: re.Match) -> str:
        fragmento = match.group(0)
        resultado = texto_a_numero(fragmento)
        if resultado is not None:
            return str(resultado)
        return fragmento  # no se reconoció → dejar igual

    return _PATRON_NUM.sub(_reemplazar, texto)


# =============================================================================
# UTILIDAD: reemplazar dígitos dentro de un texto libre por palabras
# =============================================================================

# Regex para capturar horas (13:45), decimales (3.14) y enteros (42)
_PATRON_DIGITOS = re.compile(
    r'\b(\d{1,2}):(\d{2})\b'   # hora HH:MM  → grupo 1 y 2
    r'|\b(\d+)[\.,](\d+)\b'    # decimal      → grupo 3 y 4
    r'|\b(\d+)\b',             # entero        → grupo 5
    flags=re.IGNORECASE,
)


def digitos_a_palabras(texto: str) -> str:
    """
    Reemplaza dígitos dentro de un texto por su representación en palabras.

    Reconoce:
        - Horas  HH:MM   → \"trece cuarenta y cinco\"
        - Decimales N.M  → \"tres punto catorce\"
        - Enteros N      → \"cuarenta y dos\"

    Ejemplos:
        digitos_a_palabras(\"son las 13:45\")      → \"son las trece cuarenta y cinco\"
        digitos_a_palabras(\"el valor es 3.14\")   → \"el valor es tres punto catorce\"
        digitos_a_palabras(\"tengo 42 años\")      → \"tengo cuarenta y dos años\"
        digitos_a_palabras(\"a las 8:00 AM\")      → \"a las ocho cero cero AM\"
        digitos_a_palabras(\"son las 3\")          → \"son las tres\"
    """
    def _reemplazar(m: re.Match) -> str:
        if m.group(1) is not None:
            # Hora HH:MM
            h = int(m.group(1))
            mins = int(m.group(2))
            texto_h = numero_a_texto(h)
            # Minutos: 00 → "cero cero", 05 → "cero cinco", 30 → "treinta"
            if mins == 0:
                texto_m = "cero cero"
            elif mins < 10:
                texto_m = "cero " + numero_a_texto(mins)
            else:
                texto_m = numero_a_texto(mins)
            return f"{texto_h} {texto_m}"
        elif m.group(3) is not None:
            # Decimal
            parte_entera = int(m.group(3))
            parte_dec = int(m.group(4))
            return f"{numero_a_texto(parte_entera)} punto {numero_a_texto(parte_dec)}"
        else:
            # Entero simple
            return numero_a_texto(int(m.group(5)))

    return _PATRON_DIGITOS.sub(_reemplazar, texto)


# =============================================================================
# DEMO / USO DESDE LÍNEA DE COMANDOS
# =============================================================================

if __name__ == "__main__":
    print(digitos_a_palabras("son las 13:45"))