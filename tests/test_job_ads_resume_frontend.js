// Background full-ad loading keeps going while the user works elsewhere, and
// Trash can be emptied for good. Synthetic companion and storage only.
const assert=require('assert/strict'),{fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function until(check,rounds=150){for(let i=0;i<rounds;i++){if(check())return;await tick();}assert(check(),'workflow did not settle');}
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const cards=f=>f.el('SearchResults').children;
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
const reads=f=>f.calls.filter(call=>call.action==='jobFromLink');
async function search(f){await f.init();f.state.backgroundCapable=true;await f.el('SearchStart').click();}
(async()=>{
  // The user's own companion action pauses loading; it then resumes by itself.
  const f=fixture();let first;
  f.state.onRPC=(message,reply)=>{
    if(message.action==='jobFromLink'&&!first){first=reply;return true;}
    if(message.action==='jobReadCancel'){reply(true);first(null,{message:'Stopped',code:'HR_STOPPED'});return true;}
    return false;
  };
  await search(f);await until(()=>first);
  await f.jobLeads().rpc('jobSearchTabs');
  assert.equal(reads(f).length,1,'the user action runs before any further ad is read');
  assert.match(f.el('BackgroundStatus').textContent,/Loading resumes automatically/);
  assert(f.el('BackgroundStop').hidden,'loading is paused while the action runs');
  await wait(1700);await until(()=>f.el('BackgroundStop').hidden && reads(f).length>=4,400);
  assert.equal(reads(f).length,4,'the paused ad and the two remaining ads are read after the action');
  assert.match(f.el('BackgroundStatus').textContent,/3 of 3 full ads ready/);

  // Stop is a deliberate choice: nothing resumes afterwards.
  const stopped=fixture();let held;
  stopped.state.onRPC=(message,reply)=>{
    if(message.action==='jobFromLink'&&!held){held=reply;return true;}
    if(message.action==='jobReadCancel'){reply(true);held(null,{message:'Stopped',code:'HR_STOPPED'});return true;}
    return false;
  };
  await search(stopped);await until(()=>held);
  await stopped.jobLeads().rpc('jobSearchTabs');await stopped.el('BackgroundStop').click();
  await wait(1700);await tick();
  assert.equal(reads(stopped).length,1,'Stop cancels the automatic resume');

  // An ad whose LinkedIn tab moved on is skipped; the rest still load.
  const changed=fixture();
  changed.state.onRPC=(message,reply)=>{
    if(message.action!=='jobFromLink'||reads(changed).length!==1)return false;
    reply(null,{message:'The selected job changed. Open its LinkedIn tab and try again.',code:'HR_AD_CHANGED'});return true;
  };
  await search(changed);await until(()=>changed.el('BackgroundStop').hidden);
  assert.equal(reads(changed).length,3,'one changed ad does not stop the queue');
  assert.match(text(cards(changed)[0]),/The selected job changed/);
  assert.match(changed.el('BackgroundStatus').textContent,/2 of 3.*1 could not load/);

  // A companion that is briefly busy with another short action is asked again
  // for the same ad; the queue neither stops nor skips it.
  const busy=fixture();let refused=0;
  busy.state.onRPC=(message,reply)=>{
    if(message.action!=='jobFromLink'||refused)return false;
    refused++;reply(null,{message:'Finish the current browser action before reading a job ad.',code:'HR_BUSY'});return true;
  };
  await search(busy);await wait(1100);await until(()=>busy.el('BackgroundStop').hidden,400);
  assert.equal(reads(busy).length,4,'the refused ad is read again, then the other two');
  assert.equal(new Set(reads(busy).map(call=>call.args.url)).size,3);
  assert.match(busy.el('BackgroundStatus').textContent,/3 of 3 full ads ready/);

  // Empty Trash permanently deletes exactly the trashed ads, after confirming.
  const trash=fixture();const purged=[];
  trash.state.records.push({...trash.state.records[0],id:'d'.repeat(32),url:'https://www.linkedin.com/jobs/view/4444444444',revision:5,deleted:true});
  trash.state.onRequest=data=>{
    if(data.action!=='purge')return null;
    purged.push(data.records);
    trash.state.records=trash.state.records.filter(row=>!data.records.some(selected=>selected.id===row.id));
    return {ok:true,json:async()=>({ok:true,deleted:data.records.length})};
  };
  await trash.init();
  assert.equal(trash.el('EmptyTrash').disabled,false);assert.equal(trash.el('EmptyTrash').textContent,'Empty Trash (1)');
  trash.state.allowDiscard=false;await trash.el('EmptyTrash').click();
  assert.equal(purged.length,0,'declining the confirmation deletes nothing');
  trash.state.allowDiscard=true;await trash.el('EmptyTrash').click();
  assert.deepEqual(purged,[[{id:'d'.repeat(32),revision:5}]],'only the trashed ad and its exact revision are sent');
  assert.equal(trash.state.records.length,1);assert.equal(trash.state.records[0].deleted,false,'saved ads outside Trash are kept');
  assert.match(trash.el('Message').textContent,/Trash emptied\. 1 ad was permanently deleted/);
  assert.equal(trash.el('EmptyTrash').disabled,true);assert.equal(trash.el('EmptyTrash').textContent,'Empty Trash');
  console.log('Job ads resume, skip, busy retry and Empty Trash passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
