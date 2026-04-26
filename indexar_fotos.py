import os
import sys
import json
import io
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import PIL.Image


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
        print("Error: Credenciales de Google Drive no encontradas.")
        sys.exit(1)

    creds_data = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_data,
        scopes=['https://www.googleapis.com/auth/drive.readonly']
    )
    service = build('drive', 'v3', credentials=credentials)
    return service, folder_id


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
        print("Error: No se encontró la API Key de Gemini.")
        sys.exit(1)
    genai.configure(api_key=api_key)
    return genai.GenerativeModel('gemini-2.5-flash')


def cargar_indice():
    try:
        with open('indice_fotos.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {item['id']: item for item in data}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def guardar_indice(indice):
    with open('indice_fotos.json', 'w', encoding='utf-8') as f:
        json.dump(list(indice.values()), f, ensure_ascii=False, indent=2)


def listar_fotos_drive(drive_service, folder_id):
    fotos = []
    page_token = None
    while True:
        results = drive_service.files().list(
            q=f"'{folder_id}' in parents and mimeType contains 'image/' and trashed=false",
            fields="nextPageToken, files(id, name)",
            pageSize=1000,
            pageToken=page_token
        ).execute()
        fotos.extend(results.get('files', []))
        page_token = results.get('nextPageToken')
        if not page_token:
            return fotos


def describir_imagen(modelo, drive_service, file_id, nombre):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buffer.seek(0)
        imagen = PIL.Image.open(buffer)

        respuesta = modelo.generate_content([
            "Describe esta imagen de gimnasio en UNA sola oración corta en español. "
            "Menciona: qué hay en la imagen (persona, ejercicio, equipo, flyer, logo), "
            "si es foto real o diseño gráfico, y el contexto general. "
            "Solo la descripción, sin introducciones.",
            imagen
        ])
        return respuesta.text.strip()
    except Exception as e:
        print(f"  Error describiendo {nombre}: {e}")
        return None


def main():
    print("Iniciando indexación de fotos de Google Drive...")

    drive_service, folder_id = setup_drive()
    modelo = setup_gemini()

    # Cargar índice existente
    indice = cargar_indice()
    print(f"Índice existente: {len(indice)} fotos")

    # Obtener lista completa de fotos de Drive
    fotos_drive = listar_fotos_drive(drive_service, folder_id)
    print(f"Fotos en Drive: {len(fotos_drive)}")

    # Detectar fotos nuevas (no están en el índice)
    fotos_nuevas = [f for f in fotos_drive if f['id'] not in indice]

    # Detectar fotos eliminadas (están en el índice pero ya no en Drive)
    ids_drive = {f['id'] for f in fotos_drive}
    eliminadas = [id for id in list(indice.keys()) if id not in ids_drive]

    for id_eliminado in eliminadas:
        nombre = indice[id_eliminado]['nombre']
        del indice[id_eliminado]
        print(f"Eliminada del índice: {nombre}")

    print(f"Fotos nuevas a indexar: {len(fotos_nuevas)}")

    if not fotos_nuevas and not eliminadas:
        print("El índice ya está actualizado. No hay cambios.")
        return

    # Indexar fotos nuevas
    for i, foto in enumerate(fotos_nuevas, 1):
        print(f"[{i}/{len(fotos_nuevas)}] Analizando: {foto['name']}...")
        descripcion = describir_imagen(modelo, drive_service, foto['id'], foto['name'])
        if descripcion:
            indice[foto['id']] = {
                'id': foto['id'],
                'nombre': foto['name'],
                'descripcion': descripcion
            }
            print(f"  -> {descripcion}")

    guardar_indice(indice)
    print(f"\nÍndice actualizado: {len(indice)} fotos en total.")
    print("Archivo indice_fotos.json guardado.")


if __name__ == '__main__':
    main()
