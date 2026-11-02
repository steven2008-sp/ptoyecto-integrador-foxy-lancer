"""Wrappers asíncronos de las funciones críticas de services.py.

Permite ejecutar operaciones de base de datos en segundo plano sin romper
la API síncrona existente. Cada función acepta los mismos argumentos que la
original, más kwargs opcionales: on_result, on_error, guard, busy_label.

Capa aditiva: no modifica services.py ni ninguna función existente.
"""
from __future__ import annotations

from typing import Callable, Optional, Any
from . import services
from . import async_db
from . import ui_guard


def async_save_job(user, data, job_id=None, **kwargs):
    return async_db.run_in_thread(
        services.save_job, user, data, job_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_apply_to_job(job_id, user, message, **kwargs):
    return async_db.run_in_thread(
        services.apply_to_job, job_id, user, message,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_save_profile(user_id, presentacion, habilidades, comentario, ubicacion, **kwargs):
    return async_db.run_in_thread(
        services.save_profile, user_id, presentacion, habilidades, comentario, ubicacion,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_create_interview(job_id, candidate_id, when, notes, proposer, solicitud_id=None, **kwargs):
    return async_db.run_in_thread(
        services.create_interview, job_id, candidate_id, when, notes, proposer, solicitud_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_save_review(author_id, target_id, score, comment, puntualidad=None, calidad=None, comunicacion=None, **kwargs):
    return async_db.run_in_thread(
        services.save_review, author_id, target_id, score, comment,
        puntualidad, calidad, comunicacion,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_create_report(author_id, tipo, objetivo_id, motivo, comentario, **kwargs):
    return async_db.run_in_thread(
        services.create_report, author_id, tipo, objetivo_id, motivo, comentario,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_change_password(user_id, current, new, **kwargs):
    return async_db.run_in_thread(
        services.change_password, user_id, current, new,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_set_request_state(request_id, estado, actor, **kwargs):
    return async_db.run_in_thread(
        services.set_request_state, request_id, estado, actor,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_set_interview_state(cita_id, estado, actor, **kwargs):
    return async_db.run_in_thread(
        services.set_interview_state, cita_id, estado, actor,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_create_contract(solicitud_id, actor, monto, fecha_entrega, hitos, **kwargs):
    return async_db.run_in_thread(
        services.create_contract, solicitud_id, actor, monto, fecha_entrega, hitos,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_toggle_hito(hito_id, done, actor, **kwargs):
    return async_db.run_in_thread(
        services.toggle_hito, hito_id, done, actor,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_add_hito(contract_id, actor, titulo, fecha_limite=None, **kwargs):
    return async_db.run_in_thread(
        services.add_hito, contract_id, actor, titulo, fecha_limite,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_set_user_active(admin, user_id, active, **kwargs):
    return async_db.run_in_thread(
        services.set_user_active, admin, user_id, active,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_set_user_role(admin, user_id, role, **kwargs):
    return async_db.run_in_thread(
        services.set_user_role, admin, user_id, role,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_set_job_state(user, job_id, estado, **kwargs):
    return async_db.run_in_thread(
        services.set_job_state, user, job_id, estado,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_delete_job(user, job_id, **kwargs):
    return async_db.run_in_thread(
        services.delete_job, user, job_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


# ------------------------------------------------------------------
# Lecturas asíncronas (no bloquean UI al cargar listas grandes)
# ------------------------------------------------------------------
def async_fetch_jobs(user_id, filters=None, user_skills="", **kwargs):
    return async_db.run_in_thread(
        services.search_jobs, user_id, filters, user_skills,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_fetch_profile(user_id, **kwargs):
    return async_db.run_in_thread(
        services.get_profile, user_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_fetch_requests(user_id, **kwargs):
    return async_db.run_in_thread(
        services.my_requests, user_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_fetch_users(term="", **kwargs):
    return async_db.run_in_thread(
        services.admin_users, term,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_fetch_notifications(user_id, **kwargs):
    return async_db.run_in_thread(
        services.list_notifications, user_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_contratar_freelancer(trabajo_id, solicitud_id, freelancer_id, contratante_id, mensaje_rechazo_otros=None, **kwargs):
    return async_db.run_in_thread(
        services.contratar_freelancer, trabajo_id, solicitud_id, freelancer_id, contratante_id, mensaje_rechazo_otros,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_set_user_role_own(user_id, new_role, **kwargs):
    return async_db.run_in_thread(
        services.set_user_role_own, user_id, new_role,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_confirmar_pago(contrato_id, mi_rol, **kwargs):
    return async_db.run_in_thread(
        services.confirmar_pago, contrato_id, None, mi_rol,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_reportar_pago_no_recibido(contrato_id, usuario_id, motivo, **kwargs):
    return async_db.run_in_thread(
        services.reportar_pago_no_recibido, contrato_id, usuario_id, motivo,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_crear_registro_pago_con_envio(contrato_id, monto, usuario_id, **kwargs):
    return async_db.run_in_thread(
        services.crear_registro_pago_con_envio, contrato_id, monto, usuario_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_confirmar_recepcion_pago(contrato_id, usuario_id, **kwargs):
    return async_db.run_in_thread(
        services.confirmar_recepcion_pago, contrato_id, usuario_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_bloquear_usuario(usuario_bloqueado_id, bloqueado_por, motivo, fecha_expiracion=None, **kwargs):
    return async_db.run_in_thread(
        services.bloquear_usuario, usuario_bloqueado_id, bloqueado_por, motivo, fecha_expiracion,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_desbloquear_usuario(usuario_bloqueado_id, desbloqueado_por, **kwargs):
    return async_db.run_in_thread(
        services.desbloquear_usuario, usuario_bloqueado_id, desbloqueado_por,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_crear_compensacion(pago_id, usuario_afectado_id, monto, motivo, aprobado_por=None, **kwargs):
    return async_db.run_in_thread(
        services.crear_compensacion, pago_id, usuario_afectado_id, monto, motivo, aprobado_por,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_aprobar_compensacion(compensacion_id, admin_id, **kwargs):
    return async_db.run_in_thread(
        services.aprobar_compensacion, compensacion_id, admin_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_rechazar_compensacion(compensacion_id, admin_id, motivo_rechazo=None, **kwargs):
    return async_db.run_in_thread(
        services.rechazar_compensacion, compensacion_id, admin_id, motivo_rechazo,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_reportar_usuario(reportado_id, reportado_por, tipo_reporte, motivo, contrato_id=None, solicitud_id=None, evidencia=None, **kwargs):
    return async_db.run_in_thread(
        services.reportar_usuario, reportado_id, reportado_por, tipo_reporte, motivo, contrato_id, solicitud_id, evidencia,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_listar_reportes_usuarios(**kwargs):
    return async_db.run_in_thread(
        services.listar_reportes_usuarios,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_resolver_reporte_usuario(reporte_id, admin_id, accion_tomada, motivo_resolucion=None, **kwargs):
    return async_db.run_in_thread(
        services.resolver_reporte_usuario, reporte_id, admin_id, accion_tomada, motivo_resolucion,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_suspender_usuario_temporal(usuario_id, suspendido_por, motivo, dias=7, **kwargs):
    return async_db.run_in_thread(
        services.suspender_usuario_temporal, usuario_id, suspendido_por, motivo, dias,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_suspender_usuario_permanente(usuario_id, suspendido_por, motivo, **kwargs):
    return async_db.run_in_thread(
        services.suspender_usuario_permanente, usuario_id, suspendido_por, motivo,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_reactivar_usuario(usuario_id, reactivado_por, **kwargs):
    return async_db.run_in_thread(
        services.reactivar_usuario, usuario_id, reactivado_por,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_listar_suspensiones_activas(**kwargs):
    return async_db.run_in_thread(
        services.listar_suspensiones_activas,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_reportar_resena_falsa(resena_id, reportado_por, motivo, **kwargs):
    return async_db.run_in_thread(
        services.reportar_resena_falsa, resena_id, reportado_por, motivo,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_listar_reportes_resenas(**kwargs):
    return async_db.run_in_thread(
        services.listar_reportes_resenas,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_resolver_reporte_resena(reporte_id, admin_id, accion_tomada, **kwargs):
    return async_db.run_in_thread(
        services.resolver_reporte_resena, reporte_id, admin_id, accion_tomada,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_verificar_usuario_suspension_activa(usuario_id, **kwargs):
    return async_db.run_in_thread(
        services.verificar_usuario_suspension_activa, usuario_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_agregar_contacto(usuario_id, contacto_id, nombre_apodo=None, notas=None, **kwargs):
    return async_db.run_in_thread(
        services.agregar_contacto, usuario_id, contacto_id, nombre_apodo, notas,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_eliminar_contacto(usuario_id, contacto_id, **kwargs):
    return async_db.run_in_thread(
        services.eliminar_contacto, usuario_id, contacto_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_listar_contactos_guardados(usuario_id, **kwargs):
    return async_db.run_in_thread(
        services.listar_contactos_guardados, usuario_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )


def async_es_contacto_guardado(usuario_id, contacto_id, **kwargs):
    return async_db.run_in_thread(
        services.es_contacto_guardado, usuario_id, contacto_id,
        on_result=kwargs.get("on_result"),
        on_error=kwargs.get("on_error"),
        use_pool=True,
    )
