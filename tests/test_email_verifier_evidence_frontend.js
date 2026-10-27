const assert=require('assert/strict');
const {fixture}=require('./test_email_verifier_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const answer=(patch={})=>({status:'unknown',reason:'Temporary server deferral.',mailbox_evidence:'unconfirmed',catch_all:'inconclusive',assessment:{level:'unconfirmed',label:'More evidence needed'},provider:'Microsoft 365',attempts:2,retryable:true,checked_at:'2099-01-01T00:00:00Z',...patch});
const reply=result=>({ok:true,json:async()=>({ok:true,result})});
function clockFixture(){
  let clock=1000000;const waits=[];
  class Clock extends Date {static now(){return clock;}}
  const f=fixture({Date:Clock,setTimeout:(fn,ms)=>{waits.push({fn,ms});}});
  return {...f,advance:async()=>{const wait=waits.shift();if(wait){clock+=wait.ms;wait.fn();await tick();}},waits};
}
async function main(){
  const f=clockFixture();f.el('Input').value='person@example.test';f.el('Mode').value='deep';
  f.state.fetch=async()=>reply(answer());
  const run=f.el('Start').click();await tick();
  assert.equal(f.calls.length,1);assert.match(f.el('Message').textContent,/Waiting 120 seconds/,'future server timestamp cannot extend our wait');
  for(let i=0;i<120;i++)await f.advance();await run;
  assert.equal(f.calls.length,2,'one delayed recheck only');
  assert(f.calls.every(call=>JSON.parse(call.options.body).mode==='deep'));
  assert(f.el('Recheck').disabled);
  const row=f.el('Results').children[0];assert(row.children[2].children.some(node=>node.textContent.includes('Previous check: Unconfirmed')));
  f.el('Export').click();const csv=await f.exports[0].text();assert(csv.includes('Mailbox evidence')&&csv.includes('More evidence needed'));

  const stopped=clockFixture();stopped.el('Mode').value='deep';stopped.el('Input').value='person@example.test';stopped.state.fetch=async()=>reply(answer());
  const stopRun=stopped.el('Start').click();await tick();stopped.el('Stop').click();await stopped.advance();await stopRun;
  assert.equal(stopped.calls.length,1);assert(stopped.el('Message').textContent.startsWith('Stopped.'));assert.equal(stopped.el('Unknown').textContent,1);

  const blocked=fixture();blocked.el('Mode').value='deep';blocked.el('Input').value='person@example.test';blocked.state.fetch=async()=>reply(answer({retryable:false,reason:'Policy block.'}));
  await blocked.el('Start').click();assert.equal(blocked.calls.length,1,'policy blocks are not automatically replayed');

  const manual=clockFixture();manual.el('Input').value='person@example.test';manual.state.fetch=async()=>reply(answer({status:'catch_all',retryable:false,reason:'Accepts random addresses.'}));
  await manual.el('Start').click();const manualRun=manual.el('Recheck').click();await tick();
  assert.equal(manual.el('Unknown').textContent,0,'previous result stays visible while waiting');
  manual.state.fetch=async()=>{throw Error('Fictional network loss');};
  for(let i=0;i<120;i++)await manual.advance();await manualRun;
  assert.equal(manual.el('CatchAll').textContent,1);assert.match(manual.el('Message').textContent,/Completed results have been kept/);

  const cardFixture=fixture(),card=new cardFixture.Element('article');
  const control=cardFixture.verifier.decorate(card,{name:'Example Person'});
  const wrap=card.children[0],input=wrap.children[0].children[0],button=wrap.children[1],result=wrap.children[2];
  assert.equal(cardFixture.calls.length,0,'showing a card does not contact a mail server');
  control.suggest('person@example.test');assert.equal(input.value,'person@example.test');
  let release;cardFixture.state.fetch=()=>new Promise(resolve=>{release=()=>resolve(reply(answer({status:'accepted',retryable:false})));});
  const checking=button.click();await button.click();assert.equal(cardFixture.calls.length,1);
  control.suggest('');release();await checking;assert.equal(input.value,'');assert.equal(result.children.length,0,'account change discards the old account result');
  input.value='manual@example.test';input.handlers.input();control.suggest('other@example.test');assert.equal(input.value,'manual@example.test','Apollo does not replace manually entered addresses');
  cardFixture.state.fetch=async()=>reply(answer({status:'catch_all',retryable:false,reason:'<script>fictional</script>'}));
  await button.click();assert(result.children.some(node=>node.textContent==='<script>fictional</script>'));assert(!('innerHTML' in result));
  let late;cardFixture.state.fetch=()=>new Promise(resolve=>{late=()=>resolve(reply(answer()));});
  const changed=button.click();input.value='new@example.test';input.handlers.input();late();await changed;
  assert.equal(result.children.length,0,'editing an address invalidates its pending check');
  console.log('Email evidence UI: bounded delayed rechecks, Stop, clock skew, retained results, CSV evidence and isolated HR-card checks passed.');
}
main().catch(error=>{console.error(error);process.exit(1);});
