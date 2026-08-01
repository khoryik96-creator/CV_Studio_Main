// ── Heartbeat: ping server every 10s ─────────────────────────────────
// Auto-detects server loss and auto-reloads when server comes back
(function () {
  var _serverLost   = false;
  var _banner       = null;
  var _missedPings  = 0;
  var _reloadQueued = false;
  var PING_INTERVAL  = 20000;   // ping every 20s
  var MISS_THRESHOLD = 4;       // 4 missed pings (80s) before showing banner

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
      msg.textContent = "⚠ Server connection lost — click Restart or double-click CV Studio on Desktop";
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
    fetch("/restart", {method:"POST", credentials:"same-origin", headers:{"X-CV-Studio-Restart":"1"}}).catch(function(){});
    // Keep polling every 3s — watchdog should revive it within ~45s
    var attempts = 0;
    var poll = setInterval(function() {
      attempts++;
      fetch("/ping").then(function(r) {
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

  function ping() {
    fetch("/heartbeat", { method: "POST" })
      .then(function (r) {
        if (r.ok || r.status === 204) {
          if (_serverLost) {
            // Server is back — show green banner then auto-reload
            _serverLost   = false;
            _missedPings  = 0;
            _reloadQueued = true;
            showReconnectBanner(true);
            setTimeout(function () { location.reload(); }, 1500);
          } else {
            _missedPings = 0;
          }
        }
      })
      .catch(function () {
        _missedPings++;
        // Only flag as lost after 2 consecutive misses (avoid single blip)
        if (_missedPings >= MISS_THRESHOLD && !_serverLost) {
          _serverLost = true;
          showReconnectBanner(false);
        }
      });
  }

  ping(); // immediate ping on load
  setInterval(ping, PING_INTERVAL);
})();
