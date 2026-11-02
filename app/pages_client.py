"""Páginas del modo cliente (y las compartidas con el administrador)."""
from datetime import datetime, date, timedelta

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel, QLineEdit, QCheckBox, QComboBox, QSlider,
    QTextEdit, QToolButton, QMenu, QScrollArea, QFileDialog, QMessageBox, QInputDialog, QSizePolicy,
)

from . import services, logic, ai
from . import theme as th
from .dialogs import (
    ApplyDialog, ChatDialog, ContractDialog, InterviewDialog, ProfileViewDialog, ReportDialog, ReviewDialog,
    SavedSearchesDialog, ChangePasswordDialog,
)
from .errors import handle
from .calendar_widgets import MonthCalendar
from .widgets import (
    Card, EmptyState, PageHeader, PillTabs, Avatar, KPICard, lbl, btn, badge, state_badge, chip, chips_row,
    badges_row, stars_label, progress, clear_layout, hsep, toast, row_widget, page_scroll,
)


def dots_menu(items):
    tb = QToolButton()
    tb.setObjectName("dots")
    tb.setText("⋮")
    tb.setToolTip("Más opciones")
    tb.setCursor(Qt.CursorShape.PointingHandCursor)
    tb.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    menu = QMenu(tb)
    for text, fn in items:
        act = menu.addAction(text)
        act.triggered.connect(lambda checked=False, f=fn: f())
    tb.setMenu(menu)
    return tb


def center_scroll(inner, margins=(0, 0, 0, 0)):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(inner)
    return area


def padded_page(shell, title, subtitle=None, actions=None):
    """Página estándar: encabezado + columna de contenido con scroll. Devuelve (widget, layout)."""
    root = QWidget()
    outer = QVBoxLayout(root)
    outer.setContentsMargins(0, 0, 0, 0)
    inner = QWidget()
    inner.setObjectName("page")
    v = QVBoxLayout(inner)
    v.setContentsMargins(28, 22, 28, 26)
    v.setSpacing(16)
    v.addWidget(PageHeader(title, subtitle, actions))
    outer.addWidget(center_scroll(inner))
    return root, v


def open_profile(shell, person_id):
    ProfileViewDialog(shell, shell.user, person_id).exec()


# ======================================================================
#  Tarjeta de trabajo
# ======================================================================
class JobCardV2(Card):
    def __init__(self, shell, job, on_change):
        super().__init__(spacing=9)
        self.shell, self.job, self.on_change = shell, job, on_change
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(Avatar(job["publicador"], 46), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(lbl(job["titulo"], "h3", wrap=True))
        who = job["publicador"]
        if job["pub_resenas"]:
            who += f"   ·   {logic.stars(job['pub_promedio'], job['pub_resenas'])}"
        col.addWidget(lbl(who, "muted"))
        head.addLayout(col, 1)
        badges = []
        if job["urgente"]:
            badges.append(badge("Urgente", "danger"))
        if job["es_nuevo"]:
            badges.append(badge("Nuevo", "success"))
        if job["compat"] is not None:
            badges.append(badge(f"{job['compat']}% compatible", logic.compat_tone(job["compat"])))
        for b in badges:
            head.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
        head.addWidget(dots_menu([
            ("Ver detalle", self.open_detail),
            ("Copiar título", lambda: QGuiApplication.clipboard().setText(job["titulo"])),
            ("Reportar publicación", self.report),
        ]), 0, Qt.AlignmentFlag.AlignTop)
        self.lay.addLayout(head)
        meta = [job["modalidad"], job["categoria"]]
        if job.get("ubicacion"):
            meta.append(job["ubicacion"])
        meta.append(logic.relative_time(job["creado_en"]))
        self.lay.addWidget(lbl("   •   ".join(m for m in meta if m), "muted"))
        self.lay.addWidget(lbl(logic.truncate(job["descripcion"], 175), wrap=True))
        if job["habilidades"]:
            self.lay.addWidget(chips_row(job["habilidades"], 5))
        self.lay.addWidget(hsep())
        foot = QHBoxLayout()
        foot.setSpacing(10)
        price = lbl(logic.money(job["presupuesto"]), "h3")
        price.setStyleSheet(f"color:{th.T['primary_text']}; font-weight:700;")
        foot.addWidget(price)
        foot.addWidget(lbl(f"👥 {job['postulantes']} postulante(s)", "muted"))
        foot.addStretch(1)
        self.fav = btn("♥" if job["es_favorito"] else "♡", "iconBtn", self.toggle_fav, "Guardar en favoritos")
        foot.addWidget(self.fav)
        foot.addWidget(btn("Ver detalle", "secondary", self.open_detail))
        if job["ya_aplico"]:
            done = btn("Ya aplicaste", None)
            done.setEnabled(False)
            foot.addWidget(done)
        else:
            foot.addWidget(btn("Aplicar", None, self.apply))
        self.lay.addLayout(foot)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.open_detail()
        super().mouseReleaseEvent(e)

    def open_detail(self):
        self.shell.go("detail", job_id=self.job["id"])

    def toggle_fav(self):
        try:
            on = services.toggle_favorite(self.shell.user["id"], self.job["id"])
        except Exception as exc:
            handle(self.shell, "No se pudo guardar", exc)
            return
        self.job["es_favorito"] = on
        self.fav.setText("♥" if on else "♡")
        toast(self.shell, "Guardado en favoritos" if on else "Quitado de favoritos")
        self.on_change(self.job, "fav")

    def apply(self):
        self.shell.apply_job(self.job, lambda: self.on_change(self.job, "apply"))

    def report(self):
        self.shell.report("trabajo", self.job["id"], self.job["titulo"])


# ======================================================================
#  Buscar trabajos (3 columnas: filtros | resultados | sugeridos)
# ======================================================================
class JobsPage(QWidget):
    PER_PAGE = 10

    def __init__(self, shell, preset=None):
        super().__init__()
        self.shell, self.user = shell, shell.user
        self.skills = shell.user_skills
        self.page = 1
        self.all_jobs = []
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(240)
        self.timer.timeout.connect(self.reload)
        try:
            self.ceiling = services.budget_ceiling()
            self.counts = services.category_counts(self.user["id"])
        except Exception as exc:
            self.ceiling, self.counts = 100000, {}
            handle(shell, "No se pudieron cargar los filtros", exc)
        root = QHBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 8)
        root.setSpacing(18)
        root.addWidget(self.build_filters(), 0)
        root.addWidget(self.build_center(), 1)
        root.addWidget(self.build_side(), 0)
        if preset:
            self.set_filters(preset)
        self.reload()

    # ---- columna izquierda
    def build_filters(self):
        inner = QWidget()
        inner.setObjectName("page")
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 6, 8)
        card = Card(pad=(16, 14, 16, 16), spacing=9)
        head = QHBoxLayout()
        head.addWidget(lbl("Filtros", "h3"), 1)
        head.addWidget(btn("Limpiar todo", "ghost", self.clear))
        card.lay.addLayout(head)
        card.lay.addWidget(lbl("Presupuesto", "accent"))
        self.min_slider, self.max_slider = QSlider(Qt.Orientation.Horizontal), QSlider(Qt.Orientation.Horizontal)
        self.min_label, self.max_label = lbl("", "muted"), lbl("", "muted")
        for s in (self.min_slider, self.max_slider):
            s.setRange(0, self.ceiling)
            s.setSingleStep(100)
            s.setPageStep(1000)
        self.max_slider.setValue(self.ceiling)
        for s in (self.min_slider, self.max_slider):
            s.valueChanged.connect(self.on_slider)
        card.lay.addWidget(self.min_label)
        card.lay.addWidget(self.min_slider)
        card.lay.addWidget(self.max_label)
        card.lay.addWidget(self.max_slider)
        card.lay.addWidget(hsep())
        card.lay.addWidget(lbl("Modalidad", "accent"))
        self.mod_boxes = {}
        for m in logic.MODALITIES:
            cb = QCheckBox(m)
            cb.toggled.connect(self.schedule)
            self.mod_boxes[m] = cb
            card.lay.addWidget(cb)
        self.urgent = QCheckBox("Solo urgentes")
        self.urgent.toggled.connect(self.schedule)
        card.lay.addWidget(self.urgent)
        card.lay.addWidget(hsep())
        card.lay.addWidget(lbl("Categoría", "accent"))
        self.cat_boxes = {}
        for c in logic.CATEGORIES:
            cb = QCheckBox(f"{c}  ({self.counts.get(c, 0)})")
            cb.toggled.connect(self.schedule)
            self.cat_boxes[c] = cb
            card.lay.addWidget(cb)
        card.lay.addWidget(hsep())
        card.lay.addWidget(lbl("Publicado", "accent"))
        self.date_combo = QComboBox()
        for text, key in (("Cualquier fecha", None), ("Hoy", "hoy"), ("Últimos 7 días", "7"), ("Últimos 30 días", "30")):
            self.date_combo.addItem(text, key)
        self.date_combo.currentIndexChanged.connect(self.schedule)
        card.lay.addWidget(self.date_combo)
        card.lay.addWidget(lbl("Postulantes", "accent"))
        self.app_combo = QComboBox()
        for text, key in (("Cualquier cantidad", None), ("Menos de 10", "lt10"), ("De 10 a 50", "10-50"), ("Más de 50", "gt50")):
            self.app_combo.addItem(text, key)
        self.app_combo.currentIndexChanged.connect(self.schedule)
        card.lay.addWidget(self.app_combo)
        card.lay.addWidget(hsep())
        card.lay.addWidget(btn("Guardar esta búsqueda", "secondary", self.save_search))
        card.lay.addWidget(btn("Mis búsquedas guardadas", "ghost", self.open_searches))
        v.addWidget(card)
        v.addStretch(1)
        area = center_scroll(inner)
        area.setFixedWidth(284)
        self.update_slider_labels()
        return area

    def update_slider_labels(self):
        lo, hi = self.min_slider.value(), self.max_slider.value()
        self.min_label.setText(f"Desde {logic.money(lo).replace('.00', '')}")
        self.max_label.setText("Hasta " + ("sin tope" if hi >= self.ceiling else logic.money(hi).replace(".00", "")))

    def on_slider(self, _=None):
        if self.min_slider.value() > self.max_slider.value():
            sender = self.sender()
            if sender is self.min_slider:
                self.max_slider.blockSignals(True)
                self.max_slider.setValue(self.min_slider.value())
                self.max_slider.blockSignals(False)
            else:
                self.min_slider.blockSignals(True)
                self.min_slider.setValue(self.max_slider.value())
                self.min_slider.blockSignals(False)
        self.update_slider_labels()
        self.schedule()

    def schedule(self, *args):
        self.timer.start()

    def get_filters(self):
        f = {"term": self.search.text().strip(), "categorias": [c for c, b in self.cat_boxes.items() if b.isChecked()],
             "modalidades": [m for m, b in self.mod_boxes.items() if b.isChecked()],
             "min_budget": self.min_slider.value() or None,
             "max_budget": None if self.max_slider.value() >= self.ceiling else self.max_slider.value(),
             "urgente": self.urgent.isChecked(), "fecha": self.date_combo.currentData(),
             "postulantes": self.app_combo.currentData(), "orden": self.sort.currentData()}
        return f

    def set_filters(self, f):
        widgets = (list(self.cat_boxes.values()) + list(self.mod_boxes.values()) +
                   [self.urgent, self.date_combo, self.app_combo, self.sort, self.min_slider, self.max_slider, self.search])
        for w in widgets:
            w.blockSignals(True)
        self.search.setText(f.get("term") or "")
        for c, b in self.cat_boxes.items():
            b.setChecked(c in (f.get("categorias") or []))
        for m, b in self.mod_boxes.items():
            b.setChecked(m in (f.get("modalidades") or []))
        self.urgent.setChecked(bool(f.get("urgente")))
        self.min_slider.setValue(int(f.get("min_budget") or 0))
        self.max_slider.setValue(self.ceiling if f.get("max_budget") is None else min(self.ceiling, int(f["max_budget"])))
        for combo, key in ((self.date_combo, f.get("fecha")), (self.app_combo, f.get("postulantes")), (self.sort, f.get("orden") or "recientes")):
            idx = combo.findData(key)
            combo.setCurrentIndex(max(0, idx))
        for w in widgets:
            w.blockSignals(False)
        self.update_slider_labels()
        self.page = 1
        self.reload()

    def clear(self):
        self.set_filters({})

    def save_search(self):
        f = self.get_filters()
        f.pop("orden", None)
        f.pop("fecha", None)
        f.pop("postulantes", None)
        if not any((f["term"], f["categorias"], f["modalidades"], f["min_budget"], f["max_budget"], f["urgente"])):
            QMessageBox.information(self.shell, "Búsqueda vacía", "Elegí al menos un filtro o escribí algo para guardar la búsqueda.")
            return
        name, ok = QInputDialog.getText(self.shell, "Guardar búsqueda", "Nombre de la búsqueda:", QLineEdit.EchoMode.Normal,
                                        f["term"] or ", ".join(f["categorias"] or f["modalidades"])[:40])
        if not ok or not name.strip():
            return
        try:
            services.save_search(self.user["id"], name.strip(), f)
            toast(self.shell, "Búsqueda guardada. Te avisaremos de trabajos nuevos.")
        except Exception as exc:
            handle(self.shell, "No se pudo guardar la búsqueda", exc)

    def open_searches(self):
        d = SavedSearchesDialog(self.shell, self.user)
        if d.exec() == SavedSearchesDialog.DialogCode.Accepted and d.chosen:
            self.set_filters(d.chosen)

    # ---- columna central
    def build_center(self):
        inner = QWidget()
        inner.setObjectName("page")
        v = QVBoxLayout(inner)
        v.setContentsMargins(0, 0, 6, 14)
        v.setSpacing(14)
        hero = QFrame()
        hero.setObjectName("hero")
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(26, 22, 26, 22)
        hv.setSpacing(8)
        hv.addWidget(lbl("Encontrá tu trabajo ideal", "heroTitle"))
        hv.addWidget(lbl("Explorá las últimas oportunidades y aplicá a las que mejor van con tu perfil.", "heroText", wrap=True))
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("bigSearch")
        self.search.setPlaceholderText("🔍  Buscar por título, habilidad o descripción…")
        self.search.textChanged.connect(self.schedule)
        self.search.returnPressed.connect(self.reload)
        row.addWidget(self.search, 1)
        row.addWidget(btn("Buscar", "heroBtn", self.reload))
        hv.addLayout(row)
        v.addWidget(hero)
        bar = QHBoxLayout()
        self.count = lbl("", "muted")
        bar.addWidget(self.count, 1)
        bar.addWidget(lbl("Ordenar por:", "muted"))
        self.sort = QComboBox()
        for text, key in (("Más recientes", "recientes"), ("Mayor presupuesto", "mayor"), ("Menor presupuesto", "menor"),
                          ("Más populares", "populares"), ("Mayor compatibilidad", "compat")):
            self.sort.addItem(text, key)
        self.sort.currentIndexChanged.connect(self.schedule)
        bar.addWidget(self.sort)
        bar.addWidget(btn("Actualizar", "secondary", self.reload))
        v.addLayout(bar)
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(14)
        v.addLayout(self.list_box)
        pager = QHBoxLayout()
        self.prev_b = btn("‹ Anterior", "secondary", lambda: self.goto(self.page - 1))
        self.next_b = btn("Siguiente ›", "secondary", lambda: self.goto(self.page + 1))
        self.page_label = lbl("", "muted")
        pager.addStretch(1)
        pager.addWidget(self.prev_b)
        pager.addWidget(self.page_label)
        pager.addWidget(self.next_b)
        pager.addStretch(1)
        v.addLayout(pager)
        v.addStretch(1)
        return center_scroll(inner)

    def goto(self, page):
        self.page = max(1, page)
        self.render()

    def reload(self):
        try:
            self.all_jobs = services.search_jobs(self.user["id"], self.get_filters(), self.skills)
        except Exception as exc:
            self.all_jobs = []
            handle(self.shell, "No se pudieron cargar los trabajos", exc)
        self.page = 1
        self.render()
        self.refresh_side()

    def render(self):
        clear_layout(self.list_box)
        n = len(self.all_jobs)
        pages = max(1, -(-n // self.PER_PAGE))
        self.page = min(self.page, pages)
        self.count.setText(f"{n} trabajo(s) encontrado(s)")
        start = (self.page - 1) * self.PER_PAGE
        if not n:
            self.list_box.addWidget(EmptyState("🔎", "No hay trabajos que coincidan",
                                               "Probá quitar algunos filtros o buscar con otras palabras.", "Limpiar filtros", self.clear))
        for job in self.all_jobs[start:start + self.PER_PAGE]:
            self.list_box.addWidget(JobCardV2(self.shell, job, self.on_card_change))
        self.page_label.setText(f"Página {self.page} de {pages}")
        self.prev_b.setEnabled(self.page > 1)
        self.next_b.setEnabled(self.page < pages)

    def on_card_change(self, job, what):
        if what == "apply":
            self.reload()
        else:
            self.refresh_side()

    # ---- columna derecha
    def build_side(self):
        inner = QWidget()
        inner.setObjectName("page")
        v = QVBoxLayout(inner)
        v.setContentsMargins(6, 0, 0, 14)
        v.setSpacing(14)
        self.sug_card = Card(pad=(16, 14, 16, 14), spacing=10)
        self.act_card = Card(pad=(16, 14, 16, 14), spacing=8)
        v.addWidget(self.sug_card)
        v.addWidget(self.act_card)
        v.addStretch(1)
        area = center_scroll(inner)
        area.setFixedWidth(306)
        return area

    def refresh_side(self):
        clear_layout(self.sug_card.lay)
        clear_layout(self.act_card.lay)
        self.sug_card.lay.addWidget(lbl("Trabajos sugeridos", "h3"))
        try:
            sug = services.suggested_jobs(self.user["id"], self.skills, 4)
            reqs = services.my_requests(self.user["id"])
            ints = services.list_interviews(self.user)
            favs = len(services.favorites(self.user["id"]))
        except Exception:
            sug, reqs, ints, favs = [], [], [], 0
        if not self.skills:
            self.sug_card.lay.addWidget(lbl("Completá las habilidades de tu perfil para ver sugerencias y el % de compatibilidad.", "muted", wrap=True))
            self.sug_card.lay.addWidget(btn("Completar perfil", "secondary", lambda: self.shell.go("profile")))
        for j in sug:
            item = QFrame()
            item.setObjectName("card2")
            iv = QVBoxLayout(item)
            iv.setContentsMargins(12, 10, 12, 10)
            iv.setSpacing(3)
            iv.addWidget(lbl(j["titulo"], "h3", wrap=True))
            iv.addWidget(lbl(j["publicador"], "muted"))
            iv.addWidget(lbl(f"{logic.relative_time(j['creado_en'])}  ·  {j['postulantes']} postulantes", "small"))
            r = QHBoxLayout()
            if j["compat"] is not None:
                r.addWidget(badge(f"{j['compat']}%", logic.compat_tone(j["compat"])))
            r.addStretch(1)
            r.addWidget(btn("Ver", "ghost", lambda jid=j["id"]: self.shell.go("detail", job_id=jid)))
            iv.addLayout(r)
            self.sug_card.lay.addWidget(item)
        if self.skills and not sug:
            self.sug_card.lay.addWidget(lbl("No hay sugerencias por ahora.", "muted"))
        a = self.act_card.lay
        a.addWidget(lbl("Mi actividad", "h3"))
        upcoming = [c for c in ints if c["estado"] in ("Pendiente", "Aceptada") and c["fecha"] >= datetime.now()]
        positive = [r for r in reqs if r["estado"] in logic.REQ_POSITIVE]
        for text, value in (("Solicitudes enviadas", len(reqs)), ("Solicitudes aceptadas", len(positive)),
                            ("Entrevistas próximas", len(upcoming)), ("Trabajos guardados", favs)):
            row = QHBoxLayout()
            row.addWidget(lbl(text, "muted"), 1)
            val = lbl(str(value), "h3")
            row.addWidget(val)
            a.addLayout(row)
        a.addWidget(btn("Ver guardados", "ghost", lambda: self.shell.go("favorites")))


# ======================================================================
#  Detalle de un trabajo
# ======================================================================
class JobDetailPage(QWidget):
    def __init__(self, shell, job_id):
        super().__init__()
        self.shell, self.user = shell, shell.user
        root, v = padded_page(shell, "Detalle del trabajo", None, [btn("← Volver", "secondary", lambda: shell.go("jobs"))])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        try:
            job = services.get_job(job_id, self.user["id"], shell.user_skills)
        except Exception as exc:
            job = None
            handle(shell, "No se pudo abrir el trabajo", exc)
        if not job:
            v.addWidget(EmptyState("📭", "Este trabajo ya no está disponible", "Puede que lo hayan cerrado o eliminado.", "Volver a buscar", lambda: shell.go("jobs")))
            v.addStretch(1)
            return
        self.job = job
        card = Card(pad=(24, 20, 24, 22), spacing=12)
        head = QHBoxLayout()
        head.setSpacing(14)
        head.addWidget(Avatar(job["publicador"], 58), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.addWidget(lbl(job["titulo"], "h2", wrap=True))
        who = job["publicador"] + (f"   ·   {logic.stars(job['pub_promedio'], job['pub_resenas'])}" if job["pub_resenas"] else "")
        col.addWidget(lbl(who, "muted"))
        head.addLayout(col, 1)
        if job["urgente"]:
            head.addWidget(badge("Urgente", "danger"), 0, Qt.AlignmentFlag.AlignTop)
        head.addWidget(state_badge(job["estado"]), 0, Qt.AlignmentFlag.AlignTop)
        card.lay.addLayout(head)
        meta = [job["modalidad"], job["categoria"]] + ([job["ubicacion"]] if job.get("ubicacion") else []) + ["publicado " + logic.relative_time(job["creado_en"])]
        card.lay.addWidget(lbl("   •   ".join(meta), "muted"))
        card.lay.addWidget(hsep())
        card.lay.addWidget(lbl("Descripción", "h3"))
        card.lay.addWidget(lbl(job["descripcion"], wrap=True))
        if job["habilidades"]:
            card.lay.addWidget(lbl("Habilidades requeridas", "h3"))
            card.lay.addWidget(chips_row(job["habilidades"], 12))
        price = lbl(logic.money(job["presupuesto"]), "h2")
        price.setStyleSheet(f"color:{th.T['primary_text']}; font-weight:700;")
        card.lay.addWidget(price)
        card.lay.addWidget(lbl(f"👥 {job['postulantes']} postulante(s) hasta ahora", "muted"))
        if job["compat"] is not None:
            card.lay.addWidget(lbl(f"Compatibilidad con tu perfil: {job['compat']}%", "accent"))
            card.lay.addWidget(progress(job["compat"]))
        elif shell.user_skills == "":
            card.lay.addWidget(lbl("Completá las habilidades de tu perfil para ver tu compatibilidad con este trabajo.", "muted", wrap=True))
        card.lay.addWidget(hsep())
        row = QHBoxLayout()
        row.setSpacing(10)
        if job["publicador_id"]:
            row.addWidget(btn("Ver perfil del publicador", "secondary", lambda: open_profile(shell, job["publicador_id"])))
        self.fav = btn("♥ Guardado" if job["es_favorito"] else "♡ Guardar", "secondary", self.toggle_fav)
        row.addWidget(self.fav)
        row.addWidget(btn("⚑ Reportar", "ghost", lambda: shell.report("trabajo", job["id"], job["titulo"])))
        row.addStretch(1)
        row.addWidget(btn("Proponer entrevista", "secondary", self.interview))
        if job["ya_aplico"]:
            done = btn("Ya aplicaste", None)
            done.setEnabled(False)
            row.addWidget(done)
        else:
            row.addWidget(btn("Aplicar ahora", None, self.apply))
        card.lay.addLayout(row)
        v.addWidget(card)
        v.addStretch(1)

    def toggle_fav(self):
        try:
            on = services.toggle_favorite(self.user["id"], self.job["id"])
        except Exception as exc:
            handle(self.shell, "No se pudo guardar", exc)
            return
        self.fav.setText("♥ Guardado" if on else "♡ Guardar")

    def apply(self):
        self.shell.apply_job(self.job, lambda: self.shell.go("detail", job_id=self.job["id"]))

    def interview(self):
        d = InterviewDialog(self.shell, self.user, [{"id": self.job["id"], "titulo": self.job["titulo"]}], job_id=self.job["id"],
                            subtitle=f"«{self.job['titulo']}»")
        if d.exec() == InterviewDialog.DialogCode.Accepted:
            toast(self.shell, "Entrevista propuesta")


# ======================================================================
#  Mis solicitudes
# ======================================================================
REQ_GROUPS = {
    "todas": None,
    "pendientes": ("Pendiente",),
    "revisadas": ("Revisada",),
    "aceptadas": ("Aceptada", "Entrevista"),
    "curso": ("Contratada", "En progreso"),
    "completadas": ("Completada",),
    "rechazadas": ("Rechazada", "Retirada", "Cancelada"),
}
REQ_LABELS = [("todas", "Todas"), ("pendientes", "Pendientes"), ("revisadas", "Revisadas"), ("aceptadas", "Aceptadas"),
              ("curso", "En curso"), ("completadas", "Completadas"), ("rechazadas", "Rechazadas")]


class RequestsPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.user = shell, shell.user
        root, v = padded_page(shell, "Mis solicitudes", "Seguí el estado de los trabajos a los que aplicaste.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        try:
            self.rows = services.my_requests(self.user["id"])
        except Exception as exc:
            self.rows = []
            handle(shell, "No se pudieron cargar las solicitudes", exc)
        self.tabs = PillTabs([(k, l) for k, l in REQ_LABELS])
        for key, label in REQ_LABELS:
            self.tabs.set_label(key, f"{label} ({len(self.filtered(key))})")
        self.tabs.changed.connect(lambda k: self.render())
        v.addWidget(self.tabs)
        self.box = QVBoxLayout()
        self.box.setSpacing(12)
        v.addLayout(self.box)
        v.addStretch(1)
        self.render()

    def filtered(self, key):
        states = REQ_GROUPS[key]
        return [r for r in self.rows if states is None or r["estado"] in states]

    def render(self):
        clear_layout(self.box)
        items = self.filtered(self.tabs.current)
        if not items:
            self.box.addWidget(EmptyState("📨", "No hay solicitudes aquí",
                                          "Cuando apliques a un trabajo, lo vas a ver en esta lista.", "Buscar trabajos", lambda: self.shell.go("jobs")))
        for r in items:
            card = Card(pad=(20, 16, 20, 16), spacing=8)
            head = QHBoxLayout()
            head.addWidget(lbl(r["titulo"], "h3", wrap=True), 1)
            head.addWidget(state_badge(r["estado"]))
            card.lay.addLayout(head)
            card.lay.addWidget(lbl(f"{r['publicador']}   ·   {logic.money(r['presupuesto'])}   ·   enviada {logic.relative_time(r['creado_en'])}", "muted"))
            card.lay.addWidget(lbl(logic.truncate(r["mensaje"], 260), wrap=True))
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addStretch(1)
            if r["estado"] == "Pendiente":
                row.addWidget(btn("Retirar solicitud", "ghost", lambda rid=r["id"]: self.withdraw(rid)))
            row.addWidget(btn("Mensajes", "secondary", lambda rid=r["id"]: ChatDialog(self.shell, self.user, rid).exec()))
            if r["estado"] in ("Revisada", "Aceptada", "Entrevista"):
                row.addWidget(btn("Agendar entrevista", "secondary", lambda rr=r: self.interview(rr)))
            if r["contrato_id"]:
                row.addWidget(btn("Ver contrato", None, lambda cid=r["contrato_id"]: self.contract(cid)))
            card.lay.addLayout(row)
            self.box.addWidget(card)

    def withdraw(self, request_id):
        if QMessageBox.question(self.shell, "Retirar solicitud", "¿Querés retirar esta solicitud?") != QMessageBox.StandardButton.Yes:
            return
        try:
            services.withdraw_request(request_id, self.user)
        except Exception as exc:
            handle(self.shell, "No se pudo retirar", exc)
        self.shell.go("requests")

    def interview(self, r):
        job = [{"id": r["trabajo_id"], "titulo": r["titulo"]}]
        d = InterviewDialog(self.shell, self.user, job, job_id=r["trabajo_id"], solicitud_id=r["id"], subtitle=f"«{r['titulo']}»")
        if d.exec() == InterviewDialog.DialogCode.Accepted:
            toast(self.shell, "Entrevista propuesta")

    def contract(self, contract_id):
        ContractDialog(self.shell, self.user, contract_id=contract_id).exec()
        self.shell.go("requests")


# ======================================================================
#  Mis publicaciones y candidatos
# ======================================================================
class PublicationsPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.user = shell, shell.user
        root, v = padded_page(shell, "Mis publicaciones", "Gestioná tus oportunidades y revisá a quienes aplicaron.",
                              [btn("+ Publicar oportunidad", None, shell.publish_job)])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        try:
            rows = services.my_publications(self.user["id"])
        except Exception as exc:
            rows = []
            handle(shell, "No se pudieron cargar tus publicaciones", exc)
        if not rows:
            v.addWidget(EmptyState("📣", "Todavía no publicaste oportunidades",
                                   "Publicá lo que necesitás y recibí solicitudes de personas con talento.", "Publicar oportunidad", shell.publish_job))
        for job in rows:
            card = Card(pad=(20, 16, 20, 16), spacing=8)
            head = QHBoxLayout()
            head.addWidget(lbl(job["titulo"], "h3", wrap=True), 1)
            if job.get("urgente"):
                head.addWidget(badge("Urgente", "danger"))
            head.addWidget(state_badge(job["estado"]))
            card.lay.addLayout(head)
            card.lay.addWidget(lbl(f"{job['categoria']}   ·   {job['modalidad']}   ·   {logic.money(job['presupuesto'])}   ·   {logic.relative_time(job['creado_en'])}", "muted"))
            card.lay.addWidget(lbl(f"👥 {job['postulantes']} postulante(s)   ·   {job['pendientes']} pendiente(s) por revisar", "accent"))
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addStretch(1)
            row.addWidget(btn("Editar", "secondary", lambda j=job: shell.edit_job(j)))
            if job["estado"] == "Cerrado":
                row.addWidget(btn("Reabrir", "secondary", lambda j=job: self.set_state(j, "Publicado")))
            else:
                row.addWidget(btn("Cerrar", "secondary", lambda j=job: self.set_state(j, "Cerrado")))
            row.addWidget(btn("Ver candidatos", None, lambda j=job: shell.go("candidates", job_id=j["id"])))
            card.lay.addLayout(row)
            v.addWidget(card)
        v.addStretch(1)

    def set_state(self, job, estado):
        try:
            services.set_job_state(self.user, job["id"], estado)
        except Exception as exc:
            handle(self.shell, "No se pudo cambiar el estado", exc)
        self.shell.go("publications")


class CandidatesPage(QWidget):
    def __init__(self, shell, job_id):
        super().__init__()
        self.shell, self.user, self.job_id = shell, shell.user, job_id
        self.job = None
        self.root_page, self.v = padded_page(shell, "Candidatos", None, [btn("← Mis publicaciones", "secondary", lambda: shell.go("publications"))])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.root_page)
        self.box = QVBoxLayout()
        self.box.setSpacing(12)
        self.v.addLayout(self.box)
        self.v.addStretch(1)
        self.load()

    def load(self):
        clear_layout(self.box)
        try:
            self.job = services.get_job(self.job_id, self.user["id"], "")
            cands = services.job_candidates(self.job_id, (self.job or {}).get("habilidades", ""))
        except Exception as exc:
            handle(self.shell, "No se pudieron cargar los candidatos", exc)
            return
        if not self.job or (self.user["rol"] != "admin" and self.job.get("cliente_id") != self.user["id"]):
            self.box.addWidget(EmptyState("🔒", "No tenés acceso a esta publicación", "Solo quien la publicó puede ver a los candidatos."))
            return
        self.box.addWidget(lbl(f"«{self.job['titulo']}» · {len(cands)} candidato(s)", "h3"))
        if not cands:
            self.box.addWidget(EmptyState("🕓", "Todavía nadie aplicó", "Cuando alguien envíe una solicitud la vas a ver aquí y recibirás una notificación."))
        for c in cands:
            self.box.addWidget(self.candidate_card(c))

    def candidate_card(self, c):
        try:
            prof = services.get_profile(c["cliente_id"]) or {}
        except Exception:
            prof = {}
        card = Card(pad=(20, 16, 20, 16), spacing=8)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(Avatar(c["nombre"], 52, c.get("foto_abs")), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(lbl(c["nombre"], "h3"))
        col.addWidget(lbl(c["correo"], "muted"))
        col.addWidget(stars_label(c["promedio"], int(c.get("total_resenas") or 0)))
        head.addLayout(col, 1)
        if c["compat"] is not None:
            head.addWidget(badge(f"{c['compat']}% compatible", logic.compat_tone(c["compat"])), 0, Qt.AlignmentFlag.AlignTop)
        head.addWidget(state_badge(c["estado"]), 0, Qt.AlignmentFlag.AlignTop)
        card.lay.addLayout(head)
        if prof.get("insignias"):
            card.lay.addWidget(badges_row(prof["insignias"]))
        if c["habilidades"]:
            card.lay.addWidget(chips_row(c["habilidades"], 8))
        card.lay.addWidget(lbl("“" + c["mensaje"] + "”", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(btn("Ver perfil", "ghost", lambda: open_profile(self.shell, c["cliente_id"])))
        row.addWidget(btn("Mensajes", "ghost", lambda: ChatDialog(self.shell, self.user, c["id"]).exec()))
        row.addStretch(1)
        state = c["estado"]
        if state == "Pendiente":
            row.addWidget(btn("Marcar revisada", "secondary", lambda: self.change(c, "Revisada")))
        if state in ("Pendiente", "Revisada"):
            row.addWidget(btn("Rechazar", "danger", lambda: self.change(c, "Rechazada")))
            row.addWidget(btn("Aceptar", None, lambda: self.change(c, "Aceptada")))
        if state in ("Aceptada", "Entrevista", "Revisada"):
            row.addWidget(btn("Proponer entrevista", "secondary", lambda: self.interview(c)))
        if state in ("Aceptada", "Entrevista"):
            row.addWidget(btn("Contratar", None, lambda: self.hire(c)))
        if c.get("contrato_id"):
            row.addWidget(btn("Ver contrato", None, lambda: self.open_contract(c["contrato_id"])))
        card.lay.addLayout(row)
        return card

    def change(self, c, estado):
        try:
            services.set_request_state(c["id"], estado, self.user)
        except Exception as exc:
            handle(self.shell, "No se pudo actualizar", exc)
        self.load()

    def interview(self, c):
        job = [{"id": self.job["id"], "titulo": self.job["titulo"]}]
        d = InterviewDialog(self.shell, self.user, job, job_id=self.job["id"], candidate_id=c["cliente_id"],
                            solicitud_id=c["id"], subtitle=f"Entrevista con {c['nombre']}")
        if d.exec() == InterviewDialog.DialogCode.Accepted:
            if c["estado"] in ("Pendiente", "Revisada", "Aceptada"):
                try:
                    services.set_request_state(c["id"], "Entrevista", self.user)
                except Exception:
                    pass
            toast(self.shell, "Entrevista propuesta")
            self.load()

    def hire(self, c):
        req = dict(c, titulo=self.job["titulo"])
        d = ContractDialog(self.shell, self.user, request=req, job_budget=self.job["presupuesto"])
        if d.exec() == ContractDialog.DialogCode.Accepted:
            toast(self.shell, "Contrato creado")
            self.load()

    def open_contract(self, contract_id):
        ContractDialog(self.shell, self.user, contract_id=contract_id).exec()
        self.load()


# ======================================================================
#  Calendario de entrevistas (cliente y administrador)
# ======================================================================
def interview_card(shell, cita, refresh):
    user = shell.user
    card = Card(shadow=False, pad=(16, 12, 16, 12), spacing=5)
    head = QHBoxLayout()
    head.addWidget(lbl(cita["titulo"], "h3", wrap=True), 1)
    head.addWidget(state_badge(cita["estado"]))
    card.lay.addLayout(head)
    card.lay.addWidget(lbl(f"🗓 {logic.fmt_dt(cita['fecha'])}", "accent"))
    if user["rol"] == "admin":
        card.lay.addWidget(lbl(f"Candidato: {cita['candidato']}   ·   Publicador: {cita['publicador']}", "muted"))
    elif user["id"] == cita["cliente_id"]:
        card.lay.addWidget(lbl(f"Publicador: {cita['publicador']}", "muted"))
    else:
        card.lay.addWidget(lbl(f"Candidato: {cita['candidato']}", "muted"))
    if cita.get("notas"):
        card.lay.addWidget(lbl(cita["notas"], wrap=True))
    actions = []

    def act(estado):
        def run():
            try:
                services.set_interview_state(cita["id"], estado, user)
            except Exception as exc:
                handle(shell, "No se pudo actualizar", exc)
            refresh()
        return run
    if logic.can_decide_interview(cita, user):
        actions += [btn("Rechazar", "danger", act("Rechazada")), btn("Aceptar", None, act("Aceptada"))]
    if logic.can_complete_interview(cita, user):
        actions.append(btn("Marcar completada", "secondary", act("Completada")))
    if logic.can_cancel_interview(cita, user):
        actions.append(btn("Cancelar", "ghost", act("Cancelada")))
    if actions:
        row = QHBoxLayout()
        row.addStretch(1)
        for a in actions:
            row.addWidget(a)
        card.lay.addLayout(row)
    return card


class InterviewsPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.user = shell, shell.user
        actions = [] if self.user["rol"] == "admin" else [btn("+ Agendar entrevista", None, self.schedule)]
        sub = ("Revisá las entrevistas propuestas por los candidatos." if self.user["rol"] == "admin" else
               "Tus entrevistas como candidato y como publicador. Tocá un día para ver el detalle.")
        root, v = padded_page(shell, "Calendario de entrevistas", sub, actions)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        try:
            self.rows = services.list_interviews(self.user)
        except Exception as exc:
            self.rows = []
            handle(shell, "No se pudo abrir el calendario", exc)
        body = QHBoxLayout()
        body.setSpacing(20)
        left = Card(pad=(20, 18, 20, 18))
        self.calendar = MonthCalendar()
        self.calendar.set_marks(self.marks())
        self.calendar.dateSelected.connect(lambda d: self.render_day())
        left.lay.addWidget(self.calendar)
        t = th.T
        legend = QHBoxLayout()
        for text, color in (("Pendiente", t["warn"]), ("Aceptada", t["success"]), ("Rechazada/Cancelada", t["danger"]), ("Completada", t["info"])):
            dot = QLabel(f"<span style='color:{color}'>●</span> {text}")
            dot.setStyleSheet("font-size:10pt; background:transparent;")
            legend.addWidget(dot)
        legend.addStretch(1)
        left.lay.addLayout(legend)
        left.lay.addStretch(1)
        body.addWidget(left, 5)
        right = QVBoxLayout()
        right.setSpacing(12)
        self.day_title = lbl("", "h3")
        right.addWidget(self.day_title)
        self.day_box = QVBoxLayout()
        self.day_box.setSpacing(10)
        right.addLayout(self.day_box)
        right.addWidget(lbl("Próximas entrevistas", "h3"))
        self.next_box = QVBoxLayout()
        self.next_box.setSpacing(10)
        right.addLayout(self.next_box)
        right.addStretch(1)
        body.addLayout(right, 6)
        v.addLayout(body)
        v.addStretch(1)
        self.calendar.select(date.today())
        self.render_next()

    def marks(self):
        t = th.T
        color = {"Pendiente": t["warn"], "Aceptada": t["success"], "Rechazada": t["danger"], "Cancelada": t["danger"], "Completada": t["info"]}
        marks = {}
        for c in self.rows:
            marks.setdefault(c["fecha"].date(), []).append(color.get(c["estado"], t["primary"]))
        return marks

    def render_day(self):
        d = self.calendar.selected
        clear_layout(self.day_box)
        self.day_title.setText(f"{logic.DIAS[d.weekday()].capitalize()} {d.day} de {logic.MESES[d.month - 1]}")
        todays = [c for c in self.rows if c["fecha"].date() == d]
        if not todays:
            self.day_box.addWidget(lbl("No hay entrevistas este día.", "muted"))
        for c in todays:
            self.day_box.addWidget(interview_card(self.shell, c, lambda: self.shell.go("interviews")))

    def render_next(self):
        clear_layout(self.next_box)
        upcoming = [c for c in self.rows if c["estado"] in ("Pendiente", "Aceptada") and c["fecha"] >= datetime.now()][:6]
        if not upcoming:
            self.next_box.addWidget(lbl("No tenés entrevistas próximas.", "muted"))
        for c in upcoming:
            self.next_box.addWidget(interview_card(self.shell, c, lambda: self.shell.go("interviews")))

    def schedule(self):
        try:
            jobs = services.jobs_for_scheduling(self.user["id"])
        except Exception as exc:
            handle(self.shell, "No se pudo abrir el agendador", exc)
            return
        if not jobs:
            QMessageBox.information(self.shell, "Sin trabajos disponibles", "No hay trabajos publicados para agendar. Volvé más tarde.")
            return
        d = InterviewDialog(self.shell, self.user, jobs, subtitle="Elegí el trabajo, el día y el horario.")
        if d.exec() == InterviewDialog.DialogCode.Accepted:
            toast(self.shell, "Entrevista propuesta")
            self.shell.go("interviews")


# ======================================================================
#  Contratos
# ======================================================================
class ContractsPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.user = shell, shell.user
        root, v = padded_page(shell, "Contratos", "Trabajos acordados con sus hitos y su progreso.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        try:
            rows = services.my_contracts(self.user)
        except Exception as exc:
            rows = []
            handle(shell, "No se pudieron cargar los contratos", exc)
        if not rows:
            v.addWidget(EmptyState("📑", "Todavía no tenés contratos",
                                   "Cuando aceptes y contrates a un candidato —o te contraten— el contrato aparece aquí."))
        for c in rows:
            card = Card(pad=(20, 16, 20, 16), spacing=7)
            head = QHBoxLayout()
            head.addWidget(lbl(c["titulo"], "h3", wrap=True), 1)
            head.addWidget(state_badge(c["estado"]))
            card.lay.addLayout(head)
            role = "Vos publicaste" if self.user["id"] == c["owner_id"] else "Vos sos el candidato"
            card.lay.addWidget(lbl(f"{role}   ·   {c['publicador']} ↔ {c['candidato']}", "muted"))
            card.lay.addWidget(lbl(f"{logic.money(c['monto_acordado'])}   ·   entrega {logic.fmt_dt(c['fecha_entrega']) or '—'}", "accent"))
            total, ok = c["total_hitos"], c["hitos_ok"]
            pct = round(100 * ok / total) if total else (100 if c["estado"] == "Completado" else 0)
            card.lay.addWidget(lbl(f"{ok} de {total} hito(s) · {pct}%", "muted"))
            card.lay.addWidget(progress(pct))
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(btn("Mensajes", "secondary", lambda c=c: ChatDialog(shell, self.user, c["solicitud_id"]).exec()))
            row.addWidget(btn("Abrir contrato", None, lambda cid=c["id"]: self.open(cid)))
            card.lay.addLayout(row)
            v.addWidget(card)
        v.addStretch(1)

    def open(self, contract_id):
        ContractDialog(self.shell, self.user, contract_id=contract_id).exec()
        self.shell.go("contracts")


# ======================================================================
#  Favoritos
# ======================================================================
class FavoritesPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell = shell
        root, v = padded_page(shell, "Trabajos guardados", "Las oportunidades que marcaste con ♥.",
                              [btn("← Buscar trabajos", "secondary", lambda: shell.go("jobs"))])
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        try:
            jobs = services.favorites(shell.user["id"], shell.user_skills)
        except Exception as exc:
            jobs = []
            handle(shell, "No se pudieron cargar tus favoritos", exc)
        if not jobs:
            v.addWidget(EmptyState("♡", "No guardaste trabajos todavía", "Tocá el corazón de una oferta para guardarla y encontrarla fácil después.",
                                   "Buscar trabajos", lambda: shell.go("jobs")))
        for j in jobs:
            v.addWidget(JobCardV2(shell, j, lambda job, what: shell.go("favorites")))
        v.addStretch(1)


# ======================================================================
#  Mi perfil
# ======================================================================
class ProfilePage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.user = shell, shell.user
        self._ai_worker = None
        root, v = padded_page(shell, "Mi perfil profesional", "Un perfil completo genera más confianza y mejores oportunidades.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        try:
            self.p = services.get_profile(self.user["id"]) or {}
            crit = services.criteria_avgs(self.user["id"])
            reviews = services.reviews_for(self.user["id"])
        except Exception as exc:
            self.p, crit, reviews = {}, {}, []
            handle(shell, "No se pudo cargar tu perfil", exc)
        p = self.p
        body = QHBoxLayout()
        body.setSpacing(20)
        # --- izquierda: resumen
        left = Card(pad=(22, 20, 22, 20), spacing=9)
        left.setFixedWidth(330)
        left.lay.addWidget(Avatar(self.user["nombre"], 104, p.get("foto_abs")), 0, Qt.AlignmentFlag.AlignHCenter)
        name = lbl(self.user["nombre"], "h2")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.lay.addWidget(name)
        mail = lbl(self.user.get("correo", ""), "muted")
        mail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.lay.addWidget(mail)
        left.lay.addWidget(btn("Cambiar foto", "secondary", self.pick_photo), 0, Qt.AlignmentFlag.AlignHCenter)
        st = stars_label(p.get("promedio", 0), p.get("total_resenas", 0))
        st.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.lay.addWidget(st)
        if p.get("insignias"):
            left.lay.addWidget(badges_row(p["insignias"]))
        left.lay.addWidget(hsep())
        pct = p.get("completitud", 0)
        left.lay.addWidget(lbl(f"Perfil completo al {pct}%", "h3"))
        left.lay.addWidget(progress(pct))
        for tip in p.get("faltantes", []):
            left.lay.addWidget(lbl("• " + tip, "muted", wrap=True))
        if pct >= 100:
            left.lay.addWidget(lbl("¡Tu perfil está completo! 🎉", "accent"))
        left.lay.addWidget(hsep())
        left.lay.addWidget(btn("Cambiar contraseña", "secondary", lambda: ChangePasswordDialog(shell, self.user).exec()))
        left.lay.addStretch(1)
        body.addWidget(left, 0, Qt.AlignmentFlag.AlignTop)
        # --- derecha: formulario y reseñas
        right = QVBoxLayout()
        right.setSpacing(16)
        form = Card(pad=(22, 18, 22, 20), spacing=8)
        form.lay.addWidget(lbl("Información pública", "h3"))
        form.lay.addWidget(lbl("Presentación", "muted"))
        self.bio = QTextEdit()
        self.bio.setPlainText(p.get("presentacion", ""))
        self.bio.setMinimumHeight(120)
        self.bio.setPlaceholderText("Contanos sobre vos, tu experiencia y tus objetivos…")
        form.lay.addWidget(self.bio)
        form.lay.addWidget(lbl("Habilidades (separadas por coma)", "muted"))
        self.skills = QLineEdit(p.get("habilidades", ""))
        self.skills.setPlaceholderText("Ej.: electricidad, diseño, Python, albañilería…")
        self.skills.textChanged.connect(self.preview_chips)
        form.lay.addWidget(self.skills)
        self.chips_box = QVBoxLayout()
        form.lay.addLayout(self.chips_box)
        ai_row = QHBoxLayout()
        self.ai_btn = btn("✦ Sugerir habilidades con IA", "secondary", self.suggest)
        ai_row.addWidget(self.ai_btn)
        self.ai_note = lbl("", "small", wrap=True)
        ai_row.addWidget(self.ai_note, 1)
        form.lay.addLayout(ai_row)
        form.lay.addWidget(lbl("Ubicación", "muted"))
        self.location = QLineEdit(p.get("ubicacion", ""))
        self.location.setPlaceholderText("Ciudad o zona")
        form.lay.addWidget(self.location)
        form.lay.addWidget(lbl("Comentario público", "muted"))
        self.comment = QLineEdit(p.get("comentario", ""))
        self.comment.setPlaceholderText("Estado o comentario breve para tu perfil")
        self.comment.setMaxLength(500)
        form.lay.addWidget(self.comment)
        form.lay.addWidget(btn("Guardar perfil", None, self.save), 0, Qt.AlignmentFlag.AlignRight)
        right.addWidget(form)
        rev = Card(pad=(22, 18, 22, 18), spacing=8)
        rev.lay.addWidget(lbl(f"Reseñas recibidas ({len(reviews)})", "h3"))
        for key, label in (("puntualidad", "Puntualidad"), ("calidad", "Calidad"), ("comunicacion", "Comunicación")):
            if key in crit:
                r = QHBoxLayout()
                r.addWidget(lbl(f"{label}  {crit[key]:.1f}/5"), 1)
                r.addWidget(progress(crit[key] * 20), 2)
                rev.lay.addLayout(r)
        if not reviews:
            rev.lay.addWidget(lbl("Todavía no tenés reseñas. Aparecerán cuando completes trabajos.", "muted", wrap=True))
        for r in reviews[:6]:
            rev.lay.addWidget(hsep())
            rev.lay.addWidget(lbl(f"{logic.stars(r['puntuacion'])} · {r['autor']} · {logic.relative_time(r['creado_en'])}", "accent"))
            rev.lay.addWidget(lbl(r["comentario"], wrap=True))
        right.addWidget(rev)
        right.addStretch(1)
        body.addLayout(right, 1)
        v.addLayout(body)
        v.addStretch(1)
        self.preview_chips()

    def preview_chips(self, *_):
        clear_layout(self.chips_box)
        skills = logic.parse_skills(self.skills.text())
        if skills:
            self.chips_box.addWidget(chips_row(self.skills.text(), 12))

    def pick_photo(self):
        path, _ = QFileDialog.getOpenFileName(self.shell, "Elegí tu foto de perfil", "", "Imágenes (*.png *.jpg *.jpeg)")
        if not path:
            return
        try:
            services.set_profile_photo(self.user["id"], path)
        except Exception as exc:
            handle(self.shell, "No se pudo guardar la foto", exc)
            return
        self.shell.profile_changed()
        toast(self.shell, "Foto actualizada")
        self.shell.go("profile")

    def suggest(self):
        text = self.bio.toPlainText() + " " + self.skills.text()
        local = logic.local_suggest_skills(text, self.skills.text())
        current = logic.parse_skills(self.skills.text())
        fallback = ", ".join(current + local)
        worker = ai.PromptWorker(ai.SYSTEM_ES, ai.skills_prompt(self.bio.toPlainText(), self.skills.text()), fallback)

        def done(result, used_ai, notice):
            merged = logic.parse_skills(", ".join(current) + ", " + result) if used_ai else logic.parse_skills(result)
            self.skills.setText(", ".join(merged[:15]))
            self.ai_note.setText(notice or "Habilidades sugeridas. Quitá las que no te representen.")
        ai.run_helper(self, worker, done, self.ai_btn)

    def save(self):
        try:
            services.save_profile(self.user["id"], self.bio.toPlainText().strip(), self.skills.text().strip(),
                                  self.comment.text().strip(), self.location.text().strip())
        except Exception as exc:
            handle(self.shell, "No se pudo guardar el perfil", exc)
            return
        self.shell.profile_changed()
        toast(self.shell, "Perfil guardado")
        self.shell.go("profile")


# ======================================================================
#  Comunidad (perfiles y reseñas)
# ======================================================================
class CommunityPage(QWidget):
    def __init__(self, shell):
        super().__init__()
        self.shell, self.user = shell, shell.user
        root, v = padded_page(shell, "Comunidad", "Conocé a otras personas, mirá su puntuación y dejá reseñas respetuosas.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  Buscar por nombre, habilidad o presentación…")
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(260)
        self.timer.timeout.connect(self.render)
        self.search.textChanged.connect(lambda _: self.timer.start())
        v.addWidget(self.search)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        v.addLayout(self.grid)
        v.addStretch(1)
        self.render()

    def render(self):
        clear_layout(self.grid)
        try:
            people = services.community(self.user["id"], self.search.text())
        except Exception as exc:
            people = []
            handle(self.shell, "No se pudieron cargar los perfiles", exc)
        if not people:
            self.grid.addWidget(EmptyState("👥", "No encontramos perfiles", "Probá con otra búsqueda o volvé más tarde."), 0, 0, 1, 2)
            return
        for i, p in enumerate(people):
            card = Card(pad=(18, 16, 18, 16), spacing=7)
            head = QHBoxLayout()
            head.setSpacing(12)
            head.addWidget(Avatar(p["nombre"], 52, p["foto_abs"]), 0, Qt.AlignmentFlag.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(2)
            col.addWidget(lbl(p["nombre"], "h3"))
            col.addWidget(stars_label(p["promedio"], p["total_resenas"]))
            if p["ubicacion"]:
                col.addWidget(lbl("📍 " + p["ubicacion"], "muted"))
            head.addLayout(col, 1)
            card.lay.addLayout(head)
            if p["insignias"]:
                card.lay.addWidget(badges_row(p["insignias"][:3]))
            if p["habilidades"]:
                card.lay.addWidget(chips_row(p["habilidades"], 4))
            if p["presentacion"]:
                card.lay.addWidget(lbl(logic.truncate(p["presentacion"], 130), "muted", wrap=True))
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addStretch(1)
            row.addWidget(btn("Ver perfil", "secondary", lambda pid=p["id"]: self.view(pid)))
            can = False
            if self.user["rol"] != "admin":
                try:
                    can = services.can_review(self.user["id"], p["id"])
                except Exception:
                    can = False
            review = btn("☆ Reseñar", None if can else "secondary", lambda pid=p["id"], n=p["nombre"]: self.review(pid, n))
            if not can:
                review.setEnabled(False)
                review.setToolTip("Podés reseñar a personas con las que tuviste una solicitud aceptada o un trabajo en común.")
            row.addWidget(review)
            card.lay.addLayout(row)
            self.grid.addWidget(card, i // 2, i % 2)

    def view(self, person_id):
        open_profile(self.shell, person_id)
        self.render()

    def review(self, person_id, name):
        if ReviewDialog(self.shell, self.user, person_id, name).exec() == ReviewDialog.DialogCode.Accepted:
            toast(self.shell, "Reseña guardada")
            self.render()
