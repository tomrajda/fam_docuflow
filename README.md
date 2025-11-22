@LangChain @FastAPI @LLM @Google @Gemini @ChromaDB @Redis @Vue.js @S3 @Tesseract
# DocuFlow: RAG Microservices Application

DocuFlow is a modern application that allows users to upload private PDF
documents and ask questions about their content using Gemini models and RAG
(Retrieval-Augmented Generation).

------------------------------------------------------------------------

## Services Overview

-   **Frontend (Vue.js):** User-friendly web interface for uploading
    documents and interacting with the Q&A chat.
-   **API Gateway (FastAPI):** Main entry point that handles user
    requests, manages file uploads to MinIO, and dispatches background
    jobs.
-   **Redis:** In-memory message broker for managing the asynchronous
    processing queue.
-   **Doc Processing Worker (FastAPI / LangChain):** Background worker
    performing OCR, text chunking, and embedding generation.
-   **LLM Core Service (FastAPI / LangChain):** Handles semantic search
    and AI answer generation using Google Gemini.
-   **MinIO:** S3-compatible object storage for securely storing PDF
    files.
-   **ChromaDB:** Vector database storing embeddings for fast document
    retrieval.
-   **PostgreSQL:** Relational database storing structured metadata
    about documents and users.

------------------------------------------------------------------------

## Architecture Diagram

Data flow during **Document Upload** and **Question Answering**:

``` mermaid
graph TD
    %% Clients
    Client([Frontend Vue.js])

    %% Entry Point
    API[API Gateway]

    %% Infrastructure
    Redis[(Redis Queue)]
    MinIO[(MinIO Object Storage)]
    Chroma[(Chroma Vector DB)]

    %% Workers & Logic
    Worker[Doc Processing Worker]
    LLMCore[LLM Core Service]

    %% External AI
    Gemini((Google Gemini API))

    %% --- Upload Flow (Asynchronous) ---
    Client -- "1. Upload PDF" --> API
    API -- "2. Save File" --> MinIO
    API -- "3. Enqueue Job" --> Redis
    Redis -- "4. Consume Job" --> Worker
    Worker -- "5. Fetch PDF" --> MinIO
    Worker -- "6. Generate Embeddings" --> Gemini
    Worker -- "7. Index Vectors" --> Chroma

    %% --- Q&A Flow (Synchronous) ---
    Client -- "A. Ask Question" --> API
    API -- "B. Proxy Request" --> LLMCore
    LLMCore -- "C. Semantic Search" --> Chroma
    LLMCore -- "D. RAG Generation" --> Gemini
    LLMCore -- "E. Answer + Source ID" --> Client

    %% Styling
    style API fill:#f9f,stroke:#333,stroke-width:2px
    style Worker fill:#bbf,stroke:#333,stroke-width:2px
    style LLMCore fill:#bbf,stroke:#333,stroke-width:2px
    style Gemini fill:#ff9,stroke:#333,stroke-width:4px
```

------------------------------------------------------------------------

## Getting Started

### Prerequisites

-   Docker & Docker Compose
-   Google Gemini API Key

------------------------------------------------------------------------

## Installation

### 1. Clone the repository

``` bash
git clone https://github.com/tomrajda/fam_docuflow.git
cd repo
```

### 2. Create a `.env` file in the root directory

``` env
GOOGLE_API_KEY="your_actual_api_key_here"
```

### 3. Build and start all microservices

``` bash
docker compose up -d --build
```

### 4. Access the application

Open: **http://localhost:8081**