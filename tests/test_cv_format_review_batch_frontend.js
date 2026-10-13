'use strict';
// Exercise the real batch orchestration and row actions with synthetic responses.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const clone = value => JSON.parse(JSON.stringify(value));
const root = path.resolve(__dirname, '..');
const sources = ['cv-format.js', 'batch-format.js', 'fcv-upload.js'].map(name =>
  fs.readFileSync(path.join(root, 'vendor/cvstudio', name), 'utf8')).join('\n');
function descendants(node) { return [node, ...node.children.flatMap(descendants)]; }
function deferred() { let release; const promise = new Promise(resolve => {release=resolve;}); return {promise,release}; }
function harness(options={}) {
  const nodes={}, calls=[], stats=[], uploads=[], downloads=[], links=[];
  function element(tag='div') {
    const node={tagName:tag, children:[], style:{}, value:'', checked:false, disabled:false,
      textContent:'', className:'', dataset:{}, classList:{add(){},remove(){},contains(){return false;}},
      appendChild(child){this.children.push(child);return child;},
      replaceChildren(...children){this.children=children;this.textContent='';},
      setAttribute(){},focus(){},addEventListener(){},querySelector(){return null;},querySelectorAll(){return [];}};
    let markup='';
    Object.defineProperty(node,'innerHTML',{get(){return markup;},set(value){
      markup=value;
      if(node===nodes.batchFileList) {
        for(const key of Object.keys(nodes)) if(key.startsWith('cvBatchFormattingReview-')) delete nodes[key];
        for(const match of value.matchAll(/id="([^"]+)"/g)) nodes[match[1]]=element();
      }
    }});
    return node;
  }
  const core=['batchFileList','batchFileInput','batchControls','btnBatchRun','btnBatchDownload',
    'batchTotalCost','batchSummary','batchTimer','batchTabFormat','batchTabBlind','batchSummaryToggle','cvInput'];
  core.forEach(id=>nodes[id]=element());
  const c={console,String,Object,Array,JSON,Math,Date,Promise,Blob,ArrayBuffer,
    window:{_jaToken:options.noToken?'':'synthetic',_jaAutoUpload:!options.autoUploadOff},
    document:{getElementById:id=>nodes[id]||null,createElement:element,addEventListener(){}},
    FormData:class {append(key,value){this[key]=value;}},
    setInterval:()=>1,clearInterval(){},setTimeout:()=>1,clearTimeout(){},
    getCvFormattingReview:()=>options.on===true,
    getCvAutoCorrectLanguage:()=>false,getCvBlindCandidateGenderNeutralization:()=>false,
    getCvTextAlignment:()=>options.alignment||'left',getCvSummaryBoxAutoFit:()=>options.autofit!==false,
    getCvSummaryDetailPreference:()=> 'concise',
    aiRoutePayload:feature=>({api_key:'synthetic',api_key_slot:feature,model:feature+'-model',provider:'deepseek',provider_label:'Mock'}),
    cvParseTimeoutMs:()=>1000,cvParseIsLong:()=>false,CV_EXTRACT_TEXT_TIMEOUT_MS:1000,
    cvRequireCompleteExtraction(){},cvMergeLevelLists:(a,b)=>(a||[]).concat(b||[]),
    normalizeUsageClient:()=>({api_calls:0}),mergeUsageClient:(a,b)=>({api_calls:(a.api_calls||0)+(b.api_calls||0)}),
    responseCost:data=>data.cost||0,statsMetaFromResponse:data=>data,
    statsRecord(...args){stats.push(args);return stats.length;},recordPaidAiFailure(...args){stats.push(['failed',...args]);},
    normalizeAiProviderError:text=>text,cvJoinWarnings:(a,b)=>[a,b].filter(Boolean).join(' '),cvSummaryPayNote:()=> '',
    extractNameFromFilename:()=> '',toTitleCase:text=>text,
    esc:text=>String(text||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
    escAttr:text=>String(text||'').replaceAll('"','&quot;'),
    showToast(){},markTabRunning:()=>1,markTabDone(){},markTabFailed(){},clearTabRunState(){},
    cvStudioSaveDownloadBlob:async(blob,name)=>{downloads.push({blob,name});return {};},cvStudioShowDownloadResult(){},
    cvStudioPrepareDownloadDestination:async()=>({handle:{},configured:true,directoryName:'Synthetic'}),
    batchUploadToJobAdder:async(blob,name,email,data)=>{uploads.push({blob,data:clone(data)});return options.realUpload?'candidate-'+uploads.length:'';},
    jaProfileUrlAsync:async id=>'https://example.invalid/candidates/'+id+'?tab=3',
    statsAttachJobAdderUrl:(...args)=>links.push(args),
    jaSafeTenantLabel:()=>'',ppcSetConnected(){},updateJACreateConnStatus(){},
    fetchWithTimeout:async(url,init)=>{
      const body=url==='/extract-text'?init.body:JSON.parse(init.body);
      calls.push({url,body});
      if(url==='/extract-text')return {json:async()=>({text:body.file.source,bullet_levels:[body.file.level]})};
      if(url==='/parse'||url==='/blind'){
        const file=c._batchFiles.find(bf=>bf.file.source===body.cv_text)||c._batchFiles.find(bf=>bf.status==='processing');
        const data=clone(file.fixture);
        return {ok:true,json:async()=>({data,cost:1,usage:{api_calls:1},bullet_levels:[2]})};
      }
      if(url==='/generate-docx'){
        if(body.format_review_applied&&options.exportDelay)await options.exportDelay.promise;
        if(body.format_review_applied&&options.exportFail)return {ok:false};
        const blob={data:clone(body.data), serial:calls.length};
        return {ok:true,blob:async()=>blob,headers:{get:name=>name==='X-CV-Format-Review-Applied'&&body.format_review_applied&&!options.noProof?'1':null}};
      }
      if(body.feature==='cv_format_review_apply'){
        if(options.applyDelay)await options.applyDelay.promise;
        const data=clone(body.cv_data);
        data.work_experiences[0].roles[0].title='Manager';
        return {ok:true,text:async()=>JSON.stringify({data,format_review_applied:{signature:'synthetic'}})};
      }
      if(options.reviewDelay)await options.reviewDelay.promise;
      if(options.failReview)throw new Error('Provider unavailable');
      if(options.malformedReview)return {ok:true,text:async()=>JSON.stringify({cost:2,usage:{api_calls:1}})};
      return {ok:true,text:async()=>JSON.stringify({cost:2,usage:{api_calls:1},format_review_base:clone(body.cv_data),
        format_review:{status:options.unavailable?'unavailable':'reviewed',message:'Checked <img src=x onerror=alert(1)>',
          signature:'synthetic',issues:options.clean?[]:[{id:'1',message:'Title <script>unsafe</script>',
            source_quote:body.source_cv_text,can_apply:true,
            operation:{op:'replace',path:'/work_experiences/0/roles/0/title',before:'Analyst',value:'Manager'}}]}})};
    }};
  vm.createContext(c);vm.runInContext(sources,c);
  const jaSource=fs.readFileSync(path.join(root,'vendor/cvstudio/jobadder-upload.js'),'utf8');
  vm.runInContext(jaSource.slice(jaSource.indexOf('function renderJAConnectionState('),
    jaSource.indexOf('function openJobAdderSettings(')),c);
  if(!options.realUpload)c.batchAutoUploadFile=async(bf,blob,name,data)=>{uploads.push({id:bf.id,blob,data:clone(data)});};
  for(const [index,name] of ['One','Two'].entries()){
    const file={name:'same.txt',source:name+' | Manager\nBuilt reports.',level:index+3,arrayBuffer:async()=>new ArrayBuffer(0)};
    const fixture={candidate:{name:'Synthetic Candidate'},work_experiences:[{company:name,roles:[{title:'Analyst',bullets:['Built reports.']}]}],
      education:[],skills:[],certifications:[]};
    c._batchFiles.push({id:'bf_'+index,file,fixture,status:'pending',cvData:null,cost:0});
  }
  return {c,nodes,calls,stats,uploads,downloads,links,options};
}
const reviewCalls=h=>h.calls.filter(call=>call.body.feature==='cv_format_review');
async function run(){
  // Exercise the real login/poll callback, not just the connection renderer:
  // it must reveal held rows without uploading or rebuilding their files.
  for(const {warning=false,failed=false} of [{},{warning:true},{failed:true}]){
    const f=harness({realUpload:true,noToken:true,on:warning,autoUploadOff:true});
    f.c._batchFiles.forEach(row=>row.fixture.candidate.email='synthetic@example.invalid');
    await f.c.runBatch();
    const rows=f.c._batchFiles.map(row=>({row,blob:row._docxBlob,data:row.cvData,held:row._jaHeld}));
    let poll,closed=0,attempts=0,renders=0;
    const render=f.c.renderBatchList;f.c.renderBatchList=()=>{renders++;render();};
    const fetchWithTimeout=f.c.fetchWithTimeout;
    f.c.fetchWithTimeout=async(url,init)=>{
      if(url==='/jobadder/store_creds')return {ok:true,json:async()=>({login_session_id:'synthetic-session',state:'synthetic-state'})};
      if(url==='/jobadder/poll_token'){
        attempts++;
        if(attempts===1)return {status:202};
        if(failed)return {ok:false,status:401,json:async()=>({error:'Synthetic login rejected'})};
        return {ok:true,status:200,json:async()=>({connected:true})};
      }
      return fetchWithTimeout(url,init);
    };
    Object.assign(f.c,{URLSearchParams,JA_AUTH_URL:'https://example.invalid/authorize',
      JA_REDIRECT_URI:'https://example.invalid/callback',JA_SCOPES:'synthetic',
      getJAClientId:()=> 'synthetic-client',getJAClientSecret:()=> '',hasJASavedSecretFor:()=>true,
      applyJAPublicInfo(){},localStorage:{setItem(){},removeItem(){}},
      fetch:async()=>({json:async()=>({items:[]})}),
      refreshIntegrationDiagnostics:()=>f.c.renderJAConnectionState({connected:true}),
      setInterval:callback=>{poll=callback;return 1;}});
    f.c.window.open=()=>({close(){closed++;}});
    const jaSource=fs.readFileSync(path.join(root,'vendor/cvstudio/jobadder-upload.js'),'utf8');
    vm.runInContext(jaSource.slice(jaSource.indexOf('async function jobAdderLogin('),
      jaSource.indexOf('function clearJALocalAccountState(')),f.c);
    await f.c.jobAdderLogin();assert.strictEqual(typeof poll,'function');
    await poll();assert.strictEqual(!!f.c.window._jaToken,false);
    assert.strictEqual(renders,0,'pending login cannot expose upload controls');
    await poll();
    if(failed){
      assert.strictEqual(!!f.c.window._jaToken,false);
      assert.strictEqual(closed,1);
      assert.strictEqual(renders,0,'rejected login cannot reveal upload controls');
      assert.ok(!f.nodes.batchFileList.innerHTML.includes('uploadHeldBatchFile'));
      assert.strictEqual(f.uploads.length,0);
      continue;
    }
    assert.strictEqual(f.c.window._jaToken,true);
    assert.strictEqual(closed,1);
    assert.strictEqual(renders,1,'successful OAuth refreshes held rows exactly once');
    assert.ok(!f.nodes.batchFileList.innerHTML.includes('connect to JobAdder'));
    assert.ok(f.nodes.batchFileList.innerHTML.includes(warning?'Upload anyway':'Upload to JobAdder'));
    assert.strictEqual(f.uploads.length,0,'connecting never replays held uploads');
    assert.strictEqual(f.c.window._jaAutoUpload,false,'connecting preserves auto-upload preference');
    for(const previous of rows){
      assert.strictEqual(previous.row._docxBlob,previous.blob);
      assert.strictEqual(previous.row.cvData,previous.data);
      assert.strictEqual(previous.row._jaHeld,previous.held);
    }
    f.c.renderJAConnectionState({connected:true});
    assert.strictEqual(renders,1,'unchanged status refreshes must not reset row inputs');
    f.c.renderJAConnectionState({connected:false});
    assert.ok(!f.nodes.batchFileList.innerHTML.includes('uploadHeldBatchFile'));
    assert.strictEqual(f.uploads.length,0,'disconnecting never uploads');
  }
  // A skipped upload must stay visible and actionable, rather than losing
  // both the candidate link and the way to upload a completed batch CV.
  for(const options of [{autoUploadOff:true},{noToken:true}]){
    const f=harness({...options,realUpload:true});
    f.c._batchFiles.forEach(row=>row.fixture.candidate.email='synthetic@example.invalid');
    await f.c.runBatch();
    assert.strictEqual(f.uploads.length,0,'skipped automatic uploads make no remote writes');
    assert.ok(f.c._batchFiles.every(row=>row.jaStatus&&row._jaHeld),
      'each finished row explains why it has no JobAdder link and retains its upload');
    assert.ok(f.nodes.batchFileList.innerHTML.includes(options.noToken?'connect to JobAdder':'auto-upload is off'));
    if(options.noToken){
      assert.ok(!f.nodes.batchFileList.innerHTML.includes('uploadHeldBatchFile'));
      await f.c.uploadHeldBatchFile('bf_0');assert.strictEqual(f.uploads.length,0);
      f.c.renderJAConnectionState({connected:true});
      assert.ok(!f.nodes.batchFileList.innerHTML.includes('connect to JobAdder'),
        'connecting refreshes completed rows without reformatting or auto-uploading');
      assert.strictEqual(f.uploads.length,0);
    }
    assert.ok(f.nodes.batchFileList.innerHTML.includes('Upload to JobAdder'));
    const [first,second]=f.c._batchFiles;
    await f.c.uploadHeldBatchFile(first.id);
    assert.strictEqual(f.uploads[0].blob,first._docxBlob);
    assert.ok(first.jaStatus.includes('/candidates/candidate-1?tab=3'));
    assert.ok(!second.jaStatus.includes('/candidates/'),'duplicate filenames cannot borrow another row\'s link');
    f.c.renderBatchList();assert.ok(f.nodes.batchFileList.innerHTML.includes('/candidates/candidate-1?tab=3'));
    assert.strictEqual(f.links[0][0],first._statsRecordId,'dashboard URL belongs to this exact record');
    await f.c.uploadHeldBatchFile(first.id);assert.strictEqual(f.uploads.length,1,'no automatic replay');
    await f.c.uploadHeldBatchFile(second.id);
    assert.ok(second.jaStatus.includes('/candidates/candidate-2?tab=3'));
    assert.strictEqual(f.links[1][0],second._statsRecordId);
  }
  {
    const f=harness({realUpload:true});
    f.c._batchFiles.forEach(row=>row.fixture.candidate.email='synthetic@example.invalid');
    await f.c.runBatch();assert.strictEqual(f.uploads.length,2,'connected auto-upload still works');
    assert.ok(f.c._batchFiles.every(row=>row.jaStatus.includes('/candidates/')));
    assert.strictEqual(f.links.length,2);
  }
  {
    const f=harness({realUpload:true,autoUploadOff:true});await f.c.runBatch();
    const row=f.c._batchFiles[0];
    await f.c.uploadHeldBatchFile(row.id);
    assert.ok(f.nodes.batchFileList.innerHTML.includes('Enter email for JobAdder'));
    assert.strictEqual(f.uploads.length,0,'a missing email never starts an upload');
    f.c.setBatchManualEmail({value:'synthetic@example.invalid'},row.id);
    for(let i=0;i<20&&!row.jaStatus.includes('/candidates/');i++)await Promise.resolve();
    assert.strictEqual(f.uploads.length,1);
    assert.ok(row.jaStatus.includes('/candidates/candidate-1?tab=3'));
    assert.strictEqual(f.links[0][0],row._statsRecordId);
  }
  // Red first: the enabled real batch must review every completed normal CV.
  const first=harness({on:true});await first.c.runBatch();
  assert.strictEqual(reviewCalls(first).length,2,'one extra review for each batch CV');
  for(const mode of ['off','blind']){
    const h=harness({on:mode==='blind'});if(mode==='blind')h.c.setBatchMode('blind');
    await h.c.runBatch();assert.strictEqual(reviewCalls(h).length,0,'off/Blind incur no review call');
    assert.strictEqual(h.uploads.length,2,'existing auto-upload flow remains');
  }
  const h=first;
  assert.strictEqual(h.uploads.length,0,'findings hold automatic uploads');
  for(const bf of h.c._batchFiles){
    assert.strictEqual(bf.status,'done-ok');assert.strictEqual(bf.cost,3);
    assert.strictEqual(bf.cvData.work_experiences[0].roles[0].title,'Analyst','review never auto-applies');
    assert.ok(bf._jaHeld&&bf.parseWarning);
    const panel=h.nodes['cvBatchFormattingReview-'+bf.id];
    assert.ok(panel,'review belongs to the file row');
    assert.ok(descendants(panel).some(node=>node.textContent.includes('<script>')));
    assert.ok(descendants(panel).some(node=>node.textContent==='Apply fix'));
    assert.ok(descendants(panel).some(node=>node.textContent==='Apply fix'&&!node.disabled),
      'finishing the batch enables manual Apply buttons without needing a second render');
  }
  assert.ok(reviewCalls(h).every(call=>call.body.api_key_slot==='cv_batch'),'use the Batch provider route');
  const [a,b]=h.c._batchFiles,originalBlob=a._docxBlob,otherBlob=b._docxBlob;
  assert.strictEqual(a.filename,b.filename,'duplicate output filenames exercise row identity');
  h.options.alignment='justify';h.options.autofit=false;
  await h.c.batchApplyFormattingReview(a.id,'1');
  assert.strictEqual(a.cvData.work_experiences[0].roles[0].title,'Manager');
  assert.strictEqual(b._docxBlob,otherBlob,'same filenames cannot cross-apply another row');
  assert.strictEqual(h.c._batchBlobs.find(item=>item.id===a.id).blob,a._docxBlob,'Download All receives corrected file');
  assert.strictEqual(a._jaHeld.blob,a._docxBlob,'held manual upload uses corrected file');
  assert.strictEqual(a._jaHeld.cvData,a.cvData);
  assert.strictEqual(h.uploads.length,0,'apply never automatically uploads');
  assert.strictEqual(a.cost,3,'apply/export make no paid AI call');
  const correctedExport=h.calls.find(call=>call.url==='/generate-docx'&&call.body.format_review_applied).body;
  assert.strictEqual(correctedExport.alignment,'left','correction preserves the original output alignment');
  assert.strictEqual(correctedExport.summary_box_autofit,true,'correction preserves the original summary box setting');
  assert.deepStrictEqual(Array.from(correctedExport.bullet_levels),[3,2],'correction uses this row\'s captured bullet levels');
  await h.c.downloadSingleBatchFile(a.id);
  assert.strictEqual(h.downloads[0].blob,a._docxBlob);
  h.c.batchUndoFormattingReview(a.id);
  assert.strictEqual(a._docxBlob,originalBlob);
  assert.strictEqual(h.c._batchBlobs.find(item=>item.id===a.id).blob,originalBlob);
  assert.strictEqual(a.cvData.work_experiences[0].roles[0].title,'Analyst');
  assert.strictEqual(a._jaHeld.blob,originalBlob);
  assert.strictEqual(b._docxBlob,otherBlob);
  await h.c.batchCheckFormattingReviewAgain(a.id);
  assert.strictEqual(a.cost,5);assert.strictEqual(b.cost,3);
  assert.strictEqual(h.stats.filter(row=>row[1]==='format_review').length,1);
  assert.ok(h.nodes.batchTotalCost.textContent.includes('$8.0000'));
  await h.c.uploadHeldBatchFile(a.id);
  assert.strictEqual(h.uploads[0].blob,originalBlob,'manual upload receives current Undo result');
  for(const option of ['failReview','unavailable','malformedReview']){
    const f=harness({on:true,[option]:true});await f.c.runBatch();
    assert.strictEqual(reviewCalls(f).length,2,'failure/unavailable does not retry or stop later files');
    assert.ok(f.c._batchFiles.every(bf=>bf.status==='done-ok'&&bf._docxBlob&&bf._jaHeld));
    assert.strictEqual(f.uploads.length,0);
    if(option!=='failReview')assert.ok(f.c._batchFiles.every(bf=>bf.cost===3),'completed unusable paid checks remain in totals');
  }
  const clean=harness({on:true,clean:true});await clean.c.runBatch();
  assert.strictEqual(clean.uploads.length,2,'clean review preserves automatic upload');
  for(const option of ['exportFail','noProof']){
    const f=harness({on:true,[option]:true});await f.c.runBatch();const row=f.c._batchFiles[0],blob=row._docxBlob;
    await f.c.batchApplyFormattingReview(row.id,'1');
    assert.strictEqual(row._docxBlob,blob);assert.strictEqual(row.cvData.work_experiences[0].roles[0].title,'Analyst');
    assert.strictEqual(row._jaHeld.blob,blob);assert.strictEqual(f.c._batchBlobs[0].blob,blob);
  }
  {
    const f=harness({on:true});await f.c.runBatch();const row=f.c._batchFiles[0],blob=row._docxBlob;
    const render=f.c.renderBatchList;
    f.c.renderBatchList=()=>{if(row.cvData.work_experiences[0].roles[0].title==='Manager')throw new Error('Render failed');render();};
    await f.c.batchApplyFormattingReview(row.id,'1');
    assert.strictEqual(row._docxBlob,blob,'render failure rolls back the file, row and upload pair');
    assert.strictEqual(row._jaHeld.blob,blob);assert.strictEqual(f.c._batchBlobs[0].blob,blob);
  }
  {
    const delay=deferred(),f=harness({on:true,reviewDelay:delay});const formatting=f.c.runBatch();
    while(!reviewCalls(f).length)await Promise.resolve();
    f.options.on=false;delay.release();await formatting;
    assert.strictEqual(reviewCalls(f).length,2,'capture setting once for a consistent batch');
  }
  {
    const delay=deferred(),f=harness({on:true,reviewDelay:delay});const formatting=f.c.runBatch();
    while(!reviewCalls(f).length)await Promise.resolve();
    f.c._batchFiles[0]._reviewSource='Changed during the review';delay.release();await formatting;
    assert.strictEqual(f.uploads.length,0,'a stale initial review must not enable automatic upload');
    assert.ok(f.c._batchFiles[0].parseWarning&&f.c._batchFiles[0]._jaHeld);
    assert.strictEqual(f.stats.filter(row=>row[1]==='format_review').length,1,'the stale paid check remains accounted');
  }
  {
    const f=harness({on:true});await f.c.runBatch();const row=f.c._batchFiles[0],blob=row._docxBlob;
    f.options.applyDelay=deferred();const applying=f.c.batchApplyFormattingReview(row.id,'1');
    await Promise.resolve();
    await f.c.uploadHeldBatchFile(row.id);await f.c.downloadSingleBatchFile(row.id);
    await f.c.downloadBatchZip();
    f.c.setBatchManualEmail({value:'synthetic@example.test'},row.id);
    assert.strictEqual(f.uploads.length,0,'busy correction cannot upload stale content');
    assert.strictEqual(f.downloads.length,0,'busy correction cannot download stale content');
    assert.strictEqual(row._manualEmail,undefined,'email entry cannot bypass the upload hold while busy');
    const count=f.calls.length;await f.c.batchCheckFormattingReviewAgain(f.c._batchFiles[1].id);
    assert.strictEqual(f.calls.length,count,'overlapping manual reviews do not spend again');
    f.c.removeBatchFile(row.id);f.options.applyDelay.release();await applying;
    assert.strictEqual(f.c._batchFiles.length,1);
    assert.ok(f.c._batchBlobs.every(item=>item.id!==row.id),'late apply cannot recreate a removed row');
    assert.strictEqual(row._docxBlob,blob);
  }
  {
    const f=harness({on:true});await f.c.runBatch();const row=f.c._batchFiles[0];
    f.options.reviewDelay=deferred();const checking=f.c.batchCheckFormattingReviewAgain(row.id);
    await Promise.resolve();f.c.clearBatch();f.options.reviewDelay.release();await checking;
    assert.strictEqual(f.c._batchFiles.length,0);
    assert.strictEqual(f.c._batchBlobs.length,0);
    assert.strictEqual(f.stats.filter(record=>record[1]==='format_review').length,1,'completed stale paid review stays in history');
    assert.strictEqual(f.nodes.btnBatchDownload.disabled,true);
  }
  {
    const f=harness({on:true});await f.c.runBatch();const row=f.c._batchFiles[0];
    row._reviewSource='Different source';const count=f.calls.length;
    await f.c.batchApplyFormattingReview(row.id,'1');
    assert.strictEqual(f.calls.length,count,'changed source cannot receive an old suggestion');
  }
  {
    const f=harness({on:true});await f.c.runBatch();const row=f.c._batchFiles[0];
    row.jaClass='show uploading';const count=f.calls.length;
    await f.c.batchApplyFormattingReview(row.id,'1');await f.c.batchCheckFormattingReviewAgain(row.id);
    assert.strictEqual(f.calls.length,count,'an active JobAdder upload locks its output against review changes');
  }
  {
    const f=harness({on:true});await f.c.runBatch();const row=f.c._batchFiles[0],blob=row._docxBlob;
    f.options.exportDelay=deferred();const applying=f.c.batchApplyFormattingReview(row.id,'1');
    while(!f.calls.some(call=>call.url==='/generate-docx'&&call.body.format_review_applied))await Promise.resolve();
    row._reviewSource='Changed while rebuilding';f.options.exportDelay.release();await applying;
    assert.strictEqual(row._docxBlob,blob,'source changing during Word generation cannot publish the old correction');
    assert.strictEqual(row._jaHeld.blob,blob);assert.strictEqual(f.c._batchBlobs[0].blob,blob);
  }
  {
    const f=harness({on:true});await f.c.runBatch();
    f.c._batchFiles[1].id=f.c._batchFiles[0].id;f.c._batchBlobs[1].id=f.c._batchBlobs[0].id;
    const count=f.calls.length;await f.c.batchApplyFormattingReview(f.c._batchFiles[0].id,'1');
    assert.strictEqual(f.calls.length,count,'an ambiguous row ID must not choose a CV to change');
  }
  console.log('Batch AI review: opt-in/Blind, per-row routing/cost/quotes, apply/undo, downloads/uploads, failures and stale work passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
