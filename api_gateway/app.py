# api_gateway/app.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from redis import Redis
from rq import Queue
import uuid
import os
import requests
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

import boto3
from botocore.config import Config
from contextlib import asynccontextmanager

from fastapi.responses import StreamingResponse
import botocore.exceptions
# Nowa Konfiguracja MinIO/S3 (używamy boto3, bo jest standardem)

MINIO_ENDPOINT = "http://minio:9000" # Wewnętrzny adres serwisu
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_NAME = "docuflow-files" # Stała nazwa zasobnika

# --- Konfiguracja ---
# W Docker Compose, 'redis' to nazwa serwisu brokera.
redis_conn = Redis(host='redis', port=6379)
queue = Queue('default', connection=redis_conn) # Używamy domyślnej kolejki

# Symulowane miejsce zapisu plików (na potrzeby testów lokalnych)
UPLOAD_DIRECTORY = "/app/shared_files"
LLM_CORE_SERVICE_URL = "http://llm_core_service:8002"

origins = [
    "http://localhost:8081",  # Adres, z którego będzie działał frontend
    "http://127.0.0.1:8081",
]



s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4'),
    verify=False
)

class QueryRequest(BaseModel):
    question: str
    categories_to_search: list[str] | None = None

# Upewnij się, że katalog istnieje
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # KOD WYKONYWANY PRZY STARCIE (Zamiast on_event("startup"))
    create_bucket_if_not_exists()
    yield
    # KOD WYKONYWANY PRZY ZAMYKANIU (Zamiast on_event("shutdown"))
    pass

# Inicjalizacja FastAPI musi używać Lifespan
app = FastAPI(title="DocuFlow API Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Zezwolenie na wszystkie metody (POST, GET)
    allow_headers=["*"],  # Zezwolenie na wszystkie nagłówki
)

@app.get("/", tags=["Healthcheck"])
def health_check():
    """Sprawdza, czy API Gateway jest aktywne."""
    return {"status": "API Gateway is running", "redis_queue_status": queue.connection.ping()}

@app.post("/document/upload", tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...), 
    category: str = "Umowy" # Parametr dodany przez front-end
    ):
    """
    Przyjmuje plik, zapisuje go i wysyła zadanie do workera przez Redis Queue.
    """
    if file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # 1. Generowanie unikalnego ID i ścieżki
    file_id = str(uuid.uuid4())
    file_location = f"{file_id}.pdf" # To będzie klucz (nazwa pliku) w buckecie

    # 2. Zapis pliku do MinIO (bezpośrednio z pamięci)
    try:
        content = await file.read()
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=file_location,
            Body=content,
            ContentType='application/pdf'
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload to MinIO: {e}")

    # 3. Umieszczenie zadania w kolejce RQ (przekazujemy klucz S3)
    job = queue.enqueue(
        'worker_logic.process_document_job',
        file_id=file_id, 
        category=category,
        file_path=file_location, # Przekazujemy klucz S3, nie ścieżkę dyskową!
        job_timeout='1h' 
    )
    
    return {
        "status": "Document upload accepted", 
        "file_id": file_id,
        "job_id": job.id,
        "message": "Processing started in background."
    }

@app.post("/query", tags=["Q&A"])
async def get_answer(request_data: QueryRequest):
    """
    Odbiera zapytanie (question, collection_name) i przekazuje je synchronicznie do LLM Core Service.
    """
    
    # Payload jest bezpośrednio obiektem Pydantic, konwertujemy go na słownik/JSON
    payload = request_data.model_dump()

    try:
        # Zmienna LLM_CORE_SERVICE_URL musi być dostępna (co już masz)
        response = requests.post(
            f"{LLM_CORE_SERVICE_URL}/query",
            json=payload,
            timeout=60 # Użyj dłuższego timeoutu dla LLM
        )
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503, 
            detail=f"LLM Core Service Unavailable or returned error: {e}"
        )

# Funkcja do tworzenia Bucketa przy starcie (niezbędne, bo MinIO nie tworzy go automatycznie)
def create_bucket_if_not_exists():
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
    except s3_client.exceptions.ClientError:
        s3_client.create_bucket(Bucket=BUCKET_NAME)

@app.get("/document/{file_id}")
async def download_document(file_id: str):
    """
    Pobiera plik z MinIO i zwraca go jako strumień PDF do przeglądarki.
    """
    # Klucz w MinIO to UUID + .pdf. Sprawdzamy, czy ID już ma rozszerzenie.
    key = f"{file_id}.pdf" if not file_id.endswith('.pdf') else file_id

    try:
        # Pobieramy obiekt z MinIO (nie ściągamy całego do RAM, tylko otwieramy strumień)
        file_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)

        # Zwracamy jako StreamingResponse - przeglądarka rozpozna PDF
        return StreamingResponse(
            file_obj['Body'], 
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename={key}"} 
            # 'inline' sprawia, że otwiera się w oknie, 'attachment' pobrałoby plik
        )

    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Plik nie został znaleziony w MinIO")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Błąd pobierania pliku: {e}")



