FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app

# Pre-download GLiNER model to prevent cold-start delays
RUN python -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_multi-v2.1')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
