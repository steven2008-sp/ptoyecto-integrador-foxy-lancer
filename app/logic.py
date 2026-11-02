"""Lógica pura de Foxy Lancer (sin Qt ni MySQL): fácil de probar.

Aquí viven la compatibilidad trabajo-candidato, la completitud del perfil, las
insignias, los horarios de entrevistas, las series de tiempo del dashboard y los
textos de ayuda local cuando la IA generativa no está disponible.
"""
import re
import unicodedata
from datetime import datetime, date, timedelta

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Estados de solicitud que significan "hubo una relación de trabajo con esa persona".
REQ_POSITIVE = ("Aceptada", "Entrevista", "Contratada", "En progreso", "Completada")
REQ_STATES = ("Pendiente", "Revisada", "Aceptada", "Rechazada", "Entrevista", "Contratada",
              "En progreso", "Completada", "Cancelada", "Retirada")

TONES = {
    "Pendiente": "warn", "Revisada": "info", "Aceptada": "success", "Rechazada": "danger",
    "Entrevista": "info", "Contratada": "success", "En progreso": "info", "Completada": "success",
    "Cancelada": "danger", "Retirada": "neutral", "Publicado": "success", "Borrador": "neutral",
    "Cerrado": "neutral", "Activo": "info", "Completado": "success", "Cancelado": "danger",
    "Nuevo": "warn", "En revisión": "info", "Resuelto": "success", "Descartado": "neutral",
}


def tone_for(state):
    return TONES.get(state, "neutral")


# --------------------------------------------------------------------------- texto
def _norm(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).casefold().strip()


def parse_skills(text):
    """'Python, MySQL; Diseño' -> ['Python', 'MySQL', 'Diseño'] sin repetidos."""
    if not text:
        return []
    out, seen = [], set()
    for part in re.split(r"[,;/\n|]+", str(text)):
        s = part.strip()
        key = _norm(s)
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def initials(name):
    parts = [p for p in re.split(r"\s+", str(name or "").strip()) if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def money(value):
    try:
        return f"C$ {float(value):,.2f}"
    except (TypeError, ValueError):
        return "C$ 0.00"


def truncate(text, n=170):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def stars(score, count=None):
    score = float(score or 0)
    full = int(round(score))
    full = max(0, min(5, full))
    txt = "★" * full + "☆" * (5 - full)
    if count is None:
        return f"{txt} {score:.1f}"
    return f"{txt} {score:.1f} ({count})"


def relative_time(dt, now=None):
    if not dt:
        return ""
    now = now or datetime.now()
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime.combine(dt, datetime.min.time())
    days = (now.date() - dt.date()).days
    if days <= 0:
        return "hoy"
    if days == 1:
        return "ayer"
    if days < 7:
        return f"hace {days} días"
    if days < 30:
        w = days // 7
        return f"hace {w} semana" + ("s" if w > 1 else "")
    if days < 365:
        m = days // 30
        return f"hace {m} mes" + ("es" if m > 1 else "")
    y = days // 365
    return f"hace {y} año" + ("s" if y > 1 else "")


def fmt_dt(dt):
    if not dt:
        return ""
    if isinstance(dt, datetime):
        return dt.strftime("%d/%m/%Y %H:%M")
    return dt.strftime("%d/%m/%Y")


def slot_label(hhmm):
    """'14:30' -> '2:30 pm'."""
    h, m = [int(x) for x in hhmm.split(":")]
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {suffix}"


# --------------------------------------------------------------- compatibilidad
def compat_score(job_skills, user_skills):
    """Porcentaje (0-100) de habilidades del trabajo que cubre el usuario.

    Devuelve None si no hay datos suficientes (el trabajo o el perfil sin habilidades).
    """
    job = [_norm(s) for s in parse_skills(job_skills)]
    usr = [_norm(s) for s in parse_skills(user_skills)]
    if not job or not usr:
        return None
    hits = 0
    for js in job:
        for us in usr:
            if js == us or (len(js) >= 3 and len(us) >= 3 and (js in us or us in js)):
                hits += 1
                break
    return round(100 * hits / len(job))


def compat_tone(score):
    if score is None:
        return "neutral"
    if score >= 70:
        return "success"
    if score >= 40:
        return "warn"
    return "neutral"


# ------------------------------------------------------------ perfil e insignias
def completeness(profile):
    """(porcentaje, sugerencias) según qué tan completo está el perfil."""
    profile = profile or {}
    checks = [
        ("Cuenta creada", 15, True, None),
        ("Foto", 15, bool(profile.get("foto")), "Subí una foto de perfil"),
        ("Presentación", 20, len(str(profile.get("presentacion") or "").strip()) >= 30,
         "Escribí una presentación de al menos 30 caracteres"),
        ("Habilidades", 25, len(parse_skills(profile.get("habilidades"))) >= 3,
         "Agregá por lo menos 3 habilidades"),
        ("Ubicación", 15, bool(str(profile.get("ubicacion") or "").strip()), "Indicá tu ubicación"),
        ("Comentario", 10, bool(str(profile.get("comentario") or "").strip()),
         "Escribí un comentario o estado corto"),
    ]
    pct = sum(w for _, w, ok, _ in checks if ok)
    missing = [tip for _, _, ok, tip in checks if not ok]
    return pct, missing


def compute_badges(stats):
    """Lista de (clave, texto, tono) a partir de estadísticas reales."""
    out = []
    dias = stats.get("dias_cuenta")
    if dias is not None and dias <= 30:
        out.append(("nuevo", "Nuevo talento", "info"))
    if (stats.get("completitud") or 0) >= 90:
        out.append(("completo", "Perfil completo", "success"))
    if (stats.get("total_resenas") or 0) >= 3 and (stats.get("promedio") or 0) >= 4.5:
        out.append(("top", "Top valorado", "warn"))
    done = stats.get("completados") or 0
    for threshold in (25, 10, 5):
        if done >= threshold:
            out.append(("completados", f"{threshold}+ trabajos completados", "success"))
            break
    horas = stats.get("horas_resp")
    if (stats.get("atendidas") or 0) >= 3 and horas is not None and float(horas) <= 24:
        out.append(("rapida", "Respuesta rápida", "info"))
    return out


# ---------------------------------------------------------------- entrevistas
def time_slots(start="08:00", end="17:30", step=30):
    sh, sm = [int(x) for x in start.split(":")]
    eh, em = [int(x) for x in end.split(":")]
    cur, last = sh * 60 + sm, eh * 60 + em
    out = []
    while cur <= last:
        out.append(f"{cur // 60:02d}:{cur % 60:02d}")
        cur += step
    return out


def _proposer(cita):
    return cita.get("propuesta_por") or cita.get("cliente_id")


def can_decide_interview(cita, user):
    """¿Puede este usuario aceptar o rechazar la entrevista?"""
    if cita.get("estado") != "Pendiente":
        return False
    if user.get("rol") == "admin":
        return True
    uid = user.get("id")
    proposer = _proposer(cita)
    if uid == proposer:
        return False
    if proposer == cita.get("cliente_id"):
        return cita.get("owner_id") is not None and uid == cita.get("owner_id")
    return uid == cita.get("cliente_id")


def can_cancel_interview(cita, user):
    if cita.get("estado") not in ("Pendiente", "Aceptada"):
        return False
    uid = user.get("id")
    return user.get("rol") == "admin" or uid in (cita.get("cliente_id"), cita.get("owner_id"))


def can_complete_interview(cita, user):
    if cita.get("estado") != "Aceptada":
        return False
    return user.get("rol") == "admin" or user.get("id") == cita.get("owner_id")


# ------------------------------------------------------------------ dashboard
def pct_change(current, previous):
    current, previous = float(current or 0), float(previous or 0)
    if current == 0 and previous == 0:
        return None
    if previous == 0:
        return 100.0
    return (current - previous) / previous * 100.0


def bucket_counts(datetimes, period, now=None):
    """Cuenta eventos por día (14), semana (8) o mes (6). Devuelve (etiquetas, conteos)."""
    now = now or datetime.now()
    today = now.date()
    labels, starts = [], []
    if period == "dia":
        for i in range(13, -1, -1):
            d = today - timedelta(days=i)
            starts.append(d)
            labels.append(d.strftime("%d/%m"))
        ends = [s + timedelta(days=1) for s in starts]
    elif period == "semana":
        monday = today - timedelta(days=today.weekday())
        for i in range(7, -1, -1):
            d = monday - timedelta(weeks=i)
            starts.append(d)
            labels.append(d.strftime("%d/%m"))
        ends = [s + timedelta(days=7) for s in starts]
    else:
        y, m = today.year, today.month
        months = []
        for _ in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        months.reverse()
        for (yy, mm) in months:
            starts.append(date(yy, mm, 1))
            labels.append(MESES_CORTOS[mm - 1])
        ends = starts[1:] + [date(today.year + (today.month == 12), (today.month % 12) + 1, 1)]
    counts = [0] * len(starts)
    for dt in datetimes:
        if dt is None:
            continue
        d = dt.date() if isinstance(dt, datetime) else dt
        for i, (s, e) in enumerate(zip(starts, ends)):
            if s <= d < e:
                counts[i] += 1
                break
    return labels, counts


# ------------------------------------------------------- búsquedas guardadas
def job_matches_filters(job, f):
    """¿El trabajo cumple los filtros de una búsqueda guardada?"""
    if not f:
        return True
    term = _norm(f.get("term"))
    if term:
        hay = _norm(" ".join(str(job.get(k) or "") for k in ("titulo", "categoria", "descripcion", "habilidades")))
        if term not in hay:
            return False
    cats = f.get("categorias") or []
    if cats and job.get("categoria") not in cats:
        return False
    mods = f.get("modalidades") or []
    if mods and job.get("modalidad") not in mods:
        return False
    price = float(job.get("presupuesto") or 0)
    if f.get("min_budget") is not None and price < float(f["min_budget"]):
        return False
    if f.get("max_budget") is not None and price > float(f["max_budget"]):
        return False
    if f.get("urgente") and not job.get("urgente"):
        return False
    return True


def describe_filters(f):
    parts = []
    if f.get("term"):
        parts.append(f'"{f["term"]}"')
    if f.get("categorias"):
        parts.append(", ".join(f["categorias"]))
    if f.get("modalidades"):
        parts.append(", ".join(f["modalidades"]))
    if f.get("min_budget") is not None or f.get("max_budget") is not None:
        lo = money(f.get("min_budget") or 0)
        hi = money(f["max_budget"]) if f.get("max_budget") is not None else "sin tope"
        parts.append(f"{lo} – {hi}")
    if f.get("urgente"):
        parts.append("Urgente")
    return " · ".join(parts) or "Todos los trabajos"


# ------------------------------------------------- ayuda local (sin IA externa)
_SKILL_HINTS = {
    "web": ["HTML", "CSS", "JavaScript", "Responsive design"],
    "pagina": ["HTML", "CSS", "JavaScript"],
    "react": ["React", "JavaScript", "TypeScript"],
    "python": ["Python", "SQL", "Git"],
    "datos": ["Excel", "SQL", "Power BI", "Python"],
    "excel": ["Excel", "Análisis de datos"],
    "mysql": ["MySQL", "SQL", "Modelado de datos"],
    "base de datos": ["MySQL", "SQL", "Modelado de datos"],
    "movil": ["Flutter", "Android", "UI/UX"],
    "android": ["Kotlin", "Android"],
    "diseno": ["Figma", "UI/UX", "Adobe Photoshop"],
    "logo": ["Illustrator", "Diseño gráfico"],
    "marketing": ["Redes sociales", "SEO", "Copywriting"],
    "redes": ["Community management", "Canva", "Copywriting"],
    "redaccion": ["Redacción", "Corrección de estilo", "SEO"],
    "contenido": ["Redacción", "Copywriting"],
    "soporte": ["Soporte técnico", "Redes", "Windows"],
    "redes de": ["Redes", "Cisco", "Linux"],
    "seguridad": ["Ciberseguridad", "Linux", "Redes"],
    "prueba": ["QA", "Pruebas manuales", "Selenium"],
    "automat": ["Python", "Scripts", "APIs"],
    "electric": ["Electricidad", "Instalaciones"],
    "albanil": ["Albañilería", "Construcción"],
    "ingles": ["Inglés", "Traducción"],
}


def local_suggest_skills(text, current=""):
    have = {_norm(s) for s in parse_skills(current)}
    base = _norm(text)
    out = []
    for key, skills in _SKILL_HINTS.items():
        if key in base:
            for s in skills:
                if _norm(s) not in have and s not in out:
                    out.append(s)
    return out[:8]


def local_application_message(user_name, user_skills, bio, job):
    mine = parse_skills(user_skills)
    needed = parse_skills(job.get("habilidades"))
    shared = [s for s in needed if any(_norm(s) == _norm(m) or _norm(s) in _norm(m) or _norm(m) in _norm(s) for m in mine)]
    lines = [f"Hola, mi nombre es {user_name or 'un candidato'} y me interesa mucho la oportunidad «{job.get('titulo', '')}»."]
    if shared:
        lines.append("Cuento con experiencia en " + ", ".join(shared) + ", que son habilidades que mencionás en la publicación.")
    elif mine:
        lines.append("Mis habilidades principales son " + ", ".join(mine[:5]) + ".")
    bio = (bio or "").strip()
    if bio:
        lines.append(truncate(bio, 220))
    modality = job.get("modalidad")
    if modality:
        lines.append(f"La modalidad {modality.lower()} me funciona bien y puedo coordinar los tiempos de entrega con vos.")
    lines.append("Quedo atento para conversar en una entrevista y resolver cualquier duda. ¡Gracias por tu tiempo!")
    return "\n\n".join(lines)


def local_improve_description(title, category, description, skills, modality, budget):
    desc = (description or "").strip() or "Describí aquí qué necesitás lograr con este trabajo."
    skills_list = parse_skills(skills)
    parts = [f"{title or 'Oportunidad'} ({category or 'General'})", "", "Qué necesitamos:", desc, ""]
    if skills_list:
        parts += ["Habilidades requeridas:"] + [f"• {s}" for s in skills_list] + [""]
    parts += ["Condiciones:", f"• Modalidad: {modality or 'Remoto'}"]
    if budget:
        parts.append(f"• Presupuesto: {money(budget)}")
    parts += ["", "Cómo aplicar: enviá tu solicitud con una breve presentación, tu experiencia relacionada y tu disponibilidad."]
    return "\n".join(parts)


CATEGORIES = ["Frontend", "Backend", "Full Stack", "Aplicaciones móviles", "Bases de datos", "DevOps", "Diseño",
              "Marketing digital", "Contenido y redacción", "Soporte técnico", "Análisis de datos", "QA y pruebas",
              "Ciberseguridad", "Automatización", "Otro"]
MODALITIES = ["Remoto", "Presencial", "Híbrido"]
APP_VERSION = "2.0"
