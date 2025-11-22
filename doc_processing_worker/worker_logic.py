import os
import pytesseract # ZMIANA: Używamy właściwej nazwy biblioteki
from PIL import Image

import sys
import pysqlite3 as sqlite3
sys.modules['sqlite3'] = sqlite3

# POPRAWKA: Używamy poprawnej ścieżki dla nowych wersji LangChain
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from chromadb import HttpClient

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

import boto3

MINIO_ENDPOINT = "http://minio:9000" 
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_NAME = "docuflow-files"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MASTER_COLLECTION_NAME = "docuflow_master_index"

s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4'),
    verify=False
)

def perform_ocr_if_needed(file_path: str) -> str:
    """
    Symulowana funkcja do ekstrakcji tekstu (dla skanów).
    W praktyce, PyPDFLoader obsługuje tekst, a Tesseract byłby dla skanów.
    Na razie pomijamy złożoną logikę detekcji, skupiając się na LangChain.
    """
    # Ta funkcja mogłaby używać: pytesseract.image_to_string(Image.open(file_path))
    # Na potrzeby uproszczenia, zakładamy, że PyPDFLoader zrobi swoją pracę,
    # ale kontener ma już Tesseract na wypadek potrzeby.
    print(f"OCR/Tekst: Analizowanie pliku {file_path}...")
    return file_path


# --- Główna Funkcja Workera ---

def process_document_job(file_id: str, category: str, file_path: str):
    print(f"[*] JOB STARTED: Processing document {file_id} in category {category}")
    
    # Krok 0: Weryfikacja Klucza API
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
    if not GOOGLE_API_KEY:
        print("[ERROR] GOOGLE_API_KEY environment variable not set.")
        return False
        
    temp_file_path = f"/app/shared_files/{file_id}.pdf"

    try:

        # 1. POBRANIE PLIKU Z MINIO (file_path to klucz S3, np. "3bece154.pdf")
        obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_path)
        pdf_content = obj['Body'].read()

        # Aby PyPDFLoader mógł to wczytać, musimy zapisać plik tymczasowo na dysk Workera
        TEMP_FILE_PATH = f"/tmp/{file_id}_temp.pdf"
        with open(TEMP_FILE_PATH, 'wb') as tmp_file:
            tmp_file.write(pdf_content)

        pdf_path_for_loader = perform_ocr_if_needed(TEMP_FILE_PATH)
        loader = PyPDFLoader(pdf_path_for_loader)
        documents = loader.load()

        # 2. Podział na fragmenty (Chunking) - LangChain TextSplitters
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""] # Dostosowanie separatorów dla dokumentów
        )
        texts = text_splitter.split_documents(documents)
        print(f"Split into {len(texts)} chunks.")
        
        # Przypisanie metadanych do każdego fragmentu
        for doc in texts:
            # Metadane są używane do filtrowania w ChromaDB
            doc.metadata["category"] = category
            doc.metadata["file_id"] = file_id 

        print(f"Split into {len(texts)} chunks with category: {category}.")


        # 2. Inicjalizacja Embeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001", 
            api_key=GOOGLE_API_KEY 
        )
        
        # 3. Zapis do ChromaDB (KRYTYCZNY PUNKT)
        
        # JAWNA INICJALIZACJA KLIENTA HTTP (chroma to nazwa serwisu w docker-compose)
        chroma_client = HttpClient(host='chroma', port=8000)
        
        # OPCJONALNY DEBUG: Sprawdzenie, czy serwer odpowiada
        # chroma_client.heartbeat() 
        # print("[INFO] Pomyślnie nawiązano połączenie HTTP z ChromaDB.")
        
        # TWORZENIE VECTOR STORE
        # vector_store = Chroma(
        #    client=chroma_client,
        #    collection_name=f"doc_collection_{file_id}",
        #    embedding_function=embeddings
        # )
        
        # DODAWANIE DOKUMENTÓW
        # vector_store.add_documents(texts)
        
        #print(f"SUCCESS: Document {file_id} indexed in ChromaDB.")

        # 3a. Inicjalizacja Klienta Chroma
        chroma_client = HttpClient(host='chroma', port=8000)

        # 3b. Tworzenie instancji ChromaDB z klientem (pozwala na interakcję z serwerem)
        vector_store = Chroma(
            client=chroma_client,
            collection_name=MASTER_COLLECTION_NAME, 
            embedding_function=embeddings
        )

        # 3c. Dodawanie dokumentów do istniejącej kolekcji/klienta
        # To jest poprawna metoda dla klienta serwerowego.
        vector_store.add_documents(texts) 

        print(f"SUCCESS: Document {file_id} indexed into {MASTER_COLLECTION_NAME}.")
        
    except Exception as e:
        # BARDZO WAŻNE: Wypisz pełny błąd dla debugowania
        print(f"[ERROR] Job failed for {file_id}: {e}")
        # Możesz dodać czyszczenie pliku tutaj (Cleaned up temporary file...)
        return False
    finally:
        
        if os.path.exists(TEMP_FILE_PATH):
            os.remove(TEMP_FILE_PATH)

    return True


if __name__ == "__main__":

    test_file_id = "825e843d-b1e3-411b-8f3b-dee4f5e3036d"
    test_category = "Umowy"
    test_file_path = "/home/tomek/Projekty/docuflow-project/shared_files/825e843d-b1e3-411b-8f3b-dee4f5e3036d.pdf"  # Zmień na rzeczywistą ścieżkę do testowego PDF

    process_document_job(test_file_id, test_category, test_file_path)
    