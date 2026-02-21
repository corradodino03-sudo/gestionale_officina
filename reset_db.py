import asyncio
import sys
import os

# Aggiungi backend/ alla PYTHONPATH per importare app.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.core.database import engine
from app.models import Base

async def reset():
    print("Connessione al database, eliminazione tabelle...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("Tabelle eliminate. Creazione nuove tabelle...")
        await conn.run_sync(Base.metadata.create_all)
    print("Database resettato con successo!")

if __name__ == "__main__":
    asyncio.run(reset())
