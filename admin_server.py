import csv
import json
import mimetypes
import os
import re
import shutil
import tempfile
import ast
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


HOST = "127.0.0.1"
PORT = 8787
ROOT_DIR = Path(__file__).resolve().parent
ADMIN_DIR = ROOT_DIR / "admin"
CSV_PATH = ROOT_DIR / "calendario_publicaciones.csv"
BACKUP_PATH = ROOT_DIR / "calendario_publicaciones.csv.bak"
POSTS_DIR = ROOT_DIR / "posts_programados"

CSV_COLUMNS = ["fecha", "hora", "estado", "tema", "imagen_archivo", "copy"]
ALLOWED_STATES = {"pendiente", "lista", "programada", "ready", "publicada"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def clean_filename(filename):
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    name = name.strip("._")
    if not name:
        raise ValueError("Nombre de archivo invalido.")
    return name


def safe_asset_path(filename):
    name = clean_filename(filename)
    path = (POSTS_DIR / name).resolve()
    if POSTS_DIR.resolve() not in path.parents and path != POSTS_DIR.resolve():
        raise ValueError("Ruta de archivo invalida.")
    return path


def asset_type(filename):
    suffix = Path(filename or "").suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return "none"


def slot_filename(fecha, hora, suffix):
    fecha = (fecha or "").strip()
    hora = (hora or "").strip()
    suffix = (suffix or "").lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extension no permitida: {suffix or '(sin extension)'}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        raise ValueError("La fila necesita una fecha valida para renombrar el archivo.")
    if not re.fullmatch(r"\d{2}:\d{2}", hora):
        raise ValueError("La fila necesita una hora valida para renombrar el archivo.")
    return f"{fecha}_{hora.replace(':', '')}{suffix}"


def load_topics_from_publisher():
    publisher_path = ROOT_DIR / "publisher.py"
    if not publisher_path.exists():
        return []
    try:
        tree = ast.parse(publisher_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "TEMAS_POR_CATEGORIA" for target in node.targets):
            continue
        try:
            topics_by_category = ast.literal_eval(node.value)
        except Exception:
            return []
        topics = []
        for values in topics_by_category.values():
            for topic in values:
                if isinstance(topic, str) and topic.strip():
                    topics.append(topic.strip())
        return topics
    return []


def row_asset_info(filename):
    filename = (filename or "").strip()
    if not filename:
        return {"exists": False, "type": "none", "url": ""}
    if filename.startswith(("http://", "https://")):
        return {"exists": True, "type": asset_type(filename), "url": filename}
    try:
        path = safe_asset_path(filename)
    except ValueError:
        return {"exists": False, "type": asset_type(filename), "url": ""}
    exists = path.exists() and path.is_file()
    return {
        "exists": exists,
        "type": asset_type(filename),
        "url": f"/assets/{filename}" if exists else "",
    }


def read_posts():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            normalized = {column: (row.get(column) or "") for column in CSV_COLUMNS}
            rows.append(normalized)
        return rows


def validate_rows(rows):
    if not isinstance(rows, list):
        raise ValueError("El payload debe incluir una lista de filas.")

    clean_rows = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"La fila {index} no es valida.")
        clean = {column: str(row.get(column) or "").strip() for column in CSV_COLUMNS}
        state = clean["estado"].lower()
        if state not in ALLOWED_STATES:
            raise ValueError(f"Estado invalido en fila {index}: {clean['estado']}")
        if clean["imagen_archivo"] and not clean["imagen_archivo"].startswith(("http://", "https://")):
            suffix = Path(clean["imagen_archivo"]).suffix.lower()
            if suffix and suffix not in ALLOWED_EXTENSIONS:
                raise ValueError(f"Extension no permitida en fila {index}: {suffix}")
            clean["imagen_archivo"] = clean_filename(clean["imagen_archivo"])
        clean_rows.append(clean)
    return clean_rows


def write_posts(rows):
    POSTS_DIR.mkdir(exist_ok=True)
    if CSV_PATH.exists():
        shutil.copy2(CSV_PATH, BACKUP_PATH)

    fd, temp_name = tempfile.mkstemp(prefix="calendario_", suffix=".csv", dir=str(ROOT_DIR))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temp_path, CSV_PATH)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def parse_multipart_upload(handler):
    content_type = handler.headers.get("Content-Type", "")
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("Solicitud multipart invalida.")
    boundary = match.group("boundary").strip().strip('"').encode("utf-8")
    length = int(handler.headers.get("Content-Length", "0") or "0")
    body = handler.rfile.read(length)
    delimiter = b"--" + boundary

    fields = {}
    upload = None
    for part in body.split(delimiter):
        part = part.strip()
        if not part or part == b"--":
            continue
        if part.endswith(b"--"):
            part = part[:-2].strip()
        header_bytes, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = header_bytes.decode("utf-8", errors="replace")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'name="([^"]*)"', disposition)
        field_name = name_match.group(1) if name_match else ""
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if content.endswith(b"\r\n"):
            content = content[:-2]
        if not filename_match:
            if field_name:
                fields[field_name] = content.decode("utf-8", errors="replace")
            continue
        filename = filename_match.group(1)
        upload = (filename, content)
    if not upload:
        raise ValueError("No se recibio ningun archivo.")
    return upload[0], upload[1], fields


def save_upload(filename, content, target_name=None):
    POSTS_DIR.mkdir(exist_ok=True)
    filename = clean_filename(filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extension no permitida: {suffix or '(sin extension)'}")

    if target_name:
        candidate = clean_filename(target_name)
        candidate_suffix = Path(candidate).suffix.lower()
        if candidate_suffix not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Extension no permitida: {candidate_suffix or '(sin extension)'}")
        path = safe_asset_path(candidate)
        path.write_bytes(content)
        return candidate

    base = Path(filename).stem
    candidate = filename
    counter = 1
    while safe_asset_path(candidate).exists():
        candidate = f"{base}_{counter}{suffix}"
        counter += 1

    path = safe_asset_path(candidate)
    path.write_bytes(content)
    return candidate


class AdminHandler(SimpleHTTPRequestHandler):
    server_version = "MegagymAdmin/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/posts":
            rows = read_posts()
            payload = {
                "columns": CSV_COLUMNS,
                "states": sorted(ALLOWED_STATES),
                "rows": [
                    {**row, "_asset": row_asset_info(row.get("imagen_archivo", ""))}
                    for row in rows
                ],
            }
            json_response(self, 200, payload)
            return
        if path == "/api/topics":
            json_response(self, 200, {"topics": load_topics_from_publisher()})
            return
        if path.startswith("/assets/"):
            self.serve_asset(path.removeprefix("/assets/"))
            return
        if path in {"/", "/admin", "/admin/"}:
            self.serve_file(ADMIN_DIR / "index.html")
            return
        if path.startswith("/admin/"):
            self.serve_file(ADMIN_DIR / unquote(path.removeprefix("/admin/")))
            return
        self.send_error(404, "No encontrado")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/posts":
            try:
                data = read_json_body(self)
                rows = validate_rows(data.get("rows"))
                write_posts(rows)
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "saved_at": datetime.now().isoformat(timespec="seconds"),
                        "backup": BACKUP_PATH.name,
                    },
                )
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return
        if parsed.path == "/api/upload":
            try:
                filename, content, fields = parse_multipart_upload(self)
                suffix = Path(filename).suffix.lower()
                target_name = None
                if fields.get("fecha") and fields.get("hora"):
                    target_name = slot_filename(fields.get("fecha"), fields.get("hora"), suffix)
                saved = save_upload(filename, content, target_name)
                json_response(self, 200, {"ok": True, "filename": saved, "_asset": row_asset_info(saved)})
            except Exception as exc:
                json_response(self, 400, {"ok": False, "error": str(exc)})
            return
        self.send_error(404, "No encontrado")

    def serve_file(self, path):
        path = path.resolve()
        admin_root = ADMIN_DIR.resolve()
        if admin_root not in path.parents and path != admin_root:
            self.send_error(403, "Ruta no permitida")
            return
        if not path.exists() or not path.is_file():
            self.send_error(404, "No encontrado")
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_asset(self, filename):
        try:
            path = safe_asset_path(unquote(filename))
        except ValueError:
            self.send_error(403, "Ruta no permitida")
            return
        if not path.exists() or not path.is_file():
            self.send_error(404, "Archivo no encontrado")
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"[admin] {self.address_string()} - {format % args}")


def main():
    ADMIN_DIR.mkdir(exist_ok=True)
    POSTS_DIR.mkdir(exist_ok=True)
    print(f"Panel MEGAGYM disponible en http://{HOST}:{PORT}")
    with ThreadingHTTPServer((HOST, PORT), AdminHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
