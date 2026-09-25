from fastapi import FastAPI
from .database import engine, Base
from . import models

# Crea las tablas automáticamente en la base de datos si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API Maratón Mijovi",
    version="2.0.0",
    description="Backend oficial escalable para la gestión de la maratón."
)

@app.get("/")
def read_root():
    return {"message": "¡Servidor de Backend de Maratón Mijovi V2.0 funcionando con éxito!"}