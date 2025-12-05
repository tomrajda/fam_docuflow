# Standard libraries and environment patch
import os
import sys
import requests
import uuid
from contextlib import asynccontextmanager

__import__('pysqlite3')
import pysqlite3 as sqlite3
sys.modules['sqlite3'] = sqlite3

# Web Framework
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Message Broker & Queue
from redis import Redis
from rq import Queue

# External libraries
import boto3

# Data Validation & Models
from pydantic import BaseModel

# Environment Variables
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME","docuflow-files")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))
LLM_CORE_SERVICE_URL = os.getenv("LLM_CORE_SERVICE_URL")
RAW_ORIGINS = os.getenv("CORS_ORIGINS")

# MinIO/S3 Client initializaton
s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4'),
    verify=False
)

# Redis Queue Client initialization
redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT)
queue = Queue('default', connection=redis_conn)

# CORS Configuration
origins = [origin.strip() for origin in RAW_ORIGINS.split(",")]

# Pydantic Models (Schemas)
class QueryRequest(BaseModel):
    question: str
    categories_to_search: list[str] | None = None

# Helper functions
def create_bucket_if_not_exists():
    """
    Creates the MinIO/S3 bucket if it does not exist.
    """
    
    try:
        s3_client.head_bucket(Bucket=MINIO_BUCKET_NAME)

    except s3_client.exceptions.ClientError:
        s3_client.create_bucket(Bucket=MINIO_BUCKET_NAME)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # executed on startup
    create_bucket_if_not_exists()
    yield
    # executed on shutdown
    pass

# App initialization 
app = FastAPI(title="DocuFlow API Gateway", lifespan=lifespan)

# App Middleware initialization
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Zezwolenie na wszystkie metody (POST, GET)
    allow_headers=["*"],  # Zezwolenie na wszystkie nagłówki
)

@app.get("/", tags=["Healthcheck"])
def health_check():
    """
    Healthcheck endpoint to verify that the API Gateway is running.
    """
    
    return {"status": "API Gateway is running", "redis_queue_status": queue.connection.ping()}

@app.post("/document/upload", tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...), 
    category: str = "Umowy"
    ):
    """
    Accepts the file, saves it, and 
    sends the task to the worker via Redis Queue.

    :param file: UploadFile object 
    :type file: str
    :param category: Document category
    :type category: str
    """

    if file.content_type != 'application/pdf':
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # Generating a unique ID and path
    file_id = str(uuid.uuid4())
    # key (file name) in the bucket
    file_location = f"{file_id}.pdf"

    # Save file to MinIO/S3
    try:
        content = await file.read()
        s3_client.put_object(
            Bucket=MINIO_BUCKET_NAME,
            Key=file_location,
            Body=content,
            ContentType='application/pdf'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload to MinIO/S3: {e}")

    # Add a task to RQ queue 
    job = queue.enqueue(
        'worker_logic.process_document_job',
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
    Receives the query and forwards 
    it synchronously to the LLM Core Service.

    :request_data: QueryRequest object
    :type request_data: QueryRequest
    """
    
    # Payload is Pydantic obj -> convert to Dict/JSON
    payload = request_data.model_dump()

    try:
        response = requests.post(
            f"{LLM_CORE_SERVICE_URL}/query",
            json=payload,
            timeout=60
        )
        response.raise_for_status() 
        return response.json()
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503, 
            detail=f"LLM Core Service Unavailable or returned error: {e}"
        )

@app.get("/document/{file_id}")
async def download_document(file_id: str):
    """
    Downloads a file from MinIO and 
    returns it as a PDF stream to the browser.

    :file_id: File identifier
    :type file_id: str   
    """

    # UUID key in MinIO/S3
    key = f"{file_id}.pdf" if not file_id.endswith('.pdf') else file_id

    try:
        # Get obj from MinIO/S3
        file_obj = s3_client.get_object(Bucket=MINIO_BUCKET_NAME, Key=key)

        # Return as StreamingResponse
        return StreamingResponse(
            file_obj['Body'], 
            media_type="application/pdf",
            # 'inline' open file in new window
            headers={"Content-Disposition": f"inline; filename={key}"} 
        )

    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="File not found in MinIO/S3")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File download error: {e}")