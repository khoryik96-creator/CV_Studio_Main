const assert=require('assert/strict'),{fixture}=require('./test_job_search_frontend');
function make(){const events=[];const f=fixture({activity:{markTabRunning:tab=>{assert.equal(tab,'jobleads');events.push('running');return 7},markTabDone:(tab,token)=>{assert.equal(token,7);events.push('done')},markTabFailed:(tab,token)=>{assert.equal(token,7);events.push('failed')}}});f.activity=events;return f;}
async function held(f){for(let i=0;i<60&&!f.state.held;i++)await new Promise(resolve=>setTimeout(resolve,0));assert(f.state.held);}
(async()=>{
  const f=make();await f.init();assert.deepEqual(f.activity,[],'loading the module does not create a false scan notification');f.state.hold=true;
  const running=f.el('SearchStart').click();await held(f);assert.deepEqual(f.activity,['running']);f.el('SearchStop').click();f.state.held();await running;assert.deepEqual(f.activity,['running','done']);
  const bad=make();await bad.init();bad.state.connected=false;await bad.el('SearchStart').click();assert.deepEqual(bad.activity,['running','failed']);
  const invalid=make();await invalid.init();invalid.el('SearchPages').value='0';await invalid.el('SearchStart').click();assert.deepEqual(invalid.activity,[]);
  console.log('Job Leads activity: orange run token, Stop completion, error attention, no startup/invalid-input notifications passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
