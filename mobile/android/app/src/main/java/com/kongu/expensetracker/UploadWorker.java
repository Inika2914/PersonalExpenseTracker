package com.kongu.expensetracker;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.work.BackoffPolicy;
import androidx.work.Constraints;
import androidx.work.Data;
import androidx.work.NetworkType;
import androidx.work.OneTimeWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

/**
 * Uploads ONE captured message to the Flask server.
 *
 * WorkManager is used (instead of a plain thread) because it survives the app being killed
 * and retries automatically when the phone is offline - so a payment SMS received on the
 * metro is still saved once the network comes back.
 */
public class UploadWorker extends Worker {
    static final String K_TEXT = "raw_text";
    static final String K_SOURCE = "source";
    static final String K_SENDER = "sender";
    static final String K_PACKAGE = "package";
    static final String K_TIME = "received_at";

    private static final int MAX_ATTEMPTS = 8;
    private static final int MAX_TEXT = 1500;

    public UploadWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    /** Queue one message for upload. */
    static void enqueue(Context c, String text, String source, String sender, String pkg, long receivedAtMs) {
        if (text == null || text.trim().isEmpty()) return;
        if (text.length() > MAX_TEXT) text = text.substring(0, MAX_TEXT);

        Data.Builder data = new Data.Builder()
            .putString(K_TEXT, text)
            .putString(K_SOURCE, source)
            .putLong(K_TIME, receivedAtMs);
        if (sender != null) data.putString(K_SENDER, sender);
        if (pkg != null) data.putString(K_PACKAGE, pkg);

        Constraints needsNetwork = new Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED).build();

        OneTimeWorkRequest request = new OneTimeWorkRequest.Builder(UploadWorker.class)
            .setConstraints(needsNetwork)
            .setInputData(data.build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build();
        WorkManager.getInstance(c.getApplicationContext()).enqueue(request);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context c = getApplicationContext();
        if (!CaptureStore.isConfigured(c)) return Result.failure();   // phone was unlinked meanwhile

        String text = getInputData().getString(K_TEXT);
        if (text == null || text.trim().isEmpty()) return Result.failure();

        HttpURLConnection conn = null;
        try {
            JSONObject body = new JSONObject();
            body.put("raw_text", text);
            body.put("source", getInputData().getString(K_SOURCE));
            String sender = getInputData().getString(K_SENDER);
            if (sender != null) body.put("sender", sender);
            String pkg = getInputData().getString(K_PACKAGE);
            if (pkg != null) body.put("package", pkg);
            long ts = getInputData().getLong(K_TIME, 0L);
            if (ts > 0) body.put("received_at", ts);
            byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);

            URL url = new URL(CaptureStore.serverUrl(c) + "/api/transactions/raw");
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(15000);
            conn.setReadTimeout(20000);
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setRequestProperty("Authorization", "Bearer " + CaptureStore.token(c));
            conn.setFixedLengthStreamingMode(payload.length);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(payload);
            }

            int code = conn.getResponseCode();
            String response = readAll(code >= 400 ? conn.getErrorStream() : conn.getInputStream());

            if (code >= 200 && code < 300) {
                String status = new JSONObject(response).optString("status", "ok");
                CaptureStore.recordUpload(c, describe(status));
                return Result.success();
            }
            if (code == 401 || code == 403) {                // token revoked or wrong server
                CaptureStore.markTokenInvalid(c, true);
                CaptureStore.recordUpload(c, "Rejected by server - re-link this phone");
                return Result.failure();
            }
            if (code >= 500 || code == 408 || code == 429) {
                return retryOrGiveUp(c, "Server busy (" + code + ") - will retry");
            }
            CaptureStore.recordUpload(c, "Rejected (" + code + ")");
            return Result.failure();
        } catch (IOException e) {
            return retryOrGiveUp(c, "Offline or server unreachable - will retry");
        } catch (Exception e) {
            CaptureStore.recordUpload(c, "Error: " + e.getClass().getSimpleName());
            return Result.failure();
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private Result retryOrGiveUp(Context c, String message) {
        if (getRunAttemptCount() >= MAX_ATTEMPTS) {
            CaptureStore.recordUpload(c, "Gave up after " + MAX_ATTEMPTS + " attempts");
            return Result.failure();
        }
        CaptureStore.recordUpload(c, message);
        return Result.retry();
    }

    private static String describe(String status) {
        switch (status) {
            case "created":   return "Saved as a new transaction";
            case "merged":    return "Merged with the same payment (SMS + notification)";
            case "duplicate": return "Already saved earlier";
            case "ignored":   return "Ignored (not a completed payment)";
            default:          return status;
        }
    }

    private static String readAll(InputStream in) throws IOException {
        if (in == null) return "";
        try (BufferedReader r = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            StringBuilder sb = new StringBuilder();
            String line;
            while ((line = r.readLine()) != null) sb.append(line);
            return sb.toString();
        }
    }
}
