import os
import csv
import datetime
from io import StringIO
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from dotenv import load_dotenv
from typing import Optional

import models
from database import engine, SessionLocal

# Cargar variables de entorno
load_dotenv()

# Inicializar tablas en la base de datos
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API Maratón Mijovi S.R.L.")

# Directorio local para guardar los PDFs escaneados de certificados médicos
UPLOAD_DIR = "uploads_certificados"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Configuración SMTP (FastAPI-Mail)
mail_config = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME", "usuario@gmail.com"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD", "password"),
    MAIL_FROM=os.getenv("MAIL_FROM", "no-reply@maratonmijovi.com"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER=os.getenv("MAIL_SERVER", "smtp.gmail.com"),
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- SCHEMAS DE VALIDACIÓN (PYDANTIC) ---

class ValidarQRRequest(BaseModel):
    qr_code: str

class FotoSubidaRequest(BaseModel):
    usuario_nombre: str
    imagen_url: str
    categoria: str = "General"

class CambiarDatosRequest(BaseModel):
    dni: str
    nueva_distancia: Optional[str] = None
    nuevo_talle: Optional[str] = None

class AlbumOficialCreate(BaseModel):
    titulo: str
    subtitulo: Optional[str] = None
    google_photos_url: str
    portada_url: Optional[str] = "https://images.unsplash.com/photo-1530549387789-4c1017266635?auto=format&fit=crop&w=800&q=80"
    fecha_evento: Optional[str] = "2027"

# --- TAREA EN SEGUNDO PLANO: CORREO DE CONFIRMACIÓN ---

async def enviar_correo_confirmacion(email_destino: str, nombre: str, dni: str, distancia: str, qr_code: str, talle: str):
    qr_image_url = f"https://quickchart.io/qr?text={qr_code}&size=200"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
            <div style="background-color: #000000; padding: 20px; text-align: center;">
                <h1 style="color: #F15A24; margin: 0; font-size: 24px;">MARATÓN MIJOVI 2027</h1>
            </div>
            <div style="padding: 30px; text-align: center;">
                <h2 style="color: #333333; margin-top: 0;">¡Inscripción Confirmada! 🎉</h2>
                <p style="color: #666666; font-size: 16px;">Hola <strong>{nombre}</strong>, tu registro se completó con éxito.</p>
                <div style="background-color: #f9f9f9; border-left: 4px solid #F15A24; padding: 15px; text-align: left; margin: 20px 0;">
                    <p style="margin: 5px 0; color: #333;"><strong>DNI:</strong> {dni}</p>
                    <p style="margin: 5px 0; color: #333;"><strong>Distancia:</strong> {distancia}</p>
                    <p style="margin: 5px 0; color: #333;"><strong>Talle de Remera:</strong> {talle}</p>
                    <p style="margin: 5px 0; color: #333;"><strong>Código Pase:</strong> {qr_code}</p>
                </div>
                <p style="color: #333; font-weight: bold;">Tu Código QR de Acreditación:</p>
                <img src="{qr_image_url}" alt="Código QR Acreditación" style="width: 180px; height: 180px; border: 2px solid #ddd; padding: 5px; border-radius: 8px; margin-bottom: 15px;">
            </div>
            <div style="background-color: #f4f4f4; padding: 15px; text-align: center; color: #888888; font-size: 12px;">
                Mijovi S.R.L. © 2027 - Todos los derechos reservados.
            </div>
        </div>
    </body>
    </html>
    """
    message = MessageSchema(
        subject=f"🏁 Inscripción Confirmada - Maratón Mijovi ({distancia})",
        recipients=[email_destino],
        body=html_content,
        subtype=MessageType.html
    )
    fastmail = FastMail(mail_config)
    try:
        await fastmail.send_message(message)
    except Exception as e:
        print(f"Error al enviar correo a {email_destino}: {e}")

# --- ENDPOINTS ---

# 1. Registro de Corredor
@app.post("/api/registro", status_code=status.HTTP_201_CREATED)
async def registrar_corredor(
    background_tasks: BackgroundTasks,
    nombre_completo: str = Form(...),
    dni: str = Form(...),
    email: EmailStr = Form(...),
    genero: str = Form(...),
    fecha_nacimiento: str = Form(...),
    whatsapp: str = Form(...),
    telefono_emergencia: str = Form(...),
    distancia: str = Form(...),
    talle_remera: str = Form(...),
    grupo_sanguineo: Optional[str] = Form(None),
    certificado_pdf: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    if db.query(models.Usuario).filter(models.Usuario.dni == dni).first():
        raise HTTPException(status_code=400, detail="El DNI ya se encuentra registrado.")
    if db.query(models.Usuario).filter(models.Usuario.email == email).first():
        raise HTTPException(status_code=400, detail="El correo electrónico ya se encuentra registrado.")
    
    pdf_path = None
    if certificado_pdf and certificado_pdf.filename:
        file_ext = certificado_pdf.filename.split(".")[-1]
        file_name = f"certificado_{dni}.{file_ext}"
        pdf_path = os.path.join(UPLOAD_DIR, file_name)
        with open(pdf_path, "wb") as buffer:
            buffer.write(await certificado_pdf.read())

    qr_generado = f"MIJOVI-{dni}-{distancia}"
    nuevo_usuario = models.Usuario(
        nombre_completo=nombre_completo,
        dni=dni,
        email=email,
        genero=genero,
        fecha_nacimiento=fecha_nacimiento,
        whatsapp=whatsapp,
        telefono_emergencia=telefono_emergencia,
        grupo_sanguineo=grupo_sanguineo or "No especificado",
        certificado_medico_url=pdf_path,
        distancia=distancia,
        talle_remera=talle_remera,
        qr_code=qr_generado,
        acreditado=False
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)

    background_tasks.add_task(
        enviar_correo_confirmacion,
        email_destino=email,
        nombre=nombre_completo,
        dni=dni,
        distancia=distancia,
        qr_code=qr_generado,
        talle=talle_remera
    )
    return {"mensaje": "Inscripción exitosa.", "qr_code": qr_generado, "id": nuevo_usuario.id}

# 2. Búsqueda de Inscripción por DNI
@app.get("/api/corredor/dni/{dni}")
def buscar_inscripcion(dni: str, db: Session = Depends(get_db)):
    corredor = db.query(models.Usuario).filter(models.Usuario.dni == dni).first()
    if not corredor:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada para este DNI.")
    return corredor

# 3. Cambiar Datos de Inscripción (Distancia o Talle)
@app.put("/api/corredor/cambiar-datos")
def cambiar_datos_corredor(payload: CambiarDatosRequest, db: Session = Depends(get_db)):
    corredor = db.query(models.Usuario).filter(models.Usuario.dni == payload.dni).first()
    if not corredor:
        raise HTTPException(status_code=404, detail="Inscripción no encontrada.")
    if corredor.acreditado:
        raise HTTPException(status_code=400, detail="⚠️ Kit ya entregado. No se pueden modificar los datos.")
    
    if payload.nueva_distancia:
        corredor.distancia = payload.nueva_distancia
        corredor.qr_code = f"MIJOVI-{corredor.dni}-{payload.nueva_distancia}"
    
    if payload.nuevo_talle:
        corredor.talle_remera = payload.nuevo_talle

    db.commit()
    db.refresh(corredor)
    return {"status": "exito", "mensaje": "Datos actualizados correctamente.", "corredor": corredor}

# 4. Descargar Certificado Médico (PDF)
@app.get("/api/admin/descargar-certificado/{dni}")
def descargar_certificado(dni: str, db: Session = Depends(get_db)):
    corredor = db.query(models.Usuario).filter(models.Usuario.dni == dni).first()
    if not corredor or not corredor.certificado_medico_url or not os.path.exists(corredor.certificado_medico_url):
        raise HTTPException(status_code=404, detail="Certificado médico no encontrado para este corredor.")
    return FileResponse(corredor.certificado_medico_url, media_type="application/pdf", filename=f"certificado_{dni}.pdf")

# 5. Acreditación por QR (Staff)
@app.post("/api/admin/acreditar")
def acreditar_corredor(payload: ValidarQRRequest, db: Session = Depends(get_db)):
    corredor = db.query(models.Usuario).filter(models.Usuario.qr_code == payload.qr_code).first()
    if not corredor:
        raise HTTPException(status_code=404, detail="Código QR no válido.")
    if corredor.acreditado:
        raise HTTPException(status_code=400, detail="⚠️ Kit ya entregado previamente.")
    
    corredor.acreditado = True
    corredor.fecha_acreditacion = datetime.datetime.now()
    db.commit()
    return {"status": "exito", "mensaje": "✅ Kit Entregado", "corredor": {"nombre": corredor.nombre_completo, "dni": corredor.dni, "distancia": corredor.distancia, "talle": corredor.talle_remera}}

# 6. Acreditación Manual por DNI (Staff)
@app.post("/api/admin/acreditar-manual/{dni}")
def acreditar_manual(dni: str, db: Session = Depends(get_db)):
    corredor = db.query(models.Usuario).filter(models.Usuario.dni == dni).first()
    if not corredor:
        raise HTTPException(status_code=404, detail="Corredor no encontrado.")
    if corredor.acreditado:
        raise HTTPException(status_code=400, detail="Este kit ya fue entregado.")
    
    corredor.acreditado = True
    corredor.fecha_acreditacion = datetime.datetime.now()
    db.commit()
    return {"mensaje": f"✅ Kit de {corredor.nombre_completo} acreditado manualmente."}

# 7. Listado General de Corredores (Staff)
@app.get("/api/admin/corredores")
def listar_todos_corredores(db: Session = Depends(get_db)):
    return db.query(models.Usuario).all()

# 8. Exportar Padrón a CSV (Staff)
@app.get("/api/admin/exportar-csv")
def exportar_csv_corredores(db: Session = Depends(get_db)):
    corredores = db.query(models.Usuario).all()
    f = StringIO()
    writer = csv.writer(f)
    writer.writerow(["ID", "Nombre Completo", "DNI", "Email", "Género", "F. Nacimiento", "WhatsApp", "Tel. Emergencia", "Grupo Sanguíneo", "Certificado Médico", "Distancia", "Talle Remera", "QR Code", "Acreditado", "Fecha Acreditacion"])
    
    for c in corredores:
        writer.writerow([
            c.id, c.nombre_completo, c.dni, c.email, c.genero, c.fecha_nacimiento,
            c.whatsapp, c.telefono_emergencia, c.grupo_sanguineo, "Adjunto" if c.certificado_medico_url else "No Adjunto",
            c.distancia, c.talle_remera, c.qr_code, 
            "SI" if c.acreditado else "NO", 
            c.fecha_acreditacion.strftime('%Y-%m-%d %H:%M:%S') if c.fecha_acreditacion else ""
        ])
    
    f.seek(0)
    response = StreamingResponse(iter([f.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=corredores_maraton_mijovi.csv"
    return response

# 9. Gestión de Fotos en la Comunidad (Muro)
@app.get("/api/fotos")
def obtener_fotos(categoria: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(models.FotoComunidad)
    if categoria and categoria != "Todos":
        query = query.filter(models.FotoComunidad.categoria == categoria)
    return query.order_by(models.FotoComunidad.fecha_subida.desc()).all()

@app.post("/api/fotos", status_code=status.HTTP_201_CREATED)
def subir_foto(foto: FotoSubidaRequest, db: Session = Depends(get_db)):
    nueva_foto = models.FotoComunidad(
        usuario_nombre=foto.usuario_nombre, 
        imagen_url=foto.imagen_url,
        categoria=foto.categoria
    )
    db.add(nueva_foto)
    db.commit()
    db.refresh(nueva_foto)
    return {"mensaje": "Foto publicada", "id": nueva_foto.id}

@app.delete("/api/fotos/{foto_id}")
def eliminar_foto(foto_id: int, db: Session = Depends(get_db)):
    foto = db.query(models.FotoComunidad).filter(models.FotoComunidad.id == foto_id).first()
    if not foto:
        raise HTTPException(status_code=404, detail="Foto no encontrada")
    db.delete(foto)
    db.commit()
    return {"mensaje": "Foto eliminada con éxito"}

# 10. Listado y Creación de Álbumes Oficiales HD (Google Fotos)
@app.get("/api/albumes-oficiales")
def obtener_albumes_oficiales(db: Session = Depends(get_db)):
    return db.query(models.AlbumOficial).order_by(models.AlbumOficial.id.desc()).all()

@app.post("/api/admin/albumes-oficiales", status_code=status.HTTP_201_CREATED)
def crear_album_oficial(album: AlbumOficialCreate, db: Session = Depends(get_db)):
    nuevo_album = models.AlbumOficial(**album.dict())
    db.add(nuevo_album)
    db.commit()
    db.refresh(nuevo_album)
    return {"mensaje": "Álbum oficial creado con éxito", "id": nuevo_album.id}

# 11. Métricas y Control de Inventario de Remeras (KPIs)
@app.get("/api/kpis")
def obtener_kpis(db: Session = Depends(get_db)):
    total = db.query(models.Usuario).count()
    acreditados = db.query(models.Usuario).filter(models.Usuario.acreditado.is_(True)).count()
    
    talles = ["S", "M", "L", "XL", "XXL"]
    inventario = {}
    for t in talles:
        sol = db.query(models.Usuario).filter(models.Usuario.talle_remera == t).count()
        ent = db.query(models.Usuario).filter(models.Usuario.talle_remera == t, models.Usuario.acreditado.is_(True)).count()
        inventario[t] = {"solicitados": sol, "entregados": ent, "pendientes": sol - ent}

    meta = 1000
    porcentaje_meta = round((total / meta) * 100, 1) if meta > 0 else 0

    return {
        "total_inscriptos": total,
        "total_acreditados": acreditados,
        "pendientes_kit": total - acreditados,
        "porcentaje_meta": porcentaje_meta,
        "control_medallas": {
            "medallas_entregadas": acreditados,
            "medallas_en_stock": max(0, 2000 - acreditados)
        },
        "distribucion": {
            "5K": db.query(models.Usuario).filter(models.Usuario.distancia == "5K").count(),
            "10K": db.query(models.Usuario).filter(models.Usuario.distancia == "10K").count(),
            "21K": db.query(models.Usuario).filter(models.Usuario.distancia == "21K").count()
        },
        "inventario_talles": inventario
    }