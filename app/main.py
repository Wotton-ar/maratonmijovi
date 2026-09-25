from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
import shutil
import os
import uuid

from .database import engine, Base, get_db
from . import models

# Crea las tablas automáticamente en la base de datos si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API Maratón Mijovi",
    version="2.0.0",
    description="Backend oficial escalable para la gestión de la maratón."
)

# Configuración de CORS para permitir peticiones desde la App Móvil y Web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "app/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "¡Servidor de Backend de Maratón Mijovi V2.0 funcionando con éxito!"}

@app.get("/api/kpis")
def get_kpis(db: Session = Depends(get_db)):
    total_inscriptos = db.query(models.Runner).count()
    total_acreditados = db.query(models.Registration).filter(models.Registration.payment_status == "paid").count()
    
    distancias = {"5K": 0, "10K": 0, "21K": 0}
    
    return {
        "total_inscriptos": total_inscriptos,
        "total_acreditados": total_acreditados,
        "pendientes_kit": max(0, total_inscriptos - total_acreditados),
        "control_medallas": {
            "medallas_entregadas": total_acreditados,
            "medallas_en_stock": max(0, 2000 - total_acreditados)
        },
        "distribucion": distancias,
        "inventario_talles": {"S": 300, "M": 600, "L": 600, "XL": 400, "XXL": 100}
    }

@app.get("/api/admin/corredores")
def get_admin_corredores(db: Session = Depends(get_db)):
    runners = db.query(models.Runner).all()
    resultado = []
    for r in runners:
        reg = db.query(models.Registration).filter(models.Registration.runner_id == r.id).first()
        resultado.append({
            "id": r.id,
            "nombre_completo": f"{r.first_name} {r.last_name}",
            "dni": r.dni,
            "whatsapp": r.phone or "",
            "distancia": "10K",
            "talle_remera": "L",
            "acreditado": reg.payment_status == "paid" if reg else False,
            "qr_code": f"QR-{r.dni}"
        })
    return resultado

@app.get("/api/corredor/dni/{dni}")
def get_corredor_by_dni(dni: str, db: Session = Depends(get_db)):
    runner = db.query(models.Runner).filter(models.Runner.dni == dni).first()
    if not runner:
        raise HTTPException(status_code=404, detail="No existe ninguna inscripción registrada con este DNI.")
    
    reg = db.query(models.Registration).filter(models.Registration.runner_id == runner.id).first()
    
    return {
        "id": runner.id,
        "nombre_completo": f"{runner.first_name} {runner.last_name}",
        "dni": runner.dni,
        "whatsapp": runner.phone or "",
        "grupo_sanguineo": "NO ESPECIFICADO",
        "telefono_emergencia": runner.emergency_contact or "",
        "distancia": "10K",
        "talle_remera": "L",
        "qr_code": f"QR-{runner.dni}",
        "acreditado": reg.payment_status == "paid" if reg else False,
        "certificado_medico_url": True,
        "tiempo_oficial": "00:48:30"
    }

@app.post("/api/registro", status_code=status.HTTP_201_CREATED)
async def registrar_corredor(
    nombre_completo: str = Form(...),
    dni: str = Form(...),
    email: str = Form(...),
    genero: str = Form(...),
    fecha_nacimiento: str = Form(...),
    whatsapp: str = Form(...),
    telefono_emergencia: str = Form(...),
    grupo_sanguineo: str = Form("NO ESPECIFICADO"),
    distancia: str = Form(...),
    talle_remera: str = Form(...),
    certificado_pdf: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    existing = db.query(models.Runner).filter(models.Runner.dni == dni).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un corredor inscripto con este DNI.")
    
    partes = nombre_completo.split(" ", 1)
    first_name = partes[0]
    last_name = partes[1] if len(partes) > 1 else ""

    new_runner = models.Runner(
        first_name=first_name,
        last_name=last_name,
        dni=dni,
        gender=genero,
        phone=whatsapp,
        emergency_contact=telefono_emergencia
    )
    db.add(new_runner)
    db.commit()
    db.refresh(new_runner)

    new_reg = models.Registration(
        runner_id=new_runner.id,
        race_id=1,
        category_id=1,
        payment_status="pending"
    )
    db.add(new_reg)
    db.commit()

    return {"mensaje": "Inscripción exitosa", "qr_code": f"QR-{dni}"}

@app.post("/api/admin/acreditar/{qr_code}")
def acreditar_por_qr(qr_code: str, db: Session = Depends(get_db)):
    dni = qr_code.replace("QR-", "")
    runner = db.query(models.Runner).filter(models.Runner.dni == dni).first()
    if not runner:
        raise HTTPException(status_code=404, detail="Código QR / Atleta no encontrado.")
    
    reg = db.query(models.Registration).filter(models.Registration.runner_id == runner.id).first()
    if reg:
        reg.payment_status = "paid"
        db.commit()
        
    return {
        "nombre_completo": f"{runner.first_name} {runner.last_name}",
        "distancia": "10K"
    }

@app.post("/api/admin/acreditar-manual/{dni}")
def acreditar_manual(dni: str, db: Session = Depends(get_db)):
    runner = db.query(models.Runner).filter(models.Runner.dni == dni).first()
    if not runner:
        raise HTTPException(status_code=404, detail="Atleta no encontrado.")
    reg = db.query(models.Registration).filter(models.Registration.runner_id == runner.id).first()
    if reg:
        reg.payment_status = "paid"
        db.commit()
    return {"mensaje": f"Atleta {runner.first_name} acreditado correctamente."}

@app.get("/api/albumes-oficiales")
def get_albumes():
    return [
        {
            "id": 1,
            "titulo": "Álbum Oficial - Maratón Mijovi",
            "subtitulo": "Galería oficial de fotos del evento en Google Fotos",
            "fecha_evento": "Abril 2027",
            "portada_url": "",  # Sin imágenes externas de relleno
            "google_photos_url": "https://photos.google.com/share/AF1QipOobX7UJw1vuPIw4p936Me9Kr6cB0PLaVr-PEOFCOmtqHSfk2J5Yfng6RXfbQ5thg?pli=1&key=NVF5cTBLTjdnejg5VVZkYmUwOVNjNG1sOU95eElR"
        }
    ]

@app.get("/api/fotos")
def get_fotos():
    return []

@app.post("/api/fotos")
def post_foto():
    return {"mensaje": "Foto publicada con éxito"}