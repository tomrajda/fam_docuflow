# Dockerfile w api_gateway
FROM python:3.11-slim

# Ustawienie zmiennej środowiskowej
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Kopiowanie i instalacja zależności
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie kodu aplikacji
COPY . .

# Wystawienie portu Uvicorn
EXPOSE 8001

# Uruchomienie serwera FastAPI
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]