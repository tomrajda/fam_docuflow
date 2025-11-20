# Używamy tego samego stabilnego obrazu co Worker, aby zapewnić spójność wersji Python i bibliotek systemowych.
FROM python:3.11-slim-bullseye 

# Ustawienie zmiennej środowiskowej
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# 1. Instalacja systemowych bibliotek dla Pythona (np. do kompilacji niektórych zależności)
# Ponieważ używamy pysqlite3-binary, minimalizujemy tu potrzebne pakiety, ale warto mieć podstawy.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 2. Kopiowanie pliku zależności i instalacja
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Kopiowanie kodu aplikacji
COPY . .

# Wystawienie portu, na którym działa Uvicorn
EXPOSE 8002

# 4. Uruchomienie serwisu przez Uvicorn
# app:app oznacza, że uruchamiamy aplikację 'app' z pliku 'app.py'
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]