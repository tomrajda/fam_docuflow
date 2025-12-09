import streamlit as st
import requests
import os

st.set_page_config(page_title="DocuFlow Chat", layout="wide")

# 1. Konfiguracja URL
# Wewnątrz sieci Docker Twoje API Gateway jest dostępne pod nazwą serwisu i portem wewnętrznym
GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://docuflow_api_gateway:8001")

# ZMIANA 1: Endpoint to /query, a nie /chat (zgodnie z Twoim kodem FastAPI)
CHAT_ENDPOINT = f"{GATEWAY_URL}/query"

st.title("📄 DocuFlow Q&A")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Zadaj pytanie do dokumentów..."):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Szukam odpowiedzi w dokumentach..."):
            try:
                # ZMIANA 2: Dostosowanie payloadu do modelu QueryRequest w FastAPI
                # class QueryRequest(BaseModel):
                #     question: str  <--- To jest wymagane pole
                #     categories_to_search: list[str] | None = None
                
                payload = {
                    "question": prompt,
                    "categories_to_search": None # Możesz tu dodać logikę wyboru kategorii w UI
                }
                
                response = requests.post(CHAT_ENDPOINT, json=payload, timeout=60)
                
                if response.status_code == 200:
                    # Zakładam, że LLM Core zwraca JSON, np. {"answer": "Tekst"} 
                    # lub API Gateway przekazuje odpowiedź 1:1.
                    # Sprawdź co dokładnie zwraca Twój LLM Core.
                    data = response.json()
                    
                    # Spróbuj pobrać odpowiedź z różnych typowych kluczy
                    ai_text = data.get("answer") or data.get("response") or data.get("result") or str(data)
                    
                    st.markdown(ai_text)
                    st.session_state.messages.append({"role": "assistant", "content": ai_text})
                else:
                    st.error(f"Błąd API ({response.status_code}): {response.text}")
            
            except requests.exceptions.ConnectionError:
                st.error(f"Nie można połączyć się z: {CHAT_ENDPOINT}. Sprawdź czy API Gateway działa.")
            except Exception as e:
                st.error(f"Wystąpił błąd: {e}")