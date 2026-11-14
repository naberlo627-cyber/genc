# Genç — etkinlik keşif uygulaması

Türkçe mobil etkinlik uygulaması. Tek dosyalık HTML uygulaması (`Genc.html`) +
PWA dosyaları + geliştirme sunucusu.

## Yapı

- `Genc.html` — uygulamanın tamamı (HTML + CSS + JS tek dosyada). QR kodu
  üreticisi de dosyanın içine gömülüdür (`QRCodeLite` global'i).
- `manifest.json` — PWA manifest'i; `shortcuts` dizisi ana ekran kısayollarını
  tanımlar (`?git=...` derin bağlantıları).
- `sw.js` — servis çalışanı. Uygulama sayfası **ağ öncelikli** (düzenlemeler
  anında görünür), simgeler önbellek öncelikli.
- `icons/` — Pillow ile üretilen PNG simgeler.
- `server.py` — önizleme + `/upload` fotoğraf yükleme ucu (port 12000).
  `/upload` multipart/form-data alır, dosyayı `yuklenenler/` altına benzersiz
  adla yazar ve JSON döner: `{"ok":true,"files":[...],"url":"/yuklenenler/..."}`.
- `yuklenenler/` — yüklenen fotoğraflar (sürüm kontrolüne girmez).
- `tools/qr.js` — QR kaynak kodu (Genc.html'e gömülmeden önceki hali).
- `tools/generate_icons.py` — simge üretici. İkon, uygulama içi logonun
  kutusuz halidir: köşegen gradyan zemin + beyaz dört uçlu ışıltı işareti
  (eski "G" harfi kaldırıldı).
- `tools/generate_shortcuts.py` — kısayol simgesi üretici (her kısayola kendi
  glifi; Android ve masaüstünde aynı ikon tekrar etmesin).
- `android/` — PWA'yı saran Android kabuğu (Gradle, paket `com.genc.app`).
  `android/build-apk.sh` web varlıklarını `assets/www/` altına kopyalar,
  Gradle ile derler ve `indir/Genc.apk` dosyasını üretir.
- `indir/` — indirilebilir APK'lar (sürüm kontrolüne girmez).
- Simgeler değişince `sw.js` içindeki `CACHE` sürümünü artırın; yoksa tarayıcı
  eski simgeyi önbellekten göstermeye devam eder.

## Android (APK)

```bash
./android/build-apk.sh                  # imzalı sürüm APK'sı -> indir/Genc.apk
./android/build-apk.sh assembleDebug    # hata ayıklama APK'sı
```

- Web varlıkları APK içine gömülür ve `WebViewAssetLoader` ile
  `https://appassets.androidplatform.net/assets/www/` altından sunulur; bu yüzden
  tüm iç yollar `assets/www/` önekini kullanmalıdır (`res/xml/shortcuts.xml`
  dahil).
- `MainActivity`, sayfa yüklenince `window.GENC_APP=true` atar. Uygulama bunu
  görünce fotoğrafları sunucuya göndermez, `cropSquare()` ile kırpıp data URL
  olarak `localStorage`'da saklar.
- Kamera/galeri: `WebChromeClient.onPermissionRequest` (kamera izni) ve
  `onShowFileChooser` (galeri) ile karşılanır.
- İmzalama anahtarı `android/app/genc-release.jks` yerel geliştirme içindir,
  depoya girmez. Yayın için kendi anahtarınızı üretin.

## Geliştirme komutları

```bash
python server.py            # http://localhost:12000 önizleme
node --check sw.js          # servis çalışanı sözdizimi
node --check tools/qr.js    # QR modülü sözdizimi
```

JS sözdizimini denetlemek için `<script>` bloklarını ayırıp `node --check`
çalıştırın; tarayıcı testi için herkese açık önizleme adresini kullanın.

## Notlar

- `localStorage` anahtarı: `genc.v1` (profil, biletler, kartlar, tema, sürüm).
- Sürüm etiketi: `APP_VERSION` (Genc.html). Hesap sayfasının altında
  "Genç sürüm X.Y (tarayıcı|uygulama)" olarak görünür ve `S.version`
  alanına yazılır. Bir değişikliğin cihaza ulaşıp ulaşmadığını bu etiketle
  doğrulayın; etiket eskiyse kullanıcı önbellekteki eski derlemeyi görüyor.
- Bilet QR yükü: `GENÇ|etkinlikId|kod|adet|tür|koltuklar` (EC seviyesi M).
- Uygulama kısayolu derin bağlantıları: `?git=yakin|videolar|ara|biletlerim|profil|bilet-al`.
  `git` parametresi çalıştıktan sonra adres çubuğundan silinir (yenilemede tekrar
  tetiklenmesin). Kullanıcı giriş yapmamışsa kısayol `pendingShortcut` olarak
  saklanır ve onboarding bitince uygulanır.
- Paylaşılan bilet bağlantısı: `?bilet=KOD`.
- Fotoğraf yükleme: avatara (profil fotoğrafı) dokununca açılan "Profil fotoğrafı"
  katmanı (`data-act="setphoto"` → `uploadSheet()`). Katman iki yol sunar:
  **Kamerayla çek** (uygulama içi canlı önizleme, `getUserMedia`, izin
  reddedilirse galeri önerilir) ve **Galeriden seç** (`accept="image/*"`,
  gizli `#gphoto` input'u). Biletlerim sekmesinde ayrı bir "Fotoğraf yükle"
  düğmesi yoktur; fotoğraf yalnızca profilden yönetilir. Seçilen görsel
  otomatik olarak profil fotoğrafı olur (`S.photo`, `localStorage`'da saklanır)
  ve tüm avatarlarda görünür (`paintAvatars()`). Kamera akışı katman kapanınca
  `stopCam()` ile durdurulur.
- APK'da (tarayıcı değil) fotoğraf sunucuya gönderilmez; `cropSquare()` ile
  400×400 kareye kırpılıp data URL olarak `S.photo`'ya yazılır. Tarayıcıda ise
  `/upload` ucuna gönderilir ve dönen `/yuklenenler/...` yolu kullanılır.
- `S.photo` boşsa avatarlar baş harfleri gösterir (`initials()`); doluysa
  `<img class="avimg">` gösterilir (`avatarHTML()`).
- Yuvarlak avatarlar (`avatar`, `ph .big`, `acctop .big`, `.back`, `.x`) `aspect-ratio:1`
  ve `flex:none` kullanır; böylece dar ekranda veya uzun adlarda esneyip oval olmazlar.
  `.ph` başlığı `flex-wrap` ile sarar, ad `overflow-wrap:anywhere` ile kırılır.
- Geri tuşu yönetimi: `histStack` + `popstate`. Açılan her katman (alt sayfa,
  satıcı sayfası) geçmişe yazılır; geri tuşu önce katmanı kapatır, kök
  seviyede uygulamadan çıkar. Katmanı kod içinden kapatırken `closeTopLayer`
  çağrılır, yoksa fazladan geçmiş girdisi kalır.
- Logoya basmak ana sayfaya döner (`#home-logo`, `#web-logo`, `#feed-logo` →
  `goHome()`): üst katmanları kapatır, Keşfet sekmesine geçer, başa kaydırır.
  Logo artık kutu + ışıltı işareti + "Genç" kelime işaretinden oluşur (`#logo`,
  viewBox `0 0 134 44`); kelime rengi `var(--ink)` olduğu için her iki temada
  okunur, kutu gradyanı `--logo-c1..c3` ile temaya uyar.
- Keşfet üst şeridi: solda logo, sağda profil avatarı. Tür seçimi yalnızca
  "Türe göre" ızgarasından yapılır (seçili kart `.cat.on` ile çerçevelenir).
  Logoya basmak (`goHome()`) filtreyi ve aramayı sıfırlar, Keşfet'e döner.
- Alt menü üç sekme: Keşfet, Videolar, Biletlerim. Profil sekmesi yok;
  profile erişim yalnızca sağ üstteki avatardan (`data-tab="profil"`).
- Profildeki kalem (`data-act="editprofile"`) hesap sayfasını açar
  (`openSheet('Hesap', …)`): profil alanları, kart yönetimi, tema seçici ve
  çıkış burada. Bu sayfadaki işlemler sayfayı kapatmaz; `refreshAccount()`
  içeriği yerinde yeniler. Kart ekleme alt sayfası `fromAccount` ile geri döner.
  Profil sayfası yalnızca kişisel içerik gösterir (bilet, kayıt, beğeni).
  Hesap sayfasının altında (yalnızca tarayıcıda) APK indirme satırı bulunur
  (`data-act="getapk"` → `getApk()`, `indir/Genc.apk`).
