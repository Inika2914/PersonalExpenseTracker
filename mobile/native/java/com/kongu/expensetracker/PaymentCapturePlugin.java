package com.kongu.expensetracker;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.os.Build;
import android.provider.Settings;
import android.provider.Telephony;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;
import androidx.work.WorkManager;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

/**
 * JavaScript-facing side of the capture feature. The web pages (static/js/native.js and
 * capture.js) call these methods through Capacitor.Plugins.PaymentCapture.
 *
 * The capture itself does NOT depend on this plugin or on the WebView being open:
 * SmsReceiver and PaymentNotificationListener are started by Android and upload directly.
 */
@CapacitorPlugin(
    name = "PaymentCapture",
    permissions = {
        @Permission(alias = "sms", strings = { Manifest.permission.RECEIVE_SMS, Manifest.permission.READ_SMS }),
        @Permission(alias = "postNotifications", strings = { "android.permission.POST_NOTIFICATIONS" })
    }
)
public class PaymentCapturePlugin extends Plugin {
    private static final String CHANNEL_ID = "demo_payment_alerts";
    private static final int MAX_INBOX_ROWS = 500;
    private static final long DAY_MS = 24L * 60L * 60L * 1000L;

    // ------------------------------------------------------------ linking
    @PluginMethod
    public void configure(PluginCall call) {
        String serverUrl = call.getString("serverUrl");
        String token = call.getString("token");
        if (serverUrl == null || serverUrl.isEmpty() || token == null || token.isEmpty()) {
            call.reject("serverUrl and token are required");
            return;
        }
        long userId = call.getData().optLong("userId", 0L);
        String userName = call.getString("userName", "");
        CaptureStore.saveConfig(getContext(), serverUrl, token, userId, userName);
        call.resolve(buildStatus());
    }

    @PluginMethod
    public void clear(PluginCall call) {
        CaptureStore.clear(getContext());
        WorkManager.getInstance(getContext().getApplicationContext()).cancelAllWork();
        call.resolve(buildStatus());
    }

    @PluginMethod
    public void getStatus(PluginCall call) {
        call.resolve(buildStatus());
    }

    // ------------------------------------------------------------ permissions
    @PluginMethod
    public void requestSmsPermissions(PluginCall call) {
        if (hasSmsPermission(getContext())) {
            call.resolve(buildStatus());
            return;
        }
        requestPermissionForAlias("sms", call, "smsPermsCallback");
    }

    @PermissionCallback
    private void smsPermsCallback(PluginCall call) {
        call.resolve(buildStatus());
    }

    @PluginMethod
    public void requestNotificationPermission(PluginCall call) {
        if (Build.VERSION.SDK_INT < 33 || canPostNotifications(getContext())) {
            call.resolve(buildStatus());
            return;
        }
        requestPermissionForAlias("postNotifications", call, "notifPermsCallback");
    }

    @PermissionCallback
    private void notifPermsCallback(PluginCall call) {
        call.resolve(buildStatus());
    }

    /** Opens Android's "Notification access" screen, where the user switches this app on. */
    @PluginMethod
    public void openNotificationAccessSettings(PluginCall call) {
        try {
            Intent intent = new Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS);
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception e) {
            call.reject("Could not open notification access settings: " + e.getMessage());
        }
    }

    @PluginMethod
    public void setDemoMode(PluginCall call) {
        Boolean enabled = call.getBoolean("enabled", false);
        CaptureStore.setDemoMode(getContext(), enabled != null && enabled);
        call.resolve(buildStatus());
    }

    // ------------------------------------------------------------ demo: simulated UPI notification
    @SuppressLint("MissingPermission")
    @PluginMethod
    public void simulateUpiNotification(PluginCall call) {
        String text = call.getString("text");
        String title = call.getString("title", "Google Pay");
        if (text == null || text.trim().isEmpty()) {
            call.reject("text is required");
            return;
        }
        Context c = getContext();
        if (!canPostNotifications(c)) {
            call.reject("Notifications are not allowed for this app - tap \"Allow demo notifications\" first");
            return;
        }
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "Payment alerts (demo)", NotificationManager.IMPORTANCE_DEFAULT);
            NotificationManager nm = c.getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
        NotificationCompat.Builder builder = new NotificationCompat.Builder(c, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText(text)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true);
        NotificationManagerCompat.from(c).notify((int) (System.currentTimeMillis() % Integer.MAX_VALUE), builder.build());
        call.resolve();
    }

    // ------------------------------------------------------------ backfill from the SMS inbox
    @PluginMethod
    public void syncInbox(PluginCall call) {
        Context c = getContext();
        if (!hasSmsPermission(c)) {
            call.reject("SMS permission not granted");
            return;
        }
        if (!CaptureStore.isConfigured(c)) {
            call.reject("This phone is not linked to an account yet");
            return;
        }
        Integer requested = call.getInt("days", 30);
        int days = (requested == null || requested < 1) ? 30 : Math.min(requested, 365);
        long since = System.currentTimeMillis() - days * DAY_MS;

        int scanned = 0;
        int queued = 0;
        Cursor cursor = null;
        try {
            cursor = c.getContentResolver().query(
                Telephony.Sms.Inbox.CONTENT_URI,
                new String[] { Telephony.Sms.ADDRESS, Telephony.Sms.BODY, Telephony.Sms.DATE },
                Telephony.Sms.DATE + " >= ?",
                new String[] { String.valueOf(since) },
                Telephony.Sms.DATE + " DESC");
            if (cursor != null) {
                int iAddress = cursor.getColumnIndexOrThrow(Telephony.Sms.ADDRESS);
                int iBody = cursor.getColumnIndexOrThrow(Telephony.Sms.BODY);
                int iDate = cursor.getColumnIndexOrThrow(Telephony.Sms.DATE);
                while (scanned < MAX_INBOX_ROWS && cursor.moveToNext()) {
                    scanned++;
                    String address = cursor.getString(iAddress);
                    String body = cursor.getString(iBody);
                    long date = cursor.getLong(iDate);
                    if (!PaymentFilter.isTransactionalSender(c, address)) continue;
                    if (!PaymentFilter.looksLikePayment(body)) continue;
                    UploadWorker.enqueue(c, body, "sms", address, null, date);
                    queued++;
                }
            }
        } catch (Exception e) {
            call.reject("Could not read the SMS inbox: " + e.getMessage());
            return;
        } finally {
            if (cursor != null) cursor.close();
        }
        JSObject result = new JSObject();
        result.put("scanned", scanned);
        result.put("queued", queued);
        call.resolve(result);
    }

    // ------------------------------------------------------------ status
    private JSObject buildStatus() {
        Context c = getContext();
        JSObject o = new JSObject();
        o.put("native", true);
        o.put("configured", CaptureStore.isConfigured(c));
        o.put("serverUrl", CaptureStore.serverUrl(c));
        o.put("userId", CaptureStore.userId(c));
        o.put("userName", CaptureStore.userName(c));
        o.put("tokenInvalid", CaptureStore.tokenInvalid(c));
        o.put("demoMode", CaptureStore.demoMode(c));
        o.put("smsPermission", hasSmsPermission(c));
        o.put("notificationAccess", isNotificationAccessEnabled(c));
        o.put("canPostNotifications", canPostNotifications(c));
        o.put("lastCaptureAt", CaptureStore.lastCaptureAt(c));
        o.put("lastCaptureSource", CaptureStore.lastCaptureSource(c));
        o.put("lastUpload", CaptureStore.lastUpload(c));
        return o;
    }

    private static boolean hasSmsPermission(Context c) {
        return ContextCompat.checkSelfPermission(c, Manifest.permission.RECEIVE_SMS) == PackageManager.PERMISSION_GRANTED
            && ContextCompat.checkSelfPermission(c, Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED;
    }

    private static boolean isNotificationAccessEnabled(Context c) {
        return NotificationManagerCompat.getEnabledListenerPackages(c).contains(c.getPackageName());
    }

    private static boolean canPostNotifications(Context c) {
        return NotificationManagerCompat.from(c).areNotificationsEnabled();
    }
}
