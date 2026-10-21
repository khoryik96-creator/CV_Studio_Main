const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
class Element {
  constructor(tag='div'){Object.assign(this,{tagName:tag,value:'',textContent:'',children:[],events:{},checked:false,disabled:false,open:false})}
  addEventListener(type,fn){(this.events[type]??=[]).push(fn)}
  append(...items){this.children.push(...items)} appendChild(item){this.append(item);return item}
  replaceChildren(...items){this.children=items} focus(){this.focused=true}
  get options(){return this.children} async change(){for(const fn of this.events.change||[])await fn()}
}
const people={id:2,url:'https://www.linkedin.com/search/results/people/?keywords=SAP',title:'SAP people | LinkedIn',lastAccessed:20};
const previous={name:'Previous candidate',url:'https://www.linkedin.com/in/previous',score:80,evidence:['Previous evidence'],unknowns:[]};
function fixture(){
  const ids=new Map(),events={},calls=[],requests=[];
  const el=name=>{if(!ids.has(name))ids.set(name,new Element());return ids.get(name)};
  el('Mode').value='auto';el('Pages').value='10';el('Calls').value='35';el('OpenSearch').checked=true;
  const state={tabs:[people],connected:true,hold:false,held:null,failStart:false,page:1};
  let serial=0;
  const run={id:'a'.repeat(32),calls:0,max_calls:35,tokens:0,usage_complete:true,stopped:false};
  const candidate={id:'p0',name:'Sample candidate',url:'https://www.linkedin.com/in/sample',text:'SAP finance experience',score:85,evidence:['SAP finance experience'],unknowns:['Availability']};
  const location={origin:'http://127.0.0.1:5000',search:''};
  const window={addEventListener:(name,fn)=>events[name]=fn,postMessage:message=>{
    calls.push(message);
    const reply=(result,error)=>events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:message.channel,id:message.id,...(error?{error}:{result})}});
    if(!state.connected)return reply(null,'The browser action stopped. Reconnect the companion or check the LinkedIn page.');
    if(message.action==='tabs'){if(state.hold){state.held=()=>reply(state.tabs);return}return reply(state.tabs)}
    if(message.action==='begin'||message.action==='end'||message.action==='navigate')return reply(true);
    if(message.action==='create')return reply(10);
    if(message.action==='read')return reply(message.args.method==='readProfile'?{text:candidate.text,name:candidate.name}:message.args.method==='search'?true:{profiles:[candidate],signature:'one',hasNext:false,paginationKnown:true});
    throw Error('Unexpected browser command '+message.action);
  }};
  const saved=JSON.stringify({run:null,results:[previous]});
  const context=vm.createContext({window,document:{getElementById:id=>el(id.replace(/^liSourcer/,'')),createElement:tag=>new Element(tag)},location,
    sessionStorage:{getItem:()=>saved,setItem:()=>{}},crypto:{randomUUID:()=>String(++serial).padStart(32,'0')},
    setTimeout:(fn,ms)=>setTimeout(fn,[500,1000,1500,2000].includes(ms)?0:ms),clearTimeout,AbortController,URL,URLSearchParams,Blob,
    markTabRunning:()=>1,finishTabRun:()=>{},responseHasPaidUsage:()=>false,
    fetch:async(url,options)=>{assert.equal(url,'/linkedin-sourcer');const body=options?.body?JSON.parse(options.body):null;if(body)requests.push(body);
      if(!body)return {ok:true,json:async()=>({configured:true,run:null})};
      if(body.action==='start'&&state.failStart)return {ok:false,json:async()=>({error:'Synthetic start rejected'})};
      if(body.action==='stop')run.stopped=true;
      return {ok:true,json:async()=>({run:{...run},...(body.action==='plan'?{plan:{query:'SAP'}}:{}),...(body.action==='review'?{candidates:[candidate]}:{})})};}
  });
  for(const file of ['linkedin-sourcer-core.js','linkedin-sourcer.js']){vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio',file),'utf8'),context);context.CVLinkedinCore=window.CVLinkedinCore;}
  return {el,state,calls,requests,init:async()=>{await window.initLinkedinSourcer();await new Promise(resolve=>setTimeout(resolve,0))},
    start:()=>window.startLinkedinSourcer(),stop:()=>window.stopLinkedinSourcer()};
}
(async()=>{
  const f=fixture();f.state.tabs=[{id:9,url:'https://www.linkedin.com/jobs/search/',title:'Jobs',lastAccessed:99},{id:8,url:previous.url,title:'Profile',lastAccessed:100},people];await f.init();
  assert.equal(f.el('Source').value,'2',f.el('Connection').textContent+' / '+f.el('Status').textContent);assert.match(f.el('Connection').textContent,/Connected.*SAP people.*keeping its filters/);assert.equal(f.el('Options').open,false);
  assert.equal(f.requests.length,0,'tab discovery never starts AI work');assert.equal(f.el('Consent').checked,false,'permission stays explicit');
  f.el('Brief').value='Finance managers in Malaysia';await f.start();assert.match(f.el('Status').textContent,/Tick.*Use DeepSeek/);assert(f.el('Consent').focused);assert.equal(f.requests.length,0);
  f.el('Consent').checked=true;await f.start();
  assert.equal(f.requests[0].action,'start');assert.equal(f.requests[0].mode,'standard');assert.equal(f.requests[0].confirm_paid,true);assert.equal(f.requests[0].use_open_search,true);
  assert.equal(f.el('Count').textContent,1);assert.match(f.el('Status').textContent,/last result page/);assert.equal(f.el('Start').disabled,false);
  assert.equal(f.calls.filter(call=>call.action==='navigate').length,0,'default preserves the open search filters');
  const legacy=fixture();legacy.state.tabs=[{...people,lastAccessed:undefined,active:false},{...people,id:5,title:'Active compatible search',lastAccessed:undefined,active:true}];await legacy.init();
  assert.equal(legacy.el('Source').value,'5','without recency metadata an active compatible search wins over query order');
  const recent=fixture();recent.state.tabs=[{...people,id:6,lastAccessed:10,active:true},people];await recent.init();
  assert.equal(recent.el('Source').value,'2','real recency metadata remains authoritative when available');
  const begin=f.calls.find(call=>call.action==='begin');assert.equal(begin.args.source_tab_id,2);assert.equal(begin.args.mode,'standard');
  for(const [title,mode] of [['Recruiter Lite search','lite'],['Recruiter search','recruiter']]){
    const g=fixture();g.state.tabs=[{id:7,url:'https://www.linkedin.com/talent/search',title}];await g.init();g.el('Brief').value='SAP finance managers';g.el('Consent').checked=true;await g.start();assert.equal(g.requests[0].mode,mode);
  }
  const missing=fixture();missing.state.tabs=[];await missing.init();missing.el('Brief').value='SAP finance';missing.el('Consent').checked=true;await missing.start();
  assert.equal(missing.requests.length,0);assert.equal(missing.el('Count').textContent,1,'missing tabs preserve the previous list');assert(missing.el('Options').open);
  const disconnected=fixture();disconnected.state.connected=false;await disconnected.init();disconnected.el('Brief').value='SAP finance';disconnected.el('Consent').checked=true;await disconnected.start();
  assert.equal(disconnected.requests.length,0);assert.equal(disconnected.el('Count').textContent,1);assert(disconnected.el('Setup').open);assert.match(disconnected.el('Connection').textContent,/toolbar icon/);
  const chosen=fixture();chosen.state.tabs=[people,{...people,id:4,title:'Older filtered search',lastAccessed:1}];await chosen.init();chosen.el('Source').value='4';chosen.el('Mode').value='standard';await chosen.el('Source').change();
  chosen.el('Brief').value='SAP finance';chosen.el('Consent').checked=true;await chosen.start();assert.equal(chosen.calls.find(call=>call.action==='begin').args.source_tab_id,4,'a manual source selection is retained');
  const rejected=fixture();await rejected.init();rejected.state.failStart=true;rejected.el('Brief').value='SAP finance';rejected.el('Consent').checked=true;await rejected.start();assert.equal(rejected.el('Count').textContent,1);assert.match(rejected.el('Status').textContent,/Synthetic start rejected/);
  const cancelled=fixture();await cancelled.init();cancelled.state.hold=true;cancelled.el('Brief').value='SAP finance';cancelled.el('Consent').checked=true;const starting=cancelled.start();
  assert(cancelled.state.held);await cancelled.stop();cancelled.state.held();await starting;assert.equal(cancelled.requests.length,0,'Stop during readiness sends no paid action');assert.equal(cancelled.el('Count').textContent,1);
  const invalid=fixture();await invalid.init();invalid.el('Brief').value='SAP finance';invalid.el('Consent').checked=true;invalid.el('Pages').value='16';await invalid.start();assert.equal(invalid.requests.length,0);assert(invalid.el('Options').open);
  console.log('Sourcer UI: automatic tabs/modes, explicit consent, preserved filters and prior results, missing/disconnected readiness, manual selection, rejected start and Stop before paid work passed');
})().catch(error=>{console.error(error);process.exitCode=1});
