#!/usr/bin/env python3
"""Genç - gerçek bilet/etkinlik toplayıcı.

Birden çok bilet satış sitesini tarar, her etkinliğin **gerçek** adını, mekanını,
konumunu, tarihini ve **fiyatını** toplar; aynı etkinliği satan kaynakları
eşleştirip en ucuzunu işaretler. Çıktı `data/tickets.json` (uygulama bunu okur).

Kaynaklar:
  * Biletinial - halka açık JSON-LD (schema.org Event + Offer). Giriş gerekmez.
    robots.txt genel botlara izin verir. Fiyat `offers.price` alanındadır.
Diğer siteler (Passo, Biletix, Bubilet) fiyatı giriş/Cloudflare arkasında
sakladığından şimdilik yalnızca listeleme düzeyinde eklenebilir; `SOURCES`
yapısı yeni kaynak eklemeye açıktır.

Kullanım:
    python3 tools/collect_tickets.py [--sehir İzmir] [--limit 200]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tickets.json"

UA = (
    "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120 Mobile Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "tr-TR,tr", "Accept": "text/html"}

# Biletinial listeleme sayfaları → uygulamanın tür adı.
BIletnial_LISTS = [
    ("https://biletinial.com/tr-tr/muzik", "Konser"),
    ("https://biletinial.com/tr-tr/tiyatro", "Tiyatro"),
    ("https://biletinial.com/tr-tr/etkinlikleri/stand-up", "Stand-up"),
    ("https://biletinial.com/tr-tr/opera-bale", "Opera ve bale"),
    ("https://biletinial.com/tr-tr/sinema", "Sinema"),
    ("https://biletinial.com/tr-tr/kids", "Çocuk etkinlikleri"),
    ("https://biletinial.com/tr-tr/spor", "Spor"),
]

# Uygulamanın tür adı → SVG illüstrasyon kimliği.
ART_BY_TYPE = {
    "Konser": "art-concert",
    "Tiyatro": "art-theatre",
    "Stand-up": "art-standup",
    "Opera ve bale": "art-dance",
    "Sinema": "art-film",
    "Çocuk etkinlikleri": "art-kids",
    "Spor": "art-sport",
    "Festival": "art-festival",
    "Sergi": "art-expo",
    "Gezi turu": "art-tour",
}

DISTRICT_COORDS = {
    "Bornova": (38.468, 27.222), "Karşıyaka": (38.461, 27.112), "Konak": (38.419, 27.128),
    "Buca": (38.385, 27.175), "Gaziemir": (38.323, 27.130), "Balçova": (38.393, 27.083),
    "Çiğli": (38.494, 27.064), "Bayraklı": (38.462, 27.163), "Karabağlar": (38.373, 27.133),
    "Menemen": (38.607, 27.070), "Torbalı": (38.155, 27.362), "Urla": (38.322, 26.766),
}


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    import math
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def sane_coords(lat, lng, district: str) -> tuple[float | None, float | None]:
    """Koordinat yoksa ya da ilçe merkezinden çok uzaksa ilçe merkezini kullan.

    Bazı kaynaklar etkinliğin kendi mekanı yerine organizatörün adresini verir
    (ör. İzmir DOB oyunları). İlçe merkezi, gösterilen 'km' değerini güvenilir kılar.
    """
    center = DISTRICT_COORDS.get(district)
    if center is None:
        return lat, lng
    if lat is None or lng is None:
        return center
    if _haversine((lat, lng), center) > 5:
        return center
    return lat, lng


MON = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
WD = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]


def fetch(url: str, tries: int = 3) -> str:
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            time.sleep(1.5 * (i + 1))
    raise last  # type: ignore[misc]


def ld_blocks(html_text: str) -> list:
    out = []
    for m in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.S,
    ):
        try:
            out.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return out


def walk(node):
    if isinstance(node, list):
        for item in node:
            yield from walk(item)
    elif isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)


def list_links(html_text: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for block in ld_blocks(html_text):
        for node in walk(block):
            if node.get("@type") == "ListItem" and node.get("url"):
                url = node["url"]
                if url not in seen:
                    seen.add(url)
                    links.append(url)
    return links


def _offers(offers) -> list[dict]:
    return [o for o in (offers if isinstance(offers, list) else [offers]) if isinstance(o, dict)]


def _price_of(offers) -> tuple[float | None, str | None, str | None]:
    prices: list[float] = []
    currency = None
    label = None
    for offer in _offers(offers):
        price = offer.get("price")
        if price is None:
            continue
        try:
            prices.append(float(price))
        except (TypeError, ValueError):
            continue
        currency = currency or offer.get("priceCurrency")
        label = label or offer.get("name")
    if not prices:
        return None, currency, label
    return min(prices), currency, label


def _availability(offers) -> str:
    for offer in _offers(offers):
        if offer.get("availability"):
            return str(offer["availability"]).rsplit("/", 1)[-1]
    return ""


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(text)).strip("-")


def when_label(start: str) -> tuple[str, str, str]:
    """ISO başlangıçtan (insan etiketi, hafta kısa adı, tarih) üretir."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", start or "")
    if not m:
        return "", "", ""
    y, mo, d, hh, mm = (int(x) for x in m.groups())
    try:
        wd = WD[time.strptime(f"{y}-{mo}-{d}", "%Y-%m-%d").tm_wday]
    except ValueError:
        wd = ""
    label = f"{wd} {d} {MON[mo - 1]}, {hh:02d}.{mm:02d}"
    return label, wd, f"{y}-{mo:02d}-{d:02d}"


def district_of(venue: str, street: str, city: str) -> str:
    """Mekan/adres metninden ilçe tahmini (ör. 'Bornova', 'Karşıyaka').

    Önce bilinen İzmir ilçeleri, sonra adresteki "X/İl" kalıbı, en son olarak
    adres sonundaki ilçe benzeri sözcük denenir. Bulunamazsa şehir adı döner.
    """
    for known in (
        "Bornova", "Karşıyaka", "Konak", "Buca", "Gaziemir", "Balçova",
        "Çiğli", "Bayraklı", "Karabağlar", "Menemen", "Torbalı", "Urla",
        "Çeşme", "Foça", "Kemalpaşa", "Menderes", "Seferihisar", "Tire",
    ):
        if norm(known) in norm(venue) or norm(known) in norm(street):
            return known
    # "Bakırköy/İstanbul", "Mamak/ Ankara" gibi kalıptan ilçeyi çıkar.
    m = re.search(r"([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s*/\s*" + re.escape(city or ""), street or "")
    if m:
        return m.group(1)
    # Şehirden bağımsız "X/İl" kalıbı (adres sonunda il adı yazılmış olabilir).
    m = re.search(r"([A-ZÇĞİÖŞÜ][a-zçğıöşü]+)\s*/", street or "")
    if m:
        return m.group(1)
    return city or ""


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(html_fragment: str) -> str:
    """HTML parçasını düz metne çevirir (etiketleri ve fazla boşluğu atar)."""
    import html as _html
    txt = re.sub(r"<[^>]+>", " ", html_fragment)
    return re.sub(r"\s+", " ", _html.unescape(txt)).strip()


def _tracking_info(html_text: str) -> dict:
    """Sayfadaki `trackingInfo` JSON'unu (kadro, süre, tür) okur."""
    m = re.search(
        r'<script[^>]*id=["\']trackingInfo["\'][^>]*>(.*?)</script>', html_text, re.S
    )
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def _fact(html_text: str, label: str) -> str:
    """Detay sayfasındaki "Etkinlik Türü / Süre / Yaş Sınırı" gibi bilgi satırını okur."""
    m = re.search(
        r"<dt>\s*" + re.escape(label) + r"[^<]*</dt>\s*<dd>(.*?)</dd>", html_text, re.S
    )
    return _text(m.group(1)) if m else ""


def _rules(html_text: str) -> list[str]:
    """Etkinlik kuralları maddelerini toplar.

    Biletinial iki biçim kullanır: `event-rules-v2__content` bloğu (paragraflar)
    ve facts tablosundaki tek `dd` içinde • ile ayrılmış metin. İkisini de
    destekler; tür bilgisinin sızmasını önlemek için yalnızca kural bloğu okunur.
    """
    block = re.search(r'class="event-rules-v2__content"[^>]*>(.*?)</div>', html_text, re.S)
    if not block:
        block = re.search(r"Etkinlik Kuralları.*?</dt>\s*<dd>(.*?)</dd>", html_text, re.S)
    if not block:
        return []
    raw = block.group(1)
    chunks = re.split(r"</p>|<br\s*/?>", raw)
    items: list[str] = []
    for chunk in chunks:
        txt = _text(chunk)
        if not txt:
            continue
        for part in re.split(r"\s*[•\u2022]\s*", txt):
            part = part.strip()
            if len(part) > 3:
                items.append(part)
    return items[:15]


def detail_extras(html_text: str, node: dict) -> dict:
    """Detay sayfasından açıklama, kadro, süre, tür, yaş sınırı, kurallar ve organizatörü toplar."""
    info = _tracking_info(html_text)
    artists = [a.get("profileName", "").strip() for a in (info.get("artists") or []) if isinstance(a, dict)]
    directors = [d.get("profileName", "").strip() for d in (info.get("directors") or []) if isinstance(d, dict)]
    genres = [g.get("genre", "").strip() for g in (info.get("genres") or []) if isinstance(g, dict)]
    runtime = info.get("runtime") or 0
    desc = (node.get("description") or "").strip()
    org = (node.get("organizer") or {})
    if isinstance(org, list):
        org = org[0] if org else {}
    organizer = (org.get("name") or "").strip() if isinstance(org, dict) else ""
    age = _fact(html_text, "Yaş Sınırı")
    genre_label = _fact(html_text, "Etkinlik Türü")
    return {
        "description": desc,
        "cast": [{"name": n, "role": "Yönetmen"} for n in dict.fromkeys(directors)]
        + [{"name": n, "role": "Oyuncu"} for n in dict.fromkeys(artists)],
        "runtime": runtime,
        "genres": list(dict.fromkeys(genres)),
        "genre_label": genre_label,
        "age": age,
        "rules": _rules(html_text),
        "organizer": organizer,
    }


def parse_events(html_text: str, source: str, url: str, genre: str) -> list[dict]:
    events = []
    for block in ld_blocks(html_text):
        for node in walk(block):
            if node.get("@type") != "Event":
                continue
            loc = node.get("location") or {}
            addr = loc.get("address") or {}
            geo = loc.get("geo") or {}
            price, currency, label = _price_of(node.get("offers"))
            start = node.get("startDate") or ""
            when, wd, date = when_label(start)
            city = norm_city((addr.get("addressLocality") or "").strip())
            street = (addr.get("streetAddress") or "").strip()
            venue = (loc.get("name") or "").strip()
            title = (node.get("name") or "").strip()
            img = (node.get("image") or "").strip()
            if isinstance(node.get("image"), list) and node["image"]:
                img = str(node["image"][0])
            district = district_of(venue, street, city)
            lat, lng = sane_coords(_to_float(geo.get("latitude")), _to_float(geo.get("longitude")), district)
            eid = f"{slug(title)[:40]}-{date}-{hashlib.sha1(norm(venue).encode()).hexdigest()[:5]}"
            extras = detail_extras(html_text, node)
            events.append(
                {
                    "id": eid,
                    "type": genre,
                    "art": ART_BY_TYPE.get(genre, "art-festival"),
                    "title": title,
                    "venue": venue,
                    "city": city,
                    "image": img,
                    "district": district,
                    "address": street,
                    "lat": lat,
                    "lng": lng,
                    "start": start,
                    "date": date,
                    "when": when,
                    "wd": wd,
                    "price": price,
                    "price_label": label or "Bilet",
                    "currency": currency or "TRY",
                    "availability": _availability(node.get("offers")),
                    "source": source,
                    "provider": "biletinial",
                    "ref": url,
                    "url": url,
                    **extras,
                }
            )
    return events


def collect_biletinial(limit: int) -> list[dict]:
    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for listing, genre in BIletnial_LISTS:
        try:
            html_text = fetch(listing)
        except Exception as exc:
            print(f"  ! liste alınamadı: {listing} ({exc})")
            continue
        for link in list_links(html_text):
            if link not in seen:
                seen.add(link)
                targets.append((link, genre))
    print(f"  Biletinial: {len(targets)} etkinlik bağlantısı")
    targets = targets[:limit]

    def one(item: tuple[str, str]) -> list[dict]:
        link, genre = item
        try:
            time.sleep(0.25)  # siteyi yormamak için
            return parse_events(fetch(link), "Biletinial", link, genre)
        except Exception as exc:
            print(f"  ! detay alınamadı: {link} ({exc})")
            return []

    events: list[dict] = []
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for found in pool.map(one, targets):
            events.extend(found)
            done += 1
            if done % 40 == 0:
                print(f"    ...{done}/{len(targets)} işlendi")
    return events


PASSO_API = "https://ticketingweb.passo.com.tr/api/passoweb"
PASSO_IMG = "https://image.passo.com.tr/api/r/tr/p/"


def passo_img(name, folder: str = "event") -> str:
    """Passo görsel dosya adını tam URL'ye çevirir (liste veya metin kabul eder).

    Etkinlik görselleri `event/`, mekan (salon) görselleri `venueTemplate/`
    klasöründe sunulur; yanlış klasör 500 döner.
    """
    if isinstance(name, list):
        name = name[0] if name else ""
    name = (name or "").strip()
    # Passo görsel CDN'i boyut parametresi olmadan 500 döner.
    return f"{PASSO_IMG}{folder}/{name}?w=800&h=500" if name else ""


PASSO_HDRS = {
    "User-Agent": UA,
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.passo.com.tr",
    "currentculture": "tr-TR",
}


def passo_type(genre: str, name: str) -> str:
    g = norm(f"{genre} {name}")
    if any(k in g for k in ("futbol", "spor", "basket", "mac", "voleybol")):
        return "Spor"
    if "tiyatro" in g:
        return "Tiyatro"
    if "stand" in g or "komedi" in g:
        return "Stand-up"
    if "opera" in g or "bale" in g:
        return "Opera ve bale"
    if "sinema" in g or "film" in g:
        return "Sinema"
    if "festival" in g:
        return "Festival"
    if "cocuk" in g or "kids" in g:
        return "Çocuk etkinlikleri"
    if "sergi" in g:
        return "Sergi"
    if "dans" in g:
        return "Dans"
    return "Konser"


def _post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=PASSO_HDRS, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=PASSO_HDRS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _passo_rules(note: str) -> list[str]:
    """Passo `detailNote` alanını kural maddelerine çevirir (satır başına bir madde)."""
    text = _text(note or "")
    if not text:
        return []
    parts = re.split(r"\s*(?:•|\u2022|\u00b7)\s*|\s+-\s+(?=[A-ZÇĞİÖŞÜ])", text)
    items = [p.strip(" -–—\t") for p in parts]
    return [p for p in items if len(p) > 3][:15]


def passo_extras(v: dict) -> dict:
    """Passo detay yanıtından açıklama, kural, tür ve organizatörü çıkarır.

    Passo zengin detay verir: `detailPageDescription` (açıklama), `detailNote`
    (etkinlik kuralları), `organizerName`, `genreName`/`subGenreName` (tür).
    """
    desc = _text(v.get("detailPageDescription"))
    genres = [g for g in (v.get("genreName"), v.get("subGenreName")) if g]
    return {
        "description": desc,
        "cast": [],
        "runtime": 0,
        "genres": list(dict.fromkeys(genres)),
        "genre_label": (v.get("subGenreName") or v.get("genreName") or "").strip(),
        "age": "",
        "rules": _passo_rules(v.get("detailNote")),
        "organizer": (v.get("organizerName") or "").strip(),
    }


def collect_passo(limit: int) -> list[dict]:
    """Passo'nun halka açık web API'si (fiyatlar kategori bazında açık)."""
    try:
        listing = _post_json(f"{PASSO_API}/allevents", {"LanguageId": 118, "from": 0, "size": 3000})
    except Exception as exc:
        print(f"  ! Passo listesi alınamadı: {exc}")
        return []
    cands = [
        e for e in listing.get("valueList", [])
        if e.get("seoUrl") and "zmir" in norm(e.get("venueName", "") + e.get("seoTitle", ""))
    ]
    print(f"  Passo: {len(cands)} İzmir adayı (toplam {listing.get('totalItemCount')})")
    events: list[dict] = []
    for e in cands[:limit]:
        try:
            v = _get_json(f"{PASSO_API}/geteventdetails/{e['seoUrl']}/{e['id']}/118").get("value") or {}
        except Exception:
            continue
        if norm(v.get("venueCity", "")) != "izmir":
            continue
        cats = [c for c in (v.get("categories") or []) if c.get("price") is not None]
        price = v.get("lowPrice")
        if price is None and cats:
            price = min(c["price"] for c in cats)
        start = (v.get("date") or "").replace(" ", "T")
        when, wd, date = when_label(start)
        genre = passo_type(v.get("genreName", ""), v.get("name", ""))
        title = (v.get("name") or "").strip()
        venue = (v.get("venueName") or "").strip()
        if not title or not date:
            continue
        eid = f"{slug(title)[:40]}-{date}-{hashlib.sha1(norm(venue).encode()).hexdigest()[:5]}"
        district = (v.get("venueCounty") or "").strip()
        img = passo_img(v.get("detailPageImageName") or v.get("homePageImageName"))
        venue_img = passo_img(v.get("venueTemplateImageName") or v.get("venueImageNames"))
        lat, lng = sane_coords(_to_float(v.get("venueLatitude")), _to_float(v.get("venueLongitude")), district)
        available = bool(v.get("isAvailable"))
        events.append({
            "id": eid,
            "type": genre,
            "art": ART_BY_TYPE.get(genre, "art-festival"),
            "title": title,
            "venue": venue,
            "city": (v.get("venueCity") or "İzmir").strip(),
            "image": img,
            "venue_image": venue_img,
            "district": district,
            "address": (v.get("venueAdress") or "").strip(),
            "lat": lat,
            "lng": lng,
            "start": start,
            "date": date,
            "when": when,
            "wd": wd,
            "price": float(price) if price is not None else None,
            "price_label": "Bilet",
            "currency": "TRY",
            "availability": "InStock" if available else "",
            "source": "Passo",
            "provider": "passo",
            "ref": {"seo": e["seoUrl"], "id": e["id"]},
            "url": f"https://www.passo.com.tr/tr/etkinlik/{e['seoUrl']}",
            **passo_extras(v),
        })
        time.sleep(0.2)
    return events


# Biletino şehir listeleme sayfaları. Detay sayfaları halka açık JSON-LD
# (schema.org Event + Offer) taşır; fiyat `offers.price` alanındadır.
BILETINO_CITY_LISTS = [
    "https://biletino.com/tr/city/istanbul/",
    "https://biletino.com/tr/city/ankara/",
    "https://biletino.com/tr/city/izmir/",
    "https://biletino.com/tr/city/antalya/",
    "https://biletino.com/tr/city/bursa/",
]


def biletino_type(schema_type: str, name: str, desc: str) -> str:
    """schema.org @type'ı önceler, yoksa ad/açıklamadan tür tahmin eder."""
    direct = {
        "MusicEvent": "Konser",
        "TheaterEvent": "Tiyatro",
        "ComedyEvent": "Stand-up",
        "DanceEvent": "Dans",
        "Festival": "Festival",
        "ChildrensEvent": "Çocuk etkinlikleri",
        "ScreeningEvent": "Sinema",
        "SportsEvent": "Spor",
        "ExhibitionEvent": "Sergi",
        # Atölye/workshop etkinlikleri uygulamada "Sergi" başlığı altında toplanır.
        "EducationEvent": "Sergi",
    }
    if schema_type in direct:
        return direct[schema_type]
    g = norm(f"{name} {desc}")
    if any(k in g for k in ("stand up", "standup", "komedi", "komedyen")):
        return "Stand-up"
    if any(k in g for k in ("tiyatro", "muzikal", "opera", "bale")):
        return "Opera ve bale" if any(k in g for k in ("opera", "bale")) else "Tiyatro"
    if any(k in g for k in ("sinema", "film")):
        return "Sinema"
    if any(k in g for k in ("atolye", "workshop", "egitim", "seminer", "tadim", "pilates", "yoga")):
        return "Sergi"
    if any(k in g for k in ("dans",)):
        return "Dans"
    if any(k in g for k in ("kosu", "turnuva", "mac", "spor")):
        return "Spor"
    # SocialEvent ve sınıflandırılamayanlar: parti/gece etkinlikleri müzik ağırlıklı.
    return "Konser"


def norm_city(city: str) -> str:
    """Kaynakların şehir adını uygulamanın il adına indirger.

    Biletinial İstanbul'u "İstanbul Avrupa"/"İstanbul Anadolu" diye ikiye
    böler; uygulama İstanbul'u tek il olarak kullanır.
    """
    c = (city or "").strip()
    if c.startswith("İstanbul"):
        return "İstanbul"
    return c


def parse_biletino_event(html_text: str, url: str) -> list[dict]:
    """Biletino detay sayfasındaki JSON-LD Event kaydını uygulama olayına çevirir."""
    out: list[dict] = []
    for block in ld_blocks(html_text):
        for node in walk(block):
            if not str(node.get("@type", "")).endswith("Event"):
                continue
            if node.get("@type") == "EventSeries":
                continue
            loc = node.get("location") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}
            addr = loc.get("address") or {}
            if isinstance(addr, list):
                addr = addr[0] if addr else {}
            price, currency, label = _price_of(node.get("offers"))
            start = node.get("startDate") or ""
            when, wd, date = when_label(start)
            title = (node.get("name") or "").strip()
            venue = (loc.get("name") or "").strip()
            if not title or not date or not venue:
                continue
            desc = (node.get("description") or "").strip()
            city = (addr.get("addressRegion") or addr.get("addressLocality") or "").strip()
            city = norm_city(city)
            street = (addr.get("streetAddress") or "").strip()
            district = (addr.get("addressLocality") or "").strip() or district_of(venue, street, city)
            img = node.get("image") or ""
            if isinstance(img, list):
                img = img[0] if img else ""
            lat = _to_float(addr.get("latitude"))
            lng = _to_float(addr.get("longitude"))
            lat, lng = sane_coords(lat, lng, district)
            performers = node.get("performer") or []
            if isinstance(performers, dict):
                performers = [performers]
            cast = [{"name": (p.get("name") or "").strip(), "role": "Sanatçı"}
                    for p in performers if isinstance(p, dict) and p.get("name")]
            genre = biletino_type(str(node.get("@type", "")), title, desc)
            eid = f"{slug(title)[:40]}-{date}-{hashlib.sha1(norm(venue).encode()).hexdigest()[:5]}"
            out.append({
                "id": eid,
                "type": genre,
                "art": ART_BY_TYPE.get(genre, "art-festival"),
                "title": title,
                "venue": venue,
                "city": city,
                "image": img,
                "district": district,
                "address": street,
                "lat": lat,
                "lng": lng,
                "start": start,
                "date": date,
                "when": when,
                "wd": wd,
                "price": price,
                "price_label": label or "Bilet",
                "currency": currency or "TRY",
                "availability": _availability(node.get("offers")),
                "source": "Biletino",
                "provider": "biletino",
                "ref": url,
                "url": url,
                "description": desc,
                "cast": cast,
                "runtime": 0,
                "genres": [],
                "genre_label": "",
                "age": "",
                "rules": [],
                "organizer": "",
            })
    return out


def collect_biletino(limit: int) -> list[dict]:
    """Biletino: halka açık JSON-LD (schema.org Event + Offer). Fiyat `offers.price`."""
    targets: dict[str, str] = {}
    for listing in BILETINO_CITY_LISTS:
        try:
            html_text = fetch(listing)
        except Exception as exc:
            print(f"  ! Biletino liste alınamadı: {listing} ({exc})")
            continue
        for path in sorted(set(re.findall(r'href="(/tr/e-[^"]+?)"', html_text))):
            targets.setdefault("https://biletino.com" + path, "")
    print(f"  Biletino: {len(targets)} etkinlik bağlantısı")
    items = list(targets.keys())[:limit]

    def one(link: str) -> list[dict]:
        try:
            time.sleep(0.25)
            return parse_biletino_event(fetch(link), link)
        except Exception as exc:
            print(f"  ! Biletino detay alınamadı: {link} ({exc})")
            return []

    events: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for found in pool.map(one, items):
            events.extend(found)
    return events


# Yeni kaynak eklemek için: (ad, toplayıcı fonksiyonu)
SOURCES = [
    ("Biletinial", collect_biletinial),
    ("Passo", collect_passo),
    ("Biletino", collect_biletino),
]


def key_of(ev: dict) -> str:
    """Aynı etkinliği farklı kaynaklarda eşleştirmek için anahtar."""
    return f"{norm(ev['title'])}|{norm(ev['venue'])}|{ev.get('date','')}"


def dedupe_and_cheapest(events: list[dict]) -> list[dict]:
    """Aynı etkinlik+tarih+mekan kayıtlarını birleştirir, en ucuzu işaretler."""
    groups: dict[str, list[dict]] = {}
    for ev in events:
        groups.setdefault(key_of(ev), []).append(ev)
    result = []
    for group in groups.values():
        priced = [e for e in group if e.get("price") is not None]
        cheapest = min(priced, key=lambda e: e["price"]) if priced else group[0]
        entry = dict(cheapest)
        for field in ("image", "venue_image"):
            if not entry.get(field):
                entry[field] = next((e[field] for e in group if e.get(field)), "")
        # Detay alanları: en ucuz kayıtta yoksa aynı etkinliği taşıyan diğer kaynaktan al.
        for field in ("description", "cast", "genres", "genre_label", "age", "rules", "organizer", "runtime"):
            if not entry.get(field):
                entry[field] = next((e[field] for e in group if e.get(field)), entry.get(field) or ([] if field in ("cast", "genres", "rules") else (0 if field == "runtime" else "")))
        entry["sources"] = sorted({e["source"] for e in group})
        entry["price_by_source"] = {
            e["source"]: e["price"] for e in group if e.get("price") is not None
        }
        entry["cheapest_source"] = cheapest["source"] if len(entry["sources"]) > 1 else None
        result.append(entry)
    result.sort(key=lambda e: (e.get("date") or "", e.get("price") or 0))
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sehir", default="İzmir", help="şehir filtresi (virgülle birden çok: 'İzmir,Ankara'; boş = tümü)")
    ap.add_argument("--limit", type=int, default=200, help="kaynak başına detay sınırı")
    args = ap.parse_args()

    wanted = [s.strip() for s in args.sehir.split(",") if s.strip()]
    all_events: list[dict] = []
    for name, collector in SOURCES:
        print(f"→ {name} taranıyor…")
        all_events.extend(collector(args.limit))

    if wanted:
        needles = [norm(s) for s in wanted]
        all_events = [e for e in all_events if any(n in norm(e.get("city", "")) for n in needles)]

    merged = dedupe_and_cheapest(all_events)
    cities = sorted({e.get("city", "") for e in merged if e.get("city")})
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "city": (cities[0] if len(cities) == 1 else ""),
        "cities": cities,
        "count": len(merged),
        "sources": [name for name, _ in SOURCES],
        "events": merged,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    priced = [e for e in merged if e.get("price") is not None]
    print(f"✓ {len(merged)} etkinlik yazıldı ({len(priced)} tanesi fiyatlı) → {OUT}")
    for ev in merged[:10]:
        price = f"{ev['price']:.0f} ₺" if ev.get("price") is not None else "—"
        print(f"   {price:>9}  {ev['title'][:34]:<34} {ev.get('venue','')[:26]}")


if __name__ == "__main__":
    main()
