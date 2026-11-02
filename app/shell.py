"""Ventana principal de Foxy Lancer: barra superior (cliente) o barra lateral (administrador)."""
import os
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton, QMenu, QStackedWidget,
    QLineEdit, QDialog, QSystemTrayIcon, QApplication,
)

from . import services, logic, ai
from . import theme as th
from . import pages_client as pc
from . import pages_admin as pa
from .dialogs import (
    ApplyDialog, JobDialog, NotificationsDialog, OnboardingDialog, AboutDialog, ChangePasswordDialog, ReportDialog,
)
from .errors import handle, show_error
from .widgets import make_avatar, EmptyState, btn, toast, lbl

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

CLIENT_NAV = [("jobs", "Buscar trabajo"), ("requests", "Mis solicitudes"), ("publications", "Publicaciones"),
              ("interviews", "Entrevistas"), ("contracts", "Contratos"), ("community", "Comunidad")]
ADMIN_NAV = [("dashboard", "▦  Dashboard"), ("calendar", "🗓  Calendario"), ("interviews", "☎  Entrevistas"),
             ("requests", "▤  Solicitudes"), ("jobs", "⌂  Trabajos"), ("users", "☺  Usuarios"), ("reviews", "☆  Reseñas"),
             ("reports", "⚑  Reportes recibidos"), ("exports", "⭳  Informes"), ("activity", "≡  Actividad"),
             ("backup", "⛁  Respaldo")]
NAV_ALIAS = {"detail": "jobs", "favorites": "jobs", "candidates": "publications"}


class MainWindow(QMainWindow):
    def __init__(self, user, on_logout=None):
        super().__init__()
        self.user = user
        self.on_logout = on_logout
        self.is_admin = user["rol"] == "admin"
        self._skills = None
        self._unread = None
        self._photo = None
        self.current_key, self.current_kw = None, {}
        self.nav_buttons = {}
        th.set_theme(services.get_theme(user["id"]))
        self.setStyleSheet(th.build_stylesheet())
        self.setWindowTitle(f'Foxy Lancer | {user["nombre"]}')
        self.resize(1360, 880)
        self.setMinimumSize(1100, 680)
        self.stack = QStackedWidget()
        self.factories = self.make_factories()
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        if self.is_admin:
            self.build_admin_layout(root)
        else:
            self.build_client_layout(root)
        self.build_user_menu()
        self.setup_tray()
        self.setup_shortcuts()
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.refresh_bell(True))
        self.timer.start(30000)
        self.refresh_bell(False)
        self.go("dashboard" if self.is_admin else "jobs")
        if not self.is_admin:
            QTimer.singleShot(700, self.maybe_onboarding)

    # ------------------------------------------------------------ páginas
    def make_factories(self):
        s = self
        common = {
            "profile": lambda: pc.ProfilePage(s),
            "community": lambda: pc.CommunityPage(s),
        }
        if self.is_admin:
            common.update({
                "dashboard": lambda: pa.DashboardPage(s),
                "calendar": lambda: pc.InterviewsPage(s),
                "interviews": lambda: pa.RequestsAdminPage(s, "citas"),
                "requests": lambda: pa.RequestsAdminPage(s, "solicitudes"),
                "jobs": lambda term="": pa.AdminJobsPage(s, term),
                "users": lambda: pa.UsersPage(s),
                "reviews": lambda: pa.ReviewsAdminPage(s),
                "reports": lambda: pa.ReportsPage(s),
                "exports": lambda: pa.ExportPage(s),
                "activity": lambda: pa.ActivityPage(s),
                "backup": lambda: pa.BackupPage(s),
            })
        else:
            common.update({
                "jobs": lambda preset=None: pc.JobsPage(s, preset),
                "detail": lambda job_id: pc.JobDetailPage(s, job_id),
                "requests": lambda: pc.RequestsPage(s),
                "publications": lambda: pc.PublicationsPage(s),
                "candidates": lambda job_id: pc.CandidatesPage(s, job_id),
                "interviews": lambda: pc.InterviewsPage(s),
                "contracts": lambda: pc.ContractsPage(s),
                "favorites": lambda: pc.FavoritesPage(s),
            })
        return common

    def go(self, key, **kw):
        factory = self.factories.get(key)
        if factory is None:
            return
        try:
            page = factory(**kw)
        except Exception as exc:
            show_error(self, "No se pudo abrir la página", exc)
            page = EmptyState("⚠", "No se pudo abrir esta página", "Revisá la conexión con MySQL y volvé a intentar.")
        old = self.stack.currentWidget()
        self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)
        if old is not None and old is not page:
            self.stack.removeWidget(old)
            old.deleteLater()
        self.current_key, self.current_kw = key, kw
        nav = NAV_ALIAS.get(key, key)
        for k, b in self.nav_buttons.items():
            b.setChecked(k == nav)
        self.statusBar().showMessage(f"●  Conectado a MySQL   ·   actualizado {datetime.now():%H:%M}   ·   © 2026 Foxy Lancer")
        self.refresh_bell(True)

    def reload(self):
        if self.current_key:
            self.go(self.current_key, **self.current_kw)

    # ------------------------------------------------------- layout cliente
    def build_client_layout(self, root):
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        top = QFrame()
        top.setObjectName("topbar")
        top.setFixedHeight(68)
        h = QHBoxLayout(top)
        h.setContentsMargins(22, 8, 22, 8)
        h.setSpacing(6)
        h.addWidget(self.logo(40))
        brand = QLabel("Foxy Lancer")
        brand.setObjectName("accent")
        brand.setStyleSheet("font-size:17pt; font-weight:700;")
        h.addWidget(brand)
        h.addSpacing(22)
        for key, text in CLIENT_NAV:
            b = QPushButton(text)
            b.setObjectName("navtab")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda checked=False, k=key: self.go(k))
            self.nav_buttons[key] = b
            h.addWidget(b)
        h.addStretch(1)
        h.addWidget(self.ai_button())
        h.addSpacing(4)
        h.addWidget(self.bell_button())
        h.addWidget(self.user_button())
        outer.addWidget(top)
        outer.addWidget(self.stack, 1)
        self.statusBar().setSizeGripEnabled(False)

    # ---------------------------------------------------- layout administrador
    def build_admin_layout(self, root):
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(240)
        v = QVBoxLayout(side)
        v.setContentsMargins(16, 18, 16, 16)
        v.setSpacing(6)
        brand_row = QHBoxLayout()
        brand_row.addWidget(self.logo(36))
        brand = QLabel("Foxy Lancer")
        brand.setObjectName("accent")
        brand.setStyleSheet("font-size:16pt; font-weight:700;")
        brand_row.addWidget(brand)
        brand_row.addStretch(1)
        v.addLayout(brand_row)
        v.addSpacing(8)
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("🔍 Buscar trabajos…")
        self.global_search.returnPressed.connect(lambda: self.go("jobs", term=self.global_search.text().strip()))
        v.addWidget(self.global_search)
        v.addSpacing(8)
        for key, text in ADMIN_NAV:
            b = QPushButton(text)
            b.setObjectName("side")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda checked=False, k=key: self.go(k))
            self.nav_buttons[key] = b
            v.addWidget(b)
        v.addStretch(1)
        v.addWidget(self.user_button())
        outer.addWidget(side)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(64)
        h = QHBoxLayout(bar)
        h.setContentsMargins(26, 8, 22, 8)
        h.setSpacing(8)
        title = lbl("Panel de administración", "muted")
        h.addWidget(title)
        h.addStretch(1)
        h.addWidget(self.ai_button())
        h.addWidget(self.bell_button())
        h.addWidget(btn("+ Nuevo trabajo", None, self.publish_job))
        right.addWidget(bar)
        right.addWidget(self.stack, 1)
        outer.addLayout(right, 1)

    # ---------------------------------------------------------- componentes
    def logo(self, size):
        label = QLabel()
        pix = QPixmap(os.path.join(ASSETS, "mypines_fox.png"))
        if not pix.isNull():
            label.setPixmap(pix.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        label.setStyleSheet("background:transparent;")
        return label

    def ai_button(self):
        b = QPushButton("✦ Foxy Lancer AI")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(self.open_ai)
        return b

    def bell_button(self):
        self.bell = QPushButton("🔔")
        self.bell.setObjectName("iconBtn")
        self.bell.setToolTip("Notificaciones")
        self.bell.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bell.clicked.connect(self.open_notifications)
        return self.bell

    def user_button(self):
        self.user_btn = QToolButton()
        self.user_btn.setObjectName("avatarBtn")
        self.user_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.user_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.user_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.user_btn.setIconSize(QSize(30, 30))
        return self.user_btn

    def build_user_menu(self):
        photo = None
        try:
            prof = services.get_profile(self.user["id"])
            photo = (prof or {}).get("foto_abs")
        except Exception:
            pass
        self.user_btn.setIcon(QIcon(make_avatar(self.user["nombre"], 30, photo)))
        first = self.user["nombre"].split()[0] if self.user["nombre"].split() else self.user["nombre"]
        self.user_btn.setText("  " + first + (" (admin)" if self.is_admin else ""))
        menu = QMenu(self.user_btn)
        menu.addAction("Mi perfil").triggered.connect(lambda: self.go("profile"))
        if not self.is_admin:
            menu.addAction("Trabajos guardados").triggered.connect(lambda: self.go("favorites"))
        menu.addAction("Cambiar contraseña").triggered.connect(lambda: ChangePasswordDialog(self, self.user).exec())
        menu.addSeparator()
        menu.addAction("Modo claro" if th.is_dark() else "Modo oscuro").triggered.connect(self.toggle_theme)
        if not self.is_admin:
            menu.addAction("Ver bienvenida").triggered.connect(lambda: OnboardingDialog(self).exec())
        menu.addAction("Acerca de Foxy Lancer").triggered.connect(lambda: AboutDialog(self).exec())
        menu.addSeparator()
        menu.addAction("Cerrar sesión").triggered.connect(self.logout)
        self.user_btn.setMenu(menu)

    # -------------------------------------------------------------- estado
    @property
    def user_skills(self):
        if self._skills is None:
            try:
                self._skills = (services.get_profile(self.user["id"]) or {}).get("habilidades", "")
            except Exception:
                self._skills = ""
        return self._skills

    def profile_changed(self):
        self._skills = None
        self.build_user_menu()

    def toggle_theme(self):
        new = "claro" if th.is_dark() else "oscuro"
        th.set_theme(new)
        services.set_theme(self.user["id"], new)
        self.setStyleSheet(th.build_stylesheet())
        self.build_user_menu()
        self.refresh_bell(False)
        self.reload()

    # ------------------------------------------------------- notificaciones
    def setup_tray(self):
        self.tray = None
        try:
            if QSystemTrayIcon.isSystemTrayAvailable():
                pix = QPixmap(os.path.join(ASSETS, "mypines_fox.png"))
                self.tray = QSystemTrayIcon(QIcon(pix), self)
                self.tray.setToolTip("Foxy Lancer")
                self.tray.show()
        except Exception:
            self.tray = None

    def refresh_bell(self, allow_popup=True):
        n = services.unread_count(self.user["id"])
        t = th.T
        self.bell.setText(f"🔔 {n}" if n else "🔔")
        self.bell.setStyleSheet(f"background:{t['danger_bg']}; color:{t['danger']}; font-weight:700;" if n else "")
        if allow_popup and self.tray is not None and self._unread is not None and n > self._unread:
            try:
                self.tray.showMessage("Foxy Lancer", f"Tenés {n} notificación(es) sin leer.", QSystemTrayIcon.MessageIcon.Information, 5000)
            except Exception:
                pass
        self._unread = n

    def open_notifications(self):
        NotificationsDialog(self, self.user).exec()
        self.refresh_bell(False)

    # ------------------------------------------------------------- acciones
    def publish_job(self):
        d = JobDialog(self, None, self.is_admin)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            services.save_job(self.user, d.values())
        except Exception as exc:
            handle(self, "No se pudo guardar", exc)
            return
        toast(self, "Trabajo guardado")
        self.go("jobs" if self.is_admin else "publications")

    def edit_job(self, job):
        d = JobDialog(self, job, self.is_admin)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            services.save_job(self.user, d.values(), job["id"])
        except Exception as exc:
            handle(self, "No se pudo guardar", exc)
            return
        toast(self, "Cambios guardados")
        self.reload()

    def apply_job(self, job, after=None):
        if ApplyDialog(self, self.user, job).exec() == QDialog.DialogCode.Accepted:
            toast(self, "Solicitud enviada")
            if after:
                after()

    def report(self, tipo, target_id, name):
        ReportDialog(self, self.user, tipo, target_id, name).exec()

    def open_ai(self):
        ai.MyPinesAI(self).exec()

    def maybe_onboarding(self):
        if services.onboarding_seen(self.user["id"]):
            return
        d = OnboardingDialog(self)
        d.exec()
        if d.dont_show.isChecked():
            services.set_onboarding_seen(self.user["id"])

    # --------------------------------------------------------------- atajos
    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.focus_search)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.publish_job)

    def focus_search(self):
        page = self.stack.currentWidget()
        field = getattr(page, "search", None)
        if field is None and self.is_admin:
            field = getattr(self, "global_search", None)
        if field is not None:
            field.setFocus()
            field.selectAll()

    # --------------------------------------------------------------- sesión
    def logout(self):
        self.timer.stop()
        if self.tray is not None:
            self.tray.hide()
        if self.on_logout:
            self.on_logout()
        self.close()

    def closeEvent(self, e):
        self.timer.stop()
        if self.tray is not None:
            self.tray.hide()
        super().closeEvent(e)
