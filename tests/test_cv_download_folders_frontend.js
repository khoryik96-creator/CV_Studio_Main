'use strict';

const assert = require('assert');
const vm = require('vm');
const html = require('./frontend_sources').frontendSource();

function functionSource(source, name) {
  const asyncStart = source.lastIndexOf('async function ' + name + '(');
  const regularStart = source.lastIndexOf('function ' + name + '(');
  const start = asyncStart >= 0 && regularStart === asyncStart + 6
    ? asyncStart
    : Math.max(asyncStart, regularStart);
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
  assert.ok(html.includes('id="cvDownloadFormattedFolderPreview"'));
  assert.ok(html.includes('id="cvDownloadBlindFolderPreview"'));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('formatted')"));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('blind')"));
  assert.ok(html.includes("cvStudioVerifyDownloadDirectory('formatted')"));
  assert.ok(html.includes("cvStudioVerifyDownloadDirectory('blind')"));
  assert.ok(html.includes("CV Studio's private local runtime state"));
  assert.ok(html.includes('The same folder can be used for both'));
  assert.ok(!html.includes('browsers expose only the selected folder name'));

  const showSettings = functionSource(html, 'showSettingsTab');
  assert.ok(showSettings.includes("downloads:'Downloads'"));
  assert.ok(showSettings.includes("'downloads'"));
  assert.ok(showSettings.includes('renderCvDownloadSettings'));
  const singleDownload = functionSource(html, 'downloadDocx');
  assert.ok(singleDownload.includes('cvStudioSaveDownloadBlob'));
  assert.ok(singleDownload.includes('result.uncertain'));

  const batchOne = functionSource(html, 'downloadSingleBatchFile');
  const batchAll = functionSource(html, 'downloadBatchZip');
  assert.ok(batchOne.includes('item.kind || bf.downloadKind'));
  assert.ok(batchAll.includes('firstItem.kind'));
  assert.ok(!batchOne.includes('_batchMode'));
  assert.ok(!batchAll.includes('_batchMode'));
  assert.ok(batchOne.includes('cvStudioSaveDownloadBlob'));
  assert.ok(batchOne.includes('result.uncertain'));
  assert.ok(batchAll.includes('cvStudioPrepareDownloadDestination'));
  assert.ok(batchAll.includes('uncertainCount'));
}

function filenameSafetyContract() {
  const context = {String, Math, Date};
  loadFunctions(context, ['cvStudioSafeDownloadFilename']);
  assert.strictEqual(context.cvStudioSafeDownloadFilename('Hyppies CV - Lee.docx'), 'Hyppies CV - Lee.docx');
  assert.strictEqual(context.cvStudioSafeDownloadFilename('../CON.docx'), '_CON.docx');
  assert.strictEqual(context.cvStudioSafeDownloadFilename('A/B\\C:*?"<>|.docx'), 'A_B_C_______.docx');
  assert.ok(context.cvStudioSafeDownloadFilename('x'.repeat(240) + '.docx').length <= 180);
}

async function nativeFolderSaveAndFallbackContract() {
  const clicked = [], revoked = [], requests = [];
  let saveMode = 'success';
  const context = {
    String, Math, Date, Promise,
    FormData: class { constructor(){this.entries=[];} append(){this.entries.push(Array.from(arguments));} },
    window:{},
    document:{body:{appendChild(){}},createElement(){return {click(){clicked.push(this.download);},remove(){}};}},
    URL:{createObjectURL(){return 'blob:fallback';},revokeObjectURL(v){revoked.push(v);}},
    setTimeout(fn){fn();},
    _cvDownloadLastResult:{},
    _cvNativeDownloadFolderState:{native_supported:true,status_loaded:true,folders:{
      formatted:{configured:true,path:'C:\\CV Output',available:true},
      blind:{configured:false,path:'',available:false},
    }},
    _cvNativeDownloadFolderLoadPromise:null,
    cvStudioRenderDownloadDestination(){},
    async fetch(path, options){
      requests.push({path,options});
      if(path==='/downloads/folders')return {ok:true,async json(){return {ok:true,native_supported:true,folders:{
        formatted:{configured:true,path:'C:\\CV Output',available:true},
        blind:{configured:false,path:'',available:false},
      }};}};
      if(saveMode==='success')return {ok:true,async json(){return {ok:true,filename:'Hyppies CV (1).docx',folder:'C:\\CV Output',path:'C:\\CV Output\\Hyppies CV (1).docx'};}};
      if(saveMode==='lost')throw new Error('Connection lost after upload');
      return {ok:false,async json(){return {ok:false,error:'Drive unavailable'};}};
    },
  };
  loadFunctions(context,[
    'normalizeCvDownloadDestination','cvStudioSafeDownloadFilename','cvStudioFallbackDownloadBlob',
    'cvStudioNativeDownloadFolder','cvStudioLoadDownloadFolderState',
    'cvStudioPrepareDownloadDestination','cvStudioSaveDownloadBlob',
  ]);

  const blob={fixture:true};
  const saved=await context.cvStudioSaveDownloadBlob(blob,'Hyppies CV.docx','formatted');
  assert.strictEqual(saved.method,'folder');
  assert.strictEqual(saved.path,'C:\\CV Output\\Hyppies CV (1).docx');
  assert.strictEqual(requests[0].path,'/downloads/folders');
  assert.strictEqual(requests[1].path,'/downloads/save');
  assert.strictEqual(clicked.length,0);

  const browser=await context.cvStudioSaveDownloadBlob(blob,'Blind.docx','blind');
  assert.strictEqual(browser.method,'browser');
  assert.strictEqual(clicked[0],'Blind.docx');

  saveMode='failed';
  const fallback=await context.cvStudioSaveDownloadBlob(blob,'Failure.docx','formatted');
  assert.strictEqual(fallback.method,'failed');
  assert.strictEqual(fallback.configured,true);
  assert.ok(fallback.fallbackReason.includes('Drive unavailable'));

  saveMode='lost';
  const uncertain=await context.cvStudioSaveDownloadBlob(blob,'Uncertain.docx','formatted');
  assert.strictEqual(uncertain.method,'uncertain');
  assert.strictEqual(uncertain.uncertain,true);
  assert.strictEqual(uncertain.folder,'C:\\CV Output');
  assert.ok(uncertain.fallbackReason.includes('could not confirm'));
  assert.ok(uncertain.fallbackReason.includes('before retrying'));
  assert.deepStrictEqual(revoked,['blob:fallback']);
}

async function folderStatusFailureStopsBrowserFallbackContract() {
  const clicked=[];
  const context={
    String,Math,Date,Promise,
    window:{},
    document:{body:{appendChild(){}},createElement(){return {click(){clicked.push(this.download);},remove(){}};}},
    URL:{createObjectURL(){return 'blob:must-not-download';},revokeObjectURL(){}},
    setTimeout(fn){fn();},
    _cvDownloadLastResult:{},
    _cvNativeDownloadFolderState:{native_supported:true,status_loaded:false,folders:{formatted:null,blind:null}},
    _cvNativeDownloadFolderLoadPromise:null,
    cvStudioRenderDownloadDestination(){},
    async fetch(){throw new Error('Folder status unavailable');},
  };
  loadFunctions(context,[
    'normalizeCvDownloadDestination','cvStudioSafeDownloadFilename','cvStudioFallbackDownloadBlob',
    'cvStudioNativeDownloadFolder','cvStudioLoadDownloadFolderState',
    'cvStudioPrepareDownloadDestination','cvStudioSaveDownloadBlob',
  ]);
  const result=await context.cvStudioSaveDownloadBlob({fixture:true},'Sensitive CV.docx','formatted');
  assert.strictEqual(result.method,'failed');
  assert.strictEqual(result.configured,true);
  assert.ok(result.fallbackReason.includes('Folder status unavailable'));
  assert.deepStrictEqual(clicked,[]);
}

async function nativeSelectionAndFullPathPreviewContract() {
  const nodes={};
  function node(id){if(!nodes[id])nodes[id]={textContent:'',style:{},classList:{remove(){},toggle(){}}};return nodes[id];}
  const toasts=[];
  const context={
    String,Promise,document:{getElementById:node},
    showToast(message,level){toasts.push({message,level});},
    _cvDownloadLastResult:{},
    _cvNativeDownloadFolderState:{native_supported:true,folders:{formatted:null,blind:null}},
    async cvStudioNativeDownloadFolderRequest(){return {ok:true,folder:{configured:true,path:'C:\\Recruitment\\CVs',available:true,writable:true}};},
  };
  loadFunctions(context,[
    'normalizeCvDownloadDestination','cvStudioRenderDownloadDestination',
    'cvStudioRenderDownloadDirectory','cvStudioChooseDownloadDirectory',
  ]);
  const chosen=await context.cvStudioChooseDownloadDirectory('formatted');
  assert.strictEqual(chosen,true);
  assert.strictEqual(nodes.cvDownloadFormattedFolderName.textContent,'C:\\Recruitment\\CVs');
  assert.strictEqual(nodes.cvDownloadFormattedFolderPreview.textContent,'Destination: C:\\Recruitment\\CVs');
  assert.strictEqual(nodes.cvDownloadFormattedFolderAccess.textContent,'Configured');
  assert.ok(toasts[0].message.includes('C:\\Recruitment\\CVs'));

  context._cvDownloadLastResult.formatted={method:'folder',path:'C:\\Recruitment\\CVs\\Hyppies CV.docx'};
  context.cvStudioRenderDownloadDestination('formatted',{configured:true,path:'C:\\Recruitment\\CVs',available:true});
  assert.strictEqual(nodes.cvDownloadFormattedFolderPreview.textContent,'Last saved: C:\\Recruitment\\CVs\\Hyppies CV.docx');
}

async function batchModeContract() {
  const saveCalls=[];
  const toasts=[];
  const context={
    _batchMode:'blind',
    _batchFiles:[{id:'formatted-row',filename:'Formatted.docx',status:'done-ok',downloadKind:'formatted'}],
    _batchBlobs:[{filename:'Formatted.docx',blob:{id:1},kind:'formatted'}],
    cvStudioSaveDownloadBlob:async (blob,filename,kind)=>{saveCalls.push({blob,filename,kind});return {method:'folder',filename,folder:'Formatted'};},
    cvStudioPrepareDownloadDestination:async (kind)=>({kind,configured:true,folder:{path:'C:\\Formatted'},handle:{native:true}}),
    showToast(message,level){toasts.push({message,level});},setTimeout(fn){fn();},
  };
  loadFunctions(context,['downloadSingleBatchFile','downloadBatchZip']);
  await context.downloadSingleBatchFile('formatted-row');
  assert.strictEqual(saveCalls[0].kind,'formatted');
  saveCalls.length=0;
  await context.downloadBatchZip();
  assert.strictEqual(saveCalls[0].kind,'formatted');
  saveCalls.length=0;
  context.cvStudioPrepareDownloadDestination=async ()=>({statusFailed:true,fallbackReason:'Folder status unavailable',handle:null});
  await context.downloadBatchZip();
  assert.strictEqual(saveCalls.length,0);
  assert.ok(toasts[toasts.length-1].message.includes('Download was not started'));
}

async function staleStartupRegistrationRepairContract() {
  const nodes={
    startupToggle:{checked:false},
    startupLabel:{textContent:''},
  };
  const requests=[];
  const toasts=[];
  const context={
    Promise,
    document:{getElementById(id){return nodes[id] || null;}},
    async fetch(path,options){
      requests.push({path,options:options || {}});
      if(path==='/startup/status')return {async json(){return {enabled:true,configured:false,repair_required:true};}};
      if(path==='/startup/enable')return {async json(){return {ok:true};}};
      throw new Error('Unexpected request: '+path);
    },
    showToast(message,level){toasts.push({message,level});},
  };
  loadFunctions(context,['setStartup','loadStartupStatus']);
  await context.loadStartupStatus();
  assert.strictEqual(nodes.startupToggle.checked,true);
  assert.strictEqual(nodes.startupLabel.textContent,'On');
  assert.deepStrictEqual(requests.map((item)=>item.path),['/startup/status','/startup/enable']);
  assert.strictEqual(requests[1].options.method,'POST');
  assert.ok(toasts[0].message.includes('startup location updated'));
}

Promise.resolve()
  .then(markupAndWiringContract)
  .then(filenameSafetyContract)
  .then(nativeFolderSaveAndFallbackContract)
  .then(folderStatusFailureStopsBrowserFallbackContract)
  .then(nativeSelectionAndFullPathPreviewContract)
  .then(batchModeContract)
  .then(staleStartupRegistrationRepairContract)
  .then(()=>console.log('CV download folder frontend fixtures passed'))
  .catch((error)=>{console.error(error);process.exit(1);});
