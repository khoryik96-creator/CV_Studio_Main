// ── Heartbeat: ping server, auto-detect loss, auto-recover ───────────
// The local server does not auto-shut-down; a "connection lost" almost always
// means the machine slept or the tab was backgrounded, which stalls in-flight
// fetches. So the ping has a hard timeout, and returning to the tab / coming
// back online triggers an immediate re-check instead of waiting for the next
// interval — the banner recovers on its own without a manual reload.
(function () {
  var _serverLost      = false;
  var _banner          = null;
  var _missedPings     = 0;
  var _reloadQueued    = false;
  var _lastPingAt      = 0;
  var _recoverTimer    = null;
  var _recoverAttempts = 0;
  var _inFlight        = false;  // only one heartbeat request in flight at a time
  var _pingSeq         = 0;      // monotonic id assigned to each ping
  var _lastResolvedSeq = 0;      // highest ping whose completion we have applied
  var PING_INTERVAL     = 20000;  // steady-state: ping every 20s (idle cost unchanged)
  var RECOVER_INTERVAL  = 2500;   // once a ping is missed, poll fast until healthy again
  var RECOVER_MAX_TRIES = 48;     // cap the fast burst at ~2 min, then fall back to slow
  var MISS_THRESHOLD    = 4;      // consecutive misses before showing the banner
  var FETCH_TIMEOUT     = 8000;   // give up on a stuck request after 8s

  function timedFetch(url, options) {
    options = options || {};
    var ctrl = null, timer = null;
    try {
      ctrl = new AbortController();
      options.signal = ctrl.signal;
      timer = setTimeout(function () { try { ctrl.abort(); } catch (e) {} }, FETCH_TIMEOUT);
    } catch (e) { ctrl = null; }
    return fetch(url, options).then(
      function (r) { if (timer) clearTimeout(timer); return r; },
      function (e) { if (timer) clearTimeout(timer); throw e; }
    );
  }

  function showReconnectBanner(recovering) {
    var bg = recovering ? "#2f855a" : "#c05621";
    if (!_banner) {
      _banner = document.createElement("div");
      _banner.id = "reconnect-banner";
      _banner.style.cssText = [
        "position:fixed","top:0","left:0","right:0","z-index:2147483644",
        "color:#fff","text-align:center","padding:10px 16px",
        "font-size:14px","font-weight:500",
        "box-shadow:0 2px 8px rgba(0,0,0,0.35)",
        "transition:background 0.4s",
        "display:flex","align-items:center","justify-content:center","gap:12px"
      ].join(";");
      document.body.prepend(_banner);
    }
    _banner.style.background = bg;
    if (recovering) {
      _banner.innerHTML = "&#x27F3; Server restarted &mdash; reloading automatically&hellip;";
    } else {
      _banner.innerHTML = "";
      var msg = document.createElement("span");
      msg.id = "reconnect-msg";
      msg.textContent = "⚠ Server connection lost — reconnecting…";
      var btn = document.createElement("button");
      btn.textContent = "↻ Restart Server";
      btn.style.cssText = "background:#fff;color:#c05621;border:none;border-radius:6px;padding:4px 12px;font-size:13px;font-weight:600;cursor:pointer;";
      btn.onclick = restartServer;
      _banner.appendChild(msg);
      _banner.appendChild(btn);
    }
  }

  function restartServer() {
    var btn = document.querySelector("#reconnect-banner button");
    if (btn) { btn.textContent = "⏳ Waiting for server..."; btn.disabled = true; }
    // Try Flask restart first (works if server is slow, not if it's dead)
    timedFetch("/restart", {method:"POST", credentials:"same-origin", headers:{"X-CV-Studio-Restart":"1"}}).catch(function(){});
    // Keep polling every 3s — watchdog should revive it within ~45s
    var attempts = 0;
    var poll = setInterval(function() {
      attempts++;
      timedFetch("/ping").then(function(r) {
        if (r.ok || r.status === 204) {
          clearInterval(poll);
          location.reload();
        }
      }).catch(function(){});
      if (attempts > 40) { // 2 mins
        clearInterval(poll);
        if (btn) {
          btn.textContent = "↻ Restart Server";
          btn.disabled = false;
        }
        var msg = document.getElementById("reconnect-msg");
        if (msg) msg.innerHTML = "Server not responding. Please double-click <b>CV Studio</b> on your Desktop to restart.";
      }
    }, 3000);
  }

  function hideReconnectBanner() {
    if (_banner) { _banner.remove(); _banner = null; }
  }

  // While the connection looks lost, poll quickly — a short burst, not a
  // permanent fast interval — so recovery happens within a couple of seconds
  // instead of waiting out the 20s cadence. The burst stops the instant a ping
  // succeeds, and self-caps after ~2 minutes so a server that stays down does
  // not leave a 2.5s loop pinned forever; a later wake/focus event restarts it.
  function startFastRecovery() {
    if (_recoverTimer || _reloadQueued) return;
    _recoverAttempts = 0;
    _recoverTimer = setInterval(function () {
      if (_reloadQueued) { stopFastRecovery(); return; }
      _recoverAttempts++;
      if (_recoverAttempts > RECOVER_MAX_TRIES) { stopFastRecovery(); return; }
      ping();
    }, RECOVER_INTERVAL);
  }

  function stopFastRecovery() {
    if (_recoverTimer) { clearInterval(_recoverTimer); _recoverTimer = null; }
    _recoverAttempts = 0;
  }

  // A completion is only actionable if no newer ping has already resolved. With
  // the in-flight guard this is normally always true, but it is a cheap guard
  // against a slow/aborted request landing after a newer one and flipping state
  // back (a false "connection lost", or hiding a real outage).
  function acceptCompletion(seq) {
    if (seq <= _lastResolvedSeq) return false;
    _lastResolvedSeq = seq;
    return true;
  }

  function ping() {
    // Never overlap heartbeats: the steady interval, the fast-recovery burst,
    // and the wake/focus/online/pageshow retries all funnel through here, so a
    // single in-flight guard keeps exactly one request outstanding. The 8s
    // timedFetch deadline guarantees the guard is always released.
    if (_inFlight || _reloadQueued) return;
    _inFlight = true;
    _lastPingAt = Date.now();
    var seq = ++_pingSeq;
    timedFetch("/heartbeat", { method: "POST" })
      .then(function (r) {
        _inFlight = false;
        if (!acceptCompletion(seq)) return;
        if (r.ok || r.status === 204) {
          if (_serverLost && !_reloadQueued) {
            // Server is reachable again — show green banner then auto-reload
            // (a reload re-syncs the loopback session cookie in case the
            // process actually restarted while we were unreachable).
            _serverLost   = false;
            _missedPings  = 0;
            _reloadQueued = true;
            stopFastRecovery();
            showReconnectBanner(true);
            setTimeout(function () { location.reload(); }, 1500);
          } else {
            // Healthy ping — clear any miss streak and end the fast burst.
            _missedPings = 0;
            stopFastRecovery();
          }
        }
      })
      .catch(function () {
        _inFlight = false;
        if (!acceptCompletion(seq)) return;
        _missedPings++;
        // A missed ping is the first sign of trouble; start polling fast right
        // away so we notice recovery in ~2.5s rather than up to 20s. This burst
        // costs nothing at idle — it only runs while a ping is actually failing.
        startFastRecovery();
        // Only flag as lost after MISS_THRESHOLD consecutive misses (avoid a
        // single blip from a slow request or a momentary background throttle).
        if (_missedPings >= MISS_THRESHOLD && !_serverLost) {
          _serverLost = true;
          showReconnectBanner(false);
        }
      });
  }

  // Re-check immediately when the user comes back to the tab or the machine
  // wakes / reconnects, so recovery does not wait for the next 20s interval.
  function pingNow() {
    if (_reloadQueued) return;
    if (Date.now() - _lastPingAt < 1500) return; // throttle bursts of events
    ping();
  }

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") pingNow();
  });
  window.addEventListener("focus", pingNow);
  window.addEventListener("online", pingNow);
  window.addEventListener("pageshow", pingNow);

  ping(); // immediate ping on load
  setInterval(ping, PING_INTERVAL);
})();
