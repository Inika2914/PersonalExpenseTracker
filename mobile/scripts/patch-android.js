#!/usr/bin/env node
/*
 * Wires the native capture code into the Android project that `npx cap add android` generated.
 *
 *   1. copies native/java/*.java into android/app/src/main/java/<appId>/ (rewriting the package)
 *   2. adds the SMS / notification permissions, the SMS receiver and the notification listener
 *      to AndroidManifest.xml, and allows plain-http traffic (development server)
 *   3. adds the WorkManager dependency to android/app/build.gradle
 *
 * Safe to run more than once.
 */
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const androidDir = path.join(root, 'android');
const MARK_BEGIN = '<!-- PEC-CAPTURE-BEGIN -->';

function fail(msg) { console.error('\n[patch-android] ' + msg + '\n'); process.exit(1); }

if (!fs.existsSync(androidDir)) {
  fail('The android/ folder does not exist yet. Run  npx cap add android  first.');
}
const config = JSON.parse(fs.readFileSync(path.join(root, 'capacitor.config.json'), 'utf8'));
const appId = config.appId;
if (!/^[a-z][\w]*(\.[a-z][\w]*)+$/i.test(appId || '')) fail('capacitor.config.json has an invalid appId.');

// ---------------------------------------------------------------- 1. Java sources
const srcDir = path.join(root, 'native', 'java', 'com', 'kongu', 'expensetracker');
const destDir = path.join(androidDir, 'app', 'src', 'main', 'java', ...appId.split('.'));
fs.mkdirSync(destDir, { recursive: true });
let copied = 0;
for (const file of fs.readdirSync(srcDir)) {
  if (!file.endsWith('.java')) continue;
  const code = fs.readFileSync(path.join(srcDir, file), 'utf8')
    .replace(/^package\s+[\w.]+;/m, 'package ' + appId + ';');
  fs.writeFileSync(path.join(destDir, file), code);
  copied++;
}
console.log('[patch-android] copied ' + copied + ' Java files to ' + path.relative(root, destDir));

// ---------------------------------------------------------------- 2. AndroidManifest.xml
const manifestPath = path.join(androidDir, 'app', 'src', 'main', 'AndroidManifest.xml');
if (!fs.existsSync(manifestPath)) fail('AndroidManifest.xml not found at ' + manifestPath);
let manifest = fs.readFileSync(manifestPath, 'utf8');

if (manifest.includes(MARK_BEGIN)) {
  console.log('[patch-android] AndroidManifest.xml already patched - skipping');
} else {
  const permissions = [
    '    ' + MARK_BEGIN,
    '    <uses-permission android:name="android.permission.RECEIVE_SMS" />',
    '    <uses-permission android:name="android.permission.READ_SMS" />',
    '    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />',
    '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />',
    '    <!-- PEC-CAPTURE-END -->'
  ].join('\n');

  const components = [
    '        ' + MARK_BEGIN,
    '        <!-- Wakes up for every incoming SMS, even when the app is closed -->',
    '        <receiver',
    '            android:name=".SmsReceiver"',
    '            android:exported="true"',
    '            android:permission="android.permission.BROADCAST_SMS">',
    '            <intent-filter android:priority="100">',
    '                <action android:name="android.provider.Telephony.SMS_RECEIVED" />',
    '            </intent-filter>',
    '        </receiver>',
    '',
    '        <!-- Reads UPI app notifications once the user enables Notification access -->',
    '        <service',
    '            android:name=".PaymentNotificationListener"',
    '            android:exported="true"',
    '            android:label="Personal Expense Tracker"',
    '            android:permission="android.permission.BIND_NOTIFICATION_LISTENER_SERVICE">',
    '            <intent-filter>',
    '                <action android:name="android.service.notification.NotificationListenerService" />',
    '            </intent-filter>',
    '        </service>',
    '        <!-- PEC-CAPTURE-END -->'
  ].join('\n');

  // permissions: right after the INTERNET permission the Capacitor template ships with
  const internet = /<uses-permission\s+android:name="android\.permission\.INTERNET"\s*\/>/;
  if (!internet.test(manifest)) fail('Could not find the INTERNET permission line in AndroidManifest.xml.');
  manifest = manifest.replace(internet, (m) => m + '\n' + permissions);

  // components: just before </application>
  if (!manifest.includes('</application>')) fail('Could not find </application> in AndroidManifest.xml.');
  manifest = manifest.replace('</application>', components + '\n    </application>');

  // development server is plain http://  (use https in production and remove this)
  if (!/usesCleartextTraffic/.test(manifest)) {
    manifest = manifest.replace('<application', '<application\n        android:usesCleartextTraffic="true"');
  }
  fs.writeFileSync(manifestPath, manifest);
  console.log('[patch-android] patched AndroidManifest.xml');
}

// ---------------------------------------------------------------- 3. app/build.gradle
const gradlePath = path.join(androidDir, 'app', 'build.gradle');
if (!fs.existsSync(gradlePath)) fail('app/build.gradle not found at ' + gradlePath);
let gradle = fs.readFileSync(gradlePath, 'utf8');
if (gradle.includes('androidx.work:work-runtime')) {
  console.log('[patch-android] build.gradle already has WorkManager - skipping');
} else {
  const anchor = /(implementation\s+project\(\s*['"]:capacitor-android['"]\s*\)[^\n]*\n)/;
  if (!anchor.test(gradle)) fail('Could not find the capacitor-android dependency line in app/build.gradle.');
  gradle = gradle.replace(anchor, '$1    implementation "androidx.work:work-runtime:2.9.1"\n');
  fs.writeFileSync(gradlePath, gradle);
  console.log('[patch-android] added WorkManager dependency to app/build.gradle');
}

console.log('\n[patch-android] done. Next:  npm run assets   then   npx cap sync android   then   npx cap open android\n');
