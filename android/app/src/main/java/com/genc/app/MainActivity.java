package com.genc.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.ContextCompat;
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

    private WebView web;
    private ValueCallback<Uri[]> filePathCallback;
    private PermissionRequest pendingWebPermission;

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
        web.clearCache(true);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                // Uygulama, APK içinde çalıştığını bilsin: fotoğraflar sunucuya
                // gönderilmez, cihazda saklanır.
                view.evaluateJavascript("window.GENC_APP=true;", null);
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
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

    private boolean hasCameraPermission() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA)
                == PackageManager.PERMISSION_GRANTED;
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(code, permissions, results);
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
