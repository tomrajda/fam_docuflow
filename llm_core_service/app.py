from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from contextlib import asynccontextmanager

# Korekta dla SQLite/Chroma
import sys
import pysqlite3 as sqlite3
sys.modules['sqlite3'] = sqlite3

# LangChain
from langchain_core.runnables import RunnableLambda
from langchain.chains.combine_documents.stuff import StuffDocumentsChain
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
from chromadb import HttpClient
from langchain.chains.combine_documents import create_stuff_documents_chain

# --- Konfiguracja ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CHROMA_HOST = "chroma"
CHROMA_PORT = 8000
MODEL_GENERATION = "gemini-2.5-flash-lite"
MODEL_EMBEDDING = "models/embedding-001"

# --- Lifespan FastAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set. Please check your .env file.")
    print("LLM Core Service started successfully.")
    yield
    print("LLM Core Service shutting down.")

# --- FastAPI app ---
app = FastAPI(title="LLM Core Service (RAG Query)", lifespan=lifespan)

# --- Schemat danych ---
class QueryRequest(BaseModel):
    question: str
    collection_name: str

# --- Endpoint RAG ---
@app.post("/query", tags=["RAG"])
async def rag_query(request: QueryRequest):
    try:
        # 1. Chroma + embeddings
        chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        embeddings = GoogleGenerativeAIEmbeddings(model=MODEL_EMBEDDING, api_key=GOOGLE_API_KEY)

        # 2. Retriever
        vector_store = Chroma(
            client=chroma_client,
            collection_name=request.collection_name,
            embedding_function=embeddings
        )
        retriever = vector_store.as_retriever(search_kwargs={"k": 3})

        # 3. LLM
        llm = ChatGoogleGenerativeAI(model=MODEL_GENERATION, temperature=0.0, api_key=GOOGLE_API_KEY)

        # 4. Prompt
        system_prompt = (
            "Jesteś asystentem do wyszukiwania informacji w dokumentach. "
            "Odpowiedz na pytanie bazując WYŁĄCZNIE na poniższym kontekście. "
            "Jeśli kontekst nie zawiera odpowiedzi, powiedz, że nie możesz jej znaleźć w dostarczonych dokumentach.\n\n"
            "Kontekst: {context}"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])

        # 5. Document Chain
        document_chain = create_stuff_documents_chain(llm, prompt)
        print(document_chain)

        # 6. Pobranie dokumentów (invoke zamiast deprecated get_relevant_documents)
        retriever_output = retriever.invoke(request.question)
        docs_raw = retriever_output.get("documents", retriever_output) if isinstance(retriever_output, dict) else retriever_output
        print(docs_raw)
        # 7. Konwersja na Document
        docs = []
        for d in docs_raw:
            if isinstance(d, Document):
                docs.append(d)
            elif isinstance(d, dict):
                docs.append(Document(page_content=d.get("page_content", str(d))))
            else:
                docs.append(Document(page_content=str(d)))
        print("lol")
        
        docs = [d if isinstance(d, Document) else Document(page_content=d.get("page_content", str(d)) if isinstance(d, dict) else str(d)) for d in docs_raw]
        print(docs)
        # 8. Invoke chain
        # Wywołanie chain z odpowiednim kluczem
        response = document_chain.invoke({
            "input": request.question,
            "context": docs
        })

        # 9. Zwrócenie odpowiedzi
        return {"answer": response['output_text'] if 'output_text' in response else str(response)}

    except Exception as e:
        print(f"RAG Query Failed: {e}")
        raise HTTPException(status_code=500, detail=f"RAG Query Failed: {e}")
    
@app.get("/collections")
async def list_collections():
    """Zwraca listę wszystkich dostępnych kolekcji w ChromaDB."""
    try:
        chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        collections = chroma_client.list_collections()
        
        # Ekstrakcja nazw
        names = [c.name for c in collections]
        return {"collections": names, "count": len(names)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {e}")