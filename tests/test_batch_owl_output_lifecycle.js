'use strict';
// Exercise complete production workflows with synthetic responses, never live AI.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const root = path.resolve(__dirname, '..');
function load(name, context) {
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, 'vendor/cvstudio', name), 'utf8'), context);
}
function dom() {
  const nodes = {};
  return {getElementById(id) {
    return nodes[id] || (nodes[id] = {
      value:'', checked:false, disabled:false, dataset:{}, style:{display:''}, textContent:'',
      classList:{add(){},remove(){},contains(){return false;}},
      _html:'', set innerHTML(v){this._html=v;}, get innerHTML(){return this._html;},
      get innerText(){return this._html.replace(/<[^>]*>/g,' ');},
    });
  }};
}
async function batchLifecycle() {
  const saved=[], opened=[], messages=[];
  let serial=0, fail=false;
  const c={window:{}, document:dom(), console, FormData:class{append(){}},
    setTimeout(){return 1;}, clearTimeout(){}, setInterval(){return 1;}, clearInterval(){},
    showToast:(message)=>messages.push(message), clearTabRunState(){},
    aiRoutePayload:()=>({api_key:'synthetic-key',provider:'mock'}),
    markTabRunning:()=>1, markTabDone(){messages.push('run done');}, markTabFailed(){messages.push('run failed');},
    getCvTextAlignment:()=> 'left', getCvBlindCandidateGenderNeutralization:()=>false,
    getCvSummaryBoxAutoFit:()=>true, getCvAutoCorrectLanguage:()=>false,
    normalizeUsageClient:()=>({}), mergeUsageClient:()=>({}), responseCost:()=>0,
    cvRequireCompleteExtraction(){}, cvParseIsLong:()=>false, cvParseTimeoutMs:()=>1000,
    CV_EXTRACT_TEXT_TIMEOUT_MS:1000, cvMergeLevelLists:()=>[],
    recordPaidAiFailure(){}, normalizeAiProviderError:s=>s,
    extractNameFromFilename:()=>'', toTitleCase:s=>s, statsRecord:()=>1, statsMetaFromResponse:()=>({}),
    fetchWithTimeout:async url=>{
      if(fail) throw Error('Simulated extraction failure');
      if(url==='/extract-text') return {json:async()=>({text:'Synthetic CV'})};
      if(url==='/parse'||url==='/blind') return {ok:true,json:async()=>({data:{candidate:{name:'Same Name'}}})};
      assert.strictEqual(url,'/generate-docx');
      return {ok:true,blob:async()=>({serial:++serial})};
    },
    cvStudioSaveDownloadBlob:async(blob,filename,kind,destination)=>{
      saved.push({blob,filename,kind,destination});return {method:'folder'};
    },
    cvStudioPrepareDownloadDestination:async kind=>({kind,configured:true,handle:{native:true}}),
    cvStudioShowDownloadResult(){}, cvStudioOpenOutputFolder:async kind=>{opened.push(kind);return true;},
  };
  load('batch-format.js',c);
  c.renderBatchList=()=>{}; c.batchSetProgress=()=>{}; c.updateBatchSummary=()=>{};
  const row=id=>({id,file:{name:id+'.pdf'},status:'pending'});
  c._batchFiles=[row('first'),row('second')];
  await c.runBatch();
  assert.strictEqual(c._batchFiles[1].status,'done-ok');
  assert.strictEqual(c._batchBlobs.length,2);
  await c.downloadSingleBatchFile('second');
  assert.strictEqual(saved.pop().blob.serial,2,'same filenames must not select the first CV');
  c._batchFiles.push(row('third')); c._batchMode='blind';
  await c.runBatch();
  assert.strictEqual(c._batchBlobs.length,3,'additional runs retain previous outputs');
  await c.downloadSingleBatchFile('first');
  assert.strictEqual(saved.pop().blob.serial,1);
  await c.downloadBatchZip();
  assert.deepStrictEqual(saved.map(x=>x.kind),['formatted','formatted','blind']);
  assert.ok(saved.every(x=>x.destination.kind===x.kind),'each output uses its own destination');
  await c.openBatchOutputFolder();
  assert.deepStrictEqual(opened,['formatted','blind']);
  c._batchFiles.push(row('failed')); fail=true;
  await c.runBatch();
  assert.strictEqual(c._batchBlobs.length,3,'failed later runs do not erase successful outputs');
  assert.strictEqual(messages.at(-1),'run failed','earlier successes cannot mask a failed new run');
  assert.strictEqual(c.document.getElementById('btnBatchDownload').disabled,false);
  c.removeBatchFile('second');
  assert.strictEqual(c._batchBlobs.length,2);
  saved.length=0; await c.downloadBatchZip();
  assert.deepStrictEqual(saved.map(x=>x.blob.serial),[1,3],'removed rows leave Download All');
  c._batchRunning=true; c.removeBatchFile('first');
  assert.strictEqual(c._batchBlobs.length,2,'in-flight rows cannot be removed');
  c._batchRunning=false;
  // A concurrent list change cannot add files to a download already started.
  saved.length=0;
  c.cvStudioSaveDownloadBlob=async(blob,filename,kind)=>{
    saved.push({blob,filename,kind});
    if(saved.length===1)c._batchBlobs.push({id:'later',filename:'Later.docx',blob:{serial:99},kind:'formatted'});
    return {method:'folder'};
  };
  await c.downloadBatchZip();
  assert.deepStrictEqual(saved.map(x=>x.blob.serial),[1,3]);
  c._batchBlobs=c._batchBlobs.filter(x=>x.id!=='later');
  // Browser-only saves retain throttling and accurate outcomes.
  c.setTimeout=fn=>fn();
  c.cvStudioPrepareDownloadDestination=async kind=>({kind,configured:false,handle:null});
  c.cvStudioSaveDownloadBlob=async()=>({method:'browser'});
  await c.downloadBatchZip();
  assert.ok(messages.at(-1).includes('Downloading 2 files'));
  fail=false; c._batchFiles.push(row('snapshot'));
  const fetchBefore=c.fetchWithTimeout;
  let added=false;
  c.fetchWithTimeout=async url=>{
    if(!added){added=true;c._batchFiles.push(row('queued-during-run'));}
    return fetchBefore(url);
  };
  await c.runBatch();
  assert.strictEqual(c._batchFiles.find(x=>x.id==='snapshot').status,'done-blind');
  assert.strictEqual(c._batchFiles.find(x=>x.id==='queued-during-run').status,'pending',
    'newly added inputs wait for the next explicit run');
  c.clearBatch(); assert.strictEqual(c._batchBlobs.length,0);
  assert.strictEqual(c.document.getElementById('btnBatchDownload').disabled,true);
}
async function owlLifecycle() {
  const exported=[], messages=[];
  let reject=false;
  const c={window:{},document:dom(),console,
    aiRoutePayload:()=>({api_key:'synthetic-key'}),
    markTabRunning:()=>1,markTabDone(){},markTabFailed(){},
    showToast:m=>messages.push(m),esc:s=>s,_escDoc:s=>s,_safeFileStem:s=>s,
    normalizeUsageClient:()=>({input_tokens:0,output_tokens:0}),responseCost:()=>0,
    statsRecord(){},statsMetaFromResponse:()=>({}),
    callAIProxy:async()=>{if(reject)throw Error('Simulated failure');return {};},
    aiText:()=> 'Successful synthetic talent map',
    exportWordDocumentToDestination:async html=>{exported.push(html);return {result:{},format:'docx'};},
    cvStudioShowDownloadResult(){}, HYPPIES_LOGO_URI:'',
  };
  load('the-owl.js',c);
  c.formatMarketHTML=s=>s; c.marketTextToDocHtml=s=>s;
  c.document.getElementById('theOwlText').value='Synthetic job description '.repeat(8);
  await c.generateTheOwl(); await c.exportTheOwlWordImpl();
  assert.ok(exported[0].includes('Successful synthetic talent map'));
  assert.strictEqual(c.document.getElementById('theOwlWordBtn').style.display,'');
  reject=true;
  await c.generateTheOwl();
  for(const id of ['theOwlCopyBtn','theOwlWordBtn','theOwlPdfBtn'])
    assert.strictEqual(c.document.getElementById(id).style.display,'none');
  await c.exportTheOwlWordImpl(); await c.exportTheOwlPDFImpl(); await c.copyTheOwlReport();
  assert.strictEqual(exported.length,1,'failure/loading text must never become a report');
  assert.strictEqual(messages.at(-1),'Generate The Owl map first');
  reject=false; await c.generateTheOwl(); await c.exportTheOwlWordImpl();
  assert.strictEqual(exported.length,2,'a successful retry re-enables export');
}
Promise.resolve().then(batchLifecycle).then(owlLifecycle)
  .then(()=>console.log('Batch and Owl output lifecycle regression tests passed'))
  .catch(error=>{console.error(error);process.exit(1);});
