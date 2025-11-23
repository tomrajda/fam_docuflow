from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
from contextlib import asynccontextmanager

# Korekta dla SQLite/Chroma
import sys
import pysqlite3 as sqlite3
sys.modules['sqlite3'] = sqlite3

# LangChain
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
MASTER_COLLECTION_NAME = "docuflow_master_index"

# 1. Prompt GENERYCZNY (Domyślny)
# Służy do ogólnej analizy, gdy nie wiemy, co to za dokument.
PROMPT_GENERIC = (
    "Jesteś ekspertem w analizie dokumentów cyfrowych po skanowaniu (OCR).\n"
    "Twój cel: Wyciągnięcie informacji z zaszumionego tekstu.\n"
    "ZASADY:\n"
    "1. Tekst zawiera błędy literowe i dziwne znaki (szum OCR) - ignoruj je i rekonstruuj słowa z kontekstu.\n"
    "2. Jeśli informacje są rozrzucone po dokumencie, próbuj je logicznie połączyć.\n"
    "3. Nie zgaduj nazw własnych, jeśli są nieczytelne.\n"
    "4. Odpowiadaj zwięźle i na temat.\n\n"
    "Kontekst:\n{context}"
)

# 2. Prompt UMOWY (Prawny/Biznesowy)
# Nastawiony na strony umowy, kwoty, daty i podpisy.
PROMPT_CONTRACTS = (
    "Jesteś analitykiem prawnym analizującym trudne skany umów (OCR).\n"
    "ZASADY WNIOSKOWANIA (KRYTYCZNE):\n"
    "1. ZASADA JEDNEGO PRACOWNIKA: Typowa umowa o pracę dotyczy jednej osoby. Jeśli w całym dokumencie (nawet w odległych fragmentach) znajdziesz nazwisko pracownika (np. w podpisie) i sekcję z kwotą wynagrodzenia, MUSISZ przypisać tę kwotę do tej osoby.\n"
    "2. IGNORUJ UKŁAD: W OCR linie się przesuwają. Kwota '3.200 zł' może wylądować pod złym nagłówkiem. Traktuj ją jako główną stawkę, jeśli wygląda na kwotę miesięczną.\n"
    "3. ŁĄCZ FAKTY: Nie szukaj zdania 'Kowalski zarabia X'. Szukaj faktu 'Kowalski jest w dokumencie' + faktu 'W dokumencie jest kwota X'.\n"
    "4. Jeśli widzisz kwotę i nazwisko, napisz: 'Wynagrodzenie wynosi [KWOTA], na podstawie analizy treści umowy dotyczącej [NAZWISKO]'.\n\n"
    "Kontekst:\n{context}"
)

# 3. Prompt MEDYCZNY (Zdrowotny)
# Nastawiony na pacjenta, leki, diagnozy.
PROMPT_MEDICAL = (
    "Jesteś asystentem medycznym. Analizujesz wyniki badań, recepty i wypisy ze szpitala.\n"
    "ZASADY WNIOSKOWANIA:\n"
    "1. PACJENT: Szukaj imienia i nazwiska pacjenta (zwykle góra strony). Wszystkie parametry dotyczą tej osoby.\n"
    "2. PARAMETRY: Jeśli widzisz nazwy badań (np. 'Morfologia', 'TSH') i liczby obok nich, to są wyniki.\n"
    "3. ZALECENIA: Szukaj nazw leków i dawkowania (np. '1x1', '2 razy dziennie').\n"
    "4. Bądź precyzyjny. W medycynie liczby są kluczowe. Jeśli cyfra jest nieczytelna, powiedz o tym.\n\n"
    "Kontekst:\n{context}"
)

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
    categories_to_search: list[str] | None = None

# --- Endpoint RAG ---
@app.post("/query", tags=["RAG"])
async def rag_query(request: QueryRequest):

    print(f"Received RAG query: {request.question} with categories: {request.categories_to_search}")

    try:
        # 1. Chroma + embeddings
        chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        embeddings = GoogleGenerativeAIEmbeddings(model=MODEL_EMBEDDING, api_key=GOOGLE_API_KEY)

        # 3. LLM
        llm = ChatGoogleGenerativeAI(model=MODEL_GENERATION, temperature=0.8, api_key=GOOGLE_API_KEY)

        # 1. Tworzenie Retrievra (mechanizm pobierania kontekstu)
        # 1. Tworzenie filtra ChromaDB (inicjujemy jako None)
        chroma_filter = None 
            
        if request.categories_to_search and len(request.categories_to_search) > 0:
            chroma_filter = {
                "category": {"$in": request.categories_to_search}
            }

        # Tworzymy Vector Store (master index)
        vector_store = Chroma(
            client=chroma_client,
            collection_name=MASTER_COLLECTION_NAME,
            embedding_function=embeddings
        )

        # Konfiguracja parametrów wyszukiwania
        search_kwargs = {"k": 3, "score_threshold": 0.55}

        
        if chroma_filter is not None:
            search_kwargs["filter"] = chroma_filter

        # WAŻNE: Musimy ustawić search_type="similarity_score_threshold"
        retriever = vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs=search_kwargs
        )

        # 4. Wybór Promptu na podstawie Kategorii
        # Domyślnie używamy generycznego
        selected_system_prompt = PROMPT_GENERIC
        
        # Sprawdzamy, co wybrał użytkownik
        # (Zakładamy, że jeśli wybrał kilka, priorytet ma ta bardziej specyficzna)
        categories = request.categories_to_search or []
        
        if "Umowy" in categories:
            print("Selected Prompt: CONTRACTS")
            selected_system_prompt = PROMPT_CONTRACTS
        elif "Medyczne" in categories:
            print("Selected Prompt: MEDICAL")
            selected_system_prompt = PROMPT_MEDICAL

        prompt = ChatPromptTemplate.from_messages([
            ("system", selected_system_prompt),
            ("human", "{input}"),
        ])

        # 5. Document Chain
        document_chain = create_stuff_documents_chain(llm, prompt)
        print(document_chain)

        # 6. Pobranie dokumentów (invoke zamiast deprecated get_relevant_documents)
        retriever_output = retriever.invoke(request.question)

        docs_raw = retriever_output.get("documents", retriever_output) if isinstance(retriever_output, dict) else retriever_output
        
        source_documents = [
                    d if isinstance(d, Document) else Document(
                        page_content=d.get("page_content", str(d)) if isinstance(d, dict) else str(d),
                        metadata=d.get("metadata", {}) if isinstance(d, dict) else {} # Zachowujemy metadane!
                    ) 
                    for d in docs_raw
                ]
        # 8. Invoke chain
        # Wywołanie chain z odpowiednim kluczem
        response = document_chain.invoke({
                    "input": request.question,
                    "context": source_documents # Używamy skonwertowanych dokumentów
                })

        # 9. EKSTRAKCJA ŹRÓDEŁ
        unique_file_ids = set()
        for doc in source_documents:
            # Weryfikujemy, czy metadane zostały zachowane i dodajemy ID do zestawu
            if doc.metadata and "file_id" in doc.metadata:
                unique_file_ids.add(doc.metadata["file_id"])

        # 9. Zwrócenie odpowiedzi
        return {
            "answer": response['output_text'] if 'output_text' in response else str(response),
            "source_files": list(unique_file_ids)
        }

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