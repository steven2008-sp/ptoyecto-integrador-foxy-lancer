"""Manejo amigable de errores: nunca cierra la app y todo queda en mypines.log."""
import logging

from PySide6.QtWidgets import QMessageBox

logger = logging.getLogger("mypines")


def show_error(parent, title, exc):
    """Muestra un error con pistas útiles (mismos mensajes que la versión original)."""
    logger.exception("%s: %s", title, exc)
    detail = str(exc)
    if getattr(exc, "errno", None) == 1146 or "doesn't exist" in detail.lower():
        hint = "\n\nFalta una tabla de Foxy Lancer. La aplicación intenta crear las tablas al iniciar; volvé a abrirla. Si continúa, ejecutá database/schema.sql en Workbench."
    elif getattr(exc, "errno", None) == 1045 or "access denied" in detail.lower():
        hint = "\n\nMySQL rechazó el usuario o la contraseña. Revisá MYSQL_USER y MYSQL_PASSWORD en el archivo .env."
    elif getattr(exc, "errno", None) == 2003 or "can't connect" in detail.lower():
        hint = "\n\nNo se pudo alcanzar el servidor MySQL. Comprobá que el servicio MySQL80 esté en ejecución."
    else:
        hint = "\n\nRevisá el detalle del error. No se borraron tus datos."
    QMessageBox.critical(parent, title, detail + hint)


def handle(parent, title, exc):
    """Errores de reglas de negocio -> aviso simple; el resto -> error técnico."""
    if isinstance(exc, (ValueError, PermissionError)):
        QMessageBox.warning(parent, title, str(exc))
    else:
        show_error(parent, title, exc)
