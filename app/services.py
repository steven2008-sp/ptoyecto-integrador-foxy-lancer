"""Capa de datos y reglas de negocio de Foxy Lancer.

Todas las consultas usan parámetros (%s) y cierran la conexión. Ninguna función
borra datos de forma masiva: los cambios son los que el usuario pide.
"""
import json
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime, date, timedelta

from mysql.connector import Error

from database import get_connection
from security import hash_password, verify_password
from . import logic

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")
POSITIVE = logic.REQ_POSITIVE


# ---------------------------------------------------------------- conexión
def fetchall(sql, params=()):
    cn = get_connection()
    try:
        cur = cn.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cn.close()


def fetchone(sql, params=()):
    cn = get_connection()
    try:
        cur = cn.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cn.close()


def execute(sql, params=()):
    """Ejecuta una escritura y devuelve el id insertado (si aplica)."""
    cn = get_connection()
    try:
        cur = cn.cursor()
        cur.execute(sql, params)
        cn.commit()
        return cur.lastrowid
    except Exception:
        cn.rollback()
        raise
    finally:
        cn.close()


@contextmanager
def tx():
    cn = get_connection()
    try:
        cur = cn.cursor(dictionary=True)
        yield cur
        cn.commit()
    except Exception:
        cn.rollback()
        raise
    finally:
        cn.close()


def is_duplicate(exc):
    return isinstance(exc, Error) and getattr(exc, "errno", None) == 1062


def abs_path(rel):
    if not rel:
        return None
    return os.path.join(BASE_DIR, rel.replace("/", os.sep))


# --------------------------------------------------------- bloqueo de login
class LoginGuard:
    """Bloquea temporalmente un correo tras varios intentos fallidos (en memoria)."""

    def __init__(self, max_attempts=5, lock_seconds=600):
        self.max_attempts, self.lock_seconds = max_attempts, lock_seconds
        self._fails, self._locked = {}, {}

    def remaining(self, email):
        until = self._locked.get(email)
        if not until:
            return 0
        left = int(until - time.time())
        if left <= 0:
            self._locked.pop(email, None)
            self._fails.pop(email, None)
            return 0
        return left

    def fail(self, email):
        self._fails[email] = self._fails.get(email, 0) + 1
        if self._fails[email] >= self.max_attempts:
            self._locked[email] = time.time() + self.lock_seconds

    def clear(self, email):
        self._fails.pop(email, None)
        self._locked.pop(email, None)


LOGIN_GUARD = LoginGuard()


# ----------------------------------------------------------- bitácora / avisos
def log(user_id, accion, detalle=""):
    try:
        execute("INSERT INTO bitacora (usuario_id,accion,detalle) VALUES (%s,%s,%s)",
                (user_id, accion, str(detalle)[:400]))
    except Exception:
        pass


def notify(user_id, titulo, mensaje="", tipo="info"):
    if not user_id:
        return
    try:
        execute("INSERT INTO notificaciones (usuario_id,titulo,mensaje,tipo) VALUES (%s,%s,%s,%s)",
                (user_id, str(titulo)[:160], str(mensaje)[:500], tipo))
    except Exception:
        pass


def admin_ids():
    try:
        return [r["id"] for r in fetchall("SELECT id FROM usuarios WHERE rol='admin' AND activo=1")]
    except Exception:
        return []


def notify_admins(titulo, mensaje="", tipo="info"):
    for uid in admin_ids():
        notify(uid, titulo, mensaje, tipo)


def notify_owner_or_admins(owner_id, titulo, mensaje="", tipo="info"):
    if owner_id:
        notify(owner_id, titulo, mensaje, tipo)
    else:
        notify_admins(titulo, mensaje, tipo)


def unread_count(user_id):
    try:
        r = fetchone("SELECT COUNT(*) AS n FROM notificaciones WHERE usuario_id=%s AND leida=0", (user_id,))
        return int(r["n"])
    except Exception:
        return 0


def list_notifications(user_id, limit=40):
    return fetchall("SELECT * FROM notificaciones WHERE usuario_id=%s ORDER BY creado_en DESC, id DESC LIMIT %s",
                    (user_id, int(limit)))


def mark_all_read(user_id):
    execute("UPDATE notificaciones SET leida=1 WHERE usuario_id=%s AND leida=0", (user_id,))


def mark_read(notif_id, user_id):
    execute("UPDATE notificaciones SET leida=1 WHERE id=%s AND usuario_id=%s", (notif_id, user_id))


# ------------------------------------------------------------- preferencias
def get_theme(user_id):
    try:
        r = fetchone("SELECT tema FROM usuarios WHERE id=%s", (user_id,))
        return (r or {}).get("tema") or "claro"
    except Exception:
        return "claro"


def set_theme(user_id, name):
    try:
        execute("UPDATE usuarios SET tema=%s WHERE id=%s", ("oscuro" if name == "oscuro" else "claro", user_id))
    except Exception:
        pass


def onboarding_seen(user_id):
    try:
        r = fetchone("SELECT onboarding_visto AS v FROM usuarios WHERE id=%s", (user_id,))
        return bool((r or {}).get("v"))
    except Exception:
        return True


def set_onboarding_seen(user_id):
    try:
        execute("UPDATE usuarios SET onboarding_visto=1 WHERE id=%s", (user_id,))
    except Exception:
        pass


def change_password(user_id, current, new):
    if len(new) < 8:
        raise ValueError("La nueva contraseña debe tener al menos 8 caracteres.")
    row = fetchone("SELECT password_hash FROM usuarios WHERE id=%s", (user_id,))
    if not row or not verify_password(current, row["password_hash"]):
        raise ValueError("La contraseña actual no es correcta.")
    execute("UPDATE usuarios SET password_hash=%s WHERE id=%s", (hash_password(new), user_id))
    log(user_id, "cambio_contrasena", "")


# ------------------------------------------------------------------- perfiles
def _decorate_user(row):
    row = dict(row)
    row["promedio"] = float(row.get("promedio") or 0)
    row["total_resenas"] = int(row.get("total_resenas") or 0)
    row["completados"] = int(row.get("completados") or 0)
    row["atendidas"] = int(row.get("atendidas") or 0)
    created = row.get("creado_en")
    row["dias_cuenta"] = (datetime.now() - created).days if created else None
    pct, missing = logic.completeness(row)
    row["completitud"], row["faltantes"] = pct, missing
    row["insignias"] = logic.compute_badges(row)
    row["foto_abs"] = abs_path(row.get("foto"))
    return row


USER_STATS_SQL = """SELECT u.id,u.nombre,u.correo,u.rol,u.activo,u.creado_en,
    COALESCE(p.presentacion,'') AS presentacion, COALESCE(p.habilidades,'') AS habilidades,
    COALESCE(p.comentario,'') AS comentario, p.foto AS foto, COALESCE(p.ubicacion,'') AS ubicacion,
    (SELECT COALESCE(AVG(r.puntuacion),0) FROM resenas r WHERE r.trabajador_id=u.id) AS promedio,
    (SELECT COUNT(*) FROM resenas r WHERE r.trabajador_id=u.id) AS total_resenas,
    (SELECT COUNT(*) FROM contratos c JOIN solicitudes s ON s.id=c.solicitud_id
        WHERE s.cliente_id=u.id AND c.estado='Completado') AS completados,
    (SELECT COUNT(*) FROM solicitudes s2 JOIN trabajos t2 ON t2.id=s2.trabajo_id
        WHERE t2.cliente_id=u.id AND s2.actualizado_en IS NOT NULL) AS atendidas,
    (SELECT AVG(TIMESTAMPDIFF(HOUR,s3.creado_en,s3.actualizado_en)) FROM solicitudes s3
        JOIN trabajos t3 ON t3.id=s3.trabajo_id WHERE t3.cliente_id=u.id AND s3.actualizado_en IS NOT NULL) AS horas_resp
    FROM usuarios u LEFT JOIN perfiles p ON p.usuario_id=u.id """


def get_profile(user_id):
    row = fetchone(USER_STATS_SQL + "WHERE u.id=%s", (user_id,))
    return _decorate_user(row) if row else None


def community(user_id, term=""):
    sql = USER_STATS_SQL + "WHERE u.activo=1 AND u.rol='cliente' AND u.id<>%s"
    params = [user_id]
    if term.strip():
        sql += " AND (u.nombre LIKE %s OR p.habilidades LIKE %s OR p.presentacion LIKE %s)"
        like = "%" + term.strip() + "%"
        params += [like, like, like]
    sql += " ORDER BY promedio DESC, u.nombre"
    return [_decorate_user(r) for r in fetchall(sql, tuple(params))]


def save_profile(user_id, presentacion, habilidades, comentario, ubicacion):
    exists = fetchone("SELECT usuario_id FROM perfiles WHERE usuario_id=%s", (user_id,))
    if exists:
        execute("UPDATE perfiles SET presentacion=%s,habilidades=%s,comentario=%s,ubicacion=%s WHERE usuario_id=%s",
                (presentacion, habilidades, comentario, ubicacion, user_id))
    else:
        execute("INSERT INTO perfiles (usuario_id,presentacion,habilidades,comentario,ubicacion) VALUES (%s,%s,%s,%s,%s)",
                (user_id, presentacion, habilidades, comentario, ubicacion))


def set_profile_photo(user_id, source_path):
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        raise ValueError("Usá una imagen PNG o JPG.")
    if os.path.getsize(source_path) > 5 * 1024 * 1024:
        raise ValueError("La imagen supera los 5 MB.")
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    for old in (".png", ".jpg", ".jpeg"):
        try:
            os.remove(os.path.join(UPLOADS_DIR, f"{user_id}{old}"))
        except OSError:
            pass
    dest = os.path.join(UPLOADS_DIR, f"{user_id}{ext}")
    shutil.copyfile(source_path, dest)
    rel = f"uploads/avatars/{user_id}{ext}"
    exists = fetchone("SELECT usuario_id FROM perfiles WHERE usuario_id=%s", (user_id,))
    if exists:
        execute("UPDATE perfiles SET foto=%s WHERE usuario_id=%s", (rel, user_id))
    else:
        execute("INSERT INTO perfiles (usuario_id,foto) VALUES (%s,%s)", (user_id, rel))
    return rel


# --------------------------------------------------------------------- reseñas
def can_review(author_id, target_id):
    r = fetchone(
        """SELECT s.id FROM solicitudes s JOIN trabajos t ON t.id=s.trabajo_id
           WHERE s.estado IN ('Aceptada','Entrevista','Contratada','En progreso','Completada')
           AND ((s.cliente_id=%s AND t.cliente_id=%s) OR (s.cliente_id=%s AND t.cliente_id=%s)) LIMIT 1""",
        (author_id, target_id, target_id, author_id))
    return r is not None


def save_review(author_id, target_id, score, comment, puntualidad=None, calidad=None, comunicacion=None):
    if author_id == target_id:
        raise ValueError("No podés reseñarte a vos mismo.")
    if not can_review(author_id, target_id):
        raise ValueError("Solo podés reseñar a personas con las que tuviste una solicitud aceptada o un trabajo en común.")
    existing = fetchone("SELECT id FROM resenas WHERE trabajador_id=%s AND autor_id=%s", (target_id, author_id))
    if existing:
        execute("""UPDATE resenas SET puntuacion=%s,comentario=%s,puntualidad=%s,calidad=%s,comunicacion=%s,
                   creado_en=CURRENT_TIMESTAMP WHERE id=%s""",
                (score, comment, puntualidad, calidad, comunicacion, existing["id"]))
    else:
        execute("""INSERT INTO resenas (trabajador_id,autor_id,puntuacion,comentario,puntualidad,calidad,comunicacion)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (target_id, author_id, score, comment, puntualidad, calidad, comunicacion))
    notify(target_id, "Recibiste una reseña", f"Te calificaron con {score}/5.", "resena")


def reviews_for(user_id):
    return fetchall(
        """SELECT r.id,r.puntuacion,r.comentario,r.creado_en,r.puntualidad,r.calidad,r.comunicacion,u.nombre AS autor
           FROM resenas r JOIN usuarios u ON u.id=r.autor_id WHERE r.trabajador_id=%s ORDER BY r.creado_en DESC""",
        (user_id,))


def criteria_avgs(user_id):
    r = fetchone("""SELECT AVG(puntualidad) AS puntualidad, AVG(calidad) AS calidad, AVG(comunicacion) AS comunicacion
                    FROM resenas WHERE trabajador_id=%s""", (user_id,))
    return {k: float(v) for k, v in (r or {}).items() if v is not None}


def all_reviews():
    return fetchall(
        """SELECT r.id,r.puntuacion,r.comentario,r.creado_en,a.nombre AS autor,w.nombre AS destinatario
           FROM resenas r JOIN usuarios a ON a.id=r.autor_id JOIN usuarios w ON w.id=r.trabajador_id
           ORDER BY r.creado_en DESC LIMIT 300""")


def delete_review(review_id, admin_id):
    execute("DELETE FROM resenas WHERE id=%s", (review_id,))
    log(admin_id, "eliminar_resena", f"reseña #{review_id}")


# --------------------------------------------------------------------- trabajos
JOB_SELECT = """SELECT t.*, COALESCE(u.nombre,'Foxy Lancer') AS publicador, u.id AS publicador_id,
    (SELECT COUNT(*) FROM solicitudes s WHERE s.trabajo_id=t.id) AS postulantes,
    (SELECT COALESCE(AVG(r.puntuacion),0) FROM resenas r WHERE r.trabajador_id=t.cliente_id) AS pub_promedio,
    (SELECT COUNT(*) FROM resenas r WHERE r.trabajador_id=t.cliente_id) AS pub_resenas,
    (SELECT COUNT(*) FROM solicitudes s WHERE s.trabajo_id=t.id AND s.cliente_id=%s) AS ya_aplico,
    (SELECT COUNT(*) FROM favoritos f WHERE f.trabajo_id=t.id AND f.usuario_id=%s) AS es_favorito
    FROM trabajos t LEFT JOIN usuarios u ON u.id=t.cliente_id """


def _job_row(row, user_skills=""):
    row = dict(row)
    row["pub_promedio"] = float(row.get("pub_promedio") or 0)
    row["postulantes"] = int(row.get("postulantes") or 0)
    row["ya_aplico"] = bool(row.get("ya_aplico"))
    row["es_favorito"] = bool(row.get("es_favorito"))
    row["urgente"] = bool(row.get("urgente"))
    row["presupuesto"] = float(row.get("presupuesto") or 0)
    row["compat"] = logic.compat_score(row.get("habilidades"), user_skills)
    created = row.get("creado_en")
    row["es_nuevo"] = bool(created and (datetime.now() - created).days < 3)
    return row


def search_jobs(user_id, filters=None, user_skills=""):
    f = filters or {}
    where = ["t.estado='Publicado'", "(t.cliente_id IS NULL OR t.cliente_id<>%s)"]
    params = [user_id, user_id, user_id]
    term = (f.get("term") or "").strip()
    if term:
        like = "%" + term + "%"
        where.append("(t.titulo LIKE %s OR t.descripcion LIKE %s OR t.habilidades LIKE %s OR t.categoria LIKE %s)")
        params += [like, like, like, like]
    for key, col in (("categorias", "t.categoria"), ("modalidades", "t.modalidad")):
        vals = f.get(key) or []
        if vals:
            where.append(f"{col} IN ({','.join(['%s'] * len(vals))})")
            params += list(vals)
    if f.get("min_budget") is not None:
        where.append("t.presupuesto>=%s")
        params.append(f["min_budget"])
    if f.get("max_budget") is not None:
        where.append("t.presupuesto<=%s")
        params.append(f["max_budget"])
    fecha = f.get("fecha")
    if fecha:
        now = datetime.now()
        since = datetime.combine(now.date(), datetime.min.time()) if fecha == "hoy" else now - timedelta(days=int(fecha))
        where.append("t.creado_en>=%s")
        params.append(since)
    if f.get("urgente"):
        where.append("t.urgente=1")
    rows = fetchall(JOB_SELECT + "WHERE " + " AND ".join(where) + " ORDER BY t.creado_en DESC", tuple(params))
    jobs = [_job_row(r, user_skills) for r in rows]
    pf = f.get("postulantes")
    if pf == "lt10":
        jobs = [j for j in jobs if j["postulantes"] < 10]
    elif pf == "10-50":
        jobs = [j for j in jobs if 10 <= j["postulantes"] <= 50]
    elif pf == "gt50":
        jobs = [j for j in jobs if j["postulantes"] > 50]
    order = f.get("orden") or "recientes"
    if order == "mayor":
        jobs.sort(key=lambda j: j["presupuesto"], reverse=True)
    elif order == "menor":
        jobs.sort(key=lambda j: j["presupuesto"])
    elif order == "populares":
        jobs.sort(key=lambda j: j["postulantes"], reverse=True)
    elif order == "compat":
        jobs.sort(key=lambda j: (j["compat"] if j["compat"] is not None else -1), reverse=True)
    return jobs


def get_job(job_id, user_id=0, user_skills=""):
    row = fetchone(JOB_SELECT + "WHERE t.id=%s", (user_id, user_id, job_id))
    return _job_row(row, user_skills) if row else None


def budget_ceiling():
    r = fetchone("SELECT COALESCE(MAX(presupuesto),0) AS m FROM trabajos WHERE estado='Publicado'")
    top = float(r["m"] or 0)
    return max(1000, int(((top // 1000) + 1) * 1000))


def category_counts(user_id):
    rows = fetchall("""SELECT categoria, COUNT(*) AS n FROM trabajos WHERE estado='Publicado'
                       AND (cliente_id IS NULL OR cliente_id<>%s) GROUP BY categoria""", (user_id,))
    return {r["categoria"]: int(r["n"]) for r in rows}


def suggested_jobs(user_id, user_skills, limit=5):
    jobs = [j for j in search_jobs(user_id, {}, user_skills) if not j["ya_aplico"]]
    jobs.sort(key=lambda j: ((j["compat"] if j["compat"] is not None else -1), j["creado_en"]), reverse=True)
    return jobs[:limit]


def favorites(user_id, user_skills=""):
    rows = fetchall(JOB_SELECT + "JOIN favoritos fv ON fv.trabajo_id=t.id AND fv.usuario_id=%s "
                    "ORDER BY fv.creado_en DESC", (user_id, user_id, user_id))
    return [_job_row(r, user_skills) for r in rows]


def toggle_favorite(user_id, job_id):
    row = fetchone("SELECT 1 AS x FROM favoritos WHERE usuario_id=%s AND trabajo_id=%s", (user_id, job_id))
    if row:
        execute("DELETE FROM favoritos WHERE usuario_id=%s AND trabajo_id=%s", (user_id, job_id))
        return False
    execute("INSERT INTO favoritos (usuario_id,trabajo_id) VALUES (%s,%s)", (user_id, job_id))
    return True


def my_publications(user_id):
    rows = fetchall(
        """SELECT t.*, (SELECT COUNT(*) FROM solicitudes s WHERE s.trabajo_id=t.id) AS postulantes,
           (SELECT COUNT(*) FROM solicitudes s WHERE s.trabajo_id=t.id AND s.estado='Pendiente') AS pendientes
           FROM trabajos t WHERE t.cliente_id=%s ORDER BY t.creado_en DESC""", (user_id,))
    return rows


def save_job(user, data, job_id=None):
    """Crea o actualiza un trabajo. data: dict con los campos del formulario."""
    values = (data["titulo"], data["categoria"], data["descripcion"], data["habilidades"], data["modalidad"],
              data["presupuesto"], data["estado"], 1 if data.get("urgente") else 0, data.get("ubicacion", ""))
    if job_id:
        owner = fetchone("SELECT cliente_id FROM trabajos WHERE id=%s", (job_id,))
        if not owner:
            raise ValueError("El trabajo ya no existe.")
        if user["rol"] != "admin" and owner["cliente_id"] != user["id"]:
            raise PermissionError("Solo podés editar tus propias publicaciones.")
        execute("""UPDATE trabajos SET titulo=%s,categoria=%s,descripcion=%s,habilidades=%s,modalidad=%s,
                   presupuesto=%s,estado=%s,urgente=%s,ubicacion=%s WHERE id=%s""", values + (job_id,))
        log(user["id"], "editar_trabajo", data["titulo"])
        return job_id
    owner_id = None if user["rol"] == "admin" else user["id"]
    new_id = execute("""INSERT INTO trabajos (titulo,categoria,descripcion,habilidades,modalidad,presupuesto,estado,urgente,ubicacion,cliente_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", values + (owner_id,))
    log(user["id"], "crear_trabajo", data["titulo"])
    if data["estado"] == "Publicado":
        check_alerts_for_job(new_id)
    return new_id


def set_job_state(user, job_id, estado):
    owner = fetchone("SELECT cliente_id,titulo FROM trabajos WHERE id=%s", (job_id,))
    if not owner:
        raise ValueError("El trabajo ya no existe.")
    if user["rol"] != "admin" and owner["cliente_id"] != user["id"]:
        raise PermissionError("Solo podés cambiar tus propias publicaciones.")
    execute("UPDATE trabajos SET estado=%s WHERE id=%s", (estado, job_id))
    log(user["id"], "estado_trabajo", f"{owner['titulo']} → {estado}")


def set_job_urgent(admin, job_id, urgente):
    execute("UPDATE trabajos SET urgente=%s WHERE id=%s", (1 if urgente else 0, job_id))
    log(admin["id"], "urgente_trabajo", f"#{job_id} → {'sí' if urgente else 'no'}")


def delete_job(user, job_id):
    owner = fetchone("SELECT cliente_id,titulo FROM trabajos WHERE id=%s", (job_id,))
    if not owner:
        return
    if user["rol"] != "admin" and owner["cliente_id"] != user["id"]:
        raise PermissionError("Solo podés eliminar tus propias publicaciones.")
    execute("DELETE FROM trabajos WHERE id=%s", (job_id,))
    log(user["id"], "eliminar_trabajo", owner["titulo"])


def admin_jobs(term="", categoria="", estado=""):
    sql = """SELECT t.*, COALESCE(u.nombre,'Foxy Lancer') AS publicador,
             (SELECT COUNT(*) FROM solicitudes s WHERE s.trabajo_id=t.id) AS postulantes
             FROM trabajos t LEFT JOIN usuarios u ON u.id=t.cliente_id WHERE 1=1"""
    params = []
    if term.strip():
        like = "%" + term.strip() + "%"
        sql += " AND (t.titulo LIKE %s OR t.habilidades LIKE %s OR u.nombre LIKE %s)"
        params += [like, like, like]
    if categoria:
        sql += " AND t.categoria=%s"
        params.append(categoria)
    if estado:
        sql += " AND t.estado=%s"
        params.append(estado)
    sql += " ORDER BY t.creado_en DESC"
    return fetchall(sql, tuple(params))


# ------------------------------------------------------------------ alertas
def save_search(user_id, nombre, filtros):
    return execute("INSERT INTO busquedas_guardadas (usuario_id,nombre,filtros) VALUES (%s,%s,%s)",
                   (user_id, nombre[:80], json.dumps(filtros, ensure_ascii=False)))


def list_searches(user_id):
    rows = fetchall("SELECT * FROM busquedas_guardadas WHERE usuario_id=%s ORDER BY creado_en DESC", (user_id,))
    for r in rows:
        try:
            r["filtros"] = json.loads(r["filtros"])
        except Exception:
            r["filtros"] = {}
    return rows


def delete_search(user_id, search_id):
    execute("DELETE FROM busquedas_guardadas WHERE id=%s AND usuario_id=%s", (search_id, user_id))


def check_alerts_for_job(job_id):
    try:
        job = fetchone("SELECT * FROM trabajos WHERE id=%s", (job_id,))
        if not job:
            return
        notified = set()
        for s in fetchall("SELECT * FROM busquedas_guardadas"):
            if s["usuario_id"] == job.get("cliente_id") or s["usuario_id"] in notified:
                continue
            try:
                f = json.loads(s["filtros"])
            except Exception:
                continue
            if logic.job_matches_filters(job, f):
                notified.add(s["usuario_id"])
                notify(s["usuario_id"], "Nuevo trabajo para tu búsqueda",
                       f"«{job['titulo']}» coincide con «{s['nombre']}».", "alerta")
    except Exception:
        pass


# ------------------------------------------------------------------ solicitudes
def apply_to_job(job_id, user, message):
    job = fetchone("SELECT id,titulo,cliente_id,estado FROM trabajos WHERE id=%s", (job_id,))
    if not job or job["estado"] != "Publicado":
        raise ValueError("Este trabajo ya no está disponible.")
    if job["cliente_id"] == user["id"]:
        raise ValueError("No podés aplicar a tu propia publicación.")
    rid = execute("INSERT INTO solicitudes (trabajo_id,cliente_id,mensaje) VALUES (%s,%s,%s)", (job_id, user["id"], message))
    notify_owner_or_admins(job["cliente_id"], "Nueva solicitud recibida",
                           f"{user['nombre']} aplicó a «{job['titulo']}».", "solicitud")
    log(user["id"], "aplicar_trabajo", job["titulo"])
    return rid


def my_requests(user_id):
    return fetchall(
        """SELECT s.*, t.titulo, t.presupuesto, t.modalidad, t.cliente_id AS publicador_id,
           COALESCE(u.nombre,'Foxy Lancer') AS publicador, c.id AS contrato_id, c.estado AS contrato_estado
           FROM solicitudes s JOIN trabajos t ON t.id=s.trabajo_id LEFT JOIN usuarios u ON u.id=t.cliente_id
           LEFT JOIN contratos c ON c.solicitud_id=s.id WHERE s.cliente_id=%s ORDER BY s.creado_en DESC""",
        (user_id,))


def withdraw_request(request_id, user):
    row = fetchone("SELECT estado FROM solicitudes WHERE id=%s AND cliente_id=%s", (request_id, user["id"]))
    if not row or row["estado"] != "Pendiente":
        raise ValueError("Solo podés retirar solicitudes pendientes.")
    execute("UPDATE solicitudes SET estado='Retirada', actualizado_en=NOW() WHERE id=%s", (request_id,))
    log(user["id"], "retirar_solicitud", f"#{request_id}")


def job_candidates(job_id, job_skills=""):
    rows = fetchall(
        """SELECT s.*, u.nombre, u.correo, COALESCE(p.habilidades,'') AS habilidades,
           COALESCE(p.presentacion,'') AS presentacion, p.foto AS foto,
           (SELECT COALESCE(AVG(r.puntuacion),0) FROM resenas r WHERE r.trabajador_id=u.id) AS promedio,
           (SELECT COUNT(*) FROM resenas r WHERE r.trabajador_id=u.id) AS total_resenas,
           c.id AS contrato_id
           FROM solicitudes s JOIN usuarios u ON u.id=s.cliente_id LEFT JOIN perfiles p ON p.usuario_id=u.id
           LEFT JOIN contratos c ON c.solicitud_id=s.id WHERE s.trabajo_id=%s ORDER BY s.creado_en DESC""", (job_id,))
    for r in rows:
        r["promedio"] = float(r["promedio"] or 0)
        r["compat"] = logic.compat_score(job_skills, r["habilidades"])
        r["foto_abs"] = abs_path(r.get("foto"))
    return rows


def set_request_state(request_id, estado, actor):
    """Cambia el estado de una solicitud (dueño del trabajo o admin)."""
    row = fetchone(
        """SELECT s.id,s.cliente_id,s.estado,t.titulo,t.cliente_id AS owner_id FROM solicitudes s
           JOIN trabajos t ON t.id=s.trabajo_id WHERE s.id=%s""", (request_id,))
    if not row:
        raise ValueError("La solicitud ya no existe.")
    if actor["rol"] != "admin" and actor["id"] != row["owner_id"]:
        raise PermissionError("Solo quien publicó el trabajo puede cambiar el estado.")
    execute("UPDATE solicitudes SET estado=%s, actualizado_en=NOW() WHERE id=%s", (estado, request_id))
    notify(row["cliente_id"], f"Tu solicitud fue {estado.lower()}", f"«{row['titulo']}»", "solicitud")
    log(actor["id"], "estado_solicitud", f"#{request_id} → {estado}")


def admin_requests():
    return fetchall(
        """SELECT s.id,s.estado,s.mensaje,s.creado_en,t.titulo,t.modalidad,t.presupuesto,t.cliente_id AS owner_id,
           u.id AS candidato_id,u.nombre AS candidato,u.correo AS candidato_correo,
           COALESCE(o.nombre,'Foxy Lancer') AS publicador
           FROM solicitudes s JOIN trabajos t ON t.id=s.trabajo_id JOIN usuarios u ON u.id=s.cliente_id
           LEFT JOIN usuarios o ON o.id=t.cliente_id ORDER BY s.creado_en DESC LIMIT 500""")


def request_thread_info(request_id):
    return fetchone(
        """SELECT s.id,s.cliente_id,s.estado,t.titulo,t.id AS trabajo_id,t.cliente_id AS owner_id,
           u.nombre AS candidato,COALESCE(o.nombre,'Foxy Lancer') AS publicador
           FROM solicitudes s JOIN trabajos t ON t.id=s.trabajo_id JOIN usuarios u ON u.id=s.cliente_id
           LEFT JOIN usuarios o ON o.id=t.cliente_id WHERE s.id=%s""", (request_id,))


# ---------------------------------------------------------------- mensajes
def get_messages(request_id, user):
    info = request_thread_info(request_id)
    if not info or (user["rol"] != "admin" and user["id"] not in (info["cliente_id"], info["owner_id"])):
        raise PermissionError("No tenés acceso a esta conversación.")
    return fetchall("""SELECT m.id,m.texto,m.creado_en,m.emisor_id,u.nombre FROM mensajes m
                       JOIN usuarios u ON u.id=m.emisor_id WHERE m.solicitud_id=%s ORDER BY m.creado_en, m.id""", (request_id,))


def send_message(request_id, user, text):
    info = request_thread_info(request_id)
    if not info or (user["rol"] != "admin" and user["id"] not in (info["cliente_id"], info["owner_id"])):
        raise PermissionError("No tenés acceso a esta conversación.")
    text = text.strip()
    if not text:
        raise ValueError("Escribí un mensaje.")
    execute("INSERT INTO mensajes (solicitud_id,emisor_id,texto) VALUES (%s,%s,%s)", (request_id, user["id"], text[:2000]))
    if user["id"] == info["cliente_id"]:
        notify_owner_or_admins(info["owner_id"], "Mensaje nuevo", f"{user['nombre']} te escribió sobre «{info['titulo']}».", "mensaje")
    else:
        notify(info["cliente_id"], "Mensaje nuevo", f"{user['nombre']} te escribió sobre «{info['titulo']}».", "mensaje")


# -------------------------------------------------------------- entrevistas
INTERVIEW_SELECT = """SELECT c.*, t.titulo, t.modalidad, t.presupuesto, t.cliente_id AS owner_id,
    u.nombre AS candidato, u.correo AS candidato_correo, COALESCE(o.nombre,'Foxy Lancer') AS publicador
    FROM citas c JOIN trabajos t ON t.id=c.trabajo_id JOIN usuarios u ON u.id=c.cliente_id
    LEFT JOIN usuarios o ON o.id=t.cliente_id """


def list_interviews(user):
    if user["rol"] == "admin":
        return fetchall(INTERVIEW_SELECT + "ORDER BY c.fecha")
    return fetchall(INTERVIEW_SELECT + "WHERE c.cliente_id=%s OR t.cliente_id=%s ORDER BY c.fecha", (user["id"], user["id"]))


def busy_slots(job_id, day):
    start = datetime.combine(day, datetime.min.time())
    rows = fetchall("""SELECT fecha FROM citas WHERE trabajo_id=%s AND fecha>=%s AND fecha<%s
                       AND estado IN ('Pendiente','Aceptada')""", (job_id, start, start + timedelta(days=1)))
    return {r["fecha"].strftime("%H:%M") for r in rows}


def jobs_for_scheduling(user_id):
    return fetchall("""SELECT id,titulo,cliente_id FROM trabajos WHERE estado='Publicado'
                       AND (cliente_id IS NULL OR cliente_id<>%s) ORDER BY titulo""", (user_id,))


def create_interview(job_id, candidate_id, when, notes, proposer, solicitud_id=None):
    if when <= datetime.now():
        raise ValueError("Elegí una fecha y hora futuras.")
    job = fetchone("SELECT id,titulo,cliente_id FROM trabajos WHERE id=%s", (job_id,))
    if not job:
        raise ValueError("El trabajo ya no existe.")
    if when.strftime("%H:%M") in busy_slots(job_id, when.date()):
        raise ValueError("Ese horario ya está ocupado. Elegí otro.")
    cid = execute("""INSERT INTO citas (trabajo_id,cliente_id,fecha,notas,solicitud_id,propuesta_por)
                     VALUES (%s,%s,%s,%s,%s,%s)""", (job_id, candidate_id, when, notes, solicitud_id, proposer["id"]))
    msg = f"«{job['titulo']}» · {logic.fmt_dt(when)}"
    if proposer["id"] == candidate_id:
        notify_owner_or_admins(job["cliente_id"], "Nueva entrevista propuesta", f"{proposer['nombre']}: {msg}", "entrevista")
    else:
        notify(candidate_id, "Te propusieron una entrevista", msg, "entrevista")
    log(proposer["id"], "proponer_entrevista", msg)
    return cid


def set_interview_state(cita_id, estado, actor):
    cita = fetchone(INTERVIEW_SELECT + "WHERE c.id=%s", (cita_id,))
    if not cita:
        raise ValueError("La entrevista ya no existe.")
    allowed = {
        "Aceptada": logic.can_decide_interview, "Rechazada": logic.can_decide_interview,
        "Cancelada": logic.can_cancel_interview, "Completada": logic.can_complete_interview,
    }.get(estado)
    if not allowed or not allowed(cita, actor):
        raise PermissionError("No podés realizar esta acción sobre la entrevista.")
    execute("UPDATE citas SET estado=%s WHERE id=%s", (estado, cita_id))
    if estado == "Aceptada" and cita.get("solicitud_id"):
        execute("""UPDATE solicitudes SET estado='Entrevista', actualizado_en=NOW()
                   WHERE id=%s AND estado IN ('Pendiente','Revisada','Aceptada')""", (cita["solicitud_id"],))
    msg = f"«{cita['titulo']}» · {logic.fmt_dt(cita['fecha'])}"
    for target in {cita["cliente_id"], cita["owner_id"]} - {actor["id"], None}:
        notify(target, f"Entrevista {estado.lower()}", msg, "entrevista")
    if cita["owner_id"] is None and actor["rol"] != "admin":
        notify_admins(f"Entrevista {estado.lower()}", msg, "entrevista")
    log(actor["id"], "estado_entrevista", f"#{cita_id} → {estado}")


# ---------------------------------------------------------------- contratos
CONTRACT_SELECT = """SELECT c.*, s.cliente_id AS candidato_id, s.estado AS solicitud_estado, s.id AS solicitud_id2,
    t.id AS trabajo_id, t.titulo, t.cliente_id AS owner_id, t.modalidad,
    u.nombre AS candidato, u.correo AS candidato_correo, COALESCE(o.nombre,'Foxy Lancer') AS publicador,
    (SELECT COUNT(*) FROM hitos h WHERE h.contrato_id=c.id) AS total_hitos,
    (SELECT COUNT(*) FROM hitos h WHERE h.contrato_id=c.id AND h.completado=1) AS hitos_ok
    FROM contratos c JOIN solicitudes s ON s.id=c.solicitud_id JOIN trabajos t ON t.id=s.trabajo_id
    JOIN usuarios u ON u.id=s.cliente_id LEFT JOIN usuarios o ON o.id=t.cliente_id """


def create_contract(solicitud_id, actor, monto, fecha_entrega, hitos):
    with tx() as cur:
        cur.execute("""SELECT s.id,s.cliente_id,s.estado,t.titulo,t.cliente_id AS owner_id FROM solicitudes s
                       JOIN trabajos t ON t.id=s.trabajo_id WHERE s.id=%s""", (solicitud_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError("La solicitud ya no existe.")
        if actor["rol"] != "admin" and actor["id"] != row["owner_id"]:
            raise PermissionError("Solo quien publicó el trabajo puede contratar.")
        if row["estado"] not in ("Revisada", "Aceptada", "Entrevista"):
            raise ValueError("Primero aceptá la solicitud para poder contratar.")
        cur.execute("SELECT id FROM contratos WHERE solicitud_id=%s", (solicitud_id,))
        if cur.fetchone():
            raise ValueError("Esta solicitud ya tiene un contrato.")
        cur.execute("INSERT INTO contratos (solicitud_id,monto_acordado,fecha_entrega) VALUES (%s,%s,%s)",
                    (solicitud_id, monto, fecha_entrega))
        contract_id = cur.lastrowid
        for h in hitos:
            cur.execute("INSERT INTO hitos (contrato_id,titulo,fecha_limite) VALUES (%s,%s,%s)",
                        (contract_id, h["titulo"][:160], h.get("fecha_limite")))
        cur.execute("UPDATE solicitudes SET estado='Contratada', actualizado_en=NOW() WHERE id=%s", (solicitud_id,))
    notify(row["cliente_id"], "¡Te contrataron!", f"«{row['titulo']}» por {logic.money(monto)}.", "contrato")
    log(actor["id"], "crear_contrato", f"{row['titulo']} · {logic.money(monto)}")
    return contract_id


def get_contract(contract_id):
    c = fetchone(CONTRACT_SELECT + "WHERE c.id=%s", (contract_id,))
    if not c:
        return None
    c["hitos"] = fetchall("SELECT * FROM hitos WHERE contrato_id=%s ORDER BY id", (contract_id,))
    return c


def contract_for_request(request_id):
    r = fetchone("SELECT id FROM contratos WHERE solicitud_id=%s", (request_id,))
    return get_contract(r["id"]) if r else None


def my_contracts(user):
    if user["rol"] == "admin":
        return fetchall(CONTRACT_SELECT + "ORDER BY c.creado_en DESC")
    return fetchall(CONTRACT_SELECT + "WHERE s.cliente_id=%s OR t.cliente_id=%s ORDER BY c.creado_en DESC",
                    (user["id"], user["id"]))


def _contract_manager_check(contract, actor):
    if actor["rol"] != "admin" and actor["id"] != contract["owner_id"]:
        raise PermissionError("Solo quien publicó el trabajo puede gestionar el contrato.")


def _recalc_contract(contract_id):
    c = get_contract(contract_id)
    total, ok = c["total_hitos"], c["hitos_ok"]
    if c["estado"] == "Cancelado":
        return
    if total and ok == total:
        execute("UPDATE contratos SET estado='Completado' WHERE id=%s", (contract_id,))
        execute("UPDATE solicitudes SET estado='Completada', actualizado_en=NOW() WHERE id=%s", (c["solicitud_id"],))
        if c["estado"] != "Completado":
            notify(c["candidato_id"], "Trabajo completado", f"«{c['titulo']}» se marcó como completado. Ya podés dejar una reseña.", "contrato")
            notify_owner_or_admins(c["owner_id"], "Trabajo completado", f"«{c['titulo']}». Ya podés dejar una reseña.", "contrato")
    elif c["estado"] == "Completado":
        execute("UPDATE contratos SET estado='Activo' WHERE id=%s", (contract_id,))
        execute("UPDATE solicitudes SET estado='En progreso', actualizado_en=NOW() WHERE id=%s", (c["solicitud_id"],))
    elif ok and c["solicitud_estado"] == "Contratada":
        execute("UPDATE solicitudes SET estado='En progreso', actualizado_en=NOW() WHERE id=%s", (c["solicitud_id"],))


def toggle_hito(hito_id, done, actor):
    h = fetchone("SELECT contrato_id FROM hitos WHERE id=%s", (hito_id,))
    if not h:
        raise ValueError("El hito ya no existe.")
    contract = get_contract(h["contrato_id"])
    _contract_manager_check(contract, actor)
    if contract["estado"] == "Cancelado":
        raise ValueError("El contrato está cancelado.")
    execute("UPDATE hitos SET completado=%s, completado_en=%s WHERE id=%s",
            (1 if done else 0, datetime.now() if done else None, hito_id))
    _recalc_contract(h["contrato_id"])
    log(actor["id"], "hito", f"#{hito_id} → {'completado' if done else 'pendiente'}")


def add_hito(contract_id, actor, titulo, fecha_limite=None):
    contract = get_contract(contract_id)
    _contract_manager_check(contract, actor)
    if not titulo.strip():
        raise ValueError("Escribí el título del hito.")
    execute("INSERT INTO hitos (contrato_id,titulo,fecha_limite) VALUES (%s,%s,%s)", (contract_id, titulo.strip()[:160], fecha_limite))
    _recalc_contract(contract_id)


def start_contract(contract_id, actor):
    contract = get_contract(contract_id)
    _contract_manager_check(contract, actor)
    if contract["estado"] == "Activo" and contract["solicitud_estado"] == "Contratada":
        execute("UPDATE solicitudes SET estado='En progreso', actualizado_en=NOW() WHERE id=%s", (contract["solicitud_id"],))
        notify(contract["candidato_id"], "Trabajo en progreso", f"«{contract['titulo']}» comenzó.", "contrato")


def complete_contract(contract_id, actor):
    contract = get_contract(contract_id)
    _contract_manager_check(contract, actor)
    if contract["estado"] == "Completado":
        return
    execute("UPDATE hitos SET completado=1, completado_en=NOW() WHERE contrato_id=%s AND completado=0", (contract_id,))
    execute("UPDATE contratos SET estado='Completado' WHERE id=%s", (contract_id,))
    execute("UPDATE solicitudes SET estado='Completada', actualizado_en=NOW() WHERE id=%s", (contract["solicitud_id"],))
    notify(contract["candidato_id"], "Trabajo completado", f"«{contract['titulo']}». Ya podés dejar una reseña.", "contrato")
    log(actor["id"], "completar_contrato", contract["titulo"])


def cancel_contract(contract_id, actor):
    contract = get_contract(contract_id)
    _contract_manager_check(contract, actor)
    execute("UPDATE contratos SET estado='Cancelado' WHERE id=%s", (contract_id,))
    execute("UPDATE solicitudes SET estado='Cancelada', actualizado_en=NOW() WHERE id=%s", (contract["solicitud_id"],))
    notify(contract["candidato_id"], "Contrato cancelado", f"«{contract['titulo']}».", "contrato")
    log(actor["id"], "cancelar_contrato", contract["titulo"])


# ------------------------------------------------------------------ reportes
def create_report(author_id, tipo, objetivo_id, motivo, comentario):
    rid = execute("INSERT INTO reportes (autor_id,tipo,objetivo_id,motivo,comentario) VALUES (%s,%s,%s,%s,%s)",
                  (author_id, tipo, objetivo_id, motivo[:120], comentario))
    notify_admins("Nuevo reporte", f"{motivo} ({tipo} #{objetivo_id})", "reporte")
    log(author_id, "reportar", f"{tipo} #{objetivo_id}: {motivo}")
    return rid


def list_reports(estado=""):
    sql = """SELECT r.*, a.nombre AS autor,
             CASE WHEN r.tipo='trabajo' THEN (SELECT titulo FROM trabajos WHERE id=r.objetivo_id)
                  ELSE (SELECT nombre FROM usuarios WHERE id=r.objetivo_id) END AS objetivo
             FROM reportes r JOIN usuarios a ON a.id=r.autor_id"""
    params = ()
    if estado:
        sql += " WHERE r.estado=%s"
        params = (estado,)
    return fetchall(sql + " ORDER BY r.creado_en DESC LIMIT 300", params)


def set_report_state(report_id, estado, admin):
    execute("UPDATE reportes SET estado=%s WHERE id=%s", (estado, report_id))
    log(admin["id"], "estado_reporte", f"#{report_id} → {estado}")


# ------------------------------------------------------------------- admin
def admin_users(term=""):
    sql = """SELECT u.id,u.nombre,u.correo,u.rol,u.activo,u.creado_en,
             (SELECT COUNT(*) FROM trabajos t WHERE t.cliente_id=u.id) AS publicaciones,
             (SELECT COUNT(*) FROM solicitudes s WHERE s.cliente_id=u.id) AS solicitudes,
             (SELECT COUNT(*) FROM resenas r WHERE r.trabajador_id=u.id) AS resenas
             FROM usuarios u WHERE 1=1"""
    params = []
    if term.strip():
        like = "%" + term.strip() + "%"
        sql += " AND (u.nombre LIKE %s OR u.correo LIKE %s)"
        params += [like, like]
    return fetchall(sql + " ORDER BY u.creado_en DESC", tuple(params))


def set_user_active(admin, user_id, active):
    if admin["id"] == user_id:
        raise ValueError("No podés desactivar tu propia cuenta.")
    execute("UPDATE usuarios SET activo=%s WHERE id=%s", (1 if active else 0, user_id))
    log(admin["id"], "usuario_activo", f"#{user_id} → {'activo' if active else 'inactivo'}")


def set_user_role(admin, user_id, role):
    if admin["id"] == user_id:
        raise ValueError("No podés cambiar tu propio rol.")
    if role not in ("cliente", "admin"):
        raise ValueError("Rol no válido.")
    execute("UPDATE usuarios SET rol=%s WHERE id=%s", (role, user_id))
    log(admin["id"], "usuario_rol", f"#{user_id} → {role}")


def user_activity(user_id, limit=40):
    return fetchall("SELECT accion,detalle,creado_en FROM bitacora WHERE usuario_id=%s ORDER BY creado_en DESC, id DESC LIMIT %s",
                    (user_id, int(limit)))


def bitacora_list(term="", accion=""):
    sql = """SELECT b.id,b.accion,b.detalle,b.creado_en,COALESCE(u.nombre,'Sistema') AS usuario
             FROM bitacora b LEFT JOIN usuarios u ON u.id=b.usuario_id WHERE 1=1"""
    params = []
    if accion:
        sql += " AND b.accion=%s"
        params.append(accion)
    if term.strip():
        like = "%" + term.strip() + "%"
        sql += " AND (b.detalle LIKE %s OR u.nombre LIKE %s)"
        params += [like, like]
    return fetchall(sql + " ORDER BY b.creado_en DESC, b.id DESC LIMIT 400", tuple(params))


def bitacora_actions():
    return [r["accion"] for r in fetchall("SELECT DISTINCT accion FROM bitacora ORDER BY accion")]


def _period_counts(table, col, where=""):
    now = datetime.now()
    a, b = now - timedelta(days=30), now - timedelta(days=60)
    r = fetchone(f"SELECT COUNT(*) AS total, SUM({col}>=%s) AS cur, SUM({col}>=%s AND {col}<%s) AS prev "
                 f"FROM {table} {where}", (a, b, a))
    return int(r["total"] or 0), int(r["cur"] or 0), int(r["prev"] or 0)


def dashboard_kpis():
    users_t, users_c, users_p = _period_counts("usuarios", "creado_en")
    jobs_t, jobs_c, jobs_p = _period_counts("trabajos", "creado_en", "WHERE estado='Publicado'")
    req_t, req_c, req_p = _period_counts("solicitudes", "creado_en")
    cit_t, cit_c, cit_p = _period_counts("citas", "creado_en", "WHERE estado='Pendiente'")
    now = datetime.now()
    a, b = now - timedelta(days=30), now - timedelta(days=60)
    m = fetchone("""SELECT COALESCE(SUM(presupuesto),0) AS total,
                    COALESCE(SUM(CASE WHEN creado_en>=%s THEN presupuesto ELSE 0 END),0) AS cur,
                    COALESCE(SUM(CASE WHEN creado_en>=%s AND creado_en<%s THEN presupuesto ELSE 0 END),0) AS prev
                    FROM trabajos WHERE estado='Publicado'""", (a, b, a))
    rate = fetchone("""SELECT SUM(estado IN ('Aceptada','Entrevista','Contratada','En progreso','Completada')) AS ok,
                       SUM(estado IN ('Aceptada','Entrevista','Contratada','En progreso','Completada','Rechazada')) AS decided
                       FROM solicitudes""")
    ok, decided = int(rate["ok"] or 0), int(rate["decided"] or 0)
    return [
        {"key": "usuarios", "title": "Usuarios registrados", "value": f"{users_t:,}", "delta": logic.pct_change(users_c, users_p)},
        {"key": "trabajos", "title": "Trabajos publicados", "value": f"{jobs_t:,}", "delta": logic.pct_change(jobs_c, jobs_p)},
        {"key": "solicitudes", "title": "Solicitudes totales", "value": f"{req_t:,}", "delta": logic.pct_change(req_c, req_p)},
        {"key": "citas", "title": "Entrevistas pendientes", "value": f"{cit_t:,}", "delta": logic.pct_change(cit_c, cit_p)},
        {"key": "presupuesto", "title": "Presupuesto publicado", "value": logic.money(m["total"]).replace(".00", ""),
         "delta": logic.pct_change(m["cur"], m["prev"])},
        {"key": "aceptacion", "title": "Tasa de aceptación", "value": f"{(100 * ok / decided):.0f}%" if decided else "—", "delta": None},
    ]


def activity_series(period):
    now = datetime.now()
    horizon = {"dia": 14, "semana": 56, "mes": 190}[period]
    since = now - timedelta(days=horizon)
    req = [r["creado_en"] for r in fetchall("SELECT creado_en FROM solicitudes WHERE creado_en>=%s", (since,))]
    jobs = [r["creado_en"] for r in fetchall("SELECT creado_en FROM trabajos WHERE creado_en>=%s", (since,))]
    labels, req_counts = logic.bucket_counts(req, period, now)
    _, job_counts = logic.bucket_counts(jobs, period, now)
    return labels, req_counts, job_counts


def jobs_by_category():
    rows = fetchall("SELECT categoria, COUNT(*) AS n FROM trabajos WHERE estado='Publicado' GROUP BY categoria ORDER BY n DESC")
    return [(r["categoria"], int(r["n"])) for r in rows]


def requests_by_state():
    rows = fetchall("SELECT estado, COUNT(*) AS n FROM solicitudes GROUP BY estado ORDER BY n DESC")
    return [(r["estado"], int(r["n"])) for r in rows]


def users_new_vs_returning():
    cutoff = datetime.now() - timedelta(days=30)
    r = fetchone("SELECT SUM(creado_en>=%s) AS nuevos, SUM(creado_en<%s) AS recurrentes FROM usuarios WHERE rol='cliente'",
                 (cutoff, cutoff))
    return int(r["nuevos"] or 0), int(r["recurrentes"] or 0)


# ----------------------------------------------------------- datos para informes
def export_dataset(kind, date_from=None, date_to=None):
    """Devuelve (encabezados, filas) para Excel/PDF."""
    def rng(col):
        sql, params = "", []
        if date_from:
            sql += f" AND {col}>=%s"
            params.append(datetime.combine(date_from, datetime.min.time()))
        if date_to:
            sql += f" AND {col}<%s"
            params.append(datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
        return sql, params

    if kind == "usuarios":
        w, p = rng("u.creado_en")
        rows = fetchall(f"SELECT u.id,u.nombre,u.correo,u.rol,u.activo,u.creado_en FROM usuarios u WHERE 1=1{w} ORDER BY u.creado_en DESC", tuple(p))
        return (["ID", "Nombre", "Correo", "Rol", "Activo", "Registro"],
                [[r["id"], r["nombre"], r["correo"], r["rol"], "Sí" if r["activo"] else "No", logic.fmt_dt(r["creado_en"])] for r in rows])
    if kind == "trabajos":
        w, p = rng("t.creado_en")
        rows = fetchall(f"""SELECT t.id,t.titulo,t.categoria,t.modalidad,t.presupuesto,t.estado,t.urgente,t.creado_en,
                            COALESCE(u.nombre,'Foxy Lancer') AS publicador FROM trabajos t LEFT JOIN usuarios u ON u.id=t.cliente_id
                            WHERE 1=1{w} ORDER BY t.creado_en DESC""", tuple(p))
        return (["ID", "Título", "Categoría", "Modalidad", "Presupuesto (C$)", "Estado", "Urgente", "Publicador", "Fecha"],
                [[r["id"], r["titulo"], r["categoria"], r["modalidad"], float(r["presupuesto"]), r["estado"],
                  "Sí" if r["urgente"] else "No", r["publicador"], logic.fmt_dt(r["creado_en"])] for r in rows])
    if kind == "solicitudes":
        w, p = rng("s.creado_en")
        rows = fetchall(f"""SELECT s.id,s.estado,s.creado_en,t.titulo,u.nombre AS candidato,u.correo FROM solicitudes s
                            JOIN trabajos t ON t.id=s.trabajo_id JOIN usuarios u ON u.id=s.cliente_id
                            WHERE 1=1{w} ORDER BY s.creado_en DESC""", tuple(p))
        return (["ID", "Trabajo", "Candidato", "Correo", "Estado", "Fecha"],
                [[r["id"], r["titulo"], r["candidato"], r["correo"], r["estado"], logic.fmt_dt(r["creado_en"])] for r in rows])
    if kind == "entrevistas":
        w, p = rng("c.fecha")
        rows = fetchall(f"""SELECT c.id,c.fecha,c.estado,t.titulo,u.nombre AS candidato FROM citas c
                            JOIN trabajos t ON t.id=c.trabajo_id JOIN usuarios u ON u.id=c.cliente_id
                            WHERE 1=1{w} ORDER BY c.fecha DESC""", tuple(p))
        return (["ID", "Trabajo", "Candidato", "Fecha y hora", "Estado"],
                [[r["id"], r["titulo"], r["candidato"], logic.fmt_dt(r["fecha"]), r["estado"]] for r in rows])
    if kind == "contratos":
        w, p = rng("c.creado_en")
        rows = fetchall(CONTRACT_SELECT + f"WHERE 1=1{w} ORDER BY c.creado_en DESC", tuple(p))
        return (["ID", "Trabajo", "Publicador", "Candidato", "Monto (C$)", "Entrega", "Estado", "Hitos"],
                [[r["id"], r["titulo"], r["publicador"], r["candidato"], float(r["monto_acordado"]),
                  logic.fmt_dt(r["fecha_entrega"]), r["estado"], f"{r['hitos_ok']}/{r['total_hitos']}"] for r in rows])
    raise ValueError("Tipo de informe no válido.")


# ------------------------------------------------------------ ayudas de pantalla
def related_user_ids(user_id):
    """Personas con las que el usuario tuvo una solicitud aceptada o un trabajo en común."""
    rows = fetchall(
        """SELECT DISTINCT CASE WHEN s.cliente_id=%s THEN t.cliente_id ELSE s.cliente_id END AS other
           FROM solicitudes s JOIN trabajos t ON t.id=s.trabajo_id
           WHERE s.estado IN ('Aceptada','Entrevista','Contratada','En progreso','Completada')
           AND (s.cliente_id=%s OR t.cliente_id=%s)""", (user_id, user_id, user_id))
    return {r["other"] for r in rows if r["other"]}


def my_activity(user_id):
    enviadas = fetchone("SELECT COUNT(*) AS n FROM solicitudes WHERE cliente_id=%s", (user_id,))["n"]
    aceptadas = fetchone("""SELECT COUNT(*) AS n FROM solicitudes WHERE cliente_id=%s
                            AND estado IN ('Aceptada','Entrevista','Contratada','En progreso','Completada')""", (user_id,))["n"]
    proximas = fetchone("""SELECT COUNT(*) AS n FROM citas c JOIN trabajos t ON t.id=c.trabajo_id
                           WHERE (c.cliente_id=%s OR t.cliente_id=%s) AND c.fecha>=%s AND c.estado IN ('Pendiente','Aceptada')""",
                        (user_id, user_id, datetime.now()))["n"]
    pendientes = fetchone("""SELECT COUNT(*) AS n FROM solicitudes s JOIN trabajos t ON t.id=s.trabajo_id
                             WHERE t.cliente_id=%s AND s.estado='Pendiente'""", (user_id,))["n"]
    return {"enviadas": int(enviadas), "aceptadas": int(aceptadas), "entrevistas": int(proximas), "por_revisar": int(pendientes)}
