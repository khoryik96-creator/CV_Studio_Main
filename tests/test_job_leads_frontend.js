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
  const context = vm.createContext({chrome,URL,Map,Set,Error,Number,console});
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
    querySelectorAll(tag){return this.children.flatMap(child=>[...(child.tagName===tag?[child]:[]),...child.querySelectorAll(tag)])}
    scrollIntoView(){}
    click(){this.clicked=true;return this.handlers.click?.()}
    get selectedOptions(){return this.children.filter(child=>child.value===this.value)}
  }
  const ids = new Map(), events={}, blobs=[];
  const document = {getElementById:id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)},createElement:tag=>new Element(tag),createTextNode:text=>new Element('#text',text),addEventListener:(type,fn)=>events[type]=fn};
  const el = name=>document.getElementById('jobLeads'+name);
  el('FolderFilter').value='*';
  let records=[], sequence=0, allowDiscard=true, lookupError=false, lookups=0, missingDescription=false;
  class TestURL extends URL {static createObjectURL(blob){blobs.push(blob);return 'blob:synthetic'} static revokeObjectURL(){}}
  const location={origin:'http://127.0.0.1:5000',search:'',href:''};
  const window={addEventListener:(type,fn)=>events[type]=fn,confirm:()=>allowDiscard,postMessage:message=>{
    events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:message.channel,id:message.id,result:message.action==='jobTabs'?[{id:2,title:'Sample job',url}]:{url,company:'Read company',role:'Read role',contact:'Do not copy from ad',status:'won',follow_up:'2030-01-01',notes:'Do not replace notes'}}});
  }};
  const fetch=async(endpoint,options)=>{
    assert.equal(endpoint,'/job-leads');
    if(!options?.body)return {ok:true,json:async()=>({records})};
    const data=JSON.parse(options.body), value=data.record;
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
  const ui=vm.createContext({window,document,location,URL:TestURL,URLSearchParams,Blob,Map,Set,Date,Error,SyntaxError,Number,String,Object,JSON,Option:function(text,value){const node=new Element('option',text);node.value=value;return node},crypto:{randomUUID:()=>String(++sequence).padStart(32,'0')},setTimeout,clearTimeout,fetch});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/cvstudio/job-leads.js'),'utf8'),ui);
  await window.initJobLeads();
  el('url').value=url;el('company').value='=FORMULA()';el('role').value='<img src=x onerror=alert(1)>';el('notes').value='Important notes';
  el('Form').handlers.submit({preventDefault(){}}); // wait for both save and list request
  await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(el('Total').textContent,'1');
  assert.equal(el('List').children[0].children[0].textContent,'=FORMULA()');
  assert.equal(el('List').children[0].children[1].textContent,'<img src=x onerror=alert(1)>');
  const missingDetails=el('List').children[0].children.at(-1);
  assert.equal(missingDetails.tagName,'details');assert.match(missingDetails.children[0].textContent,/View more/);assert.match(missingDetails.children[1].textContent,/No job description was saved/);
  assert(el('List').children[0].children[2].children.some(child=>child.textContent==='Posted: Not available'));
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
  const savedCard=el('List').children[0], more=savedCard.children.at(-1);
  assert(savedCard.children[2].children.some(child=>child.textContent==='Posted: 2 Oct 2026'));
  assert.equal(more.tagName,'details');assert.equal(more.children.find(child=>child.tagName==='div').textContent,'<script>Never execute()</script>\nFull saved description');
  await el('Export').click();assert.match(await blobs.at(-1).text(),/date_posted/);assert.match(await blobs.at(-1).text(),/2026-10-02/);
  await el('New').click();el('url').value='https://attacker.invalid/jobs/view/123';await el('AutoFill').click();assert.equal(el('company').value,'');assert.match(el('Message').textContent,/Paste a LinkedIn job ad link/);
  // Realistic organization workflow: folders, known creation date, rich paste,
  // recoverable row deletion, restore, cancellation and clear with a hidden row.
  assert(savedCard.children[2].children.some(child=>/Date created: 2 Oct 2026/.test(child.textContent)));
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
  console.log('Job Leads: capture binding/isolation, save/edit/search, duplicate/draft protection, paste-link autofill, optional manual contact/status/date preservation, failure, CSV and HTML safety passed');
})().catch(error=>{console.error(error);process.exitCode=1});
