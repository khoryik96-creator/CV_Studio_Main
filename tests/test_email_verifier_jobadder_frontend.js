// JobAdder client-contact email scan (vendor/cvstudio/email-verifier-jobadder.js).
// No network: JobAdder pages and verifier answers are synthetic. All names and
// domains are made up.
const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../vendor/cvstudio/email-verifier-jobadder.js'), 'utf8');

class Element {
  constructor(tag = 'div') {
    Object.assign(this, {tag, value: '', textContent: '', children: [], handlers: {}, disabled: false, hidden: false, checked: false, className: ''});
  }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  appendChild(node) { this.children.push(node); return node; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  click() { return this.handlers.click?.(); }
}
const tick = () => new Promise(resolve => setImmediate(resolve));
// Values made inside the vm context come from another realm; compare as plain data.
const plain = value => JSON.parse(JSON.stringify(value));
async function settle(times = 20) { for (let i = 0; i < times; i++) await tick(); }

function contact(id, email, extra = {}) {
  return {contact_id: id, name: 'Person ' + id, company: extra.company || 'Contoso', email, inactive: !!extra.inactive};
}

function fixture(options = {}) {
  const ids = new Map(), calls = [], exports = [], state = {inflight: 0, maxInflight: 0, domains: new Set(), sameDomainOverlap: false};
  const document = {
    readyState: 'complete',
    getElementById: id => { if (!ids.has(id)) ids.set(id, new Element()); return ids.get(id); },
    createElement: tag => new Element(tag),
    addEventListener() {},
  };
  const el = name => document.getElementById('emailVerifierJa' + name);
  el('Mode').value = options.mode || 'full';
  el('Filter').value = 'invalid';
  const pages = options.pages || [{contacts: [contact(1, 'a@contoso.example')], next_offset: null, total: 1}];
  const verdict = options.verdict || (email => ({status: email.startsWith('bad') ? 'invalid' : 'accepted', reason: 'Synthetic check', attempts: 1}));
  const window = {_jaAccountCacheNamespace: options.namespace ?? 'ja' + 'a'.repeat(64), _jaWebBase: options.webBase, addEventListener() {}};
  // The real URL class (the module normalises domains with it) plus blob stubs.
  class FakeURL extends URL {}
  FakeURL.createObjectURL = blob => { exports.push(blob); return 'blob:synthetic'; };
  FakeURL.revokeObjectURL = () => {};
  const context = {
    document, window, Date, Intl,
    module: {exports: {}}, Blob,
    URL: FakeURL,
    setTimeout: fn => setImmediate(fn),
    ...(options.localStorage ? {localStorage: options.localStorage} : {}),
    markTabRunning: () => 1, markTabDone: () => { state.done = (state.done || 0) + 1; }, markTabFailed: () => { state.failed = (state.failed || 0) + 1; },
    fetch: async (url, init = {}) => {
      calls.push({url, init});
      if (url.startsWith('/jobadder/client_contacts')) {
        assert.equal(init.method, 'GET');
        if (options.contactsFetch) return options.contactsFetch(url, init);
        const offset = Number(new URL('http://x' + url).searchParams.get('offset'));
        const page = pages.find(item => (item.offset ?? 0) === offset) || pages[0];
        return {ok: true, status: 200, json: async () => page};
      }
      assert.equal(url, '/email-verifier');
      assert.equal(init.method, 'POST');
      const body = JSON.parse(init.body);
      const domain = body.email.slice(body.email.lastIndexOf('@') + 1);
      if (state.domains.has(domain)) state.sameDomainOverlap = true;
      state.domains.add(domain);
      state.inflight += 1; state.maxInflight = Math.max(state.maxInflight, state.inflight);
      try {
        if (options.verifierFetch) return await options.verifierFetch(body, state);
        await tick(); await tick();
        const result = verdict(body.email, body.mode);
        return {ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, checked_at: '2026-10-28T00:00:00Z', ...result}})};
      } finally {
        state.inflight -= 1; state.domains.delete(domain);
      }
    },
  };
  vm.runInNewContext(source, context);
  return {el, calls, exports, state, window, api: context.module.exports, verifierCalls: () => calls.filter(call => call.url === '/email-verifier')};
}

async function main() {
  // ---- Pure helpers --------------------------------------------------------
  const {api} = fixture();
  assert.equal(api.emailKey(' Alex@Contoso.EXAMPLE '), 'Alex@contoso.example');
  assert.equal(api.domainOf('Alex@Contoso.EXAMPLE'), 'contoso.example');
  assert.equal(api.domainOf('no-at-sign'), '');
  assert.equal(api.domainOf('x@B\u00fccher.EXAMPLE'), 'xn--bcher-kva.example', 'the same ASCII domain key as the verifier engine');
  assert.equal(api.domainOf('y@xn--bcher-kva.example'), 'xn--bcher-kva.example');
  assert.equal(api.domainOf('z@odd/host'), 'odd/host');
  assert.equal(api.contactLink(41), 'https://app.jobadder.com/contacts/41');
  for (const bad of ['41', -1, 0, 1.5, NaN, null]) assert.equal(api.contactLink(bad), '');
  // The tenant's own JobAdder address is used when known, never an arbitrary one.
  assert.equal(fixture({webBase: 'https://au.jobadder.com'}).api.contactLink(5), 'https://au.jobadder.com/contacts/5');
  assert.equal(fixture({webBase: 'https://app.jobadder.com', localStorage: {getItem: () => 'https://sg.jobadder.com/'}}).api.contactLink(5), 'https://sg.jobadder.com/contacts/5');
  for (const unsafe of ['https://evil.example', 'javascript:alert(1)', 'http://au.jobadder.com', 'https://jobadder.com.evil.example']) {
    assert.equal(fixture({webBase: unsafe, localStorage: {getItem: () => unsafe}}).api.contactLink(5), 'https://app.jobadder.com/contacts/5', unsafe);
  }
  assert.equal(fixture({localStorage: {getItem: () => { throw Error('blocked'); }}}).api.contactLink(5), 'https://app.jobadder.com/contacts/5');

  const page = api.normalizePage({contacts: [contact(5, ' x@y.example '), {contact_id: '6'}, {contact_id: 0}, null, {contact_id: 7, name: 9, email: ['x'], inactive: 'yes'}], next_offset: 100, total: 300}, 0);
  assert.deepEqual(plain(page.contacts.map(item => item.id)), [5, 7]);
  assert.equal(page.contacts[0].email, 'x@y.example');
  assert.equal(page.contacts[1].name, '');
  assert.equal(page.contacts[1].email, '');
  assert.equal(page.contacts[1].inactive, false);
  assert.equal(page.nextOffset, 100);
  assert.equal(page.total, 300);
  assert.equal(api.normalizePage({contacts: [], next_offset: 100}, 100).nextOffset, null, 'a page that does not move forward ends loading');
  assert.equal(api.normalizePage({contacts: [], next_offset: 50}, 100).nextOffset, null);
  for (const bad of [null, [], {contacts: 'x'}, 'text']) assert.throws(() => api.normalizePage(bad, 0));

  const scan = api.newScan('full', 'ns');
  api.addContacts(scan, [
    {id: 1, name: 'A', company: 'Contoso', email: 'Same@Contoso.example', inactive: false},
    {id: 2, name: 'B', company: 'Contoso', email: 'Same@contoso.EXAMPLE', inactive: false},
    {id: 1, name: 'A again', company: 'Contoso', email: 'other@contoso.example', inactive: false},
    {id: 3, name: 'C', company: 'Northwind', email: '', inactive: true},
    {id: 4, name: 'D', company: 'Northwind', email: 'd@northwind.example', inactive: false},
  ]);
  assert.equal(scan.contacts.length, 4, 'a contact id appears once');
  assert.equal(scan.order.length, 2, 'the same email (domain case aside) is checked once');
  assert.equal(scan.entries.get('Same@contoso.example').contacts, 2);
  let pick = api.takeNext(scan);
  assert.equal(pick.entry.email, 'Same@Contoso.example');
  scan.inflight.add('contoso.example'); pick.entry.state = 'running';
  assert.equal(api.takeNext(scan).entry.email, 'd@northwind.example', 'a domain already being checked is skipped');
  scan.inflight.add('northwind.example');
  assert.equal(api.takeNext(scan), null);
  scan.inflight.clear();
  api.recordResult(scan, pick.entry, {status: 'catch_all', reason: 'x', attempts: 2});
  assert(scan.catchAll.has('contoso.example'));
  api.addContacts(scan, [{id: 9, name: 'E', company: 'Contoso', email: 'e@contoso.example', inactive: false}]);
  pick = api.takeNext(scan);
  assert.equal(pick.entry.email, 'd@northwind.example');
  pick.entry.state = 'done'; pick.entry.result = {status: 'accepted', reason: 'ok'};
  pick = api.takeNext(scan);
  assert.equal(pick.entry.email, 'e@contoso.example');
  assert.equal(pick.inferred, true, 'other addresses on a catch-all domain get a format-only check, not a mailbox probe');
  assert.equal(api.inferredResult({status: 'domain_ok', reason: 'x', attempts: 0}).status, 'catch_all');
  assert.equal(api.inferredResult({status: 'invalid', reason: 'Bad format'}).status, 'invalid', 'a malformed address on a catch-all domain stays Invalid');
  assert.equal(api.inferredResult({status: 'unknown', reason: 'DNS'}).status, 'unknown');
  const quick = api.newScan('quick', 'ns');
  api.addContacts(quick, [{id: 1, name: 'A', company: 'C', email: 'a@x.example'}, {id: 2, name: 'B', company: 'C', email: 'b@x.example'}]);
  api.recordResult(quick, quick.entries.get('a@x.example'), {status: 'catch_all', reason: 'x'});
  assert.equal(api.takeNext(quick).inferred, false, 'quick mode never infers');
  assert.equal(quick.catchAll.size, 0, 'quick mode never remembers a catch-all domain');
  const byDefault = api.newScan('full', 'ns');
  api.addContacts(byDefault, [{id: 1, name: 'A', company: 'C', email: 'a@x.example'}, {id: 2, name: 'B', company: 'C', email: 'b@y.example'}]);
  api.recordResult(byDefault, byDefault.entries.get('a@x.example'), {status: 'invalid', reason: 'Gone'});
  api.recordResult(byDefault, byDefault.entries.get('b@y.example'), {status: 'accepted', reason: 'Fine'});
  assert.deepEqual(plain(api.visibleRows(byDefault, {}).map(row => row.contact.id)), [1], 'invalid emails are the default view');

  const summary = api.summarize(scan);
  assert.equal(summary.contacts, 5);
  assert.equal(summary.counts.catch_all, 2);
  assert.equal(summary.counts.ok, 1);
  assert.equal(summary.counts.no_email, 1);
  assert.equal(summary.counts.not_checked, 1);
  assert.deepEqual(plain(api.visibleRows(scan, {filter: 'catch_all'}).map(row => row.contact.id)), [1, 2]);
  assert.deepEqual(plain(api.visibleRows(scan, {filter: 'no_email', hideInactive: true}).map(row => row.contact.id)), []);
  assert.deepEqual(plain(api.visibleRows(scan, {filter: '', search: 'NORTHWIND'}).map(row => row.contact.id)), [4, 3]);
  assert.deepEqual(plain(api.visibleRows(scan, {filter: ''}).map(row => row.status)), ['catch_all', 'catch_all', 'not_checked', 'accepted', 'no_email']);
  const sortedOnce = scan.sorted;
  api.visibleRows(scan, {filter: ''});
  assert.equal(scan.sorted, sortedOnce, 'contacts are sorted once, not on every redraw');
  api.addContacts(scan, [{id: 50, name: 'A', company: 'Aardvark', email: '', inactive: false}]);
  assert.equal(scan.sorted, null, 'a new contact re-sorts');
  assert.equal(api.visibleRows(scan, {filter: 'no_email'})[0].contact.company, 'Aardvark');

  const csv = api.makeCSV([{contact: {id: 3, name: '=HYPERLINK("x")', company: '+Contoso', email: '-a@b.example', inactive: true}, status: 'invalid', result: {reason: '@cmd "quoted"', checked_at: '2026-10-28T00:00:00Z'}}]);
  assert(csv.startsWith('"Contact ID","Contact","Company","Email","Result"'));
  assert(csv.includes('"\'=HYPERLINK(""x"")"') && csv.includes('"\'+Contoso"') && csv.includes('"\'-a@b.example"') && csv.includes('"\'@cmd ""quoted"""'));
  assert(csv.includes('"https://app.jobadder.com/contacts/3"') && csv.includes('"Yes"') && csv.includes('"Invalid"'));

  const capped = api.newScan('full', 'ns');
  api.addContacts(capped, Array.from({length: api.MAX_CONTACTS + 5}, (_, i) => ({id: i + 1, name: '', company: '', email: '', inactive: false})));
  assert.equal(capped.contacts.length, api.MAX_CONTACTS);
  assert.equal(capped.capped, true);

  // ---- Full scan: two pages, duplicates, no email, catch-all inference -------
  const pages = [
    {offset: 0, contacts: [contact(1, 'bad@contoso.example'), contact(2, 'ok@contoso.example'), contact(3, '', {company: 'Northwind'})], next_offset: 3, total: 7},
    {offset: 3, contacts: [contact(4, 'one@catchall.example', {company: 'Fabrikam'}), contact(5, 'two@catchall.example', {company: 'Fabrikam'}), contact(6, 'bad@contoso.example', {inactive: true}), contact(7, 'gone@northwind.example', {company: 'Northwind'}), contact(8, 'jo hn@catchall.example', {company: 'Fabrikam'})], next_offset: null, total: 8},
  ];
  const verdict = (email, mode) => mode === 'quick' ? (/\s/.test(email) ? {status: 'invalid', reason: 'This address has an invalid format.', attempts: 0} : {status: 'domain_ok', reason: 'Domain passed', attempts: 0})
    : email.endsWith('@catchall.example') ? {status: 'catch_all', reason: 'Accepts any address', attempts: 2}
    : email.startsWith('bad') || email.startsWith('gone') ? {status: 'invalid', reason: 'The mailbox does not exist.', attempts: 1}
    : {status: 'accepted', reason: 'Mailbox accepted', attempts: 2};
  const full = fixture({pages, verdict});
  await full.el('Start').click();
  await settle();
  const pageCalls = full.calls.filter(call => call.url.startsWith('/jobadder/client_contacts'));
  assert.deepEqual(plain(pageCalls.map(call => call.url)), ['/jobadder/client_contacts?offset=0&limit=100', '/jobadder/client_contacts?offset=3&limit=100']);
  const checked = full.verifierCalls().map(call => JSON.parse(call.init.body).email);
  assert.equal(checked.filter(email => email === 'bad@contoso.example').length, 1, 'a shared email is checked once');
  const catchAllCalls = full.verifierCalls().map(call => JSON.parse(call.init.body)).filter(body => body.email.endsWith('@catchall.example'));
  assert.deepEqual(plain(catchAllCalls.map(body => body.mode)), ['full', 'quick', 'quick'], 'only the first catch-all address gets a mailbox probe');
  assert.equal(checked.length, 6);
  assert(full.verifierCalls().every(call => Object.keys(JSON.parse(call.init.body)).join() === 'email,mode'));
  assert.equal(full.el('Invalid').textContent, 4, 'the malformed catch-all address is Invalid');
  assert.equal(full.el('CatchAll').textContent, 2);
  assert.equal(full.el('Accepted').textContent, 1);
  assert.equal(full.el('NoEmail').textContent, 1);
  assert(full.el('Message').textContent.startsWith('Finished. 6 unique emails checked for 8 contacts; 4 contacts have an invalid email.'), full.el('Message').textContent);
  assert.equal(full.state.done, 1);
  const rows = full.el('Results').children;
  assert.equal(rows.length, 4, 'the dashboard shows only invalid emails by default');
  const firstLink = rows[0].children[0].children[0];
  assert.equal(firstLink.tag, 'a');
  assert.match(firstLink.href, /^https:\/\/app\.jobadder\.com\/contacts\/[1-8]$/);
  assert.equal(firstLink.target, '_blank');
  assert.equal(firstLink.rel, 'noopener noreferrer');
  assert.deepEqual(plain(rows.map(row => row.children[1].textContent)), ['Contoso', 'Contoso', 'Fabrikam', 'Northwind']);
  assert(rows.some(row => row.children[0].children[1]?.textContent === 'No longer with the company'));
  full.el('HideInactive').checked = true; full.el('HideInactive').handlers.change();
  assert.equal(full.el('Results').children.length, 3);
  full.el('Filter').value = 'catch_all'; full.el('Filter').handlers.change();
  const inferredRow = full.el('Results').children.find(row => row.children[2].children[0].textContent === 'two@catchall.example');
  assert.equal(inferredRow.children[4].children[0].textContent, api.INFERRED_CATCH_ALL);
  full.el('Filter').value = 'invalid'; full.el('HideInactive').checked = false; full.el('Filter').handlers.change();
  full.el('Export').click();
  const exported = await full.exports[0].text();
  assert(exported.includes('"https://app.jobadder.com/contacts/7"') && exported.includes('gone@northwind.example'));
  assert(!exported.includes('ok@contoso.example'));
  assert.equal(full.el('Continue').disabled, true, 'a finished scan has nothing to continue');
  // Read-only: only the contact listing and the existing verifier are called.
  assert(full.calls.every(call => call.url.startsWith('/jobadder/client_contacts?') || call.url === '/email-verifier'));

  // ---- Never more than two checks, never two on one domain -------------------
  const many = Array.from({length: 12}, (_, i) => contact(i + 1, 'p' + i + '@d' + (i % 4) + '.example'));
  const busyRun = fixture({pages: [{contacts: many, next_offset: null, total: 12}]});
  await busyRun.el('Start').click();
  await settle();
  assert.equal(busyRun.verifierCalls().length, 12);
  assert(busyRun.state.maxInflight <= 2, 'at most two checks at once');
  assert.equal(busyRun.state.maxInflight, 2, 'two checks do run in parallel');
  assert.equal(busyRun.state.sameDomainOverlap, false, 'never two checks on one domain');

  // ---- A busy verifier (429) is waited for, not reported --------------------
  // Busy answers are waited out however many there are: they are not failures,
  // so they never use up the retries for a failed check.
  let busyLeft = 5;
  const busy = fixture({verifierFetch: async body => {
    if (busyLeft > 0) { busyLeft -= 1; return {ok: false, status: 429, json: async () => ({ok: false, error: 'The verifier is busy.'})}; }
    return {ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'invalid', reason: 'Gone', attempts: 1}})};
  }});
  await busy.el('Start').click();
  await settle(40);
  assert.equal(busy.verifierCalls().length, 6);
  assert.equal(busy.el('Invalid').textContent, 1);
  assert(busy.el('Message').textContent.startsWith('Finished.'));

  // ---- A temporary failure is retried, not a reason to stop -------------------
  let failOnce = true;
  const failing = fixture({
    pages: [{contacts: [contact(1, 'a@one.example'), contact(2, 'b@two.example'), contact(3, 'c@three.example')], next_offset: null, total: 3}],
    verifierFetch: async body => {
      if (body.email === 'a@one.example' && failOnce) { failOnce = false; throw Error('Request timed out.'); }
      await tick();
      return {ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'accepted', reason: 'Fine', attempts: 2}})};
    },
  });
  await failing.el('Start').click();
  await settle();
  assert(failing.el('Message').textContent.startsWith('Finished. 3 unique emails'), failing.el('Message').textContent);
  assert.equal(failing.verifierCalls().filter(call => JSON.parse(call.init.body).email === 'a@one.example').length, 2);
  assert.equal(failing.state.failed, undefined);

  // ---- One email that keeps failing is set aside; Continue retries it -----------
  let stuckFails = true;
  const stuck1 = fixture({
    pages: [{contacts: [contact(1, 'a@one.example'), contact(2, 'b@two.example'), contact(3, 'c@three.example')], next_offset: null, total: 3}],
    verifierFetch: async body => {
      if (body.email === 'a@one.example' && stuckFails) throw Error('Request timed out.');
      await tick();
      return {ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'accepted', reason: 'Fine', attempts: 2}})};
    },
  });
  await stuck1.el('Start').click();
  await settle();
  assert.equal(stuck1.verifierCalls().filter(call => JSON.parse(call.init.body).email === 'a@one.example').length, 3, 'tried once and retried twice');
  assert.equal(stuck1.el('Message').textContent, 'Finished. 2 unique emails checked for 3 contacts; 0 contacts have an invalid email. 1 email could not be checked; press Continue to try again.');
  assert.equal(stuck1.el('Continue').disabled, false);
  stuck1.el('Filter').value = 'not_checked'; stuck1.el('Filter').handlers.change();
  assert.equal(stuck1.el('Results').children[0].children[4].children[0].textContent, 'Could not be checked: Request timed out. Press Continue to try again.');
  stuckFails = false;
  await stuck1.el('Continue').click();
  await settle();
  assert(stuck1.el('Message').textContent.startsWith('Finished. 3 unique emails checked for 3 contacts'), stuck1.el('Message').textContent);
  assert.equal(stuck1.el('Continue').disabled, true);
  assert.equal(stuck1.calls.filter(call => call.url.startsWith('/jobadder')).length, 1, 'Continue does not reload contacts');

  // ---- Failures between successes are not an outage ------------------------------
  const mixed = fixture({
    pages: [{contacts: Array.from({length: 12}, (_, i) => contact(i + 1, (i % 2 ? 'ok' : 'stuck') + i + '@m' + i + '.example')), next_offset: null, total: 12}],
    verifierFetch: async body => {
      await tick();
      if (body.email.startsWith('stuck')) throw Error('Request timed out.');
      return {ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'accepted', reason: 'Fine', attempts: 2}})};
    },
  });
  await mixed.el('Start').click();
  await settle(80);
  assert.equal(mixed.el('Message').textContent, 'Finished. 6 unique emails checked for 12 contacts; 0 contacts have an invalid email. 6 emails could not be checked; press Continue to try again.');

  // ---- Many failures in a row mean the connection is down: stop ---------------
  const outage = fixture({
    pages: [{contacts: Array.from({length: 8}, (_, i) => contact(i + 1, 'x@o' + i + '.example')), next_offset: null, total: 8}],
    verifierFetch: async () => { await tick(); throw Error('Synthetic outage.'); },
  });
  await outage.el('Start').click();
  await settle(60);
  assert(outage.el('Message').textContent.startsWith('Stopped: 5 emails in a row could not be checked (Synthetic outage.)'), outage.el('Message').textContent);
  assert.equal(outage.state.failed, 1);
  assert.equal(outage.el('Continue').disabled, false);

  // ---- Not connected to JobAdder ---------------------------------------------
  const offline = fixture({contactsFetch: async () => ({ok: false, status: 401, json: async () => ({error: 'Connect JobAdder first, then scan again.'})})});
  await offline.el('Start').click();
  await settle();
  assert.equal(offline.el('Message').textContent, 'Connect JobAdder first, then scan again.');
  assert.equal(offline.verifierCalls().length, 0);

  // ---- The account becomes known after the scan started ---------------------------
  const lateReleases = [];
  const late = fixture({
    namespace: '',
    pages: [{contacts: [contact(1, 'bad@one.example'), contact(2, 'bad@two.example'), contact(3, 'bad@three.example')], next_offset: null, total: 3}],
    verifierFetch: body => new Promise(resolve => { lateReleases.push(() => resolve({ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'invalid', reason: 'Gone', attempts: 1}})})); }),
  });
  const lateRun = late.el('Start').click();
  await settle();
  late.window._jaAccountCacheNamespace = 'ja' + 'd'.repeat(64);
  while (lateReleases.length) { for (const release of lateReleases.splice(0)) release(); await settle(); }
  await lateRun; await settle();
  assert.equal(late.el('Invalid').textContent, 3, 'learning the account after starting is not an account change');
  assert(late.el('Message').textContent.startsWith('Finished.'), late.el('Message').textContent);

  // ---- Stop while the first page is loading -------------------------------------
  let firstPage;
  const early = fixture({contactsFetch: () => new Promise(resolve => { firstPage = () => resolve({ok: true, status: 200, json: async () => ({contacts: [contact(1, 'a@x.example')], next_offset: 1, total: 2})}); })});
  const earlyRun = early.el('Start').click();
  await settle();
  early.el('Stop').click();
  firstPage();
  await earlyRun; await settle();
  assert.equal(early.el('Message').textContent, 'Stopped. Completed results are kept; press Continue to check the rest.');
  assert.equal(early.el('Start').disabled, false);
  assert.equal(early.verifierCalls().length, 0);

  // ---- Temporary JobAdder page errors are retried --------------------------------
  let pageTries = 0;
  const flaky = fixture({contactsFetch: async () => {
    pageTries += 1;
    if (pageTries === 1) return {ok: false, status: 503, json: async () => ({error: 'JobAdder could not be reached to refresh the sign-in.'})};
    if (pageTries === 2) throw TypeError('Failed to fetch');
    return {ok: true, status: 200, json: async () => ({contacts: [contact(1, 'bad@x.example')], next_offset: null, total: 1})};
  }});
  await flaky.el('Start').click();
  await settle();
  assert.equal(pageTries, 3);
  assert(flaky.el('Message').textContent.startsWith('Finished.'), flaky.el('Message').textContent);
  let pageFails = 0;
  const down = fixture({contactsFetch: async () => { pageFails += 1; return {ok: false, status: 502, json: async () => ({error: 'JobAdder could not list client contacts (HTTP 500). Try again later.'})}; }});
  await down.el('Start').click();
  await settle();
  assert.equal(pageFails, 4, 'tried once and retried three times');
  assert(down.el('Message').textContent.startsWith('Stopped: JobAdder could not list client contacts'), down.el('Message').textContent);

  // ---- The JobAdder account changes in the middle of a check ------------------
  const releases = [];
  const switching = fixture({
    pages: [{contacts: [contact(1, 'bad@one.example'), contact(2, 'bad@two.example'), contact(3, 'bad@three.example')], next_offset: null, total: 3}],
    verifierFetch: body => new Promise(resolve => { releases.push(() => resolve({ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'invalid', reason: 'Gone', attempts: 1}})})); }),
  });
  const switchingRun = switching.el('Start').click();
  await settle();
  assert.equal(switching.verifierCalls().length, 2);
  switching.window._jaAccountCacheNamespace = 'ja' + 'b'.repeat(64);
  switching.window.clearEmailVerifierJobAdderAccountState();
  for (const release of releases.splice(0)) release();
  await switchingRun; await settle();
  assert.equal(switching.el('Invalid').textContent, 0, 'no result from the old account is shown');
  assert.equal(switching.el('Results').children.length, 0);
  assert.equal(switching.verifierCalls().length, 2, 'no further checks after the account changed');
  assert.equal(switching.el('Message').textContent, 'The JobAdder account changed, so the previous scan was cleared.');
  assert.equal(switching.el('Start').disabled, false);

  // ---- Sign out and straight back into the same account mid-check -------------
  const sameReleases = [];
  const same = fixture({
    pages: [{contacts: Array.from({length: 5}, (_, i) => contact(i + 1, 'bad@s' + i + '.example')), next_offset: null, total: 5}],
    verifierFetch: body => new Promise(resolve => { sameReleases.push(() => resolve({ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'invalid', reason: 'Gone', attempts: 1}})})); }),
  });
  const sameNamespace = same.window._jaAccountCacheNamespace;
  const sameRun = same.el('Start').click();
  await settle();
  same.window._jaAccountCacheNamespace = '';
  same.window.clearEmailVerifierJobAdderAccountState();
  same.window._jaAccountCacheNamespace = sameNamespace;
  for (const release of sameReleases.splice(0)) release();
  await sameRun; await settle();
  assert.equal(same.verifierCalls().length, 2, 'the cleared scan does not keep checking in the background');
  assert.equal(same.el('Results').children.length, 0);

  // ---- The account changes and the sign-out signal is missed ----------------------
  const silentReleases = [];
  const silent = fixture({
    pages: [{contacts: [contact(1, 'bad@one.example'), contact(2, 'bad@two.example'), contact(3, 'bad@three.example')], next_offset: null, total: 3}],
    verifierFetch: body => new Promise(resolve => { silentReleases.push(() => resolve({ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'invalid', reason: 'Gone', attempts: 1}})})); }),
  });
  const silentRun = silent.el('Start').click();
  await settle();
  silent.window._jaAccountCacheNamespace = 'ja' + 'c'.repeat(64);
  for (const release of silentReleases.splice(0)) release();
  await silentRun; await settle();
  assert.equal(silent.el('Invalid').textContent, 0, 'results from the previous account are never shown');
  assert.equal(silent.el('Results').children.length, 0);
  assert.equal(silent.verifierCalls().length, 2, 'no further checks for the previous account');
  assert.equal(silent.el('Message').textContent, 'The JobAdder account changed, so the previous scan was cleared.');
  assert.equal(silent.el('Continue').disabled, true);

  // ---- Stop keeps results; Continue after an account change starts over ------
  const gates = [];
  const stopping = fixture({
    pages: [{contacts: [contact(1, 'a@one.example'), contact(2, 'b@two.example'), contact(3, 'c@three.example'), contact(4, 'd@four.example')], next_offset: null, total: 4}],
    verifierFetch: body => new Promise(resolve => { gates.push(() => resolve({ok: true, status: 200, json: async () => ({ok: true, result: {email: body.email, status: 'invalid', reason: 'Gone', attempts: 1}})})); }),
  });
  const stopRun = stopping.el('Start').click();
  await settle();
  stopping.el('Stop').click();
  for (const gate of gates.splice(0)) gate();
  await stopRun; await settle();
  assert.equal(stopping.verifierCalls().length, 2);
  assert.equal(stopping.el('Invalid').textContent, 2);
  assert(stopping.el('Message').textContent.startsWith('Stopped. Completed results are kept'));
  stopping.window._jaAccountCacheNamespace = '';
  await stopping.el('Continue').click();
  assert.equal(stopping.el('Message').textContent, 'The JobAdder account changed. Start a new scan.');
  assert.equal(stopping.el('Invalid').textContent, 0);
  assert.equal(stopping.verifierCalls().length, 2);

  // ---- Network that cannot reach mail servers --------------------------------
  const blocked = fixture({
    pages: [{contacts: Array.from({length: 6}, (_, i) => contact(i + 1, 'x@b' + i + '.example')), next_offset: null, total: 6}],
    verdict: () => ({status: 'unknown', outcome: 'connection', reason: 'Could not connect.', attempts: 2}),
  });
  await blocked.el('Start').click();
  await settle();
  assert.equal(blocked.el('Warning').hidden, false);
  assert(blocked.el('Warning').textContent.includes('port 25'));
  assert.equal(blocked.el('Invalid').textContent, 0, 'blocked checks never become Invalid');
  const reachable = fixture({
    pages: [{contacts: Array.from({length: 7}, (_, i) => contact(i + 1, 'x@r' + i + '.example')), next_offset: null, total: 7}],
    verdict: email => email.endsWith('@r6.example') ? {status: 'accepted', reason: 'Fine', attempts: 2} : {status: 'unknown', outcome: 'connection', reason: 'Could not connect.', attempts: 2},
  });
  await reachable.el('Start').click();
  await settle();
  assert.equal(reachable.el('Warning').hidden, true, 'one reachable server rules out a blocked network');

  // ---- Quick mode and the render cap ---------------------------------------------
  const quickRun = fixture({mode: 'quick', pages: [{contacts: Array.from({length: 520}, (_, i) => contact(i + 1, 'p' + i + '@q' + i + '.example')), next_offset: null, total: 520}],
    verdict: () => ({status: 'domain_ok', reason: 'Domain passed', attempts: 0})});
  await quickRun.el('Start').click();
  await settle(40);
  assert(quickRun.verifierCalls().every(call => JSON.parse(call.init.body).mode === 'quick'));
  assert.equal(quickRun.el('Accepted').textContent, 520);
  quickRun.el('Filter').value = ''; quickRun.el('Filter').handlers.change();
  assert.equal(quickRun.el('Results').children.length, 500);
  assert.equal(quickRun.el('More').hidden, false);
  assert(quickRun.el('More').textContent.includes('first 500 of 520'));

  // ---- A page that does not advance stops loading instead of looping ----------
  let pageRequests = 0;
  const stuck = fixture({contactsFetch: async () => { pageRequests += 1; return {ok: true, status: 200, json: async () => ({contacts: [contact(pageRequests, 'a' + pageRequests + '@s.example')], next_offset: 0, total: 50})}; }});
  await stuck.el('Start').click();
  await settle();
  assert.equal(pageRequests, 1);
  assert.equal(stuck.verifierCalls().length, 1);

  console.log('email verifier JobAdder scan fixture passed');
  finished = true;
}
// A scan that never settles would let Node exit 0 with nothing left to run.
let finished = false;
process.on('exit', () => { if (!finished) { console.error('The fixture stopped before finishing: a scan never settled.'); process.exitCode = 1; } });
main().catch(error => { console.error(error); process.exit(1); });
