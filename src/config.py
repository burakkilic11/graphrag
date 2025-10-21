import os
from dotenv import load_dotenv

load_dotenv()

# Veri Yolu
DATA_PATH = "./data"

# Neo4j Bağlantı Bilgileri
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "graphrag")

# Ollama Modelleri
EMBEDDING_MODEL = "bge-m3"
LLM_MODEL = "gemma3:4b"
OLLAMA_HOST = "http://localhost:11434"

# Ana anlamsal ayıracımız: Madde başlıkları
MADDE_REGEX = r"((?:^|\n)\s*(?:Geçici Madde \d+|Ek Madde \d+|Madde \d+)\b)"

# Hiyerarşik chunking ayarları
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100