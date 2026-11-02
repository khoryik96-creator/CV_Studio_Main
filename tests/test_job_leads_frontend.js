const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert/strict');
const root = path.resolve(__dirname, '..');

(async () => {
  const hooks = {}, scriptCalls = [];
  const url = 'https://www.linkedin.com/jobs/view/1234567890';
  const tabs = new Map([
    [1, {id:1, url:'http://127.0.0.1:5000/', status:'complete'}],
    [2, {id:2, url, title:'Sample job', status:'complete'}],
    [3, {id:3, url:'https://www.linkedin.com/search/results/people/', status:'complete'}],
    [4, {id:4, url:'https://www.linkedin.com/jobs/search/?currentJobId=1234567890', title:'Search with selected job', status:'complete'}],
    [5, {id:5, url:'https://attacker.invalid/jobs/view/1234567890', status:'complete'}]
  ]);
  const chrome = {
    storage:{session:{get:async()=>({}),set:async()=>{}}},
    action:{onClicked:{addListener:fn=>hooks.click=fn}, setBadgeText:async()=>{}},
    tabs:{onRemoved:{addListener:()=>{}},onUpdated:{addListener:fn=>hooks.updated=fn},onActivated:{addListener:()=>{}}, query:async()=>[...tabs.values()], get:async id=>tabs.get(id),
      create:async()=>{throw Error('Job capture must never create a tab')}, update:async()=>{throw Error('Job capture must never navigate')}, remove:async()=>{throw Error('Job capture must never close a tab')}},
    scripting:{executeScript:async args=>{
      scriptCalls.push(args);
      if(args.files)return [{}];
      if(!args.args)return [{result:true,documentId:'bound-document'}];
      return [{result:{url,company:'Example Company',role:'Finance Manager'}}];
    }},runtime:{onMessage:{addListener:fn=>hooks.message=fn}}
  };
  const identity=require('./linkedin_companion_identity_fixture')(chrome);
  const context = vm.createContext({chrome,URL,Map,Set,Error,Number,console,setTimeout:fn=>fn(),crypto:identity.crypto,TextEncoder});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/linkedin-companion/worker.js'),'utf8'), context);
  const sender = {tab:{id:1},documentId:'bound-document',url:tabs.get(1).url};
  const rpc = (action,args={},who=sender)=>new Promise(resolve=>hooks.message({kind:'sourcer',action,args},who,resolve));
  assert((await rpc('jobRead',{tab_id:2,expected_url:url})).error);
  await hooks.click(tabs.get(1));
  assert.deepEqual(Array.from((await rpc('jobTabs')).result, row=>row.id),[2,4]);
  assert((await rpc('jobRead',{tab_id:2,expected_url:url},{...sender,documentId:'stale-document'})).error);
  assert((await rpc('jobRead',{tab_id:5,expected_url:url})).error);
  assert((await rpc('jobRead',{tab_id:2,expected_url:'https://www.linkedin.com/jobs/view/999'})).error);
  assert.equal((await rpc('jobRead',{tab_id:4,expected_url:url})).result.company,'Example Company');
  assert.equal(scriptCalls.at(-1).args[0],url);
  const run_id='a'.repeat(32);
  assert.equal((await rpc('begin',{run_id,source_tab_id:3,max_pages:1,mode:'standard'})).result,true);
  assert((await rpc('jobRead',{tab_id:2,expected_url:url})).error, 'job capture must not interfere with a running sourcer');
  await rpc('end',{run_id});
  hooks.updated(1,{status:'loading'});
  assert((await rpc('jobRead',{tab_id:2,expected_url:url})).error, 'reload must revoke browser authority');

  class Element {
    constructor(tag='div', text='') {this.tagName=tag;this.textContent=text;this.value='';this.children=[];this.handlers={};this.dataset={};this.disabled=false;this.files=[];}
    addEventListener(type,fn){this.handlers[type]=fn}
    append(...children){this.children.push(...children)}
    appendChild(child){this.children.push(child);return child}
    replaceChildren(...children){this.children=children}
    setAttribute(name,value){this[name]=value}
    focus(){}
    querySelectorAll(tag){return this.children.flatMap(child=>[...(child.tagName===tag?[child]:[]),...child.querySelectorAll(tag)])}
    scrollIntoView(){}
    click(){this.clicked=true;return this.handlers.click?.()}
    get selectedOptions(){return this.children.filter(child=>child.value===this.value)}
  }
  const ids = new Map(), events={}, blobs=[];
  const document = {getElementById:id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)},createElement:tag=>new Element(tag),createTextNode:text=>new Element('#text',text),addEventListener:(type,fn)=>events[type]=fn};
  const el = name=>document.getElementById('jobLeads'+name);
  el('FolderFilter').value='*';
  let records=[], folders=[], sequence=0, allowDiscard=true, lookupError=false, lookups=0, missingDescription=false, moveError=false;
  class TestURL extends URL {static createObjectURL(blob){blobs.push(blob);return 'blob:synthetic'} static revokeObjectURL(){}}
  const location={origin:'http://127.0.0.1:5000',search:'',href:''};
  const window={addEventListener:(type,fn)=>events[type]=fn,confirm:()=>allowDiscard,postMessage:message=>{
    events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:message.channel,id:message.id,result:message.action==='jobTabs'?[{id:2,title:'Sample job',url}]:{url,company:'Read company',role:'Read role',contact:'Do not copy from ad',status:'won',follow_up:'2030-01-01',notes:'Do not replace notes'}}});
  }};
  const fetch=async(endpoint,options)=>{
    assert.equal(endpoint,'/job-leads');
    if(!options?.body)return {ok:true,json:async()=>({records,folders})};
    const data=JSON.parse(options.body), value=data.record;
    if(data.action==='create_folder') {
      if (!folders.includes(data.folder)) folders.push(data.folder);
      return {ok:true,json:async()=>({folder:data.folder})};
    }
    if(data.action==='delete_folder') {
      folders=folders.filter(name=>name!==data.folder);
      records.forEach(row=>{if(row.folder===data.folder){row.folder='';row.revision++;}});
      return {ok:true,json:async()=>({changed:data.records.length})};
    }
    if(data.action==='move_folder') {
      if(moveError)return {ok:false,json:async()=>({error:'Selected ad changed in another window'})};
      records.forEach(row=>{if(data.records.some(item=>item.id===row.id)){row.folder=data.folder;row.revision++;}});
      return {ok:true,json:async()=>({changed:data.records.length})};
    }
    if(data.action==='format_content')return {ok:true,json:async()=>({description_rich:[{tag:'p',children:[{tag:'strong',children:[{text:data.description}]}]}]})};
    if(['trash','untrash'].includes(data.action)){
      for(const row of records) if(data.records.some(item=>item.id===row.id)){row.deleted=data.action==='trash';row.revision++;}
      return {ok:true,json:async()=>({changed:data.records.length})};
    }
    if(data.action==='lookup'){
      lookups++;
      if(data.url.endsWith('/9999999990'))return {ok:!lookupError,json:async()=>lookupError?{error:'Synthetic public page read failure'}:{record:{url:data.url,company:'Other company',role:'Other role',location:'Penang',description:'Other description'}}};
      return {ok:!lookupError,json:async()=>lookupError?{error:'Synthetic public page read failure'}:{record:{url:data.url,company:'Read company',role:'Read role',location:'Kuala Lumpur',date_posted:'2026-10-02',description:missingDescription?'':'Job description',description_rich:[{tag:'p',children:[{tag:'strong',children:[{text:'Job description'}]}]}],description_truncated:true,contact:'Do not copy',status:'won',follow_up:'2030-01-01'}}};
    }
    if(data.action==='restore')return {ok:true,json:async()=>({added:0,skipped:records.length})};
    const duplicate=records.find(row=>row.url===value.url && row.id!==value.id);
    if(duplicate)return {ok:true,json:async()=>({record:duplicate,duplicate:true})};
    const record={...value,id:value.id||'b'.repeat(32),revision:(value.revision||0)+1,created_at:'2026-10-02T12:30:00Z'};
    records=[record];return {ok:true,json:async()=>({record,duplicate:false})};
  };
  const preferences=new Map();
  const ui=vm.createContext({window,document,location,localStorage:{getItem:key=>preferences.get(key)??null,setItem:(key,value)=>preferences.set(key,value),removeItem:key=>preferences.delete(key)},URL:TestURL,URLSearchParams,Blob,Map,Set,Date,Error,SyntaxError,Number,String,Object,JSON,Option:function(text,value){const node=new Element('option',text);node.value=value;return node},crypto:{randomUUID:()=>String(++sequence).padStart(32,'0')},setTimeout,clearTimeout,fetch});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/cvstudio/job-search-walk.js'),'utf8'),ui);vm.runInContext(fs.readFileSync(path.join(root,'vendor/cvstudio/job-leads.js'),'utf8'),ui);
  await window.initJobLeads();
  el('url').value=url;el('company').value='=FORMULA()';el('role').value='<img src=x onerror=alert(1)>';el('notes').value='Important notes';
  el('Form').handlers.submit({preventDefault(){}}); // wait for both save and list request
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(el('Total').textContent,'1');
  // Table row: select, posted, title (opens the preview), company, client, …
  const titleOf=row=>row.children[2].children[0];
  assert.equal(el('List').children[0].children[3].textContent,'=FORMULA()');
  assert.equal(titleOf(el('List').children[0]).textContent,'<img src=x onerror=alert(1)>');
  assert.equal(el('List').children[0].children[1].textContent,'—','no posted date');
  await titleOf(el('List').children[0]).click();assert.equal(el('PreviewTitle').textContent,'<img src=x onerror=alert(1)>','the title opens the preview');
  assert.match(el('Message').textContent,/saved on this computer/);
  await el('Export').click();assert((await blobs[0].text()).includes("'=FORMULA()"));
  el('Search').value='not present';el('Search').handlers.input();assert.equal(el('Count').textContent,'0 leads');
  el('Search').value='';el('Search').handlers.input();
  await el('New').click();el('url').value=url;el('company').value='Duplicate';el('role').value='Role';el('notes').value='Keep draft';el('notes').handlers.input();
  await el('Form').handlers.submit({preventDefault(){}});
  assert.match(el('Message').textContent,/already saved/);assert.equal(el('notes').value,'Keep draft');
  assert.equal(records[0].notes,'Important notes');
  allowDiscard=false;await el('New').click();assert.equal(el('notes').value,'Keep draft');
  await el('Tabs').click();el('Source').value='2';
  await el('Read').click();assert.equal(el('notes').value,'Keep draft');
  allowDiscard=true;await el('Read').click();
  assert.equal(el('company').value,'Read company');assert.match(el('Message').textContent,/Review the details/);
  assert.equal(records[0].company,'=FORMULA()', 'capture must not save automatically');
  await el('New').click();
  let prevented=false;
  await el('url').handlers.paste({clipboardData:{getData:()=>url+'?trk=discard'},preventDefault(){prevented=true}});
  assert(prevented);assert.equal(el('url').value,url);
  assert.equal(el('company').value,'Read company');assert.equal(el('role').value,'Read role');
  assert.equal(el('location').value,'Kuala Lumpur');assert(lookups>0,'paste uses the local public-read API without a companion');
  assert.equal(el('date_posted').value,'2026-10-02');assert.match(el('DescriptionNote').textContent,/Captured excerpt/);
  assert.equal(el('status').value,'new');assert.equal(el('contact').value,'');assert.equal(el('follow_up').value,'');
  assert.match(el('Message').textContent,/optionally add a contact/);
  el('company').value='Manual correction';el('contact').value='Manual Contact';el('notes').value='Keep my notes';el('status').value='contacted';el('follow_up').value='2026-11-01';
  await el('AutoFill').click();
  assert.equal(el('company').value,'Manual correction');assert.equal(el('contact').value,'Manual Contact');assert.equal(el('notes').value,'Keep my notes');assert.equal(el('status').value,'contacted');assert.equal(el('follow_up').value,'2026-11-01');
  el('date_posted').value='2026-09-30';await el('AutoFill').click();assert.equal(el('date_posted').value,'2026-09-30');
  missingDescription=true;await el('RefreshContent').click();assert.equal(el('description').value,'Job description');assert.match(el('Message').textContent,/current content has been kept/);missingDescription=false;
  lookupError=true;
  await el('AutoFill').click();assert.equal(el('company').value,'Manual correction');assert.equal(el('contact').value,'Manual Contact');assert.equal(el('Save').disabled,false);assert.match(el('Message').textContent,/draft has been kept/);
  lookupError=false;
  await el('BrowserFill').click();assert.equal(el('contact').value,'Manual Contact');
  await el('New').click();
  el('url').value='https://www.linkedin.com/jobs/view/7777777777';el('company').value='Saved Ad Company';el('role').value='Account Manager';el('date_posted').value='2026-10-02';el('description').value='<script>Never execute()</script>\nFull saved description';
  await el('Form').handlers.submit({preventDefault(){}});
  const savedRow=el('List').children[0];
  assert.equal(savedRow.children[1].textContent,'2 Oct 2026');
  await titleOf(savedRow).click();const more=el('PreviewContent');
  const savedText=more.querySelectorAll('#text').map(child=>child.textContent).join('\n');
  assert.equal(savedText,'<script>Never execute()</script>\nFull saved description');
  assert.equal(more.querySelectorAll('script').length,0,'ad text is never executed');
  await el('Export').click();assert.match(await blobs.at(-1).text(),/date_posted/);assert.match(await blobs.at(-1).text(),/2026-10-02/);
  await el('New').click();el('url').value='https://attacker.invalid/jobs/view/123';await el('AutoFill').click();assert.equal(el('company').value,'');assert.match(el('Message').textContent,/Paste a LinkedIn job ad link/);
  // Realistic organization workflow: folders, known creation date, rich paste,
  // recoverable row deletion, restore, cancellation and clear with a hidden row.
  assert.equal(savedRow.children[8].textContent,'2 Oct 2026','the Saved column shows the date created');
  el('FolderFilter').value='*';
  records[0].folder='Finance';records.push({...records[0],id:'c'.repeat(32),folder:'Technology',url:'https://www.linkedin.com/jobs/view/8888888888'});
  await el('Refresh').click();el('FolderFilter').value='Finance';el('FolderFilter').handlers.change();
  assert.equal(el('Count').textContent,'1–1 of 1');await el('New').click();assert.equal(el('folder').value,'Finance');
  let pasted=false;
  await el('description').handlers.paste({clipboardData:{getData:type=>type==='text/html'?'<p><b>Rich job text</b></p>':'Rich job text'},preventDefault(){pasted=true}});
  assert(pasted);assert.equal(el('description').value,'Rich job text');assert.equal(el('Content').querySelectorAll('strong').length,1);
  await el('New').click();
  const deleteButton=el('List').children[0].querySelectorAll('button').find(button=>button.textContent==='Delete');
  await deleteButton.click();assert.equal(records.filter(row=>row.deleted).length,1);assert.equal(el('Total').textContent,'1');
  el('FolderFilter').value='!trash';el('FolderFilter').handlers.change();assert.equal(el('Count').textContent,'1–1 of 1');
  await el('List').children[0].querySelectorAll('button').find(button=>button.textContent==='Restore').click();assert(!records.some(row=>row.deleted));
  el('FolderFilter').value='Finance';el('FolderFilter').handlers.change();allowDiscard=false;await el('Clear').click();assert(!records.some(row=>row.deleted));
  allowDiscard=true;await el('Clear').click();assert(records.find(row=>row.folder==='Finance').deleted);assert(!records.find(row=>row.folder==='Technology').deleted);
  await el('ClearAll').click();assert(records.every(row=>row.deleted));assert.equal(el('Total').textContent,'0');
  // Changing source identity must never save a new URL with the old ad's data.
  await el('New').click();
  const pasteJob=value=>el('url').handlers.paste({clipboardData:{getData:()=>value},preventDefault(){}});
  await pasteJob(url);
  el('contact').value='Contact for A';el('notes').value='Notes for A';el('company').value='Manual A correction';
  el('folder').value='Priority';el('status').value='contacted';el('follow_up').value='2026-11-01';
  allowDiscard=false;await pasteJob('https://www.linkedin.com/jobs/view/9999999990');
  assert.equal(el('url').value,url,'cancel keeps the original ad identity');assert.equal(el('company').value,'Manual A correction');
  allowDiscard=true;lookupError=true;await pasteJob('https://www.linkedin.com/jobs/view/9999999990');
  assert.equal(el('url').value,url,'failed switch keeps the original ad identity');assert.equal(el('notes').value,'Notes for A');
  lookupError=false;await pasteJob('https://www.linkedin.com/jobs/view/9999999990');
  assert.equal(el('company').value,'Other company');assert.equal(el('role').value,'Other role');assert.equal(el('description').value,'Other description');
  assert.equal(el('contact').value,'');assert.equal(el('notes').value,'');assert.equal(el('status').value,'new');assert.equal(el('date_posted').value,'');assert.equal(el('follow_up').value,'');assert.equal(el('folder').value,'Priority');
  el('company').value='Manual B correction';await el('AutoFill').click();assert.equal(el('company').value,'Manual B correction','same-job manual corrections survive');
  el('url').value='https://www.linkedin.com/jobs/view/1234567899';const oldRecords=JSON.stringify(records);
  await el('Form').handlers.submit({preventDefault(){}});assert.equal(JSON.stringify(records),oldRecords,'Save cannot bypass source identity check');
  assert.match(el('Message').textContent,/different job|different ad/i);
  // Explicit empty folders and selecting already-saved ads for later filing.
  await el('New').click();
  records=[{...records[0],id:'d'.repeat(32),url:'https://www.linkedin.com/jobs/view/555',folder:'',deleted:false},
    {...records[0],id:'e'.repeat(32),url:'https://www.linkedin.com/jobs/view/666',folder:'',deleted:false}];
  folders=[];await el('Refresh').click();
  await el('FolderNew').click();assert.equal(el('FolderEditor').hidden,false);
  el('FolderName').value='Shortlisted';await el('FolderCreate').click();
  assert.equal(el('FolderEditor').hidden,true);assert.equal(el('FolderFilter').value,'Shortlisted');
  assert.equal(el('Count').textContent,'0 leads');assert.equal(el('FolderDelete').disabled,false);
  await el('Refresh').click();assert(el('FolderFilter').children.some(item=>item.value==='Shortlisted'),'empty folder survives a fresh list request');
  el('FolderFilter').value='*';el('FolderFilter').handlers.change();
  let pick=el('List').children[0].querySelectorAll('input')[0];pick.checked=true;pick.handlers.change();
  assert.equal(el('SelectedCount').textContent,'1 selected');assert.equal(el('Selection').hidden,false);
  const originalNote=records[0].notes,originalCreated=records[0].created_at;
  el('MoveFolder').value='Shortlisted';await el('Move').click();
  assert.equal(records[0].folder,'Shortlisted');assert.equal(records[1].folder,'');
  assert.equal(records[0].notes,originalNote);assert.equal(records[0].created_at,originalCreated);
  assert.equal(el('Selection').hidden,true);
  el('SelectPage').checked=true;el('SelectPage').handlers.change();assert.equal(el('SelectedCount').textContent,'2 selected');
  el('Search').value='no match';el('Search').handlers.input();assert.equal(el('Selection').hidden,true,'filter changes clear hidden selections');
  el('Search').value='';el('Search').handlers.input();
  await el('FolderNew').click();el('FolderName').value='Another';await el('FolderCreate').click();
  el('FolderFilter').value='*';el('FolderFilter').handlers.change();
  await el('List').children[0].querySelectorAll('button').find(button=>button.textContent==='Edit').click();
  el('notes').value='Unsaved notes';el('notes').handlers.input();
  pick=el('List').children[0].querySelectorAll('input')[0];pick.checked=true;pick.handlers.change();
  el('MoveFolder').value='Another';allowDiscard=false;await el('Move').click();
  assert.equal(records[0].folder,'Shortlisted');assert.equal(el('notes').value,'Unsaved notes');
  allowDiscard=true;moveError=true;await el('Move').click();
  assert.equal(records[0].folder,'Shortlisted');assert.equal(el('notes').value,'Unsaved notes');assert.match(el('Message').textContent,/changed in another window/);
  moveError=false;await el('Move').click();assert.equal(records[0].folder,'Another');assert.equal(el('folder').value,'Another');
  assert.equal(el('notes').value,originalNote,'successful move reloads the current revision only after discard confirmation');
  el('FolderFilter').value='Another';el('FolderFilter').handlers.change();allowDiscard=false;await el('FolderDelete').click();
  assert(folders.includes('Another'));assert.equal(records[0].folder,'Another');
  allowDiscard=true;await el('FolderDelete').click();
  assert(!folders.includes('Another'));assert(records.every(row=>row.folder===''&&!row.deleted),'deleting a folder keeps its saved ads');
  el('FolderFilter').value='Shortlisted';el('FolderFilter').handlers.change();await el('FolderDelete').click();
  assert.equal(folders.length,0);assert.equal(records.length,2);
  // The chosen destination survives New, capture, editing another record and a
  // fresh controller. An explicit Unfiled choice and deletion clear the default.
  await el('FolderNew').click();el('FolderName').value='Preferred';await el('FolderCreate').click();
  el('folder').value='Preferred';el('folder').handlers.change();
  await el('New').click();assert.equal(el('folder').value,'Preferred');
  await el('Read').click();assert.equal(el('folder').value,'Preferred');
  el('FolderFilter').value='*';el('FolderFilter').handlers.change();
  await el('List').children[0].querySelectorAll('button').find(button=>button.textContent==='Edit').click();
  assert.equal(el('folder').value,'','editing uses that saved ad\'s own folder');
  await el('New').click();assert.equal(el('folder').value,'Preferred');
  el('folder').value='';el('folder').handlers.change();
  el('FolderFilter').value='Preferred';el('FolderFilter').handlers.change();
  await el('New').click();assert.equal(el('folder').value,'','Unfiled overrides the board filter');
  el('folder').value='Preferred';el('folder').handlers.change();
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/cvstudio/job-search-walk.js'),'utf8'),ui);vm.runInContext(fs.readFileSync(path.join(root,'vendor/cvstudio/job-leads.js'),'utf8'),ui);await window.initJobLeads();
  assert.equal(el('folder').value,'Preferred','selection survives reloading this CV Studio address');
  await el('FolderDelete').click();await el('New').click();
  assert.equal(el('folder').value,'');assert(!preferences.has('cvstudio_job_leads_folder'));
  // Legacy nested paragraphs flatten for display; plain explicit bullets become
  // lists while literal markup stays text. Saved payloads remain unchanged.
  records[0].description='Heading\nFirst item\nSecond item';
  records[0].description_rich=[{tag:'p',children:[{tag:'p',children:[{text:'Heading'}]},{tag:'ul',children:[{tag:'li',children:[{text:'First item'}]},{tag:'li',children:[{text:'Second item'}]}]}]}];
  await el('Refresh').click();await titleOf(el('List').children[0]).click();
  const body=el('PreviewContent');
  assert.equal(body.children[0].tagName,'p');assert.equal(body.children[1].tagName,'ul');assert.equal(body.children[0].querySelectorAll('p').length,0);
  records[0].description_rich=[];records[0].description='Heading\n\n• First item\n• Second item';await el('Refresh').click();await titleOf(el('List').children[0]).click();
  assert.equal(el('PreviewContent').querySelectorAll('li').length,2);
  // Job ads table: Client, Posted (estimates count) and Sort filters, empty
  // states, the manual form toggle and the tab count.
  {const day=offset=>{const d=new Date();d.setDate(d.getDate()-offset);return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');};
   const label=value=>new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(value+'T00:00:00Z'));
   const ad=(n,patch)=>({id:String(n).repeat(32),revision:1,url:'https://www.linkedin.com/jobs/view/100000000'+n,company:'Company '+n,role:'Role '+n,contact:'',location:'',status:'new',folder:'',follow_up:'',notes:'',description:'',description_rich:[],date_posted:'',created_at:'2026-10-0'+n+'T00:00:00Z',deleted:false,...patch});
   records=[ad(1,{role:'Zeta role',date_posted:day(2),client:{company_id:11,name:'Example Client'}}),ad(2,{role:'Alpha role',date_posted_estimate:day(3)}),
     ad(3,{role:'Mid role',date_posted:day(20),client:{company_id:12,name:'Second Client'}})];
   await el('Refresh').click();await el('FiltersReset').click();
   const titles=()=>el('List').children.map(tr=>tr.children[2].children[0].textContent);
   const choose=(name,value)=>{el(name).value=value;el(name).handlers.change();};
   assert.deepEqual(titles(),['Zeta role','Alpha role','Mid role'],'Recently updated keeps the saved order');
   assert.equal(el('List').children[1].children[1].textContent,'≈ '+label(day(3)),'an estimate shows with ≈');
   assert.deepEqual([el('List').children[0].children[4].textContent,el('List').children[1].children[4].textContent],['Example Client','—']);
   assert.deepEqual(el('ClientFilter').children.map(option=>option.textContent),['All ads','Any client','Example Client','Second Client']);
   choose('ClientFilter','!any');assert.deepEqual(titles(),['Zeta role','Mid role']);
   choose('ClientFilter','12');assert.deepEqual(titles(),['Mid role']);
   await el('FiltersReset').click();choose('PostedFilter','7');assert.deepEqual(titles(),['Zeta role','Alpha role'],'estimates count for Posted');
   await el('FiltersReset').click();choose('Sort','posted_asc');assert.deepEqual(titles(),['Mid role','Alpha role','Zeta role']);
   choose('Sort','role_asc');assert.deepEqual(titles(),['Alpha role','Mid role','Zeta role']);
   choose('Sort','client_asc');assert.deepEqual(titles(),['Zeta role','Mid role','Alpha role'],'ads without a client sort last');
   choose('Sort','saved_desc');assert.deepEqual(titles(),['Mid role','Alpha role','Zeta role']);
   await el('FiltersReset').click();el('Search').value='second client';el('Search').handlers.input();assert.deepEqual(titles(),['Mid role'],'search includes the client name');
   el('Search').value='nothing like this';el('Search').handlers.input();assert.match(el('List').children[0].children[0].textContent,/No matching ads/);
   await el('FiltersReset').click();assert.equal(el('AdsTabCount').textContent,'3');
   // Followed clients opens its ads here: one client, or every client ad.
   await window.cvStudioJobLeads.showClientAds(12);assert.equal(el('ClientFilter').value,'12');assert.deepEqual(titles(),['Mid role']);
   await window.cvStudioJobLeads.showClientAds(99);assert.equal(el('ClientFilter').value,'!any');
   await window.cvStudioJobLeads.showClientAds();assert.equal(el('ClientFilter').value,'!any');assert.deepEqual(titles(),['Zeta role','Mid role']);
   // The manual form opens only when it is used.
   await el('FormClose').click();assert(el('FormCard').hidden && !el('AddManual').hidden);assert.equal(el('Layout').dataset.form,'');
   await el('AddManual').click();assert(!el('FormCard').hidden && el('AddManual').hidden);assert.equal(el('Layout').dataset.form,'open');
   await el('FormClose').click();await el('List').children[0].querySelectorAll('button').find(button=>button.textContent==='Edit').click();
   assert(!el('FormCard').hidden,'Edit opens the form');assert.equal(el('company').value,'Company 1');
   records=[];await el('Refresh').click();assert.match(el('List').children[0].children[0].textContent,/No saved ads yet/);assert.equal(el('AdsTabCount').textContent,'0');}
  console.log('Job Leads: capture binding/isolation, save/edit/search, duplicate/draft protection, paste-link autofill, optional manual contact/status/date preservation, failure, CSV and HTML safety passed');
})().catch(error=>{console.error(error);process.exitCode=1});
