# Standard libraries and environment patch
import os
from contextlib import asynccontextmanager

import sys
import pysqlite3 as sqlite3
sys.modules['sqlite3'] = sqlite3

# Data Validation & Models
from pydantic import BaseModel

# Web Framework
from fastapi import FastAPI, HTTPException

# LangChain libraries
# Prompts
from langchain_core.prompts import ChatPromptTemplate
# Google, Embeddings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
# Vector Stores
from langchain_community.vectorstores import Chroma
# Document Schema 
from langchain.schema import Document
# Document Chains
from langchain.chains.combine_documents import create_stuff_documents_chain

# Vector Database libraries
from chromadb import HttpClient

# Environment Variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = int(os.getenv("CHROMA_PORT"))
MODEL_GENERATION = os.getenv("MODEL_GENERATION")
MODEL_EMBEDDING = os.getenv("MODEL_EMBEDDING")
MASTER_COLLECTION_NAME = os.getenv("MASTER_COLLECTION_NAME")

# Generic Prompt (Default)
# overall analysis when we don't know the document type
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

# UMOWY Prompt (Prawny/Biznesowy)
# dedicated to contracts, agreements, financial terms
PROMPT_CONTRACTS = (
    "Jesteś analitykiem prawnym analizującym trudne skany umów (OCR).\n"
    "ZASADY WNIOSKOWANIA (KRYTYCZNE):\n"
    "1. ZASADA JEDNEGO PRACOWNIKA: Typowa umowa o pracę dotyczy jednej osoby. Jeśli w całym dokumencie (nawet w odległych fragmentach) znajdziesz nazwisko pracownika (np. w podpisie) i sekcję z kwotą wynagrodzenia, MUSISZ przypisać tę kwotę do tej osoby.\n"
    "2. IGNORUJ UKŁAD: W OCR linie się przesuwają. Kwota '3.200 zł' może wylądować pod złym nagłówkiem. Traktuj ją jako główną stawkę, jeśli wygląda na kwotę miesięczną.\n"
    "3. ŁĄCZ FAKTY: Nie szukaj zdania 'Kowalski zarabia X'. Szukaj faktu 'Kowalski jest w dokumencie' + faktu 'W dokumencie jest kwota X'.\n"
    "4. Jeśli widzisz kwotę i nazwisko, napisz: 'Wynagrodzenie wynosi [KWOTA], na podstawie analizy treści umowy dotyczącej [NAZWISKO]'.\n\n"
    "Kontekst:\n{context}"
)

# MEDYCZNY Prompt (Zdrowotny)
# dedicated to medical documents, prescriptions, diagnoses
PROMPT_MEDICAL = (
    "Jesteś asystentem medycznym. Analizujesz wyniki badań, recepty i wypisy ze szpitala.\n"
    "ZASADY WNIOSKOWANIA:\n"
    "1. PACJENT: Szukaj imienia i nazwiska pacjenta (zwykle góra strony). Wszystkie parametry dotyczą tej osoby.\n"
    "2. PARAMETRY: Jeśli widzisz nazwy badań (np. 'Morfologia', 'TSH') i liczby obok nich, to są wyniki.\n"
    "3. ZALECENIA: Szukaj nazw leków i dawkowania (np. '1x1', '2 razy dziennie').\n"
    "4. Bądź precyzyjny. W medycynie liczby są kluczowe. Jeśli cyfra jest nieczytelna, powiedz o tym.\n\n"
    "Kontekst:\n{context}"
)

# Pydantic Models (Schemas)
class QueryRequest(BaseModel):
    question: str
    categories_to_search: list[str] | None = None

# Lifespan FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set. Please check your .env file.")
    print("LLM Core Service started successfully.")
    yield
    print("LLM Core Service shutting down.")

# FastAPI app
app = FastAPI(title="LLM Core Service (RAG Query)", lifespan=lifespan)

@app.post("/query", tags=["RAG"])
async def rag_query(request: QueryRequest):
    """
    Main RAG endpoint.
    1. Converts the question into a vector.
    2. Searches for similar fragments in ChromaDB (Retrieval).
    3. Selects the appropriate Prompt based on the category.
    4. Generates a response using Gemini (Generation).
    5. Returns the response and sources (file IDs).

    :request_data: QueryRequest object
    :type request_data: QueryRequest
    """
    
    print(f"Received RAG query: {request.question} with categories: {request.categories_to_search}")

    try:
        
        # -- COMPONENTS INITIALIZATION --
        # Chroma + embeddings Initialization
        chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        embeddings = GoogleGenerativeAIEmbeddings(model=MODEL_EMBEDDING, api_key=GOOGLE_API_KEY)
        
        # Vector Store Object (represents ChromaDB collection)
        vector_store = Chroma(
            client=chroma_client,
            collection_name=MASTER_COLLECTION_NAME,
            embedding_function=embeddings
        )
        
        # -- RETRIEVER CONFIGURATION --
        # Create metadata filter (if user selected category)
        chroma_filter = None    
        if request.categories_to_search and len(request.categories_to_search) > 0:
            chroma_filter = {
                "category": {"$in": request.categories_to_search}
            }

        # Configure search parameters
        search_kwargs = {"k": 3, "score_threshold": 0.55}

        if chroma_filter is not None:
            search_kwargs["filter"] = chroma_filter

        # Create Retriever 
        # (its queries like "select * from documents where ..." in vector area)
        retriever = vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs=search_kwargs
        )

        # -- LLM MODEL AND PROMPT CONFIGUTARTION --
        llm = ChatGoogleGenerativeAI(
            model=MODEL_GENERATION, 
            temperature=0.8, # creative is little bit higher for better thinking
            api_key=GOOGLE_API_KEY)

        # Prompt Selection based on category
        selected_system_prompt = PROMPT_GENERIC
        categories = request.categories_to_search or []
        
        if "Umowy" in categories:
            print("Selected Prompt: CONTRACTS")
            selected_system_prompt = PROMPT_CONTRACTS
        elif "Medyczne" in categories:
            print("Selected Prompt: MEDICAL")
            selected_system_prompt = PROMPT_MEDICAL

        # Final prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", selected_system_prompt), # prompt - who are you
            ("human", "{input}"),               # user question
        ])

        # -- RETRIEVAL --
        # Querying the retriever to get relevant documents/fragments
        retriever_output = retriever.invoke(request.question)

        # Just in case, sometimes Chroma returns a dict instead of a list
        docs_raw = retriever_output.get(
            "documents", retriever_output) if isinstance(
                retriever_output, dict) else retriever_output
        
        # Conversion to clean Document objects (standardization for LangChain)
        # This is necessary to prevent the text processing chain from crashing.
        source_documents = [
                    d if isinstance(d, Document) else Document(
                        page_content=d.get("page_content", str(d)) if isinstance(d, dict) else str(d),
                        metadata=d.get("metadata", {}) if isinstance(d, dict) else {} # Preserve metadata
                    ) 
                    for d in docs_raw
                ]
        
        # If the list is empty after filtering (threshold), stop now
        if not source_documents:
            return {
                "answer": "I did not find any documents matching this query (match confidence too low).",
                "source_files": []
            }

        # -- RESPONSE GENERATION (CHAIN EXECUTION) --

        # We create a chain that:
        # 1. Takes a list of documents
        # 2. Sticks them together into one long text (stuffing)
        # 3. Inserts them into the Prompt in place of {context}
        # 4. Sends them to LLM

        document_chain = create_stuff_documents_chain(llm, prompt)

        # Invoke chain
        response = document_chain.invoke({
                    "input": request.question,
                    "context": source_documents
        })

        # -- SOURCES EXTRACTION AND RESULTS RETURN --
        
        # extract unique file IDs from the metadata of the fragments found
        unique_file_ids = set()
        for doc in source_documents:
            if doc.metadata and "file_id" in doc.metadata:
                unique_file_ids.add(doc.metadata["file_id"])

        # buidl response for API Gateway
        return {
            "answer": response['output_text'] if 'output_text' in response else str(response),
            "source_files": list(unique_file_ids)
        }

    except Exception as e:
        print(f"RAG Query Failed: {e}")
        raise HTTPException(status_code=500, detail=f"RAG Query Failed: {e}")
    
@app.get("/collections")
async def list_collections():
    """
    Returns a list of all available collections in ChromaDB.

    :return: List of collection names
    """

    try:
        chroma_client = HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        collections = chroma_client.list_collections()
        
        # names extraction
        names = [c.name for c in collections]
        return {"collections": names, "count": len(names)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list collections: {e}")