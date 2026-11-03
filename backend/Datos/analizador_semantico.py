"""
analizador_semantico_v2.py
---------------------------
Versión mejorada del analizador semántico con:
- Extracción robusta de tripletas (sujeto-relación-objeto)
- Detección mejorada de entidades con spaCy
- Integración con ExtractorTripletas
- Manejo de variaciones sintácticas y entrada por voz

MEJORAS sobre v1:
✅ Extracción de tripletas estructuradas
✅ Normalización de relaciones verbales
✅ Detección de entidades mejorada
✅ Robustez ante entrada por voz (muletillas, frases incompletas)
✅ Metadata enriquecida con información estructurada

MANTIENE:
- Todo el código funcional de v1
- Patrones lingüísticos existentes
- Lógica de importancia y retención
"""

import re
import logging
import dateparser
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Importar el nuevo extractor de tripletas
from backend.Datos.extractor_tripletas import ExtractorTripletas

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar modelo de spaCy
""" try:
    nlp_memoria = spacy.load("es_core_news_md")
    logger.info("✅ Modelo spaCy cargado para análisis semántico v2")
except OSError:
    logger.warning("⚠️ Modelo spaCy no encontrado. Instalando...")
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "es_core_news_md"])
    nlp_memoria = spacy.load("es_core_news_md") """

from backend.utils.utils_nlp import get_nlp
nlp_memoria = get_nlp()

class AnalizadorSemanticoV2:
    """
    Análisis semántico profundo de texto en español con extracción de tripletas.
    
    Versión mejorada que añade:
    - Extracción de tripletas estructuradas
    - Detección mejorada de entidades
    - Normalización de relaciones
    - Mayor robustez ante variaciones sintácticas
    """
    
    # MANTENER: Patrones lingüísticos originales
    PATRONES_LINGUISTICOS = {
        "identidad_nombre": {
            "descripcion": "Patrón: me llamo X, mi nombre es X, soy X",
            "verbos_clave": ["llamar", "llamarse"],
            "construcciones": ["mi nombre es", "me llamo"],
            "etiqueta": "identidad_personal",
            "importancia": 0.95,
            "retencion": "permanente"
        },
        "identidad_edad": {
            "patron_regex": r"tengo\s+(\d+)\s+años",
            "etiqueta": "identidad_personal",
            "importancia": 0.95,
            "retencion": "permanente"
        },
        "relacion_temporal": {
            "patron_regex": r"llevo\s+\d+\s+(años?|meses?)\s+con",
            "etiqueta": "familia",
            "importancia": 0.85,
            "retencion": "largo_plazo"
        },
        "estado_salud": {
            "verbos_indicadores": ["padecer", "sufrir"],
            "construcciones": [
                "soy alérgico",
                "soy alérgica",
                "tengo alergia",
                "tengo enfermedad",
            ],
            "etiqueta": "salud",
            "importancia": 0.95,
            "retencion": "permanente"
        },
        "preferencias": {
            "verbos_clave": ["gustar", "encantar", "preferir", "amar", "adorar", "fascinar"],
            "etiqueta": "preferencias",
            "importancia": 0.6,
            "retencion": "medio_plazo"
        },
        "evento_temporal": {
            "marcadores_temporales": [
                "mañana", "hoy", "pasado mañana", "lunes", "martes", 
                "miércoles", "jueves", "viernes", "sábado", "domingo", 
                "próxima", "próximo", "la semana que viene", "el mes que viene"
            ],
            "verbos_compromiso": ["tener", "deber", "ir"],
            "etiqueta": "evento_futuro",
            "importancia": 0.85,
            "retencion": "temporal"
        },
        "actividad_profesional": {
            "verbos_clave": ["trabajar", "estudiar"],
            "construcciones": ["trabajo como", "trabajo en", "soy"],
            "etiqueta": "trabajo_estudio",
            "importancia": 0.85,
            "retencion": "largo_plazo"
        },
        "ubicacion_residencia": {
            "verbos_clave": ["vivir", "residir"],
            "construcciones": ["soy de", "vivo en", "resido en"],
            "entidades_spacy": ["GPE", "LOC"],
            "etiqueta": "ubicacion",
            "importancia": 0.8,
            "retencion": "largo_plazo"
        },
        "relacion_familiar": {
            "palabras_familia": [
                "mamá", "papá", "hermano", "hermana", "hijo", "hija",
                "padre", "madre", "abuelo", "abuela", "tío", "tía",
                "novia", "novio", "pareja", "esposa", "esposo",
                "primo", "prima", "sobrino", "sobrina"
            ],
            "etiqueta": "familia",
            "importancia": 0.9,
            "retencion": "permanente"
        }
    }
    
    # MANTENER: Frases descartables
    DESCARTE_EXACTO = {
        "hola", "hi", "hey", "buenas", "buenos días", "buenas tardes", 
        "buenas noches", "qué tal", "que tal", "cómo estás", "como estas",
        "cómo vas", "qué pasa", "gracias", "ok", "vale", "entiendo",
        "claro", "sí", "si", "no", "ah", "oh", "adiós", "adios",
        "chao", "hasta luego", "nos vemos", "bye", "bien", "mal",
        "regular", "más o menos", "ayuda", "ayúdame"
    }
    
    # MANTENER: Estados efímeros
    ESTADOS_EFIMEROS = {
        "hambre", "sed", "sueño", "cansado", "cansada", 
        "aburrido", "aburrida", "estresado", "estresada"
    }
    
    def __init__(self):
        """Inicializa el analizador semántico v2"""
        # NUEVO: Inicializar extractor de tripletas
        self.extractor_tripletas = ExtractorTripletas()
        logger.info("🧠 AnalizadorSemanticoV2 inicializado con extracción de tripletas")
    
    def analizar(self, texto: str) -> Dict:
        """
        Análisis semántico completo del texto con extracción de tripletas.
        
        MEJORA: Ahora incluye tripletas estructuradas y entidades en el resultado.
        
        Args:
            texto: Texto a analizar
        
        Returns:
            Dict con: {
                "importancia": float,
                "tipo_memoria": str,
                "metadata": dict,
                "hechos_extraidos": list,
                "tripletas": list,  # NUEVO
                "entidades": list   # NUEVO
            }
        """
        if not texto or not texto.strip():
            return {
                "texto": texto,
                "etiqueta": "conversacion_casual",
                "importancia": 0.0,
                "tipo_memoria": "efimero",
                "retencion": "efimero",
                "metadata": {},
                "hechos_extraidos": [],
                "tripletas": [],
                "entidades": []
            }
        
        # MANTENER: Verificar si es descartable
        if self.es_descartable(texto):
            return {
                "texto": texto,
                "etiqueta": "conversacion_casual",
                "importancia": 0.1,
                "tipo_memoria": "efimero",
                "retencion": "efimero",
                "metadata": {"descartado": True},
                "hechos_extraidos": [],
                "tripletas": [],
                "entidades": []
            }
        
        # MANTENER: Extraer hechos con método original
        hechos = self.extraer_hechos(texto)
        
        # NUEVO: Extraer tripletas estructuradas
        tripletas = self.extractor_tripletas.extraer_tripletas(texto)
        
        # NUEVO: Extraer entidades con spaCy
        entidades = self._extraer_entidades_spacy(texto)
        
        # MANTENER: Calcular importancia máxima de los hechos
        importancia_hechos = max(
            (h.get("importancia", 0.5) for h in hechos),
            default=0.3
        )
        
        # NUEVO: Ajustar importancia si hay tripletas de alta confianza
        if tripletas:
            max_confianza_tripleta = max(t.confianza for t in tripletas)
            importancia_tripletas = max_confianza_tripleta * 0.9
            importancia = max(importancia_hechos, importancia_tripletas)
        else:
            importancia = importancia_hechos
        
        # MANTENER: Determinar tipo de memoria
        tipos_retencion = [h.get("retencion", "efimero") for h in hechos]
        tipo_memoria = self._determinar_tipo_memoria(tipos_retencion)
        
        # MEJORAR: Metadata enriquecida
        metadata = {
            "num_hechos": len(hechos),
            "num_tripletas": len(tripletas),  # NUEVO
            "num_entidades": len(entidades),  # NUEVO
            "tiene_fecha": any("fecha" in h.get("metadata", {}) for h in hechos)
        }
        
        # MANTENER: Extraer fecha si es evento temporal
        if any(h.get("etiqueta") == "evento_futuro" for h in hechos):
            fecha_extraida = self.extraer_fecha(texto)
            if fecha_extraida:
                metadata["fecha"] = fecha_extraida
        
        # NUEVO: Serializar tripletas para JSON
        tripletas_dict = [
            {
                "sujeto": t.sujeto,
                "relacion": t.relacion,
                "relacion_normalizada": t.relacion_normalizada,
                "objeto": t.objeto,
                "confianza": t.confianza,
                "tipo_extraccion": t.metadata.get("tipo_extraccion", "unknown")
            }
            for t in tripletas
        ]
        hecho_principal = max(
            hechos,
            key=lambda hecho: hecho.get("importancia", 0.0),
            default={},
        )

        return {
            "texto": texto,
            "etiqueta": hecho_principal.get("etiqueta", "conversacion_casual"),
            "importancia": importancia,
            "tipo_memoria": tipo_memoria,
            "retencion": tipo_memoria,
            "metadata": metadata,
            "hechos_extraidos": hechos,
            "tripletas": tripletas_dict,  # NUEVO
            "entidades": entidades  # NUEVO
        }
    
    def _extraer_entidades_spacy(self, texto: str) -> List[Tuple[str, str]]:
        """
        NUEVO: Extrae entidades nombradas usando spaCy.
        
        Args:
            texto: Texto a analizar
            
        Returns:
            Lista de tuplas (texto_entidad, tipo_entidad)
        """
        doc = nlp_memoria(texto)
        
        entidades = []
        for ent in doc.ents:
            entidades.append((ent.text, ent.label_))
        
        # Deduplicar
        entidades = list(set(entidades))
        
        logger.debug(f"Entidades extraídas: {entidades}")
        
        return entidades
    
    # ========================================================================
    # MANTENER TODOS LOS MÉTODOS ORIGINALES SIN CAMBIOS
    # ========================================================================
    
    def _determinar_tipo_memoria(self, tipos: List[str]) -> str:
        """MANTENER: Determina el tipo de memoria más restrictivo"""
        prioridad = {
            "permanente": 5,
            "largo_plazo": 4,
            "medio_plazo": 3,
            "temporal": 2,
            "efimero": 1
        }
        
        if not tipos:
            return "efimero"
        
        tipo_max = max(tipos, key=lambda t: prioridad.get(t, 0))
        return tipo_max
    
    def es_descartable(self, texto: str) -> bool:
        """MANTENER: Verifica si el texto es descartable"""
        texto_lower = texto.lower().strip()
        
        # Descartar frases exactas
        if texto_lower in self.DESCARTE_EXACTO:
            return True
        
        # Descartar estados efímeros simples
        if texto_lower in self.ESTADOS_EFIMEROS:
            return True
        
        # Descartar frases muy cortas sin contenido
        if len(texto_lower.split()) <= 2:
            palabras = set(texto_lower.split())
            if palabras.issubset(self.DESCARTE_EXACTO):
                return True
        
        return False
    
    def extraer_hechos(self, texto: str) -> List[Dict]:
        """MANTENER: Extrae hechos del texto usando el método original"""
        doc = nlp_memoria(texto)
        hechos = []
        
        # Extraer por patrones lingüísticos
        hechos.extend(self._extraer_por_patrones(texto, doc))
        
        # Extraer posesiones
        hechos.extend(self._extraer_posesiones_explicitas(texto, doc))
        hechos.extend(self._extraer_posesiones_implicitas(texto, doc))
        
        # Normalizar y deduplicar
        hechos = self._deduplicar_y_normalizar(hechos)
        
        return hechos
    
    def _extraer_por_patrones(self, texto: str, doc) -> List[Dict]:
        """MANTENER: Extrae hechos basados en patrones lingüísticos"""
        hechos = []
        texto_lower = texto.lower()
        
        # Identidad - nombre
        if "me llamo" in texto_lower or "mi nombre es" in texto_lower:
            for ent in doc.ents:
                if ent.label_ in ["PER", "PERSON"]:
                    hechos.append({
                        "texto": f"mi nombre es {ent.text}",
                        "etiqueta": "identidad_personal",
                        "importancia": 0.95,
                        "retencion": "permanente",
                        "tipo": "identidad",
                        "metadata": {"nombre": ent.text, "entidad_tipo": ent.label_}
                    })
                    break
        
        # Identidad - edad
        match_edad = re.search(r'tengo\s+(\d+)\s+años?', texto_lower)
        if match_edad:
            edad = match_edad.group(1)
            hechos.append({
                "texto": f"tengo {edad} años",
                "etiqueta": "identidad_personal",
                "importancia": 0.95,
                "retencion": "permanente",
                "tipo": "edad",
                "metadata": {"edad": int(edad)}
            })
        
        # Trabajo/Estudio
        for token in doc:
            if token.lemma_ in ["trabajar", "estudiar"]:
                for child in token.children:
                    if child.dep_ in ["obl", "obj"] or (child.dep_ == "prep" and child.text in ["en", "como"]):
                        # Buscar organización o lugar
                        for ent in doc.ents:
                            if ent.label_ in ["ORG", "LOC", "GPE"]:
                                verbo = "trabajo" if token.lemma_ == "trabajar" else "estudio"
                                hechos.append({
                                    "texto": f"{verbo} en {ent.text}",
                                    "etiqueta": "trabajo_estudio",
                                    "importancia": 0.85,
                                    "retencion": "largo_plazo",
                                    "tipo": "profesional",
                                    "metadata": {"organizacion": ent.text, "tipo": ent.label_}
                                })
                                break
        
        # Ubicación
        if any(palabra in texto_lower for palabra in ["vivo en", "resido en", "soy de"]):
            for ent in doc.ents:
                if ent.label_ in ["GPE", "LOC"]:
                    hechos.append({
                        "texto": f"vivo en {ent.text}",
                        "etiqueta": "ubicacion",
                        "importancia": 0.8,
                        "retencion": "largo_plazo",
                        "tipo": "residencia",
                        "metadata": {"lugar": ent.text, "tipo": ent.label_}
                    })
        
        # Preferencias
        for verbo in ["gustar", "encantar", "preferir"]:
            if verbo in texto_lower:
                for token in doc:
                    if token.lemma_ == verbo:
                        for child in token.children:
                            if child.dep_ in ["nsubj", "obj"]:
                                objeto = self._expandir_frase_nominal(child)
                                if len(objeto) > 2:
                                    hechos.append({
                                        "texto": f"me {verbo} {objeto}",
                                        "etiqueta": "preferencias",
                                        "importancia": 0.6,
                                        "retencion": "medio_plazo",
                                        "tipo": "gusto",
                                        "metadata": {"objeto": objeto}
                                    })
        
        # Salud
        for indicador in [
            "alérgico",
            "alérgica",
            "alergia",
            "padezco",
            "sufro",
            "tengo diabetes",
            "tengo hipertensión",
        ]:
            if indicador in texto_lower:
                hechos.append({
                    "texto": texto.strip()[:100],
                    "etiqueta": "salud",
                    "importancia": 0.95,
                    "retencion": "permanente",
                    "tipo": "condicion_medica",
                    "metadata": {"indicador": indicador}
                })
        
        # Eventos futuros
        for marcador in ["mañana", "próximo", "la semana que viene", "tengo cita", "tengo reunión"]:
            if marcador in texto_lower:
                hechos.append({
                    "texto": texto.strip()[:100],
                    "etiqueta": "evento_futuro",
                    "importancia": 0.85,
                    "retencion": "temporal",
                    "tipo": "evento",
                    "metadata": {"marcador_temporal": marcador}
                })
                break
        
        return hechos
    
    def _extraer_posesiones_explicitas(self, texto: str, doc) -> List[Dict]:
        """MANTENER: Extrae posesiones explícitas con 'tengo'"""
        hechos = []
        
        if "tengo" in texto:
            for token in doc:
                if token.lemma_ == "tener":
                    for child in token.children:
                        if child.dep_ == "obj":
                            objeto = child.text.lower()
                            
                            excluir = self.ESTADOS_EFIMEROS | {
                                "años", "reunión", "cita", "junta", "examen"
                            }
                            
                            if objeto not in excluir and len(objeto) > 2:
                                if objeto in ["novia", "novio", "pareja", "esposa", "esposo"]:
                                    etiqueta = "familia"
                                    importancia = 0.85
                                elif objeto in ["perro", "gato", "mascota", "loro", "pez"]:
                                    etiqueta = "mascota"
                                    importancia = 0.8
                                else:
                                    etiqueta = "posesion"
                                    importancia = 0.7
                                
                                hechos.append({
                                    "texto": f"tengo {objeto}",
                                    "etiqueta": etiqueta,
                                    "importancia": importancia,
                                    "retencion": "largo_plazo",
                                    "tipo": "explicito",
                                    "metadata": {"objeto": objeto}
                                })
        
        return hechos
    
    def _extraer_posesiones_implicitas(self, texto: str, doc) -> List[Dict]:
        """MANTENER: Extrae posesiones implícitas: mi X, tu X, su X"""
        hechos = []
        
        # FIX 5: En es_core_news_md el posesivo "mi/mis" es hijo del sustantivo
        # con dep_="det", no al revés. Iterar sobre el sustantivo y buscar
        # determinantes posesivos entre sus hijos.
        for token in doc:
            if token.pos_ in {"NOUN", "PROPN"}:
                for child in token.children:
                    if child.dep_ == "det" and child.text.lower() in {"mi", "mis"}:
                        objeto = token.text.lower()
                        
                        excluir = {"nombre", "edad", "familia"} | self.ESTADOS_EFIMEROS
                        
                        if objeto not in excluir and len(objeto) > 2:
                            if objeto in ["novia", "novio", "pareja"]:
                                etiqueta = "familia"
                                importancia = 0.85
                            elif objeto in ["perro", "gato", "mascota"]:
                                etiqueta = "mascota"
                                importancia = 0.8
                            else:
                                etiqueta = "posesion"
                                importancia = 0.7
                            
                            hechos.append({
                                "texto": f"tengo {objeto}",
                                "etiqueta": etiqueta,
                                "importancia": importancia,
                                "retencion": "largo_plazo",
                                "tipo": "implicito",
                                "metadata": {"objeto": objeto}
                            })
                        break  # un solo "mi/mis" por token es suficiente
        
        return hechos
    
    def _expandir_frase_nominal(self, token) -> str:
        """MANTENER: Expande un token a su frase nominal completa"""
        subtree = list(token.subtree)
        subtree.sort(key=lambda t: t.i)
        frase = " ".join([t.text for t in subtree])
        frase = re.sub(r'\s+', ' ', frase).strip()
        return frase
    
    def _deduplicar_y_normalizar(self, hechos: List[Dict]) -> List[Dict]:
        """MANTENER: Normaliza y elimina duplicados semánticos"""
        if not hechos:
            return []
        
        for hecho in hechos:
            texto = hecho["texto"].lower().strip()
            texto = texto.replace("me llamo", "mi nombre es")
            if "soy" in texto and hecho.get("etiqueta") == "identidad_personal":
                texto = texto.replace("soy ", "mi nombre es ")
            hecho["texto"] = texto
        
        unicos = []
        textos_vistos = set()
        
        for hecho in hechos:
            texto_norm = hecho["texto"].strip()
            
            if texto_norm in textos_vistos:
                continue
            
            es_duplicado = False
            for texto_visto in textos_vistos:
                palabras1 = set(texto_norm.split())
                palabras2 = set(texto_visto.split())
                
                if len(palabras1) >= 2 and len(palabras2) >= 2:
                    interseccion = len(palabras1 & palabras2)
                    union = len(palabras1 | palabras2)
                    jaccard = interseccion / union if union > 0 else 0
                    
                    if jaccard > 0.7:
                        es_duplicado = True
                        break
            
            if not es_duplicado:
                unicos.append(hecho)
                textos_vistos.add(texto_norm)
        
        return unicos
    
    def extraer_fecha(self, texto: str) -> Optional[str]:
        """MANTENER: Extrae fecha de un texto usando dateparser"""
        try:
            fecha = dateparser.parse(
                texto,
                languages=['es'],
                settings={
                    'RELATIVE_BASE': datetime.now(),
                    'PREFER_DATES_FROM': 'future'
                }
            )
            
            if fecha:
                match_hora = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm|a\.m\.|p\.m\.)?', texto.lower())
                
                if match_hora:
                    hora = int(match_hora.group(1))
                    minutos = int(match_hora.group(2)) if match_hora.group(2) else 0
                    
                    if match_hora.group(3):
                        periodo = match_hora.group(3).replace('.', '').lower()
                        if periodo == 'pm' and hora < 12:
                            hora += 12
                        elif periodo == 'am' and hora == 12:
                            hora = 0
                    
                    fecha = fecha.replace(hour=hora, minute=minutos, second=0, microsecond=0)
                else:
                    fecha = fecha.replace(hour=12, minute=0, second=0, microsecond=0)
                
                fecha_str = fecha.strftime("%Y-%m-%d %H:%M:%S")
                logger.debug(f"Fecha extraída: {fecha_str} de '{texto[:50]}...'")
                return fecha_str
                
        except Exception as e:
            logger.warning(f"Error extrayendo fecha de '{texto[:50]}...': {e}")
        
        return None


if __name__ == "__main__":
    # Ejemplo de uso
    analizador = AnalizadorSemanticoV2()
    
    textos_prueba = [
        "Me llamo Juan García y tengo 30 años",
        "Trabajo como ingeniero de software en Google",
        "Tengo diabetes tipo 2",
        "Mañana tengo una reunión a las 3pm",
        "Me gusta el café por las mañanas",
        "Vivo en Madrid con mi esposa",
        "Tengo un perro llamado Max",
        "Eh... pues trabajo en Microsoft",  # Con muletillas
        "Llevo 5 años con mi pareja"
    ]
    
    print("\n🧪 Pruebas del AnalizadorSemanticoV2\n")
    print("=" * 80)
    
    for texto in textos_prueba:
        print(f"\n📝 Texto: '{texto}'")
        print("-" * 80)
        
        resultado = analizador.analizar(texto)
        
        print(f"Importancia: {resultado['importancia']:.2f}")
        print(f"Tipo memoria: {resultado['tipo_memoria']}")
        print(f"Hechos: {len(resultado['hechos_extraidos'])}")
        print(f"Tripletas: {len(resultado['tripletas'])}")
        print(f"Entidades: {len(resultado['entidades'])}")
        
        if resultado['tripletas']:
            print("\n  Tripletas extraídas:")
            for t in resultado['tripletas']:
                print(f"    - ({t['sujeto']}) --[{t['relacion_normalizada']}]--> ({t['objeto']})")
        
        if resultado['entidades']:
            print(f"\n  Entidades: {resultado['entidades']}")
    
    print("\n" + "=" * 80)
    print("✅ Pruebas completadas\n")