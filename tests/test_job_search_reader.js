const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8');
const url='https://www.linkedin.com/jobs/view/1234567890';
function fixture(){
  const state={date:'2026-10-02T00:15:00+08:00',next:0,scrolls:0,scope:true,restricted:false,empty:false,pendingCards:false,countText:''};
  const visible=(innerText,extra={})=>({innerText,getClientRects:()=>[{}],...extra});
  const role=visible('Finance Manager\nFinance Manager with verification'),company=visible('Example Finance'),where=visible('Penang');
  const card=visible('Finance Manager Example Finance Penang 2 weeks ago');
  const link=visible('Finance Manager',{href:url+'?trackingId=discard',closest:()=>card});
  const duplicate=visible('Duplicate label',{href:url,closest:()=>card});
  const evil=visible('Wrong origin',{href:'https://www.linkedin.com.attacker.invalid/jobs/view/222',closest:()=>card});
  const other=visible('Other',{href:'https://www.linkedin.com/jobs/view/999',closest:()=>({getClientRects:()=>[{}],querySelectorAll:()=>[link,other]})});
  card.querySelectorAll=selector=>selector==='a[href]'?[link,duplicate]:selector.includes('job-card-list__title')?[role]:selector.includes('primary-description')?[company]:selector.includes('metadata-item')?[where]:selector==='time[datetime]'?[visible('',{getAttribute:()=>state.date})]:[];
  const scope=visible(card.innerText,{scrollTop:0,clientHeight:500,scrollHeight:1500,contains:value=>value===scope,
    querySelectorAll:()=>state.empty||state.pendingCards?[]:[link,duplicate,evil,other],scrollBy:({top})=>{scope.scrollTop+=top;state.scrolls++}});
  const next=visible('Next',{disabled:false,getAttribute:()=> 'View next page',matches:()=>true,click:()=>state.next++});
  const pager=visible('Pagination',{querySelectorAll:()=>[next]});
  const main=visible('Current job search');
  Object.defineProperty(main,'innerText',{get:()=>state.restricted?'You have reached the commercial search limit':state.countText|| (state.empty?'No matching jobs found':'Current job search')});
  Object.defineProperty(scope,'innerText',{get:()=>state.countText|| (state.empty?'No matching jobs found':card.innerText)});
  const document={body:main,querySelector:selector=>selector==='main'?main:null,querySelectorAll:selector=>selector.includes('.jobs-search-pagination')?[pager]:selector.includes('.jobs-search-results-list')&&state.scope?[scope]:[]};
  const location={origin:'https://www.linkedin.com',href:'https://www.linkedin.com/jobs/search/?keywords=finance',pathname:'/jobs/search/',search:'?keywords=finance'};
  const context=vm.createContext({document,location,URL,URLSearchParams,Date,Number,getComputedStyle:()=>({visibility:'visible'})});
  vm.runInContext(source,context);return {reader:context.SourcerReader,state,scope,next,location};
}
const f=fixture();let result=f.reader.readJobSearch();
assert.equal(result.jobs.length,1,'duplicates, hostile hosts and ambiguous multi-job cards are excluded');
assert.equal(result.jobs[0].url,url);assert.equal(result.jobs[0].role,'Finance Manager');assert.equal(result.jobs[0].company,'Example Finance');
assert.equal(result.jobs[0].date_posted,'2026-10-02');assert(result.jobs[0].description_truncated);
assert.equal(result.hasNext,true);assert.equal(result.atBottom,false);
assert.throws(()=>f.reader.nextJobSearch('stale signature'));assert.equal(f.state.next,0);
assert(f.reader.nextJobSearch(result.signature));assert.equal(f.state.next,1);
assert(f.reader.scrollJobSearch(result.signature));assert.equal(f.state.scrolls,1);
f.scope.scrollTop=1000;assert.equal(f.reader.readJobSearch().atBottom,true);assert.equal(f.reader.scrollJobSearch(result.signature),false);
f.next.disabled=true;assert.equal(f.reader.readJobSearch().hasNext,false);assert.equal(f.reader.nextJobSearch(result.signature),false);
for(const date of ['2 weeks ago','2026-02-30','2026-10-02Tbad','2026-10-02T24:00:00Z']){f.state.date=date;assert.equal(f.reader.readJobSearch().jobs[0].date_posted,'',date)}
f.state.empty=true;assert.equal(f.reader.readJobSearch().empty,true);
f.state.scope=false;assert.equal(f.reader.readJobSearch().empty,true);f.state.empty=false;assert.equal(f.reader.readJobSearch().loading,true);
// Counts can render before the cards/results region. A positive count must
// keep polling rather than end the search as an empty result.
const loading=fixture();loading.state.pendingCards=true;
for(const scope of [true,false]){
  loading.state.scope=scope;
  for(const label of ['10 jobs','20 jobs','100 jobs','1,000 jobs','10,000 jobs','101 jobs','Found 120 jobs']){
    loading.state.countText=label;const snapshot=loading.reader.readJobSearch();
    assert.equal(snapshot.empty,false,label);assert.equal(snapshot.loading,true,label);
  }
  for(const label of ['0 jobs','Found 0 jobs','0 jobs found','No matching jobs found',"We couldn't find any jobs"]){
    loading.state.countText=label;const snapshot=loading.reader.readJobSearch();
    assert.equal(snapshot.empty,true,label);assert.equal(snapshot.loading,false,label);
  }
}
loading.state.scope=true;loading.state.countText='100 jobs';loading.state.pendingCards=false;
assert.equal(loading.reader.readJobSearch().jobs.length,1,'cards are read once they finish loading');
assert.equal(loading.reader.readJobSearch().empty,false);
f.state.restricted=true;assert.throws(()=>f.reader.readJobSearch());
f.state.restricted=false;f.location.pathname='/jobs/view/123';assert.throws(()=>f.reader.readJobSearch());
console.log('Job search DOM reader: scoped identities, duplicate/host/ambiguity rejection, summaries, exact dates, paging, scrolling, limits and challenges passed');
