const assert=require('assert/strict');
const {fixture}=require('./test_job_search_frontend');
const PAGE='https://www.linkedin.com/company/example/';
const links=f=>f.el('List').children.flatMap(row=>row.children[3]?.querySelectorAll('a') || []);
const incoming={url:'https://www.linkedin.com/jobs/view/6666666601',company:'Example Finance',company_url:PAGE,role:'Finance Manager',location:'Malaysia',description:'Observed job description',date_posted:''};
(async()=>{
  const stored=fixture();stored.state.records[0].company_url=PAGE;await stored.init();
  assert.equal(links(stored)[0].href,PAGE);assert.equal(links(stored)[0].target,'_blank');assert.equal(links(stored)[0].rel,'noopener noreferrer');
  assert.equal(links(stored)[0]['aria-label'],'Open Example Finance on LinkedIn');
  const old=fixture();old.state.records[0].hr={company:'Example Finance',company_url:PAGE,company_id:'4242',people:[],country:'',keywords:'HR',pages:1,scanned_at:'2026-11-05T00:00:00Z'};await old.init();assert.equal(links(old)[0].href,PAGE,'existing HR evidence provides a link without another read');
  const unrelated=fixture();unrelated.state.records[0].company_url='javascript:alert(1)';unrelated.state.records[0].hr={...old.state.records[0].hr,company:'Different Employer'};await unrelated.init();assert.equal(links(unrelated).length,0,'unsafe links and mismatched employer evidence stay plain text');
  for(const mode of ['search','full']){
    const f=fixture();f.el('SearchPages').value='1';
    f.state.onRPC=(m,reply)=>{
      if(m.action==='read'){const {company_url,...summary}=incoming;reply({jobs:[mode==='search'?incoming:summary],signature:'one',hasNext:false,atBottom:true});return true;}
      if(m.action==='jobFromLink'){reply(incoming);return true;}
    };
    await f.init();await f.el('SearchStart').click();
    if(mode==='full')await f.el('SearchResults').children[0].querySelectorAll('button').find(button=>button.textContent==='Read full ad').click();
    f.el('SearchSelectPage').checked=true;f.el('SearchSelectPage').handlers.change();await f.el('SearchAdd').click();
    assert.equal(f.state.records.find(row=>row.url===incoming.url).company_url,PAGE,mode+' capture retains the employer link through save');
    assert(links(f).some(link=>link.href===PAGE));
  }
  const form=fixture();form.state.onRPC=(m,reply)=>{if(m.action==='jobFromLink'){reply(incoming);return true;}};
  await form.init();form.el('url').value=incoming.url;await form.el('BrowserFill').click();
  await form.el('Form').handlers.submit({preventDefault(){}});
  assert.equal(form.state.records.find(row=>row.url===incoming.url).company_url,PAGE,'manual-fill draft retains hidden employer metadata');
  const direct=fixture();await direct.init();assert((await direct.capture(incoming)).ok);
  assert.equal(direct.state.records.find(row=>row.url===incoming.url).company_url,PAGE,'direct companion Add retains employer metadata');
  console.log('Company links: saved and HR-backed names, safe new-tab links, search/full/manual/direct capture persistence and hostile/stale evidence checks passed');
})().catch(error=>{console.error(error);process.exitCode=1});
