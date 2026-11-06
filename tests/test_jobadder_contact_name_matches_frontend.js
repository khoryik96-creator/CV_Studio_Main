/* Fictional read-only JobAdder matches and paid Apollo boundaries. */
const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const scope='a'.repeat(64),person={name:'Marina Q.',url:'https://www.linkedin.com/in/fictional-marina',title:'Talent Manager'};
const match={contact_id:31,name:'Marina Quinn',company:'Example Bank',company_matches:true,reason:'Name and initial',url:'https://au3.jobadder.com/contacts/31'};
const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
async function setup(result={state:'matches',matches:[match],partial:false,message:'Possible JobAdder contacts'}){
 const f=fixture({apollo:true,jobAdderContacts:true});
 f.window._jaAccountCacheNamespace='ja'+scope;f.state.records[0].hr={people:[person]};
 f.state.reads=[];f.state.paid=[];f.state.confirms=[];
 f.state.onJA=async data=>{f.state.reads.push(data);if(f.state.hold)await new Promise(resolve=>f.state.release=resolve);return reply({account:scope,...result});};
 f.state.onApollo=async data=>{
  if(!data)return reply({available:true,connected:true});
  if(data.action==='emails')return reply({emails:{}});
  if(data.action==='contacts')return reply({contacts:[]});
  if(data.action==='reveal'){f.state.paid.push(data);return reply({result:{state:'found',email:'fictional@example.test',message:'Fictional email'}});}
  throw Error('Unexpected Apollo action');
 };
 f.window.confirm=message=>{f.state.confirms.push(message);return f.state.consent!==false;};
 await f.init();await tick();f.source=f.state.records[0];
 f.unlock=(options={},previous=null)=>f.window.cvStudioApollo.unlockSaved(f.source,person,previous,value=>f.state.note=value,value=>f.state.result=value,options);
 return f;
}
(async()=>{
 const bulk=await setup();const host=bulk.document.createElement('div');bulk.window.cvStudioJAContacts.decoratePerson(host,bulk.source,person);
 assert.equal(await bulk.unlock({confirmed:true,batch:true}),'jobadder_match');
 assert.equal(bulk.state.paid.length,0);assert.equal(bulk.state.reads.length,1);assert.equal(bulk.state.confirms.length,0);
 assert(!bulk.state.result,'a possible name must not be saved as a paid lookup or a confirmed identity');
 assert.equal(host.querySelectorAll('a')[0].href,match.url);assert.equal(host.querySelectorAll('a')[0].rel,'noopener noreferrer');
 const single=await setup();single.state.consent=false;
 assert.equal(await single.unlock(),'jobadder_match');assert.equal(single.state.paid.length,0);
 assert.match(single.state.confirms[0],/Marina Quinn/);assert.match(single.state.confirms[0],/credit/);
 single.state.consent=true;assert.equal(await single.unlock(),true);assert.equal(single.state.reads.length,1,'a short-lived checked result is reused within this account');assert.equal(single.state.paid.length,1);
 assert(single.state.paid[0].confirmed,'unlocking despite a possible name still needs explicit paid consent');
 const fresh=await setup({state:'no_matches',matches:[],partial:false,message:'No matching names found in this check.'});
 assert.equal(await fresh.unlock(),true);assert.equal(fresh.state.reads.length,1);assert.equal(fresh.state.paid.length,1);
 const appeared=await setup({state:'no_matches',matches:[],partial:false,message:'No match'});await appeared.window.cvStudioJAContacts.checkPerson(appeared.source,person);appeared.state.onJA=async()=>reply({account:scope,state:'matches',matches:[match],partial:false,message:'New contact'});assert.equal(await appeared.unlock({confirmed:true,batch:true}),'jobadder_match');assert.equal(appeared.state.paid.length,0,'a cached negative result is rechecked before spending a credit');
 const recovery=await setup();assert.equal(await recovery.unlock({}, {state:'unconfirmed'}),true);assert.equal(recovery.state.reads.length,0,'free recovery never starts a new duplicate or paid search');assert.equal(recovery.state.paid[0].confirmed,false);
 for(const result of [{state:'incomplete',matches:[],partial:true,message:'Incomplete'}, {state:'matches',matches:[{...match,url:'https://attacker.invalid/contacts/31'}],partial:false}]){
  const f=await setup(result);assert.equal(await f.unlock({confirmed:true,batch:true}),'jobadder_unchecked');assert.equal(f.state.paid.length,0);assert(!f.state.result);
 }
 const stopped=await setup({state:'no_matches',matches:[],partial:false,message:'No match'});stopped.state.hold=true;let keepGoing=true;const stopPending=stopped.unlock({confirmed:true,batch:true,shouldContinue:()=>keepGoing});await tick();keepGoing=false;stopped.state.release();assert.equal(await stopPending,'jobadder_stopped');assert.equal(stopped.state.paid.length,0,'Stop during a free name read must not start a paid action');
 const stale=await setup();stale.state.hold=true;const pending=stale.unlock({confirmed:true,batch:true});await tick();
 stale.window._jaAccountCacheNamespace='ja'+'c'.repeat(64);stale.window.cvStudioJAContacts.accountChanged();stale.state.release();
 assert.equal(await pending,'jobadder_unchecked');assert.equal(stale.state.paid.length,0);assert(!stale.window.cvStudioJAContacts.cachedMatch(stale.source,person));
 const changed=await setup();changed.window.confirm=()=>{changed.window._jaAccountCacheNamespace='ja'+'c'.repeat(64);changed.window.cvStudioJAContacts.accountChanged();return true;};
 assert.equal(await changed.unlock(),'jobadder_unchecked');assert.equal(changed.state.paid.length,0,'an account change during confirmation cancels the paid action');
 console.log('JobAdder name UI: initials, safe links, account-bound cache, bulk skips, explicit override, incomplete checks and no paid replay passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
