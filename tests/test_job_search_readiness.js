const assert=require('assert/strict'),fs=require('fs'),path=require('path'),vm=require('vm');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/job-search-walk.js'),'utf8');
const job=id=>({url:'https://www.linkedin.com/jobs/view/'+id,company:'Example',role:'Consultant'});
const snapshot=(id,page,patch={})=>({jobs:[job(id)],signature:job(id).url,page,hasNext:true,atBottom:true,...patch});
async function run(read,options={}){
  const calls=[],kept=[],finished=[],waiting=[];let reads=0,stopped=false;
  const context=vm.createContext({window:{},URL,Date:options.clock||Date,setTimeout:fn=>{fn();return 1}});vm.runInContext(source,context);
  const rpc=async(action,args)=>{calls.push(args.method);if(args.method==='readJobSearch')return read(++reads,()=>{stopped=true});return true};
  let error;
  try{await context.window.cvStudioJobSearch.walk({rpc,run:'a'.repeat(32),tab:20,pages:2,
    check:()=>{if(stopped)throw Error('Stopped.')},keep:s=>kept.push(s),page:i=>finished.push(i),
    full:()=>false,waiting:stage=>waiting.push(stage),...options});}catch(e){error=e}
  return {calls,kept,finished,waiting,error,reads};
}
(async()=>{
  // LinkedIn can take longer than the former 35 reads to hydrate either page.
  const slow=await run(n=>n<=45?{loading:true}:n===46?snapshot(100,1):n<=95?snapshot(100,1):snapshot(200,2,{hasNext:false}));
  assert(!slow.error,slow.error?.message);assert.deepEqual(slow.kept.map(s=>s.page),[1,2]);
  assert.equal(slow.calls.filter(x=>x==='nextJobSearch').length,1,'Next is clicked once, never retried');
  assert(slow.waiting.length,'bounded waiting reports progress');
  // A different active page can legitimately repeat the same promoted jobs.
  const repeated=await run(n=>snapshot(100,n===1?1:2,{hasNext:n===1}));
  assert(!repeated.error,repeated.error?.message);assert.deepEqual(repeated.finished,[0,1]);
  // Changed/reordered virtual cards on the OLD page are not a completed Next.
  const stale=await run(n=>n===1?snapshot(100,4):n<5?snapshot(200,4):snapshot(300,5,{hasNext:false}));
  assert(!stale.error,stale.error?.message);assert.deepEqual(stale.kept.map(s=>s.jobs[0].url),[job(100).url,job(300).url]);
  const missingMarker=await run(n=>n===1?snapshot(100,1):n<5?snapshot(200,undefined):snapshot(300,2,{hasNext:false}));
  assert(!missingMarker.error);assert.equal(missingMarker.kept[1].jobs[0].url,job(300).url);
  const jumped=await run(n=>snapshot(n===1?100:300,n===1?1:3));
  assert(jumped.error,'a user-driven page jump must not be counted as the requested next page');assert.equal(jumped.kept.length,1);
  const forever=await run(()=>snapshot(100,1));
  assert(forever.error);assert(forever.reads<=132,'polling stays bounded');assert.equal(forever.kept.length,1);
  assert.equal(forever.calls.filter(x=>x==='nextJobSearch').length,1);
  let elapsed=0;
  const wall=await run(()=>{elapsed+=15000;return {loading:true}},{clock:class extends Date{static now(){return elapsed}}});
  assert(wall.error);assert.equal(wall.reads,3,'slow transport counts toward the 45-second observation deadline');
  const stopped=await run((n,stop)=>{if(n===12)stop();return {loading:true}});
  assert.match(stopped.error.message,/Stopped/);assert.equal(stopped.kept.length,0);assert.equal(stopped.reads,12);
  const empty=await run(n=>n===1?snapshot(100,1):{jobs:[],signature:'',empty:true,loading:false});
  assert(!empty.error);assert.equal(empty.kept.length,1);
  const legacy=await run(n=>snapshot(n===1?100:200,undefined,{hasNext:n===1}));
  assert(!legacy.error,'older companion without page numbers still uses changed result identity');
  const notClicked=await run(()=>snapshot(100,1),{rpc:async(action,args)=>args.method==='readJobSearch'?snapshot(100,1):{loading:true}});
  assert.match(notClicked.error.message,/before changing pages/);assert.equal(notClicked.kept.length,1,'loading is not confirmation of a click');
  // Scroll observations remain on the current page; a manual page change stops.
  const scrolled=await run(n=>snapshot(n===1?100:200,n===1?1:2,{atBottom:n!==1}));
  assert(scrolled.error);assert.equal(scrolled.kept.length,1);
  console.log('Jobs readiness: slow initial/next pages, repeated ads, stale/missing markers, jumps, bounded timeout, Stop, empty/legacy pages and non-replayed Next passed');
})().catch(error=>{console.error(error);process.exitCode=1});
