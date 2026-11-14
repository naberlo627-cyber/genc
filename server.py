#!/usr/bin/env python3
"""Genç - önizleme ve dosya yükleme sunucusu.

Aynı klasördeki dosyaları yayınlar, /upload adresine gelen dosyaları
proje klasörüne kaydeder. Geliştirme sırasında canlı önizleme için.
"""
import http.server
import os
import re
import shutil
import socketserver
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "12000"))
UPLOAD_DIR = os.path.join(ROOT, "yuklenenler")


def parse_multipart(body, boundary):
    """Minimal multipart/form-data ayrıştırıcı; (dosya adı, içerik) çiftleri döner."""
    delim = b"--" + boundary
    parts = body.split(delim)
    for part in parts[1:]:
        if part.startswith(b"--"):
            break
        header, _, content = part.partition(b"\r\n\r\n")
        content = content[:-2] if content.endswith(b"\r\n") else content
        m = re.search(rb'filename="([^"]*)"', header)
        if not m:
            continue
        yield m.group(1).decode("utf-8", "replace"), content


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", ""):
            self.path = "/Genc.html"
        if parsed.path == "/upload":
            self.send_upload_page()
            return
        super().do_GET()

    def send_upload_page(self):
        files = sorted(os.listdir(UPLOAD_DIR)) if os.path.isdir(UPLOAD_DIR) else []
        rows = "".join(
            f'<li><a href="/yuklenenler/{urllib.parse.quote(f)}">{f}</a></li>'
            for f in files
        ) or "<li><em>Henüz dosya yok.</em></li>"
        body = f"""<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Genç - dosya yükle</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:640px;margin:0 auto;padding:24px;background:#E9E1FA;color:#17112E}}
h1{{font-size:22px}} form{{background:#fff;padding:18px;border-radius:16px;margin:16px 0}}
input[type=file]{{margin:10px 0;display:block}} button{{background:#5B3DF5;color:#fff;border:0;padding:12px 18px;border-radius:12px;font-weight:700;font-size:15px}}
ul{{background:#fff;padding:14px 14px 14px 32px;border-radius:16px}} a{{color:#5B3DF5}}
</style>
<h1>Genç - dosya yükle</h1>
<p>Dosyalar burada yüklenir, ardından <a href="/">uygulamaya</a> dönün.</p>
<form method="post" action="/upload" enctype="multipart/form-data">
  <input type="file" name="file" multiple required>
  <button type="submit">Yükle</button>
</form>
<h2>Yüklenenler</h2><ul>{rows}</ul>
</html>"""
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/upload":
            self.send_error(404)
            return
        ctype = self.headers.get("Content-Type", "")
        m = re.search(r'boundary="?([^";]+)"?', ctype)
        if not ctype.startswith("multipart/form-data") or not m:
            self.send_error(400, "multipart/form-data gerekli")
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        for name, content in parse_multipart(body, m.group(1).encode()):
            if not name:
                continue
            safe = os.path.basename(name).replace("\x00", "")
            if not safe:
                continue
            with open(os.path.join(UPLOAD_DIR, safe), "wb") as fh:
                fh.write(content)
        self.send_response(303)
        self.send_header("Location", "/upload")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with Server(("0.0.0.0", PORT), Handler) as httpd:
        print(f"Genç önizleme: http://0.0.0.0:{PORT}/  (yükleme: /upload)")
        httpd.serve_forever()
