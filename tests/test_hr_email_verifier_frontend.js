const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
(async()=>{
 const f=fixture({apollo:true,emailVerifier:true});
 const person={url:'https://www.linkedin.com/in/fictional-person',name:'Example Person',title:'HR',matched:'HR'};
 f.state.records[0].hr={people:[person]};let connected=true,checks=0;
 f.state.onApollo=async data=>{
  if(!data)return reply({available:true,connected,name:'Example User'});
  if(data.action==='emails')return reply({emails:{[person.url]:{state:'found',email:'person@example.test',email_status:'verified'}}});
  if(data.action==='disconnect'){connected=false;return reply({connected:false})}
  throw Error('Unexpected Apollo action');
 };
 f.state.onVerify=async data=>{checks++;assert.equal(data.mode,'deep');return reply({result:{status:'catch_all',reason:'Domain accepts all recipients.',mailbox_evidence:'accepted',catch_all:'detected',assessment:{label:'Use caution'},attempts:2}})};
 await f.init();await tick();
 const input=f.el('HRResults').querySelectorAll('input')[0];
 assert.equal(input.value,'person@example.test');assert.equal(checks,0,'Apollo display does not start a probe');
 const before=structuredClone(f.state.records);f.el('notes').value='Keep my draft';f.el('notes').handlers.input();
 const button=f.el('HRResults').querySelectorAll('button').find(node=>node.textContent==='Verify email');
 await button.click();assert.equal(checks,1);assert.equal(f.requests.length,0);assert.deepEqual(f.state.records,before);
 assert.equal(f.el('notes').value,'Keep my draft');
 assert(f.el('HRResults').querySelectorAll('strong').some(node=>node.textContent==='Use caution'));
 await f.el('ApolloDisconnect').click();assert.equal(input.value,'');
 assert(!f.el('HRResults').querySelectorAll('strong').some(node=>node.textContent==='Use caution'));
 input.value='manual@example.test';input.handlers.input();await button.click();assert.equal(checks,2,'manual checks work without Apollo');
 // An email just unlocked is checked once, automatically; nothing else probes.
 const g=fixture({apollo:true,emailVerifier:true});
 const other={url:'https://www.linkedin.com/in/fictional-other',name:'Other Person',title:'HR',matched:'HR'};
 g.state.records[0].hr={people:[other]};let gChecks=0,reveals=0;
 g.state.onApollo=async data=>{
  if(!data)return reply({available:true,connected:true,name:'Example User'});
  if(data.action==='emails')return reply({emails:{}});
  if(data.action==='reveal'){reveals++;return reply({result:{state:'found',email:'Other@Example.test',email_status:'verified',message:'Email found.'}});}
  throw Error('Unexpected Apollo action');
 };
 g.state.onVerify=async data=>{gChecks++;assert.deepEqual([data.email,data.mode],['other@example.test','deep']);return reply({result:{status:'accepted',reason:'The mailbox accepted the address.',assessment:{label:'Looks deliverable'},attempts:1}})};
 await g.init();await tick();assert.equal(gChecks,0,'showing HR people never probes');
 await g.el('HRResults').querySelectorAll('button').find(node=>node.textContent==='Unlock email').click();
 for(let i=0;i<5;i++)await tick();
 assert.equal(reveals,1);assert.equal(gChecks,1,'the unlocked email is checked once');
 const auto=g.el('HRResults').querySelectorAll('small').map(node=>node.textContent).join(' ');assert.match(auto,/Checked automatically after unlock/);
 assert(g.el('HRResults').querySelectorAll('strong').some(node=>node.textContent==='Looks deliverable'));
  assert.equal(gChecks,1,'the same address is not checked again this session');
 g.pagehide();
 f.pagehide();console.log('HR email integration: explicit probes, Apollo prefill/disconnect, manual checks, saved records and draft isolation passed.');
})().catch(error=>{console.error(error);process.exit(1)});
