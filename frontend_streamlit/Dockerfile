FROM python:3.10-slim

WORKDIR /app

# Instalacja zależności
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie kodu
COPY . .

# Wystawienie portu Streamlit
EXPOSE 8501

# Healthcheck (opcjonalnie, ale dobra praktyka w mikroserwisach)
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Start
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]