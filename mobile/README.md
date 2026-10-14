# Personal Expense Tracker - Android app

This folder turns the Flask web app into a real Android app that **reads actual bank SMS and
UPI-app notifications in the background** and saves them as transactions.

```
 Android phone                                              Laptop / server
 ┌──────────────────────────────────────┐                   ┌──────────────────────┐
 │ Bank SMS ──► SmsReceiver ────────┐   │   HTTPS/HTTP      │ Flask                │
 │ GPay/PhonePe ► NotificationListener ─┼─► UploadWorker ──►│  POST /api/transactions/raw
 │                                  │   │  (+ device token) │   parser → categorizer
 │ WebView = your Flask web pages   │   │                   │   de-duplicate → SQLite
 └──────────────────────────────────────┘                   └──────────────────────┘
```

* The screens you see are the **same Flask web pages** (shown inside the app, no browser bar).
* Capture is **native Android code** (browsers are not allowed to read SMS or notifications).
  It runs even when the app is closed, and retries automatically when the phone is offline.

## What you need (once)

| Tool | Notes |
|---|---|
| Node.js 20 or newer | check with `node -v` |
| Android Studio (2024.2 "Ladybug" or newer) | installs the Android SDK and JDK 21 |
| An Android phone with **USB debugging** on (or an emulator) | Settings → About phone → tap *Build number* 7 times → Developer options → USB debugging |

## Step 1 - run the Flask server so the phone can reach it

```powershell
cd expense_tracker
venv\Scripts\activate
python app.py
```

* The new `device_tokens` table is created automatically on start-up - nothing to migrate.
* The phone and the computer must be on the **same Wi-Fi**.
* Find the computer's address with `ipconfig` (the *IPv4 Address*, e.g. `192.168.1.8`).
* If the phone cannot connect, allow Python through Windows Firewall (run PowerShell **as administrator** once):

```powershell
New-NetFirewallRule -DisplayName "Flask 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private
```

## Step 2 - tell the app where the server is

Open `mobile/capacitor.config.json` and change one line:

```json
"url": "http://192.168.1.8:5000"
```

* Real phone → your computer's IP address (as above).
* Android **emulator** → leave it as `http://10.0.2.2:5000` (that is the emulator's name for your computer).
* Server hosted online (Render, PythonAnywhere...) → use its `https://...` address.

## Step 3 - generate the Android project (one command)

```powershell
cd mobile
npm run setup
```

This installs Capacitor, creates the `android/` project, adds the SMS / notification code and
permissions, creates the launcher icons + splash screens from the logo, and syncs everything.
(Run it **once**. Afterwards use `npm run sync` after changing `capacitor.config.json`.)

If you prefer to see each step:

```powershell
npm install
npx cap add android
node scripts/patch-android.js
npm run assets
npx cap sync android
```

## Step 4 - run it on the phone

```powershell
npx cap open android
```

Android Studio opens → wait for Gradle to finish → pick your phone at the top → press the green ▶ **Run**.

## Step 5 - switch capture on (inside the app)

1. Register / log in. The app **links itself** to your account automatically.
2. Open **Phone Capture** in the menu, then:
   * **Allow SMS access** → tap *Allow*.
   * **Enable notification access** → Android's settings screen opens → switch on *Personal Expense Tracker* → press back.
   * (Optional) **Import bank SMS** pulls in the last 7 / 30 / 90 days of payment messages already on the phone.
3. All the badges at the top should be green.

> **Android 13+ and installed APK files:** if you install an APK you downloaded or received on WhatsApp
> (not through Android Studio), Android may grey out *Notification access*. Open *Settings → Apps →
> Personal Expense Tracker → ⋮ → **Allow restricted settings***, then try again.

## How to test it (for your review)

| # | Test | Expected result |
|---|---|---|
| 1 | Phone Capture → **Allow demo notifications**, then **Simulate UPI notification** | A notification appears; within a few seconds a transaction (e.g. Swiggy ₹450, category Food) is in **Transactions** with source `notification`. |
| 2 | Turn on **demo mode**, then text the phone from another number: `Rs.450.00 debited from A/c XX1234 to SWIGGY on 11-09-26 via UPI - HDFC Bank` | A transaction appears with source `sms`. |
| 3 | Send an **OTP-style** text: `Your OTP is 482913 for Rs.450 payment` | Nothing is saved (OTPs are ignored). |
| 4 | Repeat test 2 + test 1 for the same amount within 2 minutes | Only **one** transaction (SMS and notification are merged, merchant filled in). |
| 5 | Switch the phone to **flight mode**, send test 2, wait, then switch Wi-Fi back on | The transaction appears after reconnecting (queued and retried). |
| 6 | Real device: with demo mode **off**, a real bank/UPI SMS arrives | It is captured (sender IDs like `VM-HDFCBK` are accepted; friends' numbers are not). |

On the **emulator** you can send an SMS from your computer (turn demo mode on first, because the
emulator's sender is a plain number):

```powershell
adb emu sms send 5551234 "Rs.450.00 debited from A/c XX1234 to SWIGGY on 11-09-26 via UPI - HDFC Bank"
```

## Build an APK to share

Android Studio → **Build → Build Bundle(s) / APK(s) → Build APK(s)** → `app-debug.apk`
(in `android/app/build/outputs/apk/debug/`).

## Privacy design (good to mention in the report)

* Only SMS from **alphanumeric bank-style sender IDs** (e.g. `VM-HDFCBK`) that **look like a payment** are
  uploaded. Messages from phone numbers, OTPs and promotions (`-P` senders) never leave the phone.
* Notifications are read **only from payment apps** (Google Pay, PhonePe, Paytm, BHIM, CRED, ...) - never
  from chat or email apps. The list is in `PaymentNotificationListener.java`.
* The phone talks to the server with a **per-phone token** (only its SHA-256 hash is stored on the server).
  *Phone Capture → Unlink this phone* revokes every token for the account.
* Messages go only to **your own server**, not to any third party.

## Troubleshooting

| Problem | Fix |
|---|---|
| App shows *Can't reach the server* | Server running? Same Wi-Fi? IP correct in `capacitor.config.json` (then `npm run sync` and run again)? Firewall rule added? |
| `npx cap add android` says *android already exists* | You already ran it - just run `node scripts/patch-android.js` and `npx cap sync android`. |
| Capture stops after a while on Xiaomi / Vivo / Oppo / Realme | These phones kill background apps. Settings → Apps → Personal Expense Tracker → *Autostart* ON and *Battery* → **No restrictions**. |
| Badge says *Rejected - tap Re-link* | The server database was reset or tokens revoked - tap **Re-link this phone** (while logged in). |
| Nothing appears after a real SMS | Check *Phone Capture*: SMS badge green? Sender must be a bank-style ID (or enable demo mode). Look at **Last capture** and **Last upload** lines for the reason. |
| Gradle error about Java version | In Android Studio use *Settings → Build Tools → Gradle → Gradle JDK = jbr-21*. |

## Notes for later semesters

* **HTTPS:** for a hosted server use `https://` and remove `android:usesCleartextTraffic="true"` (added by the patch script for local development).
* **Token storage:** the token is kept in app-private storage; Android's *EncryptedSharedPreferences* would harden it further.
* **Play Store:** Google restricts `READ_SMS` / `RECEIVE_SMS` to apps whose core purpose needs them and requires a permissions declaration - mention this as a deployment constraint. Sideloaded APKs (as in this project) are not affected.
* The paste-in **Simulate SMS** page is still available in the web version for demos and tests.
