const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const response=data=>({ok:true,json:async()=>({ok:true,...data})});
(async()=>{
  const f=fixture({apollo:true,jobAdderContacts:true}),calls=[];
  let defaults=null,scope='a'.repeat(64);
  const users=[{id:7,name:'Example Owner'},{id:8,name:'Example Recruiter'},{id:9,name:'Third <User>'}];
  f.state.onApollo=async data=>data?.action==='contacts'?response({contacts:[{contact_key:'b'.repeat(64),name:'Example Person',position:'HR',company:'Example Company',email:'person@example.test'}]}):response({available:false});
  f.state.onJA=async data=>{
    calls.push(data);
    if(data.action==='companies')return response({account:scope,companies:[{id:12,name:'Example Company'}],assignments:f.state.unavailable?{available:false,message:'User choices unavailable'}:{available:true,users,defaults}});
    if(data.action==='review')return response({state:'review',review_token:'review',company:'Example Company',message:'Review'});
    if(data.action==='create'){
      if(data.remember_assignments)defaults={owner_user_id:data.owner_user_id,recruiter_user_ids:data.recruiter_user_ids};
      return response({state:'created',contact_id:45,message:'Created'});
    }
    throw Error('Unexpected action');
  };
  await f.init();await tick();await f.el('ApolloContactsTab').click();await tick();
  const open=()=>f.el('ApolloContactsRows').querySelectorAll('button')[0].click();
  await open();assert(f.el('JAOwner').disabled);await f.el('JASearch').click();f.el('JACompany').value='12';
  assert(!f.el('JAOwner').disabled);assert.equal(f.el('JAOwner').value,'');
  f.el('JAOwner').value='7';f.el('JAOwner').handlers.change();await f.el('JASelectAll').click();
  assert.equal(f.el('JARecruiterSummary').textContent,'Recruiters · 3 selected');
  assert(f.el('JARecruiterList').querySelectorAll('#text').some(n=>n.textContent==='Third <User>'),'names stay text');
  await f.el('JAReview').click();let reviewed=calls.at(-1);assert.equal(reviewed.owner_user_id,7);assert.deepEqual([...reviewed.recruiter_user_ids],[7,8,9]);
  f.el('JAOwner').value='8';f.el('JAOwner').handlers.change();assert(f.el('JACreate').hidden,'assignment changes invalidate review');
  await f.el('JAReview').click();await f.el('JACreate').click();assert.equal(defaults.owner_user_id,8);
  await f.el('JAClose').click();await open();await f.el('JASearch').click();f.el('JACompany').value='12';
  assert.equal(f.el('JAOwner').value,'8');assert.equal(f.el('JARecruiterSummary').textContent,'Recruiters · 3 selected');
  f.el('JARecruiterFilter').value='Recruiter';f.el('JARecruiterFilter').handlers.input();assert.equal(f.el('JARecruiterList').querySelectorAll('input').length,1);
  await f.el('JAClearRecruiters').click();await f.el('JAReview').click();assert.deepEqual([...calls.at(-1).recruiter_user_ids],[]);
  f.el('JARemember').checked=false;await f.el('JACreate').click();assert.equal(defaults.recruiter_user_ids.length,3,'one-off choices do not overwrite defaults');
  scope='c'.repeat(64);defaults=null;await f.el('JASearch').click();assert.equal(f.el('JAOwner').value,'');assert.equal(f.el('JARecruiterSummary').textContent,'Recruiters · JobAdder default','new connection cannot reuse old selections');
  f.state.unavailable=true;await f.el('JASearch').click();f.el('JACompany').value='12';assert(f.el('JAOwner').disabled);await f.el('JAReview').click();
  assert.equal(calls.at(-1).owner_user_id,null);assert.equal(calls.at(-1).remember_assignments,false,'unavailable directory cannot clear protected defaults');
  f.pagehide();console.log('Contact assignments UI: owner, select all/clear/filter, reviewed payload, reusable/one-off defaults, account isolation and unavailable directory passed');
})().catch(error=>{console.error(error);process.exitCode=1});
