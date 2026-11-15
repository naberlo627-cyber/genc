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
- `img/` — kategori kutucuklarındaki gerçek fotoğraflar (`cat-<slug>.jpg`,
  480x340). `tools/fetch_category_photos.py` bunları Openverse'ten indirir,
  kırpar ve `img/CREDITS.md` içine kaynak/lisans bilgisi yazar. Türev yasak
  (ND) lisanslı görseller atlanır. Yeni fotoğraf için: `python3
  tools/fetch_category_photos.py [kategori-slug]`.
- `server.py` — önizleme + `/upload` fotoğraf yükleme ucu (port 12000).
  `/upload` multipart/form-data alır, dosyayı `yuklenenler/` altına benzersiz
  adla yazar ve JSON döner: `{"ok":true,"files":[...],"url":"/yuklenenler/..."}`.
- `yuklenenler/` — yüklenen fotoğraflar (sürüm kontrolüne girmez).
- `tools/qr.js` — QR kaynak kodu (Genc.html'e gömülmeden önceki hali).
- `tools/brand.py` — ortak marka yardımcıları. Logo gradyanı (`STOPS`: premium
  "Aurora" paleti — indigo `#4338CA` → menekşe `#7C3AED` → mor `#A855F7` →
  fuşya `#D946EF`; tek renk ailesi, ~57° dar ton aralığı) ve beyaz yatay bilet
  işareti (`TICKET`, `NOTCH_CX`, `NOTCH_R`, `PERF_CX`, `PERF_Y`, `PERF_W`,
  `PERF_HH`, `ticket_mask`, `draw_ticket`) burada tanımlıdır; `gloss()`
  simgelere sol üstten düşen yumuşak beyaz parlama (cam hissi) ekler. Tüm
  simge üreticileri bu modülü kullanır.
- `tools/generate_icons.py` — PWA simge üretici. İkon, uygulama içi logonun
  kutusuz halidir: köşegen gradyan zemin + beyaz yatay bilet işareti
  (eski "G" harfi, dört uçlu ışıltı, konum iğnesi ve yan çentikli/dikey
  perforasyonlu ilk bilet denemesi kaldırıldı).
- `tools/generate_shortcuts.py` — kısayol simgesi üretici (her kısayola kendi
  glifi; Android ve masaüstünde aynı ikon tekrar etmesin).
- `tools/generate_launcher_icons.py` — Android başlatıcı simgeleri. Yuvarlak
  kare, daire ve uyarlanabilir ön katman üretir; ön katmandaki bilet güvenli
  alana sığması için `scale=0.6` ile küçültülür.
- `android/` — PWA'yı saran Android kabuğu (Gradle, paket `com.genc.app`).
  `android/build-apk.sh` web varlıklarını `assets/www/` altına kopyalar,
  Gradle ile derler ve `indir/Genc.apk` dosyasını üretir.
- `indir/` — indirilebilir APK'lar (sürüm kontrolüne girmez).
- Simgeler veya `img/` fotoğrafları değişince `sw.js` içindeki `CACHE` sürümünü
  artırın; yoksa tarayıcı eskisini önbellekten göstermeye devam eder.
- Kategori kutucukları `.cats` ızgarasındadır (3 sütun, `Genc.html`). Her
  kutuda `<img class="catimg">` gerçek fotoğrafı gösterir; fotoğraf
  yüklenemezse `onerror` ile kaldırılır ve `CATC` renk geçişi yedek kalır.
  Fotoğrafın üstünde okunurluk için `.cat::before` koyu katmanı vardır.

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

APK derleme ortamı (kabuk sıfırlanınca yeniden gerekebilir):

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_HOME=/home/openhands/android-sdk
./android/build-apk.sh        # assets/www güncellenir, sürüm yazılır, imzalı APK üretilir
apksigner verify indir/Genc.apk
```

Gerekli araçlar: OpenJDK 21 (`apt-get install openjdk-21-jdk-headless`), Gradle 8.7
(`/home/openhands/gradle-8.7`), Android SDK cmdline-tools + `platforms;android-34` +
`build-tools;34.0.0` (`ANDROID_HOME=/home/openhands/android-sdk`). İmza anahtarı
`android/app/genc-release.jks` yerelde durur ve `.gitignore` ile dışlanır; parola
`android/app/build.gradle` içindeki `signingConfigs.release` bloğundadır.

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
  Logo kutu + bilet işareti + "Genç" kelime işaretinden oluşur (`#logo`,
  viewBox `0 0 134 44`); kelime rengi `var(--ink)` olduğu için her iki temada
  okunur, kutu gradyanı mor→orkide→gül→sarı (`--logo-c1..c4`, dört durak) ile
  temaya uyar. Bilet işareti SVG'de tek `path` (`fill-rule="evenodd"`): yatay
  bilet gövdesi + üst/alt kenarın ortasındaki iki çentik + yatay perforasyon
  (üç yuvarlatılmış kesik). Çentik/perforasyon oyulur, bu yüzden evenodd ile
  gövdeyle aynı `path` içinde birleşir. Python tarafında `brand.TICKET` +
  `NOTCH_*`/`PERF_*` sabitleri aynı koordinatları kullanır.
- Keşfet üst şeridi: solda logo, sağda profil avatarı. Tür seçimi yalnızca
  "Türe göre" ızgarasından yapılır (seçili kart `.cat.on` ile çerçevelenir).
  Logoya basmak (`goHome()`) filtreyi ve aramayı sıfırlar, Keşfet'e döner.
- Alt menü üç sekme: Keşfet, Videolar, Biletlerim. Profil sekmesi yok;
  profile erişim yalnızca sağ üstteki avatardan (`data-tab="profil"`).
- Videolar sekmesi tam ekran, kaydırmalı kısa video akışıdır (`#feed`, her kart
  `.vid`). Her kartın zemini gerçek fotoğraftır (`.vphoto`, `img/vid-<id>.jpg`,
  dikey 720x1280, `loading="lazy"`); fotoğraf yüklenmezse `onerror` ile kaldırılır
  ve gradyan zemin görünür. Üstte logo + "Sana özel / Yakınında" hap sekmeleri
  (`.vtabs`), altta bilgi paneli (`.vpanel`: tür etiketi `.vtag`, başlık `.vtitle`,
  tarih/yer satırları `.vrow`). Video kartlarında beğen/kaydet/paylaş/bilet al
  düğmeleri ve bilet/kaydedilen/beğenilen sayaçları yoktur; kullanıcı bunları
  istemedi. İlerleme çubuğu (`.vprog`) aktif kartta döner, `IntersectionObserver`
  ile yönetilir; kaydırma sonunda `.vend` kapanış kartı gelir.
- Video fotoğrafları Wikimedia Commons'tan `tools/fetch_video_photos.py` ile
  indirilir (açık lisanslı, dikey, renkli; kaynak listesi `img/VID-CREDITS.md`).
- Video akışındaki "Sana özel" sıralaması `S.likes` tür uyumuna ve konuma göre
  yapılır (`videoList()`); beğeni verisi artık tutulmaz.
- Profildeki kalem (`data-act="editprofile"`) hesap sayfasını açar
  (`openSheet('Hesap', …)`): profil alanları, kart yönetimi, tema seçici ve
  çıkış burada. Bu sayfadaki işlemler sayfayı kapatmaz; `refreshAccount()`
  içeriği yerinde yeniler. Kart ekleme alt sayfası `fromAccount` ile geri döner.
  Profil sayfası yalnızca kişisel içerik gösterir (bilet, kayıt, beğeni).
  Hesap sayfasının altında (yalnızca tarayıcıda) APK indirme satırı bulunur
  (`data-act="getapk"` → `getApk()`, `indir/Genc.apk`).

## Kart doğrulama
- Varsayılan kart yoktur; `S.cards` boş başlar (`[]`), kullanıcı kendi kartını
  ekler. Kart yoksa hesap sayfası "Kayıtlı kartın yok." gösterir.
- `cardBrand(d)` numaradan markayı bulur: Visa `^4`, Mastercard `^(5[1-5]|2[2-7])`,
  Amex `^3[47]`. Marka başına uzunluk/CVV kuralı vardır (Amex 15 hane, 4 haneli CVV).
- `addCard()` Luhn algoritmasıyla numarayı doğrular; geçmeyen kart reddedilir ve
  `#k-err` alanında hata gösterilir. Marka adı kart satırında görünür.

## Güncelleme (APK)
- Sürüm tek kaynaktan yönetilir: `Genc.html` içindeki `var APP_VERSION='x.y'`.
  `build-apk.sh` bunu okuyup `versionName`'i yazar, `versionCode`'u türetir
  (`major*10000 + minor*100 + patch`) ve `version.json` üretir.
- `version.json` (`{version, versionCode, notes, apk}`) güncelleme denetiminin
  kaynağıdır. `build-apk.sh` bunu `assets/www/` içine de kopyalar.
- Sayfa açılışında `checkUpdate()` (1.5 sn sonra) `version.json`'ı çeker;
  sunucudaki sürüm `APP_VERSION`'dan büyükse `#upbar` güncelleme şeridi görünür.
  `cmpVer()` sürümleri sayısal olarak karşılaştırır.
- Şeritteki "Güncelle" (`data-act="update"` → `installUpdate()`): uygulama
  içindeyse `window.GENC_INSTALL(url)` çağrılır, tarayıcıda APK indirilir.
- `absUrl()` göreli `apk` yolunu uygulama modunda `REMOTE_BASE`'e bağlar;
  uygulamanın gömülü kopyası eski olacağı için denetim uzaktan yapılır.
- Android tarafı: `UpdateBridge` (`GencUpdate.install(url)`) APK'yı `cache/updates/`
  altına indirir, `FileProvider` (`com.genc.app.fileprovider`) ile paylaşıp sistem
  kurulum ekranını açar. `REQUEST_INSTALL_PACKAGES` izni ve `res/xml/file_paths.xml`
  gereklidir. Android 8+ için `ACTION_MANAGE_UNKNOWN_APP_SOURCES` yönlendirmesi var.
- İmza anahtarı (`android/app/genc-release.jks`) sabit kalmalı; aksi halde
  güncelleme kurulamaz. APK imzası `apksigner verify` ile denetlenir.
  Anahtar `.gitignore` ile dışlandığı için repoda yedeği yoktur; kaybolursa
  yeni APK eskisinin üzerine kurulamaz, kullanıcı uygulamayı silip yeniden kurar.
- Servis çalışanı (`sw.js`) `version.json` ve `.apk` isteklerini önbelleğe almaz
  (her zaman ağdan); yoksa eski sürüm görünür.
