const assert=require('assert/strict'),{hrFixture}=require('./test_linkedin_company_hr');
const job='https://www.linkedin.com/jobs/view/1234567890',company='https://www.linkedin.com/company/example/';
function sourceFixture(){
  const f=hrFixture(),original=f.state.onScript;Object.assign(f.state,{companyReads:0,readerCompany:'',fastWait:true});
  f.state.onScript=args=>{
    const method=args.args?.[0];
    if(method===job){
      f.state.companyReads++;
      if(f.state.delayedSource>0){f.state.delayedSource--;return [{result:{loading:true}}];}
      const name=f.state.changing&&f.state.companyReads===1?'Old Employer':'ABC Corporate Business Solutions';
      const result=[{result:{url:job,company:name,company_url:f.state.noLink?'':company,role:'SAP Consultant',description:''}}];
      if(f.state.holdSource)return new Promise(resolve=>{f.state.releaseSource=()=>resolve(result)});
      return result;
    }
    if(method==='readHRCompany'){
      f.state.sourceConfirmed=args.args[1][2];
      return [{result:{company_id:'123',...(f.state.sourceConfirmed?{company_name:'ABC Group'}:{})}}];
    }
    if(method==='readHRSearch')f.state.readerCompany=args.args[1][0];
    return original(args);
  };
  f.capture=()=>f.rpc('jobFromLink',{url:job,company_only:true});
  f.start=patch=>f.beginHR({company:'ABC Corporate Business Solutions',job_url:job,...patch});
  return f;
}
module.exports={sourceFixture};
if(require.main===module)(async()=>{
  const f=sourceFixture();await f.arm();assert(!(await f.capture()).error);assert.equal(f.state.companyReads,2,'two consecutive source observations must agree');
  f.boot();const started=await f.start();assert(!started.error,started.error);const id=started.result.tab_id;
  let snapshot;for(let i=0;i<5;i++){f.boot();snapshot=await f.readHR(id);assert(!snapshot.error,snapshot.error);if(!snapshot.result.loading)break;}
  assert.equal(f.state.sourceConfirmed,true);assert.equal(f.state.readerCompany,'ABC Group');assert.equal(snapshot.result.company_name,'ABC Group');
  assert.equal((await f.start()).result.tab_id,id,'repeated Begin cannot consume another source or open another tab');
  const changing=sourceFixture();await changing.arm();changing.state.changing=true;assert(!(await changing.capture()).error);assert.equal(changing.state.companyReads,3,'a stale first employer must settle before capture');
  const loading=sourceFixture();await loading.arm();let injections=0;loading.state.onInject=()=>{if(++injections===1){const tab=[...loading.tabs.values()].find(t=>t.url===job);tab.status='loading';setTimeout(()=>{tab.status='complete'},0)}};
  assert(!(await loading.capture()).error);assert(injections>=2,'a same-job reload reinjects the reader into the committed document');assert.equal(loading.state.companyReads,2);
  for(const patch of [{job_url:'https://www.linkedin.com/jobs/view/999'},{company_url:'https://www.linkedin.com/company/other/'},{company:'Different Company'}]){
    const bad=sourceFixture();await bad.arm();await bad.capture();const count=bad.state.created.length;assert((await bad.start(patch)).error);assert.equal(bad.state.created.length,count,'source evidence cannot authorize another job, company URL or label');
  }
  const cold=sourceFixture();await cold.arm();assert((await cold.start()).error,'an app flag without observed employer evidence is insufficient');
  const stale=sourceFixture();await stale.arm();await stale.capture();stale.state.session.cvstudioLinkedinSessionV1.connection.jobCompany.at-=120001;stale.boot();assert((await stale.start()).error,'expired evidence cannot authorize a scan after restart');
  const missing=sourceFixture();await missing.arm();missing.state.noLink=true;assert((await missing.capture()).error);assert.equal(missing.state.companyReads,48);assert((await missing.start()).error,'a loaded name without a single employer link cannot authorize a scan');
  const manual=sourceFixture();await manual.arm();const manualID=(await manual.beginHR()).result.tab_id;await manual.readHR(manualID);assert.equal(manual.state.sourceConfirmed,false,'manual company pages keep the strict name match');
  console.log('HR source identity: exact job/employer evidence, stable reads, short-to-full labels, canonical company name, restart, expiry, manual boundaries and missing/changed sources passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
