const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const root=path.join(__dirname,'..'),source=fs.readFileSync(path.join(root,'vendor/linkedin-companion/worker.js'),'utf8');
const url='https://www.linkedin.com/jobs/view/1234567890',search='https://www.linkedin.com/jobs/search-results/?keywords=finance';
function fixture(){
  let hooks;
  const state={session:{},saved:[],appDoc:'app-document',wrong:false,hold:null,release:null};
  const tabs=new Map([[1,{id:1,url:'http://127.0.0.1:5000/',status:'complete'}],[2,{id:2,url:search,status:'complete'}]]);
  const chrome={storage:{session:{get:async key=>({[key]:structuredClone(state.session[key]||null)}),set:async data=>Object.assign(state.session,structuredClone(data))}},
    action:{onClicked:{addListener:fn=>hooks.arm=fn},setBadgeText:async()=>{}},
    tabs:{onRemoved:{addListener:()=>{}},onUpdated:{addListener:fn=>hooks.updated=fn},onActivated:{addListener:()=>{}},
      get:async id=>({...tabs.get(id)}),query:async()=>[...tabs.values()],
      sendMessage:async(id,message,options)=>{assert.equal(id,1);if(options.documentId!==state.appDoc)throw Error('Stale app');state.saved.push(message);return {ok:true,folder:'Priority',duplicate:state.saved.length>1}},
      create:async()=>{throw Error('A direct pick must not create a tab')},update:async()=>{throw Error('A direct pick must not navigate')},remove:async()=>{throw Error('A direct pick must not close a tab')}},
    scripting:{executeScript:async args=>{
      if(args.files)return [{}];
      if(!args.args){if(args.target.documentIds?.[0]&&args.target.documentIds[0]!==state.appDoc)throw Error('Stale app');return [{result:true,documentId:state.appDoc}]}
      if(state.hold){await state.hold;state.hold=null}
      return [{result:{url:state.wrong?'https://www.linkedin.com/jobs/view/999':args.args[0],company:'Example Finance',role:'Finance Manager',description:'Visible ad',description_truncated:true}}];
    }},runtime:{onMessage:{addListener:fn=>hooks.message=fn}}};
  const boot=()=>{hooks={};vm.runInContext(source,vm.createContext({chrome,URL,Map,Set,Date,setTimeout,clearTimeout,crypto:{randomUUID:()=> 'a'.repeat(32)}}))};boot();
  const app=()=>({tab:{id:1},documentId:state.appDoc,url:tabs.get(1).url});
  const sender=()=>({tab:{id:2},documentId:'linkedin-document',frameId:0,url:tabs.get(2).url});
  const pick=(patch={})=>new Promise(resolve=>hooks.message({kind:'sourcer_job_pick',url},{...sender(),...patch},resolve));
  const rpc=(action,args={})=>new Promise(resolve=>hooks.message({kind:'sourcer',action,args},app(),resolve));
  return {state,tabs,boot,pick,rpc,arm:()=>hooks.arm(tabs.get(1)),reload:()=>hooks.updated(1,{status:'loading'})};
}
(async()=>{
  const f=fixture();assert((await f.pick()).error);assert.equal(f.state.saved.length,0);await f.arm();
  assert((await f.pick({frameId:1})).error);assert((await f.pick({url:'https://attacker.invalid/jobs/search/'})).error);
  assert((await f.pick()).result.ok);assert.equal(f.state.saved[0].record.url,url);assert.equal(f.state.saved[0].record.company,'Example Finance');
  f.boot();assert((await f.pick()).result.duplicate,'bound picks survive normal worker suspension');
  const run='b'.repeat(32);await f.rpc('jobSearchBegin',{run_id:run,max_pages:1,use_open:true,source_tab_id:2});assert.match((await f.pick()).error,/current search/);await f.rpc('end',{run_id:run});
  f.state.wrong=true;const before=f.state.saved.length;assert((await f.pick()).error);assert.equal(f.state.saved.length,before);f.state.wrong=false;
  f.tabs.get(2).pendingUrl='https://www.linkedin.com/login';assert((await f.pick()).error);delete f.tabs.get(2).pendingUrl;
  f.state.hold=new Promise(resolve=>{f.state.release=resolve});const pending=f.pick();await new Promise(resolve=>setTimeout(resolve,0));assert((await f.pick()).error);f.state.release();assert((await pending).result.ok);
  f.state.appDoc='new-document';assert((await f.pick()).error,'stale destination document cannot receive a save');assert.equal(f.state.saved.length,before+1);
  await f.reload();assert((await f.pick()).error);
  console.log('Direct LinkedIn picks: exact app/document binding, top-frame host/identity checks, no tab actions, suspension, busy/concurrency and stale destination protection passed');
})().catch(error=>{console.error(error);process.exitCode=1});
