// Team setup file: strict parsing, fill-and-save through the existing Settings
// actions, safe file creation from a form with every column. Fictional values
// only; no network or storage.
const assert = require('assert/strict'), fs = require('fs'), path = require('path'), vm = require('vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'vendor', 'cvstudio', 'setup-file.js'), 'utf8');
// Values made inside the sandbox are compared as plain data.
const P = value => JSON.parse(JSON.stringify(value));
const GUID = '11111111-2222-3333-4444-555555555555', GUID2 = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

function fixture(globals = {}) {
  const nodes = new Map(), downloads = [], confirms = [];
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {id, value:'', placeholder:'', textContent:'', disabled:false, open:false, dataset:{}, files:null, handlers:{},
      addEventListener(type, fn) { this.handlers[type] = fn; }, click() { this.handlers.click?.(); }, remove() {}});
    return nodes.get(id);
  };
  const store = {onenote_ms_client_id:GUID2, onenote_ms_tenant:'contoso.onmicrosoft.com'};
  const window = {confirm:text => { confirms.push(text); return true; }, ...globals};
  const document = {readyState:'complete', getElementById:node, addEventListener() {}, body:{appendChild() {}},
    createElement:() => ({click() { downloads.push(this.download); }, remove() {}})};
  const context = vm.createContext({window, document, localStorage:{getItem:key => store[key] ?? null},
    Blob:class { constructor(parts) { this.text = parts.join(''); downloads.blob = this.text; } },
    URL:{createObjectURL:() => 'blob:fixture', revokeObjectURL() {}}, setTimeout, JSON, Object, Array, String, Error, Date});
  // Settings save actions are globals in the app; the module looks them up on window.
  vm.runInContext(source, context);
  const open = () => { node('settingsSetupCreate').open = true; node('settingsSetupCreate').handlers.toggle(); };
  const type = (id, value) => { node(id).value = value; node(id).handlers.input?.(); };
  return {window, node, downloads, confirms, open, type, setup:window.cvStudioSetupFile};
}
const file = (extra = {}) => JSON.stringify({product:'CV Studio setup', schema:1,
  jobadder:{client_id:'example-ja-client', client_secret:'example-ja-secret'},
  outlook:{client_id:GUID, tenant:'common'}, onenote:{client_id:GUID2},
  ai:{main:{provider:'deepseek', key:'sk-example-main'}, search:{provider:'tavily', key:'tvly-example'}, lead:{provider:'openai'}}, ...extra});
const file2 = ai => JSON.stringify({product:'CV Studio setup', schema:2, ai});

(async () => {
  // Parsing: everything is checked before anything changes; schema 1 files still import.
  const {setup} = fixture();
  const plan = setup.parse(file());
  assert.deepEqual(Object.keys(plan).sort(), ['jobadder', 'main', 'onenote', 'outlook', 'search']);
  assert.equal(plan.onenote.tenant, 'common', 'tenant defaults to common');
  assert.equal(plan.lead, undefined, 'a provider without its key changes nothing');
  assert.deepEqual(P(plan.main), {provider:'deepseek', keys:{deepseek:'sk-example-main'}}, 'a schema 1 main key becomes that provider\'s key');
  assert.deepEqual(P(setup.describe(plan)), ['JobAdder Client ID and Client Secret', 'Outlook app (Client ID, tenant common)', 'OneNote app (Client ID, tenant common)', 'Main AI key (DeepSeek)', 'Search provider key (Tavily)']);
  assert.deepEqual(P(setup.missing(plan)), ['Lead Finder key (optional)', 'Enrichment key (optional)']);
  const many = setup.parse(file2({main_provider:'deepseek', keys:{anthropic:'sk-ant-example', deepseek:'sk-example-main'}}));
  assert.deepEqual(P(many.main), {provider:'deepseek', keys:{anthropic:'sk-ant-example', deepseek:'sk-example-main'}});
  assert.deepEqual(P(setup.describe(many)), ['Main AI key (DeepSeek)', 'Other AI keys (Claude)']);
  assert.deepEqual(P(setup.missing(many)).slice(0, 3), ['JobAdder Client ID and Client Secret', 'Outlook app ID and tenant', 'OneNote app ID and tenant']);
  assert.equal(setup.parse(file2({keys:{openai:'sk-example'}})).main.provider, 'openai', 'one key is the main one');
  for (const [bad, reason] of [
    ['not json', /not a CV Studio setup file/], [JSON.stringify({product:'Other', schema:1}), /not a CV Studio setup file/],
    [file({schema:3}), /different CV Studio version/], [file({outlook:{client_id:'not-a-guid'}}), /valid Microsoft app ID/],
    [file({onenote:{client_id:GUID, tenant:'bad tenant!'}}), /tenant/], [file({jobadder:{client_secret:'orphan'}}), /without its Client ID/],
    [file({ai:{main:{provider:'unknown', key:'x'}}}), /unknown provider/], [file({jobadder:{client_id:'a\u0007b'}}), /hidden characters/],
    [file({jobadder:{client_id:42}}), /not text/], [file({ai:[]}), /not valid/], ['x'.repeat(70000), /under 64 KB/],
    [file2({keys:{mystery:'x'}}), /unknown provider/], [file2({keys:[]}), /not valid/],
    [file2({keys:{anthropic:'a', deepseek:'b'}}), /Main AI provider has no key/], [file2({main_provider:'openai', keys:{deepseek:'b'}}), /Main AI provider has no key/],
    [file2({main_provider:'mystery', keys:{deepseek:'b'}}), /unknown provider/],
    [file2({main:{provider:'deepseek', key:'one'}, keys:{deepseek:'two'}}), /two different DeepSeek keys/],
    [JSON.stringify({product:'CV Studio setup', schema:1, ai:{main:{provider:'openai'}}}), /nothing to fill in/]]) {
    assert.throws(() => setup.parse(bad), reason);
  }

  // Apply: fills each field, then runs that section's own Save; the main AI key is saved last.
  const seen = {mainSaves:[]};
  const f = fixture({
    hasJASavedSecretFor:() => false,
    saveJobAdderSettings:async () => { seen.ja = [f.node('settingsJobAdderClientId').value, f.node('settingsJobAdderClientSecret').value]; return true; },
    ppcSaveOutlookSettingsFromPanel:async () => { seen.outlook = [f.node('settingsOutlookClientId').value, f.node('settingsOutlookTenant').value]; return true; },
    oneNoteApiSaveSettings:silent => { seen.onenote = [f.node('settingsOneNoteClientId').value, f.node('settingsOneNoteTenant').value, silent]; },
    onMainProviderChange:() => { seen.mainChange = f.node('mainProviderSel').value; },
    saveKey:async () => { seen.mainSaves.push([f.node('mainProviderSel').value, f.node('keyInput').value]); f.node('keyInput').value = ''; },
    saveSearchProvider:async () => { seen.search = [f.node('searchProviderSel').value, f.node('searchProviderKeyInput').value]; return true; },
  });
  const result = await f.setup.apply(f.setup.parse(file()));
  assert.deepEqual(seen.ja, ['example-ja-client', 'example-ja-secret']);
  assert.deepEqual(seen.outlook, [GUID, 'common']);
  assert.deepEqual(seen.onenote, [GUID2, 'common', true]);
  assert.equal(seen.mainChange, 'deepseek'); assert.deepEqual(seen.mainSaves, [['deepseek', 'sk-example-main']]);
  assert.deepEqual(seen.search, ['tavily', 'tvly-example']);
  assert.equal(f.node('searchProviderKeyInput').value, '', 'no key is left in a Settings box');
  assert.deepEqual(P(result), {done:['JobAdder', 'Outlook', 'OneNote', 'Main AI key (DeepSeek)', 'Search provider'], todo:[]});
  seen.mainSaves = [];
  const both = await f.setup.apply(many);
  assert.deepEqual(seen.mainSaves, [['anthropic', 'sk-ant-example'], ['deepseek', 'sk-example-main']], 'each provider key is saved; the main one last stays selected');
  assert.deepEqual(P(both.done), ['Claude key', 'Main AI key (DeepSeek)']);

  // Partial outcomes are reported per part.
  let jaSaves = 0;
  const partial = fixture({hasJASavedSecretFor:() => false, saveJobAdderSettings:async () => { jaSaves++; return true; },
    ppcSaveOutlookSettingsFromPanel:async () => false, saveKey:async () => {}, saveSearchProvider:async () => false});
  const mixed = await partial.setup.apply(partial.setup.parse(JSON.stringify({product:'CV Studio setup', schema:1,
    jobadder:{client_id:'example-ja-client'}, outlook:{client_id:GUID}, ai:{main:{provider:'openai', key:'sk-example'}, search:{provider:'serpapi', key:'serp-example'}}})));
  assert.equal(partial.node('searchProviderKeyInput').value, 'serp-example', 'an unsaved key stays in its box to retry');
  assert.match(mixed.todo.join(' '), /Search provider key: not saved/);
  assert.equal(jaSaves, 0, 'a Client ID without a known secret is only filled in');
  assert.equal(partial.node('settingsJobAdderClientId').value, 'example-ja-client');
  assert.deepEqual(P(mixed.done), []);
  assert.match(mixed.todo.join(' '), /Enter the Client Secret/); assert.match(mixed.todo.join(' '), /Outlook: settings were not saved/); assert.match(mixed.todo.join(' '), /Main AI key \(OpenAI\): not saved/);
  const known = fixture({hasJASavedSecretFor:id => id === 'example-ja-client', saveJobAdderSettings:async () => true});
  assert.deepEqual(P((await known.setup.apply({jobadder:{client_id:'example-ja-client', client_secret:''}})).done), ['JobAdder'], 'the saved secret for the same Client ID is reused');

  // Import: cancel and bad files change nothing; the confirmation lists what the file leaves out.
  let applied = 0;
  const imp = fixture({saveJobAdderSettings:async () => { applied++; return true; }, hasJASavedSecretFor:() => true});
  imp.window.confirm = () => false;
  await imp.setup.importFile({size:100, text:async () => file()});
  assert.equal(applied, 0); assert.match(imp.node('settingsSetupFileStatus').textContent, /cancelled/);
  let asked = '';
  imp.window.confirm = text => { asked = text; return true; };
  await imp.setup.importFile({size:100, text:async () => '{"product":"nope"}'});
  assert.equal(applied, 0); assert.match(imp.node('settingsSetupFileStatus').textContent, /Nothing was changed/);
  await imp.setup.importFile({size:100, text:async () => JSON.stringify({product:'CV Studio setup', schema:2, jobadder:{client_id:'example-ja-client'}})});
  assert.equal(applied, 1); assert.match(imp.node('settingsSetupFileStatus').textContent, /Filled in: JobAdder\./);
  assert.match(asked, /Not in this file[^]*• JobAdder Client Secret\n• Outlook app ID and tenant\n• OneNote app ID and tenant\n• Main AI key/);
  assert.match(imp.node('settingsSetupFileStatus').textContent, /Not in the file: JobAdder Client Secret, Outlook app ID and tenant, OneNote app ID and tenant, Main AI key/);
  assert.equal(imp.node('settingsSetupFileImport').disabled, false, 'controls unlock after import');

  // Create: opening the form fills every saved ID, tenant and provider; secrets only when typed.
  const owner = fixture({getJAClientId:() => 'example-ja-client', hasJASavedSecretFor:id => id === 'example-ja-client',
    ppcOutlookClientLoad:() => ({client_id:GUID, tenant:'common'}),
    getProvider:() => 'deepseek', getSavedLeadProvider:() => 'anthropic', getSearchProviderConfig:() => ({provider:'serpapi'}),
    getEnrichmentProviderConfig:() => ({provider:'none'}), _secureAiConfigured:{main_deepseek:true, search_serpapi:true}});
  let warned = 0; owner.window.confirm = () => { warned++; return true; };
  owner.open();
  const shown = id => owner.node(id).value;
  assert.deepEqual(['settingsSetupJobAdderId', 'settingsSetupOutlookId', 'settingsSetupOutlookTenant', 'settingsSetupOneNoteId', 'settingsSetupOneNoteTenant',
    'settingsSetupMainProvider', 'settingsSetupLeadProvider', 'settingsSetupSearchProvider'].map(shown),
    ['example-ja-client', GUID, 'common', GUID2, 'contoso.onmicrosoft.com', 'deepseek', 'anthropic', 'serpapi']);
  assert.equal(shown('settingsSetupEnrichmentProvider'), '', 'an unsaved provider is not invented');
  const hint = id => owner.node(id).placeholder;
  assert.match(hint('settingsSetupJobAdderSecret'), /Saved on this computer/); assert.match(hint('settingsSetupKeyDeepseek'), /Saved on this computer/);
  assert.match(hint('settingsSetupSearchKey'), /Saved on this computer/); assert.match(hint('settingsSetupKeyAnthropic'), /Leave blank/);
  owner.node('settingsSetupFileCreate').click();
  const plain = JSON.parse(owner.downloads.blob);
  assert.equal(warned, 0, 'no warning without secrets');
  assert.equal(plain.schema, 2);
  assert.deepEqual(plain.jobadder, {client_id:'example-ja-client'}); assert.equal(plain.ai, undefined);
  assert.deepEqual(plain.outlook, {client_id:GUID, tenant:'common'});
  assert.deepEqual(plain.onenote, {client_id:GUID2, tenant:'contoso.onmicrosoft.com'});
  assert.equal(owner.downloads[0], 'CV-Studio-setup.json');
  assert.match(owner.node('settingsSetupFileStatus').textContent, /Not in the file: JobAdder Client Secret, Main AI key/);
  // Edited boxes survive reopening; a typed tenant and ID go into the file as shown.
  owner.type('settingsSetupOutlookTenant', 'contoso.onmicrosoft.com'); owner.open();
  assert.equal(shown('settingsSetupOutlookTenant'), 'contoso.onmicrosoft.com', 'reopening keeps what the owner typed');
  owner.type('settingsSetupJobAdderSecret', 'example-ja-secret');
  owner.type('settingsSetupKeyDeepseek', 'sk-example-main'); owner.type('settingsSetupKeyAnthropic', 'sk-ant-example');
  owner.type('settingsSetupSearchKey', 'serp-example');
  owner.node('settingsSetupEnrichmentProvider').value = 'apollo'; owner.type('settingsSetupEnrichmentKey', 'example-apollo');
  owner.node('settingsSetupFileCreate').click();
  const secret = JSON.parse(owner.downloads.blob);
  assert.equal(warned, 1); assert.equal(secret.jobadder.client_secret, 'example-ja-secret');
  assert.equal(secret.outlook.tenant, 'contoso.onmicrosoft.com');
  assert.deepEqual(secret.ai, {main_provider:'deepseek', keys:{anthropic:'sk-ant-example', deepseek:'sk-example-main'},
    search:{provider:'serpapi', key:'serp-example'}, enrichment:{provider:'apollo', key:'example-apollo'}});
  for (const id of ['settingsSetupJobAdderSecret', 'settingsSetupKeyDeepseek', 'settingsSetupKeyAnthropic', 'settingsSetupSearchKey', 'settingsSetupEnrichmentKey'])
    assert.equal(owner.node(id).value, '', 'typed secrets are cleared after the file is made: ' + id);
  assert.deepEqual(Object.keys(owner.setup.parse(JSON.stringify(secret))).sort(), ['enrichment', 'jobadder', 'main', 'onenote', 'outlook', 'search'], 'a created file imports cleanly');
  // The main AI provider needs its own key in the file.
  owner.type('settingsSetupKeyAnthropic', 'sk-ant-example');
  const before = owner.downloads.length; owner.node('settingsSetupFileCreate').click();
  assert.match(owner.node('settingsSetupFileStatus').textContent, /Main AI is DeepSeek: type its key too/);
  assert.equal(owner.downloads.length, before, 'no file without the main key');
  owner.type('settingsSetupKeyAnthropic', ''); owner.type('settingsSetupJobAdderId', ''); owner.type('settingsSetupJobAdderSecret', 'orphan');
  owner.node('settingsSetupFileCreate').click();
  assert.match(owner.node('settingsSetupFileStatus').textContent, /Type the JobAdder Client ID for this Client Secret/);
  owner.type('settingsSetupJobAdderSecret', ''); owner.type('settingsSetupOutlookId', 'not-a-guid');
  owner.node('settingsSetupFileCreate').click();
  assert.match(owner.node('settingsSetupFileStatus').textContent, /Outlook Client ID in the setup file is not a valid Microsoft app ID/);
  owner.type('settingsSetupOutlookId', GUID); owner.window.confirm = () => false; owner.type('settingsSetupLeadKey', 'sk-lead');
  const declined = owner.downloads.length; owner.node('settingsSetupFileCreate').click();
  assert.equal(owner.downloads.length, declined, 'declining the secret warning creates no file');
  const empty = fixture(); empty.node('settingsSetupFileCreate').click();
  assert.match(empty.node('settingsSetupFileStatus').textContent, /Fill in at least one ID or key first/);
  console.log('Team setup file: every ID/tenant/secret column, per-provider AI keys, schema 1 import, strict parsing, per-section saves, missing-item lists, cancel/invalid safety and opt-in secrets passed.');
})().catch(error => { console.error(error); process.exit(1); });
