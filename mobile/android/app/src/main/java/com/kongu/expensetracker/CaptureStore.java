package com.kongu.expensetracker;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * Small private key-value store shared by the plugin, the SMS receiver, the notification
 * listener and the upload worker (they run in different components, so they cannot share objects).
 */
final class CaptureStore {
    private static final String PREFS = "payment_capture";

    private CaptureStore() {}

    private static SharedPreferences p(Context c) {
        return c.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static void saveConfig(Context c, String serverUrl, String token, long userId, String userName) {
        String url = serverUrl == null ? "" : serverUrl.trim();
        while (url.endsWith("/")) url = url.substring(0, url.length() - 1);
        p(c).edit()
            .putString("serverUrl", url)
            .putString("token", token == null ? "" : token)
            .putLong("userId", userId)
            .putString("userName", userName == null ? "" : userName)
            .putBoolean("tokenInvalid", false)
            .apply();
    }

    static void clear(Context c) {
        p(c).edit().remove("serverUrl").remove("token").remove("userId")
            .remove("userName").remove("tokenInvalid").apply();
    }

    static String serverUrl(Context c) { return p(c).getString("serverUrl", ""); }
    static String token(Context c) { return p(c).getString("token", ""); }
    static long userId(Context c) { return p(c).getLong("userId", 0L); }
    static String userName(Context c) { return p(c).getString("userName", ""); }

    static boolean isConfigured(Context c) {
        return !serverUrl(c).isEmpty() && !token(c).isEmpty();
    }

    static boolean tokenInvalid(Context c) { return p(c).getBoolean("tokenInvalid", false); }
    static void markTokenInvalid(Context c, boolean invalid) {
        p(c).edit().putBoolean("tokenInvalid", invalid).apply();
    }

    static boolean demoMode(Context c) { return p(c).getBoolean("demoMode", false); }
    static void setDemoMode(Context c, boolean on) { p(c).edit().putBoolean("demoMode", on).apply(); }

    static void recordCapture(Context c, String source) {
        p(c).edit().putLong("lastCaptureAt", System.currentTimeMillis())
            .putString("lastCaptureSource", source).apply();
    }
    static long lastCaptureAt(Context c) { return p(c).getLong("lastCaptureAt", 0L); }
    static String lastCaptureSource(Context c) { return p(c).getString("lastCaptureSource", ""); }

    static void recordUpload(Context c, String text) {
        p(c).edit().putString("lastUpload", text).apply();
    }
    static String lastUpload(Context c) { return p(c).getString("lastUpload", ""); }
}
