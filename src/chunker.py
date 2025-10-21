import re
from typing import List, Dict, Any
from .config import MADDE_REGEX, CHUNK_SIZE, CHUNK_OVERLAP
from langchain_text_splitters import RecursiveCharacterTextSplitter

def chunk_document_by_article(document_text: str) -> List[Dict[str, Any]]:
    """
    Bir doküman metnini hiyerarşik olarak chunk'lara ayırır.
    1. Önce 'MADDE_REGEX' ile anlamsal olarak ayırır (anlamsal bağlamı korur).
    2. Ardından, 'CHUNK_SIZE'ı aşan anlamsal parçaları daha küçük parçalara böler.
    3. Bölünen her parçanın başına ana madde başlığını ekleyerek bağlamı korur.
    
    Not: Bu fonksiyonun döndürdüğü 'madde_basligi_tahmini' artık KG'ye EKLENMİYOR,
    ancak bölme stratejisi (semantik ayırma) devam ediyor.
    """
    
    sub_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    parts = re.split(MADDE_REGEX, document_text, flags=re.IGNORECASE | re.MULTILINE)
    chunks = []
    
    # Giriş Metni
    giris_metni = parts[0].strip()
    if giris_metni:
        if len(giris_metni) > CHUNK_SIZE:
            sub_texts = sub_splitter.split_text(giris_metni)
            for j, sub_text in enumerate(sub_texts):
                chunks.append({
                    "metin": sub_text,
                    "madde_basligi_tahmini": f"Giriş (Bölüm {j+1})"
                })
        else:
            chunks.append({
                "metin": giris_metni,
                "madde_basligi_tahmini": "Giriş"
            })
            
    # Madde Metinleri
    i = 1
    while i < len(parts):
        madde_basligi = parts[i].strip()
        madde_icerigi = parts[i+1].strip() if (i + 1) < len(parts) else ""
        
        full_chunk_text = f"{madde_basligi}\n{madde_icerigi}"
        madde_basligi_tahmini = madde_basligi.split('\n')[0]

        if len(full_chunk_text) > CHUNK_SIZE:
            print(f"   [!] Uzun madde bölünüyor: {madde_basligi_tahmini} ({len(full_chunk_text)} char)")
            
            sub_texts = sub_splitter.split_text(madde_icerigi)
            
            for j, sub_text in enumerate(sub_texts):
                prepended_text = f"{madde_basligi}\n(Bölüm {j+1})\n{sub_text}"
                
                chunks.append({
                    "metin": prepended_text,
                    "madde_basligi_tahmini": f"{madde_basligi_tahmini} (Bölüm {j+1})"
                })
        else:
            chunks.append({
                "metin": full_chunk_text.strip(),
                "madde_basligi_tahmini": madde_basligi_tahmini
            })
        
        i += 2
        
    return chunks