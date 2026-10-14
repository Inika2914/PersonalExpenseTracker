/* Phone Capture page logic. Only active inside the Android app (see native.js). */
(function () {
  var PEC = window.PEC;
  var $ = function (id) { return document.getElementById(id); };

  function say(text, kind) {
    var box = $('cap-msg');
    box.textContent = text || '';
    box.className = 'cap-msg ' + (kind || '');
    box.hidden = !text;
  }

  if (!PEC || !PEC.isNative) { $('browser-only').hidden = false; return; }
  $('native-only').hidden = false;
  var plugin = PEC.plugin;

  function badge(id, ok, yes, no) {
    var el = $(id);
    el.textContent = ok ? yes : no;
    el.className = 'badge ' + (ok ? 'ok' : 'warn');
  }

  async function refresh() {
    try {
      var s = await plugin.getStatus();
      var linked = s.configured && !s.tokenInvalid;
      badge('st-link', linked, 'Linked', s.tokenInvalid ? 'Rejected - tap Re-link' : 'Not linked');
      badge('st-sms', s.smsPermission, 'Allowed', 'Not allowed');
      badge('st-nl', s.notificationAccess, 'Enabled', 'Not enabled');
      var last = $('st-last');
      last.textContent = s.lastCaptureAt
        ? new Date(s.lastCaptureAt).toLocaleString() + ' (' + s.lastCaptureSource + ')'
        : 'Nothing yet';
      last.className = 'badge muted';
      var up = $('st-upload');
      up.textContent = s.lastUpload || 'Nothing yet';
      up.className = 'badge muted';
      $('demo-mode').checked = !!s.demoMode;
    } catch (e) {
      say('Could not read phone status: ' + (e.message || e), 'err');
    }
  }

  async function run(label, fn) {
    say('');
    try { await fn(); } catch (e) { say(label + ' failed: ' + (e.message || e), 'err'); }
    refresh();
  }

  $('btn-sms').addEventListener('click', function () {
    run('SMS permission', async function () {
      var s = await plugin.requestSmsPermissions();
      say(s.smsPermission ? 'SMS access allowed.' : 'SMS access was not granted. Automatic bank-SMS capture needs it.',
          s.smsPermission ? 'ok' : 'err');
    });
  });

  $('btn-nl').addEventListener('click', function () {
    run('Notification access', async function () {
      await plugin.openNotificationAccessSettings();
      say('Switch on "Personal Expense Tracker" in the Android screen, then return to this app.');
    });
  });

  $('btn-link').addEventListener('click', function () {
    run('Linking', async function () {
      var ok = await PEC.link(true);
      say(ok ? 'This phone is linked to your account.' : 'Could not link - are you logged in and online?', ok ? 'ok' : 'err');
    });
  });

  $('btn-sync').addEventListener('click', function () {
    run('Import', async function () {
      var days = parseInt($('sync-days').value, 10) || 30;
      var r = await plugin.syncInbox({ days: days });
      say('Scanned ' + r.scanned + ' messages, found ' + r.queued + ' payment messages. They are uploading now - check Transactions in a few seconds.', 'ok');
    });
  });

  $('sim-preset').addEventListener('change', function () { $('sim-text').value = this.value; });

  $('btn-notify-perm').addEventListener('click', function () {
    run('Notification permission', async function () {
      var s = await plugin.requestNotificationPermission();
      say(s.canPostNotifications ? 'Demo notifications allowed.' : 'Not allowed - the simulated notification cannot be shown.',
          s.canPostNotifications ? 'ok' : 'err');
    });
  });

  $('btn-simulate').addEventListener('click', function () {
    run('Simulation', async function () {
      var sel = $('sim-preset').selectedOptions[0];
      await plugin.simulateUpiNotification({ title: sel ? sel.dataset.title : 'Google Pay', text: $('sim-text').value });
      say('Notification posted. If notification access is enabled it will appear under Transactions within a few seconds.', 'ok');
    });
  });

  $('demo-mode').addEventListener('change', function () {
    var on = this.checked;
    run('Demo mode', async function () {
      await plugin.setDemoMode({ enabled: on });
      say(on ? 'Demo mode ON: SMS from any sender that looks like a payment will be captured.' : 'Demo mode off.', 'ok');
    });
  });

  $('btn-unlink').addEventListener('click', function () {
    if (!confirm('Unlink this phone and revoke access for all phones on this account?')) return;
    run('Unlink', async function () {
      var res = await fetch('/api/device/revoke', { method: 'POST', credentials: 'same-origin' });
      await plugin.clear();
      $('linked-count').textContent = '0';
      say(res.ok ? 'Phone unlinked. Capture has stopped until you link again.' : 'Phone unlinked locally, but the server could not be reached to revoke tokens.', res.ok ? 'ok' : 'err');
    });
  });

  document.addEventListener('visibilitychange', function () { if (!document.hidden) refresh(); });
  refresh();
})();
