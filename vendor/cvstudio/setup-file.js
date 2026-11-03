/* Team setup file: one JSON file a team owner creates once and new users import
 * in one click (Settings → Integrations & Data). Importing fills the existing
 * Settings fields and runs their own Save actions, so every value is stored
 * exactly as if it had been typed: secrets go to the protected store, never to
 * browser storage. The create form shows every column (app ID, tenant, secret,
 * provider and key); saved IDs and tenants are filled in for the owner, while
 * secrets are only written into a file when the owner types them for it.
 */
(function () {
  'use strict';
  // Schema 2 adds a key per AI provider; schema 1 files still import.
  const PRODUCT = 'CV Studio setup', SCHEMA = 2, READS = [1, 2], MAX_BYTES = 64 * 1024;
  const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const TENANT = /^[A-Za-z0-9._-]{1,100}$/;
  const AI_PROVIDERS = ['anthropic', 'openai', 'deepseek'];
  const SLOTS = {
    lead:{label:'Lead Finder key', providers:AI_PROVIDERS},
    search:{label:'Search provider key', providers:['tavily', 'serpapi']},
    enrichment:{label:'Enrichment key', providers:['apollo']}
  };
  const APPS = [['outlook', 'Outlook'], ['onenote', 'OneNote']];
  const NAMES = {anthropic:'Claude', openai:'OpenAI', deepseek:'DeepSeek', tavily:'Tavily', serpapi:'SerpAPI', apollo:'Apollo'};
  const cap = name => name[0].toUpperCase() + name.slice(1);
  const SECRET_BOXES = ['settingsSetupJobAdderSecret', ...AI_PROVIDERS.map(p => 'settingsSetupKey' + cap(p)),
    ...Object.keys(SLOTS).map(slot => 'settingsSetup' + cap(slot) + 'Key')];
  const SAVED_BOXES = ['settingsSetupJobAdderId', 'settingsSetupOutlookId', 'settingsSetupOutlookTenant', 'settingsSetupOneNoteId',
    'settingsSetupOneNoteTenant', 'settingsSetupMainProvider', ...Object.keys(SLOTS).map(slot => 'settingsSetup' + cap(slot) + 'Provider')];
  const el = id => document.getElementById(id);
  const value = id => String(el(id)?.value || '').trim();
  let busy = false;

  function text(raw, max) {
    if (raw === undefined || raw === null || raw === '') return '';
    if (typeof raw !== 'string') throw Error('The setup file has a value that is not text.');
    const clean = raw.trim();
    if (clean.length > max || /[\x00-\x1f\x7f]/.test(clean)) throw Error('The setup file has a value that is too long or contains hidden characters.');
    return clean;
  }
  function section(data, key, where = 'section "' + key + '"') {
    const raw = data[key];
    if (raw === undefined || raw === null) return {};
    if (typeof raw !== 'object' || Array.isArray(raw)) throw Error('The setup file ' + where + ' is not valid.');
    return raw;
  }
  function slot(ai, name) {
    const raw = section(ai, name, 'AI section');
    return {provider:text(raw.provider, 20).toLowerCase(), key:text(raw.key, 500)};
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
    if (!READS.includes(data.schema)) throw Error('This setup file was made by a different CV Studio version. Ask for a new one.');
    const ja = section(data, 'jobadder'), plan = {};
    const jaId = text(ja.client_id, 200), jaSecret = text(ja.client_secret, 500);
    if (jaSecret && !jaId) throw Error('The setup file has a JobAdder Client Secret without its Client ID.');
    if (jaId) plan.jobadder = {client_id:jaId, client_secret:jaSecret};
    for (const [key, name] of APPS) { const found = app(data, key, name); if (found) plan[key] = found; }
    const ai = section(data, 'ai'), keys = {};
    for (const [provider, raw] of Object.entries(section(ai, 'keys', 'AI section'))) {
      if (!AI_PROVIDERS.includes(provider)) throw Error('The setup file has an AI key for an unknown provider.');
      const key = text(raw, 500);
      if (key) keys[provider] = key;
    }
    // Schema 1 holds one main key as {provider, key}.
    const legacy = slot(ai, 'main');
    if (legacy.key) {
      if (!AI_PROVIDERS.includes(legacy.provider)) throw Error('The setup file Main AI key names an unknown provider.');
      if (keys[legacy.provider] && keys[legacy.provider] !== legacy.key) throw Error('The setup file has two different ' + NAMES[legacy.provider] + ' keys.');
      keys[legacy.provider] = legacy.key;
    }
    const named = text(ai.main_provider, 20).toLowerCase() || (legacy.key ? legacy.provider : '');
    if (named && !AI_PROVIDERS.includes(named)) throw Error('The setup file Main AI names an unknown provider.');
    const withKeys = Object.keys(keys);
    if (withKeys.length) {
      const main = named || (withKeys.length === 1 ? withKeys[0] : '');
      if (!keys[main]) throw Error('The setup file Main AI provider has no key in the file.');
      plan.main = {provider:main, keys};
    }
    for (const [name, rule] of Object.entries(SLOTS)) {
      const found = slot(ai, name);
      if (!found.key) continue; // a provider without its key changes nothing
      if (!rule.providers.includes(found.provider)) throw Error('The setup file ' + rule.label + ' names an unknown provider.');
      plan[name] = found;
    }
    if (!Object.keys(plan).length) throw Error('This setup file has nothing to fill in.');
    return plan;
  }
  function describe(plan) {
    const rows = [];
    if (plan.jobadder) rows.push('JobAdder Client ID' + (plan.jobadder.client_secret ? ' and Client Secret' : ''));
    for (const [key, name] of APPS) if (plan[key]) rows.push(name + ' app (Client ID, tenant ' + plan[key].tenant + ')');
    if (plan.main) {
      const others = Object.keys(plan.main.keys).filter(provider => provider !== plan.main.provider);
      rows.push('Main AI key (' + NAMES[plan.main.provider] + ')');
      if (others.length) rows.push('Other AI keys (' + others.map(provider => NAMES[provider]).join(', ') + ')');
    }
    for (const [name, rule] of Object.entries(SLOTS)) if (plan[name]) rows.push(rule.label + ' (' + NAMES[plan[name].provider] + ')');
    return rows;
  }
  // What the file leaves for each person to fill in themselves.
  function missing(plan) {
    const rows = [];
    if (!plan.jobadder) rows.push('JobAdder Client ID and Client Secret');
    else if (!plan.jobadder.client_secret) rows.push('JobAdder Client Secret');
    for (const [key, name] of APPS) if (!plan[key]) rows.push(name + ' app ID and tenant');
    if (!plan.main) rows.push('Main AI key');
    for (const [name, rule] of Object.entries(SLOTS)) if (!plan[name]) rows.push(rule.label + ' (optional)');
    return rows;
  }
  function field(id, next) { const node = el(id); if (node) node.value = next; return node; }
  function choose(id, next, onChange) { field(id, next); if (typeof onChange === 'function') onChange(); }
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
      // Saving a key also selects its provider, so the main one is saved last.
      const {provider:main, keys} = plan.main;
      for (const provider of Object.keys(keys).filter(other => other !== main).concat(main)) {
        choose('mainProviderSel', provider, call('onMainProviderChange')); field('keyInput', keys[provider]);
        // The key box is emptied only when the key was saved.
        await call('saveKey')?.();
        const label = provider === main ? 'Main AI key (' + NAMES[main] + ')' : NAMES[provider] + ' key';
        if (!el('keyInput')?.value) done.push(label); else todo.push(label + ': not saved.');
      }
    }
    if (plan.lead) {
      choose('leadProviderSel', plan.lead.provider, call('onLeadProviderChange')); field('leadKeyInput', plan.lead.key);
      await call('saveLeadKey')?.();
      if (!el('leadKeyInput')?.value) done.push('Lead Finder key'); else todo.push('Lead Finder key: not saved.');
    }
    if (plan.search) {
      choose('searchProviderSel', plan.search.provider); field('searchProviderKeyInput', plan.search.key);
      // Only a confirmed save clears the box; a failure leaves the key to retry.
      if (await call('saveSearchProvider')?.() === true) { field('searchProviderKeyInput', ''); done.push('Search provider'); } else todo.push('Search provider key: not saved.');
    }
    if (plan.enrichment) {
      choose('enrichmentProviderSel', plan.enrichment.provider); field('enrichmentProviderKeyInput', plan.enrichment.key);
      if (await call('saveEnrichmentProvider')?.() === true) { field('enrichmentProviderKeyInput', ''); done.push('Enrichment provider'); } else todo.push('Enrichment key: not saved.');
    }
    return {done, todo};
  }
  function status(next) { const node = el('settingsSetupFileStatus'); if (node) node.textContent = next; }
  function lock(next) { busy = next; for (const id of ['settingsSetupFileImport', 'settingsSetupFileCreate']) { const node = el(id); if (node) node.disabled = next; } }
  const bullets = rows => '• ' + rows.join('\n• ');

  async function importFile(file) {
    if (busy || !file) return;
    lock(true);
    try {
      if (file.size > MAX_BYTES) throw Error('Choose a CV Studio setup file (.json, under 64 KB).');
      const plan = parse(await file.text()), absent = missing(plan);
      if (!window.confirm('Fill in these settings from the setup file?\n\n' + bullets(describe(plan)) +
        '\n\nThe current values for these settings will be replaced.' +
        (absent.length ? '\n\nNot in this file (fill these in yourself if you use them):\n' + bullets(absent) : ''))) { status('Import cancelled. Nothing was changed.'); return; }
      status('Filling in settings…');
      const {done, todo} = await apply(plan);
      status((done.length ? 'Filled in: ' + done.join(', ') + '. ' : '') + todo.join(' ') +
        (absent.length ? ' Not in the file: ' + absent.join(', ') + '.' : '') +
        ' Next: connect JobAdder, Outlook and Apollo with each person\'s own sign-in.');
      call('refreshIntegrationDiagnostics')?.();
    } catch (error) { status(error.message + ' Nothing was changed.'); }
    finally { lock(false); }
  }

  // Create form. Saved IDs, tenants and providers are filled in (without
  // overwriting a box the owner has edited); secret boxes only say whether a
  // secret is saved here, because saved secrets are never returned to the page.
  function hints() {
    const configured = window._secureAiConfigured || {};
    const mark = (id, saved) => { const node = el(id); if (node) node.placeholder = saved ? 'Saved on this computer · type it to include' : 'Leave blank to leave out'; };
    mark('settingsSetupJobAdderSecret', !!call('hasJASavedSecretFor')?.(value('settingsSetupJobAdderId')));
    for (const provider of AI_PROVIDERS) mark('settingsSetupKey' + cap(provider), !!configured['main_' + provider]);
    for (const name of Object.keys(SLOTS)) mark('settingsSetup' + cap(name) + 'Key', !!configured[name + '_' + value('settingsSetup' + cap(name) + 'Provider')]);
  }
  function fillFromSaved() {
    const outlook = call('ppcOutlookClientLoad')?.() || {};
    let onenoteId = '', onenoteTenant = '';
    try { onenoteId = localStorage.getItem('onenote_ms_client_id') || ''; onenoteTenant = localStorage.getItem('onenote_ms_tenant') || ''; } catch {}
    const known = (list, provider) => list.includes(provider) ? provider : '';
    const saved = {
      settingsSetupJobAdderId:String(call('getJAClientId')?.() || '').trim(),
      settingsSetupOutlookId:outlook.client_id || '', settingsSetupOutlookTenant:outlook.client_id ? outlook.tenant || 'common' : '',
      settingsSetupOneNoteId:onenoteId, settingsSetupOneNoteTenant:onenoteId ? onenoteTenant || 'common' : '',
      settingsSetupMainProvider:known(AI_PROVIDERS, call('getProvider')?.()),
      settingsSetupLeadProvider:known(SLOTS.lead.providers, call('getSavedLeadProvider')?.()),
      settingsSetupSearchProvider:known(SLOTS.search.providers, call('getSearchProviderConfig')?.()?.provider),
      settingsSetupEnrichmentProvider:known(SLOTS.enrichment.providers, call('getEnrichmentProviderConfig')?.()?.provider)
    };
    for (const [id, next] of Object.entries(saved)) { const node = el(id); if (node && next && !node.dataset.edited) node.value = next; }
    hints();
  }
  // The file holds exactly what the form shows; blank boxes are left out.
  function build() {
    const data = {product:PRODUCT, schema:SCHEMA, created_at:new Date().toISOString()};
    const jaId = value('settingsSetupJobAdderId'), jaSecret = value('settingsSetupJobAdderSecret');
    if (jaSecret && !jaId) throw Error('Type the JobAdder Client ID for this Client Secret.');
    if (jaId) data.jobadder = {client_id:jaId, ...(jaSecret ? {client_secret:jaSecret} : {})};
    for (const [key, name] of APPS) {
      const id = value('settingsSetup' + name + 'Id'), tenant = value('settingsSetup' + name + 'Tenant') || 'common';
      if (id) data[key] = {client_id:id, tenant};
    }
    const ai = {}, keys = {};
    for (const provider of AI_PROVIDERS) { const key = value('settingsSetupKey' + cap(provider)); if (key) keys[provider] = key; }
    if (Object.keys(keys).length) {
      const main = value('settingsSetupMainProvider');
      if (!keys[main]) throw Error('Main AI is ' + (NAMES[main] || 'not chosen') + ': type its key too, or choose the provider whose key you typed.');
      ai.main_provider = main; ai.keys = keys;
    }
    for (const name of Object.keys(SLOTS)) {
      const key = value('settingsSetup' + cap(name) + 'Key');
      if (key) ai[name] = {provider:value('settingsSetup' + cap(name) + 'Provider'), key};
    }
    if (Object.keys(ai).length) data.ai = ai;
    if (!data.jobadder && !data.outlook && !data.onenote && !data.ai) throw Error('Fill in at least one ID or key first.');
    return data;
  }
  function createFile() {
    if (busy) return;
    try {
      const data = build(), plan = parse(JSON.stringify(data)), absent = missing(plan);
      const secrets = !!(data.jobadder?.client_secret || data.ai);
      if (secrets && !window.confirm('This setup file will contain secrets in plain text. Send it privately (not in a group chat or email list) and ask people to delete it after importing. Create it?')) return;
      const blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'}), url = URL.createObjectURL(blob), link = document.createElement('a');
      // A detached link: its click must not reach Settings' "click outside closes" listener.
      link.href = url; link.download = 'CV-Studio-setup.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      for (const id of SECRET_BOXES) field(id, '');
      status('Setup file created with: ' + describe(plan).join(', ') + '.' + (absent.length ? ' Not in the file: ' + absent.join(', ') + '.' : ''));
    } catch (error) { status(error.message); }
  }
  function init() {
    const input = el('settingsSetupFileInput');
    if (!input || input.dataset.ready) return;
    input.dataset.ready = '1';
    el('settingsSetupFileImport')?.addEventListener('click', () => { if (!busy) input.click(); });
    input.addEventListener('change', () => { const file = input.files && input.files[0]; input.value = ''; void importFile(file); });
    el('settingsSetupFileCreate')?.addEventListener('click', createFile);
    const form = el('settingsSetupCreate');
    form?.addEventListener('toggle', () => { if (form.open) fillFromSaved(); });
    for (const id of SAVED_BOXES) {
      const node = el(id);
      if (!node) continue;
      const edited = () => { node.dataset.edited = '1'; hints(); };
      node.addEventListener('input', edited); node.addEventListener('change', edited);
    }
  }
  window.cvStudioSetupFile = {parse, describe, missing, apply, build, fillFromSaved, importFile, init};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
