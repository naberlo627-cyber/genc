# Genç veri yenileme — günlük zamanlanmış çalıştırma.
#
# Bu dosya iki yol sunar:
#   A) systemd (önerilir, Linux sunucu): refresh/systemd/ altındaki servis + timer
#   B) cron (her yerde çalışır): aşağıdaki crontab satırı
#
# Yenileme her gün 04:30'da (Türkiye saati) çalışır. Gece saatleri seçildi ki
# kaynak sitelerin yoğun olmadığı bir anda toplama yapılsın.

## A) systemd kurulumu (önerilen)
#   sudo cp refresh/systemd/genc-refresh.service /etc/systemd/system/
#   sudo cp refresh/systemd/genc-refresh.timer   /etc/systemd/system/
#   sudo systemctl daemon-reload
#   sudo systemctl enable --now genc-refresh.timer
#   systemctl list-timers genc-refresh.timer      # sonraki çalışmayı göster
#   journalctl -u genc-refresh.service -n 50      # son çalışmanın günlüğü
#
# systemd avantajı: makine kapalıysa/uykudaysa kaçan çalışmayı telafi eder
# (Persistent=true), çöken çalışmayı yeniden dener ve günlükleri toplar.

## B) cron kurulumu
#   crontab -e
#   # Genç veri yenileme (her gün 04:30)
#   30 4 * * * cd /workspace/project && ./refresh/run.sh >> refresh/logs/cron.log 2>&1
#
# Not: cron, betiğin ortam değişkenlerini görmez. Python ve ağ erişimi
# gerekiyorsa tam yol kullanın (örn. PYTHON=/usr/bin/python3 ./refresh/run.sh).

## Veri yenilemesi sonrası ne olur?
#   data/tickets.json   → kaynak veri (girintili, okunabilir)
#   data/events.json    → uygulamanın indirdiği kompakt veri (yayın)
#   data/refresh_status.json → son çalışma durumu (izleme için)
#   Genc.html           → gömülü yedek veri (çevrimdışı/APK için)
#   sw.js               → önbellek sürümü artar (tarayıcı yeni veriyi görsün)
#   version.json        → yayın sürümü artar (güncelleme şeridi tetiklenir)
#
# Uygulama açılışta data/events.json'u çeker; bu yüzden yeni veri için APK'yı
# yeniden derlemek GEREKMEZ. Yalnızca WebView/APK içindeki gömülü yedek
# güncellensin isteniyorsa android/build-apk.sh çalıştırılır.
