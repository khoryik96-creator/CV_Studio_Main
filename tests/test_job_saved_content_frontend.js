const assert=require('assert/strict'),{fixture}=require('./test_job_search_frontend');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function until(check){for(let i=0;i<200;i++){if(check())return;await tick();}assert(check(),'saved-content workflow did not settle');}
const reads=f=>f.calls.filter(call=>call.action==='jobFromLink');
const text=node=>[node.textContent,...node.children.map(text)].join(' ');
async function search(f){await f.init();f.state.backgroundCapable=true;await f.el('SearchStart').click();await until(()=>f.el('BackgroundStop').hidden);}
(async()=>{
 const f=fixture();Object.assign(f.state.records[0],{description_truncated:false,description_rich:[{tag:'p',children:[{tag:'strong',children:[{text:'Saved full content'}]}]}]});
 const before=structuredClone(f.state.records);await search(f);
 assert.equal(reads(f).length,2,'an already saved full ad is not opened in another browser tab');
 assert(!reads(f).some(call=>call.args.url===before[0].url));assert.match(f.el('BackgroundStatus').textContent,/3 of 3 full ads ready/);
 const saved=f.el('SearchResults').children[1];assert.match(text(saved),/Saved full ad/);
 await saved.click();assert(f.el('PreviewContent').querySelectorAll('strong').length);assert.match(text(f.el('PreviewContent')),/Saved full content/);
 await f.el('PreviewRead').click();assert.equal(reads(f).length,2,'cached saved content opens without a fresh capture');assert.match(f.el('PreviewMeta').textContent,/Saved ad content/);
 assert.deepEqual(f.state.records,before);assert(!f.requests.some(request=>request.action==='save'));
 for(const patch of [{description_truncated:true},{description_truncated:undefined},{description:''},{deleted:true}]){
  const g=fixture();Object.assign(g.state.records[0],{description_truncated:false},patch);await search(g);
  assert.equal(reads(g).length,3,'excerpt/unknown/empty/trashed content does not count as a captured full ad');
 }
 const all=fixture(),template=all.state.records[0];
 all.state.records=['1111111110','1111111111','1111111112'].map((id,index)=>({...template,id:String(index+1).repeat(32),url:'https://www.linkedin.com/jobs/view/'+id,description:'Saved full body '+index,description_truncated:false}));
 await search(all);assert.equal(reads(all).length,0);assert.match(all.el('BackgroundStatus').textContent,/3 of 3 full ads ready/);assert(all.el('BackgroundStart').hidden);
 console.log('Saved full-ad reuse: exact URL and explicit complete flag, rich cached preview, readiness counts, no redundant browser reads/writes, excerpts/empty/unknown/trash excluded passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
