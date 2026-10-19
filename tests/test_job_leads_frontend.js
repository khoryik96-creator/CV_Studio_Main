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
    action:{onClicked:{addListener:fn=>hooks.click=fn}, setBadgeText:async()=>{}},
    tabs:{onRemoved:{addListener:()=>{}},onUpdated:{addListener:fn=>hooks.updated=fn}, query:async()=>[...tabs.values()], get:async id=>tabs.get(id),
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
  const document = {getElementById:id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)},createElement:tag=>new Element(tag),addEventListener:(type,fn)=>events[type]=fn};
  const el = name=>document.getElementById('jobLeads'+name);
  let records=[], sequence=0, allowDiscard=true;
  class TestURL extends URL {static createObjectURL(blob){blobs.push(blob);return 'blob:synthetic'} static revokeObjectURL(){}}
  const location={origin:'http://127.0.0.1:5000',search:'',href:''};
  const window={addEventListener:(type,fn)=>events[type]=fn,confirm:()=>allowDiscard,postMessage:message=>{
    events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:message.channel,id:message.id,result:message.action==='jobTabs'?[{id:2,title:'Sample job',url}]:{url,company:'Read company',role:'Read role',contact:'Do not copy from ad',status:'won',follow_up:'2030-01-01',notes:'Do not replace notes'}}});
  }};
  const fetch=async(endpoint,options)=>{
    assert.equal(endpoint,'/job-leads');
    if(!options?.body)return {ok:true,json:async()=>({records})};
    const data=JSON.parse(options.body), value=data.record;
    if(data.action==='restore')return {ok:true,json:async()=>({added:0,skipped:records.length})};
    const duplicate=records.find(row=>row.url===value.url && row.id!==value.id);
    if(duplicate)return {ok:true,json:async()=>({record:duplicate,duplicate:true})};
    const record={...value,id:value.id||'b'.repeat(32),revision:(value.revision||0)+1};
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
  assert.equal(el('status').value,'new');assert.equal(el('contact').value,'');assert.equal(el('follow_up').value,'');
  assert.match(el('Message').textContent,/optionally add a contact/);
  el('company').value='Manual correction';el('contact').value='Manual Contact';el('notes').value='Keep my notes';el('status').value='contacted';el('follow_up').value='2026-11-01';
  await el('AutoFill').click();
  assert.equal(el('company').value,'Manual correction');assert.equal(el('contact').value,'Manual Contact');assert.equal(el('notes').value,'Keep my notes');assert.equal(el('status').value,'contacted');assert.equal(el('follow_up').value,'2026-11-01');
  const previousPost=window.postMessage;
  window.postMessage=message=>events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:message.channel,id:message.id,error:'Synthetic read failure'}});
  await el('AutoFill').click();assert.equal(el('company').value,'Manual correction');assert.equal(el('contact').value,'Manual Contact');assert.equal(el('Save').disabled,false);assert.match(el('Message').textContent,/draft has been kept/);
  window.postMessage=previousPost;
  await el('New').click();el('url').value='https://attacker.invalid/jobs/view/123';await el('AutoFill').click();assert.equal(el('company').value,'');assert.match(el('Message').textContent,/Paste a LinkedIn job ad link/);
  console.log('Job Leads: capture binding/isolation, save/edit/search, duplicate/draft protection, paste-link autofill, optional manual contact/status/date preservation, failure, CSV and HTML safety passed');
})().catch(error=>{console.error(error);process.exitCode=1});
