const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/content.js'),'utf8');
class Element{
  constructor(tag='div'){Object.assign(this,{tagName:tag,dataset:{},style:{},children:[],events:{},textContent:'',disabled:false})}
  addEventListener(name,fn){this.events[name]=fn} setAttribute(name,value){this[name]=value}
  append(...nodes){for(const node of nodes){node.parent=this;this.children.push(node)}} appendChild(node){this.append(node)}
  querySelector(){return this.children.find(node=>node.dataset.cvstudioJobControls)||null}
  remove(){this.parent.children=this.parent.children.filter(node=>node!==this)}
}
function fixture(linkedin){
  const events={},state={messages:[],observer:null,reply:null,delivered:[],timers:new Map(),sequence:0};
  const card=new Element(),root=new Element();root.dataset.companionChannel='a'.repeat(32);
  const document={body:new Element(),hidden:false,createElement:tag=>new Element(tag),addEventListener:(name,fn)=>events[name]=fn,getElementById:()=>root};
  const location={origin:linkedin?'https://www.linkedin.com':'http://127.0.0.1:5000',pathname:linkedin?'/jobs/search-results/':'/'};
  const window={addEventListener:(name,fn)=>events[name]=fn,postMessage:message=>state.delivered.push(message)};window.top=window;
  const chrome={runtime:{id:'extension-id',lastError:null,onMessage:{addListener:fn=>state.onRuntime=fn},sendMessage:(message,reply)=>{state.messages.push(message);state.reply=reply}}};
  const context=vm.createContext({window,document,location,chrome,Map,Set,MutationObserver:class{constructor(fn){state.observer=fn}observe(){}},
    setTimeout:fn=>{const id=++state.sequence;state.timers.set(id,fn);return id},clearTimeout:id=>state.timers.delete(id),
    SourcerReader:{jobTargets:()=>[{element:card,url:'https://www.linkedin.com/jobs/view/1234567890'}]}});
  vm.runInContext(source,context);
  return {state,card,root,chrome,events,window,location,context,send:message=>events.message({source:window,origin:location.origin,data:message})};
}
const li=fixture(true);assert.equal(li.card.children.length,1);let controls=li.card.children[0],button=controls.children[0];
const click=trusted=>button.events.click({isTrusted:trusted,preventDefault(){},stopPropagation(){}});
click(false);assert.equal(li.state.messages.length,0,'page-script clicks cannot capture');click(true);assert.equal(li.state.messages.length,1);
assert.equal(li.state.messages[0].kind,'sourcer_job_pick');assert.equal(button.disabled,true);
li.state.reply({error:'Connect CV Studio first'});assert.equal(button.disabled,false);assert.equal(controls.children[1].textContent,'Connect CV Studio first');
click(true);li.state.reply({result:{ok:true,folder:'Priority'}});assert.equal(button.textContent,'Added');assert.equal(controls.children[1].textContent,'CV Studio · Priority');
li.state.observer();for(const fn of [...li.state.timers.values()])fn();assert.equal(li.card.children.length,1,'DOM updates do not duplicate buttons');
vm.runInContext(source,li.context);assert.equal(li.card.children.length,1,'re-injection does not install a second observer/control');
const app=fixture(false),message={type:'CVSTUDIO_JOB_CAPTURE',id:'b'.repeat(32),record:{url:'https://www.linkedin.com/jobs/view/1234567890'}};
let replied;
assert.equal(app.state.onRuntime(message,{id:'foreign-extension'},()=>{throw Error('Foreign sender replied')}),false);
assert.equal(app.state.onRuntime(message,{id:'extension-id'},result=>replied=result),true);
assert.equal(app.state.delivered[0].channel,'a'.repeat(32));
app.send({type:'CVSTUDIO_LINKEDIN_CAPTURE_RESULT',id:message.id,channel:'c'.repeat(32),result:{ok:true}});assert.equal(replied,undefined);
app.send({type:'CVSTUDIO_LINKEDIN_CAPTURE_RESULT',id:message.id,channel:'a'.repeat(32),result:{ok:true,folder:'Priority'}});assert.equal(replied.folder,'Priority');
assert.equal(app.state.timers.size,0);
app.root.dataset.companionChannel='';app.state.onRuntime(message,{id:'extension-id'},result=>replied=result);assert(replied.error);
app.root.dataset.companionChannel='a'.repeat(32);app.state.onRuntime(message,{id:'extension-id'},result=>replied=result);
let overlap;app.state.onRuntime({...message,id:'d'.repeat(32)},{id:'extension-id'},result=>overlap=result);assert(overlap.error);
for(const fn of [...app.state.timers.values()])fn();assert.match(replied.error,/Check its saved list/,'ambiguous saves are not automatically replayed');
console.log('Capture content bridge: trusted explicit clicks, DOM/re-injection deduplication, readable success/errors, extension/channel correlation, busy and timeout non-replay passed');
