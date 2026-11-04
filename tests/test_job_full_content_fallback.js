const assert=require('assert/strict'),{fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function until(check){for(let i=0;i<200;i++){if(check())return;await tick();}assert(check(),'full-ad workflow did not settle');}
const reads=f=>f.calls.filter(call=>call.action==='jobFromLink');
const lookups=f=>f.requests.filter(request=>request.action==='lookup');
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const response=record=>({ok:true,json:async()=>({record})});
const publicAd=url=>({url,role:'Database Administrator',company:'Fictional Employer',description:'Public full job description',description_rich:[{tag:'p',children:[{tag:'strong',children:[{text:'Public full job description'}]}]}],description_truncated:false});
function failingBrowser(f,code){f.state.onRPC=(message,reply)=>{
 if(message.action==='jobReadCancel'){reply(true);return true;}
 if(message.action!=='jobFromLink')return false;
 reply(null,{message:'Synthetic browser layout failure',code});return true;
};}
async function background(f){await f.init();f.state.backgroundCapable=true;await f.el('SearchStart').click();}
(async()=>{
 for(const code of ['HR_AD_TIMEOUT','HR_AD_LAYOUT','HR_AD_EMPTY']){
  const f=fixture(),before=structuredClone(f.state.records);failingBrowser(f,code);
  f.state.onRequest=data=>data.action==='lookup'?response(publicAd(data.url)):null;
  await background(f);await until(()=>f.el('BackgroundStop').hidden);
  assert.equal(reads(f).length,3);assert.equal(lookups(f).length,3,'one independent public read per browser failure');
  assert.match(f.el('BackgroundStatus').textContent,/3 of 3 full ads ready/);
  assert(f.el('PreviewContent').querySelectorAll('strong').length,'public rich formatting is retained');
  assert.deepEqual(f.state.records,before,'public fallback does not overwrite saved ads');
  await f.el('PreviewRead').click();assert.equal(reads(f).length,3);assert.equal(lookups(f).length,3,'cached public content is reused');
 }
 const legacy=fixture();legacy.state.onRPC=(message,reply)=>{
  if(message.action!=='jobFromLink')return false;
  reply(null,'The LinkedIn ad did not finish loading. Open it in your browser, wait for the page to load, then try again.');return true;
 };
 legacy.state.onRequest=data=>data.action==='lookup'?response(publicAd(data.url)):null;
 await background(legacy);await until(()=>legacy.el('BackgroundStop').hidden);
 assert.equal(reads(legacy).length,3);assert.equal(lookups(legacy).length,3);assert.match(legacy.el('BackgroundStatus').textContent,/3 of 3/,'the old fixed loading error still falls back and never stops the queue');
 const manual=fixture();await manual.init();await manual.el('SearchStart').click();
 failingBrowser(manual,'HR_AD_LAYOUT');manual.state.onRequest=data=>data.action==='lookup'?response(publicAd(data.url)):null;
 await manual.el('PreviewRead').click();assert.equal(lookups(manual).length,1);assert.match(text(manual.el('PreviewContent')),/Public full job description/);

 for(const code of ['HR_ACCESS_REQUIRED','HR_STOPPED','HR_AD_UNAVAILABLE','HR_PAGE_CHANGED']){
  const f=fixture();failingBrowser(f,code);await background(f);await until(()=>f.el('BackgroundStop').hidden);
  assert.equal(lookups(f).length,0,'no public fallback around access, cancellation or identity failures: '+code);
 }
 for(const failure of ['wrong-job','busy']){
  const f=fixture();failingBrowser(f,'HR_AD_TIMEOUT');f.state.onRequest=data=>{
   if(data.action!=='lookup')return;
   if(failure==='wrong-job')return response(publicAd('https://www.linkedin.com/jobs/view/999'));
   return {ok:false,json:async()=>({error:'Synthetic public reader '+failure,code:failure==='busy'?'JOB_AD_BUSY':'JOB_AD_RATE_LIMITED'})};
  };
  await background(f);await until(()=>f.el('BackgroundStop').hidden);
  assert.equal(lookups(f).length,1,'public restrictions and wrong-ad responses pause the queue without replay');
  assert.equal(reads(f).length,1);assert.equal(f.el('SearchResults').children.length,3);
  assert(!text(f.el('PreviewContent')).includes('Public full job description'),'unconfirmed content never replaces the summary');
 }
 // A limit on the public transport must not stop healthy browser reads.
 const mixed=fixture(),before=structuredClone(mixed.state.records);
 mixed.state.onRPC=(message,reply)=>{
  if(message.action!=='jobFromLink')return false;
  if(reads(mixed).length===2)return false;
  reply(null,{message:'Synthetic browser layout failure',code:'HR_AD_LAYOUT'});return true;
 };
 mixed.state.onRequest=data=>data.action==='lookup'?{ok:false,json:async()=>({error:'Synthetic public rate limit',code:'JOB_AD_RATE_LIMITED',retry_after_seconds:120})}:null;
 await background(mixed);await until(()=>mixed.el('BackgroundStop').hidden);
 assert.equal(reads(mixed).length,3,'all remaining ads are still tried with the companion');
 assert.equal(lookups(mixed).length,1,'the public transport is not retried after its rate limit');
 assert.match(mixed.el('BackgroundStatus').textContent,/1 of 3 full ads ready.*2 could not load.*Public reads paused; Chrome companion only/);
 assert.match(text(mixed.el('SearchResults').children[1]),/Full ad captured/);assert.deepEqual(mixed.state.records,before);
 await mixed.el('PreviewRead').click();assert.equal(lookups(mixed).length,1,'manual retries also honor the same cooldown');
 mixed.state.onRPC=null;await mixed.el('PreviewRead').click();assert.equal(lookups(mixed).length,1,'a manual companion success stays usable during the public cooldown');
 assert.match(mixed.el('BackgroundStatus').textContent,/2 of 3 full ads ready/);

 for(const retry_after_seconds of [2,90000,undefined,0,-1,'2',Number.MAX_SAFE_INTEGER]){
  let now=1000000;class Clock extends Date{static now(){return now;}}
  const f=fixture({activity:{Date:Clock}});failingBrowser(f,'HR_AD_TIMEOUT');
  f.state.onRequest=data=>{
   if(data.action!=='lookup')return;
   if(lookups(f).length===1)return {ok:false,json:async()=>({error:'Synthetic public rate limit',code:'JOB_AD_RATE_LIMITED',retry_after_seconds})};
   return response(publicAd(data.url));
  };
  await background(f);await until(()=>f.el('BackgroundStop').hidden);assert.equal(reads(f).length,3);assert.equal(lookups(f).length,1);
  await f.el('SearchClear').click();await f.el('SearchStart').click();await until(()=>f.el('BackgroundStop').hidden);
  assert.equal(lookups(f).length,1,'clearing/new searches do not reset a known public cooldown');
  const pause=[2,90000].includes(retry_after_seconds)?retry_after_seconds*1000:300000;
  now+=pause-1;await f.el('PreviewRead').click();assert.equal(lookups(f).length,1,'no public read before the cooldown expires');
  now++;await f.el('PreviewRead').click();assert.equal(lookups(f).length,2,'a later explicit read may use public content after the cooldown');
  assert.match(text(f.el('PreviewContent')),/Public full job description/);
 }
 const cancel=fixture();failingBrowser(cancel,'HR_AD_LAYOUT');let release,signal;
 cancel.state.onRequest=(data,options)=>{
  if(data.action!=='lookup')return;
  signal=options.signal;return new Promise(resolve=>{release=()=>resolve(response(publicAd(data.url)));});
 };
 await background(cancel);await until(()=>release);
 const stopping=cancel.el('BackgroundStop').click();assert(signal.aborted,'Stop aborts the pending public request');
 release();await stopping;
 assert.equal(lookups(cancel).length,1);assert.equal(reads(cancel).length,1);
 assert(!text(cancel.el('PreviewContent')).includes('Public full job description'),'late public results after Stop are ignored');
 console.log('Full-ad fallback: one public read after layout failures, exact job identity, rich cache, manual/background capture, access/identity/cancel boundaries, public cooldown with continued companion reads, public busy stops and aborted late results passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
