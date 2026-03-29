# Contexto del Proyecto: MEGAGYM Publicador Incansable

Este archivo sirve para que cualquier IA (como Claude Code) entienda el estado actual, la arquitectura y los objetivos de este proyecto de automatización.

## 🎯 Objetivo Principal
Automatizar al 100% la creación y publicación de contenido para las redes sociales (Instagram, Facebook) del gimnasio **MEGAGYM**.

## 🏗️ Arquitectura Actual
1.  **Motor de Contenido (`publisher.py`):**
    *   Usa **Gemini 2.5 Flash** para generar el copy (texto) basado en una voz de marca profesional, motivadora y sin rellenos conversacionales.
    *   Usa el motor híbrido de imágenes con la siguiente prioridad:
        1. Busca en **Google Drive** (carpeta MEGAGYM con +400 fotos). Gemini analiza los nombres de archivo y elige la más relevante al tema.
        2. Si no hay coincidencia en Drive, busca en la carpeta local `fotos_reales/`.
        3. Si tampoco hay coincidencia, usa **DALL-E 3** (OpenAI) para generar una imagen fotorrealista.
    *   Envía los datos (imagen + texto) a un Webhook de **Make.com** para la publicación final en Facebook e Instagram.
2.  **Automatización (GitHub Actions):**
    *   El flujo se dispara automáticamente cada día a las **8:00 AM hora Perú/Colombia (13:00 UTC)**.
    *   Configurado en `.github/workflows/publicar.yml`.
3.  **Gestión de Datos:**
    *   `memory.md`: Contiene las directrices de voz y marca.
    *   `settings.json`: Almacena las API Keys y configuraciones locales (protegido por `.gitignore`). En GitHub se usan **Secrets**.

## 🔐 Secrets de GitHub Actions configurados
| Secret | Descripción |
|--------|-------------|
| `GOOGLE_API_KEY` | API Key de Gemini (proyecto: megagym-publicador-incansable) |
| `OPENAI_API_KEY` | API Key de OpenAI para DALL-E 3 |
| `MAKE_WEBHOOK_URL` | URL del webhook de Make.com |
| `GOOGLE_DRIVE_CREDENTIALS` | JSON de la Service Account para acceder a Drive |
| `GOOGLE_DRIVE_FOLDER_ID` | ID de la carpeta MEGAGYM en Drive |

## ✅ Logros Alcanzados
*   [x] Publicación automática desde la nube funcionando (Facebook + Instagram).
*   [x] Motor híbrido: Drive > fotos_reales > DALL-E 3.
*   [x] Integración con Google Drive (carpeta MEGAGYM, +400 fotos).
*   [x] Service Account `megagym-drive` en proyecto `megagym-publicador-incansable`.
*   [x] Limpieza de "conversación" en los textos (va directo al copy).
*   [x] Webhook URL movido a variable de entorno (seguridad).
*   [x] Credenciales de Drive protegidas con `.gitignore` y GitHub Secrets.

## 🚀 Próximos Pasos
1. **Registro de fotos usadas** — evitar repetir la misma imagen dos días seguidos.
2. **Soporte para videos/Reels** — publicar videos cortos desde Drive.
3. **Ampliar lista de temas** — actualmente son 10 temas fijos, se repiten cada ~10 días.

## 🛠️ Tecnologías en uso
*   Python 3.11
*   Google Generative AI (Gemini 2.5 Flash)
*   Google Drive API v3 (Service Account)
*   OpenAI API (DALL-E 3)
*   GitHub Actions
*   Make.com (integración con Meta Business Suite)

## 📁 Archivos clave
| Archivo | Descripción |
|---------|-------------|
| `publisher.py` | Motor principal de generación y publicación |
| `memory.md` | Voz y directrices de marca de MEGAGYM |
| `settings.json` | Configuración local (ignorado por git) |
| `.github/workflows/publicar.yml` | Workflow de automatización diaria |
| `fotos_reales/` | Galería local de fotos (fallback de Drive) |

---
*Última actualización: 28 de marzo de 2026*
