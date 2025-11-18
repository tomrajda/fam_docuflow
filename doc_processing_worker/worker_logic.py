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
from psycopg2 import connect

# Ustawienia Globalne
# Klucz API powinien być dostarczony przez zmienne środowiskowe z Docker Compose/Kube Secret
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Funkcje Pomocnicze ---

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
    """
    Główna logika przetwarzania dokumentu RAG za pomocą LangChain.
    """
    if not GOOGLE_API_KEY:
        print("[ERROR] GOOGLE_API_KEY environment variable not set.")
        return False
        
    print(f"[*] JOB STARTED: Processing document {file_id} in category {category}")

    try:
        # 1. Ekstrakcja tekstu (obsługa PDF i ew. OCR)
        # Zmienna file_path powinna być dostępna wewnątrz kontenera workera
        pdf_path = perform_ocr_if_needed(file_path)
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        
        # 2. Podział na fragmenty (Chunking) - LangChain TextSplitters
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, 
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""] # Dostosowanie separatorów dla dokumentów
        )
        texts = text_splitter.split_documents(documents)
        print(f"Split into {len(texts)} chunks.")
        
        # 3. Embedding i zapis do Chroma (Vector Store)
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001", 
            api_key=GOOGLE_API_KEY 
        )
        
        # Inicjalizacja Chroma Client Settings
        chroma_client_settings = {
            "host": "chroma", 
            "port": 8000,
            "allow_reset": True # Dobra praktyka w środowisku deweloperskim
        }
        
        # Tworzenie Vector Store i dodawanie dokumentów
        # Używamy metody .from_documents, ale dodajemy client_settings,
        # co LangChain interpretuje jako połączenie HTTP.
        Chroma.from_documents(
            documents=texts,
            embedding=embeddings,
            collection_name=f"doc_collection_{file_id}",
            client_settings=chroma_client_settings 
        )

        print(f"SUCCESS: Document {file_id} indexed in ChromaDB.")
        
    except Exception as e:
        print(f"[ERROR] Job failed for {file_id}: {e}")
        # W tym miejscu powinna być logika aktualizacji PostgreSQL na 'failed'
        return False
    
    finally:
        # Opcjonalnie: usuń plik tymczasowy po przetworzeniu
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Cleaned up temporary file {file_path}")

    return True