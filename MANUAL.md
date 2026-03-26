# 📱 Manual de Uso — Auto Redes Sociales MEGAGYM

Sistema de publicación automática de contenido en Facebook e Instagram mediante Inteligencia Artificial.

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

Abre `auto_scheduler.py` y busca la **línea 25**:

```python
HORA_PUBLICACION = "10:00"
```

Cambia `"10:00"` por la hora que quieras en **formato 24 horas**:

| Publicar a... | Escribir |
|---|---|
| 9:00 AM | `"09:00"` |
| 12:00 PM | `"12:00"` |
| 6:00 PM | `"18:00"` |
| 8:30 PM | `"20:30"` |

Guarda el archivo, detén el programador (`Ctrl+C`) y vuelve a iniciarlo.

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
