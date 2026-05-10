# Project Context

## Vision general
Automatizacion de publicaciones para MEGAGYM en Facebook, Instagram y WhatsApp. El sistema usa un calendario CSV, genera o reutiliza contenido, valida assets publicos y envia el resultado a Make.com para publicar.

## Stack
- Python 3.11
- GitHub Actions
- Make.com webhook
- Gemini para copy
- OpenAI para generacion opcional de imagenes
- Google Drive para seleccion de fotos
- GitHub Raw como URL publica para assets programados

## Flujo principal
1. GitHub Actions ejecuta `publisher.py` dos veces al dia.
2. `publisher.py` busca una fila del calendario por fecha y hora.
3. Si la fila esta en `lista`, `programada` o `ready`, usa el asset indicado.
4. Si el archivo es imagen, envia `asset_type = image` e `image_url`.
5. Si el archivo es video, envia `asset_type = video` y `video_url`.
6. Make enruta por `asset_type`:
   - Imagen: Instagram photo post y Facebook post with photos.
   - Video: Instagram reel y Facebook upload video.
7. El publicador tambien intenta enviar el asset a WhatsApp si las variables de importacion estan configuradas.

## Archivos clave
- `publisher.py`: motor principal de publicacion.
- `calendario_publicaciones.csv`: calendario de publicaciones.
- `posts_programados/`: assets preparados para filas del calendario.
- `.github/workflows/publicar.yml`: workflow programado y manual.
- `MANUAL.md`: instrucciones operativas.
- `historial_fotos.json`: historial de assets usados.

## Variables y secretos relevantes
- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- `MAKE_WEBHOOK_URL`
- `GOOGLE_DRIVE_CREDENTIALS`
- `GOOGLE_DRIVE_FOLDER_ID`
- `GITHUB_TOKEN`
- `GITHUB_REPOSITORY`
- `WHATSAPP_IMPORT_URL`
- `WHATSAPP_IMPORT_KEY`
- `WHATSAPP_IMPORT_USER_ID`
- `WHATSAPP_STATUS_TIMES`
- `PUBLICACION_FECHA`
- `PUBLICACION_HORA`

## Run/deploy
- Automatico: GitHub Actions corre a las 8:00 y 20:00 hora Peru.
- Manual: GitHub Actions permite `workflow_dispatch` con `publicacion_fecha` y `publicacion_hora`.
- Make debe estar activo para procesar webhooks entrantes.

## Estado actual
El proyecto soporta imagenes y videos programados desde el calendario. La prueba de video en Make completo correctamente para Facebook Upload a Video e Instagram Create a reel post.
