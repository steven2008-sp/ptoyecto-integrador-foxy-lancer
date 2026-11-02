"""Páginas del modo administrador (estilo dashboard)."""
import os
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, QDate, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QComboBox, QMenu, QMessageBox, QFileDialog,
    QDateEdit, QCheckBox, QApplication, QPushButton,
)

from . import services, logic, exports
from . import theme as th
from .charts import LineChart, HBarChart, DonutChart
from .dialogs import DetailDialog, UserActivityDialog
from .errors import handle
from .pages_client import padded_page
from .widgets import (
    Card, EmptyState, PillTabs, KPICard, DataTable, lbl, btn, badge, state_badge, two_line, action_cell, small_btn,
    row_widget, clear_layout, toast, stars_label,
)


def _wrap(widget):
    """Centra verticalmente un widget (badges) dentro de una celda."""
    return row_widget([widget], 0)


def _menu_button(text, items, kind="secondary"):
    b = QPushButton(text)
    b.setObjectName(kind)
    b.setStyleSheet("padding:6px 12px; font-size:10pt;")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    m = QMenu(b)
    for label, fn in items:
        a = m.addAction(label)
        a.triggered.connect(lambda checked=False, f=fn: f())
    b.setMenu(m)
    return b


def _save_dialog(parent, title, default, filt):
    path, _ = QFileDialog.getSaveFileName(parent, title, default, filt)
    return path


def _export(shell, title, headers, rows, kind):
    """Exporta a Excel ('xlsx') o PDF ('pdf') preguntando dónde guardar."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    ext = "xlsx" if kind == "xlsx" else "pdf"
    path = _save_dialog(shell, "Guardar informe", f"mypines_{title.lower().replace(' ', '_')}_{stamp}.{ext}",
                        "Excel (*.xlsx)" if kind == "xlsx" else "PDF (*.pdf)")
    if not path:
        return
    try:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        if kind == "xlsx":
            exports.export_xlsx(path, title, headers, rows)
        else:
            exports.export_pdf_table(path, title, headers, rows)
        services.log(shell.user["id"], "exportar_informe", f"{title} ({ext}, {len(rows)} filas)")
    except Exception as exc:
        QApplication.restoreOverrideCursor()
        handle(shell, "No se pudo exportar", exc)
        return
    QApplication.restoreOverrideCursor()
    toast(shell, f"Informe guardado ({len(rows)} filas)")


# ======================================================================
#  Tabla de solicitudes / entrevistas (con pestañas)
# ======================================================================
class AdminTableCard(Card):
    TABS = [("nuevas", "Nuevas"), ("pendientes", "Pendientes"), ("aprobadas", "Aprobadas"), ("canceladas", "Canceladas")]

    def __init__(self, shell, source="solicitudes", allow_switch=False):
        super().__init__(pad=(20, 18, 20, 18), spacing=12)
        self.shell, self.admin, self.source = shell, shell.user, source
        self.rows = []
        top = QHBoxLayout()
        top.setSpacing(10)
        self.title = lbl("", "h3")
        top.addWidget(self.title)
        top.addStretch(1)
        self.switch = None
        if allow_switch:
            self.switch = PillTabs([("solicitudes", "Solicitudes"), ("citas", "Entrevistas")], source)
            self.switch.changed.connect(self.change_source)
            top.addWidget(self.switch)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Buscar candidato o trabajo…")
        self.search.setMinimumWidth(230)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.render)
        self.search.textChanged.connect(lambda _: self.timer.start())
        top.addWidget(self.search)
        top.addWidget(_menu_button("⭳ Exportar", [("Excel (.xlsx)", lambda: self.export("xlsx")), ("PDF", lambda: self.export("pdf"))]))
        self.lay.addLayout(top)
        self.tabs = PillTabs(self.TABS, "pendientes")
        self.tabs.changed.connect(lambda k: self.render())
        self.lay.addWidget(self.tabs)
        self.table = None
        self.holder = QVBoxLayout()
        self.lay.addLayout(self.holder)
        self.load()

    # ---- datos
    def load(self):
        try:
            self.rows = services.admin_requests() if self.source == "solicitudes" else services.list_interviews(self.admin)
        except Exception as exc:
            self.rows = []
            handle(self.shell, "No se pudieron cargar los datos", exc)
        self.title.setText("Todas las solicitudes" if self.source == "solicitudes" else "Todas las entrevistas")
        self.render()

    def change_source(self, key):
        self.source = key
        self.load()

    def group(self, key):
        positive = logic.REQ_POSITIVE if self.source == "solicitudes" else ("Aceptada", "Completada")
        negative = ("Rechazada", "Cancelada", "Retirada") if self.source == "solicitudes" else ("Rechazada", "Cancelada")
        week = datetime.now() - timedelta(days=7)
        out = []
        for r in self.rows:
            if key == "nuevas" and r["creado_en"] >= week:
                out.append(r)
            elif key == "pendientes" and r["estado"] == "Pendiente":
                out.append(r)
            elif key == "aprobadas" and r["estado"] in positive:
                out.append(r)
            elif key == "canceladas" and r["estado"] in negative:
                out.append(r)
        return out

    def visible(self):
        items = self.group(self.tabs.current)
        term = self.search.text().strip().casefold()
        if term:
            items = [r for r in items if term in f"{r['candidato']} {r['candidato_correo']} {r['titulo']}".casefold()]
        return items

    # ---- pintado
    def render(self):
        for key, label in self.TABS:
            self.tabs.set_label(key, f"{label} ({len(self.group(key))})")
        clear_layout(self.holder)
        items = self.visible()
        date_header = "Fecha" if self.source == "solicitudes" else "Fecha y hora"
        self.table = DataTable(["Candidato", "Trabajo", date_header, "Modalidad", "Presupuesto", "Estado", "Acciones"],
                               ["s", "s", "c", "c", "c", "c", "c"])
        data = []
        for r in items:
            when = r["creado_en"] if self.source == "solicitudes" else r["fecha"]
            actions = []
            if r["estado"] == "Pendiente":
                actions += [small_btn("Aceptar", None, lambda rr=r: self.decide(rr, "Aceptada")),
                            small_btn("Rechazar", "secondary", lambda rr=r: self.decide(rr, "Rechazada"))]
            actions.append(small_btn("Detalle", "ghost", lambda rr=r: self.detail(rr)))
            data.append([two_line(r["candidato"], r["candidato_correo"]), r["titulo"], logic.fmt_dt(when), r["modalidad"],
                         logic.money(r["presupuesto"]), _wrap(state_badge(r["estado"])), action_cell(actions)])
        if not data:
            self.holder.addWidget(EmptyState("📭", "No hay registros en esta pestaña", "Cuando haya actividad la vas a ver aquí."))
            return
        self.table.set_rows(data)
        self.holder.addWidget(self.table)

    def decide(self, r, estado):
        try:
            if self.source == "solicitudes":
                services.set_request_state(r["id"], estado, self.admin)
            else:
                services.set_interview_state(r["id"], estado, self.admin)
        except Exception as exc:
            handle(self.shell, "No se pudo actualizar", exc)
        self.load()

    def detail(self, r):
        if self.source == "solicitudes":
            DetailDialog(self.shell, "Solicitud #" + str(r["id"]),
                         [("Candidato", f"{r['candidato']} · {r['candidato_correo']}"), ("Trabajo", r["titulo"]),
                          ("Publicador", r["publicador"]), ("Estado", r["estado"]), ("Enviada", logic.fmt_dt(r["creado_en"])),
                          ("Presupuesto", logic.money(r["presupuesto"]))], r["mensaje"]).exec()
        else:
            DetailDialog(self.shell, "Entrevista #" + str(r["id"]),
                         [("Candidato", f"{r['candidato']} · {r['candidato_correo']}"), ("Trabajo", r["titulo"]),
                          ("Publicador", r["publicador"]), ("Estado", r["estado"]), ("Fecha y hora", logic.fmt_dt(r["fecha"]))],
                         r.get("notas") or "").exec()

    def export(self, kind):
        items = self.visible()
        if self.source == "solicitudes":
            headers = ["ID", "Candidato", "Correo", "Trabajo", "Fecha", "Modalidad", "Presupuesto (C$)", "Estado"]
            rows = [[r["id"], r["candidato"], r["candidato_correo"], r["titulo"], logic.fmt_dt(r["creado_en"]), r["modalidad"],
                     float(r["presupuesto"]), r["estado"]] for r in items]
            title = "Solicitudes"
        else:
            headers = ["ID", "Candidato", "Correo", "Trabajo", "Fecha y hora", "Modalidad", "Presupuesto (C$)", "Estado"]
            rows = [[r["id"], r["candidato"], r["candidato_correo"], r["titulo"], logic.fmt_dt(r["fecha"]), r["modalidad"],
                     float(r["presupuesto"]), r["estado"]] for r in items]
            title = "Entrevistas"
        _export(self.shell, title, headers, rows, kind)


# ======================================================================
#  Dashboard
# ======================================================================
class DashboardPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        root, v = padded_page(shell, "Dashboard", f"Resumen operativo de Foxy Lancer · {datetime.now().strftime('%d/%m/%Y')}")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        try:
            kpis = services.dashboard_kpis()
        except Exception as exc:
            kpis = []
            handle(shell, "No se pudo cargar el resumen", exc)
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, k in enumerate(kpis):
            grid.addWidget(KPICard(k["title"], k["value"], k["delta"]), i // 3, i % 3)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        v.addLayout(grid)
        # --- fila de gráficos 1
        row = QHBoxLayout()
        row.setSpacing(14)
        line_card = Card(pad=(20, 16, 20, 16))
        head = QHBoxLayout()
        head.addWidget(lbl("Actividad", "h3"), 1)
        self.period = QComboBox()
        for text, key in (("Últimos 14 días", "dia"), ("Últimas 8 semanas", "semana"), ("Últimos 6 meses", "mes")):
            self.period.addItem(text, key)
        self.period.currentIndexChanged.connect(self.load_line)
        head.addWidget(self.period)
        line_card.lay.addLayout(head)
        self.line = LineChart()
        line_card.lay.addWidget(self.line)
        row.addWidget(line_card, 3)
        donut_card = Card(pad=(20, 16, 20, 16))
        donut_card.lay.addWidget(lbl("Usuarios: nuevos vs. recurrentes", "h3"))
        donut_card.lay.addWidget(lbl("Nuevos = registrados en los últimos 30 días", "small"))
        self.users_donut = DonutChart()
        donut_card.lay.addWidget(self.users_donut)
        row.addWidget(donut_card, 2)
        v.addLayout(row)
        # --- fila de gráficos 2
        row2 = QHBoxLayout()
        row2.setSpacing(14)
        cat_card = Card(pad=(20, 16, 20, 16))
        cat_card.lay.addWidget(lbl("Trabajos por categoría", "h3"))
        self.cat_chart = HBarChart()
        cat_card.lay.addWidget(self.cat_chart)
        cat_card.lay.addStretch(1)
        row2.addWidget(cat_card, 3)
        st_card = Card(pad=(20, 16, 20, 16))
        st_card.lay.addWidget(lbl("Solicitudes por estado", "h3"))
        self.state_donut = DonutChart()
        st_card.lay.addWidget(self.state_donut)
        row2.addWidget(st_card, 2)
        v.addLayout(row2)
        v.addWidget(AdminTableCard(shell, "solicitudes", allow_switch=True))
        v.addStretch(1)
        self.load_line()
        self.load_charts()

    def load_line(self, *_):
        try:
            labels, req, jobs = services.activity_series(self.period.currentData())
        except Exception as exc:
            handle(self.shell, "No se pudo cargar la actividad", exc)
            return
        colors = th.chart_colors()
        self.line.set_data(labels, [("Solicitudes", req, colors[0]), ("Trabajos publicados", jobs, colors[1])])

    def load_charts(self):
        colors = th.chart_colors()
        try:
            new, old = services.users_new_vs_returning()
            self.users_donut.set_data([("Nuevos", new, colors[0]), ("Recurrentes", old, colors[1])], str(new + old))
            cats = services.jobs_by_category()
            self.cat_chart.set_data([(c, n, colors[i % len(colors)]) for i, (c, n) in enumerate(cats)])
            states = services.requests_by_state()
            tone_color = {"Pendiente": th.T["warn"], "Rechazada": th.T["danger"], "Aceptada": th.T["success"],
                          "Completada": th.T["success"], "Contratada": th.T["success"], "En progreso": th.T["info"],
                          "Revisada": th.T["info"], "Entrevista": colors[3], "Cancelada": th.T["danger"], "Retirada": th.T["muted"]}
            self.state_donut.set_data([(s, n, tone_color.get(s)) for s, n in states])
        except Exception as exc:
            handle(self.shell, "No se pudieron cargar los gráficos", exc)


class RequestsAdminPage(QWidget):
    def __init__(self, shell, source="solicitudes"):
        super().__init__()
        title = "Solicitudes" if source == "solicitudes" else "Entrevistas"
        sub = ("Todas las solicitudes enviadas por los usuarios." if source == "solicitudes"
               else "Entrevistas propuestas; aceptalas o rechazalas.")
        root, v = padded_page(shell, title, sub)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        v.addWidget(AdminTableCard(shell, source))
        v.addStretch(1)


# ======================================================================
#  Trabajos
# ======================================================================
class AdminJobsPage(QWidget):
    def __init__(self, shell, term=""):
        super().__init__()
        self.shell, self.admin = shell, shell.user
        root, v = padded_page(shell, "Trabajos", "Creá, editá, cerrá o eliminá las publicaciones de la plataforma.",
                              [btn("+ Nuevo trabajo", None, shell.publish_job)])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        card = Card(pad=(20, 18, 20, 18), spacing=12)
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.search = QLineEdit(term)
        self.search.setPlaceholderText("🔍 Buscar por título, habilidad o publicador…")
        self.cat = QComboBox()
        self.cat.addItem("Todas las categorías", "")
        for c in logic.CATEGORIES:
            self.cat.addItem(c, c)
        self.state = QComboBox()
        for text, key in (("Todos los estados", ""), ("Publicado", "Publicado"), ("Borrador", "Borrador"), ("Cerrado", "Cerrado")):
            self.state.addItem(text, key)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.render)
        self.search.textChanged.connect(lambda _: self.timer.start())
        self.cat.currentIndexChanged.connect(lambda _: self.render())
        self.state.currentIndexChanged.connect(lambda _: self.render())
        bar.addWidget(self.search, 1)
        bar.addWidget(self.cat)
        bar.addWidget(self.state)
        bar.addWidget(_menu_button("⭳ Exportar", [("Excel (.xlsx)", lambda: self.export("xlsx")), ("PDF", lambda: self.export("pdf"))]))
        card.lay.addLayout(bar)
        self.count = lbl("", "muted")
        card.lay.addWidget(self.count)
        self.holder = QVBoxLayout()
        card.lay.addLayout(self.holder)
        v.addWidget(card)
        v.addStretch(1)
        self.rows = []
        self.render()

    def render(self):
        clear_layout(self.holder)
        try:
            self.rows = services.admin_jobs(self.search.text(), self.cat.currentData(), self.state.currentData())
        except Exception as exc:
            self.rows = []
            handle(self.shell, "No se pudieron cargar los trabajos", exc)
        self.count.setText(f"{len(self.rows)} trabajo(s)")
        if not self.rows:
            self.holder.addWidget(EmptyState("🗂", "No hay trabajos con esos filtros", "Probá con otra búsqueda o creá uno nuevo."))
            return
        table = DataTable(["Trabajo", "Publicador", "Modalidad", "Presupuesto", "Postulantes", "Estado", "Acciones"],
                          ["s", "c", "c", "c", "c", "c", "c"], 62)
        data = []
        for j in self.rows:
            state_widgets = [state_badge(j["estado"])]
            if j.get("urgente"):
                state_widgets.append(badge("Urgente", "danger"))
            acts = [small_btn("Editar", "secondary", lambda jj=j: self.shell.edit_job(jj)),
                    small_btn("Reabrir" if j["estado"] == "Cerrado" else "Cerrar", "secondary", lambda jj=j: self.toggle_state(jj)),
                    small_btn("Normal" if j.get("urgente") else "Urgente", "secondary", lambda jj=j: self.toggle_urgent(jj)),
                    small_btn("Eliminar", "danger", lambda jj=j: self.remove(jj))]
            data.append([two_line(j["titulo"], j["categoria"]), j["publicador"], j["modalidad"], logic.money(j["presupuesto"]),
                         str(j["postulantes"]), row_widget(state_widgets, 4), action_cell(acts)])
        table.set_rows(data)
        self.holder.addWidget(table)

    def toggle_state(self, j):
        try:
            services.set_job_state(self.admin, j["id"], "Publicado" if j["estado"] == "Cerrado" else "Cerrado")
        except Exception as exc:
            handle(self.shell, "No se pudo cambiar el estado", exc)
        self.render()

    def toggle_urgent(self, j):
        try:
            services.set_job_urgent(self.admin, j["id"], not j.get("urgente"))
        except Exception as exc:
            handle(self.shell, "No se pudo actualizar", exc)
        self.render()

    def remove(self, j):
        answer = QMessageBox.question(self.shell, "Confirmar eliminación",
                                      f"¿Seguro que querés eliminar «{j['titulo']}»? También se eliminarán sus solicitudes y entrevistas. Esta acción no se puede deshacer.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            services.delete_job(self.admin, j["id"])
        except Exception as exc:
            handle(self.shell, "No se pudo eliminar", exc)
        self.render()

    def export(self, kind):
        headers = ["ID", "Título", "Categoría", "Publicador", "Modalidad", "Presupuesto (C$)", "Postulantes", "Estado", "Urgente"]
        rows = [[j["id"], j["titulo"], j["categoria"], j["publicador"], j["modalidad"], float(j["presupuesto"]), j["postulantes"],
                 j["estado"], "Sí" if j.get("urgente") else "No"] for j in self.rows]
        _export(self.shell, "Trabajos", headers, rows, kind)


# ======================================================================
#  Usuarios
# ======================================================================
class UsersPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.admin = shell, shell.user
        root, v = padded_page(shell, "Usuarios", "Activá o desactivá cuentas, cambiá roles y revisá la actividad.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        card = Card(pad=(20, 18, 20, 18), spacing=12)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Buscar por nombre o correo…")
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.render)
        self.search.textChanged.connect(lambda _: self.timer.start())
        bar.addWidget(self.search, 1)
        bar.addWidget(_menu_button("⭳ Exportar", [("Excel (.xlsx)", lambda: self.export("xlsx")), ("PDF", lambda: self.export("pdf"))]))
        card.lay.addLayout(bar)
        self.holder = QVBoxLayout()
        card.lay.addLayout(self.holder)
        v.addWidget(card)
        v.addStretch(1)
        self.rows = []
        self.render()

    def render(self):
        clear_layout(self.holder)
        try:
            self.rows = services.admin_users(self.search.text())
        except Exception as exc:
            self.rows = []
            handle(self.shell, "No se pudieron cargar los usuarios", exc)
        if not self.rows:
            self.holder.addWidget(EmptyState("👥", "No hay usuarios con esa búsqueda", ""))
            return
        table = DataTable(["Usuario", "Rol", "Estado", "Registro", "Publ.", "Solic.", "Reseñas", "Acciones"],
                          ["s", "c", "c", "c", "c", "c", "c", "c"], 62)
        data = []
        for u in self.rows:
            me = u["id"] == self.admin["id"]
            toggle = small_btn("Desactivar" if u["activo"] else "Activar", "secondary", lambda uu=u: self.toggle_active(uu))
            role = small_btn("Hacer cliente" if u["rol"] == "admin" else "Hacer admin", "secondary", lambda uu=u: self.toggle_role(uu))
            if me:
                toggle.setEnabled(False)
                role.setEnabled(False)
            acts = [toggle, role, small_btn("Actividad", "ghost", lambda uu=u: UserActivityDialog(self.shell, uu).exec())]
            data.append([two_line(u["nombre"] + ("  (vos)" if me else ""), u["correo"]),
                         _wrap(badge(u["rol"], "info" if u["rol"] == "admin" else "neutral")),
                         _wrap(badge("Activo" if u["activo"] else "Inactivo", "success" if u["activo"] else "danger")),
                         logic.fmt_dt(u["creado_en"]), str(u["publicaciones"]), str(u["solicitudes"]), str(u["resenas"]),
                         action_cell(acts)])
        table.set_rows(data)
        self.holder.addWidget(table)

    def toggle_active(self, u):
        verb = "desactivar" if u["activo"] else "activar"
        if QMessageBox.question(self.shell, "Confirmar", f"¿Querés {verb} la cuenta de {u['nombre']}?") != QMessageBox.StandardButton.Yes:
            return
        try:
            services.set_user_active(self.admin, u["id"], not u["activo"])
        except Exception as exc:
            handle(self.shell, "No se pudo actualizar", exc)
        self.render()

    def toggle_role(self, u):
        new = "cliente" if u["rol"] == "admin" else "admin"
        if QMessageBox.question(self.shell, "Confirmar", f"¿Cambiar el rol de {u['nombre']} a «{new}»?") != QMessageBox.StandardButton.Yes:
            return
        try:
            services.set_user_role(self.admin, u["id"], new)
        except Exception as exc:
            handle(self.shell, "No se pudo actualizar", exc)
        self.render()

    def export(self, kind):
        headers = ["ID", "Nombre", "Correo", "Rol", "Activo", "Registro", "Publicaciones", "Solicitudes", "Reseñas"]
        rows = [[u["id"], u["nombre"], u["correo"], u["rol"], "Sí" if u["activo"] else "No", logic.fmt_dt(u["creado_en"]),
                 u["publicaciones"], u["solicitudes"], u["resenas"]] for u in self.rows]
        _export(self.shell, "Usuarios", headers, rows, kind)


# ======================================================================
#  Reseñas (moderación)
# ======================================================================
class ReviewsAdminPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.admin = shell, shell.user
        root, v = padded_page(shell, "Reseñas", "Moderá las reseñas de la comunidad y eliminá las inapropiadas.",
                              [btn("Ver perfiles de la comunidad", "secondary", lambda: shell.go("community"))])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        card = Card(pad=(20, 18, 20, 18), spacing=12)
        self.holder = QVBoxLayout()
        card.lay.addLayout(self.holder)
        v.addWidget(card)
        v.addStretch(1)
        self.render()

    def render(self):
        clear_layout(self.holder)
        try:
            rows = services.all_reviews()
        except Exception as exc:
            rows = []
            handle(self.shell, "No se pudieron cargar las reseñas", exc)
        if not rows:
            self.holder.addWidget(EmptyState("☆", "Todavía no hay reseñas", "Cuando los usuarios dejen reseñas aparecerán aquí."))
            return
        table = DataTable(["Autor", "Destinatario", "Puntuación", "Comentario", "Fecha", "Acciones"], ["c", "c", "c", "s", "c", "c"], 66)
        data = []
        for r in rows:
            data.append([r["autor"], r["destinatario"], stars_label(r["puntuacion"]), logic.truncate(r["comentario"], 140),
                         logic.fmt_dt(r["creado_en"]), action_cell([small_btn("Eliminar", "danger", lambda rr=r: self.remove(rr))])])
        table.set_rows(data)
        self.holder.addWidget(table)

    def remove(self, r):
        if QMessageBox.question(self.shell, "Eliminar reseña", f"¿Eliminar la reseña de {r['autor']} sobre {r['destinatario']}?") != QMessageBox.StandardButton.Yes:
            return
        try:
            services.delete_review(r["id"], self.admin["id"])
        except Exception as exc:
            handle(self.shell, "No se pudo eliminar", exc)
        self.render()


# ======================================================================
#  Reportes recibidos
# ======================================================================
class ReportsPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.admin = shell, shell.user
        root, v = padded_page(shell, "Reportes recibidos", "Publicaciones y usuarios reportados por la comunidad.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        card = Card(pad=(20, 18, 20, 18), spacing=12)
        self.tabs = PillTabs([("", "Todos"), ("Nuevo", "Nuevos"), ("En revisión", "En revisión"), ("Resuelto", "Resueltos"), ("Descartado", "Descartados")], "Nuevo")
        self.tabs.changed.connect(lambda k: self.render())
        card.lay.addWidget(self.tabs)
        self.holder = QVBoxLayout()
        card.lay.addLayout(self.holder)
        v.addWidget(card)
        v.addStretch(1)
        self.render()

    def render(self):
        clear_layout(self.holder)
        try:
            rows = services.list_reports(self.tabs.current)
        except Exception as exc:
            rows = []
            handle(self.shell, "No se pudieron cargar los reportes", exc)
        if not rows:
            self.holder.addWidget(EmptyState("🛡", "No hay reportes en esta categoría", "¡Todo tranquilo por ahora!"))
            return
        table = DataTable(["Fecha", "Reportó", "Objetivo", "Motivo", "Estado", "Acciones"], ["c", "c", "s", "s", "c", "c"], 62)
        data = []
        for r in rows:
            items = [("Ver detalle", lambda rr=r: DetailDialog(self.shell, f"Reporte #{rr['id']}", [
                ("Tipo", rr["tipo"]), ("Objetivo", rr["objetivo"] or "(eliminado)"), ("Reportó", rr["autor"]), ("Motivo", rr["motivo"]),
                ("Estado", rr["estado"]), ("Fecha", logic.fmt_dt(rr["creado_en"]))], rr.get("comentario") or "").exec()),
                ("Marcar en revisión", lambda rr=r: self.state(rr, "En revisión")),
                ("Marcar resuelto", lambda rr=r: self.state(rr, "Resuelto")),
                ("Descartar", lambda rr=r: self.state(rr, "Descartado"))]
            if r["tipo"] == "trabajo":
                items.append(("Cerrar la publicación", lambda rr=r: self.close_job(rr)))
            else:
                items.append(("Desactivar al usuario", lambda rr=r: self.disable_user(rr)))
            data.append([logic.fmt_dt(r["creado_en"]), r["autor"], f"{'Publicación' if r['tipo'] == 'trabajo' else 'Usuario'}: {r['objetivo'] or '(eliminado)'}",
                         r["motivo"], _wrap(state_badge(r["estado"])), action_cell([_menu_button("Acciones ▾", items)])])
        table.set_rows(data)
        self.holder.addWidget(table)

    def state(self, r, estado):
        try:
            services.set_report_state(r["id"], estado, self.admin)
        except Exception as exc:
            handle(self.shell, "No se pudo actualizar", exc)
        self.render()

    def close_job(self, r):
        if QMessageBox.question(self.shell, "Cerrar publicación", f"¿Cerrar «{r['objetivo']}» y marcar el reporte como resuelto?") != QMessageBox.StandardButton.Yes:
            return
        try:
            services.set_job_state(self.admin, r["objetivo_id"], "Cerrado")
            services.set_report_state(r["id"], "Resuelto", self.admin)
        except Exception as exc:
            handle(self.shell, "No se pudo cerrar", exc)
        self.render()

    def disable_user(self, r):
        if QMessageBox.question(self.shell, "Desactivar usuario", f"¿Desactivar a {r['objetivo']} y marcar el reporte como resuelto?") != QMessageBox.StandardButton.Yes:
            return
        try:
            services.set_user_active(self.admin, r["objetivo_id"], False)
            services.set_report_state(r["id"], "Resuelto", self.admin)
        except Exception as exc:
            handle(self.shell, "No se pudo desactivar", exc)
        self.render()


# ======================================================================
#  Informes (Excel / PDF)
# ======================================================================
class ExportPage(QWidget):
    KINDS = [("usuarios", "Usuarios"), ("trabajos", "Trabajos"), ("solicitudes", "Solicitudes"), ("entrevistas", "Entrevistas"), ("contratos", "Contratos")]

    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        root, v = padded_page(shell, "Informes", "Generá reportes en Excel o PDF con filtros por rango de fechas.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        card = Card(pad=(22, 20, 22, 20), spacing=12)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.kind = QComboBox()
        for key, label in self.KINDS:
            self.kind.addItem(label, key)
        row.addWidget(lbl("Informe:", "muted"))
        row.addWidget(self.kind)
        self.use_dates = QCheckBox("Filtrar por fechas")
        row.addWidget(self.use_dates)
        self.d_from, self.d_to = QDateEdit(), QDateEdit()
        for d in (self.d_from, self.d_to):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy")
        self.d_from.setDate(QDate.currentDate().addMonths(-1))
        self.d_to.setDate(QDate.currentDate())
        row.addWidget(lbl("Desde", "muted"))
        row.addWidget(self.d_from)
        row.addWidget(lbl("Hasta", "muted"))
        row.addWidget(self.d_to)
        row.addStretch(1)
        card.lay.addLayout(row)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addWidget(btn("Vista previa", "secondary", self.preview))
        actions.addWidget(btn("Exportar Excel", None, lambda: self.export("xlsx")))
        actions.addWidget(btn("Exportar PDF", None, lambda: self.export("pdf")))
        actions.addStretch(1)
        card.lay.addLayout(actions)
        self.summary = lbl("", "muted")
        card.lay.addWidget(self.summary)
        self.holder = QVBoxLayout()
        card.lay.addLayout(self.holder)
        v.addWidget(card)
        v.addStretch(1)

    def dataset(self):
        d1 = self.d_from.date().toPython() if self.use_dates.isChecked() else None
        d2 = self.d_to.date().toPython() if self.use_dates.isChecked() else None
        if d1 and d2 and d1 > d2:
            raise ValueError("La fecha «Desde» no puede ser posterior a «Hasta».")
        return services.export_dataset(self.kind.currentData(), d1, d2)

    def preview(self):
        clear_layout(self.holder)
        try:
            headers, rows = self.dataset()
        except Exception as exc:
            handle(self.shell, "No se pudo generar la vista previa", exc)
            return
        self.summary.setText(f"{len(rows)} registro(s) · mostrando los primeros {min(len(rows), 12)}")
        if not rows:
            self.holder.addWidget(EmptyState("📭", "Sin datos para ese rango", "Probá ampliar las fechas."))
            return
        table = DataTable(headers, ["s"] * len(headers), 44)
        table.set_rows([[("" if c is None else str(c)) for c in r] for r in rows[:12]])
        self.holder.addWidget(table)

    def export(self, kind):
        try:
            headers, rows = self.dataset()
        except Exception as exc:
            handle(self.shell, "No se pudo generar el informe", exc)
            return
        _export(self.shell, self.kind.currentText(), headers, rows, kind)


# ======================================================================
#  Actividad (bitácora)
# ======================================================================
class ActivityPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        root, v = padded_page(shell, "Actividad", "Bitácora de acciones importantes en la plataforma.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        card = Card(pad=(20, 18, 20, 18), spacing=12)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Buscar por usuario o detalle…")
        self.action = QComboBox()
        self.action.addItem("Todas las acciones", "")
        try:
            for a in services.bitacora_actions():
                self.action.addItem(a, a)
        except Exception:
            pass
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.render)
        self.search.textChanged.connect(lambda _: self.timer.start())
        self.action.currentIndexChanged.connect(lambda _: self.render())
        bar.addWidget(self.search, 1)
        bar.addWidget(self.action)
        card.lay.addLayout(bar)
        self.holder = QVBoxLayout()
        card.lay.addLayout(self.holder)
        v.addWidget(card)
        v.addStretch(1)
        self.render()

    def render(self):
        clear_layout(self.holder)
        try:
            rows = services.bitacora_list(self.search.text(), self.action.currentData())
        except Exception as exc:
            rows = []
            handle(self.shell, "No se pudo cargar la bitácora", exc)
        if not rows:
            self.holder.addWidget(EmptyState("📜", "Sin actividad registrada", "Las acciones importantes aparecerán aquí."))
            return
        table = DataTable(["Fecha", "Usuario", "Acción", "Detalle"], ["c", "c", "c", "s"], 46)
        table.set_rows([[logic.fmt_dt(r["creado_en"]), r["usuario"], r["accion"], r["detalle"]] for r in rows])
        self.holder.addWidget(table)


# ======================================================================
#  Respaldo
# ======================================================================
class BackupPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.admin = shell, shell.user
        root, v = padded_page(shell, "Respaldo", "Exportá una copia de la base de datos a un archivo .sql. No modifica ni borra datos.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        card = Card(pad=(22, 20, 22, 20), spacing=12)
        card.lay.addWidget(lbl("Crear respaldo", "h3"))
        card.lay.addWidget(lbl(f"Los respaldos se guardan en la carpeta «backups» del proyecto:\n{services.BACKUPS_DIR}", "muted", wrap=True))
        row = QHBoxLayout()
        row.addWidget(btn("Crear respaldo ahora", None, self.create))
        row.addWidget(btn("Abrir carpeta", "secondary", self.open_folder))
        row.addStretch(1)
        card.lay.addLayout(row)
        v.addWidget(card)
        self.list_card = Card(pad=(22, 20, 22, 20), spacing=10)
        v.addWidget(self.list_card)
        v.addStretch(1)
        self.render()

    def render(self):
        clear_layout(self.list_card.lay)
        self.list_card.lay.addWidget(lbl("Respaldos existentes", "h3"))
        items = exports.list_backups()
        if not items:
            self.list_card.lay.addWidget(lbl("Todavía no hay respaldos.", "muted"))
            return
        table = DataTable(["Archivo", "Fecha", "Tamaño"], ["s", "c", "c"], 46)
        table.set_rows([[i["nombre"], logic.fmt_dt(i["fecha"]), f"{i['tamano'] / 1024:,.0f} KB"] for i in items[:30]])
        self.list_card.lay.addWidget(table)

    def create(self):
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            path = exports.backup_database()
            services.log(self.admin["id"], "respaldo", os.path.basename(path))
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            handle(self.shell, "No se pudo crear el respaldo", exc)
            return
        QApplication.restoreOverrideCursor()
        toast(self.shell, "Respaldo creado: " + os.path.basename(path))
        self.render()

    def open_folder(self):
        os.makedirs(services.BACKUPS_DIR, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(services.BACKUPS_DIR))
