"""Modelos ORM con SQLAlchemy para Foxy Lancer.

Capa opcional y aditiva: NO reemplaza mysql.connector ni database.py.
Sirve para operaciones nuevas o migraciones graduales sin romper lo actual.

Requisito adicional: pip install SQLAlchemy PyMySQL
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    Enum, ForeignKey, Boolean, DECIMAL, Index
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

_engine = None
_SessionLocal = None


def init_orm(database_url: Optional[str] = None):
    """Inicializa el engine de SQLAlchemy (una sola vez)."""
    global _engine, _SessionLocal
    if _engine is not None:
        return _SessionLocal

    url = database_url or os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:perez.2008@127.0.0.1:3306/mypines_db?charset=utf8mb4",
    )
    _engine = create_engine(url, pool_pre_ping=True, pool_recycle=3600, pool_size=10, max_overflow=20)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _SessionLocal


def get_session():
    """Devuelve una sesión SQLAlchemy nueva."""
    if _SessionLocal is None:
        init_orm()
    return _SessionLocal()


def close_session(session):
    """Cierra una sesión de forma segura."""
    try:
        session.close()
    except Exception:
        pass


# ======================================================================
# Modelos
# ======================================================================
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    correo = Column(String(190), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    rol = Column(Enum("contratante", "freelancer", "admin", name="rol_enum"), nullable=False, default="freelancer")
    activo = Column(Boolean, default=True, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    trabajos = relationship("Trabajo", back_populates="cliente", cascade="all, delete-orphan")
    solicitudes = relationship("Solicitud", back_populates="cliente_rel", cascade="all, delete-orphan")
    perfiles = relationship("Perfil", back_populates="usuario", uselist=False, cascade="all, delete-orphan")


class Trabajo(Base):
    __tablename__ = "trabajos"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(140), nullable=False)
    categoria = Column(String(50), nullable=False, default="Otro")
    descripcion = Column(Text, nullable=False)
    habilidades = Column(String(500), nullable=False, default="")
    modalidad = Column(Enum("Remoto", "Presencial", "Híbrido", name="modalidad_enum"), default="Remoto")
    presupuesto = Column(DECIMAL(10, 2), default=0.00)
    cliente_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    estado = Column(Enum("Publicado", "Borrador", "Cerrado", name="estado_enum"), default="Publicado")
    urgente = Column(Boolean, default=False, nullable=False)
    ubicacion = Column(String(120), nullable=False, default="")
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cliente = relationship("Usuario", back_populates="trabajos")
    solicitudes = relationship("Solicitud", back_populates="trabajo_rel", cascade="all, delete-orphan")
    citas = relationship("Cita", back_populates="trabajo_rel", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_trabajos_estado_creado", "estado", "creado_en"),
        Index("ix_trabajos_categoria", "categoria"),
    )


class Solicitud(Base):
    __tablename__ = "solicitudes"
    id = Column(Integer, primary_key=True, index=True)
    trabajo_id = Column(Integer, ForeignKey("trabajos.id", ondelete="CASCADE"), nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    mensaje = Column(Text, nullable=False)
    estado = Column(
        Enum(
            'Pendiente', 'Revisada', 'Aceptada', 'Rechazada', 'Entrevista',
            'Contratada', 'En progreso', 'Completada', 'Cancelada', 'Retirada',
            name="estado_solicitud_enum"
        ),
        default="Pendiente",
        nullable=False,
    )
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, nullable=True)

    trabajo_rel = relationship("Trabajo", back_populates="solicitudes")
    cliente_rel = relationship("Usuario", back_populates="solicitudes")
    contratos = relationship("Contrato", back_populates="solicitud_rel", uselist=False, cascade="all, delete-orphan")
    citas = relationship("Cita", back_populates="solicitud_rel", cascade="all, delete-orphan")
    mensajes = relationship("Mensaje", back_populates="solicitud_rel", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_solicitudes_estado", "estado"),
        Index("uq_solicitud_cliente_trabajo", "trabajo_id", "cliente_id", unique=True),
    )


class Cita(Base):
    __tablename__ = "citas"
    id = Column(Integer, primary_key=True, index=True)
    trabajo_id = Column(Integer, ForeignKey("trabajos.id", ondelete="CASCADE"), nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha = Column(DateTime, nullable=False)
    notas = Column(Text, nullable=True)
    estado = Column(
        Enum('Pendiente', 'Aceptada', 'Rechazada', 'Completada', 'Cancelada', name="estado_cita_enum"),
        default="Pendiente",
        nullable=False,
    )
    creado_en = Column(DateTime, default=datetime.utcnow)
    solicitud_id = Column(Integer, ForeignKey("solicitudes.id", ondelete="SET NULL"), nullable=True, index=True)
    propuesta_por = Column(Integer, nullable=True)

    trabajo_rel = relationship("Trabajo", back_populates="citas")
    solicitud_rel = relationship("Solicitud", back_populates="citas")

    __table_args__ = (
        Index("idx_citas_fecha", "fecha"),
        Index("idx_citas_cliente", "cliente_id"),
    )


class PasswordReset(Base):
    __tablename__ = "password_resets"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False)
    expira_en = Column(DateTime, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_password_resets_usuario", "usuario_id"),
        Index("idx_password_resets_expira", "expira_en"),
    )


class Perfil(Base):
    __tablename__ = "perfiles"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True, index=True)
    presentacion = Column(Text, nullable=True)
    habilidades = Column(String(500), nullable=False, default="")
    comentario = Column(String(500), nullable=False, default="")
    foto = Column(String(255), nullable=True)
    ubicacion = Column(String(120), nullable=False, default="")
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="perfiles")


class Resena(Base):
    __tablename__ = "resenas"
    id = Column(Integer, primary_key=True, index=True)
    trabajador_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    autor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    puntuacion = Column(Integer, nullable=False)
    comentario = Column(Text, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)
    puntualidad = Column(Integer, nullable=True)
    calidad = Column(Integer, nullable=True)
    comunicacion = Column(Integer, nullable=True)

    __table_args__ = (
        Index("idx_resenas_trabajador", "trabajador_id"),
        Index("idx_resenas_fecha", "creado_en"),
    )


class Favorito(Base):
    __tablename__ = "favoritos"
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True, index=True)
    trabajo_id = Column(Integer, ForeignKey("trabajos.id", ondelete="CASCADE"), primary_key=True, index=True)
    creado_en = Column(DateTime, default=datetime.utcnow)


class Notificacion(Base):
    __tablename__ = "notificaciones"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    titulo = Column(String(160), nullable=False)
    mensaje = Column(String(500), nullable=False, default="")
    tipo = Column(String(30), nullable=False, default="info")
    leida = Column(Boolean, default=False, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_notif_usuario", "usuario_id", "leida"),
    )


class BusquedaGuardada(Base):
    __tablename__ = "busquedas_guardadas"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    nombre = Column(String(80), nullable=False)
    filtros = Column(Text, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)


class Mensaje(Base):
    __tablename__ = "mensajes"
    id = Column(Integer, primary_key=True, index=True)
    solicitud_id = Column(Integer, ForeignKey("solicitudes.id", ondelete="CASCADE"), nullable=False, index=True)
    emisor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    texto = Column(Text, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    solicitud_rel = relationship("Solicitud", back_populates="mensajes")

    __table_args__ = (
        Index("idx_mensajes_solicitud", "solicitud_id"),
    )


class Contrato(Base):
    __tablename__ = "contratos"
    id = Column(Integer, primary_key=True, index=True)
    solicitud_id = Column(Integer, ForeignKey("solicitudes.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    monto_acordado = Column(DECIMAL(12, 2), default=0.00, nullable=False)
    fecha_entrega = Column(DateTime, nullable=True)
    estado = Column(Enum('Activo', 'Completado', 'Cancelado', name="estado_contrato_enum"), default="Activo", nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    solicitud_rel = relationship("Solicitud", back_populates="contratos")
    hitos = relationship("Hito", back_populates="contrato_rel", cascade="all, delete-orphan")


class Hito(Base):
    __tablename__ = "hitos"
    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id", ondelete="CASCADE"), nullable=False, index=True)
    titulo = Column(String(160), nullable=False)
    descripcion = Column(String(400), nullable=True)
    fecha_limite = Column(DateTime, nullable=True)
    completado = Column(Boolean, default=False, nullable=False)
    completado_en = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    contrato_rel = relationship("Contrato", back_populates="hitos")

    __table_args__ = (
        Index("idx_hitos_contrato", "contrato_id"),
    )


class Reporte(Base):
    __tablename__ = "reportes"
    id = Column(Integer, primary_key=True, index=True)
    autor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(Enum('trabajo', 'usuario', name="tipo_reporte_enum"), nullable=False)
    objetivo_id = Column(Integer, nullable=False)
    motivo = Column(String(120), nullable=False)
    comentario = Column(Text, nullable=True)
    estado = Column(
        Enum('Nuevo', 'En revisión', 'Resuelto', 'Descartado', name="estado_reporte_enum"),
        default="Nuevo",
        nullable=False,
    )
    creado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_reportes_estado", "estado"),
    )


class Bitacora(Base):
    __tablename__ = "bitacora"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    accion = Column(String(60), nullable=False)
    detalle = Column(String(400), nullable=False, default="")
    creado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_bitacora_fecha", "creado_en"),
    )


# ============================================================
# Modelos Foxy Lancer 3.0: Contratante / Freelancer
# ============================================================
class ExperienciaFreelancer(Base):
    __tablename__ = "experiencias_freelancer"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    empresa = Column(String(150), nullable=False)
    cargo = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    fecha_inicio = Column(DateTime, nullable=False)
    fecha_fin = Column(DateTime, nullable=True)
    actual = Column(Boolean, default=False, nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_exp_usuario", "usuario_id"),
    )


class ProyectoFreelancer(Base):
    __tablename__ = "proyectos_freelancer"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    titulo = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    enlace = Column(String(500), nullable=True)
    tecnologias = Column(String(500), nullable=False, default="")
    fecha = Column(DateTime, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_proy_usuario", "usuario_id"),
    )


class Contratacion(Base):
    __tablename__ = "contrataciones"
    id = Column(Integer, primary_key=True, index=True)
    trabajo_id = Column(Integer, ForeignKey("trabajos.id", ondelete="CASCADE"), nullable=False, index=True)
    solicitud_id = Column(Integer, ForeignKey("solicitudes.id", ondelete="CASCADE"), nullable=False, index=True)
    freelancer_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    contratante_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    estado = Column(
        Enum('Pendiente', 'Aceptada', 'Rechazada', 'Completada', name="estado_contratacion_enum"),
        default="Pendiente",
        nullable=False,
    )
    mensaje_rechazo = Column(Text, nullable=True)
    creado_en = Column(DateTime, default=datetime.utcnow)
    actualizado_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_contratacion_trabajo", "trabajo_id"),
        Index("idx_contratacion_freelancer", "freelancer_id"),
    )
