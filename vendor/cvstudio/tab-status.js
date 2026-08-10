// ── Sidebar tab run status / light indicators ──────────────────────────────
// Orange = processing, green = completed, red = failed. Token-based run tracking
// prevents an old async action from changing a tab after the user has cleared it
// or started a newer action.
var TAB_BUTTON_IDS = {
  format: 'tabFormat', summary: 'tabSummary', appraiser: 'tabAppraiser', theowl: 'tabTheOwl', thespider: 'tabTheSpider', batch: 'tabBatch', jaupload: 'tabJAUpload', jacreate: 'tabJACreate',
  jdanon: 'tabJDAnon', company: 'tabCompany', onenote: 'tabOneNote', leadfinder: 'tabLeadFinder', stats: 'tabStats', ppc: 'tabPPC'
};
var TAB_STATUS_LABELS = { running: 'Processing', done: 'Done', failed: 'Failed' };
var TAB_RUN_COUNTS = {};
var TAB_RUN_SEQ = {};
var TAB_ACTIVE_RUNS = {};
function setTabRunState(tab, state) {
  var id = TAB_BUTTON_IDS[tab] || tab;
  var el = document.getElementById(id);
  if (!el) return;
  el.classList.remove('tab-running', 'tab-done', 'tab-failed');
  el.removeAttribute('data-run-state');
  var baseTitle = el.getAttribute('data-base-title');
  if (!baseTitle) { baseTitle = el.textContent.trim(); el.setAttribute('data-base-title', baseTitle); }
  if (!state || state === 'idle') { el.title = baseTitle; return; }
  if (state === 'running') el.classList.add('tab-running');
  else if (state === 'done') el.classList.add('tab-done');
  else if (state === 'failed') el.classList.add('tab-failed');
  else return;
  el.setAttribute('data-run-state', state);
  el.title = baseTitle + ' — ' + (TAB_STATUS_LABELS[state] || state);
}
function _tabRunCount(tab) {
  var runs = TAB_ACTIVE_RUNS[tab] || {};
  return Object.keys(runs).length;
}
function markTabRunning(tab) {
  var token = (TAB_RUN_SEQ[tab] || 0) + 1;
  TAB_RUN_SEQ[tab] = token;
  if (!TAB_ACTIVE_RUNS[tab]) TAB_ACTIVE_RUNS[tab] = {};
  TAB_ACTIVE_RUNS[tab][token] = true;
  TAB_RUN_COUNTS[tab] = _tabRunCount(tab);
  setTabRunState(tab, 'running');
  return token;
}
function finishTabRun(tab, state, token) {
  if (token !== undefined && token !== null) {
    // A cleared or superseded token is stale. It must not alter either the
    // in-app outline or the browser-tab badge after Clear/new run.
    if (!TAB_ACTIVE_RUNS[tab] || !TAB_ACTIVE_RUNS[tab][token]) return null;
    delete TAB_ACTIVE_RUNS[tab][token];
  } else {
    var keys = Object.keys(TAB_ACTIVE_RUNS[tab] || {});
    if (!keys.length) return null;
    delete TAB_ACTIVE_RUNS[tab][keys[0]];
  }
  TAB_RUN_COUNTS[tab] = _tabRunCount(tab);
  if (TAB_RUN_COUNTS[tab] > 0) { setTabRunState(tab, 'running'); return false; }
  setTabRunState(tab, state);
  return true;
}
function markTabDone(tab, token, opts) {
  opts = opts || {};
  if (finishTabRun(tab, 'done', token) === true) {
    if (!opts.forceBrowser && typeof shouldSuppressBrowserActivityForTab === 'function' && shouldSuppressBrowserActivityForTab(tab)) {
      clearTabRunState(tab);
      updateBrowserActivityBadge();
    } else {
      notifyBrowserActivityDone(tab, !!opts.forceBrowser);
    }
  }
}
function markTabFailed(tab, token, opts) {
  opts = opts || {};
  if (finishTabRun(tab, 'failed', token) !== true) return;
  notifyBrowserActivityFailed(tab, !!opts.forceBrowser);
}
function clearTabRunState(tab) { TAB_ACTIVE_RUNS[tab] = {}; TAB_RUN_COUNTS[tab] = 0; setTabRunState(tab, 'idle'); }

// Browser tab completion badge. Browser tabs cannot be physically recoloured,
// so this updates the page title and favicon with a green count for completed
// work that needs attention. Counts are acknowledged per completed CV Studio
// tab, not cleared globally on focus. v24.6.66+ also badges completions while
// CV Studio is focused, unless the user is already viewing that same in-app tab.
function cleanBrowserActivityBaseTitle(title) {
  var t = String(title || '');
  // Strip any old notification prefixes from previous builds, including
  // repeated combinations like "🟢 (1) (1) CV Studio...".
  for (var i = 0; i < 4; i++) {
    t = t.replace(/^\s*(?:🟢|🔴|●|•|\u25CF)\s*/u, '').replace(/^\s*\(\d+\)\s*/, '');
  }
  t = t.trim();
  return t || 'CV Studio';
}
var BROWSER_ACTIVITY_BASE_TITLE = 'CV Studio';
var BROWSER_ACTIVITY_DONE_COUNT = 0;
var BROWSER_ACTIVITY_DONE_BY_TAB = {};
var BROWSER_ACTIVITY_FAIL_BY_TAB = {};
var BROWSER_ACTIVITY_CLEAR_TIMER = null;
var BROWSER_ACTIVITY_PULSE_TIMER = null;
var BROWSER_ACTIVITY_PULSE_ON = false;
var BROWSER_ACTIVITY_ORIGINAL_ICON_HREF = (function(){ var l = document.querySelector('link[rel~="icon"]'); return l ? (l.getAttribute('href') || '') : ''; })();
function browserActivityNormalizeBaseIconHref(href) {
  var h = String(href || '').trim();
  // Never treat a generated canvas/data-url badge from a previous page state as
  // the base favicon. This is what caused fresh loads to show a stale green "1".
  if (!h || /^data:/i.test(h) || /cvstudio-badge|cvbadge/i.test(h)) return 'cv_studio_logo.png?v=24.6.79-ui';
  return h;
}
var BROWSER_ACTIVITY_BASE_ICON_HREF = browserActivityNormalizeBaseIconHref(BROWSER_ACTIVITY_ORIGINAL_ICON_HREF);
function browserActivityBaseIconHrefFresh() {
  var base = String(BROWSER_ACTIVITY_BASE_ICON_HREF || 'cv_studio_logo.png?v=24.6.79-ui');
  var clean = base.replace(/([?&])cvbadge_reset=\d+(&?)/, function(_, sep, tail){ return tail ? sep : ''; }).replace(/[?&]$/, '');
  return clean + (clean.indexOf('?') >= 0 ? '&' : '?') + 'cvbadge_reset=' + Date.now();
}
function getBrowserFaviconLink() {
  var link = document.querySelector('link[rel~="icon"]');
  if (!link) {
    link = document.createElement('link');
    link.rel = 'icon';
    document.head.appendChild(link);
  }
  return link;
}
function resetBrowserFaviconToBase() {
  try {
    var links = Array.prototype.slice.call(document.querySelectorAll('link[rel~="icon"]'));
    var link = links[0] || getBrowserFaviconLink();
    for (var i = 1; i < links.length; i++) {
      if (links[i].getAttribute('data-cvstudio-badge-icon') === '1') links[i].parentNode.removeChild(links[i]);
    }
    link.removeAttribute('data-cvstudio-badge-icon');
    if (BROWSER_ACTIVITY_BASE_ICON_HREF) {
      link.rel = 'icon';
      link.type = 'image/png';
      link.href = browserActivityBaseIconHrefFresh();
      // Chrome can occasionally keep showing the previous canvas data-url favicon.
      // Re-applying the base icon shortly after acknowledgement makes the reset reliable.
      setTimeout(function(){
        if (BROWSER_ACTIVITY_DONE_COUNT <= 0 && _browserActivityFailureCount() <= 0) {
          var l2 = getBrowserFaviconLink();
          l2.removeAttribute('data-cvstudio-badge-icon');
          l2.type = 'image/png';
          l2.href = browserActivityBaseIconHrefFresh();
        }
      }, 180);
      setTimeout(function(){
        if (BROWSER_ACTIVITY_DONE_COUNT <= 0 && _browserActivityFailureCount() <= 0) {
          var l3 = getBrowserFaviconLink();
          l3.removeAttribute('data-cvstudio-badge-icon');
          l3.type = 'image/png';
          l3.href = browserActivityBaseIconHrefFresh();
        }
      }, 900);
    } else if (link && link.parentNode) {
      link.parentNode.removeChild(link);
    }
  } catch(e) {}
}
function makeBrowserBadgeIcon(count, pulseOn) {
  try {
    var canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    var ctx = canvas.getContext('2d');
    if (!ctx) return '';
    ctx.clearRect(0, 0, 64, 64);
    // v24.6.66+: keep the favicon as a clear pulsing green notification icon,
    // but do not draw the number here. The number lives in the page title only,
    // so Chrome does not show duplicate "1" indicators.
    if (pulseOn) {
      ctx.fillStyle = 'rgba(184,247,200,0.95)';
      ctx.beginPath();
      ctx.arc(32, 32, 30, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = pulseOn ? '#2FA84F' : '#1D6A3A';
    ctx.beginPath();
    ctx.arc(32, 32, pulseOn ? 22 : 19, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 30px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('✓', 32, 34);
    return canvas.toDataURL('image/png');
  } catch (e) {
    return '';
  }
}

function makeBrowserFailureIcon(pulseOn) {
  try {
    var canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    var ctx = canvas.getContext('2d');
    if (!ctx) return '';
    ctx.clearRect(0, 0, 64, 64);
    // Red failure badge has no number; it simply says an unacknowledged tab failed.
    if (pulseOn) {
      ctx.fillStyle = 'rgba(254,202,202,0.95)';
      ctx.beginPath();
      ctx.arc(32, 32, 30, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = pulseOn ? '#DC2626' : '#991B1B';
    ctx.beginPath();
    ctx.arc(32, 32, pulseOn ? 22 : 19, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 34px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('!', 32, 35);
    return canvas.toDataURL('image/png');
  } catch (e) {
    return '';
  }
}
function _browserActivityFailureCount() {
  return Object.keys(BROWSER_ACTIVITY_FAIL_BY_TAB || {}).filter(function(k){ return !!BROWSER_ACTIVITY_FAIL_BY_TAB[k]; }).length;
}
function stopBrowserActivityPulse() {
  if (BROWSER_ACTIVITY_PULSE_TIMER) {
    clearInterval(BROWSER_ACTIVITY_PULSE_TIMER);
    BROWSER_ACTIVITY_PULSE_TIMER = null;
  }
  BROWSER_ACTIVITY_PULSE_ON = false;
}
function startBrowserActivityPulse() {
  if (BROWSER_ACTIVITY_PULSE_TIMER || (BROWSER_ACTIVITY_DONE_COUNT <= 0 && _browserActivityFailureCount() <= 0)) return;
  BROWSER_ACTIVITY_PULSE_TIMER = setInterval(function(){
    if (BROWSER_ACTIVITY_DONE_COUNT <= 0 && _browserActivityFailureCount() <= 0) { stopBrowserActivityPulse(); return; }
    BROWSER_ACTIVITY_PULSE_ON = !BROWSER_ACTIVITY_PULSE_ON;
    updateBrowserActivityBadge();
  }, 850);
}
function updateBrowserActivityBadge() {
  var failCount = _browserActivityFailureCount();
  if (failCount > 0) {
    // Red failure favicon takes priority when any failed feature tab has not
    // been opened yet.  Keep the existing green completion count in the title
    // so successful background work still behaves as before.
    var failPrefix = BROWSER_ACTIVITY_PULSE_ON ? '🔴 ' : '';
    document.title = failPrefix + (BROWSER_ACTIVITY_DONE_COUNT > 0 ? '(' + BROWSER_ACTIVITY_DONE_COUNT + ') ' : '') + BROWSER_ACTIVITY_BASE_TITLE;
    var failUrl = makeBrowserFailureIcon(BROWSER_ACTIVITY_PULSE_ON);
    if (failUrl) {
      var failLink = getBrowserFaviconLink();
      failLink.setAttribute('data-cvstudio-badge-icon', '1');
      failLink.href = failUrl;
    }
    startBrowserActivityPulse();
  } else if (BROWSER_ACTIVITY_DONE_COUNT > 0) {
    // Single-count mode: show the unread number only once, in the browser title.
    // Browser title text cannot be styled with a real CSS green outline, so the
    // title itself pulses by alternating a green dot prefix while the favicon
    // pulses as a green attention marker without another number.
    var pulsePrefix = BROWSER_ACTIVITY_PULSE_ON ? '🟢 ' : '';
    document.title = pulsePrefix + '(' + BROWSER_ACTIVITY_DONE_COUNT + ') ' + BROWSER_ACTIVITY_BASE_TITLE;
    var dataUrl = makeBrowserBadgeIcon(BROWSER_ACTIVITY_DONE_COUNT, BROWSER_ACTIVITY_PULSE_ON);
    if (dataUrl) {
      var badgeLink = getBrowserFaviconLink();
      badgeLink.setAttribute('data-cvstudio-badge-icon', '1');
      badgeLink.href = dataUrl;
    }
    startBrowserActivityPulse();
  } else {
    stopBrowserActivityPulse();
    document.title = BROWSER_ACTIVITY_BASE_TITLE;
    resetBrowserFaviconToBase();
  }
}
function _browserActivitySumByTab() {
  var total = 0;
  Object.keys(BROWSER_ACTIVITY_DONE_BY_TAB || {}).forEach(function(k){
    total += Math.max(0, Number(BROWSER_ACTIVITY_DONE_BY_TAB[k] || 0));
  });
  return total;
}
function shouldSuppressBrowserActivityForTab(tab) {
  // Do not raise a browser-tab badge only when the user is actively looking at
  // the same CV Studio feature tab that just completed. If CV Studio is focused
  // on another feature tab, still badge it so the user notices the completed work.
  var pageIsActive = !document.hidden && (typeof document.hasFocus !== 'function' || document.hasFocus());
  if (!pageIsActive) return false;
  return !!tab && getActiveCvStudioTab && getActiveCvStudioTab() === tab;
}
function notifyBrowserActivityDone(tab, force) {
  var key = tab || 'general';
  if (!force && shouldSuppressBrowserActivityForTab(key)) return;
  BROWSER_ACTIVITY_DONE_BY_TAB[key] = Math.max(0, Number(BROWSER_ACTIVITY_DONE_BY_TAB[key] || 0)) + 1;
  BROWSER_ACTIVITY_DONE_COUNT = _browserActivitySumByTab();
  updateBrowserActivityBadge();
}
function notifyBrowserActivityFailed(tab, force) {
  var key = tab || 'general';
  if (!force && shouldSuppressBrowserActivityForTab(key)) return;
  BROWSER_ACTIVITY_FAIL_BY_TAB[key] = true;
  updateBrowserActivityBadge();
}
function ackBrowserActivityFailedForTab(tab) {
  if (tab && BROWSER_ACTIVITY_FAIL_BY_TAB && BROWSER_ACTIVITY_FAIL_BY_TAB[tab]) delete BROWSER_ACTIVITY_FAIL_BY_TAB[tab];
  updateBrowserActivityBadge();
}
function ackBrowserActivityForTab(tab) {
  // Always refresh title/favicon even when the per-tab entry is already gone.
  // This prevents a stale green numbered favicon from sticking after the in-app
  // green tab was clicked or cleared by another path.
  if (tab && BROWSER_ACTIVITY_DONE_BY_TAB[tab]) delete BROWSER_ACTIVITY_DONE_BY_TAB[tab];
  BROWSER_ACTIVITY_DONE_COUNT = _browserActivitySumByTab();
  updateBrowserActivityBadge();
}
function clearBrowserActivityBadgeSoon() {
  // Keep for emergency/manual compatibility, but do not auto-clear on focus.
  clearTimeout(BROWSER_ACTIVITY_CLEAR_TIMER);
  BROWSER_ACTIVITY_CLEAR_TIMER = setTimeout(function(){
    BROWSER_ACTIVITY_DONE_BY_TAB = {};
    BROWSER_ACTIVITY_FAIL_BY_TAB = {};
    BROWSER_ACTIVITY_DONE_COUNT = 0;
    updateBrowserActivityBadge();
  }, 1800);
}
// Do not auto-clear every browser badge just because the app receives focus.
// The count behaves like an unread counter and clears only when the relevant
// completed CV Studio tab is opened or is already the active tab on return.

function getActiveCvStudioTab() {
  try {
    var keys = Object.keys(TAB_BUTTON_IDS || {});
    for (var i = 0; i < keys.length; i++) {
      var tab = keys[i];
      var el = document.getElementById(TAB_BUTTON_IDS[tab]);
      if (el && el.classList && el.classList.contains('active')) return tab;
    }
  } catch(e) {}
  return '';
}
function ackBrowserActivityForActiveCompletedTab() {
  // Edge case: if the user left CV Studio while already viewing a tab and that
  // same tab completes in the background, returning to the browser does not call
  // switchTab(). Acknowledge only that active completed tab; keep other completed
  // tabs unread until opened.
  var tab = getActiveCvStudioTab();
  if (!tab) return;
  var id = TAB_BUTTON_IDS[tab] || tab;
  var el = document.getElementById(id);
  var runState = el ? el.getAttribute('data-run-state') : '';
  var hasPendingBrowserActivity = !!(BROWSER_ACTIVITY_DONE_BY_TAB && BROWSER_ACTIVITY_DONE_BY_TAB[tab]);
  if (runState === 'done' || runState === 'failed') clearTabRunState(tab);
  if (runState === 'done' || hasPendingBrowserActivity) ackBrowserActivityForTab(tab);
  if (runState === 'failed') ackBrowserActivityFailedForTab(tab);
}
window.addEventListener('focus', function(){
  setTimeout(ackBrowserActivityForActiveCompletedTab, 120);
});
document.addEventListener('visibilitychange', function(){
  if (!document.hidden) setTimeout(ackBrowserActivityForActiveCompletedTab, 120);
});

function hardResetBrowserActivityBadgeOnStartup() {
  // Browser favicon state can survive a previous session/reload visually in Chrome.
  // Start every CV Studio load from zero unread activity and the base favicon.
  try {
    BROWSER_ACTIVITY_DONE_BY_TAB = {};
    BROWSER_ACTIVITY_DONE_COUNT = 0;
    stopBrowserActivityPulse();
    document.title = BROWSER_ACTIVITY_BASE_TITLE;
    resetBrowserFaviconToBase();
    setTimeout(function(){
      if (_browserActivitySumByTab() <= 0) {
        BROWSER_ACTIVITY_DONE_COUNT = 0;
        document.title = BROWSER_ACTIVITY_BASE_TITLE;
        resetBrowserFaviconToBase();
      }
    }, 250);
    setTimeout(function(){
      if (_browserActivitySumByTab() <= 0) {
        BROWSER_ACTIVITY_DONE_COUNT = 0;
        document.title = BROWSER_ACTIVITY_BASE_TITLE;
        resetBrowserFaviconToBase();
      }
    }, 1200);
  } catch(e) {}
}
hardResetBrowserActivityBadgeOnStartup();
window.addEventListener('load', hardResetBrowserActivityBadgeOnStartup);
