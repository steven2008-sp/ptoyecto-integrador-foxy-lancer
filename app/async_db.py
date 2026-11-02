"""Ejecución segura de operaciones de base de datos en segundo plano.

Capa de rendimiento: permite llamar a cualquier función síncrona de database.py o
services.py sin congelar la interfaz de PySide6. Usa QThreadPool para reutilizar
hilos y evitar la sobrecarga de crear/destruir hilos por operación.

Capa aditiva: no modifica ningún archivo existente.
"""
from __future__ import annotations

import traceback
from typing import Callable, Any, Optional, List, Tuple
from PySide6.QtCore import QThread, QThreadPool, QRunnable, Signal, QObject


class _WorkerSignals(QObject):
    """Señales del trabajador."""
    finished = Signal(object)   # resultado
    error = Signal(str)         # mensaje de error
    started_signal = Signal()   # al iniciar


class _DatabaseRunnable(QRunnable):
    """Tarea ejecutada en QThreadPool."""

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = _WorkerSignals()
        self._result: Any = None
        self._error: Optional[Exception] = None
        self.setAutoDelete(True)

    def run(self) -> None:
        self.signals.started_signal.emit()
        try:
            self._result = self._fn(*self._args, **self._kwargs)
            self.signals.finished.emit(self._result)
        except Exception:  # noqa: BLE001
            self._error = traceback.format_exc()
            self.signals.error.emit(str(self._error))

    @property
    def result(self) -> Any:
        return self._result

    @property
    def exception(self) -> Optional[Exception]:
        return self._error


class DatabaseWorker(QThread):
    """Hilo dedicado (para operaciones que necesitan QThread puro, como IA)."""

    finished = Signal(object)
    error = Signal(str)
    started_signal = Signal()

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self._result: Any = None
        self._error: Optional[Exception] = None

    def run(self) -> None:
        self.started_signal.emit()
        try:
            self._result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(self._result)
        except Exception:  # noqa: BLE001
            self._error = traceback.format_exc()
            self.error.emit(str(self._error))

    @property
    def result(self) -> Any:
        return self._result

    @property
    def exception(self) -> Optional[Exception]:
        return self._error


# Pool global de hilos para operaciones de BD
_thread_pool = QThreadPool.globalInstance()
_thread_pool.setMaxThreadCount(8)


def run_in_thread(fn: Callable, *args, on_result=None, on_error=None, use_pool: bool = True, **kwargs):
    """Ejecuta `fn` en segundo plano sin congelar la UI.

    Ejemplo:
        worker = run_in_thread(services.save_job, user, data,
                               on_result=lambda r: print("Guardado", r),
                               on_error=lambda e: print("Error", e))

    Retorna el worker/runnable (guárdalo para no perder la referencia).
    """
    if use_pool:
        runnable = _DatabaseRunnable(fn, *args, **kwargs)
        if on_result:
            runnable.signals.finished.connect(on_result)
        if on_error:
            runnable.signals.error.connect(on_error)
        _thread_pool.start(runnable)
        return runnable
    else:
        worker = DatabaseWorker(fn, *args, **kwargs)
        if on_result:
            worker.finished.connect(on_result)
        if on_error:
            worker.error.connect(on_error)
        worker.start()
        return worker


# ------------------------------------------------------------------
# Escritura en lotes (batch) para entrada masiva de datos
# ------------------------------------------------------------------
class BatchWriteResult:
    def __init__(self, total: int, success: int, failed: int, errors: List[str]):
        self.total = total
        self.success = success
        self.failed = failed
        self.errors = errors


def run_batch_writes(
    operations: List[Callable],
    on_complete=None,
    on_error=None,
    max_concurrent: int = 4,
):
    """Ejecuta múltiples operaciones de escritura en segundo plano.

    `operations` es una lista de funciones sin argumentos (o con args vía partial).
    Cada una se ejecuta en un hilo del pool. Al terminar, se emite on_complete
    con un BatchWriteResult.
    """
    results = {"success": 0, "failed": 0, "errors": []}
    completed = {"count": 0}
    total = len(operations)
    lock = __import__("threading").Lock()

    def _make_callback(idx):
        def _on_result(result):
            with lock:
                results["success"] += 1
            _check_finish()

        def _on_error(err):
            with lock:
                results["failed"] += 1
                results["errors"].append(err)
            _check_finish()

        return _on_result, _on_error

    def _check_finish():
        with lock:
            completed["count"] += 1
            done = completed["count"] >= total
        if done and on_complete:
            res = BatchWriteResult(
                total=total,
                success=results["success"],
                failed=results["failed"],
                errors=results["errors"],
            )
            on_complete(res)

    for i, op in enumerate(operations):
        on_r, on_e = _make_callback(i)
        run_in_thread(op, use_pool=True, on_result=on_r, on_error=on_e)

