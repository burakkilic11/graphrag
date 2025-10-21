import sys
import re
import os
from datetime import datetime
from neo4j import GraphDatabase
from src.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE
from src.embedding_utils import EmbeddingGenerator
from src.retriever import ChatRetriever

LOG_FILENAME = "chat_history.txt"

def log_chat(filename, user_query, ai_response):
    """Sohbeti belirtilen dosyaya zaman damgasıyla kaydeder."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = (
        f"--- {timestamp} ---\n"
        f"user_question: {user_query}\n"
        f"answer: {ai_response}\n"
        f"{'-'*20}\n\n"
    )
    try:
        # 'a' modu: append (ekle), 'utf-8' Türkçe karakterler için önemli
        with open(filename, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"\n[UYARI] Sohbet log dosyasına yazılamadı ({filename}): {e}")

def main():
    print(f"GraphRAG Mevzuat Sohbet Arayüzü ({NEO4J_DATABASE} veritabanı)")
    print("Çıkmak için 'exit' veya 'quit' yazın.")
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity(database=NEO4J_DATABASE)
        print(f"Neo4j bağlantısı başarılı. (Kullanıcı: {NEO4J_USER}, Veritabanı: {NEO4J_DATABASE})")
    except Exception as e:
        print(f"Neo4j'e bağlanılamadı: {e}", file=sys.stderr)
        return

    embedder = EmbeddingGenerator()
    retriever = ChatRetriever(driver, embedder)

    try:
        while True:
            query = input("\nSoru: ")
            if query.lower() in ["exit", "quit", "çıkış"]:
                break
            
            if not query.strip():
                continue
                
            response = retriever.get_response(query)
            log_chat(LOG_FILENAME, query, response)
            
    except KeyboardInterrupt:
        print("\nÇıkış yapılıyor...")
    finally:
        driver.close()
        print("Bağlantılar kapatıldı.")

if __name__ == "__main__":
    main()