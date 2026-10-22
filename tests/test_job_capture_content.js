const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/content.js'),'utf8');
class Element{
  constructor(tag='div'){Object.assign(this,{tagName:tag,dataset:{},style:{},children:[],events:{},textContent:'',disabled:false})}
  addEventListener(name,fn){this.events[name]=fn} setAttribute(name,value){this[name]=value}
  append(...nodes){for(const node of nodes){node.parent=this;node.parentElement=this;this.children.push(node)}} appendChild(node){this.append(node)}
  replaceChildren(...nodes){this.children=[];this.append(...nodes)} focus(){}
  contains(node){return node===this||this.children.some(child=>child.contains(node))}
  querySelectorAll(selector){return this.children.flatMap(node=>[...(node.tagName===selector?[node]:[]),...node.querySelectorAll(selector)])}
  querySelector(){return this.children.find(node=>node.dataset.cvstudioJobControls)||this.children.map(node=>node.querySelector()).find(Boolean)||null}
  remove(){this.parent.children=this.parent.children.filter(node=>node!==this)}
}
async function fixture(linkedin,layout='flex',options={}){
  const events={},state={messages:[],observer:null,reply:null,delivered:[],timers:new Map(),sequence:0};
  const card=new Element(),details=new Element(),root=new Element();card.display=layout==='grid'?'grid':'flex';card.direction='row';details.display='flex';details.direction=layout==='unsupported'?'row':'column';
  details.append(new Element('p'),new Element('p'),new Element('p'));card.append(new Element('img'),details);
  root.dataset.companionChannel='a'.repeat(32);root.dataset.companionActions='1';
  const document={body:new Element(),hidden:false,querySelectorAll:()=>[],createElement:tag=>new Element(tag),addEventListener:(name,fn)=>events[name]=fn,getElementById:()=>root};
  document.body.append(card);
  document.querySelectorAll=selector=>selector==='[data-cvstudio-job-folder]'?document.body.querySelectorAll('select'):[];
  const location={origin:linkedin?'https://www.linkedin.com':'http://127.0.0.1:5000',pathname:linkedin?'/jobs/search-results/':'/'};
  const window={addEventListener:(name,fn)=>events[name]=fn,postMessage:message=>state.delivered.push(message)};window.top=window;
  const chrome={runtime:{id:'extension-id',lastError:null,onMessage:{addListener:fn=>state.onRuntime=fn},sendMessage:(message,reply)=>{state.messages.push(message);state.reply=reply;if(message.operation==='folders'&&!state.manualFolders&&!options.hold)reply(options.fail?{error:'Synthetic folder connection failure'}:{result:{ok:true,saved:false,folder:'Priority',folders:['Priority']}})}}};
  state.targets=[{element:card,url:'https://www.linkedin.com/jobs/view/1234567890'}];
  const context=vm.createContext({window,document,location,chrome,Map,Set,MutationObserver:class{constructor(fn){state.observer=fn}observe(){}},
    setTimeout:fn=>{const id=++state.sequence;state.timers.set(id,fn);return id},clearTimeout:id=>state.timers.delete(id),
    getComputedStyle:el=>({display:el.display||'block',flexDirection:el.direction||'row'}),SourcerReader:{jobTargets:()=>state.targets}});
  vm.runInContext(source,context);
  await new Promise(resolve=>setImmediate(resolve));
  state.manualFolders=true;
  return {state,card,details,root,chrome,events,window,location,context,document,send:message=>events.message({source:window,origin:location.origin,data:message})};
}
(async()=>{
const li=await fixture(true);assert.equal(li.card.children.length,2,'controls do not become a competing native flex-row column');let controls=li.details.children.at(-1),button=controls.children[0];
assert.deepEqual(controls.children[1].children.map(option=>option.value),['','Priority'],'folders are ready before the first native menu opens');
assert.equal(li.state.messages.length,1,'one read-only catalog load per page, rather than one per card');li.state.messages=[];
assert.equal((await fixture(true,'grid')).details.children.length,4,'grid cards also use their existing vertical text column');
assert.equal((await fixture(true,'unsupported')).details.children.length,3,'unrecognized horizontal-only layouts are left untouched');
const click=trusted=>button.events.click({isTrusted:trusted,preventDefault(){},stopPropagation(){}});
click(false);assert.equal(li.state.messages.length,0,'page-script clicks cannot capture');let work=click(true);assert.equal(li.state.messages.length,1);
assert.equal(li.state.messages[0].kind,'sourcer_job_pick');assert.equal(button.disabled,true);
li.state.reply({error:'Connect CV Studio first'});await work;assert.equal(button.disabled,false);assert.equal(controls.children[4].textContent,'Connect CV Studio first');
work=click(true);li.state.reply({result:{ok:true,saved:true,folder:'Priority'}});await work;assert.match(button.textContent,/^Added/);assert.equal(button.disabled,false);
work=click(true);assert.equal(li.state.messages.at(-1).operation,'remove');li.state.reply({result:{ok:true,saved:false,folder:'Priority'}});await work;assert.equal(button.textContent,'Add to CV Studio');assert.match(controls.children[4].textContent,/recoverable/);
const select=controls.children[1];work=select.events.focus({isTrusted:true});assert.equal(li.state.messages.at(-1).operation,'folders');li.state.reply({result:{ok:true,saved:false,folders:['Priority'],folder:'Priority'}});await work;assert.equal(select.value,'Priority');
work=select.events.focus({isTrusted:true});assert.equal(li.state.messages.at(-1).operation,'folders');li.state.reply({result:{ok:true,saved:false,folders:['Priority','New externally'],folder:'Priority'}});await work;
assert(select.children.some(option=>option.value==='New externally'),'reopening a loaded menu refreshes existing folders');
select.value='';select.events.change({isTrusted:true,stopPropagation(){}});work=click(true);assert.equal(li.state.messages.at(-1).folder,'');li.state.reply({result:{ok:true,saved:true,folder:''}});await work;
controls.children[2].events.click({isTrusted:true,preventDefault(){},stopPropagation(){}});const editor=controls.children[3];assert.equal(editor.hidden,false);editor.children[0].value='SAP';
work=editor.children[1].events.click({isTrusted:true,preventDefault(){},stopPropagation(){}});assert.equal(li.state.messages.at(-1).operation,'create_folder');assert.equal(li.state.messages.at(-1).folder,'SAP');li.state.reply({result:{ok:true,saved:true,folder:'SAP',folders:['Priority','SAP']}});await work;assert.equal(select.value,'SAP');assert.equal(editor.hidden,true);
li.state.observer();for(const fn of [...li.state.timers.values()])fn();assert.equal(li.details.children.length,4,'DOM updates do not duplicate buttons');
vm.runInContext(source,li.context);assert.equal(li.details.children.length,4,'re-injection does not install a second observer/control');
const openFolders=select.events.pointerdown({isTrusted:true,stopPropagation(){}});li.state.reply({result:{ok:true,saved:true,folder:'Priority',folders:['Priority','SAP','Later']}});await openFolders;
assert.equal(select.value,'SAP','refresh preserves the folder explicitly chosen on this page');
const second=new Element(),secondColumn=new Element();second.display='flex';secondColumn.display='flex';secondColumn.direction='column';secondColumn.append(new Element('p'),new Element('p'));second.append(new Element('img'),secondColumn);li.document.body.append(second);
li.state.targets.push({element:second,url:'https://www.linkedin.com/jobs/view/1234567891'});
const beforeNewCard=li.state.messages.length;li.state.observer();for(const fn of [...li.state.timers.values()])fn();
const secondControls=secondColumn.children.at(-1),secondSelect=secondControls.children[1];
assert.equal(li.state.messages.length,beforeNewCard,'new cards reuse the shared catalog without repeated requests');assert.equal(secondSelect.value,'SAP');assert(secondSelect.children.some(option=>option.value==='Later'));
work=select.events.focus({isTrusted:true});const firstReply=li.state.reply;
const secondWork=secondSelect.events.focus({isTrusted:true});assert.equal(li.state.reply,firstReply,'simultaneous metadata refreshes are coalesced');
firstReply({result:{ok:true,saved:true,folder:'Priority',folders:['Priority','SAP','Across cards']}});await Promise.all([work,secondWork]);
assert(secondSelect.children.some(option=>option.value==='Across cards'));assert.equal(secondControls.children[0].textContent,'Add to CV Studio','the first ad status is never applied to another card');
work=select.events.focus({isTrusted:true});li.state.reply({error:'Synthetic transient failure'});await work;assert.equal(select.value,'SAP');assert.equal(select.disabled,false,'a failure retains the usable cached catalog');
work=controls.children[5].events.click({isTrusted:true,preventDefault(){},stopPropagation(){}});li.state.reply({result:{ok:true,saved:false,folders:['Priority'],folder:''}});await work;
assert.equal(select.value,'');assert.equal(secondSelect.value,'','deleted folders are removed from every menu without recreating them');
const failed=await fixture(true,'flex',{fail:true}),failedControls=failed.details.children.at(-1);
assert(failedControls.children[1].disabled);assert.match(failedControls.children[4].textContent,/connection failure/);
const failedCard=new Element(),failedColumn=new Element();failedColumn.append(new Element('p'),new Element('p'));failedCard.append(failedColumn);failed.document.body.append(failedCard);
failed.state.targets.push({element:failedCard,url:'https://www.linkedin.com/jobs/view/1234567892'});failed.state.observer();for(const fn of [...failed.state.timers.values()])fn();
assert.match(failedColumn.children.at(-1).children[4].textContent,/connection failure/,'new cards show the shared failure rather than loading forever');
work=failedControls.children[5].events.click({isTrusted:true,preventDefault(){},stopPropagation(){}});failed.state.reply({result:{ok:true,saved:false,folder:'Priority',folders:['Priority','Recovered']}});await work;
assert.equal(failedControls.children[1].disabled,false);assert(failedControls.children[1].children.some(option=>option.value==='Recovered'),'Refresh retries an initial failure without requiring a new focus event');
const timeout=await fixture(true,'flex',{hold:true}),timeoutControls=timeout.details.children.at(-1),lateReply=timeout.state.reply;
for(const fn of [...timeout.state.timers.values()])fn();await new Promise(resolve=>setImmediate(resolve));
assert.match(timeoutControls.children[4].textContent,/Refresh folders/);assert.equal(timeoutControls.children[5].disabled,false);
work=timeoutControls.children[5].events.click({isTrusted:true,preventDefault(){},stopPropagation(){}});timeout.state.reply({result:{ok:true,saved:false,folders:['Current'],folder:''}});await work;
lateReply({result:{ok:true,saved:false,folders:['Stale'],folder:''}});await new Promise(resolve=>setImmediate(resolve));
assert(timeoutControls.children[1].children.some(option=>option.value==='Current'));assert(!timeoutControls.children[1].children.some(option=>option.value==='Stale'),'late timed-out reads cannot overwrite fresh folders');
li.events.visibilitychange();for(const fn of [...li.state.timers.values()])fn();assert.equal(li.state.messages.at(-1).operation,'folders');li.state.reply({result:{ok:true,saved:false,folders:['Back from CV Studio'],folder:''}});await new Promise(resolve=>setImmediate(resolve));
assert(secondSelect.children.some(option=>option.value==='Back from CV Studio'));
work=select.events.focus({isTrusted:true});li.state.reply({result:{ok:true,saved:false,folders:[],folder:''}});await work;
assert.deepEqual(secondSelect.children.map(option=>option.value),['']);assert.equal(secondSelect.disabled,false,'an empty authoritative catalog still offers Unfiled');
const app=await fixture(false),message={type:'CVSTUDIO_JOB_CAPTURE',id:'b'.repeat(32),record:{url:'https://www.linkedin.com/jobs/view/1234567890'}};
let replied;
assert.equal(app.state.onRuntime(message,{id:'foreign-extension'},()=>{throw Error('Foreign sender replied')}),false);
assert.equal(app.state.onRuntime(message,{id:'extension-id'},result=>replied=result),true);
assert.equal(app.state.delivered[0].channel,'a'.repeat(32));
app.send({type:'CVSTUDIO_LINKEDIN_CAPTURE_RESULT',id:message.id,channel:'c'.repeat(32),result:{ok:true}});assert.equal(replied,undefined);
app.send({type:'CVSTUDIO_LINKEDIN_CAPTURE_RESULT',id:message.id,channel:'a'.repeat(32),result:{ok:true,folder:'Priority'}});assert.equal(replied.folder,'Priority');
assert.equal(app.state.timers.size,0);
app.root.dataset.companionChannel='';app.state.onRuntime(message,{id:'extension-id'},result=>replied=result);assert(replied.error);
app.root.dataset.companionChannel='a'.repeat(32);app.root.dataset.companionActions='';app.state.onRuntime({...message,request:{action:'remove'}},{id:'extension-id'},result=>replied=result);assert.match(replied.error,/Update CV Studio/,'older app pages cannot interpret remove as a legacy add');app.root.dataset.companionActions='1';
app.root.dataset.companionChannel='a'.repeat(32);app.state.onRuntime(message,{id:'extension-id'},result=>replied=result);
let overlap;app.state.onRuntime({...message,id:'d'.repeat(32)},{id:'extension-id'},result=>overlap=result);assert(overlap.error);
for(const fn of [...app.state.timers.values()])fn();assert.match(replied.error,/Check its saved list/,'ambiguous saves are not automatically replayed');
const metadata=await fixture(false),metadataMessage={...message,request:{action:'folders'}};
metadata.state.onRuntime(metadataMessage,{id:'extension-id'},result=>replied=result);assert.match(replied.error,/Update CV Studio/,'older pages receive explicit guidance for metadata-only reads');
metadata.root.dataset.companionFolders='2';assert.equal(metadata.state.onRuntime(metadataMessage,{id:'extension-id'},result=>replied=result),true);
metadata.send({type:'CVSTUDIO_LINKEDIN_CAPTURE_RESULT',id:message.id,channel:'a'.repeat(32),result:{ok:true,folders:['Priority']}});assert.equal(replied.folders[0],'Priority');
const concurrent=await fixture(false);concurrent.root.dataset.companionFolders='2';
assert.equal(concurrent.state.onRuntime(metadataMessage,{id:'extension-id'},()=>{}),true);
assert.equal(concurrent.state.onRuntime({...metadataMessage,id:'c'.repeat(32)},{id:'extension-id'},()=>{}),true,'metadata from another LinkedIn tab can load concurrently');
assert.equal(concurrent.state.onRuntime({...message,id:'d'.repeat(32)},{id:'extension-id'},()=>{}),true,'read-only folder requests cannot block an explicit save');
concurrent.state.onRuntime({...message,id:'e'.repeat(32)},{id:'extension-id'},result=>replied=result);assert(replied.error,'concurrent writes remain blocked');
for(const digit of ['1','2','3','4','5'])assert.equal(concurrent.state.onRuntime({...metadataMessage,id:digit.repeat(32)},{id:'extension-id'},()=>{}),true);
concurrent.state.onRuntime({...metadataMessage,id:'6'.repeat(32)},{id:'extension-id'},result=>replied=result);assert(replied.error,'pending metadata requests remain bounded');
console.log('Capture content bridge: trusted explicit clicks, DOM/re-injection deduplication, readable success/errors, extension/channel correlation, busy and timeout non-replay passed');
})().catch(error=>{console.error(error);process.exitCode=1});
