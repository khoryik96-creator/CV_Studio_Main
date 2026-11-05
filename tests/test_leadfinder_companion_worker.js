const assert=require('assert/strict');const {fixture}=require('./test_linkedin_job_search');
(async()=>{
 for(const mode of ['normal','viewed','changed','suspended','failed']){
  const f=fixture();await f.arm();const run='d'.repeat(32);
  const begin=await f.rpc('leadPeopleBegin',{run_id:run,query:'"Elitez" (HR OR Recruiter)'},undefined,'leads');
  assert(begin.result,JSON.stringify(begin));const id=begin.result.tab_id;assert.equal(f.state.created[0].active,false);
  if(mode==='viewed'){f.tabs.get(id).active=true;await f.hooks().activated({tabId:id});f.tabs.get(id).active=false;}
  if(mode==='changed'){f.tabs.get(id).url='https://www.linkedin.com/feed/';await f.hooks().updated(id,{url:f.tabs.get(id).url});}
  f.state.onScript=args=>args.target.tabId===id && args.func?[{result:{url:f.tabs.get(id).url,profiles:[{url:'https://www.linkedin.com/in/fictional-hr',name:'Fictional HR',title:'HR Manager',text:'Fictional HR HR Manager at Elitez'}],signature:'one',empty:false}}]:undefined;
  if(mode==='suspended')f.boot();if(mode==='failed')f.state.failInjection=true;
  const result=await f.rpc('leadPeopleRead',{run_id:run,tab_id:id},undefined,'leads');
  if(['changed','failed'].includes(mode))assert(result.error);else assert.equal(result.result.profiles[0].name,'Fictional HR');
  assert.equal((await f.rpc('end',{run_id:run},undefined,'leads')).result,true);
  assert.equal(f.tabs.has(id),['viewed','changed'].includes(mode),'cleanup respects user control');assert(f.tabs.has(2) && f.tabs.has(3));
 }
 const f=fixture();await f.arm();assert((await f.rpc('leadPeopleBegin',{run_id:'d'.repeat(32),query:'Elitez'},undefined,'profiles')).error);
 console.log('Lead Finder companion: scoped source, read, cleanup, suspension and viewed/changed-tab protection passed');
})().catch(e=>{console.error(e);process.exitCode=1});
