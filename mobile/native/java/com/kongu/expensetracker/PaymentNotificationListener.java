package com.kongu.expensetracker;

import android.app.Notification;
import android.content.Context;
import android.os.Bundle;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * Reads notifications posted by UPI / payment apps (the user must enable "Notification access"
 * for this app once in Android settings). Notifications from every other app - chat apps,
 * email, etc. - are ignored immediately and never inspected.
 */
public class PaymentNotificationListener extends NotificationListenerService {

    /** Payment apps whose notifications are read. Add more package names here if needed. */
    private static final Set<String> PAYMENT_APPS = new HashSet<>(Arrays.asList(
        "com.google.android.apps.nbu.paisa.user",   // Google Pay
        "com.phonepe.app",                          // PhonePe
        "net.one97.paytm",                          // Paytm
        "in.org.npci.upiapp",                       // BHIM
        "com.dreamplug.androidapp",                 // CRED
        "com.mobikwik_new",                         // MobiKwik
        "com.freecharge.android"                    // Freecharge
    ));

    // Apps re-post the same notification when they update it; ignore repeats within a minute.
    private static final Map<String, Long> RECENT = new LinkedHashMap<String, Long>() {
        @Override
        protected boolean removeEldestEntry(Map.Entry<String, Long> eldest) {
            return size() > 50;
        }
    };

    private static synchronized boolean seenRecently(String key, long now) {
        Long t = RECENT.get(key);
        if (t != null && now - t < 60000L) return true;
        RECENT.put(key, now);
        return false;
    }

    @Override
    public void onNotificationPosted(StatusBarNotification sbn) {
        try {
            if (sbn == null) return;
            Context c = getApplicationContext();
            if (!CaptureStore.isConfigured(c)) return;

            String pkg = sbn.getPackageName();
            // our own package is allowed so the in-app "Simulate UPI notification" demo works
            if (!PAYMENT_APPS.contains(pkg) && !c.getPackageName().equals(pkg)) return;

            Notification n = sbn.getNotification();
            if (n == null || n.extras == null) return;
            if ((n.flags & Notification.FLAG_GROUP_SUMMARY) != 0) return;

            Bundle extras = n.extras;
            String title = text(extras.getCharSequence(Notification.EXTRA_TITLE));
            String body = text(extras.getCharSequence(Notification.EXTRA_BIG_TEXT));
            if (body.isEmpty()) body = text(extras.getCharSequence(Notification.EXTRA_TEXT));
            String full = (title + " " + body).trim();

            if (!PaymentFilter.looksLikePayment(full)) return;

            long now = System.currentTimeMillis();
            if (seenRecently(pkg + "|" + full, now)) return;

            CaptureStore.recordCapture(c, "Notification from " + pkg);
            UploadWorker.enqueue(c, full, "notification", null, pkg, now);
        } catch (Exception ignored) {
            // a listener must never crash - Android would unbind it
        }
    }

    private static String text(CharSequence cs) {
        return cs == null ? "" : cs.toString();
    }
}
