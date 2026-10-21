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
function fixture(linkedin,layout='flex'){
  const events={},state={messages:[],observer:null,reply:null,delivered:[],timers:new Map(),sequence:0};
  const card=new Element(),details=new Element(),root=new Element();card.display=layout==='grid'?'grid':'flex';card.direction='row';details.display='flex';details.direction=layout==='unsupported'?'row':'column';
  details.append(new Element('p'),new Element('p'),new Element('p'));card.append(new Element('img'),details);
  root.dataset.companionChannel='a'.repeat(32);root.dataset.companionActions='1';
  const document={body:new Element(),hidden:false,querySelectorAll:()=>[],createElement:tag=>new Element(tag),addEventListener:(name,fn)=>events[name]=fn,getElementById:()=>root};
  const location={origin:linkedin?'https://www.linkedin.com':'http://127.0.0.1:5000',pathname:linkedin?'/jobs/search-results/':'/'};
  const window={addEventListener:(name,fn)=>events[name]=fn,postMessage:message=>state.delivered.push(message)};window.top=window;
  const chrome={runtime:{id:'extension-id',lastError:null,onMessage:{addListener:fn=>state.onRuntime=fn},sendMessage:(message,reply)=>{state.messages.push(message);state.reply=reply}}};
  const context=vm.createContext({window,document,location,chrome,Map,Set,MutationObserver:class{constructor(fn){state.observer=fn}observe(){}},
    setTimeout:fn=>{const id=++state.sequence;state.timers.set(id,fn);return id},clearTimeout:id=>state.timers.delete(id),
    getComputedStyle:el=>({display:el.display||'block',flexDirection:el.direction||'row'}),SourcerReader:{jobTargets:()=>[{element:card,url:'https://www.linkedin.com/jobs/view/1234567890'}]}});
  vm.runInContext(source,context);
  return {state,card,details,root,chrome,events,window,location,context,send:message=>events.message({source:window,origin:location.origin,data:message})};
}
(async()=>{
const li=fixture(true);assert.equal(li.card.children.length,2,'controls do not become a competing native flex-row column');let controls=li.details.children.at(-1),button=controls.children[0];
assert.equal(fixture(true,'grid').details.children.length,4,'grid cards also use their existing vertical text column');
assert.equal(fixture(true,'unsupported').details.children.length,3,'unrecognized horizontal-only layouts are left untouched');
const click=trusted=>button.events.click({isTrusted:trusted,preventDefault(){},stopPropagation(){}});
click(false);assert.equal(li.state.messages.length,0,'page-script clicks cannot capture');let work=click(true);assert.equal(li.state.messages.length,1);
assert.equal(li.state.messages[0].kind,'sourcer_job_pick');assert.equal(button.disabled,true);
li.state.reply({error:'Connect CV Studio first'});await work;assert.equal(button.disabled,false);assert.equal(controls.children[4].textContent,'Connect CV Studio first');
work=click(true);li.state.reply({result:{ok:true,saved:true,folder:'Priority'}});await work;assert.match(button.textContent,/^Added/);assert.equal(button.disabled,false);
work=click(true);assert.equal(li.state.messages.at(-1).operation,'remove');li.state.reply({result:{ok:true,saved:false,folder:'Priority'}});await work;assert.equal(button.textContent,'Add to CV Studio');assert.match(controls.children[4].textContent,/recoverable/);
const select=controls.children[1];work=select.events.focus({isTrusted:true});assert.equal(li.state.messages.at(-1).operation,'folders');li.state.reply({result:{ok:true,saved:false,folders:['Priority'],folder:'Priority'}});await work;assert.equal(select.value,'Priority');
select.value='';select.events.change({isTrusted:true,stopPropagation(){}});work=click(true);assert.equal(li.state.messages.at(-1).folder,'');li.state.reply({result:{ok:true,saved:true,folder:''}});await work;
controls.children[2].events.click({isTrusted:true,preventDefault(){},stopPropagation(){}});const editor=controls.children[3];assert.equal(editor.hidden,false);editor.children[0].value='SAP';
work=editor.children[1].events.click({isTrusted:true,preventDefault(){},stopPropagation(){}});assert.equal(li.state.messages.at(-1).operation,'create_folder');assert.equal(li.state.messages.at(-1).folder,'SAP');li.state.reply({result:{ok:true,saved:true,folder:'SAP',folders:['Priority','SAP']}});await work;assert.equal(select.value,'SAP');assert.equal(editor.hidden,true);
li.state.observer();for(const fn of [...li.state.timers.values()])fn();assert.equal(li.details.children.length,4,'DOM updates do not duplicate buttons');
vm.runInContext(source,li.context);assert.equal(li.details.children.length,4,'re-injection does not install a second observer/control');
const app=fixture(false),message={type:'CVSTUDIO_JOB_CAPTURE',id:'b'.repeat(32),record:{url:'https://www.linkedin.com/jobs/view/1234567890'}};
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
console.log('Capture content bridge: trusted explicit clicks, DOM/re-injection deduplication, readable success/errors, extension/channel correlation, busy and timeout non-replay passed');
})().catch(error=>{console.error(error);process.exitCode=1});
