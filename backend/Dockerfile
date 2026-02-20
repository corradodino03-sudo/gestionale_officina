# ============================================================
# Dockerfile - Backend FastAPI
# Progetto: Garage Manager (Gestionale Officina)
# Python 3.12 slim
# ============================================================

FROM python:3.12-slim-bookworm

# Variabili d'ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Crea directory lavoro
WORKDIR /app

# Copia requirements e installa dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia codice applicazione
COPY . .

# Esposi porta applicazione
EXPOSE 8000

# Comando di avvio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
