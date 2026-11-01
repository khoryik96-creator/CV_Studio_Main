const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
class Element {
  constructor(tagName='div',textContent=''){Object.assign(this,{tagName,textContent,value:'',children:[],handlers:{},disabled:false,checked:false,hidden:false,dataset:{}})}
  addEventListener(type,fn){this.handlers[type]=fn} append(...values){this.children.push(...values)}
  appendChild(value){this.children.push(value);return value} replaceChildren(...values){this.children=values}
  setAttribute(name,value){this[name]=value} focus(){} scrollIntoView(){}
  showModal(){this.open=true} close(){this.open=false}
  querySelectorAll(tag){return this.children.flatMap(child=>[...(child.tagName===tag?[child]:[]),...child.querySelectorAll(tag)])}
  click(){return this.handlers.click?.()} get selectedOptions(){return this.children.filter(row=>row.value===this.value)}
}
const job=(number,patch={})=>({url:'https://www.linkedin.com/jobs/view/'+number,company:'Example Finance',role:'Finance Manager',location:'Penang',date_posted:'2026-10-02',description:'Search summary '+number,contact:'Never copy',notes:'Never copy',status:'won',...patch});
const a=job('1111111110'),b=job('1111111111'),c=job('1111111112');
function fixture(options={}){
  const ids=new Map(),events={},calls=[],requests=[];
  const document={getElementById:id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)},createElement:tag=>new Element(tag),createTextNode:text=>new Element('#text',text),addEventListener:(name,fn)=>events[name]=fn};
  const el=name=>document.getElementById('jobLeads'+name),location={origin:'http://127.0.0.1:5000',search:''};
  el('FolderFilter').value='*';el('SearchPages').value='2';el('SearchMode').value='new';el('SearchQuery').value='finance';el('SearchLocation').value='Malaysia';
  let serial=0;
  const state={page:0,scroll:0,totalPages:2,hold:false,held:null,failSave:'',failRead:false,many:false,connected:true,searchCapable:true,searchRevision:1,busy:false,
    folders:['Priority'],records:[{...b,id:'e'.repeat(32),revision:2,contact:'Manual Contact',notes:'Important saved notes',status:'contacted',description:'Saved full content',created_at:'2026-10-01T00:00:00Z',folder:'',deleted:false,follow_up:''}]};
  const window={addEventListener:(name,fn)=>events[name]=fn,confirm:()=>state.allowDiscard!==false,postMessage:message=>{
    if(message.type==='CVSTUDIO_LINKEDIN_CAPTURE_RESULT'){state.captureReply?.(message.result);state.captureReply=null;return}
    calls.push(message);const reply=(value,error)=>events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',id:message.id,channel:message.channel,...(error?typeof error==='object'?{error:error.message,error_code:error.code,...(error.companyURL?{company_url:error.companyURL}:{})}:{error}:{result:value})}});
    if(state.onRPC?.(message,reply))return;
    if(message.action==='jobStatus')return reply({connected:state.connected,job_search:state.searchCapable,job_search_revision:state.searchRevision,concurrent_scans_revision:state.oldConcurrent?0:1,version:'24.6.461',busy:state.busy});
    if(message.action==='jobSearchTabs')return reply([{id:20,title:'Open filtered jobs',url:'https://www.linkedin.com/jobs/search/?keywords=finance&f_WT=2'}]);
    if(message.action==='jobSearchBegin'){state.page=0;state.scroll=0;return reply({tab_id:20})}
    if(message.action==='end')return reply(true);
    if(message.action==='jobFromLink')return state.failRead?reply(null,'Synthetic layout changed'):reply({...c,url:message.args.url,description:'Full captured job ad',description_html:'<p><b>Full captured job ad</b></p>'});
    if(message.action==='read'){
      if(message.args.method==='nextJobSearch'){state.page++;state.scroll=0;return reply(true)}
      if(message.args.method==='scrollJobSearch'){state.scroll++;return reply(true)}
      const jobs=state.many?Array.from({length:state.pageSize||1},(_,index)=>job(String(2222222200+state.page*(state.pageSize||1)+index),{role:'Found role '+index})):state.page===0?state.scroll?[a,b]:[a]:[b,c,job('999',{url:'https://attacker.invalid/jobs/view/999'})];
      const snapshot={jobs,signature:jobs.map(row=>row.url).join('|'),hasNext:state.page+1<state.totalPages,atBottom:state.many||state.page>0||!!state.scroll};
      if(state.hold&&state.page===1){state.held=()=>reply(snapshot);return}
      return reply(snapshot);
    }
    throw Error('Unexpected companion command '+message.action);
  }};
  const fetch=async(endpoint,options)=>{
    if(endpoint==='/jobadder/contact_actions'){assert(state.onJA,'JobAdder contacts require an explicit fictional fixture');return state.onJA(JSON.parse(options.body));}
    if(endpoint==='/apollo') {
      assert(state.onApollo,'Apollo calls require an explicit test fixture');
      return state.onApollo(options?.body?JSON.parse(options.body):null);
    }
    if(endpoint==='/email-verifier') {assert(state.onVerify,'Mail checks require an explicit fixture');return state.onVerify(JSON.parse(options.body));}
    assert.equal(endpoint,'/job-leads','search must not call a paid route');
    if(!options?.body)return {ok:true,json:async()=>({records:structuredClone(state.records),folders:[...state.folders]})};
    const data=JSON.parse(options.body);requests.push(data);
    if(state.onRequest){const response=await state.onRequest(data);if(response)return response;}
    if(data.action==='format_content')return {ok:true,json:async()=>({description_rich:[{tag:'p',children:[{tag:'strong',children:[{text:data.description}]}]}]})};
    if(data.action==='create_folder'){if(!data.folder?.trim())return {ok:false,json:async()=>({error:'Enter a folder name.'})};if(!state.folders.includes(data.folder))state.folders.push(data.folder);return {ok:true,json:async()=>({folder:data.folder})};}
    if(['trash','untrash','move_folder'].includes(data.action)){
      if(data.action==='trash'&&state.failTrash)return {ok:false,json:async()=>({error:'Synthetic stale ad revision'})};
      if(data.action==='move_folder'&&state.failMove)return {ok:false,json:async()=>({error:'Synthetic folder move failure'})};
      for(const selected of data.records){const row=state.records.find(row=>row.id===selected.id);assert.equal(row.revision,selected.revision);if(data.action==='move_folder')row.folder=data.folder;else row.deleted=data.action==='trash';row.revision++;}
      return {ok:true,json:async()=>({changed:data.records.length})};
    }
    assert.equal(data.action,'save');
    if(data.record.url===state.failSave)return {ok:false,json:async()=>({error:'Synthetic storage limit'})};
    if(state.beforeSave){state.records.push(state.beforeSave);state.beforeSave=null;}
    const duplicate=state.records.find(row=>row.url===data.record.url);
    if(duplicate)return {ok:true,json:async()=>({record:duplicate,duplicate:true})};
    const record={...data.record,id:String(++serial).padStart(32,'0'),revision:1,created_at:'2026-10-20T00:00:00Z',deleted:false};
    state.records.push(record);return {ok:true,json:async()=>({record,duplicate:false})};
  };
  const preferences=options.preferences || new Map();
  const localStorage=options.storage || {getItem:key=>preferences.get(key)??null,setItem:(key,value)=>preferences.set(key,value),removeItem:key=>preferences.delete(key)};
  const context=vm.createContext({window,document,location,localStorage,fetch,URL,URLSearchParams,Blob,Map,Set,Date,crypto:{randomUUID:()=>String(++serial).padStart(32,'0')},
    ...options.activity,
    navigator:{clipboard:{writeText:async value=>{state.clipboard=value}}},
    setTimeout:(fn,ms)=>setTimeout(fn,ms===350?0:ms),clearTimeout,Option:function(text,value){const node=new Element('option',text);node.value=value;return node}});
  if(options.emailVerifier) vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/email-verifier.js'),'utf8'),context);
  if(options.jobAdderContacts)vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-leads-jobadder.js'),'utf8'),context);
  if(options.apollo) {
    window.open=()=>{state.popup={location:{},close(){state.popupClosed=true}};return state.popup};
    vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-leads-apollo.js'),'utf8'),context);
  }
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-search-walk.js'),'utf8'),context);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-leads.js'),'utf8'),context);
  return {el,state,calls,requests,apollo:window.cvStudioApollo,pagehide:()=>events.pagehide?.(),init:()=>window.initJobLeads(),capture:(record,request)=>new Promise(resolve=>{
    state.captureReply=resolve;events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_CAPTURE',channel:document.getElementById('viewJobLeads').dataset.companionChannel,id:String(++serial).padStart(32,'0'),record,request}});
  })};
}
module.exports={fixture};
if(require.main===module)(async()=>{
  const f=fixture();await f.init();
  assert.equal(f.el('PreviewTitle').textContent,b.role,'a saved ad fills the preview after reload without repeating the search');
  assert(f.el('PreviewContent').querySelectorAll('#text').some(node=>node.textContent==='Saved full content'));
  assert.equal(f.el('PreviewSave').textContent,'Already saved');
  const folderPreview=fixture();await folderPreview.init();
  folderPreview.el('notes').value='Keep my draft';folderPreview.el('notes').handlers.input();
  const folderRecords=structuredClone(folderPreview.state.records);
  folderPreview.el('FolderName').value='Empty folder';await folderPreview.el('FolderCreate').click();
  assert.equal(folderPreview.el('FolderFilter').value,'Empty folder');assert.equal(folderPreview.el('Count').textContent,'0 leads');
  assert(folderPreview.el('Preview').hidden,'creating an empty folder clears the previous folder preview');
  assert.equal(folderPreview.el('PreviewPosition').textContent,'');assert(folderPreview.el('PreviewRemove').hidden);
  assert(folderPreview.el('PreviewPrevious').disabled);assert(folderPreview.el('PreviewNext').disabled);
  assert.equal(folderPreview.el('notes').value,'Keep my draft');assert.deepEqual(folderPreview.state.records,folderRecords);
  assert.deepEqual(folderPreview.requests.map(request=>request.action),['create_folder'],'folder selection never removes or updates ads');
  const existingFolder=fixture();const folderBase=structuredClone(existingFolder.state.records[0]);
  existingFolder.state.records.push({...folderBase,id:'c'.repeat(32),url:c.url,role:'Priority architect',folder:'Priority'},
    {...folderBase,id:'a'.repeat(32),url:a.url,role:'Priority manager',folder:'Priority'});
  await existingFolder.init();existingFolder.el('FolderName').value='Priority';await existingFolder.el('FolderCreate').click();
  assert.equal(existingFolder.el('PreviewTitle').textContent,'Priority architect');assert.match(existingFolder.el('PreviewPosition').textContent,/1 of 2/);
  await existingFolder.el('PreviewNext').click();assert.equal(existingFolder.el('PreviewTitle').textContent,'Priority manager');
  await existingFolder.el('PreviewClose').click();existingFolder.el('FolderName').value='Priority';await existingFolder.el('FolderCreate').click();
  assert(existingFolder.el('Preview').hidden,'folder creation respects a dismissed preview');
  const searchFolder=fixture();await searchFolder.init();await searchFolder.el('SearchStart').click();
  searchFolder.el('SearchSelectPage').checked=true;searchFolder.el('SearchSelectPage').handlers.change();
  const searchPosition=searchFolder.el('PreviewPosition').textContent;
  searchFolder.el('FolderName').value='Search shortlist';await searchFolder.el('FolderCreate').click();
  assert.equal(searchFolder.el('PreviewPosition').textContent,searchPosition,'saved folder changes preserve search preview context');
  assert.match(searchFolder.el('SearchCount').textContent,/2 selected/);
  const browse=fixture();
  const savedBase=structuredClone(browse.state.records[0]);
  browse.state.records=[{...savedBase,folder:'Priority'},
    {...savedBase,url:c.url,id:'c'.repeat(32),role:'Cloud Architect',folder:'Priority'},
    {...savedBase,url:a.url,id:'a'.repeat(32),role:'Finance Lead',folder:'Other'}];
  await browse.init();
  assert.match(browse.el('PreviewPosition').textContent,/Saved ads.*1 of 3/);
  assert(browse.el('PreviewPrevious').disabled);assert(!browse.el('PreviewNext').disabled);
  assert(browse.el('SearchPagination').hidden,'empty search pagination is hidden while browsing saved ads');
  await browse.el('PreviewNext').click();assert.equal(browse.el('PreviewTitle').textContent,'Cloud Architect');
  await browse.el('PreviewPrevious').click();assert.equal(browse.el('PreviewTitle').textContent,b.role);
  await browse.el('PreviewNext').click();await browse.el('PreviewNext').click();
  assert.equal(browse.el('PreviewTitle').textContent,'Finance Lead');assert(browse.el('PreviewNext').disabled);
  assert.equal(browse.requests.length,0,'browsing saved previews never writes records');
  await browse.el('PreviewClose').click();assert(browse.el('Preview').hidden);
  await browse.el('Refresh').click();assert(browse.el('Preview').hidden,'refresh does not reopen a dismissed preview');
  await browse.el('List').children[0].querySelectorAll('button').find(button=>button.textContent==='Preview').click();
  browse.el('FolderFilter').value='Priority';browse.el('FolderFilter').handlers.change();
  assert.match(browse.el('PreviewPosition').textContent,/1 of 2/);await browse.el('PreviewNext').click();
  assert.equal(browse.el('PreviewTitle').textContent,'Cloud Architect');assert(browse.el('PreviewNext').disabled,'saved navigation respects folder filters');
  browse.state.failTrash=true;await browse.el('PreviewRemove').click();
  assert.equal(browse.el('PreviewTitle').textContent,'Cloud Architect');assert.match(browse.el('Message').textContent,/stale ad revision/);
  assert(!browse.state.records[1].deleted);browse.state.failTrash=false;
  await browse.el('PreviewRemove').click();assert(browse.state.records[1].deleted);
  assert.equal(browse.el('PreviewTitle').textContent,b.role,'removing a saved preview advances to the remaining ad');
  assert.equal(browse.state.records[1].notes,savedBase.notes,'Trash preserves saved notes');
  await browse.el('List').children[0].querySelectorAll('button').find(button=>button.textContent==='Edit / view details').click();
  browse.el('notes').value='Unsaved editing notes';browse.el('notes').handlers.input();browse.state.allowDiscard=false;
  const beforeCancel=browse.requests.length;await browse.el('PreviewRemove').click();
  assert.equal(browse.requests.length,beforeCancel,'cancelled discard prevents removing the edited ad');
  assert.equal(browse.el('notes').value,'Unsaved editing notes');assert(!browse.state.records[0].deleted);
  browse.state.allowDiscard=true;await browse.el('PreviewRemove').click();
  assert(browse.el('Preview').hidden,'removing the last matching ad clears the preview');
  assert(browse.el('PreviewRemove').hidden);assert.equal(browse.state.records[2].deleted,false,'ads outside the chosen folder are unchanged');
  browse.el('FolderFilter').value='!trash';browse.el('FolderFilter').handlers.change();
  await browse.el('List').children[0].querySelectorAll('button').find(button=>button.textContent==='Preview').click();
  assert.equal(browse.el('PreviewRemove').textContent,'Restore ad');await browse.el('PreviewRemove').click();
  assert.equal(browse.state.records[0].deleted,false,'a trashed preview restores through the existing guarded operation');
  assert.equal(browse.state.records[0].notes,savedBase.notes);
  const paging=fixture();paging.state.many=true;paging.state.totalPages=1;paging.state.pageSize=23;
  await paging.init();await paging.el('SearchStart').click();assert.match(paging.el('PreviewPosition').textContent,/Search results.*1 of 23/);
  assert(!paging.el('SearchPagination').hidden);assert(paging.el('PreviewRemove').hidden,'unsaved search ads cannot be trashed as saved records');
  await paging.el('SearchNext').click();assert.equal(paging.el('PreviewTitle').textContent,'Found role 20');
  await paging.el('PreviewPrevious').click();assert.equal(paging.el('PreviewTitle').textContent,'Found role 19');
  assert(!paging.el('SearchNext').disabled,'ad navigation follows its result across results pages');
  await paging.el('PreviewNext').click();assert.equal(paging.el('PreviewTitle').textContent,'Found role 20');
  await paging.el('SearchPrevious').click();assert.equal(paging.el('PreviewTitle').textContent,'Found role 0');
  assert.equal(paging.requests.length,0,'search preview navigation never saves or removes ads');
  const empty=fixture();empty.state.records=[];await empty.init();
  assert(empty.el('Preview').hidden);assert(empty.el('PreviewRead').hidden);assert(empty.el('PreviewSave').hidden);
  const savedPreview=fixture();await savedPreview.init();
  await savedPreview.el('List').querySelectorAll('button').find(button=>button.textContent==='Preview').click();
  assert.equal(savedPreview.el('SearchPanel').open,true);
  savedPreview.el('description').value='Unsaved description';savedPreview.el('notes').value='Unsaved notes';savedPreview.el('notes').handlers.input();
  const beforeSaved=structuredClone(savedPreview.state.records);
  await savedPreview.el('PreviewRead').click();
  assert(savedPreview.el('PreviewContent').querySelectorAll('#text').some(node=>node.textContent==='Full captured job ad'));
  assert.deepEqual(savedPreview.state.records,beforeSaved,'a full preview never overwrites a saved lead');
  assert.deepEqual(savedPreview.requests.map(request=>request.action),['format_content'],'previewing does not issue record writes');
  assert.equal(savedPreview.el('description').value,'Unsaved description');assert.equal(savedPreview.el('notes').value,'Unsaved notes');
  await savedPreview.el('Refresh').click();
  assert(savedPreview.el('PreviewContent').querySelectorAll('#text').some(node=>node.textContent==='Saved full content'),'refresh discards the temporary full read and shows authoritative saved content');
  f.el('url').value='https://www.linkedin.com/jobs/view/7777777777';f.el('company').value='Unsaved company';f.el('role').value='Unsaved role';
  f.el('notes').value='Keep unsaved notes';f.el('contact').value='Unsaved Contact';f.el('notes').handlers.input();
  await f.el('SearchStart').click();assert.match(f.el('SearchCount').textContent,/3 found/);
  assert.equal(f.el('PreviewTitle').textContent,'Finance Manager');
  await f.el('SearchResults').children[2].querySelectorAll('button').find(button=>button.textContent==='Preview').click();
  assert(f.el('PreviewContent').querySelectorAll('#text').some(node=>node.textContent===c.description));
  assert.equal(f.calls.filter(call=>call.args.method==='nextJobSearch').length,1);
  assert.equal(f.calls.filter(call=>call.args.method==='scrollJobSearch').length,1);
  assert.equal(f.requests.length,0,'crawling never saves automatically');
  assert.equal(f.el('notes').value,'Keep unsaved notes');assert.equal(f.el('contact').value,'Unsaved Contact');
  assert(f.el('SearchResults').children[1].children.some(child=>child.querySelectorAll('span').some(item=>item.textContent==='Already saved')));
  const previews=f.el('SearchResults').querySelectorAll('button').filter(button=>button.textContent==='Read full ad');
  f.state.failRead=true;await previews[0].click();assert.match(f.el('SearchStatus').textContent,/summary is still available/);
  f.state.failRead=false;await f.el('SearchResults').querySelectorAll('button').filter(button=>button.textContent==='Read full ad')[2].click();
  assert(f.el('SearchResults').children[2].querySelectorAll('strong').some(item=>item.children.some(child=>child.textContent==='Full captured job ad')));
  f.el('SearchSelectPage').checked=true;f.el('SearchSelectPage').handlers.change();assert.match(f.el('SearchCount').textContent,/2 selected/);
  f.el('SearchFolder').value='Priority';f.state.failSave=c.url;await f.el('SearchAdd').click();
  assert.equal(f.state.records.length,2);assert.match(f.el('SearchStatus').textContent,/Added 1 ads.*Synthetic storage limit/);
  assert.match(f.el('SearchCount').textContent,/1 selected/,'failed/unattempted ads remain selectable');
  f.state.failSave='';await f.el('SearchAdd').click();assert.equal(f.state.records.length,3);
  const original=f.state.records.find(row=>row.url===b.url),added=f.state.records.find(row=>row.url===c.url);
  assert.equal(original.contact,'Manual Contact');assert.equal(original.notes,'Important saved notes');assert.equal(original.status,'contacted');
  assert.equal(added.folder,'Priority');assert.equal(added.status,'new');assert.equal(added.contact,'');assert.equal(added.notes,'');
  assert.equal(added.description,'Full captured job ad');assert.equal(added.description_rich[0].tag,'p');
  assert.equal(f.el('notes').value,'Keep unsaved notes','import does not replace the manual draft');
  await f.el('SearchClear').click();assert.equal(f.state.records.length,3);assert.match(f.el('SearchCount').textContent,/0 found/);
  assert(f.el('Preview').hidden,'Clear results does not silently select an unrelated saved ad');
  const badCalls=f.calls.length;f.el('SearchPages').value='16';await f.el('SearchStart').click();assert.equal(f.calls.length,badCalls);
  f.el('SearchPages').value='2';f.el('SearchMode').value='open';f.el('SearchMode').handlers.change();await f.el('SearchRefresh').click();
  f.el('SearchSource').value='20';f.el('SearchQuery').value='';await f.el('SearchStart').click();
  assert(f.calls.some(call=>call.action==='jobSearchBegin'&&call.args.use_open&&call.args.source_tab_id===20));
  for(const patch of [{connected:false},{searchCapable:false},{searchRevision:undefined},{searchRevision:0},{searchRevision:'1'},{oldConcurrent:true},{busy:true}]){
    Object.assign(f.state,{connected:true,searchCapable:true,searchRevision:1,oldConcurrent:false,busy:false},patch);
    const before=f.calls.length;await f.el('SearchStart').click();
    assert.deepEqual(f.calls.slice(before).map(call=>call.action),['jobStatus'],'unavailable/busy/old companions never open or end a search');
    assert.match(f.el('SearchCount').textContent,/3 found/,'readiness failures keep the prior results');
    assert.equal(f.el('SearchStart').disabled,false);
    if('searchRevision' in patch)assert.match(f.el('SearchStatus').textContent,/Update and reload/);
  }
  const stopped=fixture();await stopped.init();stopped.state.hold=true;const running=stopped.el('SearchStart').click();
  for(let attempt=0;attempt<50&&!stopped.state.held;attempt++)await new Promise(resolve=>setTimeout(resolve,5));
  assert(stopped.state.held);await stopped.el('SearchStop').click();stopped.state.held();await running;
  assert.match(stopped.el('SearchStatus').textContent,/Stopped/);assert.match(stopped.el('SearchCount').textContent,/2 found/);
  assert.equal(stopped.requests.length,0,'stop never saves results');assert.equal(stopped.el('SearchStart').disabled,false);
  const many=fixture();await many.init();many.state.many=true;many.state.totalPages=15;many.el('SearchPages').value='15';await many.el('SearchStart').click();
  assert.match(many.el('SearchCount').textContent,/15 found/);assert.equal(many.calls.filter(call=>call.args.method==='nextJobSearch').length,14);
  const direct=fixture();await direct.init();direct.el('SearchFolder').value='Priority';direct.el('notes').value='Keep unsaved notes';direct.el('notes').handlers.input();
  const incoming=job('3333333333',{role:'Direct LinkedIn preview',description:'Content added from LinkedIn'});assert((await direct.capture(incoming)).ok);
  assert.equal(direct.el('PreviewTitle').textContent,incoming.role);assert.equal(direct.el('SearchPanel').open,true);
  assert(direct.el('PreviewContent').querySelectorAll('#text').some(node=>node.textContent===incoming.description));
  assert.match(direct.el('SearchCount').textContent,/0 found/,'direct additions do not become temporary search results');
  const quick=direct.state.records.find(row=>row.url===incoming.url);assert.equal(quick.folder,'Priority');assert.equal(quick.contact,'');assert.equal(quick.notes,'');assert.equal(quick.status,'new');
  assert.equal(direct.el('notes').value,'Keep unsaved notes');
  assert((await direct.capture({...b,notes:'Do not overwrite'})).duplicate);assert.equal(direct.state.records[0].notes,'Important saved notes');
  const count=direct.state.records.length;assert((await direct.capture(job('9',{url:'https://attacker.invalid/jobs/view/9'}))).error);assert.equal(direct.state.records.length,count);
  direct.state.failSave=a.url;assert((await direct.capture(a)).error);assert.equal(direct.el('notes').value,'Keep unsaved notes');
  const folders=await direct.capture(b,{action:'folders'});assert.equal(folders.folders[0],'Priority');assert.equal(folders.saved,true);
  const beforeFolderRead=direct.requests.length;
  const metadataFolders=await direct.capture({url:b.url},{action:'folders'});
  assert.equal(metadataFolders.folders[0],'Priority','read-only folders accept a canonical identity without reparsing company/role');
  assert.equal(metadataFolders.saved,true);assert.equal(direct.requests.length,beforeFolderRead,'folder reads never write records');
  assert((await direct.capture({url:b.url},{action:'add'})).error,'identity-only metadata cannot become an ad save');
  assert((await direct.capture({url:b.url},{action:'remove'})).error,'existing removal confirmation remains strict');
  const raced=fixture();await raced.init();raced.state.folders.push('Keep original','SAP');
  assert.equal((await raced.capture({url:a.url},{action:'folders'})).saved,false);
  const racedRecord={...raced.state.records[0],...a,id:'d'.repeat(32),folder:'Keep original',notes:'Keep original notes',contact:'Keep original contact'};
  raced.state.records.push(structuredClone(racedRecord));
  const beforeRacedAdd=raced.requests.length;
  const racedResult=await raced.capture(a,{action:'add',folder:'SAP'});
  assert.equal(racedResult.folder,'Keep original','an ad saved between metadata and Add cannot be moved implicitly');
  assert.equal(racedResult.duplicate,true);assert.deepEqual(raced.state.records.find(row=>row.url===a.url),racedRecord);
  assert.equal(raced.requests.length,beforeRacedAdd,'an already-active duplicate causes no write regardless of supplied folder');
  const duringSave=fixture();await duringSave.init();duringSave.state.folders.push('Keep original','SAP');
  duringSave.state.beforeSave=structuredClone(racedRecord);
  const duringResult=await duringSave.capture(a,{action:'add',folder:'SAP'});
  assert.equal(duringResult.folder,'Keep original');assert.deepEqual(duringSave.state.records.find(row=>row.url===a.url),racedRecord);
  assert(!duringSave.requests.some(request=>request.action==='move_folder'),'a duplicate found atomically by save never enters a move path');
  const folderSelection=fixture();await folderSelection.init();await folderSelection.el('SearchStart').click();
  folderSelection.el('SearchSelectPage').checked=true;folderSelection.el('SearchSelectPage').handlers.change();
  folderSelection.el('notes').value='Keep this local draft';folderSelection.el('notes').handlers.input();
  const selectionCount=folderSelection.el('SearchCount').textContent,previewTitle=folderSelection.el('PreviewTitle').textContent;
  folderSelection.state.folders.push('Created elsewhere');
  assert((await folderSelection.capture({url:b.url},{action:'folders'})).folders.includes('Created elsewhere'));
  assert.equal(folderSelection.el('SearchCount').textContent,selectionCount);assert.equal(folderSelection.el('PreviewTitle').textContent,previewTitle);
  assert.equal(folderSelection.el('notes').value,'Keep this local draft');assert.equal(folderSelection.requests.length,0,'metadata refresh has no write/render side effects');
  const busyMetadata=fixture();await busyMetadata.init();busyMetadata.state.hold=true;const busyRun=busyMetadata.el('SearchStart').click();
  for(let attempt=0;attempt<50&&!busyMetadata.state.held;attempt++)await new Promise(resolve=>setTimeout(resolve,5));
  assert(busyMetadata.state.held);assert(busyMetadata.el('SearchStart').disabled);
  assert((await busyMetadata.capture({url:b.url},{action:'folders'})).ok,'local metadata remains readable during discovery');
  assert(busyMetadata.el('SearchStart').disabled,'metadata cannot unlock a running operation');
  await busyMetadata.el('SearchStop').click();busyMetadata.state.held();await busyRun;
  assert((await direct.capture(b,{action:'create_folder',folder:'SAP'})).ok);assert(direct.state.folders.includes('SAP'));assert.equal(direct.state.records.length,count,'creating a folder never adds an ad');
  assert((await direct.capture(b,{action:'remove'})).saved===false);assert(direct.state.records[0].deleted);assert.equal(direct.state.records[0].notes,'Important saved notes');
  assert.equal(direct.el('PreviewSave').textContent,'In Trash');assert.equal(direct.el('PreviewSave').disabled,true);
  assert((await direct.capture(b,{action:'add',folder:'SAP'})).saved);assert.equal(direct.state.records[0].folder,'SAP');assert.equal(direct.state.records[0].deleted,false);assert.equal(direct.state.records[0].status,'contacted');assert.equal(direct.state.records[0].notes,'Important saved notes');
  await direct.capture(b,{action:'remove'});direct.state.failMove=true;const partial=await direct.capture(b,{action:'add',folder:'Priority'});assert.equal(partial.saved,true);assert.match(partial.warning,/folder move failure/);assert.equal(direct.state.records[0].folder,'SAP');direct.state.failMove=false;
  const writes=direct.requests.length;assert((await direct.capture(b,{action:'purge'})).error);assert((await direct.capture(b,null)).error);assert.equal(direct.requests.length,writes);
  assert.equal(direct.el('notes').value,'Keep unsaved notes','folder creation/removal/restore preserve the manual draft');
  const editingCard=direct.el('List').children.find(card=>card.querySelectorAll('a').some(link=>link.href===b.url));
  await editingCard.querySelectorAll('button').find(button=>button.textContent==='Edit / view details').click();
  direct.el('notes').value='Keep this editing draft';direct.el('notes').handlers.input();const protectedWrites=direct.requests.length;
  assert.match((await direct.capture(b,{action:'remove'})).error,/Finish editing/);
  assert.match((await direct.capture(b,{action:'add',folder:'Priority'})).error,/Finish editing/);
  assert.equal(direct.requests.length,protectedWrites);assert.equal(direct.state.records[0].deleted,false);assert.equal(direct.el('notes').value,'Keep this editing draft');
  const single=fixture();await single.init();await single.el('SearchStart').click();single.el('SearchSelectPage').checked=true;single.el('SearchSelectPage').handlers.change();
  await single.el('PreviewClose').click();single.el('SearchSelectPage').handlers.change();
  assert(single.el('Preview').hidden,'changing selections does not reopen a dismissed preview');
  assert.match(single.el('SearchCount').textContent,/2 selected/,'closing the preview retains selected results');
  await single.el('SearchResults').children[2].querySelectorAll('button').find(button=>button.textContent==='Preview').click();await single.el('PreviewSave').click();
  assert(single.state.records.some(row=>row.url===c.url));assert(!single.state.records.some(row=>row.url===a.url),'Add this ad does not save other selected results');
  console.log('Job search UI: multi-page scroll/deduplication, review-only capture, full previews, selected folder import, partial failure/retry, existing notes/drafts, open filters, Stop and 15-page bounds passed');
})().catch(error=>{console.error(error);process.exitCode=1});
