import ollama
import re  # 're not defined' hatası için
from .config import EMBEDDING_MODEL, OLLAMA_HOST, NEO4J_DATABASE
from neo4j import GraphDatabase

class EmbeddingGenerator:
    def __init__(self):
        self.client = ollama.Client(host=OLLAMA_HOST)
        print(f"Embedding modeli '{EMBEDDING_MODEL}' başlatıldı.")

    def get_embedding(self, text: str):
        try:
            # Metni normalleştir
            text = re.sub(r'\s+', ' ', text).strip()
            response = self.client.embeddings(model=EMBEDDING_MODEL, prompt=text)
            return response["embedding"]
        except Exception as e:
            print(f"Embedding alınırken hata: {e}")
            return None

def setup_neo4j_vector_index(driver):
    """
    Neo4j'de 'CHUNK' nodeları için vektör indexi oluşturur.
    """
    index_query = """
    CREATE VECTOR INDEX `chunk_embeddings` IF NOT EXISTS
    FOR (c:CHUNK) ON (c.embedding)
    OPTIONS { indexConfig: {
        `vector.dimensions`: 1024,
        `vector.similarity_function`: 'cosine'
    }}
    """
    
    with driver.session(database=NEO4J_DATABASE) as session:
        try:
            session.run(index_query)
            print(f"Neo4j vektör indexi 'chunk_embeddings' '{NEO4J_DATABASE}' veritabanında oluşturuldu.")
        except Exception as e:
            print(f"Neo4j vektör indexi oluşturulamadı: {e}")