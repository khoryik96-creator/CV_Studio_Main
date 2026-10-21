const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8');
const url='https://www.linkedin.com/jobs/view/1234567890';
const visible=(innerText='',extra={})=>({innerText,getClientRects:()=>[{}],getAttribute:()=>null,querySelectorAll:()=>[],...extra});
function card(id,patch={}){
  const state={id,...patch},ps=[visible('Finance Manager (Verified job)\nFinance Manager'),visible('Example Finance'),visible('Penang')];
  return visible('Finance Manager Example Finance Penang Posted 2 weeks ago',{state,ps,
    getAttribute:name=>name==='componentkey'?'job-card-component-ref-'+state.id:null,
    querySelector:()=>state.controls?visible(state.controls):null,
    querySelectorAll:selector=>selector==='p'?ps:selector==='a[href]'?(state.wrongLink?[{href:'https://www.linkedin.com/jobs/view/999'}]:[]):
      selector.startsWith('[componentkey')?(state.nested?[{getAttribute:()=> 'job-card-component-ref-999'}]:[]):[]});
}
const first=card('1234567890'),duplicate=card('1234567890'),bad=card('not-an-id'),ambiguous=card('7777777777',{nested:true}),wrong=card('8888888888',{wrongLink:true});
const state={cards:[first,duplicate,bad,ambiguous,wrong],next:0,scroll:0,about:true,stale:false,companyConflict:false,locations:['Malaysia'],filters:[]};
const pageButton=visible('1'),pager={querySelector:selector=>selector==='ul button[aria-label^="Page "]'?pageButton:null};
const next=visible('Next',{disabled:false,parentElement:pager,click:()=>state.next++});
const decoy=visible('Next',{parentElement:{querySelector:()=>null},click:()=>{throw Error('Clicked unrelated next')}});
const scope=visible('Current job search',{scrollTop:0,clientHeight:500,scrollHeight:1800,contains:el=>el===scope,
  querySelector:selector=>state.cards.find(card=>selector.includes('job-card-component-ref-'+card.state.id+'"')) || null,
  getAttribute:name=>name==='componentkey'?'SearchResultsMainContent':null,
  scrollBy:()=>{scope.scrollTop+=500;state.scroll++},
  querySelectorAll:selector=>selector==='button'?[decoy,next]:selector.startsWith('[role="button"]')?state.cards.filter(card=>!selector.includes('componentkey="job-card-component-ref-') || selector.includes('job-card-component-ref-'+card.state.id+'"')):[]});
const company=visible('Example Finance'),companyOther=visible('Other Company'),companyP=visible('Example Finance'),titleP=visible('Finance Manager'),locationP=visible('Penang · 2 weeks ago · 20 applicants');
const title=visible('Finance Manager',{href:url,closest:()=>titleP});
const header=visible('',{querySelectorAll:selector=>selector==='a[href*="/company/"]'?state.companyConflict?[company,companyOther]:[company,company]:selector==='p'?[companyP,titleP,locationP]:[]});
title.parentElement=header;
const showMore=visible('Show more');
const about=visible('About the job\nBuild partnerships.\nManage reporting.\nShow more',{
  innerHTML:'<h2>About the job</h2><ul><li>Build partnerships.</li><li>Manage reporting.</li></ul><button>Show more</button>',querySelectorAll:selector=>selector==='button'?[showMore]:[]});
const workspace=visible('Current jobs',{querySelectorAll:selector=>selector==='a[href]'?state.stale?[{...title,href:'https://www.linkedin.com/jobs/view/999'}]:[title]:
  selector==='[componentkey="JobDetails_AboutTheJob_1234567890"]'&&state.about?[about]:[]});
header.parentElement=workspace;
const location={origin:'https://www.linkedin.com',pathname:'/jobs/search-results/',href:'https://www.linkedin.com/jobs/search-results/?keywords=finance&currentJobId=1234567890',search:'?keywords=finance&currentJobId=1234567890'};
const searchHeader={querySelectorAll:()=>[
  ...state.locations.map(value=>visible(value,{querySelectorAll:selector=>selector==='[aria-label]'?[visible(value,{getAttribute:name=>name==='aria-label'?'Location '+value:null})]:[]})),
  ...state.filters.map(value=>visible(value,{getAttribute:name=>name==='aria-label'?value:null}))
]};
const document={body:workspace,querySelector:selector=>selector==='[componentkey="searchResultsHeaderComponent"]'?searchHeader:selector==='main#workspace'||selector==='main'?workspace:null,
  querySelectorAll:selector=>selector.includes('.jobs-search-results-list')?[scope]:[]};
const context=vm.createContext({document,location,URL,URLSearchParams,Date,Number,getComputedStyle:()=>({visibility:'visible'})});
vm.runInContext(source,context);const reader=context.SourcerReader;
let snapshot=reader.readJobSearch();assert.equal(snapshot.jobs.length,1,'canonical component identity, duplicates, malformed and mixed-job cards');
assert.equal(reader.jobTargets().length,1,'direct-add targets use only confirmed card identities');
assert.equal(reader.jobSearchContext().location,'Malaysia');state.locations=['Malaysia','Singapore'];assert.equal(reader.jobSearchContext().location,'','ambiguous locations cannot authorize initial normalization');state.locations=['Malaysia'];
state.filters=['Date posted','Company','How promoted jobs are ranked','How AI search works'];
assert.equal(reader.jobSearchContext().location,'Malaysia','other expandable filters/help controls cannot obscure the labelled location');
state.locations=[];assert.equal(reader.jobSearchContext().location,'','unrelated header controls never authorize a location');
state.locations=['Malaysia','Singapore'];assert.equal(reader.jobSearchContext().location,'','conflicting labelled locations still reject with unrelated filters present');
state.locations=['Malaysia'];state.filters=[];
first.state.controls='Add to CV Studio';first.innerText+=' Add to CV Studio';assert(!reader.readJobSearch().jobs[0].description.includes('Add to CV Studio'),'companion UI never enters saved ad content');
first.innerText+=' Viewed';assert(!reader.readJobSearch().jobs[0].description.includes('Add to CV Studio'),'controls inside the text column are excluded before native footer text too');assert(reader.readJobSearch().jobs[0].description.endsWith('Viewed'));
assert.equal(reader.readJobPick(url).company,'Example Finance');
assert.throws(()=>reader.readJobPick('https://www.linkedin.com/jobs/view/999'),'unobserved jobs are never captured');
assert.equal(snapshot.jobs[0].url,url);assert.equal(snapshot.jobs[0].role,'Finance Manager');assert.equal(snapshot.jobs[0].company,'Example Finance');assert.equal(snapshot.jobs[0].location,'Penang');assert.equal(snapshot.jobs[0].date_posted,'','relative dates are never guessed');
assert(snapshot.hasNext);assert(reader.nextJobSearch(snapshot.signature));assert.equal(state.next,1);
next.disabled=true;assert.equal(reader.nextJobSearch(snapshot.signature),false);assert.equal(state.next,1);
assert(reader.scrollJobSearch(snapshot.signature));assert.equal(state.scroll,1);
first.ps[0].innerText='';assert.equal(reader.readJobSearch().jobs.length,1,'loaded duplicate remains when one title is empty');
state.cards=[first];assert.equal(reader.readJobSearch().loading,true,'missing title never shifts company into the role field');
state.cards=Array.from({length:45},(_,i)=>card(String(2222222200+i)));assert.equal(reader.readJobSearch().jobs.length,40,'snapshot bound remains');
state.cards=[];
for(const label of ['10 jobs','20 jobs','100 jobs','1,000 jobs','10,000 jobs']){
  scope.innerText=label;const pending=reader.readJobSearch();
  assert.equal(pending.empty,false,label);assert.equal(pending.loading,true,label);
}
scope.innerText='0 jobs';assert.equal(reader.readJobSearch().empty,true,'modern zero count remains a true empty result');
scope.innerText='100 jobs';state.cards=[duplicate];assert.equal(reader.readJobSearch().jobs.length,1,'modern cards are read after loading');
let captured=reader.readJob(url);assert.equal(captured.role,'Finance Manager');assert.equal(captured.company,'Example Finance');assert.equal(captured.location,'Penang');
assert.equal(captured.description,'About the job\nBuild partnerships.\nManage reporting.');assert.equal(captured.description_truncated,true);assert(captured.description_html.includes('<ul>'));
location.pathname='/jobs/collections/recommended/';assert.equal(reader.jobTargets()[0].floating,true,'a confirmed selected collection ad gets the same direct-add control');location.pathname='/jobs/search-results/';
const previousText=about.innerText;about.innerText='About the job';
assert.throws(()=>reader.readJob(url),error=>error.cvstudioJobLoading===true,'a heading-only loading panel is never a successful content capture');about.innerText=previousText;
for(const patch of [{about:false},{stale:true},{companyConflict:true}]){
  Object.assign(state,{about:true,stale:false,companyConflict:false},patch);
  assert.throws(()=>reader.readJob(url),error=>error.cvstudioJobLoading===true,'stale or ambiguous detail fields must not mix');
}
location.search='?currentJobId=1234567890&currentJobId=999';assert.throws(()=>reader.readJob(url));
location.origin='https://attacker.invalid';assert.throws(()=>reader.readJobSearch());
console.log('Modern LinkedIn Jobs: rendered keyed cards, field ordering, canonical identity/deduplication/bounds, scoped pagination, selected-ad identity and content safety passed');
