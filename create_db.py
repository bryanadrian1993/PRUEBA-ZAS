from database import engine, Base
import models

# Este comando crea físicamente las tablas en zastaxi.db
print("Creando base de datos profesional para ZasTaxi...")
Base.metadata.create_all(bind=engine)
print("¡Éxito! La base de datos está lista para operar.")
