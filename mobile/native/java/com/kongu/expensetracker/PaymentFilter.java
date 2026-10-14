package com.kongu.expensetracker;

import android.content.Context;

import java.util.Locale;
import java.util.regex.Pattern;

/**
 * Cheap on-device checks so that only payment-looking messages ever leave the phone.
 * The server's parser makes the final decision; this filter is deliberately lenient
 * about payments but strict about privacy (who the message is from, and secrets like OTPs).
 */
final class PaymentFilter {
    private PaymentFilter() {}

    private static final Pattern AMOUNT = Pattern.compile(
        "(?i)(?:rs\\.?|inr|\\u20B9)\\s*[\\d,]*\\d|(?:debited|credited)\\s+(?:by|with|for|of)\\s*[\\d,]*\\d");
    private static final Pattern MONEY_WORD = Pattern.compile(
        "(?i)\\b(?:debited|credited|spent|paid|sent|received|deposited|withdrawn|transferred|purchase|refunded)\\b");
    private static final Pattern SECRET = Pattern.compile(
        "(?i)\\b(?:otp|one[- ]time password|verification code|passcode|cvv)\\b");

    static boolean looksLikePayment(String text) {
        if (text == null) return false;
        return AMOUNT.matcher(text).find()
            && MONEY_WORD.matcher(text).find()
            && !SECRET.matcher(text).find();
    }

    /**
     * Bank and payment SMS come from alphanumeric sender IDs such as "VM-HDFCBK".
     * Messages from phone numbers (friends, family) are never read. IDs ending in "-P"
     * are promotional. Demo mode (off by default) accepts any sender so the feature can
     * be tested by texting the phone.
     */
    static boolean isTransactionalSender(Context c, String sender) {
        if (CaptureStore.demoMode(c)) return true;
        if (sender == null) return false;
        String s = sender.trim();
        if (s.isEmpty()) return false;
        boolean hasLetter = false;
        for (int i = 0; i < s.length(); i++) {
            if (Character.isLetter(s.charAt(i))) { hasLetter = true; break; }
        }
        if (!hasLetter) return false;                       // phone numbers / short codes
        return !s.toUpperCase(Locale.ROOT).endsWith("-P");  // promotional header
    }
}
