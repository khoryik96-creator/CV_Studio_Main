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
  assert.ok(html.includes('id="cvDownloadCompanyProfileFolderPreview"'));
  assert.ok(html.includes('id="cvDownloadSummaryFolderPreview"'));
  assert.ok(html.includes('id="cvDownloadBlindJdFolderPreview"'));
  assert.ok(html.includes('id="cvDownloadOwlFolderPreview"'));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('formatted')"));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('blind')"));
  assert.ok(html.includes("cvStudioVerifyDownloadDirectory('formatted')"));
  assert.ok(html.includes("cvStudioVerifyDownloadDirectory('blind')"));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('company_profile')"));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('summary')"));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('blind_jd')"));
  assert.ok(html.includes("cvStudioChooseDownloadDirectory('owl')"));
  assert.ok(html.includes("CV Studio's private local runtime state"));
  assert.ok(html.includes('The same folder can be used for any or all destinations'));
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

  const summary = functionSource(html, 'applySummaryToUploadedDocx');
  const companyWord = functionSource(html, 'exportCompanyDocImpl');
  const companyPdf = functionSource(html, 'exportCompanyPDFImpl');
  const blindJdWord = functionSource(html, 'exportAnonJDDocImpl');
  const blindJdPdf = functionSource(html, 'exportAnonJDPDFImpl');
  const owlWord = functionSource(html, 'exportTheOwlWordImpl');
  const owlPdf = functionSource(html, 'exportTheOwlPDFImpl');
  // Each public export is a thin guarded wrapper so a build/save failure shows a
  // user-facing error instead of an unhandled promise rejection (silent no-op).
  ['exportCompanyDoc', 'exportCompanyPDF', 'exportAnonJDDoc', 'exportAnonJDPDF',
   'exportTheOwlWord', 'exportTheOwlPDF'].forEach(function(name){
    const wrapper = functionSource(html, name);
    assert.ok(wrapper.includes('try {') && wrapper.includes('catch'),
      name + ' must wrap its implementation in try/catch');
    assert.ok(wrapper.includes('showToast'), name + ' must surface a failure toast');
    assert.ok(wrapper.includes(name + 'Impl('), name + ' must delegate to its impl');
  });
  // Summary DOCX routes through the Summary Output folder (this feature) while
  // still honouring the anonymized filename introduced by the anonymization work.
  assert.ok(summary.includes("cvStudioSaveDownloadBlob(blob, summaryName, 'summary')"));
  assert.ok(summary.includes("_summaryGeneratedAnonymized === true ? ' - Anonymized Summary.docx' : ' - Summary.docx'"));
  assert.ok(companyWord.includes("'company_profile'"));
  assert.ok(companyPdf.includes("doc.output('blob')"));
  assert.ok(companyPdf.includes("'company_profile'"));
  assert.ok(!companyPdf.includes('doc.save('));
  assert.ok(blindJdWord.includes("'blind_jd'"));
  assert.ok(blindJdPdf.includes("doc.output('blob')"));
  assert.ok(blindJdPdf.includes("'blind_jd'"));
  assert.ok(!blindJdPdf.includes('doc.save('));
  assert.ok(owlWord.includes("'owl'"));
  assert.ok(owlPdf.includes("doc.output('blob')"));
  assert.ok(owlPdf.includes("'owl'"));
  assert.ok(!owlPdf.includes('doc.save('));
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
    'cvStudioDownloadDestinationConfig','normalizeCvDownloadDestination','cvStudioSafeDownloadFilename','cvStudioFallbackDownloadBlob',
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

  // A definitive folder-save failure must NOT lose the file: it also lands in
  // the browser Downloads folder (the same place unconfigured saves use).
  saveMode='failed';
  const fallback=await context.cvStudioSaveDownloadBlob(blob,'Failure.docx','formatted');
  assert.strictEqual(fallback.method,'failed');
  assert.strictEqual(fallback.configured,true);
  assert.strictEqual(fallback.browserFallback,true);
  assert.ok(fallback.fallbackReason.includes('Drive unavailable'));
  assert.strictEqual(clicked[1],'Failure.docx');

  // An unconfirmed (network-dropped) save also falls back rather than risk loss.
  saveMode='lost';
  const uncertain=await context.cvStudioSaveDownloadBlob(blob,'Uncertain.docx','formatted');
  assert.strictEqual(uncertain.method,'uncertain');
  assert.strictEqual(uncertain.uncertain,true);
  assert.strictEqual(uncertain.browserFallback,true);
  assert.strictEqual(uncertain.folder,'C:\\CV Output');
  assert.ok(uncertain.fallbackReason.includes('could not confirm'));
  assert.ok(uncertain.fallbackReason.includes('before retrying'));
  assert.strictEqual(clicked[2],'Uncertain.docx');
  // One browser fallback per failed/uncertain save (the blind case plus these two).
  assert.strictEqual(revoked.length,3);
  assert.ok(revoked.every(function(v){return v==='blob:fallback';}));
}

async function folderStatusFailureFallsBackToBrowserContract() {
  const clicked=[];
  const context={
    String,Math,Date,Promise,
    window:{},
    document:{body:{appendChild(){}},createElement(){return {click(){clicked.push(this.download);},remove(){}};}},
    URL:{createObjectURL(){return 'blob:fallback';},revokeObjectURL(){}},
    setTimeout(fn){fn();},
    _cvDownloadLastResult:{},
    _cvNativeDownloadFolderState:{native_supported:true,status_loaded:false,folders:{formatted:null,blind:null}},
    _cvNativeDownloadFolderLoadPromise:null,
    cvStudioRenderDownloadDestination(){},
    async fetch(){throw new Error('Folder status unavailable');},
  };
  loadFunctions(context,[
    'cvStudioDownloadDestinationConfig','normalizeCvDownloadDestination','cvStudioSafeDownloadFilename','cvStudioFallbackDownloadBlob',
    'cvStudioNativeDownloadFolder','cvStudioLoadDownloadFolderState',
    'cvStudioPrepareDownloadDestination','cvStudioSaveDownloadBlob',
  ]);
  // When the configured folder's status cannot even be verified, the generated
  // file must not be lost: it falls back to the browser Downloads folder.
  const result=await context.cvStudioSaveDownloadBlob({fixture:true},'Sensitive CV.docx','formatted');
  assert.strictEqual(result.method,'failed');
  assert.strictEqual(result.configured,true);
  assert.strictEqual(result.browserFallback,true);
  assert.ok(result.fallbackReason.includes('Folder status unavailable'));
  assert.deepStrictEqual(clicked,['Sensitive CV.docx']);
}

async function showDownloadResultReportsBrowserFallbackContract() {
  const toasts=[];
  const context={String, showToast(message,level){toasts.push({message,level});}};
  loadFunctions(context,['cvStudioShowDownloadResult']);
  // A folder failure that fell back to the browser is a warning, not an error,
  // and reports success so callers do not treat it as a lost file.
  const ok=context.cvStudioShowDownloadResult(
    {method:'failed',configured:true,browserFallback:true,fallbackReason:'Drive unavailable.'},
    'Company Profile PDF');
  assert.strictEqual(ok,true);
  assert.strictEqual(toasts[0].level,'warn');
  assert.ok(toasts[0].message.includes('downloaded to your browser instead'));
  assert.ok(toasts[0].message.includes('Drive unavailable'));
  // A true failure with no fallback at all is still an error returning false.
  const bad=context.cvStudioShowDownloadResult(
    {method:'failed',configured:true,fallbackReason:'nowhere to write'},'Company Profile PDF');
  assert.strictEqual(bad,false);
  assert.strictEqual(toasts[1].level,'err');
}

async function nativeSelectionAndFullPathPreviewContract() {
  const nodes={};
  function node(id){if(!nodes[id])nodes[id]={textContent:'',style:{},classList:{remove(){},toggle(){}}};return nodes[id];}
  const toasts=[];
  const context={
    String,Promise,document:{getElementById:node},
    showToast(message,level){toasts.push({message,level});},
    _cvDownloadLastResult:{},
    _cvNativeDownloadFolderState:{native_supported:true,folders:{formatted:null,blind:null,company_profile:null,summary:null,blind_jd:null,owl:null}},
    async cvStudioNativeDownloadFolderRequest(){return {ok:true,folder:{configured:true,path:'C:\\Recruitment\\CVs',available:true,writable:true}};},
  };
  loadFunctions(context,[
    'cvStudioDownloadDestinationConfig','normalizeCvDownloadDestination','cvStudioRenderDownloadDestination',
    'cvStudioRenderDownloadDirectory','cvStudioChooseDownloadDirectory',
  ]);
  const chosen=await context.cvStudioChooseDownloadDirectory('company_profile');
  assert.strictEqual(chosen,true);
  assert.strictEqual(nodes.cvDownloadCompanyProfileFolderName.textContent,'C:\\Recruitment\\CVs');
  assert.strictEqual(nodes.cvDownloadCompanyProfileFolderPreview.textContent,'Destination: C:\\Recruitment\\CVs');
  assert.strictEqual(nodes.cvDownloadCompanyProfileFolderAccess.textContent,'Configured');
  assert.ok(toasts[0].message.includes('Company Profile'));
  assert.ok(toasts[0].message.includes('C:\\Recruitment\\CVs'));

  context._cvDownloadLastResult.company_profile={method:'folder',path:'C:\\Recruitment\\CVs\\Company.pdf'};
  context.cvStudioRenderDownloadDestination('company_profile',{configured:true,path:'C:\\Recruitment\\CVs',available:true});
  assert.strictEqual(nodes.cvDownloadCompanyProfileFolderPreview.textContent,'Last saved: C:\\Recruitment\\CVs\\Company.pdf');
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
  .then(folderStatusFailureFallsBackToBrowserContract)
  .then(showDownloadResultReportsBrowserFallbackContract)
  .then(nativeSelectionAndFullPathPreviewContract)
  .then(batchModeContract)
  .then(staleStartupRegistrationRepairContract)
  .then(()=>console.log('CV download folder frontend fixtures passed'))
  .catch((error)=>{console.error(error);process.exit(1);});
