from sqlalchemy import Column, Integer, String, Boolean, DateTime
import datetime
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String, nullable=False)
    dni = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    genero = Column(String, nullable=False)
    fecha_nacimiento = Column(String, nullable=False)
    whatsapp = Column(String, nullable=False)
    telefono_emergencia = Column(String, nullable=False)
    
    # Datos opcionales
    grupo_sanguineo = Column(String, nullable=True)
    certificado_medico_url = Column(String, nullable=True)
    
    distancia = Column(String, nullable=False)  # 5K, 10K, 21K
    talle_remera = Column(String, nullable=False)  # S, M, L, XL, XXL
    qr_code = Column(String, unique=True, nullable=False)
    
    # Control estricto de acreditación
    acreditado = Column(Boolean, default=False)
    fecha_acreditacion = Column(DateTime, nullable=True)

class FotoComunidad(Base):
    __tablename__ = "fotos_comunidad"

    id = Column(Integer, primary_key=True, index=True)
    usuario_nombre = Column(String, nullable=False)
    imagen_url = Column(String, nullable=False)
    categoria = Column(String, default="General")
    fecha_subida = Column(DateTime, default=datetime.datetime.utcnow)