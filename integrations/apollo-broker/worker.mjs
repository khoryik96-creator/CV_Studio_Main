// Shared OAuth broker. No Apollo client secret or provider token ships to a
// colleague. Every opaque connection key binds one installation to one account.
// No console/request logging, CORS, third-party assets, outreach or paid retries.
const encoder = new TextEncoder(), decoder = new TextDecoder();
const HEX = /^[a-f0-9]{64}$/;
const PROFILE = /^https:\/\/www\.linkedin\.com\/in\/[A-Za-z0-9_%~-]+\/?$/;
const COMPANY = /^https:\/\/www\.linkedin\.com\/company\/[A-Za-z0-9_-]+\/$/;
const STATUS = new Set(['verified','unverified','catch_all','unavailable','user_managed']);
const headers = {'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
  'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"};
const json = (data, status=200) => new Response(JSON.stringify(data),{status,headers:{...headers,'Content-Type':'application/json'}});
const page = (ok) => new Response(ok ? 'Apollo connected. Return to CV Studio. You can close this tab.' :
  'Apollo sign-in was declined or interrupted. Return to CV Studio and check your account permissions before connecting again.',
  {headers:{...headers,'Content-Type':'text/plain; charset=utf-8'}});
const random = () => Array.from(crypto.getRandomValues(new Uint8Array(32)), b=>b.toString(16).padStart(2,'0')).join('');
export const digest = async text => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(text))),b=>b.toString(16).padStart(2,'0')).join('');
const b64 = bytes => btoa(String.fromCharCode(...bytes));
const bytes = value => Uint8Array.from(atob(value),c=>c.charCodeAt(0));
async function key(env) {
  if (!HEX.test(env.TOKEN_KEY || '')) throw Error('configuration');
  return crypto.subtle.importKey('raw',Uint8Array.from(env.TOKEN_KEY.match(/../g),h=>parseInt(h,16)),'AES-GCM',false,['encrypt','decrypt']);
}
export async function seal(env, value, identity) {
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const encrypted=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:encoder.encode(identity)},await key(env),encoder.encode(JSON.stringify(value)));
  return b64(iv)+'.'+b64(new Uint8Array(encrypted));
}
export async function unseal(env, value, identity) {
  const [iv, data]=value.split('.');
  return JSON.parse(decoder.decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:bytes(iv),additionalData:encoder.encode(identity)},await key(env),bytes(data))));
}
const statement = (env, sql, ...args) => env.DB.prepare(sql).bind(...args);
async function bodyJSON(request) {
  if (!(request.headers.get('Content-Type') || '').startsWith('application/json')) throw Error('input');
  const reader=request.body?.getReader(); if(!reader) throw Error('input');
  let size=0, chunks=[];
  try { for(;;) { const {value,done}=await reader.read(); if(done) break; size+=value.length; if(size>16384) throw Error('input'); chunks.push(value); } }
  finally { await reader.cancel().catch(()=>{}); }
  const all=new Uint8Array(size);let offset=0;for(const chunk of chunks){all.set(chunk,offset);offset+=chunk.length;}
  const data=JSON.parse(decoder.decode(all));
  if(!data || typeof data!=='object' || Array.isArray(data)) throw Error('input');
  return data;
}
async function external(url, options, fetcher) {
  const response=await fetcher(url,{...options,redirect:'manual',signal:AbortSignal.timeout(18000)});
  if(!response.ok) { await response.body?.cancel(); return {status:response.status}; }
  const reader=response.body.getReader();let length=0,chunks=[];
  try {for(;;){const {value,done}=await reader.read();if(done)break;length+=value.length;if(length>131072)throw Error('response');chunks.push(value);}}
  finally {await reader.cancel().catch(()=>{});}
  const raw=new Uint8Array(length);let offset=0;for(const chunk of chunks){raw.set(chunk,offset);offset+=chunk.length;}
  return {status:response.status,data:JSON.parse(decoder.decode(raw))};
}
function tokenRecord(data, now) {
  if(!data || typeof data.access_token!=='string' || !data.access_token || data.access_token.length>4096 ||
      typeof data.refresh_token!=='string' || !data.refresh_token || data.refresh_token.length>4096 ||
      !Number.isSafeInteger(data.expires_in) || data.expires_in<60 || data.expires_in>5184000 ||
      typeof data.scope!=='string' || !data.scope.split(/\s+/).includes('people_match') || !data.scope.split(/\s+/).includes('read_user_profile')) throw Error('token');
  return {access_token:data.access_token,refresh_token:data.refresh_token,expires:now+data.expires_in};
}
async function exchange(env, parameters, fetcher) {
  return external('https://app.apollo.io/api/v1/oauth/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded','Accept':'application/json'},
    body:new URLSearchParams({...parameters,client_id:env.APOLLO_CLIENT_ID,client_secret:env.APOLLO_CLIENT_SECRET}).toString()},fetcher);
}
const normalized = text => typeof text==='string' ? text.trim().replace(/\s+/g,' ').toLowerCase() : '';
// Apollo returns LinkedIn links as http://www.linkedin.com/...; saved HR links
// are https. Compare the public handle only, never the scheme or host form.
const linkedinHandle = (value, kind) => {
  const m=/^(?:https?:\/\/)?(?:www\.|[a-z]{2}\.)?linkedin\.com\/(in|company)\/([A-Za-z0-9_%~-]+)\/?$/i.exec(String(value || '').trim());
  return m && m[1].toLowerCase()===kind ? m[2].toLowerCase() : '';
};
const LEGAL = new Set(['pt','tbk','sdn','bhd','berhad','pte','ltd','limited','inc','llc','corp','corporation','co','plc','gmbh','the']);
const nameWords = text => normalized(text).replace(/[^a-z0-9]+/g,' ').split(' ').filter(word=>word && !LEGAL.has(word));
function sameCompanyName(a, b) {
  const [short,long]=[nameWords(a),nameWords(b)].sort((x,y)=>x.length-y.length);
  return short.length>0 && short.every(word=>long.includes(word));
}
export function emailResult(data, expected) {
  const person=data?.person;
  if(!person) return {state:'not_found'};
  const profile=linkedinHandle(person.linkedin_url,'in');
  const org=person.organization;
  const company=linkedinHandle(org?.linkedin_url,'company');
  const companyMatches=(company && (company===linkedinHandle(expected.company_url,'company') || company===expected.company_id)) ||
    sameCompanyName(org?.name,expected.company);
  if(!profile || profile!==linkedinHandle(expected.url,'in') || !companyMatches || data.match_confidence==='low' || data.match_confidence==='none') return {state:'mismatch'};
  const email=person.email;
  if(typeof email!=='string' || email.length>254 || !/^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$/.test(email) ||
      /@(gmail|googlemail|yahoo|hotmail|outlook|live|aol|icloud|protonmail|proton|mail|gmx)\./i.test(email)) return {state:'not_found'};
  return {state:'found',email,email_status:STATUS.has(person.email_status)?person.email_status:'unknown'};
}
function validPerson(p) {
  return p && typeof p.url==='string' && typeof p.company_url==='string' && typeof p.company_id==='string' && PROFILE.test(p.url) && COMPANY.test(p.company_url) && /^[0-9]{1,24}$/.test(p.company_id) &&
    typeof p.name==='string' && p.name.trim() && p.name.length<=200 && typeof p.company==='string' && p.company.trim() && p.company.length<=200 &&
    !/[\x00-\x1f\x7f]/.test(p.name+p.company);
}
async function authenticate(env, data, now) {
  if(!HEX.test(data.connection_id || '') || !HEX.test(data.secret || '')) return null;
  return statement(env,'SELECT * FROM connections WHERE id=? AND proof=? AND expires>?',data.connection_id,await digest(data.secret),now).first();
}
async function operationResult(env, connection, operation) {
  if(!operation) return {state:'unconfirmed'};
  if(operation.state==='done') return unseal(env,operation.cipher,connection.id+':'+operation.id);
  return {state:'unconfirmed'};
}
async function callback(request, env, now, fetcher) {
  const query=new URL(request.url).searchParams, id=query.get('state');
  if(!HEX.test(id || '') || query.getAll('state').length!==1 || query.getAll('code').length>1) return page(false);
  const flow=await statement(env,"UPDATE flows SET status='exchanging' WHERE id=? AND status='pending' AND expires>? RETURNING *",id,now).first();
  if(!flow) return page(false); // Never replay a code exchange, including after a timeout.
  try {
    if(query.has('error') || query.has('error_message') || query.has('status_code') || !query.get('code') || query.get('code').length>2048) throw Error('authorization');
    const reply=await exchange(env,{grant_type:'authorization_code',code:query.get('code'),redirect_uri:env.PUBLIC_ORIGIN+'/callback'},fetcher);
    if(reply.status!==200) throw Error('authorization');
    const tokens=tokenRecord(reply.data,now);
    const profile=await external('https://app.apollo.io/api/v1/users/api_profile',{headers:{Authorization:'Bearer '+tokens.access_token,Accept:'application/json'}},fetcher);
    const user=profile.data?.user || profile.data;
    const name=user?.name || [user?.first_name,user?.last_name].filter(Boolean).join(' ') || user?.email;
    if(profile.status!==200 || !user?.id || typeof name!=='string' || !name.trim() || name.length>160 || /[\x00-\x1f\x7f]/.test(name)) throw Error('identity');
    const cipher=await seal(env,{...tokens,name},id);
    await env.DB.batch([
      statement(env,"INSERT INTO connections(id,proof,cipher,expires) SELECT id,proof,?,? FROM flows WHERE id=? AND status='exchanging' AND expires>?",cipher,now+2592000,id,now),
      statement(env,"UPDATE flows SET status='connected' WHERE id=? AND status='exchanging'",id)
    ]);
    return page(Boolean(await statement(env,'SELECT id FROM connections WHERE id=?',id).first()));
  } catch {
    await statement(env,"UPDATE flows SET status='failed' WHERE id=? AND status='exchanging'",id).run();
    return page(false);
  }
}
async function reveal(env, data, connection, now, fetcher) {
  if(!HEX.test(data.operation_id || '') || !validPerson(data.person) || data.confirmed!==true) return json({error:'Confirm a valid person lookup.'},400);
  const p=data.person, fingerprint=await digest(JSON.stringify([p.url.replace(/\/$/,''),p.company,p.company_id,p.company_url]));
  let previous=await statement(env,'SELECT * FROM operations WHERE connection_id=? AND id=?',connection.id,data.operation_id).first();
  if(previous) return previous.fingerprint===fingerprint ? json(await operationResult(env,connection,previous)) : json({error:'Operation identity changed.'},409);
  const inserted=await statement(env,"INSERT OR IGNORE INTO operations(connection_id,id,fingerprint,state,expires) VALUES(?,?,?,'pending',?)",connection.id,data.operation_id,fingerprint,now+86400).run();
  if(!inserted.meta.changes) return json({state:'unconfirmed'});
  let result={state:'unconfirmed'}, claimed=false;
  try {
    const active=await statement(env,'UPDATE connections SET busy=1 WHERE id=? AND busy=0 AND reauth=0 AND expires>? RETURNING *',connection.id,now).first();
    if(!active) {result={state:connection.reauth?'auth_required':'limited'};}
    else {
      claimed=true;
      let credentials=await unseal(env,active.cipher,connection.id);
      if(credentials.expires<now+60) {
        // Refresh-token rotation is also non-replayable after ambiguity.
        await statement(env,'UPDATE connections SET reauth=1 WHERE id=?',connection.id).run();
        const refresh=await exchange(env,{grant_type:'refresh_token',refresh_token:credentials.refresh_token},fetcher);
        if(refresh.status!==200) throw Error('refresh');
        credentials={...tokenRecord(refresh.data,now),name:credentials.name};
        const updated=await statement(env,'UPDATE connections SET cipher=?,reauth=0 WHERE id=?',await seal(env,credentials,connection.id),connection.id).run();
        if(!updated.meta.changes) throw Error('disconnected');
      }
      const params=new URLSearchParams({linkedin_url:p.url,name:p.name,organization_name:p.company,
        reveal_personal_emails:'false',reveal_phone_number:'false',run_waterfall_email:'false',run_waterfall_phone:'false'});
      const reply=await external('https://api.apollo.io/api/v1/people/match?'+params,{method:'POST',headers:{Authorization:'Bearer '+credentials.access_token,Accept:'application/json'},body:''},fetcher);
      result=reply.status===200 ? emailResult(reply.data,p) : {state:reply.status===401?'auth_required':[402,403,429].includes(reply.status)?'limited':'unconfirmed'};
      if(reply.status===401) await statement(env,'UPDATE connections SET reauth=1 WHERE id=?',connection.id).run();
    }
    await statement(env,"UPDATE operations SET state='done',cipher=? WHERE connection_id=? AND id=?",await seal(env,result,connection.id+':'+data.operation_id),connection.id,data.operation_id).run();
  } catch {result={state:'unconfirmed'};}
  finally {if(claimed) await statement(env,'UPDATE connections SET busy=0 WHERE id=?',connection.id).run();}
  return json(result);
}
export async function handle(request, env, fetcher=fetch, now=Math.floor(Date.now()/1000)) {
  try {
    const url=new URL(request.url);
    if(url.origin!==env.PUBLIC_ORIGIN) return json({error:'Service setup is incomplete.'},503);
    // Apollo's registration form verifies the callback before issuing the
    // client secret. This public probe contains no state, account or token.
    if(['GET','HEAD'].includes(request.method) && url.pathname==='/callback' && !url.search) return new Response(request.method==='HEAD'?null:'CV Studio Apollo callback. Sign-in requires completed owner setup.',
      {headers:{...headers,'Content-Type':'text/plain; charset=utf-8','Access-Control-Allow-Origin':'*'}});
    if(!env.APOLLO_CLIENT_ID || !env.APOLLO_CLIENT_SECRET || !HEX.test(env.TOKEN_KEY || '')) return json({error:'Service setup is incomplete.'},503);
    if(request.method==='GET' && url.pathname==='/callback') return await callback(request,env,now,fetcher);
    if(request.method!=='POST' || url.search || !['/start','/poll','/cancel','/disconnect','/reveal','/lookup-status'].includes(url.pathname)) return json({error:'Unsupported action.'},404);
    const data=await bodyJSON(request), action=url.pathname;
    if(action==='/start') {
      if(!HEX.test(data.proof_hash || '')) return json({error:'Invalid sign-in request.'},400);
      const ip=await digest(env.TOKEN_KEY+'|'+(request.headers.get('CF-Connecting-IP') || 'unknown'));
      const count=await statement(env,'SELECT COUNT(*) AS n FROM flows WHERE ip_hash=? AND created>?',ip,now-3600).first();
      if(count.n>=100) return json({error:'Sign-in limit reached.'},429);
      const id=random();await statement(env,"INSERT INTO flows VALUES(?,?,'pending',?,?,?)",id,data.proof_hash,now+600,now,ip).run();
      const params=new URLSearchParams({client_id:env.APOLLO_CLIENT_ID,redirect_uri:env.PUBLIC_ORIGIN+'/callback',response_type:'code',scope:'read_user_profile app_scopes people_match',state:id});
      return json({flow_id:id,authorization_url:'https://app.apollo.io/#/oauth/authorize?'+params});
    }
    if(action==='/poll' || action==='/cancel') {
      if(!HEX.test(data.flow_id || '') || !HEX.test(data.secret || '')) return json({error:'Sign-in expired.'},401);
      const flow=await statement(env,'SELECT * FROM flows WHERE id=? AND proof=? AND expires>?',data.flow_id,await digest(data.secret),now).first();
      if(!flow) return json({error:'Sign-in expired.'},401);
      if(action==='/cancel') {
        await env.DB.batch([statement(env,"UPDATE flows SET status='cancelled' WHERE id=?",flow.id),statement(env,'DELETE FROM connections WHERE id=?',flow.id)]);
        return json({state:'cancelled'});
      }
      if(flow.status==='connected') {
        const connection=await authenticate(env,{connection_id:flow.id,secret:data.secret},now);
        if(!connection) return json({state:'failed'});
        const credentials=await unseal(env,connection.cipher,connection.id);
        return json({state:'connected',connection_id:connection.id,name:credentials.name});
      }
      return json({state:['pending','exchanging'].includes(flow.status)?'pending':'failed'});
    }
    const connection=await authenticate(env,data,now);
    if(!connection) return json({error:'Reconnect Apollo.'},401);
    if(action==='/disconnect') {await statement(env,'DELETE FROM connections WHERE id=?',connection.id).run();return json({connected:false});}
    if(action==='/lookup-status') {
      if(!HEX.test(data.operation_id || '')) return json({error:'Invalid lookup.'},400);
      const op=await statement(env,'SELECT * FROM operations WHERE connection_id=? AND id=? AND expires>?',connection.id,data.operation_id,now).first();
      return json(await operationResult(env,connection,op));
    }
    return await reveal(env,data,connection,now,fetcher);
  } catch {return json({error:'The action could not be confirmed. No provider request was repeated.'},503);}
}
export default {
  fetch(request,env) {return handle(request,env);},
  async scheduled(event,env) {
    const now=Math.floor(Date.now()/1000);
    await env.DB.batch([statement(env,'DELETE FROM operations WHERE expires<?',now),statement(env,'DELETE FROM flows WHERE expires<?',now),statement(env,'DELETE FROM connections WHERE expires<?',now)]);
  }
};
