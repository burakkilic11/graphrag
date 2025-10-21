# GraphRAG

Türkiye enerji sektörü mevzuat dokümanlarını otomatik olarak bilgi grafına dönüştüren, semantik ve ilişkisel arama ile doğal dilde yanıtlar üreten bir GraphRAG (Graph-based Retrieval-Augmented Generation) projesi.

---

## Özellikler

- PDF mevzuat dokümanlarını otomatik okuma ve madde bazlı parçalara ayırma
- Chunk’lar arası atıf ilişkilerini LLM ile tespit edip Neo4j bilgi grafına yükleme
- Embedding tabanlı semantik arama ve grafik tabanlı bağlam toplama
- Doğal dilde soru-cevap ve sohbet desteği (LLM ile)
- Sohbet geçmişi kaydı ve manuel grafik kürasyonu

---

## Kurulum

### 1. Gerekli Yazılımlar

- [Python 3.10+](https://www.python.org/)
- [Neo4j Community Server](https://neo4j.com/download-center/#community)
- [Ollama](https://ollama.com/) (LLM ve embedding için)

### 2. Depoyu Klonlayın

```sh
git clone https://github.com/kullaniciadiniz/graphrag.git
cd graphrag
```

### 3. Sanal Ortam Oluşturun ve Aktif Edin

```sh
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

### 4. Bağımlılıkları Yükleyin

```sh
pip install -r requirements.txt
```

### 5. Ortam Değişkenlerini Ayarlayın

Proje kök dizinine `.env` dosyası oluşturun ve aşağıdaki gibi doldurun:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=parolaniz
OLLAMA_API_URL=http://localhost:11434
```

### 6. Neo4j ve Ollama’yı Başlatın

- Neo4j’i başlatın ve yukarıdaki kullanıcı adı/şifre ile erişilebilir olduğundan emin olun.
- Ollama’yı başlatın ve aşağıdaki modelleri yükleyin:
    ```sh
    ollama pull gemma:3b
    ollama pull bge-m3
    ```

---

## Kullanım

### 1. Mevzuat Dokümanlarını Yükleyin

- PDF dosyalarını `data/` klasörüne yerleştirin (örnekler repoda mevcutsa kullanabilirsiniz).

### 2. Veriyi Graf’a Yükleyin

```sh
python main_ingest.py
```
- Bu adım, PDF’leri okuyup chunk’lara böler, embedding’leri üretir ve Neo4j grafına yükler.

### 3. Grafik Kürasyonu (Opsiyonel)

```sh
python curate_graph.py
```
- Yanlış veya eksik node/ilişkileri manuel olarak düzeltir.

### 4. Soru-Cevap ve Sohbet

```sh
python main_chat.py
```
- Doğal dilde mevzuat soruları sorabilir, yanıtları ve sohbet geçmişini görebilirsiniz.

---

## Ek Notlar

- Sohbet geçmişi `chat_history.txt` dosyasında tutulur.
- Okunan/okunamayan dokümanlar `dokuman_listesi.txt` dosyasında listelenir.
- `data/` klasöründeki dosya adlarının çok uzun olmamasına dikkat edin (Windows dosya yolu sınırı nedeniyle).

---
