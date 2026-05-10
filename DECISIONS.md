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
