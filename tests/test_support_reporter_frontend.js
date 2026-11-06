/* Standalone support reporting; every HTTP/Outlook answer is fictional. */
const assert=require('assert/strict'),fs=require('fs'),vm=require('vm'),path=require('path');
class Element{
 constructor(tag='div'){Object.assign(this,{tagName:tag,handlers:{},children:[],style:{},value:'',textContent:'',disabled:false,hidden:false,open:false,files:[]});}
 addEventListener(type,fn){(this.handlers[type] ||= []).push(fn);}appendChild(value){this.children.push(value);return value;}
 setAttribute(name,value){this[name]=value;}showModal(){this.open=true;}close(){this.open=false;}focus(){this.focused=true;}remove(){}
 async click(){if(!this.disabled)for(const fn of this.handlers.click || [])await fn({target:this,preventDefault(){}});}
}
function fixture(){
 const nodes=new Map(),calls=[],downloads=[],confirms=[],blobs=new Map(),events={};let serial=0;
 const node=name=>{if(!nodes.has(name))nodes.set(name,new Element());return nodes.get(name);};
 const document={readyState:'complete',body:new Element('body'),getElementById:node,
  querySelector:()=>({textContent:'Job Leads',id:'viewJobLeads'}),addEventListener:(type,fn)=>events[type]=fn,
  createElement:tag=>{const item=new Element(tag);if(tag==='a')item.click=()=>{if(item.download)downloads.push({name:item.download,blob:blobs.get(item.href)});};return item;}};
 const state={consent:true,sends:0,result:'prepared',delivery:{recipient:'support@example.test',sender:'reporter@example.test',connected:true,can_send:true}};
 const window={cvDoctor:{supportReport:()=>('Fictional Doctor\napi_key="sk-proj-'+('FAKEVALUE'.repeat(7))+'"\nprivate@example.test')},addEventListener:(name,fn)=>events[name]=fn,confirm:message=>{confirms.push(message);return state.consent;}};
 const fetch=async(url,options)=>{
  assert.equal(url,'/diagnostics/support_bundle');const body=JSON.parse(options.body);calls.push(body);
  const reply=data=>({ok:true,json:async()=>({ok:true,...data})});
  if(body.action==='issue_status'){if(state.offline)throw Error('Fictional offline');return reply(state.delivery);}
  if(body.action==='issue_prepare'){
   const report_id=(++serial).toString(16).padStart(32,'0');state.result='prepared';
   return reply({report_id,preview_token:'a'.repeat(64),delivery:state.delivery,text:'Reviewed report '+report_id,doctor:body.doctor,runtime:{version:'test'},attachments:[{name:'doctor-report.txt',bytes:100}],screenshot:''});
  }
  if(body.action==='issue_send'){
   state.sends++;if(state.hold)await new Promise(resolve=>state.release=resolve);state.result='accepted';
   if(state.lost)throw Error('Fictional response lost');return reply({state:'accepted'});
  }
  if(body.action==='issue_result')return reply({state:state.result});
  if(body.action==='issue_discard')return reply({state:'discarded'});
  if(body.action==='issue_download')return {ok:true,blob:async()=>new Blob(['fictional report'])};
  throw Error('Unexpected request');
 };
 const context=vm.createContext({window,document,fetch,navigator:{userAgent:'Fictional Browser'},Intl,Date,Blob,Map,Set,Promise,console,
  URL:{createObjectURL:blob=>{const id='blob:'+blobs.size;blobs.set(id,blob);return id;},revokeObjectURL:id=>blobs.delete(id)},
  setTimeout:(fn)=>setTimeout(fn,0),clearTimeout});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/support-reporter.js'),'utf8'),context);
 const el=name=>node('cvSupport'+name);
 return {window,el,calls,downloads,confirms,state,events};
}
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
(async()=>{
 const f=fixture();f.events.error();assert.equal(f.calls.length,0,'recording an issue never sends it automatically');
 await f.window.cvStudioSupport.open();f.el('Description').value='A fictional JobAdder create is unconfirmed.';
 await f.el('Review').click();assert(!f.el('Preview').hidden && !f.el('Send').disabled);
 const request=f.calls.find(row=>row.action==='issue_prepare');assert(!request.doctor.includes('FAKEVALUE') && !request.doctor.includes('private@example.test'));
 f.state.consent=false;await f.el('Send').click();assert.equal(f.state.sends,0);assert.match(f.confirms[0],/support@example.test/);
 f.state.consent=true;f.state.hold=true;const first=f.el('Send').click();await tick();await f.el('Send').click();assert.equal(f.state.sends,1);
 f.state.release();await first;assert.match(f.el('Message').textContent,/Outlook accepted/);assert(f.el('Send').hidden);
 const edit=fixture();await edit.window.cvStudioSupport.open();edit.el('Description').value='First description';await edit.el('Review').click();
 const old=edit.calls.find(row=>row.action==='issue_prepare');await edit.el('Edit').click();edit.el('Description').value='Changed description';await edit.el('Review').click();await edit.el('Send').click();
 assert(edit.calls.some(row=>row.action==='issue_discard'));assert.equal(edit.calls.filter(row=>row.action==='issue_prepare').length,2);
 const sent=edit.calls.find(row=>row.action==='issue_send');assert.equal(sent.report_id,'2'.padStart(32,'0'));assert.equal(sent.confirmed,true);assert(!sent.description && !sent.to,'sending references the exact server-prepared packet');
 const lost=fixture();await lost.window.cvStudioSupport.open();lost.el('Description').value='Fictional issue';await lost.el('Review').click();lost.state.lost=true;await lost.el('Send').click();
 assert(!lost.el('Check').hidden && lost.el('Send').hidden);await lost.el('Check').click();assert.match(lost.el('Message').textContent,/Outlook accepted/);assert.equal(lost.state.sends,1,'status check never repeats send');
 const disconnected=fixture();disconnected.state.delivery.can_send=false;await disconnected.window.cvStudioSupport.open();disconnected.el('Description').value='Fictional offline issue';await disconnected.el('Review').click();assert(disconnected.el('Send').disabled);await disconnected.el('Download').click();assert.equal(disconnected.state.sends,0);assert.equal(disconnected.downloads.length,1);
 const offline=fixture();offline.state.offline=true;await offline.window.cvStudioSupport.open();await offline.el('SaveDoctor').click();assert.equal(offline.downloads.length,1);assert(!(await offline.downloads[0].blob.text()).includes('FAKEVALUE'));
 console.log('Support UI: automatic Doctor extraction, preview/confirmation, immutable review, double-send prevention, status recovery, offline download and no background email passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
