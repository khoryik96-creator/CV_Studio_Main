'use strict';
// The /parse source check's warning has to stay on screen.
//
// It used to be a 3.5-second toast. In the single-CV flow the very next line
// showed "Parsed! Generating DOCX..." in the same toast slot, so the warning was
// visible for well under a second: a CV the app itself had flagged as missing
// three employers was delivered with nobody having seen the flag. In a batch each
// file's toast replaced the previous file's.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const read = name => fs.readFileSync(path.join(root, 'vendor', 'cvstudio', name), 'utf8');
const cvFormat = read('cv-format.js');
const batchFormat = read('batch-format.js');

function fnFrom(src, name) {
  const start = src.search(new RegExp('(?:async\\s+)?function\\s+' + name + '\\('));
  assert.ok(start >= 0, 'missing function: ' + name);
  let depth = 0, quote = '', escaped = false;
  for (let i = src.indexOf('{', start); i < src.length; i += 1) {
    const ch = src[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === quote) quote = '';
      continue;
    }
    if (ch === '"' || ch === "'" || ch.charCodeAt(0) === 96) { quote = ch; continue; }
    if (ch === '{') depth += 1;
    else if (ch === '}' && --depth === 0) return src.slice(start, i + 1);
  }
  throw new Error('unterminated function: ' + name);
}

// ── single CV: the banner itself ─────────────────────────────────────────────
function bannerContext() {
  const inserted = [];
  const outputBox = {
    firstChild: {marker: 'preview'},
    insertBefore(node, ref) { inserted.push({node, ref}); },
  };
  const context = {
    String,
    document: {
      getElementById(id) { return id === 'outputBox' ? outputBox : null; },
      createElement(tag) {
        const attrs = {};
        return {tag, className: '', textContent: '', attrs,
          setAttribute(k, v) { attrs[k] = v; },
          set innerHTML(v) { throw new Error('the banner must never be built from HTML'); }};
      },
    },
  };
  vm.createContext(context);
  vm.runInContext(fnFrom(cvFormat, 'cvShowParseWarningBanner'), context);
  return {context, inserted, outputBox};
}

{
  const {context, inserted, outputBox} = bannerContext();
  // The message names employers taken from an uploaded CV, so it is text.
  const hostile = 'Employer(s) missing: <img src=x onerror=alert(1)> Acme & Co';
  context.cvShowParseWarningBanner(hostile);
  assert.strictEqual(inserted.length, 1);
  const {node, ref} = inserted[0];
  assert.strictEqual(ref, outputBox.firstChild, 'the banner goes above the preview');
  assert.strictEqual(node.tag, 'div');
  assert.strictEqual(node.className, 'cv-parse-warning');
  assert.strictEqual(node.attrs.role, 'alert');
  assert.ok(node.textContent.includes(hostile), 'the message is carried verbatim as text');
}
{
  const {context, inserted} = bannerContext();
  for (const empty of ['', '   ', null, undefined]) context.cvShowParseWarningBanner(empty);
  assert.strictEqual(inserted.length, 0, 'no warning, no banner');
}

// ── single CV: where the flow calls it ───────────────────────────────────────
{
  const flow = cvFormat;
  const preview = flow.indexOf('renderPreview(_parsedData);');
  const banner = flow.indexOf('cvShowParseWarningBanner(parseWarning);');
  const parsedToast = flow.indexOf("'Parsed! Generating DOCX…'");
  assert.ok(preview > 0 && banner > 0 && parsedToast > 0);
  // renderPreview replaces the whole output panel, so the banner must follow it.
  assert.ok(banner > preview, 'the banner is added after the preview renders');
  // A warning shown via toast only would be overwritten by this next toast.
  assert.ok(banner < parsedToast);
  // The warning is read from the response and kept in a variable the end of the
  // flow can still see.
  assert.ok(/var parseWarning = String\(\(data && data\.warning\) \|\| ''\)\.trim\(\);/.test(flow));
  // A flagged run does not finish on a green "Done!".
  assert.ok(/if \(parseWarning\) showToast\('Done — but read the warning above the preview/.test(flow));
  assert.ok(/else showToast\('Done! Click Download DOCX', 'ok'\);/.test(flow));
}

// ── batch: the warning stays on the file it belongs to ───────────────────────
function batchContext(files) {
  const nodes = {};
  const esc = s => String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const context = {
    String, Array, Object, JSON, Math,
    window: {},
    document: {getElementById(id) {
      return nodes[id] || (nodes[id] = {innerHTML: '', style: {}, classList: {add() {}, remove() {}}});
    }},
    esc, escAttr: s => esc(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
  };
  vm.createContext(context);
  vm.runInContext(batchFormat, context);
  context._batchFiles = files;
  context.renderBatchList();
  return nodes.batchFileList.innerHTML;
}

{
  const hostile = 'Employer(s) missing: <script>alert(1)</script>';
  const html = batchContext([
    {id: 'a', file: {name: 'a.docx'}, status: 'done-ok', parseWarning: hostile},
    {id: 'b', file: {name: 'b.docx'}, status: 'done-ok'},
    {id: 'c', file: {name: 'c.docx'}, status: 'done-blind', parseWarning: 'Blind check'},
  ]);
  assert.strictEqual((html.match(/class="cv-parse-warning batch"/g) || []).length, 2,
    'one warning per flagged file, none on the clean one');
  assert.ok(!html.includes('<script>alert(1)</script>'), 'the warning is escaped');
  assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
  assert.ok(html.includes('Blind check'));
}
{
  // Until a file finishes, its row shows progress, not a verdict.
  const html = batchContext([
    {id: 'p', file: {name: 'p.docx'}, status: 'processing', parseWarning: 'too early'},
    {id: 'q', file: {name: 'q.docx'}, status: 'pending', parseWarning: 'too early'},
    {id: 'r', file: {name: 'r.docx'}, status: 'done-err', error: 'x', parseWarning: 'too early'},
  ]);
  assert.ok(!html.includes('cv-parse-warning'));
}
{
  // The batch flow reads the field itself rather than depending on a helper from
  // another module: an earlier draft did, and a harness that loads this module
  // on its own marked every file failed.
  assert.ok(/bf\.parseWarning = String\(\(pData && pData\.warning\) \|\| ''\)\.trim\(\);/.test(batchFormat));
}

// ── the style exists and matches the app's amber warning ─────────────────────
{
  const css = read('app.css');
  assert.ok(/\.cv-parse-warning \{ background: #FFF7D6; color: #7A5200;/.test(css));
  assert.ok(/\.cv-parse-warning\.batch \{/.test(css));
}

console.log('PASS: CV parse warning persistence');
