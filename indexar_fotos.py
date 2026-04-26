import os
import sys
import json
import io
import re
import unicodedata
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


def slugify(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:70] or "foto-gimnasio"


def normalizar_categoria(categoria):
    permitidas = {
        "entrenamiento", "fuerza", "cardio", "nutricion", "recuperacion",
        "promocion", "transformacion", "selfie", "ambiente", "staff", "logo", "otro"
    }
    categoria = slugify(categoria).replace("-", "_")
    return categoria if categoria in permitidas else "otro"


def parsear_metadata(texto, nombre_original):
    try:
        data = json.loads(texto)
    except json.JSONDecodeError:
        return {
            "descripcion": texto.strip(),
            "nombre_sugerido": slugify(nombre_original),
            "categoria_visual": "otro",
            "tipo_visual": "otro"
        }

    tipo_visual = slugify(data.get("tipo_visual", "otro")).replace("-", "_")
    if tipo_visual not in {"foto_real", "flyer", "logo", "otro"}:
        tipo_visual = "otro"

    return {
        "descripcion": str(data.get("descripcion", "")).strip(),
        "nombre_sugerido": slugify(data.get("nombre_sugerido") or nombre_original),
        "categoria_visual": normalizar_categoria(data.get("categoria_visual", "otro")),
        "tipo_visual": tipo_visual
    }


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


def analizar_imagen(modelo, drive_service, file_id, nombre):
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
            """
            Analiza esta imagen de gimnasio y responde SOLO con JSON valido, sin markdown.
            Campos:
            - descripcion: una sola oracion corta en espanol. Menciona persona, ejercicio, equipo, flyer/logo si aplica y contexto.
            - nombre_sugerido: slug corto en minusculas, sin extension, 3 a 7 palabras separadas por guiones.
            - categoria_visual: una de entrenamiento, fuerza, cardio, nutricion, recuperacion, promocion, transformacion, selfie, ambiente, staff, logo, otro.
            - tipo_visual: una de foto_real, flyer, logo, otro.
            """,
            imagen
        ])
        return parsear_metadata(respuesta.text.strip(), nombre)
    except Exception as e:
        print(f"  Error analizando {nombre}: {e}")
        return None


def completar_metadata_existente(modelo, drive_service, indice):
    pendientes = [
        item for item in indice.values()
        if not item.get('nombre_sugerido') or not item.get('categoria_visual') or not item.get('tipo_visual')
    ]
    if not pendientes:
        return False

    print(f"Fotos existentes con metadata incompleta: {len(pendientes)}")
    for i, item in enumerate(pendientes, 1):
        print(f"[metadata {i}/{len(pendientes)}] Analizando: {item['nombre']}...")
        metadata = analizar_imagen(modelo, drive_service, item['id'], item['nombre'])
        if not metadata:
            continue
        item.update(metadata)
        print(f"  -> {metadata['nombre_sugerido']} ({metadata['categoria_visual']}, {metadata['tipo_visual']})")
    return True


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

    metadata_actualizada = completar_metadata_existente(modelo, drive_service, indice)

    if not fotos_nuevas and not eliminadas and not metadata_actualizada:
        print("El índice ya está actualizado. No hay cambios.")
        return

    # Indexar fotos nuevas
    for i, foto in enumerate(fotos_nuevas, 1):
        print(f"[{i}/{len(fotos_nuevas)}] Analizando: {foto['name']}...")
        metadata = analizar_imagen(modelo, drive_service, foto['id'], foto['name'])
        if metadata:
            indice[foto['id']] = {
                'id': foto['id'],
                'nombre': foto['name'],
                **metadata
            }
            print(f"  -> {metadata['nombre_sugerido']} ({metadata['categoria_visual']}, {metadata['tipo_visual']})")

    guardar_indice(indice)
    print(f"\nÍndice actualizado: {len(indice)} fotos en total.")
    print("Archivo indice_fotos.json guardado.")


if __name__ == '__main__':
    main()
