import os
import requests
import sys
import time
import json
import random
from datetime import date, timedelta
import google.generativeai as genai
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build

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

def seleccionar_foto_drive(modelo, tema_post, drive_service, folder_id):
    # Intentar usar el índice inteligente si existe
    try:
        with open('indice_fotos.json', 'r', encoding='utf-8') as f:
            indice = json.load(f)
        if indice:
            print(f"Usando índice inteligente ({len(indice)} fotos indexadas)...")
            return _seleccionar_por_indice(modelo, tema_post, indice)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Fallback: selección por nombres de archivo
    print("Índice no encontrado. Usando selección por nombres...")
    return _seleccionar_por_nombres(modelo, tema_post, drive_service, folder_id)


def _seleccionar_por_indice(modelo, tema_post, indice):
    descripciones = [f"{item['nombre']}: {item['descripcion']}" for item in indice]

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

        foto = next((item for item in indice if item['nombre'] == respuesta), None)
        if not foto or respuesta.upper() == "NONE":
            print("No se encontró coincidencia en el índice. Se usará fallback.")
            return None

        print(f"Foto seleccionada del índice: {respuesta}")
        return f"https://lh3.googleusercontent.com/d/{foto['id']}"
    except Exception as e:
        print(f"Error seleccionando foto del índice: {e}")
        return None


def _seleccionar_por_nombres(modelo, tema_post, drive_service, folder_id):
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

    print(f"Analizando {len(fotos)} fotos en Drive por nombre...")
    nombres = [f['name'] for f in fotos]

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

        foto = next((f for f in fotos if f['name'] == respuesta), None)
        if not foto or respuesta.upper() == "NONE":
            print("No coincidio ninguna foto de Drive. Se usara fallback.")
            return None

        file_id = foto['id']
        print(f"Foto seleccionada de Drive: {respuesta} (id: {file_id})")
        return f"https://lh3.googleusercontent.com/d/{file_id}"
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
    3. NO uses hashtags excesivos, máximo 3.
    4. El resultado debe ser EXCLUSIVAMENTE el copy final. NO incluyas introducciones como "¡Claro!", "Aquí tienes el post" ni explicaciones. Solo el texto que va en Instagram.
    """
    
    try:
        respuesta = modelo.generate_content(prompt)
        return respuesta.text.strip()
    except Exception as e:
        print(f"Error generando contenido con Gemini: {e}")
        sys.exit(1)

def generar_imagen_dalle(cliente_openai, tema):
    print(f"Generando imagen con DALL-E para el tema: '{tema}'...")
    
    # Preparamos un prompt especifico en ingles para DALL-E para los mejores resultados
    prompt_visual = f"A highly realistic, gritty, and raw photography representing this fitness topic: '{tema}'. The image should be professional gym photography, dark and moody lighting, real people, no text whatsoever, no overlays."
    
    MAX_INTENTOS = 3
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            response = cliente_openai.images.generate(
                model="dall-e-3",
                prompt=prompt_visual,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            return response.data[0].url
        except Exception as e:
            print(f"[Intento {intento}/{MAX_INTENTOS}] Error generando imagen con DALL-E: {e}")
            if intento < MAX_INTENTOS:
                print(f"Esperando 10 segundos antes de reintentar...")
                time.sleep(10)
            else:
                print("Se agotaron los intentos. No se pudo generar la imagen.")
                sys.exit(1)

def seleccionar_imagen_fotorreal(modelo, tema_post):
    carpeta = "fotos_reales"
    if not os.path.exists(carpeta):
        return None
        
    fotos = [f for f in os.listdir(carpeta) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not fotos:
        return None
        
    print(f"Analizando {len(fotos)} fotos reales para ver si alguna coincide con el tema...")
    
    prompt = f"""
    Tengo las siguientes fotos en mi biblioteca: {fotos}
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
        # Limpiar posibles comillas o espacios extras
        respuesta = respuesta.replace('"', '').replace("'", "").strip()
        
        if respuesta.upper() == "NONE" or respuesta not in fotos:
            print("No se encontro una foto real que coincida. Se usara IA.")
            return None
            
        print(f"¡Coincidencia encontrada! Usando foto real: {respuesta}")
        
        # Generar URL de GitHub Raw para que Make.com pueda acceder
        repo_url = "https://raw.githubusercontent.com/mysterrpj/megagym-publicador-incansable/master"
        return f"{repo_url}/fotos_reales/{respuesta}"
    except Exception as e:
        print(f"Error en seleccion hibrida: {e}")
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

        # 3. Seleccionar Imagen (Prioridad: Drive > fotos_reales > DALL-E)
        imagen_principal = None

        if drive_service:
            imagen_principal = seleccionar_foto_drive(modelo_gemini, tema_dia, drive_service, drive_folder_id)

        if not imagen_principal:
            imagen_principal = seleccionar_imagen_fotorreal(modelo_gemini, tema_dia)

        if not imagen_principal:
            imagen_principal = generar_imagen_dalle(cliente_openai, tema_dia)

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
