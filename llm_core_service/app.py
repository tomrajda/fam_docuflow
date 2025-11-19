# llm_core_service/app.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from contextlib import asynccontextmanager

# Korekty dla ChromaDB/SQLite3
import sys
# Wymuszamy użycie nowszej wersji SQLite z pakietu pysqlite3-binary
import pysqlite3 as sqlite3
sys.modules['sqlite3'] = sqlite3

# Importy LangChain (LCEL)
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from chromadb import HttpClient # Import klienta HTTP

# --- Konfiguracja Serwisu ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") 
CHROMA_HOST = "chroma"
CHROMA_PORT = 8000
MODEL_GENERATION = "gemini-2.5-flash-lite"
MODEL_EMBEDDING = "models/embedding-001"

# --- Funkcja Lifespan FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Sprawdza klucz API przy starcie i zarządza cyklem życia serwera."""
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set. Please check your .env file.")
    print("LLM Core Service started successfully.")
    
    yield
    
    print("LLM Core Service shutting down.")

# --- Inicjalizacja FastAPI ---
app = FastAPI(title="LLM Core Service (RAG Query)", lifespan=lifespan)

# --- Schemat Danych ---
class QueryRequest(BaseModel):
    question: str
    # Wartość domyślna dla kolekcji (powinna być ID ostatnio wgranego dokumentu)
    collection_name: str 

# --- Endpoint Q&A ---
@app.post("/query", tags=["RAG"])
async def rag_query(request: QueryRequest):
    """
    Wykonuje zapytanie RAG: pobiera kontekst z Chroma i generuje odpowiedź Gemini.
    """
    try:
        # 1. Inicjalizacja Klienta Chroma i Embeddings
        chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

        embeddings = GoogleGenerativeAIEmbeddings(
            model=MODEL_EMBEDDING,
            api_key=GOOGLE_API_KEY
        )

        # 2. Tworzenie Retrievera (mechanizm pobierania kontekstu)
        # Będzie szukał w konkretnej kolekcji (dokumencie)
        vector_store = Chroma(
            client=chroma_client,
            collection_name=request.collection_name,
            embedding_function=embeddings
        )
        # Pobieramy 3 najbardziej podobne fragmenty do użycia jako kontekst
        retriever = vector_store.as_retriever(search_kwargs={"k": 3}) 

        # 3. Inicjalizacja LLM (Gemini do generacji)
        llm = ChatGoogleGenerativeAI(
            model=MODEL_GENERATION,
            temperature=0.0, # Niska temperatura dla precyzyjnych odpowiedzi Q&A
            api_key=GOOGLE_API_KEY
        )

        # 4. Definicja System Promptu (LCEL)
        system_prompt = (
            "Jesteś asystentem do wyszukiwania informacji w dokumentach. "
            "Odpowiedz na pytanie bazując WYŁĄCZNIE na poniższym kontekście. "
            "Jeśli kontekst nie zawiera odpowiedzi, powiedz, że nie możesz jej znaleźć w dostarczonych dokumentach.\n\n"
            "Kontekst: {context}"
        )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                ("human", "{input}"), 
            ]
        )

        # 5. Tworzenie Łańcucha Dokumentów (Combine Docs Chain)
        document_chain = create_stuff_documents_chain(llm, prompt)

        # 6. Utworzenie Głównego Łańcucha RAG (LCEL)
        retrieval_chain = create_retrieval_chain(retriever, document_chain)

        # 7. Wykonanie zapytania
        response = retrieval_chain.invoke({"input": request.question})

        # Zwracamy tylko wygenerowaną odpowiedź
        return {"answer": response['answer']}

    except Exception as e:
        # Logowanie i zwracanie błędu
        print(f"RAG Query Failed: {e}")
        raise HTTPException(status_code=500, detail=f"RAG Query Failed: {e}")