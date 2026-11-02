# Foxy Lancer Plataforma

Aplicación de escritorio Python/PySide6 para explorar trabajos, publicar oportunidades, enviar solicitudes, proponer entrevistas, administrar publicaciones y gestionar perfiles/reseñas. Incluye contraste reforzado, calendario de selección de fecha/hora, categorías ampliadas y ayuda local de Foxy Lancer AI para preguntas frecuentes de la plataforma.

## Iniciar
1. Instala Python 3.11 o posterior y MySQL Server.
2. Verifica el archivo `.env` en esta carpeta. Debe contener los valores de conexión de tu MySQL (`MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`). No compartas el archivo porque contiene credenciales.
3. Inicia el servicio MySQL80.
4. Ejecuta `INSTALAR_DEPENDENCIAS.bat` una vez.
5. Ejecuta `INICIAR_MYPINES.bat`.

La aplicación intenta crear tablas auxiliares de forma no destructiva al iniciar. No elimina ni recrea la base de datos.

## Administrador
Para crear o promover una cuenta administradora, ejecuta `CREAR_ADMIN.bat` e introduce nombre, correo y contraseña cuando lo solicite. La contraseña se almacena como hash. No conviertas una cuenta a administrador desde una consulta SQL si no es necesario.

El panel de administración permite ver un resumen, revisar solicitudes y aceptar/rechazar entrevistas pendientes. Los usuarios pueden publicar oportunidades y ver sus propias publicaciones, solicitar entrevistas sobre trabajos publicados y consultar sus solicitudes. Las entrevistas quedan pendientes hasta que administración las revise.

## Foxy Lancer AI
La IA generativa necesita una clave `OPENAI_API_KEY` válida en `.env` y crédito/límite disponible en OpenAI API. Si falta la clave o la API devuelve HTTP 429, el asistente ofrece ayuda local limitada sobre las funciones de Foxy Lancer, pero no puede reemplazar a un modelo generativo. La suscripción de ChatGPT y el uso de la API son independientes.

## Seguridad
- No publiques ni envíes el archivo `.env`.
- No guardes la contraseña de MySQL directamente en `database.py`.
- No compartas claves de OpenAI en capturas de pantalla.

## Novedades de la versión 2.0
El login/registro quedó igual y la conexión MySQL no cambió (la contraseña sigue únicamente en `.env`).

**Modo cliente**: barra superior, filtros con slider de salario, buscador, tarjetas con % de compatibilidad, trabajos sugeridos, favoritos, búsquedas guardadas con alertas, mensajes, notificaciones (campana + bandeja del sistema), contratos con hitos y recibo PDF, reseñas por criterios, insignias y completitud de perfil, reportes, asistentes de IA con respaldo local.
**Modo administrador**: barra lateral clara, KPIs con variación %, gráficos (línea, donas, barras), tablas con pestañas/filtro/exportar, usuarios, reseñas, reportes, calendario de entrevistas (calendario + horarios), exportación Excel/PDF, bitácora y respaldo de la base.
**General**: modo claro/oscuro, onboarding, atajos (Ctrl+F buscar, Ctrl+N publicar), bloqueo temporal tras 5 intentos fallidos, registro en `mypines.log`.

La migración de base de datos es aditiva (`ensure_schema`). Haz un respaldo de tu base antes de la primera ejecución. Instala dependencias de nuevo (`INSTALAR_DEPENDENCIAS.bat`) para `openpyxl` y `reportlab`.
Pruebas: `python tests/test_theme.py` y `python tests/test_logic.py`.
