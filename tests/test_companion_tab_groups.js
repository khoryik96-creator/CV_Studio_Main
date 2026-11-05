const assert=require('assert/strict'),{fixture}=require('./test_linkedin_job_search');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function until(check){for(let i=0;i<200;i++){if(check())return;await tick();}assert(check(),'tab grouping did not settle');}
function grouped(make=fixture){
 return make({configureChrome(chrome,state,tabs){
  state.groups=new Map();state.groupCalls=[];let serial=100;
  for(const tab of tabs.values())Object.assign(tab,{windowId:7,groupId:-1});
  const originalCreate=chrome.tabs.create;
  chrome.tabs.create=async args=>{const tab=await originalCreate(args);Object.assign(tabs.get(tab.id),{windowId:args.windowId??99,groupId:-1});return {...tabs.get(tab.id)};};
  chrome.tabs.group=async args=>{
   if(state.groupHold)return new Promise(()=>{});
   if(state.groupError)throw Error('Tabs cannot be edited now');
   state.groupCalls.push(args);const groupId=args.groupId??++serial;
   const windowId=args.createProperties?.windowId??state.groups.get(groupId)?.windowId;
   for(const id of args.tabIds){assert.equal(tabs.get(id).windowId,windowId,'never move a tab between windows');tabs.get(id).groupId=groupId;}
   if(!state.groups.has(groupId))state.groups.set(groupId,{id:groupId,windowId});
   return groupId;
  };
  chrome.tabGroups={update:async(id,args)=>Object.assign(state.groups.get(id),args)};
  chrome.tabs.onCreated={addListener:fn=>state.createdEvent=fn};
  chrome.webNavigation={onCreatedNavigationTarget:{addListener:fn=>state.navigationEvent=fn}};
  const set=chrome.storage.session.set;
  chrome.storage.session.set=async data=>{if(state.groupStorageError && Object.hasOwn(data,'cvstudioTabFamiliesV1'))throw Error('Cosmetic storage failed');return set(data);};
 }});
}
(async()=>{
 const f=grouped();await f.arm();await until(()=>f.tabs.get(1).groupId>=0);const rootGroup=f.tabs.get(1).groupId;
 assert(rootGroup>=0);assert.equal(f.state.groups.get(rootGroup).title,'CV Studio');assert.equal(f.state.groups.get(rootGroup).color,'blue');
 const id=(await f.begin()).result.tab_id;await until(()=>f.tabs.get(id).groupId===rootGroup);assert.equal(f.tabs.get(id).groupId,rootGroup);assert.equal(f.state.created[0].windowId,7,'background scans open in their app window');
 await f.end();assert(f.tabs.has(id),'grouping does not change search-tab retention');
 f.tabs.set(50,{id:50,windowId:7,groupId:-1,url:'https://outlook.office.com/mail/'});
 f.state.navigationEvent({sourceTabId:1,tabId:50});await until(()=>f.tabs.get(50).groupId===rootGroup);
 f.tabs.set(51,{id:51,windowId:7,groupId:-1,url:'https://example.test/'});
 f.state.createdEvent({id:51,openerTabId:50});await until(()=>f.tabs.get(51).groupId===rootGroup);
 assert.equal(f.state.groups.size,1,'links and descendants reuse one group');
 f.tabs.set(52,{id:52,windowId:8,groupId:-1});f.state.navigationEvent({sourceTabId:50,tabId:52});
 await until(()=>f.tabs.get(52).groupId>=0);const otherGroup=f.tabs.get(52).groupId;
 assert.notEqual(otherGroup,rootGroup);assert.equal(f.state.groups.get(otherGroup).title,'CV Studio');
 f.tabs.set(53,{id:53,windowId:8,groupId:-1});f.state.navigationEvent({sourceTabId:52,tabId:53});await until(()=>f.tabs.get(53).groupId===otherGroup);
 f.tabs.set(60,{id:60,windowId:7,groupId:-1});f.state.navigationEvent({sourceTabId:2,tabId:60});await tick();await tick();
 assert.equal(f.tabs.get(2).groupId,-1);assert.equal(f.tabs.get(60).groupId,-1,'existing user tabs do not acquire app provenance');
 // Browser session metadata survives worker suspension, without gaining scan rights.
 f.boot();await f.rpc('jobStatus');f.tabs.set(54,{id:54,windowId:7,groupId:-1});f.state.navigationEvent({sourceTabId:51,tabId:54});await until(()=>f.tabs.get(54).groupId===rootGroup);
 assert((await f.rpc('read',{run_id:f.run,tab_id:50,method:'readProfile',values:['https://www.linkedin.com/in/unobserved']})).error);
 await f.hooks().removed(50);await until(()=>!f.state.session.cvstudioTabFamiliesV1.some(([id])=>id===50));
 assert(f.state.session.cvstudioTabFamiliesV1.every(entry=>entry.length===2 && entry.every(Number.isInteger)),'only numeric provenance is stored');
 // Respect the group chosen by the user for the app tab.
 f.state.groups.set(90,{id:90,windowId:7,title:'My workspace',color:'purple'});f.tabs.get(1).groupId=90;
 f.tabs.set(55,{id:55,windowId:7,groupId:-1});f.state.navigationEvent({sourceTabId:1,tabId:55});await until(()=>f.tabs.get(55).groupId===90);
 assert.equal(f.state.groups.get(90).title,'My workspace');
 const leadPeople=grouped();await leadPeople.arm();await until(()=>leadPeople.tabs.get(1).groupId>=0);
 const leadRun='e'.repeat(32);const leadSource=(await leadPeople.rpc('leadPeopleBegin',{run_id:leadRun,query:'Elitez HR'},undefined,'leads')).result.tab_id;
 await until(()=>leadPeople.tabs.get(leadSource).groupId===leadPeople.tabs.get(1).groupId);
 assert.equal(leadPeople.tabs.get(leadSource).groupId,leadPeople.tabs.get(1).groupId,'Lead Finder People source belongs to CV Studio');
 await leadPeople.rpc('end',{run_id:leadRun},undefined,'leads');assert(!leadPeople.tabs.has(leadSource),'completed Lead Finder source is closed');
 const hr=grouped(options=>require('./test_linkedin_company_hr').hrFixture('',options));await hr.arm();
 const hrSource=(await hr.beginHR()).result.tab_id;await until(()=>hr.tabs.get(hrSource).groupId===hr.tabs.get(1).groupId);assert.equal(hr.tabs.get(hrSource).groupId,hr.tabs.get(1).groupId,'HR People source belongs to the app group');
 await hr.readHR(hrSource);await hr.readHR(hrSource);
 await hr.rpc('hrJoined',{run_id:hr.run,tab_id:hrSource,url:'https://www.linkedin.com/in/sample'});
 await until(()=>hr.tabs.get(12)?.groupId===hr.tabs.get(1).groupId);assert.equal(hr.tabs.get(12).groupId,hr.tabs.get(1).groupId,'employment/profile tabs opened during HR scans share the group');
 await hr.end();assert(hr.tabs.has(1),'grouping never changes owned-tab cleanup');
 const stopped=fixture({configureChrome(chrome,state){const get=chrome.tabs.get;chrome.tabs.get=async id=>id===1 && state.holdRoot?(state.holdRoot=false,new Promise(resolve=>state.releaseRoot=()=>resolve(get(id)))):get(id);}});
 await stopped.arm();const run='c'.repeat(32),profile='https://www.linkedin.com/in/stopped';
 stopped.state.onScript=args=>args.args?.[0]==='readSearch'?[{result:{profiles:[{id:'p0',url:profile}],signature:'one',hasNext:false}}]:undefined;
 const rpc=(action,args={})=>stopped.rpc(action,{run_id:run,...args},undefined,'profiles');
 await rpc('begin',{source_tab_id:3,mode:'standard',max_pages:1});await rpc('read',{tab_id:3,method:'readSearch',values:['standard']});
 stopped.state.holdRoot=true;const creating=rpc('create',{url:profile});await until(()=>stopped.state.releaseRoot);await rpc('end');stopped.state.releaseRoot();
 assert((await creating).error);assert.equal(stopped.state.created.length,0,'End during app-window lookup prevents the native tab creation');
 const failed=grouped();failed.state.groupError=true;await failed.arm();const result=await failed.begin();assert(result.result?.tab_id,'group API failure does not fail a scan');await failed.end();
 const held=grouped();held.state.groupHold=true;await held.arm();assert((await held.begin()).result?.tab_id,'a hung cosmetic group API never delays scan creation or ownership');await held.end();
 const storage=grouped();storage.state.groupStorageError=true;await storage.arm();assert((await storage.begin()).result?.tab_id,'group storage failure does not fail a scan');await storage.end();
 console.log('Companion groups: authenticated app + created scans, noopener links and descendants, per-window groups, existing user groups, suspension, numeric-only provenance and independent scan authority/failure handling passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
