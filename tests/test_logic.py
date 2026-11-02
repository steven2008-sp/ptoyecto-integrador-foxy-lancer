"""Pruebas de la lógica pura. Ejecutar: python tests/test_logic.py"""
import os, sys
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import logic
from security import hash_password, verify_password


def test_password():
    h = hash_password("abc123")
    assert verify_password("abc123", h) and not verify_password("x", h)
    assert not verify_password("abc", "basura")


def test_compat():
    assert logic.compat_score("Python, SQL", "python, sql, qt") == 100
    assert logic.compat_score("Python, SQL", "sql") == 50
    assert logic.compat_score("", "sql") is None
    assert logic.compat_score("Python", "") is None


def test_completeness():
    pct, missing = logic.completeness({})
    assert pct == 15 and len(missing) == 5
    full = {"foto": "a.png", "presentacion": "x" * 40, "habilidades": "a,b,c", "ubicacion": "Managua", "comentario": "hola"}
    assert logic.completeness(full) == (100, [])


def test_badges():
    keys = [b[0] for b in logic.compute_badges({"dias_cuenta": 5, "completitud": 95, "total_resenas": 4,
                                               "promedio": 4.8, "completados": 12})]
    assert {"nuevo", "completo", "top", "completados"} <= set(keys)
    assert logic.compute_badges({}) == []


def test_slots():
    s = logic.time_slots("08:00", "09:00", 30)
    assert s == ["08:00", "08:30", "09:00"]


def test_pct_and_buckets():
    assert logic.pct_change(0, 0) is None
    assert logic.pct_change(5, 0) == 100.0
    assert logic.pct_change(15, 10) == 50.0
    now = datetime(2026, 10, 25, 12)
    labels, counts = logic.bucket_counts([now, now], "dia", now)
    assert len(labels) == len(counts) == 14 and counts[-1] == 2 and sum(counts) == 2


def test_filters():
    job = {"titulo": "Logo", "categoria": "Diseño", "modalidad": "Remoto", "presupuesto": 100, "urgente": 0}
    assert logic.job_matches_filters(job, {"term": "logo"})
    assert not logic.job_matches_filters(job, {"categorias": ["Otro"]})
    assert not logic.job_matches_filters(job, {"min_budget": 200})
    assert not logic.job_matches_filters(job, {"urgente": True})
    assert logic.job_matches_filters(job, None)


def test_interview_rules():
    cita = {"estado": "Pendiente", "cliente_id": 1, "owner_id": 2, "propuesta_por": 1}
    assert not logic.can_decide_interview(cita, {"id": 1, "rol": "usuario"})
    assert logic.can_decide_interview(cita, {"id": 2, "rol": "usuario"})
    assert logic.can_decide_interview(cita, {"id": 9, "rol": "admin"})
    assert not logic.can_decide_interview(dict(cita, estado="Aceptada"), {"id": 2})
    assert logic.can_complete_interview(dict(cita, estado="Aceptada"), {"id": 2})


if __name__ == "__main__":
    fails = 0
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            try:
                f(); print("OK  ", n)
            except Exception as e:
                fails += 1; print("FAIL", n, repr(e))
    sys.exit(1 if fails else 0)
