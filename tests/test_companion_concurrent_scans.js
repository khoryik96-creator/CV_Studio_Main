const assert=require('assert/strict');
const {hrFixture}=require('./test_linkedin_company_hr');
const first='https://www.linkedin.com/in/profile-scan',second='https://www.linkedin.com/in/profile-next',profileRun='c'.repeat(32);
async function setup(){
 const f=hrFixture();await f.arm();
 const prior=f.state.onScript;f.state.onScript=args=>{
  if(args.args?.[0]==='readSearch')return [{result:{profiles:[{url:first},{url:second}],signature:'profile-results',hasNext:true}}];
  if(args.args?.[0]==='readProfile')return [{result:{text:'Observed fictional professional evidence'}}];
  if(args.args?.[0]==='next')return [{result:true}];
  return prior(args);
 };
 const rpc=(scope,action,args={})=>f.rpc(action,args,undefined,scope);
 const begin=()=>rpc('profiles','begin',{run_id:profileRun,source_tab_id:3,mode:'standard',max_pages:2});
 return {f,rpc,begin,profiles:(action,args={})=>rpc('profiles',action,{run_id:profileRun,...args}),leads:(action,args={})=>rpc('leads',action,{run_id:f.run,...args})};
}
const cases=[
 ['fresh profile lookups cannot inherit delayed events from the previous profile',async()=>{
  const {f,begin,profiles}=await setup();await begin();await profiles('read',{tab_id:3,method:'readSearch',values:['standard']});const old=(await profiles('create',{url:first})).result;
  const moved=(await profiles('navigate',{tab_id:old,url:second,fresh:true})).result;assert.notEqual(moved.tab_id,old);assert(!f.tabs.has(old));
  await f.hooks().updated(old,{url:first+'/'});await f.hooks().removed(old);
  assert((await profiles('read',{tab_id:moved.tab_id,method:'readProfile',values:[second]})).result.text);await profiles('end');
 }],
 ['independent scans overlap, survive restart, and Stop releases only its own tabs',async()=>{
  const {f,rpc,begin,profiles,leads}=await setup();assert((await begin()).result);assert((await profiles('read',{tab_id:3,method:'readSearch',values:['standard']})).result.profiles);
  const profileId=(await profiles('create',{url:first})).result;
  const source=(await leads('hrBegin',{company_url:'https://www.linkedin.com/company/example/',company:'Example Company',country:'',keywords:'HR',max_pages:2})).result.tab_id;
  await leads('hrRead',{tab_id:source});assert((await leads('hrRead',{tab_id:source})).result.people);
  assert((await rpc('profiles','jobStatus')).result.busy);assert((await rpc('leads','jobStatus')).result.busy);
  f.boot();assert((await profiles('read',{tab_id:profileId,method:'readProfile',values:[first]})).result.text);assert((await leads('hrRead',{tab_id:source})).result.people);
  assert((await profiles('end')).result);assert(!f.tabs.has(profileId));assert((await rpc('leads','jobStatus')).result.busy);assert((await leads('hrRead',{tab_id:source})).result.people);await leads('end');
 }],
 ['HR cleanup, activation, unrelated tab closure and corrupt reads do not affect Sourcer',async()=>{
  const {f,rpc,begin,profiles,leads}=await setup();await begin();await profiles('read',{tab_id:3,method:'readSearch',values:['standard']});const id=(await profiles('create',{url:first})).result;
  const source=(await leads('hrBegin',{company_url:'https://www.linkedin.com/company/example/',company:'Example Company',country:'',keywords:'HR',max_pages:2})).result.tab_id;await leads('hrRead',{tab_id:source});await leads('hrRead',{tab_id:source});await leads('hrJoined',{tab_id:source,url:'https://www.linkedin.com/in/sample'});
  const joinedId=f.state.session.cvstudioLinkedinLeadsSessionV1.connection.hr.joining.tab_id;f.tabs.get(joinedId).active=true;await f.hooks().activated({tabId:joinedId});await f.hooks().removed(999);
  await leads('end');assert(f.tabs.has(joinedId));assert(f.tabs.has(id));assert((await profiles('read',{tab_id:id,method:'readProfile',values:[first]})).result.text);assert(!(await rpc('leads','jobStatus')).result.busy);await profiles('end');
 }],
 ['another scan cannot read, navigate, close, adopt or list the reserved source/profile',async()=>{
  const {f,rpc,begin,profiles,leads}=await setup();await begin();await profiles('read',{tab_id:3,method:'readSearch',values:['standard']});const id=(await profiles('create',{url:first})).result;
  assert((await leads('jobSearchBegin',{use_open:true,source_tab_id:3,max_pages:2})).error);
  assert((await leads('read',{tab_id:id,method:'readProfile',values:[first]})).error);
  assert((await leads('navigate',{tab_id:id,url:second})).error);assert((await leads('end',{run_id:profileRun})).error);assert(f.tabs.has(id));
  assert((await rpc('unknown','jobStatus')).error);assert((await profiles('hrBegin',{})).error);await profiles('end');
 }],
 ['a pending profile read does not prevent HR from starting and finishing',async()=>{
  const {f,begin,profiles,leads}=await setup();await begin();await profiles('read',{tab_id:3,method:'readSearch',values:['standard']});const id=(await profiles('create',{url:first})).result;
  let release,started;const ready=new Promise(resolve=>started=resolve);
  const old=f.state.onScript;f.state.onScript=args=>args.args?.[0]==='readProfile'?new Promise(resolve=>{release=()=>resolve([{result:{text:'Observed professional evidence'}}]);started()}):old(args);
  const reading=profiles('read',{tab_id:id,method:'readProfile',values:[first]});await ready;
  const source=(await leads('hrBegin',{company_url:'https://www.linkedin.com/company/example/',company:'Example Company',country:'',keywords:'HR',max_pages:2})).result.tab_id;assert(Number.isInteger(source));await leads('end');release();assert((await reading).result.text);await profiles('end');
 }],
 ['legacy HR state migrates atomically without resuming or changing budgets',async()=>{
  const {f,leads}=await setup();const source=(await f.beginHR()).result.tab_id;await f.readHR(source);
  const saved=f.state.session.cvstudioLinkedinLeadsSessionV1;delete saved.scope;saved.nextCount=1;delete f.state.session.cvstudioLinkedinLeadsSessionV1;f.state.session.cvstudioLinkedinSessionV1=saved;const before=f.state.created.length;f.boot();
  assert((await leads('hrRead',{tab_id:source})).result.people);assert.equal(f.state.created.length,before);assert.equal(f.state.session.cvstudioLinkedinLeadsSessionV1.nextCount,1);assert.equal(f.state.session.cvstudioLinkedinSessionV1,null);await leads('end');
 }],
 ['scoped readiness, legacy busy state and shared update protection remain distinct',async()=>{
  const {f,rpc,begin,profiles}=await setup();await begin();assert.equal((await rpc('leads','jobStatus')).result.busy,false);assert.equal((await rpc('leads','jobStatus')).result.other_busy,true);assert((await f.rpc('jobStatus')).result.busy);
  assert((await rpc('leads','reloadCompanion',{version:'24.6.511'})).error);assert((await f.beginHR()).error,'old unscoped UI cannot start a second scan');
  f.tabs.set(4,{id:4,url:'http://127.0.0.1:5000/',status:'complete',active:true});assert((await f.rpc('connect',{}, {tab:{id:4},url:f.tabs.get(4).url,documentId:'bound'})).error);
  assert.equal(f.state.session.cvstudioLinkedinSessionV1.connection.tabId,1);assert.equal(f.state.session.cvstudioLinkedinLeadsSessionV1.connection.tabId,1);await profiles('end');
 }]
];
(async()=>{let failures=0;for(const [name,test] of cases){try{await test();console.log('PASS',name)}catch(error){failures++;console.error('FAIL',name,error.stack)}}if(failures)process.exitCode=1})().catch(error=>{console.error(error);process.exitCode=1});
