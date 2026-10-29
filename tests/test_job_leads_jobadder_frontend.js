const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const response=data=>({ok:true,json:async()=>({ok:true,...data})});
(async()=>{
  const f=fixture({apollo:true,jobAdderContacts:true});const calls=[];
  f.state.onApollo=async data=>data?.action==='contacts'?response({contacts:[{contact_key:'b'.repeat(64),name:'Example Person',position:'HR',company:'Example Company',email:'person@example.test',profile_url:'https://www.linkedin.com/in/example-person'}]}):response({available:false,connected:false});
  f.state.onJA=async data=>{
    calls.push(data);
    if(data.action==='companies')return response({account:'a'.repeat(64),companies:[{id:12,name:'Example Company'}]});
    if(data.action==='review')return response({state:'review',review_token:'fictional-review',company:'Example Company',message:'Check the contact'});
    if(data.action==='create'){
      if(f.state.hold)await new Promise(resolve=>{f.state.release=resolve});
      return response({state:f.state.unknown?'unconfirmed':'created',contact_id:f.state.unknown?null:45,message:f.state.unknown?'Check previous result':'Contact created'});
    }
    if(data.action==='check')return response({state:'created',contact_id:45,message:'Previous result confirmed'});
    throw Error('Unexpected action');
  };
  await f.init();await tick();await f.el('ApolloContactsTab').click();await tick();
  assert.equal(calls.length,0,'listing contacts never accesses JobAdder');
  const button=f.el('ApolloContactsRows').querySelectorAll('button')[0];await button.click();
  assert(f.el('JADialog').open);assert.equal(f.el('JAFirst').value,'Example');assert.equal(f.el('JALast').value,'Person');assert.equal(f.el('JAEmail').value,'person@example.test');
  await f.el('JACreate').click();assert.equal(calls.length,0,'create is gated by company selection and review');
  await f.el('JASearch').click();f.el('JACompany').value='12';f.el('JACompany').handlers.change();
  await f.el('JAReview').click();assert(!f.el('JACreate').hidden);assert.equal(calls.filter(c=>c.action==='create').length,0);
  f.el('JAPosition').value='HR Manager';f.el('JAPosition').handlers.input();assert(f.el('JACreate').hidden);
  await f.el('JACreate').click();assert.equal(calls.filter(c=>c.action==='create').length,0,'editing a reviewed field invalidates create');
  await f.el('JAReview').click();f.el('notes').value='Keep this ad draft';f.state.hold=true;
  const create=f.el('JACreate').click();await tick();await f.el('JACreate').click();
  assert.equal(calls.filter(c=>c.action==='create').length,1);assert(f.el('JAClose').disabled);
  let prevented=false;f.el('JADialog').handlers.cancel({preventDefault(){prevented=true}});assert(prevented,'cannot fake-cancel an unsafe write');
  f.state.release();await create;assert.match(f.el('JAMessage').textContent,/Contact created/);
  assert.equal(calls.find(c=>c.action==='create').confirmed,true);assert.equal(calls.find(c=>c.action==='create').position,'HR Manager');
  assert.equal(f.el('notes').value,'Keep this ad draft');assert.equal(f.requests.length,0,'creating contacts never rewrites an ad');
  await f.el('JAClose').click();assert(!f.el('JADialog').open);
  await button.click();await f.el('JASearch').click();f.el('JACompany').value='12';await f.el('JAReview').click();
  f.state.hold=false;f.state.unknown=true;await f.el('JACreate').click();assert(!f.el('JACheck').hidden);
  const writes=calls.filter(c=>c.action==='create').length;await f.el('JACheck').click();assert.equal(calls.filter(c=>c.action==='create').length,writes);
  assert.match(f.el('JAMessage').textContent,/confirmed/);
  assert(!calls.some(c=>Object.keys(c).some(k=>/secret|access_token|refresh_token/.test(k))));
  f.pagehide();console.log('JobAdder contact UI: existing-company choice, source fill, review invalidation, explicit single create, read-only recovery and draft safety passed.');
})().catch(error=>{console.error(error);process.exit(1)});
