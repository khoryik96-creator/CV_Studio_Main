const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
class Element {
  constructor(tagName='div',textContent=''){Object.assign(this,{tagName,textContent,value:'',children:[],handlers:{},disabled:false,checked:false,hidden:false,dataset:{}})}
  addEventListener(type,fn){this.handlers[type]=fn} append(...values){this.children.push(...values)}
  appendChild(value){this.children.push(value);return value} replaceChildren(...values){this.children=values}
  setAttribute(name,value){this[name]=value} focus(){} scrollIntoView(){}
  querySelectorAll(tag){return this.children.flatMap(child=>[...(child.tagName===tag?[child]:[]),...child.querySelectorAll(tag)])}
  click(){return this.handlers.click?.()} get selectedOptions(){return this.children.filter(row=>row.value===this.value)}
}
const job=(number,patch={})=>({url:'https://www.linkedin.com/jobs/view/'+number,company:'Example Finance',role:'Finance Manager',location:'Penang',date_posted:'2026-10-02',description:'Search summary '+number,contact:'Never copy',notes:'Never copy',status:'won',...patch});
const a=job('1111111110'),b=job('1111111111'),c=job('1111111112');
function fixture(){
  const ids=new Map(),events={},calls=[],requests=[];
  const document={getElementById:id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id)},createElement:tag=>new Element(tag),createTextNode:text=>new Element('#text',text),addEventListener:(name,fn)=>events[name]=fn};
  const el=name=>document.getElementById('jobLeads'+name),location={origin:'http://127.0.0.1:5000',search:''};
  el('FolderFilter').value='*';el('SearchPages').value='2';el('SearchMode').value='new';el('SearchQuery').value='finance';el('SearchLocation').value='Malaysia';
  let serial=0;
  const state={page:0,scroll:0,totalPages:2,hold:false,held:null,failSave:'',failRead:false,many:false,connected:true,searchCapable:true,busy:false,
    records:[{...b,id:'e'.repeat(32),revision:2,contact:'Manual Contact',notes:'Important saved notes',status:'contacted',description:'Saved full content',created_at:'2026-10-01T00:00:00Z',folder:'',deleted:false,follow_up:''}]};
  const window={addEventListener:(name,fn)=>events[name]=fn,confirm:()=>true,postMessage:message=>{
    calls.push(message);const reply=(value,error)=>events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',id:message.id,channel:message.channel,...(error?{error}:{result:value})}});
    if(message.action==='jobStatus')return reply({connected:state.connected,job_search:state.searchCapable,busy:state.busy});
    if(message.action==='jobSearchTabs')return reply([{id:20,title:'Open filtered jobs',url:'https://www.linkedin.com/jobs/search/?keywords=finance&f_WT=2'}]);
    if(message.action==='jobSearchBegin'){state.page=0;state.scroll=0;return reply({tab_id:20})}
    if(message.action==='end')return reply(true);
    if(message.action==='jobFromLink')return state.failRead?reply(null,'Synthetic layout changed'):reply({...c,url:message.args.url,description:'Full captured job ad',description_html:'<p><b>Full captured job ad</b></p>'});
    if(message.action==='read'){
      if(message.args.method==='nextJobSearch'){state.page++;state.scroll=0;return reply(true)}
      if(message.args.method==='scrollJobSearch'){state.scroll++;return reply(true)}
      const jobs=state.many?[job(String(2222222200+state.page))]:state.page===0?state.scroll?[a,b]:[a]:[b,c,job('999',{url:'https://attacker.invalid/jobs/view/999'})];
      const snapshot={jobs,signature:jobs.map(row=>row.url).join('|'),hasNext:state.page+1<state.totalPages,atBottom:state.many||state.page>0||!!state.scroll};
      if(state.hold&&state.page===1){state.held=()=>reply(snapshot);return}
      return reply(snapshot);
    }
    throw Error('Unexpected companion command '+message.action);
  }};
  const fetch=async(endpoint,options)=>{
    assert.equal(endpoint,'/job-leads','search must not call a paid route');
    if(!options?.body)return {ok:true,json:async()=>({records:structuredClone(state.records),folders:['Priority']})};
    const data=JSON.parse(options.body);requests.push(data);
    if(data.action==='format_content')return {ok:true,json:async()=>({description_rich:[{tag:'p',children:[{tag:'strong',children:[{text:data.description}]}]}]})};
    assert.equal(data.action,'save');
    if(data.record.url===state.failSave)return {ok:false,json:async()=>({error:'Synthetic storage limit'})};
    const duplicate=state.records.find(row=>row.url===data.record.url);
    if(duplicate)return {ok:true,json:async()=>({record:duplicate,duplicate:true})};
    const record={...data.record,id:String(++serial).padStart(32,'0'),revision:1,created_at:'2026-10-20T00:00:00Z',deleted:false};
    state.records.push(record);return {ok:true,json:async()=>({record,duplicate:false})};
  };
  const context=vm.createContext({window,document,location,fetch,URL,URLSearchParams,Blob,Map,Set,Date,crypto:{randomUUID:()=>String(++serial).padStart(32,'0')},
    setTimeout:(fn,ms)=>setTimeout(fn,ms===350?0:ms),clearTimeout,Option:function(text,value){const node=new Element('option',text);node.value=value;return node}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-leads.js'),'utf8'),context);
  return {el,state,calls,requests,init:()=>window.initJobLeads()};
}
(async()=>{
  const f=fixture();await f.init();
  f.el('url').value='https://www.linkedin.com/jobs/view/7777777777';f.el('company').value='Unsaved company';f.el('role').value='Unsaved role';
  f.el('notes').value='Keep unsaved notes';f.el('contact').value='Unsaved Contact';f.el('notes').handlers.input();
  await f.el('SearchStart').click();assert.match(f.el('SearchCount').textContent,/3 found/);
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
  const badCalls=f.calls.length;f.el('SearchPages').value='16';await f.el('SearchStart').click();assert.equal(f.calls.length,badCalls);
  f.el('SearchPages').value='2';f.el('SearchMode').value='open';f.el('SearchMode').handlers.change();await f.el('SearchRefresh').click();
  f.el('SearchSource').value='20';f.el('SearchQuery').value='';await f.el('SearchStart').click();
  assert(f.calls.some(call=>call.action==='jobSearchBegin'&&call.args.use_open&&call.args.source_tab_id===20));
  for(const patch of [{connected:false},{searchCapable:false},{busy:true}]){
    Object.assign(f.state,{connected:true,searchCapable:true,busy:false},patch);
    const before=f.calls.length;await f.el('SearchStart').click();
    assert.deepEqual(f.calls.slice(before).map(call=>call.action),['jobStatus'],'unavailable/busy/old companions never open or end a search');
    assert.match(f.el('SearchCount').textContent,/3 found/,'readiness failures keep the prior results');
    assert.equal(f.el('SearchStart').disabled,false);
  }
  const stopped=fixture();await stopped.init();stopped.state.hold=true;const running=stopped.el('SearchStart').click();
  for(let attempt=0;attempt<50&&!stopped.state.held;attempt++)await new Promise(resolve=>setTimeout(resolve,5));
  assert(stopped.state.held);await stopped.el('SearchStop').click();stopped.state.held();await running;
  assert.match(stopped.el('SearchStatus').textContent,/Stopped/);assert.match(stopped.el('SearchCount').textContent,/2 found/);
  assert.equal(stopped.requests.length,0,'stop never saves results');assert.equal(stopped.el('SearchStart').disabled,false);
  const many=fixture();await many.init();many.state.many=true;many.state.totalPages=15;many.el('SearchPages').value='15';await many.el('SearchStart').click();
  assert.match(many.el('SearchCount').textContent,/15 found/);assert.equal(many.calls.filter(call=>call.args.method==='nextJobSearch').length,14);
  console.log('Job search UI: multi-page scroll/deduplication, review-only capture, full previews, selected folder import, partial failure/retry, existing notes/drafts, open filters, Stop and 15-page bounds passed');
})().catch(error=>{console.error(error);process.exitCode=1});
