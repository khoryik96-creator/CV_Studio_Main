const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/cvstudio/email-verifier.js'),'utf8');
class Element {
  constructor(tag='div'){Object.assign(this,{tag,value:'',textContent:'',children:[],handlers:{},disabled:false,hidden:false,files:[]});}
  addEventListener(name,fn){this.handlers[name]=fn;} appendChild(node){this.children.push(node);return node;}
  append(...nodes){this.children.push(...nodes);} replaceChildren(...nodes){this.children=nodes;} click(){return this.handlers.click?.();}
}
function fixture(options={}){
  const ids=new Map(),calls=[],events={},exports=[],state={};
  const document={getElementById:id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id);},createElement:tag=>new Element(tag),addEventListener:(name,fn)=>events[name]=fn};
  const el=name=>document.getElementById('emailVerifier'+name);
  el('Mode').value='full';
  const context={document,window:{addEventListener:(name,fn)=>events[name]=fn},Date:options.Date || Date,WeakMap,location:{search:''},URLSearchParams,module:{exports:{}},Blob,URL:{createObjectURL:blob=>{exports.push(blob);return 'blob:synthetic';},revokeObjectURL(){}},setTimeout:options.setTimeout || (fn=>fn()),
    markTabRunning:()=>1,markTabDone:()=>{state.done=true;},markTabFailed:()=>{state.failed=true;},
    fetch:async(url,options)=>{calls.push({url,options});if(state.fetch)return state.fetch(url,options);const body=JSON.parse(options.body);return {ok:true,json:async()=>({ok:true,result:{email:body.email,status:body.email.startsWith('bad')?'invalid':'accepted',reason:'Synthetic check',flags:[],mode:body.mode,checked_at:'2026-10-26T00:00:00Z'}})};}};
  vm.runInNewContext(source,context);context.window.initEmailVerifier();
  return {el,calls,exports,state,api:context.module.exports,verifier:context.window.cvStudioEmailVerifier,Element,events};
}
async function main(){
  const {api}=fixture();
  assert.deepEqual(Array.from(api.parseText('Name@EXAMPLE.test; Name@example.test\nname@example.test\nnot-an-email').emails),['Name@EXAMPLE.test','name@example.test','not-an-email']);
  assert.equal(api.parseText('Name@EXAMPLE.test; Name@example.test').duplicates,1);
  assert.deepEqual(Array.from(api.parseText('"first,last"@example.test; a@example.test').emails),['"first,last"@example.test','a@example.test']);
  const csv='\uFEFFName,Email,Notes\r\n"Example, Person",a@example.test,"line one\nline two"\r\nSecond,not-an-email,"quote ""here"""\r\n';
  assert.deepEqual(Array.from(api.parseCSV(csv).emails),['a@example.test','not-an-email']);
  assert.deepEqual(Array.from(api.parseCSV('a@example.test\nb@example.test\n').emails),['a@example.test','b@example.test']);
  assert.deepEqual(Array.from(api.parseCSV('Email\n"""first,last""@example.test"').emails),['"first,last"@example.test']);
  for(const csv of ['Name,Contact\nA,a@example.test','Email,Email Address\na@example.test,b@example.test','Email\n"unfinished','Email\n"a@example.test"extra'])assert.throws(()=>api.parseCSV(csv));
  assert.throws(()=>api.parseText(Array.from({length:201},(_,i)=>'person'+i+'@example.test').join('\n')));
  assert.throws(()=>api.parseText('x'.repeat(321)));
  const exported=api.makeCSV([{email:'=formula@example.test',status:'unknown',reason:'  +unsafe, "quoted"',flags:['Role address'],suggestion:'',mode:'full',checked_at:''}]);
  assert(exported.includes('"\'=formula@example.test"')&&exported.includes('"\'  +unsafe, ""quoted"""'));

  const happy=fixture();happy.el('Input').value='a@example.test\nbad@example.test\na@example.test';
  await happy.el('Start').click();
  assert.equal(happy.calls.length,2);assert(happy.state.done);
  for(const call of happy.calls){assert.equal(call.url,'/email-verifier');assert.deepEqual(Object.keys(JSON.parse(call.options.body)),['email','mode']);}
  assert.equal(happy.el('Accepted').textContent,1);assert.equal(happy.el('Invalid').textContent,1);
  happy.el('Filter').value='invalid';happy.el('Filter').handlers.change();
  assert.equal(happy.el('Results').children.length,1);
  happy.el('Export').click();assert((await happy.exports[0].text()).includes('bad@example.test'));assert(!(await happy.exports[0].text()).includes('"a@example.test"'));
  happy.el('Clear').click();assert.equal(happy.el('Input').value,'');assert.equal(happy.el('Results').children.length,0);

  const stopped=fixture();let release;
  stopped.state.fetch=()=>new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>({ok:true,result:{status:'unknown',reason:'Blocked',flags:[]}})});});
  stopped.el('Input').value='a@example.test\nb@example.test';const run=stopped.el('Start').click();
  assert(stopped.el('Clear').disabled&&stopped.el('Input').disabled);stopped.el('Clear').click();
  stopped.el('Stop').click();release();await run;
  assert.equal(stopped.calls.length,1);assert.equal(stopped.el('Unknown').textContent,1);
  assert.equal(stopped.el('Total').textContent,'1 of 2 checked');assert(stopped.el('Message').textContent.startsWith('Stopped.'));

  const failed=fixture();failed.el('Input').value='a@example.test\nb@example.test';failed.state.fetch=async()=>{throw Error('Synthetic transport failure');};
  await failed.el('Start').click();assert.equal(failed.calls.length,1);assert(failed.state.failed);
  assert.equal(failed.el('Total').textContent,'0 of 2 checked');assert(failed.el('Start').disabled===false);

  const unconfirmed=fixture();unconfirmed.el('Input').value='person@example.test';
  unconfirmed.state.fetch=async()=>({ok:true,json:async()=>({ok:true,result:{status:'unknown',syntax:'ok',domain:'mx',mailbox:'unknown',reason:'Connection timed out.',flags:[]}})});
  await unconfirmed.el('Start').click();
  const row=unconfirmed.el('Results').children[0];
  assert.equal(row.children[1].children[0].textContent,'Unconfirmed');
  assert(row.children[2].children.some(n=>/Format: Passed.*Mail records: Found.*Mailbox: Unconfirmed/.test(n.textContent)));
  assert.equal(unconfirmed.el('Invalid').textContent,0);

  const importing=fixture();let load;
  importing.el('File').files=[{size:30,text:()=>new Promise(resolve=>{load=resolve;})}];
  const upload=importing.el('File').handlers.change();importing.el('Filter').handlers.change();
  assert(importing.el('Start').disabled&&importing.el('Input').disabled&&importing.el('Import').disabled);
  await importing.el('Start').click();assert.equal(importing.calls.length,0);
  load('Email\na@example.test');await upload;assert.equal(importing.el('Input').value,'a@example.test');assert(!importing.el('Start').disabled);

  const hostile=fixture();hostile.el('Input').value='<img onerror=alert(1)>@example.test';await hostile.el('Start').click();
  const address=hostile.el('Results').children[0].children[0].children[0];
  assert.equal(address.textContent,'<img onerror=alert(1)>@example.test');assert(!('innerHTML' in address));
  console.log('Email Verifier: parser, queue, stop, import races, filtering, CSV safety and text rendering passed.');
}
if(require.main===module)main().catch(error=>{console.error(error);process.exit(1);});
module.exports={fixture};
