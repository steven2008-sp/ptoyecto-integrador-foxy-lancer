"""Validaciones y sanitización centralizadas para Foxy Lancer.

Capa de defensa en profundidad: valida entradas antes de que lleguen a la base de datos
y sanitiza salidas para evitar fuga de información interna. No modifica ningún archivo
existente; solo se importa y se usa.
"""
from __future__ import annotations

import html
import re
from typing import Optional


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------
class ValidationError(ValueError):
    """Se lanza cuando un campo no pasa la validación."""


# ---------------------------------------------------------------------------
# Sanitización de salida (evita fuga de información interna)
# ---------------------------------------------------------------------------
def safe_error_message(exc: Exception, default: str = "Ocurrió un error inesperado.") -> str:
    """Devuelve un mensaje de error seguro para mostrar al usuario.

    Nunca devuelve trazas, nombres de tablas, usuarios de BD, ni errno de MySQL.
    """
    return default


# ---------------------------------------------------------------------------
# Expresiones regulares
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SKILL_RE = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñ0-9 ,#+./\-]{1,80}$")
SAFE_TEXT_RE = re.compile(r"^[\w\sÁÉÍÓÚáéíóúÑñ,.()\-:;¿?¡!\"'@#$%&*/+=\[\]{}|]{0,4000}$")
NUMERIC_RE = re.compile(r"^\d+(\.\d{1,2})?$")


# ---------------------------------------------------------------------------
# Validadores de campos
# ---------------------------------------------------------------------------
def validar_email(valor: str, campo: str = "correo") -> str:
    valor = (valor or "").strip().lower()
    if not valor:
        raise ValidationError(f"{campo} es obligatorio.")
    if not EMAIL_RE.match(valor):
        raise ValidationError(f"{campo} no tiene un formato válido.")
    if len(valor) > 190:
        raise ValidationError(f"{campo} es demasiado largo (máximo 190 caracteres).")
    return valor


def validar_texto_obligatorio(valor: str, campo: str, min_len: int = 1, max_len: int = 500) -> str:
    valor = (valor or "").strip()
    if not valor:
        raise ValidationError(f"{campo} es obligatorio.")
    if len(valor) < min_len:
        raise ValidationError(f"{campo} debe tener al menos {min_len} carácter(es).")
    if len(valor) > max_len:
        raise ValidationError(f"{campo} excede los {max_len} caracteres permitidos.")
    return valor


def validar_titulo(valor: str) -> str:
    return validar_texto_obligatorio(valor, "Título", min_len=5, max_len=140)


def validar_descripcion(valor: str) -> str:
    return validar_texto_obligatorio(valor, "Descripción", min_len=10, max_len=4000)


def validar_habilidades(valor: str) -> str:
    valor = (valor or "").strip()
    if len(valor) > 500:
        raise ValidationError("Habilidades excede los 500 caracteres permitidos.")
    for parte in [p.strip() for p in valor.split(",") if p.strip()]:
        if not SKILL_RE.match(parte):
            raise ValidationError(f"Habilidad no válida: '{parte}'. Usá solo letras, números y símbolos básicos.")
    return valor


def validar_presupuesto(valor) -> float:
    try:
        monto = float(valor)
    except (TypeError, ValueError):
        raise ValidationError("Presupuesto no es un número válido.")
    if monto < 0:
        raise ValidationError("El presupuesto no puede ser negativo.")
    if monto > 99_999_999.99:
        raise ValidationError("El presupuesto es demasiado alto.")
    return round(monto, 2)


def validar_monto_acordado(valor) -> float:
    return validar_presupuesto(valor)


def validar_mensaje(valor: str, campo: str = "mensaje", min_len: int = 1, max_len: int = 2000) -> str:
    valor = (valor or "").strip()
    if not valor:
        raise ValidationError(f"{campo} es obligatorio.")
    if len(valor) < min_len:
        raise ValidationError(f"{campo} debe tener al menos {min_len} carácter(es).")
    if len(valor) > max_len:
        raise ValidationError(f"{campo} excede los {max_len} caracteres permitidos.")
    return valor


def validar_ubicacion(valor: str) -> str:
    valor = (valor or "").strip()
    if len(valor) > 120:
        raise ValidationError("Ubicación excede los 120 caracteres permitidos.")
    return valor


def validar_notas(valor: str) -> str:
    valor = (valor or "").strip()
    if len(valor) > 1000:
        raise ValidationError("Las notas exceden los 1000 caracteres permitidos.")
    return valor


def validar_comentario_resena(valor: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        raise ValidationError("El comentario es obligatorio.")
    if len(valor) < 5:
        raise ValidationError("El comentario debe tener al menos 5 caracteres.")
    if len(valor) > 1000:
        raise ValidationError("El comentario excede los 1000 caracteres permitidos.")
    return valor


def validar_password(valor: str, campo: str = "contraseña") -> str:
    valor = valor or ""
    if len(valor) < 8:
        raise ValidationError(f"{campo} debe tener al menos 8 caracteres.")
    if len(valor) > 128:
        raise ValidationError(f"{campo} es demasiado larga (máximo 128 caracteres).")
    return valor


def validar_password_fuerte(valor: str, campo: str = "contraseña") -> str:
    """Exige al menos 8 caracteres, una mayúscula, una minúscula y un número."""
    valor = validar_password(valor, campo)
    if not re.search(r"[A-Z]", valor):
        raise ValidationError(f"{campo} debe contener al menos una letra mayúscula.")
    if not re.search(r"[a-z]", valor):
        raise ValidationError(f"{campo} debe contener al menos una letra minúscula.")
    if not re.search(r"\d", valor):
        raise ValidationError(f"{campo} debe contener al menos un número.")
    return valor


def validar_nombre(valor: str) -> str:
    return validar_texto_obligatorio(valor, "Nombre", min_len=2, max_len=100)


def validar_rol(valor: str) -> str:
    valor = (valor or "").strip().lower()
    if valor not in ("contratante", "freelancer", "admin"):
        raise ValidationError("Rol no válido. Debe ser 'contratante', 'freelancer' o 'admin'.")
    return valor


def validar_enlace_proyecto(valor: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        raise ValidationError("El enlace es obligatorio.")
    if len(valor) > 500:
        raise ValidationError("El enlace es demasiado largo (máximo 500 caracteres).")
    if not valor.startswith(("http://", "https://")):
        raise ValidationError("El enlace debe comenzar con http:// o https://.")
    return valor


def validar_fecha(valor, campo: str = "fecha") -> str:
    from datetime import date
    if isinstance(valor, date):
        return valor.isoformat()
    try:
        date.fromisoformat(str(valor))
    except (ValueError, TypeError):
        raise ValidationError(f"{campo} no tiene una fecha válida (YYYY-MM-DD).")
    return str(valor)


def validar_tecnologias(valor: str) -> str:
    return validar_habilidades(valor)


def validar_fecha_limite(valor, urgente: bool = False, campo: str = "fecha límite"):
    """Valida que la fecha límite no sea anterior a hoy.
    Si urgente=True, es obligatoria y debe ser >= hoy."""
    from datetime import date
    if valor is None:
        if urgente:
            raise ValidationError(f"{campo} es obligatoria para trabajos urgentes.")
        return None
    try:
        if isinstance(valor, date):
            fecha = valor
        else:
            fecha = date.fromisoformat(str(valor))
    except (ValueError, TypeError):
        raise ValidationError(f"{campo} no tiene un formato válido (YYYY-MM-DD).")
    hoy = date.today()
    if fecha < hoy:
        raise ValidationError(f"{campo} no puede ser anterior a hoy ({hoy.strftime('%d/%m/%Y')}).")
    return fecha


def validar_estado_trabajo(valor: str) -> str:
    valor = (valor or "").strip()
    if valor not in ("Publicado", "Borrador", "Cerrado"):
        raise ValidationError("Estado de trabajo no válido.")
    return valor


def validar_modalidad(valor: str) -> str:
    valor = (valor or "").strip()
    if valor not in ("Remoto", "Presencial", "Híbrido"):
        raise ValidationError("Modalidad no válida.")
    return valor


def validar_categoria(valor: str, categorias_permitidas=None) -> str:
    valor = (valor or "").strip()
    if categorias_permitidas is None:
        from . import logic
        categorias_permitidas = logic.CATEGORIES
    if valor not in categorias_permitidas:
        raise ValidationError("Categoría no válida.")
    return valor


def validar_estado_solicitud(valor: str) -> str:
    valor = (valor or "").strip()
    permitidos = ("Pendiente", "Revisada", "Aceptada", "Rechazada", "Entrevista",
                  "Contratada", "En progreso", "Completada", "Cancelada", "Retirada")
    if valor not in permitidos:
        raise ValidationError("Estado de solicitud no válido.")
    return valor


def validar_estado_entrevista(valor: str) -> str:
    valor = (valor or "").strip()
    permitidos = ("Pendiente", "Aceptada", "Rechazada", "Completada", "Cancelada")
    if valor not in permitidos:
        raise ValidationError("Estado de entrevista no válido.")
    return valor


def validar_estado_contrato(valor: str) -> str:
    valor = (valor or "").strip()
    permitidos = ("Activo", "Completado", "Cancelado")
    if valor not in permitidos:
        raise ValidationError("Estado de contrato no válido.")
    return valor


def validar_puntuacion(valor) -> int:
    try:
        puntuacion = int(valor)
    except (TypeError, ValueError):
        raise ValidationError("La puntuación debe ser un número entero.")
    if puntuacion < 1 or puntuacion > 5:
        raise ValidationError("La puntuación debe estar entre 1 y 5.")
    return puntuacion


def validar_id_entero(valor, campo: str = "ID") -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ValidationError(f"{campo} debe ser un número entero válido.")


def escape_html(texto: Optional[str]) -> str:
    """Escapa HTML para evitar XSS en etiquetas QLabel con rich text."""
    if texto is None:
        return ""
    return html.escape(str(texto))


def sanitizar_texto_seguro(texto: str, max_len: int = 4000) -> str:
    """Sanitiza texto permitiendo solo caracteres seguros."""
    texto = (texto or "").strip()
    if len(texto) > max_len:
        raise ValidationError(f"El texto excede los {max_len} caracteres permitidos.")
    if not SAFE_TEXT_RE.match(texto):
        raise ValidationError("El texto contiene caracteres no permitidos.")
    return texto
