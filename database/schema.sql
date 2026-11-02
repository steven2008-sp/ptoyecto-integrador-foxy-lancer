CREATE DATABASE IF NOT EXISTS mypines_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mypines_db;

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(190) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol ENUM('cliente','admin') NOT NULL DEFAULT 'cliente',
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
    estado ENUM('Pendiente','Revisada','Aceptada','Rechazada') NOT NULL DEFAULT 'Pendiente',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_solicitud_cliente_trabajo (trabajo_id, cliente_id),
    CONSTRAINT fk_solicitud_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE,
    CONSTRAINT fk_solicitud_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

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

-- Calendario de entrevistas relacionado con los trabajos y solicitudes de Foxy Lancer.
CREATE TABLE IF NOT EXISTS citas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trabajo_id INT NOT NULL,
    cliente_id INT NOT NULL,
    fecha DATETIME NOT NULL,
    notas TEXT NULL,
    estado ENUM('Pendiente','Aceptada','Rechazada','Completada','Cancelada') NOT NULL DEFAULT 'Pendiente',
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_citas_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE CASCADE,
    CONSTRAINT fk_citas_cliente FOREIGN KEY (cliente_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_citas_fecha (fecha),
    INDEX idx_citas_cliente (cliente_id)
);

-- Tabla para recuperación de contraseña mediante token enviado por correo.
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


-- Perfil público y habilidades de cada usuario.
CREATE TABLE IF NOT EXISTS perfiles (
    usuario_id INT PRIMARY KEY,
    presentacion TEXT NULL,
    habilidades VARCHAR(500) NOT NULL DEFAULT '',
    comentario VARCHAR(500) NOT NULL DEFAULT '',
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_perfiles_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Puntuación y reseñas de la comunidad. Cada autor puede actualizar su reseña de un trabajador.
CREATE TABLE IF NOT EXISTS resenas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trabajador_id INT NOT NULL,
    autor_id INT NOT NULL,
    puntuacion TINYINT NOT NULL,
    comentario TEXT NOT NULL,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_resenas_trabajador FOREIGN KEY (trabajador_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    CONSTRAINT fk_resenas_autor FOREIGN KEY (autor_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    INDEX idx_resenas_trabajador (trabajador_id),
    INDEX idx_resenas_fecha (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ============================================================
-- Foxy Lancer 2.0: las tablas y columnas nuevas (favoritos, notificaciones,
-- busquedas_guardadas, mensajes, contratos, hitos, reportes, bitacora y
-- columnas extra) las crea/migra automáticamente database.ensure_schema()
-- al iniciar la app, de forma aditiva e idempotente. No se borra nada.
-- ============================================================
