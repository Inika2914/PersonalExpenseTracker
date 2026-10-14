/*
 * Bridge between the web pages and the Android app (Capacitor).
 *
 * Inside the Android app the native "PaymentCapture" plugin is available; in a normal
 * browser it is not, so everything here is a no-op there.
 *
 * On every logged-in page it makes sure the phone is linked to the current account:
 * it asks the server for a device token (using the normal login session) and hands it
 * to the native side. From then on the native SMS receiver / notification listener
 * upload captured payments in the background, even when this page is closed.
 */
(function () {
  var cap = window.Capacitor;
  var native = !!(cap && typeof cap.isNativePlatform === 'function' && cap.isNativePlatform());
  var plugin = native && cap.Plugins ? cap.Plugins.PaymentCapture : null;
  var PEC = window.PEC = { isNative: !!plugin, plugin: plugin };
  if (!PEC.isNative) return;

  document.documentElement.classList.add('is-native');

  // Link (or re-link) this phone to the logged-in user. Resolves true when linked.
  PEC.link = async function (force) {
    var me = await fetch('/api/device/me', { credentials: 'same-origin' });
    if (!me.ok) return false;
    var user = await me.json();
    var st = await plugin.getStatus();
    var upToDate = st.configured && !st.tokenInvalid &&
                   st.userId === user.user_id && st.serverUrl === location.origin;
    if (upToDate && !force) return true;

    var res = await fetch('/api/device/link', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_name: 'Android app' })
    });
    if (!res.ok) return false;
    var data = await res.json();
    await plugin.configure({
      serverUrl: location.origin, token: data.token, userId: data.user_id, userName: data.name
    });
    return true;
  };

  document.addEventListener('DOMContentLoaded', function () {
    PEC.link(false).catch(function () { /* will retry on next page load */ });
  });
})();
