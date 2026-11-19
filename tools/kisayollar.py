#!/usr/bin/env python3
"""Uygulama kısayollarının tek kaynağı.

Aynı kısayol üç yerde tanımlanmak zorunda: PWA manifesti, Android
`res/xml/shortcuts.xml` ve `strings.xml` etiketleri. Bunlar elle yazıldığında
sıra ve adlandırma kaçınılmaz olarak ayrışıyordu (manifest `bilet-al`, Android
`bilet_al`; manifest 11 kısayolu farklı sırayla sayıyordu). Bu betik listeyi
burada tutar ve üç dosyayı da buradan üretir.

Kullanım:
    python3 tools/kisayollar.py            # dosyaları yeniden yaz
    python3 tools/kisayollar.py --denetle  # yalnızca tutarlılığı denetle

Sıra `android:rank` olarak da yazılır. Çoğu başlatıcı en fazla 4-5 kısayol
gösterdiği için listenin başındakiler en çok kullanılanlardır.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANDROID_RES = os.path.join(ROOT, "android", "app", "src", "main", "res")
MANIFEST = os.path.join(ROOT, "manifest.json")
SHORTCUTS_XML = os.path.join(ANDROID_RES, "xml", "shortcuts.xml")
STRINGS_XML = os.path.join(ANDROID_RES, "values", "strings.xml")
SW_JS = os.path.join(ROOT, "sw.js")

# key: Genc.html içindeki runShortcut() kimliği (alt çizgi tireye çevrilir).
# android: kısayol kimliği; Android alt çizgi ister.
KISAYOLLAR = [
    {
        "key": "ara",
        "android": "ara",
        "pwa_name": "Etkinlik ara",
        "short": "Ara",
        "long": "Etkinlik ara",
        "desc": "Konser, sinema ve etkinlik ara",
        "icon": "shortcut-ara",
    },
    {
        "key": "biletlerim",
        "android": "biletlerim",
        "pwa_name": "Biletlerim",
        "short": "Biletlerim",
        "long": "Aldığın biletler",
        "desc": "Aldığın biletleri göster",
        "icon": "shortcut-biletlerim",
    },
    {
        "key": "yakin",
        "android": "yakin",
        "pwa_name": "Yakınımdaki etkinlikler",
        "short": "Yakınımda",
        "long": "Yakınımdaki etkinlikler",
        "desc": "Bulunduğun yere en yakın etkinlikler",
        "icon": "shortcut-yakin",
    },
    {
        "key": "hafta",
        "android": "hafta",
        "pwa_name": "Bu hafta ne var?",
        "short": "Bu hafta",
        "long": "Bu hafta ne var?",
        "desc": "Bu haftanın etkinliklerini paylaş",
        "icon": "shortcut-hafta",
    },
    {
        "key": "salonlar",
        "android": "salonlar",
        "pwa_name": "Salonlar",
        "short": "Salonlar",
        "long": "Salonların programı",
        "desc": "İl ve ilçe seç, salonların programını gör",
        "icon": "shortcut-salonlar",
    },
    {
        "key": "bilet-al",
        "android": "bilet_al",
        "pwa_name": "Bilet al",
        "short": "Bilet al",
        "long": "Sana yakın etkinliğe bilet al",
        "desc": "Sana en yakın etkinliğin biletini al",
        "icon": "shortcut-bilet-al",
    },
    {
        "key": "bildirimler",
        "android": "bildirimler",
        "pwa_name": "Bildirimler",
        "short": "Bildirimler",
        "long": "Bildirim ayarları",
        "desc": "Hangi etkinlikler için haber verilsin",
        "icon": "shortcut-bildirimler",
    },
    {
        "key": "hoslandiklarim",
        "android": "hoslandiklarim",
        "pwa_name": "Hoşlandıklarım",
        "short": "Hoşlandıklarım",
        "long": "Hoşlandığın kategoriler",
        "desc": "Sevdiğin kategorileri seç",
        "icon": "shortcut-hoslandiklarim",
    },
    {
        "key": "kaydedilenler",
        "android": "kaydedilenler",
        "pwa_name": "Kaydedilenler",
        "short": "Kaydedilenler",
        "long": "Kaydedilen etkinlikler",
        "desc": "Yer imine eklediğin etkinlikler",
        "icon": "shortcut-kaydedilenler",
    },
    {
        "key": "profil",
        "android": "profil",
        "pwa_name": "Profilim",
        "short": "Profil",
        "long": "Profilim",
        "desc": "Profilini ve biletlerini gör",
        "icon": "shortcut-profil",
    },
    {
        "key": "ayarlar",
        "android": "ayarlar",
        "pwa_name": "Ayarlar",
        "short": "Ayarlar",
        "long": "Uygulama ayarları",
        "desc": "Konum, bildirim ve görünüm ayarları",
        "icon": "shortcut-ayarlar",
    },
    {
        "key": "paylas",
        "android": "paylas",
        "pwa_name": "Genç’i paylaş",
        "short": "Paylaş",
        "long": "Genç’i paylaş",
        "desc": "Uygulama bağlantısını arkadaşlarınla paylaş",
        "icon": "shortcut-paylas",
    },
    {
        "key": "yardim",
        "android": "yardim",
        "pwa_name": "Yardım",
        "short": "Yardım",
        "long": "Sık sorulan sorular",
        "desc": "Bilet, fiyat ve hatırlatıcı sorularının yanıtları",
        "icon": "shortcut-yardim",
    },
]

BASE_URL = "https://appassets.androidplatform.net/assets/www/Genc.html"


def _manifest_block() -> list[dict]:
    return [
        {
            "name": k["pwa_name"],
            "short_name": k["short"],
            "description": k["desc"],
            "url": "./Genc.html?git=" + k["key"],
            "icons": [
                {
                    "src": "icons/" + k["icon"] + ".png",
                    "sizes": "192x192",
                    "type": "image/png",
                }
            ],
        }
        for k in KISAYOLLAR
    ]


def _shortcuts_xml() -> str:
    satirlar = [
        '<?xml version="1.0" encoding="utf-8"?>',
        "<!--",
        "  UZUN BASMA KISAYOLLARI — ELLE DÜZENLEMEYİN.",
        "",
        "  Bu dosya tools/kisayollar.py tarafından üretilir. Statik kısayollarda",
        "  sıra DOKÜMAN SIRASIDIR (XML'de android:rank yok); çoğu başlatıcı en",
        "  fazla 4-5 kısayol gösterdiği için ilk satırlar en çok kullanılanlardır.",
        "  Değişiklik için o betikteki KISAYOLLAR listesini düzenleyip betiği",
        "  yeniden çalıştırın.",
        "",
        "  Son bakılan etkinlik için dinamik kısayol Java tarafında",
        "  (MainActivity.installDynamicShortcut) eklenir ve rank 0 alır.",
        "-->",
        '<shortcuts xmlns:android="http://schemas.android.com/apk/res/android">',
        "",
    ]
    for rank, k in enumerate(KISAYOLLAR):
        satirlar += [
            "    <shortcut",
            '        android:shortcutId="%s"' % k["android"],
            '        android:enabled="true"',
            '        android:icon="@drawable/sc_%s"' % k["android"],
            '        android:shortcutShortLabel="@string/sc_%s"' % k["android"],
            '        android:shortcutLongLabel="@string/sc_%s_long"' % k["android"],
            "        >",
            "        <intent",
            '            android:action="android.intent.action.VIEW"',
            '            android:targetPackage="com.genc.app"',
            '            android:targetClass="com.genc.app.MainActivity"',
            '            android:data="%s?git=%s" />' % (BASE_URL, k["android"]),
            "    </shortcut>",
            "",
        ]
    satirlar.append("</shortcuts>")
    return "\n".join(satirlar) + "\n"


def _strings_block() -> str:
    satirlar = []
    for k in KISAYOLLAR:
        satirlar.append('    <string name="sc_%s">%s</string>' % (k["android"], k["short"]))
        satirlar.append('    <string name="sc_%s_long">%s</string>' % (k["android"], k["long"]))
    return "\n".join(satirlar) + "\n"


def _sw_asset_lines() -> list[str]:
    return ['  "./icons/%s.png",' % k["icon"] for k in KISAYOLLAR]


def uret() -> None:
    # manifest.json: yalnızca "shortcuts" anahtarı değişir, diğer alanlar korunur.
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    manifest["shortcuts"] = _manifest_block()
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(SHORTCUTS_XML, "w", encoding="utf-8") as f:
        f.write(_shortcuts_xml())

    # strings.xml: sc_* satırları yeniden yazılır, app_name gibi diğerleri kalır.
    mevcut = open(STRINGS_XML, encoding="utf-8").read()
    digerleri = [
        s for s in mevcut.splitlines()
        if "<string " in s and not re.search(r'name="sc_', s)
    ]
    with open(STRINGS_XML, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n')
        f.write("\n".join(digerleri) + "\n")
        f.write(_strings_block())
        f.write("</resources>\n")

    # sw.js: ASSETS listesindeki kısayol ikon satırları tek blokta toplanır.
    sw = open(SW_JS, encoding="utf-8").read()
    sw = re.sub(r'(?:\s*"\./icons/shortcut-[a-z-]+\.png",)+\n', "\n", sw)
    sw = sw.replace(
        '  "./icons/favicon-32.png",\n',
        '  "./icons/favicon-32.png",\n' + "\n".join(_sw_asset_lines()) + "\n",
    )
    with open(SW_JS, "w", encoding="utf-8") as f:
        f.write(sw)

    print("✓ manifest.json     : %d kısayol" % len(KISAYOLLAR))
    print("✓ shortcuts.xml     : %d kısayol (doküman sırası = gösterim sırası)"
          % len(KISAYOLLAR))
    print("✓ strings.xml       : %d etiket" % (len(KISAYOLLAR) * 2))
    print("✓ sw.js             : %d kısayol ikonu çevrimdışı" % len(KISAYOLLAR))


def denetle() -> int:
    """Üç tanımın aynı kümeyi aynı sırada saydığını doğrular."""
    hatalar = []

    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    pwa = [s["url"].split("git=")[1] for s in manifest.get("shortcuts", [])]
    beklenen = [k["key"] for k in KISAYOLLAR]
    if pwa != beklenen:
        hatalar.append("manifest.json sırası farklı: %s" % pwa)

    xml = open(SHORTCUTS_XML, encoding="utf-8").read()
    apk = re.findall(r'android:shortcutId="([a-z_]+)"', xml)
    beklenen_apk = [k["android"] for k in KISAYOLLAR]
    if apk != beklenen_apk:
        hatalar.append("shortcuts.xml sırası farklı: %s" % apk)
    if re.search(r'\sandroid:rank=', xml):
        hatalar.append("android:rank geçersiz bir öznitelik; sıra doküman sırasıyla verilir")

    strings = open(STRINGS_XML, encoding="utf-8").read()
    for k in KISAYOLLAR:
        for ad in ("sc_" + k["android"], "sc_" + k["android"] + "_long"):
            if 'name="%s"' % ad not in strings:
                hatalar.append("strings.xml eksik: %s" % ad)

    for k in KISAYOLLAR:
        yol = os.path.join(ROOT, "icons", k["icon"] + ".png")
        if not os.path.exists(yol):
            hatalar.append("PWA ikonu yok: %s" % yol)
        for dens in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
            yol = os.path.join(ANDROID_RES, "drawable-" + dens, "sc_%s.png" % k["android"])
            if not os.path.exists(yol):
                hatalar.append("Android ikonu yok: %s" % yol)

    sw = open(SW_JS, encoding="utf-8").read()
    for k in KISAYOLLAR:
        if k["icon"] + ".png" not in sw:
            hatalar.append("sw.js çevrimdışı listesinde yok: %s" % k["icon"])

    # runShortcut() her anahtarı tanımalı; yoksa kısayol sessizce ölü kalır.
    genc = open(os.path.join(ROOT, "Genc.html"), encoding="utf-8").read()
    for k in KISAYOLLAR:
        if "git==='%s'" % k["key"] not in genc:
            hatalar.append("runShortcut() tanımıyor: %s" % k["key"])

    if hatalar:
        print("✗ kısayol denetimi başarısız:")
        for h in hatalar:
            print("  -", h)
        return 1
    print("✓ kısayol denetimi geçti: %d kısayol, üç tanım aynı sırada" % len(KISAYOLLAR))
    return 0


if __name__ == "__main__":
    if "--denetle" in sys.argv:
        sys.exit(denetle())
    uret()
