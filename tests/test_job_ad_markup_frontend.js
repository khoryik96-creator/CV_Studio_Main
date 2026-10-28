const assert=require('assert/strict'),{fixture}=require('./test_job_search_frontend');
const markup='<strong>Example company</strong><br><ul><li></li><ul><li>Build systems.</li></ul></ul>';
const rich=[{tag:'strong',children:[{text:'Example company'}]},{tag:'ul',children:[{tag:'li',children:[{text:'Build systems.'}]}]}];
const turn=()=>new Promise(resolve=>setImmediate(resolve));
const preview=f=>f.el('List').querySelectorAll('button').find(button=>button.textContent==='Preview').click();
(async()=>{
 const f=fixture();f.state.records[0].description=markup;f.state.records[0].description_rich=[];const original=structuredClone(f.state.records);
 f.state.onRequest=data=>{assert.equal(data.action,'format_content');assert(data.render_markup);return {ok:true,json:async()=>({description:'Example company\nBuild systems.',description_rich:rich})}};
 await f.init();await preview(f);await turn();
 assert.equal(f.el('PreviewContent').querySelectorAll('strong').length,1);assert.equal(f.el('PreviewContent').querySelectorAll('li').length,1);
 assert.deepEqual(f.state.records,original);assert(f.requests.every(r=>r.action==='format_content'),'formatting never saves or alters records');assert.equal(f.requests.length,1,'repeated rendering shares bounded read-only work');
 const stale=fixture();stale.state.records[0].description=markup;stale.state.records[0].description_rich=[];let release;
 stale.state.onRequest=()=>new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>({description:'Old content',description_rich:rich})})});
 await stale.init();await preview(stale);assert(release);await stale.el('PreviewClose').click();
 stale.state.records[0].description='New current content';await stale.el('Refresh').click();await preview(stale);release();await turn();
 assert(!stale.el('PreviewContent').querySelectorAll('strong').length,'late formatting cannot replace a newer preview');
 assert(stale.el('PreviewContent').querySelectorAll('#text').some(n=>n.textContent==='New current content'));
 console.log('Literal job-ad HTML: safe rich display, clean lists, deduplicated read-only requests, unchanged records and stale-response protection passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
