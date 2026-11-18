/* Genç - çevrimdışı desteği ve hızlı açılış için servis çalışanı. */
var CACHE = "genc-v51";
var ASSETS = [
  "./",
  "./Genc.html",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/maskable-512.png",
  "./icons/apple-touch-icon.png",
  "./icons/favicon-32.png",
  "./icons/shortcut-bilet-al.png",
  "./icons/shortcut-hafta.png",
  "./icons/shortcut-yakin.png",
  "./icons/shortcut-videolar.png",
  "./icons/shortcut-ara.png",
  "./icons/shortcut-biletlerim.png",
  "./icons/shortcut-bildirimler.png",
  "./icons/shortcut-hoslandiklarim.png",
  "./icons/shortcut-profil.png",
  "./img/cat-konser.jpg",
  "./img/cat-sinema.jpg",
  "./img/cat-tiyatro.jpg",
  "./img/cat-stand-up.jpg",
  "./img/cat-festival.jpg",
  "./img/cat-cocuk-etkinlikleri.jpg",
  "./img/cat-gezi-turu.jpg",
  "./img/cat-spor.jpg",
  "./img/cat-sergi.jpg",
  "./img/cat-dans.jpg",
  "./img/cat-opera-ve-bale.jpg",
  "./img/cat-acik-hava.jpg",
  "./img/vid-caz.jpg",
  "./img/vid-celik.jpg",
  "./img/vid-efes.jpg",
  "./img/vid-gulmece.jpg",
  "./img/vid-kardelen.jpg",
  "./img/vid-kaz.jpg",
  "./img/vid-kugu.jpg",
  "./img/vid-minik.jpg",
  "./img/vid-sessiz.jpg",
  "./img/vid-tango.jpg",
  "./img/vid-yaz.jpg",
  "./img/venue-istinyeart-100-performans-arena.jpg"
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) { return c.addAll(ASSETS); }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) { if (k !== CACHE) return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

/* Uygulama sayfası ağdan tazelenir; çevrimdışıyken önbellekten açılır. */
function networkFirst(req) {
  return fetch(req).then(function (res) {
    if (res && res.ok && res.type === "basic") {
      var copy = res.clone();
      caches.open(CACHE).then(function (c) { c.put("./Genc.html", copy); });
    }
    return res;
  }).catch(function () {
    return caches.match("./Genc.html").then(function (hit) {
      return hit || caches.match("./");
    });
  });
}

/* Simgeler ve manifest önbellekten gelir, arka planda tazelenir. */
function staleWhileRevalidate(req) {
  return caches.match(req).then(function (hit) {
    var net = fetch(req).then(function (res) {
      if (res && res.ok) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
      }
      return res;
    }).catch(function () { return hit; });
    return hit || net;
  });
}

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  var path = new URL(req.url).pathname;
  // Güncelleme denetimi, uygulama verisi ve APK her zaman ağdan gelir;
  // önbellek sürümü gizlemesin.
  if (/(^|\/)version\.json$/.test(path) || /\.apk$/.test(path) || /(^|\/)data\/events\.json$/.test(path)) {
    e.respondWith(fetch(req));
    return;
  }
  // Canlı durum her zaman ağdan denenir; hata olursa uygulama beklemeye geçer.
  if (/(^|\/)live$/.test(path)) {
    e.respondWith(fetch(req).catch(function () { return new Response("{}", { headers: { "Content-Type": "application/json" } }); }));
    return;
  }
  if (req.mode === "navigate" || /(^|\/)Genc\.html$/.test(path)) {
    e.respondWith(networkFirst(req));
    return;
  }
  e.respondWith(staleWhileRevalidate(req));
});

/* Bilet hatırlatıcısı: bildirime dokununca uygulamayı ilgili bilete aç.
   Uygulama zaten açıksa var olan pencereye mesaj gönderir ve öne alır. */
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var data = e.notification.data || {};
  var target = "./Genc.html" + (data.ticket ? "?bilet=" + encodeURIComponent(data.ticket) : "");
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (list) {
      for (var i = 0; i < list.length; i++) {
        var c = list[i];
        if (c.url.indexOf("Genc.html") !== -1 && "focus" in c) {
          c.postMessage({ type: "notify-open", ticket: data.ticket || "" });
          return c.focus();
        }
      }
      if (self.clients.openWindow) return self.clients.openWindow(target);
    })
  );
});
