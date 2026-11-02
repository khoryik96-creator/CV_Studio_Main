const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert/strict');
// Synthetic job ads only. A recognized ad whose own wording mentions fraud or
// identity checks is not a LinkedIn restriction; real notices still stop.
const expected='https://www.linkedin.com/jobs/view/1234567890',companyURL='https://www.linkedin.com/company/example/';
const element=(innerText='',extra={})=>({innerText,getClientRects:()=>[{}],querySelector:()=>null,querySelectorAll:()=>[],getAttribute:()=>null,matches:()=>false,...extra});
const companyLink=element('Example Bank Berhad',{href:companyURL});
const company=element('Example Bank Berhad',{querySelectorAll:()=>[companyLink]});
const title=element('Fraud Analyst',{querySelector:()=>({href:expected})});
const panel=element('',{querySelector:()=>title,querySelectorAll:selector=>selector.includes('job-title')?[title]:selector.includes('company-name')?[company]:[]});
const state={main:'',panel:true,captcha:false};
const main=element('');Object.defineProperty(main,'innerText',{get:()=>state.main});
const document={body:main,
  querySelector:selector=>selector==='main'?main:selector.includes('captcha')&&state.captcha?element(''):null,
  querySelectorAll:selector=>state.panel&&selector.includes('jobs-details')?[panel]:[]};
const location={origin:'https://www.linkedin.com',pathname:'/jobs/view/1234567890',href:expected,search:''};
const context=vm.createContext({document,location,URL,URLSearchParams,Date,Number,getComputedStyle:()=>({visibility:'visible'})});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../vendor/linkedin-companion/reader.js'),'utf8'),context);const reader=context.SourcerReader;
const access=error=>/access or usage restriction|sign in|verification check/.test(error.message) && !error.cvstudioJobLoading;
const loading=error=>error.cvstudioJobLoading===true;
const adText='Fraud Analyst Example Bank Berhad. About the job: monitor unusual activity across card payments, run security verification for new accounts, '+
  'escalate when a customer has too many requests in a day. Once you have reached two years in the team, our research programme sets no limit on growth.';
for(const companyOnly of [true,false]){
  state.main=adText;
  const result=reader.readJob(expected,companyOnly);
  assert.equal(result.company,'Example Bank Berhad','an ad that mentions fraud/identity checks is read, not reported as a LinkedIn restriction');
  assert.equal(result.company_url,companyURL);
}
state.captcha=true;assert.throws(()=>reader.readJob(expected,true),access,'a captcha still stops a recognized ad read');state.captcha=false;
location.pathname='/checkpoint/challenge/';assert.throws(()=>reader.readJob(expected,true),access,'a checkpoint URL still stops the read');
location.pathname='/jobs/view/1234567890';
// With no recognized ad, page text is the only evidence of a restriction page.
state.panel=false;
for(const notice of ['You’ve reached the monthly limit for profile searches.','You have reached the commercial use limit on search.',
  'Your account is temporarily restricted.','We noticed unusual activity on your account.']){
  state.main=notice;assert.throws(()=>reader.readJob(expected,true),access,'restriction notice: '+notice);
}
state.main='You have reached the end of this page. Try another search. There is no limit to new jobs.';
assert.throws(()=>reader.readJob(expected,true),loading,'words in separate sentences do not combine into a usage-limit notice');
state.main='';assert.throws(()=>reader.readJob(expected,true),loading,'an empty unrecognized page is still loading');
console.log('Job ad access notices: ad wording is not a restriction, checkpoint/captcha stop, unrecognized-page notices stop, and sentence-bounded limits passed.');
