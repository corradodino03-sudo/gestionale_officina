# ============================================================
# Dockerfile - Backend FastAPI
# Progetto: Garage Manager (Gestionale Officina)
# Python 3.12 slim con multi-stage build
# ============================================================

# ------------------------------------------------------------
# STAGE 1: Builder
# ------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

# Variabili d'ambiente per build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Installa dipendenze di sistema per compilazione
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Crea utente non-root per sicurezza
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Crea directory lavoro
WORKDIR /app

# Copia solo requirements per caching layer Docker
COPY requirements.txt .

# Installa dipendenze Python nell'ambiente virtuale
RUN pip install --root-user-action=ignore --no-user -r requirements.txt


# ------------------------------------------------------------
# STAGE 2: Runtime
# ------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Variabili d'ambiente runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/venv/bin:$PATH"

# Installa dipendenze runtime minime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Crea utente non-root (stesso UID/GID del builder)
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Copia ambiente virtuale dal builder
COPY --from=builder /venv /venv

# Crea directory per l'applicazione
RUN mkdir -p /app && chown -R appuser:appgroup /app

# Imposta ownership
WORKDIR /app

# Copia codice applicazione
COPY --chown=appuser:appgroup . .

# Switcha a utente non-root (sicurezza)
USER appuser

# Esposi porta applicazione
EXPOSE 8000

# Comando di avvio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
