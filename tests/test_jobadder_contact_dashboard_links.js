const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const scope='a'.repeat(64),key='b'.repeat(64),url='https://au3.jobadder.com/contacts/45';
const row={contact_key:key,name:'Example Person',position:'HR',company:'Example Company',email:'person@example.test',profile_url:'https://www.linkedin.com/in/example-person'};
const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const openLinks=f=>f.el('ApolloContactsRows').querySelectorAll('a').filter(a=>a.textContent==='Open in JobAdder');
const createButtons=f=>f.el('ApolloContactsRows').querySelectorAll('button').filter(a=>a.textContent==='Create in JobAdder');
(async()=>{
 let confirmed=false,hold=false,release,calls=0;
 const f=fixture({apollo:true,jobAdderContacts:true});f.window._jaAccountCacheNamespace='ja'+scope;
 const snapshot=()=>({contacts:[row],jobadder_account:scope,jobadder_links:confirmed?[{contact_key:key,state:'created',contact_id:45,contact_url:url}]:[]});
 f.state.onApollo=async data=>{if(data?.action!=='contacts')return reply({available:false,connected:false});const dataBefore=snapshot();if(hold)await new Promise(resolve=>release=resolve);return reply(dataBefore);};
 f.state.onJA=async data=>{calls++;if(data.action==='companies')return reply({account:scope,companies:[{id:12,name:'Example Company'}]});if(data.action==='review')return reply({state:'review',review_token:'fictional',company:'Example Company',message:'Review'});if(data.action==='create'){confirmed=true;return reply({state:'created',contact_id:45,contact_url:url,message:'Created'});}throw Error('Unexpected request');};
 await f.init();await tick();await f.el('ApolloContactsTab').click();await tick();assert.equal(calls,0);
 await createButtons(f)[0].click();await f.el('JASearch').click();f.el('JACompany').value='12';await f.el('JAReview').click();
 hold=true;const pending=f.el('ApolloContactsRefresh').click();await tick();
 await f.el('JACreate').click();assert.equal(openLinks(f)[0].href,url);assert.equal(createButtons(f).length,0,'created contact immediately replaces Create with its record link');
 release();await pending;hold=false;assert.equal(openLinks(f)[0].href,url,'an older contact refresh cannot erase a newly confirmed link');
 await f.el('ApolloContactsRefresh').click();assert.equal(openLinks(f)[0].href,url);assert.equal(calls,3,'refreshing links performs no extra JobAdder request');
 assert.equal(openLinks(f)[0].target,'_blank');assert.equal(openLinks(f)[0].rel,'noopener noreferrer');
 f.window._jaAccountCacheNamespace='ja'+'c'.repeat(64);f.window.cvStudioJAContacts.accountChanged();assert.equal(openLinks(f).length,0);
 await f.el('ApolloContactsRefresh').click();assert.equal(openLinks(f).length,0,'late results from another account do not expose old links');
 const restored=fixture({apollo:true,jobAdderContacts:true});restored.window._jaAccountCacheNamespace='ja'+scope;
 restored.state.onApollo=async data=>reply(data?.action==='contacts'?snapshot():{available:false,connected:false});
 await restored.init();await tick();await restored.el('ApolloContactsTab').click();await tick();
 assert.equal(openLinks(restored)[0].href,url,'a fresh dashboard renders protected-history links without recreating the contact');
 restored.window.cvStudioJAContacts.setLinks(scope,[{contact_key:key,state:'created',contact_id:45,contact_url:'https://attacker.invalid/contacts/45'}],restored.window.cvStudioJAContacts.linkVersion());restored.apollo.redrawContacts();assert.equal(openLinks(restored).length,0,'unsafe links never render');
 for(const changes of [[scope],[scope,'c'.repeat(64)]]){
  const cold=fixture({apollo:true,jobAdderContacts:true});let releaseFirst,reads=0,activeScope=scope;
  cold.state.onJA=()=>{throw Error('Account-link refresh must not contact JobAdder');};
  cold.state.onApollo=async data=>{
   if(data?.action!=='contacts')return reply({available:false,connected:false});
   const seen=activeScope,id=seen===scope?45:55;reads++;
   if(reads===1)await new Promise(resolve=>releaseFirst=resolve);
   return reply({contacts:[row],jobadder_account:seen,jobadder_links:[{contact_key:key,state:'created',contact_id:id,contact_url:'https://au3.jobadder.com/contacts/'+id}]});
  };
  await cold.init();await tick();cold.el('ApolloContactsTab').click();await tick();
  for(const next of changes){activeScope=next;cold.window._jaAccountCacheNamespace='ja'+next;cold.window.cvStudioJAContacts.accountChanged();}
  releaseFirst();for(let i=0;i<20 && !openLinks(cold).length;i++)await tick();
  assert.equal(reads,2,'account changes during a pending read coalesce into one fresh local snapshot');
  assert.equal(openLinks(cold)[0].href,'https://au3.jobadder.com/contacts/'+(activeScope===scope?45:55),'startup timing cannot leave a saved contact labelled Create');
  activeScope='d'.repeat(64);cold.window._jaAccountCacheNamespace='ja'+activeScope;cold.window.cvStudioJAContacts.accountChanged();
  assert.equal(openLinks(cold).length,0,'old-account links disappear before the new snapshot');
  for(let i=0;i<20 && !openLinks(cold).length;i++)await tick();
  assert.equal(reads,3);assert.equal(openLinks(cold)[0].href,'https://au3.jobadder.com/contacts/55','an idle account switch refreshes existing contacts automatically');
  cold.pagehide();
 }
 f.pagehide();restored.pagehide();console.log('JobAdder dashboard links: immediate create result, persisted reload, stale refresh/account isolation and safe anchors passed');
})().catch(error=>{console.error(error);process.exitCode=1});
