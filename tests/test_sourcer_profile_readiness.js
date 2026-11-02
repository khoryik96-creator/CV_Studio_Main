/* Unread details keep grounded card assessments and never replay paid calls. */
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const context=vm.createContext({window:{},URL,Map,Set,setTimeout,clearTimeout,Error,console});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/linkedin-sourcer-core.js'),'utf8'),context);
const Agent=context.window.CVLinkedinCore.Agent;
// Exercise the actual DOM reader: a valid-but-empty background profile is
// loading; a different URL or access page is never treated as skippable data.
const profileURL='https://www.linkedin.com/in/fictional-1';
let words='',mainPresent=false;
const main={get innerText(){return words;},querySelector:()=>null,querySelectorAll:()=>[]};
const location={origin:'https://www.linkedin.com',href:profileURL,pathname:'/in/fictional-1'};
const document={body:main,querySelector:s=>s==='main'&&mainPresent?main:null};
const readerContext=vm.createContext({document,location,URL,URLSearchParams,Date,Number});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8'),readerContext);
assert(readerContext.SourcerReader.readProfile(profileURL).loading);mainPresent=true;words='Loading';assert(readerContext.SourcerReader.readProfile(profileURL).loading);
words='Fictional candidate SAP finance experience and current job';assert.equal(readerContext.SourcerReader.readProfile(profileURL).text,words);
assert.throws(()=>readerContext.SourcerReader.readProfile(profileURL+'-other'),/changed/);
location.pathname='/login';assert.throws(()=>readerContext.SourcerReader.readProfile(profileURL),/sign in/);
(async()=>{
 for(const mode of ['timeout','access','identity','stop']){
  const controller=new AbortController(),run={id:'a'.repeat(32)},calls=[],updates=[],seen=[];
  const profiles=[1,2].map(n=>({id:'p'+n,name:'Fictional '+n,url:'https://www.linkedin.com/in/fictional-'+n,text:'SAP finance',score:80,evidence:['SAP finance'],unknowns:['Availability']}));
  let closed=0;
  const agent=new Agent({signal:controller.signal,wait:async()=>{},update:value=>updates.push(value),api:async(route,body)=>{
    calls.push({route,body});if(route.endsWith('/plan'))return {run,plan:{query:'SAP'}};
    return {run,...(route.endsWith('/review')?{candidates:body.stage==='screen'?profiles:body.profiles}: {})};
  },browser:{activeTab:async()=>({id:2,url:'https://www.linkedin.com/search/results/people/'}),navigate:async()=>({tab_id:11}),createTab:async()=>10,closeOwnedTab:async()=>{closed++;},read:async(id,method,args)=>{
    if(method==='readSearch')return {profiles,signature:'one',hasNext:false,paginationKnown:true};
    if(method==='readProfile'){
      seen.push(args[0]);if(seen.length===1){if(mode==='stop')controller.abort();const error=Error(mode);error.code=mode==='timeout'?'LI_PROFILE_NOT_READY':'';throw error;}
      return {text:'Observed detail',name:'Fictional 2'};
    }
    return true;
  }}});
  if(mode==='timeout'){
    await agent.start({mode:'standard',max_pages:2,use_open_search:false});
    assert.equal(seen.length,2,'the next observed profile is still read');assert.equal(agent.results.length,2);
    assert(!agent.results[0].checked,'unread profile remains search-card-only');assert(agent.results[1].checked);
    assert.equal(calls.filter(c=>c.body?.stage==='screen').length,1);assert.equal(calls.filter(c=>c.body?.stage==='detail').length,1);
    assert.equal(calls.find(c=>c.body?.stage==='detail').body.profiles.length,1,'only actual detail text reaches AI');
    assert.match(updates.at(-2).status || updates.at(-3).status,/search-card results were kept/);
  }else{
    await assert.rejects(agent.start({mode:'standard',max_pages:2,use_open_search:false}));assert.equal(seen.length,1);assert(!calls.some(c=>c.body?.stage==='detail'));
  }
  assert.equal(closed,1);assert.equal(calls.filter(c=>c.route.endsWith('/stop')).length,1);
 }
 console.log('Sourcer detail readiness: retained screen results, subsequent profiles, selective detail calls, access/identity/Stop and cleanup passed.');
})().catch(e=>{console.error(e);process.exitCode=1});
