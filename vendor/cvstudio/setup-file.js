/* Team setup file: one JSON file a team owner creates once and new users import
 * in one click (Settings → Integrations & Data). Importing fills the existing
 * Settings fields and runs their own Save actions, so every value is stored
 * exactly as if it had been typed: secrets go to the protected store, never to
 * browser storage. Secrets are only written into a file when the owner types
 * them into this card while creating it.
 */
(function () {
  'use strict';
  const PRODUCT = 'CV Studio setup', SCHEMA = 1, MAX_BYTES = 64 * 1024;
  const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const TENANT = /^[A-Za-z0-9._-]{1,100}$/;
  const AI = {
    main:{label:'Main AI key', providers:['anthropic', 'openai', 'deepseek']},
    lead:{label:'Lead Finder key', providers:['anthropic', 'openai', 'deepseek']},
    search:{label:'Search provider key', providers:['tavily', 'serpapi']},
    enrichment:{label:'Enrichment key', providers:['apollo']}
  };
  const NAMES = {anthropic:'Claude', openai:'GPT (OpenAI)', deepseek:'DeepSeek', tavily:'Tavily', serpapi:'SerpAPI', apollo:'Apollo'};
  const el = id => document.getElementById(id);
  let busy = false;

  function text(value, max) {
    if (value === undefined || value === null || value === '') return '';
    if (typeof value !== 'string') throw Error('The setup file has a value that is not text.');
    const clean = value.trim();
    if (clean.length > max || /[\x00-\x1f\x7f]/.test(clean)) throw Error('The setup file has a value that is too long or contains hidden characters.');
    return clean;
  }
  function section(data, key) {
    const value = data[key];
    if (value === undefined || value === null) return {};
    if (typeof value !== 'object' || Array.isArray(value)) throw Error('The setup file section "' + key + '" is not valid.');
    return value;
  }
  function app(data, key, name) {
    const raw = section(data, key), clientId = text(raw.client_id, 100), tenant = text(raw.tenant, 100) || 'common';
    if (!clientId) return null;
    if (!GUID.test(clientId)) throw Error('The ' + name + ' Client ID in the setup file is not a valid Microsoft app ID.');
    if (!TENANT.test(tenant)) throw Error('The ' + name + ' tenant in the setup file is not valid.');
    return {client_id:clientId, tenant};
  }
  // Checks the whole file before anything is changed.
  function parse(source) {
    if (typeof source !== 'string' || source.length > MAX_BYTES) throw Error('Choose a CV Studio setup file (.json, under 64 KB).');
    let data;
    try { data = JSON.parse(source); } catch { throw Error('This file is not a CV Studio setup file.'); }
    if (!data || typeof data !== 'object' || Array.isArray(data) || data.product !== PRODUCT) throw Error('This file is not a CV Studio setup file.');
    if (data.schema !== SCHEMA) throw Error('This setup file was made by a different CV Studio version. Ask for a new one.');
    const ja = section(data, 'jobadder'), plan = {};
    const jaId = text(ja.client_id, 200), jaSecret = text(ja.client_secret, 500);
    if (jaSecret && !jaId) throw Error('The setup file has a JobAdder Client Secret without its Client ID.');
    if (jaId) plan.jobadder = {client_id:jaId, client_secret:jaSecret};
    const outlook = app(data, 'outlook', 'Outlook'), onenote = app(data, 'onenote', 'OneNote');
    if (outlook) plan.outlook = outlook;
    if (onenote) plan.onenote = onenote;
    const ai = section(data, 'ai');
    for (const [slot, rule] of Object.entries(AI)) {
      const raw = ai[slot] === undefined || ai[slot] === null ? {} : ai[slot];
      if (typeof raw !== 'object' || Array.isArray(raw)) throw Error('The setup file AI section is not valid.');
      const provider = text(raw.provider, 20).toLowerCase(), key = text(raw.key, 500);
      if (!key) continue; // a provider without its key changes nothing
      if (!rule.providers.includes(provider)) throw Error('The setup file ' + rule.label + ' names an unknown provider.');
      plan[slot] = {provider, key};
    }
    if (!Object.keys(plan).length) throw Error('This setup file has nothing to fill in.');
    return plan;
  }
  function describe(plan) {
    const rows = [];
    if (plan.jobadder) rows.push('JobAdder Client ID' + (plan.jobadder.client_secret ? ' and Client Secret' : ''));
    if (plan.outlook) rows.push('Outlook app (Client ID, tenant ' + plan.outlook.tenant + ')');
    if (plan.onenote) rows.push('OneNote app (Client ID, tenant ' + plan.onenote.tenant + ')');
    for (const [slot, rule] of Object.entries(AI)) if (plan[slot]) rows.push(rule.label + ' (' + NAMES[plan[slot].provider] + ')');
    return rows;
  }
  function field(id, value) { const node = el(id); if (node) node.value = value; return node; }
  function choose(id, value, onChange) { field(id, value); if (typeof onChange === 'function') onChange(); }
  const call = name => typeof window[name] === 'function' ? window[name] : null;

  // Fills each Settings field and runs that section's own Save. Each part is
  // reported separately; one failure does not undo the parts before it.
  async function apply(plan) {
    const done = [], todo = [];
    if (plan.jobadder) {
      const {client_id, client_secret} = plan.jobadder;
      field('settingsJobAdderClientId', client_id); field('settingsJobAdderClientSecret', client_secret);
      const known = call('hasJASavedSecretFor')?.(client_id);
      if (!client_secret && !known) todo.push('JobAdder: Client ID filled in. Enter the Client Secret, then Save settings.');
      else if (await call('saveJobAdderSettings')?.()) done.push('JobAdder');
      else todo.push('JobAdder: settings were not saved. Check them and Save settings.');
    }
    if (plan.outlook) {
      field('settingsOutlookClientId', plan.outlook.client_id); field('settingsOutlookTenant', plan.outlook.tenant);
      if (await call('ppcSaveOutlookSettingsFromPanel')?.()) done.push('Outlook'); else todo.push('Outlook: settings were not saved.');
    }
    if (plan.onenote) {
      field('settingsOneNoteClientId', plan.onenote.client_id); field('settingsOneNoteTenant', plan.onenote.tenant);
      const save = call('oneNoteApiSaveSettings');
      if (save) { save(true); done.push('OneNote'); } else todo.push('OneNote: settings were not saved.');
    }
    if (plan.main) {
      choose('mainProviderSel', plan.main.provider, call('onMainProviderChange')); field('keyInput', plan.main.key);
      // The key box is emptied only when the key was saved.
      await call('saveKey')?.();
      if (!el('keyInput')?.value) done.push('Main AI key'); else todo.push('Main AI key: not saved.');
    }
    if (plan.lead) {
      choose('leadProviderSel', plan.lead.provider, call('onLeadProviderChange')); field('leadKeyInput', plan.lead.key);
      await call('saveLeadKey')?.();
      if (!el('leadKeyInput')?.value) done.push('Lead Finder key'); else todo.push('Lead Finder key: not saved.');
    }
    if (plan.search) {
      choose('searchProviderSel', plan.search.provider); field('searchProviderKeyInput', plan.search.key);
      await call('saveSearchProvider')?.(); field('searchProviderKeyInput', ''); done.push('Search provider');
    }
    if (plan.enrichment) {
      choose('enrichmentProviderSel', plan.enrichment.provider); field('enrichmentProviderKeyInput', plan.enrichment.key);
      await call('saveEnrichmentProvider')?.(); field('enrichmentProviderKeyInput', ''); done.push('Enrichment provider');
    }
    return {done, todo};
  }
  function status(value) { const node = el('settingsSetupFileStatus'); if (node) node.textContent = value; }
  function lock(value) { busy = value; for (const id of ['settingsSetupFileImport', 'settingsSetupFileCreate']) { const node = el(id); if (node) node.disabled = value; } }

  async function importFile(file) {
    if (busy || !file) return;
    lock(true);
    try {
      if (file.size > MAX_BYTES) throw Error('Choose a CV Studio setup file (.json, under 64 KB).');
      const plan = parse(await file.text());
      if (!window.confirm('Fill in these settings from the setup file?\n\n• ' + describe(plan).join('\n• ') + '\n\nThe current values for these settings will be replaced.')) { status('Import cancelled. Nothing was changed.'); return; }
      status('Filling in settings…');
      const {done, todo} = await apply(plan);
      status((done.length ? 'Filled in: ' + done.join(', ') + '. ' : '') + todo.join(' ') +
        ' Next: connect JobAdder, Outlook and Apollo with each person\'s own sign-in.');
      call('refreshIntegrationDiagnostics')?.();
    } catch (error) { status(error.message + ' Nothing was changed.'); }
    finally { lock(false); }
  }
  // The file holds every saved non-secret ID, plus any secret the owner typed
  // into this card for this file only.
  function build() {
    const data = {product:PRODUCT, schema:SCHEMA, created_at:new Date().toISOString()};
    const jaId = String(call('getJAClientId')?.() || '').trim(), jaSecret = String(el('settingsSetupJobAdderSecret')?.value || '').trim();
    if (jaId) data.jobadder = {client_id:jaId, ...(jaSecret ? {client_secret:jaSecret} : {})};
    const outlook = call('ppcOutlookClientLoad')?.();
    if (outlook?.client_id) data.outlook = {client_id:outlook.client_id, tenant:outlook.tenant || 'common'};
    let onenoteId = '', onenoteTenant = 'common';
    try { onenoteId = localStorage.getItem('onenote_ms_client_id') || ''; onenoteTenant = localStorage.getItem('onenote_ms_tenant') || 'common'; } catch {}
    if (onenoteId) data.onenote = {client_id:onenoteId, tenant:onenoteTenant};
    const saved = {
      main:call('getProvider')?.(), lead:call('getSavedLeadProvider')?.(),
      search:call('getSearchProviderConfig')?.().provider, enrichment:call('getEnrichmentProviderConfig')?.().provider
    };
    const ai = {};
    for (const slot of Object.keys(AI)) {
      const key = String(el('settingsSetup' + slot[0].toUpperCase() + slot.slice(1) + 'Key')?.value || '').trim();
      if (key && AI[slot].providers.includes(saved[slot])) ai[slot] = {provider:saved[slot], key};
      else if (key) throw Error(AI[slot].label + ': choose and save its provider in Settings first.');
    }
    if (Object.keys(ai).length) data.ai = ai;
    if (jaSecret && !jaId) throw Error('Save the JobAdder Client ID first, then add its Client Secret here.');
    return data;
  }
  function createFile() {
    if (busy) return;
    try {
      const data = build(), plan = parse(JSON.stringify(data));
      const secrets = !!(data.jobadder?.client_secret || data.ai);
      if (secrets && !window.confirm('This setup file will contain secrets in plain text. Send it privately (not in a group chat or email list) and ask people to delete it after importing. Create it?')) return;
      const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}), url = URL.createObjectURL(blob), link = document.createElement('a');
      // A detached link: its click must not reach Settings' "click outside closes" listener.
      link.href = url; link.download = 'CV-Studio-setup.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      for (const id of ['settingsSetupJobAdderSecret', 'settingsSetupMainKey', 'settingsSetupLeadKey', 'settingsSetupSearchKey', 'settingsSetupEnrichmentKey']) field(id, '');
      status('Setup file created with: ' + describe(plan).join(', ') + '.');
    } catch (error) { status(error.message); }
  }
  function init() {
    const input = el('settingsSetupFileInput');
    if (!input || input.dataset.ready) return;
    input.dataset.ready = '1';
    el('settingsSetupFileImport')?.addEventListener('click', () => { if (!busy) input.click(); });
    input.addEventListener('change', () => { const file = input.files && input.files[0]; input.value = ''; void importFile(file); });
    el('settingsSetupFileCreate')?.addEventListener('click', createFile);
  }
  window.cvStudioSetupFile = {parse, describe, apply, build, importFile, init};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
