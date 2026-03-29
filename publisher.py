import os
import requests
import sys
import time
import json
import random
import google.generativeai as genai
import openai
from google.oauth2 import service_account
from googleapiclient.discovery import build

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

    print(f"Analizando {len(fotos)} fotos en Drive...")
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
        # URL directa compatible con Instagram (requiere carpeta publica)
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
    
    # 2. Elegir Tema Aleatorio
    lista_temas = [
        "Por que el entrenamiento de fuerza es mejor que el cardio para perder grasa",
        "La importancia de dormir al menos 7-8 horas para ganar musculo",
        "Mito y verdad sobre los batidos de proteina post-entrenamiento",
        "Como mantener la disciplina cuando la motivacion desaparece",
        "Por que no deberias cambiar de rutina cada dos semanas",
        "Los beneficios de hacer sentadillas y peso muerto (ejercicios compuestos)",
        "El impacto del estres diario en tus resultados del gimnasio",
        "Como prepararse mentalmente antes de un levantamiento pesado",
        "Por que no necesitas comer 6 veces al dia para ver resultados",
        "El mayor error de los principiantes en el gym y como evitarlo"
    ]
    
    tema_dia = random.choice(lista_temas)
    print(f"\n[INFO] Tema del dia seleccionado al azar: {tema_dia}")
    
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

    print("\n--- Accion 1: Enviando Post a Facebook ---")
    send_to_make(webhook_url, "facebook", ig_text, image_url=imagen_principal)

    print("\n[Esperando 3 segundos para que Make procese el primer post...]")
    time.sleep(3)

    print("\n--- Accion 2: Enviando Post a Instagram ---")
    send_to_make(webhook_url, "instagram", ig_text, image_url=imagen_principal)

if __name__ == '__main__':
    main()
