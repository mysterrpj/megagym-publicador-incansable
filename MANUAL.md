# 📱 Manual de Uso — Auto Redes Sociales MEGAGYM

Sistema de publicación automática de contenido en Facebook e Instagram mediante Inteligencia Artificial.

---

## ✅ Estado actual del sistema

El sistema publica **automáticamente 2 veces al día** desde GitHub, sin que toques nada:

| Hora | Qué hace |
|---|---|
| **8:00 AM hora Perú** | Publica 1 post en Facebook e Instagram |
| **8:00 PM hora Perú** | Publica 1 post en Facebook e Instagram |

No necesitas tener la PC encendida. Todo corre en la nube.

---

## ¿Cómo funciona el sistema?

1. GitHub Actions ejecuta `publisher.py` a las horas programadas.
2. El sistema elige un tema del día (de 56 temas en 5 categorías, o fecha especial si aplica).
3. **Gemini AI** genera el texto del post.
4. El sistema elige la mejor imagen de tu Google Drive usando el **índice inteligente**.
5. Si no encuentra imagen adecuada, no genera imagen por IA salvo que se active `PERMITIR_IMAGENES_IA=true`.
6. Envía todo a **Make.com**, que publica en Facebook e Instagram.

---

## 📂 Archivos clave

| Archivo | Función |
|---|---|
| `publisher.py` | Motor principal — genera y publica el contenido |
| `indexar_fotos.py` | Indexa visualmente tus fotos de Drive |
| `indice_fotos.json` | Índice de fotos (generado automáticamente) |
| `memory.md` | Voz y estilo de marca de MEGAGYM |
| `settings.json` | Claves API locales (no se sube a GitHub) |

---

## 🖼️ Cómo agregar fotos nuevas a Drive

1. Sube tus fotos a la carpeta MEGAGYM en Google Drive (desde el móvil o PC).
2. Ve a GitHub → pestaña **Actions** → **"Indexar Fotos Drive"** → **"Run workflow"**.
3. El sistema analiza solo las fotos nuevas y actualiza el índice automáticamente.

> El índice también se actualiza solo cada **domingo a las 6:00 AM** sin que hagas nada.

---

## Calendario de 30 días con fotos exactas

El archivo `calendario_publicaciones.csv` permite planificar 2 publicaciones diarias por 30 días.

Columnas principales:
```
fecha,hora,estado,tema,imagen_archivo,copy
```

Uso recomendado:
1. Revisa el tema de cada fila.
2. Prepara la foto adecuada con el nombre indicado en `imagen_archivo`.
3. Coloca la foto en la carpeta `posts_programados/`.
4. Cambia `estado` de `pendiente` a `lista`.
5. Si llenas `copy`, el sistema publicará ese texto exacto. Si lo dejas vacío, Gemini genera el texto usando el tema.

El publicador solo usa filas con estado `lista`, `programada` o `ready`. Las filas `pendiente` no se publican todavía, así el sistema actual sigue funcionando mientras preparas las 60 fotos.

---

## ▶️ Cómo publicar ahora mismo (manual)

Ve a GitHub → pestaña **Actions** → **"Publicador Automatico MEGAGYM"** → **"Run workflow"**.

Esto publica 1 post en ese momento, igual que si fuera las 8 AM.

---

## ⏸️ Cómo pausar el sistema

1. Ve a tu repo en GitHub
2. Pestaña **Actions**
3. Clic en **"Publicador Automatico MEGAGYM"**
4. Clic en **`...`** (esquina superior derecha)
5. Selecciona **"Disable workflow"**

Para reactivarlo, repite los pasos y selecciona **"Enable workflow"**.

---

## ⏰ Cómo cambiar los horarios de publicación

Edita `.github/workflows/publicar.yml` y modifica las líneas cron:

```yaml
schedule:
  - cron: '0 13 * * *'   # 8:00 AM hora Perú (UTC-5)
  - cron: '0 1 * * *'    # 8:00 PM hora Perú (UTC-5)
```

Referencia de horas Perú → UTC:

| Hora Perú | UTC | Cron |
|---|---|---|
| 7:00 AM | 12:00 UTC | `'0 12 * * *'` |
| 8:00 AM | 13:00 UTC | `'0 13 * * *'` |
| 12:00 PM | 17:00 UTC | `'0 17 * * *'` |
| 6:00 PM | 23:00 UTC | `'0 23 * * *'` |
| 8:00 PM | 01:00 UTC | `'0 1 * * *'` |

---

## 📝 Cómo agregar temas de publicación

Abre `publisher.py` y busca `TEMAS_POR_CATEGORIA`. Agrega temas a la categoría que corresponda:

```python
TEMAS_POR_CATEGORIA = {
    "fuerza": [
        "tema existente...",
        "Tu nuevo tema aquí",  # <-- agrega así
    ],
    ...
}
```

Categorías disponibles: `fuerza`, `cardio`, `nutricion`, `mentalidad`, `recuperacion`.

---

## 📅 Cómo agregar fechas especiales

Abre `publisher.py` y busca `FECHAS_ESPECIALES`. Agrega la fecha con formato `(mes, dia)`:

```python
FECHAS_ESPECIALES = {
    (1, 1):  "Año Nuevo: texto del post...",
    (3, 15): "Tu fecha especial aquí",  # <-- agrega así
}
```

---

## ✍️ Cómo modificar la voz de marca

Edita `memory.md`. Contiene el tono, frases típicas y reglas de estilo de MEGAGYM. Cualquier cambio se aplica automáticamente al próximo post.

---

## 🔑 Cómo actualizar las claves API

Las claves están en GitHub como Secrets. Ve a:
**Repositorio → Settings → Secrets and variables → Actions**

Y actualiza el secret correspondiente.

---

## ❓ Preguntas frecuentes

**¿Puedo publicar más de 2 veces al día?**
Sí. Agrega más líneas cron en `.github/workflows/publicar.yml`.

**¿Qué pasa si hay un error?**
GitHub Actions muestra el error en el log. Al siguiente horario intenta de nuevo automáticamente.

**Si Make.com desactiva el escenario**
1. En Make.com abre el escenario → **History** → ejecución en rojo → **Details**.
2. Si el error menciona OAuth, token, permissions o Facebook Pages, ve a **Connections** y usa **Reauthorize** en la conexión de Facebook/Instagram.
3. Ve a **Show queue** o **Incomplete executions**, elimina o resuelve las ejecuciones fallidas y reactiva el escenario.
4. Para que no vuelva a tumbarse por un error aislado, agrega un **Error handler** en los módulos de Facebook/Instagram y termina esa ruta con **Ignore/Resume** o guardando el fallo en una tabla/log.

El publicador valida la URL de imagen antes de enviarla a Make. Si la imagen no es pública o no responde como imagen, la descarta para no mandar a Make una URL que pueda romper la ejecución.

**¿Cómo sé que publicó correctamente?**
Ve a GitHub → Actions → clic en la última ejecución. Deberías ver:
```
[Exito] Post de facebook recibido por Make.com.
[Exito] Post de instagram recibido por Make.com.
```

**¿Las fotos se renombran automáticamente?**
No. El sistema usa el **índice inteligente** — Gemini analiza visualmente cada foto y genera una descripción. No necesitas renombrar nada.

**¿Puedo subir fotos desde el móvil?**
Sí. Súbelas a Google Drive y luego ejecuta el indexador desde GitHub Actions → "Indexar Fotos Drive" → "Run workflow".
---

## Enviar tambien a estados de WhatsApp

El publicador puede reenviar cada post generado al proyecto `create-next-app` para que quede como tarea de estado de WhatsApp.

Secrets necesarios en GitHub:
```
WHATSAPP_IMPORT_URL=https://us-central1-status-architect-stitch.cloudfunctions.net/importExternalPost
WHATSAPP_IMPORT_KEY=la_misma_clave_configurada_en_firebase
WHATSAPP_IMPORT_USER_ID=uid_del_usuario_dueno_de_las_tareas
```

Opcional:
```
WHATSAPP_STATUS_TIMES=12:00,21:00
```

Por defecto, cada post se programa en el proximo horario libre: `12:00` o `21:00`, hora Peru. Asi el post de Facebook/Instagram de las `08:00` queda para WhatsApp a las `12:00`, y el de las `20:00` queda para WhatsApp a las `21:00`.

Grilla resultante:
```
08:00 megagym
10:30 streaming
12:00 megagym importado
13:00 streaming
16:30 megagym
19:30 streaming
21:00 megagym importado
22:00 streaming
```

Si faltan `WHATSAPP_IMPORT_URL` o `WHATSAPP_IMPORT_KEY`, el publicador sigue enviando a Facebook/Instagram y omite WhatsApp.
