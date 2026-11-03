# utils/embeddings.py  ← archivo único compartido
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

_embedding_model: SentenceTransformer | None = None

def cargar_modelo_embeddings_general(nombre: str = "paraphrase-multilingual-MiniLM-L12-v2") -> SentenceTransformer:
    """
    Devuelve siempre la misma instancia del modelo (singleton).
    Solo carga desde disco la primera vez que se llama.
    """
    global _embedding_model

    if _embedding_model is not None:
        return _embedding_model  # Ya estaba cargado, devolver directo

    try:
        logger.info(f"📥 Cargando modelo de embeddings: {nombre}")
        _embedding_model = SentenceTransformer(nombre)
        logger.info("✅ Modelo de embeddings cargado")
        return _embedding_model
    except Exception as e:
        logger.error(f"❌ Error cargando modelo de embeddings: {e}")
        raise RuntimeError(
            f"No se pudo cargar el modelo '{nombre}'. "
            "Verifica tu conexión a internet y que el modelo exista."
        ) from e