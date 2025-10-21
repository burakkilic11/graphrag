import ollama
import json
import re  # _clean_madde_list için
from neo4j import GraphDatabase
from .config import LLM_MODEL, OLLAMA_HOST, NEO4J_DATABASE
from .embedding_utils import EmbeddingGenerator
from typing import List, Dict, Any
from .chunker import chunk_document_by_article

class GraphBuilder:
    def __init__(self, driver: GraphDatabase.driver, embedder: EmbeddingGenerator):
        self.driver = driver
        self.embedder = embedder
        self.client = ollama.Client(host=OLLAMA_HOST)
        print(f"GraphBuilder, LLM '{LLM_MODEL}' ile başlatıldı.")

    def _get_json_from_llm(self, chunk_text: str, doc_name: str) -> Dict[str, Any]:
        """
        Gemma'yı kullanarak chunk metninden atıf yapılan belge adlarını VE madde numaralarını çıkarır.
        """
        
        system_prompt = f"""
Sen bir hukuk metni analistisin. Görevin, sana verilen metin parçasını (chunk) analiz etmek ve 
aşağıdaki JSON formatında yapılandırılmış veri çıkarmaktır.

JSON ŞEMASI:
{{
  "atiflar_raw": [
    {{
      "belge_adi_raw": "string (Metinde geçtiği gibi, örn: '6446 sayılı kanun' veya 'bu kanun')",
      "madde_referanslari": [int]
    }}
  ]
}}

TALİMATLAR:
1. Sadece ve sadece JSON formatında çıktı ver. Başka hiçbir açıklama ekleme.
2. "atiflar_raw" TALİMATLARI:
   a. Metin içinde atıf yapılan belgeleri bul (mevcut belge dahil).
   b. 'belge_adi_raw' alanına, atıf yapılan belgenin adını metinde tam olarak nasıl geçiyorsa o şekilde yaz.
   c. 'madde_referanslari' alanına, atıf yapılan tamsayı madde numaralarını ekle (Alt fıkra numaralarını (1), (2) EKLEME).
   d. Atıf yoksa, "atiflar_raw" listesini boş `[]` olarak döndür.
"""
        user_prompt = f"Aşağıdaki metni analiz et:\n\nMETIN:\n\"\"\"\n{chunk_text}\n\"\"\""

        try:
            response = self.client.chat(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                format="json"
                options={'temperature': 0.3}
            )
            json_output = json.loads(response['message']['content'])
            
            if "atiflar_raw" not in json_output:
                json_output["atiflar_raw"] = []
                
            return json_output
            
        except Exception as e:
            print(f"LLM'den JSON alınırken hata: {e}")
            return {"atiflar_raw": []}

    
    def _clean_madde_list(self, raw_list: List[Any]) -> List[int]:
        """
        LLM'den gelen (atıflar için) ham madde listesini temizler ve tamsayı listesine çevirir.
        """
        cleaned_list = []
        if not isinstance(raw_list, list):
            return []
            
        for item in raw_list:
            try:
                # Doğrudan int'e çevirmeyi dene (5 veya "5" için)
                cleaned_list.append(int(item))
            except (ValueError, TypeError):
                # Hata verirse (örn: "Madde 5", "15. madde"), regex ile sayıyı ara
                match = re.search(r'\d+', str(item))
                if match:
                    cleaned_list.append(int(match.group(0)))
        
        return list(set(cleaned_list))


    def process_document(self, doc: 'Document'):
        """
        Tek bir dökümanı işler.
        LLM'den gelen TÜM atıfları 'MERGE' kullanarak [:ATIF_YAPAR] ilişkisine dönüştürür.
        Chunk'lara madde bilgisi (madde_listesi vs.) EKLEMEZ.
        """
        print(f"İşleniyor: {doc.isim}")
        
        # 'data/' klasöründen gelen belgeleri yükle
        with self.driver.session(database=NEO4J_DATABASE) as session:
            session.run(
                """
                MERGE (k:KURUM {isim: $kurum_isim})
                MERGE (b:BELGE {isim: $belge_isim})
                SET b.tur = $belge_tur, b.kurum = $kurum_isim
                MERGE (k)-[:YAYINLADI]->(b)
                """,
                kurum_isim=doc.kurum,
                belge_isim=doc.isim,
                belge_tur=doc.tur
            )
            
        # Dokümanı madde bazlı (semantik) chunk'lara ayır
        chunks = chunk_document_by_article(doc.metin)
        
        for i, chunk_data in enumerate(chunks):
            chunk_text = chunk_data["metin"]
            
            embedding = self.embedder.get_embedding(chunk_text)
            if not embedding:
                print(f"   [!] Chunk {i} için embedding alınamadı, atlanıyor.")
                continue

            # LLM'den sadece atıf verilerini al
            llm_json_data = self._get_json_from_llm(chunk_text, doc.isim)
            raw_references_list = llm_json_data.get("atiflar_raw", [])
            
            with self.driver.session(database=NEO4J_DATABASE) as session:
                
                # 1. CHUNK nodunu oluştur (madde bilgisi olmadan)
                result = session.run(
                    """
                    MATCH (b:BELGE {isim: $belge_isim})
                    CREATE (c:CHUNK {
                        metin: $metin,
                        kaynak_belge: $belge_isim,
                        embedding: $embedding
                    })
                    CREATE (b)-[:ICERIR]->(c)
                    RETURN elementId(c) AS chunk_id
                    """,
                    belge_isim=doc.isim,
                    metin=chunk_text,
                    embedding=embedding
                )
                chunk_node_id = result.single()["chunk_id"]

                # 2. Atıfları işle (MERGE mantığı)
                for atif in raw_references_list:
                    llm_belge_ismi = atif.get("belge_adi_raw")
                    if not llm_belge_ismi:
                        continue
                    
                    # LLM'in atıf için bulduğu madde listesini temizle
                    atif_madde_listesi = self._clean_madde_list(
                        atif.get("madde_referanslari", [])
                    )
                    
                    print(f"      [~] Atıf İLİŞKİSİ (MERGE): '{llm_belge_ismi}' Maddeler: {atif_madde_listesi}")
                    session.run(
                        """
                        MATCH (c:CHUNK) WHERE elementId(c) = $chunk_id
                        
                        // Hedef belgeyi MERGE et (yoksa oluştur, varsa eşleştir)
                        // Bu, "6446 sayılı kanun" gibi hatalı/yeni nodelar oluşturacak (Faz 2'de temizlenecek)
                        MERGE (b_hedef:BELGE {isim: $hedef_belge_isim})
                        
                        // İlişkiyi MERGE et ve madde özelliğini ayarla
                        MERGE (c)-[r:ATIF_YAPAR]->(b_hedef)
                        SET r.madde = $madde_listesi
                        """,
                        chunk_id=chunk_node_id,
                        hedef_belge_isim=llm_belge_ismi, # LLM'in ham çıktısı
                        madde_listesi=atif_madde_listesi 
                    )

            print(f"   [+] Chunk {i} eklendi (İşlenen Atıf Sayısı: {len(raw_references_list)})")