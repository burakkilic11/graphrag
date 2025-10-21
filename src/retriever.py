import ollama
import re  # Madde aramak için Python'un Regex kütüphanesini import ediyoruz
from neo4j import GraphDatabase
from .config import EMBEDDING_MODEL, LLM_MODEL, OLLAMA_HOST, NEO4J_DATABASE
from .embedding_utils import EmbeddingGenerator

class ChatRetriever:
    def __init__(self, driver: GraphDatabase.driver, embedder: EmbeddingGenerator):
        self.driver = driver
        self.embedder = embedder
        self.client = ollama.Client(host=OLLAMA_HOST)

    def _find_chunks_for_articles(self, session, hedef_belge_isim: str, hedef_maddeler: list[int]) -> list[str]:
        """
        Yardımcı fonksiyon: Bir belgenin TÜM chunk'larını çeker ve
        Python Regex kullanarak belirli maddeleri içerenleri arar.
        """
        if not hedef_maddeler:
            return []

        # 1. Hedef belgenin TÜM chunk'larını Neo4j'den çek
        query_all_chunks = """
        MATCH (b:BELGE {isim: $belge_isim})-[:ICERIR]->(c:CHUNK)
        RETURN c.metin AS metin
        """
        records = session.run(query_all_chunks, belge_isim=hedef_belge_isim)
        all_chunk_texts = [record["metin"] for record in records]
        
        if not all_chunk_texts:
            print(f"      [!] '{hedef_belge_isim}' için chunk bulunamadı (Bu bir kanonik belge olmayabilir).")
            return []

        # 2. Python Regex ile bu chunk'lar içinde maddeleri ara
        found_chunk_texts = []
        for madde_no in hedef_maddeler:
            # "Madde 5", "Ek Madde 5", "Geçici Madde 5" kalıplarını (büyük/küçük harf duyarsız) arar
            madde_regex = re.compile(rf'(?i)(?:Madde|Ek Madde|Geçici Madde)\s+{madde_no}\b')
            
            for chunk_text in all_chunk_texts:
                if madde_regex.search(chunk_text):
                    print(f"      [~] Derin Gezinti BAŞARILI: '{hedef_belge_isim}' içinden Madde {madde_no} bulundu.")
                    found_chunk_texts.append(chunk_text)
                    break # Bu madde için chunk'ı bulduk, sonraki maddeye geç
        
        return found_chunk_texts


    def get_response(self, user_query: str):
        print(f"Sorgu alindi: {user_query}")

        query_embedding = self.embedder.get_embedding(user_query)
        if not query_embedding:
            return "Sorgunuz için embedding oluşturulamadı."

        # --- 1. Adım: Vektör Arama (Tohumlama, k=5 ve Kurum Bilgisi) ---
        k_seed = 5 # Alınacak tohum chunk sayısı
        
        with self.driver.session(database=NEO4J_DATABASE) as session:
            vector_search_result = session.run(
                """
                CALL db.index.vector.queryNodes('chunk_embeddings', $k, $embedding)
                YIELD node AS chunk, score
                
                // Kaynak belgeyi ve Kurumunu bul
                MATCH (b_kaynak:BELGE)-[:ICERIR]->(chunk)
                MATCH (k_kaynak:KURUM)-[:YAYINLADI]->(b_kaynak)
                
                RETURN elementId(chunk) AS chunk_id, 
                       chunk.metin AS metin, 
                       b_kaynak.isim AS kaynak_belge,
                       k_kaynak.isim AS kaynak_kurum, // Kurum bilgisi eklendi
                       score
                ORDER BY score DESC
                LIMIT $k
                """,
                k=k_seed,
                embedding=query_embedding
            )
            retrieved_chunks = [record.data() for record in vector_search_result]
        
        if not retrieved_chunks:
            return "İlgili bilgi bulunamadı."

        seed_chunk_ids = [chunk['chunk_id'] for chunk in retrieved_chunks]
        context_str = ""
        
        # --- 2. Adım: Bağlam 1 (Tohum Chunk'lar) ---
        for i, chunk in enumerate(retrieved_chunks):
            context_str += (
                f"--- BAĞLAM {i+1} (Tohum Chunk)\n"
                f"Kurum: {chunk['kaynak_kurum']}\n"
                f"Kaynak Belge: {chunk['kaynak_belge']}\n"
                f"Metin:\n{chunk['metin']}\n---\n\n"
            )
            
        # --- 3. Adım: Grafik Gezintisi (1. Seviye Atıflar) ---
        with self.driver.session(database=NEO4J_DATABASE) as session:
            graph_relations_result = session.run(
                """
                MATCH (c:CHUNK)-[r:ATIF_YAPAR]->(b_hedef:BELGE)
                WHERE elementId(c) IN $chunk_ids
                RETURN c.kaynak_belge AS kaynak_belge_ati_yapan, 
                       b_hedef.isim AS hedef_belge, 
                       r.madde AS hedef_maddeler
                """,
                chunk_ids=seed_chunk_ids
            )
            graph_relations = [record.data() for record in graph_relations_result]

        # --- 4. Adım: Bağlam 2 (İlişkiler ve Derin Gezinti) ---
        if graph_relations:
            context_str += "--- İLGİLİ BAĞLANTILAR (Grafikten Alındı) ---\n"
            
            with self.driver.session(database=NEO4J_DATABASE) as session_for_deep_traversal:
                for i, relation in enumerate(graph_relations):
                    hedef_belge = relation['hedef_belge']
                    hedef_maddeler = relation['hedef_maddeler']
                    
                    context_str += (
                        f"Bağlantı {i+1}: '{relation['kaynak_belge_ati_yapan']}' dokümanı, "
                        f"'{hedef_belge}' dokümanına atıf yapıyor."
                    )
                    
                    if not hedef_maddeler:
                        context_str += " (Madde belirtilmemiş).\n\n"
                        continue # Derin gezintiye gerek yok
                    
                    # --- 4b. Adım: Derin Gezinti (2. Seviye) ---
                    context_str += f" (İlgili maddeler: {hedef_maddeler})\n"
                    
                    # Python'da Regex ile ilgili maddelerin metinlerini bul
                    found_article_texts = self._find_chunks_for_articles(
                        session_for_deep_traversal, 
                        hedef_belge, 
                        hedef_maddeler
                    )
                    
                    if found_article_texts:
                        for j, text in enumerate(found_article_texts):
                            context_str += (
                                f"  --- EK BAĞLAM (Atıf Yapılan Madde Metni {j+1} - Kaynak: {hedef_belge}) ---\n"
                                f"  {text}\n"
                                f"  ---\n"
                            )
                    else:
                        context_str += f"  (Not: '{hedef_belge}' içindeki {hedef_maddeler} maddelerinin metni KG'de bulunamadı.)\n"
                    
                    context_str += "\n"
        
        # --- 5. Adım: LLM'e Gönderme ---
        system_prompt = """
Sen Türkiye enerji mevzuatı konusunda uzman bir yapay zeka asistanısın.
Sana iki tür bilgi sağlanacak:
1. 'BAĞLAM (Tohum Chunk)': Kullanıcının sorusuyla doğrudan ilgili metin parçaları (Kurum ve Kaynak Belge bilgisiyle).
2. 'İLGİLİ BAĞLANTILAR' ve 'EK BAĞLAM': Bu tohum chunk'ların grafikteki diğer belgelere yaptığı atıflar VE o atıf yapılan maddelerin metinleri.

Görevin, bu bilgileri birleştirerek kullanıcının sorusunu kapsamlı bir şekilde cevaplamaktır.
Cevabını SADECE sağlanan bu bilgilere dayandır.
Eğer cevap bağlamda yoksa, 'Sağlanan belgelerde bu bilgiye ulaşamadım.' de.
Cevaplarını açık, net ve Türkçe ver.
        """
        
        final_prompt = f"BAĞLAM:\n{context_str}\n\nSORU: {user_query}"
        
        try:
            response_stream = self.client.chat(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": final_prompt}
                ],
                stream=True
            )
            
            print("\n--- Cevap ---")
            full_response = ""
            for chunk in response_stream:
                content = chunk['message']['content']
                print(content, end="", flush=True)
                full_response += content
            print("\n-----------")
            return full_response
            
        except Exception as e:
            return f"LLM ile cevap üretirken hata: {e}"