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
function fixture(reuse=true){
  const ids=new Map(),events={},calls=[],requests=[];
  const el=name=>{if(!ids.has(name))ids.set(name,new Element());return ids.get(name)};
  el('Mode').value='auto';el('Pages').value='10';el('Calls').value='35';el('OpenSearch').checked=reuse;
  const state={tabs:[people],connected:true,hold:false,held:null,failStart:false,page:1,opened:0,missingReads:0,readCount:0};
  let serial=0;
  const run={id:'a'.repeat(32),calls:0,max_calls:35,tokens:0,usage_complete:true,stopped:false};
  const candidate={id:'p0',name:'Sample candidate',url:'https://www.linkedin.com/in/sample',text:'SAP finance experience',score:85,evidence:['SAP finance experience'],unknowns:['Availability']};
  const location={origin:'http://127.0.0.1:5000',search:''};
  const window={addEventListener:(name,fn)=>events[name]=fn,postMessage:message=>{
    calls.push(message);
    const reply=(result,error)=>events.message({source:window,origin:location.origin,data:{type:'CVSTUDIO_LINKEDIN_RESPONSE',channel:message.channel,id:message.id,...(error?{error}:{result})}});
    if(!state.connected)return reply(null,'The browser action stopped. Reconnect the companion or check the LinkedIn page.');
    if(message.action==='tabs'){if(state.hold){state.held=()=>reply(state.tabs);return}return reply(state.tabs)}
    if(message.action==='reloadCompanion')return reply(state.reloadResult||{current:true});
    if(message.action==='jobStatus')return reply({connected:true,profile_browsing_revision:state.oldBrowsingCompanion?0:1,people_results_revision:state.oldResultsCompanion?0:1,people_country_revision:state.oldCountryCompanion?0:1,companion_update_revision:state.oldUpdateCompanion?0:1});
    if(message.action==='openPeopleSearch'){
      if(state.oldCompanion)return reply(null,'Unsupported browser action.');
      const tab={...people,id:20+(++state.opened),url:'https://www.linkedin.com/search/results/people/',title:'New People search'};
      state.tabs.push(tab);
      if(state.holdOpen){state.held=()=>reply(tab);return}
      return reply(tab);
    }
    if(message.action==='begin'){if(state.failBegin)return reply(null,'Synthetic reservation failed');if(state.holdBegin){state.beginReply=()=>reply(true);return;}return reply(true);}
    if(message.action==='end'||message.action==='navigate')return reply(true);
    if(message.action==='create')return reply(10);
    if(message.action==='read'){
      state.readCount++;
      if(message.args.method==='setCountry'){if(state.holdCountry){state.countryReply=()=>reply(true);return;}return reply(true);}
      if(state.missingReads-- > 0 || state.missingMethod===message.args.method)return reply(null);
      return reply(message.args.method==='readProfile'?{text:candidate.text,name:candidate.name}:['search','next'].includes(message.args.method)?true:{profiles:[candidate],signature:'one',hasNext:!!state.morePages,paginationKnown:true});
    }
    throw Error('Unexpected browser command '+message.action);
  }};
  const saved=JSON.stringify({run:null,results:[previous]});
  const context=vm.createContext({window,document:{getElementById:id=>el(id.replace(/^liSourcer/,'')),createElement:tag=>new Element(tag)},location,
    sessionStorage:{getItem:()=>saved,setItem:()=>{}},crypto:{randomUUID:()=>String(++serial).padStart(32,'0')},
    setTimeout:(fn,ms)=>setTimeout(fn,[500,1000,1500,2000].includes(ms)?0:ms),clearTimeout,AbortController,URL,URLSearchParams,Blob,
    markTabRunning:()=>1,finishTabRun:()=>{},responseHasPaidUsage:()=>false,
    navigator:{clipboard:{writeText:async text=>{if(state.clipboardFail)throw Error('Unavailable');state.copied=text;}}},
    fetch:async(url,options)=>{if(url==='/linkedin-sourcer?action=companion_setup')return {ok:true,json:async()=>({folder:'Bundled companion folder',version:'24.6.480'})};assert.equal(url,'/linkedin-sourcer');const body=options?.body?JSON.parse(options.body):null;if(body)requests.push(body);
      if(!body)return {ok:true,json:async()=>({configured:true,run:null})};
      if(body.action==='start'&&state.failStart)return {ok:false,json:async()=>({error:'Synthetic start rejected'})};
      if(body.action==='plan'&&state.holdPlan)await new Promise(resolve=>state.planReply=resolve);
      if(body.action==='stop')run.stopped=true;
      return {ok:true,json:async()=>({run:{...run},...(body.action==='plan'?{plan:{query:'SAP',country:state.planCountry||''}}:{}),...(body.action==='review'?{candidates:[candidate]}:{})})};}
  });
  for(const file of ['linkedin-sourcer-core.js','linkedin-sourcer.js']){vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio',file),'utf8'),context);context.CVLinkedinCore=window.CVLinkedinCore;}
  return {el,state,calls,requests,copy:window.copyLinkedinCompanionFolder,reload:window.reloadLinkedinCompanion,init:async()=>{await window.initLinkedinSourcer();await new Promise(resolve=>setTimeout(resolve,0))},
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
  const planning=fixture();await planning.init();planning.el('Brief').value='SAP finance';planning.el('Consent').checked=true;planning.state.holdPlan=true;
  const planningRun=planning.start();await new Promise(resolve=>setImmediate(resolve));assert(planning.state.planReply);
  assert(planning.calls.some(c=>c.action==='begin'),'worker ownership must be reserved before the paid plan is pending');
  planning.state.planReply();await planningRun;assert.equal(planning.calls.filter(c=>c.action==='begin').length,1,'reservation does not reset budgets after planning');
  const noReservation=fixture();await noReservation.init();noReservation.el('Brief').value='SAP finance';noReservation.el('Consent').checked=true;noReservation.state.failBegin=true;await noReservation.start();
  assert.equal(noReservation.requests.filter(r=>r.action==='plan').length,0,'failed reservation sends no paid plan');
  const stopReservation=fixture();await stopReservation.init();stopReservation.el('Brief').value='SAP finance';stopReservation.el('Consent').checked=true;stopReservation.state.holdBegin=true;
  const reservedRun=stopReservation.start();await new Promise(resolve=>setImmediate(resolve));assert(stopReservation.state.beginReply);await stopReservation.stop();stopReservation.state.beginReply();await reservedRun;
  assert.equal(stopReservation.requests.filter(r=>r.action==='plan').length,0,'Stop during reservation sends no paid plan');assert(stopReservation.calls.some(c=>c.action==='end'),'a late reservation acknowledgement is cleaned up');
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
  assert.equal(disconnected.requests.length,0);assert.equal(disconnected.el('Count').textContent,1);assert(disconnected.el('Setup').open);assert.match(disconnected.el('Connection').textContent,/connects automatically/);
  const setup=fixture(),note=new Element(),button={disabled:false,parentElement:{querySelector:()=>note}};
  await setup.copy(button);assert.equal(setup.state.copied,'Bundled companion folder');assert.match(note.textContent,/Folder copied/);assert.equal(button.disabled,false);
  setup.state.clipboardFail=true;await setup.copy(button);assert.equal(note.textContent,'Bundled companion folder','clipboard denial retains a selectable setup path');
  await setup.reload(button);assert.match(note.textContent,/up to date/);assert.equal(setup.calls.at(-1).action,'reloadCompanion');assert.equal(setup.requests.length,0,'setup never starts paid work');
  setup.state.reloadResult={reloading:true};await setup.reload(button);assert.match(note.textContent,/reloading.*Refresh/);
  setup.state.oldUpdateCompanion=true;const reloads=setup.calls.filter(c=>c.action==='reloadCompanion').length;await setup.reload(button);assert.match(note.textContent,/Set up companion once/);assert.equal(setup.calls.filter(c=>c.action==='reloadCompanion').length,reloads,'legacy extensions receive migration guidance without an unsupported reload');
  const chosen=fixture();chosen.state.tabs=[people,{...people,id:4,title:'Older filtered search',lastAccessed:1}];await chosen.init();chosen.el('Source').value='4';chosen.el('Mode').value='standard';await chosen.el('Source').change();
  chosen.el('Brief').value='SAP finance';chosen.el('Consent').checked=true;await chosen.start();assert.equal(chosen.calls.find(call=>call.action==='begin').args.source_tab_id,4,'a manual source selection is retained');
  const rejected=fixture();await rejected.init();rejected.state.failStart=true;rejected.el('Brief').value='SAP finance';rejected.el('Consent').checked=true;await rejected.start();assert.equal(rejected.el('Count').textContent,1);assert.match(rejected.el('Status').textContent,/Synthetic start rejected/);
  const cancelled=fixture();await cancelled.init();cancelled.state.hold=true;cancelled.el('Brief').value='SAP finance';cancelled.el('Consent').checked=true;const starting=cancelled.start();
  assert(cancelled.state.held);await cancelled.stop();cancelled.state.held();await starting;assert.equal(cancelled.requests.length,0,'Stop during readiness sends no paid action');assert.equal(cancelled.el('Count').textContent,1);
  const invalid=fixture();await invalid.init();invalid.el('Brief').value='SAP finance';invalid.el('Consent').checked=true;invalid.el('Pages').value='16';await invalid.start();assert.equal(invalid.requests.length,0);assert(invalid.el('Options').open);
  const fresh=fixture(false);fresh.state.tabs=[];await fresh.init();assert.equal(fresh.state.opened,0,'panel initialization never opens tabs');
  fresh.el('Brief').value='SAP finance';await fresh.start();assert.equal(fresh.state.opened,0,'consent is required before opening a source');
  fresh.el('Consent').checked=true;await fresh.start();await fresh.start();
  assert.equal(fresh.state.opened,2,'each Start opens a separate People search, even if one now exists');
  assert.deepEqual(fresh.calls.filter(c=>c.action==='begin').map(c=>c.args.source_tab_id),[21,22]);
  assert(fresh.requests.filter(r=>r.action==='start').every(r=>r.mode==='standard'&&!r.use_open_search));
  assert(fresh.calls.filter(c=>c.action==='navigate').every(c=>/^https:\/\/www\.linkedin\.com\/search\/results\/people\/\?keywords=SAP$/.test(c.args.url)));
  const old=fixture(false);old.state.oldCompanion=true;await old.init();old.el('Brief').value='SAP finance';old.el('Consent').checked=true;await old.start();
  assert.equal(old.requests.length,0);assert.equal(old.el('Count').textContent,1);assert.match(old.el('Status').textContent,/latest companion/i);
  const oldCountry=fixture(false);oldCountry.state.oldCountryCompanion=true;await oldCountry.init();oldCountry.el('Brief').value='SAP in Malaysia';oldCountry.el('Consent').checked=true;await oldCountry.start();
  assert.equal(oldCountry.requests.length,0,'country capability is checked before any paid planning');assert.match(oldCountry.el('Status').textContent,/companion update/i);
  const location=fixture(false);await location.init();location.state.planCountry='Malaysia';location.el('Brief').value='SAP FICO in Malaysia';location.el('Consent').checked=true;await location.start();
  assert(location.calls.some(c=>c.action==='read'&&c.args.method==='setCountry'&&c.args.values[0]==='Malaysia'));assert.match(location.el('Query').textContent,/Location filter: Malaysia/);
  assert.equal(new URL(location.calls.find(c=>c.action==='navigate').args.url).searchParams.get('keywords'),'SAP');assert.equal(location.el('Count').textContent,1);
  const stopCountry=fixture(false);await stopCountry.init();stopCountry.state.planCountry='Malaysia';stopCountry.state.holdCountry=true;stopCountry.el('Brief').value='SAP FICO in Malaysia';stopCountry.el('Consent').checked=true;
  const countryRun=stopCountry.start();for(let i=0;i<30&&!stopCountry.state.countryReply;i++)await new Promise(resolve=>setTimeout(resolve,0));assert(stopCountry.state.countryReply);await stopCountry.stop();stopCountry.state.countryReply();await countryRun;
  assert.equal(stopCountry.requests.filter(r=>r.action==='review').length,0,'Stop during native location selection sends no scoring request');
  const opening=fixture(false);await opening.init();opening.state.holdOpen=true;opening.el('Brief').value='SAP finance';opening.el('Consent').checked=true;const openingRun=opening.start();
  await new Promise(resolve=>setTimeout(resolve,0));assert(opening.state.held);await opening.stop();opening.state.held();await openingRun;
  assert.equal(opening.requests.length,0,'Stop while opening a tab prevents the first paid action');
  const transient=fixture();await transient.init();transient.el('Brief').value='SAP finance';transient.el('Consent').checked=true;transient.state.missingReads=1;await transient.start();
  assert.match(transient.el('Status').textContent,/last result page/);assert.equal(transient.requests.filter(r=>r.action==='plan').length,1);
  const unavailable=fixture();await unavailable.init();unavailable.el('Brief').value='SAP finance';unavailable.el('Consent').checked=true;unavailable.state.missingReads=100;await unavailable.start();
  assert.match(unavailable.el('Status').textContent,/LinkedIn.*read|LinkedIn.*reader/);assert.equal(unavailable.state.readCount,30,'missing results have a bounded read-only retry');
  assert.equal(unavailable.requests.filter(r=>r.action==='plan').length,1);assert.equal(unavailable.requests.filter(r=>r.action==='review').length,0);assert.equal(unavailable.requests.filter(r=>r.action==='stop').length,1);
  assert(unavailable.calls.some(c=>c.action==='end'),'reader failure cleans up the browser run');
  for(const reuse of [true,false]){
    const outdated=fixture(reuse);await outdated.init();outdated.el('Brief').value='SAP finance';outdated.el('Consent').checked=true;outdated.state.oldResultsCompanion=true;await outdated.start();
    assert.equal(outdated.requests.filter(r=>r.action==='start'||r.action==='plan').length,0,'an old People reader is rejected before any paid work');assert.match(outdated.el('Status').textContent,/latest companion update/);
  }
  for(const mode of ['standard','lite','recruiter']){
    const outdated=fixture(mode!=='standard');outdated.state.tabs=[{id:7,url:mode==='standard'?'https://www.linkedin.com/search/results/people/':'https://www.linkedin.com/talent/search',title:'Recruiter search'}];await outdated.init();
    outdated.el('Mode').value=mode;outdated.el('Brief').value='SAP finance';outdated.el('Consent').checked=true;outdated.state.oldBrowsingCompanion=true;await outdated.start();
    assert.equal(outdated.requests.length,0,'old tab policy stops before paid work in '+mode);assert(!outdated.calls.some(c=>c.action==='begin'));assert.match(outdated.el('Status').textContent,/keep browsing safely/);
  }
  const ambiguousSearch=fixture(false);ambiguousSearch.el('Mode').value='lite';ambiguousSearch.state.tabs=[{id:7,url:'https://www.linkedin.com/talent/search',title:'Recruiter Lite'}];
  await ambiguousSearch.init();ambiguousSearch.el('Brief').value='SAP finance';ambiguousSearch.el('Consent').checked=true;ambiguousSearch.state.missingMethod='search';await ambiguousSearch.start();
  assert.equal(ambiguousSearch.calls.filter(c=>c.action==='read'&&c.args.method==='search').length,1,'an ambiguous search submission is never replayed');
  assert.equal(ambiguousSearch.requests.filter(r=>r.action==='review').length,0);
  const ambiguousNext=fixture();await ambiguousNext.init();ambiguousNext.el('Brief').value='SAP finance';ambiguousNext.el('Consent').checked=true;ambiguousNext.state.morePages=true;ambiguousNext.state.missingMethod='next';await ambiguousNext.start();
  assert.equal(ambiguousNext.calls.filter(c=>c.action==='read'&&c.args.method==='next').length,1,'an ambiguous next-page click is never replayed');
  assert.match(ambiguousNext.el('Status').textContent,/did not confirm/);
  assert(!/id="liSourcerOpenSearch"[^>]*\bchecked\b/.test(fs.readFileSync(path.join(__dirname,'../index.html'),'utf8')),'fresh searches are the actual UI default');
  console.log('Sourcer UI: fresh sources on every Start, reuse/Recruiter options, consent, null-read recovery/bounds, non-replay, prior results and Stop before paid work passed');
})().catch(error=>{console.error(error);process.exitCode=1});
