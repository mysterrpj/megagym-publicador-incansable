# Plan de Integración: Google Drive Inteligente (MEGAGYM)

Este plan detalla los pasos para conectar la galería de Google Drive (más de 400 fotos) con el publicador automático de GitHub Actions.

## Checklist de Implementación

### Fase 1: Preparación y Acceso
- [x] **Proporcionar el enlace de la carpeta de Drive:** `https://drive.google.com/drive/folders/1BhIN2I9YEfZxWZv0Ec93AVlOO9l4thHc`
- [x] **Creación de Credenciales:** Service Account `megagym-drive` en proyecto `megagym-publicador-incansable`.

### Fase 2: Configuración de Seguridad
- [x] **Configurar GitHub Secrets:** `GOOGLE_DRIVE_CREDENTIALS` y `GOOGLE_DRIVE_FOLDER_ID` configurados.
- [x] **Actualizar Dependencias:** `google-api-python-client` y `google-auth` agregadas al workflow.
- [x] **Proteger credenciales:** `*credentials*.json` agregado al `.gitignore`.

### Fase 3: Desarrollo del Motor Inteligente
- [x] **Módulo de Conexión:** `setup_drive()` — lista archivos de Drive via API.
- [x] **Módulo de Selección por IA:** `seleccionar_foto_drive()` — Gemini elige la foto más relevante por nombre de archivo.
- [x] **Motor híbrido:** Prioridad Drive > fotos_reales > DALL-E 3.
- [ ] **Soporte para Video:** Habilitar detección y publicación de videos cortos (Reels).
- [ ] **Registro de Uso:** Sistema que recuerde qué fotos ya se usaron para no repetirlas.

### Fase 4: Pruebas y Lanzamiento
- [x] **Prueba de Conexión:** Drive lista las fotos correctamente.
- [x] **Prueba de Publicación:** Posts publicados correctamente en Facebook e Instagram.
- [x] **Activación Final:** Cronjob de las 8:00 AM funcionando con el nuevo motor.

## Pendiente
- [ ] Mover el logo (`megagym-removebg-preview.png`) fuera de la carpeta raíz de Drive para evitar que sea seleccionado.
- [ ] Ampliar lista de temas (actualmente 10 temas fijos).
- [ ] Implementar registro de fotos usadas.
- [ ] Soporte para Reels/videos.

---
*Estado actual: Integración completa y funcionando en producción.*
*Última actualización: 28 de marzo de 2026*
