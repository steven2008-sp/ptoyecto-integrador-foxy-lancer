"""Manejo amigable de errores: nunca cierra la app y todo queda en mypines.log."""
import logging

from PySide6.QtWidgets import QMessageBox

from . import validation

logger = logging.getLogger("mypines")


def show_error(parent, title, exc):
    """Muestra un error amigable sin exponer detalles internos de la base de datos."""
    logger.exception("%s: %s", title, exc)
    if isinstance(exc, validation.ValidationError):
        QMessageBox.warning(parent, title, str(exc))
        return
    if isinstance(exc, PermissionError):
        QMessageBox.warning(parent, title, "No tenés permiso para realizar esta acción.")
        return
    errno = getattr(exc, "errno", None)
    detail = str(exc)
    if errno == 1146 or "doesn't exist" in detail.lower():
        user_msg = "Falta una tabla de Foxy Lancer. La aplicación intenta crear las tablas al iniciar; volvé a abrirla. Si continúa, ejecutá database/schema.sql en Workbench."
    elif errno == 1045 or "access denied" in detail.lower():
        user_msg = "MySQL rechazó el usuario o la contraseña. Revisá MYSQL_USER y MYSQL_PASSWORD en el archivo .env."
    elif errno == 2003 or "can't connect" in detail.lower():
        user_msg = "No se pudo alcanzar el servidor MySQL. Comprobá que el servicio MySQL80 esté en ejecución."
    elif isinstance(exc, ValueError):
        user_msg = detail
    else:
        user_msg = "Ocurrió un error inesperado. No se borró ningún dato. Revisá mypines.log para más detalles."
    QMessageBox.critical(parent, title, user_msg)


def handle(parent, title, exc):
    """Errores de reglas de negocio -> aviso simple; el resto -> error técnico."""
    if isinstance(exc, (ValueError, PermissionError, validation.ValidationError)):
        QMessageBox.warning(parent, title, str(exc))
    else:
        show_error(parent, title, exc)
