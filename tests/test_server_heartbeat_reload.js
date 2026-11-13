// The page reloads itself after a connection gap only when the server process
// really restarted. A gap with the same server (queued requests, sleep, a busy
// server) must leave the page, its running scans and unsaved results alone.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/server-heartbeat.js'),'utf8');
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function fixture(online=true){
  const state={online,boot:'aaaaaaaaaaaaaaaa',reloads:0,intervals:[],timeouts:[],banners:[],removed:0,requests:0};
  const element=()=>({id:'',style:{},innerHTML:'',textContent:'',children:[],appendChild(child){this.children.push(child);},remove(){state.removed++;}});
  const document={body:{prepend(node){state.banners.push(node);}},createElement:element,querySelector:()=>null,getElementById:()=>null,visibilityState:'visible',addEventListener(){}};
  const fetch=()=>{state.requests++;return state.online?Promise.resolve({ok:true,status:204,headers:state.boot===null?undefined:{get:name=>name==='X-CV-Studio-Boot'?state.boot:null}}):Promise.reject(Error('unreachable'));};
  let id=0;
  vm.runInContext(source,vm.createContext({console,document,window:{addEventListener(){}},fetch,location:{reload(){state.reloads++;}},Date,Promise,
    setInterval(listener,ms){state.intervals.push({id:++id,listener,ms});return id;},clearInterval(value){state.intervals=state.intervals.filter(row=>row.id!==value);},
    setTimeout(listener,ms){state.timeouts.push({listener,ms});return state.timeouts.length;},clearTimeout(){}}));
  const steady=()=>state.intervals.find(row=>row.ms===20000);
  const miss=async count=>{state.online=false;for(let i=0;i<count;i++){steady().listener();await flush();}};
  const recover=async()=>{state.online=true;steady().listener();await flush();};
  return {state,miss,recover,reloadTimer:()=>state.timeouts.find(row=>row.ms===1500)};
}
(async()=>{
  // Same server after the gap: banner is removed, nothing reloads, pings go on.
  let f=fixture();await flush();
  await f.miss(4);
  assert.equal(f.state.banners.length,1,'the connection banner is shown after four misses');
  await f.recover();
  assert.equal(f.state.removed,1,'the banner is removed once the same server answers');
  assert.equal(f.reloadTimer(),undefined,'no reload is scheduled');assert.equal(f.state.reloads,0);
  assert(!f.state.intervals.some(row=>row.ms===2500),'the fast recovery burst stops');
  const before=f.state.requests;await f.recover();assert.equal(f.state.requests,before+1,'steady pings continue');
  // A second gap behaves the same way.
  await f.miss(4);await f.recover();assert.equal(f.state.reloads,0);assert.equal(f.reloadTimer(),undefined);

  // The server restarted during the gap: reload once, exactly as before.
  f=fixture();await flush();
  await f.miss(4);f.state.boot='bbbbbbbbbbbbbbbb';await f.recover();
  assert(f.state.banners[0].innerHTML.includes('reloading automatically'));
  assert(f.reloadTimer(),'a restarted server still reloads the page');f.reloadTimer().listener();assert.equal(f.state.reloads,1);

  // A server that does not identify its process keeps the previous behaviour.
  f=fixture();f.state.boot=null;await flush();
  await f.miss(4);await f.recover();
  assert(f.reloadTimer());f.reloadTimer().listener();assert.equal(f.state.reloads,1);

  // The page first loaded during an outage, so it never saw the old process.
  f=fixture(false);await flush();
  await f.miss(4);await f.recover();
  assert(f.reloadTimer(),'an unknown earlier process is treated as a restart');
  console.log('Heartbeat reloads only after a real server restart.');
})().catch(error=>{console.error(error);process.exitCode=1;});
