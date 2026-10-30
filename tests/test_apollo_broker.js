// Actual SQLite statements and Worker WebCrypto; all Apollo HTTP is fictional.
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const {DatabaseSync}=require('node:sqlite');
const {pathToFileURL}=require('url');
async function main(){
  const {handle,seal,unseal,digest,emailResult,default:worker}=await import(pathToFileURL(path.join(__dirname,'../integrations/apollo-broker/worker.mjs')));
  const sql=new DatabaseSync(':memory:');sql.exec('PRAGMA foreign_keys=ON');sql.exec(fs.readFileSync(path.join(__dirname,'../integrations/apollo-broker/schema.sql'),'utf8'));
  function prepare(query){return {bind(...args){return {query,args,async first(){return sql.prepare(query).get(...args)||null},async run(){const r=sql.prepare(query).run(...args);return {meta:{changes:r.changes}}}}}}}
  const env={PUBLIC_ORIGIN:'https://cvstudio-apollo.example.workers.dev',APOLLO_CLIENT_ID:'fictional-client',APOLLO_CLIENT_SECRET:'fictional-secret',TOKEN_KEY:'1'.repeat(64),DB:{prepare,async batch(statements){sql.exec('BEGIN');try{for(const s of statements)sql.prepare(s.query).run(...s.args);sql.exec('COMMIT')}catch(e){sql.exec('ROLLBACK');throw e}}}};
  const setupEnv={PUBLIC_ORIGIN:env.PUBLIC_ORIGIN};
  assert.equal((await handle(new Request(env.PUBLIC_ORIGIN+'/callback'),setupEnv,()=>{throw Error('no external request')})).status,200,'callback verification is available before Apollo issues app credentials');
  assert.equal((await handle(new Request(env.PUBLIC_ORIGIN+'/callback?code=untrusted'),setupEnv,()=>{})).status,503,'the setup probe cannot complete OAuth');
  assert.equal((await handle(new Request(env.PUBLIC_ORIGIN+'/callback',{method:'HEAD'}),setupEnv,()=>{})).status,200);
  const expected={url:'https://www.linkedin.com/in/sample-person',name:'Sample Person',company:'Example Company',company_url:'https://www.linkedin.com/company/example/',company_id:'123'};
  const upstream={match_confidence:'high',person:{linkedin_url:expected.url,email:'person@example.test',email_status:'verified',organization:{linkedin_url:expected.company_url,name:expected.company}}};
  let calls=[],failLookup=false,hold=null,tokenFails=false;
  const fetcher=async(url,options)=>{calls.push({url,options});assert.equal(options.redirect,'manual');
    if(url.endsWith('/oauth/token')){if(tokenFails)throw Error('private token');return Response.json({access_token:'fictional-access',refresh_token:'fictional-refresh',scope:'read_user_profile people_match app_scopes',expires_in:2592000})}
    if(url.endsWith('/api_profile'))return Response.json({user:{id:'fictional-user',name:'Example User'}});
    assert(url.startsWith('https://api.apollo.io/api/v1/people/match?'));
    const params=new URL(url).searchParams;for(const field of ['reveal_personal_emails','reveal_phone_number','run_waterfall_email','run_waterfall_phone'])assert.equal(params.get(field),'false');
    assert.equal(options.headers.Authorization,'Bearer fictional-access');
    if(hold)await new Promise(resolve=>{hold.release=resolve});if(failLookup)throw Error('private address and token');return Response.json(upstream);
  };
  const post=async(action,body)=>handle(new Request(env.PUBLIC_ORIGIN+'/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),env,fetcher,1000);
  async function login(secret){const start=await (await post('start',{proof_hash:await digest(secret)})).json();
    assert(!JSON.stringify(start).includes(env.APOLLO_CLIENT_SECRET));
    const state=new URLSearchParams(new URL(start.authorization_url).hash.split('?')[1]).get('state');assert.equal(state,start.flow_id);
    const callback=await handle(new Request(env.PUBLIC_ORIGIN+'/callback?state='+state+'&code=fictional-code'),env,fetcher,1000);assert.match(await callback.text(),/connected/);
    const poll=await (await post('poll',{flow_id:state,secret})).json();assert.equal(poll.name,'Example User');assert(!JSON.stringify(poll).includes('fictional-access'));
    return {connection_id:poll.connection_id,secret};
  }
  const a=await login('a'.repeat(64)),b=await login('b'.repeat(64));
  const cipher=sql.prepare('SELECT cipher FROM connections WHERE id=?').get(a.connection_id).cipher;
  assert(!cipher.includes('fictional-access')&&!cipher.includes('Example User'));
  await assert.rejects(unseal(env,cipher,b.connection_id));
  assert.equal((await post('reveal',{...a,operation_id:'c'.repeat(64),person:expected})).status,400);assert.equal(calls.filter(c=>c.url.includes('/people/match')).length,0);
  const op={...a,operation_id:'c'.repeat(64),person:expected,confirmed:true};
  assert.equal((await (await post('reveal',op)).json()).email,'person@example.test');
  assert.equal((await (await post('reveal',op)).json()).email_status,'verified');assert.equal(calls.filter(c=>c.url.includes('/people/match')).length,1);
  assert.equal((await post('reveal',{...op,person:{...expected,company:'Different'}})).status,409);
  assert.equal((await (await post('lookup-status',{...b,operation_id:op.operation_id})).json()).state,'unconfirmed','one account cannot read another account lookup');
  assert.equal((await post('lookup-status',{...a,secret:b.secret,operation_id:op.operation_id})).status,401);
  const stored=sql.prepare('SELECT cipher FROM operations WHERE connection_id=?').get(a.connection_id).cipher;assert(!stored.includes('person@example.test'));
  failLookup=true;const ambiguous={...op,operation_id:'d'.repeat(64)};
  assert.equal((await (await post('reveal',ambiguous)).json()).state,'unconfirmed');
  failLookup=false;await post('reveal',ambiguous);await post('lookup-status',ambiguous);
  assert.equal(calls.filter(c=>c.url.includes('/people/match')).length,2,'ambiguous paid lookup never replays');
  hold={};const concurrent={...op,...b,operation_id:'9'.repeat(64)},running=post('reveal',concurrent);
  for(let i=0;i<100 && !hold.release;i++)await new Promise(resolve=>setImmediate(resolve));
  assert(hold.release,'the first lookup reached the controlled provider');
  assert.equal((await (await post('reveal',concurrent)).json()).state,'unconfirmed');
  assert.equal((await (await post('reveal',{...concurrent,operation_id:'8'.repeat(64)})).json()).state,'limited');
  const release=hold.release;hold=null;release();assert.equal((await (await running).json()).state,'found');
  assert.equal((await (await post('lookup-status',concurrent)).json()).state,'found');
  assert.equal(calls.filter(c=>c.url.includes('/people/match')).length,3,'concurrent requests cannot duplicate a paid operation');
  const freshStart=await (await post('start',{proof_hash:await digest('e'.repeat(64))})).json();
  await post('cancel',{flow_id:freshStart.flow_id,secret:'e'.repeat(64)});
  const previous=calls.length;await handle(new Request(env.PUBLIC_ORIGIN+'/callback?state='+freshStart.flow_id+'&code=late'),env,fetcher,1000);assert.equal(calls.length,previous,'cancelled OAuth cannot recreate a connection');
  await handle(new Request(env.PUBLIC_ORIGIN+'/callback?state='+a.connection_id+'&code=replayed'),env,fetcher,1000);assert.equal(calls.length,previous,'callback code is consumed once');
  for(const bad of [{...upstream,person:{...upstream.person,linkedin_url:'https://www.linkedin.com/in/other'}},{...upstream,person:{...upstream.person,organization:{name:'Other'}}},{...upstream,match_confidence:'low'}])assert.equal(emailResult(bad,expected).state,'mismatch');
  assert.equal(emailResult({...upstream,person:{...upstream.person,email:'person@gmail.com'}},expected).state,'not_found');
  // Apollo's own link form (http, trailing slash, other letter case) still matches the saved profile and company.
  const apolloForm={match_confidence:'high',person:{...upstream.person,linkedin_url:'http://www.linkedin.com/in/Sample-Person/',organization:{linkedin_url:'http://www.linkedin.com/company/example',name:'Example Company'}}};
  assert.equal(emailResult(apolloForm,expected).state,'found');
  assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,organization:{linkedin_url:'http://www.linkedin.com/company/123',name:'Renamed'}}},expected).state,'found');
  assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,organization:{linkedin_url:'http://www.linkedin.com/company/456',name:expected.company}}},expected).state,'mismatch');
  assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,organization:{linkedin_url:'http://www.linkedin.com/company/example-old-slug',name:'PT Example Company Tbk'}}},expected).state,'found');
  assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,organization:{name:'Example'}}},expected).state,'mismatch');
  for(const name of ['Example Company Services','Example Other Company','Company Example','PT Tbk','中国企业','Éxample Company'])
    assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,organization:{name}}},expected).state,'mismatch','an overlapping or non-ASCII distinct brand is not the same employer');
  for(const name of ['PT Example Company Tbk','The Example Company Sdn. Bhd.','Example Company Pte Ltd'])
    assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,organization:{name}}},expected).state,'found');
  const unicodeExpected={...expected,company:'Éxample 中国'};
  assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,organization:{name:'Éxample 中国 Ltd'}}},unicodeExpected).state,'found');
  for(const org of [{linkedin_url:'http://www.linkedin.com/company/other',name:'Other Holdings'},{name:'PT Tbk'},{}])
    assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,organization:org}},expected).state,'mismatch');
  for(const url of ['http://www.linkedin.com/in/sample-person-2','http://www.linkedin.com/company/sample-person','https://evil.test/in/sample-person',''])
    assert.equal(emailResult({...apolloForm,person:{...apolloForm.person,linkedin_url:url}},expected).state,'mismatch');
  assert.equal(emailResult({...upstream,person:{...upstream.person,email_status:'catch_all'}},expected).email_status,'catch_all');
  // The real Worker persists only the selected contact email and can recover
  // it through the same operation without a second enrichment request.
  const primary=upstream.person;
  upstream.person={...primary,id:'fictional-person',organization_id:'fictional-organization',email:null,
    contact:{person_id:'fictional-person',organization_id:'fictional-organization',email:'fictional@proton.com',email_status:'verified'}};
  const savedOp={...op,operation_id:'6'.repeat(64)},beforeSaved=calls.filter(c=>c.url.includes('/people/match')).length;
  const savedResult=await (await post('reveal',savedOp)).json();
  assert.equal(savedResult.email,'fictional@proton.com');assert.equal(savedResult.email_source,'saved_contact');
  assert.equal((await (await post('lookup-status',savedOp)).json()).email,'fictional@proton.com');
  await post('reveal',savedOp);
  assert.equal(calls.filter(c=>c.url.includes('/people/match')).length,beforeSaved+1);
  const resultCipher=sql.prepare('SELECT cipher FROM operations WHERE connection_id=? AND id=?').get(a.connection_id,savedOp.operation_id).cipher;
  assert(!resultCipher.includes('fictional@proton.com'));
  const persisted=await unseal(env,resultCipher,a.connection_id+':'+savedOp.operation_id);
  assert(!('contact' in persisted) && !('person_id' in persisted),'raw contact/profile details are not retained');
  upstream.person=primary;
  await post('disconnect',a);assert.equal((await post('lookup-status',{...a,operation_id:op.operation_id})).status,401);assert.equal(sql.prepare('SELECT COUNT(*) AS n FROM operations WHERE connection_id=?').get(a.connection_id).n,0);
  // Refresh rotation is serialized and uncertain refreshes require reconnect.
  const existing=sql.prepare('SELECT cipher FROM connections WHERE id=?').get(b.connection_id);const old=await unseal(env,existing.cipher,b.connection_id);old.expires=900;
  sql.prepare('UPDATE connections SET cipher=? WHERE id=?').run(await seal(env,old,b.connection_id),b.connection_id);tokenFails=true;
  await post('reveal',{...op,...b,operation_id:'f'.repeat(64)});tokenFails=false;const tokenCalls=calls.filter(c=>c.url.endsWith('/oauth/token')).length;
  assert.equal((await (await post('reveal',{...op,...b,operation_id:'0'.repeat(64)})).json()).state,'auth_required');assert.equal(calls.filter(c=>c.url.endsWith('/oauth/token')).length,tokenCalls);
  assert.equal((await handle(new Request(env.PUBLIC_ORIGIN+'/start',{method:'POST',headers:{'Content-Type':'application/json'},body:'x'.repeat(17000)}),env,fetcher,1000)).status,503);
  assert.equal((await handle(new Request(env.PUBLIC_ORIGIN+'/start',{method:'OPTIONS'}),env,fetcher,1000)).headers.get('Access-Control-Allow-Origin'),null);
  await worker.scheduled({},env);sql.close();console.log('Apollo broker: SQLite authority, encrypted accounts/results, OAuth cancellation, identity checks, paid non-replay and refresh boundaries passed.');
}
main().catch(error=>{console.error(error);process.exit(1)});
