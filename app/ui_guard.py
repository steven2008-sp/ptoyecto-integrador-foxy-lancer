"""Guardas de interfaz para evitar congelamiento durante operaciones de BD.

Utilidades para deshabilitar botones, mostrar indicadores de carga y
restaurar la UI automáticamente cuando termina una operación en segundo plano.

Capa aditiva: no modifica ningún archivo existente.
"""
from __future__ import annotations

from typing import Callable, Optional, List
from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtCore import QObject

from . import async_db


class BusyGuard(QObject):
    """Deshabilita widgets mientras una operación está en curso y los restaura al terminar."""

    def __init__(self, parent: QWidget, widgets: Optional[List[QWidget]] = None):
        super().__init__(parent)
        self.parent = parent
        self.widgets = widgets or []
        self._active_count = 0

    def add(self, widget: QWidget):
        if widget not in self.widgets:
            self.widgets.append(widget)

    def remove(self, widget: QWidget):
        if widget in self.widgets:
            self.widgets.remove(widget)

    def begin(self, label: str = "Procesando…"):
        """Marca el inicio de una operación. Deshabilita los widgets registrados."""
        self._active_count += 1
        self._set_enabled(False)
        self._show_busy(label)

    def end(self, label: str = ""):
        """Marca el fin de una operación. Restaura los widgets."""
        self._active_count = max(0, self._active_count - 1)
        if self._active_count == 0:
            self._set_enabled(True)
            self._hide_busy()

    def _set_enabled(self, enabled: bool):
        for w in self.widgets:
            try:
                w.setEnabled(enabled)
            except Exception:
                pass

    def _show_busy(self, label: str):
        # Si hay un statusBar en la ventana principal, usarlo
        window = self.parent.window() if self.parent else None
        if window and hasattr(window, "statusBar"):
            try:
                window.statusBar().showMessage(f"● {label}")
            except Exception:
                pass

    def _hide_busy(self):
        window = self.parent.window() if self.parent else None
        if window and hasattr(window, "statusBar"):
            try:
                window.statusBar().clearMessage()
            except Exception:
                pass


def run_with_busy_guard(
    fn: Callable,
    *args,
    guard: Optional[BusyGuard] = None,
    busy_label: str = "Procesando…",
    on_result=None,
    on_error=None,
    use_pool: bool = True,
    **kwargs,
):
    """Ejecuta `fn` en segundo plano con protección automática de UI.

    Si se pasa un `guard`, se llama a guard.begin() al iniciar y guard.end()
    al terminar (ya sea con éxito o error).
    """
    if guard:
        guard.begin(busy_label)

    def _on_result(result):
        if guard:
            guard.end()
        if on_result:
            on_result(result)

    def _on_error(err):
        if guard:
            guard.end()
        if on_error:
            on_error(err)

    return async_db.run_in_thread(
        fn, *args, on_result=_on_result, on_error=_on_error, use_pool=use_pool, **kwargs
    )


def disable_during(widget: QWidget, fn: Callable, *args, **kwargs):
    """Deshabilita un widget mientras se ejecuta `fn` en segundo plano."""
    guard = BusyGuard(widget.window() if widget else None, [widget])
    return run_with_busy_guard(fn, *args, guard=guard, **kwargs)
