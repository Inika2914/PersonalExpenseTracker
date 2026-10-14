package com.kongu.expensetracker;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Receives every incoming SMS (the system wakes this receiver even when the app is closed).
 * Only messages from bank-style sender IDs that look like a payment are queued for upload.
 */
public class SmsReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(intent.getAction())) return;
        if (!CaptureStore.isConfigured(context)) return;          // phone not linked yet

        SmsMessage[] parts = Telephony.Sms.Intents.getMessagesFromIntent(intent);
        if (parts == null || parts.length == 0) return;

        // A long SMS arrives as several parts - stitch the parts of each sender together.
        Map<String, StringBuilder> bySender = new LinkedHashMap<>();
        for (SmsMessage part : parts) {
            if (part == null) continue;
            String sender = part.getOriginatingAddress();
            if (sender == null) continue;
            StringBuilder sb = bySender.get(sender);
            if (sb == null) {
                sb = new StringBuilder();
                bySender.put(sender, sb);
            }
            String body = part.getMessageBody();
            if (body != null) sb.append(body);
        }

        long now = System.currentTimeMillis();
        for (Map.Entry<String, StringBuilder> entry : bySender.entrySet()) {
            String sender = entry.getKey();
            String text = entry.getValue().toString();
            if (!PaymentFilter.isTransactionalSender(context, sender)) continue;
            if (!PaymentFilter.looksLikePayment(text)) continue;
            CaptureStore.recordCapture(context, "SMS from " + sender);
            UploadWorker.enqueue(context, text, "sms", sender, null, now);
        }
    }
}
