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
import datetime
import hashlib
import html as html_lib
import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
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
MONTHS_TR_FULL = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
                  "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


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


_TR_FOLD = str.maketrans({
    "ı": "i", "İ": "i", "I": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
    "â": "a", "Â": "a", "î": "i", "Î": "i", "û": "u", "Û": "u",
})


# İl başına resmî ilçe listesi (kaynak: Genc.html içindeki TR_CITY_DISTRICTS).
# Yalnızca ilgili ilin ilçeleri aranır: aksi hâlde "Çeşme" gibi bir İzmir ilçesi
# İstanbul'daki "Kazlıçeşme" sokak adında eşleşip yanlış ilçe yazıyordu.
KNOWN_DISTRICTS = {
    "Adana": ("Aladağ", "Ceyhan", "Feke", "Karaisalı", "Karataş", "Kozan", "Pozantı", "Saimbeyli", "Sarıçam", "Seyhan", "Tufanbeyli", "Yumurtalık", "Yüreğir", "Çukurova", "İmamoğlu"),
    "Adıyaman": ("Besni", "Gerger", "Gölbaşı", "Kahta", "Merkez", "Samsat", "Sincik", "Tut", "Çelikhan"),
    "Afyonkarahisar": ("Bayat", "Başmakçı", "Bolvadin", "Dazkırı", "Dinar", "Emirdağ", "Evciler", "Hocalar", "Kızılören", "Merkez", "Sandıklı", "Sinanpaşa", "Sultandağı", "Çay", "Çobanlar", "İhsaniye", "İscehisar", "Şuhut"),
    "Aksaray": ("Ağaçören", "Eskil", "Gülağaç", "Güzelyurt", "Merkez", "Ortaköy", "Sarıyahşi", "Sultanhanı"),
    "Amasya": ("Göynücek", "Gümüşhacıköy", "Hamamözü", "Merkez", "Merzifon", "Suluova", "Taşova"),
    "Ankara": ("Akyurt", "Altındağ", "Ayaş", "Bala", "Beypazarı", "Elmadağ", "Etimesgut", "Evren", "Gölbaşı", "Güdül", "Haymana", "Kahramankazan", "Kalecik", "Keçiören", "Kızılcahamam", "Mamak", "Nallıhan", "Polatlı", "Pursaklar", "Sincan", "Yenimahalle", "Çamlıdere", "Çankaya", "Çubuk", "Şereflikoçhisar"),
    "Antalya": ("Akseki", "Aksu", "Alanya", "Demre", "Döşemealtı", "Elmalı", "Finike", "Gazipaşa", "Gündoğmuş", "Kaş", "Kemer", "Kepez", "Konyaaltı", "Korkuteli", "Kumluca", "Manavgat", "Muratpaşa", "Serik", "İbradı"),
    "Ardahan": ("Damal", "Göle", "Hanak", "Merkez", "Posof", "Çıldır"),
    "Artvin": ("Ardanuç", "Arhavi", "Borçka", "Hopa", "Kemalpaşa", "Merkez", "Murgul", "Yusufeli", "Şavşat"),
    "Aydın": ("Bozdoğan", "Buharkent", "Didim", "Efeler", "Germencik", "Karacasu", "Karpuzlu", "Koçarlı", "Kuyucak", "Kuşadası", "Köşk", "Nazilli", "Sultanhisar", "Söke", "Yenipazar", "Çine", "İncirliova"),
    "Ağrı": ("Diyadin", "Doğubayazıt", "Eleşkirt", "Hamur", "Merkez", "Patnos", "Taşlıçay", "Tutak"),
    "Balıkesir": ("Altıeylül", "Ayvalık", "Balya", "Bandırma", "Bigadiç", "Burhaniye", "Dursunbey", "Edremit", "Erdek", "Gömeç", "Gönen", "Havran", "Karesi", "Kepsut", "Manyas", "Marmara", "Savaştepe", "Susurluk", "Sındırgı", "İvrindi"),
    "Bartın": ("Amasra", "Kurucaşile", "Merkez", "Ulus"),
    "Batman": ("Beşiri", "Gercüş", "Hasankeyf", "Kozluk", "Merkez", "Sason"),
    "Bayburt": ("Aydıntepe", "Demirözü", "Merkez"),
    "Bilecik": ("Bozüyük", "Gölpazarı", "Merkez", "Osmaneli", "Pazaryeri", "Söğüt", "Yenipazar", "İnhisar"),
    "Bingöl": ("Adaklı", "Genç", "Karlıova", "Kiğı", "Merkez", "Solhan", "Yayladere", "Yedisu"),
    "Bitlis": ("Adilcevaz", "Ahlat", "Güroymak", "Hizan", "Merkez", "Mutki", "Tatvan"),
    "Bolu": ("Dörtdivan", "Gerede", "Göynük", "Kıbrıscık", "Mengen", "Merkez", "Mudurnu", "Seben", "Yeniçağa"),
    "Burdur": ("Altınyayla", "Ağlasun", "Bucak", "Gölhisar", "Karamanlı", "Kemer", "Merkez", "Tefenni", "Yeşilova", "Çavdır", "Çeltikçi"),
    "Bursa": ("Büyükorhan", "Gemlik", "Gürsu", "Harmancık", "Karacabey", "Keles", "Kestel", "Mudanya", "Mustafakemalpaşa", "Nilüfer", "Orhaneli", "Orhangazi", "Osmangazi", "Yenişehir", "Yıldırım", "İnegöl", "İznik"),
    "Denizli": ("Acıpayam", "Babadağ", "Baklan", "Bekilli", "Beyağaç", "Bozkurt", "Buldan", "Güney", "Honaz", "Kale", "Merkezefendi", "Pamukkale", "Sarayköy", "Serinhisar", "Tavas", "Çal", "Çameli", "Çardak", "Çivril"),
    "Diyarbakır": ("Bağlar", "Bismil", "Dicle", "Ergani", "Eğil", "Hani", "Hazro", "Kayapınar", "Kocaköy", "Kulp", "Lice", "Silvan", "Sur", "Yenişehir", "Çermik", "Çüngüş", "Çınar"),
    "Düzce": ("Akçakoca", "Cumayeri", "Gölyaka", "Gümüşova", "Kaynaşlı", "Merkez", "Yığılca", "Çilimli"),
    "Edirne": ("Enez", "Havsa", "Keşan", "Lalapaşa", "Meriç", "Merkez", "Süloğlu", "Uzunköprü", "İpsala"),
    "Elazığ": ("Alacakaya", "Arıcak", "Ağın", "Baskil", "Karakoçan", "Keban", "Kovancılar", "Maden", "Merkez", "Palu", "Sivrice"),
    "Erzincan": ("Kemah", "Kemaliye", "Merkez", "Otlukbeli", "Refahiye", "Tercan", "Çayırlı", "Üzümlü", "İliç"),
    "Erzurum": ("Aziziye", "Aşkale", "Horasan", "Hınıs", "Karayazı", "Karaçoban", "Köprüköy", "Narman", "Oltu", "Olur", "Palandöken", "Pasinler", "Pazaryolu", "Tekman", "Tortum", "Uzundere", "Yakutiye", "Çat", "İspir", "Şenkaya"),
    "Eskişehir": ("Alpu", "Beylikova", "Günyüzü", "Han", "Mahmudiye", "Mihalgazi", "Mihalıççık", "Odunpazarı", "Sarıcakaya", "Seyitgazi", "Sivrihisar", "Tepebaşı", "Çifteler", "İnönü"),
    "Gaziantep": ("Araban", "Karkamış", "Nizip", "Nurdağı", "Oğuzeli", "Yavuzeli", "İslahiye", "Şahinbey", "Şehitkamil"),
    "Giresun": ("Alucra", "Bulancak", "Dereli", "Doğankent", "Espiye", "Eynesil", "Görele", "Güce", "Keşap", "Merkez", "Piraziz", "Tirebolu", "Yağlıdere", "Çamoluk", "Çanakçı", "Şebinkarahisar"),
    "Gümüşhane": ("Kelkit", "Köse", "Kürtün", "Merkez", "Torul", "Şiran"),
    "Hakkari": ("Derecik", "Merkez", "Yüksekova", "Çukurca", "Şemdinli"),
    "Hatay": ("Altınözü", "Antakya", "Arsuz", "Belen", "Defne", "Dörtyol", "Erzin", "Hassa", "Kumlu", "Kırıkhan", "Payas", "Reyhanlı", "Samandağ", "Yayladağı", "İskenderun"),
    "Isparta": ("Aksu", "Atabey", "Eğirdir", "Gelendost", "Gönen", "Keçiborlu", "Merkez", "Senirkent", "Sütçüler", "Uluborlu", "Yalvaç", "Yenişarbademli", "Şarkikaraağaç"),
    "Iğdır": ("Aralık", "Karakoyunlu", "Merkez", "Tuzluca"),
    "Kahramanmaraş": ("Afşin", "Andırın", "Dulkadiroğlu", "Ekinözü", "Elbistan", "Göksun", "Nurhak", "Onikişubat", "Pazarcık", "Türkoğlu", "Çağlayancerit"),
    "Karabük": ("Eflani", "Eskipazar", "Merkez", "Ovacık", "Safranbolu", "Yenice"),
    "Karaman": ("Ayrancı", "Başyayla", "Ermenek", "Kazımkarabekir", "Merkez", "Sarıveliler"),
    "Kars": ("Akyaka", "Arpaçay", "Digor", "Kağızman", "Merkez", "Sarıkamış", "Selim", "Susuz"),
    "Kastamonu": ("Abana", "Araç", "Azdavay", "Ağlı", "Bozkurt", "Cide", "Daday", "Devrekani", "Doğanyurt", "Hanönü", "Küre", "Merkez", "Pınarbaşı", "Seydiler", "Taşköprü", "Tosya", "Çatalzeytin", "İhsangazi", "İnebolu", "Şenpazar"),
    "Kayseri": ("Akkışla", "Bünyan", "Develi", "Felahiye", "Hacılar", "Kocasinan", "Melikgazi", "Pınarbaşı", "Sarıoğlan", "Sarız", "Talas", "Tomarza", "Yahyalı", "Yeşilhisar", "Özvatan", "İncesu"),
    "Kilis": ("Elbeyli", "Merkez", "Musabeyli", "Polateli"),
    "Kocaeli": ("Başiskele", "Darıca", "Derince", "Dilovası", "Gebze", "Gölcük", "Kandıra", "Karamürsel", "Kartepe", "Körfez", "Çayırova", "İzmit"),
    "Konya": ("Ahırlı", "Akören", "Akşehir", "Altınekin", "Beyşehir", "Bozkır", "Cihanbeyli", "Derbent", "Derebucak", "Doğanhisar", "Emirgazi", "Ereğli", "Güneysınır", "Hadim", "Halkapınar", "Hüyük", "Ilgın", "Kadınhanı", "Karapınar", "Karatay", "Kulu", "Meram", "Sarayönü", "Selçuklu", "Seydişehir", "Taşkent", "Tuzlukçu", "Yalıhüyük", "Yunak", "Çeltik", "Çumra"),
    "Kütahya": ("Altıntaş", "Aslanapa", "Domaniç", "Dumlupınar", "Emet", "Gediz", "Hisarcık", "Merkez", "Pazarlar", "Simav", "Tavşanlı", "Çavdarhisar", "Şaphane"),
    "Kırklareli": ("Babaeski", "Demirköy", "Kofçaz", "Lüleburgaz", "Merkez", "Pehlivanköy", "Pınarhisar", "Vize"),
    "Kırıkkale": ("Bahşılı", "Balışeyh", "Delice", "Karakeçili", "Keskin", "Merkez", "Sulakyurt", "Yahşihan", "Çelebi"),
    "Kırşehir": ("Akpınar", "Akçakent", "Boztepe", "Kaman", "Merkez", "Mucur", "Çiçekdağı"),
    "Malatya": ("Akçadağ", "Arapgir", "Arguvan", "Battalgazi", "Darende", "Doğanyol", "Doğanşehir", "Hekimhan", "Kale", "Kuluncak", "Pütürge", "Yazıhan", "Yeşilyurt"),
    "Manisa": ("Ahmetli", "Akhisar", "Alaşehir", "Demirci", "Gölmarmara", "Gördes", "Kula", "Köprübaşı", "Kırkağaç", "Salihli", "Saruhanlı", "Sarıgöl", "Selendi", "Soma", "Turgutlu", "Yunusemre", "Şehzadeler"),
    "Mardin": ("Artuklu", "Dargeçit", "Derik", "Kızıltepe", "Mazıdağı", "Midyat", "Nusaybin", "Savur", "Yeşilli", "Ömerli"),
    "Mersin": ("Akdeniz", "Anamur", "Aydıncık", "Bozyazı", "Erdemli", "Gülnar", "Mezitli", "Mut", "Silifke", "Tarsus", "Toroslar", "Yenişehir", "Çamlıyayla"),
    "Muğla": ("Bodrum", "Dalaman", "Datça", "Fethiye", "Kavaklıdere", "Köyceğiz", "Marmaris", "Menteşe", "Milas", "Ortaca", "Seydikemer", "Ula", "Yatağan"),
    "Muş": ("Bulanık", "Hasköy", "Korkut", "Malazgirt", "Merkez", "Varto"),
    "Nevşehir": ("Acıgöl", "Avanos", "Derinkuyu", "Gülşehir", "Hacıbektaş", "Kozaklı", "Merkez", "Ürgüp"),
    "Niğde": ("Altunhisar", "Bor", "Merkez", "Ulukışla", "Çamardı", "Çiftlik"),
    "Ordu": ("Akkuş", "Altınordu", "Aybastı", "Fatsa", "Gölköy", "Gülyalı", "Gürgentepe", "Kabadüz", "Kabataş", "Korgan", "Kumru", "Mesudiye", "Perşembe", "Ulubey", "Çamaş", "Çatalpınar", "Çaybaşı", "Ünye", "İkizce"),
    "Osmaniye": ("Bahçe", "Düziçi", "Hasanbeyli", "Kadirli", "Merkez", "Sumbas", "Toprakkale"),
    "Rize": ("Ardeşen", "Derepazarı", "Fındıklı", "Güneysu", "Hemşin", "Kalkandere", "Merkez", "Pazar", "Çamlıhemşin", "Çayeli", "İkizdere", "İyidere"),
    "Sakarya": ("Adapazarı", "Akyazı", "Arifiye", "Erenler", "Ferizli", "Geyve", "Hendek", "Karapürçek", "Karasu", "Kaynarca", "Kocaali", "Pamukova", "Sapanca", "Serdivan", "Söğütlü", "Taraklı"),
    "Samsun": ("19 mayıs", "Alaçam", "Asarcık", "Atakum", "Ayvacık", "Bafra", "Canik", "Havza", "Kavak", "Ladik", "Salıpazarı", "Tekkeköy", "Terme", "Vezirköprü", "Yakakent", "Çarşamba", "İlkadım"),
    "Siirt": ("Baykan", "Eruh", "Kurtalan", "Merkez", "Pervari", "Tillo", "Şirvan"),
    "Sinop": ("Ayancık", "Boyabat", "Dikmen", "Durağan", "Erfelek", "Gerze", "Merkez", "Saraydüzü", "Türkeli"),
    "Sivas": ("Akıncılar", "Altınyayla", "Divriği", "Doğanşar", "Gemerek", "Gölova", "Gürün", "Hafik", "Kangal", "Koyulhisar", "Merkez", "Suşehri", "Ulaş", "Yıldızeli", "Zara", "İmranlı", "Şarkışla"),
    "Tekirdağ": ("Ergene", "Hayrabolu", "Kapaklı", "Malkara", "Marmaraereğlisi", "Muratlı", "Saray", "Süleymanpaşa", "Çerkezköy", "Çorlu", "Şarköy"),
    "Tokat": ("Almus", "Artova", "Başçiftlik", "Erbaa", "Merkez", "Niksar", "Pazar", "Reşadiye", "Sulusaray", "Turhal", "Yeşilyurt", "Zile"),
    "Trabzon": ("Akçaabat", "Araklı", "Arsin", "Beşikdüzü", "Dernekpazarı", "Düzköy", "Hayrat", "Köprübaşı", "Maçka", "Of", "Ortahisar", "Sürmene", "Tonya", "Vakfıkebir", "Yomra", "Çarşıbaşı", "Çaykara", "Şalpazarı"),
    "Tunceli": ("Hozat", "Mazgirt", "Merkez", "Nazımiye", "Ovacık", "Pertek", "Pülümür", "Çemişgezek"),
    "Uşak": ("Banaz", "Eşme", "Karahallı", "Merkez", "Sivaslı", "Ulubey"),
    "Van": ("Bahçesaray", "Başkale", "Edremit", "Erciş", "Gevaş", "Gürpınar", "Muradiye", "Saray", "Tuşba", "Çaldıran", "Çatak", "Özalp", "İpekyolu"),
    "Yalova": ("Altınova", "Armutlu", "Merkez", "Termal", "Çiftlikköy", "Çınarcık"),
    "Yozgat": ("Akdağmadeni", "Aydıncık", "Boğazlıyan", "Kadışehri", "Merkez", "Saraykent", "Sarıkaya", "Sorgun", "Yenifakılı", "Yerköy", "Çandır", "Çayıralan", "Çekerek", "Şefaatli"),
    "Zonguldak": ("Alaplı", "Devrek", "Ereğli", "Gökçebey", "Kilimli", "Kozlu", "Merkez", "Çaycuma"),
    "Çanakkale": ("Ayvacık", "Bayramiç", "Biga", "Bozcaada", "Eceabat", "Ezine", "Gelibolu", "Gökçeada", "Lapseki", "Merkez", "Yenice", "Çan"),
    "Çankırı": ("Atkaracalar", "Bayramören", "Eldivan", "Ilgaz", "Korgun", "Kurşunlu", "Kızılırmak", "Merkez", "Orta", "Yapraklı", "Çerkeş", "Şabanözü"),
    "Çorum": ("Alaca", "Bayat", "Boğazkale", "Dodurga", "Kargı", "Laçin", "Mecitözü", "Merkez", "Ortaköy", "Osmancık", "Oğuzlar", "Sungurlu", "Uğurludağ", "İskilip"),
    "İstanbul": ("Adalar", "Arnavutköy", "Ataşehir", "Avcılar", "Bahçelievler", "Bakırköy", "Bayrampaşa", "Bağcılar", "Başakşehir", "Beykoz", "Beylikdüzü", "Beyoğlu", "Beşiktaş", "Büyükçekmece", "Esenler", "Esenyurt", "Eyüpsultan", "Fatih", "Gaziosmanpaşa", "Güngören", "Kadıköy", "Kartal", "Kağıthane", "Küçükçekmece", "Maltepe", "Pendik", "Sancaktepe", "Sarıyer", "Silivri", "Sultanbeyli", "Sultangazi", "Tuzla", "Zeytinburnu", "Çatalca", "Çekmeköy", "Ümraniye", "Üsküdar", "Şile", "Şişli"),
    "İzmir": ("Aliağa", "Balçova", "Bayraklı", "Bayındır", "Bergama", "Beydağ", "Bornova", "Buca", "Dikili", "Foça", "Gaziemir", "Güzelbahçe", "Karabağlar", "Karaburun", "Karşıyaka", "Kemalpaşa", "Kiraz", "Konak", "Kınık", "Menderes", "Menemen", "Narlıdere", "Seferihisar", "Selçuk", "Tire", "Torbalı", "Urla", "Çeşme", "Çiğli", "Ödemiş"),
    "Şanlıurfa": ("Akçakale", "Birecik", "Bozova", "Ceylanpınar", "Eyyübiye", "Halfeti", "Haliliye", "Harran", "Hilvan", "Karaköprü", "Siverek", "Suruç", "Viranşehir"),
    "Şırnak": ("Beytüşşebap", "Cizre", "Güçlükonak", "Merkez", "Silopi", "Uludere", "İdil"),
}


def norm(text: str) -> str:
    """Arama/eşleştirme için Türkçe harfleri ASCII karşılığına indirger.

    NFKD tek başına yetmez: "ı" ve "ğ" ayrışmadığı için "Kadıköy" -> "kad koy"
    gibi bozuk sonuç verir. Bu yüzden önce harf çevirisi yapılır.
    """
    text = (text or "").translate(_TR_FOLD)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


# Kaynak sitelerin metinlerinde görünmez dolgu karakterleri (Hangul filler,
# sıfır genişlikli boşluk) ve kırılmaz boşluk bulunabilir; bunlar başlık/mekan
# adlarında bozuk görünüme yol açar, bu yüzden kayıttan önce ayıklanır.
_INVISIBLE = dict.fromkeys(
    [0x3164, 0xFEFF, 0x2060, *range(0x200B, 0x2010)], None
)


def clean_text(text: str) -> str:
    text = (text or "").translate(_INVISIBLE).replace("\u00a0", " ")
    return re.sub(r"\s{2,}", " ", text).strip()


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

    Önce ilin bilinen ilçeleri, sonra adresteki "X/İl" kalıbı, en son olarak
    adres sonundaki ilçe benzeri sözcük denenir. Bulunamazsa şehir adı döner.
    """
    for known in KNOWN_DISTRICTS.get(city, ()):
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
            street = clean_text(addr.get("streetAddress") or "")
            venue = clean_text(loc.get("name") or "")
            title = clean_text(node.get("name") or "")
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


BILETINIAL_API = "https://biletinial.com/List/GetMoreItems"
# organizerUrl -> uygulamanın tür adı. Site bu yolu kategori kimliği olarak kullanır.
BILETINIAL_CATS = [
    ("muzik", "Konser"),
    ("tiyatro", "Tiyatro"),
    ("opera-bale", "Opera ve bale"),
    ("sinema", "Sinema"),
    ("stand-up", "Stand-up"),
    ("spor", "Spor"),
    ("cocuk", "Çocuk etkinlikleri"),
]
BILETINIAL_MAX_PAGES = 30


def _biletinial_slug(city: str) -> str:
    """İl adını sitenin cityUrl biçimine çevirir (ı->i, ş->s, ğ->g ...)."""
    table = {"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
             "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c"}
    return "".join(table.get(ch, ch) for ch in city).lower().replace(" ", "")


def _biletinial_page(city_url: str, cat: str, page: int) -> list[dict]:
    params = urllib.parse.urlencode({
        "region": "tr-tr", "cityId": "", "cityUrl": city_url, "order": 0,
        "isKids": "false", "isCampaign": "false", "isForeign": "false",
        "organizerUrl": cat, "page": page,
    })
    return _get_json(f"{BILETINIAL_API}?{params}").get("items") or []


def _biletinial_city(city: str) -> list[tuple[str, str]]:
    """Bir ilin tüm kategorilerindeki etkinlikleri (detay linki, tür) olarak toplar."""
    city_url = _biletinial_slug(city)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for cat, genre in BILETINIAL_CATS:
        for page in range(1, BILETINIAL_MAX_PAGES + 1):
            try:
                items = _biletinial_page(city_url, cat, page)
            except Exception:
                break
            fresh = [i for i in items if i.get("seoUrl") and i["seoUrl"] not in seen]
            if not fresh:
                break
            for item in fresh:
                seen.add(item["seoUrl"])
                out.append((f"https://biletinial.com/tr-tr/{cat}/{item['seoUrl']}", genre))
    return out


def collect_biletinial(limit: int) -> list[dict]:
    targets: list[tuple[str, str]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for links in pool.map(_biletinial_city, TR_CITIES):
            targets.extend(links)
    cities = len({link for link, _ in targets})
    print(f"  Biletinial: {len(targets)} etkinlik bağlantısı ({cities} il)")
    if limit:
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
    cands = [e for e in listing.get("valueList", []) if e.get("seoUrl") and e.get("id")]
    print(f"  Passo: {len(cands)} aday (toplam {listing.get('totalItemCount')})")
    events: list[dict] = []
    for e in (cands[:limit] if limit else cands):
        try:
            v = _get_json(f"{PASSO_API}/geteventdetails/{e['seoUrl']}/{e['id']}/118").get("value") or {}
        except Exception:
            continue
        cats = [c for c in (v.get("categories") or []) if c.get("price") is not None]
        price = v.get("lowPrice")
        if price is None and cats:
            price = min(c["price"] for c in cats)
        start = (v.get("date") or "").replace(" ", "T")
        when, wd, date = when_label(start)
        genre = passo_type(v.get("genreName", ""), v.get("name", ""))
        title = clean_text(v.get("name") or "")
        venue = clean_text(v.get("venueName") or "")
        if not title or not date:
            continue
        eid = f"{slug(title)[:40]}-{date}-{hashlib.sha1(norm(venue).encode()).hexdigest()[:5]}"
        district = clean_text(v.get("venueCounty") or "")
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


# Türkiye'nin 81 ili. Biletino'nun arama ucu il adını `city` parametresiyle
# kabul eder; her il için tüm sayfalar gezilir.
TR_CITIES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara",
    "Antalya", "Ardahan", "Artvin", "Aydın", "Balıkesir", "Bartın", "Batman",
    "Bayburt", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa",
    "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Düzce", "Edirne",
    "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun",
    "Gümüşhane", "Hakkâri", "Hatay", "Iğdır", "Isparta", "İstanbul", "İzmir",
    "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri",
    "Kırıkkale", "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", "Konya",
    "Kütahya", "Malatya", "Manisa", "Mardin", "Muğla", "Muş", "Nevşehir",
    "Niğde", "Ordu", "Osmaniye", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop",
    "Sivas", "Şanlıurfa", "Şırnak", "Tekirdağ", "Tokat", "Trabzon", "Tunceli",
    "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak",
]

BILETINO_SEARCH = "https://biletino.com/tr/search/"
BILETINO_PAGE = 24
BILETINO_MAX_PAGES = 12


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


# Kaynakların kullandığı kısa/alternatif il adları.
CITY_ALIASES = {
    "afyon": "Afyonkarahisar",
    "afyonkarahisar": "Afyonkarahisar",
    "icel": "Mersin",
    "i̇stanbul": "İstanbul",
    "kibris": "Kıbrıs",
    "kktc": "Kıbrıs",
    "maras": "Kahramanmaraş",
    "urfa": "Şanlıurfa",
    "antep": "Gaziantep",
}


def norm_city(city: str) -> str:
    """Kaynakların şehir adını uygulamanın il adına indirger.

    Biletinial İstanbul'u "İstanbul Avrupa"/"İstanbul Anadolu" diye ikiye
    böler; uygulama İstanbul'u tek il olarak kullanır. Bazı kaynaklar ilin
    eski/kısa adını yazar ("Afyon", "İçel", "Urfa").
    """
    c = (city or "").strip()
    if not c:
        return ""
    if c.startswith("İstanbul") or c.startswith("Istanbul"):
        return "İstanbul"
    key = norm(c).replace(" ", "")
    return CITY_ALIASES.get(key, c)


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
            title = clean_text(node.get("name") or "")
            venue = clean_text(loc.get("name") or "")
            if not title or not date or not venue:
                continue
            desc = (node.get("description") or "").strip()
            city = (addr.get("addressRegion") or addr.get("addressLocality") or "").strip()
            city = norm_city(city)
            street = clean_text(addr.get("streetAddress") or "")
            district = clean_text(addr.get("addressLocality") or "") or district_of(venue, street, city)
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


def _biletino_page(city: str, start: int) -> set[str]:
    """Tek sayfa sonucundaki etkinlik bağlantılarını döndürür."""
    params = urllib.parse.urlencode({
        "city": city,
        "ajax": "true",
        "autochange": "true",
        "start": start,
        "count": BILETINO_PAGE,
        "loadmore": "true" if start else "false",
    })
    html_text = fetch(f"{BILETINO_SEARCH}?{params}")
    return set(re.findall(r'href="(/tr/e-[^"]+?)"', html_text))


def _biletino_city_links(city: str) -> list[str]:
    """Bir ilin tüm etkinlik bağlantılarını sayfa sayfa toplar."""
    seen: set[str] = set()
    for page in range(BILETINO_MAX_PAGES):
        try:
            found = _biletino_page(city, page * BILETINO_PAGE)
        except Exception as exc:
            if page == 0:
                print(f"  ! Biletino il alınamadı: {city} ({exc})")
            break
        fresh = found - seen
        if not fresh:
            break
        seen |= found
    return sorted(seen)


def collect_biletino(limit: int) -> list[dict]:
    """Biletino: 81 ilin tamamı, halka açık JSON-LD (schema.org Event + Offer)."""
    by_city: dict[str, list[str]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for city, links in zip(TR_CITIES, pool.map(_biletino_city_links, TR_CITIES)):
            if links:
                by_city[city] = links
    targets: dict[str, str] = {}
    for city in sorted(by_city):
        for path in by_city[city]:
            targets.setdefault("https://biletino.com" + path, "")
    print(f"  Biletino: {len(by_city)} il, {len(targets)} etkinlik bağlantısı")
    items = list(targets.keys())
    if limit:
        items = items[:limit]

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


# --- Biletimgo -------------------------------------------------------------
# Site sunucu tarafında şehir sayfalarını kart listesiyle verir; her kartta
# başlık, mekan, tarih ve görsel bulunur (fiyat yalnızca JS ile yüklenir, bu
# yüzden alınmaz). Şehir sayfası adresi: /sehir-etkinlikleri/<slug>
BILETIMGO_BASE = "https://www.biletimgo.com"
BILETIMGO_SITEMAP = BILETIMGO_BASE + "/sitemap.xml"


def _biletimgo_slug(city: str) -> str:
    table = {"ı": "i", "İ": "i", "ş": "s", "Ş": "s", "ğ": "g", "Ğ": "g",
             "ü": "u", "Ü": "u", "ö": "o", "Ö": "o", "ç": "c", "Ç": "c",
             "â": "a", "Â": "a", "î": "i", "Î": "i", "û": "u", "Û": "u"}
    name = "".join(table.get(ch, ch) for ch in city).lower()
    return "".join(ch if ch.isalnum() else "-" for ch in name).strip("-")


_MONTHS_TR = {"Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5,
              "Haziran": 6, "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10,
              "Kasım": 11, "Aralık": 12}


def _biletimgo_city_page(city: str) -> list[dict]:
    """Bir ilin etkinlik kartlarını ayrıştırır."""
    url = f"{BILETIMGO_BASE}/sehir-etkinlikleri/{_biletimgo_slug(city)}"
    try:
        html_text = fetch(url)
    except Exception as exc:
        print(f"  ! Biletimgo {city}: {exc}")
        return []
    out: list[dict] = []
    # Her kart: <li data-etkinlikadi="..."> ... tarih ... <a href="../../etkinlik/slug-id">
    for block in re.findall(r'<li[^>]*data-etkinlikadi="([^"]*)"(.*?)</li>', html_text, re.S):
        title_raw, body = block
        link = re.search(r'href="[^"]*?(/etkinlik/[^"]+|\.\./\.\./etkinlik/[^"]+)"', body)
        if not link:
            continue
        href = link.group(1).replace("../../", "/")
        title = clean_text(html_lib.unescape(html_lib.unescape(title_raw)))
        venue = re.search(r'<span>([^<]+)</span>', body)
        venue_name = clean_text(html_lib.unescape(html_lib.unescape(venue.group(1)))) if venue else ""
        day = re.search(r'<span class="day">(\d{1,2})</span>', body)
        month = re.search(r'<span class="month">([^<]+)</span>', body)
        year = re.search(r'<span class="year">(\d{4})</span>', body)
        date = ""
        if day and month and year and month.group(1) in _MONTHS_TR:
            date = f"{year.group(1)}-{_MONTHS_TR[month.group(1)]:02d}-{int(day.group(1)):02d}"
        img = re.search(r'data-src="([^"]+)"', body)
        image = ""
        if img:
            image = img.group(1).replace("../../", BILETIMGO_BASE + "/")
        if not title:
            continue
        # Kart görünümünde saat yok; gün adı tarihten türetilir ki arayüzde
        # "undefined" görünmesin (diğer kaynaklar bu alanı dolduruyor).
        wd, when = "", ""
        if date:
            try:
                gun = datetime.date.fromisoformat(date)
                wd = WD[gun.weekday()]
                when = f"{wd} {gun.day} {MONTHS_TR_FULL[gun.month - 1]}"
            except ValueError:
                pass
        tur = _tur(title)
        out.append({
            "id": f"{slug(title)[:40]}-{date}-{hashlib.sha1(norm(venue_name).encode()).hexdigest()[:5]}",
            "type": tur,
            "art": ART_BY_TYPE.get(tur, "art-festival"),
            "title": title,
            "venue": venue_name,
            "city": city,
            "district": "",
            "date": date,
            "start": f"{date}T00:00:00" if date else "",
            "when": when,
            "wd": wd,
            "image": image,
            "price": None,
            "source": "Biletimgo",
            "url": BILETIMGO_BASE + href,
        })
    # Fiyat yalnızca detay sayfasında yazılı; kart sayısı kadar istek atıldığı
    # için il içinde paralel çekilir, yoksa toplama saatler sürer.
    if out:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            fiyatlar = list(pool.map(
                lambda e: _biletimgo_fiyat(e["url"][len(BILETIMGO_BASE):]), out))
        for kayit, fiyat in zip(out, fiyatlar):
            kayit["price"] = fiyat
    return out


def _biletimgo_fiyat(href: str) -> float | None:
    """Etkinlik detay sayfasından en düşük bilet fiyatını okur.

    Kart görünümünde fiyat yok; detay sayfasındaki "biletfiyatg"
    alanları (Tek kişi / Çift kişilik) tek tek okunup en düşüğü alınır.
    """
    try:
        html_text = fetch(BILETIMGO_BASE + href)
    except Exception:
        return None
    fiyatlar = []
    for ham in re.findall(r'biletfiyatg">\s*([\d.,]+)', html_text):
        try:
            fiyatlar.append(float(ham.replace(".", "").replace(",", ".")))
        except ValueError:
            continue
    return min(fiyatlar) if fiyatlar else None


def collect_biletimgo(limit: int) -> list[dict]:
    """Biletimgo: 81 ilin şehir sayfaları; kart düzeyinde başlık/mekan/tarih."""
    events: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for city, found in zip(TR_CITIES, pool.map(_biletimgo_city_page, TR_CITIES)):
            if found:
                events.extend(found)
    print(f"  Biletimgo: {len(events)} kart")
    if limit:
        events = events[:limit]
    return events



# Yeni kaynak eklemek için: (ad, toplayıcı fonksiyonu)
SOURCES = [
    ("Biletinial", collect_biletinial),
    ("Passo", collect_passo),
    ("Biletino", collect_biletino),
    ("Biletimgo", collect_biletimgo),
]


def key_of(ev: dict) -> str:
    """Aynı etkinliği farklı kaynaklarda eşleştirmek için anahtar.

    Kaynaklar aynı etkinliği farklı yazımla verir ("Kadıköy" / "Kadikoy",
    "Tiyatro Şamata" / "Tiyatro Samata - İnteraktif"). Bu yüzden anahtar
    başlık+mekan+tarih üzerinden normalize edilmiş sözcük kümesiyle kurulur.
    """
    return f"{_title_key(ev['title'])}|{_venue_key(ev.get('venue',''))}|{ev.get('date','')}"


_STOP = {"the", "ve", "ile", "bir", "de", "da", "in", "icin", "gosteri",
         "gosterimi", "etkinligi", "gecesi", "ozel", "turkiye", "istanbul"}


def _tokens(text: str) -> set[str]:
    words = [w for w in norm(text).split() if len(w) > 2 and w not in _STOP]
    return set(words)


def _title_key(title: str) -> str:
    """Başlığın ayırt edici sözcükleri; sıralamadan bağımsız."""
    words = sorted(_tokens(title))
    return " ".join(words[:8]) if words else norm(title)


# Mekan adlarında ayırt ediciliği olmayan sözcükler. Kaynaklar aynı salonu
# "Atilla Koç Kültür Merkezi" / "Atilla KM" gibi yazıyor; bu sözcükler
# eşleştirmede gürültü üretiyor, ayırt edici adlar (kişi/yer adları) kalıyor.
_VENUE_STOP = frozenset("""
salon salonu sahne sahnesi merkez merkezi kultur kültür sanat tiyatro tiyatrosu
gosteri gösteri performans kongre fuaye alan arena hall center centre km akm
k.m. km. amfi amfitiyatro oditoryum stage theatre theater oditoryumu
""".split())


def _venue_core(venue: str) -> set[str]:
    """Mekan adının ayırt edici sözcükleri (genel sözcükler ve il adı atılır)."""
    return {t for t in _tokens(venue) if t not in _VENUE_STOP}


def _venue_key(venue: str) -> str:
    """Mekan adı: ilçe/şube ekleri farklı yazılabildiği için ilk 2 sözcük."""
    words = norm(venue).split()
    return " ".join(words[:2]) if words else ""


def _similar(a: set[str], b: set[str]) -> float:
    """Jaccard benzerliği (0-1)."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _ayni_etkinlik(t1: set[str], v1: set[str], vk1: str, m1: str,
                   t2: set[str], v2: set[str], vk2: str, m2: str) -> bool:
    """İki kaydın aynı etkinliğin farklı sayfaları olup olmadığına karar verir.

    Çağıran taraf zaten aynı il ve aynı gün olduğunu doğrulamıştır. Kalan iş
    başlık ve mekanı karşılaştırmaktır; ikisi de kaynaklar arasında farklı
    yazılıyor:

      * Başlıkta il adı geçebilir ("Her Şey Biraz Yalan | Aydın"); il zaten
        eşleştiği için başlıktan çıkarılır, yoksa benzerlik şişer/eksilir.
      * Mekan adları kısaltılır ("Atilla KM" / "Atilla Koç Kültür Merkezi").
        Bu yüzden genel sözcükler atılıp ayırt edici adlar karşılaştırılır.
    """
    if _similar(t1, t2) < 0.6:
        return False
    if _similar(v1, v2) >= 0.5:
        return True
    if vk1 and vk1 == vk2:
        return True
    if _mekan_onek(m1, m2):
        return True
    c1, c2 = _venue_core_cached(v1), _venue_core_cached(v2)
    if c1 & c2:
        # Başlıklar neredeyse aynı ve mekanlar en az bir ayırt edici ad
        # paylaşıyor: aynı sayfanın iki yazımı.
        if _similar(t1, t2) >= 0.9:
            return True
    return _similar(t1, t2) >= 0.9 and len(t1) >= 3 and len(t2) >= 3


def _mekan_onek(ham1: str, ham2: str) -> bool:
    """Bitişik/ayrık yazım farkını yakalar: "Skaffpsm" ~ "Skaff PSM Alsancak".

    Adlar boşluklar atılarak karşılaştırılır; kısa olan uzunun başıysa aynı
    salonun iki yazımı sayılır. En az 6 karakter şartı, "sanat"/"sahne" gibi
    kısa ortak parçaların yanlış eşleşme üretmesini engeller.
    """
    a = "".join(norm(ham1).split())
    b = "".join(norm(ham2).split())
    if len(a) < 6 or len(b) < 6:
        return False
    kisa, uzun = (a, b) if len(a) <= len(b) else (b, a)
    return uzun.startswith(kisa)


_VENUE_CORE_CACHE: dict[frozenset[str], set[str]] = {}


def _venue_core_cached(tokens: set[str]) -> set[str]:
    """_venue_core'un önbellekli hâli: aynı sözcük kümesi çok kez soruluyor."""
    key = frozenset(tokens)
    hit = _VENUE_CORE_CACHE.get(key)
    if hit is None:
        hit = {t for t in tokens if t not in _VENUE_STOP}
        _VENUE_CORE_CACHE[key] = hit
    return hit


TUR_IPUCLARI = (
    ("Stand-up", ("stand up", "standup", "stand-up", "açık mikrofon", "komedi")),
    ("Tiyatro", ("tiyatro", "oyun", "sahne", "müzikal", "danslı")),
    ("Sinema", ("sinema", "film", "gösterim")),
    ("Konser", ("konser", "live", "party", "parti", "dj", "gece", "festival")),
    ("Sergi", ("sergi", "expo", "workshop", "atölye")),
    ("Spor", ("maç", "turnuva", "koşu", "spor")),
    ("Çocuk etkinlikleri", ("çocuk", "bebek", "masal")),
)


def _tur(title: str) -> str:
    """Başlıktan etkinlik türü tahmini.

    Biletimgo kartlarında tür alanı yok; arayüz tür rozetini ve kart
    illüstrasyonunu bu alandan kuruyor, boş kalınca "undefined" çıkıyordu.
    """
    kucuk = norm(title)
    for tur, kelimeler in TUR_IPUCLARI:
        if any(k in kucuk for k in kelimeler):
            return tur
    return "Etkinlik"


def _unique_ids(events: list[dict]) -> None:
    """Çakışan kimlikleri ayırır.

    Kimlik başlığın ilk 40 karakterinden türetiliyor; aynı gün aynı mekanda
    yapılan iki farklı atölye (başlıkları uzun ortak önekle başlıyorsa) aynı
    kimliği alıyordu. Arayüz kimliği anahtar olarak kullandığı için biri
    diğerinin üzerine yazılıyor, kart yanlış etkinliği açıyordu.
    """
    seen: dict[str, int] = {}
    for ev in events:
        eid = ev.get("id") or ""
        if eid not in seen:
            seen[eid] = 1
            continue
        seen[eid] += 1
        tam = norm(f"{ev.get('title','')}|{ev.get('venue','')}")
        ev["id"] = f"{eid}-{hashlib.sha1(tam.encode()).hexdigest()[:4]}"


def _fill_when(ev: dict) -> None:
    """Tarihi olup gün adı/saat metni olmayan kayıtları tamamlar.

    Biletimgo kart görünümünde saat yazmıyor; arayüz "Tarih: undefined"
    göstermesin diye gün adı tarihten türetilir.
    """
    if ev.get("when") and ev.get("wd"):
        return
    tarih = ev.get("date") or ""
    try:
        gun = datetime.date.fromisoformat(tarih[:10])
    except ValueError:
        return
    ev.setdefault("wd", "")
    ev["wd"] = ev["wd"] or WD[gun.weekday()]
    ev["when"] = ev.get("when") or f"{ev['wd']} {gun.day} {MONTHS_TR_FULL[gun.month - 1]}"


def dedupe_and_cheapest(events: list[dict]) -> list[dict]:
    """Aynı etkinliği (başlık+mekan+tarih) tek kayda indirger, en ucuzunu seçer.

    Katı anahtar eşleşmesi yetmediği için iki aşamalı çalışır: önce tam
    anahtar, sonra aynı tarihte benzer başlık VE benzer mekan (Jaccard ≥ 0.6)
    olan kayıtlar birleştirilir. Aynı etkinliğin farklı seansları (farklı
    tarih) ayrı kalır.
    """
    for ev in events:
        _fill_when(ev)
    groups: dict[str, list[dict]] = {}
    for ev in events:
        groups.setdefault(key_of(ev), []).append(ev)

    # İkinci aşama: benzer başlık+mekan gruplarını birleştir. Yalnızca aynı
    # tarih VE aynı ildeki gruplar karşılaştırılır; tüm çiftleri denemek
    # 13.000 kayıtta karesel maliyet yaratırdı. İl şart: aynı turne etkinliği
    # farklı illerde aynı gün oynayabilir, bunlar ayrı kayıt olmalı.
    buckets: dict[tuple[str, str], list[str]] = {}
    for k in groups:
        ev = groups[k][0]
        buckets.setdefault((ev.get("date", ""), norm(ev.get("city", ""))), []).append(k)
    for (date, _il), bucket in buckets.items():
        if date == "" or len(bucket) < 2:
            continue
        # İl adı başlıktan çıkarılır: aynı ilde olduğumuz zaten kesin, ad
        # yalnızca benzerliği bozuyor ("... | Aydın").
        il_tok = set(norm(_il).split())
        sig = {k: (_tokens(groups[k][0]["title"]) - il_tok,
                   _tokens(groups[k][0].get("venue", "")),
                   _venue_key(groups[k][0].get("venue", "")),
                   groups[k][0].get("venue", ""))
               for k in bucket}
        dead: set[str] = set()
        for i, ki in enumerate(bucket):
            if ki in dead:
                continue
            ti, vi, vki, mi = sig[ki]
            for kj in bucket[i + 1:]:
                if kj in dead:
                    continue
                tj, vj, vkj, mj = sig[kj]
                if not _ayni_etkinlik(ti, vi, vki, mi, tj, vj, vkj, mj):
                    continue
                groups[ki].extend(groups.pop(kj))
                dead.add(kj)

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
        # Girdideki kayıtlar daha önce birleştirilmiş olabilir (yeniden
        # birleştirme çağrıları); onların kaynak listesi ve fiyat dökümü de
        # korunur, yoksa ikinci geçişte çok kaynaklı bilgi silinirdi.
        kaynaklar: set[str] = set()
        by_source: dict[str, float] = {}
        for e in group:
            kaynaklar.update(e.get("sources") or ([e["source"]] if e.get("source") else []))
            for kaynak, fiyat in (e.get("price_by_source") or {}).items():
                if fiyat is None:
                    continue
                if kaynak not in by_source or fiyat < by_source[kaynak]:
                    by_source[kaynak] = fiyat
            # Aynı kaynaktan birden çok kayıt birleşebilir (ör. aynı etkinliğin
            # farklı sayfası); sözlükte sonuncusu öncekini ezmemeli, en düşük
            # fiyat kalmalı. Aksi hâlde seçilen fiyat dökümde görünmüyordu.
            fiyat = e.get("price")
            if fiyat is not None and e.get("source"):
                if e["source"] not in by_source or fiyat < by_source[e["source"]]:
                    by_source[e["source"]] = fiyat
        entry["sources"] = sorted(kaynaklar)
        entry["price_by_source"] = by_source
        if len(entry["sources"]) > 1 and by_source:
            entry["cheapest_source"] = min(by_source, key=by_source.get)
        else:
            entry["cheapest_source"] = None
        result.append(entry)
    _unique_ids(result)
    result.sort(key=lambda e: (e.get("date") or "", e.get("price") or 0))
    return result


def _tara(name: str, collector, limit: int) -> list[dict]:
    """Tek bir kaynağı tarar. Paralel çağrılır; hatası çağırana bırakılır."""
    print(f"→ {name} taranıyor…")
    return collector(limit)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sehir", default="", help="şehir filtresi (virgülle birden çok: 'İzmir,Ankara'; boş = tümü)")
    ap.add_argument("--limit", type=int, default=0, help="kaynak başına detay sınırı (0 = sınırsız)")
    args = ap.parse_args()

    wanted = [s.strip() for s in args.sehir.split(",") if s.strip()]
    # Kaynaklar birbirinden bağımsız; sırayla taramak toplam süreyi dörde
    # katlıyordu. Her kaynak kendi işçi havuzunu kurduğu için burada paralellik
    # güvenli: aynı adrese eşzamanlı istek sayısı kaynak başına sınırlı kalır.
    all_events: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        isler = {pool.submit(_tara, name, collector, args.limit): name
                 for name, collector in SOURCES}
        for is_ in concurrent.futures.as_completed(isler):
            ad = isler[is_]
            try:
                bulunan = is_.result()
            except Exception as hata:
                print(f"  ! {ad} taranamadı: {hata}")
                continue
            print(f"  ✓ {ad}: {len(bulunan)} etkinlik")
            all_events.extend(bulunan)

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
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    priced = [e for e in merged if e.get("price") is not None]
    print(f"✓ {len(merged)} etkinlik yazıldı ({len(priced)} tanesi fiyatlı) → {OUT}")
    for ev in merged[:10]:
        price = f"{ev['price']:.0f} ₺" if ev.get("price") is not None else "—"
        print(f"   {price:>9}  {ev['title'][:34]:<34} {ev.get('venue','')[:26]}")


if __name__ == "__main__":
    main()
