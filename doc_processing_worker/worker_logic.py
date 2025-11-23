import os
from PIL import ImageOps
import sys
import pysqlite3 as sqlite3
sys.modules['sqlite3'] = sqlite3

# POPRAWKA: Używamy poprawnej ścieżki dla nowych wersji LangChain
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import Chroma
from chromadb import HttpClient

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

import boto3

import pytesseract
from pdf2image import convert_from_path

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

def ocr_pdf_to_text(pdf_path: str, output_txt_path: str):
    print(f"OCR: Uruchamiam przetwarzanie wizualne dla {pdf_path}...")
    try:
        # 1. Konwersja na obrazy (DPI 300 jest BARDZO ważne, zostawiamy to)
        images = convert_from_path(pdf_path, dpi=300) 
        full_text = ""
        
        for i, image in enumerate(images):
            # --- ŁAGODNY PREPROCESSING ---
            
            # 1. Konwersja na odcienie szarości (bezpieczne)
            gray_image = image.convert('L')
            
            # 2. Autokontrast (zamiast twardego progowania)
            # To "rozciąga" histogram, sprawiając, że ciemne jest ciemniejsze, a jasne jaśniejsze,
            # ale bez niszczenia krawędzi liter.
            enhanced_image = ImageOps.autocontrast(gray_image)

            # --- OCR ---
            # Usuwamy config psm 6, wracamy do domyślnego (3), jest bardziej uniwersalny
            text = pytesseract.image_to_string(enhanced_image, lang='pol+eng')
            
            full_text += text + "\n"
            print(f"OCR: Strona {i+1} przetworzona.")
            
        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
            
        return True
    except Exception as e:
        print(f"OCR Error: {e}")
        return False


# --- Główna Funkcja Workera ---

def process_document_job(file_id: str, category: str, file_path: str):
    print(f"[*] JOB STARTED: Processing document {file_id} in category {category}")
    
    # Krok 0: Weryfikacja Klucza API
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
    if not GOOGLE_API_KEY:
        print("[ERROR] GOOGLE_API_KEY environment variable not set.")
        return False
        
    TEMP_PDF_PATH = f"/tmp/{file_id}_temp.pdf"
    TEMP_TXT_PATH = f"/tmp/{file_id}.txt"

    try:

        # 1. Pobranie pliku z MinIO
        print(f"Downloading from MinIO: {file_path}")
        s3_client.download_file(BUCKET_NAME, file_path, TEMP_PDF_PATH)
        
        # 2. Próba załadowania jako tekstowy PDF
        loader = PyPDFLoader(TEMP_PDF_PATH)
        documents = loader.load()

        # Sprawdzamy, czy udało się wydobyć sensowny tekst
        raw_text_content = "".join([doc.page_content for doc in documents])
        
        # --- LOGIKA DECYZYJNA OCR ---
        if len(raw_text_content.strip()) < 50:
            print("[INFO] Wykryto dokument typu SKAN (mało tekstu). Uruchamiam OCR...")
            
            # Uruchamiamy OCR
            if ocr_pdf_to_text(TEMP_PDF_PATH, TEMP_TXT_PATH):
                # Jeśli OCR się udał, ładujemy wynikowy plik TXT zamiast PDF
                loader = TextLoader(TEMP_TXT_PATH, encoding="utf-8")
                documents = loader.load()
                
                print("--- DEBUG: KONTEKST WYSYŁANY DO LLM ---")
                for i, doc in enumerate(documents):
                    print(f"FRAGMENT {i+1}:\n{doc.page_content[:500]}...") # Pokaż pierwsze 500 znaków
                print("---------------------------------------")

                print(f"[INFO] OCR zakończony. Wczytano tekst z {TEMP_TXT_PATH}")
            else:
                print("[WARNING] OCR nie powiódł się. Używam pustego/oryginalnego PDF.")
        else:
            print("[INFO] Dokument zawiera warstwę tekstową. OCR pominięty.")

        # 3. Chunking
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200, 
            chunk_overlap=400,
            separators=["\n\n", "\n", " ", ""]
        )
        texts = text_splitter.split_documents(documents)
        
        # Przypisanie metadanych do każdego fragmentu
        for doc in texts:
            # Metadane są używane do filtrowania w ChromaDB
            doc.metadata["category"] = category
            doc.metadata["file_id"] = file_id 

        # 2. Inicjalizacja Embeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001", 
            api_key=GOOGLE_API_KEY 
        )
        
        # 3. Zapis do ChromaDB (KRYTYCZNY PUNKT)
        # JAWNA INICJALIZACJA KLIENTA HTTP (chroma to nazwa serwisu w docker-compose)
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

        print(f"[ERROR] Job failed for {file_id}: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        
        # Czyszczenie plików tymczasowych
        if os.path.exists(TEMP_PDF_PATH):
            os.remove(TEMP_PDF_PATH)
        if os.path.exists(TEMP_TXT_PATH):
            os.remove(TEMP_TXT_PATH)

    return True


if __name__ == "__main__":

    test_file_id = "825e843d-b1e3-411b-8f3b-dee4f5e3036d"
    test_category = "Umowy"
    test_file_path = "/home/tomek/Projekty/docuflow-project/shared_files/825e843d-b1e3-411b-8f3b-dee4f5e3036d.pdf"  # Zmień na rzeczywistą ścieżkę do testowego PDF

    process_document_job(test_file_id, test_category, test_file_path)
    