import sys
from neo4j import GraphDatabase
from src.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE

# --- FAZ 2 MANUEL EŞLEŞTİRME LİSTESİ ---
CANONICAL_MAPPING = {
    # "hatalı_isim" (LLM Çıktısı) : "doğru_isim" (Kanonik Listeniz)
    
    "6446 sayılı kanun": "6446 sayılı Güncel Elektrik Piyasası Kanunu",
    "elektrik piyasası kanunu": "6446 sayılı Güncel Elektrik Piyasası Kanunu",
    
    "4628 sayılı kanun": "4628 Eski Elektrik Piyasası Kanunu",
    
    "232 sayılı khk": "233 Sayılı KHK", 
    "233 sayılı khk": "233 Sayılı KHK", 
    
    "399 sayılı khk": "399 Sayılı KHK", 
    "399 sayılı kanun hükmünde kararname": "399 Sayılı KHK", 
    
    "5346 sayılı kanun": "5346 Yenilenebilir Enerji Kaynaklarının Elektrik Enerjisi Üretimi Amaçlı Kullanımına İlişkin Kanun",
    
    "5429 sayılı kanun": "5429 Türkiye İstatistik Kanunu",
}
# --- EŞLEŞTİRME LİSTESİ SONU ---


class GraphCurator:
    """
    Neo4j grafiğini alır ve manuel eşleştirme listelerine göre temizler.
    İlişkileri yeniden yönlendirir (rewire) ve hatalı nodeları siler.
    """
    def __init__(self, driver):
        self.driver = driver
        print(f"Grafik Küratörüne '{NEO4J_DATABASE}' veritabanı için bağlanıldı.")

    # --- DÜZELTİLEN FONKSİYON ---
    def _run_query(self, query, params=None):
        """Yardımcı sorgu çalıştırma fonksiyonu (session.run() kullanır)"""
        with self.driver.session(database=NEO4J_DATABASE) as session:
            try:
                # 'session.write_transaction' yerine 'session.run' kullan
                result = session.run(query, params)
                # Orijinal kodun beklediği gibi sonucu listeye çevir
                return list(result)
            except Exception as e:
                print(f"[HATA] Sorgu başarısız: {query}\nParametreler: {params}\nHata: {e}", file=sys.stderr)
                return None
    # --- DÜZELTİLEN FONKSİYON SONU ---

    def fix_canonical_mappings(self, mapping):
        """
        CANONICAL_MAPPING'i işler.
        İlişkileri 'hatalı' noddan 'doğru' noda taşır ve 'hatalı' nodu siler.
        """
        print("\n--- Kanonik Eşleştirme (Spesifik Hatalar) Başlatıldı ---")
        if not mapping:
            print("CANONICAL_MAPPING boş, bu adım atlanıyor.")
            return

        for dirty_name, canonical_name in mapping.items():
            print(f"İşleniyor: '{dirty_name}' -> '{canonical_name}'")
            
            # 1. İlişkileri yeniden yönlendir (rewire)
            query_rewire = """
            MATCH (dirty:BELGE {isim: $dirty_name})
            MATCH (canonical:BELGE {isim: $canonical_name})
            MATCH (c:CHUNK)-[r:ATIF_YAPAR]->(dirty)
            MERGE (c)-[r_new:ATIF_YAPAR]->(canonical)
            SET r_new = properties(r)
            DELETE r
            RETURN count(r_new) AS moved_count
            """
            result = self._run_query(query_rewire, {"dirty_name": dirty_name, "canonical_name": canonical_name})
            if result is not None:
                # .data() çağrısına gerek yok, result.single() zaten kaydı verir (eğer varsa)
                count = result[0]["moved_count"] if (result and result[0]) else 0
                print(f"  > {count} atıf ilişkisi '{canonical_name}' noduna taşındı.")

            # 2. Artık ilişkisi kalmayan 'hatalı' nodu sil
            query_delete = """
            MATCH (dirty:BELGE {isim: $dirty_name})
            WHERE NOT (()-[:ATIF_YAPAR]->(dirty)) AND NOT ((dirty)-[:ICERIR]->())
            DELETE dirty
            RETURN count(dirty) AS deleted_count
            """
            result = self._run_query(query_delete, {"dirty_name": dirty_name})
            if result and result[0] and result[0]["deleted_count"] > 0:
                print(f"  > '{dirty_name}' nodu başarıyla silindi.")

        print("--- Kanonik Eşleştirme Tamamlandı ---")


def main():
    print("Faz 2: Grafik Kürasyonu Script'i Başlatıldı.")
    
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity(database=NEO4J_DATABASE)
        print("Neo4j bağlantısı başarılı.")
    except Exception as e:
        print(f"Neo4j'e bağlanılamadı: {e}", file=sys.stderr)
        return

    curator = GraphCurator(driver)
    
    # Spesifik hataları düzelt
    curator.fix_canonical_mappings(CANONICAL_MAPPING)
    
    print("\nGrafik kürasyonu tamamlandı.")
    driver.close()

if __name__ == "__main__":
    main()