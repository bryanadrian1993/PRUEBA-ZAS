from sqlalchemy import Column, Integer, String, Float
from database import Base

class Chofer(Base):
    __tablename__ = "choferes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    apellido = Column(String)
    placa = Column(String, unique=True)
    latitud = Column(Float)
    longitud = Column(Float)
    estado = Column(String) # LIBRE u OCUPADO
    deuda = Column(Float)
