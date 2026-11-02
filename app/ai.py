"""Foxy Lancer AI: chat original (sin cambios) + ayudas integradas en los formularios."""
import os
import json
import urllib.request
import urllib.error

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QLineEdit

from . import logic


class AIWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)
    def __init__(self, messages):
        super().__init__()
        self.messages = messages
    def run(self):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            question = self.messages[-1].get("content", "") if self.messages else ""
            q = question.casefold()
            if any(k in q for k in ("calendario", "entrevista", "cita", "agendar")):
                answer = "Para proponer una entrevista, abrí «Calendario de entrevistas», pulsá «Agendar entrevista», elegí el trabajo, seleccioná un día del calendario y ajustá la hora con las flechas. La propuesta queda pendiente hasta que administración la acepte o rechace."
            elif any(k in q for k in ("publicar", "puesto", "trabajador", "oportunidad", "contratar")):
                answer = "Para buscar a alguien que te ayude, entrá en «Publicar una oportunidad», completá título, categoría, descripción, habilidades, modalidad y presupuesto y guardá. Después podés revisar las solicitudes recibidas."
            elif any(k in q for k in ("solicitud", "aplicar", "postular", "trabajo")):
                answer = "En «Buscar trabajos», elegí una oferta, pulsá «Me interesa» y escribí una presentación. Luego consultá el estado en «Mis solicitudes»."
            elif any(k in q for k in ("perfil", "reseña", "valoración")):
                answer = "Desde «Mi perfil» completá tu presentación y habilidades. En «Perfiles y reseñas» podés ver perfiles y dejar valoraciones respetuosas."
            else:
                answer = "Soy el asistente básico local de Foxy Lancer. Puedo orientarte sobre buscar trabajos, publicar oportunidades, solicitudes, entrevistas y perfiles. Para preguntas generales de programación hace falta configurar una clave de OpenAI con crédito disponible."
            self.failed.emit(answer + "\n\nAviso: la IA generativa no está disponible porque falta OPENAI_API_KEY o crédito de API. No compartas tu clave; configurala solo en el archivo .env local.")
            return
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        payload = {"model": model, "messages": [{"role":"system","content":"Eres Foxy Lancer AI, un asistente útil que responde en español por defecto. Ayudas con Foxy Lancer, programación, diseño, tecnología y preguntas generales. No solicites contraseñas ni claves secretas."}] + self.messages[-12:], "temperature":0.5}
        request = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization":"Bearer "+api_key,"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.completed.emit(data["choices"][0]["message"]["content"].strip())
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
                parsed = json.loads(body)
                api_detail = parsed.get("error", {}).get("message", body[:500])
            except Exception:
                api_detail = "La API no devolvió detalles legibles."
            if exc.code == 401:
                advice = "Revisa OPENAI_API_KEY en .env: la clave puede estar incorrecta o revocada."
            elif exc.code == 404:
                advice = "El modelo configurado no está disponible para esta clave. Prueba OPENAI_MODEL=gpt-4o-mini en .env."
            elif exc.code == 429:
                advice = "OpenAI no tiene crédito disponible o alcanzó su límite. La API requiere crédito; ChatGPT Plus no incluye saldo de API. Revisá https://platform.openai.com/settings/organization/billing. Mientras tanto, te dejo una ayuda básica local según tu consulta."
                question = self.messages[-1].get("content", "") if self.messages else ""
                q = question.casefold()
                if any(k in q for k in ("calendario", "entrevista", "cita", "agendar")):
                    fallback = "Para proponer una entrevista: abrí «Calendario de entrevistas», pulsá «Agendar entrevista», elegí un trabajo, seleccioná el día en el calendario y ajustá la hora con las flechas del control. La entrevista queda pendiente hasta que administración la acepte o rechace."
                elif any(k in q for k in ("publicar", "puesto", "trabajador", "oportunidad", "contratar")):
                    fallback = "Para buscar a alguien que te ayude, entrá en «Publicar una oportunidad», completá título, categoría, descripción, habilidades, modalidad y presupuesto, y guardá. Luego podés revisar las solicitudes que recibas."
                elif any(k in q for k in ("solicitud", "aplicar", "postular")):
                    fallback = "En «Buscar trabajos», abrí una oferta que te interese, pulsá «Me interesa» y escribí una presentación. Después podés revisar el estado desde «Mis solicitudes»."
                elif any(k in q for k in ("perfil", "reseña", "valoración")):
                    fallback = "Desde «Mi perfil» podés completar tu presentación y habilidades. En «Perfiles y reseñas» podés conocer otros perfiles y dejar una valoración respetuosa."
                else:
                    fallback = "Puedo orientarte en funciones de Foxy Lancer, como buscar trabajos, publicar oportunidades, solicitudes, entrevistas y perfiles. Para preguntas generales de programación necesito que OpenAI vuelva a tener crédito."
                self.failed.emit(f"{fallback}\n\nAviso: la respuesta anterior es ayuda local porque la API de OpenAI devolvió HTTP 429.\n{advice}")
                return
            else:
                advice = "Comprueba la clave, el modelo y la configuración de la API."
            self.failed.emit(f"Error de OpenAI (HTTP {exc.code}): {api_detail}\n\n{advice}")
        except urllib.error.URLError as exc:
            self.failed.emit(f"No se pudo conectar con OpenAI: {exc.reason}. Comprueba internet o el firewall.")
        except Exception as exc:
            self.failed.emit(f"No se pudo completar la consulta de Foxy Lancer AI: {exc}")

class MyPinesAI(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Foxy Lancer AI")
        self.resize(680, 650)
        self.history = []
        self.worker = None
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("✦ Foxy Lancer AI")
        title.setFont(QFont("Arial", 19, QFont.Weight.Bold))
        title.setStyleSheet("color:#155bd5")
        header.addWidget(title)
        header.addStretch()
        clear = QPushButton("Nueva conversación")
        clear.setObjectName("secondary")
        clear.clicked.connect(self.clear_chat)
        header.addWidget(clear)
        layout.addLayout(header)
        intro = QLabel("Pregúntame sobre Foxy Lancer, programación, diseño o cualquier duda general.")
        intro.setWordWrap(True); intro.setObjectName("muted")
        layout.addWidget(intro)
        self.chat = QTextEdit(); self.chat.setReadOnly(True); self.chat.setMinimumHeight(380)
        self.chat.setStyleSheet("background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:12px;color:#182536;")
        layout.addWidget(self.chat, 1)
        row = QHBoxLayout()
        self.entry = QLineEdit(); self.entry.setPlaceholderText("Escribe tu pregunta...")
        self.entry.returnPressed.connect(self.send)
        self.send_btn = QPushButton("Enviar")
        self.send_btn.clicked.connect(self.send)
        row.addWidget(self.entry, 1); row.addWidget(self.send_btn)
        layout.addLayout(row)
        self.append("Foxy Lancer AI", "¡Hola! Soy tu asistente de Foxy Lancer. Puedo ayudarte con la plataforma, trabajos, solicitudes, entrevistas y dudas generales. La asistencia automática requiere una clave de API activa y crédito disponible en OpenAI.")
    def append(self, who, text):
        safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        color = "#155bd5" if who == "Tú" else "#182536"
        self.chat.append(f'<p><b style="color:{color}">{who}</b><br>{safe}</p>')
    def clear_chat(self):
        self.history = []; self.chat.clear()
        self.append("Foxy Lancer AI", "Nueva conversación iniciada. ¿En qué te ayudo?")
    def send(self):
        text = self.entry.text().strip()
        if not text or (self.worker and self.worker.isRunning()): return
        self.entry.clear(); self.append("Tú", text)
        self.history.append({"role":"user","content":text})
        self.send_btn.setEnabled(False); self.send_btn.setText("Pensando…")
        self.worker = AIWorker(self.history)
        self.worker.completed.connect(self.got_answer)
        self.worker.failed.connect(self.got_error)
        self.worker.start()
    def got_answer(self, answer):
        self.history.append({"role":"assistant","content":answer})
        self.append("Foxy Lancer AI", answer)
        self.send_btn.setEnabled(True); self.send_btn.setText("Enviar")
    def got_error(self, error):
        self.append("Aviso", error)
        self.send_btn.setEnabled(True); self.send_btn.setText("Enviar")


# --------------------------------------------------------------------------
# Ayudas de IA dentro de los formularios (con respaldo local si no hay API).
# --------------------------------------------------------------------------
class PromptWorker(QThread):
    """Pide un texto a OpenAI; si no hay clave o falla, usa el texto local."""
    finished_text = Signal(str, bool, str)   # texto, usó_ia, aviso

    def __init__(self, system, prompt, fallback):
        super().__init__()
        self.system, self.prompt, self.fallback = system, prompt, fallback

    def run(self):
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            self.finished_text.emit(self.fallback, False,
                                    "Sin OPENAI_API_KEY: usé la ayuda local de Foxy Lancer. Revisá el texto antes de enviarlo.")
            return
        payload = {"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "temperature": 0.6,
                   "messages": [{"role": "system", "content": self.system}, {"role": "user", "content": self.prompt}]}
        request = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(payload).encode("utf-8"),
                                         headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=35) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.finished_text.emit(data["choices"][0]["message"]["content"].strip(), True, "")
        except urllib.error.HTTPError as exc:
            self.finished_text.emit(self.fallback, False, f"OpenAI respondió HTTP {exc.code}; usé la ayuda local.")
        except Exception as exc:
            self.finished_text.emit(self.fallback, False, f"No se pudo usar OpenAI ({exc}); usé la ayuda local.")


SYSTEM_ES = "Eres Foxy Lancer AI. Respondes siempre en español, de forma breve, profesional y sin inventar datos."


def application_prompt(user_name, profile, job):
    return (f"Redacta un mensaje corto (máximo 120 palabras) para postularme al trabajo «{job.get('titulo')}». "
            f"Mi nombre: {user_name}. Mis habilidades: {profile.get('habilidades') or 'no indicadas'}. "
            f"Mi presentación: {profile.get('presentacion') or 'no indicada'}. "
            f"Habilidades que pide el trabajo: {job.get('habilidades') or 'no indicadas'}. "
            f"Descripción del trabajo: {job.get('descripcion')}. No uses marcadores ni corchetes.")


def description_prompt(data):
    return (f"Mejora esta descripción de una oferta de trabajo para que sea clara y atractiva (máximo 180 palabras), "
            f"con secciones breves: qué se necesita, habilidades, condiciones. Título: {data['titulo']}. Categoría: {data['categoria']}. "
            f"Modalidad: {data['modalidad']}. Presupuesto: C$ {data['presupuesto']}. Habilidades: {data['habilidades']}. "
            f"Descripción actual: {data['descripcion']}")


def skills_prompt(text, current):
    return (f"A partir de esta presentación profesional sugiere de 5 a 8 habilidades, separadas por comas y sin explicaciones. "
            f"Presentación: {text}. Habilidades actuales: {current}")


def run_helper(owner, worker, on_done, button=None, busy_text="Pensando…"):
    """Arranca un PromptWorker y reactiva el botón al terminar."""
    original = button.text() if button is not None else ""
    if button is not None:
        button.setEnabled(False)
        button.setText(busy_text)

    def finished(text, used_ai, notice):
        if button is not None:
            button.setEnabled(True)
            button.setText(original)
        on_done(text, used_ai, notice)
    worker.finished_text.connect(finished)
    owner._ai_worker = worker       # evita que el hilo se destruya antes de terminar
    worker.start()
