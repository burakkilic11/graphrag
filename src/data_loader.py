import os
import fitz  # PyMuPDF
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict

# Klasör isimlerini düzgün Türkçe karşılıklarına eşleyelim.
KURUM_MAP = {
    "tedas": "TEDAŞ", # Türkiye Elektrik Dağıtım A.Ş.
    "teias": "TEİAŞ", # Türkiye Elektrik İletim A.Ş.
}

TUR_MAP = {
    "usul-esaslar": "Usul ve Esaslar",
    "yonerge": "Yönerge",
    "yonetmelik": "Yönetmelik",
    "kanunlar": "Kanun"
}

@dataclass
class Document:
    isim: str      # PDF dosya adı (artık uzantısız)
    kurum: str
    tur: str
    metin: str
    kaynak_yol: str

def load_documents_from_path(data_path: str) -> List[Document]:
    """
    Verilen 'data' klasörünü tarar, PDF'leri okur ve meta verileri çıkarır.
    PDF okuma için PyMuPDF (fitz) kullanır.
    Belge 'isim'leri .pdf uzantısı olmadan (.stem) alınır.
    """
    documents = []
    root_path = Path(data_path)

    for pdf_path in root_path.rglob("*.pdf"):
        try:
            parts = pdf_path.parts
            kurum_key = parts[-3]
            tur_key = parts[-2]
            
            # .stem kullanarak dosya adını .pdf uzantısı olmadan al
            isim = pdf_path.stem 
            
            kurum_adi = KURUM_MAP.get(kurum_key, kurum_key.capitalize())
            tur_adi = TUR_MAP.get(tur_key, tur_key.capitalize())

            metin = ""
            with fitz.open(pdf_path) as doc:
                for page in doc:
                    metin += page.get_text() + "\n"
            
            if metin.strip():
                documents.append(Document(
                    isim=isim, # Uzantısız isim
                    kurum=kurum_adi,
                    tur=tur_adi,
                    metin=metin,
                    kaynak_yol=str(pdf_path)
                ))
            print(f"[+] Yüklendi: {isim} (Kurum: {kurum_adi}, Tür: {tur_adi})")
        except Exception as e:
            print(f"[!] Hata (atlandı): {pdf_path} - {e}")
            
    return documents