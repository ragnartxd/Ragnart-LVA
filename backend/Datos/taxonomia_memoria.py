"""
taxonomia_memoria.py
--------------------
Sistema de etiquetado semántico basado en taxonomía JSON.

Clasifica textos en categorías semánticas usando:
- Patrones lingüísticos
- Entidades de spaCy
- Heurísticas contextuales

Fecha: 2024
"""

import os
import json
import logging
import re
from typing import Tuple
import spacy
from spacy.matcher import PhraseMatcher
from backend.utils.json_storage import guardar_json_atomico

# Configurar logging
logger = logging.getLogger(__name__)

# Cargar modelo de spaCy
try:
    nlp_memoria = spacy.load("es_core_news_md")
    logger.info("✅ Modelo spaCy cargado")
except OSError:
    logger.warning("⚠️ Modelo spaCy no encontrado. Instalando...")
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "es_core_news_md"])
    nlp_memoria = spacy.load("es_core_news_md")


class TaxonomiaMemoria:
    """
    Sistema de etiquetado semántico basado en taxonomía JSON.
    
    La taxonomía define categorías con:
    - Patrones de texto a detectar
    - Prioridad (0-10)
    - Tiempo de retención (efímero, temporal, medio_plazo, largo_plazo, permanente)
    - Entidades spaCy asociadas
    """
    
    # Taxonomía por defecto si no existe archivo JSON
    TAXONOMIA_DEFAULT = {
        "identidad_personal": {
            "patrones": [
                "me llamo", "mi nombre es", "soy", "tengo años",
                "nací en", "vivo en"
            ],
            "entidades_spacy": ["PERSON", "PER"],
            "prioridad": 10,
            "tiempo_retencion": "permanente",
            "descripcion": "Información de identidad del usuario"
        },
        "familia": {
            "patrones": [
                "mi esposa", "mi esposo", "mi hijo", "mi hija",
                "mi padre", "mi madre", "mi hermano", "mi hermana",
                "mi pareja", "mi novio", "mi novia"
            ],
            "entidades_spacy": ["PERSON"],
            "prioridad": 9,
            "tiempo_retencion": "permanente",
            "descripcion": "Relaciones familiares"
        },
        "salud": {
            "patrones": [
                "soy alérgico", "soy alérgica", "tengo alergia", "padezco",
                "enfermedad", "medicamento", "tengo diabetes",
                "tengo hipertensión", "no puedo comer"
            ],
            "entidades_spacy": [],
            "prioridad": 10,
            "tiempo_retencion": "permanente",
            "descripcion": "Información médica y de salud"
        },
        "trabajo_estudio": {
            "patrones": [
                "trabajo como", "trabajo en", "estudio",
                "soy ingeniero", "soy médico", "soy profesor",
                "mi empresa", "mi jefe"
            ],
            "entidades_spacy": ["ORG"],
            "prioridad": 8,
            "tiempo_retencion": "largo_plazo",
            "descripcion": "Información laboral y académica"
        },
        "posesion": {
            "patrones": [
                "tengo un", "tengo una", "mi carro", "mi auto",
                "mi casa", "mi apartamento", "mi mascota"
            ],
            "entidades_spacy": [],
            "prioridad": 7,
            "tiempo_retencion": "largo_plazo",
            "descripcion": "Posesiones del usuario"
        },
        "preferencias": {
            "patrones": [
                "me gusta", "me encanta", "prefiero", "adoro",
                "me fascina", "mi favorito", "mi favorita"
            ],
            "entidades_spacy": [],
            "prioridad": 6,
            "tiempo_retencion": "medio_plazo",
            "descripcion": "Gustos y preferencias"
        },
        "evento_futuro": {
            "patrones": [
                "mañana tengo", "próximo", "la semana que viene",
                "el mes que viene", "debo ir", "tengo cita",
                "tengo reunión"
            ],
            "entidades_spacy": ["DATE", "TIME"],
            "prioridad": 8,
            "tiempo_retencion": "temporal",
            "descripcion": "Eventos y compromisos futuros"
        },
        "ubicacion": {
            "patrones": [
                "vivo en", "estoy en", "me encuentro en",
                "estoy ubicado en"
            ],
            "entidades_spacy": ["GPE", "LOC"],
            "prioridad": 7,
            "tiempo_retencion": "largo_plazo",
            "descripcion": "Información de ubicación"
        },
        "contacto": {
            "patrones": [
                "mi correo es", "mi email es", "mi teléfono es",
                "mi número es", "llamame al"
            ],
            "entidades_spacy": [],
            "prioridad": 9,
            "tiempo_retencion": "permanente",
            "descripcion": "Información de contacto"
        },
        "pregunta": {
            "patrones": [
                "qué", "cómo", "cuándo", "dónde", "por qué",
                "quién", "cuál"
            ],
            "entidades_spacy": [],
            "prioridad": 1,
            "tiempo_retencion": "efimero",
            "descripcion": "Preguntas del usuario"
        },
        "conversacion_casual": {
            "patrones": [
                "hola", "buenos días", "buenas tardes", "buenas noches",
                "gracias", "de nada", "adiós", "hasta luego"
            ],
            "entidades_spacy": [],
            "prioridad": 2,
            "tiempo_retencion": "efimero",
            "descripcion": "Conversación casual sin información crítica"
        },
        "instruccion": {
            "patrones": [
                "por favor", "ayúdame", "necesito que", "quiero que",
                "podrías", "puedes"
            ],
            "entidades_spacy": [],
            "prioridad": 3,
            "tiempo_retencion": "efimero",
            "descripcion": "Instrucciones y solicitudes"
        }
    }
    
    def __init__(self, config_path: str = "backend/Datos/taxonomia_memoria.json"):
        """
        Inicializa el sistema de taxonomía.
        
        Args:
            config_path: Ruta al archivo JSON de configuración
        """
        self.config_path = config_path
        self.taxonomia = self._cargar_taxonomia()
        self.matcher = self._inicializar_matcher()
        
        logger.info(f"✅ Taxonomía cargada: {len(self.taxonomia)} categorías")
    
    def _cargar_taxonomia(self) -> dict:
        """
        Carga la taxonomía desde JSON o crea una por defecto.
        
        Returns:
            dict: Diccionario con la taxonomía
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    taxonomia = json.load(f)
                    logger.info(f"📂 Taxonomía cargada desde {self.config_path}")
                    return taxonomia
            else:
                logger.warning("⚠️ No existe taxonomía, usando default")
                self._guardar_taxonomia_default()
                return self.TAXONOMIA_DEFAULT
        except Exception as e:
            logger.error(f"❌ Error cargando taxonomía: {e}")
            logger.info("🔄 Usando taxonomía por defecto")
            return self.TAXONOMIA_DEFAULT
    
    def _guardar_taxonomia_default(self):
        """Guarda la taxonomía por defecto en disco"""
        try:
            guardar_json_atomico(
                self.config_path,
                self.TAXONOMIA_DEFAULT,
                indent=2,
                ensure_ascii=False,
                trailing_newline=False,
            )
            logger.info(f"💾 Taxonomía por defecto guardada en {self.config_path}")
        except Exception as e:
            logger.error(f"❌ Error guardando taxonomía: {e}")
    
    def _inicializar_matcher(self) -> PhraseMatcher:
        """
        Inicializa el PhraseMatcher de spaCy con los patrones.
        
        Returns:
            PhraseMatcher: Matcher configurado
        """
        try:
            matcher = PhraseMatcher(nlp_memoria.vocab, attr="LOWER")
            
            for etiqueta, config in self.taxonomia.items():
                patrones = [
                    nlp_memoria.make_doc(p) 
                    for p in config.get("patrones", [])
                ]
                if patrones:
                    matcher.add(etiqueta, patrones)
            
            logger.debug(f"✅ PhraseMatcher inicializado con {len(matcher)} categorías")
            return matcher
            
        except Exception as e:
            logger.error(f"❌ Error inicializando matcher: {e}")
            return PhraseMatcher(nlp_memoria.vocab, attr="LOWER")
    
    def clasificar(self, texto: str) -> Tuple[str, float, str]:
        """
        Clasifica el texto según la taxonomía.
        
        Proceso:
        1. Busca coincidencias de patrones con PhraseMatcher
        2. Si no hay match, busca por entidades de spaCy
        3. Si no hay entidades, aplica heurísticas
        4. Fallback: conversación casual
        
        Args:
            texto: Texto a clasificar
        
        Returns:
            Tuple[str, float, str]: (etiqueta, prioridad_normalizada, tiempo_retencion)
        """
        if not texto or not texto.strip():
            return "conversacion_casual", 0.2, "efimero"
        
        try:
            # 3. Heurísticas adicionales
            texto_limpio = texto.strip()
            
            # ¿Es pregunta?
            if texto_limpio.endswith("?") or any(
                texto_limpio.lower().startswith(p) 
                for p in ["qué", "cómo", "cuándo", "dónde", "por qué", "quién", "cuál", "cuáles", 
                          "cuánto", "cuántos", "dime", "sabes", "recuerdas",
                            "me puedes", "puedes decirme", "podrías decirme"]
            ):
                logger.debug("🏷️ Clasificado por heurística: pregunta")
                return "pregunta", 0.1, "efimero"
            
            # ¿Es instrucción? (imperativo o petición)
            if any(palabra in texto_limpio.lower() for palabra in [
                "por favor", "ayúdame", "necesito", "quiero", "podrías", "puedes", "dime", "dame", "haz",
                  "realiza", "ejecuta", "muéstrame", "enséñame"
            ]):
                logger.debug("🏷️ Clasificado por heurística: instruccion")
                return "instruccion", 0.3, "efimero"

            if re.search(r"\btengo\s+\d+\s+años?\b", texto_limpio, re.IGNORECASE):
                config = self.taxonomia["identidad_personal"]
                prioridad = config["prioridad"] / 10.0
                return "identidad_personal", prioridad, config["tiempo_retencion"]
            
            # Procesar con spaCy
            doc = nlp_memoria(texto.lower())
            
            # 1. Buscar coincidencias de patrones
            matches = self.matcher(doc)
            if matches:
                mejor_match = max(
                    matches,
                    key=lambda m: self.taxonomia[
                        nlp_memoria.vocab.strings[m[0]]
                    ]["prioridad"]
                )
                etiqueta = nlp_memoria.vocab.strings[mejor_match[0]]
                config = self.taxonomia[etiqueta]
                prioridad = config["prioridad"] / 10.0  # Normalizar a 0-1
                
                logger.debug(f"🏷️ Clasificado por patrón: {etiqueta} (p={prioridad:.2f})")
                return etiqueta, prioridad, config["tiempo_retencion"]
            
            # 2. Buscar por entidades de spaCy
            for ent in doc.ents:
                for etiqueta, config in self.taxonomia.items():
                    if ent.label_ in config.get("entidades_spacy", []):
                        prioridad = config["prioridad"] / 10.0
                        
                        logger.debug(
                            f"🏷️ Clasificado por entidad {ent.label_}: "
                            f"{etiqueta} (p={prioridad:.2f})"
                        )
                        return etiqueta, prioridad, config["tiempo_retencion"]
            
            # 4. Fallback: conversación casual
            logger.debug("🏷️ Clasificado por fallback: conversacion_casual")
            return "conversacion_casual", 0.2, "efimero"
            
        except Exception as e:
            logger.error(f"❌ Error clasificando texto: {e}")
            return "conversacion_casual", 0.2, "efimero"
    
    def agregar_categoria(self, etiqueta: str, patrones: list, 
                         prioridad: int, tiempo_retencion: str,
                         entidades_spacy: list = None,
                         descripcion: str = ""):
        """
        Agrega una nueva categoría a la taxonomía.
        
        Args:
            etiqueta: Nombre de la categoría
            patrones: Lista de patrones de texto
            prioridad: Prioridad (0-10)
            tiempo_retencion: Tipo de retención
            entidades_spacy: Lista de entidades spaCy
            descripcion: Descripción de la categoría
        """
        try:
            self.taxonomia[etiqueta] = {
                "patrones": patrones,
                "entidades_spacy": entidades_spacy or [],
                "prioridad": prioridad,
                "tiempo_retencion": tiempo_retencion,
                "descripcion": descripcion
            }
            
            # Reinicializar matcher
            self.matcher = self._inicializar_matcher()
            
            # Guardar en disco
            self._guardar_taxonomia()
            
            logger.info(f"✅ Categoría '{etiqueta}' agregada a la taxonomía")
            
        except Exception as e:
            logger.error(f"❌ Error agregando categoría: {e}")
    
    def _guardar_taxonomia(self):
        """Guarda la taxonomía actual en disco"""
        try:
            guardar_json_atomico(
                self.config_path,
                self.taxonomia,
                indent=2,
                ensure_ascii=False,
                trailing_newline=False,
            )
            logger.debug(f"💾 Taxonomía guardada en {self.config_path}")
        except Exception as e:
            logger.error(f"❌ Error guardando taxonomía: {e}")
    
    def obtener_categorias(self) -> list:
        """
        Obtiene lista de todas las categorías.
        
        Returns:
            list: Lista de nombres de categorías
        """
        return list(self.taxonomia.keys())
    
    def obtener_info_categoria(self, etiqueta: str) -> dict:
        """
        Obtiene información de una categoría específica.
        
        Args:
            etiqueta: Nombre de la categoría
        
        Returns:
            dict: Información de la categoría o None si no existe
        """
        return self.taxonomia.get(etiqueta)


if __name__ == "__main__":
    # Ejemplo de uso
    taxonomia = TaxonomiaMemoria()
    
    # Probar clasificación
    textos_prueba = [
        "Me llamo Juan García",
        "Tengo diabetes tipo 2",
        "Trabajo como ingeniero de software en Google",
        "Mañana tengo una reunión a las 3pm",
        "Me gusta el café",
        "¿Qué hora es?",
        "Hola, buenos días"
    ]
    
    print("\n🧪 Pruebas de clasificación:\n")
    for texto in textos_prueba:
        etiqueta, prioridad, retencion = taxonomia.clasificar(texto)
        print(f"Texto: '{texto}'")
        print(f"  → Etiqueta: {etiqueta}")
        print(f"  → Prioridad: {prioridad:.2f}")
        print(f"  → Retención: {retencion}\n")
