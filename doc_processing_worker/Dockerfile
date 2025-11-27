# We use a more complete Debian-based 
#Python image to install Tesseract.
FROM python:3.11-slim-bullseye

# Installing Tesseract OCR and 
# other tools for document processing
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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Optional
EXPOSE 8002 

# Run RQ Worker
CMD ["python", "run_worker.py"]