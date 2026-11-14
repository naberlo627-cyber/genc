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
- `server.py` — önizleme + `/upload` dosya yükleme ucu (port 12000).
- `yuklenenler/` — yüklenen dosyalar (sürüm kontrolüne girmez).
- `tools/qr.js` — QR kaynak kodu (Genc.html'e gömülmeden önceki hali).
- `tools/generate_icons.py` — simge üretici.
- `tools/generate_shortcuts.py` — kısayol simgesi üretici (her kısayola kendi
  glifi; Android ve masaüstünde aynı ikon tekrar etmesin).

## Geliştirme komutları

```bash
python server.py            # http://localhost:12000 önizleme
node --check sw.js          # servis çalışanı sözdizimi
node --check tools/qr.js    # QR modülü sözdizimi
```

JS sözdizimini denetlemek için `<script>` bloklarını ayırıp `node --check`
çalıştırın; tarayıcı testi için herkese açık önizleme adresini kullanın.

## Notlar

- `localStorage` anahtarı: `genc.v1` (profil, biletler, kartlar, tema).
- Bilet QR yükü: `GENÇ|etkinlikId|kod|adet|tür|koltuklar` (EC seviyesi M).
- Uygulama kısayolu derin bağlantıları: `?git=yakin|videolar|ara|biletlerim|profil|bilet-al`.
  `git` parametresi çalıştıktan sonra adres çubuğundan silinir (yenilemede tekrar
  tetiklenmesin). Kullanıcı giriş yapmamışsa kısayol `pendingShortcut` olarak
  saklanır ve onboarding bitince uygulanır.
- Paylaşılan bilet bağlantısı: `?bilet=KOD`.
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
