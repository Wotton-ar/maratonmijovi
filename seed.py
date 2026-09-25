import sys
import os

# Asegura que el backend reconozca la raíz de los archivos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Backend.app.database import SessionLocal, engine
import Backend.app.models as models

# Recrea las tablas en la base de datos si no existen
models.Base.metadata.create_all(bind=engine)

def sembrar_base_de_datos():
    db = SessionLocal()
    try:
        print("🌱 Iniciando siembra de datos...")

        # 1. Cargar Álbum Oficial de Google Fotos (Estadio Único)
        album_existente = db.query(models.AlbumOficial).filter_by(
            titulo="21K MIKOVI [CARRERA | P1 - ESTADIO ÚNICO]"
        ).first()

        if not album_existente:
            album_estadio = models.AlbumOficial(
                titulo="21K MIKOVI [CARRERA | P1 - ESTADIO ÚNICO]",
                subtitulo="Galería fotográfica oficial de la organización",
                google_photos_url="https://photos.google.com/share/AF1QipM6gguZYyX756ZA3xOAz6TuDdp5NR_AMFRT2Amza6CRx9T4zryY7ePwBwHrCc63jg?key=V3lfZ1JNRlM2Q2doY2VDQUZEYmtzVzZxTHFQUU5B",
                portada_url="https://images.unsplash.com/photo-1530549387789-4c1017266635?auto=format&fit=crop&w=800&q=80",
                fecha_evento="26 ABRIL"
            )
            db.add(album_estadio)
            print("✅ Álbum Oficial de Google Fotos guardado correctamente.")
        else:
            print("ℹ️ El Álbum Oficial ya existía en la base de datos.")

        # 2. Cargar Fotos de Muestra para el Muro Comunitario
        if db.query(models.FotoComunidad).count() == 0:
            f1 = models.FotoComunidad(
                usuario_nombre="Carlos Mendoza",
                imagen_url="https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?auto=format&fit=crop&w=800&q=80",
                categoria="Carrera 🏁"
            )
            f2 = models.FotoComunidad(
                usuario_nombre="Sofía López",
                imagen_url="https://images.unsplash.com/photo-1516214104703-d870798883c5?auto=format&fit=crop&w=800&q=80",
                categoria="Medallas 🏅"
            )
            db.add_all([f1, f2])
            print("✅ Fotos de muestra para el Muro Comunitario cargadas.")
        else:
            print("ℹ️ El Muro Comunitario ya cuenta con publicaciones.")

        db.commit()
        print("🚀 Base de datos poblada exitosamente.")

    except Exception as error:
        db.rollback()
        print(f"❌ Error al poblar la base de datos: {error}")
    finally:
        db.close()

if __name__ == "__main__":
    sembrar_base_de_datos()