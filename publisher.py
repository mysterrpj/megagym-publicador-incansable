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
from datetime import date, datetime, timedelta
import google.generativeai as genai
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ─── HISTORIAL DE FOTOS ─────────────────────────────────────────────────────
DIAS_HISTORIAL = 30  # No repetir fotos usadas en los últimos N días
MAX_INSTAGRAM_CAPTION_CHARS = 1800
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "chatgpt-image-latest")
PERMITIR_IMAGENES_IA = os.environ.get("PERMITIR_IMAGENES_IA", "false").lower() == "true"
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
    return bool(
        (foto_id and foto_id in ids_usados)
        or (foto_nombre and foto_nombre in ids_usados)
        or (foto_firma and foto_firma in ids_usados)
    )

def cargar_historial():
    """Carga el historial de fotos usadas. Devuelve (lista_completa, set_de_ids_recientes)."""
    try:
        with open('historial_fotos.json', 'r', encoding='utf-8') as f:
            historial = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        historial = []

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
            if h['nombre'] in firmas_indice:
                ids_usados.add(firmas_indice[h['nombre']])
        if h.get('firma'):
            ids_usados.add(h['firma'])
    print(f"[Historial] {len(ids_usados)} fotos usadas en los últimos {DIAS_HISTORIAL} días.")
    return historial, ids_usados

def guardar_historial(historial, foto_id, foto_nombre, descripcion=None):
    """Agrega una foto al historial y guarda el archivo. Devuelve la lista actualizada."""
    entrada = {"id": foto_id, "nombre": foto_nombre, "fecha": date.today().isoformat()}
    firma = firma_visual(descripcion, foto_nombre)
    if firma:
        entrada["firma"] = firma
    historial.append(entrada)
    # Limpiar entradas más antiguas que 60 días para no crecer infinitamente
    limite = date.today() - timedelta(days=60)
    historial = [h for h in historial if date.fromisoformat(h['fecha']) >= limite]
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

    descripciones = [
        (
            f"{item['nombre']} | sugerido: {item.get('nombre_sugerido', 'sin-nombre')} "
            f"| categoria: {item.get('categoria_visual', 'otro')} "
            f"| tipo: {item.get('tipo_visual', 'otro')} "
            f"| descripcion: {item.get('descripcion', '')}"
        )
        for item in indice_filtrado
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

        foto = next((item for item in indice_filtrado if item['nombre'] == respuesta), None)
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

    print(f"Analizando {len(fotos_filtradas)} fotos en Drive por nombre...")
    nombres = [f['name'] for f in fotos_filtradas]

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

        foto = next((f for f in fotos_filtradas if f['name'] == respuesta), None)
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
    
    try:
        respuesta = modelo.generate_content(prompt)
        return limitar_caption_instagram(respuesta.text)
    except Exception as e:
        print(f"Error generando contenido con Gemini: {e}")
        sys.exit(1)

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

    print(f"Analizando {len(fotos_filtradas)} fotos reales para ver si alguna coincide con el tema...")

    prompt = f"""
    Tengo las siguientes fotos en mi biblioteca: {fotos_filtradas}
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

        if respuesta.upper() == "NONE" or respuesta not in fotos_filtradas:
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

def send_to_make(webhook_url, network, text, image_url=None):
    print(f"Enviando post para {network} a Make.com...")
    
    payload = {
        "network": network,
        "text": text
    }
    
    if image_url:
        payload["image_url"] = image_url
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[Exito] Post de {network} recibido por Make.com.")
        else:
            print(f"[Error] Fallo la conexion con Make.com: HTTP {response.status_code}")
            print(response.text)
    except requests.exceptions.RequestException as e:
        print(f"[Error] Excepcion al intentar conectar con Make.com: {e}")

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
    drive_service, drive_folder_id = setup_drive()

    # Cargar historial de fotos usadas
    historial, ids_usados = cargar_historial()

    # 2. Elegir Temas del Día (2 publicaciones, fechas especiales + categorías)
    temas_del_dia = seleccionar_temas_del_dia()
    print(f"\n[INFO] Temas del día: {temas_del_dia}")

    for i, tema_dia in enumerate(temas_del_dia, 1):
        print(f"\n{'='*50}")
        print(f"[PUBLICACIÓN {i} de {len(temas_del_dia)}] Tema: {tema_dia}")
        print(f"{'='*50}")

        ig_text = generar_post_con_ia(modelo_gemini, memoria_marca, tema=tema_dia)

        print("\n---------------- POST GENERADO ---------------")
        print(ig_text)
        print("----------------------------------------------\n")

        # 3. Seleccionar Imagen (Prioridad: Drive > fotos_reales; IA desactivada por defecto)
        imagen_resultado = None

        if drive_service:
            imagen_resultado = seleccionar_foto_drive(modelo_gemini, tema_dia, drive_service, drive_folder_id, ids_usados)

        if not imagen_resultado:
            imagen_resultado = seleccionar_imagen_fotorreal(modelo_gemini, tema_dia, ids_usados)

        if imagen_resultado:
            imagen_url_original, foto_id, foto_nombre = imagen_resultado[:3]
            foto_descripcion = imagen_resultado[3] if len(imagen_resultado) > 3 else None
            historial = guardar_historial(historial, foto_id, foto_nombre, foto_descripcion)
            ids_usados.add(foto_id)  # Evitar repetir en la misma ejecución (2 posts/día)
            ids_usados.add(foto_nombre)
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
        else:
            if PERMITIR_IMAGENES_IA:
                imagen_principal = generar_imagen_chatgpt(cliente_openai, tema_dia)
            else:
                print("[Imagen] No se encontró imagen adecuada y la generación con IA está desactivada.")
                imagen_principal = None

        print(f"URL de imagen final a publicar: {imagen_principal}")

        print(f"\n--- Enviando Post {i} a Facebook ---")
        send_to_make(webhook_url, "facebook", ig_text, image_url=imagen_principal)

        print("\n[Esperando 3 segundos para que Make procese el post...]")
        time.sleep(3)

        print(f"\n--- Enviando Post {i} a Instagram ---")
        send_to_make(webhook_url, "instagram", ig_text, image_url=imagen_principal)

        if i < len(temas_del_dia):
            print("\n[Esperando 10 segundos antes de la siguiente publicación...]")
            time.sleep(10)

if __name__ == '__main__':
    main()
