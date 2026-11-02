import sys
import os
import json
import urllib.request
import urllib.error
import smtplib
import secrets
import hashlib
from email.message import EmailMessage
from datetime import datetime, timedelta
from PySide6.QtCore import QThread, Signal, QTime
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QMessageBox, QComboBox, QTextEdit, QDialog, QFormLayout, QDoubleSpinBox, QInputDialog,
    QStackedWidget, QTabWidget, QCheckBox, QDialogButtonBox, QCalendarWidget, QTimeEdit,
    QSplitter, QSizePolicy
)
from mysql.connector import Error
from database import get_connection, check_connection, ensure_schema
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass
from security import hash_password, verify_password
import logging
from app import services
from app.shell import MainWindow

BLUE = "#0878ed"
STYLE = """
QMainWindow, QWidget#root, QDialog { background:#f3f6fb; color:#172b4d; font-family:"Segoe UI"; font-size:10pt; }
QWidget { color:#172b4d; }
QFrame#topbar { background:#ffffff; border-bottom:1px solid #d9e2ef; }
QFrame#sidebar { background:#10233f; border:none; }
QFrame#hero { background:#e5efff; border:1px solid #c7d9f5; border-radius:18px; }
QFrame#card { background:#ffffff; border:1px solid #dbe4f0; border-radius:14px; }
QFrame#authPanel { background:#ffffff; border:0; }
QFrame#authHero { background:#155bd5; border:0; }
QLabel { color:#172b4d; background:transparent; }
QLabel#white { color:#ffffff; }
QLabel#heroTitle { color:#102a50; font-size:20px; font-weight:700; background:transparent; }
QLabel#heroDesc { color:#385475; font-size:11pt; background:transparent; }
QLabel#muted { color:#536780; }
QLabel#chip { background:#e3efff; color:#124da8; border-radius:8px; padding:5px 8px; }
QLineEdit, QComboBox, QTextEdit, QDoubleSpinBox, QTimeEdit { background:#ffffff; border:1px solid #b8c8dc; border-radius:9px; padding:9px; color:#172b4d; selection-background-color:#155bd5; selection-color:#ffffff; }
QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QDoubleSpinBox:focus, QTimeEdit:focus { border:2px solid #155bd5; }
QLineEdit::placeholder { color:#65758b; }
QComboBox QAbstractItemView { background:#ffffff; color:#172b4d; selection-background-color:#dceafb; selection-color:#10233f; }
QCalendarWidget { background:#ffffff; color:#172b4d; }
QCalendarWidget QWidget { alternate-background-color:#edf4ff; color:#172b4d; }
QCalendarWidget QToolButton { color:#ffffff; background:#155bd5; border-radius:6px; padding:7px; min-width:38px; min-height:28px; }
QCalendarWidget QToolButton:hover { background:#104bb2; }
QCalendarWidget QSpinBox { color:#172b4d; background:#ffffff; }
QCalendarWidget QAbstractItemView { color:#172b4d; background:#ffffff; selection-background-color:#155bd5; selection-color:#ffffff; font-size:11pt; }
QCalendarWidget QAbstractItemView:enabled { color:#172b4d; background:#ffffff; }
QTimeEdit::up-button, QTimeEdit::down-button { background:#e4edfa; border:1px solid #cbd9ec; width:20px; }
QPushButton { background:#155bd5; color:#ffffff; border:none; border-radius:9px; padding:10px 14px; font-weight:600; }
QPushButton:hover { background:#104bb2; }
QPushButton:disabled { background:#aabbd2; color:#f7f9fc; }
QPushButton#secondary { background:#e4edfa; color:#123e78; border:1px solid #d0def0; }
QPushButton#secondary:hover { background:#d3e3f8; }
QPushButton#nav { text-align:left; background:transparent; color:#edf4ff; padding:12px; border-radius:8px; }
QPushButton#nav:hover { background:#214c7e; color:#ffffff; }
QScrollArea { border:none; background:transparent; }
QTabWidget::pane { border:1px solid #dbe4f0; border-radius:10px; background:#ffffff; }
QTabBar::tab { background:#e5edf8; color:#29415f; padding:10px 18px; margin-right:4px; border-radius:7px; }
QTabBar::tab:selected { background:#155bd5; color:#ffffff; }
QCheckBox { color:#243b58; spacing:7px; }
QMessageBox { background:#ffffff; color:#172b4d; }
QMessageBox QLabel { color:#172b4d; min-width:280px; }
QDialog QLabel { color:#172b4d; }
QDialog QLabel#muted { color:#536780; }
QMessageBox QPushButton { min-width:88px; }
"""

CATEGORIES = ["Frontend", "Backend", "Full Stack", "Aplicaciones móviles", "Bases de datos", "DevOps", "Diseño", "Marketing digital", "Contenido y redacción", "Soporte técnico", "Análisis de datos", "QA y pruebas", "Ciberseguridad", "Automatización", "Otro"]

def message_error(parent, title, exc):
    detail = str(exc)
    if getattr(exc, "errno", None) == 1146 or "doesn't exist" in detail.lower():
        hint = "\n\nFalta una tabla de Foxy Lancer. La aplicación intentará crear las tablas auxiliares al iniciar; vuelve a abrirla. Si continúa, ejecuta database/schema.sql en Workbench."
    elif getattr(exc, "errno", None) == 1045 or "access denied" in detail.lower():
        hint = "\n\nMySQL rechazó el usuario o la contraseña. Revisa MYSQL_USER y MYSQL_PASSWORD en el archivo .env de la carpeta Foxy Lancer."
    elif getattr(exc, "errno", None) == 2003 or "can't connect" in detail.lower():
        hint = "\n\nNo se pudo alcanzar el servidor MySQL. Comprueba que el servicio MySQL80 esté en ejecución."
    else:
        hint = "\n\nRevisa el detalle del error. No se han borrado tus datos."
    QMessageBox.critical(parent, title, detail + hint)

class AuthWindow(QWidget):
    def __init__(self, on_login):
        super().__init__()
        self.on_login = on_login
        self.setObjectName("root")
        self.setWindowTitle("Foxy Lancer | Iniciar sesión")
        self.resize(1120, 720)
        self.setMinimumSize(900, 620)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(0)
        panel = QFrame(); panel.setObjectName("authPanel")
        panel.setStyleSheet("QFrame#authPanel{background:white;border-top-left-radius:20px;border-bottom-left-radius:20px;}")
        form = QVBoxLayout(panel); form.setContentsMargins(48, 32, 48, 28); form.setSpacing(13)
        logo_row = QHBoxLayout()
        logo = QLabel(); pix = QPixmap(os.path.join(os.path.dirname(__file__), "assets", "mypines_fox.png"))
        if not pix.isNull(): logo.setPixmap(pix.scaled(66,66,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        brand = QLabel("Foxy Lancer"); brand.setStyleSheet("font-size:29px;font-weight:700;color:#155bd5;")
        logo_row.addWidget(logo); logo_row.addWidget(brand); logo_row.addStretch(); form.addLayout(logo_row)
        heading = QLabel("Iniciá sesión"); heading.setStyleSheet("font-size:35px;font-weight:700;color:#101828;")
        form.addWidget(heading)
        subtitle = QLabel("¡Qué bueno tenerte de vuelta!"); subtitle.setObjectName("muted"); subtitle.setStyleSheet("font-size:17px;color:#667085;")
        form.addWidget(subtitle); form.addSpacing(10)
        self.tabs = QTabWidget()
        login_tab = QWidget(); lf = QVBoxLayout(login_tab); lf.setContentsMargins(0,8,0,0); lf.setSpacing(12)
        self.login_email = QLineEdit(); self.login_email.setPlaceholderText("Correo electrónico"); self.login_email.setMinimumHeight(48)
        self.login_password = QLineEdit(); self.login_password.setPlaceholderText("Contraseña"); self.login_password.setEchoMode(QLineEdit.EchoMode.Password); self.login_password.setMinimumHeight(48)
        self.show_password = QCheckBox("Mostrar contraseña")
        self.show_password.toggled.connect(lambda checked: self.login_password.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password))
        lf.addWidget(self.login_email); lf.addWidget(self.login_password)
        row = QHBoxLayout(); row.addWidget(self.show_password); row.addStretch()
        forgot = QPushButton("¿Olvidaste tu contraseña?"); forgot.setObjectName("secondary"); forgot.clicked.connect(self.forgot_password); row.addWidget(forgot)
        lf.addLayout(row)
        login_btn = QPushButton("Iniciar sesión"); login_btn.setMinimumHeight(52); login_btn.setStyleSheet("font-size:17px;"); login_btn.clicked.connect(self.login); lf.addWidget(login_btn)
        lf.addStretch(1)
        register_tab = QWidget(); rf = QVBoxLayout(register_tab); rf.setContentsMargins(0,8,0,0); rf.setSpacing(10)
        self.reg_name = QLineEdit(); self.reg_name.setPlaceholderText("Nombre completo"); self.reg_name.setMinimumHeight(44)
        self.reg_email = QLineEdit(); self.reg_email.setPlaceholderText("Correo electrónico"); self.reg_email.setMinimumHeight(44)
        self.reg_password = QLineEdit(); self.reg_password.setPlaceholderText("Contraseña (mínimo 8 caracteres)"); self.reg_password.setEchoMode(QLineEdit.EchoMode.Password); self.reg_password.setMinimumHeight(44)
        self.reg_confirm = QLineEdit(); self.reg_confirm.setPlaceholderText("Confirmar contraseña"); self.reg_confirm.setEchoMode(QLineEdit.EchoMode.Password); self.reg_confirm.setMinimumHeight(44)
        for w in (self.reg_name,self.reg_email,self.reg_password,self.reg_confirm): rf.addWidget(w)
        reg_btn=QPushButton("Crear cuenta"); reg_btn.setMinimumHeight(48); reg_btn.clicked.connect(self.register); rf.addWidget(reg_btn); rf.addStretch(1)
        self.tabs.addTab(login_tab,"Iniciar sesión"); self.tabs.addTab(register_tab,"Crear cuenta"); form.addWidget(self.tabs,1)
        note=QLabel("Al crear una cuenta podrás explorar oportunidades y enviar solicitudes."); note.setWordWrap(True); note.setObjectName("muted"); form.addWidget(note)
        hero=QFrame(); hero.setObjectName("authHero"); hero.setStyleSheet("QFrame#authHero{background:#155bd5;border-top-right-radius:20px;border-bottom-right-radius:20px;}")
        hl=QVBoxLayout(hero); hl.setContentsMargins(34,50,34,40); hl.setSpacing(24); hl.addStretch(1)
        illustration=QLabel(); illustration.setAlignment(Qt.AlignmentFlag.AlignCenter)
        illustration.setMinimumHeight(235); illustration.setMaximumHeight(300)
        art=QPixmap(os.path.join(os.path.dirname(__file__), "assets", "network_illustration.png"))
        if not art.isNull(): illustration.setPixmap(art.scaled(620,300,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        illustration.setStyleSheet("background:#0b2c67;border-radius:24px;padding:8px;")
        hl.addWidget(illustration)
        hero_title=QLabel("Todo conectado en un solo lugar"); hero_title.setAlignment(Qt.AlignmentFlag.AlignCenter); hero_title.setWordWrap(True); hero_title.setStyleSheet("color:white;font-size:27px;font-weight:700;")
        hero_desc=QLabel("Encontrá oportunidades y conectá con personas."); hero_desc.setAlignment(Qt.AlignmentFlag.AlignCenter); hero_desc.setWordWrap(True); hero_desc.setStyleSheet("color:#dbeafe;font-size:17px;")
        hl.addWidget(hero_title); hl.addWidget(hero_desc); hl.addStretch(1)
        outer.addWidget(panel, 11); outer.addWidget(hero, 10)

    def login(self):
        email=self.login_email.text().strip().lower(); password=self.login_password.text()
        if not email or not password:
            QMessageBox.warning(self,"Datos incompletos","Escribe tu correo y contraseña."); return
        wait=services.LOGIN_GUARD.remaining(email)
        if wait:
            QMessageBox.warning(self,"Cuenta bloqueada temporalmente",f"Hubo demasiados intentos fallidos. Intentá de nuevo en {max(1,(wait+59)//60)} minuto(s)."); return
        try:
            connection=get_connection()
            try:
                cursor=connection.cursor(dictionary=True)
                cursor.execute("SELECT id,nombre,correo,password_hash,rol FROM usuarios WHERE correo=%s AND activo=1",(email,)); user=cursor.fetchone()
            finally: connection.close()
            if user and verify_password(password,user["password_hash"]):
                services.LOGIN_GUARD.clear(email); self.on_login(user)
            else:
                services.LOGIN_GUARD.fail(email); QMessageBox.warning(self,"Acceso denegado","El correo o la contraseña no son correctos.")
        except Exception as exc: message_error(self,"No se pudo iniciar sesión",exc)

    def register(self):
        name=self.reg_name.text().strip(); email=self.reg_email.text().strip().lower(); password=self.reg_password.text(); confirm=self.reg_confirm.text()
        if not name or not email or "@" not in email or "." not in email.split("@")[-1]:
            QMessageBox.warning(self,"Datos incorrectos","Completa tu nombre y escribe un correo válido."); return
        if len(password)<8:
            QMessageBox.warning(self,"Contraseña débil","Usa una contraseña de al menos 8 caracteres."); return
        if password!=confirm:
            QMessageBox.warning(self,"No coinciden","Las contraseñas no coinciden."); return
        try:
            connection=get_connection()
            try:
                cursor=connection.cursor(); cursor.execute("INSERT INTO usuarios (nombre,correo,password_hash,rol) VALUES (%s,%s,%s,'cliente')",(name,email,hash_password(password))); connection.commit()
            finally: connection.close()
            QMessageBox.information(self,"Cuenta creada","Tu cuenta se creó correctamente. Ya puedes iniciar sesión.")
            self.tabs.setCurrentIndex(0); self.login_email.setText(email); self.login_password.clear()
        except Error as exc:
            if getattr(exc,"errno",None)==1062: QMessageBox.warning(self,"Correo registrado","Ya existe una cuenta con ese correo.")
            else: message_error(self,"No se pudo crear la cuenta",exc)
        except Exception as exc: message_error(self,"No se pudo crear la cuenta",exc)

    def forgot_password(self):
        email, ok = QInputDialog.getText(self,"Recuperar contraseña","Escribe el correo de tu cuenta:")
        if not ok or not email.strip(): return
        email=email.strip().lower()
        smtp_host=os.getenv("SMTP_HOST","").strip(); smtp_user=os.getenv("SMTP_USER","").strip(); smtp_pass=os.getenv("SMTP_PASSWORD","").strip()
        smtp_port=int(os.getenv("SMTP_PORT","587")); sender=os.getenv("SMTP_FROM",smtp_user).strip()
        if not (smtp_host and smtp_user and smtp_pass and sender):
            QMessageBox.information(self,"Recuperación por correo","Para recuperar la contraseña de forma segura, primero configura SMTP_HOST, SMTP_USER, SMTP_PASSWORD y SMTP_FROM en el archivo .env. Las instrucciones están en README.md.")
            return
        try:
            connection=get_connection()
            try:
                cursor=connection.cursor(dictionary=True); cursor.execute("SELECT id,nombre FROM usuarios WHERE correo=%s AND activo=1",(email,)); user=cursor.fetchone()
                if not user:
                    QMessageBox.information(self,"Solicitud recibida","Si el correo corresponde a una cuenta activa, se enviarán instrucciones."); return
                token=secrets.token_urlsafe(24); token_hash=hashlib.sha256(token.encode()).hexdigest(); expires=datetime.now()+timedelta(minutes=20)
                cursor.execute("DELETE FROM password_resets WHERE usuario_id=%s OR expira_en < NOW()",(user["id"],))
                cursor.execute("INSERT INTO password_resets (usuario_id,token_hash,expira_en) VALUES (%s,%s,%s)",(user["id"],token_hash,expires)); connection.commit()
            finally: connection.close()
            msg=EmailMessage(); msg["Subject"]="Recuperación de contraseña | Foxy Lancer"; msg["From"]=sender; msg["To"]=email
            msg.set_content(f"Hola {user['nombre']},\n\nTu código de recuperación de Foxy Lancer es:\n\n{token}\n\nCaduca en 20 minutos. Si no lo solicitaste, ignora este mensaje.")
            with smtplib.SMTP(smtp_host,smtp_port,timeout=15) as server:
                server.starttls(); server.login(smtp_user,smtp_pass); server.send_message(msg)
            token_input, accepted=QInputDialog.getText(self,"Código enviado","Revisa tu correo e introduce el código de recuperación:")
            if not accepted or not token_input.strip(): return
            new_pass, accepted=QInputDialog.getText(self,"Nueva contraseña","Escribe una nueva contraseña (mínimo 8 caracteres):",QLineEdit.EchoMode.Password)
            if not accepted: return
            if len(new_pass)<8:
                QMessageBox.warning(self,"Contraseña débil","Usa al menos 8 caracteres y vuelve a solicitar la recuperación."); return
            connection=get_connection()
            try:
                cursor=connection.cursor(); cursor.execute("SELECT id FROM password_resets WHERE usuario_id=%s AND token_hash=%s AND expira_en > NOW()",(user["id"],hashlib.sha256(token_input.strip().encode()).hexdigest()))
                if not cursor.fetchone():
                    QMessageBox.warning(self,"Código inválido","El código no es válido o ya caducó."); connection.rollback(); return
                cursor.execute("UPDATE usuarios SET password_hash=%s WHERE id=%s",(hash_password(new_pass),user["id"]))
                cursor.execute("DELETE FROM password_resets WHERE usuario_id=%s",(user["id"],)); connection.commit()
            finally: connection.close()
            QMessageBox.information(self,"Contraseña actualizada","Ya puedes iniciar sesión con tu nueva contraseña.")
        except Exception as exc:
            QMessageBox.warning(self,"No se pudo recuperar","No se pudo completar la recuperación. Revisa MySQL y la configuración SMTP del archivo .env.\n\n"+str(exc))


current_window = None
auth_window = None


def start_session(user):
    """Abre la ventana principal. Devuelve True si se pudo abrir."""
    global current_window
    try:
        window = MainWindow(user, on_logout=show_login)
    except Exception as exc:
        logging.getLogger("mypines").exception("No se pudo abrir la ventana principal")
        message_error(auth_window, "No se pudo abrir Foxy Lancer", exc)
        return False
    current_window = window
    services.log(user["id"], "inicio_sesion", user["correo"])
    window.show()
    return True


def show_login():
    """Muestra la pantalla de inicio de sesión (al abrir la app y al cerrar sesión)."""
    global auth_window

    def after_login(user):
        previous = auth_window
        if start_session(user) and previous is not None:
            previous.close()

    auth_window = AuthWindow(after_login)
    auth_window.show()


def _setup_logging():
    base = os.path.dirname(os.path.abspath(__file__))
    try:
        logging.basicConfig(filename=os.path.join(base, "mypines.log"), level=logging.INFO, encoding="utf-8",
                            format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    except Exception:
        logging.basicConfig(level=logging.INFO)

    def hook(exc_type, exc, tb):
        logging.getLogger("mypines").error("Excepción no controlada", exc_info=(exc_type, exc, tb))
        try:
            QMessageBox.warning(None, "Ocurrió un error", "Algo salió mal, pero Foxy Lancer sigue funcionando.\n"
                                "El detalle quedó guardado en mypines.log.\n\n" + str(exc))
        except Exception:
            pass
    sys.excepthook = hook


def main():
    _setup_logging()
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    ok, detail = check_connection()
    if ok:
        try:
            ensure_schema()
        except Exception as exc:
            ok, detail = False, str(exc)
    show_login()
    if not ok:
        QMessageBox.warning(auth_window, "MySQL no disponible",
            "La aplicación necesita que MySQL esté iniciado y configurado para guardar los datos.\n\n"
            + detail + "\n\nRevisa MYSQL_PASSWORD en el archivo .env. Si aparece un error de esquema, consulta el detalle antes de modificar tablas.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
