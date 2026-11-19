#!/usr/bin/env python3
"""Genç - etkinlik kayıtlarındaki ilçe adlarını doğrular ve düzeltir.

Kaynak siteler ilçe alanına her zaman ilçe yazmıyor: kimi kayıt il adını
("İstanbul", "Ankara"), kimi semt adını ("Kozyatağı", "Kavaklıdere", "Ulus"),
kimi de bozuk karakterli metni ("Osmangazi̇" - sondaki birleşik nokta) taşıyor.
İlçe süzgeci bu kayıtları dışarıda bıraktığı için etkinlikler kayboluyordu.

Düzeltme sırası (ilk eşleşen kazanır):
  1. zaten geçerli          -> dokunulmaz
  2. aynı mekanın diğer kayıtlarındaki geçerli ilçe
  3. bilinen semt -> ilçe sözlüğü
  4. adres metninde geçen ilçe adı
  5. mekan adında geçen ilçe adı
  6. koordinata en yakın ilçe merkezi (8 km'ye kadar)
  7. çözülemezse ilçe boşaltılır: kayıt il genelinde görünür, ilçe süzgecinde
     yanlış yere düşmez

`data/cities/*.json` dosyaları yerinde güncellenir; gömülü veri için
ardından `tools/embed_data.py` çalıştırılır.
Tekrar çalıştırılabilir: ikinci çalıştırmada değişiklik yapmaz.

Kullanım: python3 tools/fix_districts.py [--dry-run]
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CITY_DIR = ROOT / "data" / "cities"
SOURCE = ROOT / "data" / "tickets.json"
APP = ROOT / "Genc.html"

# İlçe alanına yazılmış semt adları. Yalnızca ilçesi kesin olanlar.
SEMT = {
    ("Ankara", "kavaklidere"): "Çankaya",
    ("Ankara", "ulus"): "Altındağ",
    ("Ankara", "cayyolu"): "Çankaya",
    ("Ankara", "kizilay"): "Çankaya",
    ("Ankara", "bahcelievler"): "Çankaya",
    ("İstanbul", "kozyatagi"): "Kadıköy",
    ("İstanbul", "caddebostan"): "Kadıköy",
    ("İstanbul", "bostanci"): "Kadıköy",
    ("İstanbul", "moda"): "Kadıköy",
    ("İstanbul", "bebek"): "Beşiktaş",
    ("İstanbul", "etiler"): "Beşiktaş",
    ("İstanbul", "nisantasi"): "Şişli",
    ("İstanbul", "mecidiyekoy"): "Şişli",
    ("İstanbul", "maslak"): "Sarıyer",
    ("İstanbul", "istinye"): "Sarıyer",
    ("İzmir", "alsancak"): "Konak",
    ("İzmir", "karsiyaka"): "Karşıyaka",
    ("İzmir", "bostanli"): "Karşıyaka",
    ("Bursa", "gorukle"): "Nilüfer",
    ("Bursa", "setbasi"): "Osmangazi",
}

# Koordinat yoksa/uzaksa kabul edilmeyecek en uzak mesafe.
MAX_KM = 8.0
# En yakın ilçe, ikinciye bu kadar kat yakın olmalı; yoksa seçim belirsizdir
# ve yanlış ilçeye yazmak yerine boş bırakılır.
MIN_RATIO = 1.3
MIN_ILCE_LEN = 4  # "Ulus", "Kars" gibi kısa adlar metinde yanlış eşleşir.


def norm(x: str | None) -> str:
    """Türkçe duyarlı, aksan ve boşluk bağımsız karşılaştırma anahtarı."""
    x = unicodedata.normalize("NFC", x or "")
    x = "".join(c for c in unicodedata.normalize("NFD", x) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", "", x).lower()


def km(a, b, c, d) -> float:
    r = 6371.0
    t = math.pi / 180
    dl = (c - a) * t
    dn = (d - b) * t
    h = math.sin(dl / 2) ** 2 + math.cos(a * t) * math.cos(c * t) * math.sin(dn / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def load_districts() -> dict[str, list[str]]:
    src = APP.read_text(encoding="utf-8")
    m = re.search(r"var TR_CITY_DISTRICTS\s*=\s*(\{.*?\});\s*\n", src, re.S)
    if not m:
        raise SystemExit("TR_CITY_DISTRICTS bulunamadı")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(1)))


def load_city_files() -> list[tuple[Path, dict, list[dict]]]:
    """data/cities/*.json dosyalarını (yol, üst nesne, etkinlikler) olarak döner."""
    out = []
    for path in sorted(CITY_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        events = payload.get("events") if isinstance(payload, dict) else payload
        if not events:
            continue
        out.append((path, payload, events))
    return out


def main() -> None:
    import sys

    dry = "--dry-run" in sys.argv
    districts = load_districts()
    files = load_city_files()
    events = [e for _, _, evs in files for e in evs]

    valid = {c: {norm(d): d for d in ds} for c, ds in districts.items()}
    by_venue: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for e in events:
        key = norm(e.get("district"))
        if key in valid.get(e["city"], {}):
            by_venue[(e["city"], norm(e["venue"]))][valid[e["city"]][key]] += 1

    # İlçe merkezleri: o ilçedeki koordinatlı kayıtların ortalaması.
    pts: dict[tuple[str, str], list] = defaultdict(list)
    for e in events:
        key = norm(e.get("district"))
        if key in valid.get(e["city"], {}) and (e.get("lat") or 0) > 1:
            pts[(e["city"], valid[e["city"]][key])].append((e["lat"], e["lng"]))
    centers = {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in pts.items()}

    def resolve(e: dict) -> tuple[str, str]:
        city = e["city"]
        cur = norm(e.get("district"))
        if cur in valid.get(city, {}):
            return valid[city][cur], "gecerli"
        # İl listesinde olmayan bir ad (ör. "Kıbrıs") ilçe çözümlemesi yapamaz.
        if city not in valid:
            return "", "bilinmeyen-il"

        vk = (city, norm(e["venue"]))
        if vk in by_venue:
            return by_venue[vk].most_common(1)[0][0], "mekan"

        if (city, cur) in SEMT:
            return SEMT[(city, cur)], "semt"

        addr = norm(e.get("address"))
        # "Zeytinburnu/", "Kadıköy/İst", "Maltepe - İstanbul" gibi kalıplar güçlü
        # işarettir; "Gölbaşı Caddesi" ise sokak adıdır ve ilçe sayılmaz.
        STREET = ("caddesi", "cadde", "cad.", "cad ", "sokak", "sok.", "sok ", "bulvarı",
                  "bulvar", "mahallesi", "mah.", "mah ", "sitesi", "plaza")
        strong = None
        weak = None
        for key, real in valid[city].items():
            if len(key) < MIN_ILCE_LEN:
                continue
            pos = addr.find(key)
            if pos < 0:
                continue
            tail = addr[pos + len(key):][:16].lstrip()
            if tail.startswith("/") or tail.startswith("-") or tail.startswith("–"):
                strong = real
                break
            if any(tail.startswith(s) for s in STREET):
                continue
            if weak is None:
                weak = real
        if strong:
            return strong, "adres"
        if weak:
            return weak, "adres"

        venue = norm(e["venue"])
        hits = [real for k, real in valid[city].items() if len(k) >= MIN_ILCE_LEN and k in venue]
        if hits:
            return hits[0], "mekan-adi"

        if (e.get("lat") or 0) > 1:
            near = sorted(
                (km(e["lat"], e["lng"], *centers[(city, r)]), r)
                for r in districts[city]
                if (city, r) in centers
            )
            if near:
                dist, real = near[0]
                runner_up = near[1][0] if len(near) > 1 else float("inf")
                confident = dist <= MAX_KM and runner_up >= max(dist, 0.1) * MIN_RATIO
                if confident:
                    return real, "koordinat"

        return "", "bos"

    stats: Counter = Counter()
    changed: list[tuple[str, str, str, str]] = []
    for e in events:
        new, how = resolve(e)
        stats[how] += 1
        old = e.get("district") or ""
        if norm(new) != norm(old) or new != old:
            changed.append((e["city"], e["venue"], old, new))
            e["district"] = new
            e["_dist_changed"] = True

    print(f"toplam {len(events)} kayıt")
    for k in ("gecerli", "mekan", "semt", "adres", "mekan-adi", "koordinat", "bos", "bilinmeyen-il"):
        if stats[k]:
            print(f"  {k:12s} {stats[k]:4d}")
    print(f"değişen: {len(changed)}")
    if dry:
        for c, v, o, n in changed[:20]:
            print(f"  {c} | {v[:38]:38s} {o!r} -> {n!r}")
        print("(dry-run: dosyalar yazılmadı)")
        return

    # Her il dosyası kendi kayıtlarını taşır; düzeltilen ilçe yerinde yazılır.
    written = 0
    for path, payload, evs in files:
        if not any(e.get("_dist_changed") for e in evs):
            continue
        for e in evs:
            e.pop("_dist_changed", None)
        if isinstance(payload, dict):
            payload["events"] = evs
            out = payload
        else:
            out = evs
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written += 1
    print(f"yazıldı: {written} il dosyası")

    # Yayın yükü il dosyalarını tickets.json'dan yeniden üretir; kaynak
    # düzeltilmezse bir sonraki yenilemede eski ilçeler geri gelirdi.
    if SOURCE.exists():
        src_payload = json.loads(SOURCE.read_text(encoding="utf-8"))
        fixed = {e["id"]: e.get("district") or "" for e in events}
        touched = 0
        for e in src_payload.get("events", []):
            new_d = fixed.get(e.get("id"))
            if new_d is not None and (e.get("district") or "") != new_d:
                e["district"] = new_d
                touched += 1
        if touched:
            SOURCE.write_text(json.dumps(src_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"kaynak güncellendi: {SOURCE.relative_to(ROOT)} ({touched} kayıt)")



if __name__ == "__main__":
    main()
