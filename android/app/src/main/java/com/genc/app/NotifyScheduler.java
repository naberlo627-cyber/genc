package com.genc.app;

import android.app.AlarmManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * Bilet hatırlatıcılarının yerel bildirim tarafı.
 *
 * Web tarafı her hatırlatıcı için {@link #schedule} çağırır; burada AlarmManager
 * ile tam zamanına bir alarm kurulur. Alarm çalınca {@link Receiver} bildirimi
 * gösterir. Böylece uygulama kapalı olsa bile hatırlatıcı çalışır.
 *
 * Kurulu alarmlar küçük bir JSON listesinde saklanır (uygulama verisi); uygulama
 * her açılışta listeyi yeniden kurar (cihaz yeniden başlatılınca alarmlar düşer).
 */
final class NotifyScheduler {

    static final String CHANNEL_ID = "genc_bilet";
    static final String PREFS = "genc_notify";
    static final String KEY_ITEMS = "items";

    private NotifyScheduler() {}

    /* --- kanal --- */
    static void ensureChannel(Context ctx) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager nm = ctx.getSystemService(NotificationManager.class);
        if (nm == null || nm.getNotificationChannel(CHANNEL_ID) != null) return;
        NotificationChannel ch = new NotificationChannel(
                CHANNEL_ID, "Bilet hatırlatıcıları", NotificationManager.IMPORTANCE_HIGH);
        ch.setDescription("Bilet aldığın etkinlikler yaklaşınca haber verir.");
        nm.createNotificationChannel(ch);
    }

    /* --- alarm --- */
    static void schedule(Context ctx, String id, String title, String venue, long atMs) {
        ensureChannel(ctx);
        AlarmManager am = ctx.getSystemService(AlarmManager.class);
        if (am == null) return;
        PendingIntent pi = pending(ctx, id, title, venue, atMs, PendingIntent.FLAG_UPDATE_CURRENT);
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, atMs, pi);
            } else {
                am.setExact(AlarmManager.RTC_WAKEUP, atMs, pi);
            }
        } catch (SecurityException e) {
            // Tam zamanlı alarm izni yoksa yaklaşık zamanlıya düş.
            am.set(AlarmManager.RTC_WAKEUP, atMs, pi);
        }
        store(ctx, id, title, venue, atMs, true);
    }

    static void cancel(Context ctx, String id) {
        AlarmManager am = ctx.getSystemService(AlarmManager.class);
        if (am != null) {
            PendingIntent pi = pending(ctx, id, null, null, 0, PendingIntent.FLAG_NO_CREATE);
            if (pi != null) am.cancel(pi);
        }
        store(ctx, id, null, null, 0, false);
    }

    /* Bildirim dokunulunca uygulamayı ilgili bilete açar. */
    private static PendingIntent pending(Context ctx, String id, String title, String venue,
                                        long atMs, int baseFlags) {
        Intent i = new Intent(ctx, Receiver.class);
        i.putExtra("id", id);
        if (title != null) i.putExtra("title", title);
        if (venue != null) i.putExtra("venue", venue);
        int flags = baseFlags;
        if (baseFlags != PendingIntent.FLAG_NO_CREATE) flags |= PendingIntent.FLAG_IMMUTABLE;
        return PendingIntent.getBroadcast(ctx, id.hashCode(), i, flags);
    }

    /* --- kurulu alarm listesi (JSON) --- */
    private static synchronized void store(Context ctx, String id, String title, String venue,
                                           long atMs, boolean add) {
        android.content.SharedPreferences prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        JSONArray arr;
        try { arr = new JSONArray(prefs.getString(KEY_ITEMS, "[]")); }
        catch (Exception e) { arr = new JSONArray(); }
        List<JSONObject> keep = new ArrayList<>();
        for (int i = 0; i < arr.length(); i++) {
            JSONObject o = arr.optJSONObject(i);
            if (o != null && !id.equals(o.optString("id"))) keep.add(o);
        }
        if (add) {
            try {
                JSONObject o = new JSONObject();
                o.put("id", id);
                o.put("title", title);
                o.put("venue", venue);
                o.put("at", atMs);
                keep.add(o);
            } catch (Exception ignored) {}
        }
        JSONArray out = new JSONArray();
        for (JSONObject o : keep) out.put(o);
        prefs.edit().putString(KEY_ITEMS, out.toString()).apply();
    }

    /* --- bildirim gösterimi --- */
    static void show(Context ctx, String id, String title, String venue) {
        ensureChannel(ctx);
        Intent open = new Intent(ctx, MainActivity.class);
        open.setData(android.net.Uri.parse(
                "https://appassets.androidplatform.net/assets/www/Genc.html?bilet=" + id));
        open.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
        int piFlags = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) piFlags |= PendingIntent.FLAG_IMMUTABLE;
        PendingIntent content = PendingIntent.getActivity(ctx, id.hashCode(), open, piFlags);

        String body = (title == null ? "Biletin yaklaşıyor" : title)
                + (venue != null && !venue.isEmpty() ? " · " + venue : "");
        Notification n = new NotificationCompat.Builder(ctx, CHANNEL_ID)
                .setSmallIcon(R.drawable.ic_notify)
                .setContentTitle("Biletin yaklaşıyor 🎟️")
                .setContentText(body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
                .setAutoCancel(true)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setContentIntent(content)
                .build();
        try {
            NotificationManagerCompat.from(ctx).notify(id.hashCode(), n);
        } catch (SecurityException ignored) {
            // POST_NOTIFICATIONS verilmemişse sessizce geç.
        }
    }

    /** Alarm çalınca bildirimi gösterir. */
    public static class Receiver extends BroadcastReceiver {
        @Override
        public void onReceive(Context ctx, Intent intent) {
            String id = intent.getStringExtra("id");
            if (id == null) return;
            show(ctx, id, intent.getStringExtra("title"), intent.getStringExtra("venue"));
            store(ctx, id, null, null, 0, false);
        }
    }
}
