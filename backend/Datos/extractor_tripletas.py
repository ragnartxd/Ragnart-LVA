"""
extractor_tripletas.py
----------------------
Sistema robusto de extracción de tripletas (sujeto-relación-objeto) usando dependency parsing.
Maneja variaciones sintácticas en español, pasivas, reformulaciones y entrada por voz.

Características:
- Extracción basada en árboles de dependencias de spaCy
- Normalización de relaciones verbales a tipos canónicos
- Manejo de muletillas y frases incompletas (entrada por voz)
- Resolución de correferencias básica
- Soporte para múltiples construcciones sintácticas
"""

import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Cargar modelo de spaCy
""" try:
    nlp_tripletas = spacy.load("es_core_news_md")
except OSError:
    logger.warning("⚠️ Instalando modelo spaCy...")
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "es_core_news_md"])
    nlp_tripletas = spacy.load("es_core_news_md") """

from backend.utils.utils_nlp import get_nlp
nlp_tripletas = get_nlp()


@dataclass
class Tripleta:
    """Estructura de datos para tripletas extraídas"""
    sujeto: str
    relacion: str
    objeto: str
    relacion_normalizada: str
    confianza: float
    metadata: Dict
    
    def __repr__(self):
        return f"({self.sujeto} --[{self.relacion_normalizada}]--> {self.objeto})"


class ExtractorTripletas:
    """
    Extractor robusto de tripletas semánticas usando dependency parsing.
    
    Maneja:
    - Voz activa: "Juan trabaja en Google"
    - Voz pasiva: "Google emplea a Juan"
    - Construcciones copulativas: "Juan es ingeniero"
    - Posesiones: "Juan tiene un perro"
    - Muletillas: "eh... Juan, pues, trabaja en Google"
    """
    
    # Mapeo de verbos a relaciones canónicas
    VERBOS_CANONICOS = {
        # Identidad
        "llamar": "tiene_nombre",
        "llamarse": "tiene_nombre",
        "ser": "es",
        "estar": "esta",
        
        # Trabajo/Actividad
        "trabajar": "trabaja_en",
        "laborar": "trabaja_en",
        "desempeñar": "trabaja_en",
        "ocupar": "ocupa_cargo",
        "ejercer": "ejerce_como",
        
        # Estudio
        "estudiar": "estudia_en",
        "cursar": "estudia_en",
        "aprender": "aprende",
        
        # Ubicación
        "vivir": "vive_en",
        "residir": "vive_en",
        "habitar": "vive_en",
        "ubicar": "ubicado_en",
        
        # Relaciones familiares
        "tener": "tiene",
        "poseer": "tiene",
        "contar": "tiene",
        
        # Gustos
        "gustar": "le_gusta",
        "encantar": "le_encanta",
        "preferir": "prefiere",
        "amar": "ama",
        "adorar": "adora",
        "disfrutar": "disfruta",
        
        # Salud
        "padecer": "padece",
        "sufrir": "sufre",
        "diagnosticar": "diagnosticado_con",
        
        # Habilidades
        "saber": "sabe",
        "dominar": "domina",
        "manejar": "maneja",
        "hablar": "habla",
        "tocar": "toca_instrumento",
        
        # Otros
        "nacer": "nacio_en",
        "graduarse": "graduado_de",
        "casarse": "casado_con",
        "adoptar": "adopto",
    }
    
    # Muletillas comunes en español hablado
    MULETILLAS = {
        "eh", "ehh", "ehhh", "em", "emm", "emmm",
        "pues", "este", "bueno", "o sea", "digamos",
        "como que", "tipo", "aja", "ajá", "mhm",
        "entonces", "osea", "es decir", "viste", "sabes",
        "claro", "obvio", "obviamente", "básicamente"
    }
    
    # Preposiciones que indican relación
    PREP_RELACION = {
        "en": "en",
        "de": "de", 
        "con": "con",
        "para": "para",
        "por": "por",
        "desde": "desde",
        "como": "como",
        "a": "a"
    }
    
    def __init__(self):
        """Inicializa el extractor de tripletas"""
        logger.info("🔍 ExtractorTripletas inicializado")
    
    def limpiar_texto_voz(self, texto: str) -> str:
        """
        Limpia texto de entrada por voz: muletillas, repeticiones, frases incompletas.
        
        Args:
            texto: Texto potencialmente con muletillas
            
        Returns:
            Texto limpio
        """
        # Convertir a minúsculas para matching
        texto_lower = texto.lower()
        
        # Remover muletillas al inicio de frases
        for muletilla in self.MULETILLAS:
            # Patrón: muletilla al inicio o después de puntuación
            patron = rf'\b{re.escape(muletilla)}\b[,\s]*'
            texto_lower = re.sub(patron, ' ', texto_lower, flags=re.IGNORECASE)
        
        # Normalizar espacios
        texto_limpio = re.sub(r'\s+', ' ', texto_lower).strip()
        
        # Remover repeticiones (ej: "mi mi nombre")
        palabras = texto_limpio.split()
        sin_repeticiones = []
        for i, palabra in enumerate(palabras):
            if i == 0 or palabra != palabras[i-1]:
                sin_repeticiones.append(palabra)
        
        resultado = ' '.join(sin_repeticiones)
        logger.debug(f"Texto limpiado: '{texto[:50]}...' → '{resultado[:50]}...'")
        
        return resultado
    
    def extraer_tripletas(self, texto: str) -> List[Tripleta]:
        """
        Extrae todas las tripletas del texto.
        
        Args:
            texto: Texto a analizar
            
        Returns:
            Lista de tripletas extraídas
        """
        if not texto or not texto.strip():
            return []
        
        # Limpiar texto de muletillas
        texto_limpio = self.limpiar_texto_voz(texto)
        
        # Procesar con spaCy
        doc = nlp_tripletas(texto_limpio)
        
        tripletas = []
        
        # Método 1: Extracción basada en verbos principales
        tripletas.extend(self._extraer_por_verbos(doc, texto))
        
        # Método 2: Construcciones copulativas (ser/estar)
        tripletas.extend(self._extraer_copulativas(doc, texto))
        
        # Método 3: Construcciones con "tener"
        tripletas.extend(self._extraer_posesiones(doc, texto))
        
        # Método 4: Construcciones con "me llamo" / "mi nombre es"
        tripletas.extend(self._extraer_identidad(doc, texto))
        
        # Deduplicar y ordenar por confianza
        tripletas = self._deduplicar_tripletas(tripletas)
        tripletas.sort(key=lambda t: t.confianza, reverse=True)
        
        logger.debug(f"Extraídas {len(tripletas)} tripletas de '{texto[:30]}...'")
        
        return tripletas

    def extraer(self, texto: str) -> List[Tripleta]:
        """FIX 2: Alias de extraer_tripletas() para consistencia de interfaz."""
        return self.extraer_tripletas(texto)
    
    def _extraer_por_verbos(self, doc, texto_original: str) -> List[Tripleta]:
        """Extrae tripletas basadas en verbos principales con sus sujetos y objetos"""
        tripletas = []
        
        for token in doc:
            # Buscar verbos principales (ROOT o verbos con sujeto)
            if token.pos_ == "VERB" and (token.dep_ == "ROOT" or any(c.dep_ == "nsubj" for c in token.children)):
                
                # Extraer sujeto
                sujeto = self._extraer_sujeto(token, doc)
                if not sujeto:
                    continue
                
                # Extraer objeto
                objeto = self._extraer_objeto(token, doc)
                if not objeto:
                    continue
                
                # Normalizar relación
                relacion_original = token.lemma_
                relacion_normalizada = self.VERBOS_CANONICOS.get(
                    relacion_original, 
                    relacion_original
                )
                
                # Calcular confianza basada en completitud
                confianza = self._calcular_confianza(sujeto, objeto, token)
                
                tripletas.append(Tripleta(
                    sujeto=sujeto,
                    relacion=relacion_original,
                    objeto=objeto,
                    relacion_normalizada=relacion_normalizada,
                    confianza=confianza,
                    metadata={
                        "tipo_extraccion": "verbo_principal",
                        "verbo_pos": token.i,
                        "texto_original": texto_original
                    }
                ))
        
        return tripletas
    
    def _extraer_copulativas(self, doc, texto_original: str) -> List[Tripleta]:
        """Extrae construcciones copulativas: X es/está Y"""
        tripletas = []
        
        for token in doc:
            if token.lemma_ in ["ser", "estar"]:
                # Buscar sujeto
                sujeto = None
                for child in token.children:
                    if child.dep_ == "nsubj":
                        sujeto = self._expandir_frase_nominal(child)
                        break
                
                if not sujeto:
                    continue
                
                # Buscar atributo (predicado nominal)
                objeto = None
                for child in token.children:
                    if child.dep_ in ["attr", "acomp"]:
                        objeto = self._expandir_frase_nominal(child)
                        break
                
                if not objeto:
                    continue
                
                relacion_norm = "es" if token.lemma_ == "ser" else "esta"
                
                tripletas.append(Tripleta(
                    sujeto=sujeto,
                    relacion=token.lemma_,
                    objeto=objeto,
                    relacion_normalizada=relacion_norm,
                    confianza=0.85,
                    metadata={
                        "tipo_extraccion": "copulativa",
                        "texto_original": texto_original
                    }
                ))
        
        return tripletas
    
    def _extraer_posesiones(self, doc, texto_original: str) -> List[Tripleta]:
        """Extrae construcciones con 'tener': X tiene Y"""
        tripletas = []
        
        for token in doc:
            if token.lemma_ == "tener":
                sujeto = self._extraer_sujeto(token, doc)
                if not sujeto:
                    # Inferir "yo" si no hay sujeto explícito
                    sujeto = "usuario"
                
                # Buscar objeto directo
                objeto = None
                for child in token.children:
                    if child.dep_ == "obj":
                        objeto = self._expandir_frase_nominal(child)
                        break
                
                if objeto:
                    tripletas.append(Tripleta(
                        sujeto=sujeto,
                        relacion="tener",
                        objeto=objeto,
                        relacion_normalizada="tiene",
                        confianza=0.8,
                        metadata={
                            "tipo_extraccion": "posesion",
                            "texto_original": texto_original
                        }
                    ))
        
        return tripletas
    
    def _extraer_identidad(self, doc, texto_original: str) -> List[Tripleta]:
        """Extrae construcciones de identidad: me llamo X, mi nombre es Y"""
        tripletas = []
        texto_lower = texto_original.lower()
        
        # Patrón 1: "me llamo X"
        if "me llamo" in texto_lower or "llamarse" in texto_lower:
            for token in doc:
                if token.lemma_ in ["llamar", "llamarse"]:
                    # Buscar nombre (objeto directo o atributo)
                    nombre = None
                    for child in token.children:
                        if child.dep_ in ["obj", "attr"] and child.pos_ in ["PROPN", "NOUN"]:
                            nombre = self._expandir_frase_nominal(child)
                            break
                    
                    if nombre:
                        tripletas.append(Tripleta(
                            sujeto="usuario",
                            relacion="llamarse",
                            objeto=nombre,
                            relacion_normalizada="tiene_nombre",
                            confianza=0.95,
                            metadata={
                                "tipo_extraccion": "identidad_nombre",
                                "texto_original": texto_original
                            }
                        ))
        
        # Patrón 2: "mi nombre es X"
        if "mi nombre" in texto_lower or "nombre es" in texto_lower:
            for token in doc:
                if token.text.lower() == "nombre":
                    # Buscar verbo "ser"
                    verbo_ser = token.head
                    if verbo_ser.lemma_ == "ser":
                        # Buscar atributo
                        for child in verbo_ser.children:
                            if child.dep_ in ["attr"] and child.pos_ in ["PROPN", "NOUN"]:
                                nombre = self._expandir_frase_nominal(child)
                                tripletas.append(Tripleta(
                                    sujeto="usuario",
                                    relacion="ser",
                                    objeto=nombre,
                                    relacion_normalizada="tiene_nombre",
                                    confianza=0.95,
                                    metadata={
                                        "tipo_extraccion": "identidad_nombre",
                                        "texto_original": texto_original
                                    }
                                ))
                                break
        
        return tripletas
    
    def _extraer_sujeto(self, verbo_token, doc) -> Optional[str]:
        """Extrae el sujeto de un verbo"""
        for child in verbo_token.children:
            if child.dep_ == "nsubj":
                sujeto = self._expandir_frase_nominal(child)
                # FIX 4: si el sujeto es un pronombre de primera persona, normalizar a "usuario"
                if sujeto.lower() in {"yo", "me", "mi", "mí"}:
                    return "usuario"
                return sujeto
        
        # FIX 4: ampliar detección de primera persona implícita
        # spaCy marca persona gramatical en morph; cubrir también segunda capa:
        # verbos con clítico "me" entre sus hijos (ej: "me llamo", "me gusta")
        for child in verbo_token.children:
            if child.dep_ in {"expl", "iobj"} and child.text.lower() == "me":
                return "usuario"
        
        # Persona 1 explícita en morfología
        person = verbo_token.morph.get("Person")
        if person and person[0] == "1":
            return "usuario"
        
        # Inferencia por forma verbal de primera persona singular
        # (cubre casos donde el modelo no asigna morph correctamente)
        primera_persona_sing = {
            "soy", "estoy", "tengo", "trabajo", "vivo", "estudio",
            "hablo", "sé", "puedo", "quiero", "me llamo", "nací",
            "sufro", "padezco", "tomo", "practico", "colecciono"
        }
        if verbo_token.text.lower() in primera_persona_sing:
            return "usuario"
        
        return None
    
    def _extraer_objeto(self, verbo_token, doc) -> Optional[str]:
        """Extrae el objeto de un verbo"""
        # Buscar objeto directo
        for child in verbo_token.children:
            if child.dep_ in ["obj", "obl"]:
                return self._expandir_frase_nominal(child)
        
        # Buscar complemento preposicional (para "trabajar en", "vivir en", etc.)
        for child in verbo_token.children:
            if child.dep_ == "obl" and child.pos_ == "ADP":
                for subchild in child.children:
                    if subchild.dep_ == "pobj":
                        return self._expandir_frase_nominal(subchild)
        
        return None
    
    def _expandir_frase_nominal(self, token) -> str:
        """
        Expande un token a su frase nominal completa.
        Incluye modificadores, determinantes, etc.
        """
        # Recolectar subtokens
        subtree = list(token.subtree)
        
        # Ordenar por posición en el texto
        subtree.sort(key=lambda t: t.i)
        
        # Construir frase
        frase = " ".join([t.text for t in subtree])
        
        # Limpiar
        frase = re.sub(r'\s+', ' ', frase).strip()
        
        return frase
    
    def _calcular_confianza(self, sujeto: str, objeto: str, verbo_token) -> float:
        """
        Calcula confianza de la tripleta basada en completitud y contexto.
        
        Factores:
        - Longitud del sujeto y objeto (más palabras = más específico = mayor confianza)
        - Presencia de entidades nombradas
        - Tipo de verbo
        """
        confianza = 0.5  # Base
        
        # Factor 1: Completitud
        palabras_sujeto = len(sujeto.split())
        palabras_objeto = len(objeto.split())
        
        if palabras_sujeto >= 2:
            confianza += 0.1
        if palabras_objeto >= 2:
            confianza += 0.1
        
        # Factor 2: Entidades nombradas
        if verbo_token.doc[verbo_token.i].ent_type_:
            confianza += 0.1
        
        # Factor 3: Verbos de alta confianza
        if verbo_token.lemma_ in ["llamarse", "ser", "tener", "trabajar", "vivir"]:
            confianza += 0.15
        
        return min(confianza, 1.0)
    
    def _deduplicar_tripletas(self, tripletas: List[Tripleta]) -> List[Tripleta]:
        """Elimina tripletas duplicadas o muy similares"""
        if not tripletas:
            return []
        
        unicas = []
        vistas = set()
        
        for t in tripletas:
            # Clave de deduplicación: sujeto + relación normalizada + objeto (normalizado)
            clave = (
                t.sujeto.lower().strip(),
                t.relacion_normalizada,
                t.objeto.lower().strip()
            )
            
            if clave not in vistas:
                unicas.append(t)
                vistas.add(clave)
        
        return unicas
    
    def normalizar_relacion(self, verbo: str) -> str:
        """
        Normaliza un verbo a su forma canónica.
        
        Args:
            verbo: Verbo en forma original
            
        Returns:
            Relación normalizada
        """
        return self.VERBOS_CANONICOS.get(verbo.lower(), verbo.lower())


if __name__ == "__main__":
    # Pruebas
    extractor = ExtractorTripletas()
    
    textos_prueba = [
        "Me llamo Juan García y tengo 30 años",
        "Trabajo como ingeniero de software en Google",
        "Vivo en Madrid con mi esposa",
        "Mi nombre es Carlos y soy médico",
        "Tengo un perro llamado Max",
        "Eh... pues, trabajo en, este... Microsoft",
        "Estudio medicina en la Universidad Nacional",
        "Me gusta el café por las mañanas",
        "Padezco diabetes tipo 2",
        "Soy alérgico al maní"
    ]
    
    print("\n🔍 Pruebas del ExtractorTripletas\n")
    print("=" * 80)
    
    for texto in textos_prueba:
        print(f"\n📝 Texto: '{texto}'")
        print("-" * 80)
        
        tripletas = extractor.extraer_tripletas(texto)
        
        if tripletas:
            for i, t in enumerate(tripletas, 1):
                print(f"\n  Tripleta {i}:")
                print(f"    {t}")
                print(f"    Confianza: {t.confianza:.2f}")
                print(f"    Tipo: {t.metadata.get('tipo_extraccion')}")
        else:
            print("  ❌ No se extrajeron tripletas")
    
    print("\n" + "=" * 80)
    print("✅ Pruebas completadas\n")