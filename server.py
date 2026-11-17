#!/usr/bin/env python3
"""Genç - önizleme ve dosya yükleme sunucusu.

Aynı klasördeki dosyaları yayınlar, /upload adresine gelen dosyaları
proje klasörüne kaydeder. Geliştirme sırasında canlı önizleme için.
"""
import http.server
import json
import os
import re
import socketserver
import threading
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "12000"))
UPLOAD_DIR = os.path.join(ROOT, "yuklenenler")

# ---------- canlı durum (boş koltuk / satışta mı) ----------
# Kaynak sitelerin halka açık uçlarından kısa aralıklarla durum çeker, önbelleğe
# alır ve HİÇBİR durumda hata döndürmez: kaynak yanıt vermezse son bilinen
# durum (veya "unknown") döner. Böylece uygulama asla çökmez.
LIVE_TTL = 45          # saniye: bu süre içinde tekrar sorgulama yapılmaz
LIVE_TIMEOUT = 6       # saniye: kaynak isteği zaman aşımı
LIVE_MAX = 60          # tek istekte sorgulanacak en fazla etkinlik
_UA = "GencApp/1.3 (egitim amacli demo; iletisim: openhands@all-hands.dev)"
_live_cache = {}       # id -> {"ts": float, "data": {...}}
_live_lock = threading.Lock()
_index_cache = {"mtime": 0.0, "map": {}}


def _ticket_index():
    """data/tickets.json içinden id -> {provider, ref} eşlemesi (değişince tazelenir)."""
    path = os.path.join(ROOT, "data", "tickets.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    if _index_cache["mtime"] == mtime:
        return _index_cache["map"]
    try:
        with open(path, encoding="utf-8") as fh:
            events = json.load(fh).get("events", [])
        mapping = {
            e["id"]: {"provider": e.get("provider"), "ref": e.get("ref")}
            for e in events if e.get("id")
        }
    except Exception:
        mapping = _index_cache["map"]  # bozuksa eskisini koru
    _index_cache.update(mtime=mtime, map=mapping)
    return mapping


def _http(url, headers=None, timeout=LIVE_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": _UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _json_ld_events(html):
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            node = json.loads(m.group(1))
        except Exception:
            continue
        stack = [node]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                if cur.get("@type") == "Event":
                    yield cur
                stack.extend(cur.values())
            elif isinstance(cur, list):
                stack.extend(cur)


def _status_biletinial(ref):
    offers = None
    for ev in _json_ld_events(_http(ref)):
        if ev.get("offers"):
            offers = ev["offers"]
            break
    offer = offers[0] if isinstance(offers, list) and offers else offers
    if not isinstance(offer, dict):
        return {"status": "unknown"}
    avail = (offer.get("availability") or "").rsplit("/", 1)[-1]
    price = offer.get("price")
    return {
        "status": "soldout" if avail.lower() == "soldout" else "available",
        "price": float(price) if price not in (None, "") else None,
    }


def _status_passo(ref):
    seo, eid = (ref or {}).get("seo"), (ref or {}).get("id")
    if not seo or not eid:
        return {"status": "unknown"}
    url = f"https://ticketingweb.passo.com.tr/api/passoweb/geteventdetails/{seo}/{eid}/118"
    data = json.loads(_http(url, {"Accept": "application/json", "currentculture": "tr-TR",
                                  "Origin": "https://www.passo.com.tr"}))
    v = data.get("value") or {}
    price = v.get("lowPrice")
    if price is None:
        cats = [c["price"] for c in (v.get("categories") or []) if c.get("price") is not None]
        price = min(cats) if cats else None
    available = bool(v.get("isAvailable")) and not v.get("cancelled")
    return {"status": "available" if available else "soldout",
            "price": float(price) if price is not None else None}


def _live_one(eid):
    now = time.time()
    with _live_lock:
        cached = _live_cache.get(eid)
        if cached and now - cached["ts"] < LIVE_TTL:
            return cached["data"]
    entry = _ticket_index().get(eid) or {}
    provider, ref = entry.get("provider"), entry.get("ref")
    try:
        if provider == "biletinial" and ref:
            data = _status_biletinial(ref)
        elif provider == "passo" and ref:
            data = _status_passo(ref)
        else:
            data = {"status": "unknown"}
    except Exception:
        data = {"status": "unknown"}
    data = {**data, "checked_at": int(now)}
    # Bilinmeyen durum önceki bilinen durumu EZMESİN.
    with _live_lock:
        if data["status"] != "unknown" or eid not in _live_cache:
            _live_cache[eid] = {"ts": now, "data": data}
        else:
            data = _live_cache[eid]["data"]
    return data


def live_status(ids):
    ids = [i for i in dict.fromkeys(ids) if i][:LIVE_MAX]
    if not ids:
        return {}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_live_one, ids))
    return dict(zip(ids, results))



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

    def _send_json(self, obj, status=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", ""):
            self.path = "/Genc.html"
        if parsed.path == "/upload":
            self.send_upload_page()
            return
        if parsed.path == "/live":
            qs = urllib.parse.parse_qs(parsed.query)
            ids = [i for i in (qs.get("ids", [""])[0]).split(",") if i]
            try:
                self._send_json({"ok": True, "status": live_status(ids)})
            except Exception:
                # Canlı takip asla uygulamayı düşürmesin: bilinmeyen durum dön.
                self._send_json({"ok": True, "status": {i: {"status": "unknown"} for i in ids}})
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
body{{font-family:system-ui,sans-serif;max-width:640px;margin:0 auto;padding:24px;background:#F7F0E6;color:#14100D}}
h1{{font-size:22px}} form{{background:#fff;padding:18px;border-radius:16px;margin:16px 0}}
input[type=file]{{margin:10px 0;display:block}} button{{background:#E5402A;color:#fff;border:0;padding:12px 18px;border-radius:12px;font-weight:700;font-size:15px}}
ul{{background:#fff;padding:14px 14px 14px 32px;border-radius:16px}} a{{color:#E5402A}}
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
        saved = []
        for name, content in parse_multipart(body, m.group(1).encode()):
            if not name:
                continue
            safe = os.path.basename(name).replace("\x00", "")
            safe = re.sub(r"[^0-9A-Za-z._-]+", "-", safe).strip("-") or "dosya"
            unique = f"{int(time.time())}-{os.urandom(3).hex()}-{safe}"
            with open(os.path.join(UPLOAD_DIR, unique), "wb") as fh:
                fh.write(content)
            saved.append(unique)
        # Uygulama JSON bekler (görsel bağlantısını göstermek için).
        data = json.dumps({"ok": True, "files": saved,
                           "url": f"/yuklenenler/{urllib.parse.quote(saved[-1])}" if saved else None}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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
