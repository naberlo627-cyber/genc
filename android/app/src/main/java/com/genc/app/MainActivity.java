package com.genc.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.Settings;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;
import androidx.webkit.WebViewAssetLoader;

/**
 * Genç uygulamasının Android kabuğu.
 *
 * Genc.html, simgeler ve manifest APK içine gömülüdür; WebViewAssetLoader ile
 * https://appassets.androidplatform.net/assets/www/ altından sunulur. Böylece
 * sayfa güvenli bir kaynakta (https) çalışır ve kamera izni isteyebilir.
 */
public class MainActivity extends AppCompatActivity {

    private static final String BASE =
            "https://appassets.androidplatform.net/assets/www/Genc.html";
    private static final int REQ_CAMERA = 4711;
    private static final int REQ_LOCATION = 4712;

    private WebView web;
    private ValueCallback<Uri[]> filePathCallback;
    private PermissionRequest pendingWebPermission;
    private GeolocationPermissions.Callback pendingGeoCallback;
    private String pendingGeoOrigin;

    private final ActivityResultLauncher<Intent> fileChooser =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
                if (filePathCallback == null) return;
                Uri[] uris = null;
                if (result.getResultCode() == RESULT_OK && result.getData() != null) {
                    Intent data = result.getData();
                    if (data.getClipData() != null) {
                        int n = data.getClipData().getItemCount();
                        uris = new Uri[n];
                        for (int i = 0; i < n; i++) uris[i] = data.getClipData().getItemAt(i).getUri();
                    } else if (data.getData() != null) {
                        uris = new Uri[]{data.getData()};
                    }
                }
                filePathCallback.onReceiveValue(uris);
                filePathCallback = null;
            });

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();

        web = new WebView(this);
        setContentView(web);

        // Güncelleme köprüsü: sayfa yeni APK adresini buraya iletir.
        web.addJavascriptInterface(new UpdateBridge(), "GencUpdate");

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        // Varlıklar APK içinde gömülü; WebView'ın eski sürümü önbellekten
        // göstermemesi için önbelleği kapat ve temizle.
        s.setCacheMode(WebSettings.LOAD_NO_CACHE);
        // Konum: WebView geolocation API'si varsayılan olarak kapalıdır.
        s.setGeolocationEnabled(true);
        web.clearCache(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                // Uygulama, APK içinde çalıştığını bilsin: fotoğraflar sunucuya
                // gönderilmez, cihazda saklanır. Güncelleme köprüsü de burada verilir.
                view.evaluateJavascript(
                        "window.GENC_APP=true;"
                        + "window.GENC_INSTALL=function(u){window.GencUpdate.install(u)};",
                        null);
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin,
                                                           GeolocationPermissions.Callback callback) {
                // WebView, geolocation için ayrı izin ister. Uygulama izni varsa
                // doğrudan ver; yoksa Android iznini iste, sonucu beklet.
                if (hasLocationPermission()) {
                    callback.invoke(origin, true, true);
                } else {
                    pendingGeoCallback = callback;
                    pendingGeoOrigin = origin;
                    requestPermissions(new String[]{
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION}, REQ_LOCATION);
                }
            }

            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                // Kamera/mikrofon istekleri yalnızca izin verildiyse karşılanır.
                if (hasCameraPermission()) {
                    request.grant(request.getResources());
                } else {
                    pendingWebPermission = request;
                    requestPermissions(new String[]{Manifest.permission.CAMERA}, REQ_CAMERA);
                }
            }

            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                filePathCallback = callback;
                try {
                    fileChooser.launch(params.createIntent());
                    return true;
                } catch (Exception e) {
                    filePathCallback = null;
                    return false;
                }
            }
        });

        Uri data = getIntent() != null ? getIntent().getData() : null;
        web.loadUrl(data != null ? data.toString() : BASE);
    }

    /* --- uygulama içi güncelleme ---
       Sayfa, yeni APK adresini bu köprüye verir; APK önbelleğe indirilir ve
       sistem kurulum ekranı açılır. İndirme ağ işi olduğu için ayrı iş parçacığında. */
    private class UpdateBridge {
        @JavascriptInterface
        public void install(String url) {
            runOnUiThread(() -> Toast.makeText(MainActivity.this,
                    "Güncelleme indiriliyor…", Toast.LENGTH_SHORT).show());
            new Thread(() -> downloadAndInstall(url)).start();
        }
    }

    private void downloadAndInstall(String url) {
        File dir = new File(getCacheDir(), "updates");
        if (!dir.exists() && !dir.mkdirs()) return;
        File apk = new File(dir, "Genc-update.apk");
        try (InputStream in = openStream(url); FileOutputStream out = new FileOutputStream(apk)) {
            if (in == null) throw new Exception("indirilemedi");
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        } catch (Exception e) {
            runOnUiThread(() -> Toast.makeText(this, "Güncelleme indirilemedi.",
                    Toast.LENGTH_LONG).show());
            return;
        }
        runOnUiThread(() -> promptInstall(apk));
    }

    private InputStream openStream(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(30000);
        c.setInstanceFollowRedirects(true);
        return c.getResponseCode() == 200 ? c.getInputStream() : null;
    }

    private void promptInstall(File apk) {
        // Android 8+ kullanıcıdan "bilinmeyen uygulama kurma" izni ister.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !getPackageManager().canRequestPackageInstalls()) {
            Toast.makeText(this, "Kurulum için izin ver, sonra tekrar dene.", Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName())));
            return;
        }
        Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fileprovider", apk);
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setDataAndType(uri, "application/vnd.android.package-archive");
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(i);
    }

    private boolean hasCameraPermission() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED;
    }

    private boolean hasLocationPermission() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
        if (code == REQ_LOCATION && pendingGeoCallback != null) {
            boolean granted = false;
            for (int r : results) if (r == PackageManager.PERMISSION_GRANTED) granted = true;
            pendingGeoCallback.invoke(pendingGeoOrigin, granted, false);
            pendingGeoCallback = null;
            pendingGeoOrigin = null;
            if (!granted) {
                Toast.makeText(this, "Konum izni verilmedi. Ayarlardan açabilirsin.",
                        Toast.LENGTH_LONG).show();
            }
            return;
        }
        if (code != REQ_CAMERA || pendingWebPermission == null) return;
        if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) {
            pendingWebPermission.grant(pendingWebPermission.getResources());
        } else {
            pendingWebPermission.deny();
        }
        pendingWebPermission = null;
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        // Uygulama açıkken kısayola dokunulursa ilgili görünüme git.
        if (intent != null && intent.getData() != null) {
            web.loadUrl(intent.getData().toString());
        }
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
