import sys
import re
from neo4j import GraphDatabase
from src.config import (
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, DATA_PATH, 
    NEO4J_DATABASE
)
from src.data_loader import load_documents_from_path
from src.embedding_utils import EmbeddingGenerator, setup_neo4j_vector_index
from src.graph_builder import GraphBuilder

def main():
    print(f"GraphRAG Mevzuat Projesi - Veri Yükleme '{NEO4J_DATABASE}' veritabanına başlatıldı")

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity(database=NEO4J_DATABASE)
        print(f"Neo4j bağlantısı başarılı. (Kullanıcı: {NEO4J_USER}, Veritabanı: {NEO4J_DATABASE})")
    except Exception as e:
        print(f"Neo4j'e bağlanılamadı: {e}", file=sys.stderr)
        return

    # 1. Vektör İndexini Kur
    setup_neo4j_vector_index(driver)
    
    # 2. Embedding Modelini Başlat
    embedder = EmbeddingGenerator()
    
    # 3. Graph Builder'ı Başlat
    graph_builder = GraphBuilder(driver, embedder)

    # 4. Dokümanları Yükle
    documents = load_documents_from_path(DATA_PATH)
    if not documents:
        print("İşlenecek doküman bulunamadı.")
        return

    # 'all_doc_names' listesi kaldırıldı, çünkü artık %100 eşleşme kontrolü yapmıyoruz.
    print("Atıf mantığı: MERGE (Tüm atıflar node'a dönüştürülecek).")

    # 5. Tüm Dokümanları İşle
    for doc in documents:
        try:
            # 'all_doc_names' parametresi olmadan çağır
            graph_builder.process_document(doc)
        except Exception as e:
            print(f"[!!!] {doc.isim} işlenirken ciddi hata: {e}")

    print("Veri yükleme tamamlandı.")
    driver.close()

if __name__ == "__main__":
    main()