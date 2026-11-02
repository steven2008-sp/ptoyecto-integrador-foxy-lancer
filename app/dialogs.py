"""Formularios y ventanas pequeñas de Foxy Lancer (el contenido principal vive en páginas)."""
import html
import os
from datetime import datetime, date, timedelta

from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox,
    QCheckBox, QDateEdit, QScrollArea, QWidget, QFileDialog, QMessageBox, QStackedWidget, QFrame,
)

from . import services, logic, ai, exports
from . import theme as th
from .errors import handle
from .widgets import (
    Card, lbl, btn, badge, state_badge, chip, chips_row, badges_row, stars_label, Avatar, progress, clear_layout,
    hsep, toast,
)
from .calendar_widgets import MonthCalendar, SlotPicker


class BaseDialog(QDialog):
    def __init__(self, parent, title, width=520):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(width)
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 22, 24, 22)
        self.root.setSpacing(12)

    def buttons(self, ok_text, ok_slot, cancel_text="Cancelar"):
        row = QHBoxLayout()
        row.addStretch(1)
        if cancel_text:
            row.addWidget(btn(cancel_text, "secondary", self.reject))
        self.ok_btn = btn(ok_text, None, ok_slot)
        row.addWidget(self.ok_btn)
        self.root.addLayout(row)


def _scroll(widget, min_h=260):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setMinimumHeight(min_h)
    area.setWidget(widget)
    return area


def _list_container(spacing=10):
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 4, 0)
    v.setSpacing(spacing)
    return w, v


# ------------------------------------------------------------------ trabajos
class JobDialog(BaseDialog):
    def __init__(self, parent, job=None, is_admin=False):
        super().__init__(parent, "Editar trabajo" if job else "Publicar trabajo", 600)
        self.job = job
        self._ai_worker = None
        root = self.root
        root.addWidget(lbl("Editar publicación" if job else "Publicar una oportunidad", "h2"))
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self.title = QLineEdit(job["titulo"] if job else "")
        self.title.setMaxLength(140)
        self.title.setPlaceholderText("Ej.: Desarrollo de página web para negocio")
        self.category = QComboBox()
        self.category.addItems(logic.CATEGORIES)
        self.description = QTextEdit()
        self.description.setMinimumHeight(130)
        self.description.setPlainText(job["descripcion"] if job else "")
        self.skills = QLineEdit(job["habilidades"] if job else "")
        self.skills.setMaxLength(500)
        self.skills.setPlaceholderText("Ej.: Python, MySQL, diseño")
        self.mode = QComboBox()
        self.mode.addItems(logic.MODALITIES)
        self.location = QLineEdit(job.get("ubicacion", "") if job else "")
        self.location.setPlaceholderText("Ciudad o zona (opcional)")
        self.budget = QDoubleSpinBox()
        self.budget.setMaximum(99999999)
        self.budget.setDecimals(2)
        self.budget.setPrefix("C$ ")
        self.budget.setGroupSeparatorShown(True)
        self.budget.setValue(float(job["presupuesto"]) if job else 0)
        self.status = QComboBox()
        self.status.addItems(["Publicado", "Borrador", "Cerrado"])
        self.urgent = QCheckBox("Marcar como urgente")
        if job:
            self.category.setCurrentText(job["categoria"])
            self.mode.setCurrentText(job["modalidad"])
            self.status.setCurrentText(job["estado"])
            self.urgent.setChecked(bool(job.get("urgente")))
        form.addRow("Título:", self.title)
        form.addRow("Categoría:", self.category)
        form.addRow("Descripción:", self.description)
        self.ai_btn = btn("✦ Mejorar descripción con IA", "secondary", self.improve)
        self.ai_note = lbl("", "small", wrap=True)
        form.addRow("", self.ai_btn)
        form.addRow("", self.ai_note)
        form.addRow("Habilidades:", self.skills)
        form.addRow("Modalidad:", self.mode)
        form.addRow("Ubicación:", self.location)
        form.addRow("Presupuesto:", self.budget)
        form.addRow("Estado:", self.status)
        form.addRow("", self.urgent)
        root.addLayout(form)
        self.buttons("Guardar", self.validate_and_accept)

    def values(self):
        return {
            "titulo": self.title.text().strip(), "categoria": self.category.currentText(),
            "descripcion": self.description.toPlainText().strip(), "habilidades": self.skills.text().strip(),
            "modalidad": self.mode.currentText(), "presupuesto": self.budget.value(), "estado": self.status.currentText(),
            "urgente": self.urgent.isChecked(), "ubicacion": self.location.text().strip(),
        }

    def improve(self):
        data = self.values()
        if not data["titulo"] and not data["descripcion"]:
            QMessageBox.information(self, "Falta información", "Escribí al menos el título o una descripción para mejorarla.")
            return
        fallback = logic.local_improve_description(data["titulo"], data["categoria"], data["descripcion"],
                                                   data["habilidades"], data["modalidad"], data["presupuesto"])
        worker = ai.PromptWorker(ai.SYSTEM_ES, ai.description_prompt(data), fallback)

        def done(text, used_ai, notice):
            self.description.setPlainText(text)
            self.ai_note.setText(notice or "Descripción mejorada con Foxy Lancer AI. Revisala antes de guardar.")
        ai.run_helper(self, worker, done, self.ai_btn)

    def validate_and_accept(self):
        v = self.values()
        if not v["titulo"] or not v["descripcion"]:
            QMessageBox.warning(self, "Campos requeridos", "El título y la descripción son obligatorios.")
            return
        if len(v["titulo"]) < 5:
            QMessageBox.warning(self, "Título muy corto", "Escribí un título de al menos 5 caracteres.")
            return
        if v["presupuesto"] <= 0:
            QMessageBox.warning(self, "Presupuesto no válido", "El presupuesto debe ser mayor que 0.")
            return
        self.accept()


class ApplyDialog(BaseDialog):
    def __init__(self, parent, user, job):
        super().__init__(parent, "Enviar solicitud", 560)
        self.user, self.job = user, job
        self._ai_worker = None
        try:
            self.profile = services.get_profile(user["id"]) or {}
        except Exception:
            self.profile = {}
        self.root.addWidget(lbl("Enviar solicitud", "h2"))
        self.root.addWidget(lbl(f"Trabajo: {job['titulo']}", "muted", wrap=True))
        self.msg = QTextEdit()
        self.msg.setMinimumHeight(170)
        self.msg.setPlaceholderText("Presentate: tu experiencia, por qué te interesa y tu disponibilidad…")
        self.root.addWidget(self.msg)
        self.ai_btn = btn("✦ Redactar con IA", "secondary", self.draft)
        self.root.addWidget(self.ai_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.note = lbl("", "small", wrap=True)
        self.root.addWidget(self.note)
        self.buttons("Enviar solicitud", self.submit)

    def draft(self):
        fallback = logic.local_application_message(self.user["nombre"], self.profile.get("habilidades"),
                                                   self.profile.get("presentacion"), self.job)
        worker = ai.PromptWorker(ai.SYSTEM_ES, ai.application_prompt(self.user["nombre"], self.profile, self.job), fallback)

        def done(text, used_ai, notice):
            self.msg.setPlainText(text)
            self.note.setText(notice or "Borrador creado con Foxy Lancer AI. Editalo a tu gusto.")
        ai.run_helper(self, worker, done, self.ai_btn)

    def submit(self):
        text = self.msg.toPlainText().strip()
        if len(text) < 10:
            QMessageBox.warning(self, "Mensaje requerido", "Escribí un mensaje de al menos 10 caracteres para presentarte.")
            return
        try:
            services.apply_to_job(self.job["id"], self.user, text)
        except Exception as exc:
            if services.is_duplicate(exc):
                QMessageBox.warning(self, "Ya solicitaste este trabajo", "Solo podés enviar una solicitud por trabajo.")
            else:
                handle(self, "No se pudo enviar la solicitud", exc)
            return
        self.accept()


# ------------------------------------------------------------------- reseñas
RATING_LABELS = ["5 - Excelente", "4 - Muy bueno", "3 - Bueno", "2 - Puede mejorar", "1 - Malo"]


class ReviewDialog(BaseDialog):
    def __init__(self, parent, user, target_id, target_name):
        super().__init__(parent, "Puntuar a " + target_name, 500)
        self.user, self.target_id = user, target_id
        self.root.addWidget(lbl("Puntuar a " + target_name, "h2"))
        form = QFormLayout()
        form.setSpacing(10)
        self.rating = QComboBox()
        self.rating.addItems(RATING_LABELS)
        self.criteria = {}
        form.addRow("Puntuación general:", self.rating)
        for key, label in (("puntualidad", "Puntualidad:"), ("calidad", "Calidad del trabajo:"), ("comunicacion", "Comunicación:")):
            c = QComboBox()
            c.addItems(RATING_LABELS)
            self.criteria[key] = c
            form.addRow(label, c)
        self.comment = QTextEdit()
        self.comment.setMinimumHeight(110)
        self.comment.setPlaceholderText("Describí tu experiencia de forma honesta y respetuosa…")
        form.addRow("Reseña:", self.comment)
        self.root.addLayout(form)
        self.buttons("Publicar reseña", self.submit)

    def submit(self):
        text = self.comment.toPlainText().strip()
        if len(text) < 5:
            QMessageBox.warning(self, "Reseña requerida", "Escribí un comentario antes de publicar.")
            return
        score = 5 - self.rating.currentIndex()
        crit = {k: 5 - c.currentIndex() for k, c in self.criteria.items()}
        try:
            services.save_review(self.user["id"], self.target_id, score, text, **crit)
        except Exception as exc:
            handle(self, "No se pudo guardar la reseña", exc)
            return
        self.accept()


class ProfileViewDialog(BaseDialog):
    def __init__(self, parent, user, person_id):
        super().__init__(parent, "Perfil", 640)
        self.user, self.person_id = user, person_id
        self.resize(660, 700)
        self.body = QVBoxLayout()
        self.root.addLayout(self.body, 1)
        self.build()

    def build(self):
        clear_layout(self.body)
        try:
            p = services.get_profile(self.person_id)
            crit = services.criteria_avgs(self.person_id)
            reviews = services.reviews_for(self.person_id)
            reviewable = self.user["rol"] != "admin" and services.can_review(self.user["id"], self.person_id)
        except Exception as exc:
            handle(self, "No se pudo abrir el perfil", exc)
            self.body.addWidget(lbl("No se pudo cargar el perfil.", "muted"))
            return
        if not p:
            self.body.addWidget(lbl("Este perfil ya no existe.", "muted"))
            return
        self.setWindowTitle("Perfil de " + p["nombre"])
        head = QHBoxLayout()
        head.setSpacing(16)
        head.addWidget(Avatar(p["nombre"], 78, p["foto_abs"]))
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addWidget(lbl(p["nombre"], "h2"))
        col.addWidget(stars_label(p["promedio"], p["total_resenas"]))
        if p["ubicacion"]:
            col.addWidget(lbl("📍 " + p["ubicacion"], "muted"))
        if p["insignias"]:
            col.addWidget(badges_row(p["insignias"]))
        head.addLayout(col, 1)
        self.body.addLayout(head)
        if p["presentacion"]:
            self.body.addWidget(lbl(p["presentacion"], wrap=True))
        if p["habilidades"]:
            self.body.addWidget(lbl("Habilidades", "h3"))
            self.body.addWidget(chips_row(p["habilidades"], 10))
        if p["comentario"]:
            self.body.addWidget(lbl("“" + p["comentario"] + "”", "muted", wrap=True))
        if crit:
            self.body.addWidget(lbl("Valoración por criterio", "h3"))
            for key, label in (("puntualidad", "Puntualidad"), ("calidad", "Calidad"), ("comunicacion", "Comunicación")):
                if key in crit:
                    row = QHBoxLayout()
                    row.addWidget(lbl(f"{label}  {crit[key]:.1f}/5"), 1)
                    row.addWidget(progress(crit[key] * 20), 2)
                    self.body.addLayout(row)
        self.body.addWidget(lbl(f"Reseñas ({len(reviews)})", "h3"))
        cont, cl = _list_container(8)
        if not reviews:
            cl.addWidget(lbl("Todavía no tiene reseñas.", "muted"))
        for r in reviews:
            card = Card(shadow=False, pad=(14, 10, 14, 10), spacing=4)
            card.lay.addWidget(lbl(f"{logic.stars(r['puntuacion'])} · {r['autor']} · {logic.relative_time(r['creado_en'])}", "accent"))
            card.lay.addWidget(lbl(r["comentario"], wrap=True))
            cl.addWidget(card)
        cl.addStretch(1)
        self.body.addWidget(_scroll(cont, 140), 1)
        row = QHBoxLayout()
        if self.person_id != self.user["id"]:
            row.addWidget(btn("⚑ Reportar", "ghost", self.report))
        row.addStretch(1)
        if reviewable:
            row.addWidget(btn("☆ Escribir reseña", "secondary", self.review))
        row.addWidget(btn("Cerrar", None, self.accept))
        self.body.addLayout(row)

    def review(self):
        p = services.get_profile(self.person_id)
        if ReviewDialog(self, self.user, self.person_id, p["nombre"]).exec() == QDialog.DialogCode.Accepted:
            toast(self, "Reseña guardada")
            self.build()

    def report(self):
        p = services.get_profile(self.person_id)
        ReportDialog(self, self.user, "usuario", self.person_id, p["nombre"]).exec()


class ReportDialog(BaseDialog):
    REASONS = ["Contenido inapropiado", "Información falsa o engañosa", "Posible estafa", "Spam", "Acoso o lenguaje ofensivo", "Otro"]

    def __init__(self, parent, user, tipo, target_id, target_name):
        super().__init__(parent, "Reportar", 480)
        self.user, self.tipo, self.target_id = user, tipo, target_id
        self.root.addWidget(lbl("Reportar " + ("publicación" if tipo == "trabajo" else "usuario"), "h2"))
        self.root.addWidget(lbl(target_name, "muted", wrap=True))
        self.reason = QComboBox()
        self.reason.addItems(self.REASONS)
        self.comment = QTextEdit()
        self.comment.setPlaceholderText("Contanos qué pasó (opcional)…")
        self.comment.setMinimumHeight(100)
        self.root.addWidget(self.reason)
        self.root.addWidget(self.comment)
        self.buttons("Enviar reporte", self.submit)

    def submit(self):
        try:
            services.create_report(self.user["id"], self.tipo, self.target_id, self.reason.currentText(), self.comment.toPlainText().strip())
        except Exception as exc:
            handle(self, "No se pudo enviar el reporte", exc)
            return
        QMessageBox.information(self, "Reporte enviado", "Gracias. El equipo de administración lo revisará.")
        self.accept()


# ------------------------------------------------------------------ mensajes
class ChatDialog(BaseDialog):
    def __init__(self, parent, user, request_id):
        super().__init__(parent, "Mensajes", 560)
        self.user, self.request_id = user, request_id
        self.resize(600, 620)
        try:
            self.info = services.request_thread_info(request_id) or {}
        except Exception as exc:
            handle(self, "No se pudo abrir la conversación", exc)
            self.info = {}
        other = self.info.get("publicador") if user["id"] == self.info.get("cliente_id") else self.info.get("candidato")
        self.root.addWidget(lbl("Conversación", "h2"))
        self.root.addWidget(lbl(f"«{self.info.get('titulo', '')}» · con {other or 'Foxy Lancer'}", "muted", wrap=True))
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        self.view.setMinimumHeight(330)
        self.root.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Escribí un mensaje…")
        self.entry.setMaxLength(2000)
        self.entry.returnPressed.connect(self.send)
        row.addWidget(self.entry, 1)
        row.addWidget(btn("Enviar", None, self.send))
        self.root.addLayout(row)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(8000)
        self.refresh()

    def refresh(self):
        t = th.T
        try:
            msgs = services.get_messages(self.request_id, self.user)
        except Exception:
            return
        parts = []
        for m in msgs:
            mine = m["emisor_id"] == self.user["id"]
            color = t["primary_text"] if mine else t["text"]
            who = "Vos" if mine else html.escape(m["nombre"])
            when = m["creado_en"].strftime("%d/%m %H:%M")
            body = html.escape(m["texto"]).replace("\n", "<br>")
            parts.append(f"<p style='margin:0 0 10px 0;'><b style='color:{color}'>{who}</b> "
                         f"<span style='color:{t['muted']}'>· {when}</span><br>{body}</p>")
        if not parts:
            parts = [f"<p style='color:{t['muted']}'>Todavía no hay mensajes. ¡Escribí el primero!</p>"]
        bar = self.view.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 4
        self.view.setHtml("".join(parts))
        if at_end:
            bar.setValue(bar.maximum())

    def send(self):
        text = self.entry.text().strip()
        if not text:
            return
        try:
            services.send_message(self.request_id, self.user, text)
        except Exception as exc:
            handle(self, "No se pudo enviar", exc)
            return
        self.entry.clear()
        self.refresh()
        bar = self.view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def done(self, result):
        self.timer.stop()
        super().done(result)


# ------------------------------------------------------- búsquedas guardadas
class SavedSearchesDialog(BaseDialog):
    def __init__(self, parent, user):
        super().__init__(parent, "Búsquedas guardadas", 560)
        self.user, self.chosen = user, None
        self.root.addWidget(lbl("Búsquedas guardadas", "h2"))
        self.root.addWidget(lbl("Te avisamos con una notificación cuando se publique un trabajo que coincida.", "muted", wrap=True))
        self.body = QVBoxLayout()
        self.root.addLayout(self.body, 1)
        self.root.addWidget(btn("Cerrar", "secondary", self.reject), 0, Qt.AlignmentFlag.AlignRight)
        self.build()

    def build(self):
        clear_layout(self.body)
        try:
            rows = services.list_searches(self.user["id"])
        except Exception as exc:
            handle(self, "No se pudieron cargar las búsquedas", exc)
            return
        if not rows:
            self.body.addWidget(lbl("Todavía no guardaste búsquedas. Usá «Guardar esta búsqueda» en el panel de filtros.", "muted", wrap=True))
        for r in rows:
            card = Card(shadow=False, pad=(14, 10, 14, 10), spacing=6)
            card.lay.addWidget(lbl(r["nombre"], "h3"))
            card.lay.addWidget(lbl(logic.describe_filters(r["filtros"]), "muted", wrap=True))
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(btn("Eliminar", "ghost", lambda sid=r["id"]: self.remove(sid)))
            row.addWidget(btn("Aplicar", None, lambda f=r["filtros"]: self.apply(f)))
            card.lay.addLayout(row)
            self.body.addWidget(card)

    def apply(self, filters):
        self.chosen = filters
        self.accept()

    def remove(self, search_id):
        services.delete_search(self.user["id"], search_id)
        self.build()


# --------------------------------------------------------------- entrevistas
class InterviewDialog(BaseDialog):
    """Calendario + horarios (estilo agendador) para proponer una entrevista."""

    def __init__(self, parent, user, jobs, job_id=None, candidate_id=None, solicitud_id=None, subtitle=""):
        super().__init__(parent, "Agendar entrevista", 760)
        self.user, self.jobs = user, jobs
        self.candidate_id = candidate_id or user["id"]
        self.solicitud_id = solicitud_id
        self.root.addWidget(lbl("Elegí fecha y hora", "h2"))
        if subtitle:
            self.root.addWidget(lbl(subtitle, "muted", wrap=True))
        self.job_combo = QComboBox()
        for j in jobs:
            self.job_combo.addItem(j["titulo"], j["id"])
        if job_id is not None:
            idx = self.job_combo.findData(job_id)
            if idx >= 0:
                self.job_combo.setCurrentIndex(idx)
        if len(jobs) != 1:
            self.root.addWidget(self.job_combo)
        self.job_combo.currentIndexChanged.connect(lambda _: self.refresh_slots())
        row = QHBoxLayout()
        row.setSpacing(22)
        left = Card(shadow=False, pad=(16, 14, 16, 14))
        self.calendar = MonthCalendar(min_date=date.today())
        self.calendar.dateSelected.connect(lambda d: self.refresh_slots())
        left.lay.addWidget(self.calendar)
        row.addWidget(left, 5)
        right = Card(shadow=False, pad=(16, 14, 16, 14))
        self.day_label = lbl("Elegí un día en el calendario", "h3", wrap=True)
        right.lay.addWidget(self.day_label)
        self.slots = SlotPicker(cols=2)
        self.slots.slotChanged.connect(lambda s: self.update_confirm())
        right.lay.addWidget(self.slots)
        right.lay.addStretch(1)
        row.addWidget(right, 4)
        self.root.addLayout(row)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(80)
        self.notes.setPlaceholderText("Mensaje opcional para coordinar la entrevista…")
        self.root.addWidget(self.notes)
        self.buttons("Confirmar entrevista", self.submit)
        self.ok_btn.setEnabled(False)

    def _job_id(self):
        return self.job_combo.currentData()

    def refresh_slots(self):
        d = self.calendar.selected
        if d is None or self._job_id() is None:
            return
        try:
            busy = services.busy_slots(self._job_id(), d)
        except Exception:
            busy = set()
        earliest = None
        if d == date.today():
            earliest = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
        self.slots.configure(busy, earliest)
        self.day_label.setText(f"{logic.DIAS[d.weekday()]} {d.day} de {logic.MESES[d.month - 1]}".capitalize())
        self.update_confirm()

    def update_confirm(self):
        self.ok_btn.setEnabled(self.calendar.selected is not None and self.slots.selected is not None)

    def submit(self):
        d, slot = self.calendar.selected, self.slots.selected
        if not d or not slot or self._job_id() is None:
            return
        h, m = [int(x) for x in slot.split(":")]
        when = datetime.combine(d, datetime.min.time()).replace(hour=h, minute=m)
        try:
            services.create_interview(self._job_id(), self.candidate_id, when, self.notes.toPlainText().strip(),
                                      self.user, self.solicitud_id)
        except Exception as exc:
            handle(self, "No se pudo agendar", exc)
            self.refresh_slots()
            return
        self.accept()


# -------------------------------------------------------------- otros diálogos
class ChangePasswordDialog(BaseDialog):
    def __init__(self, parent, user):
        super().__init__(parent, "Cambiar contraseña", 440)
        self.user = user
        self.root.addWidget(lbl("Cambiar contraseña", "h2"))
        self.current, self.new, self.confirm = QLineEdit(), QLineEdit(), QLineEdit()
        for field, ph in ((self.current, "Contraseña actual"), (self.new, "Nueva contraseña (mínimo 8 caracteres)"), (self.confirm, "Repetí la nueva contraseña")):
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText(ph)
            self.root.addWidget(field)
        self.buttons("Guardar contraseña", self.submit)

    def submit(self):
        if self.new.text() != self.confirm.text():
            QMessageBox.warning(self, "No coinciden", "Las contraseñas nuevas no coinciden.")
            return
        try:
            services.change_password(self.user["id"], self.current.text(), self.new.text())
        except Exception as exc:
            handle(self, "No se pudo cambiar la contraseña", exc)
            return
        QMessageBox.information(self, "Contraseña actualizada", "Tu contraseña se cambió correctamente.")
        self.accept()


class NotificationsDialog(BaseDialog):
    def __init__(self, parent, user):
        super().__init__(parent, "Notificaciones", 520)
        self.user = user
        self.resize(540, 560)
        head = QHBoxLayout()
        head.addWidget(lbl("Notificaciones", "h2"), 1)
        head.addWidget(btn("Marcar todas como leídas", "secondary", self.read_all))
        self.root.addLayout(head)
        cont, self.col = _list_container(8)
        self.area = _scroll(cont, 380)
        self.root.addWidget(self.area, 1)
        self.build()

    def build(self):
        clear_layout(self.col)
        t = th.T
        try:
            rows = services.list_notifications(self.user["id"])
        except Exception as exc:
            handle(self, "No se pudieron cargar las notificaciones", exc)
            return
        if not rows:
            self.col.addWidget(lbl("🔔 No tenés notificaciones todavía.", "muted"))
        for n in rows:
            card = Card(shadow=False, pad=(14, 10, 14, 10), spacing=3)
            unread = not n["leida"]
            title = QLabel(("● " if unread else "") + n["titulo"])
            title.setStyleSheet(f"font-weight:700; color:{t['primary_text'] if unread else t['text']};")
            card.lay.addWidget(title)
            if n["mensaje"]:
                card.lay.addWidget(lbl(n["mensaje"], wrap=True))
            card.lay.addWidget(lbl(logic.relative_time(n["creado_en"]) + " · " + n["creado_en"].strftime("%H:%M"), "small"))
            self.col.addWidget(card)
        self.col.addStretch(1)

    def read_all(self):
        try:
            services.mark_all_read(self.user["id"])
        except Exception as exc:
            handle(self, "No se pudo actualizar", exc)
            return
        self.build()

    def done(self, result):
        try:
            services.mark_all_read(self.user["id"])
        except Exception:
            pass
        super().done(result)


class OnboardingDialog(BaseDialog):
    STEPS = [
        ("🦊", "¡Bienvenido a Foxy Lancer!", "Una plataforma para conectar talento con oportunidades. Podés buscar trabajo, publicar lo que necesitás y construir tu reputación con reseñas."),
        ("🔎", "Encontrá y aplicá", "Usá los filtros, mirá el porcentaje de compatibilidad con tu perfil, guardá tus favoritos y enviá tu solicitud. Foxy Lancer AI te ayuda a redactarla."),
        ("📣", "Publicá y contratá", "Publicá una oportunidad, revisá a los candidatos, agendá entrevistas, definí un contrato con hitos y calificá el trabajo al terminar."),
    ]

    def __init__(self, parent):
        super().__init__(parent, "Bienvenida", 520)
        self.stack = QStackedWidget()
        for icon, title, text in self.STEPS:
            page = QWidget()
            v = QVBoxLayout(page)
            v.setSpacing(10)
            i = lbl(icon)
            i.setStyleSheet("font-size:42pt; background:transparent;")
            i.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(i)
            h = lbl(title, "h2")
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(h)
            d = lbl(text, "muted", wrap=True)
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v.addWidget(d)
            v.addStretch(1)
            self.stack.addWidget(page)
        self.root.addWidget(self.stack)
        self.dont_show = QCheckBox("No volver a mostrar")
        self.dont_show.setChecked(True)
        self.root.addWidget(self.dont_show)
        row = QHBoxLayout()
        self.back = btn("Atrás", "secondary", lambda: self.go(-1))
        self.next = btn("Siguiente", None, lambda: self.go(1))
        row.addWidget(self.back)
        row.addStretch(1)
        row.addWidget(self.next)
        self.root.addLayout(row)
        self.go(0)

    def go(self, step):
        idx = self.stack.currentIndex() + step
        if idx >= self.stack.count():
            self.accept()
            return
        idx = max(0, idx)
        self.stack.setCurrentIndex(idx)
        self.back.setEnabled(idx > 0)
        self.next.setText("Empezar" if idx == self.stack.count() - 1 else "Siguiente")


class AboutDialog(BaseDialog):
    def __init__(self, parent):
        super().__init__(parent, "Acerca de Foxy Lancer", 420)
        i = lbl("🦊")
        i.setStyleSheet("font-size:40pt; background:transparent;")
        i.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.root.addWidget(i)
        for text, kind in ((f"Foxy Lancer {logic.APP_VERSION}", "h2"), ("Plataforma de talento y oportunidades", "muted"),
                           ("Aplicación de escritorio · Python, PySide6 y MySQL", "muted"),
                           ("Proyecto académico de quinto año", "muted")):
            l = lbl(text, kind, wrap=True)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.root.addWidget(l)
        self.root.addWidget(btn("Cerrar", None, self.accept))


class DetailDialog(BaseDialog):
    """Ventana genérica de detalle (admin): pares etiqueta/valor y un texto largo."""

    def __init__(self, parent, title, fields, text=""):
        super().__init__(parent, title, 520)
        self.root.addWidget(lbl(title, "h2"))
        form = QFormLayout()
        form.setSpacing(8)
        for k, v in fields:
            form.addRow(lbl(k + ":", "muted"), lbl(str(v), wrap=True))
        self.root.addLayout(form)
        if text:
            self.root.addWidget(hsep())
            self.root.addWidget(lbl(text, wrap=True))
        self.root.addWidget(btn("Cerrar", None, self.accept), 0, Qt.AlignmentFlag.AlignRight)


class UserActivityDialog(BaseDialog):
    def __init__(self, parent, row):
        super().__init__(parent, "Actividad de " + row["nombre"], 560)
        self.resize(600, 520)
        self.root.addWidget(lbl(row["nombre"], "h2"))
        self.root.addWidget(lbl(f"{row['correo']} · {row['rol']} · registrado {logic.fmt_dt(row['creado_en'])}", "muted", wrap=True))
        self.root.addWidget(lbl(f"{row['publicaciones']} publicación(es) · {row['solicitudes']} solicitud(es) · {row['resenas']} reseña(s) recibidas", "accent"))
        cont, col = _list_container(6)
        try:
            acts = services.user_activity(row["id"])
        except Exception as exc:
            acts = []
            handle(self, "No se pudo cargar la actividad", exc)
        if not acts:
            col.addWidget(lbl("Sin actividad registrada todavía.", "muted"))
        for a in acts:
            col.addWidget(lbl(f"{logic.fmt_dt(a['creado_en'])} · {a['accion']} · {a['detalle']}", wrap=True))
        col.addStretch(1)
        self.root.addWidget(_scroll(cont, 260), 1)
        self.root.addWidget(btn("Cerrar", None, self.accept), 0, Qt.AlignmentFlag.AlignRight)


# ----------------------------------------------------------------- contratos
class ContractDialog(BaseDialog):
    """Crear un contrato (desde una solicitud) o ver/gestionar uno existente."""

    def __init__(self, parent, user, request=None, job_budget=0, contract_id=None):
        super().__init__(parent, "Contrato", 620)
        self.user, self.request, self.contract_id = user, request, contract_id
        self.job_budget = job_budget
        self.resize(660, 640)
        self.body = QVBoxLayout()
        self.root.addLayout(self.body, 1)
        self.pending_hitos = []
        if contract_id:
            self.build_view()
        else:
            self.build_create()

    # -- crear
    def build_create(self):
        clear_layout(self.body)
        self.setWindowTitle("Nuevo contrato")
        r = self.request
        self.body.addWidget(lbl("Contratar candidato", "h2"))
        self.body.addWidget(lbl(f"{r['nombre']} · «{r.get('titulo', '')}»", "muted", wrap=True))
        form = QFormLayout()
        form.setSpacing(10)
        self.amount = QDoubleSpinBox()
        self.amount.setMaximum(99999999)
        self.amount.setPrefix("C$ ")
        self.amount.setDecimals(2)
        self.amount.setGroupSeparatorShown(True)
        self.amount.setValue(float(self.job_budget or 0))
        self.due = QDateEdit()
        self.due.setCalendarPopup(True)
        self.due.setDisplayFormat("dd/MM/yyyy")
        self.due.setMinimumDate(QDate.currentDate())
        self.due.setDate(QDate.currentDate().addDays(14))
        form.addRow("Monto acordado:", self.amount)
        form.addRow("Fecha de entrega:", self.due)
        self.body.addLayout(form)
        self.body.addWidget(lbl("Hitos o entregables (opcional)", "h3"))
        add = QHBoxLayout()
        self.hito_input = QLineEdit()
        self.hito_input.setPlaceholderText("Ej.: Diseño aprobado")
        self.hito_input.returnPressed.connect(self.add_pending)
        add.addWidget(self.hito_input, 1)
        add.addWidget(btn("Agregar", "secondary", self.add_pending))
        self.body.addLayout(add)
        self.pending_box = QVBoxLayout()
        self.body.addLayout(self.pending_box)
        self.body.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn("Cancelar", "secondary", self.reject))
        row.addWidget(btn("Crear contrato", None, self.create))
        self.body.addLayout(row)
        self.render_pending()

    def add_pending(self):
        text = self.hito_input.text().strip()
        if text:
            self.pending_hitos.append({"titulo": text})
            self.hito_input.clear()
            self.render_pending()

    def render_pending(self):
        clear_layout(self.pending_box)
        for i, h in enumerate(self.pending_hitos):
            row = QHBoxLayout()
            row.addWidget(lbl(f"{i + 1}. {h['titulo']}"), 1)
            row.addWidget(btn("Quitar", "ghost", lambda idx=i: self.drop(idx)))
            w = QWidget()
            w.setLayout(row)
            self.pending_box.addWidget(w)

    def drop(self, idx):
        self.pending_hitos.pop(idx)
        self.render_pending()

    def create(self):
        if self.amount.value() <= 0:
            QMessageBox.warning(self, "Monto no válido", "El monto acordado debe ser mayor que 0.")
            return
        try:
            self.contract_id = services.create_contract(self.request["id"], self.user, self.amount.value(),
                                                        self.due.date().toPython(), self.pending_hitos)
        except Exception as exc:
            handle(self, "No se pudo crear el contrato", exc)
            return
        self.accept()

    # -- ver
    def build_view(self):
        clear_layout(self.body)
        try:
            c = services.get_contract(self.contract_id)
        except Exception as exc:
            handle(self, "No se pudo abrir el contrato", exc)
            return
        if not c:
            self.body.addWidget(lbl("El contrato ya no existe.", "muted"))
            return
        self.c = c
        manager = self.user["rol"] == "admin" or self.user["id"] == c["owner_id"]
        self.setWindowTitle(f"Contrato #{c['id']}")
        head = QHBoxLayout()
        head.addWidget(lbl(c["titulo"], "h2", wrap=True), 1)
        head.addWidget(state_badge(c["estado"]))
        self.body.addLayout(head)
        self.body.addWidget(lbl(f"Publicador: {c['publicador']}   ·   Candidato: {c['candidato']}", "muted", wrap=True))
        self.body.addWidget(lbl(f"Monto: {logic.money(c['monto_acordado'])}   ·   Entrega: {logic.fmt_dt(c['fecha_entrega']) or '—'}", "accent"))
        total, ok = c["total_hitos"], c["hitos_ok"]
        pct = round(100 * ok / total) if total else (100 if c["estado"] == "Completado" else 0)
        self.body.addWidget(lbl(f"Progreso: {ok} de {total} hito(s) · {pct}%", "muted"))
        self.body.addWidget(progress(pct))
        self.body.addWidget(lbl("Hitos", "h3"))
        cont, col = _list_container(6)
        if not c["hitos"]:
            col.addWidget(lbl("Este contrato no tiene hitos todavía.", "muted"))
        editable = manager and c["estado"] in ("Activo",)
        for h in c["hitos"]:
            cb = QCheckBox(h["titulo"] + (f"  ·  límite {logic.fmt_dt(h['fecha_limite'])}" if h["fecha_limite"] else ""))
            cb.setChecked(bool(h["completado"]))
            cb.setEnabled(editable)
            cb.toggled.connect(lambda checked, hid=h["id"]: self.toggle(hid, checked))
            col.addWidget(cb)
        col.addStretch(1)
        self.body.addWidget(_scroll(cont, 130), 1)
        if editable:
            add = QHBoxLayout()
            self.hito_input = QLineEdit()
            self.hito_input.setPlaceholderText("Agregar otro hito…")
            self.hito_input.returnPressed.connect(self.add_hito)
            add.addWidget(self.hito_input, 1)
            add.addWidget(btn("Agregar hito", "secondary", self.add_hito))
            self.body.addLayout(add)
        row = QHBoxLayout()
        row.addWidget(btn("Comprobante PDF", "secondary", self.pdf))
        row.addWidget(btn("Mensajes", "secondary", self.chat))
        row.addStretch(1)
        if manager and c["estado"] == "Activo":
            if c["solicitud_estado"] == "Contratada":
                row.addWidget(btn("Iniciar trabajo", "secondary", self.start))
            row.addWidget(btn("Cancelar contrato", "danger", self.cancel))
            row.addWidget(btn("Marcar completado", None, self.complete))
        row.addWidget(btn("Cerrar", "secondary", self.accept))
        self.body.addLayout(row)

    def _run(self, fn, *args):
        try:
            fn(*args)
        except Exception as exc:
            handle(self, "No se pudo actualizar el contrato", exc)
        self.build_view()

    def toggle(self, hito_id, checked):
        self._run(services.toggle_hito, hito_id, checked, self.user)

    def add_hito(self):
        text = self.hito_input.text().strip()
        if text:
            self._run(services.add_hito, self.contract_id, self.user, text)

    def start(self):
        self._run(services.start_contract, self.contract_id, self.user)

    def complete(self):
        if QMessageBox.question(self, "Completar trabajo", "¿Marcar todo el trabajo como completado?") == QMessageBox.StandardButton.Yes:
            self._run(services.complete_contract, self.contract_id, self.user)

    def cancel(self):
        if QMessageBox.question(self, "Cancelar contrato", "¿Seguro que querés cancelar este contrato?") == QMessageBox.StandardButton.Yes:
            self._run(services.cancel_contract, self.contract_id, self.user)

    def chat(self):
        ChatDialog(self, self.user, self.c["solicitud_id"]).exec()

    def pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar comprobante", f"comprobante_contrato_{self.c['id']}.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            exports.contract_pdf(path, self.c)
            services.log(self.user["id"], "exportar_comprobante", f"contrato #{self.c['id']}")
            toast(self, "Comprobante guardado")
        except Exception as exc:
            handle(self, "No se pudo crear el PDF", exc)
