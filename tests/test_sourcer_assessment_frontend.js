const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),path=require('path');
const root=path.resolve(__dirname,'..');
(async()=>{
  const origin='http://127.0.0.1:5000';
  const window={fetch:async()=>{},location:{origin,href:origin+'/'},dispatchEvent(){}};
  const context=vm.createContext({window,URL,Headers,setTimeout,clearTimeout,AbortController,
    CustomEvent:function(){},Uint8Array,Date,Math,JSON,Object,Array,String,Number,Promise,Error});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/cvstudio/api-transport.js'),'utf8'),context);
  const failure=window.cvStudioNormaliseApiFailure({error:'DeepSeek returned an incomplete assessment.',
    code:'AI_PROVIDER_RESPONSE_INVALID',action:'review_sourcer_results',retryable:false,
    request_id:'synthetic-request'}, {status:400,url:origin+'/linkedin-sourcer',headers:new Headers()});
  assert.match(failure.error,/Results already found are kept/);
  assert.match(failure.error,/No AI request was retried automatically/);
  assert.match(failure.error,/Request ID: synthetic-request/);
  assert(!/API Settings|provider key/.test(failure.error));
  const auth=window.cvStudioNormaliseApiFailure({error:'DeepSeek API key is invalid',
    code:'AI_PROVIDER_AUTH_REQUIRED',action:'open_ai_settings'}, {status:400,headers:new Headers()});
  assert.match(auth.error,/Open Main API Settings/);

  const core=vm.createContext({window:{},URL,Map,Set,setTimeout,clearTimeout,Error,console});
  vm.runInContext(fs.readFileSync(path.join(root,'vendor/cvstudio/linkedin-sourcer-core.js'),'utf8'),core);
  const Agent=core.window.CVLinkedinCore.Agent;
  const run={id:'a'.repeat(32)},url='https://www.linkedin.com/in/example-candidate';
  const candidate={id:'p0',url,name:'Example Candidate',text:'SAP finance experience',
    score:80,evidence:['SAP finance experience'],unknowns:['Availability']};
  const calls=[],actions=[],patches=[];
  const agent=new Agent({signal:new AbortController().signal,wait:async()=>{},update:p=>patches.push(p),
    api:async(route,body)=>{
      calls.push({route,body});
      if(route==='/api/plan')return {run,plan:{query:'SAP'}};
      if(route==='/api/review'){
        if(body.stage==='detail')throw Error(failure.error);
        return {run,candidates:[candidate]};
      }
      return {run};
    },browser:{activeTab:async()=>({id:2,url:'https://www.linkedin.com/search/results/people/'}),
      navigate:async()=>{},createTab:async()=>3,closeOwnedTab:async()=>actions.push('close'),
      read:async(id,method)=>{
        actions.push(method);
        if(method==='readProfile')return {text:'SAP finance experience. More observed details.'};
        return {profiles:[candidate],signature:'first',hasNext:true,paginationKnown:true};
      }}});
  await assert.rejects(agent.start({mode:'standard',max_pages:10,use_open_search:false}),/incomplete assessment/);
  assert.equal(agent.results.length,1);
  assert.equal(agent.results[0].url,url);
  assert.equal(agent.results[0].checked,false,'failed detail never upgrades search-card evidence');
  assert.equal(calls.filter(c=>c.route==='/api/plan').length,1);
  assert.equal(calls.filter(c=>c.route==='/api/review').length,2,'failed paid assessment is not retried');
  assert.equal(calls.filter(c=>c.route==='/api/stop').length,1);
  assert(!actions.includes('next'),'failure cannot advance the search');
  assert.equal(actions.filter(a=>a==='close').length,1);
  console.log('PASS: incomplete assessments retain results/provenance, use response guidance and never replay paid work.');
})().catch(e=>{console.error(e);process.exitCode=1});
