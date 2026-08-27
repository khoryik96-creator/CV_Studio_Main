'use strict';

const assert = require('assert');
const vm = require('vm');

const html = require('./frontend_sources').frontendSource();

function functionSource(source, name) {
  const asyncStart = source.indexOf('async function ' + name + '(');
  const start = asyncStart >= 0 ? asyncStart : source.indexOf('function ' + name + '(');
  assert.ok(start >= 0, 'missing function: ' + name);
  let brace = source.indexOf('{', start), depth = 0, quote = '', escaped = false;
  for (let i = brace; i < source.length; i += 1) {
    const ch = source[i];
    if (quote) {
      if (escaped) escaped = false;
      else if (ch === '\\') escaped = true;
      else if (ch === quote) quote = '';
      continue;
    }
    if (ch === '"' || ch === "'" || ch.charCodeAt(0) === 96) { quote = ch; continue; }
    if (ch === '{') depth += 1;
    else if (ch === '}' && --depth === 0) return source.slice(start, i + 1);
  }
  throw new Error('unterminated function: ' + name);
}

function loadFunctions(context, names) {
  vm.createContext(context);
  names.forEach((name) => vm.runInContext(functionSource(html, name), context));
}

function markupAndWiringContract() {
  assert.ok(html.includes('id="settingsTabDownloads"'));
  assert.ok(html.includes("showSettingsTab('downloads')"));
  assert.ok(html.includes('id="settingsPaneDownloads"'));
  assert.ok(html.includes('id="cvDownloadFormattedFolderName"'));
  assert.ok(html.includes('id="cvDownloadBlindFolderName"'));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('formatted')"));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('blind')"));
  assert.ok(html.includes('The same folder can be used for both'));

  const showSettings = functionSource(html, 'showSettingsTab');
  assert.ok(showSettings.includes("downloads:'Downloads'"));
  assert.ok(showSettings.includes("'downloads'"));
  assert.ok(showSettings.includes("renderCvDownloadSettings"));

  const single = functionSource(html, 'downloadDocx');
  assert.ok(single.includes("window._isBlind ? 'blind' : 'formatted'"));
  assert.ok(single.includes('cvStudioSaveDownloadBlob'));

  const batchOne = functionSource(html, 'downloadSingleBatchFile');
  const batchAll = functionSource(html, 'downloadBatchZip');
  assert.ok(batchOne.includes('item.kind || bf.downloadKind'));
  assert.ok(batchAll.includes('firstItem.kind'));
  assert.ok(!batchOne.includes('_batchMode'));
  assert.ok(!batchAll.includes('_batchMode'));
  assert.ok(batchOne.includes('cvStudioSaveDownloadBlob'));
  assert.ok(batchAll.includes('cvStudioPrepareDownloadDestination'));
}

function filenameSafetyContract() {
  const context = {String, Math, Date};
  loadFunctions(context, ['cvStudioSafeDownloadFilename']);
  assert.strictEqual(context.cvStudioSafeDownloadFilename('Hyppies CV - Lee.docx'), 'Hyppies CV - Lee.docx');
  assert.strictEqual(context.cvStudioSafeDownloadFilename('../CON.docx'), '_CON.docx');
  assert.strictEqual(context.cvStudioSafeDownloadFilename('A/B\\C:*?"<>|.docx'), 'A_B_C_______.docx');
  assert.ok(context.cvStudioSafeDownloadFilename('x'.repeat(240) + '.docx').length <= 180);
}

async function directFolderAndFallbackContract() {
  const clicked = [];
  const revoked = [];
  const body = {appendChild(){}, removeChild(){}};
  const context = {
    String, Math, Date, Promise,
    window: {},
    document: {
      body,
      createElement() {
        return {click(){ clicked.push({href:this.href, download:this.download}); }, remove(){}};
      },
    },
    URL: {
      createObjectURL(){ return 'blob:fallback'; },
      revokeObjectURL(value){ revoked.push(value); },
    },
    setTimeout(fn){ fn(); },
    showToast(){},
    cvStudioRenderDownloadDirectory(){ return Promise.resolve(true); },
    _cvDownloadDirectoryCache: {},
  };
  loadFunctions(context, [
    'normalizeCvDownloadDestination',
    'cvStudioSafeDownloadFilename',
    'cvStudioFallbackDownloadBlob',
    'cvStudioUniqueDownloadFilename',
    'cvStudioDirectoryWritePermission',
    'cvStudioPrepareDownloadDestination',
    'cvStudioSaveDownloadBlob',
  ]);

  assert.strictEqual(context.normalizeCvDownloadDestination('blind'), 'blind');
  assert.strictEqual(context.normalizeCvDownloadDestination('anything'), 'formatted');

  const writes = [];
  const handle = {
    kind: 'directory',
    name: 'CV Output',
    async queryPermission(){ return 'granted'; },
    async getFileHandle(name, options) {
      if (!options && name === 'Hyppies CV.docx') return {name};
      if (!options) { const error = new Error('missing'); error.name = 'NotFoundError'; throw error; }
      return {
        async createWritable() {
          return {
            async write(blob){ writes.push({name, blob}); },
            async close(){ writes.push({closed:name}); },
            async abort(){ writes.push({aborted:name}); },
          };
        },
      };
    },
  };
  context.cvStudioGetDownloadDirectory = async () => handle;
  const blob = {fixture:true};
  const saved = await context.cvStudioSaveDownloadBlob(blob, 'Hyppies CV.docx', 'formatted');
  assert.strictEqual(saved.method, 'folder');
  assert.strictEqual(saved.filename, 'Hyppies CV (1).docx');
  assert.deepStrictEqual(writes[0], {name:'Hyppies CV (1).docx', blob});
  assert.strictEqual(clicked.length, 0);

  const denied = {
    kind: 'directory', name: 'Denied',
    async queryPermission(){ return 'denied'; },
    async requestPermission(){ return 'denied'; },
  };
  context.cvStudioGetDownloadDirectory = async () => denied;
  const fallback = await context.cvStudioSaveDownloadBlob(blob, 'Fallback.docx', 'blind');
  assert.strictEqual(fallback.method, 'browser');
  assert.strictEqual(clicked.length, 1);
  assert.strictEqual(clicked[0].download, 'Fallback.docx');
  assert.deepStrictEqual(revoked, ['blob:fallback']);
}

async function longDuplicateAndBatchModeContract() {
  const filenameContext = {String, Math, Date, Promise};
  loadFunctions(filenameContext, ['cvStudioSafeDownloadFilename', 'cvStudioUniqueDownloadFilename']);
  const longName = filenameContext.cvStudioSafeDownloadFilename('Hyppies CV - ' + 'X'.repeat(220) + '.docx');
  assert.strictEqual(longName.length, 180);
  const checked = [];
  const longHandle = {
    async getFileHandle(name) {
      checked.push(name);
      if (name === longName) return {name};
      const error = new Error('missing'); error.name = 'NotFoundError'; throw error;
    },
  };
  const numbered = await filenameContext.cvStudioUniqueDownloadFilename(longHandle, longName);
  assert.notStrictEqual(numbered, longName);
  assert.ok(numbered.endsWith(' (1).docx'));
  assert.ok(numbered.length <= 180);
  assert.deepStrictEqual(checked.slice(0, 2), [longName, numbered]);

  const saveCalls = [];
  const batchContext = {
    _batchMode: 'blind',
    _batchFiles: [{id:'formatted-row', filename:'Formatted.docx', status:'done-ok', downloadKind:'formatted'}],
    _batchBlobs: [{filename:'Formatted.docx', blob:{id:1}, kind:'formatted'}],
    cvStudioSaveDownloadBlob: async (blob, filename, kind) => { saveCalls.push({blob, filename, kind}); return {method:'folder', filename, folder:'Formatted'}; },
    cvStudioPrepareDownloadDestination: async (kind) => ({kind, handle:{name:'Formatted'}}),
    showToast(){},
    setTimeout(fn){ fn(); },
  };
  loadFunctions(batchContext, ['downloadSingleBatchFile', 'downloadBatchZip']);
  await batchContext.downloadSingleBatchFile('formatted-row');
  assert.strictEqual(saveCalls[0].kind, 'formatted');
  saveCalls.length = 0;
  await batchContext.downloadBatchZip();
  assert.strictEqual(saveCalls[0].kind, 'formatted');
}

Promise.resolve()
  .then(markupAndWiringContract)
  .then(filenameSafetyContract)
  .then(directFolderAndFallbackContract)
  .then(longDuplicateAndBatchModeContract)
  .then(() => console.log('CV download folder frontend fixtures passed'))
  .catch((error) => { console.error(error); process.exit(1); });
