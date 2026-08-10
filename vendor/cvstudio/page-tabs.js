// ── Page Tab Switching ────────────────────────────────────────────────────────
function switchTab(tab) {
  try { if (document.activeElement && document.activeElement.classList && document.activeElement.classList.contains('page-tab')) document.activeElement.blur(); } catch(e) {}
  if (tab !== 'ppc' && typeof ppcCloseInvoicePreview === 'function') ppcCloseInvoicePreview();
  if (tab === 'summary' && !requestSummaryUnlock()) {
    tab = 'format';
  }
  if (tab === 'appraiser' && !requestCvScoringUnlock()) {
    tab = 'format';
  }
  if (tab === 'leadfinder' && !requestLeadFinderUnlock()) {
    tab = 'format';
  }
  if (tab === 'thespider' && !requestAiCrawlerUnlock()) {
    tab = 'format';
  }
  // Map tab names to their element ID suffixes
  var tabMap = { format:'Format', batch:'Batch', summary:'Summary', appraiser:'Appraiser', theowl:'TheOwl', thespider:'TheSpider', stats:'Stats', jaupload:'JAUpload', jacreate:'JACreate', onenote:'OneNote', jdanon:'JDAnon', company:'Company', leadfinder:'LeadFinder', ppc:'PPC', salary:'Salary' };
  Object.keys(tabMap).forEach(function(t) {
    var suffix = tabMap[t];
    document.getElementById('view' + suffix).classList.toggle('active', t === tab);
    document.getElementById('tab'  + suffix).classList.toggle('active', t === tab);
  });
  // Completed/failed tab lights mean the tab needs attention. Once opened, clear the light.
  // Browser badge count follows the same acknowledgement: opening the completed
  // CV Studio tab removes only that tab's completed background activities, not
  // every other pending activity.
  var statusBtn = document.getElementById('tab' + tabMap[tab]);
  var runState = statusBtn ? statusBtn.getAttribute('data-run-state') : '';
  if (runState === 'done' || runState === 'failed') {
    clearTabRunState(tab);
    if (runState === 'done') ackBrowserActivityForTab(tab);
    if (runState === 'failed') ackBrowserActivityFailedForTab(tab);
  } else if (BROWSER_ACTIVITY_DONE_BY_TAB && BROWSER_ACTIVITY_DONE_BY_TAB[tab]) {
    // Recovery path: if the green in-app tab was cleared before this click path,
    // still acknowledge that tab's browser badge count.
    ackBrowserActivityForTab(tab);
  }

  if (tab === 'stats')    renderStats();
  var quickFeatureByTab = {format:'cv_single', batch:'cv_batch', summary:'summary', appraiser:'appraiser', theowl:'the_owl', jdanon:'jd_anonymizer', company:'company_profile'};
  if (quickFeatureByTab[tab]) syncQuickAiProviderPanel(quickFeatureByTab[tab]);
  if (tab === 'ppc')      ppcInit();
  if (tab === 'summary') { updateSummaryRouteBadge(); suppressSummaryTabAutoCaret(); }
  if (tab === 'appraiser') updateAppraiserRouteBadge();
  if (tab === 'theowl') updateTheOwlRouteBadge();
  if (tab === 'thespider') updateTheSpiderRouteBadge();
  if (tab === 'jaupload') updateJAUploadConnStatus();
  if (tab === 'jacreate') updateJACreateConnStatus();
  if (tab === 'onenote') { updateOneNoteConnStatus(); oneNoteSourceModeChanged(); oneNoteRenderSavedLinks(); oneNoteRefreshCost(); oneNoteRenderRecords(); oneNoteInitActivityDiagnostic(); }
  if (tab === 'jdanon') { /* Blind JD ready */ }
  if (tab === 'company') { /* Company Profile ready */ }
  if (tab === 'leadfinder') { renderLeadFinder(); }
  if (tab === 'salary') {
    // Load the embedded Salary Comparison page lazily on first open so the
    // shared AI-route snapshot is already in localStorage when it initialises.
    var salaryFrame = document.getElementById('salaryFrame');
    if (salaryFrame && !salaryFrame.getAttribute('src')) salaryFrame.setAttribute('src', '/salary-comparison/');
  }
  if (typeof queuePageNavPinRefresh === 'function') queuePageNavPinRefresh();
}

// ── Drag-to-reorder page tabs ────────────────────────────────────────────────
// Click and hold any main tab (Batch, Create Profile, AI Crawler — locked tabs
// too) and drag it to a new position. The order is saved per browser and
// restored on the next reload. Purely front-end: no route or backend change, so
// the sealed route contract is untouched. A plain click still switches tabs; a
// drag reorders, because HTML5 dragstart only fires on an actual drag.
var PAGE_TAB_ORDER_KEY = 'cvstudio_page_tab_order';

function pageTabOrderSave(container) {
  try {
    var ids = Array.prototype.map.call(
      container.querySelectorAll('.page-tab'),
      function (el) { return el.id; }
    ).filter(Boolean);
    localStorage.setItem(PAGE_TAB_ORDER_KEY, JSON.stringify(ids));
  } catch (e) {}
}

function pageTabOrderApplySaved(container) {
  var saved;
  try { saved = JSON.parse(localStorage.getItem(PAGE_TAB_ORDER_KEY) || 'null'); } catch (e) { saved = null; }
  if (!Array.isArray(saved) || !saved.length) return;
  // The pin toggle is not a tab and always stays last.
  var pin = container.querySelector('.page-nav-pin-toggle');
  var tabs = Array.prototype.slice.call(container.querySelectorAll('.page-tab'));
  var byId = {};
  tabs.forEach(function (t) { if (t.id) byId[t.id] = t; });
  // Desired order = saved tabs that still exist, then any tabs added since
  // (e.g. a new feature in an update) in their original position.
  var ordered = [];
  saved.forEach(function (id) { if (byId[id]) { ordered.push(byId[id]); delete byId[id]; } });
  tabs.forEach(function (t) { if (t.id && byId[t.id]) ordered.push(t); });
  ordered.forEach(function (t) { container.insertBefore(t, pin || null); });
  if (pin) container.appendChild(pin);
}

function resetPageTabOrder() {
  try { localStorage.removeItem(PAGE_TAB_ORDER_KEY); } catch (e) {}
}

function initPageTabReordering() {
  var container = document.getElementById('pageTabs');
  if (!container || container._reorderReady) return;
  container._reorderReady = true;

  pageTabOrderApplySaved(container);
  Array.prototype.forEach.call(container.querySelectorAll('.page-tab'), function (tab) {
    tab.setAttribute('draggable', 'true');
  });

  var dragged = null;

  function getDragAfterElement(x, y) {
    var candidates = Array.prototype.slice.call(
      container.querySelectorAll('.page-tab:not(.tab-dragging)')
    );
    // Prefer tabs on the same visual row (the bar can wrap on narrow widths).
    var sameRow = candidates.filter(function (el) {
      var b = el.getBoundingClientRect();
      return y >= b.top && y <= b.bottom;
    });
    var pool = sameRow.length ? sameRow : candidates;
    var closest = { offset: -Infinity, element: null };
    pool.forEach(function (el) {
      var b = el.getBoundingClientRect();
      var offset = x - (b.left + b.width / 2);
      if (offset < 0 && offset > closest.offset) {
        closest = { offset: offset, element: el };
      }
    });
    return closest.element;
  }

  container.addEventListener('dragstart', function (e) {
    var tab = e.target && e.target.closest ? e.target.closest('.page-tab') : null;
    if (!tab || !container.contains(tab)) return;
    dragged = tab;
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      // Firefox needs data set for a drag to start.
      try { e.dataTransfer.setData('text/plain', tab.id || 'tab'); } catch (err) {}
    }
    container.classList.add('tabs-reordering');
    // Add after a tick so the drag image is captured at full opacity.
    setTimeout(function () { if (dragged) dragged.classList.add('tab-dragging'); }, 0);
  });

  container.addEventListener('dragover', function (e) {
    if (!dragged) return;
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
    var pin = container.querySelector('.page-nav-pin-toggle');
    var after = getDragAfterElement(e.clientX, e.clientY);
    if (after == null) {
      container.insertBefore(dragged, pin || null);
    } else if (after !== dragged) {
      container.insertBefore(dragged, after);
    }
  });

  container.addEventListener('drop', function (e) {
    if (dragged) e.preventDefault();
  });

  container.addEventListener('dragend', function () {
    if (!dragged) return;
    dragged.classList.remove('tab-dragging');
    container.classList.remove('tabs-reordering');
    dragged = null;
    // Keep the pin toggle last regardless of where the drag ended.
    var pin = container.querySelector('.page-nav-pin-toggle');
    if (pin) container.appendChild(pin);
    pageTabOrderSave(container);
    if (typeof queuePageNavPinRefresh === 'function') queuePageNavPinRefresh();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPageTabReordering);
} else {
  initPageTabReordering();
}
