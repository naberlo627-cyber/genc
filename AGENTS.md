# Genç — etkinlik keşif uygulaması

Türkçe mobil etkinlik uygulaması. Tek dosyalık HTML uygulaması (`Genc.html`) +
PWA dosyaları + geliştirme sunucusu.

## Yapı

- `Genc.html` — uygulamanın tamamı (HTML + CSS + JS tek dosyada). QR kodu
  üreticisi de dosyanın içine gömülüdür (`QRCodeLite` global'i).
- **Bölüm durumu.** Alt menü: Ana Sayfa, Keşfet, Salonlar, Profil. Kısa videolar
  bölümü geçici olarak kapalıdır (`var VIDEO_ON=false`); `true` yapınca menü
  butonu, Keşfet bölümü ve kısayollar geri gelir. Biletler ayrı sekme değildir;
  Profil sayfasının içinde `ticketsSectionHTML()` ile gösterilir (eski `biletler`
  hedefleri `setTab` içinde profile yönlenir).
- **Keşfet > Etkinlikler.** Referans uygulamadaki (Biletinial) "Etkinlikler"
  bölümünün karşılığı: `evHead` (el yazısı şehir etiketi + şehir seçici),
  `evFilterBar` (kategori hızlı seçimi + filtre düğmesi), `evSection` (2 sütunlu
  kart ızgarası + "Daha fazla göster"), `evCard` (afiş, kategori, mekan, tarih,
  başlangıç fiyatı, "Tükendi" rozeti) ve `evFilterSheet` (Kategori, Tarih,
  Sırala, Mekan). Filtre durumu `S.evCat`, `S.evVenue`, `S.evDate`, `S.evSort`,
  `S.evShow` alanlarında tutulur.
- **Etkinlik gruplama.** `groupEvents`/`groupKey` aynı oyunun (normalize edilmiş
  başlık) tüm seanslarını tek karta indirir; kart `rep.sessions` taşır ve tarih
  aralığı (`rangeLabel`) gösterir. Detayda `sessionListHTML` seansları salon
  salon listeler; seans düğmesi `data-url` ile o seansın gerçek satıcı sayfasını
  `se.url`'e yazar, böylece "Bileti satın al" doğru gösterime gider.
- **Etkinlik detayı sekmeleri.** `openDetail` sekmeli bir ekran açar:
  `detailTabsHTML` + `DTABS` ile Detay · Biletler · Kadro · Yorumlar · Etkinlik
  Kuralları. Sekme düğmeleri `data-dtab`, panolar `data-dpane` taşır;
  `switchDetailTab` seçimi `aria-selected`/`hidden` ile yönetir (dokunma
  işleyicisi `data-dtab`'ı yakalar). Panolar: `paneDetay` (açıklama + bilgi
  kartları + tür rozetleri), `paneBiletler` (`sessionListHTML` + satın al),
  `paneKadro` (`cast` kartları), `paneYorumlar` (puan + boş durum), `paneKurallar`
  (numaralı kurallar). Geçmiş etkinlikte "Biletler" sekmesi gizlenir. Veri yoksa
  `emptyState` zarif bir boş durum basar.
- **Uzun metin katlama.** Detayda `about` 320 karakterden, kural listesi 3
  maddeden uzunsa `.clamp` ile katlanır ve `.dmore` düğmesi çizilir ("Devamını
  oku" / "Tüm kuralları göster"); dokunma `expandMore()` ile `.clamp` sınıfını
  kaldırır ve düğmeyi siler. Detaydaki tarih/mekan/şehir satırları `.dmeta`
  kartında toplanır; başlık altında dağınık satırlar yerine tek bilgi kutusu
  görünür.
- **Bilet ekranı (`openWeb`).** Etkinlik görselli `.dhero` başlık, `.opt-row`
  radyo düğmeleriyle bilet türü seçimi (seçili olanda `.tick`) ve adet/toplam
  satırları. Ödeme sonrası ekran bir bilet koçanıdır (`.wstub`): etkinlik
  görseli, tarih/mekan, koltuk ve QR ile bilet kodu. Biletlerim'de bilete
  dokununca açılan kod ekranı (`showBigQR`) da aynı `.wstub` düzenini kullanır.
- **Salonlar vs. mekanlar.** `venueKind(name)` mekanı `hall` (sahne, salon,
  tiyatro, opera, gösteri merkezi, sanat merkezi, arena) veya `gather` (kültür
  merkezi, kongre merkezi, AVM, meydan, park, kafe) olarak sınıflar. Salonlar
  sekmesi (`renderVenues`) yalnızca `hall` mekanlarını listeler; salona dokunmak
  `openVenue()` ile o salonun gün gün programını alt sayfada açar. Ana Sayfa
  "Yakındaki mekanlar" bölümü `gather` alanlarını öne alır, kalanı en yakın
  mekanlarla tamamlar.
- **Sekme ve kaydırma kalıcılığı.** `S.tab` ve `S.scrolls` (sekme başına
  kaydırma konumu) `persist()`/`restore()` ile saklanır; uygulama yeniden
  açıldığında son sekme ve konum geri yüklenir (`restoreScroll`). Kaydırma
  dinleyicileri `pagehide`/`beforeunload` ile diske yazılır.
- **"Tükendi" rozeti.** `refreshLive()` rozeti yalnızca konumlandırılmış görsel
  kabına (`.evpic`, `.tkpic`, `.poster .pic`, `.wide`, `.thumb`) ekler; düz
  satırlara (ör. `.calrow`) eklenirse sayfanın sol üstüne kaçardı.
- **Çok şehir.** Veri beş ili kapsar (İzmir, Ankara, İstanbul, Bursa, Antalya).
  `S.city` seçili şehri tutar (`nearestCity` konumdan tahmin eder, onboarding 2.
  adım ve `#locbtn` şehir sayfası ayarlar); Keşfet listesi seçili şehre göre
  süzülür. İstanbul Anadolu/Avrupa yakaları `İstanbul`'a normalize edilir.
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
  fuşya `#D946EF`; tek renk ailesi, ~57° dar ton aralığı) ve beyaz "G"
  monogramı (`monogram_mask`, `draw_monogram`; maske `tools/assets/gmono_mask.png`)
  burada tanımlıdır; `gloss()` simgelere sol üstten düşen yumuşak beyaz parlama
  (cam hissi) ekler. Tüm simge üreticileri bu modülü kullanır.
- `tools/assets/gmono_mask.png` — "G" monogramının yüksek çözünürlüklü alfa
  maskesi. `Genc.html #gmono` ile aynı form (Archivo 800 "G"); ikon üreticileri
  bu maskeyi kullanır. Monogram değişirse burası ve `#gmono` birlikte güncellenir.
- `tools/generate_icons.py` — PWA simge üretici. İkon, uygulama içi markanın
  monogram halidir: köşegen gradyan zemin + beyaz "G" monogramı (eski kutu +
  bilet işareti kaldırıldı).
- `tools/generate_shortcuts.py` — kısayol simgesi üretici (her kısayola kendi
  glifi; Android ve masaüstünde aynı ikon tekrar etmesin).
- `tools/generate_launcher_icons.py` — Android başlatıcı simgeleri. Yuvarlak
  kare, daire ve uyarlanabilir ön katman üretir; ön katmandaki monogram güvenli
  alana sığması için `scale=0.6` ile küçültülür.
- `tools/collect_tickets.py` — **gerçek bilet toplayıcı**. Birden çok satıcıyı
  tarar, etkinlik adı/mekan/tarih/**fiyat** bilgisini toplar, aynı etkinliği
  satan kaynakları eşleştirip **en ucuzunu** işaretler. Çıktı: `data/tickets.json`.
  Kaynaklar: Biletinial (halka açık JSON-LD `Event`+`Offer`), Passo (halka
  açık `ticketingweb.passo.com.tr/api/passoweb` web API'si; fiyatlar kategori
  bazında açık) ve Biletino (şehir sayfalarındaki bağlantılar → detayda halka
  açık JSON-LD `Event`+`Offer`). Yeni kaynak için `SOURCES` listesine toplayıcı
  ekleyin.
  `--sehir "İzmir,Ankara,İstanbul,Bursa,Antalya"` (varsayılan İzmir), `--limit N`
  (kaynak başına detay sınırı). Biletinial'ın "İstanbul Avrupa/Anadolu" ayrımı
  `norm_city()` ile tek "İstanbul" iline indirgenir.
- `tools/embed_data.py` — `data/tickets.json` içeriğini `Genc.html` içindeki
  `var GENC_DATA=...;` satırına gömer. Bu gömülü kopya artık **yedektir**
  (çevrimdışı/ilk açılış ve APK); uygulama normalde `data/events.json`'u
  sunucudan çeker. `android/build-apk.sh` bu adımı her derlemede çalıştırır;
  `COLLECT=1` verilirse önce taze veri toplanır.
- `tools/build_payload.py` — `data/tickets.json`'u (girintili) ağ için kompakt
  `data/events.json`'a çevirir. Uygulamanın çalışma anında indirdiği dosya budur.
- `data/events.json` — uygulamanın indirdiği yayın verisi. Günlük yenileme
  yalnızca bu dosyayı değiştirir; bu yüzden yeni veri için APK/HTML yeniden
  derlemek **gerekmez**.
- `data/tickets.json` — toplanan gerçek etkinlik/fiyat verisi (uygulamaya gömülür).
  Her etkinlik detay alanları da taşır: `description` (açıklama), `cast`
  (`{name,role}` listesi), `runtime` (dakika), `genres`/`genre_label`, `age`
  (yaş sınırı), `rules` (kural maddeleri) ve `organizer`. Bu alanlar Biletinial
  detay sayfasından okunur (JSON-LD `description`/`organizer`, sayfadaki
  `trackingInfo` JSON'u ve `event-rules-v2__content` bloğu).
- `tools/enrich_events.py` — mevcut `data/tickets.json`'u detay alanlarıyla
  zenginleştirir: benzersiz satıcı sayfalarını çeker, alanları aynı URL'yi
  paylaşan tüm seanslara yazar. `--force` ile hepsini yeniden çeker. Yorum verisi
  satıcının turnstile'lı ucu arkasında olduğundan toplanmaz; uygulama yorumlar
  sekmesinde bilgilendirici bir boş durum gösterir.
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
  Kutucuğa dokunmak Keşfet'in "Etkinlikler" ızgarasını (`S.evCat`) o türe
  süzer; ana sayfanın genel filtresi (`S.filter`) **kurulmaz**, aksi halde ana
  sayfa "kilitleniyor" (Öne çıkanlar/Bu hafta/Ücretsiz/Mekanlar bölümleri
  kayboluyor) ve Keşfet afiş şeridine düşüyordu. Aynı kutucuğa tekrar dokunmak
  filtreyi kaldırır. Detaydaki "Benzer etkinlikler" de aynı yolu kullanır.

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

- `localStorage` anahtarı: `genc.v1` (profil, biletler, kartlar, sürüm).
- Sürüm etiketi: `APP_VERSION` (Genc.html). Hesap sayfasının altında
  "Genç sürüm X.Y (tarayıcı|uygulama)" olarak görünür ve `S.version`
  alanına yazılır. Bir değişikliğin cihaza ulaşıp ulaşmadığını bu etiketle
  doğrulayın; etiket eskiyse kullanıcı önbellekteki eski derlemeyi görüyor.
- Bilet QR yükü: `GENÇ|etkinlikId|kod|adet|tür|koltuklar` (EC seviyesi M).
- Uygulama kısayolu derin bağlantıları: `?git=yakin|videolar|ara|biletlerim|profil|bilet-al|hafta`.
  `git=hafta` ana sayfayı açar ve "Bu hafta ne var?" paylaşım görselini üretir.
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
- Marka, ayrı bir kutu + simge değil, doğrudan **"Genç" kelime markasıdır**
  (`#logo`, viewBox `0 0 2585.39 896.85`). Harfler Archivo 800'ün dış
  çizgilerinden (fontTools ile) SVG `path`'e çevrilmiştir: "G","e","n"
  `currentColor` (her iki temada okunur), Türkçeye özgü **"ç"** ise marka
  gradyanıyla (`url(#lg)`) boyanır — ismin içine gömülü tek marka izi
  (Amazon gülümsemesi / FedEx oku gibi). Gradyan `#logo` içinde tanımlıdır
  (`--logo-c1..c4`). Uygulama ikonları için monogram `#gmono` (44x44 beyaz "G").
- Logoya basmak **Ana Sayfa**'ya döner (`#home-logo`, `#kesfet-logo`,
  `#web-logo`, `#feed-logo` → `goHome()`): üst katmanları kapatır, `home`
  sekmesine geçer, `#hscroll`'u başa kaydırır.
- Alt menü dört sekme: **Ana Sayfa** (`home`, monogram simgesi), **Keşfet**
  (`kesfet`), Videolar (`videolar`), Biletlerim (`biletler`). Profil sekmesi
  yok; profile erişim yalnızca sağ üstteki avatardan (`data-tab="profil"`).
- Ana Sayfa (`#tab-home`, `renderHome()`): logo, konum şeridi, "Öne çıkanlar",
  "Türe göre" ızgarası, "Bu hafta/Yaklaşanlar" bilet listesi (`.tk` — solda
  afiş `.tkpic`, üstünde gün/ay etiketi `.tkdate`, sağda başlık/mekan/fiyat),
  "Ücretsiz etkinlikler", "Yakındaki mekanlar" (toplanma alanları önce).
  Aramasız/ışıksız varsayılan vitrin burada.
- Keşfet (`#tab-kesfet`, `renderKesfet()`): yalnızca arama kutusu + vitrin
  bölümleri. Aramasız durumda üç bölüm gösterir: **Kısa videolar**, **Gezi
  turları**, **Çevrende yapılacak gösteriler**. Arama/filtre varken tek
  "Sonuçlar" bölümüne düşer. Kategori kartına veya mekana dokunmak Keşfet'e
  geçip sonuçları gösterir (`renderBrowse()` ikisini birden tazeler).
  **Son aramalar** (`#recent`, `recentHTML()`): aramasız durumda son 6 arama
  çip olarak gösterilir; çipe dokunmak aramayı çalıştırır, "Temizle" listeyi
  boşaltır. Liste `S.recent` olarak `persist()` ile saklanır.
- Videolar sekmesi tam ekran, kaydırmalı kısa video akışıdır (`#feed`, her kart
  `.vid`). Her kartın zemini gerçek fotoğraftır (`.vphoto`, `img/vid-<id>.jpg`,
  dikey 720x1280, `loading="lazy"`); fotoğraf yüklenmezse `onerror` ile kaldırılır
  ve gradyan zemin görünür. Üstte logo + "Sana özel / Yakınında" hap sekmeleri
  (`.vtabs`), altta bilgi paneli (`.vpanel`: tür etiketi `.vtag`, başlık `.vtitle`,
  tarih/yer satırları `.vrow`). Video kartlarında beğen/kaydet/paylaş/bilet al
  düğmeleri ve bilet/kaydedilen/beğenilen sayaçları yoktur; kullanıcı bunları
  istemedi. İlerleme çubuğu (`.vprog`) aktif kartta döner, `IntersectionObserver`
  ile yönetilir; kaydırma sonunda `.vend` kapanış kartı gelir. Video bitince
  **hiçbir şey olmaz** — akış kendiliğinden kaymaz, kullanıcı parmağıyla
  ilerler. (Eski otomatik/akıcı geçiş ve `slideTo()` kaldırıldı.)
- Video fotoğrafları Wikimedia Commons'tan `tools/fetch_video_photos.py` ile
  indirilir (açık lisanslı, dikey, renkli; kaynak listesi `img/VID-CREDITS.md`).
- Video akışındaki "Sana özel" sıralaması `S.likes` tür uyumuna ve konuma göre
  yapılır (`videoList()`); beğeni verisi artık tutulmaz.
- Profildeki kalem (`data-act="editprofile"`) hesap sayfasını açar
  (`openSheet('Hesap', …)`): profil alanları, kart yönetimi ve çıkış burada. Bu sayfadaki işlemler sayfayı kapatmaz; `refreshAccount()`
  içeriği yerinde yeniler. Kart ekleme alt sayfası `fromAccount` ile geri döner.
  Profil sayfası yalnızca kişisel içerik gösterir (bilet, kayıt, beğeni).
  Hesap sayfasının altında (yalnızca tarayıcıda) APK indirme satırı bulunur
  (`data-act="getapk"` → `getApk()`, `indir/Genc.apk`).

## Gerçek bilet verisi ve "en ucuz" sistemi

Etkinlikler artık **gerçek**: uygulama, toplanan gerçek etkinlik/mekan/tarih/fiyat
verisini gösterir. Akış:

1. `python3 tools/collect_tickets.py [--sehir "İzmir,Ankara,İstanbul,Bursa,Antalya"]` → `data/tickets.json`.
   Her kayıt; ad, mekan, il/ilçe, koordinat, tarih ve satıcı sayfasından alınan
   **gerçek fiyatı** taşır. Aynı etkinliği (başlık+mekan+tarih) satan kaynaklar
   `dedupe_and_cheapest` ile birleştirilir; `price_by_source`, `cheapest_source`
   alanları üretilir ve **en ucuz kaynak** seçilir.
2. `python3 tools/build_payload.py` → `data/events.json` (uygulamanın indirdiği
   kompakt veri) ve `python3 tools/embed_data.py` → veri `Genc.html` içindeki
   `GENC_DATA`'ya **yedek** olarak gömülür.
3. Açılışta `applyRealData()` önce `localStorage` önbelleğini, yoksa gömülü
   `GENC_DATA`'yı gösterir; ardından `loadRemoteData()` `data/events.json`'u
   sunucudan çeker ve farklıysa ekranı tazeler. Ağ hatası sessizce yutulur,
   uygulama son bilinen veriyle çalışmaya devam eder.
   Gerçek kayıtlarda detay sayfası "Bileti satın al" gösterir ve
   `openReal()` ile **satıcının gerçek bilet sayfası** açılır (uygulama ödeme
   almaz). Birden çok kaynak eşleşirse fiyat "… ₺ · en ucuz" ve not
   "En ucuz: <kaynak> · <kaynaklar> karşılaştırıldı" olur.

## Veri yenileme servisi (`refresh/`)

Tek işi etkinlik verisini güncel tutmak olan bağımsız bir sistem. Günlük
çalışır, veriyi kaynaklardan yeniden toplar ve yayına alır; başka iş yapmaz.

- `refresh/refresh.py` — yenileme akışı: topla → zenginleştir → `data/events.json`
  üret → `Genc.html`'e yedek göm → `data/refresh_status.json` yaz.
- `refresh/run.sh` — kabuk sarmalayıcı; cron/systemd/CI bunu çağırır.
- `refresh/systemd/` — `genc-refresh.service` + `genc-refresh.timer` (her gün
  04:30 TRT, `Persistent=true` ile kaçan çalışmayı telafi eder).
- `refresh/README.md` — kurulum (systemd ve cron), izleme, sorun giderme.

Kapsam: yenilemenin tek işi veridir; `version.json` (APK sürümü) ve `sw.js`
(önbellek sürümü) artırmaz. Uygulama veriyi açılışta çektiği için bu gerekmez.

Tasarım ilkeleri: **çökmez** (her adım hata toleranslı, durum dosyası yazılır),
**eşzamanlılık güvenli** (kilit dosyası), **tekrar çalıştırılabilir** (kısmi
veri yayına alınmaz, başarısızsa önceki veri korunur), **sessizce bozmaz**
(`--min-events` altındaysa yeni veri reddedilir).

Çalıştırma ve izleme:

```bash
./refresh/run.sh                     # elle yenileme
python3 refresh/refresh.py --dry-run # akış denetimi (toplamadan)
cat data/refresh_status.json         # son çalışma: ok, etkinlik sayısı, süre
tail -f refresh/logs/refresh.log     # çalışma günlüğü
systemctl list-timers genc-refresh.timer   # systemd ile sonraki çalışma
```

Uygulama veriyi çalışma anında çektiği için **günlük veri yenilemesi APK
derlemesi gerektirmez**. Gömülü yedek (APK içi) güncellensin isteniyorsa
`./android/build-apk.sh` çalıştırılır.

Kaynak notları:

- **Biletinial**: detay sayfaları schema.org `Event` + `Offer` JSON-LD yayınlar
  (fiyat `offers.price`). `robots.txt` genel botlara izin verir; giriş gerekmez.
- **Passo**: `POST ticketingweb.passo.com.tr/api/passoweb/allevents` listeler;
  `GET …/geteventdetails/{seoUrl}/{eventId}/118` fiyatı (`categories[].price`,
  `lowPrice`) verir. Yanıtlar `access-control-allow-origin: *` ile gelir.
- **Etkinlik afişleri.** Kartlar ve detay, etkinliğin gerçek afişini (`image`)
  gösterir; afiş yoksa salon fotoğrafına (`venue_image`), o da yoksa yerel
  `VENUE_PHOTOS` kaydına düşer. `onerror="this.remove()"` ile kırık görsel
  sessizce gizlenir.
- **Passo görselleri yereldir.** `image.passo.com.tr`, Cloudflare + `nosniff`
  nedeniyle görselleri tarayıcıdan çapraz kaynak olarak sunmuyor
  (`net::ERR_BLOCKED_BY_ORB`); cURL ile erişilebilir ama `<img>` yüklenmez.
  Bu yüzden Passo afişleri toplama sırasında `img/ev/<hash>.webp` olarak
  indirilip `data/tickets.json` içinde yerel yolla saklanır. Yeni Passo verisi
  çekilirse `tools/embed_data.py` öncesi bu indirme adımı tekrarlanmalı.
  Biletinial afişleri (`merlincdn.net`) sorunsuz açılır, uzak kalır.
- **Passo şehir filtresi uygulamaz**; `allevents` tüm yurdu döndürür, toplayıcı
  `venueName`/`seoTitle` içinde "İzmir" arayıp detaydan `venueCity` ile doğrular.
- **Biletino**: şehir sayfaları (`/tr/city/<il>/`) etkinlik bağlantıları verir;
  detay sayfaları schema.org `Event`+`Offer` JSON-LD yayınlar (fiyat
  `offers.price`, tür `@type` → uygulama türü). `robots.txt` genel botlara izin
  verir; yalnızca `/account`, `/search` gibi yollar kapalıdır.
- **Fiyatı yalnızca giriş/Cloudflare arkasında veren siteler (Biletix, Bubilet,
  Mobilet) şimdilik kaynak değildir**; `SOURCES` yapısı yeni kaynağa açıktır.
  Biletix ve bilet.com denendi: Biletix içeriği JS ile yükler (JSON-LD yok),
  bilet.com otobüs/uçak bileti satar (etkinlik değil).
- Toplama siteye saygılıdır: istekler paralel ama sınırlı (6 iş parçacığı),
  aralarda gecikme, `fetch` yeniden dener.

## Tema (yalnızca sistem)
- Uygulama yalnızca **telefonun temasını** izler; uygulama içi "Sistem / Açık /
  Koyu" seçicisi kaldırıldı. Açık/koyu geçişi `prefers-color-scheme` ile
  CSS'ten yapılır; `data-theme` özniteliği hiçbir zaman zorlanmaz
  (`applyTheme()` yalnızca `theme-color` meta etiketini tazeler).
- `isDark()` = `prefers-color-scheme: dark` eşleşmesi. Tema tercihi artık
  `localStorage`'a yazılmaz.

## Reklam alanları (profil hariç)
- Sponsor alanları gerçek bir reklam ağına bağlı **değildir**; yalnızca yerleşimi
  ve görsel dili gösteren yerel örneklerdir (`ADS` dizisi + `adFor/adCardHTML/
  adRowHTML/adVideoHTML`). Uygulamanın kendi kart diliyle aynı tipografi ve
  yuvarlak köşeleri kullanır, "Reklam" etiketi taşır, tam ekran kaplamaz ve
  otomatik oynamaz/animasyonlu değildir.
- Reklamlar uygulamanın **kendi rengini** kullanır: zemin `--card` (beyaz),
  kenarlık `--line`, etiket `--line/--mute`, CTA `--brand`. Böylece arayüzle
  bütünleşir; ayrımı yalnızca "Reklam" etiketi sağlar (`--ad-*` belirteçleri
  `--card/--line/--mute/--brand`a bağlıdır, tema ile birlikte değişir).
- Reklamlar diğer bölümlerle **çakışmaz**: kartlarda `margin-top:16px` ile
  üstteki bölümden ayrılır, bölüm başlıkları (`secHead`, 22px üst boşluk) ile
  yeterli nefes alanı bırakır; yatay taşma yoktur.
- Dört yerleşim vardır: düz kart `.adcard` (Ana Sayfa'da kategori ızgarasından
  sonra, Keşfet'te Kısa videolar bölümünden sonra, Biletlerim'de liste altında ve
  etkinlik detayında), geniş satır `.adrow` (Keşfet'te Gezi turlarından sonra),
  **Ana Sayfa "Öne çıkanlar" karuselinin içinde** 3. sıradaki yatay reklam
  (`.hrail .adrow`, 300×176, `fcards.splice(2,0,adRowHTML(adFor('row',1)))`) ve
  video akışında tek, küçük, kapatılabilir şerit `.vad` (üstte, başlık çubuğunun
  altında; kapatılınca oturum boyunca gizli kalır, `S.adOff`).
- **Profilde ve ödeme (satıcı) sayfasında reklam yoktur.** Arama/filtre
  sonuçlarında da reklam gösterilmez; yalnızca durgun vitrin ve listelerde çıkar.
- Bir reklama dokunmak sayfa açmaz; örnek bir "Sponsor bağlantısı" bildirimi
  gösterir (`data-ad` tıklama yönetimi).

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

## Haftalık paylaşım görseli ("Bu hafta ne var?")
- Yerel topluluklarda (mahalle/semt grupları, WhatsApp toplulukları, yerel haber
  sayfaları) paylaşılmak üzere her hafta tekrar eden, cihazda üretilen bir görsel.
- `buildWeeklyCanvas()` 1080×1350 dikey PNG çizer: marka logosu, şehir etiketi,
  "Bu hafta ne var?" başlığı, haftanın 6 etkinliği ve alt bilgi. Şehir adı
  `S.city`'den gelir, yani konuma/seçilen şehre göre değişir.
- `wkPicks()` önce bu haftanın etkinliklerini (öne çıkanlar → en yakın), yetmezse
  yaklaşanlardan 6'ya tamamlar. `wkWeekRange()` haftayı pazartesi–pazar gösterir.
- Görsel yalnızca yerel varlıklarla çizilir: uzak satıcı fotoğrafları CORS
  başlığı göndermediği için canvas'a çizilemez (`Access-Control-Allow-Origin`
  yok → tuval "kirli" olur ve `toDataURL` hata verir). Bu yüzden fotoğraf yerine
  türü simgeleyen renk geçişi (`WK_ART`) ve simge (`WK_GLYPH`) kullanılır.
- Logo, gömülü `#logo` simgesinden `wkLogoURL()` ile yeniden üretilir: SVG yol
  verisi alınır, tema değişkenleri (`--logo-c1..c4`) kart zemini için açık
  tonlarla değiştirilir, `color:#FFFFFF` ile beyaza boyanır. Kopyalama değil,
  uygulamanın kendi logosunu yeniden kullanma.
- Giriş noktaları: ana sayfada `.wkcard` (`data-act="weekly"`) ve Profil'de
  "Bu hafta ne var?" düğmesi. Sayfa `weeklyShareSheet()` ile açılır; `wkshare`
  (Web Share API, dosya destekleniyorsa görseli ekler) ve `wksave`
  (PNG indirir, ad `genc-bu-hafta-<şehir>.png`) düğmeleri vardır.
- Yeni şehir/etkinlik türü eklenirse `WK_ART` ve `WK_GLYPH` tablolarına karşılık
  eklenir; bilinmeyen türde güvenli varsayılan kullanılır.

## Görsel katmanları (afiş / filigran)
- Kart ve detay görsellerinde iki katman yan yana durur: gerçek fotoğraf
  (`.photo` / `img`) ve dekoratif SVG (`.art`). Fotoğraf yüklenirse SVG
  gizlenmelidir; yoksa SVG fotoğrafın üzerinde filigran gibi görünür.
- Kural her konteynerde ayrı yazılır: `.poster .pic .photo~.art`,
  `.wide .photo~.art`, `.dhero .photo~.art`, `.tk .tkpic .photo~.art` ve
  `.evcard .evpic img~.art` (`display:none`). Yeni bir görsel konteyneri
  eklerken bu kuralı da eklemek gerekir.
- `evCard` görseli `<img>` etiketi kullanır (`onerror="this.remove()"`), bu
  yüzden seçici `img~.art`'tır; diğerleri `.photo` sınıfını kullanır.
- Fotoğraf üzerindeki kategori rozeti (`.evcat`) görselin altına yerleştirilir
  ve `.evpic::after` gradyanı ile okunabilirlik sağlanır.
