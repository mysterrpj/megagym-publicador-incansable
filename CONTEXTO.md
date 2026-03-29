# Contexto del Proyecto: MEGAGYM Publicador Incansable

Este archivo sirve para que cualquier IA (como Claude Code) entienda el estado actual, la arquitectura y los objetivos de este proyecto de automatización.

## 🎯 Objetivo Principal
Automatizar al 100% la creación y publicación de contenido para las redes sociales (Instagram, Facebook) del gimnasio **MEGAGYM**.

## 🏗️ Arquitectura Actual
1.  **Motor de Contenido (`publisher.py`):**
    *   Usa **Gemini 2.5 Flash** para generar el copy (texto) basado en una voz de marca profesional, motivadora y sin rellenos conversacionales.
    *   Elige 1 tema por ejecución desde un sistema de categorías rotativas (56 temas en 5 categorías) con soporte de fechas especiales peruanas.
    *   Usa el motor híbrido de imágenes con la siguiente prioridad:
        1. Busca en el **índice inteligente** (`indice_fotos.json`) — descripciones visuales generadas por Gemini de cada foto de Drive.
        2. Si no hay índice, busca por nombres de archivo en **Google Drive** (carpeta MEGAGYM con +400 fotos).
        3. Si no hay coincidencia, busca en la carpeta local `fotos_reales/`.
        4. Si tampoco hay coincidencia, usa **DALL-E 3** (OpenAI) para generar una imagen fotorrealista.
    *   Envía los datos (imagen + texto) a un Webhook de **Make.com** para la publicación final en Facebook e Instagram.
2.  **Automatización (GitHub Actions):**
    *   El flujo se dispara automáticamente **2 veces al día**:
        - **8:00 AM hora Perú** (13:00 UTC)
        - **8:00 PM hora Perú** (01:00 UTC)
    *   Configurado en `.github/workflows/publicar.yml`.
3.  **Indexación de Fotos (`indexar_fotos.py`):**
    *   Analiza visualmente cada foto de Drive con Gemini y genera una descripción.
    *   Guarda el índice en `indice_fotos.json` (commitado en el repo).
    *   Se ejecuta automáticamente **cada domingo a las 6:00 AM** para indexar fotos nuevas.
    *   Solo analiza fotos nuevas — las ya indexadas no se vuelven a procesar.
    *   Configurado en `.github/workflows/indexar.yml`.
4.  **Gestión de Datos:**
    *   `memory.md`: Contiene las directrices de voz y marca.
    *   `settings.json`: Almacena las API Keys y configuraciones locales (protegido por `.gitignore`). En GitHub se usan **Secrets**.
    *   `indice_fotos.json`: Índice de descripciones visuales de las fotos de Drive.

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
*   [x] 2 publicaciones diarias automáticas (8 AM y 8 PM hora Perú).
*   [x] Motor híbrido: Índice inteligente > Drive > fotos_reales > DALL-E 3.
*   [x] 56 temas organizados en 5 categorías (fuerza, cardio, nutrición, mentalidad, recuperación).
*   [x] Fechas especiales peruanas hardcodeadas (Fiestas Patrias, Día de la Madre, etc.).
*   [x] Indexación visual automática de fotos con Gemini (sin renombrar archivos).
*   [x] Integración con Google Drive (carpeta MEGAGYM, +400 fotos).
*   [x] Service Account `megagym-drive` en proyecto `megagym-publicador-incansable`.
*   [x] Limpieza de "conversación" en los textos (va directo al copy).
*   [x] Webhook URL movido a variable de entorno (seguridad).
*   [x] Credenciales de Drive protegidas con `.gitignore` y GitHub Secrets.

## 🚀 Próximos Pasos
1. **Ejecutar indexador por primera vez** — correr manualmente desde GitHub Actions → "Indexar Fotos Drive" → "Run workflow". Tarda ~20 min, solo se hace una vez.
2. **Registro de fotos usadas** — evitar repetir la misma imagen en días cercanos.
3. **Soporte para videos/Reels** — publicar videos cortos desde Drive.
4. **Ampliar temas** — agregar más temas a las categorías existentes según tendencias.

## 🛠️ Tecnologías en uso
*   Python 3.11
*   Google Generative AI (Gemini 2.5 Flash) — texto e imagen visual
*   Google Drive API v3 (Service Account)
*   OpenAI API (DALL-E 3)
*   GitHub Actions
*   Make.com (integración con Meta Business Suite)

## 📁 Archivos clave
| Archivo | Descripción |
|---------|-------------|
| `publisher.py` | Motor principal de generación y publicación |
| `indexar_fotos.py` | Indexador visual de fotos de Drive con Gemini |
| `indice_fotos.json` | Índice de descripciones de fotos (generado automáticamente) |
| `memory.md` | Voz y directrices de marca de MEGAGYM |
| `settings.json` | Configuración local (ignorado por git) |
| `.github/workflows/publicar.yml` | Workflow de publicación diaria (8 AM y 8 PM) |
| `.github/workflows/indexar.yml` | Workflow de indexación semanal (domingos 6 AM) |
| `fotos_reales/` | Galería local de fotos (fallback de Drive) |

---
*Última actualización: 29 de marzo de 2026*
