// ── Lead Finder Lock ─────────────────────────────────────────────────────────
var LEAD_FINDER_LOCK_CODE = '1571';
function leadFinderIsUnlocked() {
  return readVersionedUnlock('hy_lead_finder_unlocked');
}
function leadFinderSetUnlocked() {
  writeVersionedUnlock('hy_lead_finder_unlocked');
  updateLeadFinderLockUI();
}
function updateLeadFinderLockUI() {
  var tab = document.getElementById('tabLeadFinder');
  if (!tab) return;
  if (leadFinderIsUnlocked()) {
    tab.innerHTML = cvTabLabel('Lead Finder', 'lead');
    tab.classList.remove('lead-locked');
    tab.title = tab.getAttribute('data-base-title') || 'Lead Finder';
    tab.setAttribute('data-base-title', 'Lead Finder');
  } else {
    tab.innerHTML = cvLockedTabLabel();
    tab.classList.add('lead-locked');
    tab.title = 'Locked tab';
    tab.setAttribute('data-base-title', 'Locked tab');
  }
}
function requestLeadFinderUnlock() {
  if (leadFinderIsUnlocked()) return true;
  var code = window.prompt('This tab is locked. Enter the 4-digit access code to unlock:');
  if (code === LEAD_FINDER_LOCK_CODE) {
    leadFinderSetUnlocked();
    showToast('Lead Finder unlocked', 'ok');
    return true;
  }
  window.alert('Incorrect or missing code. Returning to other tabs.');
  updateLeadFinderLockUI();
  return false;
}
function requireLeadFinderUnlocked() {
  if (requestLeadFinderUnlock()) return true;
  switchTab('format');
  return false;
}
function leadFinderLockPayload() { return leadFinderIsUnlocked() ? LEAD_FINDER_LOCK_CODE : ''; }



// ── LinkedIn Sourcer Tab Lock ─────────────────────────────────────────────────
var LINKEDIN_SOURCER_LOCK_CODE = '1212';
function linkedinSourcerIsUnlocked() {
  return readVersionedUnlock('hy_linkedin_sourcer_unlocked');
}
function linkedinSourcerSetUnlocked() {
  writeVersionedUnlock('hy_linkedin_sourcer_unlocked');
  updateLinkedinSourcerLockUI();
}
function updateLinkedinSourcerLockUI() {
  var tab = document.getElementById('tabLinkedinSourcer');
  if (!tab) return;
  var unlocked = linkedinSourcerIsUnlocked();
  tab.innerHTML = cvTabLabel('LinkedIn Sourcer', unlocked ? 'lead' : 'lock');
  tab.classList.toggle('sourcer-locked', !unlocked);
  tab.title = unlocked ? 'LinkedIn Sourcer' : 'LinkedIn Sourcer — Locked';
  tab.setAttribute('data-base-title', tab.title);
}
function requestLinkedinSourcerUnlock() {
  if (linkedinSourcerIsUnlocked()) return true;
  var code = window.prompt('LinkedIn Sourcer is locked. Enter the 4-digit access code to unlock:');
  if (code === LINKEDIN_SOURCER_LOCK_CODE) {
    linkedinSourcerSetUnlocked();
    showToast('LinkedIn Sourcer unlocked', 'ok');
    return true;
  }
  if (code !== null) window.alert('Incorrect code. LinkedIn Sourcer remains locked.');
  updateLinkedinSourcerLockUI();
  return false;
}
function requireLinkedinSourcerUnlocked() {
  if (requestLinkedinSourcerUnlock()) return true;
  switchTab('format');
  return false;
}

// ── AI Crawler Lock ─────────────────────────────────────────────────────────
function aiCrawlerIsUnlocked() {
  return true;
}
function aiCrawlerSetUnlocked() {
  updateAiCrawlerLockUI();
}
function updateAiCrawlerLockUI() {
  var tab = document.getElementById('tabTheSpider');
  if (!tab) return;
  tab.innerHTML = cvTabLabel('AI Crawler', 'spider');
  tab.classList.remove('ai-crawler-locked');
  tab.title = 'AI Crawler';
  tab.setAttribute('data-base-title', 'AI Crawler');
}
function requestAiCrawlerUnlock() {
  return true;
}
function requireAiCrawlerUnlocked() {
  return true;
}
function aiCrawlerLockPayload() { return ''; }
