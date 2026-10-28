/* JobAdder client-contact email scan for the Email Verifier.
 *
 * Read-only: contacts are read page by page from /jobadder/client_contacts and
 * each unique email goes through the existing /email-verifier check. Nothing is
 * written to JobAdder. Invalid emails are listed with a link to the contact so
 * the recruiter can update it there. Contacts and results stay in this tab, like
 * the rest of the Email Verifier: there is no saved email list.
 */
(function () {
  'use strict';
  const PAGE_SIZE = 100;
  const MAX_CONTACTS = 20000;
  // The verifier engine runs two checks at once and one per domain.
  const WORKERS = 2;
  const BUSY_WAIT_MS = 1500;
  const MAX_BUSY_WAITS = 80;
  const PAGE_RETRY_WAIT_MS = 5000;
  const PAGE_RETRIES = 3;
  // A failed check is retried before it is set aside; several failed emails in
  // a row (with no success between them) mean the connection itself is down.
  const CHECK_RETRIES = 2;
  const CHECK_RETRY_WAIT_MS = 3000;
  const MAX_FAILED_IN_A_ROW = 5;
  const MAX_RENDERED_ROWS = 500;
  // Results that suggest this network cannot reach mail servers at all.
  const BLOCKED_WARNING_AFTER = 5;
  // The tenant's own web address when CV Studio knows it, like the rest of the
  // JobAdder links in the app; app.jobadder.com is only the fallback.
  const GENERIC_WEB_BASE = 'https://app.jobadder.com';
  const WEB_BASE_RE = /^https:\/\/[a-z0-9-]+(?:\.[a-z0-9-]+)*\.jobadder\.com$/i;
  const LABELS = {
    invalid: 'Invalid', unknown: 'Unconfirmed', catch_all: 'Catch-all', accepted: 'Mailbox accepted',
    domain_ok: 'Domain passed', no_email: 'No email', not_checked: 'Not checked',
  };
  const RANK = {invalid: 0, unknown: 1, catch_all: 2, not_checked: 3, domain_ok: 4, accepted: 5, no_email: 6};
  const INFERRED_CATCH_ALL = 'Address format and mail records passed; the mailbox was not checked one by one. This domain’s mail server accepted a made-up address on an earlier check, so it cannot confirm or reject single mailboxes.';

  // ---- Pure helpers (exported for the no-network fixture) -------------------
  function emailKey(email) {
    const text = String(email || '').trim();
    const at = text.lastIndexOf('@');
    return at < 0 ? text : text.slice(0, at) + text.slice(at).toLowerCase();
  }
  // The verifier engine keys its one-check-per-domain lock on the ASCII (IDNA)
  // form of the domain, so the queue uses the same key.
  function domainOf(email) {
    const text = String(email || '').trim();
    const at = text.lastIndexOf('@');
    const raw = at < 0 ? '' : text.slice(at + 1).trim().toLowerCase();
    if (!raw || /[\/\\:?#@\s]/.test(raw)) return raw;
    try { return new URL('http://' + raw + '/').hostname || raw; } catch (error) { return raw; }
  }
  function webBase() {
    let memory = '', stored = '';
    try { memory = String(window._jaWebBase || ''); } catch (error) { memory = ''; }
    try { stored = String(localStorage.getItem('ja_web_base') || ''); } catch (error) { stored = ''; }
    for (const base of [memory, stored]) {
      const trimmed = base.replace(/\/+$/, '');
      if (trimmed && trimmed !== GENERIC_WEB_BASE && WEB_BASE_RE.test(trimmed)) return trimmed;
    }
    return GENERIC_WEB_BASE;
  }
  function contactLink(id, base) {
    return Number.isSafeInteger(id) && id > 0 ? (base || webBase()) + '/contacts/' + id : '';
  }
  function text(value, limit) {
    return typeof value === 'string' ? value.slice(0, limit) : '';
  }
  function normalizePage(payload, offset) {
    if (!payload || typeof payload !== 'object' || !Array.isArray(payload.contacts)) {
      throw Error('JobAdder returned an unexpected contact list.');
    }
    const contacts = [];
    for (const item of payload.contacts) {
      if (!item || typeof item !== 'object' || !Number.isSafeInteger(item.contact_id) || item.contact_id <= 0) continue;
      contacts.push({
        id: item.contact_id, name: text(item.name, 200), company: text(item.company, 200),
        email: text(item.email, 320).trim(), inactive: item.inactive === true,
      });
    }
    // A next page must move forward, or the scan could loop on one page.
    const next = payload.next_offset;
    const nextOffset = Number.isSafeInteger(next) && next > offset ? next : null;
    const total = Number.isSafeInteger(payload.total) && payload.total >= 0 ? payload.total : null;
    return {contacts, nextOffset, total};
  }
  function newScan(mode, namespace) {
    return {
      mode: mode === 'quick' ? 'quick' : 'full', namespace: String(namespace || ''),
      contacts: [], ids: new Set(), entries: new Map(), order: [], cursor: 0, sorted: null,
      loaded: false, nextOffset: 0, total: null, capped: false,
      catchAll: new Set(), inflight: new Set(), blocked: 0, reached: 0, failedInARow: 0,
    };
  }
  function addContacts(scan, contacts) {
    for (const contact of contacts) {
      if (scan.ids.has(contact.id)) continue;
      if (scan.contacts.length >= MAX_CONTACTS) { scan.capped = true; break; }
      scan.ids.add(contact.id);
      scan.contacts.push(contact);
      scan.sorted = null;
      if (!contact.email) continue;
      const key = emailKey(contact.email);
      let entry = scan.entries.get(key);
      if (!entry) {
        entry = {key, email: contact.email, domain: domainOf(contact.email), state: 'pending', result: null, contacts: 0};
        scan.entries.set(key, entry);
        scan.order.push(key);
      }
      entry.contacts += 1;
      contact.key = key;
    }
  }
  // The next email to check: the first waiting one whose domain is not already
  // being checked. On a domain already found to accept any address, the mail
  // server is not asked again: only the address format and mail records are
  // checked ("quick"), so a malformed address there is still reported Invalid.
  function takeNext(scan) {
    while (scan.cursor < scan.order.length && scan.entries.get(scan.order[scan.cursor]).state === 'done') scan.cursor += 1;
    for (let index = scan.cursor; index < scan.order.length; index++) {
      const entry = scan.entries.get(scan.order[index]);
      if (entry.state !== 'pending') continue;
      if (entry.domain && scan.inflight.has(entry.domain)) continue;
      return {entry, inferred: !!entry.domain && scan.catchAll.has(entry.domain)};
    }
    return null;
  }
  // Emails still waiting, being checked, or set aside after failing this run.
  function hasWork(scan) {
    for (let index = scan.cursor; index < scan.order.length; index++) {
      if (scan.entries.get(scan.order[index]).state !== 'done') return true;
    }
    return false;
  }
  function countState(scan, state) {
    let count = 0;
    for (const entry of scan.entries.values()) if (entry.state === state) count += 1;
    return count;
  }
  // A quick check on a known catch-all domain that passed format and mail
  // records is shown as Catch-all; Invalid or Unconfirmed answers stand.
  function inferredResult(result) {
    return result.status === 'domain_ok'
      ? {...result, status: 'catch_all', reason: INFERRED_CATCH_ALL, inferred: true}
      : {...result, inferred: true};
  }
  function recordResult(scan, entry, result) {
    entry.result = result;
    entry.state = 'done';
    if (result.inferred) return;
    if (result.status === 'catch_all' && scan.mode !== 'quick' && entry.domain) scan.catchAll.add(entry.domain);
    if (result.status === 'unknown' && (result.outcome === 'connection' || result.outcome === 'timeout')) scan.blocked += 1;
    else if (Number(result.attempts) > 0) scan.reached += 1;
  }
  function contactStatus(scan, contact) {
    if (!contact.email) return 'no_email';
    const entry = scan.entries.get(contact.key);
    return entry && entry.state === 'done' && entry.result ? entry.result.status : 'not_checked';
  }
  // Contacts in company, then name order, sorted once per change of the list
  // rather than on every redraw.
  const collator = typeof Intl !== 'undefined' ? new Intl.Collator(undefined, {sensitivity: 'base'}) : null;
  function compareText(a, b) { return collator ? collator.compare(a, b) : a < b ? -1 : a > b ? 1 : 0; }
  function sortedContacts(scan) {
    if (!scan.sorted) {
      scan.sorted = scan.contacts.slice().sort((a, b) => compareText(a.company, b.company) || compareText(a.name, b.name) || a.id - b.id);
    }
    return scan.sorted;
  }
  function summarize(scan) {
    const counts = {invalid: 0, unknown: 0, catch_all: 0, ok: 0, no_email: 0, not_checked: 0};
    for (const contact of scan ? scan.contacts : []) {
      const status = contactStatus(scan, contact);
      if (status === 'accepted' || status === 'domain_ok') counts.ok += 1;
      else if (Object.hasOwn(counts, status)) counts[status] += 1;
      else counts.unknown += 1;
    }
    const entries = scan ? Array.from(scan.entries.values()) : [];
    return {
      counts, contacts: scan ? scan.contacts.length : 0, emails: entries.length,
      checked: entries.filter(entry => entry.state === 'done').length,
    };
  }
  function visibleRows(scan, options) {
    if (!scan) return [];
    const filter = options && typeof options.filter === 'string' ? options.filter : 'invalid';
    const search = String(options && options.search || '').trim().toLowerCase();
    const hideInactive = !!(options && options.hideInactive);
    // Bucket by result, keeping the pre-sorted company/name order in each bucket.
    const buckets = [];
    for (const contact of sortedContacts(scan)) {
      const status = contactStatus(scan, contact);
      const group = status === 'accepted' || status === 'domain_ok' ? 'ok' : status;
      if (filter && group !== filter) continue;
      if (hideInactive && contact.inactive) continue;
      if (search && ![contact.name, contact.company, contact.email].some(value => value.toLowerCase().includes(search))) continue;
      const entry = contact.key ? scan.entries.get(contact.key) : null;
      const rank = RANK[status] ?? 9;
      (buckets[rank] || (buckets[rank] = [])).push({contact, status, result: entry && entry.state === 'done' ? entry.result : null, entry});
    }
    return [].concat(...buckets.filter(Boolean));
  }
  // Escape formula prefixes as well as RFC CSV quotes; no cell is executable.
  function csvCell(value) {
    let cell = String(value ?? '');
    if (/^\s*[=+\-@]/.test(cell)) cell = "'" + cell;
    return '"' + cell.replaceAll('"', '""') + '"';
  }
  function makeCSV(rows) {
    const base = webBase();
    const header = ['Contact ID', 'Contact', 'Company', 'Email', 'Result', 'Reason', 'No longer with company', 'Checked at', 'JobAdder link'];
    return [header, ...rows.map(({contact, status, result}) => [
      contact.id, contact.name, contact.company, contact.email, LABELS[status] || 'Unconfirmed',
      result ? result.reason : '', contact.inactive ? 'Yes' : '', result ? result.checked_at || '' : '', contactLink(contact.id, base),
    ])].map(row => row.map(csvCell).join(',')).join('\r\n');
  }

  // ---- Network -------------------------------------------------------------
  function accountNamespace() {
    return typeof window !== 'undefined' ? String(window._jaAccountCacheNamespace || '') : '';
  }
  // A scan started before the page learned which JobAdder account is connected
  // belongs to the account that becomes known: the server read its contacts
  // with that account's sign-in. Any other change is a different account.
  function sameAccount(owned) {
    const now = accountNamespace();
    if (owned.namespace === now) return true;
    if (!owned.namespace && now) { owned.namespace = now; return true; }
    return false;
  }
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
  async function fetchPage(offset) {
    let response;
    try {
      response = await fetch('/jobadder/client_contacts?offset=' + offset + '&limit=' + PAGE_SIZE, {method: 'GET', timeout: 60000});
    } catch (error) {
      const failure = Error('JobAdder contacts could not be loaded. Check the connection.');
      failure.transient = true;
      throw failure;
    }
    let data = null;
    try { data = await response.json(); } catch (error) { data = null; }
    if (!response.ok) {
      const error = Error(data && typeof data.error === 'string' ? data.error : 'JobAdder contacts could not be loaded.');
      error.status = response.status;
      error.transient = [429, 502, 503, 504].includes(response.status);
      throw error;
    }
    return normalizePage(data, offset);
  }
  async function checkEmail(email, mode) {
    const response = await fetch('/email-verifier', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email, mode}), timeout: 32000,
    });
    let data = null;
    try { data = await response.json(); } catch (error) { data = null; }
    // The engine answers 429 while its two slots or this domain are in use, for
    // example by a check on the main Email Verifier list: wait, then retry.
    if (response.status === 429) return {busy: true};
    if (!response.ok || !data || !data.ok) throw Error(data && data.error || 'The check could not be completed.');
    const result = data.result;
    if (!result || !Object.hasOwn(LABELS, result.status) || ['no_email', 'not_checked'].includes(result.status) || typeof result.reason !== 'string') {
      throw Error('The verifier returned an incomplete result.');
    }
    return {result: {...result, email}};
  }

  // ---- Controller ------------------------------------------------------------
  const el = name => document.getElementById('emailVerifierJa' + name);
  let scan = null, running = false, stopping = false, leaving = false, generation = 0;
  let waiters = [], renderQueued = false;
  function notify() { const list = waiters; waiters = []; for (const resolve of list) resolve(); }
  function waitForChange() { return new Promise(resolve => waiters.push(resolve)); }
  // A run keeps working only while its scan is still the one on screen and the
  // JobAdder account is the one the scan started with.
  function current(owned) {
    return !leaving && !!owned && scan === owned && sameAccount(owned);
  }
  // One account's contacts must never be shown under another, even if the
  // sign-out signal was missed: a scan from a different account is dropped.
  function guardAccount() {
    if (!scan || sameAccount(scan)) return;
    generation += 1;
    running = false; stopping = false; scan = null;
    notify();
    setMessage('The JobAdder account changed, so the previous scan was cleared.');
  }
  function setMessage(message) { el('Message').textContent = message; }
  // Results can arrive several times a second; redraw at most four times a second.
  function scheduleRender() {
    if (renderQueued) return;
    renderQueued = true;
    setTimeout(() => { renderQueued = false; render(); }, 250);
  }
  function render() {
    guardAccount();
    const summary = summarize(scan);
    el('Invalid').textContent = summary.counts.invalid;
    el('Unknown').textContent = summary.counts.unknown;
    el('CatchAll').textContent = summary.counts.catch_all;
    el('Accepted').textContent = summary.counts.ok;
    el('NoEmail').textContent = summary.counts.no_email;
    const progress = el('Progress');
    if (!scan) {
      el('Total').textContent = 'Your scan results will appear here';
      progress.hidden = true;
    } else if (!scan.loaded) {
      el('Total').textContent = 'Loading contacts: ' + summary.contacts + (scan.total !== null ? ' of ' + scan.total : '');
      progress.hidden = scan.total === null;
      progress.max = scan.total || 1; progress.value = summary.contacts;
    } else {
      el('Total').textContent = summary.checked + ' of ' + summary.emails + ' unique emails checked · ' + summary.contacts + ' contacts';
      progress.hidden = summary.emails === 0;
      progress.max = summary.emails || 1; progress.value = summary.checked;
    }
    const warning = el('Warning');
    const blocked = !!scan && scan.blocked >= BLOCKED_WARNING_AFTER && scan.reached === 0;
    warning.hidden = !blocked;
    warning.textContent = blocked
      ? 'Mail servers are not answering from this network, so mailbox results stay Unconfirmed (outgoing port 25 may be blocked). Emails whose domain does not exist or has no mail server are still found. For a faster scan, Stop and choose Domain check only.'
      : '';
    const rows = visibleRows(scan, {filter: el('Filter').value, search: el('Search').value, hideInactive: el('HideInactive').checked});
    const body = el('Results');
    body.replaceChildren();
    for (const row of rows.slice(0, MAX_RENDERED_ROWS)) body.appendChild(renderRow(row));
    const empty = el('Empty');
    empty.hidden = rows.length > 0;
    empty.textContent = !scan ? 'Press Scan client contacts to check every client contact’s email.'
      : el('Filter').value === 'invalid' && scan.loaded && !hasWork(scan) ? 'No invalid emails found.'
      : 'No contacts match this view yet.';
    el('More').hidden = rows.length <= MAX_RENDERED_ROWS;
    el('More').textContent = rows.length > MAX_RENDERED_ROWS ? 'Showing the first ' + MAX_RENDERED_ROWS + ' of ' + rows.length + '. Use the search box or export to see the rest.' : '';
    const unfinished = !!scan && (!scan.loaded || hasWork(scan));
    el('Start').disabled = running;
    el('Continue').disabled = running || !unfinished;
    el('Stop').disabled = !running || stopping;
    el('Clear').disabled = running || !scan;
    el('Mode').disabled = running;
    el('Export').disabled = !rows.length;
  }
  function textNode(tag, value, className) {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  }
  function renderRow({contact, status, result, entry}) {
    const tr = document.createElement('tr');
    const who = document.createElement('td');
    const link = document.createElement('a');
    link.href = contactLink(contact.id);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = contact.name || 'Contact #' + contact.id;
    who.appendChild(link);
    if (contact.inactive) who.appendChild(textNode('small', 'No longer with the company', 'ev-flags'));
    const company = textNode('td', contact.company || '—');
    const email = document.createElement('td');
    email.appendChild(textNode('span', contact.email || '—', 'ev-address'));
    if (result && result.suggestion) email.appendChild(textNode('small', 'Possible typo: ' + result.suggestion, 'ev-suggestion'));
    const state = document.createElement('td');
    state.appendChild(textNode('span', LABELS[status] || 'Unconfirmed', 'ev-badge ev-' + (Object.hasOwn(LABELS, status) ? status : 'unknown')));
    const detail = document.createElement('td');
    detail.appendChild(textNode('p', result ? result.reason
      : status === 'no_email' ? 'This contact has no email address in JobAdder.'
      : entry && entry.state === 'failed' ? 'Could not be checked: ' + entry.error + ' Press Continue to try again.'
      : running ? 'Waiting for its turn.' : 'Not checked in this scan.'));
    if (result && result.checked_at) {
      const checked = new Date(result.checked_at);
      if (!Number.isNaN(checked.getTime())) detail.appendChild(textNode('small', 'Checked ' + checked.toLocaleString(), 'ev-flags'));
    }
    tr.append(who, company, email, state, detail);
    return tr;
  }

  async function loadContacts(owned) {
    while (owned.nextOffset !== null && !owned.capped) {
      if (stopping || !current(owned)) return false;
      let page = null;
      for (let attempt = 0; ; attempt++) {
        try { page = await fetchPage(owned.nextOffset); break; }
        catch (error) {
          if (error.transient && attempt < PAGE_RETRIES && !stopping && current(owned)) { await pause(PAGE_RETRY_WAIT_MS); continue; }
          throw error;
        }
      }
      if (!current(owned)) return false;
      addContacts(owned, page.contacts);
      if (page.total !== null) owned.total = page.total;
      owned.nextOffset = page.nextOffset;
      scheduleRender();
    }
    owned.loaded = true;
    return true;
  }
  async function worker(owned, failures) {
    let busyWaits = 0;
    while (!stopping && !failures.error && current(owned)) {
      const pick = takeNext(owned);
      if (!pick) {
        if (!owned.inflight.size) return;
        await waitForChange();
        continue;
      }
      const {entry} = pick;
      entry.state = 'running';
      if (entry.domain) owned.inflight.add(entry.domain);
      let outcome = null, failure = null;
      try {
        outcome = await checkEmail(entry.email, pick.inferred ? 'quick' : owned.mode);
      } catch (error) {
        failure = error;
      } finally {
        if (entry.domain) owned.inflight.delete(entry.domain);
      }
      if (!current(owned)) { entry.state = 'pending'; notify(); return; }
      if (failure) {
        // A timeout or temporary server error affects this email, not the scan:
        // retry it, then set it aside so the rest of the list keeps going.
        entry.attempts = (entry.attempts || 0) + 1;
        if (entry.attempts <= CHECK_RETRIES) {
          entry.state = 'pending';
          notify();
          await pause(CHECK_RETRY_WAIT_MS);
          continue;
        }
        entry.state = 'failed';
        entry.error = failure.message;
        owned.failedInARow += 1;
        notify();
        if (owned.failedInARow >= MAX_FAILED_IN_A_ROW) {
          failures.error = Error(MAX_FAILED_IN_A_ROW + ' emails in a row could not be checked (' + failure.message + ') The connection may be down.');
          notify();
          return;
        }
        scheduleRender();
        continue;
      }
      if (outcome.busy) {
        entry.state = 'pending';
        notify();
        busyWaits += 1;
        if (busyWaits > MAX_BUSY_WAITS) {
          failures.error = Error('The verifier stayed busy. Wait for other email checks to finish, then press Continue.');
          notify();
          return;
        }
        await pause(BUSY_WAIT_MS);
        continue;
      }
      busyWaits = 0;
      owned.failedInARow = 0;
      recordResult(owned, entry, pick.inferred ? inferredResult(outcome.result) : outcome.result);
      notify();
      scheduleRender();
    }
  }
  async function run(fresh) {
    if (running) return;
    const namespace = accountNamespace();
    if (fresh || !scan) {
      scan = newScan(el('Mode').value, namespace);
    } else if (!sameAccount(scan)) {
      clear('The JobAdder account changed. Start a new scan.');
      return;
    }
    const owned = scan;
    // Emails set aside after failing get another try on Continue.
    for (const entry of owned.entries.values()) {
      if (entry.state === 'failed') { entry.state = 'pending'; entry.attempts = 0; entry.error = ''; }
    }
    owned.cursor = 0;
    owned.failedInARow = 0;
    const token = ++generation;
    running = true; stopping = false;
    const tab = typeof markTabRunning === 'function' ? markTabRunning('emailverifier') : null;
    const failures = {error: null};
    let failed = false;
    setMessage(owned.loaded ? 'Continuing the scan…' : 'Loading client contacts from JobAdder…');
    render();
    try {
      if (!owned.loaded && !await loadContacts(owned)) return;
      if (!owned.order.length) {
        setMessage(owned.contacts.length ? 'None of these contacts has an email address.' : 'No client contacts were found in JobAdder.');
        return;
      }
      setMessage('Checking emails without sending any messages. You can Stop at any time; results are kept.');
      render();
      await Promise.all(Array.from({length: WORKERS}, () => worker(owned, failures)));
      failed = !!failures.error;
    } catch (error) {
      failures.error = error;
      failed = true;
    } finally {
      if (token === generation) {
        running = false;
        if (failures.error) {
          setMessage(failures.error.status === 401
            ? failures.error.message
            : 'Stopped: ' + failures.error.message + ' Completed results are kept. Press Continue to resume.');
        } else if (current(owned)) {
          const failedCount = countState(owned, 'failed');
          const waiting = owned.loaded && owned.order.length ? countState(owned, 'pending') + countState(owned, 'running') : 0;
          if (!owned.loaded || waiting) {
            setMessage('Stopped. Completed results are kept; press Continue to check the rest.');
          } else if (owned.order.length) {
            const summary = summarize(owned);
            setMessage('Finished. ' + summary.checked + ' unique emails checked for ' + summary.contacts + ' contacts; '
              + summary.counts.invalid + (summary.counts.invalid === 1 ? ' contact has' : ' contacts have') + ' an invalid email.'
              + (failedCount ? ' ' + failedCount + (failedCount === 1 ? ' email' : ' emails') + ' could not be checked; press Continue to try again.' : '')
              + (owned.capped ? ' Only the first ' + MAX_CONTACTS + ' contacts were scanned.' : ''));
          }
        }
        stopping = false;
        render();
      }
      if (tab !== null) {
        if (failed && typeof markTabFailed === 'function') markTabFailed('emailverifier', tab);
        else if (typeof markTabDone === 'function') markTabDone('emailverifier', tab);
      }
    }
  }
  function clear(message) {
    generation += 1;
    running = false;
    stopping = false;
    scan = null;
    notify();
    setMessage(message || '');
    render();
  }
  let ready = false;
  function init() {
    if (ready || !el('Start')) return;
    ready = true;
    el('Start').addEventListener('click', () => run(true));
    el('Continue').addEventListener('click', () => run(false));
    el('Stop').addEventListener('click', () => { stopping = true; notify(); setMessage('Stopping after the current checks…'); render(); });
    el('Clear').addEventListener('click', () => { if (!running) clear(''); });
    el('Filter').addEventListener('change', render);
    el('HideInactive').addEventListener('change', render);
    el('Search').addEventListener('input', render);
    el('Export').addEventListener('click', () => {
      const rows = visibleRows(scan, {filter: el('Filter').value, search: el('Search').value, hideInactive: el('HideInactive').checked});
      if (!rows.length) return;
      const url = URL.createObjectURL(new Blob(['﻿' + makeCSV(rows)], {type: 'text/csv;charset=utf-8'}));
      const link = document.createElement('a');
      link.href = url; link.download = 'CV-Studio-JobAdder-Contact-Emails.csv'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    render();
  }
  // Called by jobadder-upload.js when the JobAdder account signs out or changes:
  // one account's contacts must never stay on screen under another.
  window.clearEmailVerifierJobAdderAccountState = () => clear(scan ? 'The JobAdder account changed, so the previous scan was cleared.' : '');
  window.addEventListener?.('pagehide', () => { leaving = true; stopping = true; notify(); });
  window.addEventListener?.('pageshow', () => { leaving = false; });
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {emailKey, domainOf, webBase, contactLink, normalizePage, newScan, addContacts, takeNext, hasWork, inferredResult, recordResult, summarize, visibleRows, makeCSV, INFERRED_CATCH_ALL, MAX_CONTACTS};
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
}());
