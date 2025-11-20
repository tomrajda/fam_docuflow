# api_gateway/app.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from redis import Redis
from rq import Queue
import uuid
import os
import requests
from pydantic import BaseModel

# --- Konfiguracja ---
# W Docker Compose, 'redis' to nazwa serwisu brokera.
redis_conn = Redis(host='redis', port=6379)
q = Queue('default', connection=redis_conn) # Używamy domyślnej kolejki
app = FastAPI(title="DocuFlow API Gateway")
# Symulowane miejsce zapisu plików (na potrzeby testów lokalnych)
UPLOAD_DIRECTORY = "/app/shared_files"
LLM_CORE_SERVICE_URL = "http://llm_core_service:8002"

class QueryRequest(BaseModel):
    question: str
    collection_name: str

# Upewnij się, że katalog istnieje
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)


@app.get("/", tags=["Healthcheck"])
def health_check():
    """Sprawdza, czy API Gateway jest aktywne."""
    return {"status": "API Gateway is running", "redis_queue_status": q.connection.ping()}

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
    file_location = os.path.join(UPLOAD_DIRECTORY, f"{file_id}.pdf")
    
    # 2. Zapis pliku na dysk (w pełnej architekturze będzie to MinIO/S3)
    try:
        with open(file_location, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    
    # 3. Umieszczenie zadania w kolejce RQ
    # Wskazujemy funkcję w module workera, która ma zostać wywołana
    job = q.enqueue(
        'worker_logic.process_document_job',  # <--- UŻYWAMY TYLKO NAZWY PLIKU PYTHONOWEGO
        file_id=file_id, 
        category=category,
        file_path=file_location,
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