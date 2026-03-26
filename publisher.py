import os
import requests
import sys
import time
import json
import random
import google.generativeai as genai
import openai
MAKE_WEBHOOK_URL = "https://hook.us2.make.com/dqk1g8iiakkqngfn3mjhnq79lt468fhi"

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
    4. El resultado debe ser solo el copy listo para copiar y pegar.
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
        print(f"Error generando imagen con DALL-E: {e}")
        sys.exit(1)

def send_to_make(network, text, image_url=None):
    print(f"Enviando post para {network} a Make.com...")
    
    payload = {
        "network": network,
        "text": text
    }
    
    if image_url:
        payload["image_url"] = image_url
    
    try:
        response = requests.post(MAKE_WEBHOOK_URL, json=payload, timeout=10)
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
    
    # 3. Generar Imagen con DALL-E
    imagen_principal = generar_imagen_dalle(cliente_openai, tema_dia)
    print(f"URL de imagen generada: {imagen_principal}")

    print("\n--- Accion 1: Enviando Post a Facebook ---")
    send_to_make("facebook", ig_text, image_url=imagen_principal)
    
    print("\n[Esperando 3 segundos para que Make procese el primer post...]")
    time.sleep(3)
    
    print("\n--- Accion 2: Enviando Post a Instagram ---")
    send_to_make("instagram", ig_text, image_url=imagen_principal)

if __name__ == '__main__':
    main()
