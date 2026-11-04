const assert=require('assert/strict'),{fixture}=require('./test_linkedin_job_search');
const url='https://www.linkedin.com/in/captured',run='d'.repeat(32);
async function setup(options={}){
 const f=fixture(options);await f.arm();let ready=true;
 f.state.onScript=args=>{
  if(args.args?.[0]==='readSearch')return [{result:{profiles:[{id:'p0',url}],signature:'one',hasNext:false}}];
  if(args.args?.[0]==='readProfile')return [{result:ready?{text:'Observed profile text',name:'Fictional candidate'}:{loading:true}}];
 };
 const rpc=(action,args={})=>f.rpc(action,{run_id:run,...args},undefined,'profiles');
 await rpc('begin',{source_tab_id:3,mode:'standard',max_pages:1});await rpc('read',{tab_id:3,method:'readSearch',values:['standard']});
 const id=(await rpc('create',{url})).result;
 return {f,rpc,id,loading:()=>ready=false};
}
(async()=>{
 const a=await setup(),result=await a.rpc('read',{tab_id:a.id,method:'readProfile',values:[url],close_after_read:true});
 assert.equal(result.result.text,'Observed profile text');assert.equal(result.result.profile_tab_released,true);
 assert(!a.f.tabs.has(a.id),'captured background profile closes before any further AI work');
 assert.equal((await a.rpc('create',{url})).result,12,'the next observed profile can use a fresh tab');await a.rpc('end');
 const b=await setup();b.f.tabs.get(b.id).active=true;await b.f.hooks().activated({tabId:b.id});b.f.tabs.get(b.id).active=false;
 assert((await b.rpc('read',{tab_id:b.id,method:'readProfile',values:[url],close_after_read:true})).result.profile_tab_released);
 assert(b.f.tabs.has(b.id),'previously viewed tabs are released without closing');await b.rpc('end');assert(b.f.tabs.has(b.id));
 const c=await setup();c.loading();assert((await c.rpc('read',{tab_id:c.id,method:'readProfile',values:[url],close_after_read:true})).result.loading);
 assert(c.f.tabs.has(c.id),'an incomplete description stays open for readiness polling');await c.rpc('end');
 const d=await setup();assert((await d.rpc('read',{tab_id:d.id,method:'readProfile',values:[url]})).result.text);
 assert(d.f.tabs.has(d.id),'old callers retain the existing reuse/End contract');await d.rpc('end');assert(!d.f.tabs.has(d.id));
 const e=await setup();e.f.tabs.get(e.id).url='https://www.linkedin.com/in/another';
 assert((await e.rpc('read',{tab_id:e.id,method:'readProfile',values:[url],close_after_read:true})).error);assert(e.f.tabs.has(e.id));await e.rpc('end');
 const transient=await setup({configureChrome(chrome,state){const remove=chrome.tabs.remove;state.failNextRemove=true;chrome.tabs.remove=async id=>{if(state.failNextRemove){state.failNextRemove=false;throw Error('Tabs are being edited');}return remove(id);};}});
 assert((await transient.rpc('read',{tab_id:transient.id,method:'readProfile',values:[url],close_after_read:true})).result.profile_tab_released);
 assert(transient.f.tabs.has(transient.id));assert(transient.f.state.session.cvstudioLinkedinSessionV1.owned.some(([id])=>id===transient.id),'a failed close retains exact cleanup ownership');
 await transient.rpc('end');assert(!transient.f.tabs.has(transient.id),'End retries the transient close');
 const cancelled=fixture({configureChrome(chrome,state){const get=chrome.tabs.get;chrome.tabs.get=async id=>id===1 && state.holdRoot?(state.holdRoot=false,new Promise(resolve=>state.releaseRoot=()=>resolve(get(id)))):get(id);}});
 await cancelled.arm();cancelled.state.holdRoot=true;const operation='f'.repeat(32);
 const capture=cancelled.rpc('jobFromLink',{url:'https://www.linkedin.com/jobs/view/1234567890',operation_id:operation});
 for(let i=0;i<100&&!cancelled.state.releaseRoot;i++)await new Promise(resolve=>setTimeout(resolve,0));
 assert(cancelled.state.releaseRoot);await cancelled.rpc('jobReadCancel',{operation_id:operation});cancelled.state.releaseRoot();
 assert((await capture).error);assert.equal(cancelled.state.created.length,0,'cancelled ad capture never opens a late tab');
 // Run the actual controller core against the worker: each successful read closes
 // before detail review and the next profile receives a fresh tab.
 const fs=require('fs'),vm=require('vm'),path=require('path'),window={};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/linkedin-sourcer-core.js'),'utf8'),{window,URL,URLSearchParams,AbortController,setTimeout,clearTimeout});
 const native=fixture();await native.arm();const profiles=[1,2].map(n=>({id:'p'+n,url:'https://www.linkedin.com/in/captured-'+n,name:'Fictional '+n,score:80,evidence:[],unknowns:[]}));
 native.state.onScript=args=>args.args?.[0]==='readSearch'?[{result:{profiles,signature:'both',hasNext:false,paginationKnown:true}}]:args.args?.[0]==='readProfile'?[{result:{text:'Captured description',name:'Fictional'}}]:undefined;
 const rpc=(action,args={})=>native.rpc(action,{run_id:run,...args},undefined,'profiles');
 let begun=false,detailCalls=0;
 const agent=new window.CVLinkedinCore.Agent({signal:new AbortController().signal,wait:async()=>{},update:()=>{},api:async(route,body)=>{
  if(route==='/api/start'){assert((await rpc('begin',{source_tab_id:3,mode:'standard',max_pages:1})).result);begun=true;}
  if(body?.stage==='detail'){detailCalls++;assert.equal(native.state.removed.length,2,'all captured profiles are closed before AI detail review');}
  return {run:{id:run},...(route==='/api/plan'?{plan:{query:'SAP',country:''}}:{}),...(route==='/api/review'?{candidates:body.stage==='screen'?profiles:body.profiles}:{})};
 },browser:{activeTab:async()=>native.tabs.get(3),createTab:async url=>(await rpc('create',{url})).result,
  navigate:async()=>{throw Error('captured tabs must not be reused');},closeOwnedTab:async()=>{await rpc('end');},
  read:async(id,method,values)=>{const value=await rpc('read',{tab_id:id,method,values,close_after_read:method==='readProfile'});assert(!value.error,value.error);return value.result;}}});
 await agent.start({mode:'standard',max_pages:1,use_open_search:true});assert(begun);assert.equal(detailCalls,1);assert.equal(native.state.created.length,2);assert.equal(agent.profileTab,null);await rpc('end');
 console.log('Capture cleanup: ready profiles close immediately; incomplete reads, viewed/changed/user tabs remain protected; fresh subsequent tabs and legacy End cleanup passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
