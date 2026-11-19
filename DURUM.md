# Genç — Durum Defteri

Bu dosya projenin **nerede bırakıldığını** kaydeder. Yeni bir oturumda önce
burayı oku, sonra `AGENTS.md` (teknik kurallar) ve `git log` ile devam et.

Son güncelleme: 2026-11-19 · Sürüm **1.56** · Commit **e529530** · Etiket **v1.56**

---

## 1. Nerede bıraktık

Genç (Türkiye mobil etkinlik uygulaması) **yayında ve çalışır durumda**.
Son oturumda kullanıcının iki şikayeti kapatıldı ve kısayollar yenilendi.

| | |
|---|---|
| Depo | `github.com/naberlo627-cyber/genc` (public) |
| Dal | `master` |
| Sürüm | 1.56 · versionCode 15600 |
| Servis çalışanı önbelleği | `genc-v69` |
| Veri | 73 il · 6.097 etkinlik · 4 bilet sitesi |
| Veri üretim zamanı | 2026-11-19 11:18 UTC |

### Yayın adresleri (üçü de v1.56 doğrulandı)

- **Birincil:** https://genc.surge.sh
- **Yedek:** https://genc.pages.dev
- **GitHub Pages:** https://naberlo627-cyber.github.io/genc
- **APK (hep en son):** https://github.com/naberlo627-cyber/genc/releases/latest/download/Genc.apk

### GitHub tarafı

- Release `v1.56` yayında, içinde `Genc.apk` (8.085.441 bayt).
- Pages: `built`, kaynak `master` / kök dizin.
- CI: `Yayın (Surge + Cloudflare Pages)` ✓ · `pages build and deployment` ✓

---

## 2. Son oturumda kapatılan işler

### Fotoğraf yükleme (kapandı)
Kök neden kod değil **bayat yayındı**: canlı site ve APK v1.54 taşıyordu.
Doğrulama: gerçek dosya seçiciyle yükleme yapıldı, `genc.photo` 1491 bayt
yazıldı ve **sayfa yenilendikten sonra da kalıcı** kaldı.

### İl yanındaki etkinlik sayıları (kapandı)
`cityRows()` artık yalnızca il adı + onay işareti üretiyor. Konum → İl seç
ekranında **81 il** listelendi, hiçbirinde sayı yok.

> Not: Ana sayfadaki "6.097 etkinlik" metni **Türkiye toplamıdır**, il sayacı
> değil. Kullanıcı bunu sorarsa karıştırılmasın.

### Kısayollar (yenilendi)
Kısayollar üç dosyada elle tutuluyordu ve ayrışmıştı. Artık **tek kaynak**:
`tools/kisayollar.py`. Buradan üretilenler:

- `manifest.json` → `shortcuts`
- `android/app/src/main/res/xml/shortcuts.xml`
- `android/app/src/main/res/values/strings.xml` (`sc_*` / `sc_*_long`)
- `sw.js` → `ASSETS` içindeki kısayol ikonları

**13 kısayol**, sırasıyla:
`ara, biletlerim, yakin, hafta, salonlar, bilet-al, bildirimler,
hoslandiklarim, kaydedilenler, profil, ayarlar, paylas, yardim`

Yeni eklenenler: **Paylaş**, **Yardım**. Canlıda 13/13 çalıştığı doğrulandı.

Bulunan gerçek hatalar:
- `sw.js` çevrimdışı listesinde 4 kısayol ikonu eksikti.
- `android:rank` geçersiz bir öznitelik (aapt2 derlemeyi reddediyor);
  sıra XML doküman sırasıyla veriliyor.
- `sc_yakin` etiketi "Çevremdekiler" yerine "Yakınımda" yapıldı (başlıkla uyumlu).

---

## 3. Doğrulama komutları

```bash
python3 tools/kisayollar.py --denetle   # 13 kısayol, dört tanım aynı sırada
python3 tools/yayin_denetimi.py         # 73 il, 6097 etkinlik, sayı/tekrar temiz
bash android/build-apk.sh               # APK derle (Gradle 8.7 + Java 17)
```

APK derlemesi ~15-20 sn. Çıktı: `indir/Genc.apk`.

---

## 4. Bilinen açık konular

- **`videolar` bölümü kapalı** (`VIDEO_ON=false`). Kodu, ikonu
  (`sc_videolar`) ve `runShortcut` dalı hazır; sadece liste dışında.
  Açmak için `VIDEO_ON=true` yeterli, sonra `tools/kisayollar.py`
  listesine `videolar` eklenmeli.
- **Depo adresinde gömülü GitHub jetonu var** (`git remote` içinde düz metin).
  Push'lar bununla çalışıyor. Jetonun `credential helper`'a taşınması
  önerildi, kullanıcı henüz onay vermedi. **Jeton değeri hiçbir yere
  yazılmamalı.**
- `genc.pages.dev/Genc.html` **308** ile `/Genc` adresine yönleniyor;
  `curl` ile kontrol ederken `-L` kullanılmalı.

---

## 5. Ortam notları

- Çalışma dizini `/workspace/project`.
- Playwright (async) kurulu; tarayıcı testleri için kullanılabilir.
- `unzip` yok → Python `zipfile` kullan.
- Android SDK `/home/openhands/android-sdk`, Gradle `/home/openhands/gradle-8.7`.
- Emülatör **yok**; APK yalnızca derleme + kaynak düzeyinde doğrulanabiliyor.
- `/workspace/isa/genc.json` sadece DNS kaydı; başka bir uygulama değil.

---

## 6. Devam etmek için

Bu noktadan devam ederken:

1. `git log --oneline -5` ile HEAD'i doğrula (`e529530` beklenir).
2. `python3 tools/kisayollar.py --denetle` ve `python3 tools/yayin_denetimi.py`
   çalıştır — ikisi de geçmeli.
3. Yeni işe başla. Sürüm artır: `APP_VERSION`, `sw.js` CACHE,
   `version.json`, `android/app/build.gradle` dördü birlikte.
4. Yayın: `git push` → CI kendisi yayınlar. APK için
   `bash android/build-apk.sh` sonra release'e yükle.
