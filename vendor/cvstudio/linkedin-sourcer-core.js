(function(){
const MODES = new Set(['standard', 'lite', 'recruiter']);
const pause = (ms, signal) => new Promise((resolve, reject) => {
  if (signal?.aborted) return reject(new Error('Stopped.'));
  const timer = setTimeout(done, ms);
  const cancel = () => { clearTimeout(timer); signal?.removeEventListener('abort', cancel); reject(new Error('Stopped.')); };
  function done() { signal?.removeEventListener('abort', cancel); resolve(); }
  signal?.addEventListener('abort', cancel, {once: true});
});
function isSearchURL(value, mode) {
  try {
    const url = new URL(value);
    return url.origin === 'https://www.linkedin.com' && (mode === 'standard' ?
      /^\/search\/results\/people\/?$/.test(url.pathname) :
      /^\/talent\//.test(url.pathname) && !/\/profile\//.test(url.pathname));
  } catch { return false; }
}
function profileURL(value) {
  try {
    const u = new URL(value);
    const path = u.pathname.replace(/\/+$/, '');
    if (u.origin !== 'https://www.linkedin.com' || u.username || u.password ||
        !/^\/(in\/[^/]+|talent\/(?:hire\/)?profile\/[^/]+)$/.test(path) ||
        /[\x00-\x20\\]/.test(decodeURIComponent(path))) return '';
    return u.origin + path;
  } catch { return ''; }
}
function mergeCandidates(previous, incoming, checked = false) {
  const result = new Map(previous.map(row => [row.url, row]));
  for (const candidate of incoming) {
    const url = profileURL(candidate.url);
    if (!url) throw Error('An unobserved or invalid profile link was returned.');
    const old = result.get(url);
    if (old?.checked && !checked) continue;
    result.set(url, {...candidate, url, checked: checked || !!old?.checked});
  }
  return [...result.values()].sort((a, b) => b.score - a.score);
}
function csv(rows) {
  const cell = value => {
    let s = String(value ?? '');
    if (/^[\s]*[=+@-]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  };
  const records = [['Name', 'LinkedIn profile', 'Evidence match / 100', 'Read', 'Supporting profile text', 'Still unknown'],
    ...rows.map(r => [r.name, r.publicUrl || r.url, r.score, r.checked ? 'Profile detail' : 'Search card only', r.evidence.join(' | '), r.unknowns.join(' | ')])];
  return '\ufeff' + records.map(row => row.map(cell).join(',')).join('\r\n');
}

class Agent {
  constructor({api, browser, update, signal, wait = pause}) {
    Object.assign(this, {api, browser, update, signal, wait});
    this.run = null;
    this.results = [];
    this.profileTab = null;
  }
  check() { if (this.signal.aborted) throw Error('Stopped.'); }
  async read(tab, method, args = []) {
    this.check();
    const result = await this.browser.read(tab, method, args);
    this.check();
    return result;
  }
  async waitSearch(tab, mode, oldSignature = '') {
    let previous = '', stable = 0;
    for (let attempt = 0; attempt < 30; attempt++) {
      const snapshot = await this.read(tab, 'readSearch', [mode]);
      if (!snapshot || !Array.isArray(snapshot.profiles) || typeof snapshot.signature !== 'string') {
        throw Error('LinkedIn results could not be read. Refresh LinkedIn, then reload and reconnect the latest companion.');
      }
      if (snapshot.empty) return snapshot;
      if (snapshot.signature && snapshot.signature !== oldSignature) {
        stable = snapshot.signature === previous ? stable + 1 : 0;
        previous = snapshot.signature;
        if (stable >= 2) return snapshot;
      }
      await this.wait(1000, this.signal);
    }
    throw Error('Results did not become ready, or the layout is not recognized. The agent stopped.');
  }
  async start(options) {
    try {
      const tab = await this.browser.activeTab();
      this.check();
      if ((options.use_open_search || options.mode !== 'standard') && !isSearchURL(tab.url, options.mode)) {
        throw Error('Open the selected LinkedIn search first.');
      }
      this.run = (await this.api('/api/start', options)).run;
      this.update({run: this.run, status: 'Preparing your search…', results: this.results});
      const reply = await this.api('/api/plan', {run_id: this.run.id});
      this.check();
      this.run = reply.run;
      this.update({run: this.run, plan: reply.plan});
      if (options.use_open_search) {
        if (!isSearchURL(tab.url, options.mode)) throw Error('Open the selected LinkedIn search first.');
      } else if (options.mode === 'standard') {
        await this.browser.navigate(tab.id, 'https://www.linkedin.com/search/results/people/?keywords=' + encodeURIComponent(reply.plan.query));
        this.check();
        if (reply.plan.country) {
          this.update({status: 'Selecting ' + reply.plan.country + ' in LinkedIn Locations…'});
          if (await this.read(tab.id, 'setCountry', [reply.plan.country]) !== true) throw Error('LinkedIn did not confirm the requested Locations filter. Start a new search.');
        }
      } else {
        if (reply.plan.country) throw Error('For automatic country selection, choose LinkedIn People search. In Recruiter, set Locations first and use the search already open.');
        if (!isSearchURL(tab.url, options.mode)) throw Error('Open Recruiter search first, then start again.');
        await this.read(tab.id, 'search', [options.mode, reply.plan.query]);
      }
      const seen = new Set(), inspected = new Set();
      let oldSignature = '';
      for (let page = 1; page <= options.max_pages; page++) {
        this.check();
        this.update({status: `Reading search page ${page} of ${options.max_pages}…`, page});
        const snapshot = await this.waitSearch(tab.id, options.mode, oldSignature);
        if (snapshot.empty) { this.update({status: page === 1 ? 'LinkedIn found no matches for this search.' : 'LinkedIn returned no more results.'}); break; }
        if (seen.has(snapshot.signature)) throw Error('LinkedIn repeated a result page. The agent stopped.');
        seen.add(snapshot.signature);
        oldSignature = snapshot.signature;
        const reply = await this.api('/api/review', {run_id: this.run.id, stage: 'screen', page, profiles: snapshot.profiles});
        this.check();
        this.run = reply.run;
        this.results = mergeCandidates(this.results, reply.candidates);
        this.update({run: this.run, results: this.results, status: `Inspecting promising profiles from page ${page}…`});
        const details = [];
        for (const candidate of reply.candidates) {
          this.check();
          if (inspected.has(candidate.url)) continue;
          if (!profileURL(candidate.url) || !snapshot.profiles.some(p => p.id === candidate.id && p.url === candidate.url)) throw Error('An unobserved profile was rejected.');
          if (this.profileTab === null) this.profileTab = await this.browser.createTab(candidate.url);
          else await this.browser.navigate(this.profileTab, candidate.url);
          await this.wait(2000, this.signal);
          const profile = await this.read(this.profileTab, 'readProfile', [candidate.url]);
          details.push({...candidate, text: profile.text, name: profile.name || candidate.name,
                        publicUrl: profileURL(profile.publicUrl) || ''});
          inspected.add(candidate.url);
        }
        if (details.length) {
          const full = await this.api('/api/review', {run_id: this.run.id, stage: 'detail', page, profiles: details});
          this.check();
          this.run = full.run;
          const assessed = full.candidates.map(row => ({...row, publicUrl: details.find(d => d.id === row.id)?.publicUrl || ''}));
          this.results = mergeCandidates(this.results, assessed, true);
          this.update({run: this.run, results: this.results});
        }
        if (!snapshot.hasNext || page === options.max_pages) {
          this.update({status: page === options.max_pages ? 'Finished the requested pages.' :
            snapshot.paginationKnown ? 'Reached the last result page.' : 'Finished this page. No recognized next-page control was found.'});
          break;
        }
        this.check();
        this.update({status: `Opening search page ${page + 1}…`});
        if (!await this.read(tab.id, 'next', [options.mode, snapshot.signature])) break;
        await this.wait(1500, this.signal);
      }
    } finally {
      if (!this.run && this.signal.aborted) {
        try { this.run = (await this.api('/api/status', null, true)).run; }
        catch { /* The panel reports that the bridge could not be reached. */ }
      }
      if (this.run) {
        try { this.run = (await this.api('/api/stop', {run_id: this.run.id}, true)).run; }
        catch { /* The next panel opening can still explicitly stop the run. */ }
        this.update({run: this.run});
      }
      // Never close a user-created tab or a profile they have navigated elsewhere.
      if (this.profileTab !== null) await this.browser.closeOwnedTab(this.profileTab);
    }
  }
}

window.CVLinkedinCore = {Agent, csv, profileURL, isSearchURL};
})();
