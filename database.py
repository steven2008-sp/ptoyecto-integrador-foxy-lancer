import os
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass
import mysql.connector
from mysql.connector import Error

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "mypines_db"),
    "connection_timeout": 5,
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

def check_connection():
    connection = None
    try:
        connection = get_connection()
        return True, "Conexión correcta con MySQL."
    except Error as exc:
        return False, str(exc)
    finally:
        if connection is not None and connection.is_connected():
            connection.close()

def run_query(query, params=(), fetch=False, one=False):
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params)
        result = cursor.fetchone() if one else (cursor.fetchall() if fetch else None)
        if not fetch and not one:
            connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_schema():
    """Crea las tablas auxiliares que MyPines necesita sin borrar datos existentes."""
    statements = [
        """CREATE TABLE IF NOT EXISTS citas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            trabajo_id INT NOT NULL,
            cliente_id INT NOT NULL,
            fecha DATETIME NOT NULL,
            notas TEXT NULL,
            estado ENUM('Pendiente','Aceptada','Rechazada','Completada','Cancelada') NOT NULL DEFAULT 'Pendiente',
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_citas_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE,
            CONSTRAINT fk_citas_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            INDEX idx_citas_fecha (fecha), INDEX idx_citas_cliente (cliente_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS password_resets (
            id INT AUTO_INCREMENT PRIMARY KEY, usuario_id INT NOT NULL, token_hash CHAR(64) NOT NULL,
            expira_en DATETIME NOT NULL, creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_password_resets_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            INDEX idx_password_resets_usuario (usuario_id), INDEX idx_password_resets_expira (expira_en)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS perfiles (
            usuario_id INT PRIMARY KEY, presentacion TEXT NULL, habilidades VARCHAR(500) NOT NULL DEFAULT '',
            comentario VARCHAR(500) NOT NULL DEFAULT '', actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            CONSTRAINT fk_perfiles_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
        """CREATE TABLE IF NOT EXISTS resenas (
            id INT AUTO_INCREMENT PRIMARY KEY, trabajador_id INT NOT NULL, autor_id INT NOT NULL,
            puntuacion TINYINT NOT NULL, comentario TEXT NOT NULL, creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_resenas_trabajador FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            CONSTRAINT fk_resenas_autor FOREIGN KEY (autor_id) REFERENCES usuarios(id) ON DELETE CASCADE,
            CONSTRAINT chk_resenas_puntuacion CHECK (puntuacion BETWEEN 1 AND 5),
            INDEX idx_resenas_trabajador (trabajador_id), INDEX idx_resenas_fecha (creado_en)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
    ]
    connection = get_connection()
    try:
        cursor = connection.cursor()
        for statement in statements:
            cursor.execute(statement)
        # Ampliación compatible de categorías: conserva los trabajos existentes.
        cursor.execute("SHOW COLUMNS FROM trabajos LIKE 'categoria'")
        category_column = cursor.fetchone()
        category_type = str(category_column[1]) if category_column else ""
        if "Marketing digital" not in category_type:
            cursor.execute("""ALTER TABLE trabajos MODIFY categoria ENUM(
                'Frontend','Backend','Full Stack','Aplicaciones móviles','Bases de datos','DevOps','Diseño',
                'Marketing digital','Contenido y redacción','Soporte técnico','Análisis de datos','QA y pruebas',
                'Ciberseguridad','Automatización','Otro') NOT NULL DEFAULT 'Otro'""")
        _migrate_v2(cursor)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


# --------------------------------------------------------------------------
# Migración v2 (aditiva): nuevas tablas y columnas para MyPines 2.
# Nunca borra ni modifica datos existentes.
# --------------------------------------------------------------------------
def _column_exists(cursor, table, column):
    cursor.execute("SHOW COLUMNS FROM `%s` LIKE %%s" % table, (column,))
    return len(cursor.fetchall()) > 0


def _index_exists(cursor, table, name):
    cursor.execute("SHOW INDEX FROM `%s` WHERE Key_name=%%s" % table, (name,))
    return len(cursor.fetchall()) > 0


V2_COLUMNS = [
    ("trabajos", "urgente", "TINYINT(1) NOT NULL DEFAULT 0"),
    ("trabajos", "ubicacion", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("usuarios", "tema", "VARCHAR(10) NOT NULL DEFAULT 'claro'"),
    ("usuarios", "onboarding_visto", "TINYINT(1) NOT NULL DEFAULT 0"),
    ("perfiles", "foto", "VARCHAR(255) NULL"),
    ("perfiles", "ubicacion", "VARCHAR(120) NOT NULL DEFAULT ''"),
    ("solicitudes", "actualizado_en", "DATETIME NULL"),
    ("citas", "solicitud_id", "INT NULL"),
    ("citas", "propuesta_por", "INT NULL"),
    ("resenas", "puntualidad", "TINYINT NULL"),
    ("resenas", "calidad", "TINYINT NULL"),
    ("resenas", "comunicacion", "TINYINT NULL"),
]

V2_TABLES = [
    """CREATE TABLE IF NOT EXISTS favoritos (
        usuario_id INT NOT NULL, trabajo_id INT NOT NULL, creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (usuario_id, trabajo_id),
        CONSTRAINT fk_fav_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
        CONSTRAINT fk_fav_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS notificaciones (
        id INT AUTO_INCREMENT PRIMARY KEY, usuario_id INT NOT NULL, titulo VARCHAR(160) NOT NULL,
        mensaje VARCHAR(500) NOT NULL DEFAULT '', tipo VARCHAR(30) NOT NULL DEFAULT 'info',
        leida TINYINT(1) NOT NULL DEFAULT 0, creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_notif_usuario (usuario_id, leida),
        CONSTRAINT fk_notif_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS busquedas_guardadas (
        id INT AUTO_INCREMENT PRIMARY KEY, usuario_id INT NOT NULL, nombre VARCHAR(80) NOT NULL,
        filtros TEXT NOT NULL, creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_busq_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS mensajes (
        id INT AUTO_INCREMENT PRIMARY KEY, solicitud_id INT NOT NULL, emisor_id INT NOT NULL, texto TEXT NOT NULL,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP, INDEX idx_mensajes_solicitud (solicitud_id),
        CONSTRAINT fk_msg_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,
        CONSTRAINT fk_msg_emisor FOREIGN KEY (emisor_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS contratos (
        id INT AUTO_INCREMENT PRIMARY KEY, solicitud_id INT NOT NULL UNIQUE, monto_acordado DECIMAL(12,2) NOT NULL DEFAULT 0.00,
        fecha_entrega DATE NULL, estado ENUM('Activo','Completado','Cancelado') NOT NULL DEFAULT 'Activo',
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_contrato_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS hitos (
        id INT AUTO_INCREMENT PRIMARY KEY, contrato_id INT NOT NULL, titulo VARCHAR(160) NOT NULL,
        descripcion VARCHAR(400) NULL, fecha_limite DATE NULL, completado TINYINT(1) NOT NULL DEFAULT 0,
        completado_en DATETIME NULL, creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP, INDEX idx_hitos_contrato (contrato_id),
        CONSTRAINT fk_hito_contrato FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS reportes (
        id INT AUTO_INCREMENT PRIMARY KEY, autor_id INT NOT NULL, tipo ENUM('trabajo','usuario') NOT NULL,
        objetivo_id INT NOT NULL, motivo VARCHAR(120) NOT NULL, comentario TEXT NULL,
        estado ENUM('Nuevo','En revisión','Resuelto','Descartado') NOT NULL DEFAULT 'Nuevo',
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP, INDEX idx_reportes_estado (estado),
        CONSTRAINT fk_reporte_autor FOREIGN KEY (autor_id) REFERENCES usuarios(id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS bitacora (
        id INT AUTO_INCREMENT PRIMARY KEY, usuario_id INT NULL, accion VARCHAR(60) NOT NULL,
        detalle VARCHAR(400) NOT NULL DEFAULT '', creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_bitacora_fecha (creado_en),
        CONSTRAINT fk_bitacora_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]

V2_INDEXES = [
    ("trabajos", "idx_trabajos_estado_fecha", "(estado, creado_en)"),
    ("trabajos", "idx_trabajos_categoria", "(categoria)"),
    ("solicitudes", "idx_solicitudes_estado", "(estado)"),
]

REQUEST_STATES = ("Pendiente", "Revisada", "Aceptada", "Rechazada", "Entrevista", "Contratada",
                  "En progreso", "Completada", "Cancelada", "Retirada")


def _migrate_v2(cursor):
    for table, column, ddl in V2_COLUMNS:
        if not _column_exists(cursor, table, column):
            cursor.execute("ALTER TABLE `%s` ADD COLUMN `%s` %s" % (table, column, ddl))
    for statement in V2_TABLES:
        cursor.execute(statement)
    for table, name, cols in V2_INDEXES:
        if not _index_exists(cursor, table, name):
            cursor.execute("CREATE INDEX `%s` ON `%s` %s" % (name, table, cols))
    # Estados extra de solicitudes, conservando los cuatro originales.
    cursor.execute("SHOW COLUMNS FROM solicitudes LIKE 'estado'")
    rows = cursor.fetchall()
    col = rows[0] if rows else None
    if col and "Contratada" not in str(col[1]):
        states = ",".join("'%s'" % s for s in REQUEST_STATES)
        cursor.execute("ALTER TABLE solicitudes MODIFY estado ENUM(%s) NOT NULL DEFAULT 'Pendiente'" % states)
