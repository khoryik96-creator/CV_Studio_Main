const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-leads.js'),'utf8');
const url='https://www.linkedin.com/jobs/view/1234567890',other='https://www.linkedin.com/jobs/view/7777777777';
class Element {
  constructor(tagName='div',textContent=''){Object.assign(this,{tagName,textContent,value:'',children:[],handlers:{},disabled:false,dataset:{}})}
  addEventListener(type,fn){this.handlers[type]=fn} append(...values){this.children.push(...values)}
  appendChild(value){this.children.push(value);return value} replaceChildren(...values){this.children=values}
  querySelectorAll(tag){return this.children.flatMap(child=>[...(child.tagName===tag?[child]:[]),...child.querySelectorAll(tag)])}
  setAttribute(name,value){this[name]=value} click(){return this.handlers.click?.()} focus(){} scrollIntoView(){}
}
function fixture(){
  const ids=new Map(),events={},calls=[],requests=[],waits=[];
  const document={getElementById:id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)},createElement:tag=>new Element(tag),createTextNode:text=>new Element('#text',text),addEventListener:()=>{}};
  const el=name=>document.getElementById('jobLeads'+name),location={origin:'http://127.0.0.1:5000',search:''};
  el('FolderFilter').value='*';
  const state={publicError:'JOB_AD_RATE_LIMITED',ready:true,busy:false,captureFail:false,mismatch:false,confirm:true,noReply:false,empty:false};
  const record=value=>({url:value,company:'Captured Company',role:'Finance Manager',location:'Captured City',date_posted:'2026-10-02',description:state.empty?'':'Captured description',contact:'Never import this',notes:'Never import this',status:'won',follow_up:'2030-01-01'});
  const window={addEventListener:(name,fn)=>events[name]=fn,confirm:()=>state.confirm,postMessage:message=>{
    calls.push(message);let result,error;
    if(message.action==='jobStatus'){
      if(state.noReply)return;
      if(!state.ready)error='Not connected';else result={connected:true,job_read:true,busy:state.busy};
    } else if(message.action==='jobFromLink'){
      if(state.captureFail)error='Synthetic browser read failed';else result=record(state.mismatch?other:message.args.url);
    } else throw Error('Unexpected action '+message.action);
    events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',id:message.id,channel:message.channel,...(error?{error}:{result})}});
  }};
  let serial=0;
  const fetch=async(endpoint,options)=>{
    assert.equal(endpoint,'/job-leads');
    if(!options?.body)return {ok:true,json:async()=>({records:[],folders:['Priority']})};
    const data=JSON.parse(options.body);requests.push(data);assert.equal(data.action,'lookup','no save, paid call or extra request');
    return {ok:!state.publicError,json:async()=>state.publicError?{error:'Public read unavailable',code:state.publicError,request_id:'a'.repeat(16)}:{record:record(data.url)}};
  };
  vm.runInContext(source,vm.createContext({window,document,location,fetch,URL,URLSearchParams,Blob,Map,Set,Date,
    setTimeout:(fn,ms)=>{waits.push(ms);return setTimeout(fn,ms===1000?5:ms)},clearTimeout,
    crypto:{randomUUID:()=>String(++serial).padStart(32,'0')},Option:function(text,value){const node=new Element('option',text);node.value=value;return node}}));
  return {el,state,calls,requests,waits,init:()=>window.initJobLeads(),read:()=>el('AutoFill').click()};
}
(async()=>{
  const good=fixture();await good.init();good.state.publicError='';good.el('url').value=url;await good.read();
  assert.equal(good.el('role').value,'Finance Manager');assert.equal(good.calls.length,0,'public success never probes/opens browser');
  for(const code of ['JOB_AD_UNAVAILABLE','JOB_AD_RATE_LIMITED']){
    const f=fixture();await f.init();f.state.publicError=code;f.el('url').value=url;
    f.el('company').value='Manual Company';f.el('contact').value='Manual Contact';f.el('notes').value='Keep my notes';
    f.el('status').value='contacted';f.el('follow_up').value='2026-11-01';f.el('folder').value='Priority';
    f.el('notes').handlers.input();await f.read();
    assert.equal(f.requests.length,1,'public request is never replayed');
    assert.deepEqual(f.calls.map(call=>call.action),['jobStatus','jobFromLink']);
    assert.equal(f.calls[1].args.url,url);assert(f.waits.includes(1000),'unavailable companion probe is short');
    assert.equal(f.el('role').value,'Finance Manager');assert.equal(f.el('description').value,'Captured description');
    assert.equal(f.el('company').value,'Manual Company');assert.equal(f.el('contact').value,'Manual Contact');
    assert.equal(f.el('notes').value,'Keep my notes');assert.equal(f.el('status').value,'contacted');
    assert.equal(f.el('follow_up').value,'2026-11-01');assert.equal(f.el('folder').value,'Priority');
    assert.match(f.el('Message').textContent,/using your connected Chrome companion/);assert(!f.el('Save').disabled);
  }
  for(const patch of [{ready:false},{busy:true},{noReply:true},{captureFail:true},{mismatch:true}]){
    const f=fixture();await f.init();Object.assign(f.state,patch);f.el('url').value=url;
    f.el('notes').value='Keep draft';f.el('notes').handlers.input();await f.read();
    assert.equal(f.requests.length,1);assert.equal(f.el('role').value,'');assert.equal(f.el('notes').value,'Keep draft');
    assert.match(f.el('Message').textContent,/draft has been kept/);assert.equal(f.el('Save').disabled,false);
    assert(f.calls.filter(call=>call.action==='jobFromLink').length<=1,'no repeated browser capture');
    if(patch.busy||patch.ready===false||patch.noReply){assert.equal(f.calls.length,1);assert.equal(f.el('BrowserSetup').open,true)}
  }
  for(const code of ['JOB_AD_BUSY','JOB_LEADS_STORAGE','CSRF_FAILED','CVSTUDIO_ERROR']){
    const f=fixture();await f.init();f.state.publicError=code;f.el('url').value=url;await f.read();assert.equal(f.calls.length,0,code+' must not trigger fallback');
  }
  const switched=fixture();await switched.init();switched.state.publicError='';switched.el('url').value=url;await switched.read();
  switched.el('notes').value='Old job notes';switched.el('folder').value='Priority';switched.el('url').value=other;
  switched.state.publicError='JOB_AD_RATE_LIMITED';switched.state.captureFail=true;await switched.read();
  assert.equal(switched.el('url').value,url);assert.equal(switched.el('notes').value,'Old job notes');
  switched.state.captureFail=false;switched.el('url').value=other;await switched.read();
  assert.equal(switched.el('url').value,other);assert.equal(switched.el('notes').value,'');assert.equal(switched.el('folder').value,'Priority');assert.equal(switched.el('status').value,'new');
  const refresh=fixture();await refresh.init();refresh.el('url').value=url;refresh.el('description').value='Existing full content';
  refresh.state.empty=true;await refresh.el('RefreshContent').click();assert.equal(refresh.el('description').value,'Existing full content');
  console.log('Job read fallback: public success, eligible failures, one bound capture, quick disconnected probe, busy isolation, failure/identity/draft protection and refresh safety passed');
})().catch(error=>{console.error(error);process.exitCode=1});
