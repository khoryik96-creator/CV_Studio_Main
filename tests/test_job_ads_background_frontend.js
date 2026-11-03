const assert=require('assert/strict'),{fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function until(check){for(let i=0;i<150;i++){if(check())return;await tick();}assert(check(),'background workflow did not settle');}
const cards=f=>f.el('SearchResults').children;
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const reads=f=>f.calls.filter(call=>call.action==='jobFromLink');
async function search(f){await f.init();f.state.backgroundCapable=true;await f.el('SearchStart').click();}
(async()=>{
  const f=fixture();let held,active=0,maxActive=0;
  f.state.onRPC=(message,reply)=>{
    if(message.action!=='jobFromLink')return false;
    assert.equal(f.calls.filter(call=>call.action==='end').length,1,'search ends before full-ad retrieval');
    active++;maxActive=Math.max(active,maxActive);
    held=()=>{active--;reply({url:message.args.url,company:'Example Finance',role:'Finance Manager',description:'Full body',description_html:'<p><b>Full body</b></p>'});};return true;
  };
  const before=structuredClone(f.state.records);await search(f);await until(()=>held);
  assert.equal(cards(f).length,3,'all matching summaries appear before the first description arrives');
  assert.equal(f.el('SearchNext').disabled,true);assert.equal(f.el('SearchSelectPage').disabled,false);
  assert.equal(f.el('PreviewNext').disabled,false,'preview browsing stays usable');
  f.el('SearchResults').scrollTop=230;cards(f)[0].querySelectorAll('details')[0].open=true;
  f.el('SearchSelectPage').checked=true;f.el('SearchSelectPage').handlers.change();
  assert.match(f.el('SearchCount').textContent,/2 selected/);
  assert.equal(f.el('SearchAdd').disabled,false,'saving is available during background retrieval');
  assert.match(text(cards(f)[0]),/Loading full ad/);
  let release=held;held=null;release();await until(()=>held);
  assert.equal(f.el('SearchResults').scrollTop,230,'background redraw preserves the result-list position');
  assert(cards(f)[0].querySelectorAll('details')[0].open,'expanded ad content remains open across background redraws');
  assert.match(text(cards(f)[0]),/Full ad captured/);
  assert(f.el('PreviewContent').querySelectorAll('strong').length,'rich description is available in the preview');
  release=held;held=null;release();await until(()=>held);release=held;held=null;release();
  await until(()=>f.el('BackgroundStop').hidden);
  assert.equal(maxActive,1);assert.equal(reads(f).length,3);assert.deepEqual(f.state.records,before,'existing saved details remain unchanged');
  assert.match(f.el('BackgroundStatus').textContent,/3 of 3 full ads ready/);
  await cards(f)[0].querySelectorAll('button').find(button=>button.textContent==='View full ad').click();
  assert.equal(reads(f).length,3,'cached full-ad previews do not reopen LinkedIn');
  await f.el('SearchAdd').click();assert.equal(f.state.records.length,3);
  assert(f.state.records.filter(row=>row.id!==before[0].id).every(row=>row.description==='Full body'&&row.description_rich.length));

  const failed=fixture();failed.state.onRPC=(message,reply)=>{
    if(message.action!=='jobFromLink'||reads(failed).length!==1)return false;
    reply(null,{message:'Slow job details',code:'HR_AD_TIMEOUT'});return true;
  };
  await search(failed);await until(()=>failed.el('BackgroundStop').hidden);
  assert.equal(reads(failed).length,3,'one ad timeout does not block the remaining ads');
  assert.match(text(cards(failed)[0]),/Slow job details/);assert.match(text(cards(failed)[0]),/Search summary/);
  assert.match(failed.el('BackgroundStatus').textContent,/2 of 3.*1 could not load/);
  await failed.el('BackgroundStart').click();assert.equal(reads(failed).length,4,'resume retries only unfinished ads');
  assert.match(failed.el('BackgroundStatus').textContent,/3 of 3/);

  for(const action of ['stop','clear','foreground','foreground-status','new-search','pagehide']){
    const g=fixture();let replyRead,operation;
    g.state.onRPC=(message,reply)=>{
      if(message.action==='jobFromLink'&&!replyRead){operation=message.args.operation_id;replyRead=reply;return true;}
      if(message.action==='jobReadCancel'){
        assert.equal(message.args.operation_id,operation);reply(true);
        // A late success after Stop must not replace the summary.
        replyRead({url:reads(g)[0].args.url,company:'Late company',role:'Late role',description:'Late full body'});return true;
      }
      return false;
    };
    await search(g);await until(()=>replyRead);
    if(action==='stop')await g.el('BackgroundStop').click();
    if(action==='clear')await g.el('SearchClear').click();
    if(action==='foreground')await g.jobLeads().rpc('jobSearchTabs');
    if(action==='foreground-status')await g.jobLeads().rpc('jobStatus');
    if(action==='new-search'){g.state.backgroundCapable=false;await g.el('SearchStart').click();}
    if(action==='pagehide'){g.pagehide();await until(()=>g.el('BackgroundStop').hidden);}
    assert.equal(g.calls.filter(call=>call.action==='jobReadCancel').length,1);
    assert.equal(reads(g).length,1,'cancellation prevents queued reads');
    assert(!cards(g).some(card=>text(card).includes('Late full body')),'late cancelled results are ignored');
    if(action==='clear'){assert.equal(cards(g).length,0);assert.equal(g.el('BackgroundStatus').textContent,'');}
    if(action==='foreground-status')assert(g.calls.findIndex(call=>call.action==='jobReadCancel')<g.calls.map(call=>call.action).lastIndexOf('jobStatus'),'foreground status sees the companion after background cleanup');
    if(action==='foreground')assert(g.calls.findIndex(call=>call.action==='jobReadCancel')<g.calls.findIndex(call=>call.action==='jobSearchTabs'));
  }

  const access=fixture();access.state.onRPC=(message,reply)=>{
    if(message.action!=='jobFromLink')return false;
    reply(null,{message:'LinkedIn verification required',code:'HR_ACCESS_REQUIRED'});return true;
  };
  await search(access);await until(()=>access.el('BackgroundStop').hidden);
  assert.equal(reads(access).length,1,'access restrictions stop the entire queue');
  assert.match(access.el('BackgroundStatus').textContent,/verification required/);
  assert.equal(cards(access).length,3);
  console.log('Background job ads: list-first, sequential rich capture, usable selection, cache, saved-data preservation, retries, cancellation, late results and access-stop passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
