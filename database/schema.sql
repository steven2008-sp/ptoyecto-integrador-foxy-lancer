CREATE DATABASE IF NOT EXISTS mypines_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mypines_db;

-- ============================================================
-- Tablas base (Foxy Lancer 1.0 / 2.0)
-- ============================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(190) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol ENUM('contratante','freelancer','admin') NOT NULL DEFAULT 'freelancer',
    activo TINYINT(1) NOT NULL DEFAULT 1,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS trabajos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(140) NOT NULL,
    categoria ENUM('Frontend','Backend','Full Stack','Aplicaciones móviles','Bases de datos','DevOps','Diseño','Marketing digital','Contenido y redacción','Soporte técnico','Análisis de datos','QA y pruebas','Ciberseguridad','Automatización','Otro') NOT NULL DEFAULT 'Otro',
    descripcion TEXT NOT NULL,
    habilidades VARCHAR(500) NOT NULL DEFAULT '',
    modalidad ENUM('Remoto','Presencial','Híbrido') NOT NULL DEFAULT 'Remoto',
    presupuesto DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    cliente_id INT NULL,
    urgente TINYINT(1) NOT NULL DEFAULT 0,
    ubicacion VARCHAR(120) NOT NULL DEFAULT '',
    fecha_limite DATE NULL,
    estado ENUM('Publicado','Borrador','Cerrado') NOT NULL DEFAULT 'Publicado',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_trabajos_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS solicitudes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trabajo_id INT NOT NULL,
    cliente_id INT NOT NULL,
    mensaje TEXT NOT NULL,
    estado ENUM('Pendiente','Revisada','Aceptada','Rechazada','Entrevista','Contratada','En progreso','Completada','Cancelada','Retirada') NOT NULL DEFAULT 'Pendiente',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en DATETIME NULL,
    UNIQUE KEY uq_solicitud_cliente_trabajo (trabajo_id, cliente_id),
    CONSTRAINT fk_solicitud_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE,
    CONSTRAINT fk_solicitud_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS citas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trabajo_id INT NOT NULL,
    cliente_id INT NOT NULL,
    fecha DATETIME NOT NULL,
    notas TEXT NULL,
    estado ENUM('Pendiente','Aceptada','Rechazada','Completada','Cancelada') NOT NULL DEFAULT 'Pendiente',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    solicitud_id INT NULL,
    propuesta_por INT NULL,
    CONSTRAINT fk_citas_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE,
    CONSTRAINT fk_citas_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_citas_fecha (fecha),
    INDEX idx_citas_cliente (cliente_id)
);

CREATE TABLE IF NOT EXISTS password_resets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expira_en DATETIME NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_password_resets_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_password_resets_usuario (usuario_id),
    INDEX idx_password_resets_expira (expira_en)
);

CREATE TABLE IF NOT EXISTS perfiles (
    usuario_id INT PRIMARY KEY,
    presentacion TEXT NULL,
    habilidades VARCHAR(500) NOT NULL DEFAULT '',
    comentario VARCHAR(500) NOT NULL DEFAULT '',
    foto VARCHAR(255) NULL,
    ubicacion VARCHAR(120) NOT NULL DEFAULT '',
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_perfiles_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS resenas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trabajador_id INT NOT NULL,
    autor_id INT NOT NULL,
    puntuacion TINYINT NOT NULL,
    comentario TEXT NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    puntualidad TINYINT NULL,
    calidad TINYINT NULL,
    comunicacion TINYINT NULL,
    CONSTRAINT fk_resenas_trabajador FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_resenas_autor FOREIGN KEY (autor_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT chk_resenas_puntuacion CHECK (puntuacion BETWEEN 1 AND 5),
    INDEX idx_resenas_trabajador (trabajador_id),
    INDEX idx_resenas_fecha (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Tablas y columnas adicionales (Foxy Lancer 2.0)
-- ============================================================

CREATE TABLE IF NOT EXISTS favoritos (
    usuario_id INT NOT NULL,
    trabajo_id INT NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id, trabajo_id),
    CONSTRAINT fk_fav_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_fav_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notificaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    titulo VARCHAR(160) NOT NULL,
    mensaje VARCHAR(500) NOT NULL DEFAULT '',
    tipo VARCHAR(30) NOT NULL DEFAULT 'info',
    leida TINYINT(1) NOT NULL DEFAULT 0,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_notif_usuario (usuario_id, leida),
    CONSTRAINT fk_notif_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS busquedas_guardadas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    nombre VARCHAR(80) NOT NULL,
    filtros TEXT NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_busq_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mensajes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    solicitud_id INT NOT NULL,
    emisor_id INT NOT NULL,
    texto TEXT NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_mensajes_solicitud (solicitud_id),
    CONSTRAINT fk_msg_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,
    CONSTRAINT fk_msg_emisor FOREIGN KEY (emisor_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS contratos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    solicitud_id INT NOT NULL UNIQUE,
    monto_acordado DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    fecha_entrega DATE NULL,
    estado ENUM('Activo','Completado','Cancelado') NOT NULL DEFAULT 'Activo',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_contrato_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hitos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    contrato_id INT NOT NULL,
    titulo VARCHAR(160) NOT NULL,
    descripcion VARCHAR(400) NULL,
    fecha_limite DATE NULL,
    completado TINYINT(1) NOT NULL DEFAULT 0,
    completado_en DATETIME NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_hitos_contrato (contrato_id),
    CONSTRAINT fk_hito_contrato FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reportes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    autor_id INT NOT NULL,
    tipo ENUM('trabajo','usuario') NOT NULL,
    objetivo_id INT NOT NULL,
    motivo VARCHAR(120) NOT NULL,
    comentario TEXT NULL,
    estado ENUM('Nuevo','En revisión','Resuelto','Descartado') NOT NULL DEFAULT 'Nuevo',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_reportes_estado (estado),
    CONSTRAINT fk_reporte_autor FOREIGN KEY (autor_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS bitacora (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NULL,
    accion VARCHAR(60) NOT NULL,
    detalle VARCHAR(400) NOT NULL DEFAULT '',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_bitacora_fecha (creado_en),
    CONSTRAINT fk_bitacora_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Índices adicionales
CREATE INDEX idx_trabajos_estado_fecha ON trabajos (estado, creado_en);
CREATE INDEX idx_trabajos_categoria ON trabajos (categoria);
CREATE INDEX idx_solicitudes_estado ON solicitudes (estado);

-- ============================================================
-- Tablas para roles Contratante / Freelancer (Foxy Lancer 3.0)
-- ============================================================

CREATE TABLE IF NOT EXISTS experiencias_freelancer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    empresa VARCHAR(150) NOT NULL,
    cargo VARCHAR(150) NOT NULL,
    descripcion TEXT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NULL,
    actual TINYINT(1) NOT NULL DEFAULT 0,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_exp_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_exp_usuario (usuario_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS proyectos_freelancer (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    titulo VARCHAR(150) NOT NULL,
    descripcion TEXT NULL,
    enlace VARCHAR(500) NULL,
    tecnologias VARCHAR(500) NOT NULL DEFAULT '',
    fecha DATE NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_proy_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_proy_usuario (usuario_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS contrataciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trabajo_id INT NOT NULL,
    solicitud_id INT NOT NULL,
    freelancer_id INT NOT NULL,
    contratante_id INT NOT NULL,
    estado ENUM('Pendiente','Aceptada','Rechazada','Completada') NOT NULL DEFAULT 'Pendiente',
    mensaje_rechazo TEXT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_contratacion_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE,
    CONSTRAINT fk_contratacion_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE CASCADE,
    CONSTRAINT fk_contratacion_freelancer FOREIGN KEY (freelancer_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_contratacion_contratante FOREIGN KEY (contratante_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_contratacion_trabajo (trabajo_id),
    INDEX idx_contratacion_freelancer (freelancer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Migración: actualizar ENUM de rol si la tabla ya existe con 'cliente'
-- ============================================================

ALTER TABLE usuarios MODIFY COLUMN rol ENUM('contratante','freelancer','admin') NOT NULL DEFAULT 'freelancer';

-- Migrar usuarios existentes con rol 'cliente' a 'contratante' (para que puedan publicar trabajos)
UPDATE usuarios SET rol='contratante' WHERE rol='cliente';

-- ============================================================
-- Tabla de pagos y confirmaciones (Foxy Lancer 3.1)
-- ============================================================

CREATE TABLE IF NOT EXISTS pagos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    contrato_id INT NOT NULL,
    monto DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    estado ENUM('Pendiente','Enviado','Recibido','Disputado','Completado','Cancelado') NOT NULL DEFAULT 'Pendiente',
    confirmado_por_contratante TINYINT(1) NOT NULL DEFAULT 0,
    confirmado_por_freelancer TINYINT(1) NOT NULL DEFAULT 0,
    fecha_confirmacion_contratante DATETIME NULL,
    fecha_confirmacion_freelancer DATETIME NULL,
    fecha_envio DATETIME NULL,
    fecha_recepcion DATETIME NULL,
    motivo_disputa TEXT NULL,
    reportado_por INT NULL,
    fecha_reporte DATETIME NULL,
    compensacion_aprobada TINYINT(1) NOT NULL DEFAULT 0,
    monto_compensacion DECIMAL(12,2) NULL,
    fecha_compensacion DATETIME NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_pago_contrato FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE,
    CONSTRAINT fk_pago_reportado_por FOREIGN KEY (reportado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_pago_contrato (contrato_id),
    INDEX idx_pago_estado (estado),
    INDEX idx_pago_reportado (reportado_por)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Tabla de compensaciones por pagos no recibidos (Foxy Lancer 3.1)
-- ============================================================

CREATE TABLE IF NOT EXISTS compensaciones (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pago_id INT NOT NULL,
    contrato_id INT NOT NULL,
    usuario_afectado_id INT NOT NULL,
    monto DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    motivo TEXT NOT NULL,
    estado ENUM('Pendiente','Aprobada','Rechazada','Pagada') NOT NULL DEFAULT 'Pendiente',
    aprobado_por INT NULL,
    fecha_aprobacion DATETIME NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comp_pago FOREIGN KEY (pago_id) REFERENCES pagos(id) ON DELETE CASCADE,
    CONSTRAINT fk_comp_contrato FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE,
    CONSTRAINT fk_comp_usuario_afectado FOREIGN KEY (usuario_afectado_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_comp_aprobado_por FOREIGN KEY (aprobado_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_comp_pago (pago_id),
    INDEX idx_comp_estado (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Tabla de bloqueo de usuarios por administración (Foxy Lancer 3.1)
-- ============================================================

CREATE TABLE IF NOT EXISTS bloqueos_usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_bloqueado_id INT NOT NULL,
    bloqueado_por INT NOT NULL,
    motivo TEXT NOT NULL,
    fecha_bloqueo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion DATETIME NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT fk_bloq_usuario_bloqueado FOREIGN KEY (usuario_bloqueado_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_bloq_bloqueado_por FOREIGN KEY (bloqueado_por) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_bloq_usuario (usuario_bloqueado_id),
    INDEX idx_bloq_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Tabla de reportes generales de usuarios (Foxy Lancer 3.2)
-- Reportes por conducta: publicidad engañosa, no entrega, reseñas falsas, estafa, etc.
-- ============================================================

CREATE TABLE IF NOT EXISTS reportes_usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reportado_id INT NOT NULL,
    reportado_por INT NOT NULL,
    contrato_id INT NULL,
    solicitud_id INT NULL,
    tipo_reporte ENUM('publicidad_engañosa', 'no_entrega_trabajo', 'reseña_falsa', 'intento_estafa', 'conducta_inapropiada', 'pago_no_recibido', 'otro') NOT NULL,
    motivo TEXT NOT NULL,
    evidencia TEXT NULL,
    estado ENUM('Pendiente','En revisión','Resuelto','Descartado') NOT NULL DEFAULT 'Pendiente',
    fecha_reporte TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_resolucion DATETIME NULL,
    resuelto_por INT NULL,
    accion_tomada ENUM('Ninguna','Advertencia','Suspensión temporal','Suspensión permanente','Compensación') NOT NULL DEFAULT 'Ninguna',
    CONSTRAINT fk_rep_reportado FOREIGN KEY (reportado_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_rep_reportado_por FOREIGN KEY (reportado_por) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_rep_contrato FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE SET NULL,
    CONSTRAINT fk_rep_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitudes(id) ON DELETE SET NULL,
    CONSTRAINT fk_rep_resuelto_por FOREIGN KEY (resuelto_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_rep_reportado (reportado_id),
    INDEX idx_rep_estado (estado),
    INDEX idx_rep_tipo (tipo_reporte)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Tabla de suspensiones de usuarios (Foxy Lancer 3.2)
-- Suspensiones temporales y permanentes por conducta indebida
-- ============================================================

CREATE TABLE IF NOT EXISTS suspensiones_usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    suspendido_por INT NOT NULL,
    tipo_suspension ENUM('temporal', 'permanente') NOT NULL DEFAULT 'temporal',
    motivo TEXT NOT NULL,
    fecha_suspension TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion DATETIME NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    reporte_origen_id INT NULL,
    CONSTRAINT fk_susp_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_susp_suspendido_por FOREIGN KEY (suspendido_por) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_susp_reporte FOREIGN KEY (reporte_origen_id) REFERENCES reportes_usuarios(id) ON DELETE SET NULL,
    INDEX idx_susp_usuario (usuario_id),
    INDEX idx_susp_activo (activo),
    INDEX idx_susp_tipo (tipo_suspension)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Tabla de contactos guardados (Foxy Lancer 3.3)
-- Permite a contratantes y freelancers guardarse mutuamente
-- para comunicarse posteriormente y facilitar futuras colaboraciones
-- ============================================================

CREATE TABLE IF NOT EXISTS contactos_guardados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    contacto_id INT NOT NULL,
    nombre_apodo VARCHAR(100) NULL,
    notas TEXT NULL,
    fecha_guardado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_contacto_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_contacto_contacto FOREIGN KEY (contacto_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT uq_contacto UNIQUE (usuario_id, contacto_id),
    INDEX idx_contacto_usuario (usuario_id),
    INDEX idx_contacto_contacto (contacto_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Tabla de reseñas reportadas (Foxy Lancer 3.2)
-- Para reportar reseñas falsas o manipuladas
-- ============================================================

CREATE TABLE IF NOT EXISTS reportes_resenas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    resena_id INT NOT NULL,
    reportado_por INT NOT NULL,
    motivo TEXT NOT NULL,
    estado ENUM('Pendiente','En revisión','Resuelto','Descartado') NOT NULL DEFAULT 'Pendiente',
    fecha_reporte TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_resolucion DATETIME NULL,
    resuelto_por INT NULL,
    accion_tomada ENUM('Ninguna','Eliminar reseña','Advertencia al autor','Suspensión temporal autor','Suspensión permanente autor') NOT NULL DEFAULT 'Ninguna',
    CONSTRAINT fk_repres_resena FOREIGN KEY (resena_id) REFERENCES resenas(id) ON DELETE CASCADE,
    CONSTRAINT fk_repres_reportado_por FOREIGN KEY (reportado_por) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_repres_resuelto_por FOREIGN KEY (resuelto_por) REFERENCES usuarios(id) ON DELETE SET NULL,
    INDEX idx_repres_resena (resena_id),
    INDEX idx_repres_estado (estado)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Trabajos de ejemplo (opcional, para probar)
-- ============================================================

INSERT INTO trabajos (titulo,categoria,descripcion,habilidades,modalidad,presupuesto,estado)
SELECT 'Crear página web para negocio', 'Frontend',
'Se necesita una página web adaptable a celulares para presentar productos y datos de contacto.',
'HTML, CSS, JavaScript', 'Remoto', 4500.00, 'Publicado'
WHERE NOT EXISTS (SELECT 1 FROM trabajos WHERE titulo='Crear página web para negocio');

INSERT INTO trabajos (titulo,categoria,descripcion,habilidades,modalidad,presupuesto,estado)
SELECT 'Sistema de inventario básico', 'Backend',
'Desarrollar un sistema sencillo para controlar productos, existencias y reportes.',
'Python, MySQL', 'Híbrido', 8500.00, 'Publicado'
WHERE NOT EXISTS (SELECT 1 FROM trabajos WHERE titulo='Sistema de inventario básico');

INSERT INTO trabajos (titulo,categoria,descripcion,habilidades,modalidad,presupuesto,estado)
SELECT 'Diseño de aplicación móvil', 'Aplicaciones móviles',
'Diseñar las pantallas principales de una aplicación móvil para un emprendimiento.',
'Flutter, UI/UX', 'Remoto', 6000.00, 'Publicado'
WHERE NOT EXISTS (SELECT 1 FROM trabajos WHERE titulo='Diseño de aplicación móvil');

-- ============================================================
-- LIMPIEZA AUTOMÁTICA: Eliminar trabajos duplicados del mismo cliente
-- Mantiene solo el más reciente (mayor id) por título normalizado.
-- ============================================================

DELETE t1 FROM trabajos t1
INNER JOIN trabajos t2 
    ON t1.cliente_id = t2.cliente_id
    AND LOWER(TRIM(t1.titulo)) = LOWER(TRIM(t2.titulo))
    AND t1.id < t2.id;
