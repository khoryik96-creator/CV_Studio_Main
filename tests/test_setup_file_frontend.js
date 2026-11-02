// Team setup file: strict parsing, fill-and-save through the existing Settings
// actions, safe file creation. Fictional values only; no network or storage.
const assert = require('assert/strict'), fs = require('fs'), path = require('path'), vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'vendor', 'cvstudio', 'setup-file.js'), 'utf8');
// Values made inside the sandbox are compared as plain data.
const P = value => JSON.parse(JSON.stringify(value));
const GUID = '11111111-2222-3333-4444-555555555555', GUID2 = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

function fixture(globals = {}) {
  const nodes = new Map(), calls = [], downloads = [];
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {id, value:'', textContent:'', disabled:false, dataset:{}, files:null, handlers:{},
      addEventListener(type, fn) { this.handlers[type] = fn; }, click() { this.handlers.click?.(); }, remove() {}});
    return nodes.get(id);
  };
  const store = {onenote_ms_client_id:GUID2, onenote_ms_tenant:'contoso.onmicrosoft.com'};
  const window = {confirm:() => true, ...globals};
  const document = {readyState:'complete', getElementById:node, addEventListener() {}, body:{appendChild() {}},
    createElement:() => ({click() { downloads.push(this.download); }, remove() {}})};
  const context = vm.createContext({window, document, localStorage:{getItem:key => store[key] ?? null},
    Blob:class { constructor(parts) { this.text = parts.join(''); downloads.blob = this.text; } },
    URL:{createObjectURL:() => 'blob:fixture', revokeObjectURL() {}}, setTimeout, JSON, Object, Array, String, Error, Date});
  // Settings save actions are globals in the app; the module looks them up on window.
  vm.runInContext(source, context);
  return {window, node, calls, downloads, setup:window.cvStudioSetupFile};
}
const file = (extra = {}) => JSON.stringify({product:'CV Studio setup', schema:1,
  jobadder:{client_id:'example-ja-client', client_secret:'example-ja-secret'},
  outlook:{client_id:GUID, tenant:'common'}, onenote:{client_id:GUID2},
  ai:{main:{provider:'deepseek', key:'sk-example-main'}, search:{provider:'tavily', key:'tvly-example'}, lead:{provider:'openai'}}, ...extra});

(async () => {
  // Parsing: everything is checked before anything changes.
  const {setup} = fixture();
  const plan = setup.parse(file());
  assert.deepEqual(Object.keys(plan).sort(), ['jobadder', 'main', 'onenote', 'outlook', 'search']);
  assert.equal(plan.onenote.tenant, 'common', 'tenant defaults to common');
  assert.equal(plan.lead, undefined, 'a provider without its key changes nothing');
  assert.deepEqual(P(setup.describe(plan)), ['JobAdder Client ID and Client Secret', 'Outlook app (Client ID, tenant common)', 'OneNote app (Client ID, tenant common)', 'Main AI key (DeepSeek)', 'Search provider key (Tavily)']);
  for (const [bad, reason] of [
    ['not json', /not a CV Studio setup file/], [JSON.stringify({product:'Other', schema:1}), /not a CV Studio setup file/],
    [file({schema:2}), /different CV Studio version/], [file({outlook:{client_id:'not-a-guid'}}), /valid Microsoft app ID/],
    [file({onenote:{client_id:GUID, tenant:'bad tenant!'}}), /tenant/], [file({jobadder:{client_secret:'orphan'}}), /without its Client ID/],
    [file({ai:{main:{provider:'unknown', key:'x'}}}), /unknown provider/], [file({jobadder:{client_id:'a\u0007b'}}), /hidden characters/],
    [file({jobadder:{client_id:42}}), /not text/], [file({ai:[]}), /not valid/], ['x'.repeat(70000), /under 64 KB/],
    [JSON.stringify({product:'CV Studio setup', schema:1, ai:{main:{provider:'openai'}}}), /nothing to fill in/]]) {
    assert.throws(() => setup.parse(bad), reason);
  }

  // Apply: fills each field, then runs that section's own Save.
  const seen = {};
  const f = fixture({
    hasJASavedSecretFor:() => false,
    saveJobAdderSettings:async () => { seen.ja = [f.node('settingsJobAdderClientId').value, f.node('settingsJobAdderClientSecret').value]; return true; },
    ppcSaveOutlookSettingsFromPanel:async () => { seen.outlook = [f.node('settingsOutlookClientId').value, f.node('settingsOutlookTenant').value]; return true; },
    oneNoteApiSaveSettings:silent => { seen.onenote = [f.node('settingsOneNoteClientId').value, f.node('settingsOneNoteTenant').value, silent]; },
    onMainProviderChange:() => { seen.mainChange = f.node('mainProviderSel').value; },
    saveKey:async () => { seen.main = f.node('keyInput').value; f.node('keyInput').value = ''; },
    saveSearchProvider:async () => { seen.search = [f.node('searchProviderSel').value, f.node('searchProviderKeyInput').value]; },
  });
  const result = await f.setup.apply(f.setup.parse(file()));
  assert.deepEqual(seen.ja, ['example-ja-client', 'example-ja-secret']);
  assert.deepEqual(seen.outlook, [GUID, 'common']);
  assert.deepEqual(seen.onenote, [GUID2, 'common', true]);
  assert.equal(seen.mainChange, 'deepseek'); assert.equal(seen.main, 'sk-example-main');
  assert.deepEqual(seen.search, ['tavily', 'tvly-example']);
  assert.equal(f.node('searchProviderKeyInput').value, '', 'no key is left in a Settings box');
  assert.deepEqual(P(result), {done:['JobAdder', 'Outlook', 'OneNote', 'Main AI key', 'Search provider'], todo:[]});

  // Partial outcomes are reported per part.
  let jaSaves = 0;
  const partial = fixture({hasJASavedSecretFor:() => false, saveJobAdderSettings:async () => { jaSaves++; return true; },
    ppcSaveOutlookSettingsFromPanel:async () => false, saveKey:async () => {}});
  const mixed = await partial.setup.apply(partial.setup.parse(JSON.stringify({product:'CV Studio setup', schema:1,
    jobadder:{client_id:'example-ja-client'}, outlook:{client_id:GUID}, ai:{main:{provider:'openai', key:'sk-example'}}})));
  assert.equal(jaSaves, 0, 'a Client ID without a known secret is only filled in');
  assert.equal(partial.node('settingsJobAdderClientId').value, 'example-ja-client');
  assert.deepEqual(P(mixed.done), []);
  assert.match(mixed.todo.join(' '), /Enter the Client Secret/); assert.match(mixed.todo.join(' '), /Outlook: settings were not saved/); assert.match(mixed.todo.join(' '), /Main AI key: not saved/);
  const known = fixture({hasJASavedSecretFor:id => id === 'example-ja-client', saveJobAdderSettings:async () => true});
  assert.deepEqual(P((await known.setup.apply({jobadder:{client_id:'example-ja-client', client_secret:''}})).done), ['JobAdder'], 'the saved secret for the same Client ID is reused');

  // Import: cancel and bad files change nothing.
  let applied = 0;
  const imp = fixture({saveJobAdderSettings:async () => { applied++; return true; }, hasJASavedSecretFor:() => true});
  imp.window.confirm = () => false;
  await imp.setup.importFile({size:100, text:async () => file()});
  assert.equal(applied, 0); assert.match(imp.node('settingsSetupFileStatus').textContent, /cancelled/);
  imp.window.confirm = () => true;
  await imp.setup.importFile({size:100, text:async () => '{"product":"nope"}'});
  assert.equal(applied, 0); assert.match(imp.node('settingsSetupFileStatus').textContent, /Nothing was changed/);
  await imp.setup.importFile({size:100, text:async () => JSON.stringify({product:'CV Studio setup', schema:1, jobadder:{client_id:'example-ja-client'}})});
  assert.equal(applied, 1); assert.match(imp.node('settingsSetupFileStatus').textContent, /Filled in: JobAdder/);
  assert.equal(imp.node('settingsSetupFileImport').disabled, false, 'controls unlock after import');

  // Create: saved IDs always; secrets only when typed into the card, after a warning.
  const owner = fixture({getJAClientId:() => 'example-ja-client', ppcOutlookClientLoad:() => ({client_id:GUID, tenant:'common'}),
    getProvider:() => 'deepseek', getSavedLeadProvider:() => 'anthropic', getSearchProviderConfig:() => ({provider:'serpapi'}),
    getEnrichmentProviderConfig:() => ({provider:'none'})});
  let warned = 0; owner.window.confirm = () => { warned++; return true; };
  owner.node('settingsSetupFileCreate').click();
  const plain = JSON.parse(owner.downloads.blob);
  assert.equal(warned, 0, 'no warning without secrets');
  assert.deepEqual(plain.jobadder, {client_id:'example-ja-client'}); assert.equal(plain.ai, undefined);
  assert.deepEqual(plain.onenote, {client_id:GUID2, tenant:'contoso.onmicrosoft.com'});
  assert.equal(owner.downloads[0], 'CV-Studio-setup.json');
  owner.node('settingsSetupJobAdderSecret').value = 'example-ja-secret'; owner.node('settingsSetupMainKey').value = 'sk-example-main';
  owner.node('settingsSetupFileCreate').click();
  const secret = JSON.parse(owner.downloads.blob);
  assert.equal(warned, 1); assert.equal(secret.jobadder.client_secret, 'example-ja-secret'); assert.deepEqual(secret.ai, {main:{provider:'deepseek', key:'sk-example-main'}});
  assert.equal(owner.node('settingsSetupMainKey').value, '', 'typed secrets are cleared after the file is made');
  assert.deepEqual(Object.keys(owner.setup.parse(JSON.stringify(secret))).sort(), ['jobadder', 'main', 'onenote', 'outlook'], 'a created file imports cleanly');
  owner.node('settingsSetupEnrichmentKey').value = 'example-apollo';
  owner.node('settingsSetupFileCreate').click();
  assert.match(owner.node('settingsSetupFileStatus').textContent, /choose and save its provider/);
  owner.node('settingsSetupEnrichmentKey').value = ''; owner.window.confirm = () => false; owner.node('settingsSetupLeadKey').value = 'sk-lead';
  const before = owner.downloads.length; owner.node('settingsSetupFileCreate').click();
  assert.equal(owner.downloads.length, before, 'declining the secret warning creates no file');
  console.log('Team setup file: strict parsing, per-section fill and save, partial results, cancel/invalid safety, ID-only files and opt-in secrets passed.');
})().catch(error => { console.error(error); process.exit(1); });
