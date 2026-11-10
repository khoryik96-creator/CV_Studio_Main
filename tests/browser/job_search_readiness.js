// Real Chromium + fictional LinkedIn DOM. All requests are intercepted locally.
// NODE_PATH points at a Playwright installation; no account/profile is used.
const assert=require('assert/strict'),fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../..');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.CVSTUDIO_CHROMIUM?{executablePath:process.env.CVSTUDIO_CHROMIUM}:{})});
  try{
    for(const modern of [false,true]){
      const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
      const card=modern?'<div role="button" componentkey="job-card-component-ref-1234567890"><p>Consultant</p><p>Example Company</p><p>Malaysia</p></div>':
        '<li class="jobs-search-results__list-item"><a class="job-card-list__title" href="https://www.linkedin.com/jobs/view/1234567890">Consultant</a><p class="job-card-container__primary-description">Example Company</p><p class="job-card-container__metadata-item">Malaysia</p></li>';
      const pager='<div class="jobs-search-pagination"><ul><li><button id="current" aria-label="Page 1" aria-current="page">1</button></li></ul><button id="next" aria-label="Next">Next</button></div>';
      const html='<main><section id="results" aria-busy="true" '+(modern?'componentkey="SearchResultsMainContent"':'class="jobs-search-results-list"')+'>'+card+(modern?pager:'')+'</section>'+(modern?'':pager)+'</main>';
      await page.route('**/*',route=>route.fulfill({contentType:'text/html',body:html}));
      await page.goto('https://www.linkedin.com/jobs/search/?keywords=consultant');
      await page.addScriptTag({content:fs.readFileSync(path.join(root,'vendor/linkedin-companion/reader.js'),'utf8')});
      await page.addScriptTag({content:fs.readFileSync(path.join(root,'vendor/cvstudio/job-search-walk.js'),'utf8')});
      const result=await page.evaluate(async()=>{
        const nativeTimeout=window.setTimeout.bind(window);window.setTimeout=(fn,ms,...args)=>nativeTimeout(fn,ms===350?1:ms,...args);
        let phase=0,reads=0,clicks=0;const kept=[],waiting=[],finished=[];
        const region=document.querySelector('#results'),current=document.querySelector('#current'),next=document.querySelector('#next');
        next.onclick=()=>{clicks++;phase=1;reads=0;region.setAttribute('aria-busy','true');current.textContent='2';current.setAttribute('aria-label','Page 2');};
        const rpc=async(action,args)=>{
          if(args.method==='readJobSearch'){
            if(++reads===46){region.setAttribute('aria-busy','false');if(phase)next.disabled=true;}
          }
          return SourcerReader[args.method](...args.values);
        };
        await cvStudioJobSearch.walk({rpc,run:'a'.repeat(32),tab:5,pages:2,check:()=>{},keep:s=>kept.push({page:s.page,signature:s.signature,loading:s.loading}),page:i=>finished.push(i),full:()=>false,waiting:s=>waiting.push(s)});
        return {kept,clicks,waiting,finished};
      });
      assert.deepEqual(result.finished,[0,1]);assert.deepEqual(result.kept.map(s=>s.page),[1,2]);
      assert.equal(result.kept[0].signature,result.kept[1].signature,'same promoted ad can occur on consecutive pages');
      assert.equal(result.clicks,1);assert(result.waiting.includes('results'));assert(result.waiting.includes('next'));
      assert(result.kept.every(s=>!s.loading));assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log('Chromium Jobs readiness passed for classic + keyed layouts: real active-page controls, 45 stale/busy reads, repeated promoted ad, one Next click, progress and no browser errors.');
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});
