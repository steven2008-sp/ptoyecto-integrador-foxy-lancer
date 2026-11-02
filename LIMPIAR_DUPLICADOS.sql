-- ============================================================
-- LIMPIAR TRABAJOS DUPLICADOS (Foxy Lancer)
-- ============================================================
-- Este script elimina trabajos duplicados del mismo cliente
-- con el mismo título, manteniendo solo el más reciente
-- (el de mayor id).
-- ============================================================

USE mypines_db;

-- Primero, veamos cuántos duplicados existen (consulta de revisión)
SELECT 
    LOWER(TRIM(titulo)) AS titulo_normalizado,
    cliente_id,
    COUNT(*) AS cantidad_duplicados,
    GROUP_CONCAT(id ORDER BY id DESC) AS ids,
    GROUP_CONCAT(creado_en ORDER BY id DESC) AS fechas
FROM trabajos
GROUP BY LOWER(TRIM(titulo)), cliente_id
HAVING COUNT(*) > 1
ORDER BY cantidad_duplicados DESC;

-- ============================================================
-- Ejecutar esta parte SOLO si quieres eliminar los duplicados:
-- ============================================================

DELETE t1 FROM trabajos t1
INNER JOIN trabajos t2 
    ON t1.cliente_id = t2.cliente_id
    AND LOWER(TRIM(t1.titulo)) = LOWER(TRIM(t2.titulo))
    AND t1.id < t2.id;

-- Verificar que ya no queden duplicados
SELECT 
    LOWER(TRIM(titulo)) AS titulo_normalizado,
    cliente_id,
    COUNT(*) AS cantidad
FROM trabajos
GROUP BY LOWER(TRIM(titulo)), cliente_id
HAVING COUNT(*) > 1
ORDER BY cantidad DESC;

SELECT 'Limpieza de duplicados completada' AS mensaje;
