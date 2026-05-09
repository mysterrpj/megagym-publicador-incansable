import os
import io
import base64
import requests
import sys
import time
import json
import random
import re
import unicodedata
import csv
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote
import google.generativeai as genai
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ─── HISTORIAL DE FOTOS ─────────────────────────────────────────────────────
DIAS_HISTORIAL = int(os.environ.get("DIAS_HISTORIAL_FOTOS", "45"))
MAX_CANDIDATAS_IA = int(os.environ.get("MAX_CANDIDATAS_IA", "18"))
CALENDARIO_PUBLICACIONES = os.environ.get("CALENDARIO_PUBLICACIONES", "calendario_publicaciones.csv")
CARPETA_POSTS_PROGRAMADOS = os.environ.get("CARPETA_POSTS_PROGRAMADOS", "posts_programados")
MAX_INSTAGRAM_CAPTION_CHARS = 1800
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "chatgpt-image-latest")
PERMITIR_IMAGENES_IA = os.environ.get("PERMITIR_IMAGENES_IA", "false").lower() == "true"
GEMINI_MAX_INTENTOS = int(os.environ.get("GEMINI_MAX_INTENTOS", "3"))
GEMINI_ESPERA_BASE_SEGUNDOS = int(os.environ.get("GEMINI_ESPERA_BASE_SEGUNDOS", "60"))
DEFAULT_IMAGE_URL = os.environ.get(
    "DEFAULT_IMAGE_URL",
    "https://raw.githubusercontent.com/mysterrpj/megagym-publicador-incansable/master/fotos_reales/flyer_personalizado_1.jpg"
)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
PALABRAS_FIRMA_IGNORADAS = {
    "foto", "fotografia", "real", "imagen", "muestra", "gimnasio", "megagym",
    "mega", "gym", "persona", "hombre", "mujer", "joven", "atletica", "deportiva",
    "deportivo", "ropa", "equipo", "fondo", "contexto", "donde", "esta", "este",
    "esta", "una", "uno", "unos", "unas", "con", "del", "las", "los", "para",
    "por", "que", "sin", "junto", "sobre", "tipo", "diseno", "grafico"
}

def normalizar_texto(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower()

def clave_archivo(nombre):
    base = os.path.splitext(os.path.basename(nombre or ""))[0]
    base = normalizar_texto(base)
    return re.sub(r"[^a-z0-9]+", "", base)

def texto_visual_indice(item):
    partes = [
        item.get('nombre_sugerido'),
        item.get('categoria_visual'),
        item.get('tipo_visual'),
        item.get('descripcion'),
        item.get('nombre'),
    ]
    return " ".join(str(p) for p in partes if p)

def firma_visual(descripcion=None, nombre=None):
    base = normalizar_texto(descripcion or nombre or "")
    tokens = re.findall(r"[a-z0-9]+", base)
    utiles = []
    for token in tokens:
        if len(token) < 4 or token in PALABRAS_FIRMA_IGNORADAS:
            continue
        utiles.append(token)
        if len(utiles) >= 10:
            break
    return "|".join(utiles) if utiles else None

def cargar_firmas_indice():
    try:
        with open('indice_fotos.json', 'r', encoding='utf-8') as f:
            indice = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    firmas = {}
    for item in indice:
        firma = firma_visual(texto_visual_indice(item), item.get('nombre'))
        if not firma:
            continue
        if item.get('id'):
            firmas[item['id']] = firma
        if item.get('nombre'):
            firmas[item['nombre']] = firma
    return firmas

def foto_ya_usada(foto_id=None, foto_nombre=None, ids_usados=None, foto_firma=None):
    if not ids_usados:
        return False
    foto_clave = clave_archivo(foto_nombre)
    return bool(
        (foto_id and foto_id in ids_usados)
        or (foto_nombre and foto_nombre in ids_usados)
        or (foto_clave and foto_clave in ids_usados)
        or (foto_firma and foto_firma in ids_usados)
    )

def cargar_historial():
    """Carga el historial de fotos usadas. Devuelve (lista_completa, set_de_ids_recientes)."""
    try:
        with open('historial_fotos.json', 'r', encoding='utf-8') as f:
            historial = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        historial = []

    historial = deduplicar_historial(historial)
    hoy = date.today()
    limite = hoy - timedelta(days=DIAS_HISTORIAL)
    ids_usados = set()
    firmas_indice = cargar_firmas_indice()
    for h in historial:
        if date.fromisoformat(h['fecha']) < limite:
            continue
        if h.get('id'):
            ids_usados.add(h['id'])
            if h['id'] in firmas_indice:
                ids_usados.add(firmas_indice[h['id']])
        if h.get('nombre'):
            ids_usados.add(h['nombre'])
            clave = clave_archivo(h['nombre'])
            if clave:
                ids_usados.add(clave)
            if h['nombre'] in firmas_indice:
                ids_usados.add(firmas_indice[h['nombre']])
        if h.get('firma'):
            ids_usados.add(h['firma'])
        if h.get('clave'):
            ids_usados.add(h['clave'])
    print(f"[Historial] {len(ids_usados)} fotos usadas en los últimos {DIAS_HISTORIAL} días.")
    return historial, ids_usados

def deduplicar_historial(historial):
    vistos = set()
    depurado = []
    for entrada in sorted(historial, key=lambda h: h.get("fecha", ""), reverse=True):
        claves = [
            entrada.get("id"),
            entrada.get("nombre"),
            entrada.get("clave") or clave_archivo(entrada.get("nombre")),
            entrada.get("firma"),
        ]
        claves = [clave for clave in claves if clave]
        if any(clave in vistos for clave in claves):
            continue
        vistos.update(claves)
        if entrada.get("nombre") and not entrada.get("clave"):
            entrada["clave"] = clave_archivo(entrada.get("nombre"))
        depurado.append(entrada)
    return sorted(depurado, key=lambda h: h.get("fecha", ""))

def guardar_historial(historial, foto_id, foto_nombre, descripcion=None):
    """Agrega una foto al historial y guarda el archivo. Devuelve la lista actualizada."""
    entrada = {"id": foto_id, "nombre": foto_nombre, "fecha": date.today().isoformat()}
    clave = clave_archivo(foto_nombre)
    if clave:
        entrada["clave"] = clave
    firma = firma_visual(descripcion, foto_nombre)
    if firma:
        entrada["firma"] = firma
    historial.append(entrada)
    # Limpiar entradas más antiguas que 60 días para no crecer infinitamente
    limite = date.today() - timedelta(days=max(DIAS_HISTORIAL, 60))
    historial = [h for h in historial if date.fromisoformat(h['fecha']) >= limite]
    historial = deduplicar_historial(historial)
    with open('historial_fotos.json', 'w', encoding='utf-8') as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)
    print(f"[Historial] Foto guardada: {foto_nombre}")
    return historial

# ─── FECHAS ESPECIALES (Perú) ───────────────────────────────────────────────
FECHAS_ESPECIALES = {
    (1, 1):  "Año Nuevo: el mejor momento para empezar a entrenar es hoy — bienvenido al primer día de tu mejor año en MEGAGYM",
    (2, 14): "San Valentín: date el mejor regalo — un cuerpo fuerte y una mente sana. Entrena en MEGAGYM",
    (3, 8):  "Día Internacional de la Mujer: las mujeres que entrenan no piden permiso — son imparables",
    (7, 28): "Fiestas Patrias: celebra el Perú con energía — los campeones no toman días libres",
    (7, 29): "Fiestas Patrias: orgullo peruano dentro y fuera del gym — sigue entrenando fuerte",
    (8, 30): "Santa Rosa de Lima: un feriado no es excusa para parar — los resultados no esperan",
    (10, 8): "Día del Combate de Angamos: el espíritu guerrero no descansa — tampoco tus entrenamientos",
    (12, 24): "Nochebuena: la mejor versión de ti mismo es el regalo que te mereces — no pares en diciembre",
    (12, 25): "Navidad: el gimnasio no cierra en tu mente — mantén el hábito aunque sea Navidad",
    (12, 31): "Último día del año: termina fuerte como empezaste — MEGAGYM cierra el año contigo",
}

# ─── TEMAS POR CATEGORÍA ────────────────────────────────────────────────────
TEMAS_POR_CATEGORIA = {
    "fuerza": [
        "Por qué el entrenamiento de fuerza es mejor que el cardio para perder grasa",
        "Los beneficios de hacer sentadillas y peso muerto",
        "Cómo aumentar tu fuerza máxima en 8 semanas",
        "Por qué deberías hacer press de banca si quieres un pecho definido",
        "Dominadas: el ejercicio más completo para espalda y bíceps",
        "Cómo evitar estancarte en tus levantamientos",
        "La diferencia entre hipertrofia y fuerza — y cuál te conviene",
        "Por qué el peso muerto debería ser obligatorio en toda rutina",
        "Cómo estructurar una rutina de fuerza efectiva de 4 días",
        "El error más común al hacer sentadilla y cómo corregirlo",
        "Volumen vs intensidad: qué importa más para ganar músculo",
        "Por qué los ejercicios compuestos dan mejores resultados que los aislados",
    ],
    "cardio": [
        "HIIT vs cardio moderado: cuál quema más grasa",
        "Por qué caminar en ayunas puede cambiar tu composición corporal",
        "Cardio después de pesas: buena o mala idea",
        "Cómo hacer cardio sin perder músculo",
        "El entrenamiento de intervalos que te hará quemar calorías 24 horas",
        "Por qué correr no es la única forma de hacer cardio",
        "Saltar la cuerda: el cardio más subestimado del gym",
        "Cuánto cardio necesitas realmente para bajar de peso",
        "La bicicleta estática: beneficios que no conocías",
        "Cardio en ayunas: mito o realidad",
    ],
    "nutricion": [
        "Mito y verdad sobre los batidos de proteína post-entrenamiento",
        "Por qué no necesitas comer 6 veces al día para ver resultados",
        "Cuánta proteína necesitas realmente para ganar músculo",
        "Los mejores alimentos para ganar masa muscular sin grasa",
        "Hidratación y rendimiento: por qué el agua es tu mejor suplemento",
        "Carbohidratos: enemigos o aliados del entrenamiento",
        "Por qué el desayuno pre-entreno puede cambiar tu rendimiento",
        "Los suplementos que sí funcionan y los que son un gasto de dinero",
        "Comer sano sin gastar mucho: guía práctica",
        "Por qué el déficit calórico es la única forma real de perder grasa",
        "Qué comer antes y después de entrenar",
        "La creatina: el suplemento más estudiado del mundo",
    ],
    "mentalidad": [
        "Cómo mantener la disciplina cuando la motivación desaparece",
        "Por qué no deberías cambiar de rutina cada dos semanas",
        "Cómo prepararse mentalmente antes de un levantamiento pesado",
        "El mayor error de los principiantes en el gym y cómo evitarlo",
        "La diferencia entre los que logran resultados y los que no",
        "Por qué la constancia vale más que la intensidad",
        "Cómo vencer la pereza y no faltar al gym",
        "El síndrome del lunes: por qué siempre empezamos y nunca terminamos",
        "Cómo establecer metas realistas en el gym y cumplirlas",
        "Por qué compararte con otros te frena — enfócate en tu progreso",
        "El poder del hábito: cómo hacer que el gym sea automático en tu vida",
        "Por qué los resultados tardan y cómo no rendirse",
    ],
    "recuperacion": [
        "La importancia de dormir al menos 7-8 horas para ganar músculo",
        "El impacto del estrés diario en tus resultados del gimnasio",
        "Por qué los días de descanso son parte del entrenamiento",
        "Estiramientos post-entreno: cuáles son los más importantes",
        "Cómo reducir el dolor muscular después de entrenar fuerte",
        "El foam roller: tu herramienta de recuperación más barata",
        "Por qué el sueño es el suplemento más poderoso que existe",
        "Sobreentrenamiento: señales de que tu cuerpo necesita descansar",
        "La semana de descarga: qué es y por qué deberías hacerla",
        "Cómo recuperarte más rápido entre sesiones de entrenamiento",
    ],
    "tendencias_2026": [
        "Wearables en el gym: cómo usar pasos, sueño y frecuencia cardiaca sin obsesionarte",
        "Entrenamientos cortos tipo snack: 20 minutos bien hechos valen más que 2 horas sin plan",
        "Fuerza funcional: entrena para verte mejor y moverte mejor en la vida real",
        "Core, equilibrio y movilidad: la base que muchos ignoran hasta que se lesionan",
        "Entrenar por datos: cómo saber si hoy toca pesado o toca bajar la intensidad",
        "Longevidad fitness: por qué levantar pesas también es cuidar tu futuro",
        "Fitness social: entrenar acompañado aumenta la constancia y baja las excusas",
        "Sueño y recuperación medidos: cuándo los números ayudan y cuándo solo distraen",
    ],
    "tecnica_y_errores": [
        "Tres errores que arruinan tu sentadilla y cómo corregirlos",
        "Por qué no sientes el pecho en press banca y qué ajustar",
        "Remo con mancuerna: el detalle que cambia toda la espalda",
        "Hip thrust bien hecho: menos ego y más control",
        "Peso muerto sin destruir tu espalda: claves simples antes de cargar más",
        "Curl de bíceps: por qué balancearte te roba resultados",
        "Prensa de piernas: profundidad, pies y control para entrenar mejor",
        "Jalón al pecho: cómo activar la espalda sin convertirlo en bíceps",
        "Calentamiento inteligente: qué hacer antes de tocar pesos pesados",
        "Rango de movimiento: por qué las repeticiones a medias frenan tu progreso",
    ],
    "rutinas_practicas": [
        "Rutina de piernas para volver al gym después de una pausa",
        "Rutina de espalda y bíceps para construir una base fuerte",
        "Rutina full body para personas con poco tiempo",
        "Rutina de glúteos sin inventos raros: básicos que sí funcionan",
        "Rutina push pull legs: cuándo te conviene y cómo empezar",
        "Entrenamiento de 45 minutos: cómo aprovechar cada serie",
        "Plan simple para principiantes: máquinas, mancuernas y constancia",
        "Rutina para quemar grasa sin abandonar las pesas",
        "Día de torso: ejercicios clave para verte más fuerte",
        "Día de piernas: cómo entrenar cuádriceps, femorales y glúteos con orden",
    ],
    "principiantes": [
        "Tu primer mes en el gym: qué esperar y qué no exigirle a tu cuerpo",
        "Cómo perder el miedo a las máquinas si recién empiezas",
        "Cuánto peso usar cuando no sabes por dónde comenzar",
        "Por qué copiar la rutina de otro puede frenarte",
        "La técnica primero: el atajo real para progresar más rápido",
        "Cómo saber si estás entrenando fuerte o solo cansándote",
        "Lo que nadie te dice cuando vuelves al gym después de años",
        "Constancia mínima efectiva: cuántos días necesitas para empezar bien",
    ],
    "comunidad_megagym": [
        "La energía del gym también entrena tu disciplina",
        "Entrenar rodeado de gente enfocada cambia tu mentalidad",
        "No necesitas empezar perfecto: necesitas empezar acompañado",
        "El ambiente importa: por qué elegir un gimnasio donde sí te provoque volver",
        "Historias reales de progreso: el cambio empieza con una decisión repetida",
        "Entrenar en MEGAGYM: máquinas, ambiente y gente con ganas de avanzar",
        "De principiante a constante: el progreso que no siempre se ve en la balanza",
        "La disciplina se contagia cuando entrenas en el lugar correcto",
    ],
    "promociones_y_conversion": [
        "Por qué pagar el gym no basta: ven y úsalo con un plan real",
        "Empieza hoy en MEGAGYM: deja de esperar el lunes perfecto",
        "Tres meses pueden cambiar tu rutina si entrenas con constancia",
        "El mejor momento para inscribirte fue antes; el segundo mejor es hoy",
        "Ven a entrenar, conoce el ambiente y decide con hechos",
        "Promoción activa: convierte tu intención en entrenamiento real",
        "No compres motivación: compra compromiso y ven a entrenar",
        "Tu próxima transformación empieza con una visita al gym",
    ],
    "nutricion_actual": [
        "Proteína simple: cómo llegar a tu meta diaria sin complicarte",
        "Creatina sin mitos: qué hace y qué no hace por tu cuerpo",
        "Bebidas proteicas y snacks fitness: cómo elegir sin caer en puro marketing",
        "Fibra y músculo: por qué tu digestión también afecta tu rendimiento",
        "Comer para entrenar: qué hacer si llegas sin energía al gym",
        "Déficit calórico sin pasar hambre: estrategia antes que castigo",
        "Volumen limpio: cómo subir masa sin convertirlo en excusa para comer de todo",
        "Pre-entreno real: comida, sueño y agua antes que estimulantes",
    ],
}


def seleccionar_temas_del_dia():
    hoy = date.today()
    temas = []

    # Verificar fecha especial fija
    tema_especial = FECHAS_ESPECIALES.get((hoy.month, hoy.day))

    # Día de la Madre: segundo domingo de mayo
    if not tema_especial and hoy.month == 5:
        primer_dia_mayo = date(hoy.year, 5, 1)
        primer_domingo = primer_dia_mayo + timedelta(days=(6 - primer_dia_mayo.weekday()) % 7)
        segundo_domingo = primer_domingo + timedelta(days=7)
        if hoy == segundo_domingo:
            tema_especial = "Día de la Madre: mamá que entrena, mamá que inspira — feliz día a todas las madres de MEGAGYM"

    # Día del Padre: tercer domingo de junio
    if not tema_especial and hoy.month == 6:
        primer_dia_junio = date(hoy.year, 6, 1)
        primer_domingo = primer_dia_junio + timedelta(days=(6 - primer_dia_junio.weekday()) % 7)
        tercer_domingo = primer_domingo + timedelta(days=14)
        if hoy == tercer_domingo:
            tema_especial = "Día del Padre: papá que entrena, papá que inspira — feliz día a todos los padres de MEGAGYM"

    if tema_especial:
        temas.append(tema_especial)

    # Rellenar hasta 2 temas con categorías distintas al azar
    categorias = list(TEMAS_POR_CATEGORIA.keys())
    random.shuffle(categorias)
    for categoria in categorias:
        if len(temas) >= 1:
            break
        temas.append(random.choice(TEMAS_POR_CATEGORIA[categoria]))

    return temas

def slot_publicacion_actual(ahora=None):
    ahora = ahora or datetime.now(ZoneInfo("America/Lima"))
    if ahora.hour < 14:
        return "08:00"
    return "20:00"

def detectar_tipo_asset(archivo, tipo=None):
    tipo = (tipo or "").strip().lower()
    if tipo in {"imagen", "image"}:
        return "image"
    if tipo in {"video", "reel"}:
        return "video"

    extension = os.path.splitext((archivo or "").split("?", 1)[0].lower())[1]
    if extension in VIDEO_EXTENSIONS:
        return "video"
    return "image"

def url_asset_programado(asset_archivo):
    asset_archivo = (asset_archivo or "").strip()
    if not asset_archivo:
        return None
    if asset_archivo.startswith(("http://", "https://")):
        return asset_archivo

    repo = os.environ.get("GITHUB_REPOSITORY", "mysterrpj/megagym-publicador-incansable")
    branch = os.environ.get("GITHUB_REF_NAME", "master")
    ruta = f"{CARPETA_POSTS_PROGRAMADOS}/{asset_archivo}".replace("\\", "/")
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{quote(ruta, safe='/')}"

def url_imagen_programada(imagen_archivo):
    return url_asset_programado(imagen_archivo)

def cargar_publicacion_programada():
    if not os.path.exists(CALENDARIO_PUBLICACIONES):
        return None

    ahora = datetime.now(ZoneInfo("America/Lima"))
    fecha_objetivo = os.environ.get("PUBLICACION_FECHA") or ahora.date().isoformat()
    hora_objetivo = os.environ.get("PUBLICACION_HORA") or slot_publicacion_actual(ahora)

    try:
        with open(CALENDARIO_PUBLICACIONES, "r", encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
    except Exception as e:
        print(f"[Calendario] No se pudo leer {CALENDARIO_PUBLICACIONES}: {e}")
        return None

    for fila in filas:
        if (fila.get("fecha") or "").strip() != fecha_objetivo:
            continue
        if (fila.get("hora") or "").strip() != hora_objetivo:
            continue

        estado = (fila.get("estado") or "").strip().lower()
        if estado not in {"lista", "programada", "ready"}:
            print(f"[Calendario] Publicacion {fecha_objetivo} {hora_objetivo} esta en estado '{estado or 'sin estado'}'. No se publicara fallback automatico.")
            return {
                "skip": True,
                "fecha": fecha_objetivo,
                "hora": hora_objetivo,
                "estado": estado,
            }

        asset_archivo = (fila.get("archivo") or fila.get("imagen_archivo") or "").strip()
        asset_type = detectar_tipo_asset(asset_archivo, fila.get("tipo"))
        asset_url = url_asset_programado(asset_archivo)
        publicacion = {
            "fecha": fecha_objetivo,
            "hora": hora_objetivo,
            "tema": (fila.get("tema") or "").strip(),
            "copy": (fila.get("copy") or "").strip(),
            "asset_archivo": asset_archivo,
            "asset_type": asset_type,
            "asset_url": asset_url,
            "imagen_archivo": asset_archivo,
            "imagen_url": asset_url if asset_type == "image" else None,
        }
        print(f"[Calendario] Publicacion programada encontrada: {fecha_objetivo} {hora_objetivo}")
        return publicacion

    print(f"[Calendario] No hay publicacion lista para {fecha_objetivo} {hora_objetivo}. Se usara el flujo automatico.")
    return None

def get_webhook_url():
    url = os.environ.get("MAKE_WEBHOOK_URL")
    if not url:
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                url = settings.get('make', {}).get('webhook_url')
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    if not url:
        print("Error: No se encontro MAKE_WEBHOOK_URL en variables de entorno ni en settings.json.")
        sys.exit(1)
    return url

def setup_drive():
    creds_json = os.environ.get("GOOGLE_DRIVE_CREDENTIALS")
    folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")

    if not creds_json:
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                drive_cfg = settings.get('google_drive', {})
                folder_id = folder_id or drive_cfg.get('folder_id')
                creds_path = drive_cfg.get('credentials_path')
                if creds_path:
                    with open(creds_path, 'r') as cf:
                        creds_json = cf.read()
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if not creds_json or not folder_id:
        print("Advertencia: Credenciales de Google Drive no encontradas. Se omitira Drive.")
        return None, None

    creds_data = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    service = build('drive', 'v3', credentials=credentials)
    return service, folder_id

def seleccionar_foto_drive(modelo, tema_post, drive_service, folder_id, ids_usados=None):
    # Intentar usar el índice inteligente si existe
    try:
        with open('indice_fotos.json', 'r', encoding='utf-8') as f:
            indice = json.load(f)
        if indice:
            print(f"Usando índice inteligente ({len(indice)} fotos indexadas)...")
            return _seleccionar_por_indice(modelo, tema_post, indice, ids_usados)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Fallback: selección por nombres de archivo
    print("Índice no encontrado. Usando selección por nombres...")
    return _seleccionar_por_nombres(modelo, tema_post, drive_service, folder_id, ids_usados)


def _seleccionar_por_indice(modelo, tema_post, indice, ids_usados=None):
    indice_filtrado = [
        item for item in indice
        if not foto_ya_usada(
            item.get('id'),
            item.get('nombre'),
            ids_usados,
            firma_visual(texto_visual_indice(item), item.get('nombre'))
        )
    ] if ids_usados else indice
    if not indice_filtrado:
        print("Todas las fotos del índice fueron usadas recientemente. Se usará fallback.")
        return None
    else:
        print(f"Índice filtrado: {len(indice_filtrado)} fotos disponibles (de {len(indice)} totales).")

    random.shuffle(indice_filtrado)
    indice_candidatas = indice_filtrado[:MAX_CANDIDATAS_IA]
    print(f"Seleccion IA limitada a {len(indice_candidatas)} candidatas aleatorias para variar publicaciones.")

    descripciones = [
        (
            f"{item['nombre']} | sugerido: {item.get('nombre_sugerido', 'sin-nombre')} "
            f"| categoria: {item.get('categoria_visual', 'otro')} "
            f"| tipo: {item.get('tipo_visual', 'otro')} "
            f"| descripcion: {item.get('descripcion', '')}"
        )
        for item in indice_candidatas
    ]

    prompt = f"""
    Tengo las siguientes fotos indexadas de mi gimnasio: {descripciones}
    El post de hoy es sobre: "{tema_post}"

    ¿Cuál foto encaja mejor con el tema del post?
    REGLAS:
    1. PRIORIZA fotos de personas entrenando, ejercitándose o en el gimnasio.
    2. NUNCA elijas imágenes descritas como logo, fondo transparente, watermark o removebg.
    3. Flyers y banners promocionales SÍ son válidos si el tema lo justifica.
    4. Responde ÚNICAMENTE con el nombre del archivo exacto.
    5. NO incluyas introducciones ni explicaciones.
    6. Usa "NONE" solo si TODAS son logos o fondos transparentes.
    """

    try:
        respuesta = modelo.generate_content(prompt).text.strip()
        respuesta = respuesta.replace('"', '').replace("'", "").strip()

        foto = next((item for item in indice_candidatas if item['nombre'] == respuesta), None)
        if not foto or respuesta.upper() == "NONE":
            print("No se encontró coincidencia en el índice. Se usará fallback.")
            return None
        foto_firma = firma_visual(texto_visual_indice(foto), foto.get('nombre'))
        if foto_ya_usada(foto.get('id'), foto.get('nombre'), ids_usados, foto_firma):
            print("La foto elegida ya fue usada recientemente. Se usará fallback.")
            return None

        print(f"Foto seleccionada del índice: {respuesta}")
        return (f"https://lh3.googleusercontent.com/d/{foto['id']}", foto['id'], foto['nombre'], texto_visual_indice(foto))
    except Exception as e:
        print(f"Error seleccionando foto del índice: {e}")
        return None


def _seleccionar_por_nombres(modelo, tema_post, drive_service, folder_id, ids_usados=None):
    try:
        results = drive_service.files().list(
            q=f"'{folder_id}' in parents and mimeType contains 'image/' and trashed=false",
            fields="files(id, name)",
            pageSize=500
        ).execute()
        fotos = results.get('files', [])
    except Exception as e:
        print(f"Error listando fotos de Drive: {e}")
        return None

    if not fotos:
        print("No se encontraron fotos en Drive.")
        return None

    fotos_filtradas = [
        f for f in fotos
        if not foto_ya_usada(f.get('id'), f.get('name'), ids_usados)
    ] if ids_usados else fotos
    if not fotos_filtradas:
        print("Todas las fotos de Drive fueron usadas recientemente. Se usara fallback.")
        return None
    else:
        print(f"Drive filtrado: {len(fotos_filtradas)} fotos disponibles (de {len(fotos)} totales).")

    random.shuffle(fotos_filtradas)
    fotos_candidatas = fotos_filtradas[:MAX_CANDIDATAS_IA]
    print(f"Analizando {len(fotos_candidatas)} fotos candidatas en Drive por nombre...")
    nombres = [f['name'] for f in fotos_candidatas]

    prompt = f"""
    Tengo las siguientes fotos en mi biblioteca de Google Drive: {nombres}
    He escrito un post sobre el siguiente tema: "{tema_post}"

    ¿Cuál de estas fotos encaja mejor con el tema del post?
    REGLAS:
    1. PRIORIZA fotos de personas entrenando, ejercitándose o en el gimnasio.
    2. NUNCA elijas archivos que contengan en su nombre: "logo", "removebg", "watermark" o "megagym-remove". Son logos con fondo transparente, no imágenes publicables.
    3. Si el tema es de entrenamiento (fuerza, cardio, ejercicios, sudor, pesas), ELIGE la foto de persona que más se acerque, aunque no sea exacta.
    4. Responde ÚNICAMENTE con el nombre del archivo exacto.
    5. NO incluyas introducciones ni explicaciones.
    6. Usa "NONE" solo si TODAS las fotos son logos o imágenes con fondo transparente.
    """

    try:
        respuesta = modelo.generate_content(prompt).text.strip()
        respuesta = respuesta.replace('"', '').replace("'", "").strip()

        foto = next((f for f in fotos_candidatas if f['name'] == respuesta), None)
        if not foto or respuesta.upper() == "NONE":
            print("No coincidio ninguna foto de Drive. Se usara fallback.")
            return None
        if foto_ya_usada(foto.get('id'), foto.get('name'), ids_usados):
            print("La foto elegida ya fue usada recientemente. Se usara fallback.")
            return None

        file_id = foto['id']
        print(f"Foto seleccionada de Drive: {respuesta} (id: {file_id})")
        return (f"https://lh3.googleusercontent.com/d/{file_id}", file_id, foto['name'], None)
    except Exception as e:
        print(f"Error seleccionando foto de Drive: {e}")
        return None

def setup_gemini():
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                api_key = settings.get('gemini', {}).get('api_key')
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if not api_key:
        print("Error: No se encontro la API Key de Gemini ni en la variable de entorno GOOGLE_API_KEY ni en settings.json.")
        sys.exit(1)
        
    genai.configure(api_key=api_key)
    # Using gemini-2.5-flash for fast text generation
    return genai.GenerativeModel('gemini-2.5-flash')

def setup_openai():
    api_key = os.environ.get("OPENAI_API_KEY")
    
    if not api_key:
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                api_key = settings.get('openai', {}).get('api_key')
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if not api_key:
        print("Error: No se encontro la API Key de OpenAI ni en la variable de entorno OPENAI_API_KEY ni en settings.json.")
        sys.exit(1)
        
    return openai.OpenAI(api_key=api_key)

def get_memory_context():
    try:
        with open('memory.md', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print("Error: No se encontro el archivo memory.md con la voz de la marca.")
        sys.exit(1)

def limitar_caption_instagram(texto, max_chars=MAX_INSTAGRAM_CAPTION_CHARS):
    texto = texto.strip()
    if len(texto) <= max_chars:
        return texto

    limite = max_chars - 3
    corte = max(
        texto.rfind("\n\n", 0, limite),
        texto.rfind(". ", 0, limite),
        texto.rfind("! ", 0, limite),
        texto.rfind("? ", 0, limite),
        texto.rfind(" ", 0, limite),
    )
    if corte < int(max_chars * 0.65):
        corte = limite

    texto_recortado = texto[:corte].rstrip()
    print(f"[Caption] Texto recortado de {len(texto)} a {len(texto_recortado)} caracteres.")
    return texto_recortado + "..."

def extraer_espera_gemini(error):
    texto = str(error)
    patrones = [
        r"retry_delay\s*\{\s*seconds:\s*(\d+)",
        r"Please retry in\s+(\d+)",
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
        if match:
            return int(match.group(1)) + 5
    return GEMINI_ESPERA_BASE_SEGUNDOS

def generar_post_respaldo(tema):
    print("[Gemini] Usando copy de respaldo para no detener la publicacion.")
    texto = f"""¿Listo para entrenar con un plan real?

Hoy hablamos de {tema}. En MEGAGYM creemos que los resultados no salen de la suerte: salen de la constancia, la tecnica y un ambiente que te empuja a volver.

No necesitas hacerlo perfecto desde el primer dia. Necesitas empezar, moverte y sostener el habito.

Ven a MEGAGYM y entrena con nosotros.

#Megagym #FitnessReal #EntrenaHoy"""
    return limitar_caption_instagram(texto)

def generar_post_con_ia(modelo, memoria, tema="rutina de cuerpo completo para ocupados"):
    print(f"Generando nuevo post de Instagram sobre: '{tema}'...")
    
    prompt = f"""
    Actúa como el creador de contenido de MEGAGYM.
    Necesito que escribas UN post de Instagram cautivador sobre el siguiente tema: {tema}.
    
    INSTRUCCIONES CRÍTICAS:
    1. DEBES seguir estrictamente la siguiente guía de Voz de Marca:
    
    {memoria}
    
    2. El post debe tener:
       - Un gancho fuerte en la primera línea.
       - Desarrollo del valor educativo/motivador.
       - Un CTA (llamado a la acción) al final.
    3. Si el tema está inspirado en tendencias actuales, úsalo como punto de partida. NO copies frases, estructura exacta ni promesas virales; reescribe todo como contenido original de MEGAGYM.
    4. Máximo 1,500 caracteres en total. Sé directo y evita explicaciones largas.
    5. NO uses hashtags excesivos, máximo 3.
    6. El resultado debe ser EXCLUSIVAMENTE el copy final. NO incluyas introducciones como "¡Claro!", "Aquí tienes el post" ni explicaciones. Solo el texto que va en Instagram.
    """
    
    ultimo_error = None
    for intento in range(1, GEMINI_MAX_INTENTOS + 1):
        try:
            respuesta = modelo.generate_content(prompt)
            return limitar_caption_instagram(respuesta.text)
        except Exception as e:
            ultimo_error = e
            print(f"Error generando contenido con Gemini (intento {intento}/{GEMINI_MAX_INTENTOS}): {e}")
            if intento >= GEMINI_MAX_INTENTOS:
                break
            espera = extraer_espera_gemini(e)
            print(f"[Gemini] Esperando {espera} segundos antes de reintentar...")
            time.sleep(espera)

    print(f"[Gemini] No se pudo generar copy tras {GEMINI_MAX_INTENTOS} intentos. Ultimo error: {ultimo_error}")
    return generar_post_respaldo(tema)

def descargar_imagen_url(url):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"[Imagen] Error descargando imagen generada: {e}")
        return None

def generar_imagen_chatgpt(cliente_openai, tema):
    print(f"Generando imagen con {OPENAI_IMAGE_MODEL} para el tema: '{tema}'...")
    
    prompt_visual = f"""
    Create a highly realistic professional gym photo for MEGAGYM in Peru.
    Topic: {tema}

    Style: authentic fitness photography, real people, modern black and yellow gym atmosphere,
    energetic but natural lighting, Instagram-ready composition, no fake text, no captions,
    no logos unless they are subtle gym branding, no watermarks, no distorted hands or faces.
    """
    
    MAX_INTENTOS = 3
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            response = cliente_openai.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=prompt_visual,
                size="1024x1024",
                quality="high",
                n=1,
            )
            image = response.data[0]
            imagen_bytes = None
            if getattr(image, "b64_json", None):
                imagen_bytes = base64.b64decode(image.b64_json)
            elif getattr(image, "url", None):
                imagen_bytes = descargar_imagen_url(image.url)
                if not imagen_bytes:
                    return image.url

            if not imagen_bytes:
                print("[OpenAI] No se recibio imagen en base64 ni URL.")
                sys.exit(1)

            imagen_url = subir_imagen_a_github(imagen_bytes, f"{OPENAI_IMAGE_MODEL}-{tema}.jpg")
            if imagen_url:
                return imagen_url

            print("[OpenAI] No se pudo subir la imagen generada a GitHub.")
            sys.exit(1)
        except Exception as e:
            print(f"[Intento {intento}/{MAX_INTENTOS}] Error generando imagen con {OPENAI_IMAGE_MODEL}: {e}")
            if intento < MAX_INTENTOS:
                print(f"Esperando 10 segundos antes de reintentar...")
                time.sleep(10)
            else:
                print("Se agotaron los intentos. No se pudo generar la imagen.")
                sys.exit(1)

def seleccionar_imagen_fotorreal(modelo, tema_post, ids_usados=None):
    carpeta = "fotos_reales"
    if not os.path.exists(carpeta):
        return None

    fotos = [f for f in os.listdir(carpeta) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not fotos:
        return None

    fotos_filtradas = [
        f for f in fotos
        if not foto_ya_usada(foto_nombre=f, ids_usados=ids_usados)
    ] if ids_usados else fotos
    if not fotos_filtradas:
        print("Todas las fotos reales fueron usadas recientemente. Se usara IA.")
        return None

    random.shuffle(fotos_filtradas)
    fotos_candidatas = fotos_filtradas[:MAX_CANDIDATAS_IA]
    print(f"Analizando {len(fotos_candidatas)} fotos reales candidatas para ver si alguna coincide con el tema...")

    prompt = f"""
    Tengo las siguientes fotos en mi biblioteca: {fotos_candidatas}
    He escrito un post sobre el siguiente tema: "{tema_post}"

    ¿Cuál de estas fotos encaja mejor con el tema del post?
    REGLAS:
    1. Si el tema es de entrenamiento (fuerza, cardio, ejercicios, sudor, pesas), ELIGE la foto que más se acerque, aunque no sea exacta.
    2. Responde ÚNICAMENTE con el nombre del archivo (ejemplo: entrenamiento_mujer.png).
    3. NO incluyas introducciones ni explicaciones.
    4. Usa "NONE" solo si el tema es de nutricion, descanso o algo totalmente distinto y no tenemos fotos.
    """

    try:
        respuesta = modelo.generate_content(prompt).text.strip()
        respuesta = respuesta.replace('"', '').replace("'", "").strip()

        if respuesta.upper() == "NONE" or respuesta not in fotos_candidatas:
            print("No se encontro una foto real que coincida. Se usara IA.")
            return None

        print(f"¡Coincidencia encontrada! Usando foto real: {respuesta}")

        # Generar URL de GitHub Raw para que Make.com pueda acceder
        repo_url = "https://raw.githubusercontent.com/mysterrpj/megagym-publicador-incansable/master"
        return (f"{repo_url}/fotos_reales/{respuesta}", respuesta, respuesta, None)
    except Exception as e:
        print(f"Error en seleccion hibrida: {e}")
        return None

def descargar_foto_drive(drive_service, file_id):
    """Descarga una foto de Drive y devuelve sus bytes."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        print(f"[Drive] Imagen descargada ({len(fh.getvalue())} bytes).")
        return fh.getvalue()
    except Exception as e:
        print(f"[Drive] Error descargando imagen: {e}")
        return None

def nombre_archivo_publicacion(foto_nombre=None):
    base = os.path.splitext(os.path.basename(foto_nombre or "imagen_post"))[0]
    base = re.sub(r'[^a-zA-Z0-9_-]+', '-', base).strip('-').lower()[:60] or "imagen-post"
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    return f"posts/{timestamp}-{base}.jpg"

def subir_imagen_a_github(imagen_bytes, foto_nombre=None):
    """Sube la imagen a GitHub y devuelve la URL raw pública."""
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("[GitHub] GITHUB_TOKEN no disponible.")
        return None

    repo = os.environ.get('GITHUB_REPOSITORY', 'mysterrpj/megagym-publicador-incansable')
    filename = nombre_archivo_publicacion(foto_nombre)
    api_url = f"https://api.github.com/repos/{repo}/contents/{filename}"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }

    # Obtener SHA si el archivo ya existe (necesario para actualizarlo)
    sha = None
    try:
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            sha = r.json().get('sha')
    except Exception:
        pass

    payload = {
        'message': f'chore: subir imagen del post {filename}',
        'content': base64.b64encode(imagen_bytes).decode('utf-8')
    }
    if sha:
        payload['sha'] = sha

    try:
        r = requests.put(api_url, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            raw_url = f"https://raw.githubusercontent.com/{repo}/master/{filename}"
            print(f"[GitHub] Imagen subida: {raw_url}")
            return raw_url
        else:
            print(f"[GitHub] Error subiendo imagen: HTTP {r.status_code}")
            return None
    except Exception as e:
        print(f"[GitHub] Error subiendo imagen: {e}")
        return None

def validar_imagen_publica(image_url):
    """Verifica que Make/Meta podran descargar la imagen antes de enviarla."""
    return validar_asset_publico(image_url, "image")

def validar_asset_publico(asset_url, asset_type="image"):
    """Verifica que Make/Meta podran descargar el asset antes de enviarlo."""
    if not asset_url:
        return None

    asset_type = detectar_tipo_asset(asset_url, asset_type)
    headers = {"User-Agent": "MEGAGYM-Publisher/1.0"}
    try:
        response = requests.get(asset_url, headers=headers, stream=True, timeout=20)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").lower()
        if asset_type == "image" and "image/" not in content_type:
            print(f"[Imagen] URL descartada: Content-Type no es imagen ({content_type or 'sin tipo'}).")
            return None
        if asset_type == "video" and "video/" not in content_type:
            extension = os.path.splitext(asset_url.split("?", 1)[0].lower())[1]
            if extension not in VIDEO_EXTENSIONS or "application/octet-stream" not in content_type:
                print(f"[Video] URL descartada: Content-Type no es video ({content_type or 'sin tipo'}).")
                return None

        content_length = response.headers.get("Content-Length")
        if asset_type == "video" and content_length and int(content_length) <= 0:
            print("[Video] URL descartada: el video respondio vacio.")
            return None

        first_chunk = next(response.iter_content(chunk_size=1024), b"")
        if not first_chunk:
            print(f"[{asset_type.capitalize()}] URL descartada: el archivo respondio vacio.")
            return None

        print(f"[{asset_type.capitalize()}] URL publica validada ({content_type}).")
        return asset_url
    except Exception as e:
        print(f"[{asset_type.capitalize()}] URL descartada: no se pudo descargar antes de enviar a Make ({e}).")
        return None

def imagen_publica_o_respaldo(image_url):
    imagen_validada = validar_imagen_publica(image_url)
    if imagen_validada:
        return imagen_validada

    print("[Imagen] Usando imagen de respaldo para evitar enviar URL vacia a Make.")
    return validar_imagen_publica(DEFAULT_IMAGE_URL)

def asset_publico_o_respaldo(asset_url, asset_type="image"):
    asset_type = detectar_tipo_asset(asset_url, asset_type)
    asset_validado = validar_asset_publico(asset_url, asset_type)
    if asset_validado:
        return asset_validado

    if asset_type == "image":
        print("[Imagen] Usando imagen de respaldo para evitar enviar URL vacia a Make.")
        return validar_imagen_publica(DEFAULT_IMAGE_URL)

    print("[Video] No se enviara fallback de imagen porque la publicacion fue programada como video.")
    return None

def send_to_make(webhook_url, network, text, image_url=None, asset_url=None, asset_type="image"):
    print(f"Enviando post para {network} a Make.com...")

    if image_url and not asset_url:
        asset_url = image_url
        asset_type = "image"

    asset_type = detectar_tipo_asset(asset_url, asset_type)
    
    payload = {
        "network": network,
        "text": text,
        "asset_type": asset_type
    }
    
    if asset_url:
        payload["asset_url"] = asset_url
        if asset_type == "video":
            payload["video_url"] = asset_url
        else:
            payload["image_url"] = asset_url
    
    for intento in range(1, 4):
        try:
            response = requests.post(webhook_url, json=payload, timeout=20)
            if 200 <= response.status_code < 300:
                print(f"[Exito] Post de {network} recibido por Make.com.")
                return True

            print(f"[Error] Fallo la conexion con Make.com: HTTP {response.status_code}")
            print(response.text)
            if response.status_code < 500:
                return False
        except requests.exceptions.RequestException as e:
            print(f"[Error] Excepcion al intentar conectar con Make.com: {e}")

        if intento < 3:
            print(f"[Make] Reintentando envio de {network} en 10 segundos...")
            time.sleep(10)

    return False

def get_whatsapp_import_config():
    url = os.environ.get("WHATSAPP_IMPORT_URL")
    key = os.environ.get("WHATSAPP_IMPORT_KEY")
    user_id = os.environ.get("WHATSAPP_IMPORT_USER_ID")
    schedule_times = [
        value.strip()
        for value in os.environ.get("WHATSAPP_STATUS_TIMES", "12:00,21:00").split(",")
        if value.strip()
    ]

    if not url or not key:
        print("[WhatsApp] Importacion desactivada: faltan WHATSAPP_IMPORT_URL o WHATSAPP_IMPORT_KEY.")
        return None

    return {
        "url": url,
        "key": key,
        "user_id": user_id,
        "schedule_times": schedule_times,
    }

def build_external_post_id(post_index):
    run_id = os.environ.get("GITHUB_RUN_ID")
    if run_id:
        return f"github-run-{run_id}-post-{post_index}"

    return f"local-{datetime.now(ZoneInfo('America/Lima')).strftime('%Y%m%d-%H%M%S')}-post-{post_index}"

def schedule_time_for_whatsapp(config, post_index, source_date=None, source_time=None):
    lima_now = datetime.now(ZoneInfo("America/Lima"))
    base_date = lima_now.date()
    if source_date:
        try:
            base_date = date.fromisoformat(str(source_date))
        except ValueError:
            print(f"[WhatsApp] Fecha de origen invalida '{source_date}'. Se usara la fecha actual.")

    schedule_times = config.get("schedule_times") or ["12:00", "21:00"]
    candidates = []

    for slot in schedule_times:
        try:
            hour_text, minute_text = slot.split(":", 1)
            candidates.append(
                datetime.combine(base_date, datetime.min.time(), tzinfo=ZoneInfo("America/Lima")).replace(
                    hour=int(hour_text),
                    minute=int(minute_text),
                    second=0,
                    microsecond=0,
                )
            )
        except ValueError:
            print(f"[WhatsApp] Horario invalido '{slot}'. Se omitira.")

    if not candidates:
        candidates.append(lima_now.replace(hour=12, minute=0, second=0, microsecond=0))
        candidates.append(lima_now.replace(hour=21, minute=0, second=0, microsecond=0))

    candidates = sorted(candidates)

    if source_time:
        try:
            source_hour = int(str(source_time).split(":", 1)[0])
            slot_index = 0 if source_hour < 12 else min(1, len(candidates) - 1)
            return candidates[slot_index]
        except (ValueError, TypeError):
            print(f"[WhatsApp] Hora de origen invalida '{source_time}'. Se usara el proximo horario disponible.")

    if 1 <= post_index <= len(candidates):
        selected = candidates[post_index - 1]
        if selected <= lima_now:
            selected = selected + timedelta(days=1)
        return selected

    future_candidates = sorted(candidate for candidate in candidates if candidate > lima_now)
    if future_candidates:
        return future_candidates[0]

    return min(candidates) + timedelta(days=1)

def send_to_whatsapp_import(config, post_index, text, image_url=None, asset_url=None, asset_type="image", source_date=None, source_time=None):
    if not config:
        return

    if image_url and not asset_url:
        asset_url = image_url
        asset_type = "image"

    asset_type = detectar_tipo_asset(asset_url, asset_type) if asset_url else None
    schedule_time = schedule_time_for_whatsapp(config, post_index, source_date=source_date, source_time=source_time)
    payload = {
        "source": "megagym-auto-redes",
        "externalPostId": build_external_post_id(post_index),
        "message": text,
        "assetUrl": asset_url,
        "assetType": asset_type,
        "scheduleTime": schedule_time.isoformat(),
    }

    if config.get("user_id"):
        payload["userId"] = config["user_id"]

    headers = {
        "Content-Type": "application/json",
        "x-import-key": config["key"],
    }

    try:
        print(f"[WhatsApp] Enviando post al importador de estados para {schedule_time.strftime('%Y-%m-%d %H:%M')}...")
        response = requests.post(config["url"], json=payload, headers=headers, timeout=15)
        data = response.json() if response.text else {}
        if response.status_code == 200 and data.get("ok"):
            estado = "ya existia" if data.get("duplicate") else "programado"
            print(f"[WhatsApp] Estado {estado}. taskId={data.get('taskId')}")
        else:
            print(f"[WhatsApp] Error importando estado: HTTP {response.status_code}")
            print(response.text)
    except requests.exceptions.RequestException as e:
        print(f"[WhatsApp] Excepcion conectando con el importador: {e}")
    except ValueError:
        print(f"[WhatsApp] Respuesta no JSON del importador: HTTP {response.status_code}")
        print(response.text)

def main():
    # Fix para imprimir emojis en consola de Windows
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
        
    print("Iniciando Publicador de MEGAGYM (via Make.com + IA)...")
    
    # 1. Setup IA
    modelo_gemini = setup_gemini()
    cliente_openai = setup_openai()
    memoria_marca = get_memory_context()
    webhook_url = get_webhook_url()
    whatsapp_import_config = get_whatsapp_import_config()
    drive_service, drive_folder_id = setup_drive()

    # Cargar historial de fotos usadas
    historial, ids_usados = cargar_historial()

    # 2. Elegir Temas del Día (2 publicaciones, fechas especiales + categorías)
    publicacion_programada = cargar_publicacion_programada()
    if publicacion_programada and publicacion_programada.get("skip"):
        print("[Calendario] Ejecucion omitida para evitar una publicacion no planificada.")
        return

    if publicacion_programada:
        publicaciones_del_dia = [publicacion_programada]
    else:
        publicaciones_del_dia = [
            {
                "tema": tema,
                "copy": "",
                "asset_archivo": "",
                "asset_type": "image",
                "asset_url": None,
                "imagen_archivo": "",
                "imagen_url": None,
            }
            for tema in seleccionar_temas_del_dia()
        ]
    print(f"\n[INFO] Publicaciones a procesar: {[p['tema'] for p in publicaciones_del_dia]}")

    for i, publicacion in enumerate(publicaciones_del_dia, 1):
        tema_dia = publicacion["tema"]
        print(f"\n{'='*50}")
        print(f"[PUBLICACION {i} de {len(publicaciones_del_dia)}] Tema: {tema_dia}")
        print(f"{'='*50}")

        ig_text = publicacion.get("copy") or generar_post_con_ia(modelo_gemini, memoria_marca, tema=tema_dia)

        print("\n---------------- POST GENERADO ---------------")
        print(ig_text)
        print("----------------------------------------------\n")

        # 3. Seleccionar asset (video programado o imagen con fallback actual)
        imagen_resultado = None
        asset_type = publicacion.get("asset_type") or detectar_tipo_asset(publicacion.get("asset_archivo") or publicacion.get("imagen_archivo"))
        asset_principal = publicacion.get("asset_url") or publicacion.get("imagen_url")
        imagen_principal = asset_principal if asset_type == "image" else None
        if asset_principal:
            print(f"[Calendario] Usando {asset_type} planificado: {publicacion.get('asset_archivo') or publicacion.get('imagen_archivo')}")

        if asset_type == "image" and not imagen_principal and drive_service:
            imagen_resultado = seleccionar_foto_drive(modelo_gemini, tema_dia, drive_service, drive_folder_id, ids_usados)

        if asset_type == "image" and not imagen_principal and not imagen_resultado:
            imagen_resultado = seleccionar_imagen_fotorreal(modelo_gemini, tema_dia, ids_usados)

        if imagen_resultado:
            imagen_url_original, foto_id, foto_nombre = imagen_resultado[:3]
            foto_descripcion = imagen_resultado[3] if len(imagen_resultado) > 3 else None
            historial = guardar_historial(historial, foto_id, foto_nombre, foto_descripcion)
            ids_usados.add(foto_id)  # Evitar repetir en la misma ejecución (2 posts/día)
            ids_usados.add(foto_nombre)
            foto_clave = clave_archivo(foto_nombre)
            if foto_clave:
                ids_usados.add(foto_clave)
            foto_firma = firma_visual(foto_descripcion, foto_nombre)
            if foto_firma:
                ids_usados.add(foto_firma)

            # Si la imagen viene de Drive, descargarla y subirla a GitHub
            # (Instagram no acepta URLs de Drive directamente)
            if 'lh3.googleusercontent.com' in imagen_url_original:
                print("[Drive→GitHub] Descargando imagen de Drive para publicar via GitHub...")
                bytes_imagen = descargar_foto_drive(drive_service, foto_id)
                if bytes_imagen:
                    imagen_principal = subir_imagen_a_github(bytes_imagen, foto_nombre)
                    if imagen_principal:
                        print("[CDN] Esperando 20 segundos para propagación de GitHub CDN...")
                        time.sleep(20)
                    else:
                        print("[Fallback] GitHub falló. Se omitirá la imagen generada por IA.")
                        imagen_principal = None
                else:
                    print("[Fallback] Descarga de Drive falló. Se omitirá la imagen generada por IA.")
                    imagen_principal = None
            else:
                imagen_principal = imagen_url_original
            asset_principal = imagen_principal
        elif asset_type == "image" and not imagen_principal:
            if PERMITIR_IMAGENES_IA:
                imagen_principal = generar_imagen_chatgpt(cliente_openai, tema_dia)
                asset_principal = imagen_principal
            else:
                print("[Imagen] No se encontró imagen adecuada y la generación con IA está desactivada.")
                imagen_principal = None
                asset_principal = None

        asset_programado_url = publicacion.get("asset_url") or publicacion.get("imagen_url")
        asset_principal = asset_publico_o_respaldo(asset_principal, asset_type)
        if not asset_principal:
            print(f"[{asset_type.capitalize()}] Publicacion omitida porque no hay asset valido para enviar.")
            continue

        if asset_programado_url and asset_principal == asset_programado_url:
            historial = guardar_historial(
                historial,
                f"calendario:{publicacion.get('asset_archivo') or publicacion.get('imagen_archivo')}",
                publicacion.get("asset_archivo") or publicacion.get("imagen_archivo"),
                tema_dia,
            )
        print(f"URL de {asset_type} final a publicar: {asset_principal}")

        print(f"\n--- Enviando Post {i} a Facebook ---")
        send_to_make(webhook_url, "facebook", ig_text, asset_url=asset_principal, asset_type=asset_type)

        print("\n[Esperando 3 segundos para que Make procese el post...]")
        time.sleep(3)

        print(f"\n--- Enviando Post {i} a Instagram ---")
        send_to_make(webhook_url, "instagram", ig_text, asset_url=asset_principal, asset_type=asset_type)

        print(f"\n--- Enviando Post {i} a WhatsApp ---")
        send_to_whatsapp_import(
            whatsapp_import_config,
            i,
            ig_text,
            asset_url=asset_principal,
            asset_type=asset_type,
            source_date=publicacion.get("fecha"),
            source_time=publicacion.get("hora"),
        )

        if i < len(publicaciones_del_dia):
            print("\n[Esperando 10 segundos antes de la siguiente publicación...]")
            time.sleep(10)

if __name__ == '__main__':
    main()
