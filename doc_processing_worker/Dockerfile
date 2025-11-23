# Używamy pełniejszego obrazu Pythona opartego na Debianie, aby zainstalować Tesseract
FROM python:3.11-slim-bullseye

# 1. Instalacja Tesseract OCR i innych narzędzi
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-pol \
    libtesseract-dev \
    libjpeg-dev \
    zlib1g-dev \
    poppler-utils \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED 1

WORKDIR /app

# 2. Kopiowanie i instalacja zależności Pythonowych
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Kopiowanie kodu aplikacji (run_worker.py i worker_logic.py)
COPY . .

# Wystawienie portu Uvicorn (opcjonalne, ale dobra praktyka w mikrousługach)
EXPOSE 8002 

# 4. Główna komenda: Uruchomienie Workera RQ
# To jest kluczowe: kontener musi uruchomić konsumenta kolejki
CMD ["python", "run_worker.py"]