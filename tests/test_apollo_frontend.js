const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const person={url:'https://www.linkedin.com/in/sample-person',name:'Sample Person',title:'HR',matched:'HR'};
const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
async function setup({connected=true,available=true}={}){
  const f=fixture({apollo:true});f.state.records[0].hr={people:[person]};f.state.account={connected,available,name:'Example User'};f.state.apolloCalls=[];f.state.emailCache={};
  f.state.onApollo=async data=>{
    f.state.apolloCalls.push(data);
    if(!data)return reply(f.state.account);
    if(data.action==='emails')return reply({emails:f.state.emailCache});
    if(data.action==='connect')return reply({authorization_url:'https://app.apollo.io/#/oauth/authorize?state=fictional'});
    if(data.action==='poll'){f.state.account.connected=true;return reply({connected:true,name:'Second User'})}
    if(data.action==='disconnect'){f.state.account.connected=false;f.state.emailCache={};return reply({connected:false})}
    if(data.action==='reveal'){
      if(f.state.hold)await new Promise(resolve=>{f.state.release=resolve});
      if(f.state.fail)return {ok:false,json:async()=>({error:'Fictional network interruption'})};
      const result={state:'found',email:'person@example.test',email_status:'catch_all',message:'Apollo result'};f.state.emailCache[person.url]=result;return reply({result});
    }
    throw Error('Unexpected Apollo action');
  };
  await f.init();await tick();return f;
}
function buttons(f){return f.el('HRResults').querySelectorAll('button')}
(async()=>{
  const f=await setup();assert.equal(f.el('ApolloState').textContent,'Connected as Example User');
  assert.equal(f.state.apolloCalls.filter(x=>x?.action==='reveal').length,0,'display does not spend credits');
  f.el('notes').value='Keep my draft';f.el('notes').handlers.input();
  const before=structuredClone(f.state.records);
  f.state.allowDiscard=false;await buttons(f)[0].click();assert.equal(f.state.apolloCalls.filter(x=>x?.action==='reveal').length,0);
  f.state.allowDiscard=true;f.state.hold=true;const run=buttons(f)[0].click();await tick();await buttons(f)[0].click();
  assert.equal(f.state.apolloCalls.filter(x=>x?.action==='reveal').length,1);assert(f.el('ApolloDisconnect').disabled);
  f.state.release();await run;
  const result=f.el('HRResults').querySelectorAll('span').map(x=>x.textContent).join(' ');assert.match(result,/person@example.test/);
  assert(f.el('HRResults').querySelectorAll('small').some(x=>x.textContent==='Catch-all · reported by Apollo'));
  await buttons(f)[1].click();assert.equal(f.state.clipboard,'person@example.test');
  assert.equal(f.el('notes').value,'Keep my draft');assert.deepEqual(f.state.records,before);assert.equal(f.requests.length,0,'email unlock never rewrites an ad or its HR scan');
  await f.el('ApolloDisconnect').click();assert(!f.el('HRResults').querySelectorAll('span').some(x=>x.textContent==='person@example.test'));assert(buttons(f)[0].disabled);
  await f.el('ApolloConnect').click();await tick();assert.equal(f.state.popup.location.href,'https://app.apollo.io/#/oauth/authorize?state=fictional');assert.equal(f.el('ApolloState').textContent,'Connected as Second User');
  assert(!f.el('HRResults').querySelectorAll('span').some(x=>x.textContent==='person@example.test'));
  const disabled=await setup({connected:false,available:false});assert(disabled.el('ApolloConnect').disabled);assert(buttons(disabled)[0].disabled);assert.match(disabled.el('ApolloMessage').textContent,/one-time/);
  const failed=await setup();failed.state.fail=true;await buttons(failed)[0].click();assert.match(failed.el('ApolloMessage').textContent,/network/);
  const stale=await setup();stale.el('notes').value='Retain this draft';stale.el('notes').handlers.input();stale.state.hold=true;const lookup=buttons(stale)[0].click();await tick();stale.apollo.begin(null);stale.state.release();await lookup;
  assert.equal(stale.el('notes').value,'Retain this draft');
  f.pagehide();failed.pagehide();disabled.pagehide();stale.pagehide();
  console.log('Apollo UI: explicit credit use, double clicks, private cache, account changes, draft safety and setup guidance passed.');
})().catch(error=>{console.error(error);process.exit(1)});
