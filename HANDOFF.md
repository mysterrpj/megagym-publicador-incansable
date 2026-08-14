# Handoff

## Problema
El calendario solo estaba preparado para publicar imagenes. Al enviar un `.mp4`, Make recibia el webhook pero fallaba porque las rutas existentes usaban modulos de foto.

## Causa raiz
El publicador enviaba `image_url` y Make tenia solo rutas para:
- Instagram: Create a photo post.
- Facebook: Create a Post with Photos.

Los videos requieren payload y rutas distintas: `asset_type = video`, `video_url`, Facebook Upload a Video e Instagram Create a reel post.

## Que se hizo
- Se extendio `publisher.py` para manejar assets de tipo imagen o video.
- Se agregaron extensiones soportadas para video: `.mp4`, `.mov`, `.m4v`.
- Se agrego payload compatible con Make:
  - `asset_type`
  - `asset_url`
  - `video_url` cuando corresponde.
- Se agregaron inputs manuales al workflow para probar una fecha/hora especifica.
- Se configuro Make con rutas separadas para imagen y video.
- Se redetermino la estructura del webhook en Make.
- Se corrigieron filtros de Make a:
  - Imagen: `asset_type = image`.
  - Video: `asset_type = video`.

## Archivos modificados
- `.github/workflows/publicar.yml`
- `MANUAL.md`
- `calendario_publicaciones.csv`
- `historial_fotos.json`
- `publisher.py`
- `posts_programados/2026-05-10_0800.jpg`
- `posts_programados/2026-05-10_2000.mp4`
- `notes/2026-05-09-avances.md`
- `TODO.md`
- `HANDOFF.md`
- `PROJECT_CONTEXT.md`
- `DECISIONS.md`

## Cambio final aplicado
El flujo acepta filas del calendario con `.jpg/.png/.webp` como imagen y `.mp4/.mov/.m4v` como video. Para videos, Make publica en Facebook con Upload a Video y en Instagram con Create a reel post.

## Estado actual
- `master` contiene el soporte de videos.
- La prueba final en Make termino con `Success`.
- Los detalles de Make mostraron completados:
  - HTTP Download a file para Facebook.
  - Facebook Pages - Upload a Video.
  - HTTP Download a file para Instagram.
  - Instagram for Business - Create a reel post.
- La publicacion `2026-05-10 20:00` quedo en estado `publicada`.

## Como verificar
1. Subir un video nuevo a `posts_programados/`, por ejemplo `2026-05-11_2000.mp4`.
2. En `calendario_publicaciones.csv`, apuntar la fila correspondiente al `.mp4` y poner estado `lista`.
3. Ejecutar manualmente GitHub Actions `Publicador Automatico MEGAGYM` con:
   - `publicacion_fecha`: fecha de la fila.
   - `publicacion_hora`: hora de la fila.
4. En Make, verificar que pasen las rutas con `asset_type = video`.
5. Revisar Facebook e Instagram.

## Proximo objetivo recomendado
Probar una publicacion futura real de video desde GitHub Actions con el escenario de Make activo y sin intervencion manual.

## Riesgos/pendientes
- Pendiente de confirmar: el escenario de Make quedo activo tras la ultima prueba.
- Pendiente de confirmar: comportamiento estable de WhatsApp con videos.
- GitHub puede no ser ideal como hosting de videos si los archivos crecen mucho.
- El calendario conserva la columna `imagen_archivo`; se usa tambien para videos por compatibilidad.

## Comandos ejecutados
```powershell
Get-Date -Format yyyy-MM-dd
git status --short
git log --oneline -8
python -m py_compile publisher.py
git switch -c test-videos
git add .github/workflows/publicar.yml MANUAL.md calendario_publicaciones.csv publisher.py posts_programados/2026-05-10_2000.mp4
git commit -m "Agrega prueba de publicaciones con video"
git push -u origin test-videos
gh workflow run publicar.yml --ref test-videos -f publicacion_fecha=2026-05-10 -f publicacion_hora=20:00
gh run list --workflow publicar.yml --branch test-videos --limit 3
gh run view 25614534267 --log
git merge --ff-only test-videos
git push origin master
Invoke-RestMethod -Uri https://hook.us2.make.com/... -Method Post -ContentType application/json -Body <payload de prueba>
New-Item -ItemType Directory -Path notes -Force
```

## Actualizacion 2026-08-14 - Panel web /megagym y causa de imagenes repetidas

### Problema diagnosticado
El pool de fotos del indice inteligente se agoto: solo habia 57 fotos indexadas, se publican 2 veces al dia y la regla anti-repeticion es de 45 dias (DIAS_HISTORIAL=45). Los logs de GitHub Actions mostraron candidatas disponibles bajando de 9 (8 ago) a 1 (13 ago). Con 0 candidatas, el publicador cae a fotos_reales/ y luego a la imagen de respaldo, repitiendo siempre la misma.

### Que se hizo
- Diagnostico con logs de GitHub Actions, historial remoto e indice remoto.
- En create-next-app: nueva funcion generateMegagymRows + seccion "Programar nuevas publicaciones" en /megagym.
- La funcion evita temas repetidos normalizando tildes y mezcla al azar los temas libres.
- Deploy de funciones y hosting en el proyecto status-architect-stitch.
- Se corrigio un ref roto de Codex (refs/codex/.../base) que impedia el git pull local.

### Estado actual
- /megagym genera filas futuras y permite subir la imagen/video de cada fila; la imagen subida se publica tal cual.
- Google Drive queda como respaldo solo cuando una fila no tiene imagen asignada.
- Para desplegar funciones en create-next-app usar FUNCTIONS_DISCOVERY_TIMEOUT=120 (la PC tarda mas de 10s en cargar el codigo).
