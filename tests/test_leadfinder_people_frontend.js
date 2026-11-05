const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const context={window:{},crypto:require('crypto').webcrypto,setTimeout,AbortController};vm.runInNewContext(fs.readFileSync('vendor/cvstudio/lead-people.js','utf8'),context);
(async()=>{
 for(const mode of ['normal','read-fails','stop','stop-during-review']){
  const controller=new AbortController(),calls=[],requests=[];let reads=0;
  const rpc=async(action,args)=>{calls.push({action,args});if(action==='jobStatus')return {lead_people_revision:1};if(action==='leadPeopleBegin')return {tab_id:11};if(action==='end')return true;
    if(mode==='read-fails')throw Error('Synthetic read failure');if(mode==='stop')controller.abort();reads++;return {profiles:[{name:'Fictional HR',url:'https://www.linkedin.com/in/fictional',title:'HR at Elitez',text:'HR at Elitez'}],signature:'one',empty:false};};
  const request=async body=>{requests.push(body);if(body.action==='companion_review' && mode==='stop-during-review')controller.abort();return body.action==='companion_plan'?{companies:[{company:'Elitez'}],plan:[{company:'Elitez',query:'Elitez HR'}]}:{people:[{name:'Fictional HR'}],usage:{input_tokens:100}};};
  const run=context.window.cvStudioLeadFinderPeople.run({payload:{provider:'deepseek'},rpc,request,status(){},signal:controller.signal,wait:async()=>{}});
  if(mode==='normal' || mode==='stop-during-review'){const result=await run;assert.equal(result.people.length,1);assert.equal(result.usage.input_tokens,100,'completed paid response remains available for accounting');assert.equal(requests.at(-1).observed_people[0].company,'Elitez');}
  else {await assert.rejects(run);assert.equal(requests.length,1,'no AI review after failure or stop');}
  assert.equal(calls.filter(c=>c.action==='end').length,1,'cleanup runs on all outcomes');
 }
 console.log('DeepSeek people client: plan, observed-only review, failure/stop cleanup passed');
})().catch(e=>{console.error(e);process.exitCode=1});
