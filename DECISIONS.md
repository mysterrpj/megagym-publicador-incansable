# Decisions

## 2026-05-09 - Soporte de videos por asset type
Decision: usar `asset_type` para separar imagenes y videos en el payload enviado a Make.

Motivo: Make necesita rutas distintas para fotos y videos. Detectar el tipo en `publisher.py` permite mantener el calendario compatible y enrutar de forma explicita.

Impacto:
- Imagenes envian `asset_type = image` e `image_url`.
- Videos envian `asset_type = video`, `asset_url` y `video_url`.
- Make filtra rutas por `asset_type`.

## 2026-05-09 - Mantener `imagen_archivo` como columna compatible
Decision: no cambiar todavia el esquema del calendario; `imagen_archivo` se usa tambien para videos.

Motivo: evita una migracion amplia y mantiene compatibilidad con filas existentes.

Impacto:
- Para videos se coloca un `.mp4`, `.mov` o `.m4v` en `imagen_archivo`.
- Queda pendiente evaluar una columna generica `archivo` en una migracion futura.

## 2026-05-09 - No usar fallback de imagen cuando falla un video
Decision: si una publicacion esta programada como video y el video no valida, no se reemplaza por una imagen de respaldo.

Motivo: publicar una imagen cuando se esperaba un video cambia el formato planificado y puede ocultar errores operativos.

Impacto:
- Videos invalidos se omiten.
- Imagenes conservan fallback de imagen de respaldo.

## 2026-08-14 - Generar filas futuras desde el panel web /megagym
Decision: el panel web MEGAGYM de create-next-app puede crear filas futuras en el calendario (fecha de inicio + cantidad), con temas de publisher.py, 2 por dia (08:00 y 20:00), estado pendiente.

Motivo: evitar depender del panel local para programar publicaciones y permitir subir la imagen por fila desde el mismo panel.

Impacto: las filas nuevas se escriben en calendario_publicaciones.csv via GitHub API y el publicador las procesa igual que antes.

## 2026-08-14 - Deduplicacion de temas normalizando tildes
Decision: al seleccionar temas para filas nuevas, se normalizan tildes y mayusculas antes de comparar con temas ya usados.

Motivo: filas viejas guardadas sin tildes (ej. "Por que...") repetian temas con tildes ("Por qué...") porque la comparacion era literal.

Impacto: ya no se repiten temas visualmente iguales con o sin acentos.

## 2026-08-14 - Temas en orden aleatorio
Decision: los temas disponibles (no usados) se mezclan al azar antes de asignarse a las filas nuevas.

Motivo: evitar que siempre se elijan los primeros temas de la lista y dar variedad.

Impacto: cada generacion produce una seleccion variada de temas.

## 2026-08-25 - Horarios fijos de importacion a WhatsApp
Decision: cada importacion a WhatsApp usa un horario fijo segun el turno de la publicacion, no el "proximo horario libre":
- Publicacion de manana (08:00) -> mismo dia 12:00 hora Peru (`17:00Z`).
- Publicacion de noche (20:00) -> dia siguiente 21:00 hora Peru (`02:00Z`).

Motivo: antes, ambas llamadas diarias usaban `post_index=1` (cada ejecucion procesa una sola publicacion) y caian en el primer slot (12:00 Lima = 17:00Z), por lo que las 2 tareas quedaban con el mismo `scheduleTime` y se intentaban publicar a la vez.

Impacto:
- El flujo automatico ahora agrega `fecha` y `hora` a cada publicacion para calcular su turno.
- `schedule_time_for_whatsapp` mapea manana -> 12:00 mismo dia y noche -> 21:00 del dia siguiente.
- El `scheduleTime` se envia en UTC con formato ISO 8601 (sufijo `Z`).
- Cada post conserva su `externalPostId` unico.
