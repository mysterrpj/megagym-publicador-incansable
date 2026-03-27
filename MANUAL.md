# 📱 Manual de Uso — Auto Redes Sociales MEGAGYM

Sistema de publicación automática de contenido en Facebook e Instagram mediante Inteligencia Artificial.

---

## ✅ Estado actual del sistema

El sistema tiene **3 formas de ejecutarse**:

| Método | ¿Cuándo se usa? | ¿Requiere PC encendida? |
|---|---|---|
| **GitHub Actions** | Automático, todos los días a la hora programada | ❌ No |
| **`python auto_scheduler.py`** | Solo si tú lo inicias manualmente desde la terminal | ✅ Sí |
| **`python publisher.py`** | Cuando quieres publicar ahora mismo sin esperar | ✅ Sí |

**Recomendación:**
- Usa **GitHub Actions** como sistema principal — ya está activo y no necesitas hacer nada.
- Usa **`python publisher.py`** solo si quieres publicar algo en el momento.
- Ya **no necesitas correr `auto_scheduler.py`** para nada.

---

## ¿Cómo funciona el sistema?

El flujo es el siguiente:

1. **`auto_scheduler.py`** actúa como reloj interno — espera hasta la hora configurada y lanza el publicador.
2. **`publisher.py`** elige un tema al azar, genera el copy con **Gemini AI**, genera una imagen con **DALL-E 3** y lo envía a **Make.com**.
3. **Make.com** recibe el contenido y lo publica en **Facebook** e **Instagram**.

**Archivos clave:**

| Archivo | Función |
|---|---|
| `auto_scheduler.py` | El "reloj" — lanza la publicación a la hora configurada |
| `publisher.py` | El "publicador" — genera contenido con IA y lo envía |
| `memory.md` | La voz de marca de MEGAGYM (tono, frases, estilo) |
| `settings.json` | Claves API de Gemini y OpenAI |

---

## ▶️ Cómo arrancar el sistema

Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
python auto_scheduler.py
```

> [!IMPORTANT]
> **Debes dejar la ventana de la consola abierta** (puede estar minimizada). Si la cierras, el programador se detiene.

## ⏹️ Cómo detener el sistema

Haz clic en la ventana de la consola y presiona **Ctrl + C**.

---

## ⏰ Cómo cambiar el horario de publicación

El horario se controla desde el archivo `.github/workflows/publicar.yml`. Puedes editarlo de dos formas:

### Opción A — Desde tu PC (VS Code)

Abre `.github/workflows/publicar.yml` y busca esta línea:

```yaml
- cron: '0 15 * * *'
```

Cambia el número `15` por la hora UTC que quieras (**hora Perú/Colombia + 5 = UTC**):

| Publicar a... | Hora UTC | Cron |
|---|---|---|
| 8:00 AM | 13:00 UTC | `'0 13 * * *'` |
| 10:00 AM | 15:00 UTC | `'0 15 * * *'` (actual) |
| 6:00 PM | 23:00 UTC | `'0 23 * * *'` |
| 8:00 PM | 01:00 UTC | `'0 1 * * *'` |

Para publicar **varias veces al día**, agrega más líneas cron:

```yaml
on:
  schedule:
    - cron: '0 13 * * *'   # 8:00 AM hora Perú
    - cron: '0 1 * * *'    # 8:00 PM hora Perú
```

Luego guarda y sube los cambios a GitHub desde la terminal:

```bash
git add .
git commit -m "cambiar hora de publicacion"
git push origin master
```

### Opción B — Directamente desde GitHub (sin abrir VS Code)

1. Ve a tu repo → carpeta `.github/workflows/` → clic en `publicar.yml`
2. Clic en el ícono del **lápiz ✏️** (editar)
3. Cambia el valor del cron
4. Clic en **"Commit changes"**

---

## ⏸️ Cómo pausar o detener el sistema en GitHub

1. Ve a tu repo: https://github.com/mysterrpj/megagym-publicador-incansable
2. Haz clic en la pestaña **Actions**
3. En el menú izquierdo haz clic en **"Publicador Automatico MEGAGYM"**
4. Haz clic en el botón **`...`** en la esquina superior derecha de esa página
5. Selecciona **"Disable workflow"** para pausarlo

Para reactivarlo, repite los pasos y selecciona **"Enable workflow"**.

---

## 🎯 Cómo agregar o cambiar los temas de publicación

Abre `publisher.py` y busca `lista_temas` (línea ~135). Agrega o elimina temas según necesites:

```python
lista_temas = [
    "Por que el entrenamiento de fuerza es mejor que el cardio...",
    "Tu nuevo tema aquí",   # <-- agrega así
]
```

El sistema elige uno al azar cada día.

---

## ✍️ Cómo modificar la voz de marca

Edita `memory.md`. Contiene el tono, frases típicas y reglas de estilo de MEGAGYM. Cualquier cambio se aplica automáticamente al próximo post sin reiniciar nada.

---

## 🔑 Cómo actualizar las claves API

Abre `settings.json` y reemplaza el valor correspondiente:

```json
{
  "gemini":  { "api_key": "TU_NUEVA_CLAVE_AQUI" },
  "openai":  { "api_key": "TU_NUEVA_CLAVE_AQUI" }
}
```

---

## 🚀 Publicar manualmente ahora mismo

Si no quieres esperar al horario programado:

```bash
python publisher.py
```

---

## ❓ Preguntas frecuentes

**¿Puedo publicar más de una vez al día?**
Sí. En `auto_scheduler.py` agrega más líneas antes del bucle:
```python
schedule.every().day.at("09:00").do(job_publicar)
schedule.every().day.at("18:00").do(job_publicar)
```

**¿Qué pasa si hay un error?**
El programador muestra el error en consola pero sigue corriendo. Al día siguiente intenta publicar de nuevo.

**¿Cómo sé que publicó correctamente?**
La consola mostrará:
```
[Exito] Post de facebook recibido por Make.com.
[Exito] Post de instagram recibido por Make.com.
```
